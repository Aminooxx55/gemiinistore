"""Utility / helper functions."""
import io
import logging
import qrcode
from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_db
from config import get_membership, ADMIN_ID

logger = logging.getLogger(__name__)


def get_photo_object(path_or_url: str):
    """Return open file object if local path exists, otherwise return the string itself."""
    import os
    if not path_or_url:
        return None
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    
    if not os.path.isabs(path_or_url):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(base_dir, path_or_url)
    else:
        full_path = path_or_url
        
    if os.path.exists(full_path):
        with open(full_path, "rb") as f:
            buf = io.BytesIO(f.read())
            buf.name = os.path.basename(full_path)
            return buf
        
    # Fallback to placeholder if local file does not exist
    return "https://placehold.co/800x400/png?text=Welcome"


def get_product_unit_price(product_name: str, base_price: float, qty: int) -> float:
    """Calculate the unit price based on product name and quantity (bulk pricing)."""
    pn_lower = product_name.lower()
    if "google ai pro" in pn_lower or "gemini" in pn_lower:
        if qty >= 50:
            return 0.80
        elif qty >= 30:
            return 0.80
        elif qty >= 10:
            return 0.80
        else:
            return 0.80
    return base_price


async def get_or_create_user(telegram_id: int, username: str, first_name: str, referrer_id: int = None):
    """Fetch user from DB or create if not exists. Returns the user row."""
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        user = await cur.fetchone()
        if user is None:
            await db.execute(
                "INSERT INTO users (telegram_id, username, first_name, referrer_id) VALUES (?,?,?,?)",
                (telegram_id, username, first_name, referrer_id)
            )
            await db.commit()
            # Create referral record
            if referrer_id:
                cur2 = await db.execute("SELECT id FROM users WHERE telegram_id=?", (referrer_id,))
                ref_exists = await cur2.fetchone()
                if ref_exists:
                    await db.execute(
                        "INSERT INTO referrals (referrer_id, referred_id) VALUES (?,?)",
                        (referrer_id, telegram_id)
                    )
                    await db.commit()
            cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
            user = await cur.fetchone()
        return user


async def get_user(telegram_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
        return await cur.fetchone()


async def update_user_balance(telegram_id: int, delta: float):
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id=?",
            (delta, telegram_id)
        )
        await db.commit()


async def update_membership(telegram_id: int):
    async with get_db() as db:
        cur = await db.execute("SELECT total_spent FROM users WHERE telegram_id=?", (telegram_id,))
        row = await cur.fetchone()
        if row:
            membership = get_membership(row["total_spent"])
            await db.execute(
                "UPDATE users SET membership=? WHERE telegram_id=?",
                (membership, telegram_id)
            )
            await db.commit()


async def record_transaction(user_id: int, amount: float, tx_type: str, description: str, order_id: int = None):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type, description, order_id) VALUES (?,?,?,?,?)",
            (user_id, amount, tx_type, description, order_id)
        )
        await db.commit()


async def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


def make_qr_bytes(data: str) -> bytes:
    """Generate a QR code PNG and return as bytes."""
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


async def notify_admin(context: ContextTypes.DEFAULT_TYPE, text: str):
    """Send a message to the admin."""
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode="HTML")
    except Exception:
        logger.exception('Failed to notify admin with message')
        pass


def chunk_list(lst: list, n: int) -> list:
    """Split list into chunks of size n."""
    return [lst[i:i + n] for i in range(0, len(lst), n)]


