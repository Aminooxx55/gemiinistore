# -*- coding: utf-8 -*-
"""Advanced Web Admin Dashboard for Telegram Shop Bot."""
import os
import sqlite3
import logging
import urllib.request
import urllib.parse
import json
from flask import Flask, jsonify, request, render_template_string

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_dashboard")

app = Flask(__name__)
DB_PATH = "shop.db"
ENV_PATH = ".env"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_bot_token():
    """Read BOT_TOKEN from .env file."""
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    parts = line.strip().split("=", 1)
                    if parts[0].strip() == "BOT_TOKEN":
                        return parts[1].strip()
    return ""


def send_telegram_msg(token: str, chat_id: int, text: str):
    """Send a telegram message using urllib (no dependencies)."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read()
    except Exception as e:
        logger.error(f"Error sending msg to {chat_id}: {e}")
        return None


def update_env_var(key: str, value: str):
    """Write/update key-value in .env file."""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()

    key_found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            key_found = True
        else:
            new_lines.append(line)

    if not key_found:
        new_lines.append(f"{key}={value}\n")

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GeminiStore — Advanced Control Panel</title>
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <!-- FontAwesome Icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <!-- ChartJS -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    fontFamily: {
                        sans: ['"Plus Jakarta Sans"', 'sans-serif'],
                    }
                }
            }
        }
    </script>
    <style>
        body {
            background-color: #080c14;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.12) 0px, transparent 40%),
                radial-gradient(at 50% 0%, rgba(139, 92, 246, 0.08) 0px, transparent 50%),
                radial-gradient(at 100% 0%, rgba(236, 72, 153, 0.12) 0px, transparent 40%);
        }
        .glass {
            background: rgba(13, 20, 35, 0.7);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.07);
        }
        .sidebar-btn-active {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%);
            border-left: 4px solid #6366f1;
            color: #ffffff;
        }
        .custom-scrollbar::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.01);
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.2);
        }
    </style>
</head>
<body class="text-gray-200 min-h-screen font-sans antialiased custom-scrollbar">

    <!-- Global Container -->
    <div class="flex min-h-screen">

        <!-- Sidebar Navigation -->
        <aside class="w-64 glass border-r border-gray-800 flex flex-col justify-between shrink-0 sticky top-0 h-screen">
            <div class="space-y-6">
                <!-- Branding Header -->
                <div class="px-6 py-5 border-b border-gray-800 flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                        <i class="fa-solid fa-bolt text-white text-lg"></i>
                    </div>
                    <div>
                        <h1 class="text-md font-bold tracking-tight text-white leading-tight">GeminiStore v2</h1>
                        <span class="text-[10px] text-indigo-400 font-semibold uppercase tracking-wider">Advanced Console</span>
                    </div>
                </div>

                <!-- Navigation List -->
                <nav class="space-y-1 px-3">
                    <button onclick="switchTab('overview')" id="tab-overview-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition sidebar-btn-active">
                        <i class="fa-solid fa-chart-pie w-5"></i><span>Overview</span>
                    </button>
                    <button onclick="switchTab('products')" id="tab-products-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-cubes w-5"></i><span>Products Catalog</span>
                    </button>
                    <button onclick="switchTab('users')" id="tab-users-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-users w-5"></i><span>Users Database</span>
                    </button>
                    <button onclick="switchTab('orders')" id="tab-orders-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-receipt w-5"></i><span>Orders List</span>
                    </button>
                    <button onclick="switchTab('reviews')" id="tab-reviews-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-star w-5"></i><span>User Reviews</span>
                    </button>
                    <button onclick="switchTab('coupons')" id="tab-coupons-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-tags w-5"></i><span>Promo Coupons</span>
                    </button>
                    <button onclick="switchTab('broadcast')" id="tab-broadcast-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-bullhorn w-5"></i><span>Announcements</span>
                    </button>
                    <button onclick="switchTab('settings')" id="tab-settings-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-sliders w-5"></i><span>System Settings</span>
                    </button>
                </nav>
            </div>

            <!-- Sidebar Footer Status -->
            <div class="p-4 border-t border-gray-800 space-y-2">
                <div class="flex items-center justify-between text-xs">
                    <span class="text-gray-400 font-medium">Gateway Service:</span>
                    <span class="text-green-400 flex items-center"><span class="w-2 h-2 rounded-full bg-green-500 mr-2 animate-ping"></span>Online</span>
                </div>
                <div class="flex items-center justify-between text-xs">
                    <span class="text-gray-400 font-medium">API Poller:</span>
                    <span class="text-indigo-400">8s Live Sync</span>
                </div>
            </div>
        </aside>

        <!-- Main Body Wrapper -->
        <div class="flex-1 flex flex-col min-w-0 font-sans">

            <!-- Global Header -->
            <header class="h-16 glass border-b border-gray-800 px-8 flex items-center justify-between sticky top-0 z-30">
                <div class="flex items-center space-x-4">
                    <h2 class="text-md font-bold text-gray-100" id="current-page-title">Overview Dashboard</h2>
                </div>
                <div class="flex items-center space-x-4">
                    <button onclick="fetchStats(); fetchActivity();" class="px-3.5 py-1.5 rounded-lg bg-gray-900 border border-gray-800 hover:bg-gray-800 text-xs font-semibold text-gray-300 transition flex items-center space-x-1.5">
                        <i class="fa-solid fa-arrows-rotate"></i><span>Refresh Data</span>
                    </button>
                    <div class="h-6 w-px bg-gray-800"></div>
                    <span class="text-xs text-gray-400 font-medium"><i class="fa-solid fa-user-shield mr-1.5 text-indigo-500"></i>Root Administrator</span>
                </div>
            </header>

            <!-- Scrollable Content Page -->
            <div class="flex-1 p-8 space-y-6 overflow-y-auto max-w-[1400px]">

                <!-- 🌐 TAB 1: OVERVIEW -->
                <div id="tab-overview" class="space-y-6">
                    <!-- KPI statistics widgets -->
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        <div class="glass p-6 rounded-2xl flex items-center justify-between">
                            <div class="space-y-1">
                                <p class="text-xs font-semibold uppercase text-gray-500 tracking-wider">Total Sales Income</p>
                                <p class="text-3xl font-bold tracking-tight text-emerald-400" id="stat-revenue">$0.00</p>
                            </div>
                            <div class="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
                                <i class="fa-solid fa-wallet text-lg"></i>
                            </div>
                        </div>
                        <div class="glass p-6 rounded-2xl flex items-center justify-between">
                            <div class="space-y-1">
                                <p class="text-xs font-semibold uppercase text-gray-500 tracking-wider">Total Active Customers</p>
                                <p class="text-3xl font-bold tracking-tight text-white" id="stat-users">0</p>
                            </div>
                            <div class="w-12 h-12 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center border border-blue-500/20">
                                <i class="fa-solid fa-users text-lg"></i>
                            </div>
                        </div>
                        <div class="glass p-6 rounded-2xl flex items-center justify-between">
                            <div class="space-y-1">
                                <p class="text-xs font-semibold uppercase text-gray-500 tracking-wider">Completed Orders</p>
                                <p class="text-3xl font-bold tracking-tight text-indigo-400" id="stat-orders">0</p>
                            </div>
                            <div class="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
                                <i class="fa-solid fa-box text-lg"></i>
                            </div>
                        </div>
                        <div class="glass p-6 rounded-2xl flex items-center justify-between">
                            <div class="space-y-1">
                                <p class="text-xs font-semibold uppercase text-gray-500 tracking-wider">Pending Deposits</p>
                                <p class="text-3xl font-bold tracking-tight text-amber-400" id="stat-pending">0</p>
                            </div>
                            <div class="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20">
                                <i class="fa-solid fa-circle-notch text-lg animate-spin"></i>
                            </div>
                        </div>
                    </div>

                    <!-- Chart + Activity Row -->
                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <!-- Revenue Area Chart -->
                        <div class="glass p-6 rounded-2xl lg:col-span-2 space-y-4">
                            <h3 class="text-sm font-bold uppercase tracking-wider text-gray-400">Income Overview (Past 7 Days)</h3>
                            <div class="h-72">
                                <canvas id="chart-revenue"></canvas>
                            </div>
                        </div>
                        <!-- Live activity monitor -->
                        <div class="glass p-6 rounded-2xl flex flex-col h-[348px] space-y-4">
                            <div class="flex items-center justify-between border-b border-gray-800 pb-3">
                                <h3 class="text-sm font-bold uppercase tracking-wider text-gray-400"><i class="fa-solid fa-circle text-xs text-green-500 mr-2 animate-pulse"></i>Live User Logs</h3>
                                <span class="text-[10px] bg-indigo-500/10 text-indigo-400 px-2 py-0.5 rounded border border-indigo-500/20 font-bold uppercase">Real-Time</span>
                            </div>
                            <div class="flex-1 overflow-y-auto custom-scrollbar space-y-3 pr-1" id="overview-activities">
                                <p class="text-xs text-gray-500 text-center py-10">No recent logs recorded...</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 🛍️ TAB 2: PRODUCTS CATALOG -->
                <div id="tab-products" class="space-y-6 hidden">
                    <div class="flex justify-between items-center">
                        <p class="text-sm text-gray-400">View, edit, or create products listed in the shop catalog.</p>
                        <button onclick="openProductModal()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20 transition flex items-center space-x-1.5">
                            <i class="fa-solid fa-plus text-xs"></i><span>Create Product</span>
                        </button>
                    </div>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">Product Info</th>
                                        <th class="p-4">Category</th>
                                        <th class="p-4">Price</th>
                                        <th class="p-4">Stock</th>
                                        <th class="p-4">Sold</th>
                                        <th class="p-4">Status</th>
                                        <th class="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="products-table-body" class="divide-y divide-gray-800/50">
                                    <!-- Loaded via JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 👥 TAB 3: USERS DATABASE -->
                <div id="tab-users" class="space-y-6 hidden">
                    <p class="text-sm text-gray-400">Manage client accounts, adjust balances, and block/unblock users.</p>
                    
                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">User Details</th>
                                        <th class="p-4">Username</th>
                                        <th class="p-4">Telegram ID</th>
                                        <th class="p-4">Wallet Balance</th>
                                        <th class="p-4">Total Spent</th>
                                        <th class="p-4">Membership</th>
                                        <th class="p-4">Account Status</th>
                                        <th class="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="users-table-body" class="divide-y divide-gray-800/50">
                                    <!-- Loaded via JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 📋 TAB 4: ORDERS LIST -->
                <div id="tab-orders" class="space-y-6 hidden">
                    <p class="text-sm text-gray-400">View pending, completed, or failed shop orders and confirm manual deliveries.</p>
                    
                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">ID</th>
                                        <th class="p-4">Client</th>
                                        <th class="p-4">Item Details</th>
                                        <th class="p-4">Quantity</th>
                                        <th class="p-4">Total Price</th>
                                        <th class="p-4">Payment Method</th>
                                        <th class="p-4">Delivery Status</th>
                                        <th class="p-4">Order Date</th>
                                        <th class="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="orders-table-body" class="divide-y divide-gray-800/50">
                                    <!-- Loaded via JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- ⭐ TAB 5: USER REVIEWS -->
                <div id="tab-reviews" class="space-y-6 hidden">
                    <p class="text-sm text-gray-400">Check user experience feedback and star ratings submitted by customers after order delivery.</p>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">Client Details</th>
                                        <th class="p-4">Product Name</th>
                                        <th class="p-4">Rating</th>
                                        <th class="p-4">Comment Feedback</th>
                                        <th class="p-4">Submitted At</th>
                                    </tr>
                                </thead>
                                <tbody id="reviews-table-body" class="divide-y divide-gray-800/50">
                                    <!-- Loaded via JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 🎟️ TAB 6: PROMO COUPONS -->
                <div id="tab-coupons" class="space-y-6 hidden">
                    <div class="flex justify-between items-center">
                        <p class="text-sm text-gray-400">Create and distribute promotional codes for percentage or flat-rate discounts.</p>
                        <button onclick="openCouponModal()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20 transition flex items-center space-x-1.5">
                            <i class="fa-solid fa-plus text-xs"></i><span>Add Coupon</span>
                        </button>
                    </div>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">Promo Code</th>
                                        <th class="p-4">Percent Discount</th>
                                        <th class="p-4">Flat Discount ($)</th>
                                        <th class="p-4">Uses Count</th>
                                        <th class="p-4">Max Uses Limit</th>
                                        <th class="p-4">Expiration Date</th>
                                        <th class="p-4">Status</th>
                                        <th class="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="coupons-table-body" class="divide-y divide-gray-800/50">
                                    <!-- Loaded via JS -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 📢 TAB 7: ANNOUNCEMENTS / BROADCAST -->
                <div id="tab-broadcast" class="space-y-6 hidden">
                    <p class="text-sm text-gray-400">Send formatting-supported broadcast messages to all bot users in real-time.</p>

                    <div class="glass p-8 rounded-2xl max-w-xl space-y-4">
                        <div class="space-y-1">
                            <label class="text-xs font-bold uppercase text-gray-400">Broadcast Message Text</label>
                            <textarea id="broadcast-message" rows="6" class="w-full bg-gray-900/80 border border-gray-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-indigo-500 transition placeholder-gray-600" placeholder="Type your newsletter message here... Use standard Markdown if needed."></textarea>
                        </div>
                        <div class="flex justify-end pt-2">
                            <button onclick="sendBroadcast()" class="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-indigo-600/20 transition">
                                <i class="fa-solid fa-paper-plane mr-2"></i>Send Broadcast Announcement
                            </button>
                        </div>
                    </div>
                </div>

                <!-- ⚙️ TAB 8: SYSTEM SETTINGS -->
                <div id="tab-settings" class="space-y-6 hidden">
                    <p class="text-sm text-gray-400">Directly update configurations and crypto wallet addresses stored in the .env file.</p>
                    
                    <div class="glass p-8 rounded-2xl max-w-2xl space-y-6">
                        <div class="grid grid-cols-1 gap-4" id="settings-form-container">
                            <!-- Settings loaded dynamic via JS -->
                        </div>
                        <div class="pt-4 border-t border-gray-800 flex justify-end">
                            <button onclick="saveSettings()" class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20 transition">
                                <i class="fa-solid fa-save mr-1.5"></i>Save Configuration
                            </button>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <!-- ── MODAL: ADJUST BALANCE ── -->
    <div id="balanceModal" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden">
        <div class="glass max-w-md w-full p-6 rounded-2xl space-y-4 shadow-2xl">
            <div class="flex items-center justify-between">
                <h3 class="text-lg font-bold text-white">Adjust Wallet Balance</h3>
                <button onclick="closeBalanceModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-times text-lg"></i></button>
            </div>
            <div class="space-y-2 text-sm">
                <p class="text-gray-400">User Profile: <span id="modal-bal-username" class="font-semibold text-gray-200"></span></p>
                <p class="text-gray-400">Current Balance: <span id="modal-bal-current" class="font-bold text-emerald-400"></span></p>
            </div>
            <div class="space-y-1">
                <label class="text-xs text-gray-400 font-semibold uppercase tracking-wider">Balance Offset Amount ($)</label>
                <input type="number" id="balance-delta" step="0.01" class="w-full bg-gray-900/80 border border-gray-800 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-indigo-500 transition" placeholder="e.g. 10.00 or -5.00">
            </div>
            <div class="flex space-x-3 pt-2">
                <button onclick="closeBalanceModal()" class="w-1/2 py-3 rounded-xl bg-gray-800 hover:bg-gray-700 transition text-sm font-semibold">Cancel</button>
                <button onclick="submitBalanceChange()" class="w-1/2 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white transition text-sm font-semibold">Submit</button>
            </div>
            <input type="hidden" id="modal-bal-tg-id">
        </div>
    </div>

    <!-- ── MODAL: PRODUCT FORM ── -->
    <div id="productModal" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden">
        <div class="glass max-w-lg w-full p-6 rounded-2xl space-y-4 shadow-2xl overflow-y-auto max-h-[90vh] custom-scrollbar">
            <div class="flex items-center justify-between">
                <h3 class="text-lg font-bold text-white" id="prod-modal-title">Create Product</h3>
                <button onclick="closeProductModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-times text-lg"></i></button>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div class="col-span-2 space-y-1">
                    <label class="text-xs text-gray-400 font-semibold uppercase">Product Name</label>
                    <input type="text" id="prod-name" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500" placeholder="e.g. Gemini Advanced">
                </div>
                <div class="col-span-2 space-y-1">
                    <label class="text-xs text-gray-400 font-semibold uppercase">Description</label>
                    <textarea id="prod-desc" rows="3" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500" placeholder="Product details..."></textarea>
                </div>
                <div class="space-y-1">
                    <label class="text-xs text-gray-400 font-semibold uppercase">Price ($)</label>
                    <input type="number" id="prod-price" step="0.01" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500" placeholder="0.00">
                </div>
                <div class="space-y-1">
                    <label class="text-xs text-gray-400 font-semibold uppercase">Stock (-1 for Unlimited)</label>
                    <input type="number" id="prod-stock" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500" placeholder="-1">
                </div>
                <div class="space-y-1">
                    <label class="text-xs text-gray-400 font-semibold uppercase">Emoji Badge</label>
                    <input type="text" id="prod-emoji" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500" placeholder="e.g. ⚡">
                </div>
                <div class="space-y-1">
                    <label class="text-xs text-gray-400 font-semibold uppercase">Category</label>
                    <select id="prod-cat" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500">
                        <!-- Loaded dynamically -->
                    </select>
                </div>
            </div>
            <div class="flex space-x-3 pt-2">
                <button onclick="closeProductModal()" class="w-1/2 py-3 rounded-xl bg-gray-800 hover:bg-gray-700 transition text-sm font-semibold">Cancel</button>
                <button onclick="submitProductForm()" class="w-1/2 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white transition text-sm font-semibold">Save Product</button>
            </div>
            <input type="hidden" id="prod-id">
        </div>
    </div>

    <!-- ── MODAL: COUPON FORM ── -->
    <div id="couponModal" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden">
        <div class="glass max-w-md w-full p-6 rounded-2xl space-y-4 shadow-2xl">
            <div class="flex items-center justify-between">
                <h3 class="text-lg font-bold text-white">Create Coupon</h3>
                <button onclick="closeCouponModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-times text-lg"></i></button>
            </div>
            <div class="space-y-3">
                <div class="space-y-1">
                    <label class="text-xs text-gray-400 font-semibold uppercase">Promo Code</label>
                    <input type="text" id="coup-code" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500" placeholder="e.g. SAVE20">
                </div>
                <div class="grid grid-cols-2 gap-4">
                    <div class="space-y-1">
                        <label class="text-xs text-gray-400 font-semibold uppercase">Discount (%)</label>
                        <input type="number" id="coup-pct" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500" placeholder="0">
                    </div>
                    <div class="space-y-1">
                        <label class="text-xs text-gray-400 font-semibold uppercase">Flat Discount ($)</label>
                        <input type="number" step="0.01" id="coup-flat" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500" placeholder="0.00">
                    </div>
                </div>
                <div class="space-y-1">
                    <label class="text-xs text-gray-400 font-semibold uppercase">Max Uses (-1 for Unlimited)</label>
                    <input type="number" id="coup-max" class="w-full bg-gray-900/85 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500" placeholder="-1">
                </div>
            </div>
            <div class="flex space-x-3 pt-2">
                <button onclick="closeCouponModal()" class="w-1/2 py-3 rounded-xl bg-gray-800 hover:bg-gray-700 transition text-sm font-semibold">Cancel</button>
                <button onclick="submitCouponForm()" class="w-1/2 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white transition text-sm font-semibold">Create</button>
            </div>
        </div>
    </div>

    <!-- Scripts -->
    <script>
        let chartInstance = null;
        let activeTab = 'overview';

        // Tab Switching
        function switchTab(tabId) {
            const tabs = ['overview', 'products', 'users', 'orders', 'reviews', 'coupons', 'broadcast', 'settings'];
            tabs.forEach(t => {
                const el = document.getElementById(`tab-${t}`);
                const btn = document.getElementById(`tab-${t}-btn`);
                if (t === tabId) {
                    el.classList.remove('hidden');
                    btn.classList.add('sidebar-btn-active');
                } else {
                    el.classList.add('hidden');
                    btn.classList.remove('sidebar-btn-active');
                }
            });

            activeTab = tabId;
            const pageTitleMap = {
                'overview': 'Overview Dashboard',
                'products': 'Product Catalog',
                'users': 'Users Database',
                'orders': 'Orders List',
                'reviews': 'User Reviews',
                'coupons': 'Promo Coupons',
                'broadcast': 'Broadcast Announcement',
                'settings': 'System Settings'
            };
            document.getElementById('current-page-title').innerText = pageTitleMap[tabId];

            // Trigger specific tab fetches
            if (tabId === 'products') fetchProducts();
            else if (tabId === 'users') fetchUsers();
            else if (tabId === 'orders') fetchOrders();
            else if (tabId === 'reviews') fetchReviews();
            else if (tabId === 'coupons') fetchCoupons();
            else if (tabId === 'settings') fetchSettings();
        }

        // Stats Overview Loader
        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();

                document.getElementById('stat-users').innerText = data.total_users;
                document.getElementById('stat-revenue').innerText = `$${data.total_revenue.toFixed(2)}`;
                document.getElementById('stat-orders').innerText = data.total_orders;
                document.getElementById('stat-pending').innerText = data.pending_topups;

                updateChart(data.chart_data);
            } catch (err) {
                console.error(err);
            }
        }

        function updateChart(chartData) {
            const ctx = document.getElementById('chart-revenue').getContext('2d');
            if (chartInstance) {
                chartInstance.destroy();
            }

            chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartData.dates,
                    datasets: [
                        {
                            label: 'Earnings ($)',
                            data: chartData.values,
                            borderColor: '#8b5cf6',
                            backgroundColor: 'rgba(139, 92, 246, 0.04)',
                            fill: true,
                            tension: 0.4,
                            borderWidth: 3
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    scales: {
                        y: {
                            grid: { color: 'rgba(255, 255, 255, 0.02)' },
                            ticks: { color: '#6b7280', font: { family: 'Plus Jakarta Sans', size: 10 } }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#6b7280', font: { family: 'Plus Jakarta Sans', size: 10 } }
                        }
                    }
                }
            });
        }

        // Live Log activity stream
        async function fetchActivity() {
            try {
                const res = await fetch('/api/activity');
                const activities = await res.json();
                const container = document.getElementById('overview-activities');
                
                if (activities.length === 0) {
                    container.innerHTML = `<p class="text-xs text-gray-500 text-center py-10">No recent activity logs...</p>`;
                    return;
                }

                container.innerHTML = activities.map(act => {
                    const username = act.username ? ` (@${act.username})` : '';
                    return `
                        <div class="p-3 bg-gray-900/30 border border-gray-800/40 rounded-xl space-y-1 text-xs">
                            <div class="flex items-center justify-between">
                                <span class="font-bold text-gray-300">${act.first_name}${username}</span>
                                <span class="text-[10px] text-gray-500">${act.created_at.substring(11, 19)}</span>
                            </div>
                            <p class="text-gray-400 font-mono text-[11px]">${act.action.replace("Command: ", "").replace("Click: ", "")}</p>
                        </div>
                    `;
                }).join('');
            } catch (err) {
                console.error(err);
            }
        }

        // Product Manager Operations
        async function fetchProducts() {
            try {
                const res = await fetch('/api/products');
                const products = await res.json();
                const tbody = document.getElementById('products-table-body');
                
                tbody.innerHTML = products.map(p => {
                    const statusBadge = p.is_active
                        ? `<span class="px-2.5 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Active</span>`
                        : `<span class="px-2.5 py-0.5 rounded-full text-xs bg-gray-800 text-gray-500 border border-gray-700/50">Disabled</span>`;
                    
                    const stockText = p.stock === -1 ? '♾️ Unlimited' : p.stock;

                    return `
                        <tr class="hover:bg-gray-900/10 transition-colors">
                            <td class="p-4 font-medium flex items-center space-x-3">
                                <span class="text-xl">${p.emoji}</span>
                                <div>
                                    <p class="text-white font-semibold">${p.name}</p>
                                    <p class="text-xs text-gray-500 max-w-sm truncate">${p.description || ''}</p>
                                </div>
                            </td>
                            <td class="p-4 text-gray-400 font-medium">${p.category_name}</td>
                            <td class="p-4 font-bold text-emerald-400">$${p.price.toFixed(2)}</td>
                            <td class="p-4 font-mono text-gray-300">${stockText}</td>
                            <td class="p-4 text-gray-400 font-medium">${p.sold}</td>
                            <td class="p-4">${statusBadge}</td>
                            <td class="p-4 text-right space-x-2">
                                <button onclick="editProduct(${p.id}, '${p.name}', \`${p.description || ''}\`, ${p.price}, ${p.stock}, '${p.emoji}', ${p.category_id})" class="p-2 text-indigo-400 hover:bg-indigo-500/10 rounded-lg transition"><i class="fa-solid fa-edit"></i></button>
                                <button onclick="deleteProduct(${p.id})" class="p-2 text-rose-400 hover:bg-rose-500/10 rounded-lg transition"><i class="fa-solid fa-trash"></i></button>
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error(err);
            }
        }

        // Product Add/Edit Modal
        async function openProductModal() {
            document.getElementById('prod-id').value = '';
            document.getElementById('prod-name').value = '';
            document.getElementById('prod-desc').value = '';
            document.getElementById('prod-price').value = '';
            document.getElementById('prod-stock').value = '-1';
            document.getElementById('prod-emoji').value = '📦';
            document.getElementById('prod-modal-title').innerText = "Create Product";

            // Load categories dropdown
            const catRes = await fetch('/api/categories');
            const cats = await catRes.json();
            document.getElementById('prod-cat').innerHTML = cats.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

            document.getElementById('productModal').classList.remove('hidden');
        }

        async function editProduct(id, name, desc, price, stock, emoji, catId) {
            await openProductModal();
            document.getElementById('prod-id').value = id;
            document.getElementById('prod-name').value = name;
            document.getElementById('prod-desc').value = desc;
            document.getElementById('prod-price').value = price;
            document.getElementById('prod-stock').value = stock;
            document.getElementById('prod-emoji').value = emoji;
            document.getElementById('prod-cat').value = catId;
            document.getElementById('prod-modal-title').innerText = "Edit Product";
        }

        function closeProductModal() {
            document.getElementById('productModal').classList.add('hidden');
        }

        async function submitProductForm() {
            const id = document.getElementById('prod-id').value;
            const name = document.getElementById('prod-name').value;
            const description = document.getElementById('prod-desc').value;
            const price = parseFloat(document.getElementById('prod-price').value);
            const stock = parseInt(document.getElementById('prod-stock').value);
            const emoji = document.getElementById('prod-emoji').value;
            const category_id = parseInt(document.getElementById('prod-cat').value);

            if (!name || isNaN(price) || isNaN(stock)) {
                alert("Please fill in name, price, and stock levels.");
                return;
            }

            const url = id ? '/api/product/edit' : '/api/product/add';
            const body = id ? { id, name, description, price, stock, emoji, category_id } : { name, description, price, stock, emoji, category_id };

            await fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });

            closeProductModal();
            fetchProducts();
        }

        async function deleteProduct(id) {
            if (confirm("Delete this product permanently?")) {
                await fetch('/api/product/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id })
                });
                fetchProducts();
            }
        }

        // Users Tab
        async function fetchUsers() {
            try {
                const res = await fetch('/api/users');
                const users = await res.json();
                const tbody = document.getElementById('users-table-body');
                
                tbody.innerHTML = users.map(u => {
                    const bannedBadge = u.is_banned 
                        ? `<span class="px-2.5 py-0.5 rounded-full text-xs bg-rose-500/10 text-rose-400 border border-rose-500/20">Banned</span>`
                        : `<span class="px-2.5 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Active</span>`;
                    
                    const banIcon = u.is_banned ? 'fa-user-check' : 'fa-user-slash';
                    const banColor = u.is_banned ? 'text-emerald-400 hover:bg-emerald-500/10' : 'text-rose-400 hover:bg-rose-500/10';

                    return `
                        <tr class="hover:bg-gray-900/10 transition-colors">
                            <td class="p-4 font-semibold text-white">${u.first_name}</td>
                            <td class="p-4 text-gray-400">${u.username ? '@' + u.username : '-'}</td>
                            <td class="p-4 font-mono text-gray-500 text-xs">${u.telegram_id}</td>
                            <td class="p-4 font-bold text-emerald-400">$${u.balance.toFixed(2)}</td>
                            <td class="p-4 text-gray-300 font-medium">$${u.total_spent.toFixed(2)}</td>
                            <td class="p-4"><span class="px-2.5 py-0.5 rounded-full text-xs bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">${u.membership}</span></td>
                            <td class="p-4">${bannedBadge}</td>
                            <td class="p-4 text-right space-x-2">
                                <button onclick="openBalanceModal(${u.telegram_id}, '${u.first_name}', ${u.balance})" class="p-2 text-indigo-400 hover:bg-indigo-500/10 rounded-lg transition" title="Adjust Balance"><i class="fa-solid fa-wallet"></i></button>
                                <button onclick="toggleBan(${u.telegram_id}, ${u.is_banned})" class="p-2 ${banColor} rounded-lg transition" title="Ban/Unban"><i class="fa-solid ${banIcon}"></i></button>
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error(err);
            }
        }

        async function toggleBan(tgId, isBanned) {
            const action = isBanned ? 'unban' : 'ban';
            if (confirm("Toggle status of user ID " + tgId + " to " + action + "?")) {
                await fetch('/api/user/ban', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ telegram_id: tgId, action })
                });
                fetchUsers();
            }
        }

        // Balance Modal Actions
        function openBalanceModal(tgId, name, balance) {
            document.getElementById('modal-bal-tg-id').value = tgId;
            document.getElementById('modal-bal-username').innerText = name;
            document.getElementById('modal-bal-current').innerText = `$${balance.toFixed(2)}`;
            document.getElementById('balance-delta').value = '';
            document.getElementById('balanceModal').classList.remove('hidden');
        }

        function closeBalanceModal() {
            document.getElementById('balanceModal').classList.add('hidden');
        }

        async function submitBalanceChange() {
            const tgId = document.getElementById('modal-bal-tg-id').value;
            const delta = parseFloat(document.getElementById('balance-delta').value);
            if (isNaN(delta)) return;

            await fetch('/api/user/balance', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ telegram_id: tgId, delta })
            });

            closeBalanceModal();
            fetchUsers();
            fetchStats();
        }

        // Orders Tab
        async function fetchOrders() {
            try {
                const res = await fetch('/api/orders');
                const orders = await res.json();
                const tbody = document.getElementById('orders-table-body');
                
                tbody.innerHTML = orders.map(o => {
                    let badge = '';
                    let actionBtn = '';
                    if (o.status === 'paid') {
                        badge = `<span class="px-2.5 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Paid</span>`;
                        actionBtn = `<button onclick="orderAction(${o.id}, 'delivered')" class="px-3 py-1 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-bold transition flex items-center space-x-1"><i class="fa-solid fa-check text-[10px]"></i><span>Deliver</span></button>`;
                    } else if (o.status === 'delivered') {
                        badge = `<span class="px-2.5 py-0.5 rounded-full text-xs bg-blue-500/10 text-blue-400 border border-blue-500/20">Delivered</span>`;
                    } else if (o.status === 'pending') {
                        badge = `<span class="px-2.5 py-0.5 rounded-full text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">Pending</span>`;
                        actionBtn = `
                            <button onclick="orderAction(${o.id}, 'paid')" class="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition">Approve</button>
                            <button onclick="orderAction(${o.id}, 'cancelled')" class="px-2.5 py-1 bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold rounded-lg transition">Cancel</button>
                        `;
                    } else {
                        badge = `<span class="px-2.5 py-0.5 rounded-full text-xs bg-gray-800 text-gray-500 border border-gray-700/50">Cancelled</span>`;
                    }

                    return `
                        <tr class="hover:bg-gray-900/10 transition-colors">
                            <td class="p-4 font-mono text-gray-500 text-xs">#${o.id}</td>
                            <td class="p-4 font-semibold text-white">${o.first_name} <span class="text-xs text-gray-500 font-normal">(${o.user_id})</span></td>
                            <td class="p-4 text-gray-300 font-medium">${o.product_name}</td>
                            <td class="p-4 font-mono text-gray-400">${o.quantity}</td>
                            <td class="p-4 font-bold text-emerald-400">$${o.total_price.toFixed(2)}</td>
                            <td class="p-4 font-mono text-xs text-gray-400 uppercase">${o.payment_method}</td>
                            <td class="p-4">${badge}</td>
                            <td class="p-4 text-gray-500 text-xs">${o.created_at.substring(0, 16)}</td>
                            <td class="p-4 text-right space-x-1.5">${actionBtn}</td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error(err);
            }
        }

        async function orderAction(orderId, action) {
            if (confirm("Set order #" + orderId + " to " + action + "?")) {
                await fetch('/api/order/action', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ order_id: orderId, action })
                });
                fetchOrders();
                fetchStats();
            }
        }

        // Reviews Tab
        async function fetchReviews() {
            try {
                const res = await fetch('/api/reviews');
                const reviews = await res.json();
                const tbody = document.getElementById('reviews-table-body');

                tbody.innerHTML = reviews.map(r => {
                    const stars = '⭐'.repeat(r.rating);
                    const username = r.username ? ` (@${r.username})` : '';
                    return `
                        <tr class="hover:bg-gray-900/10 transition-colors">
                            <td class="p-4 font-semibold text-white">${r.first_name}${username} <span class="text-xs text-gray-500 font-normal">(${r.user_id})</span></td>
                            <td class="p-4 text-gray-300 font-medium">${r.product_name}</td>
                            <td class="p-4 font-mono text-amber-400">${stars}</td>
                            <td class="p-4 text-gray-200 italic font-medium">"${r.comment || 'No comment skipped'}"</td>
                            <td class="p-4 text-xs text-gray-500">${r.created_at.substring(0, 16)}</td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error(err);
            }
        }

        // Coupons Tab
        async function fetchCoupons() {
            try {
                const res = await fetch('/api/coupons');
                const coupons = await res.json();
                const tbody = document.getElementById('coupons-table-body');
                
                tbody.innerHTML = coupons.map(c => {
                    const statusBadge = c.is_active
                        ? `<span class="px-2.5 py-0.5 rounded-full text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Active</span>`
                        : `<span class="px-2.5 py-0.5 rounded-full text-xs bg-gray-800 text-gray-500 border border-gray-700/50">Expired</span>`;
                    
                    const pctText = c.discount_percent > 0 ? `${c.discount_percent}%` : '-';
                    const flatText = c.flat_discount > 0 ? `$${c.flat_discount.toFixed(2)}` : '-';
                    const limitText = c.max_uses === -1 ? '♾️' : c.max_uses;

                    return `
                        <tr class="hover:bg-gray-900/10 transition-colors">
                            <td class="p-4 font-mono font-bold text-white">${c.code}</td>
                            <td class="p-4 font-mono text-gray-300">${pctText}</td>
                            <td class="p-4 font-mono text-emerald-400">${flatText}</td>
                            <td class="p-4 font-mono text-gray-400">${c.uses_count}</td>
                            <td class="p-4 font-mono text-gray-400">${limitText}</td>
                            <td class="p-4 text-xs text-gray-500">${c.expires_at || 'Never'}</td>
                            <td class="p-4">${statusBadge}</td>
                            <td class="p-4 text-right">
                                <button onclick="deleteCoupon(${c.id})" class="p-2 text-rose-400 hover:bg-rose-500/10 rounded-lg transition" title="Delete"><i class="fa-solid fa-trash"></i></button>
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error(err);
            }
        }

        function openCouponModal() {
            document.getElementById('coup-code').value = '';
            document.getElementById('coup-pct').value = '';
            document.getElementById('coup-flat').value = '';
            document.getElementById('coup-max').value = '-1';
            document.getElementById('couponModal').classList.remove('hidden');
        }

        function closeCouponModal() {
            document.getElementById('couponModal').classList.add('hidden');
        }

        async function submitCouponForm() {
            const code = document.getElementById('coup-code').value.trim().toUpperCase();
            const pct = parseInt(document.getElementById('coup-pct').value) || 0;
            const flat = parseFloat(document.getElementById('coup-flat').value) || 0.0;
            const max_uses = parseInt(document.getElementById('coup-max').value) || -1;

            if (!code || (pct === 0 && flat === 0)) {
                alert("Please provide code and discount value.");
                return;
            }

            await fetch('/api/coupon/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ code, discount_percent: pct, flat_discount: flat, max_uses })
            });

            closeCouponModal();
            fetchCoupons();
        }

        async function deleteCoupon(id) {
            if (confirm("Delete this coupon permanently?")) {
                await fetch('/api/coupon/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ id })
                });
                fetchCoupons();
            }
        }

        // Broadcast Function
        async function sendBroadcast() {
            const text = document.getElementById('broadcast-message').value.trim();
            if (!text) {
                alert("Please enter message text.");
                return;
            }
            if (confirm("Send this broadcast message to all users?")) {
                const res = await fetch('/api/broadcast', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ text })
                });
                const resData = await res.json();
                if (resData.status === 'success') {
                    alert("Broadcast sent successfully to " + resData.sent + " users!");
                    document.getElementById('broadcast-message').value = '';
                } else {
                    alert("Broadcast failed.");
                }
            }
        }

        // Settings Tab
        async function fetchSettings() {
            try {
                const res = await fetch('/api/settings');
                const settings = await res.json();
                const container = document.getElementById('settings-form-container');

                container.innerHTML = Object.keys(settings).map(key => {
                    let desc = '';
                    if (key === 'CRYPTOMUS_MERCHANT_UUID') desc = 'Cryptomus Merchant ID for receiving payments';
                    else if (key === 'CRYPTOMUS_API_KEY') desc = 'Cryptomus Payment API Key';
                    else if (key === 'USDT_TRC20_ADDRESS') desc = 'Wallet Address for manual USDT TRC20 payments';
                    else if (key === 'USDT_BEP20_ADDRESS') desc = 'Wallet Address for manual USDT BEP20 payments';
                    else if (key === 'BINANCE_PAY_ID') desc = 'Binance Pay merchant / ID for payments';
                    else if (key === 'REFERRAL_REWARD') desc = 'Balance reward given to referrers when their friend buys';

                    return `
                        <div class="space-y-1">
                            <label class="text-xs font-bold uppercase tracking-wider text-gray-400">${key.replace(/_/g, ' ')}</label>
                            <input type="text" id="setting-${key}" value="${settings[key]}" class="w-full bg-gray-900/80 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-white focus:outline-none focus:border-indigo-500 transition">
                            <p class="text-[11px] text-gray-500">${desc}</p>
                        </div>
                    `;
                }).join('');
            } catch (err) {
                console.error(err);
            }
        }

        async function saveSettings() {
            const inputs = document.querySelectorAll('[id^="setting-"]');
            const data = {};
            inputs.forEach(input => {
                const key = input.id.replace('setting-', '');
                data[key] = input.value.trim();
            });

            const res = await fetch('/api/settings/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });

            const resData = await res.json();
            if (resData.status === 'success') {
                alert("System config updated successfully!");
                fetchSettings();
            } else {
                alert("Failed to update config");
            }
        }

        // Initialize polling loop
        window.addEventListener('load', () => {
            fetchStats();
            fetchActivity();

            // Refresh stats and activity every 8 seconds
            setInterval(() => {
                if (activeTab === 'overview') {
                    fetchStats();
                    fetchActivity();
                }
            }, 8000);
        });
    </script>
</body>
</html>
"""


