"""Payment handler — wallet pay, USDT TRC20/BEP20, Binance Pay."""
import io
from telegram import Update, InputFile
from telegram.ext import ContextTypes, CallbackQueryHandler
from database.db import get_db
from utils.helpers import (
    get_user, update_user_balance, record_transaction,
    make_qr_bytes, notify_admin, update_membership,
    get_product_unit_price,
)
from utils.keyboards import back_home_kb, confirm_purchase_kb
from utils.messages import payment_address_msg, escape_md
from config import (
    USDT_TRC20_ADDRESS, USDT_BEP20_ADDRESS,
    BINANCE_PAY_ID, REFERRAL_REWARD,
)


async def _finalize_order(db, user_id: int, product_id: int, qty: int,
                           unit_price: float, total: float,
                           payment_method: str, coupon_id: int = None,
                           discount: float = 0.0) -> int:
    """Insert order and update product stock/sold. Returns order_id."""
    cur = await db.execute(
        """INSERT INTO orders
           (user_id, product_id, quantity, unit_price, total_price,
            payment_method, status, coupon_id, discount_amount)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (user_id, product_id, qty, unit_price, total,
         payment_method, "paid", coupon_id, discount)
    )
    order_id = cur.lastrowid

    # Update product stock
    await db.execute(
        "UPDATE products SET sold=sold+?, stock=CASE WHEN stock=-1 THEN -1 ELSE stock-? END WHERE id=?",
        (qty, qty, product_id)
    )

    # Update coupon uses
    if coupon_id:
        await db.execute(
            "UPDATE coupons SET uses_count=uses_count+1 WHERE id=?", (coupon_id,)
        )
        await db.execute(
            "INSERT INTO coupon_uses (coupon_id, user_id, order_id) VALUES (?,?,?)",
            (coupon_id, user_id, order_id)
        )

    # Update user total_spent
    await db.execute(
        "UPDATE users SET total_spent=total_spent+? WHERE telegram_id=?",
        (total, user_id)
    )

    await db.commit()
    return order_id


async def _give_referral_reward(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Give referral reward to referrer on first purchase."""
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM referrals WHERE referred_id=? AND reward_given=0",
            (user_id,)
        )
        ref = await cur.fetchone()
        if ref:
            await db.execute(
                "UPDATE users SET balance=balance+? WHERE telegram_id=?",
                (REFERRAL_REWARD, ref["referrer_id"])
            )
            await db.execute(
                "UPDATE referrals SET reward_given=1 WHERE id=?", (ref["id"],)
            )
            await db.commit()
            await record_transaction(
                ref["referrer_id"], REFERRAL_REWARD, "referral_reward",
                f"Referral reward for user {user_id}"
            )
            ref_reward_str = escape_md(f"${REFERRAL_REWARD:.2f}")
            try:
                await context.bot.send_message(
                    chat_id=ref["referrer_id"],
                    text=f"🎉 *Referral Reward\\!*\n\nYour friend made their first purchase\\!\n"
                         f"You earned {ref_reward_str} added to your wallet\\! 🎁",
                    parse_mode="MarkdownV2"
                )
            except Exception:
                pass


