# 🛍️ Telegram Shop Bot

A fully functional Telegram shop bot similar to **Qamify** — built with Python.

## ✨ Features

| Feature | Description |
|---|---|
| 🛍️ Shop | Browse categories & products with prices, stock, emojis |
| 🛒 Buy Flow | Quantity selector, confirm screen, multiple payment methods |
| 💳 Payments | Wallet, USDT TRC20, USDT BEP20, Binance Pay |
| 💰 Wallet | Balance, top-up via crypto, transaction history |
| 🎁 Freebies | Separate section for free products |
| 📦 Orders | Full order history with status tracking |
| 👤 Profile | Membership tiers (Bronze → Silver → Gold → Diamond) |
| 📣 Refer & Earn | Referral links with automatic rewards |
| 🎟️ Coupons | Percentage or flat-rate discount codes |
| 🔧 Admin Panel | Full management via /admin command |

---

## 🚀 Setup — Step by Step

### Step 1: Get a Bot Token
1. Open Telegram → search **@BotFather**
2. Send `/newbot` and follow the steps
3. Copy the **token** you receive

### Step 2: Get Your Telegram User ID
1. Open Telegram → search **@userinfobot**
2. Send `/start`
3. Copy your **ID number**

### Step 3: Configure the Bot
```bash
# Copy the example config
copy .env.example .env
```
Open `.env` and fill in:
```
BOT_TOKEN=your_token_here
ADMIN_ID=your_telegram_id
BOT_USERNAME=your_bot_username
USDT_TRC20_ADDRESS=your_trc20_address   (optional)
USDT_BEP20_ADDRESS=your_bep20_address   (optional)
BINANCE_PAY_ID=your_binance_pay_id      (optional)
```

### Step 4: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 5: Run the Bot
```bash
python bot.py
```

---

## 🔧 Admin Panel

Send `/admin` to the bot (only works for the ADMIN_ID you set).

### Admin Features:
| Action | How |
|---|---|
| ➕ Add Product | /admin → Add Product → follow steps |
| 📦 Manage Products | /admin → Products → tap product → toggle/edit/delete |
| 📋 View Orders | /admin → Orders → tap order → mark paid/delivered/cancel |
| 💸 Approve Top-Ups | /admin → Top-up Requests → Approve / Reject |
| 👥 Manage Users | /admin → Users → add/deduct balance, ban/unban |
| 🎟️ Coupons | /admin → Coupons → create new / toggle on-off |
| 📢 Broadcast | /admin → Broadcast → type message → sends to all users |

---

## 💳 Payment Flow

### Wallet Payment (instant):
User selects Wallet → balance deducted → order created ✅

### Crypto Payment (manual):
1. User selects USDT/Binance
2. Bot shows wallet address + QR code
3. User sends payment & clicks "I've Sent Payment"
4. Admin gets notified
5. Admin goes to `/admin` → Orders → marks as Paid
6. Admin delivers the product and marks as Delivered

---

## 📁 Project Structure

```
telegram_shop_bot/
├── bot.py                  ← Entry point (run this)
├── config.py               ← Settings from .env
├── database/
│   ├── db.py               ← DB connection
│   └── models.py           ← Tables + seed data
├── handlers/
│   ├── start.py            ← /start command
│   ├── shop.py             ← Shop browsing
│   ├── payments.py         ← Payment processing
│   ├── wallet.py           ← Wallet management
│   ├── orders.py           ← Order history
│   ├── profile.py          ← User profile
│   ├── referral.py         ← Refer & earn
│   ├── freebies.py         ← Free products
│   └── admin.py            ← Admin panel
└── utils/
    ├── keyboards.py        ← All inline keyboards
    ├── messages.py         ← Message templates
    └── helpers.py          ← Utility functions
```

---

## 🔄 Membership Tiers

| Tier | Required Spend |
|---|---|
| 🥉 Bronze | $0 (default) |
| 🥈 Silver | $50+ |
| 🥇 Gold | $200+ |
| 💎 Diamond | $500+ |

Adjust thresholds in `.env`:
```
SILVER_THRESHOLD=50
GOLD_THRESHOLD=200
DIAMOND_THRESHOLD=500
```

---

## 🎟️ Coupon Codes

Create via `/admin` → Coupons → New Coupon:
- Enter code (e.g. `SAVE20`)
- Enter discount: `20%` for percentage or `$5` for flat rate
- Enter max uses (`-1` = unlimited)

---

## 📣 Referral System

- Each user gets a unique link: `t.me/YourBot?start=ref_USERID`
- When a referred user makes their **first purchase**, the referrer earns **$0.50** (configurable in `.env`)
