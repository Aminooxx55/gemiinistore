"""Wallet handler — balance, top-up requests, transaction history."""
from telegram import Update
from telegram.ext import (
    ContextTypes, CallbackQueryHandler, MessageHandler,
    filters, ConversationHandler,
)
from database.db import get_db
from utils.helpers import get_user, make_qr_bytes, notify_admin
from utils.keyboards import wallet_kb, topup_method_kb, topup_confirm_kb, back_home_kb
from utils.messages import escape_md
from config import USDT_TRC20_ADDRESS, USDT_BEP20_ADDRESS, BINANCE_PAY_ID
import io
from telegram import InputFile

AWAIT_TOPUP_AMOUNT = 10


async def cb_wallet_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user = await get_user(update.effective_user.id)
    bal_str = escape_md(f"${user['balance']:.2f}")
    spent_str = escape_md(f"${user['total_spent']:.2f}")
    message = update.callback_query.message

    from config import GEMINI_LOGO_URL
    await message.delete()

    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=GEMINI_LOGO_URL,
        caption=(
            f"💵 *My Wallet*\n\n"
            f"💰 *Balance:* {bal_str}\n"
            f"📊 *Total Spent:* {spent_str}\n\n"
            f"Top up your wallet to pay instantly\\!"
        ),
        parse_mode="MarkdownV2",
        reply_markup=wallet_kb(),
    )


async def cb_topup_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    message = update.callback_query.message
    from config import GEMINI_LOGO_URL
    await message.delete()
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=GEMINI_LOGO_URL,
        caption="💳 *Top Up Wallet*\n\nHow much would you like to add?\n\nType the amount in USD \\(e\\.g\\. 10\\):",
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )
    return AWAIT_TOPUP_AMOUNT


async def recv_topup_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace("$", "")
    try:
        amount = float(text)
        if amount < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            "⚠️ Please enter a valid amount \\(minimum \\$1\\)\\.",
            parse_mode="MarkdownV2"
        )
        return AWAIT_TOPUP_AMOUNT

    context.user_data["topup_amount"] = amount
    amount_str = escape_md(f"${amount:.2f}")
    
    from config import GEMINI_LOGO_URL
    await update.message.reply_photo(
        photo=GEMINI_LOGO_URL,
        caption=f"💳 *Top Up {amount_str}*\n\nChoose payment method:",
        parse_mode="MarkdownV2",
        reply_markup=topup_method_kb(amount),
    )
    return ConversationHandler.END


async def cb_topup_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    method = parts[1]   # trc20 / bep20 / binance
    amount = float(parts[2])

    address_map = {
        "trc20": USDT_TRC20_ADDRESS,
        "bep20": USDT_BEP20_ADDRESS,
        "binance": BINANCE_PAY_ID,
    }
    address = address_map.get(method, "")

    if not address:
        await update.callback_query.answer("❌ Payment method not configured.", show_alert=True)
        return

    # Create topup request
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO topup_requests (user_id, amount, payment_method) VALUES (?,?,?)",
            (update.effective_user.id, amount, method.upper())
        )
        req_id = cur.lastrowid
        await db.commit()

    # QR code
    qr_bytes = make_qr_bytes(address)
    network_names = {"trc20": "USDT TRC20", "bep20": "USDT BEP20", "binance": "Binance Pay"}
    network = network_names.get(method, method)

    amount_str = escape_md(f"${amount:.2f}")
    await update.callback_query.delete_message()
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=InputFile(io.BytesIO(qr_bytes), filename="qr.png"),
        caption=(
            f"📲 *Top Up {amount_str} via {escape_md(network)}*\n\n"
            f"📋 *Send to:*\n`{escape_md(address)}`\n\n"
            f"⚠️ Send *exactly* {amount_str} USDT\\.\n"
            f"After sending, click the button below\\."
        ),
        parse_mode="MarkdownV2",
        reply_markup=topup_confirm_kb(req_id),
    )

    user = await get_user(update.effective_user.id)
    await notify_admin(
        context,
        f"💰 *Top\\-Up Request \\#{req_id}*\n"
        f"User: {escape_md(user['first_name'])} \\(`{user['telegram_id']}`\\)\n"
        f"Amount: \\${amount:.2f}\n"
        f"Method: {escape_md(network)}"
    )


