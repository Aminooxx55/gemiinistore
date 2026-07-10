# -*- coding: utf-8 -*-
"""Orders handler — list, view order details, and rating system."""
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters
from database.db import get_db
from utils.keyboards import orders_kb, order_detail_kb, back_home_kb
from utils.messages import order_status_msg, escape_md
from telegram import InlineKeyboardMarkup, InlineKeyboardButton


def rating_kb(order_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⭐", callback_data=f"rate_1_{order_id}"),
            InlineKeyboardButton("⭐⭐", callback_data=f"rate_2_{order_id}"),
            InlineKeyboardButton("⭐⭐⭐", callback_data=f"rate_3_{order_id}"),
            InlineKeyboardButton("⭐⭐⭐⭐", callback_data=f"rate_4_{order_id}"),
            InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data=f"rate_5_{order_id}")
        ]
    ])


async def cb_orders_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_id = update.effective_user.id
    message = update.callback_query.message

    async with get_db() as db:
        cur = await db.execute(
            """SELECT o.*, p.name as product_name, p.emoji
               FROM orders o
               JOIN products p ON o.product_id = p.id
               WHERE o.user_id = ?
               ORDER BY o.created_at DESC
               LIMIT 20""",
            (user_id,)
        )
        orders = [dict(r) for r in await cur.fetchall()]

    from config import GEMINI_LOGO_URL

    if not orders:
        await message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=GEMINI_LOGO_URL,
            caption="👀 *My Orders*\n\nYou haven't placed any orders yet\\.\n\nGo to the Shop to get started\\!",
            parse_mode="MarkdownV2",
            reply_markup=back_home_kb(),
        )
        return

    status_emoji = {"pending": "⏳", "paid": "✅", "delivered": "📦", "cancelled": "❌"}
    rows = []
    for o in orders:
        emoji = status_emoji.get(o["status"], "❓")
        label = f"{emoji} #{o['id']} — {o['product_name'][:20]} — ${o['total_price']:.2f}"
        rows.append([InlineKeyboardButton(label, callback_data=f"order_detail_{o['id']}")])

    rows.append([InlineKeyboardButton("🏠 Back to Home", callback_data="main_menu")])

    await message.delete()
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=GEMINI_LOGO_URL,
        caption="👀 *My Orders* \\(last 20\\)\n\nClick an order to see details:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def cb_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    order_id = int(update.callback_query.data.split("_")[2])
    user_id = update.effective_user.id
    message = update.callback_query.message

    async with get_db() as db:
        cur = await db.execute(
            """SELECT o.*, p.name as product_name
               FROM orders o JOIN products p ON o.product_id=p.id
               WHERE o.id=? AND o.user_id=?""",
            (order_id, user_id)
        )
        order = await cur.fetchone()

    if not order:
        await update.callback_query.answer("Order not found!", show_alert=True)
        return

    order = dict(order)
    text = order_status_msg(order, order["product_name"])

    if order.get("delivery_info"):
        text += f"\n📬 *Delivery Info:*\n`{escape_md(order['delivery_info'])}`"

    # If delivered, show a prompt to rate if not already rated
    async with get_db() as db:
        cur = await db.execute("SELECT id FROM reviews WHERE user_id=? AND product_id=?", (user_id, order["product_id"]))
        rated = await cur.fetchone()

    keyboard = order_detail_kb(order_id)
    if order["status"] == "delivered" and not rated:
        # Append Rating Button
        kb_rows = list(keyboard.inline_keyboard)
        kb_rows.insert(0, [InlineKeyboardButton("⭐ Rate Purchase", callback_data=f"show_rate_{order_id}")])
        keyboard = InlineKeyboardMarkup(kb_rows)

    from config import GEMINI_LOGO_URL
    await message.delete()
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=GEMINI_LOGO_URL,
        caption=text,
        parse_mode="MarkdownV2",
        reply_markup=keyboard,
    )


async def cb_show_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    order_id = int(update.callback_query.data.split("_")[2])
    message = update.callback_query.message

    from config import GEMINI_LOGO_URL
    await message.delete()
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=GEMINI_LOGO_URL,
        caption="⭐ *Please rate your purchase experience:*\n\nYour feedback helps us provide better service\\!",
        parse_mode="MarkdownV2",
        reply_markup=rating_kb(order_id),
    )


async def cb_rate_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    rating = int(parts[1])
    order_id = int(parts[2])
    user_id = update.effective_user.id
    message = update.callback_query.message

    async with get_db() as db:
        cur = await db.execute("SELECT product_id FROM orders WHERE id=?", (order_id,))
        order = await cur.fetchone()

    if not order:
        await update.callback_query.answer("Order not found!", show_alert=True)
        return

    product_id = order["product_id"]

    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO reviews (user_id, product_id, rating) VALUES (?, ?, ?)",
            (user_id, product_id, rating)
        )
        await db.commit()

    context.user_data["waiting_for_review_comment"] = order_id

    stars = "⭐" * rating
    from config import GEMINI_LOGO_URL
    await message.delete()
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=GEMINI_LOGO_URL,
        caption=f"❤️ *Thank you for your rating of {stars}\\!*\n\n"
                f"✍️ Would you like to leave a feedback comment?\n"
                f"Please type it below and send it, or click **Skip**:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭️ Skip Comment", callback_data=f"skip_comment_{order_id}")]
        ]),
    )


async def cb_skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data.pop("waiting_for_review_comment", None)
    message = update.callback_query.message

    from config import GEMINI_LOGO_URL
    await message.delete()
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=GEMINI_LOGO_URL,
        caption="✅ *Feedback saved\\!*\n\nThank you for your review\\! 🥰",
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )


async def recv_review_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("waiting_for_review_comment")
    if not order_id:
        return

    comment = update.message.text.strip()
    user_id = update.effective_user.id

    async with get_db() as db:
        cur = await db.execute("SELECT product_id FROM orders WHERE id=?", (order_id,))
        order = await cur.fetchone()

        if order:
            product_id = order["product_id"]
            await db.execute(
                "UPDATE reviews SET comment=? WHERE user_id=? AND product_id=?",
                (comment, user_id, product_id)
            )
            await db.commit()

    context.user_data.pop("waiting_for_review_comment", None)
    await update.message.reply_text(
        "✅ *Comment saved\\!*\n\nThank you for your valuable feedback\\! 🥰",
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )


def register_orders_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_orders_home,  pattern="^orders_home$"))
    app.add_handler(CallbackQueryHandler(cb_order_detail, pattern=r"^order_detail_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_show_rate,    pattern=r"^show_rate_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_rate_order,   pattern=r"^rate_\d+_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_skip_comment, pattern=r"^skip_comment_\d+$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recv_review_comment), group=1)