async def translate_callback_data(callback_data: str) -> str:
    """Translate raw callback query string into a beautiful human-readable description."""
    if not callback_data:
        return "Unknown Button Click"

    static_map = {
        "main_menu": "Returned to Main Menu",
        "shop_home": "Opened Shop Catalog",
        "wallet_home": "Opened Wallet Dashboard",
        "orders_home": "Opened My Orders History",
        "profile_home": "Opened My Profile",
        "referral_home": "Opened Refer & Earn Portal",
        "support": "Opened Support & Help Menu",
        "email_trials": "Opened Email Trials Info",
        "clear_chat": "Clicked Clear Chat & Reset Screen",
        "tx_history": "Viewed Wallet Transaction Logs",
        "topup_home": "Opened Wallet Top-Up Page"
    }

    if callback_data in static_map:
        return static_map[callback_data]

    try:
        async with get_db() as db:
            if callback_data.startswith("cat_"):
                cat_id = int(callback_data.split("_")[1])
                cur = await db.execute("SELECT name FROM categories WHERE id = ?", (cat_id,))
                row = await cur.fetchone()
                name = row["name"] if row else f"ID {cat_id}"
                return f"Viewed Category: {name}"

            if callback_data.startswith("prod_"):
                prod_id = int(callback_data.split("_")[1])
                cur = await db.execute("SELECT name FROM products WHERE id = ?", (prod_id,))
                row = await cur.fetchone()
                name = row["name"] if row else f"ID {prod_id}"
                return f"Viewed Product: {name}"

            if callback_data.startswith("buy_start_"):
                prod_id = int(callback_data.split("_")[2])
                cur = await db.execute("SELECT name FROM products WHERE id = ?", (prod_id,))
                row = await cur.fetchone()
                name = row["name"] if row else f"ID {prod_id}"
                return f"Clicked 'Buy Now' for {name}"

            if callback_data.startswith("qty_custom_"):
                prod_id = int(callback_data.split("_")[2])
                cur = await db.execute("SELECT name FROM products WHERE id = ?", (prod_id,))
                row = await cur.fetchone()
                name = row["name"] if row else f"ID {prod_id}"
                return f"Requested Custom Quantity for {name}"

            if callback_data.startswith("qty_") and not callback_data.startswith("qty_custom_"):
                parts = callback_data.split("_")
                prod_id = int(parts[1])
                qty = int(parts[2])
                cur = await db.execute("SELECT name FROM products WHERE id = ?", (prod_id,))
                row = await cur.fetchone()
                name = row["name"] if row else f"ID {prod_id}"
                return f"Selected Quantity: {qty}x for {name}"

            if callback_data.startswith("pay_wallet_"):
                parts = callback_data.split("_")
                prod_id = int(parts[2])
                qty = int(parts[3])
                cur = await db.execute("SELECT name FROM products WHERE id = ?", (prod_id,))
                row = await cur.fetchone()
                name = row["name"] if row else f"ID {prod_id}"
                return f"Paid via Wallet Balance for {qty}x {name}"

            if callback_data.startswith("pay_binance_"):
                parts = callback_data.split("_")
                prod_id = int(parts[2])
                qty = int(parts[3])
                cur = await db.execute("SELECT name FROM products WHERE id = ?", (prod_id,))
                row = await cur.fetchone()
                name = row["name"] if row else f"ID {prod_id}"
                return f"Initiated Binance Pay for {qty}x {name}"

            if callback_data.startswith("pay_bep20_"):
                parts = callback_data.split("_")
                prod_id = int(parts[2])
                qty = int(parts[3])
                cur = await db.execute("SELECT name FROM products WHERE id = ?", (prod_id,))
                row = await cur.fetchone()
                name = row["name"] if row else f"ID {prod_id}"
                return f"Initiated USDT BEP20 manual pay for {qty}x {name}"

            if callback_data.startswith("payment_sent_"):
                order_id = int(callback_data.split("_")[2])
                return f"Clicked 'I've Sent Payment' for Order #{order_id}"

            if callback_data.startswith("topup_") and not callback_data.startswith("topup_sent_"):
                parts = callback_data.split("_")
                method = parts[1].upper()
                amount = float(parts[2])
                return f"Selected top-up method: {method} for ${amount:.2f}"

            if callback_data.startswith("topup_sent_"):
                req_id = int(callback_data.split("_")[2])
                return f"Clicked 'I've Sent Payment' for Top-Up Request #{req_id}"

            if callback_data.startswith("order_detail_"):
                order_id = int(callback_data.split("_")[2])
                return f"Viewed details of Order #{order_id}"

            if callback_data.startswith("show_rate_"):
                order_id = int(callback_data.split("_")[2])
                return f"Opened Star Rating prompt for Order #{order_id}"

            if callback_data.startswith("rate_"):
                parts = callback_data.split("_")
                rating = int(parts[1])
                order_id = int(parts[2])
                return f"Submitted rating of {rating} Stars for Order #{order_id}"

            if callback_data.startswith("skip_comment_"):
                order_id = int(callback_data.split("_")[2])
                return f"Skipped rating feedback comment for Order #{order_id}"

    except Exception:
        logger.exception('Failed to translate callback data: %s', callback_data)
        pass

    return f"Clicked button: {callback_data}"


