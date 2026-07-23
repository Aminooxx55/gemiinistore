"""Payment handler — wallet pay, USDT TRC20/BEP20, Binance Pay."""
import io
import logging
from telegram import Update, InputFile
from telegram.ext import ContextTypes, CallbackQueryHandler
from database.db import get_db
from utils.helpers import (
    get_user, update_user_balance, record_transaction,
    make_qr_bytes, notify_admin, update_membership,
    get_product_unit_price,
)
from utils.keyboards import back_home_kb, confirm_purchase_kb
from utils.messages import payment_address_msg
from config import (
    USDT_POL_ADDRESS, USDT_BEP20_ADDRESS,
    BINANCE_PAY_ID, REFERRAL_REWARD,
    OrderStatus, SUPPORT_USERNAME,
)
from html import escape as html_escape

logger = logging.getLogger(__name__)


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
         payment_method, OrderStatus.PAID, coupon_id, discount)
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
            try:
                await context.bot.send_message(
                    chat_id=ref["referrer_id"],
                    text=f"🎉 <b>Referral Reward!</b>\n\nYour friend made their first purchase!\n"
                         f"You earned ${REFERRAL_REWARD:.2f} added to your wallet! 🎁",
                    parse_mode="HTML"
                )
            except Exception:
                logger.exception('Failed to send referral reward notification')


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
    unit_price = get_product_unit_price(p["name"], p["price"], qty, p["id"])
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
    total_str = f"${total:.2f}"
    await notify_admin(
        context,
        f"🛒 <b>New Order #{order_id}</b>\n"
        f"User: {html_escape(user['first_name'])} (<code>{user['telegram_id']}</code>)\n"
        f"Product: {html_escape(p['name'])} x{qty}\n"
        f"Total: {total_str}\n"
        f"Payment: Wallet ✅"
    )

    context.user_data.pop("pending", None)
    msg_text = (
        f"✅ <b>Order Placed Successfully!</b>\n\n"
        f"📦 <b>{p['name']}</b> x{qty}\n"
        f"💰 <b>Paid:</b> ${total:.2f} from wallet\n"
        f"🔖 <b>Order ID:</b> #{order_id}\n\n"
        f"⚡ <b>Autopilot Delivery:</b> If this product has instant stock, it has been delivered in the next message! Otherwise, the admin will deliver it shortly.\n\n"
        f"Use 👀 Orders to track status."
    )
    try:
        await update.callback_query.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=msg_text,
        parse_mode="HTML",
        reply_markup=back_home_kb()
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
    unit_price = get_product_unit_price(p["name"], p["price"], qty, p["id"])
    total = max(0.0, unit_price * qty - coupon_discount)

    # Create pending order
    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO orders
               (user_id, product_id, quantity, unit_price, total_price,
                payment_method, status, coupon_id, discount_amount)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (update.effective_user.id, prod_id, qty, unit_price, total,
             method.upper(), OrderStatus.PENDING, coupon_id, coupon_discount)
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
        caption=msg + f"\n\n🔖 <b>Order ID:</b> #{order_id}",
        parse_mode="HTML",
        reply_markup=_sent_payment_kb(order_id),
    )
 
    # Notify admin
    user = await get_user(update.effective_user.id)
    total_str = f"${total:.2f}"
    await notify_admin(
        context,
        f"💳 <b>Payment Pending #{order_id}</b>\n"
        f"User: {html_escape(user['first_name'])} (<code>{user['telegram_id']}</code>)\n"
        f"Product: {html_escape(p['name'])} x{qty}\n"
        f"Total: {total_str}\n"
        f"Method: {method.upper()}\n"
        f"Address: <code>{html_escape(address)}</code>"
    )
    context.user_data.pop("pending", None)


def _sent_payment_kb(order_id: int):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Sent Payment", callback_data=f"payment_sent_{order_id}")],
        [InlineKeyboardButton(f"🆘 Send Screenshot to {SUPPORT_USERNAME}", url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")],
        [InlineKeyboardButton("🏠 Back to Home",      callback_data="main_menu")],
    ])


