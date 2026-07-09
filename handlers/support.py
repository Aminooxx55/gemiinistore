# -*- coding: utf-8 -*-
"""In-Bot Live Support Ticket System."""
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler,
)
from database.db import get_db
from utils.helpers import get_user
from utils.keyboards import back_home_kb, admin_kb
from config import ADMIN_ID

# Conversation states
SUPPORT_USER_MSG, ADMIN_SUPPORT_REPLY = range(2)


async def cmd_support_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start support conversation flow."""
    user_id = update.effective_user.id
    
    # If admin, show tickets list menu instead of ticket creation
    if user_id == ADMIN_ID:
        await view_open_tickets(update, context)
        return ConversationHandler.END

    text = (
        "💬 <b>Live Support Chat</b> 💬\n\n"
        "Need help? Have questions about a product or payment?\n\n"
        "👇 Please type your question or issue in detail below and send it. "
        "Our support team will reply directly through this chat!"
    )
    
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=back_home_kb())
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=back_home_kb())
        
    return SUPPORT_USER_MSG


async def recv_user_support_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message_text = update.message.text.strip()
    
    if not message_text:
        await update.message.reply_text("⚠️ Message cannot be empty. Please try again:")
        return SUPPORT_USER_MSG
        
    # 1. Insert support ticket into database
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO support_tickets (user_id, message, status) VALUES (?, ?, 'open')",
            (user_id, message_text)
        )
        ticket_id = cur.lastrowid
        await db.commit()

    # 2. Notify the Admin
    user = await get_user(user_id)
    username = f"@{user['username']}" if user['username'] else "No Username"
    
    admin_msg = (
        f"🆘 <b>New Support Ticket #{ticket_id}</b>\n\n"
        f"👤 <b>From:</b> {user['first_name']} ({username}, <code>{user_id}</code>)\n"
        f"📝 <b>Message:</b>\n<i>{message_text}</i>"
    )
    
    # Inline buttons for admin action
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Reply", callback_data=f"admin_ticket_reply_{user_id}_{ticket_id}"),
            InlineKeyboardButton("🔒 Close Ticket", callback_data=f"admin_ticket_close_{ticket_id}")
        ]
    ])
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_msg,
            parse_mode="HTML",
            reply_markup=kb
        )
    except Exception:
        pass

    # 3. Notify user
    await update.message.reply_text(
        "✅ <b>Message Sent!</b>\n\n"
        f"Your support ticket <b>#{ticket_id}</b> has been received. "
        "Our team will review it and reply shortly! 💬",
        parse_mode="HTML",
        reply_markup=back_home_kb()
    )
    
    return ConversationHandler.END


async def cb_admin_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    user_id, ticket_id = int(parts[3]), int(parts[4])
    
    context.user_data["reply_to_user_id"] = user_id
    context.user_data["reply_ticket_id"] = ticket_id
    
    await update.callback_query.edit_message_text(
        f"💬 <b>Replying to Ticket #{ticket_id}</b>\n\n"
        "Please type your reply message below and send it:",
        parse_mode="HTML"
    )
    return ADMIN_SUPPORT_REPLY


async def recv_admin_support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("reply_to_user_id")
    ticket_id = context.user_data.get("reply_ticket_id")
    reply_text = update.message.text.strip()
    
    if not reply_text:
        await update.message.reply_text("⚠️ Reply cannot be empty. Please type your reply:")
        return ADMIN_SUPPORT_REPLY

    # Send reply to user
    try:
        user_msg = (
            f"💬 <b>Support Team Reply</b> (Ticket #{ticket_id})\n\n"
            f"<i>{reply_text}</i>\n\n"
            "👉 Need more help? Click <b>💬 Support Chat</b> to reply."
        )
        await context.bot.send_message(
            chat_id=user_id,
            text=user_msg,
            parse_mode="HTML"
        )
        
        # Mark ticket as closed on reply
        async with get_db() as db:
            await db.execute(
                "UPDATE support_tickets SET status = 'closed' WHERE id = ?",
                (ticket_id,)
            )
            await db.commit()
            
        await update.message.reply_text(
            f"✅ Reply successfully sent to user `{user_id}`. Ticket #{ticket_id} marked as closed.",
            reply_markup=admin_kb()
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to send reply to user: {e}",
            reply_markup=admin_kb()
        )
        
    context.user_data.pop("reply_to_user_id", None)
    context.user_data.pop("reply_ticket_id", None)
    return ConversationHandler.END


async def cb_admin_close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    ticket_id = int(update.callback_query.data.split("_")[3])
    
    async with get_db() as db:
        cur = await db.execute("SELECT user_id FROM support_tickets WHERE id=?", (ticket_id,))
        row = await cur.fetchone()
        user_id = row[0] if row else None
        
        await db.execute("UPDATE support_tickets SET status = 'closed' WHERE id = ?", (ticket_id,))
        await db.commit()
        
    await update.callback_query.answer("Ticket closed!", show_alert=True)
    await update.callback_query.edit_message_text(
        f"✅ Ticket #{ticket_id} has been marked as closed.",
        reply_markup=admin_kb()
    )
    
    if user_id:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🔒 Your support ticket <b>#{ticket_id}</b> has been marked as closed. Thank you!",
                parse_mode="HTML"
            )
        except Exception:
            pass


async def view_open_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Helper to list open tickets for admin."""
    async with get_db() as db:
        cur = await db.execute(
            """SELECT t.*, u.first_name, u.username
               FROM support_tickets t
               JOIN users u ON t.user_id = u.telegram_id
               WHERE t.status = 'open'
               ORDER BY t.id DESC LIMIT 15"""
        )
        tickets = [dict(r) for r in await cur.fetchall()]

    if not tickets:
        text = "💬 <b>No Open Support Tickets!</b>\n\nAll queries have been handled."
        if update.message:
            await update.message.reply_text(text, parse_mode="HTML", reply_markup=admin_kb())
        else:
            await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=admin_kb())
        return

    text = "💬 <b>Open Support Tickets</b> (latest 15):\n\nTap a ticket to manage/reply:"
    rows = []
    for t in tickets:
        name = t["first_name"][:12]
        msg_preview = t["message"][:15] + "..." if len(t["message"]) > 15 else t["message"]
        label = f"#{t['id']} {name}: {msg_preview}"
        rows.append([InlineKeyboardButton(label, callback_data=f"admin_ticket_view_{t['id']}")])
        
    rows.append([InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_home")])
    
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))
    else:
        await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))


