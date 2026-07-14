# -*- coding: utf-8 -*-
"""Background scheduler to automatically check Cryptomus payments."""
import logging
from telegram.ext import ContextTypes
from database.db import get_db
from utils.cryptomus import check_cryptomus_status
from utils.helpers import update_user_balance, record_transaction, notify_admin, update_membership
from utils.messages import escape_md

logger = logging.getLogger(__name__)


async def poll_pending_payments(context: ContextTypes.DEFAULT_TYPE):
    """Periodically check all pending Cryptomus payments."""
    async with get_db() as db:
        # 1. Check pending product orders
        cur = await db.execute(
            """SELECT o.*, p.name as product_name, u.first_name, u.telegram_id
               FROM orders o
               JOIN products p ON o.product_id = p.id
               JOIN users u ON o.user_id = u.telegram_id
               WHERE o.status = 'pending' AND o.payment_method = 'CRYPTOMUS' AND o.admin_note IS NOT NULL"""
        )
        pending_orders = [dict(r) for r in await cur.fetchall()]

        # 2. Check pending wallet top-up requests
        cur2 = await db.execute(
            """SELECT t.*, u.first_name, u.telegram_id
               FROM topup_requests t
               JOIN users u ON t.user_id = u.telegram_id
               WHERE t.status = 'pending' AND t.payment_method = 'CRYPTOMUS' AND t.tx_hash IS NOT NULL"""
        )
        pending_topups = [dict(r) for r in await cur2.fetchall()]

    # Process pending orders
    for order in pending_orders:
        uuid = order["admin_note"]
        order_id = order["id"]
        user_id = order["user_id"]
        total = order["total_price"]

        status = await check_cryptomus_status(uuid)

        if status == "paid":
            logger.info(f"Order #{order_id} has been paid successfully via Cryptomus!")
            async with get_db() as db:
                # Mark order as paid
                await db.execute(
                    "UPDATE orders SET status = 'paid', updated_at = datetime('now') WHERE id = ?",
                    (order_id,)
                )
                # Deduct stock & update sold counts
                await db.execute(
                    "UPDATE products SET sold = sold + ?, stock = CASE WHEN stock=-1 THEN -1 ELSE stock - ? END WHERE id = ?",
                    (order["quantity"], order["product_id"])
                )
                # Update user total spent
                await db.execute(
                    "UPDATE users SET total_spent = total_spent + ? WHERE telegram_id = ?",
                    (total, user_id)
                )
                await db.commit()

            from utils.helpers import process_order_delivery
            async with get_db() as db:
                await process_order_delivery(db, context.bot, order_id)
                cur_order = await db.execute("SELECT status FROM orders WHERE id=?", (order_id,))
                order_status = (await cur_order.fetchone())[0]

            await update_membership(user_id)

            if order_status != "delivered":
                # Notify user
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=f"✅ *Payment Confirmed\\!*\n\nYour payment for order \\#{order_id} is verified\\.\n"
                             f"The admin will deliver your product shortly\\.\n"
                             f"Use 👀 Orders to check status\\.",
                        parse_mode="MarkdownV2"
                    )
                except Exception as e:
                    logger.error(f"Failed to send confirmation to user: {e}")

            # Notify admin
            await notify_admin(
                context,
                f"🔔 *Order \\#{order_id} Paid (Auto)*\n"
                f"User: {escape_md(order['first_name'])} \\(`{user_id}`\\)\n"
                f"Product: {escape_md(order['product_name'])} x{order['quantity']}\n"
                f"Total: {escape_md(f'${total:.2f}')}\n"
                f"Status: Paid via Cryptomus ✅\n"
                f"Please deliver using /admin"
            )

        elif status in ["expired", "failed"]:
            logger.info(f"Order #{order_id} expired/failed on Cryptomus.")
            async with get_db() as db:
                await db.execute(
                    "UPDATE orders SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?",
                    (order_id,)
                )
                await db.commit()
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ *Order \\#{order_id} Expired*\n\nYour Cryptomus payment invoice has expired or failed\\.",
                    parse_mode="MarkdownV2"
                )
            except Exception:
                logger.exception('Failed to notify user %s about expired/failed order #%s', user_id, order_id)
                pass

    # Process pending top-up requests
    for req in pending_topups:
        uuid = req["tx_hash"]
        req_id = req["id"]
        user_id = req["user_id"]
        amount = req["amount"]

        status = await check_cryptomus_status(uuid)

        if status == "paid":
            logger.info(f"Top-up request #{req_id} has been paid successfully via Cryptomus!")
            async with get_db() as db:
                await db.execute(
                    "UPDATE topup_requests SET status = 'approved', updated_at = datetime('now') WHERE id = ?",
                    (req_id,)
                )
                # Credit balance
                await db.execute(
                    "UPDATE users SET balance = balance + ? WHERE telegram_id = ?",
                    (amount, user_id)
                )
                await db.commit()

            await record_transaction(user_id, amount, "topup", f"Cryptomus auto top-up #{req_id}")

            # Notify user
            try:
                amount_str = escape_md(f"${amount:.2f}")
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ *Top\\-Up Successful\\!*\n\n{amount_str} has been automatically added to your wallet\\! 💰",
                    parse_mode="MarkdownV2"
                )
            except Exception as e:
                logger.error(f"Failed to send top-up notification: {e}")

            # Notify admin
            await notify_admin(
                context,
                f"💰 *Wallet Top\\-Up Approved (Auto)*\n"
                f"User: {escape_md(req['first_name'])} \\(`{user_id}`\\)\n"
                f"Amount: {escape_md(f'${amount:.2f}')}\n"
                f"Status: Approved via Cryptomus ✅"
            )

        elif status in ["expired", "failed"]:
            logger.info(f"Top-up request #{req_id} expired/failed on Cryptomus.")
            async with get_db() as db:
                await db.execute(
                    "UPDATE topup_requests SET status = 'rejected', updated_at = datetime('now') WHERE id = ?",
                    (req_id,)
                )
                await db.commit()
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ *Top\\-Up Expired*\n\nYour Cryptomus top-up request \\#{req_id} has expired or failed\\.",
                    parse_mode="MarkdownV2"
                )
            except Exception:
                logger.exception('Failed to notify user %s about expired/failed top-up #%s', user_id, req_id)
                pass


async def send_recurring_message(context: ContextTypes.DEFAULT_TYPE):
    """Send a repeating message to a specific chat."""
    from config import RECURRING_CHAT, RECURRING_MESSAGE
    if not RECURRING_CHAT or not RECURRING_MESSAGE:
        return
    
    try:
        await context.bot.send_message(
            chat_id=RECURRING_CHAT,
            text=RECURRING_MESSAGE,
            parse_mode="HTML"
        )
        logger.info(f"✅ Recurring message successfully sent to {RECURRING_CHAT}")
    except Exception as e:
        logger.error(f"❌ Failed to send recurring message to {RECURRING_CHAT}: {e}")

