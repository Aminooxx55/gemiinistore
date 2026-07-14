"""Profile handler."""
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from utils.helpers import get_user
from utils.keyboards import profile_kb
from utils.messages import format_profile_text


async def cb_profile_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user = await get_user(update.effective_user.id)

    text = format_profile_text(user)

    message = update.callback_query.message
    await message.delete()

    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=text,
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )


def register_profile_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_profile_home, pattern="^profile_home$"))
