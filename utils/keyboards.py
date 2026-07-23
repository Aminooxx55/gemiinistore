"""keyboard builders — all inline keyboards in one place"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def persistent_menu_kb() -> ReplyKeyboardMarkup:
    """Persistent keyboard at the bottom of the screen."""
    return ReplyKeyboardMarkup([
        ["🛍️ Browse Shop", "💵 My Wallet"],
        ["😊 My Profile", "📣 Refer & Earn"],
        ["🎡 Spin & Win", "💬 Support Chat"]
    ], resize_keyboard=True)


# ── Main Menu ───────────────────────────────────────────────────────────────
def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍️ Products", callback_data="shop_home")],
        [
            InlineKeyboardButton("👤 Profile",     callback_data="profile_home"),
            InlineKeyboardButton("📋 Orders",      callback_data="orders_home"),
        ],
        [
            InlineKeyboardButton("💵 Wallet",      callback_data="wallet_home"),
            InlineKeyboardButton("📣 Refer & Earn", callback_data="referral_home"),
        ],
        [
            InlineKeyboardButton("🎡 Spin & Win",  callback_data="spin_home"),
            InlineKeyboardButton("📧 Email Trials", callback_data="email_trials"),
        ],
        [
            InlineKeyboardButton("💬 Support Chat", callback_data="support_chat"),
            InlineKeyboardButton("🗑️ Clear Chat",     callback_data="clear_chat"),
        ],
    ])


# ── Shop ────────────────────────────────────────────────────────────────────
def shop_categories_kb(categories: list) -> InlineKeyboardMarkup:
    rows = []
    for cat in categories:
        rows.append([InlineKeyboardButton(
            f"{cat['emoji']} {cat['name']}",
            callback_data=f"cat_{cat['id']}"
        )])
    rows.append([InlineKeyboardButton("🔄 Refresh",        callback_data="shop_home")])
    rows.append([InlineKeyboardButton("🏠 Back to Home",   callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)


def products_list_kb(products: list, cat_id: int = 0) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        stock = p.get("available_stock", p.get("stock", 0))
        stock_str = "♾️" if stock == -1 else str(stock)
        emoji = p.get("emoji", "").strip()
        name = p.get("name", "Product").strip()
        
        # Strip leading emoji if present in name to prevent double rendering
        if emoji and name.startswith(emoji):
            name = name[len(emoji):].strip()
        elif name and not emoji:
            # Extract leading emoji from name if emoji field was empty
            first_word = name.split()[0] if name.split() else ""
            if any(ord(char) > 127 for char in first_word):
                emoji = first_word
                name = name[len(first_word):].strip()

        icon = emoji if emoji else "📦"
        label = f"{icon} {name} ({stock_str})"
        rows.append([InlineKeyboardButton(label, callback_data=f"prod_{p['id']}")])
    rows.append([InlineKeyboardButton("🔄 Refresh",       callback_data="shop_home")])
    rows.append([InlineKeyboardButton("🏠 Back to Home",  callback_data="main_menu")])
    return InlineKeyboardMarkup(rows)


def product_detail_kb(product_id: int, is_free: bool) -> InlineKeyboardMarkup:
    label = "🛒 Claim Free" if is_free else "🛒 Buy Now"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"buy_start_{product_id}")],
        [InlineKeyboardButton("⬅️ Back",           callback_data="shop_home")],
        [InlineKeyboardButton("🏠 Back to Home",   callback_data="main_menu")],
    ])


def quantity_kb(product_id: int) -> InlineKeyboardMarkup:
    qtys = [1, 2, 3, 5, 10, 15, 20, 25]
    rows = []
    row = []
    for i, q in enumerate(qtys):
        row.append(InlineKeyboardButton(str(q), callback_data=f"qty_{product_id}_{q}"))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✏️ Custom Quantity", callback_data=f"qty_custom_{product_id}")])
    rows.append([InlineKeyboardButton("⬅️ Back",           callback_data=f"prod_{product_id}")])
    return InlineKeyboardMarkup(rows)


from utils.cryptomus import is_cryptomus_enabled


def confirm_purchase_kb(product_id: int, qty: int) -> InlineKeyboardMarkup:
    buttons = []
    buttons.append([InlineKeyboardButton("💳 Wallet — pay now", callback_data=f"pay_wallet_{product_id}_{qty}")])
    
    buttons.append([InlineKeyboardButton("🔷 Binance Pay", callback_data=f"pay_binance_{product_id}_{qty}")])
    buttons.append([InlineKeyboardButton("💜 USDT (POL)", callback_data=f"pay_pol_{product_id}_{qty}")])
    if is_cryptomus_enabled():
        buttons.append([InlineKeyboardButton("💳 Other Cryptos (Auto)", callback_data=f"pay_cryptomus_{product_id}_{qty}")])
        
    buttons.extend([
        [InlineKeyboardButton("🎟️ Apply Coupon",          callback_data=f"coupon_{product_id}_{qty}")],
        [InlineKeyboardButton("✏️ Change Quantity",       callback_data=f"buy_start_{product_id}")],
        [InlineKeyboardButton("❌ Cancel",                callback_data="main_menu")],
    ])
    return InlineKeyboardMarkup(buttons)


# ── Wallet ───────────────────────────────────────────────────────────────────
def wallet_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Top Up Wallet",         callback_data="topup_home")],
        [InlineKeyboardButton("📋 Transaction History",   callback_data="tx_history")],
        [InlineKeyboardButton("🏠 Back to Home",          callback_data="main_menu")],
    ])


def topup_method_kb(amount: float) -> InlineKeyboardMarkup:
    buttons = []
    
    if is_cryptomus_enabled():
        buttons.append([InlineKeyboardButton("🔷 Binance Pay (Auto)", callback_data=f"topup_cryptomus_{amount}")])
    else:
        buttons.append([InlineKeyboardButton("🔷 Binance Pay (Manual)",  callback_data=f"topup_binance_{amount}")])
        
    buttons.append([InlineKeyboardButton("💜 USDT (POL)", callback_data=f"topup_pol_{amount}")])
        
    buttons.extend([
        [InlineKeyboardButton("⬅️ Back",         callback_data="wallet_home")],
    ])
    return InlineKeyboardMarkup(buttons)


def topup_confirm_kb(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I've Sent Payment", callback_data=f"topup_sent_{req_id}")],
        [InlineKeyboardButton("❌ Cancel",             callback_data="wallet_home")],
    ])


# ── Orders ───────────────────────────────────────────────────────────────────
def orders_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Back to Home", callback_data="main_menu")],
    ])


def order_detail_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Back to Orders", callback_data="orders_home")],
        [InlineKeyboardButton("🏠 Home",            callback_data="main_menu")],
    ])


# ── Profile ───────────────────────────────────────────────────────────────────
def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 My Orders",        callback_data="orders_home")],
        [InlineKeyboardButton("📣 Refer & Earn",     callback_data="referral_home")],
        [InlineKeyboardButton("🏠 Back to Home",     callback_data="main_menu")],
    ])


# ── Referral ─────────────────────────────────────────────────────────────────
def referral_kb(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
    import urllib.parse
    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    encoded_link = urllib.parse.quote(link)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Share My Link", url=f"https://t.me/share/url?url={encoded_link}&text=Join+this+amazing+shop+bot!")],
        [InlineKeyboardButton("🏠 Back to Home",  callback_data="main_menu")],
    ])


# ── Admin ─────────────────────────────────────────────────────────────────────
def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Add Product",    callback_data="admin_add_product"),
            InlineKeyboardButton("📦 Products",       callback_data="admin_products"),
        ],
        [
            InlineKeyboardButton("📋 Orders",         callback_data="admin_orders"),
            InlineKeyboardButton("👥 Users",          callback_data="admin_users"),
        ],
        [
            InlineKeyboardButton("💸 Top-up Requests", callback_data="admin_topups"),
            InlineKeyboardButton("🎟️ Coupons",        callback_data="admin_coupons"),
        ],
        [
            InlineKeyboardButton("📢 Broadcast",         callback_data="admin_broadcast"),
            InlineKeyboardButton("💬 Support Tickets",   callback_data="admin_tickets_list"),
        ],
        [InlineKeyboardButton("🏠 Close Admin",       callback_data="main_menu")],
    ])


def admin_order_actions_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Mark Paid",      callback_data=f"admin_ord_paid_{order_id}")],
        [InlineKeyboardButton("📦 Mark Delivered", callback_data=f"admin_ord_delivered_{order_id}")],
        [InlineKeyboardButton("❌ Cancel Order",   callback_data=f"admin_ord_cancel_{order_id}")],
        [InlineKeyboardButton("⬅️ Back",           callback_data="admin_orders")],
    ])


def admin_topup_actions_kb(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve",   callback_data=f"admin_topup_approve_{req_id}")],
        [InlineKeyboardButton("❌ Reject",    callback_data=f"admin_topup_reject_{req_id}")],
        [InlineKeyboardButton("⬅️ Back",     callback_data="admin_topups")],
    ])


# ── Generic ───────────────────────────────────────────────────────────────────
def back_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 Back to Home", callback_data="main_menu")],
    ])
