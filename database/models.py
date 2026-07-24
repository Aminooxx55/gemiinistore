"""
Database schema creation and initial seed data.
Run on every bot startup — uses IF NOT EXISTS so it's safe to re-run.
"""
import aiosqlite
from database.db import get_db


CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username    TEXT,
    first_name  TEXT,
    balance     REAL    DEFAULT 0.0,
    total_spent REAL    DEFAULT 0.0,
    membership  TEXT    DEFAULT 'Bronze',
    referrer_id INTEGER,
    is_banned   INTEGER DEFAULT 0,
    created_at  TEXT    DEFAULT (datetime('now'))
)"""

CREATE_CATEGORIES = """
CREATE TABLE IF NOT EXISTS categories (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT UNIQUE NOT NULL,
    emoji     TEXT DEFAULT '📦',
    is_active INTEGER DEFAULT 1
)"""

CREATE_PRODUCTS = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT,
    price       REAL    NOT NULL DEFAULT 0.0,
    stock       INTEGER DEFAULT -1,   -- -1 = unlimited
    sold        INTEGER DEFAULT 0,
    emoji       TEXT    DEFAULT '📦',
    category_id INTEGER REFERENCES categories(id),
    is_free     INTEGER DEFAULT 0,
    is_active   INTEGER DEFAULT 1,
    has_discount INTEGER DEFAULT 0,
    old_price   REAL,
    image_url   TEXT,
    logo_url    TEXT,
    tier_prices TEXT,
    bulk_discount_enabled INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
)"""

CREATE_ORDERS = """
CREATE TABLE IF NOT EXISTS orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(telegram_id),
    product_id     INTEGER NOT NULL REFERENCES products(id),
    quantity       INTEGER DEFAULT 1,
    unit_price     REAL    NOT NULL,
    total_price    REAL    NOT NULL,
    coupon_id      INTEGER REFERENCES coupons(id),
    discount_amount REAL   DEFAULT 0.0,
    payment_method TEXT    NOT NULL,
    status         TEXT    DEFAULT 'pending',  -- pending/paid/delivered/cancelled
    delivery_info  TEXT,
    admin_note     TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
)"""