# ── Wallet Payment ────────────────────────────────────────────────────────────
async def cb_pay_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    prod_id, qty = int(parts[2]), int(parts[3])

    user = await get_user(update.effective_user.id)
    pending = context.user_data.get("pending", {})
    coupon_id = pending.get("coupon_id")
    coupon_discount = pending.get("coupon_discount", 0.0)

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    if not p:
        await update.callback_query.answer("Product not found!", show_alert=True)
        return

    p = dict(p)
    unit_price = get_product_unit_price(p["name"], p["price"], qty)
    total = max(0.0, unit_price * qty - coupon_discount)

    if user["balance"] < total:
        shortage = total - user["balance"]
        await update.callback_query.answer(
            f"❌ Insufficient balance! You need ${shortage:.2f} more.", show_alert=True
        )
        return

    # Deduct balance
    await update_user_balance(update.effective_user.id, -total)
    await record_transaction(
        update.effective_user.id, -total, "purchase",
        f"Purchase: {p['name']} x{qty}", None
    )

    async with get_db() as db:
        order_id = await _finalize_order(
            db, update.effective_user.id, prod_id, qty,
            unit_price, total, "Wallet", coupon_id, coupon_discount
        )
        from utils.helpers import process_order_delivery
        await process_order_delivery(db, context.bot, order_id)

    await update_membership(update.effective_user.id)
    await _give_referral_reward(update.effective_user.id, context)

    # Notify admin
    total_str = escape_md(f"${total:.2f}")
    await notify_admin(
        context,
        f"🛒 *New Order \\#{order_id}*\n"
        f"User: {escape_md(user['first_name'])} \\(`{user['telegram_id']}`\\)\n"
        f"Product: {escape_md(p['name'])} x{qty}\n"
        f"Total: {total_str}\n"
        f"Payment: Wallet ✅"
    )

    context.user_data.pop("pending", None)
    await update.callback_query.edit_message_text(
        f"✅ *Order Placed Successfully\\!*\n\n"
        f"📦 *{escape_md(p['name'])}* x{qty}\n"
        f"💰 *Paid:* {total_str} from wallet\n"
        f"🔖 *Order ID:* \\#{order_id}\n\n"
        f"⚡ *Autopilot Delivery:* If this product has instant stock, it has been delivered in the next message\\! Otherwise, the admin will deliver it shortly\\.\n\n"
        f"Use 👀 Orders to track status\\.",
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )


# ── Crypto Payment (shared logic) ─────────────────────────────────────────────
async def _send_crypto_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                method: str, address: str):
    parts = update.callback_query.data.split("_")
    prod_id, qty = int(parts[2]), int(parts[3])

    if not address:
        await update.callback_query.answer(
            "❌ This payment method is not configured yet.", show_alert=True
        )
        return

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    if not p:
        return

    p = dict(p)
    pending = context.user_data.get("pending", {})
    coupon_discount = pending.get("coupon_discount", 0.0)
    coupon_id = pending.get("coupon_id")
    unit_price = get_product_unit_price(p["name"], p["price"], qty)
    total = max(0.0, unit_price * qty - coupon_discount)

    # Create pending order
    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO orders
               (user_id, product_id, quantity, unit_price, total_price,
                payment_method, status, coupon_id, discount_amount)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (update.effective_user.id, prod_id, qty, unit_price, total,
             method.upper(), "pending", coupon_id, coupon_discount)
        )
        order_id = cur.lastrowid
        if coupon_id:
            await db.execute(
                "UPDATE coupons SET uses_count=uses_count+1 WHERE id=?", (coupon_id,)
            )
            await db.execute(
                "INSERT INTO coupon_uses (coupon_id, user_id, order_id) VALUES (?,?,?)",
                (coupon_id, update.effective_user.id, order_id)
            )
        await db.commit()

    # Generate QR
    qr_bytes = make_qr_bytes(address)

    await update.callback_query.answer()
    await update.callback_query.delete_message()

    msg = payment_address_msg(method, total, address)
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=InputFile(io.BytesIO(qr_bytes), filename="qr.png"),
        caption=msg + f"\n\n🔖 *Order ID:* \\#{order_id}",
        parse_mode="MarkdownV2",
        reply_markup=_sent_payment_kb(order_id),
    )

    # Notify admin
    user = await get_user(update.effective_user.id)
    total_str = escape_md(f"${total:.2f}")
    await notify_admin(
        context,
        f"💳 *Payment Pending \\#{order_id}*\n"
        f"User: {escape_md(user['first_name'])} \\(`{user['telegram_id']}`\\)\n"
        f"Product: {escape_md(p['name'])} x{qty}\n"
        f"Total: {total_str}\n"
        f"Method: {method.upper()}\n"
        f"Address: `{escape_md(address)}`"
    )
    context.user_data.pop("pending", None)


def _sent_payment_kb(order_id: int):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Sent Payment", callback_data=f"payment_sent_{order_id}")],
        [InlineKeyboardButton("🆘 Send Screenshot to @lovable47", url="https://t.me/lovable47")],
        [InlineKeyboardButton("🏠 Back to Home",      callback_data="main_menu")],
    ])


