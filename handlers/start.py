"""Start handler — /start command + main menu."""
import re
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from utils.helpers import get_or_create_user, get_user
from utils.keyboards import main_menu_kb, persistent_menu_kb
from utils.messages import welcome_msg, escape_md


GEMINI_LOGO_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8a/Google_Gemini_logo.svg/1024px-Google_Gemini_logo.svg.png"

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
            "⚡ *Welcome to GeminiStore\\!*",
            parse_mode="MarkdownV2",
            reply_markup=persistent_menu_kb()
        )
        # Send the main photo with inline menu
        await update.message.reply_photo(
            photo=GEMINI_LOGO_URL,
            caption=text,
            parse_mode="MarkdownV2",
            reply_markup=main_menu_kb()
        )
    else:
        # If started via callback, delete callback and send new message
        await update.callback_query.message.delete()
        await context.bot.send_photo(
            chat_id=update.effective_user.id,
            photo=GEMINI_LOGO_URL,
            caption=text,
            parse_mode="MarkdownV2",
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
    await message.delete()
    await context.bot.send_photo(
        chat_id=update.effective_user.id,
        photo=GEMINI_LOGO_URL,
        caption=text,
        parse_mode="MarkdownV2",
        reply_markup=main_menu_kb()
    )


async def text_browse_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.db import get_db
    from utils.keyboards import shop_categories_kb, back_home_kb
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM categories WHERE is_active=1 ORDER BY id"
        )
        cats = [dict(r) for r in await cur.fetchall()]
    
    cats = [c for c in cats if "Freeb" not in c["name"]]

    if not cats:
        await update.message.reply_text(
            "🛍️ No categories available yet\\. Check back soon\\!",
            parse_mode="MarkdownV2", reply_markup=back_home_kb()
        )
        return

    await update.message.reply_text(
        "🛍️ *Shop — Choose a Category*\n\n"
        "Browse our products below\\. "
        "Green \\= in stock, Red \\= out of stock\\.",
        parse_mode="MarkdownV2",
        reply_markup=shop_categories_kb(cats),
    )


async def text_my_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.keyboards import wallet_kb
    user = await get_user(update.effective_user.id)
    bal_str = escape_md(f"${user['balance']:.2f}")
    spent_str = escape_md(f"${user['total_spent']:.2f}")
    await update.message.reply_text(
        f"💵 *My Wallet*\n\n"
        f"💰 *Balance:* {bal_str}\n"
        f"📊 *Total Spent:* {spent_str}\n\n"
        f"Top up your wallet to pay instantly\\!",
        parse_mode="MarkdownV2",
        reply_markup=wallet_kb(),
    )


async def text_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.keyboards import profile_kb
    from config import get_membership, SILVER_THRESHOLD, GOLD_THRESHOLD, DIAMOND_THRESHOLD
    from utils.messages import sep

    user = await get_user(update.effective_user.id)
    membership = get_membership(user["total_spent"])

    if user["total_spent"] < SILVER_THRESHOLD:
        diff = SILVER_THRESHOLD - user['total_spent']
        next_tier = f"🥈 Silver \\(spend {escape_md(f'${diff:.2f}')} more\\)"
    elif user["total_spent"] < GOLD_THRESHOLD:
        diff = GOLD_THRESHOLD - user['total_spent']
        next_tier = f"🥇 Gold \\(spend {escape_md(f'${diff:.2f}')} more\\)"
    elif user["total_spent"] < DIAMOND_THRESHOLD:
        diff = DIAMOND_THRESHOLD - user['total_spent']
        next_tier = f"💎 Diamond \\(spend {escape_md(f'${diff:.2f}')} more\\)"
    else:
        next_tier = "🏆 You are at the highest tier\\!"

    username_str = f"@{escape_md(user['username'])}" if user["username"] else "N/A"
    bal_str = escape_md(f"${user['balance']:.2f}")
    spent_str = escape_md(f"${user['total_spent']:.2f}")

    await update.message.reply_text(
        f"😊 *My Profile*\n\n"
        f"👤 *Name:* {escape_md(user['first_name'])}\n"
        f"🔗 *Username:* {username_str}\n"
        f"🆔 *ID:* `{user['telegram_id']}`\n\n"
        f"{sep()}\n"
        f"💰 *Balance:* {bal_str}\n"
        f"📊 *Total Spent:* {spent_str}\n"
        f"🪪 *Membership:* {escape_md(membership)}\n"
        f"⬆️ *Next Tier:* {next_tier}\n"
        f"{sep()}",
        parse_mode="MarkdownV2",
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

    reward_str = escape_md(f"${REFERRAL_REWARD:.2f}")
    earned_str = escape_md(f"${earned:.2f}")
    link = f"https://t\\.me/{escape_md(BOT_USERNAME)}?start=ref\\_{user_id}"

    await update.message.reply_text(
        f"📣 *Refer \\& Earn*\n\n"
        f"Invite friends and earn {reward_str} for every friend "
        f"who makes their first purchase\\!\n\n"
        f"{sep()}\n"
        f"👥 *Total Referrals:* {total_refs}\n"
        f"✅ *Rewarded:* {rewarded}\n"
        f"💰 *Total Earned:* {earned_str}\n"
        f"{sep()}\n\n"
        f"🔗 *Your Referral Link:*\n`{link}`\n\n"
        f"Share it with friends\\!",
        parse_mode="MarkdownV2",
        reply_markup=referral_kb(BOT_USERNAME, user_id),
    )


async def text_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from utils.keyboards import back_home_kb
    await update.message.reply_text(
        "🆘 *Support*\n\nFor any issues, contact the admin\\.\n\nYou can reach us at: @lovable47\n\n⚡ *Instant Delivery*: All purchases are processed and delivered instantly after payment verification\\!",
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )


async def cb_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    from utils.keyboards import back_home_kb
    await update.callback_query.edit_message_text(
        "🆘 *Support*\n\nFor any issues, contact the admin\\.\n\nYou can reach us at: @lovable47\n\n⚡ *Instant Delivery*: All purchases are processed and delivered instantly after payment verification\\!",
        parse_mode="MarkdownV2",
        reply_markup=back_home_kb(),
    )


async def cb_email_trials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    from utils.keyboards import back_home_kb
    await update.callback_query.edit_message_text(
        "📧 *Email Trials*\n\nWant to try a product before buying\\?\n\nContact @lovable47 to request a free trial\\.",
        parse_mode="MarkdownV2",
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
    app.add_handler(MessageHandler(filters.Regex("^🆘 Support$"), text_support))
