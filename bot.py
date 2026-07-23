# -*- coding: utf-8 -*-
"""Main bot entry point."""
import os
import sys
import logging
import asyncio

# Force UTF-8 on Windows (no stdout redirect — use PYTHONUTF8=1 env var)
os.environ["PYTHONUTF8"] = "1"
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, TypeHandler, ContextTypes, CallbackQueryHandler, ApplicationHandlerStop
from config import BOT_TOKEN, ADMIN_ID
from database.models import init_db
from handlers.start import register_start_handlers
from handlers.shop import register_shop_handlers
from handlers.payments import register_payment_handlers
from handlers.wallet import register_wallet_handlers
from handlers.orders import register_orders_handlers
from handlers.profile import register_profile_handlers
from handlers.referral import register_referral_handlers
from handlers.freebies import register_freebies_handlers
from handlers.admin import register_admin_handlers
from handlers.spin import register_spin_handlers
from handlers.support import register_support_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)
async def post_init(app: Application):
    """Called after bot starts — init DB and set bot commands."""
    await init_db()
    logger.info("✅ Database initialized.")
    await app.bot.set_my_commands([
        ("start", "Open the shop"),
    ])

    from utils.cryptomus import is_cryptomus_enabled
    if is_cryptomus_enabled():
        from utils.scheduler import poll_pending_payments
        app.job_queue.run_repeating(poll_pending_payments, interval=15, first=10)
        logger.info("✅ Cryptomus auto-verification enabled.")
    else:
        logger.info("ℹ️ Cryptomus auto-verification disabled (keys not set in .env).")

    from config import RECURRING_CHAT, RECURRING_INTERVAL
    if RECURRING_CHAT:
        from utils.scheduler import send_recurring_message
        app.job_queue.run_repeating(send_recurring_message, interval=RECURRING_INTERVAL, first=10)
        logger.info(f"✅ Recurring message sender enabled: every {RECURRING_INTERVAL}s to {RECURRING_CHAT}")


async def log_update_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.helpers import notify_admin
    from utils.messages import escape_md

    # Ignore actions by the admin themselves to prevent loops/spam
    if update.effective_user and update.effective_user.id == ADMIN_ID:
        return

    user = update.effective_user
    if not user:
        return

    from html import escape as html_escape
    name = html_escape(user.first_name or "User")
    username = f"@{html_escape(user.username)}" if user.username else "No Username"
    user_info = f"👤 <b>{name}</b> ({username}, <code>{user.id}</code>)"

    log_msg = None
    action_str = None
    if update.message and update.message.text:
        log_msg = f"{user_info} sent:\n<code>{html_escape(update.message.text)}</code>"
        action_str = f"Command: {update.message.text}"
    elif update.callback_query and update.callback_query.data:
        from utils.helpers import translate_callback_data
        translated_action = await translate_callback_data(update.callback_query.data)
        log_msg = f"{user_info} clicked button:\n<code>{html_escape(update.callback_query.data)}</code> ({html_escape(translated_action)})"
        action_str = f"Click: {translated_action}"

    if action_str:
        from database.db import get_db
        try:
            async with get_db() as db:
                await db.execute(
                    "INSERT INTO user_activity (telegram_id, first_name, username, action) VALUES (?, ?, ?, ?)",
                    (user.id, user.first_name or "User", user.username or "", action_str)
                )
                await db.commit()
        except Exception as e:
            logger.error(f"Error saving user activity: {e}")

    if log_msg:
        await notify_admin(context, log_msg)


async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global pre-handler to force users to join the required channel."""
    user = update.effective_user
    if not user:
        return

    # Skip check for admin
    if user.id == ADMIN_ID:
        return

    # Allow check_join callback query to bypass so they can verify status
    if update.callback_query and update.callback_query.data == "check_join":
        return

    # Check join status
    from utils.helpers import is_user_member_of_channel
    joined = await is_user_member_of_channel(context.bot, user.id)
    if not joined:
        from config import REQUIRED_CHANNEL
        
        # Dynamically build the join link
        if REQUIRED_CHANNEL.startswith("http://") or REQUIRED_CHANNEL.startswith("https://"):
            join_url = REQUIRED_CHANNEL
            channel_display = REQUIRED_CHANNEL
        elif REQUIRED_CHANNEL.startswith("@"):
            join_url = f"https://t.me/{REQUIRED_CHANNEL[1:]}"
            channel_display = REQUIRED_CHANNEL
        else:
            join_url = f"https://t.me/{REQUIRED_CHANNEL}"
            channel_display = f"@{REQUIRED_CHANNEL}"

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Join Channel", url=join_url)],
            [InlineKeyboardButton("🔄 Check Join Status", callback_data="check_join")]
        ])
        
        msg_text = (
            "⚠️ <b>Access Denied!</b>\n\n"
            "You must join our main channel to continue using the bot.\n\n"
            f"👉 Please join here: {channel_display}\n"
            "After joining, click <b>Check Join Status</b> below!"
        )
        
        if update.callback_query:
            await update.callback_query.answer("⚠️ Please join the channel first!", show_alert=True)
            try:
                await update.callback_query.edit_message_text(
                    text=msg_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception:
                try:
                    await context.bot.send_message(
                        chat_id=user.id,
                        text=msg_text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    logger.exception('Failed to send channel join message')
        else:
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=msg_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception:
                logger.exception('Failed to send channel join message')
            
        raise ApplicationHandlerStop()



async def cb_check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback for check_join button."""
    await update.callback_query.answer()
    user_id = update.effective_user.id
    from utils.helpers import is_user_member_of_channel
    joined = await is_user_member_of_channel(context.bot, user_id, force_check=True)
    if joined:
        await update.callback_query.edit_message_text(
            "✅ <b>Thank you for joining!</b>\n\nUse /start to open the main menu.",
            parse_mode="HTML"
        )
    else:
        await update.callback_query.answer("❌ You haven't joined yet. Please join the channel first!", show_alert=True)


async def run_bot():
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN is not set in .env file!")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register all handlers (order matters for ConversationHandlers)
    app.add_handler(TypeHandler(Update, log_update_to_admin), group=-2)
    app.add_handler(TypeHandler(Update, check_membership), group=-1)
    app.add_handler(CallbackQueryHandler(cb_check_join, pattern="^check_join$"))
    register_admin_handlers(app)
    register_shop_handlers(app)
    register_wallet_handlers(app)
    register_payment_handlers(app)
    register_start_handlers(app)
    register_orders_handlers(app)
    register_profile_handlers(app)
    register_referral_handlers(app)
    register_freebies_handlers(app)
    register_spin_handlers(app)
    register_support_handlers(app)


    logger.info("🤖 Bot is running... Press Ctrl+C to stop.")
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        # Keep running until Ctrl+C
        await asyncio.Event().wait()
        await app.updater.stop()
        await app.stop()


if __name__ == "__main__":
    asyncio.run(run_bot())


