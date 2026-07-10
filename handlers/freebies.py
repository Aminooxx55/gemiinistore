"""Freebies handler — list and claim free products."""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CallbackQueryHandler
from database.db import get_db
from utils.keyboards import product_detail_kb, back_home_kb
from utils.messages import product_detail_msg, escape_md


async def cb_freebies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    message = update.callback_query.message

    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM products WHERE is_free=1 AND is_active=1 ORDER BY id"
        )
        products = [dict(r) for r in await cur.fetchall()]

    if not products:
        await message.delete()
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="🎁 *Freebies*\n\nNo free items available right now\\. Check back later\\!",
            parse_mode="MarkdownV2",
            reply_markup=back_home_kb(),
        )
        return

    rows = []
    for p in products:
        stock_str = "♾️" if p["stock"] == -1 else f"📦 {p['stock']}"
        label = f"{p['emoji']} {p['name']} | FREE 🔥 | {stock_str}"
        rows.append([InlineKeyboardButton(label, callback_data=f"prod_{p['id']}")])

    rows.append([InlineKeyboardButton("🔄 Refresh",      callback_data="freebies")])
    rows.append([InlineKeyboardButton("🏠 Back to Home", callback_data="main_menu")])

    await message.delete()
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="🎁 *Freebies*\n\nClaim these free items — no payment needed\\!",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(rows),
    )


def register_freebies_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_freebies, pattern="^freebies$"))
