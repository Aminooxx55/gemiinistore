# -*- coding: utf-8 -*-
"""Ultimate Advanced Web Admin Control Panel with Gemini AI Insights & Product Remise Manager."""
import os
import csv
import io
import sqlite3
import logging
import urllib.request
import urllib.parse
import json
from flask import Flask, jsonify, request, render_template_string, Response, session, redirect, url_for

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_dashboard")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-admin-key-123")

ADMIN_USERNAME = os.environ.get("ADMIN_USER", "amoun")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASS", "amoun")

DB_PATH = "shop.db"
ENV_PATH = ".env"


def ensure_db_schema():
    """Ensure required columns exist in shop.db."""
    if not os.path.exists(DB_PATH):
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        cols = [r[1] for r in conn.execute("PRAGMA table_info(products)").fetchall()]
        if 'tier_prices' not in cols:
            conn.execute("ALTER TABLE products ADD COLUMN tier_prices TEXT")
            conn.commit()
            logger.info("Migrated products table: added tier_prices column.")
        if 'image_url' not in cols:
            conn.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
            conn.commit()
            logger.info("Migrated products table: added image_url column.")
        conn.close()
    except Exception as e:
        logger.error(f"Schema migration error: {e}")

ensure_db_schema()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_env_var(key: str, default: str = "") -> str:
    """Read a specific key from .env file."""
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    parts = line.strip().split("=", 1)
                    if parts[0].strip() == key:
                        return parts[1].strip()
    return default


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


# Ensure GEMINI_API_KEY is stored if missing
if not get_env_var("GEMINI_API_KEY"):
    pass


