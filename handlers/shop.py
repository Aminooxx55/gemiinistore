"""Shop handler — browse categories, products, and buy flow."""
from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from database.db import get_db
from utils.helpers import get_user, get_product_unit_price, get_photo_object
from utils.keyboards import (
    shop_categories_kb, products_list_kb, product_detail_kb,
    quantity_kb, confirm_purchase_kb, back_home_kb,
)
from utils.messages import product_detail_msg, confirm_purchase_msg, escape_md

# ConversationHandler states
AWAIT_CUSTOM_QTY = 1
AWAIT_COUPON_CODE = 2


async def cb_shop_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    message = update.callback_query.message
    
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM categories WHERE is_active=1 ORDER BY id"
        )
        cats = [dict(r) for r in await cur.fetchall()]

    cats = [c for c in cats if "Freeb" not in c["name"]]

    from config import WELCOME_BANNER_URL

    if not cats:
        text = "🛍️ No categories available yet\\. Check back soon\\!"
        markup = back_home_kb()
        try:
            await message.edit_caption(caption=text, parse_mode="MarkdownV2", reply_markup=markup)
        except Exception:
            await message.delete()
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=get_photo_object(WELCOME_BANNER_URL),
                caption=text,
                parse_mode="MarkdownV2",
                reply_markup=markup
            )
        return

    # Check if len(cats) == 1
    if len(cats) == 1:
        cat_id = cats[0]["id"]
        cat_name = cats[0]["name"]
        async with get_db() as db:
            cur = await db.execute(
                "SELECT * FROM products WHERE category_id=? AND is_active=1 AND is_free=0 ORDER BY id",
                (cat_id,)
            )
            products = [dict(r) for r in await cur.fetchall()]
        if products:
            text = f"📦 *{escape_md(cat_name)}*\n\nSelect a product to view details:"
            markup = products_list_kb(products, cat_id)
            try:
                await message.edit_caption(caption=text, parse_mode="MarkdownV2", reply_markup=markup)
            except Exception:
                await message.delete()
                await context.bot.send_photo(
                    chat_id=update.effective_user.id,
                    photo=get_photo_object(WELCOME_BANNER_URL),
                    caption=text,
                    parse_mode="MarkdownV2",
                    reply_markup=markup
                )
            return

    text = (
        "🛍️ *Shop — Choose a Category*\n\n"
        "Browse our products below\\. "
        "Green \\= in stock, Red \\= out of stock\\."
    )
    markup = shop_categories_kb(cats)
    try:
        await message.edit_caption(caption=text, parse_mode="MarkdownV2", reply_markup=markup)
    except Exception:
        await message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=get_photo_object(WELCOME_BANNER_URL),
            caption=text,
            parse_mode="MarkdownV2",
            reply_markup=markup
        )


async def cb_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    cat_id = int(update.callback_query.data.split("_")[1])
    message = update.callback_query.message

    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM products WHERE category_id=? AND is_active=1 AND is_free=0 ORDER BY id",
            (cat_id,)
        )
        products = [dict(r) for r in await cur.fetchall()]
        cur2 = await db.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
        cat_row = await cur2.fetchone()

    cat_name = cat_row["name"] if cat_row else "Category"
    from config import WELCOME_BANNER_URL

    if not products:
        text = f"📦 *{escape_md(cat_name)}*\n\nNo products in this category yet\\."
        markup = back_home_kb()
        try:
            await message.edit_caption(caption=text, parse_mode="MarkdownV2", reply_markup=markup)
        except Exception:
            await message.delete()
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=get_photo_object(WELCOME_BANNER_URL),
                caption=text,
                parse_mode="MarkdownV2",
                reply_markup=markup
            )
        return

    text = f"📦 *{escape_md(cat_name)}*\n\nSelect a product to view details:"
    markup = products_list_kb(products, cat_id)
    try:
        await message.edit_caption(caption=text, parse_mode="MarkdownV2", reply_markup=markup)
    except Exception:
        await message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=get_photo_object(WELCOME_BANNER_URL),
            caption=text,
            parse_mode="MarkdownV2",
            reply_markup=markup
        )


async def cb_product_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[1])
    message = update.callback_query.message

    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    from config import WELCOME_BANNER_URL
    if not p:
        text = "❌ Product not found\\."
        markup = back_home_kb()
        try:
            await message.edit_caption(caption=text, parse_mode="MarkdownV2", reply_markup=markup)
        except Exception:
            await message.delete()
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=get_photo_object(WELCOME_BANNER_URL),
                caption=text,
                parse_mode="MarkdownV2",
                reply_markup=markup
            )
        return

    p = dict(p)
    out_of_stock = (p["stock"] == 0)

    text = product_detail_msg(p)
    if out_of_stock:
        text += "\n\n❌ *OUT OF STOCK*"

    from config import DEFAULT_PRODUCT_BANNER_URL
    img_url = p.get("image_url") or DEFAULT_PRODUCT_BANNER_URL
    markup = product_detail_kb(prod_id, p["is_free"]) if not out_of_stock else back_home_kb()

    # Change the media (image) to the product's image and edit caption/markup
    from telegram import InputMediaPhoto
    try:
        await message.edit_media(
            media=InputMediaPhoto(
                media=get_photo_object(img_url),
                caption=text,
                parse_mode="MarkdownV2"
            ),
            reply_markup=markup
        )
    except Exception:
        await message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=get_photo_object(img_url),
            caption=text,
            parse_mode="MarkdownV2",
            reply_markup=markup
        )


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
            await message.edit_caption(caption=text, parse_mode="MarkdownV2", reply_markup=markup)
        except Exception:
            await message.delete()
            await context.bot.send_photo(
                chat_id=update.effective_user.id,
                photo=get_photo_object(img_url),
                caption=text,
                parse_mode="MarkdownV2",
                reply_markup=markup
            )
        return

    price_str = escape_md(f"${p['price']:.2f}")
    bulk_info = ""
    if "Google AI Pro" in p["name"] or "Gemini" in p["name"]:
        bulk_info = (
            "\n\n📈 *Bulk Discounts:*\n"
            "• 10\\+ items: *\\$1\\.35* each\n"
            "• 20\\+ items: *\\$1\\.25* each\n"
            "• 50\\+ items: *\\$1\\.10* each\n"
        )

    text = (
        f"🛒 *Buy: {escape_md(p['name'])}*\n\n"
        f"💲 Base Price: {price_str} each"
        f"{bulk_info}\n"
        f"Select quantity:"
    )
    markup = quantity_kb(prod_id)
    try:
        await message.edit_caption(caption=text, parse_mode="MarkdownV2", reply_markup=markup)
    except Exception:
        await message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=get_photo_object(img_url),
            caption=text,
            parse_mode="MarkdownV2",
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
    unit_price = get_product_unit_price(p["name"], p["price"], qty)
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
        await message.edit_caption(caption=text, parse_mode="MarkdownV2", reply_markup=markup)
    except Exception:
        await message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=get_photo_object(img_url),
            caption=text,
            parse_mode="MarkdownV2",
            reply_markup=markup
        )


