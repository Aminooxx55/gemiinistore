import asyncio
import os
import sqlite3
import sys
from dotenv import load_dotenv
from telegram import Bot

# Load env configuration
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def main():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN is not set in .env!")
        return

    # Define the message to send (supports HTML formatting)
    message = (
        "🎁 <b>GIVEAWAY ALERT!</b> 🎁\n\n"
        "First person to put their X (Twitter) username in our main channel gets <b>12 months of X Premium for FREE!</b> ⚡\n\n"
        "👉 Go to our main channel now: @grokkkmet\n\n"
        "Good luck! 🍀"
    )


    bot = Bot(token=BOT_TOKEN)
    
    # Fetch all active (non-banned) users from the database
    conn = sqlite3.connect("shop.db")
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id FROM users WHERE is_banned=0")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()

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
            # Format error safely without emojis
            print(f"Failed: {uid} - Error: {str(e)}", file=sys.stderr, flush=True)
            failed += 1

    print(f"\nBroadcast complete! Sent: {sent}, Failed: {failed}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
