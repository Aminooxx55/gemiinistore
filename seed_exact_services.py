import sqlite3

def main():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    services = [
        ("🤖 AI Services Pack", "🤖", "⚡ Access to all top AI models & tools", 2.50, 10, "static/gemini.jpg"),
        ("🤖 Gemini Advanced 18m", "🤖", "⚡ Google AI Pro subscription for 18 Months", 0.70, 0, "static/gemini.jpg"),
        ("📚 Coursera Plus 12m", "📚", "⚡ 1 Year Coursera Plus Unlimited Access", 1.50, 15, "static/welcome_banner.png"),
        ("🛠️ Supabase Pro 12m", "🛠️", "⚡ 1 Year Supabase Pro Plan", 2.00, 0, "static/welcome_banner.png"),
        ("🔁 N8N Starter 12m", "🔁", "⚡ 1 Year N8N Cloud Starter Plan", 2.00, 23, "static/welcome_banner.png"),
        ("💡 Lovable Pro 12m", "💡", "⚡ 1 Year Lovable Pro Plan", 2.00, 35, "static/welcome_banner.png"),
    ]
    
    for name, emoji, desc, price, default_stock, img in services:
        # Search by keyword
        key = name.split()[1] if len(name.split()) > 1 else name
        cursor.execute("SELECT id FROM products WHERE name LIKE ?", (f"%{key}%",))
        row = cursor.fetchone()
        if not row:
            cursor.execute(
                """INSERT INTO products 
                (name, emoji, description, price, stock, sold, is_free, is_active, image_url)
                VALUES (?, ?, ?, ?, ?, 0, 0, 1, ?)""",
                (name, emoji, desc, price, default_stock, img)
            )
        else:
            cursor.execute(
                "UPDATE products SET name=?, emoji=?, description=?, is_active=1 WHERE id=?",
                (name, emoji, desc, row[0])
            )
            
    conn.commit()
    conn.close()
    print("Exact 6 services seeded successfully!")

if __name__ == "__main__":
    main()