MEMBERSHIP_CACHE = {}  # user_id -> (is_member, expiry_timestamp)


async def is_user_member_of_channel(bot, user_id: int, force_check: bool = False) -> bool:
    """Check if the user is a member of the required channel, using a cache to prevent slow API requests."""
    from config import REQUIRED_CHANNEL, STRICT_CHANNEL_CHECK, ADMIN_ID
    import time
    if not REQUIRED_CHANNEL:
        return True

    now = time.time()
    if not force_check and user_id in MEMBERSHIP_CACHE:
        val, expiry = MEMBERSHIP_CACHE[user_id]
        if now < expiry:
            return val

    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        is_member = member.status in ["member", "administrator", "creator"]
        
        # Cache results for 5 minutes (300 seconds)
        MEMBERSHIP_CACHE[user_id] = (is_member, now + 300)
        return is_member
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to check channel membership for {user_id} on {REQUIRED_CHANNEL}: {e}")
        
        # If check fails (e.g. bot not administrator), notify the admin so they can fix it
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    f"⚠️ <b>Channel Membership Check Error!</b>\n\n"
                    f"The bot failed to verify membership for user <code>{user_id}</code> in channel <code>{REQUIRED_CHANNEL}</code>.\n"
                    f"<b>Error:</b> <code>{str(e)}</code>\n\n"
                    f"💡 <b>Action Required:</b> Ensure the bot is added to the channel <code>{REQUIRED_CHANNEL}</code> as an <b>Administrator</b> with rights to check chat members."
                ),
                parse_mode="HTML"
            )
        except Exception as admin_err:
            logger.error(f"Failed to notify admin of membership check error: {admin_err}")
            
        return not STRICT_CHANNEL_CHECK