# ── Web endpoints ────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/stats")
def api_stats():
    conn = get_db_connection()
    try:
        # Total users
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        # Total revenue
        total_revenue = conn.execute(
            "SELECT SUM(total_price) FROM orders WHERE status='paid' OR status='delivered'"
        ).fetchone()[0] or 0.0

        # Total orders
        total_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status='paid' OR status='delivered'"
        ).fetchone()[0]

        # Pending topups
        pending_topups = conn.execute(
            "SELECT COUNT(*) FROM topup_requests WHERE status='pending'"
        ).fetchone()[0]

        # Chart data: last 7 days of sales
        chart_rows = conn.execute(
            """SELECT date(created_at) as sales_date, SUM(total_price) as revenue
               FROM orders
               WHERE status='paid' OR status='delivered'
               GROUP BY sales_date
               ORDER BY sales_date DESC
               LIMIT 7"""
        ).fetchall()

        dates = []
        values = []
        for r in reversed(chart_rows):
            dates.append(r["sales_date"])
            values.append(r["revenue"])

        if not dates:
            dates = ["No Sales"]
            values = [0.0]

        return jsonify({
            "total_users": total_users,
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "pending_topups": pending_topups,
            "chart_data": {
                "dates": dates,
                "values": values
            }
        })
    finally:
        conn.close()


