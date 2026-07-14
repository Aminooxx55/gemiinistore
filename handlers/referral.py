"""Referral handler."""
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from database.db import get_db
from utils.helpers import get_user
from utils.keyboards import referral_kb, back_home_kb
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
 
    reward_str = f"${REFERRAL_REWARD:.2f}"
    earned_str = f"${earned:.2f}"
    link = f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"
    from utils.messages import sep
    message = update.callback_query.message
    await message.delete()
 
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=(
            f"📣 <b>Refer & Earn</b>\n\n"
            f"Invite friends and earn {reward_str} for every friend "
            f"who makes their first purchase!\n\n"
            f"{sep()}\n"
            f"👥 <b>Total Referrals:</b> {total_refs}\n"
            f"✅ <b>Rewarded:</b> {rewarded}\n"
            f"💰 <b>Total Earned:</b> {earned_str}\n"
            f"{sep()}\n\n"
            f"🔗 <b>Your Referral Link:</b>\n<code>{link}</code>\n\n"
            f"Share it with friends!"
        ),
        parse_mode="HTML",
        reply_markup=referral_kb(BOT_USERNAME, user_id),
    )


def register_referral_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_referral_home, pattern="^referral_home$"))
