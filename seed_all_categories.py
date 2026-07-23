import sqlite3

def main():
    conn = sqlite3.connect('shop.db')
    categories = [
        ("🤖 Gemini Advanced", "🤖"),
        ("📚 Coursera", "📚"),
        ("🛠️ Supabase", "🛠️"),
        ("🔁 N8N", "🔁"),
        ("💡 Lovable", "💡"),
    ]
    for name, emoji in categories:
        conn.execute(
            "INSERT OR IGNORE INTO categories (name, emoji, is_active) VALUES (?, ?, 1)",
            (name, emoji)
        )
    conn.commit()

    cur = conn.execute("SELECT id FROM categories WHERE name LIKE '%Gemini%' OR name LIKE '%AI%' LIMIT 1")
    row = cur.fetchone()
    if row:
        conn.execute("UPDATE products SET category_id=? WHERE id=14", (row[0],))
        conn.commit()

    conn.close()
    print("Categories seeded successfully!")

if __name__ == "__main__":
    main()