@app.route("/api/users")
def api_users():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM users ORDER BY total_spent DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/orders")
def api_orders():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT o.*, p.name as product_name, u.first_name
               FROM orders o
               JOIN products p ON o.product_id = p.id
               JOIN users u ON o.user_id = u.telegram_id
               ORDER BY o.created_at DESC"""
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/activity")
def api_activity():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM user_activity ORDER BY created_at DESC LIMIT 30").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/products")
def api_products():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT p.*, c.name as category_name
               FROM products p
               LEFT JOIN categories c ON p.category_id = c.id
               ORDER BY p.id DESC"""
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/categories")
def api_categories():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/reviews")
def api_reviews():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT r.*, u.first_name, u.username, p.name as product_name
               FROM reviews r
               JOIN users u ON r.user_id = u.telegram_id
               JOIN products p ON r.product_id = p.id
               ORDER BY r.created_at DESC"""
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/coupons")
def api_coupons():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


# Product Actions
@app.route("/api/product/add", methods=["POST"])
def product_add():
    data = request.json
    name = data["name"]
    description = data.get("description", "")
    price = float(data["price"])
    stock = int(data["stock"])
    emoji = data.get("emoji", "📦")
    category_id = int(data["category_id"])

    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO products (name, description, price, stock, emoji, category_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, description, price, stock, emoji, category_id)
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error adding product: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/product/edit", methods=["POST"])
def product_edit():
    data = request.json
    p_id = int(data["id"])
    name = data["name"]
    description = data.get("description", "")
    price = float(data["price"])
    stock = int(data["stock"])
    emoji = data.get("emoji", "📦")
    category_id = int(data["category_id"])

    conn = get_db_connection()
    try:
        conn.execute(
            """UPDATE products
               SET name=?, description=?, price=?, stock=?, emoji=?, category_id=?
               WHERE id=?""",
            (name, description, price, stock, emoji, category_id, p_id)
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error editing product: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/product/delete", methods=["POST"])
def product_delete():
    data = request.json
    p_id = int(data["id"])

    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM products WHERE id=?", (p_id,))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# Coupon Actions
@app.route("/api/coupon/add", methods=["POST"])
def coupon_add():
    data = request.json
    code = data["code"].strip().upper()
    discount_percent = int(data.get("discount_percent", 0))
    flat_discount = float(data.get("flat_discount", 0.0))
    max_uses = int(data.get("max_uses", -1))

    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO coupons (code, discount_percent, flat_discount, max_uses)
               VALUES (?, ?, ?, ?)""",
            (code, discount_percent, flat_discount, max_uses)
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error adding coupon: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/coupon/delete", methods=["POST"])
def coupon_delete():
    data = request.json
    c_id = int(data["id"])

    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM coupons WHERE id=?", (c_id,))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error deleting coupon: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# User Balance and status