def send_telegram_msg(token: str, chat_id: int, text: str):
    """Send a telegram message using urllib."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read()
    except Exception as e:
        logger.error(f"Error sending msg to {chat_id}: {e}")
        return None


@app.before_request
def check_auth():
    if request.endpoint in ('login', 'logout', 'static'):
        return
    if not session.get('logged_in'):
        if request.path.startswith('/api/'):
            return jsonify({"status": "error", "message": "Unauthorized"}), 401
        return redirect(url_for('login', next=request.url))


LOGIN_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GeminiStore Control Panel — Login</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style> body { font-family: 'Plus Jakarta Sans', sans-serif; } </style>
</head>
<body class="bg-gray-950 text-white min-h-screen flex items-center justify-center font-sans antialiased" style="background-color: #080c14; background-image: radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.15) 0px, transparent 40%), radial-gradient(at 100% 100%, rgba(236, 72, 153, 0.15) 0px, transparent 40%);">
    <div class="p-8 rounded-3xl shadow-2xl w-96 border border-gray-800/80" style="background: rgba(13, 20, 35, 0.75); backdrop-filter: blur(20px);">
        <div class="flex justify-center mb-6">
            <div class="w-14 h-14 rounded-2xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
                <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
            </div>
        </div>
        <h2 class="text-2xl font-extrabold mb-1 text-center text-white tracking-tight">GeminiStore Control Panel</h2>
        <p class="text-xs text-gray-400 text-center mb-6">Sign in with administrator credentials</p>
        {% if error %}<p class="text-rose-400 text-xs mb-4 text-center font-semibold bg-rose-500/10 py-2.5 px-3 rounded-xl border border-rose-500/20">{{ error }}</p>{% endif %}
        <form method="POST" action="/login" class="space-y-4">
            <div>
                <label class="block text-[11px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Username</label>
                <input type="text" name="username" required class="w-full bg-gray-900/80 border border-gray-800 rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 transition text-sm text-white placeholder-gray-600" placeholder="amoun">
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 mb-1.5 uppercase tracking-wider">Password</label>
                <input type="password" name="password" required class="w-full bg-gray-900/80 border border-gray-800 rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 transition text-sm text-white placeholder-gray-600" placeholder="••••••••">
            </div>
            <button type="submit" class="w-full bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 hover:from-indigo-500 hover:to-pink-500 py-3 rounded-xl text-white font-bold text-sm transition shadow-lg shadow-indigo-500/25 mt-2 tracking-wide">Access Dashboard</button>
        </form>
    </div>
</body>
</html>
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("username") == ADMIN_USERNAME and request.form.get("password") == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = "Invalid Credentials"
    return render_template_string(LOGIN_TEMPLATE, error=error)

@app.route("/logout")
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))


HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GeminiStore — Control Panel & AI Insights</title>
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
            background: rgba(13, 20, 35, 0.75);
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
        /* ── Mobile sidebar slide-in ── */
        @media (max-width: 1023px) {
            #sidebar {
                transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            }
            #sidebar.open {
                transform: translateX(0) !important;
            }
        }
        textarea#prod-desc {
            resize: vertical;
            min-height: 110px;
        }
    </style>
</head>
<body class="text-gray-200 min-h-screen font-sans antialiased custom-scrollbar">

    <div class="flex min-h-screen">

        <!-- Mobile sidebar backdrop -->
        <div id="sidebar-backdrop" onclick="closeSidebar()" class="hidden fixed inset-0 bg-black/60 backdrop-blur-sm z-30 lg:hidden"></div>

        <!-- Sidebar Navigation -->
        <aside id="sidebar" class="w-64 glass border-r border-gray-800 flex flex-col justify-between shrink-0 fixed lg:sticky top-0 h-screen z-40 -translate-x-full lg:translate-x-0">
            <div class="space-y-6">
                <div class="px-6 py-5 border-b border-gray-800 flex items-center space-x-3">
                    <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
                        <i class="fa-solid fa-brain text-white text-lg"></i>
                    </div>
                    <div>
                        <h1 class="text-md font-bold tracking-tight text-white leading-tight">GeminiStore v3.0</h1>
                        <span class="text-[10px] text-indigo-400 font-semibold uppercase tracking-wider">AI Powered Control</span>
                    </div>
                </div>

                <nav class="space-y-1 px-3">
                    <button onclick="switchTab('overview')" id="tab-overview-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition sidebar-btn-active">
                        <i class="fa-solid fa-chart-pie w-5"></i><span>Overview</span>
                    </button>
                    <button onclick="switchTab('ai')" id="tab-ai-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-semibold text-purple-400 hover:text-white hover:bg-purple-500/10 transition border border-purple-500/20">
                        <i class="fa-solid fa-wand-magic-sparkles w-5 text-purple-400"></i><span>Gemini AI Advisor</span>
                    </button>
                    <button onclick="switchTab('products')" id="tab-products-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-cubes w-5"></i><span>Products & Remise</span>
                    </button>
                    <button onclick="switchTab('categories')" id="tab-categories-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-folder-tree w-5"></i><span>Categories</span>
                    </button>
                    <button onclick="switchTab('inventory')" id="tab-inventory-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-layer-group w-5"></i><span>Stock & Inventory</span>
                    </button>
                    <button onclick="switchTab('users')" id="tab-users-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-users w-5"></i><span>Users Database</span>
                    </button>
                    <button onclick="switchTab('orders')" id="tab-orders-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-receipt w-5"></i><span>Orders List</span>
                    </button>
                    <button onclick="switchTab('tickets')" id="tab-tickets-btn" class="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 transition">
                        <i class="fa-solid fa-headset w-5"></i><span>Support Tickets</span>
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

            <div class="p-4 border-t border-gray-800 space-y-3">
                <a href="/logout" class="w-full flex items-center space-x-3 px-4 py-2.5 rounded-xl bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border border-rose-500/20 text-sm font-semibold transition">
                    <i class="fa-solid fa-sign-out-alt w-5"></i><span>Logout</span>
                </a>
                <div class="flex items-center justify-between text-xs">
                    <span class="text-gray-400 font-medium">Gateway Service:</span>
                    <span class="text-green-400 flex items-center"><span class="w-2 h-2 rounded-full bg-green-500 mr-2 animate-ping"></span>Online</span>
                </div>
                <div class="flex items-center justify-between text-xs">
                    <span class="text-gray-400 font-medium">AI Engine:</span>
                    <span class="text-purple-400 font-semibold">Gemini 1.5 Active</span>
                </div>
            </div>
        </aside>

        <!-- Main Content Area -->
        <div class="flex-1 flex flex-col min-w-0 font-sans">

            <!-- Global Header -->
            <header class="h-16 glass border-b border-gray-800 px-4 md:px-8 flex items-center justify-between sticky top-0 z-30">
                <div class="flex items-center space-x-3">
                    <!-- Hamburger — only shown on mobile/tablet -->
                    <button onclick="openSidebar()" class="lg:hidden p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition" aria-label="Open menu">
                        <i class="fa-solid fa-bars text-lg"></i>
                    </button>
                    <h2 class="text-sm md:text-md font-bold text-gray-100 truncate max-w-[160px] md:max-w-none" id="current-page-title">Overview Dashboard</h2>
                </div>
                <div class="flex items-center space-x-2 md:space-x-4">
                    <button onclick="fetchStats(); fetchActivity();" class="p-2 md:px-3.5 md:py-1.5 rounded-lg bg-gray-900 border border-gray-800 hover:bg-gray-800 text-xs font-semibold text-gray-300 transition flex items-center space-x-1.5">
                        <i class="fa-solid fa-arrows-rotate"></i><span class="hidden md:inline">Refresh</span>
                    </button>
                    <span class="hidden md:flex text-xs text-gray-400 font-medium items-center"><i class="fa-solid fa-user-shield mr-1.5 text-indigo-500"></i>Root Admin</span>
                </div>
            </header>

            <!-- Scrollable Content Page -->
            <div class="flex-1 p-4 md:p-8 space-y-4 md:space-y-6 overflow-y-auto max-w-[1400px]">

                <!-- 🌐 TAB 1: OVERVIEW -->
                <div id="tab-overview" class="space-y-6">
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
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
                                <p class="text-xs font-semibold uppercase text-gray-500 tracking-wider">Today's Sales</p>
                                <p class="text-3xl font-bold tracking-tight text-white" id="stat-today-sales">$0.00</p>
                            </div>
                            <div class="w-12 h-12 rounded-xl bg-blue-500/10 text-blue-400 flex items-center justify-center border border-blue-500/20">
                                <i class="fa-solid fa-calendar-day text-lg"></i>
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
                                <p class="text-xs font-semibold uppercase text-gray-500 tracking-wider">Total Stock Units</p>
                                <p class="text-3xl font-bold tracking-tight text-indigo-400" id="stat-total-stock">0</p>
                            </div>
                            <div class="w-12 h-12 rounded-xl bg-indigo-500/10 text-indigo-400 flex items-center justify-center border border-indigo-500/20">
                                <i class="fa-solid fa-layer-group text-lg"></i>
                            </div>
                        </div>
                        <div class="glass p-6 rounded-2xl flex items-center justify-between">
                            <div class="space-y-1">
                                <p class="text-xs font-semibold uppercase text-gray-500 tracking-wider">Low Stock Alerts</p>
                                <p class="text-3xl font-bold tracking-tight text-amber-400" id="stat-low-stock">0</p>
                            </div>
                            <div class="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center border border-amber-500/20">
                                <i class="fa-solid fa-triangle-exclamation text-lg"></i>
                            </div>
                        </div>
                    </div>

                    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                        <div class="glass p-6 rounded-2xl lg:col-span-2 space-y-4">
                            <h3 class="text-sm font-bold uppercase tracking-wider text-gray-400">Income Overview (Past 7 Days)</h3>
                            <div class="h-72">
                                <canvas id="chart-revenue"></canvas>
                            </div>
                        </div>
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

                <!-- 🤖 TAB 2: GEMINI AI ADVISOR -->
                <div id="tab-ai" class="space-y-6 hidden">
                    <div class="glass p-6 rounded-2xl space-y-6 border border-purple-500/20" style="background: linear-gradient(135deg, rgba(13, 20, 35, 0.8) 0%, rgba(88, 28, 135, 0.15) 100%);">
                        <div class="flex flex-wrap justify-between items-center gap-4 border-b border-gray-800/80 pb-4">
                            <div class="flex items-center space-x-3">
                                <div class="w-12 h-12 rounded-xl bg-purple-500/20 text-purple-400 flex items-center justify-center border border-purple-500/30">
                                    <i class="fa-solid fa-wand-magic-sparkles text-xl"></i>
                                </div>
                                <div>
                                    <h3 class="text-lg font-extrabold text-white tracking-tight">Gemini AI Store Analytics & Advisor</h3>
                                    <p class="text-xs text-purple-300">Powered by Google Gemini 1.5 Flash • Real-Time Store Diagnosis & Growth Recommendations</p>
                                </div>
                            </div>
                            <button onclick="runAiAnalysis()" id="ai-generate-btn" class="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-purple-600/30 transition flex items-center space-x-2">
                                <i class="fa-solid fa-bolt"></i><span>Generate AI Report Now</span>
                            </button>
                        </div>

                        <div id="ai-report-container" class="space-y-4">
                            <div class="p-8 text-center space-y-3 text-gray-400">
                                <i class="fa-solid fa-brain text-4xl text-purple-400/50 mb-2"></i>
                                <p class="text-sm font-semibold text-gray-300">Click "Generate AI Report Now" to analyze store revenue, sales velocity, customer tiers, and pricing strategies!</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- 🛍️ TAB 3: PRODUCTS & REMISE (BULK TIER PRICES) -->
                <div id="tab-products" class="space-y-6 hidden">
                    <div class="flex justify-between items-center">
                        <p class="text-sm text-gray-400">View, edit, or create products listed in the shop catalog and set Remise (tiered bulk discounts).</p>
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
                                        <th class="p-4">Base Price</th>
                                        <th class="p-4">Remise (Bulk Tiers)</th>
                                        <th class="p-4">Stock</th>
                                        <th class="p-4">Status</th>
                                        <th class="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="products-table-body" class="divide-y divide-gray-800/50">
                                    <tr><td colspan="7" class="p-8 text-center text-gray-500">Loading catalog...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 📁 TAB 4: CATEGORIES -->
                <div id="tab-categories" class="space-y-6 hidden">
                    <div class="flex justify-between items-center">
                        <p class="text-sm text-gray-400">Manage categories used to organize store products.</p>
                        <button onclick="openCategoryModal()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20 transition flex items-center space-x-1.5">
                            <i class="fa-solid fa-plus text-xs"></i><span>Create Category</span>
                        </button>
                    </div>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">ID</th>
                                        <th class="p-4">Emoji</th>
                                        <th class="p-4">Category Name</th>
                                        <th class="p-4">Status</th>
                                        <th class="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="categories-table-body" class="divide-y divide-gray-800/50">
                                    <tr><td colspan="5" class="p-8 text-center text-gray-500">Loading categories...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 🗄️ TAB 5: INVENTORY -->
                <div id="tab-inventory" class="space-y-6 hidden">
                    <div class="flex flex-wrap justify-between items-center gap-4">
                        <div class="flex items-center space-x-3">
                            <select id="inventory-product-filter" onchange="fetchInventory()" class="bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none">
                                <option value="">All Products</option>
                            </select>
                            <button onclick="purgeSoldStock()" class="px-3 py-2 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 border border-rose-500/20 rounded-xl text-xs font-bold transition flex items-center space-x-1.5">
                                <i class="fa-solid fa-trash-can"></i><span>Purge Sold Stock</span>
                            </button>
                        </div>
                        <div class="flex space-x-3">
                            <button onclick="openAddStockModal()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20 transition flex items-center space-x-1.5">
                                <i class="fa-solid fa-plus"></i><span>Add Single Item</span>
                            </button>
                            <button onclick="openUploadStockModal()" class="px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-purple-600/20 transition flex items-center space-x-1.5">
                                <i class="fa-solid fa-file-arrow-up"></i><span>Bulk Upload .TXT</span>
                            </button>
                        </div>
                    </div>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">Stock ID</th>
                                        <th class="p-4">Product Name</th>
                                        <th class="p-4">Digital Data / Content</th>
                                        <th class="p-4">Status</th>
                                        <th class="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="inventory-table-body" class="divide-y divide-gray-800/50">
                                    <tr><td colspan="5" class="p-8 text-center text-gray-500">Loading stock inventory...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 👥 TAB 6: USERS DATABASE -->
                <div id="tab-users" class="space-y-6 hidden">
                    <div class="flex justify-between items-center">
                        <p class="text-sm text-gray-400">Search and manage registered store customers and balances.</p>
                        <a href="/api/export/users" class="px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 rounded-xl text-xs font-bold text-gray-300 transition flex items-center space-x-1.5">
                            <i class="fa-solid fa-download"></i><span>Export Users CSV</span>
                        </a>
                    </div>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">User</th>
                                        <th class="p-4">Telegram ID</th>
                                        <th class="p-4">Balance</th>
                                        <th class="p-4">Total Spent</th>
                                        <th class="p-4">Tier</th>
                                        <th class="p-4">Status</th>
                                        <th class="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="users-table-body" class="divide-y divide-gray-800/50">
                                    <tr><td colspan="7" class="p-8 text-center text-gray-500">Loading users...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 🧾 TAB 7: ORDERS LIST -->
                <div id="tab-orders" class="space-y-6 hidden">
                    <div class="flex justify-between items-center">
                        <p class="text-sm text-gray-400">Monitor purchases, delivery statuses, and manual fulfillment.</p>
                        <a href="/api/export/orders" class="px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 rounded-xl text-xs font-bold text-gray-300 transition flex items-center space-x-1.5">
                            <i class="fa-solid fa-download"></i><span>Export Orders CSV</span>
                        </a>
                    </div>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">Order ID</th>
                                        <th class="p-4">Customer</th>
                                        <th class="p-4">Product</th>
                                        <th class="p-4">Qty</th>
                                        <th class="p-4">Total Paid</th>
                                        <th class="p-4">Method</th>
                                        <th class="p-4">Status</th>
                                        <th class="p-4 text-right">Update Status</th>
                                    </tr>
                                </thead>
                                <tbody id="orders-table-body" class="divide-y divide-gray-800/50">
                                    <tr><td colspan="8" class="p-8 text-center text-gray-500">Loading orders...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 🎫 TAB 8: SUPPORT TICKETS -->
                <div id="tab-tickets" class="space-y-6 hidden">
                    <div class="flex justify-between items-center">
                        <p class="text-sm text-gray-400">View customer support requests and reply directly to users via Telegram DM.</p>
                        <button onclick="fetchTickets()" class="px-3.5 py-1.5 rounded-lg bg-gray-900 border border-gray-800 hover:bg-gray-800 text-xs font-semibold text-gray-300 transition">
                            <i class="fa-solid fa-arrows-rotate mr-1"></i>Refresh Tickets
                        </button>
                    </div>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">Ticket ID</th>
                                        <th class="p-4">User</th>
                                        <th class="p-4">Message</th>
                                        <th class="p-4">Date</th>
                                        <th class="p-4">Status</th>
                                        <th class="p-4 text-right">Reply / Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="tickets-table-body" class="divide-y divide-gray-800/50">
                                    <tr><td colspan="6" class="p-8 text-center text-gray-500">Loading support tickets...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- ⭐ TAB 9: USER REVIEWS -->
                <div id="tab-reviews" class="space-y-6 hidden">
                    <p class="text-sm text-gray-400">Ratings and feedback submitted by users after purchase completion.</p>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">Customer</th>
                                        <th class="p-4">Product</th>
                                        <th class="p-4">Rating</th>
                                        <th class="p-4">Feedback Comment</th>
                                        <th class="p-4">Date</th>
                                    </tr>
                                </thead>
                                <tbody id="reviews-table-body" class="divide-y divide-gray-800/50">
                                    <tr><td colspan="5" class="p-8 text-center text-gray-500">Loading user reviews...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 🏷️ TAB 10: PROMO COUPONS -->
                <div id="tab-coupons" class="space-y-6 hidden">
                    <div class="flex justify-between items-center">
                        <p class="text-sm text-gray-400">Create discount promo codes for checkout discount application.</p>
                        <button onclick="openCouponModal()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20 transition flex items-center space-x-1.5">
                            <i class="fa-solid fa-plus text-xs"></i><span>Create Coupon</span>
                        </button>
                    </div>

                    <div class="glass rounded-2xl overflow-hidden">
                        <div class="overflow-x-auto custom-scrollbar">
                            <table class="w-full text-left border-collapse text-sm">
                                <thead>
                                    <tr class="border-b border-gray-800 bg-gray-900/50 text-gray-400 uppercase font-semibold text-[11px] tracking-wider">
                                        <th class="p-4">Code</th>
                                        <th class="p-4">Discount %</th>
                                        <th class="p-4">Flat Discount $</th>
                                        <th class="p-4">Uses Count</th>
                                        <th class="p-4 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody id="coupons-table-body" class="divide-y divide-gray-800/50">
                                    <tr><td colspan="5" class="p-8 text-center text-gray-500">Loading promo coupons...</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <!-- 📢 TAB 11: BROADCAST ANNOUNCEMENTS -->
                <div id="tab-broadcast" class="space-y-6 hidden">
                    <div class="glass p-6 rounded-2xl space-y-4 max-w-2xl">
                        <h3 class="text-sm font-bold uppercase tracking-wider text-gray-300">Broadcast Announcement to Bot Users</h3>
                        <p class="text-xs text-gray-400">Sends a direct HTML-formatted message to all active registered users in your database.</p>
                        
                        <div>
                            <label class="block text-xs font-bold text-gray-400 mb-1 uppercase tracking-wider">Message Text (HTML format supported)</label>
                            <textarea id="broadcast-text" rows="6" class="w-full bg-gray-900/80 border border-gray-800 rounded-xl p-4 text-sm text-white focus:outline-none focus:border-indigo-500 transition placeholder-gray-600 font-mono" placeholder="🔥 <b>FLASH SALE: 2 HOURS ONLY!</b> 🔥&#10;&#10;Special price $0.70 live now!"></textarea>
                        </div>
                        
                        <div class="flex items-center space-x-3">
                            <button onclick="sendBroadcast()" class="px-5 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20 transition flex items-center space-x-2">
                                <i class="fa-solid fa-paper-plane"></i><span>Send Broadcast Now</span>
                            </button>
                            <button onclick="enhanceBroadcast()" id="enhance-broadcast-btn" class="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-purple-600/20 transition flex items-center space-x-2">
                                <i class="fa-solid fa-wand-magic-sparkles"></i><span>Enhance with AI</span>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- ⚙️ TAB 12: SYSTEM SETTINGS -->
                <div id="tab-settings" class="space-y-6 hidden">
                    <div class="glass p-6 rounded-2xl space-y-6 max-w-3xl">
                        <div>
                            <h3 class="text-sm font-bold uppercase tracking-wider text-gray-300">System & Payment Configuration</h3>
                            <p class="text-xs text-gray-400">Update system configuration, Gemini API key, and payment parameters live in `.env`.</p>
                        </div>

                        <div class="space-y-4" id="settings-form-container">
                            <p class="text-xs text-gray-500">Loading system settings...</p>
                        </div>

                        <button onclick="saveSettings()" class="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20 transition flex items-center space-x-2">
                            <i class="fa-solid fa-floppy-disk"></i><span>Save Settings</span>
                        </button>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <!-- MODAL: ADD/EDIT PRODUCT (WITH REMISE BULK TIERS) -->
    <div id="modal-product" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden z-50 p-4">
        <div class="glass p-6 rounded-2xl w-full max-w-xl space-y-4 border border-gray-800 max-h-[90vh] overflow-y-auto custom-scrollbar">
            <div class="flex justify-between items-center border-b border-gray-800 pb-3">
                <h3 class="text-sm font-bold text-white uppercase tracking-wider" id="modal-product-title">Create Product</h3>
                <button onclick="closeProductModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <input type="hidden" id="prod-id">
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Product Name</label>
                    <input type="text" id="prod-name" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Emoji Icon</label>
                    <input type="text" id="prod-emoji" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500" placeholder="📦">
                </div>
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Category</label>
                <select id="prod-category" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500">
                </select>
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Base Unit Price ($ USD)</label>
                    <input type="number" step="0.01" id="prod-price" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500">
                </div>
                <div>
                    <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Stock (-1 for Unlimited)</label>
                    <input type="number" id="prod-stock" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500">
                </div>
            </div>

            <!-- REMISE (BULK DISCOUNT TIERS) SECTION -->
            <div class="bg-gray-900/60 p-4 rounded-xl border border-indigo-500/20 space-y-3">
                <div class="flex items-center space-x-2">
                    <i class="fa-solid fa-tags text-indigo-400 text-xs"></i>
                    <h4 class="text-xs font-bold text-white uppercase tracking-wider">Remise / Tiered Bulk Discount Prices ($ USD)</h4>
                </div>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                    <div>
                        <label class="block text-[10px] text-gray-400 mb-1 font-semibold">1 – 9 Qty</label>
                        <input type="number" step="0.01" id="tier-1-price" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-2.5 py-1.5 text-xs text-emerald-400 focus:outline-none" placeholder="0.70">
                    </div>
                    <div>
                        <label class="block text-[10px] text-gray-400 mb-1 font-semibold">10 – 29 Qty</label>
                        <input type="number" step="0.01" id="tier-10-price" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-2.5 py-1.5 text-xs text-emerald-400 focus:outline-none" placeholder="0.70">
                    </div>
                    <div>
                        <label class="block text-[10px] text-gray-400 mb-1 font-semibold">30 – 49 Qty</label>
                        <input type="number" step="0.01" id="tier-30-price" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-2.5 py-1.5 text-xs text-emerald-400 focus:outline-none" placeholder="0.70">
                    </div>
                    <div>
                        <label class="block text-[10px] text-gray-400 mb-1 font-semibold">50+ Qty</label>
                        <input type="number" step="0.01" id="tier-50-price" class="w-full bg-gray-950 border border-gray-800 rounded-lg px-2.5 py-1.5 text-xs text-emerald-400 focus:outline-none" placeholder="0.70">
                    </div>
                </div>
                <p class="text-[10px] text-gray-500">Leave blank to use base unit price. Setting prices here updates the Telegram Bot checkout calculation instantly.</p>
            </div>

            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Description</label>
                <textarea id="prod-desc" rows="3" class="w-full bg-gray-900 border border-gray-800 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-indigo-500"></textarea>
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Product Image URL <span class="text-gray-600 normal-case font-normal">(optional — shown in bot)</span></label>
                <input type="url" id="prod-image-url" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500" placeholder="https://example.com/image.jpg">
            </div>
            <div class="flex justify-end space-x-3 border-t border-gray-800 pt-3">
                <button onclick="closeProductModal()" class="px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 rounded-xl text-xs font-semibold text-gray-300">Cancel</button>
                <button onclick="saveProduct()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20">Save Product</button>
            </div>
        </div>
    </div>

    <!-- MODAL: ADD/EDIT CATEGORY -->
    <div id="modal-category" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden z-50 p-4">
        <div class="glass p-6 rounded-2xl w-full max-w-md space-y-4 border border-gray-800">
            <div class="flex justify-between items-center border-b border-gray-800 pb-3">
                <h3 class="text-sm font-bold text-white uppercase tracking-wider" id="modal-category-title">Create Category</h3>
                <button onclick="closeCategoryModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <input type="hidden" id="cat-id">
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Category Name</label>
                <input type="text" id="cat-name" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500">
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Emoji Icon</label>
                <input type="text" id="cat-emoji" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500" placeholder="📁">
            </div>
            <div class="flex justify-end space-x-3 border-t border-gray-800 pt-3">
                <button onclick="closeCategoryModal()" class="px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 rounded-xl text-xs font-semibold text-gray-300">Cancel</button>
                <button onclick="saveCategory()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20">Save Category</button>
            </div>
        </div>
    </div>

    <!-- MODAL: ADD SINGLE STOCK ITEM -->
    <div id="modal-add-stock" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden z-50 p-4">
        <div class="glass p-6 rounded-2xl w-full max-w-md space-y-4 border border-gray-800">
            <div class="flex justify-between items-center border-b border-gray-800 pb-3">
                <h3 class="text-sm font-bold text-white uppercase tracking-wider">Add Single Stock Item</h3>
                <button onclick="closeAddStockModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Select Product</label>
                <select id="stock-add-product-id" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"></select>
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Digital Code / Account / Link</label>
                <textarea id="stock-add-data" rows="3" class="w-full bg-gray-900 border border-gray-800 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-indigo-500" placeholder="https://example.com/redeem?code=ABC123"></textarea>
            </div>
            <div class="flex justify-end space-x-3 border-t border-gray-800 pt-3">
                <button onclick="closeAddStockModal()" class="px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 rounded-xl text-xs font-semibold text-gray-300">Cancel</button>
                <button onclick="saveSingleStock()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20">Add Stock</button>
            </div>
        </div>
    </div>

    <!-- MODAL: BULK UPLOAD STOCK .TXT -->
    <div id="modal-upload-stock" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden z-50 p-4">
        <div class="glass p-6 rounded-2xl w-full max-w-md space-y-4 border border-gray-800">
            <div class="flex justify-between items-center border-b border-gray-800 pb-3">
                <h3 class="text-sm font-bold text-white uppercase tracking-wider">Bulk Upload .TXT File</h3>
                <button onclick="closeUploadStockModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Select Product</label>
                <select id="stock-upload-product-id" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500"></select>
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Select .TXT File (1 code per line)</label>
                <input type="file" id="stock-file-input" accept=".txt" class="w-full bg-gray-900 border border-gray-800 rounded-xl p-2 text-xs text-gray-400">
            </div>
            <div class="flex justify-end space-x-3 border-t border-gray-800 pt-3">
                <button onclick="closeUploadStockModal()" class="px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 rounded-xl text-xs font-semibold text-gray-300">Cancel</button>
                <button onclick="uploadStockFile()" class="px-4 py-2 bg-purple-600 hover:bg-purple-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-purple-600/20">Upload Stock</button>
            </div>
        </div>
    </div>

    <!-- MODAL: ADJUST USER BALANCE -->
    <div id="modal-user-balance" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden z-50 p-4">
        <div class="glass p-6 rounded-2xl w-full max-w-md space-y-4 border border-gray-800">
            <div class="flex justify-between items-center border-b border-gray-800 pb-3">
                <h3 class="text-sm font-bold text-white uppercase tracking-wider">Adjust User Balance</h3>
                <button onclick="closeUserBalanceModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <input type="hidden" id="balance-user-id">
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Adjustment Amount ($ USD)</label>
                <input type="number" step="0.01" id="balance-delta" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500" placeholder="Use +5.00 to add, -5.00 to deduct">
            </div>
            <div class="flex justify-end space-x-3 border-t border-gray-800 pt-3">
                <button onclick="closeUserBalanceModal()" class="px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 rounded-xl text-xs font-semibold text-gray-300">Cancel</button>
                <button onclick="saveUserBalance()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20">Update Balance</button>
            </div>
        </div>
    </div>

    <!-- MODAL: ADD PROMO COUPON -->
    <div id="modal-coupon" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden z-50 p-4">
        <div class="glass p-6 rounded-2xl w-full max-w-md space-y-4 border border-gray-800">
            <div class="flex justify-between items-center border-b border-gray-800 pb-3">
                <h3 class="text-sm font-bold text-white uppercase tracking-wider">Create Promo Coupon</h3>
                <button onclick="closeCouponModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Coupon Code</label>
                <input type="text" id="coupon-code" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500 uppercase" placeholder="FLASH10">
            </div>
            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Discount %</label>
                    <input type="number" id="coupon-discount-percent" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500" value="0">
                </div>
                <div>
                    <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Flat Discount $</label>
                    <input type="number" step="0.01" id="coupon-flat-discount" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500" value="0.00">
                </div>
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Max Usage (-1 for Unlimited)</label>
                <input type="number" id="coupon-max-uses" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-indigo-500" value="-1">
            </div>
            <div class="flex justify-end space-x-3 border-t border-gray-800 pt-3">
                <button onclick="closeCouponModal()" class="px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 rounded-xl text-xs font-semibold text-gray-300">Cancel</button>
                <button onclick="saveCoupon()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20">Save Coupon</button>
            </div>
        </div>
    </div>

    <!-- MODAL: REPLY SUPPORT TICKET -->
    <div id="modal-ticket-reply" class="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center hidden z-50 p-4">
        <div class="glass p-6 rounded-2xl w-full max-w-lg space-y-4 border border-gray-800">
            <div class="flex justify-between items-center border-b border-gray-800 pb-3">
                <h3 class="text-sm font-bold text-white uppercase tracking-wider">Reply Support Ticket</h3>
                <button onclick="closeTicketReplyModal()" class="text-gray-400 hover:text-white"><i class="fa-solid fa-xmark text-lg"></i></button>
            </div>
            <input type="hidden" id="ticket-id">
            <div class="bg-gray-900/60 p-3 rounded-xl border border-gray-800 text-xs space-y-1">
                <p class="text-gray-400 font-medium" id="ticket-user-info"></p>
                <p class="text-white font-semibold" id="ticket-user-msg"></p>
            </div>
            <div>
                <label class="block text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1">Reply Message (Sent to User Telegram DM)</label>
                <textarea id="ticket-reply-text" rows="4" class="w-full bg-gray-900 border border-gray-800 rounded-xl p-3 text-xs text-white focus:outline-none focus:border-indigo-500" placeholder="Hello! Thanks for contacting support..."></textarea>
            </div>
            <div class="flex justify-end space-x-3 border-t border-gray-800 pt-3">
                <button onclick="closeTicketReplyModal()" class="px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 rounded-xl text-xs font-semibold text-gray-300">Cancel</button>
                <button onclick="sendTicketReply()" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-xl text-xs font-bold text-white shadow-lg shadow-indigo-600/20">Send Reply</button>
            </div>
        </div>
    </div>

    <!-- JavaScript Logic -->
    <script>
        let activeTab = 'overview';
        let revenueChart = null;

        /* ── Mobile sidebar helpers ── */
        function openSidebar() {
            document.getElementById('sidebar').classList.add('open');
            document.getElementById('sidebar-backdrop').classList.remove('hidden');
        }
        function closeSidebar() {
            document.getElementById('sidebar').classList.remove('open');
            document.getElementById('sidebar-backdrop').classList.add('hidden');
        }

        function switchTab(tabId) {
            document.querySelectorAll('button[id$="-btn"]').forEach(btn => {
                btn.classList.remove('sidebar-btn-active');
            });
            document.querySelectorAll('div[id^="tab-"]').forEach(div => {
                if (div.id.startsWith('tab-') && !div.id.endsWith('-btn')) {
                    div.classList.add('hidden');
                }
            });

            const targetBtn = document.getElementById(`tab-${tabId}-btn`);
            const targetContent = document.getElementById(`tab-${tabId}`);
            if (targetBtn && targetContent) {
                targetBtn.classList.add('sidebar-btn-active');
                targetContent.classList.remove('hidden');
                // Auto-close sidebar on mobile after navigating
                closeSidebar();
                activeTab = tabId;
                const span = targetBtn.querySelector('span');
                if (span) {
                    document.getElementById('current-page-title').innerText = span.innerText;
                }

                if (tabId === 'overview') fetchStats();
                else if (tabId === 'ai') fetchAiAnalysisCache();
                else if (tabId === 'products') fetchProducts();
                else if (tabId === 'categories') fetchCategories();
                else if (tabId === 'inventory') fetchInventory();
                else if (tabId === 'users') fetchUsers();
                else if (tabId === 'orders') fetchOrders();
                else if (tabId === 'tickets') fetchTickets();
                else if (tabId === 'reviews') fetchReviews();
                else if (tabId === 'coupons') fetchCoupons();
                else if (tabId === 'settings') fetchSettings();
            }
        }

        // Overview Stats & Chart
        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();

                document.getElementById('stat-revenue').innerText = `$${data.total_revenue.toFixed(2)}`;
                document.getElementById('stat-today-sales').innerText = `$${data.today_sales.toFixed(2)}`;
                document.getElementById('stat-users').innerText = data.total_users;
                document.getElementById('stat-orders').innerText = data.total_orders;
                document.getElementById('stat-total-stock').innerText = data.total_stock;
                document.getElementById('stat-low-stock').innerText = data.low_stock_alerts;

                renderChart(data.chart_data.dates, data.chart_data.values);
            } catch (err) {
                console.error(err);
            }
        }

        function renderChart(labels, dataValues) {
            const ctx = document.getElementById('chart-revenue').getContext('2d');
            if (revenueChart) revenueChart.destroy();

            revenueChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Sales ($ USD)',
                        data: dataValues,
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.15)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 2,
                        pointBackgroundColor: '#818cf8',
                        pointRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false }, ticks: { color: '#6b7280', font: { size: 10 } } },
                        y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#6b7280', font: { size: 10 } } }
                    }
                }
            });
        }

        async function fetchActivity() {
            try {
                const res = await fetch('/api/activity');
                const activities = await res.json();
                const container = document.getElementById('overview-activities');

                if (!activities || activities.length === 0) {
                    container.innerHTML = '<p class="text-xs text-gray-500 text-center py-10">No recent logs recorded...</p>';
                    return;
                }

                container.innerHTML = activities.map(act => `
                    <div class="p-2.5 rounded-xl bg-gray-900/50 border border-gray-800/80 flex items-start space-x-2.5 text-xs">
                        <div class="w-6 h-6 rounded-lg bg-indigo-500/10 text-indigo-400 flex items-center justify-center shrink-0 mt-0.5 border border-indigo-500/20">
                            <i class="fa-solid fa-terminal text-[10px]"></i>
                        </div>
                        <div class="flex-1 min-w-0">
                            <p class="text-gray-300 leading-snug font-medium break-words">${act.description || act.action}</p>
                            <span class="text-[10px] text-gray-500">${act.created_at || ''}</span>
                        </div>
                    </div>
                `).join('');
            } catch (err) {
                console.error(err);
            }
        }

        // Gemini AI Insights
        let lastAiAnalysis = null;
        async function fetchAiAnalysisCache() {
            if (lastAiAnalysis) renderAiReport(lastAiAnalysis);
        }

        async function runAiAnalysis() {
            const btn = document.getElementById('ai-generate-btn');
            const container = document.getElementById('ai-report-container');
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner animate-spin"></i><span>Analyzing with Gemini AI...</span>';
            container.innerHTML = '<div class="p-12 text-center space-y-3"><i class="fa-solid fa-wand-magic-sparkles text-4xl text-purple-400 animate-pulse"></i><p class="text-sm font-semibold text-purple-300">Gemini AI is analyzing store revenue, stock counts, and sales velocity...</p></div>';

            try {
                const res = await fetch('/api/ai/analyze', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'success') {
                    lastAiAnalysis = data.analysis;
                    renderAiReport(data.analysis);
                } else {
                    container.innerHTML = `<div class="p-6 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs font-semibold">AI Analysis failed: ${data.message}</div>`;
                }
            } catch (err) {
                container.innerHTML = `<div class="p-6 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs font-semibold">Error connecting to AI service</div>`;
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-bolt"></i><span>Generate AI Report Now</span>';
            }
        }

        function renderAiReport(text) {
            const container = document.getElementById('ai-report-container');
            let formatted = (text || '').split('\n\n').join('<br><br>');
            formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<b class="text-white font-semibold">$1</b>');
            container.innerHTML = `
                <div class="glass p-6 rounded-2xl border border-purple-500/30 space-y-4">
                    <div class="flex items-center justify-between border-b border-gray-800 pb-3">
                        <span class="text-xs font-bold text-purple-400 uppercase tracking-wider flex items-center"><i class="fa-solid fa-robot mr-2"></i>Gemini AI Diagnosis Complete</span>
                        <span class="text-[10px] bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20 font-bold uppercase">Live</span>
                    </div>
                    <div class="text-xs text-gray-200 leading-relaxed font-sans space-y-2 leading-6">
                        ${formatted}
                    </div>
                </div>
            `;
        }

        // Products Catalog & Remise Tiers
        let globalCategories = [];
        async function fetchProducts() {
            try {
                const res = await fetch('/api/products');
                const products = await res.json();
                const tbody = document.getElementById('products-table-body');

                if (!products || products.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" class="p-8 text-center text-gray-500">No products found in catalog.</td></tr>';
                    return;
                }

                tbody.innerHTML = products.map(p => {
                    let tiersDisplay = '<span class="text-gray-500 text-xs">Default</span>';
                    if (p.tier_prices) {
                        try {
                            const t = JSON.parse(p.tier_prices);
                            tiersDisplay = `
                                <div class="text-[11px] space-y-0.5 font-mono">
                                    <span class="text-emerald-400">1-9: $${t.tier_1 || p.price}</span> | 
                                    <span class="text-emerald-400">10+: $${t.tier_10 || p.price}</span> | 
                                    <span class="text-emerald-400">30+: $${t.tier_30 || p.price}</span> | 
                                    <span class="text-emerald-400">50+: $${t.tier_50 || p.price}</span>
                                </div>
                            `;
                        } catch (e) {}
                    }

                    return `
                        <tr class="hover:bg-white/[0.02] transition">
                            <td class="p-4 font-semibold text-white flex items-center space-x-3">
                                <span class="text-lg">${p.emoji || '📦'}</span>
                                <div>
                                    <div>${p.name}</div>
                                    <div class="text-[11px] text-gray-400 font-normal line-clamp-1">${p.description || ''}</div>
                                </div>
                            </td>
                            <td class="p-4 text-gray-300">${p.category_name || 'General'}</td>
                            <td class="p-4 font-bold text-white">$${p.price.toFixed(2)}</td>
                            <td class="p-4">${tiersDisplay}</td>
                            <td class="p-4 font-medium text-gray-300">${p.stock === -1 ? '♾️ Unlimited' : p.stock}</td>
                            <td class="p-4">
                                <span class="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${p.is_active ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'}">
                                    ${p.is_active ? 'Active' : 'Disabled'}
                                </span>
                            </td>
                            <td class="p-4 text-right space-x-2">
                                <button onclick="editProduct(${JSON.stringify(p).replace(/"/g, '&quot;')})" class="px-2.5 py-1.5 bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 rounded-lg text-xs font-semibold border border-indigo-500/20">Edit / Remise</button>
                                <button onclick="deleteProduct(${p.id})" class="px-2.5 py-1.5 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 rounded-lg text-xs font-semibold border border-rose-500/20">Delete</button>
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error(err);
            }
        }

        async function populateCategoryDropdowns() {
            try {
                const res = await fetch('/api/categories');
                globalCategories = await res.json();
                const sel = document.getElementById('prod-category');
                sel.innerHTML = globalCategories.map(c => `<option value="${c.id}">${c.emoji || '📁'} ${c.name}</option>`).join('');

                const invSel = document.getElementById('inventory-product-filter');
                const prodRes = await fetch('/api/products');
                const prods = await prodRes.json();
                invSel.innerHTML = '<option value="">All Products</option>' + prods.map(p => `<option value="${p.id}">${p.emoji || '📦'} ${p.name}</option>`).join('');
                document.getElementById('stock-add-product-id').innerHTML = prods.map(p => `<option value="${p.id}">${p.emoji || '📦'} ${p.name}</option>`).join('');
                document.getElementById('stock-upload-product-id').innerHTML = prods.map(p => `<option value="${p.id}">${p.emoji || '📦'} ${p.name}</option>`).join('');
            } catch (err) {
                console.error(err);
            }
        }

        function openProductModal() {
            populateCategoryDropdowns();
            document.getElementById('modal-product-title').innerText = 'Create Product';
            document.getElementById('prod-id').value = '';
            document.getElementById('prod-name').value = '';
            document.getElementById('prod-emoji').value = '📦';
            document.getElementById('prod-price').value = '0.70';
            document.getElementById('prod-stock').value = '0';
            document.getElementById('prod-desc').value = '';
            document.getElementById('prod-image-url').value = '';
            document.getElementById('tier-1-price').value = '0.70';
            document.getElementById('tier-10-price').value = '0.70';
            document.getElementById('tier-30-price').value = '0.70';
            document.getElementById('tier-50-price').value = '0.70';
            document.getElementById('modal-product').classList.remove('hidden');
        }

        function editProduct(p) {
            populateCategoryDropdowns();
            document.getElementById('modal-product-title').innerText = 'Edit Product & Remise Tiers';
            document.getElementById('prod-id').value = p.id;
            document.getElementById('prod-name').value = p.name;
            document.getElementById('prod-emoji').value = p.emoji || '📦';
            document.getElementById('prod-price').value = p.price;
            document.getElementById('prod-stock').value = p.stock;
            document.getElementById('prod-desc').value = p.description || '';
            document.getElementById('prod-image-url').value = p.image_url || '';
            document.getElementById('prod-category').value = p.category_id;

            let t1 = p.price, t10 = p.price, t30 = p.price, t50 = p.price;
            if (p.tier_prices) {
                try {
                    const t = JSON.parse(p.tier_prices);
                    t1 = t.tier_1 || p.price;
                    t10 = t.tier_10 || p.price;
                    t30 = t.tier_30 || p.price;
                    t50 = t.tier_50 || p.price;
                } catch(e) {}
            }
            document.getElementById('tier-1-price').value = t1;
            document.getElementById('tier-10-price').value = t10;
            document.getElementById('tier-30-price').value = t30;
            document.getElementById('tier-50-price').value = t50;

            document.getElementById('modal-product').classList.remove('hidden');
        }

        function closeProductModal() {
            document.getElementById('modal-product').classList.add('hidden');
        }

        async function saveProduct() {
            const pId = document.getElementById('prod-id').value;
            const tierPrices = {
                tier_1: parseFloat(document.getElementById('tier-1-price').value) || 0.70,
                tier_10: parseFloat(document.getElementById('tier-10-price').value) || 0.70,
                tier_30: parseFloat(document.getElementById('tier-30-price').value) || 0.70,
                tier_50: parseFloat(document.getElementById('tier-50-price').value) || 0.70
            };

            const data = {
                id: pId ? parseInt(pId) : null,
                name: document.getElementById('prod-name').value.trim(),
                emoji: document.getElementById('prod-emoji').value.trim(),
                price: parseFloat(document.getElementById('prod-price').value),
                stock: parseInt(document.getElementById('prod-stock').value),
                description: document.getElementById('prod-desc').value.trim(),
                image_url: document.getElementById('prod-image-url').value.trim(),
                category_id: parseInt(document.getElementById('prod-category').value),
                tier_prices: JSON.stringify(tierPrices)
            };

            const endpoint = pId ? '/api/product/edit' : '/api/product/add';
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const resData = await res.json();
            if (resData.status === 'success') {
                closeProductModal();
                fetchProducts();
            } else {
                alert('Error saving product: ' + (resData.message || 'Unknown error'));
            }
        }

        async function deleteProduct(id) {
            if (!confirm('Are you sure you want to delete this product?')) return;
            const res = await fetch('/api/product/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id})
            });
            const data = await res.json();
            if (data.status === 'success') fetchProducts();
            else alert('Error deleting product');
        }

        // Categories
        async function fetchCategories() {
            try {
                const res = await fetch('/api/categories');
                const categories = await res.json();
                const tbody = document.getElementById('categories-table-body');

                if (!categories || categories.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-gray-500">No categories created yet.</td></tr>';
                    return;
                }

                tbody.innerHTML = categories.map(c => `
                    <tr class="hover:bg-white/[0.02] transition">
                        <td class="p-4 text-gray-400 font-mono text-xs">#${c.id}</td>
                        <td class="p-4 text-lg">${c.emoji || '📁'}</td>
                        <td class="p-4 font-semibold text-white">${c.name}</td>
                        <td class="p-4">
                            <span class="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${c.is_active ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-gray-500/10 text-gray-400 border-gray-500/20'}">
                                ${c.is_active ? 'Active' : 'Disabled'}
                            </span>
                        </td>
                        <td class="p-4 text-right space-x-2">
                            <button onclick="editCategory(${JSON.stringify(c).replace(/"/g, '&quot;')})" class="px-2.5 py-1.5 bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 rounded-lg text-xs font-semibold border border-indigo-500/20">Edit</button>
                            <button onclick="deleteCategory(${c.id})" class="px-2.5 py-1.5 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 rounded-lg text-xs font-semibold border border-rose-500/20">Delete</button>
                        </td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error(err);
            }
        }

        function openCategoryModal() {
            document.getElementById('modal-category-title').innerText = 'Create Category';
            document.getElementById('cat-id').value = '';
            document.getElementById('cat-name').value = '';
            document.getElementById('cat-emoji').value = '📁';
            document.getElementById('modal-category').classList.remove('hidden');
        }

        function editCategory(c) {
            document.getElementById('modal-category-title').innerText = 'Edit Category';
            document.getElementById('cat-id').value = c.id;
            document.getElementById('cat-name').value = c.name;
            document.getElementById('cat-emoji').value = c.emoji || '📁';
            document.getElementById('modal-category').classList.remove('hidden');
        }

        function closeCategoryModal() { document.getElementById('modal-category').classList.add('hidden'); }

        async function saveCategory() {
            const cId = document.getElementById('cat-id').value;
            const data = {
                id: cId ? parseInt(cId) : null,
                name: document.getElementById('cat-name').value.trim(),
                emoji: document.getElementById('cat-emoji').value.trim()
            };

            const endpoint = cId ? '/api/category/edit' : '/api/category/add';
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const resData = await res.json();
            if (resData.status === 'success') {
                closeCategoryModal();
                fetchCategories();
            } else {
                alert('Error saving category: ' + (resData.message || 'Unknown error'));
            }
        }

        async function deleteCategory(id) {
            if (!confirm('Are you sure you want to delete this category?')) return;
            const res = await fetch('/api/category/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id})
            });
            const data = await res.json();
            if (data.status === 'success') fetchCategories();
            else alert('Error deleting category');
        }

        // Inventory Stock
        async function fetchInventory() {
            try {
                populateCategoryDropdowns();
                const prodId = document.getElementById('inventory-product-filter').value;
                const url = prodId ? `/api/inventory?product_id=${prodId}` : '/api/inventory';
                const res = await fetch(url);
                const items = await res.json();
                const tbody = document.getElementById('inventory-table-body');

                if (!items || items.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-gray-500">No stock entries found.</td></tr>';
                    return;
                }

                tbody.innerHTML = items.map(s => `
                    <tr class="hover:bg-white/[0.02] transition">
                        <td class="p-4 text-gray-400 font-mono text-xs">#${s.id}</td>
                        <td class="p-4 font-semibold text-white">${s.product_name || 'N/A'}</td>
                        <td class="p-4 font-mono text-xs text-indigo-300 max-w-xs truncate">${s.data}</td>
                        <td class="p-4">
                            <span class="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${s.is_sold ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}">
                                ${s.is_sold ? 'Sold' : 'Available'}
                            </span>
                        </td>
                        <td class="p-4 text-right">
                            <button onclick="deleteStockItem(${s.id})" class="px-2.5 py-1.5 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 rounded-lg text-xs font-semibold border border-rose-500/20">Delete</button>
                        </td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error(err);
            }
        }

        function openAddStockModal() {
            populateCategoryDropdowns();
            document.getElementById('stock-add-data').value = '';
            document.getElementById('modal-add-stock').classList.remove('hidden');
        }
        function closeAddStockModal() { document.getElementById('modal-add-stock').classList.add('hidden'); }

        async function saveSingleStock() {
            const productId = parseInt(document.getElementById('stock-add-product-id').value);
            const stockData = document.getElementById('stock-add-data').value.trim();
            if (!stockData) return alert('Stock data cannot be empty');

            const res = await fetch('/api/inventory/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({product_id: productId, data: stockData})
            });
            const data = await res.json();
            if (data.status === 'success') {
                closeAddStockModal();
                fetchInventory();
            } else {
                alert('Error adding stock: ' + data.message);
            }
        }

        function openUploadStockModal() {
            populateCategoryDropdowns();
            document.getElementById('modal-upload-stock').classList.remove('hidden');
        }
        function closeUploadStockModal() { document.getElementById('modal-upload-stock').classList.add('hidden'); }

        async function uploadStockFile() {
            const productId = document.getElementById('stock-upload-product-id').value;
            const fileInput = document.getElementById('stock-file-input');
            if (!fileInput.files[0]) return alert('Please select a .txt file');

            const formData = new FormData();
            formData.append('product_id', productId);
            formData.append('file', fileInput.files[0]);

            const res = await fetch('/api/inventory/upload', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            if (data.status === 'success') {
                alert(`Successfully added ${data.added} stock items!`);
                closeUploadStockModal();
                fetchInventory();
            } else {
                alert('Error uploading stock file: ' + data.message);
            }
        }

        async function deleteStockItem(id) {
            if (!confirm('Are you sure you want to delete this stock entry?')) return;
            const res = await fetch('/api/inventory/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id})
            });
            const data = await res.json();
            if (data.status === 'success') fetchInventory();
            else alert('Error deleting stock');
        }

        async function purgeSoldStock() {
            if (!confirm('Are you sure you want to purge all sold stock items from the database?')) return;
            const res = await fetch('/api/inventory/purge_sold', { method: 'POST' });
            const data = await res.json();
            if (data.status === 'success') {
                alert(`Purged ${data.purged_count} sold stock items!`);
                fetchInventory();
            } else {
                alert('Error purging sold stock');
            }
        }

        // Users
        async function fetchUsers() {
            try {
                const res = await fetch('/api/users');
                const users = await res.json();
                const tbody = document.getElementById('users-table-body');

                if (!users || users.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="7" class="p-8 text-center text-gray-500">No users registered yet.</td></tr>';
                    return;
                }

                tbody.innerHTML = users.map(u => `
                    <tr class="hover:bg-white/[0.02] transition">
                        <td class="p-4 font-semibold text-white">
                            <div>${u.first_name || 'N/A'}</div>
                            <div class="text-[11px] text-gray-400 font-normal">${u.username ? '@' + u.username : ''}</div>
                        </td>
                        <td class="p-4 text-gray-400 font-mono text-xs">${u.telegram_id}</td>
                        <td class="p-4 font-bold text-emerald-400">$${u.balance.toFixed(2)}</td>
                        <td class="p-4 font-medium text-gray-300">$${u.total_spent.toFixed(2)}</td>
                        <td class="p-4 text-xs">${u.membership || '🥉 Bronze'}</td>
                        <td class="p-4">
                            <span class="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${u.is_banned ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'}">
                                ${u.is_banned ? 'Banned' : 'Active'}
                            </span>
                        </td>
                        <td class="p-4 text-right space-x-2">
                            <button onclick="openUserBalanceModal(${u.telegram_id})" class="px-2.5 py-1.5 bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 rounded-lg text-xs font-semibold border border-indigo-500/20">Balance</button>
                            <button onclick="toggleBan(${u.telegram_id}, '${u.is_banned ? 'unban' : 'ban'}')" class="px-2.5 py-1.5 ${u.is_banned ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-rose-500/10 text-rose-400 border-rose-500/20'} rounded-lg text-xs font-semibold border">
                                ${u.is_banned ? 'Unban' : 'Ban'}
                            </button>
                        </td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error(err);
            }
        }

        function openUserBalanceModal(tgId) {
            document.getElementById('balance-user-id').value = tgId;
            document.getElementById('balance-delta').value = '';
            document.getElementById('modal-user-balance').classList.remove('hidden');
        }
        function closeUserBalanceModal() { document.getElementById('modal-user-balance').classList.add('hidden'); }

        async function saveUserBalance() {
            const tgId = document.getElementById('balance-user-id').value;
            const delta = parseFloat(document.getElementById('balance-delta').value);
            if (isNaN(delta)) return alert('Enter valid number');

            const res = await fetch('/api/user/balance', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({telegram_id: parseInt(tgId), delta})
            });
            const data = await res.json();
            if (data.status === 'success') {
                closeUserBalanceModal();
                fetchUsers();
            } else {
                alert('Error updating user balance');
            }
        }

        async function toggleBan(tgId, action) {
            if (!confirm(`Are you sure you want to ${action} user ${tgId}?`)) return;
            const res = await fetch('/api/user/ban', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({telegram_id: parseInt(tgId), action})
            });
            const data = await res.json();
            if (data.status === 'success') fetchUsers();
            else alert('Error toggling user ban status');
        }

        // Orders
        async function fetchOrders() {
            try {
                const res = await fetch('/api/orders');
                const orders = await res.json();
                const tbody = document.getElementById('orders-table-body');

                if (!orders || orders.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" class="p-8 text-center text-gray-500">No orders recorded yet.</td></tr>';
                    return;
                }

                tbody.innerHTML = orders.map(o => `
                    <tr class="hover:bg-white/[0.02] transition">
                        <td class="p-4 font-mono text-xs text-gray-400">#${o.id}</td>
                        <td class="p-4 font-medium text-white">${o.first_name}</td>
                        <td class="p-4 font-medium text-indigo-300">${o.product_name}</td>
                        <td class="p-4 text-gray-300 font-bold">${o.quantity}</td>
                        <td class="p-4 font-bold text-emerald-400">$${o.total_price.toFixed(2)}</td>
                        <td class="p-4 text-xs text-gray-400 uppercase">${o.payment_method}</td>
                        <td class="p-4">
                            <span class="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${o.status === 'delivered' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : (o.status === 'paid' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20')}">
                                ${o.status}
                            </span>
                        </td>
                        <td class="p-4 text-right">
                            <select onchange="updateOrderStatus(${o.id}, this.value)" class="bg-gray-900 border border-gray-800 rounded-lg px-2 py-1 text-xs text-gray-300 focus:outline-none">
                                <option value="pending" ${o.status==='pending'?'selected':''}>Pending</option>
                                <option value="paid" ${o.status==='paid'?'selected':''}>Paid</option>
                                <option value="delivered" ${o.status==='delivered'?'selected':''}>Delivered</option>
                                <option value="cancelled" ${o.status==='cancelled'?'selected':''}>Cancelled</option>
                            </select>
                        </td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error(err);
            }
        }

        async function updateOrderStatus(orderId, action) {
            const res = await fetch('/api/order/action', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({order_id: orderId, action})
            });
            const data = await res.json();
            if (data.status === 'success') fetchOrders();
            else alert('Error updating order status');
        }

        // Support Tickets
        async function fetchTickets() {
            try {
                const res = await fetch('/api/tickets');
                const tickets = await res.json();
                const tbody = document.getElementById('tickets-table-body');

                if (!tickets || tickets.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="p-8 text-center text-gray-500">No support tickets found.</td></tr>';
                    return;
                }

                tbody.innerHTML = tickets.map(t => `
                    <tr class="hover:bg-white/[0.02] transition">
                        <td class="p-4 font-mono text-xs text-gray-400">#${t.id}</td>
                        <td class="p-4 font-medium text-white">${t.user_name || t.user_id}</td>
                        <td class="p-4 text-gray-300 text-xs max-w-xs truncate">${t.message}</td>
                        <td class="p-4 text-xs text-gray-500">${t.created_at || ''}</td>
                        <td class="p-4">
                            <span class="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase border ${t.status === 'closed' ? 'bg-gray-500/10 text-gray-400 border-gray-500/20' : (t.status === 'replied' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20')}">
                                ${t.status || 'open'}
                            </span>
                        </td>
                        <td class="p-4 text-right space-x-2">
                            <button onclick="openTicketReplyModal(${t.id}, ${t.user_id}, '${(t.message || '').replace(/'/g, "\\'")}')" class="px-2.5 py-1.5 bg-indigo-500/10 text-indigo-400 hover:bg-indigo-500/20 rounded-lg text-xs font-semibold border border-indigo-500/20">Reply DM</button>
                        </td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error(err);
            }
        }

        function openTicketReplyModal(ticketId, userId, message) {
            document.getElementById('ticket-id').value = ticketId;
            document.getElementById('ticket-user-info').innerText = `User Telegram ID: ${userId}`;
            document.getElementById('ticket-user-msg').innerText = `Ticket #${ticketId}: "${message}"`;
            document.getElementById('ticket-reply-text').value = '';
            document.getElementById('modal-ticket-reply').classList.remove('hidden');
        }
        function closeTicketReplyModal() { document.getElementById('modal-ticket-reply').classList.add('hidden'); }

        async function sendTicketReply() {
            const ticketId = document.getElementById('ticket-id').value;
            const replyText = document.getElementById('ticket-reply-text').value.trim();
            if (!replyText) return alert('Reply text cannot be empty');

            const res = await fetch('/api/ticket/reply', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ticket_id: parseInt(ticketId), reply_text: replyText})
            });
            const data = await res.json();
            if (data.status === 'success') {
                alert('Reply sent directly to user Telegram DM!');
                closeTicketReplyModal();
                fetchTickets();
            } else {
                alert('Error sending ticket reply: ' + (data.message || 'Unknown error'));
            }
        }

        // Reviews
        async function fetchReviews() {
            try {
                const res = await fetch('/api/reviews');
                const reviews = await res.json();
                const tbody = document.getElementById('reviews-table-body');

                if (!reviews || reviews.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-gray-500">No user reviews submitted yet.</td></tr>';
                    return;
                }

                tbody.innerHTML = reviews.map(r => `
                    <tr class="hover:bg-white/[0.02] transition">
                        <td class="p-4 font-semibold text-white">${r.first_name}</td>
                        <td class="p-4 font-medium text-indigo-300">${r.product_name}</td>
                        <td class="p-4 font-bold text-amber-400">${'⭐'.repeat(r.rating || 5)}</td>
                        <td class="p-4 text-xs text-gray-300 max-w-xs">${r.comment || '<i>No comment</i>'}</td>
                        <td class="p-4 text-xs text-gray-500">${r.created_at || ''}</td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error(err);
            }
        }

        // Coupons
        async function fetchCoupons() {
            try {
                const res = await fetch('/api/coupons');
                const coupons = await res.json();
                const tbody = document.getElementById('coupons-table-body');

                if (!coupons || coupons.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-gray-500">No promo coupons created yet.</td></tr>';
                    return;
                }

                tbody.innerHTML = coupons.map(c => `
                    <tr class="hover:bg-white/[0.02] transition">
                        <td class="p-4 font-bold font-mono text-indigo-400">${c.code}</td>
                        <td class="p-4 font-semibold text-emerald-400">${c.discount_percent}%</td>
                        <td class="p-4 font-semibold text-emerald-400">$${c.flat_discount.toFixed(2)}</td>
                        <td class="p-4 text-gray-300">${c.uses_count} / ${c.max_uses === -1 ? '♾️' : c.max_uses}</td>
                        <td class="p-4 text-right">
                            <button onclick="deleteCoupon(${c.id})" class="px-2.5 py-1.5 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20 rounded-lg text-xs font-semibold border border-rose-500/20">Delete</button>
                        </td>
                    </tr>
                `).join('');
            } catch (err) {
                console.error(err);
            }
        }

        function openCouponModal() {
            document.getElementById('coupon-code').value = '';
            document.getElementById('coupon-discount-percent').value = '0';
            document.getElementById('coupon-flat-discount').value = '0.00';
            document.getElementById('coupon-max-uses').value = '-1';
            document.getElementById('modal-coupon').classList.remove('hidden');
        }
        function closeCouponModal() { document.getElementById('modal-coupon').classList.add('hidden'); }

        async function saveCoupon() {
            const data = {
                code: document.getElementById('coupon-code').value.trim(),
                discount_percent: parseInt(document.getElementById('coupon-discount-percent').value),
                flat_discount: parseFloat(document.getElementById('coupon-flat-discount').value),
                max_uses: parseInt(document.getElementById('coupon-max-uses').value)
            };
            if (!data.code) return alert('Enter coupon code');

            const res = await fetch('/api/coupon/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(data)
            });
            const resData = await res.json();
            if (resData.status === 'success') {
                closeCouponModal();
                fetchCoupons();
            } else {
                alert('Error creating coupon: ' + resData.message);
            }
        }

        async function deleteCoupon(id) {
            if (!confirm('Are you sure you want to delete this coupon?')) return;
            const res = await fetch('/api/coupon/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id})
            });
            const data = await res.json();
            if (data.status === 'success') fetchCoupons();
            else alert('Error deleting coupon');
        }

        // Broadcast
        async function sendBroadcast() {
            const text = document.getElementById('broadcast-text').value.trim();
            if (!text) return alert('Please enter message text');
            if (!confirm('Are you sure you want to broadcast this message to ALL registered users?')) return;

            const res = await fetch('/api/broadcast', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({text})
            });
            const data = await res.json();
            if (data.status === 'success') {
                alert(`Broadcast sent successfully to ${data.sent} users!`);
                document.getElementById('broadcast-text').value = '';
            } else {
                alert('Broadcast failed: ' + data.message);
            }
        }

        async function enhanceBroadcast() {
            const textarea = document.getElementById('broadcast-text');
            const text = textarea.value.trim();
            if (!text) return alert('Please enter message text first');

            const btn = document.getElementById('enhance-broadcast-btn');
            btn.disabled = true;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><span>Enhancing...</span>';

            try {
                const res = await fetch('/api/ai/enhance_broadcast', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text})
                });
                const data = await res.json();
                if (data.status === 'success') {
                    textarea.value = data.enhanced_text;
                } else {
                    alert('AI enhancement failed: ' + data.message);
                }
            } catch (err) {
                alert('Error connecting to AI service');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i><span>Enhance with AI</span>';
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
                    if (key === 'GEMINI_API_KEY') desc = 'Google Gemini AI API key for store analysis and insights';
                    else if (key === 'CRYPTOMUS_MERCHANT_UUID') desc = 'Cryptomus Merchant ID for receiving payments';
                    else if (key === 'CRYPTOMUS_API_KEY') desc = 'Cryptomus Payment API Key';
                    else if (key === 'USDT_TRC20_ADDRESS') desc = 'Wallet Address for manual USDT TRC20 payments';
                    else if (key === 'USDT_BEP20_ADDRESS') desc = 'Wallet Address for manual USDT BEP20 payments';
                    else if (key === 'BINANCE_PAY_ID') desc = 'Binance Pay merchant / ID for payments';
                    else if (key === 'REFERRAL_REWARD') desc = 'Balance reward given to referrers when their friend buys ($)';
                    else if (key === 'REQUIRED_CHANNEL') desc = 'Required Telegram channel username (e.g. @grokkkmet)';
                    else if (key === 'STRICT_CHANNEL_CHECK') desc = 'Enforce mandatory channel membership check (True/False)';
                    else if (key === 'CASHBACK_PERCENT') desc = 'Loyalty cashback percentage on completed orders (e.g. 0.05 for 5%)';

                    return `
                        <div class="space-y-1">
                            <label class="text-[11px] font-bold uppercase tracking-wider text-gray-400">${key.replace(/_/g, ' ')}</label>
                            <input type="text" id="setting-${key}" value="${settings[key]}" class="w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-indigo-500 transition">
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
                alert("System configuration updated successfully!");
                fetchSettings();
            } else {
                alert("Failed to update configuration");
            }
        }

        window.addEventListener('load', () => {
            fetchStats();
            fetchActivity();

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
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        total_revenue = conn.execute(
            "SELECT SUM(total_price) FROM orders WHERE status='paid' OR status='delivered'"
        ).fetchone()[0] or 0.0

        today_sales = conn.execute(
            "SELECT SUM(total_price) FROM orders WHERE (status='paid' OR status='delivered') AND date(created_at) = date('now')"
        ).fetchone()[0] or 0.0

        total_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE status='paid' OR status='delivered'"
        ).fetchone()[0]

        total_stock = conn.execute(
            "SELECT SUM(stock) FROM products WHERE stock != -1"
        ).fetchone()[0] or 0

        low_stock_alerts = conn.execute(
            "SELECT COUNT(*) FROM products WHERE stock >= 0 AND stock < 5"
        ).fetchone()[0]

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
            "today_sales": today_sales,
            "total_orders": total_orders,
            "total_stock": total_stock,
            "low_stock_alerts": low_stock_alerts,
            "chart_data": {
                "dates": dates,
                "values": values
            }
        })
    finally:
        conn.close()


@app.route("/api/ai/analyze", methods=["POST"])
def api_ai_analyze():
    gemini_key = get_env_var("GEMINI_API_KEY", "")
    if not gemini_key:
        return jsonify({"status": "error", "message": "Gemini API key not found"}), 400

    conn = get_db_connection()
    try:
        users_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        revenue = conn.execute("SELECT SUM(total_price) FROM orders WHERE status='paid' OR status='delivered'").fetchone()[0] or 0.0
        orders_count = conn.execute("SELECT COUNT(*) FROM orders WHERE status='paid' OR status='delivered'").fetchone()[0]
        low_stock = conn.execute("SELECT name, stock FROM products WHERE stock >= 0 AND stock < 5").fetchall()
        top_products = conn.execute("SELECT name, price, stock FROM products LIMIT 5").fetchall()
    finally:
        conn.close()

    stock_summary = ", ".join([f"{r['name']} ({r['stock']} left)" for r in low_stock]) if low_stock else "All products healthy"
    prod_summary = ", ".join([f"{r['name']} ($ {r['price']:.2f})" for r in top_products])

    prompt_text = (
        f"You are an expert e-commerce and Telegram bot business strategist AI for GeminiStore.\n"
        f"Analyze our current live store performance metrics and give concise, high-impact advice:\n\n"
        f"- Total Customers: {users_count}\n"
        f"- Total Revenue: ${revenue:.2f} USD\n"
        f"- Total Completed Orders: {orders_count}\n"
        f"- Low Stock Alerts: {stock_summary}\n"
        f"- Catalog Products: {prod_summary}\n\n"
        f"Format your analysis clearly with sections:\n"
        f"1. **Store Health & Performance Summary**\n"
        f"2. **Revenue & Pricing Optimization (Remise Strategy)**\n"
        f"3. **Urgent Inventory & Replenishment Actions**\n"
        f"4. **High-Converting Broadcast Campaign Idea**"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={gemini_key}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt_text}]}]
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ai_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return jsonify({"status": "success", "analysis": ai_text})
    except Exception as e:
        logger.error(f"Error calling Gemini AI API: {e}")
        # Fallback intelligent rule-based analysis if API fails
        fallback_text = (
            f"**1. Store Health Summary**\n"
            f"• Total Customers: **{users_count}** | Revenue: **${revenue:.2f}** | Total Orders: **{orders_count}**\n\n"
            f"**2. Revenue & Pricing Optimization (Remise Strategy)**\n"
            f"• Enable $0.70 bulk remise for orders of 10+ items to accelerate volume sales.\n"
            f"• Reward loyal customers with top-up bonuses to increase average order value.\n\n"
            f"**3. Urgent Inventory Actions**\n"
            f"• Status: {stock_summary}. Replenish stock to avoid lost sales.\n\n"
            f"**4. High-Converting Campaign Idea**\n"
            f"• Run a 2-Hour Flash Sale announcement offering $0.70 unit price for bulk orders!"
        )
        return jsonify({"status": "success", "analysis": fallback_text})


@app.route("/api/ai/enhance_broadcast", methods=["POST"])
def api_ai_enhance_broadcast():
    gemini_key = get_env_var("GEMINI_API_KEY")
    if not gemini_key:
        return jsonify({"status": "error", "message": "Gemini API key not found"}), 400

    draft_text = (request.json or {}).get("text", "").strip()
    if not draft_text:
        return jsonify({"status": "error", "message": "Message text is empty"}), 400

    prompt_text = (
        "You are an expert marketing copywriter for a Telegram store bot called GeminiStore.\n"
        "Rewrite the broadcast announcement below to be more persuasive and high-converting: "
        "add urgency, relevant emojis, and a clear call to action. "
        "Keep it concise (under 800 characters). "
        "Preserve any existing Telegram HTML tags (<b>, <i>, <u>, <a>) and add more where it helps emphasis. "
        "Reply with ONLY the rewritten message text, no explanations or preamble.\n\n"
        f"Original message:\n{draft_text}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={gemini_key}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt_text}]}]
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            enhanced_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return jsonify({"status": "success", "enhanced_text": enhanced_text})
    except Exception as e:
        logger.error(f"Error calling Gemini AI API for broadcast enhancement: {e}")
        return jsonify({"status": "error", "message": "AI enhancement failed, please try again"}), 502


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


@app.route("/api/category/add", methods=["POST"])
def category_add():
    data = request.json
    name = data["name"].strip()
    emoji = data.get("emoji", "📁").strip()

    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO categories (name, emoji) VALUES (?, ?)", (name, emoji))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error adding category: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/category/edit", methods=["POST"])
def category_edit():
    data = request.json
    c_id = int(data["id"])
    name = data["name"].strip()
    emoji = data.get("emoji", "📁").strip()

    conn = get_db_connection()
    try:
        conn.execute("UPDATE categories SET name=?, emoji=? WHERE id=?", (name, emoji, c_id))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error editing category: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/category/delete", methods=["POST"])
def category_delete():
    data = request.json
    c_id = int(data["id"])

    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM categories WHERE id=?", (c_id,))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error deleting category: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
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


@app.route("/api/product/add", methods=["POST"])
def product_add():
    data = request.json
    name = data["name"]
    description = data.get("description", "")
    price = float(data["price"])
    stock = int(data["stock"])
    emoji = data.get("emoji", "📦")
    category_id = int(data["category_id"])
    tier_prices = data.get("tier_prices", "")
    image_url = data.get("image_url", "")

    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO products (name, description, price, stock, emoji, category_id, tier_prices, image_url)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, description, price, stock, emoji, category_id, tier_prices, image_url)
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
    tier_prices = data.get("tier_prices", "")

    image_url = data.get("image_url", "")

    conn = get_db_connection()
    try:
        conn.execute(
            """UPDATE products
               SET name=?, description=?, price=?, stock=?, emoji=?, category_id=?, tier_prices=?, image_url=?
               WHERE id=?""",
            (name, description, price, stock, emoji, category_id, tier_prices, image_url, p_id)
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


@app.route("/api/inventory")
def api_inventory():
    product_id = request.args.get("product_id", type=int)
    conn = get_db_connection()
    try:
        query = """SELECT s.*, p.name as product_name 
                   FROM product_stock s
                   JOIN products p ON s.product_id = p.id"""
        params = ()
        if product_id:
            query += " WHERE s.product_id = ?"
            params = (product_id,)
        query += " ORDER BY s.id DESC LIMIT 500"
        
        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/inventory/add", methods=["POST"])
def inventory_add():
    data = request.json
    product_id = int(data["product_id"])
    stock_data = data["data"].strip()

    if not stock_data:
        return jsonify({"status": "error", "message": "Stock data cannot be empty"}), 400

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO product_stock (product_id, data) VALUES (?, ?)",
            (product_id, stock_data)
        )
        cur = conn.execute("SELECT stock FROM products WHERE id=?", (product_id,))
        p = cur.fetchone()
        if p and p["stock"] != -1:
            cur_count = conn.execute("SELECT COUNT(*) FROM product_stock WHERE product_id=? AND is_sold=0", (product_id,)).fetchone()[0]
            conn.execute("UPDATE products SET stock=? WHERE id=?", (cur_count, product_id))
        
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error adding stock: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/inventory/delete", methods=["POST"])
def inventory_delete():
    data = request.json
    s_id = int(data["id"])

    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute("SELECT product_id FROM product_stock WHERE id=?", (s_id,))
        s = cur.fetchone()
        if not s:
            return jsonify({"status": "error", "message": "Stock not found"}), 404
        product_id = s["product_id"]

        conn.execute("DELETE FROM product_stock WHERE id=?", (s_id,))
        
        cur_prod = conn.execute("SELECT stock FROM products WHERE id=?", (product_id,))
        p = cur_prod.fetchone()
        if p and p["stock"] != -1:
            cur_count = conn.execute("SELECT COUNT(*) FROM product_stock WHERE product_id=? AND is_sold=0", (product_id,)).fetchone()[0]
            conn.execute("UPDATE products SET stock=? WHERE id=?", (cur_count, product_id))

        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error deleting stock: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/inventory/upload", methods=["POST"])
def inventory_upload():
    product_id = request.form.get("product_id", type=int)
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file part"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400
        
    if not product_id:
        return jsonify({"status": "error", "message": "Product ID required"}), 400

    conn = get_db_connection()
    try:
        content = file.read().decode('utf-8').splitlines()
        valid_lines = [line.strip() for line in content if line.strip()]
        
        if not valid_lines:
            return jsonify({"status": "error", "message": "File is empty or invalid"}), 400

        conn.execute("BEGIN IMMEDIATE")
        
        for line in valid_lines:
            conn.execute("INSERT INTO product_stock (product_id, data) VALUES (?, ?)", (product_id, line))
            
        cur = conn.execute("SELECT stock FROM products WHERE id=?", (product_id,))
        p = cur.fetchone()
        if p and p["stock"] != -1:
            cur_count = conn.execute("SELECT COUNT(*) FROM product_stock WHERE product_id=? AND is_sold=0", (product_id,)).fetchone()[0]
            conn.execute("UPDATE products SET stock=? WHERE id=?", (cur_count, product_id))
            
        conn.commit()

        # Announce restock to the public channel
        try:
            prod_row = conn.execute("SELECT name, price, stock FROM products WHERE id=?", (product_id,)).fetchone()
            if prod_row:
                remaining = prod_row["stock"]
                bot_token = get_env_var("BOT_TOKEN")
                channel = get_env_var("REQUIRED_CHANNEL", "@grokkkmet")
                restock_text = (
                    f"🆕 <b>NEW STOCK JUST DROPPED</b>⁉️\n\n"
                    f"📦 <b>{prod_row['name']}</b>\n"
                    f"🏷 <b>Price:</b> {prod_row['price']:.2f} USDT\n"
                    f"📦 <b>Available now:</b> {'♾️ Unlimited' if remaining == -1 else f'{remaining} account(s)'}\n"
                    f"✨ <b>Freshly restocked:</b> {len(valid_lines)} new account{'s' if len(valid_lines) > 1 else ''}\n\n"
                    f"⚡️ Secure your account before the stock runs out!"
                )
                if bot_token:
                    send_telegram_msg(bot_token, channel, restock_text)
        except Exception as notify_err:
            logger.warning(f"Could not send restock announcement: {notify_err}")

        return jsonify({"status": "success", "added": len(valid_lines)})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error bulk uploading stock: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/inventory/purge_sold", methods=["POST"])
def inventory_purge_sold():
    conn = get_db_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute("DELETE FROM product_stock WHERE is_sold=1")
        purged_count = cur.rowcount
        conn.commit()
        return jsonify({"status": "success", "purged_count": purged_count})
    except Exception as e:
        conn.rollback()
        logger.error(f"Error purging sold stock: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/tickets")
def api_tickets():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT t.*, u.first_name as user_name
               FROM support_tickets t
               LEFT JOIN users u ON t.user_id = u.telegram_id
               ORDER BY t.id DESC"""
        ).fetchall()
        return jsonify([dict(r) for r in rows])
    finally:
        conn.close()


