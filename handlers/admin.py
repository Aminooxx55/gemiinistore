"""Admin panel — full management of products, orders, users, top-ups, coupons, broadcast."""
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler,
)
from database.db import get_db
from utils.helpers import get_user, update_user_balance, record_transaction, is_admin
from utils.keyboards import (
    admin_kb, admin_order_actions_kb, admin_topup_actions_kb, back_home_kb,
)
from utils.messages import escape_md

# Conversation states
(
    ADMIN_PROD_NAME, ADMIN_PROD_DESC, ADMIN_PROD_PRICE,
    ADMIN_PROD_STOCK, ADMIN_PROD_EMOJI, ADMIN_PROD_CAT,
    ADMIN_BROADCAST, ADMIN_ADD_BALANCE, ADMIN_ADD_BALANCE_AMOUNT,
    ADMIN_COUPON_CODE, ADMIN_COUPON_DISC, ADMIN_COUPON_USES,
    ADMIN_DELIVER_INFO, ADMIN_UPLOAD_STOCK,
) = range(14)


def admin_only(func):
    """Decorator to restrict handler to admin only."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await is_admin(update.effective_user.id):
            if update.callback_query:
                await update.callback_query.answer("⛔ Admin only!", show_alert=True)
            else:
                await update.message.reply_text("⛔ You are not authorized.")
            return
        return await func(update, context)
    return wrapper


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any active admin conversation."""
    await update.message.reply_text("❌ Operation cancelled.", reply_markup=admin_kb())
    return ConversationHandler.END