@app.route("/api/user/balance", methods=["POST"])
def adjust_balance():
    data = request.json
    tg_id = int(data["telegram_id"])
    delta = float(data["delta"])

    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET balance = balance + ? WHERE telegram_id=?", (delta, tg_id))
        conn.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?,?,?,?)",
            (tg_id, delta, "adjustment", f"Admin Web Dashboard adjustment of ${delta:.2f}")
        )
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error adjusting user balance: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/user/ban", methods=["POST"])
def toggle_ban():
    data = request.json
    tg_id = int(data["telegram_id"])
    action = data["action"]
    is_banned = 1 if action == "ban" else 0

    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET is_banned = ? WHERE telegram_id=?", (is_banned, tg_id))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error banning/unbanning user: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# Order operations
@app.route("/api/order/action", methods=["POST"])
def order_action():
    data = request.json
    order_id = int(data["order_id"])
    action = data["action"]

    conn = get_db_connection()
    try:
        conn.execute("UPDATE orders SET status = ?, updated_at = datetime('now') WHERE id = ?", (action, order_id))
        conn.commit()
        
        # Trigger delivered notification rating flow if set to 'delivered'
        if action == "delivered":
            cur = conn.execute("SELECT user_id, product_id, delivery_info FROM orders WHERE id=?", (order_id,))
            o = cur.fetchone()
            if o:
                token = get_bot_token()
                if token:
                    msg = f"📦 *Order #{order_id} Delivered!*\n\nYour product has been delivered! 🎉"
                    if o["delivery_info"]:
                        msg += f"\n\n📬 *Delivery Info:*\n`{o['delivery_info']}`"
                    
                    msg += "\n\n⭐ *Please rate your purchase experience:*\n(Select a rating callback below)"
                    
                    # Construct Inline Keyboard rating structure
                    markup = {
                        "inline_keyboard": [[
                            {"text": "⭐", "callback_data": f"rate_1_{order_id}"},
                            {"text": "⭐⭐", "callback_data": f"rate_2_{order_id}"},
                            {"text": "⭐⭐⭐", "callback_data": f"rate_3_{order_id}"},
                            {"text": "⭐⭐⭐⭐", "callback_data": f"rate_4_{order_id}"},
                            {"text": "⭐⭐⭐⭐⭐", "callback_data": f"rate_5_{order_id}"}
                        ]]
                    }
                    send_telegram_msg(token, o["user_id"], msg + f"\n\n_To submit, click below:_")
                    # Make another call with keyboard markup
                    url = f"https://api.telegram.org/bot{token}/sendMessage"
                    post_data = urllib.parse.urlencode({
                        "chat_id": o["user_id"],
                        "text": "⭐ *Submit Rating:*",
                        "parse_mode": "Markdown",
                        "reply_markup": json.dumps(markup)
                    }).encode("utf-8")
                    try:
                        req = urllib.request.Request(url, data=post_data)
                        urllib.request.urlopen(req, timeout=5)
                    except Exception as ex:
                        logger.error(f"Error sending rating keyb: {ex}")

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error updating order state: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


