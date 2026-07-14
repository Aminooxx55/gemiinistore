"""Start handler — /start command + main menu."""
import re
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from utils.helpers import get_or_create_user, get_user, get_photo_object
from utils.keyboards import main_menu_kb, persistent_menu_kb
from utils.messages import welcome_msg, format_profile_text
 
 
from config import WELCOME_BANNER_URL, SUPPORT_USERNAME
 
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    referrer_id = None
    if args:
        match = re.match(r"ref_(\d+)", args[0])
        if match:
            referrer_id = int(match.group(1))
            if referrer_id == update.effective_user.id:
                referrer_id = None  # can't refer yourself
 
    user = await get_or_create_user(
        telegram_id=update.effective_user.id,
        username=update.effective_user.username or "",
        first_name=update.effective_user.first_name or "User",
        referrer_id=referrer_id,
    )
 
    text = welcome_msg(
        first_name=user["first_name"],
        balance=user["balance"],
        total_spent=user["total_spent"],
    )
 
    if update.message:
        # Activate persistent bottom menu keyboard
        await update.message.reply_text(
            "⚡ <b>Welcome to GeminiStore!</b>",
            parse_mode="HTML",
            reply_markup=persistent_menu_kb()
        )
        # Send the main photo with inline menu
        await update.message.reply_photo(
            photo=get_photo_object(WELCOME_BANNER_URL),
            caption=text,
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
    else:
        # If started via callback, delete callback and send new message
        await update.callback_query.message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=get_photo_object(WELCOME_BANNER_URL),
            caption=text,
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
 
 
async def cb_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user = await get_user(update.effective_user.id)
    if not user:
        await cmd_start(update, context)
        return
 
    text = welcome_msg(
        first_name=user["first_name"],
        balance=user["balance"],
        total_spent=user["total_spent"],
    )
    message = update.callback_query.message
    
    from telegram import InputMediaPhoto
    try:
        await message.edit_media(
            media=InputMediaPhoto(
                media=get_photo_object(WELCOME_BANNER_URL),
                caption=text,
                parse_mode="HTML"
            ),
            reply_markup=main_menu_kb()
        )
    except Exception:
        await message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=get_photo_object(WELCOME_BANNER_URL),
            caption=text,
            parse_mode="HTML",
            reply_markup=main_menu_kb()
        )
 
 
async def text_browse_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db import get_db
    from utils.keyboards import products_list_kb, back_home_kb
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM products WHERE is_active=1 ORDER BY id"
        )
        products = [dict(r) for r in await cur.fetchall()]
    
    if not products:
        await update.message.reply_text(
            "🛍️ No products available yet. Check back soon!",
            parse_mode="HTML", reply_markup=back_home_kb()
        )
        return
 
    if len(products) == 1:
        # If there's only 1 product, jump straight to its detail
        from handlers.shop import _show_product_detail
        await _show_product_detail(update.message, update.effective_user.id, context, products[0]["id"])
        return

    await update.message.reply_text(
        "🛍️ <b>Shop — All Products</b>\n\n"
        "Browse our products below. "
        "Green = in stock, Red = out of stock.",
        parse_mode="HTML",
        reply_markup=products_list_kb(products, 0),
    )
 
 
async def text_my_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.keyboards import wallet_kb
    user = await get_user(update.effective_user.id)
    bal_str = f"${user['balance']:.2f}"
    spent_str = f"${user['total_spent']:.2f}"
    await update.message.reply_text(
        f"💵 <b>My Wallet</b>\n\n"
        f"💰 <b>Balance:</b> {bal_str}\n"
        f"📊 <b>Total Spent:</b> {spent_str}\n\n"
        f"Top up your wallet to pay instantly!",
        parse_mode="HTML",
        reply_markup=wallet_kb(),
    )
 
 
async def text_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.keyboards import profile_kb
 
    user = await get_user(update.effective_user.id)
    text = format_profile_text(user)
 
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=profile_kb(),
    )
 
 
async def text_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db import get_db
    from config import BOT_USERNAME, REFERRAL_REWARD
    from utils.keyboards import referral_kb
    from utils.messages import sep
 
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
 
    await update.message.reply_text(
        f"📣 <b>Refer & Earn</b>\n\n"
        f"Invite friends and earn {reward_str} for every friend "
        f"who makes their first purchase!\n\n"
        f"{sep()}\n"
        f"👥 <b>Total Referrals:</b> {total_refs}\n"
        f"✅ <b>Rewarded:</b> {rewarded}\n"
        f"💰 <b>Total Earned:</b> {earned_str}\n"
        f"{sep()}\n\n"
        f"🔗 <b>Your Referral Link:</b>\n<code>{link}</code>\n\n"
        f"Share it with friends!",
        parse_mode="HTML",
        reply_markup=referral_kb(BOT_USERNAME, user_id),
    )
 
 
async def text_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.keyboards import back_home_kb
    await update.message.reply_text(
        f"🆘 <b>Support</b>\n\nFor any issues, contact the admin.\n\nYou can reach us at: {SUPPORT_USERNAME}\n\n⚡ <b>Instant Delivery</b>: All purchases are processed and delivered instantly after payment verification!",
        parse_mode="HTML",
        reply_markup=back_home_kb(),
    )
 
 
async def cb_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    from utils.keyboards import back_home_kb
    await update.callback_query.edit_message_text(
        f"🆘 <b>Support</b>\n\nFor any issues, contact the admin.\n\nYou can reach us at: {SUPPORT_USERNAME}\n\n⚡ <b>Instant Delivery</b>: All purchases are processed and delivered instantly after payment verification!",
        parse_mode="HTML",
        reply_markup=back_home_kb(),
    )
 
 
async def cb_email_trials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    from utils.keyboards import back_home_kb
    await update.callback_query.edit_message_text(
        f"📧 <b>Email Trials</b>\n\nWant to try a product before buying?\n\nContact {SUPPORT_USERNAME} to request a free trial.",
        parse_mode="HTML",
        reply_markup=back_home_kb(),
    )


async def cb_clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Chat cleared! Send /start to begin again.")
    await update.callback_query.delete_message()


def register_start_handlers(app):
    from telegram.ext import MessageHandler, filters
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(cb_main_menu,    pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(cb_support,      pattern="^support$"))
    app.add_handler(CallbackQueryHandler(cb_email_trials, pattern="^email_trials$"))
    app.add_handler(CallbackQueryHandler(cb_clear_chat,   pattern="^clear_chat$"))
    
    # Persistent keyboard button text message handlers
    app.add_handler(MessageHandler(filters.Regex("^🛍️ Browse Shop$"), text_browse_shop))
    app.add_handler(MessageHandler(filters.Regex("^💵 My Wallet$"), text_my_wallet))
    app.add_handler(MessageHandler(filters.Regex("^😊 My Profile$"), text_my_profile))
    app.add_handler(MessageHandler(filters.Regex("^📣 Refer & Earn$"), text_referral))
    app.add_handler(MessageHandler(filters.Regex("^💬 Support Chat$"), text_support))