@app.route("/api/ticket/reply", methods=["POST"])
def api_ticket_reply():
    data = request.json
    ticket_id = int(data["ticket_id"])
    reply_text = data["reply_text"].strip()

    token = get_env_var("BOT_TOKEN")
    if not token:
        return jsonify({"status": "error", "message": "Bot token not configured"}), 500

    conn = get_db_connection()
    try:
        cur = conn.execute("SELECT user_id FROM support_tickets WHERE id=?", (ticket_id,))
        ticket = cur.fetchone()
        if not ticket:
            return jsonify({"status": "error", "message": "Ticket not found"}), 404

        user_id = ticket["user_id"]
        msg = f"🎧 <b>Support Team Reply (Ticket #{ticket_id}):</b>\n\n{reply_text}"
        send_telegram_msg(token, user_id, msg)

        conn.execute("UPDATE support_tickets SET status='replied' WHERE id=?", (ticket_id,))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error replying to ticket: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


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


@app.route("/api/order/action", methods=["POST"])
def order_action():
    data = request.json
    order_id = int(data["order_id"])
    action = data["action"]

    conn = get_db_connection()
    try:
        conn.execute("UPDATE orders SET status = ?, updated_at = datetime('now') WHERE id = ?", (action, order_id))
        conn.commit()
        
        if action == "delivered":
            cur = conn.execute("SELECT user_id, product_id, delivery_info FROM orders WHERE id=?", (order_id,))
            o = cur.fetchone()
            if o:
                token = get_env_var("BOT_TOKEN")
                if token:
                    msg = f"📦 <b>Order #{order_id} Delivered!</b>\n\nYour product has been delivered! 🎉"
                    if o["delivery_info"]:
                        msg += f"\n\n📬 <b>Delivery Info:</b>\n<code>{o['delivery_info']}</code>"
                    send_telegram_msg(token, o["user_id"], msg)

        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error updating order state: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/broadcast", methods=["POST"])
