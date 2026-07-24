# -*- coding: utf-8 -*-
"""All message templates used throughout the bot, optimized for premium readability."""
from config import get_membership, SILVER_THRESHOLD, GOLD_THRESHOLD, DIAMOND_THRESHOLD

from html import escape as html_escape
from config import SUPPORT_USERNAME

def sep() -> str:
    """Consistent visual separator line."""
    return "━━━━━━━━━━━━━━━━━━━━━━"


def welcome_msg(first_name: str, balance: float, total_spent: float) -> str:
    membership = get_membership(total_spent)
    name = html_escape(first_name)
    bal = f"${balance:.2f} USDT"
    mem = html_escape(membership)
    return (
        f"✨ <b>Digital store • Instant delivery</b>  ❞\n"
        f"Welcome to <b>GeminiStore</b>\n"
        f"🏛️ <b>Main Menu</b> 🏛️\n\n"
        f"💸 <b>Your Balance:</b> <code>{bal}</code>\n"
        f"🏆 <b>Membership Tier:</b> {mem}\n\n"
        f"👇 <i>Choose an option below</i> 👇"
    )


def product_detail_msg(p: dict) -> str:
    stock = p.get("stock", 0)
    if stock == -1:
        stock_str = "♾️ Unlimited Stock"
    elif stock == 0:
        stock_str = "0 (OUT OF STOCK)"
    else:
        stock_str = str(stock)

    desc = html_escape(p.get("description") or "")
    name = html_escape(p.get("name", ""))
    sold = p.get("sold", 0) or 0

    # Build a real, data-driven bulk-pricing block from tier_prices when the
    # product has bulk discount enabled. Never hardcoded, never drifts.
    tier_block = ""
    try:
        from utils.helpers import build_tier_summary
        summary = build_tier_summary(p.get("id"), float(p.get("price", 0) or 0))
        if summary:
            tier_block = f"{summary}\n"
    except Exception:
        tier_block = ""

    return (
        f"📦 <b>{name.upper()}</b>\n"
        f"{sep()}\n"
        f"{desc}\n\n"
        f"{tier_block}"
        f"📊 Stock: {stock_str}\n"
        f"🔥 Popularity: {sold} items sold\n\n"
        f"👇 Select your action below:"
    )


def confirm_purchase_msg(name: str, qty: int, unit_price: float,
                          total: float, balance: float,
                          coupon_discount: float = 0.0) -> str:
    final = max(0.0, total - coupon_discount)
    shortage = max(0.0, final - balance)
    
    lines = [
        "🛒 <b>ORDER CONFIRMATION</b>",
        sep(),
        f"📦 <b>Product:</b> {html_escape(name)}",
        f"🔢 <b>Quantity:</b> <code>{qty}</code>",
        f"💵 <b>Unit Price:</b> <code>${unit_price:.2f}</code>",
    ]
    if coupon_discount > 0:
        lines.append(f"🎟️ <b>Coupon Discount:</b> <code>-${coupon_discount:.2f}</code>")
    
    lines.extend([
        sep(),
        f"💰 <b>Total Amount:</b> <code>${final:.2f}</code>",
        f"💳 <b>Your Wallet Balance:</b> <code>${balance:.2f}</code>",
    ])
    
    if shortage > 0:
        lines.extend([
            sep(),
            f"⚠️ <b>Insufficient Balance!</b>",
            f"You need <code>${shortage:.2f}</code> more in your wallet to complete this purchase.",
        ])
    else:
        lines.extend([
            sep(),
            "✅ You have enough balance to pay instantly from your wallet.",
        ])
        
    return "\n".join(lines)


def payment_address_msg(method: str, amount: float, address: str) -> str:
    network = {
        "pol": "USDT POL",
        "bep20": "USDT BEP20",
        "binance": "Binance Pay",
    }.get(method, method)
    extra_instructions = (
        f"Once sent, click the <b>✅ I've Sent Payment</b> button below and enter your Transaction ID/Reference for <i>instant automatic verification</i>."
        if method == "binance" else
        f"Once sent, click the <b>✅ I've Sent Payment</b> button below.\n\n📸 <i>Please forward your transaction receipt / screenshot to {SUPPORT_USERNAME} for manual verification.</i>"
    )

    return (
        f"💳 <b>INVOICE DETAILS</b>\n"
        f"{sep()}\n"
        f"💵 <b>Amount to Send:</b> <code>${amount:.2f}</code>\n"
        f"🔷 <b>Payment Method:</b> {html_escape(network)}\n"
        f"{sep()}\n\n"
        f"📋 <b>Recipient Address / Pay ID:</b>\n"
        f"<code>{html_escape(address)}</code>\n\n"
        f"⚠️ <b>Crucial Rules:</b>\n"
        f"1. Send <b>exactly</b> the amount requested above.\n"
        f"2. {extra_instructions}"
    )


