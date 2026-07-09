# -*- coding: utf-8 -*-
"""All message templates used throughout the bot."""
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
    return "\\-\\-\\-\\-\\-\\-\\-\\-\\-"


def welcome_msg(first_name: str, balance: float, total_spent: float) -> str:
    membership = get_membership(total_spent)
    name = escape_md(first_name)
    bal = escape_md(f"${balance:.2f}")
    mem = escape_md(membership)
    return (
        f"✨ *Welcome to GeminiStore, {name}\\!* ✨\n\n"
        f"🚀 *Your premium hub for Google AI Pro activations\\.*\n"
        f"Get instant activation links at the absolute cheapest rates on the market\\!\n\n"
        f"💳 *Wallet Balance:* {bal}\n"
        f"🪪 *Membership Tier:* {mem}\n\n"
        f"Use the menu buttons below to browse products, manage your wallet, or contact support\\."
    )


def product_detail_msg(p: dict) -> str:
    stock = p.get("stock", 0)
    if stock == -1:
        stock_str = "Unlimited"
    elif stock == 0:
        stock_str = "OUT OF STOCK"
    elif stock <= 3:
        stock_str = f"Only {stock} left\\!"
    else:
        stock_str = f"{stock} in stock"

    if p.get("is_free"):
        price_line = "Price: *FREE* \U0001f525"
    else:
        price_val = p.get("price", 0.0)
        price_str = escape_md(f"${price_val:.2f}")
        if p.get("has_discount") and p.get("old_price"):
            old_val = p.get("old_price", 0.0)
            old_str = escape_md(f"${old_val:.2f}")
            price_line = f"Price: *{price_str}* ~{old_str}~ \u26a1"
        else:
            price_line = f"Price: *{price_str}*"

    desc = escape_md(p.get("description") or "")
    name = escape_md(p.get("name", ""))

    return (
        f"{p.get('emoji','') } *{name}*\n\n"
        f"{desc}\n\n"
        f"{sep()}\n"
        f"\U0001f4b0 {price_line}\n"
        f"\U0001f4e6 Stock: {escape_md(stock_str)}\n"
        f"\U0001f6d2 {p.get('sold', 0)} sold\n"
        f"{sep()}"
    )


def confirm_purchase_msg(name: str, qty: int, unit_price: float,
                          total: float, balance: float,
                          coupon_discount: float = 0.0) -> str:
    final = max(0.0, total - coupon_discount)
    shortage = max(0.0, final - balance)
    lines = [
        "\U0001f6d2 *Confirm Purchase*",
        sep(),
        f"\U0001f4e6 *Product:* {escape_md(name)}",
        f"\U0001f522 *Quantity:* {qty}",
        f"\U0001f4b2 *Unit Price:* {escape_md(f'${unit_price:.2f}')}",
    ]
    if coupon_discount > 0:
        lines.append(f"\U0001f3ab *Coupon Discount:* {escape_md(f'-${coupon_discount:.2f}')}")
    if shortage > 0:
        lines.append(f"\u26a0 *Wallet short {escape_md(f'${shortage:.2f}')}*")
    lines += [
        f"\U0001f4b0 *Total:* {escape_md(f'${final:.2f}')}",
        sep(),
        f"\U0001f45b *Your Wallet Balance:* {escape_md(f'${balance:.2f}')}",
        sep(),
        "",
        "Choose a payment method:",
    ]
    return "\n".join(lines)


def payment_address_msg(method: str, amount: float, address: str) -> str:
    network = {
        "trc20": "USDT TRC20",
        "bep20": "USDT BEP20",
        "binance": "Binance Pay",
    }.get(method, method)
    return (
        f"\U0001f4b3 *Send Exactly {escape_md(f'${amount:.2f}')} via {escape_md(network)}*\n\n"
        f"\U0001f4cb *Address / ID:*\n"
        f"`{escape_md(address)}`\n\n"
        f"\u26a0 Send *exactly* the amount shown\\.\n"
        f"After sending, click \u2705 I've Sent Payment\\.\n\n"
        f"📸 *Send a screenshot of the payment to @lovable47 for instant check\\!*"
    )


def order_status_msg(order: dict, product_name: str) -> str:
    status_emoji = {
        "pending": "\u23f3",
        "paid": "\u2705",
        "delivered": "\U0001f4e6",
        "cancelled": "\u274c",
    }.get(order["status"], "?")
    total_val = order.get("total_price", 0.0)
    total_str = escape_md(f"${total_val:.2f}")
    return (
        f"\U0001f4cb *Order \\#{order['id']}*\n\n"
        f"\U0001f4e6 *Product:* {escape_md(product_name)}\n"
        f"\U0001f522 *Quantity:* {order['quantity']}\n"
        f"\U0001f4b0 *Total:* {total_str}\n"
        f"\U0001f4b3 *Payment:* {escape_md(order['payment_method'])}\n"
        f"\U0001f4ca *Status:* {status_emoji} {order['status'].capitalize()}\n"
        f"\U0001f4c5 *Date:* {escape_md(order['created_at'][:16])}\n"
    )
