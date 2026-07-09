import asyncio
import os
import sqlite3
import sys
import time
from dotenv import load_dotenv
from telegram import Bot

# Load env configuration
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is not set in .env!")
        return

    product_id = 1  # Grok X Premium+ Method
    sale_price = 2.40
    original_price = 9.99
    sale_duration = 3600  # 1 hour in seconds


    # Define the message to send (supports HTML formatting)
    message = (
        "⚡ <b>FLASH SALE — 1 HOUR ONLY!</b> ⚡\n\n"
        "Get the <b>Grok X Premium+ Method (6M & 12M)</b> for only <b>$2.40</b> (Regular: $4.99)!\n\n"
        "⏰ <b>This offer is valid for exactly 1 HOUR!</b> The price will automatically return to normal when the timer ends.\n\n"
        "🛍️ Open the bot at @GrokSrorebot and buy now!"
    )

    # 1. Update the price in the database to the sale price
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET price = ? WHERE id = ?", (sale_price, product_id))
    conn.commit()
    print(f"Database: Product ID {product_id} price updated to ${sale_price:.2f}", flush=True)

    # 2. Fetch all active (non-banned) users
    cursor.execute("SELECT telegram_id FROM users WHERE is_banned=0")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()

    # 3. Broadcast the special offer message
    bot = Bot(token=BOT_TOKEN)
    print(f"Broadcast: Starting broadcast to {len(users)} users...", flush=True)
    sent = 0
    failed = 0
    for uid in users:
        try:
            await bot.send_message(chat_id=uid, text=message, parse_mode="HTML")
            print(f"Sent: {uid}", flush=True)
            sent += 1
            await asyncio.sleep(0.05)  # Pause slightly to respect Telegram rate limits
        except Exception as e:
            print(f"Failed: {uid} - Error: {str(e)}", file=sys.stderr, flush=True)
            failed += 1

    print(f"Broadcast complete! Sent: {sent}, Failed: {failed}", flush=True)
    print(f"Sleeping for {sale_duration} seconds (1 hour)...", flush=True)

    # 4. Wait for 1 hour
    await asyncio.sleep(sale_duration)

    # 5. Revert the price back to original
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET price = ? WHERE id = ?", (original_price, product_id))
    conn.commit()
    conn.close()
    print(f"Database: Flash sale ended. Product ID {product_id} price reverted to ${original_price:.2f}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