async def cb_pay_pol(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_crypto_invoice(update, context, "pol", USDT_POL_ADDRESS)


async def cb_pay_bep20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_crypto_invoice(update, context, "bep20", USDT_BEP20_ADDRESS)


async def cb_pay_binance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _send_crypto_invoice(update, context, "binance", BINANCE_PAY_ID)


WAIT_BINANCE_REF = 112233

async def cb_payment_sent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User clicked 'I've Sent Payment'."""
    await update.callback_query.answer()
    order_id = int(update.callback_query.data.split("_")[2])
    user = await get_user(update.effective_user.id)

    # Check if the payment method for this order is BINANCE
    async with get_db() as db:
        cur = await db.execute("SELECT payment_method FROM orders WHERE id=?", (order_id,))
        order = await cur.fetchone()

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    from telegram.ext import ConversationHandler

    if order:
        pm = dict(order).get("payment_method")
        if pm in ("BINANCE", "POL"):
            method_name = "Binance Pay Transaction ID" if pm == "BINANCE" else "POL Transaction Hash (TxID)"
            hint = "long number or starts with <code>P_</code>" if pm == "BINANCE" else "the blockchain transaction hash"
            await update.callback_query.edit_message_caption(
                caption=(
                    f"⏳ <b>Auto-Verification</b>\n\n"
                    f"Please type and send your <b>{method_name}</b> now.\n\n"
                    f"💡 This is usually a {hint}."
                ),
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel Verification", callback_data="cancel_binance_verify")]
                ]),
            )
            context.user_data["verify_order_id"] = order_id
            return WAIT_BINANCE_REF

    await update.callback_query.edit_message_caption(
        caption=(
            f"⏳ <b>Payment Submitted!</b>\n\n"
            f"Order #{order_id} is pending verification.\n\n"
            f"📸 <b>Please send the screenshot of your payment to {SUPPORT_USERNAME} now!</b>"
        ),
        parse_mode="HTML",
        reply_markup=back_home_kb(),
    )
    # Ping admin
    await notify_admin(
        context,
        f"🔔 <b>User Confirmed Payment #{order_id}</b>\n"
        f"User: {html_escape(user['first_name'])} (<code>{user['telegram_id']}</code>)\n"
        f"Please verify and approve via /admin"
    )
    return ConversationHandler.END


async def recv_binance_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    
    order_id = context.user_data.get("verify_order_id")
    if not order_id:
        return ConversationHandler.END

    ref_id = update.message.text.strip()
    
    # 1. Fetch order details to know the expected amount
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        order = await cur.fetchone()
        
    if not order:
        await update.message.reply_text("❌ Order not found.", reply_markup=back_home_kb())
        context.user_data.pop("verify_order_id", None)
        return ConversationHandler.END
        
    order = dict(order)
    expected_amount = order["total_price"]
    
    # Show "verifying..." message
    verifying_msg = await update.message.reply_text(
        "⏳ <b>Verifying transaction on Binance Pay...</b>\nThis may take up to 10 seconds.",
        parse_mode="HTML"
    )
    
    from utils.binance_pay import verify_transaction, verify_spot_deposit
    try:
        if order["payment_method"] == "POL":
            success = await verify_spot_deposit(ref_id, expected_amount, order_id, network="MATIC")
        else:
            success = await verify_transaction(ref_id, expected_amount, order_id)
    except Exception:
        logger.exception(f"Error during verification for order {order_id}")
        success = False
        
    if success:
        # Update order status to paid
        async with get_db() as db:
            await db.execute("UPDATE orders SET status=? WHERE id=?", (OrderStatus.PAID, order_id))
            # Deliver order
            from utils.helpers import process_order_delivery
            await process_order_delivery(db, context.bot, order_id)
            await db.commit()
            
        # Notify user
        await verifying_msg.delete()
        await update.message.reply_text(
            f"✅ <b>Payment Verified Successfully!</b>\n\n"
            f"💰 <b>Amount Verified:</b> <code>${expected_amount:.2f}</code>\n"
            f"🔖 <b>Transaction ID:</b> <code>{ref_id}</code>\n\n"
            f"⚡ Your product has been delivered above! Enjoy!",
            parse_mode="HTML",
            reply_markup=back_home_kb()
        )
        
        # Notify admin of auto sale
        user = await get_user(update.effective_user.id)
        total_str = f"${expected_amount:.2f}"
        await notify_admin(
            context,
            f"🎉 <b>Automated Binance Pay Sale!</b>\n"
            f"Order #{order_id} verified automatically!\n"
            f"User: {html_escape(user['first_name'])} (<code>{user['telegram_id']}</code>)\n"
            f"Total: {total_str}\n"
            f"TxID: <code>{html_escape(ref_id)}</code>"
        )
        
        context.user_data.pop("verify_order_id", None)
        return ConversationHandler.END
    else:
        # Verification failed
        await verifying_msg.delete()
        await update.message.reply_text(
            "❌ <b>Verification Failed!</b>\n\n"
            "We couldn't find a matching transaction for that ID/Reference, "
            "or the payment amount/currency did not match your order.\n\n"
            "✍️ <b>Please enter the correct Transaction ID, or click Cancel below:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Verification", callback_data="cancel_binance_verify")]])
        )
        return WAIT_BINANCE_REF


