# -*- coding: utf-8 -*-
"""Lucky Spin & Win daily draw handler."""
import random
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database.db import get_db
from config import SPIN_COOLDOWN
from utils.helpers import update_user_balance, record_transaction
from utils.keyboards import back_home_kb


async def cmd_spin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /spin command or persistent menu click."""
    user_id = update.effective_user.id
    
    # Check if cooldowned
    cooldown_time = await check_spin_cooldown(user_id)
    if cooldown_time > 0:
        hours = int(cooldown_time // 3600)
        minutes = int((cooldown_time % 3600) // 60)
        cooldown_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
        
        msg_text = (
            "⏳ <b>Spin Cooldown!</b>\n\n"
            "You have already spun the wheel today.\n"
            f"Please wait <b>{cooldown_str}</b> before spinning again! 🎡"
        )
        if update.message:
            await update.message.reply_text(msg_text, parse_mode="HTML", reply_markup=back_home_kb())
        else:
            await update.callback_query.answer()
            await update.callback_query.message.delete()
            await context.bot.send_message(
                chat_id=update.effective_user.id,
                text=msg_text,
                parse_mode="HTML",
                reply_markup=back_home_kb()
            )
        return

    # Render Spin Start Screen
    text = (
        "🎡 <b>Lucky Spin & Win!</b> 🎡\n\n"
        "Spin the wheel once every 24 hours to win amazing prizes:\n"
        "💰 <b>$0.50 Wallet Credit</b> (10% chance)\n"
        "💵 <b>$0.25 Wallet Credit</b> (20% chance)\n"
        "🎟️ <b>15% Store Discount Coupon</b> (30% chance)\n"
        "🍀 <b>Try again tomorrow</b> (40% chance)\n\n"
        "Are you ready to test your luck?"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎡 Spin Now!", callback_data="spin_start")],
        [InlineKeyboardButton("🏠 Back to Home", callback_data="main_menu")]
    ])
    
    if update.message:
        await update.message.reply_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await update.callback_query.answer()
        await update.callback_query.message.delete()
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=text,
            parse_mode="HTML",
            reply_markup=kb
        )


async def check_spin_cooldown(user_id: int) -> float:
    """Return seconds remaining if cooldowned, 0 otherwise."""
    async with get_db() as db:
        cur = await db.execute("SELECT last_spin_at FROM user_spins WHERE telegram_id=?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return 0
        
        last_spin = datetime.fromisoformat(row["last_spin_at"])
        elapsed = (datetime.now() - last_spin).total_seconds()
        if elapsed < SPIN_COOLDOWN:
            return SPIN_COOLDOWN - elapsed
        return 0


async def cb_spin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Re-check cooldown to prevent cheat
    cooldown_time = await check_spin_cooldown(user_id)
    if cooldown_time > 0:
        await update.callback_query.answer("⏳ Cooldown is active!", show_alert=True)
        return
        
    await update.callback_query.answer()
    
    # Save spin time to DB immediately
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO user_spins (telegram_id, last_spin_at) VALUES (?, ?)",
            (user_id, datetime.now().isoformat())
        )
        await db.commit()
        
    # Animation Frames
    frames = [
        "🔄 <b>[ 🎡 SPINNING... 🎡 ]</b>\n\n🔴 🟢 🔵 🟡",
        "🔄 <b>[ 🎡 SPINNING... 🎡 ]</b>\n\n🟢 🔵 🟡 🔴",
        "🔄 <b>[ 🎡 SPINNING... 🎡 ]</b>\n\n🔵 🟡 🔴 🟢",
        "🔄 <b>[ 🎡 SPINNING... 🎡 ]</b>\n\n🟡 🔴 🟢 🔵"
    ]
    
    for frame in frames:
        try:
            await update.callback_query.edit_message_text(text=frame, parse_mode="HTML")
            await asyncio.sleep(0.4)
        except Exception:
            pass
        
    # Pick a prize
    roll = random.randint(1, 100)
    
    if roll <= 10:
        # $0.50 Win
        amount = 0.50
        await update_user_balance(user_id, amount)
        await record_transaction(user_id, amount, "topup", "Lucky Spin Reward")
        
        result_text = (
            "🎉 <b>CONGRATULATIONS!</b> 🎉\n\n"
            "🎡 The wheel stopped on:\n"
            "💰 <b>$0.50 Wallet Credit!</b>\n\n"
            "The credits have been added directly to your wallet. Spend them anytime!"
        )
    elif roll <= 30:
        # $0.25 Win
        amount = 0.25
        await update_user_balance(user_id, amount)
        await record_transaction(user_id, amount, "topup", "Lucky Spin Reward")
        
        result_text = (
            "🎉 <b>CONGRATULATIONS!</b> 🎉\n\n"
            "🎡 The wheel stopped on:\n"
            "💵 <b>$0.25 Wallet Credit!</b>\n\n"
            "The credits have been added directly to your wallet. Spend them anytime!"
        )
    elif roll <= 60:
        # 15% discount coupon Win
        coupon_code = f"SPIN15_{random.randint(1000, 9999)}"
        async with get_db() as db:
            await db.execute(
                "INSERT INTO coupons (code, discount_percent, flat_discount, max_uses, uses_count, is_active) VALUES (?, 15.0, 0.0, 1, 0, 1)",
                (coupon_code,)
            )
            await db.commit()
            
        result_text = (
            "🎉 <b>CONGRATULATIONS!</b> 🎉\n\n"
            "🎡 The wheel stopped on:\n"
            "🎟️ <b>15% Store Discount Coupon!</b>\n\n"
            f"Your coupon code is: <code>{coupon_code}</code>\n"
            "This coupon is valid for 1 use. Enter it during checkout to save 15%!"
        )
    else:
        # No prize
        result_text = (
            "😢 <b>No luck today!</b>\n\n"
            "🎡 The wheel stopped on:\n"
            "❌ <b>Try again tomorrow!</b>\n\n"
            "Don't worry, you can spin the wheel again in 24 hours. Better luck next time! 🍀"
        )
        
    try:
        await update.callback_query.edit_message_text(text=result_text, parse_mode="HTML", reply_markup=back_home_kb())
    except Exception:
        pass


async def text_spin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback text menu message handler."""
    await cmd_spin(update, context)


def register_spin_handlers(app):
    app.add_handler(CommandHandler("spin", cmd_spin))
    app.add_handler(CallbackQueryHandler(cmd_spin, pattern="^spin_home$"))
    app.add_handler(CallbackQueryHandler(cb_spin_start, pattern="^spin_start$"))
    app.add_handler(MessageHandler(filters.Regex("^🎡 Spin & Win$"), text_spin_menu))