async def cb_custom_qty_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Prompt user to type a custom quantity."""
    await update.callback_query.answer()
    prod_id = int(update.callback_query.data.split("_")[2])
    context.user_data["awaiting_qty_for"] = prod_id
    await update.callback_query.edit_message_text(
        "✏️ *Enter Custom Quantity*\n\nType the number of items you want:",
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )
    return AWAIT_CUSTOM_QTY


async def recv_custom_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    prod_id = context.user_data.get("awaiting_qty_for")
    if not prod_id:
        return ConversationHandler.END

    if not text.isdigit() or int(text) < 1:
        await update.message.reply_text("⚠️ Please enter a valid positive number\\.", parse_mode="MarkdownV2")
        return AWAIT_CUSTOM_QTY

    qty = int(text)
    # Rebuild a fake callback to reuse _show_confirm
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur.fetchone()

    if not p:
        await update.message.reply_text("❌ Product not found\\.", parse_mode="MarkdownV2")
        return ConversationHandler.END

    p = dict(p)
    if p["stock"] != -1 and p["stock"] < qty:
        await update.message.reply_text(
            f"⚠️ Only *{p['stock']}* item\\(s\\) in stock\\!",
            parse_mode="MarkdownV2"
        )
        return AWAIT_CUSTOM_QTY

    user = await get_user(update.effective_user.id)
    unit_price = get_product_unit_price(p["name"], p["price"], qty)
    total = unit_price * qty
    context.user_data["pending"] = {"product_id": prod_id, "qty": qty, "coupon_discount": 0.0}
    text_msg = confirm_purchase_msg(p["name"], qty, unit_price, total, user["balance"])
    await update.message.reply_text(
        text_msg, parse_mode="MarkdownV2",
        reply_markup=confirm_purchase_kb(prod_id, qty)
    )
    return ConversationHandler.END


async def cb_coupon_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    parts = update.callback_query.data.split("_")
    prod_id, qty = int(parts[1]), int(parts[2])
    context.user_data["coupon_for"] = (prod_id, qty)
    await update.callback_query.edit_message_text(
        "🎟️ *Apply Coupon*\n\nEnter your coupon code:",
        parse_mode="MarkdownV2",
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
            await update.message.reply_text("❌ Invalid or expired coupon\\.", parse_mode="MarkdownV2")
            return AWAIT_COUPON_CODE

        # Check if user already used it
        cur2 = await db.execute(
            "SELECT id FROM coupon_uses WHERE coupon_id=? AND user_id=?",
            (coupon["id"], update.effective_user.id)
        )
        already_used = await cur2.fetchone()
        if already_used:
            await update.message.reply_text("⚠️ You have already used this coupon\\.", parse_mode="MarkdownV2")
            return ConversationHandler.END

        cur3 = await db.execute("SELECT * FROM products WHERE id=?", (prod_id,))
        p = await cur3.fetchone()

    if not p:
        return ConversationHandler.END

    p = dict(p)
    coupon = dict(coupon)
    unit_price = get_product_unit_price(p["name"], p["price"], qty)
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
    disc_str = escape_md(f"-${discount:.2f}")
    await update.message.reply_text(
        f"✅ *Coupon Applied\\!* Discount: {disc_str}\n\n" + text,
        parse_mode="MarkdownV2",
        reply_markup=confirm_purchase_kb(prod_id, qty),
    )
    return ConversationHandler.END


def register_shop_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_shop_home,     pattern="^shop_home$"))
    app.add_handler(CallbackQueryHandler(cb_category,      pattern=r"^cat_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_product_detail,pattern=r"^prod_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_buy_start,     pattern=r"^buy_start_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_quantity,      pattern=r"^qty_\d+_\d+$"))

    # Custom quantity conversation
    from telegram.ext import ConversationHandler
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_custom_qty_prompt, pattern=r"^qty_custom_\d+$")],
        states={AWAIT_CUSTOM_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_custom_qty)]},
        fallbacks=[],
        per_chat=True, per_user=True,
    ))

    # Coupon conversation
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_coupon_prompt, pattern=r"^coupon_\d+_\d+$")],
        states={AWAIT_COUPON_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_coupon_code)]},
        fallbacks=[],
        per_chat=True, per_user=True,
    ))