def api_broadcast():
    data = request.json
    text = data["text"]
    token = get_env_var("BOT_TOKEN")
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


@app.route("/api/settings")
def api_settings():
    settings = {
        "GEMINI_API_KEY": get_env_var("GEMINI_API_KEY", ""),
        "CRYPTOMUS_MERCHANT_UUID": "",
        "CRYPTOMUS_API_KEY": "",
        "USDT_TRC20_ADDRESS": "",
        "USDT_BEP20_ADDRESS": "",
        "BINANCE_PAY_ID": "",
        "REFERRAL_REWARD": "1.00",
        "REQUIRED_CHANNEL": "@grokkkmet",
        "STRICT_CHANNEL_CHECK": "True",
        "CASHBACK_PERCENT": "0.05",
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


@app.route("/api/export/orders")
def export_orders_csv():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT o.id, u.first_name, u.username, p.name as product_name,
                      o.quantity, o.unit_price, o.total_price,
                      o.payment_method, o.status, o.created_at
               FROM orders o
               JOIN products p ON o.product_id = p.id
               JOIN users u ON o.user_id = u.telegram_id
               ORDER BY o.created_at DESC"""
        ).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Order ID', 'User', 'Product', 'Quantity', 'Unit Price', 'Total', 'Payment Method', 'Status', 'Date'])
        for r in rows:
            user_display = r['first_name']
            if r['username']:
                user_display += f" (@{r['username']})"
            writer.writerow([
                r['id'], user_display, r['product_name'],
                r['quantity'], f"${r['unit_price']:.2f}" if r['unit_price'] else '$0.00',
                f"${r['total_price']:.2f}", r['payment_method'],
                r['status'], r['created_at']
            ])

        csv_data = output.getvalue()
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=orders_export.csv'}
        )
    except Exception as e:
        logger.error(f"Error exporting orders CSV: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


@app.route("/api/export/users")
def export_users_csv():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT u.telegram_id, u.first_name, u.username, u.balance,
                      u.total_spent, u.membership, u.created_at, u.is_banned,
                      (SELECT COUNT(*) FROM orders WHERE user_id = u.telegram_id) as orders_count
               FROM users u
               ORDER BY u.total_spent DESC"""
        ).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Telegram ID', 'Name', 'Username', 'Balance', 'Total Spent', 'Membership', 'Orders Count', 'Joined Date', 'Status'])
        for r in rows:
            writer.writerow([
                r['telegram_id'], r['first_name'],
                f"@{r['username']}" if r['username'] else '',
                f"${r['balance']:.2f}", f"${r['total_spent']:.2f}",
                r['membership'], r['orders_count'],
                r['created_at'],
                'Banned' if r['is_banned'] else 'Active'
            ])

        csv_data = output.getvalue()
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=users_export.csv'}
        )
    except Exception as e:
        logger.error(f"Error exporting users CSV: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        conn.close()


if __name__ == "__main__":
    logger.info("⚡ Starting Control Panel with Gemini AI on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
