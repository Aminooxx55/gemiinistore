"""Profile handler."""
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from utils.helpers import get_user
from utils.keyboards import profile_kb
from utils.messages import escape_md
from config import get_membership, SILVER_THRESHOLD, GOLD_THRESHOLD, DIAMOND_THRESHOLD


async def cb_profile_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user = await get_user(update.effective_user.id)

    membership = get_membership(user["total_spent"])

    # Next tier info
    if user["total_spent"] < SILVER_THRESHOLD:
        diff = SILVER_THRESHOLD - user['total_spent']
        next_tier = f"🥈 Silver \\(spend {escape_md(f'${diff:.2f}')} more\\)"
    elif user["total_spent"] < GOLD_THRESHOLD:
        diff = GOLD_THRESHOLD - user['total_spent']
        next_tier = f"🥇 Gold \\(spend {escape_md(f'${diff:.2f}')} more\\)"
    elif user["total_spent"] < DIAMOND_THRESHOLD:
        diff = DIAMOND_THRESHOLD - user['total_spent']
        next_tier = f"💎 Diamond \\(spend {escape_md(f'${diff:.2f}')} more\\)"
    else:
        next_tier = "🏆 You are at the highest tier\\!"

    username_str = f"@{escape_md(user['username'])}" if user["username"] else "N/A"
    bal_str = escape_md(f"${user['balance']:.2f}")
    spent_str = escape_md(f"${user['total_spent']:.2f}")
    from utils.messages import sep

    await update.callback_query.edit_message_text(
        f"😊 *My Profile*\n\n"
        f"👤 *Name:* {escape_md(user['first_name'])}\n"
        f"🔗 *Username:* {username_str}\n"
        f"🆔 *ID:* `{user['telegram_id']}`\n\n"
        f"{sep()}\n"
        f"💰 *Balance:* {bal_str}\n"
        f"📊 *Total Spent:* {spent_str}\n"
        f"🪪 *Membership:* {escape_md(membership)}\n"
        f"⬆️ *Next Tier:* {next_tier}\n"
        f"{sep()}",
        parse_mode="MarkdownV2",
        reply_markup=profile_kb(),
    )


def register_profile_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_profile_home, pattern="^profile_home$"))
