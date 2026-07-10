import sqlite3
import os

def main():
    db_path = "/root/gemiinistore/shop.db"
    if not os.path.exists(db_path):
        db_path = os.path.join(os.path.dirname(__file__), "shop.db")

    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    try:
        c = conn.cursor()
        c.execute("UPDATE products SET image_url='http://134.122.112.90:5000/static/product_banner.png' WHERE id=2")
        conn.commit()
        print("Success: Updated product 2 image_url in shop.db!")
    except Exception as e:
        print(f"Error updating product: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
