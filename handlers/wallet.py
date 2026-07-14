"""Wallet handler — balance, top-up requests, transaction history."""
import logging
from telegram import Update
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler,
    filters, ConversationHandler,
)
from database.db import get_db
from utils.helpers import get_user, make_qr_bytes, notify_admin
from utils.keyboards import wallet_kb, topup_method_kb, topup_confirm_kb, back_home_kb
from utils.messages import sep
from html import escape as html_escape
from config import USDT_POL_ADDRESS, USDT_BEP20_ADDRESS, BINANCE_PAY_ID
import io
from telegram import InputFile
from utils.messages import payment_address_msg
from config import SUPPORT_USERNAME
 
AWAIT_TOPUP_AMOUNT = 1
WAIT_BINANCE_TOPUP_REF = 20
 
 
async def cancel_wallet_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any active wallet conversation."""
    from utils.keyboards import back_home_kb
    await update.message.reply_text("❌ Operation cancelled.", reply_markup=back_home_kb())
    return ConversationHandler.END
 
 
async def cb_wallet_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user = await get_user(update.effective_user.id)
    bal_str = f"${user['balance']:.2f}"
    spent_str = f"${user['total_spent']:.2f}"
    message = update.callback_query.message
 
    await message.delete()
 
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=(
            f"💵 <b>My Wallet</b>\n\n"
            f"💰 <b>Balance:</b> {bal_str}\n"
            f"📊 <b>Total Spent:</b> {spent_str}\n\n"
            f"Top up your wallet to pay instantly!"
        ),
        parse_mode="HTML",
        reply_markup=wallet_kb(),
    )
 
 
async def cb_topup_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    message = update.callback_query.message
    await message.delete()
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="💳 <b>Top Up Wallet</b>\n\nHow much would you like to add?\n\nType the amount in USD (e.g. 10):",
        parse_mode="HTML",
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
            "⚠️ Please enter a valid amount (minimum $1).",
            parse_mode="HTML"
        )
        return AWAIT_TOPUP_AMOUNT
 
    context.user_data["topup_amount"] = amount
    amount_str = f"${amount:.2f}"
    
    await update.message.reply_text(
        text=f"💳 <b>Top Up {amount_str}</b>\n\nChoose payment method:",
        parse_mode="HTML",
        reply_markup=topup_method_kb(amount),
    )
    return ConversationHandler.END
 
 
async def cb_topup_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    method = parts[1]   # trc20 / bep20 / binance
    amount = float(parts[2])
 
    address_map = {
        "pol": USDT_POL_ADDRESS,
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
    network_names = {"pol": "USDT POL", "bep20": "USDT BEP20", "binance": "Binance Pay"}
    network = network_names.get(method, method)
 
    amount_str = f"${amount:.2f}"
    await update.callback_query.delete_message()
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=InputFile(io.BytesIO(qr_bytes), filename="qr.png"),
        caption=(
            f"📲 <b>Top Up {amount_str} via {html_escape(network)}</b>\n\n"
            f"📋 <b>Send to:</b>\n<code>{html_escape(address)}</code>\n\n"
            f"⚠️ Send <b>exactly</b> {amount_str} USDT.\n"
            f"After sending, click the button below."
        ),
        parse_mode="HTML",
        reply_markup=topup_confirm_kb(req_id),
    )
 
    user = await get_user(update.effective_user.id)
    await notify_admin(
        context,
        f"💰 <b>Top-Up Request #{req_id}</b>\n"
        f"User: {html_escape(user['first_name'])} (<code>{user['telegram_id']}</code>)\n"
        f"Amount: ${amount:.2f}\n"
        f"Method: {html_escape(network)}"
    )
 
 
async def cb_topup_sent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    await update.callback_query.answer()
    req_id = int(update.callback_query.data.split("_")[2])

    async with get_db() as db:
        cur = await db.execute("SELECT payment_method FROM topup_requests WHERE id=?", (req_id,))
        req = await cur.fetchone()

    method = req["payment_method"] if req else ""
    
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    if method in ("BINANCE", "POL"):
        method_name = "Binance Pay Transaction ID / Order ID" if method == "BINANCE" else "POL Transaction Hash (TxID)"
        hint = "(You can find this in your Binance App history)" if method == "BINANCE" else "(The blockchain hash of your deposit)"
        await update.callback_query.edit_message_caption(
            caption=(
                f"⏳ <b>Payment Submitted!</b>\n\n"
                f"Top-Up Request #{req_id} is pending verification.\n\n"
                f"📝 <b>Please reply with your {method_name}:</b>\n"
                f"{hint}"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_binance_topup")]])
        )
        context.user_data["verify_topup_req_id"] = req_id
        return WAIT_BINANCE_TOPUP_REF
    else:
        await update.callback_query.edit_message_caption(
            caption=(
                f"⏳ <b>Payment Submitted!</b>\n\n"
                f"Request #{req_id} is pending admin verification.\n"
                f"Your balance will be updated after confirmation."
            ),
            parse_mode="HTML",
            reply_markup=back_home_kb(),
        )
        user = await get_user(update.effective_user.id)
        await notify_admin(
            context,
            f"🔔 <b>Top-Up Sent #{req_id}</b>\n"
            f"User: {html_escape(user['first_name'])} (<code>{user['telegram_id']}</code>)\n"
            f"Please approve via /admin → Top-up Requests"
        )
        return ConversationHandler.END


async def recv_binance_topup_ref(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    from utils.helpers import update_user_balance, record_transaction
    
    req_id = context.user_data.get("verify_topup_req_id")
    if not req_id:
        return ConversationHandler.END

    ref_id = update.message.text.strip()
    
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM topup_requests WHERE id=?", (req_id,))
        req = await cur.fetchone()
        
    if not req:
        await update.message.reply_text("❌ Request not found.", reply_markup=back_home_kb())
        context.user_data.pop("verify_topup_req_id", None)
        return ConversationHandler.END
        
    req = dict(req)
    if req["status"] != "PENDING":
        await update.message.reply_text("❌ This request is already processed.", reply_markup=back_home_kb())
        context.user_data.pop("verify_topup_req_id", None)
        return ConversationHandler.END

    expected_amount = req["amount"]
    
    verifying_msg = await update.message.reply_text(
        "⏳ <b>Verifying transaction on Binance Pay...</b>\nThis may take up to 10 seconds.",
        parse_mode="HTML"
    )
    
    from utils.binance_pay import verify_transaction, verify_spot_deposit
    try:
        if req["payment_method"] == "POL":
            # Pass a negative order_id or topup ID equivalent for admin_note mapping
            success = await verify_spot_deposit(ref_id, expected_amount, -req_id, network="MATIC")
        else:
            success = await verify_transaction(ref_id, expected_amount, f"topup_{req_id}")
    except Exception:
        logger.exception(f"Error during verification for topup {req_id}")
        success = False
        
    if success:
        async with get_db() as db:
            await db.execute("UPDATE topup_requests SET status='APPROVED', tx_hash=? WHERE id=?", (ref_id, req_id))
            await db.commit()
            
        await update_user_balance(update.effective_user.id, expected_amount)
        await record_transaction(
            update.effective_user.id, expected_amount, "deposit",
            f"Auto Binance Pay Deposit (#{req_id})", None
        )
            
        await verifying_msg.delete()
        await update.message.reply_text(
            f"✅ <b>Top-Up Verified Successfully!</b>\n\n"
            f"💰 <b>Amount Added:</b> <code>${expected_amount:.2f}</code>\n"
            f"🔖 <b>Transaction ID:</b> <code>{ref_id}</code>\n\n"
            f"Your balance has been updated! You can now use your wallet.",
            parse_mode="HTML",
            reply_markup=back_home_kb()
        )
        
        user = await get_user(update.effective_user.id)
        await notify_admin(
            context,
            f"🎉 <b>Automated Binance Top-Up!</b>\n"
            f"Request #{req_id} verified automatically!\n"
            f"User: {html_escape(user['first_name'])} (<code>{user['telegram_id']}</code>)\n"
            f"Amount: ${expected_amount:.2f}\n"
            f"TxID: <code>{html_escape(ref_id)}</code>"
        )
        
        context.user_data.pop("verify_topup_req_id", None)
        return ConversationHandler.END
    else:
        await verifying_msg.delete()
        await update.message.reply_text(
            "❌ <b>Verification Failed!</b>\n\n"
            "We couldn't find a matching transaction for that ID/Reference, "
            "or the payment amount/currency did not match your top-up request.\n\n"
            "✍️ <b>Please enter the correct Transaction ID, or click Cancel below:</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_binance_topup")]])
        )
        return WAIT_BINANCE_TOPUP_REF

async def cb_cancel_binance_topup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    await update.callback_query.answer()
    context.user_data.pop("verify_topup_req_id", None)
    
    # Just go back to wallet home
    await cb_wallet_home(update, context)
    return ConversationHandler.END
 
 
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
            "📋 <b>Transaction History</b>\n\nNo transactions yet.",
            parse_mode="HTML", reply_markup=back_home_kb()
        )
        return
 
    lines = ["📋 <b>Transaction History</b> (last 15)\n"]
    for tx in txs:
        sign = "+" if tx["amount"] > 0 else ""
        emoji = "🟢" if tx["amount"] > 0 else "🔴"
        amt_str = f"${abs(tx['amount']):.2f}"
        lines.append(
            f"{emoji} {sign}{amt_str} — "
            f"{html_escape(tx['type'])} — "
            f"{html_escape(tx['created_at'][:10])}"
        )
 
    await update.callback_query.edit_message_text(
        "\n".join(lines),
        parse_mode="HTML",
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
            "❌ <b>Payment Gateway Error</b>\n\nUnable to generate payment link. Please try again later.",
            parse_mode="HTML",
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
 
    amount_str = f"${amount:.2f}"
    await update.callback_query.edit_message_text(
        f"⚡ <b>Auto Top-Up Invoice Generated!</b>\n\n"
        f"💰 <b>Amount:</b> {amount_str}\n\n"
        f"Click the button below to complete the deposit.\n"
        f"Your balance will be updated automatically once the payment is confirmed.",
        parse_mode="HTML",
        reply_markup=cryptomus_kb
    )


def register_wallet_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_wallet_home, pattern="^wallet_home$"))
    app.add_handler(CallbackQueryHandler(cb_topup_method, pattern=r"^topup_(pol|bep20|binance)_[\d.]+$"))
    app.add_handler(CallbackQueryHandler(cb_tx_history,  pattern="^tx_history$"))
    app.add_handler(CallbackQueryHandler(cb_topup_cryptomus, pattern=r"^topup_cryptomus_[\d.]+$"))

    from telegram.ext import ConversationHandler
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_topup_home, pattern="^topup_home$")],
        states={AWAIT_TOPUP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_topup_amount)]},
        fallbacks=[CommandHandler('cancel', cancel_wallet_conversation)],
        per_chat=True, per_user=True,
        conversation_timeout=300,
    ))

    # Add ConversationHandler for Binance Pay topup verification
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_topup_sent, pattern=r"^topup_sent_\d+$")],
        states={
            WAIT_BINANCE_TOPUP_REF: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_binance_topup_ref)]
        },
        fallbacks=[
            CommandHandler("cancel", cb_cancel_binance_topup),
            CallbackQueryHandler(cb_cancel_binance_topup, pattern="^cancel_binance_topup$")
        ],
        per_chat=True, per_user=True
    ))
