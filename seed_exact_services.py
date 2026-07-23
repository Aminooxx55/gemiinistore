import sqlite3

def main():
    conn = sqlite3.connect('shop.db')
    cursor = conn.cursor()
    
    services = [
        ("AI Services Pack", "🤖", "⚡ Access to all top AI models & tools", 2.50, 10, "static/aiservices_banner.jpg"),
        ("Gemini Advanced 18m", "🤖", "⚡ Google AI Pro subscription for 18 Months", 0.70, 0, "static/gemini_banner.jpg"),
        ("Coursera Plus 12m", "📚", "⚡ 1 Year Coursera Plus Unlimited Access", 1.50, 15, "static/coursera_banner.jpg"),
        ("Supabase Pro 12m", "🛠️", "⚡ 1 Year Supabase Pro Plan", 2.00, 0, "static/supabase_banner.jpg"),
        ("N8N Starter 12m", "🔁", "⚡ 1 Year N8N Cloud Starter Plan", 2.00, 23, "static/n8n_banner.jpg"),
        ("Lovable Pro 12m", "💡", "⚡ 1 Year Lovable Pro Plan", 2.00, 35, "static/lovable_banner.jpg"),
    ]
    
    for name, emoji, desc, price, default_stock, img in services:
        key = name.split()[0]
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
                "UPDATE products SET name=?, emoji=?, description=?, image_url=?, is_active=1 WHERE id=?",
                (name, emoji, desc, img, row[0])
            )
            
    conn.commit()
    conn.close()
    print("Exact 6 services seeded with clean names and logo icons!")

if __name__ == "__main__":
    main()