# Broadcast endpoint
@app.route("/api/broadcast", methods=["POST"])
def api_broadcast():
    data = request.json
    text = data["text"]
    token = get_bot_token()
    if not token:
        return jsonify({"status": "error", "message": "Bot token not found"}), 500

    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT telegram_id FROM users WHERE is_banned=0").fetchall()
        users = [r["telegram_id"] for r in rows]
    finally:
        conn.close()

    sent = 0
    for uid in users:
        res = send_telegram_msg(token, uid, text)
        if res:
            sent += 1
    return jsonify({"status": "success", "sent": sent})


# Settings endpoint
@app.route("/api/settings")
def api_settings():
    # Parse .env keys
    settings = {
        "CRYPTOMUS_MERCHANT_UUID": "",
        "CRYPTOMUS_API_KEY": "",
        "USDT_TRC20_ADDRESS": "",
        "USDT_BEP20_ADDRESS": "",
        "BINANCE_PAY_ID": "",
        "REFERRAL_REWARD": "1.00",
    }
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    parts = line.strip().split("=", 1)
                    key = parts[0].strip()
                    val = parts[1].strip()
                    if key in settings:
                        settings[key] = val
    return jsonify(settings)


@app.route("/api/settings/save", methods=["POST"])
def api_settings_save():
    data = request.json
    try:
        for key, val in data.items():
            update_env_var(key, val)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    logger.info("⚡ Starting Advanced Dashboard Server on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