CREATE_TRANSACTIONS = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(telegram_id),
    amount      REAL    NOT NULL,
    type        TEXT    NOT NULL,  -- topup/purchase/refund/referral_reward
    description TEXT,
    order_id    INTEGER,
    created_at  TEXT DEFAULT (datetime('now'))
)"""

CREATE_COUPONS = """
CREATE TABLE IF NOT EXISTS coupons (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    code             TEXT UNIQUE NOT NULL,
    discount_percent REAL    DEFAULT 0.0,
    flat_discount    REAL    DEFAULT 0.0,
    max_uses         INTEGER DEFAULT -1,  -- -1 = unlimited
    uses_count       INTEGER DEFAULT 0,
    expires_at       TEXT,
    is_active        INTEGER DEFAULT 1,
    created_at       TEXT DEFAULT (datetime('now'))
)"""

CREATE_COUPON_USES = """
CREATE TABLE IF NOT EXISTS coupon_uses (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    coupon_id INTEGER REFERENCES coupons(id),
    user_id   INTEGER REFERENCES users(telegram_id),
    order_id  INTEGER REFERENCES orders(id),
    used_at   TEXT DEFAULT (datetime('now'))
)"""

CREATE_REFERRALS = """
CREATE TABLE IF NOT EXISTS referrals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    referrer_id  INTEGER NOT NULL REFERENCES users(telegram_id),
    referred_id  INTEGER NOT NULL REFERENCES users(telegram_id),
    reward_given INTEGER DEFAULT 0,
    created_at   TEXT DEFAULT (datetime('now'))
)"""

CREATE_TOPUP_REQUESTS = """
CREATE TABLE IF NOT EXISTS topup_requests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL REFERENCES users(telegram_id),
    amount         REAL    NOT NULL,
    payment_method TEXT    NOT NULL,
    tx_hash        TEXT,
    status         TEXT    DEFAULT 'pending',  -- pending/approved/rejected
    admin_note     TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
)"""

CREATE_USER_ACTIVITY = """
CREATE TABLE IF NOT EXISTS user_activity (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    first_name  TEXT,
    username    TEXT,
    action      TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
)"""

CREATE_REVIEWS = """
CREATE TABLE IF NOT EXISTS reviews (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(telegram_id),
    product_id  INTEGER NOT NULL REFERENCES products(id),
    rating      INTEGER NOT NULL,
    comment     TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
)"""

CREATE_PRODUCT_STOCK = """
CREATE TABLE IF NOT EXISTS product_stock (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    data       TEXT NOT NULL,
    is_sold    INTEGER DEFAULT 0,
    sold_at    TEXT,
    order_id   INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    created_at TEXT DEFAULT (datetime('now'))
)"""

CREATE_USER_SPINS = """
CREATE TABLE IF NOT EXISTS user_spins (
    telegram_id INTEGER PRIMARY KEY,
    last_spin_at TEXT NOT NULL
)"""

CREATE_SUPPORT_TICKETS = """
CREATE TABLE IF NOT EXISTS support_tickets (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(telegram_id),
    message    TEXT NOT NULL,
    status     TEXT DEFAULT 'open',
    created_at TEXT DEFAULT (datetime('now'))
)"""

CREATE_INDEX_ORDERS_USER = "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id)"
CREATE_INDEX_ORDERS_PRODUCT = "CREATE INDEX IF NOT EXISTS idx_orders_product_id ON orders(product_id)"
CREATE_INDEX_TRANSACTIONS_USER = "CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id)"
CREATE_INDEX_PRODUCT_STOCK_PROD = "CREATE INDEX IF NOT EXISTS idx_product_stock_prod ON product_stock(product_id, is_sold)"
CREATE_INDEX_SUPPORT_USER = "CREATE INDEX IF NOT EXISTS idx_support_user_id ON support_tickets(user_id)"

SEED_CATEGORIES = [
    ("🤖 Gemini Advanced", "🤖"),
    ("📚 Coursera", "📚"),
    ("🛠️ Supabase", "🛠️"),
    ("🔁 N8N", "🔁"),
    ("💡 Lovable", "💡"),
]

SEED_PRODUCTS = [
    # name, desc, price, stock, sold, emoji, cat_id (1-based index), is_free, is_active, has_discount, old_price, image_url
    ("Google AI Pro 18 Months (Activation Link)", "⚡ *Instant Activation Link*\n\nReceive a direct link to activate Google AI Pro on your own Google account for 18 Months!\nNo login required. Works worldwide.\n\n📈 *Bulk Discounts:*\n• 10+ items: *$1.35* each\n• 20+ items: *$1.25* each\n• 50+ items: *$1.10* each", 1.49, 0, 0, "🤖", 1, 0, 1, 0, None, "http://134.122.112.90:5000/static/product_banner.png"),
]


async def init_db():
    async with get_db() as db:
        # Create tables
        for sql in [CREATE_USERS, CREATE_CATEGORIES, CREATE_PRODUCTS,
                    CREATE_ORDERS, CREATE_TRANSACTIONS, CREATE_COUPONS,
                    CREATE_COUPON_USES, CREATE_REFERRALS, CREATE_TOPUP_REQUESTS,
                    CREATE_USER_ACTIVITY, CREATE_REVIEWS, CREATE_PRODUCT_STOCK,
                    CREATE_USER_SPINS, CREATE_SUPPORT_TICKETS,
                    CREATE_INDEX_ORDERS_USER, CREATE_INDEX_ORDERS_PRODUCT,
                    CREATE_INDEX_TRANSACTIONS_USER, CREATE_INDEX_PRODUCT_STOCK_PROD,
                    CREATE_INDEX_SUPPORT_USER]:
            await db.execute(sql)

        # Migration: Add image_url column if not exists
        try:
            await db.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
            await db.commit()
        except Exception:
            pass

        # Migration: Add tier_prices column if not exists
        try:
            await db.execute("ALTER TABLE products ADD COLUMN tier_prices TEXT")
            await db.commit()
        except Exception:
            pass

        # Migration: Add bulk_discount_enabled toggle (per-product on/off switch)
        try:
            await db.execute("ALTER TABLE products ADD COLUMN bulk_discount_enabled INTEGER DEFAULT 0")
            await db.commit()
        except Exception:
            pass

        # Migration: Add logo_url column (small brand logo shown next to product)
        try:
            await db.execute("ALTER TABLE products ADD COLUMN logo_url TEXT")
            await db.commit()
        except Exception:
            pass

        # Migration: Add created_at column to product_stock if not exists
        try:
            await db.execute("ALTER TABLE product_stock ADD COLUMN created_at TEXT DEFAULT (datetime('now'))")
            await db.commit()
        except Exception:
            pass

        # Seed categories if empty
        cur = await db.execute("SELECT COUNT(*) FROM categories")
        row = await cur.fetchone()
        if row[0] == 0:
            for name, emoji in SEED_CATEGORIES:
                await db.execute(
                    "INSERT OR IGNORE INTO categories (name, emoji) VALUES (?, ?)",
                    (name, emoji)
                )

        # Seed products if empty
        cur = await db.execute("SELECT COUNT(*) FROM products")
        row = await cur.fetchone()
        if row[0] == 0:
            # Get category IDs in order
            cur = await db.execute("SELECT id FROM categories ORDER BY id")
            cats = [r[0] for r in await cur.fetchall()]
            for p in SEED_PRODUCTS:
                name, desc, price, stock, sold, emoji, cat_idx, is_free, is_active, has_discount, old_price, img_url = p
                cat_id = cats[cat_idx - 1] if cat_idx <= len(cats) else None
                await db.execute(
                    """INSERT INTO products
                       (name, description, price, stock, sold, emoji, category_id,
                        is_free, is_active, has_discount, old_price, image_url)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (name, desc, price, stock, sold, emoji, cat_id,
                     is_free, is_active, has_discount, old_price, img_url)
                )

        # Seed coupons
        await db.execute(
            "INSERT OR IGNORE INTO coupons (code, discount_percent, flat_discount, max_uses, uses_count, is_active) VALUES ('gemini20', 20.0, 0.0, -1, 0, 1)"
        )

        await db.commit()
