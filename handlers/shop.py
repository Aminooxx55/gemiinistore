"""Shop handler — browse categories, products, and buy flow."""
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from database.db import get_db
from utils.helpers import get_user, get_product_unit_price, get_photo_object
from utils.keyboards import (
    shop_categories_kb, products_list_kb, product_detail_kb,
    quantity_kb, confirm_purchase_kb, back_home_kb,
)
from utils.messages import product_detail_msg, confirm_purchase_msg

# ConversationHandler states
AWAIT_CUSTOM_QTY = 1
AWAIT_COUPON_CODE = 2


async def cb_shop_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    message = update.callback_query.message
    
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE is_active=1 AND is_free=0 ORDER BY id")
        products = [dict(r) for r in await cur.fetchall()]

    from config import WELCOME_BANNER_URL

    if not products:
        text = "🛍️ <b>Shop</b>\n\nNo products available yet. Check back soon!"
        markup = back_home_kb()
        try:
            if message.photo or message.document or message.video:
                await message.edit_caption(caption=text, parse_mode="HTML", reply_markup=markup)
            else:
                await message.edit_text(text=text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await message.delete()
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_user.id,
                    photo=get_photo_object(WELCOME_BANNER_URL),
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
        return

    if len(products) == 1:
        # Jump directly to product detail using our new helper
        await _show_product_detail(message, update.effective_user.id, context, products[0]['id'])
        return

    text = (
        "🛍️ <b>Shop — All Products</b>\n\n"
        "Browse our products below. "
        "Green = in stock, Red = out of stock."
    )
    markup = products_list_kb(products, 0)
    try:
        if message.photo or message.document or message.video:
            await message.edit_caption(caption=text, parse_mode="HTML", reply_markup=markup)
        else:
            await message.edit_text(text=text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await message.delete()
        try:
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=get_photo_object(WELCOME_BANNER_URL),
                caption=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )

async def cb_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This handler is deprecated since categories are bypassed
    await cb_shop_home(update, context)


async def _show_product_detail(message, user_id: int, context: ContextTypes.DEFAULT_TYPE, prod_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    from config import WELCOME_BANNER_URL
    if not p:
        text = "❌ Product not found."
        markup = back_home_kb()
        try:
            await message.edit_caption(caption=text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            try:
                await message.delete()
            except Exception:
                pass
            await context.bot.send_photo(
                chat_id=user_id,
                photo=get_photo_object(WELCOME_BANNER_URL),
                caption=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        return

    p = dict(p)
    out_of_stock = (p["stock"] == 0)

    text = product_detail_msg(p)
    if out_of_stock:
        text += "\n\n❌ <b>OUT OF STOCK</b>"

    from config import DEFAULT_PRODUCT_BANNER_URL
    img_url = p.get("image_url") or DEFAULT_PRODUCT_BANNER_URL
    markup = product_detail_kb(prod_id, p["is_free"]) if not out_of_stock else back_home_kb()

    from telegram import InputMediaPhoto
    try:
        if message.photo or message.document or message.video:
            await message.edit_media(
                media=InputMediaPhoto(
                    media=get_photo_object(img_url),
                    caption=text,
                    parse_mode="HTML"
                ),
                reply_markup=markup
            )
        else:
            # Cannot edit_media on a text message. Delete and send new.
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=get_photo_object(img_url),
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
    except Exception:
        try:
            await message.delete()
        except Exception:
            pass
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=get_photo_object(img_url),
                caption=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )


async def cb_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[1])
    await _show_product_detail(update.callback_query.message, update.effective_user.id, context, prod_id)


async def cb_buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show quantity selector."""
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[2])

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    if not p:
        await update.callback_query.answer("Product not found!", show_alert=True)
        return

    p = dict(p)
    message = update.callback_query.message

    from config import DEFAULT_PRODUCT_BANNER_URL
    img_url = p.get("image_url") or DEFAULT_PRODUCT_BANNER_URL

    if p["is_free"]:
        # Skip quantity for free items, go straight to confirm
        context.user_data["pending"] = {"product_id": prod_id, "qty": 1, "coupon_discount": 0.0}
        user = await get_user(update.effective_user.id)
        text = confirm_purchase_msg(p["name"], 1, 0.0, 0.0, user["balance"])
        markup = confirm_purchase_kb(prod_id, 1)
        try:
            if message.photo or message.document or message.video:
                await message.edit_caption(caption=text, parse_mode="HTML", reply_markup=markup)
            else:
                await message.edit_text(text=text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await message.delete()
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_user.id,
                    photo=get_photo_object(img_url),
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
            except Exception:
                await context.bot.send_message(
                    chat_id=update.effective_user.id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=markup
                )
        return

    text = (
        f"🛒 <b>Buy: {p['name']}</b>\n\n"
        f"💲 Base Price: ${p['price']:.2f} each\n"
    )
    
    pn_lower = p["name"].lower()
    if "google ai pro" in pn_lower or "gemini" in pn_lower:
        text += "Select quantity:    ( 1-9 $0.70 | +10 $0.70 | +30 $0.70 | +50 $0.70 )"
    else:
        text += "Select quantity:"
    markup = quantity_kb(prod_id)
    try:
        if message.photo or message.document or message.video:
            await message.edit_caption(caption=text, parse_mode="HTML", reply_markup=markup)
        else:
            await message.edit_text(text=text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await message.delete()
        try:
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=get_photo_object(img_url),
                caption=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )


async def cb_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle quantity selection."""
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    prod_id = int(parts[1])
    qty = int(parts[2])
    await _show_confirm(update, context, prod_id, qty)


async def _show_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE, prod_id: int, qty: int):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    if not p:
        return

    p = dict(p)

    # Check stock
    if p["stock"] != -1 and p["stock"] < qty:
        await update.callback_query.answer(
            f"⚠️ Only {p['stock']} in stock!", show_alert=True
        )
        return

    coupon_discount = context.user_data.get("pending", {}).get("coupon_discount", 0.0)
    unit_price = get_product_unit_price(p["name"], p["price"], qty, p["id"])
    total = unit_price * qty
    user = await get_user(update.effective_user.id)

    context.user_data["pending"] = {
        "product_id": prod_id,
        "qty": qty,
        "coupon_discount": coupon_discount,
    }

    text = confirm_purchase_msg(
        p["name"], qty, unit_price, total, user["balance"], coupon_discount
    )
    message = update.callback_query.message
    markup = confirm_purchase_kb(prod_id, qty)
    
    from config import DEFAULT_PRODUCT_BANNER_URL
    img_url = p.get("image_url") or DEFAULT_PRODUCT_BANNER_URL
    try:
        if message.photo or message.document or message.video:
            await message.edit_caption(caption=text, parse_mode="HTML", reply_markup=markup)
        else:
            await message.edit_text(text=text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await message.delete()
        try:
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=get_photo_object(img_url),
                caption=text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup
            )


async def cb_custom_qty_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to type a custom quantity."""
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[2])
    context.user_data["awaiting_qty_for"] = prod_id
    try:
        await update.callback_query.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="✏️ <b>Enter Custom Quantity</b>\n\nType the number of items you want:",
        parse_mode="HTML",
        reply_markup=back_home_kb(),
    )
    return AWAIT_CUSTOM_QTY


async def recv_custom_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    prod_id = context.user_data.get("awaiting_qty_for")
    if not prod_id:
        return ConversationHandler.END

    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("⚠️ Please enter a valid positive number.", parse_mode="HTML")
        return AWAIT_CUSTOM_QTY

    qty = int(text)
    # Rebuild a fake callback to reuse _show_confirm
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    if not p:
        await update.message.reply_text("❌ Product not found.", parse_mode="HTML")
        return ConversationHandler.END

    p = dict(p)
    if p["stock"] != -1 and p["stock"] < qty:
        await update.message.reply_text(
            f"⚠️ Only <b>{p['stock']}</b> item(s) in stock!",
            parse_mode="HTML"
        )
        return AWAIT_CUSTOM_QTY

    user = await get_user(update.effective_user.id)
    unit_price = get_product_unit_price(p["name"], p["price"], qty, p["id"])
    total = unit_price * qty
    context.user_data["pending"] = {"product_id": prod_id, "qty": qty, "coupon_discount": 0.0}
    text_msg = confirm_purchase_msg(p["name"], qty, unit_price, total, user["balance"])
    await update.message.reply_text(
        text_msg, parse_mode="HTML",
        reply_markup=confirm_purchase_kb(prod_id, qty)
    )
    return ConversationHandler.END


async def cb_coupon_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    prod_id, qty = int(parts[1]), int(parts[2])
    context.user_data["coupon_for"] = (prod_id, qty)
    try:
        await update.callback_query.message.delete()
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="🎟️ <b>Apply Coupon</b>\n\nEnter your coupon code:",
        parse_mode="HTML",
        reply_markup=back_home_kb(),
    )
    return AWAIT_COUPON_CODE


async def recv_coupon_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    pair = context.user_data.get("coupon_for")
    if not pair:
        return ConversationHandler.END

    prod_id, qty = pair

    async with get_db() as db:
        cur = await db.execute(
            """SELECT * FROM coupons
               WHERE code=? AND is_active=1
               AND (expires_at IS NULL OR expires_at > datetime('now'))
               AND (max_uses=-1 OR uses_count < max_uses)""",
            (code,)
        )
        coupon = await cur.fetchone()

        if not coupon:
            await update.message.reply_text("❌ Invalid or expired coupon.", parse_mode="HTML")
            return AWAIT_COUPON_CODE

        # Check if user already used it
        cur2 = await db.execute(
            "SELECT id FROM coupon_uses WHERE coupon_id=? AND user_id=?",
            (coupon["id"], update.effective_user.id)
        )
        already_used = await cur2.fetchone()
        if already_used:
            await update.message.reply_text("⚠️ You have already used this coupon.", parse_mode="HTML")
            return ConversationHandler.END

        cur3 = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur3.fetchone()

    if not p:
        return ConversationHandler.END

    p = dict(p)
    coupon = dict(coupon)
    unit_price = get_product_unit_price(p["name"], p["price"], qty, p["id"])
    total = unit_price * qty
    discount = 0.0
    if coupon["discount_percent"] > 0:
        discount = round(total * coupon["discount_percent"] / 100, 2)
    elif coupon["flat_discount"] > 0:
        discount = min(coupon["flat_discount"], total)

    context.user_data["pending"] = {
        "product_id": prod_id,
        "qty": qty,
        "coupon_id": coupon["id"],
        "coupon_discount": discount,
    }

    user = await get_user(update.effective_user.id)
    text = confirm_purchase_msg(p["name"], qty, unit_price, total, user["balance"], discount)
    await update.message.reply_text(
        f"✅ <b>Coupon Applied!</b> Discount: -${discount:.2f}\n\n" + text,
        parse_mode="HTML",
        reply_markup=confirm_purchase_kb(prod_id, qty),
    )
    return ConversationHandler.END


async def cb_cancel_shop_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    await update.callback_query.answer()
    
    # Clear user data states
    context.user_data.pop("awaiting_qty_for", None)
    context.user_data.pop("coupon_for", None)
    context.user_data.pop("pending", None)

    data = update.callback_query.data
    
    # Route to appropriate handlers
    if data == "main_menu":
        from handlers.start import cb_main_menu
        await cb_main_menu(update, context)
    elif data == "shop_home":
        await cb_shop_home(update, context)
    elif data.startswith("cat_"):
        await cb_category(update, context)
    elif data.startswith("prod_"):
        await cb_product_detail(update, context)
    elif data == "support":
        from handlers.start import cb_support
        await cb_support(update, context)
    else:
        from handlers.start import cb_main_menu
        await cb_main_menu(update, context)

    return ConversationHandler.END


async def cb_cancel_shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from telegram.ext import ConversationHandler
    # Clear user data states
    context.user_data.pop("awaiting_qty_for", None)
    context.user_data.pop("coupon_for", None)
    context.user_data.pop("pending", None)

    # Route start command
    from handlers.start import cmd_start
    await cmd_start(update, context)
    return ConversationHandler.END


def register_shop_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_shop_home,     pattern="^shop_home$"))
    app.add_handler(CallbackQueryHandler(cb_category,      pattern=r"^cat_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_product_detail,pattern=r"^prod_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_buy_start,     pattern=r"^buy_start_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_quantity,      pattern=r"^qty_\d+_\d+$"))

    # Custom quantity conversation
    from telegram.ext import ConversationHandler, CommandHandler
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_custom_qty_prompt, pattern=r"^qty_custom_\d+$")],
        states={AWAIT_CUSTOM_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_custom_qty)]},
        fallbacks=[
            CommandHandler("start", cb_cancel_shop_command),
            CallbackQueryHandler(cb_cancel_shop_conv, pattern="^.*$")
        ],
        per_chat=True, per_user=True,
    ))

    # Coupon conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_coupon_prompt, pattern=r"^coupon_\d+_\d+$")],
        states={AWAIT_COUPON_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_coupon_code)]},
        fallbacks=[
            CommandHandler("start", cb_cancel_shop_command),
            CallbackQueryHandler(cb_cancel_shop_conv, pattern="^.*$")
        ],
        per_chat=True, per_user=True,
    ))
