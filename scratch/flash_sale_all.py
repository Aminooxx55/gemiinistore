# -*- coding: utf-8 -*-
import asyncio
import os
import sqlite3
import sys
import json
from dotenv import load_dotenv
from telegram import Bot

# Load env configuration
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Setup safe console encoding for stdout/stderr
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
sys.stderr.reconfigure(encoding='utf-8') if hasattr(sys.stderr, 'reconfigure') else None

async def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is not set in .env!", flush=True)
        return

    db_path = "shop.db"
    backup_path = "scratch/original_prices.json"

    # 1. Fetch current products & backup their original prices
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price FROM products")
    products = [dict(row) for row in cursor.fetchall()]
    
    if not products:
        print("Error: No products found in the database to discount!", flush=True)
        conn.close()
        return

    # Save original prices to JSON backup
    original_prices = {p["id"]: p["price"] for p in products}
    os.makedirs("scratch", exist_ok=True)
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(original_prices, f, indent=4)
        
    print(f"Backed up original prices for {len(products)} products to {backup_path}", flush=True)

    # 2. Apply 40% discount (prices = original * 0.6)
    for p in products:
        discounted_price = round(p["price"] * 0.6, 2)
        # Avoid letting prices go to 0 or negative
        discounted_price = max(0.01, discounted_price)
        cursor.execute("UPDATE products SET price = ? WHERE id = ?", (discounted_price, p["id"]))
        print(f"Discounted: {p['name']} | Original: ${p['price']:.2f} -> Discounted: ${discounted_price:.2f}", flush=True)
        
    conn.commit()
    conn.close()
    print("Database updated: 40% discount applied to all products.", flush=True)

    # 3. Broadcast dual-language message
    message = (
        "⚡️ <b>FLASH SALE - 40% OFF EVERYTHING!</b> ⚡️\n"
        "⚡️ <b>تخفيضات فلاش - خصم 40% على كل شيء!</b> ⚡️\n\n"
        "🇬🇧 <b>English:</b>\n"
        "For the next <b>2 HOURS</b> only, all prices in our store have been slashed by <b>40%</b>!\n"
        "No coupon needed — the discounts are already applied to all products in the shop! 🛍️\n\n"
        "⏰ Hurry, this special offer expires in exactly 2 hours!\n"
        "👉 Shop now: @GrokSrorebot\n\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        "🇸🇦 <b>العربية:</b>\n"
        "خلال <b>الساعتين</b> القادمتين فقط، تم تخفيض جميع الأسعار في متجرنا بنسبة <b>40%</b>!\n"
        "لا داعي لاستخدام أي كوبون — الخصومات مطبقة بالفعل على جميع المنتجات في المتجر! 🛍️\n\n"
        "⏰ سارع الآن، هذا العرض الخاص ينتهي خلال ساعتين بالضبط!\n"
        "👉 تسوق الآن: @GrokSrorebot"
    )

    bot = Bot(token=BOT_TOKEN)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users WHERE is_banned=0")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"Starting broadcast to {len(users)} users...", flush=True)
    sent, failed = 0, 0
    for uid in users:
        try:
            await bot.send_message(chat_id=uid, text=message, parse_mode="HTML")
            print(f"Sent: {uid}", flush=True)
            sent += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"Failed: {uid} - Error: {str(e)}", file=sys.stderr, flush=True)
            failed += 1

    print(f"Broadcast complete! Sent: {sent}, Failed: {failed}", flush=True)
    
    # 4. Wait for 2 hours (7200 seconds)
    duration = 7200
    print(f"Sleeping for {duration} seconds (2 hours) before restoring original prices...", flush=True)
    await asyncio.sleep(duration)

    # 5. Restore original prices
    print("Timer expired! Restoring original prices...", flush=True)
    if os.path.exists(backup_path):
        with open(backup_path, "r", encoding="utf-8") as f:
            original_prices = json.load(f)
            
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for pid_str, orig_price in original_prices.items():
            pid = int(pid_str)
            cursor.execute("UPDATE products SET price = ? WHERE id = ?", (orig_price, pid))
            print(f"Restored product ID {pid} price back to ${orig_price:.2f}", flush=True)
        conn.commit()
        conn.close()
        print("Prices restored successfully!", flush=True)
        
        # Delete backup file
        try:
            os.remove(backup_path)
        except Exception:
            pass
    else:
        print("Error: Backup file original_prices.json not found! Cannot restore automatically.", file=sys.stderr, flush=True)

if __name__ == "__main__":
    asyncio.run(main())