def order_status_msg(order: dict, product_name: str) -> str:
    status_emoji = {
        "pending": "⏳",
        "paid": "✅",
        "delivered": "📦",
        "cancelled": "❌",
    }.get(order["status"], "❓")
    
    total_val = order.get("total_price", 0.0)
    total_str = f"${total_val:.2f}"
    
    return (
        f"📋 <b>ORDER #{order['id']} DETAIL</b>\n"
        f"{sep()}\n"
        f"📦 <b>Product:</b> {html_escape(product_name)}\n"
        f"🔢 <b>Quantity:</b> <code>{order['quantity']}</code>\n"
        f"💰 <b>Total Paid:</b> <code>{total_str}</code>\n"
        f"💳 <b>Method:</b> {html_escape(order['payment_method'])}\n"
        f"⏱️ <b>Status:</b> {status_emoji} {order['status'].capitalize()}\n"
        f"📅 <b>Order Date:</b> <code>{html_escape(order['created_at'][:16])}</code>\n"
        f"{sep()}"
    )


def format_profile_text(user: dict) -> str:
    """Generate HTML-formatted profile display text.

    Args:
        user: A user row dict with keys: first_name, username, telegram_id,
              balance, total_spent.

    Returns:
        HTML-formatted profile text string.
    """
    membership = get_membership(user["total_spent"])

    # Next tier info
    if user["total_spent"] < SILVER_THRESHOLD:
        diff = SILVER_THRESHOLD - user['total_spent']
        next_tier = f"🥈 Silver (spend ${diff:.2f} more)"
    elif user["total_spent"] < GOLD_THRESHOLD:
        diff = GOLD_THRESHOLD - user['total_spent']
        next_tier = f"🥇 Gold (spend ${diff:.2f} more)"
    elif user["total_spent"] < DIAMOND_THRESHOLD:
        diff = DIAMOND_THRESHOLD - user['total_spent']
        next_tier = f"💎 Diamond (spend ${diff:.2f} more)"
    else:
        next_tier = "🏆 You are at the highest tier!"

    username_str = f"@{html_escape(user['username'])}" if user["username"] else "N/A"
    bal_str = f"${user['balance']:.2f}"
    spent_str = f"${user['total_spent']:.2f}"

    return (
        f"😊 <b>My Profile</b>\n\n"
        f"👤 <b>Name:</b> {html_escape(user['first_name'])}\n"
        f"🔗 <b>Username:</b> {username_str}\n"
        f"🆔 <b>ID:</b> <code>{user['telegram_id']}</code>\n\n"
        f"{sep()}\n"
        f"💰 <b>Balance:</b> {bal_str}\n"
        f"📊 <b>Total Spent:</b> {spent_str}\n"
        f"🪪 <b>Membership:</b> {html_escape(membership)}\n"
        f"⬆️ <b>Next Tier:</b> {next_tier}\n"
        f"{sep()}"
    )


def channel_sale_announcement_msg(product_name: str, qty: int, total_price: float, remaining_stock: int) -> str:
    """Posted to the public channel whenever a purchase is completed."""
    name = html_escape(product_name)
    if remaining_stock == -1:
        stock_str = "♾️ Unlimited"
    elif remaining_stock == 0:
        stock_str = "⚠️ OUT OF STOCK"
    else:
        stock_str = f"{remaining_stock} account(s) left"

    return (
        f"🛒 <b>NEW SALE!</b>\n\n"
        f"📦 <b>{name}</b>\n"
        f"🔢 <b>Qty Bought:</b> {qty} account{'s' if qty > 1 else ''}\n"
        f"💰 <b>Total:</b> ${total_price:.2f} USDT\n"
        f"📊 <b>Stock Remaining:</b> {stock_str}\n\n"
        f"⚡️ <i>Get yours before it's gone — visit the shop now!</i>"
    )


def channel_restock_msg(product_name: str, price: float, qty_added: int, remaining: int) -> str:
    """Posted to the public channel whenever admin uploads new stock."""
    name = html_escape(product_name)
    stock_str = "♾️ Unlimited" if remaining == -1 else f"{remaining} account(s)"
    return (
        f"🆕 <b>NEW STOCK JUST DROPPED</b>⁉️\n\n"
        f"📦 <b>{name}</b>\n"
        f"🏷 <b>Price:</b> {price:.2f} USDT\n"
        f"📦 <b>Available now:</b> {stock_str}\n"
        f"✨ <b>Freshly restocked:</b> {qty_added} new account{'s' if qty_added > 1 else ''}\n\n"
        f"⚡️ Secure your account before the stock runs out!"
    )


def escape_md(text: str) -> str:
    """Escape all MarkdownV2 special characters (fallback for legacy files)."""
    if not text:
        return ""
    text = str(text)
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text
