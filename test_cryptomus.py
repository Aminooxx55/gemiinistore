import sqlite3
import os

def main():
    db_path = "/root/gemiinistore/shop.db"
    if not os.path.exists(db_path):
        db_path = os.path.join(os.path.dirname(__file__), "shop.db")
    
    print("=== Categories ===")
    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute("SELECT id, name FROM categories")
        for r in c.fetchall():
            print(r)
        print("\n=== Products ===")
        c.execute("SELECT id, name FROM products")
        for r in c.fetchall():
            print(r)
    except Exception as e:
        print("Error:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    main()