async def cb_admin_view_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    ticket_id = int(update.callback_query.data.split("_")[3])
    
    async with get_db() as db:
        cur = await db.execute(
            """SELECT t.*, u.first_name, u.username
               FROM support_tickets t
               JOIN users u ON t.user_id = u.telegram_id
               WHERE t.id = ?""",
            (ticket_id,)
        )
        t = await cur.fetchone()
        
    if not t:
        await update.callback_query.answer("Ticket not found!", show_alert=True)
        return
        
    t = dict(t)
    username = f"@{t['username']}" if t['username'] else "No Username"
    
    msg_text = (
        f"🆘 <b>Support Ticket #{t['id']}</b>\n\n"
        f"👤 <b>User:</b> {t['first_name']} ({username}, <code>{t['user_id']}</code>)\n"
        f"📅 <b>Date:</b> {t['created_at'][:16]}\n"
        f"📊 <b>Status:</b> {t['status']}\n\n"
        f"📝 <b>Message:</b>\n<i>{t['message']}</i>"
    )
    
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Reply", callback_data=f"admin_ticket_reply_{t['user_id']}_{t['id']}"),
            InlineKeyboardButton("🔒 Close Ticket", callback_data=f"admin_ticket_close_{t['id']}")
        ],
        [InlineKeyboardButton("⬅️ Back to Tickets", callback_data="admin_tickets_list")]
    ])
    
    await update.callback_query.edit_message_text(msg_text, parse_mode="HTML", reply_markup=kb)


async def text_support_chat_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback text menu message handler."""
    return await cmd_support_chat(update, context)


def register_support_handlers(app):
    # User ticket creation conversation
    app.add_handler(ConversationHandler(
        entry_points=[
            CommandHandler("support_chat", cmd_support_chat),
            CallbackQueryHandler(cmd_support_chat, pattern="^support_chat$"),
            MessageHandler(filters.Regex("^💬 Support Chat$"), text_support_chat_menu)
        ],
        states={
            SUPPORT_USER_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_user_support_msg)]
        },
        fallbacks=[], per_chat=True, per_user=True,
    ))

    # Admin reply conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_admin_reply_start, pattern=r"^admin_ticket_reply_\d+_\d+$")],
        states={
            ADMIN_SUPPORT_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_admin_support_reply)]
        },
        fallbacks=[], per_chat=True, per_user=True,
    ))

    # Admin action callbacks
    app.add_handler(CallbackQueryHandler(view_open_tickets, pattern="^admin_tickets_list$"))
    app.add_handler(CallbackQueryHandler(cb_admin_view_ticket, pattern=r"^admin_ticket_view_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_close_ticket, pattern=r"^admin_ticket_close_\d+$"))