async def timeout_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle conversation timeout."""
    if update.effective_user:
        try:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text="⏰ Conversation timed out. Use /admin to start again.",
                reply_markup=admin_kb()
            )
        except Exception:
            logging.exception("Error sending timeout message")


# ── Admin Home ────────────────────────────────────────────────────────────────
@admin_only
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with get_db() as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        user_count = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
        pending_orders = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM topup_requests WHERE status='pending'")
        pending_topups = (await cur.fetchone())[0]
        cur = await db.execute("SELECT SUM(total_price) FROM orders WHERE status IN ('paid','delivered')")
        total_revenue = (await cur.fetchone())[0] or 0.0

    text = (
        f"🔧 *Admin Panel*\n\n"
        f"👥 *Users:* {user_count}\n"
        f"⏳ *Pending Orders:* {pending_orders}\n"
        f"💰 *Pending Top\\-Ups:* {pending_topups}\n"
        f"📈 *Total Revenue:* \\${total_revenue:.2f}\n\n"
        f"Choose an action:"
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="MarkdownV2", reply_markup=admin_kb())
    else:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, parse_mode="MarkdownV2", reply_markup=admin_kb())


# ── Products ──────────────────────────────────────────────────────────────────
@admin_only
async def cb_admin_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products ORDER BY id DESC LIMIT 30")
        products = [dict(r) for r in await cur.fetchall()]

    rows = []
    for p in products:
        status = "✅" if p["is_active"] else "❌"
        stock = "∞" if p["stock"] == -1 else str(p["stock"])
        label = f"{status} {p['emoji']} {p['name'][:25]} | ${p['price']:.2f} | 📦{stock}"
        rows.append([InlineKeyboardButton(label, callback_data=f"admin_prod_mgr_{p['id']}")])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_home")])
    await update.callback_query.edit_message_text(
        "📦 *Products* — tap to manage:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(rows),
    )


@admin_only
async def cb_admin_prod_mgr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    if not p:
        await update.callback_query.answer("Not found!", show_alert=True)
        return

    p = dict(p)
    toggle_label = "🔴 Deactivate" if p["is_active"] else "🟢 Activate"

    await update.callback_query.edit_message_text(
        f"📦 *{escape_md(p['name'])}*\n"
        f"Price: \\${p['price']:.2f} | Stock: {'∞' if p['stock']==-1 else p['stock']} | Sold: {p['sold']}\n"
        f"Status: {'✅ Active' if p['is_active'] else '❌ Inactive'}",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(toggle_label,         callback_data=f"admin_prod_toggle_{prod_id}")],
            [InlineKeyboardButton("📝 Edit Stock",      callback_data=f"admin_prod_stock_{prod_id}")],
            [InlineKeyboardButton("🗑️ Delete",          callback_data=f"admin_prod_delete_{prod_id}")],
            [InlineKeyboardButton("⬅️ Back",            callback_data="admin_products")],
        ]),
    )


@admin_only
async def cb_admin_prod_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        await db.execute(
            "UPDATE products SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?",
            (prod_id,)
        )
        await db.commit()
    await cb_admin_prod_mgr(update, context)


@admin_only
async def cb_admin_prod_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        await db.execute("DELETE FROM products WHERE id=?", (prod_id,))
        await db.commit()
    await update.callback_query.edit_message_text(
        "🗑️ Product deleted\\.", parse_mode="MarkdownV2", reply_markup=admin_kb()
    )


# ── Add Product Conversation ──────────────────────────────────────────────────
@admin_only
async def cb_admin_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["new_prod"] = {}
    await update.callback_query.edit_message_text(
        "➕ *Add New Product*\n\nStep 1/6: Enter the *product name*:",
        parse_mode="MarkdownV2"
    )
    return ADMIN_PROD_NAME


async def recv_prod_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prod"]["name"] = update.message.text.strip()
    await update.message.reply_text("Step 2/6: Enter the *product description*:", parse_mode="MarkdownV2")
    return ADMIN_PROD_DESC


async def recv_prod_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prod"]["description"] = update.message.text.strip()
    await update.message.reply_text("Step 3/6: Enter the *price* \\(e\\.g\\. 4\\.99, or 0 for free\\):", parse_mode="MarkdownV2")
    return ADMIN_PROD_PRICE


async def recv_prod_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace("$", ""))
    except ValueError:
        await update.message.reply_text("⚠️ Invalid price. Try again:")
        return ADMIN_PROD_PRICE
    context.user_data["new_prod"]["price"] = price
    context.user_data["new_prod"]["is_free"] = 1 if price == 0 else 0
    await update.message.reply_text("Step 4/6: Enter *stock* \\(\\-1 for unlimited\\):", parse_mode="MarkdownV2")
    return ADMIN_PROD_STOCK


async def recv_prod_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        stock = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ Invalid stock. Enter a number:")
        return ADMIN_PROD_STOCK
    context.user_data["new_prod"]["stock"] = stock
    await update.message.reply_text("Step 5/6: Enter an *emoji* for this product \\(e\\.g\\. 🎵\\):", parse_mode="MarkdownV2")
    return ADMIN_PROD_EMOJI


async def recv_prod_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prod"]["emoji"] = update.message.text.strip()
    async with get_db() as db:
        cur = await db.execute("SELECT id, name FROM categories WHERE is_active=1")
        cats = [dict(r) for r in await cur.fetchall()]

    cat_list = "\n".join([f"{c['id']}\\. {escape_md(c['name'])}" for c in cats])
    await update.message.reply_text(
        f"Step 6/6: Choose *category ID*:\n\n{cat_list}",
        parse_mode="MarkdownV2"
    )
    return ADMIN_PROD_CAT


async def recv_prod_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        cat_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ Invalid ID. Try again:")
        return ADMIN_PROD_CAT

    p = context.user_data["new_prod"]
    async with get_db() as db:
        await db.execute(
            """INSERT INTO products (name, description, price, stock, emoji, category_id, is_free)
               VALUES (?,?,?,?,?,?,?)""",
            (p["name"], p["description"], p["price"], p["stock"],
             p["emoji"], cat_id, p["is_free"])
        )
        await db.commit()

    await update.message.reply_text(
        f"✅ *Product Added\\!*\n\n"
        f"{escape_md(p['emoji'])} *{escape_md(p['name'])}* \\— \\${p['price']:.2f}",
        parse_mode="MarkdownV2",
        reply_markup=admin_kb(),
    )
    context.user_data.pop("new_prod", None)
    return ConversationHandler.END


# ── Orders ────────────────────────────────────────────────────────────────────
@admin_only
async def cb_admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    async with get_db() as db:
        cur = await db.execute(
            """SELECT o.*, p.name as product_name, u.first_name, u.username
               FROM orders o
               JOIN products p ON o.product_id=p.id
               JOIN users u ON o.user_id=u.telegram_id
               ORDER BY o.created_at DESC LIMIT 25"""
        )
        orders = [dict(r) for r in await cur.fetchall()]

    if not orders:
        await update.callback_query.edit_message_text(
            "📋 No orders yet\\.", parse_mode="MarkdownV2", reply_markup=admin_kb()
        )
        return

    status_emoji = {"pending": "⏳", "paid": "✅", "delivered": "📦", "cancelled": "❌"}
    rows = []
    for o in orders:
        se = status_emoji.get(o["status"], "❓")
        label = f"{se} #{o['id']} {o['first_name'][:10]} — {o['product_name'][:15]} ${o['total_price']:.2f}"
        rows.append([InlineKeyboardButton(label, callback_data=f"admin_order_detail_{o['id']}")])

    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_home")])
    await update.callback_query.edit_message_text(
        "📋 *Orders* \\(latest 25\\):", parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(rows)
    )


@admin_only
async def cb_admin_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    order_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        cur = await db.execute(
            """SELECT o.*, p.name as product_name, u.first_name, u.username, u.telegram_id as uid
               FROM orders o
               JOIN products p ON o.product_id=p.id
               JOIN users u ON o.user_id=u.telegram_id
               WHERE o.id=?""",
            (order_id,)
        )
        o = await cur.fetchone()

    if not o:
        await update.callback_query.answer("Not found!", show_alert=True)
        return

    o = dict(o)
    uname = f"@{o['username']}" if o["username"] else str(o["uid"])
    await update.callback_query.edit_message_text(
        f"📋 *Order \\#{o['id']}*\n"
        f"👤 User: {escape_md(o['first_name'])} \\({escape_md(uname)}\\)\n"
        f"📦 Product: {escape_md(o['product_name'])} x{o['quantity']}\n"
        f"💰 Total: \\${o['total_price']:.2f}\n"
        f"💳 Payment: {escape_md(o['payment_method'])}\n"
        f"📊 Status: {o['status']}\n"
        f"📅 Date: {escape_md(o['created_at'][:16])}",
        parse_mode="MarkdownV2",
        reply_markup=admin_order_actions_kb(order_id),
    )


@admin_only
async def cb_admin_order_paid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    order_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        await db.execute(
            "UPDATE orders SET status='paid', updated_at=datetime('now') WHERE id=?",
            (order_id,)
        )
        await db.commit()
        cur = await db.execute("SELECT user_id, total_price, quantity FROM orders WHERE id=?", (order_id,))
        o = await cur.fetchone()
    # Update product sold
    async with get_db() as db:
        cur2 = await db.execute("SELECT product_id FROM orders WHERE id=?", (order_id,))
        row = await cur2.fetchone()
        if row:
            await db.execute(
                "UPDATE products SET sold=sold+? WHERE id=?",
                (o["quantity"], row["product_id"])
            )
            await db.commit()
    # Credit referral if first purchase
    from utils.helpers import update_membership, process_order_delivery
    await update_membership(o["user_id"])
    
    async with get_db() as db:
        await process_order_delivery(db, context.bot, order_id)
        cur_order = await db.execute("SELECT status FROM orders WHERE id=?", (order_id,))
        order_status = (await cur_order.fetchone())[0]

    await update.callback_query.answer("✅ Marked as Paid!", show_alert=True)
    if order_status != "delivered":
        try:
            await context.bot.send_message(
                chat_id=o["user_id"],
                text=f"✅ *Payment Confirmed\\!*\n\nYour order \\#{order_id} has been confirmed\\. "
                     f"Delivery is in progress\\.",
                parse_mode="MarkdownV2"
            )
        except Exception:
            logging.exception("Failed to notify user about payment confirmation for order #%s", order_id)
            pass


@admin_only
async def cb_admin_order_delivered(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    order_id = int(update.callback_query.data.split("_")[3])
    context.user_data["delivering_order"] = order_id
    await update.callback_query.edit_message_text(
        "📦 *Mark as Delivered*\n\nEnter delivery info to send to customer "
        "\\(credentials, instructions, etc.\\)\\.\n\nType /skip to skip sending info:",
        parse_mode="MarkdownV2"
    )
    return ADMIN_DELIVER_INFO


async def recv_deliver_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_id = context.user_data.get("delivering_order")
    info = update.message.text.strip()
    skip = info == "/skip"

    async with get_db() as db:
        await db.execute(
            "UPDATE orders SET status='delivered', delivery_info=?, updated_at=datetime('now') WHERE id=?",
            (None if skip else info, order_id)
        )
        await db.commit()
        cur = await db.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
        row = await cur.fetchone()

    if row:
        msg = f"📦 *Order \\#{order_id} Delivered\\!*\n\nYour product has been delivered\\! 🎉"
        if not skip:
            msg += f"\n\n📬 *Delivery Info:*\n`{escape_md(info)}`"
        
        msg += "\n\n⭐ *Please rate your purchase experience:*"
        from handlers.orders import rating_kb
        try:
            await context.bot.send_message(
                chat_id=row["user_id"], text=msg, parse_mode="MarkdownV2",
                reply_markup=rating_kb(order_id)
            )
        except Exception:
            logging.exception("Failed to send delivery info to user for order #%s", order_id)
            pass

    await update.message.reply_text(
        f"✅ Order \\#{order_id} marked as delivered\\.", parse_mode="MarkdownV2",
        reply_markup=admin_kb()
    )
    return ConversationHandler.END


@admin_only
async def cb_admin_order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    order_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        o = await cur.fetchone()
        if o and o["payment_method"] == "Wallet" and o["status"] == "paid":
            # Refund wallet
            await db.execute(
                "UPDATE users SET balance=balance+? WHERE telegram_id=?",
                (o["total_price"], o["user_id"])
            )
        await db.execute(
            "UPDATE orders SET status='cancelled', updated_at=datetime('now') WHERE id=?",
            (order_id,)
        )
        await db.commit()
    await update.callback_query.answer("❌ Order cancelled!", show_alert=True)
    if o:
        try:
            await context.bot.send_message(
                chat_id=o["user_id"],
                text=f"❌ *Order \\#{order_id} Cancelled*\n\nYour order has been cancelled\\."
                     + (f" \\${o['total_price']:.2f} refunded to your wallet\\." if o["payment_method"] == "Wallet" and o["status"] == "paid" else ""),
                parse_mode="MarkdownV2"
            )
        except Exception:
            logging.exception("Failed to notify user about order cancellation for order #%s", order_id)
            pass


# ── Top-Up Requests ───────────────────────────────────────────────────────────
@admin_only
async def cb_admin_topups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    async with get_db() as db:
        cur = await db.execute(
            """SELECT t.*, u.first_name, u.username
               FROM topup_requests t JOIN users u ON t.user_id=u.telegram_id
               WHERE t.status='pending' ORDER BY t.created_at DESC LIMIT 20"""
        )
        topups = [dict(r) for r in await cur.fetchall()]

    if not topups:
        await update.callback_query.edit_message_text(
            "💸 No pending top\\-up requests\\.", parse_mode="MarkdownV2", reply_markup=admin_kb()
        )
        return

    rows = []
    for t in topups:
        label = f"#{t['id']} {t['first_name'][:10]} — ${t['amount']:.2f} ({t['payment_method']})"
        rows.append([InlineKeyboardButton(label, callback_data=f"admin_topup_detail_{t['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_home")])
    await update.callback_query.edit_message_text(
        "💸 *Pending Top\\-Ups*:", parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(rows)
    )


@admin_only
async def cb_admin_topup_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    req_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        cur = await db.execute(
            "SELECT t.*, u.first_name, u.username FROM topup_requests t JOIN users u ON t.user_id=u.telegram_id WHERE t.id=?",
            (req_id,)
        )
        t = await cur.fetchone()
    if not t:
        return
    t = dict(t)
    await update.callback_query.edit_message_text(
        f"💸 *Top\\-Up Request \\#{t['id']}*\n"
        f"👤 User: {escape_md(t['first_name'])}\n"
        f"💰 Amount: \\${t['amount']:.2f}\n"
        f"💳 Method: {escape_md(t['payment_method'])}\n"
        f"📅 Date: {escape_md(t['created_at'][:16])}",
        parse_mode="MarkdownV2",
        reply_markup=admin_topup_actions_kb(req_id),
    )


@admin_only
async def cb_admin_topup_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    req_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM topup_requests WHERE id=?", (req_id,))
        req = await cur.fetchone()
        if not req or req["status"] != "pending":
            await update.callback_query.answer("Already processed!", show_alert=True)
            return
        req = dict(req)
        await db.execute(
            "UPDATE topup_requests SET status='approved', updated_at=datetime('now') WHERE id=?",
            (req_id,)
        )
        await db.execute(
            "UPDATE users SET balance=balance+? WHERE telegram_id=?",
            (req["amount"], req["user_id"])
        )
        await db.commit()

    await record_transaction(req["user_id"], req["amount"], "topup", f"Wallet top-up #{req_id}")
    await update.callback_query.answer("✅ Approved!", show_alert=True)
    try:
        await context.bot.send_message(
            chat_id=req["user_id"],
            text=f"✅ *Top\\-Up Approved\\!*\n\n"
                 f"\\${req['amount']:.2f} has been added to your wallet\\. 💰",
            parse_mode="MarkdownV2"
        )
    except Exception:
        logging.exception("Failed to notify user about top-up approval for request #%s", req_id)
        pass
    await cb_admin_topups(update, context)


@admin_only
async def cb_admin_topup_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    req_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM topup_requests WHERE id=?", (req_id,))
        req = await cur.fetchone()
        if not req:
            return
        req = dict(req)
        await db.execute(
            "UPDATE topup_requests SET status='rejected', updated_at=datetime('now') WHERE id=?",
            (req_id,)
        )
        await db.commit()
    try:
        await context.bot.send_message(
            chat_id=req["user_id"],
            text=f"❌ *Top\\-Up Rejected*\n\nRequest \\#{req_id} was rejected\\. "
                 f"Please contact support if you believe this is an error\\.",
            parse_mode="MarkdownV2"
        )
    except Exception:
        logging.exception("Failed to notify user about top-up rejection for request #%s", req_id)
        pass
    await cb_admin_topups(update, context)


# ── Users ─────────────────────────────────────────────────────────────────────
@admin_only
async def cb_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users ORDER BY created_at DESC LIMIT 30")
        users = [dict(r) for r in await cur.fetchall()]

    rows = []
    for u in users:
        uname = f"@{u['username']}" if u["username"] else str(u["telegram_id"])
        label = f"{'🚫' if u['is_banned'] else '👤'} {u['first_name'][:12]} — ${u['balance']:.2f}"
        rows.append([InlineKeyboardButton(label, callback_data=f"admin_user_detail_{u['telegram_id']}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="admin_home")])
    await update.callback_query.edit_message_text(
        "👥 *Users* \\(latest 30\\):", parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(rows)
    )


@admin_only
async def cb_admin_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    uid = int(update.callback_query.data.split("_")[3])
    user = await get_user(uid)
    if not user:
        return
    user = dict(user)
    ban_label = "🟢 Unban" if user["is_banned"] else "🚫 Ban"
    await update.callback_query.edit_message_text(
        f"👤 *{escape_md(user['first_name'])}*\n"
        f"ID: `{user['telegram_id']}`\n"
        f"Balance: \\${user['balance']:.2f}\n"
        f"Spent: \\${user['total_spent']:.2f}\n"
        f"Tier: {escape_md(user['membership'])}\n"
        f"Banned: {'Yes' if user['is_banned'] else 'No'}",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Balance",   callback_data=f"admin_addbal_{uid}")],
            [InlineKeyboardButton(ban_label,          callback_data=f"admin_ban_{uid}")],
            [InlineKeyboardButton("⬅️ Back",          callback_data="admin_users")],
        ]),
    )


@admin_only
async def cb_admin_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    uid = int(update.callback_query.data.split("_")[2])
    context.user_data["addbal_uid"] = uid
    await update.callback_query.edit_message_text(
        "💰 *Add Balance*\n\nEnter amount to add \\(can be negative to deduct\\):",
        parse_mode="MarkdownV2"
    )
    return ADMIN_ADD_BALANCE_AMOUNT


async def recv_add_balance_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = float(update.message.text.strip().replace("$", ""))
    except ValueError:
        await update.message.reply_text("⚠️ Invalid amount.")
        return ADMIN_ADD_BALANCE_AMOUNT

    uid = context.user_data.get("addbal_uid")
    await update_user_balance(uid, amount)
    await record_transaction(uid, amount, "topup" if amount > 0 else "deduction", "Admin adjustment")
    sign = "\\+" if amount > 0 else ""
    await update.message.reply_text(
        f"✅ Balance updated\\! {sign}\\${abs(amount):.2f} for user `{uid}`",
        parse_mode="MarkdownV2", reply_markup=admin_kb()
    )
    try:
        await context.bot.send_message(
            chat_id=uid,
            text=f"💰 *Balance Updated*\n\nAdmin {'added' if amount > 0 else 'deducted'} "
                 f"\\${abs(amount):.2f} {'to' if amount > 0 else 'from'} your wallet\\.",
            parse_mode="MarkdownV2"
        )
    except Exception:
        logging.exception("Failed to notify user about balance update for user %s", uid)
        pass
    return ConversationHandler.END


@admin_only
async def cb_admin_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    uid = int(update.callback_query.data.split("_")[2])
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET is_banned = CASE WHEN is_banned=1 THEN 0 ELSE 1 END WHERE telegram_id=?",
            (uid,)
        )
        await db.commit()
    await update.callback_query.answer("User ban status toggled!", show_alert=True)


# ── Coupons ───────────────────────────────────────────────────────────────────
@admin_only
async def cb_admin_coupons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM coupons ORDER BY id DESC LIMIT 20")
        coupons = [dict(r) for r in await cur.fetchall()]

    rows = []
    for c in coupons:
        status = "✅" if c["is_active"] else "❌"
        disc = f"{c['discount_percent']}%" if c["discount_percent"] > 0 else f"${c['flat_discount']:.2f}"
        label = f"{status} {c['code']} — {disc} | Used: {c['uses_count']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"admin_coupon_toggle_{c['id']}")])
    rows.append([InlineKeyboardButton("➕ New Coupon", callback_data="admin_coupon_new")])
    rows.append([InlineKeyboardButton("⬅️ Back",       callback_data="admin_home")])
    await update.callback_query.edit_message_text(
        "🎟️ *Coupons*:", parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup(rows)
    )


@admin_only
async def cb_admin_coupon_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    coupon_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        await db.execute(
            "UPDATE coupons SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?",
            (coupon_id,)
        )
        await db.commit()
    await cb_admin_coupons(update, context)


@admin_only
async def cb_admin_coupon_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["new_coupon"] = {}
    await update.callback_query.edit_message_text(
        "🎟️ *New Coupon*\n\nStep 1/3: Enter the coupon *code* \\(e\\.g\\. SAVE20\\):",
        parse_mode="MarkdownV2"
    )
    return ADMIN_COUPON_CODE


async def recv_coupon_code_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_coupon"]["code"] = update.message.text.strip().upper()
    await update.message.reply_text(
        "Step 2/3: Enter *discount* \\— percentage \\(e\\.g\\. 20 for 20%\\) or flat \\(e\\.g\\. \\$2 for \\$2 off\\):",
        parse_mode="MarkdownV2"
    )
    return ADMIN_COUPON_DISC


async def recv_coupon_disc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.endswith("%"):
        context.user_data["new_coupon"]["discount_percent"] = float(text[:-1])
        context.user_data["new_coupon"]["flat_discount"] = 0
    elif text.startswith("$"):
        context.user_data["new_coupon"]["flat_discount"] = float(text[1:])
        context.user_data["new_coupon"]["discount_percent"] = 0
    else:
        try:
            context.user_data["new_coupon"]["discount_percent"] = float(text)
            context.user_data["new_coupon"]["flat_discount"] = 0
        except ValueError:
            await update.message.reply_text("⚠️ Invalid. Enter like: 20% or $5")
            return ADMIN_COUPON_DISC
    await update.message.reply_text("Step 3/3: Max *number of uses* \\(\\-1 for unlimited\\):", parse_mode="MarkdownV2")
    return ADMIN_COUPON_USES


async def recv_coupon_uses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        max_uses = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ Invalid. Enter a number:")
        return ADMIN_COUPON_USES

    c = context.user_data["new_coupon"]
    async with get_db() as db:
        await db.execute(
            "INSERT INTO coupons (code, discount_percent, flat_discount, max_uses) VALUES (?,?,?,?)",
            (c["code"], c.get("discount_percent", 0), c.get("flat_discount", 0), max_uses)
        )
        await db.commit()

    disc_str = f"{c['discount_percent']}%" if c.get("discount_percent", 0) > 0 else f"${c.get('flat_discount', 0):.2f}"
    await update.message.reply_text(
        f"✅ Coupon *{escape_md(c['code'])}* created\\! \\({escape_md(disc_str)} off\\)",
        parse_mode="MarkdownV2", reply_markup=admin_kb()
    )
    context.user_data.pop("new_coupon", None)
    return ConversationHandler.END


# ── Broadcast ─────────────────────────────────────────────────────────────────
@admin_only
async def cb_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "📢 *Broadcast*\n\nType the message to send to ALL users:\n\\(Supports MarkdownV2\\)",
        parse_mode="MarkdownV2"
    )
    return ADMIN_BROADCAST


async def run_broadcast_in_background(bot, user_ids: list, text: str, admin_id: int):
    import asyncio
    from telegram.error import RetryAfter
    from utils.messages import escape_md
    
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            try:
                # Try MarkdownV2 first
                await bot.send_message(chat_id=uid, text=text, parse_mode="MarkdownV2")
            except Exception:
                logging.exception("Failed to send broadcast message (MarkdownV2 fallback) to user %s", uid)
                # Fallback to plain text if markdown formatting is invalid
                await bot.send_message(chat_id=uid, text=text)
            sent += 1
            await asyncio.sleep(0.05)  # Throttling to respect Telegram's 30/sec rate limits
        except RetryAfter as e:
            # Respect Telegram's explicit rate limit backoff request
            await asyncio.sleep(e.retry_after)
            try:
                await bot.send_message(chat_id=uid, text=text)
                sent += 1
            except Exception:
                logging.exception("Failed to send broadcast retry to user %s after rate limit", uid)
                failed += 1
        except Exception:
            logging.exception("Failed to send broadcast to user %s", uid)
            failed += 1

    try:
        await bot.send_message(
            chat_id=admin_id,
            text=f"📢 *Broadcast Completed\\!*\n\n"
                 f"✅ *Delivered:* `{sent}`\n"
                 f"❌ *Failed:* `{failed}`",
            parse_mode="MarkdownV2"
        )
    except Exception:
        logging.exception("Failed to send broadcast completion notification to admin %s", admin_id)
        pass


async def recv_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import asyncio
    text = update.message.text
    admin_id = update.effective_user.id
    
    async with get_db() as db:
        cur = await db.execute("SELECT telegram_id FROM users WHERE is_banned=0")
        users = [r[0] for r in await cur.fetchall()]

    if not users:
        await update.message.reply_text("⚠️ No active users found to broadcast to.", reply_markup=admin_kb())
        return ConversationHandler.END

    # Start non-blocking task in background
    asyncio.create_task(run_broadcast_in_background(context.bot, users, text, admin_id))

    await update.message.reply_text(
        f"📢 *Broadcast Started\\!*\n\n"
        f"Sending messages in the background to `{len(users)}` users\\.\n"
        f"You will receive a notification here when it is complete\\.",
        parse_mode="MarkdownV2",
        reply_markup=admin_kb()
    )
    return ConversationHandler.END


# ── Stock Management ──────────────────────────────────────────────────────────
@admin_only
async def cb_admin_prod_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        cur = await db.execute("SELECT name, stock FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()
        
        cur = await db.execute("SELECT COUNT(*) FROM product_stock WHERE product_id=? AND is_sold=0", (prod_id,))
        unsold_count = (await cur.fetchone())[0]

    if not p:
        await update.callback_query.answer("Product not found!", show_alert=True)
        return

    p = dict(p)
    await update.callback_query.edit_message_text(
        f"📦 *Manage Stock: {escape_md(p['name'])}*\n\n"
        f"📋 *In\\-Stock Count \\(Database\\):* `{unsold_count}` items\n"
        f"📊 *Current Displayed Stock:* `{escape_md('Unlimited' if p['stock'] == -1 else str(p['stock']))}`\n\n"
        f"Choose an action:",
        parse_mode="MarkdownV2",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Add Stock (Text/Keys)", callback_data=f"admin_add_stock_{prod_id}")],
            [InlineKeyboardButton("🗑️ Clear Unsold Stock",  callback_data=f"admin_clear_stock_{prod_id}")],
            [InlineKeyboardButton("⬅️ Back to Product",      callback_data=f"admin_prod_mgr_{prod_id}")],
        ])
    )


@admin_only
async def cb_admin_add_stock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[3])
    context.user_data["stock_prod_id"] = prod_id
    await update.callback_query.edit_message_text(
        "📥 *Add Stock Items*\n\n"
        "Please send the stock data \\(accounts, keys, codes, or credentials\\)\\.\n"
        "💡 *Important:* Put *one item per line*\\. Each line will be added as a separate stock item\\.",
        parse_mode="MarkdownV2"
    )
    return ADMIN_UPLOAD_STOCK


@admin_only
async def recv_stock_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prod_id = context.user_data.get("stock_prod_id")
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("⚠️ Content is empty. Try again:")
        return ADMIN_UPLOAD_STOCK

    items = [line.strip() for line in text.split("\n") if line.strip()]
    if not items:
        await update.message.reply_text("⚠️ No valid lines found. Try again:")
        return ADMIN_UPLOAD_STOCK

    async with get_db() as db:
        for item in items:
            await db.execute(
                "INSERT INTO product_stock (product_id, data, is_sold) VALUES (?, ?, 0)",
                (prod_id, item)
            )
        
        cur = await db.execute("SELECT COUNT(*) FROM product_stock WHERE product_id=? AND is_sold=0", (prod_id,))
        new_count = (await cur.fetchone())[0]

        cur = await db.execute("SELECT stock FROM products WHERE id=?", (prod_id,))
        p_stock = (await cur.fetchone())[0]
        if p_stock != -1:
            await db.execute("UPDATE products SET stock = ? WHERE id = ?", (new_count, prod_id))
        
        await db.commit()

    await update.message.reply_text(
        f"✅ *Stock Added\\!*\n\n"
        f"Successfully loaded `{len(items)}` new items to the inventory\\.\n"
        f"Total active stock is now `{new_count}`\\.",
        parse_mode="MarkdownV2",
        reply_markup=admin_kb()
    )
    context.user_data.pop("stock_prod_id", None)
    return ConversationHandler.END


@admin_only
async def cb_admin_clear_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[3])
    async with get_db() as db:
        await db.execute("DELETE FROM product_stock WHERE product_id=? AND is_sold=0", (prod_id,))
        cur = await db.execute("SELECT stock FROM products WHERE id=?", (prod_id,))
        p_stock = (await cur.fetchone())[0]
        if p_stock != -1:
            await db.execute("UPDATE products SET stock = 0 WHERE id = ?", (prod_id,))
        await db.commit()
        
    await update.callback_query.answer("🧹 Unsold stock cleared!", show_alert=True)
    await cb_admin_prod_stock(update, context)


# ── Register ──────────────────────────────────────────────────────────────────
def register_admin_handlers(app):
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(cmd_admin,               pattern="^admin_home$"))
    app.add_handler(CallbackQueryHandler(cb_admin_products,       pattern="^admin_products$"))
    app.add_handler(CallbackQueryHandler(cb_admin_prod_mgr,       pattern=r"^admin_prod_mgr_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_prod_toggle,    pattern=r"^admin_prod_toggle_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_prod_delete,    pattern=r"^admin_prod_delete_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_orders,         pattern="^admin_orders$"))
    app.add_handler(CallbackQueryHandler(cb_admin_order_detail,   pattern=r"^admin_order_detail_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_order_paid,     pattern=r"^admin_ord_paid_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_order_cancel,   pattern=r"^admin_ord_cancel_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_topups,         pattern="^admin_topups$"))
    app.add_handler(CallbackQueryHandler(cb_admin_topup_detail,   pattern=r"^admin_topup_detail_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_topup_approve,  pattern=r"^admin_topup_approve_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_topup_reject,   pattern=r"^admin_topup_reject_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_users,          pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(cb_admin_user_detail,    pattern=r"^admin_user_detail_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_add_balance,    pattern=r"^admin_addbal_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_ban,            pattern=r"^admin_ban_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_coupons,        pattern="^admin_coupons$"))
    app.add_handler(CallbackQueryHandler(cb_admin_coupon_toggle,  pattern=r"^admin_coupon_toggle_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_prod_stock,     pattern=r"^admin_prod_stock_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_admin_clear_stock,    pattern=r"^admin_clear_stock_\d+$"))


    # Add product conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_admin_add_product, pattern="^admin_add_product$")],
        states={
            ADMIN_PROD_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_prod_name)],
            ADMIN_PROD_DESC:  [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_prod_desc)],
            ADMIN_PROD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_prod_price)],
            ADMIN_PROD_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_prod_stock)],
            ADMIN_PROD_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_prod_emoji)],
            ADMIN_PROD_CAT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_prod_cat)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_chat=True, per_user=True,
        conversation_timeout=300,
    ))

    # Broadcast conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_admin_broadcast, pattern="^admin_broadcast$")],
        states={ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_broadcast)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_chat=True, per_user=True,
        conversation_timeout=300,
    ))

    # Add balance conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_admin_add_balance, pattern=r"^admin_addbal_\d+$")],
        states={ADMIN_ADD_BALANCE_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_add_balance_amount)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_chat=True, per_user=True,
        conversation_timeout=300,
    ))

    # Deliver order conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_admin_order_delivered, pattern=r"^admin_ord_delivered_\d+$")],
        states={ADMIN_DELIVER_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_deliver_info)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_chat=True, per_user=True,
        conversation_timeout=300,
    ))

    # New coupon conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_admin_coupon_new, pattern="^admin_coupon_new$")],
        states={
            ADMIN_COUPON_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_coupon_code_admin)],
            ADMIN_COUPON_DISC: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_coupon_disc)],
            ADMIN_COUPON_USES: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_coupon_uses)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_chat=True, per_user=True,
        conversation_timeout=300,
    ))

    # Add stock conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_admin_add_stock_start, pattern=r"^admin_add_stock_\d+$")],
        states={
            ADMIN_UPLOAD_STOCK: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_stock_data)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_chat=True, per_user=True,
        conversation_timeout=300,
    ))