async def process_order_delivery(db, bot, order_id: int):
    """Check if the product has digital stock, fulfill it automatically if available, and process loyalty cashback."""
    import logging
    logger = logging.getLogger(__name__)

    # Start atomic transaction to prevent double delivery race conditions
    try:
        await db.execute("BEGIN IMMEDIATE")
    except Exception:
        pass # Might already be in a transaction

    try:
        # 1. Fetch order details
        cur = await db.execute(
            """SELECT o.*, p.name as product_name, p.price as product_price, u.first_name
               FROM orders o
               JOIN products p ON o.product_id = p.id
               JOIN users u ON o.user_id = u.telegram_id
               WHERE o.id = ?""",
            (order_id,)
        )
        order = await cur.fetchone()
        if not order:
            await db.commit()
            return

        order = dict(order)
        user_id = order["user_id"]
        product_id = order["product_id"]
        qty = order["quantity"]
        total_price = order["total_price"]

        # 2. Check for available stock
        cur_stock = await db.execute(
            "SELECT id, data FROM product_stock WHERE product_id = ? AND is_sold = 0 ORDER BY id ASC LIMIT ?",
            (product_id, qty)
        )
        stock_items = [dict(r) for r in await cur_stock.fetchall()]

        delivery_successful = False
        delivery_info = None
        formatted_delivery_text = ""

        if len(stock_items) >= qty:
            stock_ids = [item["id"] for item in stock_items]
            delivery_info = "\n".join([item["data"] for item in stock_items])
            
            # Format the delivery output nicely as per user request
            formatted_items = []
            for idx, item in enumerate(stock_items, 1):
                formatted_items.append(f"{idx}.\n<code>{item['data']}</code>\n")
            
            formatted_delivery_text = "".join(formatted_items)
            
            placeholders = ",".join(["?"] * len(stock_ids))
            await db.execute(
                f"UPDATE product_stock SET is_sold = 1, sold_at = datetime('now'), order_id = ? WHERE id IN ({placeholders})",
                (order_id, *stock_ids)
            )
            
            await db.execute(
                "UPDATE orders SET status = 'delivered', delivery_info = ?, updated_at = datetime('now') WHERE id = ?",
                (delivery_info, order_id)
            )
            
            cur_count = await db.execute("SELECT COUNT(*) FROM product_stock WHERE product_id = ? AND is_sold = 0", (product_id,))
            unsold_count = (await cur_count.fetchone())[0]
            
            cur_prod = await db.execute("SELECT stock FROM products WHERE id = ?", (product_id,))
            p_stock = (await cur_prod.fetchone())[0]
            if p_stock != -1:
                await db.execute("UPDATE products SET stock = ? WHERE id = ?", (unsold_count, product_id))
                
            delivery_successful = True
            
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.error(f"Error processing delivery for order {order_id}: {e}")
        return

    # 3. Process Loyalty Cashback
    from config import CASHBACK_PERCENT
    cashback_amount = round(total_price * CASHBACK_PERCENT, 2)
    if cashback_amount > 0:
        await db.execute(
            "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
            (cashback_amount, user_id)
        )
        await db.execute(
            "INSERT INTO transactions (user_id, amount, type, description, order_id) VALUES (?, ?, 'topup', ?, ?)",
            (user_id, cashback_amount, f"Loyalty Cashback ({int(CASHBACK_PERCENT*100)}%) for Order #{order_id}", order_id)
        )
        await db.commit()
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"🎁 <b>Loyalty Cashback Awarded!</b>\n\nYou earned ${cashback_amount:.2f} cashback for Order #{order_id}. It has been added to your wallet! 💰",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to notify user of cashback: {e}")

    # 4. Notify user about digital delivery if successful
    if delivery_successful:
        from handlers.orders import rating_kb
        from html import escape as html_escape
        try:
            msg = (
                f"🎉 <b>Your order has been delivered successfully.</b>\n\n"
                f"<b>{html_escape(order['product_name'])}</b>\n\n"
                f"{formatted_delivery_text}"
                f"<b>Total:</b>\n"
                f"{qty} link{'s' if qty > 1 else ''}\n\n"
                f"⭐ <b>Please rate your experience:</b>"
            )
            
            # Send message. If it's too long, Telegram might reject it.
            # Usually limit is 4096 chars. If large orders, we might need chunking.
            # Assuming typical lengths, a few hundred links could exceed.
            # But the requirement is "support thousands of links", let's handle long msgs by chunking.
            
            if qty >= 15:
                import io
                file_content = "\n".join([item["data"] for item in stock_items])
                doc = io.BytesIO(file_content.encode("utf-8"))
                doc.name = f"Order_{order_id}.txt"
                
                intro_msg = (
                    f"🎉 <b>Your order has been delivered successfully.</b>\n\n"
                    f"<b>{html_escape(order['product_name'])}</b>\n\n"
                    f"<b>Total:</b>\n{qty} links\n\n"
                    f"⭐ <b>Please rate your experience:</b>"
                )
                await bot.send_document(
                    chat_id=user_id,
                    document=doc,
                    caption=intro_msg,
                    parse_mode="HTML",
                    reply_markup=rating_kb(order_id)
                )
            elif len(msg) <= 4000:
                await bot.send_message(
                    chat_id=user_id,
                    text=msg,
                    parse_mode="HTML",
                    reply_markup=rating_kb(order_id)
                )
            else:
                # Chunking strategy
                intro_msg = f"🎉 <b>Your order has been delivered successfully.</b>\n\n<b>{html_escape(order['product_name'])}</b>\n"
                await bot.send_message(chat_id=user_id, text=intro_msg, parse_mode="HTML")
                
                chunk = ""
                for idx, item in enumerate(stock_items, 1):
                    line = f"{idx}.\n<code>{item['data']}</code>\n\n"
                    if len(chunk) + len(line) > 4000:
                        await bot.send_message(chat_id=user_id, text=chunk, parse_mode="HTML")
                        chunk = line
                    else:
                        chunk += line
                if chunk:
                    await bot.send_message(chat_id=user_id, text=chunk, parse_mode="HTML")
                    
                summary_msg = f"<b>Total:</b>\n{qty} link{'s' if qty > 1 else ''}\n\n⭐ <b>Please rate your experience:</b>"
                await bot.send_message(
                    chat_id=user_id,
                    text=summary_msg,
                    parse_mode="HTML",
                    reply_markup=rating_kb(order_id)
                )
                
        except Exception as e:
            logger.error(f"Failed to send instant delivery message: {e}")


