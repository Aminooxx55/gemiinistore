# -*- coding: utf-8 -*-
"""All message templates used throughout the bot, optimized for premium readability."""
from config import get_membership

MD_CHARS = r"\_*[]()~`>#+-=|{}.!"


def escape_md(text: str) -> str:
    """Escape all MarkdownV2 special characters."""
    if not text:
        return ""
    text = str(text)
    for ch in MD_CHARS:
        text = text.replace(ch, f"\\{ch}")
    return text


def sep() -> str:
    """Consistent visual separator line."""
    return "━━━━━━━━━━━━━━━━━━━━━━"


def welcome_msg(first_name: str, balance: float, total_spent: float) -> str:
    membership = get_membership(total_spent)
    name = escape_md(first_name)
    bal = escape_md(f"${balance:.2f} USDT")
    mem = escape_md(membership)
    return (
        f"✨ *Digital store • Instant delivery*  ❞\n"
        f"Welcome to *GeminiStore*\n"
        f"🏛️ *Main Menu* 🏛️\n\n"
        f"💸 *Your Balance:* `{bal}`\n"
        f"🏆 *Membership Tier:* {mem}\n\n"
        f"👇 _Choose an option below_ 👇"
    )


def product_detail_msg(p: dict) -> str:
    stock = p.get("stock", 0)
    if stock == -1:
        stock_str = "♾️ Unlimited Stock"
    elif stock == 0:
        stock_str = "🔴 OUT OF STOCK"
    elif stock <= 3:
        stock_str = f"⚠️ Low Stock: Only {stock} left\\!"
    else:
        stock_str = f"🟢 In Stock: {stock} units"

    if p.get("is_free"):
        price_line = "Price: *FREE* 🔥"
    else:
        price_val = p.get("price", 0.0)
        price_str = escape_md(f"${price_val:.2f}")
        if p.get("has_discount") and p.get("old_price"):
            old_val = p.get("old_price", 0.0)
            old_str = escape_md(f"${old_val:.2f}")
            price_line = f"Price: *{price_str}* ~{old_str}~ \\(Save {escape_md(f'${old_val - price_val:.2f}')}\\) ⚡"
        else:
            price_line = f"Price: *{price_str}*"

    desc = escape_md(p.get("description") or "")
    name = escape_md(p.get("name", ""))

    return (
        f"📦 *{name.upper()}*\n"
        f"{sep()}\n"
        f"{desc}\n"
        f"{sep()}\n\n"
        f"💰 *{price_line}*\n"
        f"📦 *Availability:* {stock_str}\n"
        f"🔥 *Popularity:* {p.get('sold', 0)} items sold\n\n"
        f"👇 _Select your quantity or action below:_ "
    )


def confirm_purchase_msg(name: str, qty: int, unit_price: float,
                          total: float, balance: float,
                          coupon_discount: float = 0.0) -> str:
    final = max(0.0, total - coupon_discount)
    shortage = max(0.0, final - balance)
    
    lines = [
        "🛒 *ORDER CONFIRMATION*",
        sep(),
        f"📦 *Product:* {escape_md(name)}",
        f"🔢 *Quantity:* `{qty}`",
        f"💵 *Unit Price:* `{escape_md(f'${unit_price:.2f}')}`",
    ]
    if coupon_discount > 0:
        lines.append(f"🎟️ *Coupon Discount:* `-{escape_md(f'${coupon_discount:.2f}')}`")
    
    lines.extend([
        sep(),
        f"💰 *Total Amount:* `{escape_md(f'${final:.2f}')}`",
        f"💳 *Your Wallet Balance:* `{escape_md(f'${balance:.2f}')}`",
    ])
    
    if shortage > 0:
        lines.extend([
            sep(),
            f"⚠️ *Insufficient Balance\\!*",
            f"You need `{escape_md(f'${shortage:.2f}')}` more in your wallet to complete this purchase\\.",
        ])
    else:
        lines.extend([
            sep(),
            "✅ You have enough balance to pay instantly from your wallet\\.",
        ])
        
    return "\n".join(lines)


def payment_address_msg(method: str, amount: float, address: str) -> str:
    network = {
        "trc20": "USDT TRC20",
        "bep20": "USDT BEP20",
        "binance": "Binance Pay",
    }.get(method, method)
    return (
        f"💳 *INVOICE DETAILS*\n"
        f"{sep()}\n"
        f"💵 *Amount to Send:* `{escape_md(f'${amount:.2f}')}`\n"
        f"🔷 *Payment Method:* {escape_md(network)}\n"
        f"{sep()}\n\n"
        f"📋 *Recipient Address / Pay ID:*\n"
        f"`{escape_md(address)}`\n\n"
        f"⚠️ *Crucial Rules:*\n"
        f"1\\. Send *exactly* the amount requested above\\.\n"
        f"2\\. Once sent, click the **✅ I've Sent Payment** button below\\.\n\n"
        f"📸 _Please forward your transaction receipt / screenshot to @lovable47 for manual verification\\._"
    )


def order_status_msg(order: dict, product_name: str) -> str:
    status_emoji = {
        "pending": "⏳",
        "paid": "✅",
        "delivered": "📦",
        "cancelled": "❌",
    }.get(order["status"], "❓")
    
    total_val = order.get("total_price", 0.0)
    total_str = escape_md(f"${total_val:.2f}")
    
    return (
        f"📋 *ORDER #{order['id']} DETAIL*\n"
        f"{sep()}\n"
        f"📦 *Product:* {escape_md(product_name)}\n"
        f"🔢 *Quantity:* `{order['quantity']}`\n"
        f"💰 *Total Paid:* `{total_str}`\n"
        f"💳 *Method:* {escape_md(order['payment_method'])}\n"
        f"⏱️ *Status:* {status_emoji} {order['status'].capitalize()}\n"
        f"📅 *Order Date:* {escape_md(order['created_at'][:16])}\n"
        f"{sep()}"
    )