async def cb_topup_sent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    req_id = int(update.callback_query.data.split("_")[2])
    await update.callback_query.edit_message_caption(
        caption=(
            f"⏳ *Payment Submitted\\!*\n\n"
            f"Request \\#{req_id} is pending admin verification\\.\n"
            f"Your balance will be updated after confirmation\\."
        ),
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )
    user = await get_user(update.effective_user.id)
    await notify_admin(
        context,
        f"🔔 *Top\\-Up Sent \\#{req_id}*\n"
        f"User: {escape_md(user['first_name'])} \\(`{user['telegram_id']}`\\)\n"
        f"Please approve via /admin → Top\\-up Requests"
    )


async def cb_tx_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = update.effective_user.id
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 15",
            (user_id,)
        )
        txs = [dict(r) for r in await cur.fetchall()]

    if not txs:
        await update.callback_query.edit_message_text(
            "📋 *Transaction History*\n\nNo transactions yet\\.",
            parse_mode="MarkdownV2", reply_markup=back_home_kb()
        )
        return

    lines = ["📋 *Transaction History* \\(last 15\\)\n"]
    for tx in txs:
        sign = "\\+" if tx["amount"] > 0 else ""
        emoji = "🟢" if tx["amount"] > 0 else "🔴"
        amt_str = escape_md(f"${abs(tx['amount']):.2f}")
        lines.append(
            f"{emoji} {sign}{amt_str} — "
            f"{escape_md(tx['type'])} — "
            f"{escape_md(tx['created_at'][:10])}"
        )

    await update.callback_query.edit_message_text(
        "\n".join(lines),
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )


import time
from utils.cryptomus import create_cryptomus_invoice


async def cb_topup_cryptomus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    amount = float(parts[2])

    # Create topup request
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO topup_requests (user_id, amount, payment_method) VALUES (?,?,?)",
            (update.effective_user.id, amount, "CRYPTOMUS")
        )
        req_id = cur.lastrowid
        await db.commit()

    unique_ref = f"topup_{req_id}_{int(time.time())}"

    try:
        payment_url, payment_uuid = await create_cryptomus_invoice(amount, unique_ref)
    except Exception as e:
        async with get_db() as db:
            await db.execute("DELETE FROM topup_requests WHERE id=?", (req_id,))
            await db.commit()
        await update.callback_query.edit_message_text(
            "❌ *Payment Gateway Error*\n\nUnable to generate payment link. Please try again later.",
            parse_mode="MarkdownV2",
            reply_markup=back_home_kb()
        )
        return

    # Update topup request with Cryptomus UUID
    async with get_db() as db:
        await db.execute(
            "UPDATE topup_requests SET tx_hash=? WHERE id=?",
            (payment_uuid, req_id)
        )
        await db.commit()

    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    cryptomus_kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Pay Now (Open Checkout)", url=payment_url)],
        [InlineKeyboardButton("🏠 Back to Home", callback_data="main_menu")]
    ])

    amount_str = escape_md(f"${amount:.2f}")
    await update.callback_query.edit_message_text(
        f"⚡ *Auto Top\\-Up Invoice Generated\\!*\n\n"
        f"💰 *Amount:* {amount_str}\n\n"
        f"Click the button below to complete the deposit\\.\n"
        f"Your balance will be updated automatically once the payment is confirmed\\.",
        parse_mode="MarkdownV2",
        reply_markup=cryptomus_kb
    )


def register_wallet_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_wallet_home, pattern="^wallet_home$"))
    app.add_handler(CallbackQueryHandler(cb_topup_method, pattern=r"^topup_(trc20|bep20|binance)_[\d.]+$"))
    app.add_handler(CallbackQueryHandler(cb_topup_sent,  pattern=r"^topup_sent_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_tx_history,  pattern="^tx_history$"))
    app.add_handler(CallbackQueryHandler(cb_topup_cryptomus, pattern=r"^topup_cryptomus_[\d.]+$"))

    from telegram.ext import ConversationHandler
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_topup_home, pattern="^topup_home$")],
        states={AWAIT_TOPUP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_topup_amount)]},
        fallbacks=[],
        per_chat=True, per_user=True,
    ))