async def cb_cancel_binance_verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    await update.callback_query.answer()
    
    # Clear user data states
    context.user_data.pop("verify_order_id", None)
    context.user_data.pop("awaiting_qty_for", None)
    context.user_data.pop("coupon_for", None)
    context.user_data.pop("pending", None)

    data = update.callback_query.data
    
    # Route to appropriate handlers
    if data == "main_menu" or data == "cancel_binance_verify":
        from handlers.start import cb_main_menu
        await cb_main_menu(update, context)
    elif data == "shop_home":
        from handlers.shop import cb_shop_home
        await cb_shop_home(update, context)
    elif data.startswith("cat_"):
        from handlers.shop import cb_category
        await cb_category(update, context)
    elif data.startswith("prod_"):
        from handlers.shop import cb_product_detail
        await cb_product_detail(update, context)
    elif data == "support":
        from handlers.start import cb_support
        await cb_support(update, context)
    else:
        from handlers.start import cb_main_menu
        await cb_main_menu(update, context)

    return ConversationHandler.END


async def cb_cancel_binance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    # Clear user data states
    context.user_data.pop("verify_order_id", None)
    context.user_data.pop("awaiting_qty_for", None)
    context.user_data.pop("coupon_for", None)
    context.user_data.pop("pending", None)

    # Route start command
    from handlers.start import cmd_start
    await cmd_start(update, context)
    return ConversationHandler.END



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
    unit_price = get_product_unit_price(p["name"], p["price"], qty, p["id"])
    total = max(0.0, unit_price * qty - coupon_discount)

    # Create pending order
    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO orders
               (user_id, product_id, quantity, unit_price, total_price,
                payment_method, status, coupon_id, discount_amount)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (update.effective_user.id, prod_id, qty, unit_price, total,
             "CRYPTOMUS", OrderStatus.PENDING, coupon_id, coupon_discount)
        )
        order_id = cur.lastrowid
        await db.commit()

    unique_ref = f"order_{order_id}_{int(time.time())}"

    try:
        payment_url, payment_uuid = await create_cryptomus_invoice(total, unique_ref)
    except Exception:
        logger.exception(f"Cryptomus invoice creation failed for order {order_id}")
        # Delete pending order on failure
        async with get_db() as db:
            await db.execute("DELETE FROM orders WHERE id=?", (order_id,))
            await db.commit()
        try:
            await update.callback_query.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="❌ <b>Payment Gateway Error</b>\n\nUnable to generate payment link at this moment. Please try again later.",
            parse_mode="HTML",
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

    try:
        await update.callback_query.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=f"⚡ <b>Auto Crypto Invoice Generated!</b>\n\n"
             f"📦 <b>Product:</b> {p['name']}\n"
             f"🔢 <b>Quantity:</b> {qty}\n"
             f"💰 <b>Total:</b> ${total:.2f}\n\n"
             f"Click the button below to pay via USDT, Binance Pay, etc.\n"
             f"The bot will detect your payment automatically within 1 minute.",
        parse_mode="HTML",
        reply_markup=cryptomus_kb
    )


def register_payment_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_pay_wallet,    pattern=r"^pay_wallet_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_pol,     pattern=r"^pay_pol_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_bep20,     pattern=r"^pay_bep20_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_pay_binance,   pattern=r"^pay_binance_\d+_\d+$"))
    from telegram.ext import ConversationHandler, MessageHandler, filters, CommandHandler
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_payment_sent, pattern=r"^payment_sent_\d+$")],
        states={
            WAIT_BINANCE_REF: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_binance_ref)]
        },
        fallbacks=[
            CommandHandler("start", cb_cancel_binance_command),
            CallbackQueryHandler(cb_cancel_binance_verify, pattern="^.*$")
        ],
        per_chat=True, per_user=True
    ))
    app.add_handler(CallbackQueryHandler(cb_pay_cryptomus,  pattern=r"^pay_cryptomus_\d+_\d+$"))