async def cb_pay_trc20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_crypto_invoice(update, context, "trc20", USDT_TRC20_ADDRESS)


async def cb_pay_bep20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_crypto_invoice(update, context, "bep20", USDT_BEP20_ADDRESS)


async def cb_pay_binance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_crypto_invoice(update, context, "binance", BINANCE_PAY_ID)


async def cb_payment_sent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User clicked 'I've Sent Payment'."""
    await update.callback_query.answer()
    order_id = int(update.callback_query.data.split("_")[2])
    user = await get_user(update.effective_user.id)

    await update.callback_query.edit_message_caption(
        caption=(
            f"⏳ *Payment Submitted\\!*\n\n"
            f"Order \\#{order_id} is pending verification\\.\n\n"
            f"📸 *Please send the screenshot of your payment to @lovable47 now\\!*"
        ),
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )
    # Ping admin
    await notify_admin(
        context,
        f"🔔 *User Confirmed Payment \\#{order_id}*\n"
        f"User: {escape_md(user['first_name'])} \\(`{user['telegram_id']}`\\)\n"
        f"Please verify and approve via /admin"
    )


import time
from utils.cryptomus import create_cryptomus_invoice


async def cb_pay_cryptomus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    prod_id, qty = int(parts[2]), int(parts[3])

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    if not p:
        await update.callback_query.answer("Product not found!", show_alert=True)
        return

    p = dict(p)
    pending = context.user_data.get("pending", {})
    coupon_discount = pending.get("coupon_discount", 0.0)
    coupon_id = pending.get("coupon_id")
    unit_price = get_product_unit_price(p["name"], p["price"], qty)
    total = max(0.0, unit_price * qty - coupon_discount)

    # Create pending order
    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO orders
               (user_id, product_id, quantity, unit_price, total_price,
                payment_method, status, coupon_id, discount_amount)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (update.effective_user.id, prod_id, qty, unit_price, total,
             "CRYPTOMUS", "pending", coupon_id, coupon_discount)
        )
        order_id = cur.lastrowid
        await db.commit()

    unique_ref = f"order_{order_id}_{int(time.time())}"

    try:
        payment_url, payment_uuid = await create_cryptomus_invoice(total, unique_ref)
    except Exception as e:
        # Delete pending order on failure
        async with get_db() as db:
            await db.execute("DELETE FROM orders WHERE id=?", (order_id,))
            await db.commit()
        await update.callback_query.edit_message_text(
            "❌ *Payment Gateway Error*\n\nUnable to generate payment link at this moment. Please try again later.",
            parse_mode="MarkdownV2",
            reply_markup=back_home_kb()
        )
        return

    # Store Cryptomus UUID in admin_note
    async with get_db() as db:
        await db.execute(
            "UPDATE orders SET admin_note=? WHERE id=?",
            (payment_uuid, order_id)
        )
        await db.commit()

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    cryptomus_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pay Now (Open Checkout)", url=payment_url)],
        [InlineKeyboardButton("🏠 Back to Home", callback_data="main_menu")]
    ])

    total_str = escape_md(f"${total:.2f}")
    await update.callback_query.edit_message_text(
        f"⚡ *Auto Crypto Invoice Generated\\!*\n\n"
        f"📦 *Product:* {escape_md(p['name'])}\n"
        f"🔢 *Quantity:* {qty}\n"
        f"💰 *Total:* {total_str}\n\n"
        f"Click the button below to pay via USDT, Binance Pay, etc\\.\n"
        f"The bot will detect your payment automatically within 1 minute\\.",
        parse_mode="MarkdownV2",
        reply_markup=cryptomus_kb
    )


def register_payment_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_pay_wallet,    pattern=r"^pay_wallet_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_trc20,     pattern=r"^pay_trc20_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_bep20,     pattern=r"^pay_bep20_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_binance,   pattern=r"^pay_binance_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_payment_sent,  pattern=r"^payment_sent_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_cryptomus,  pattern=r"^pay_cryptomus_\d+_\d+$"))
