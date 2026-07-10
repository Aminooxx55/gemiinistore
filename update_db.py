import sqlite3
import os

db_path = "/root/gemiinistore/shop.db"
if not os.path.exists(db_path):
    db_path = "shop.db"

conn = sqlite3.connect(db_path)
try:
    c = conn.cursor()
    # Update product price to 1.38
    c.execute("UPDATE products SET price=1.38 WHERE id=2")
    conn.commit()
    print("Product price updated to 1.38 successfully!")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
