"""Referral handler."""
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from database.db import get_db
from utils.helpers import get_user
from utils.keyboards import referral_kb, back_home_kb
from utils.messages import escape_md
from config import BOT_USERNAME, REFERRAL_REWARD


async def cb_referral_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = update.effective_user.id

    async with get_db() as db:
        cur = await db.execute(
            "SELECT COUNT(*) as total, SUM(reward_given) as rewarded FROM referrals WHERE referrer_id=?",
            (user_id,)
        )
        stats = await cur.fetchone()

    total_refs = stats["total"] or 0
    rewarded = int(stats["rewarded"] or 0)
    earned = rewarded * REFERRAL_REWARD

    reward_str = escape_md(f"${REFERRAL_REWARD:.2f}")
    earned_str = escape_md(f"${earned:.2f}")
    link = f"https://t\\.me/{escape_md(BOT_USERNAME)}?start=ref\\_{user_id}"
    from utils.messages import sep
    from config import GEMINI_LOGO_URL

    message = update.callback_query.message
    await message.delete()

    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=GEMINI_LOGO_URL,
        caption=(
            f"📣 *Refer \\& Earn*\n\n"
            f"Invite friends and earn {reward_str} for every friend "
            f"who makes their first purchase\\!\n\n"
            f"{sep()}\n"
            f"👥 *Total Referrals:* {total_refs}\n"
            f"✅ *Rewarded:* {rewarded}\n"
            f"💰 *Total Earned:* {earned_str}\n"
            f"{sep()}\n\n"
            f"🔗 *Your Referral Link:*\n`{link}`\n\n"
            f"Share it with friends\\!"
        ),
        parse_mode="MarkdownV2",
        reply_markup=referral_kb(BOT_USERNAME, user_id),
    )


def register_referral_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_referral_home, pattern="^referral_home$"))
