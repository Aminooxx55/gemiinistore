import sqlite3
import os

db_path = "/root/gemiinistore/shop.db"
if not os.path.exists(db_path):
    db_path = "shop.db"

conn = sqlite3.connect(db_path)
try:
    c = conn.cursor()
    # Update category 1 name to Gemini
    c.execute("UPDATE categories SET name='Gemini' WHERE id=1")
    # Update product 2 name to Google AI Pro 18 Months
    c.execute("UPDATE products SET name='Google AI Pro 18 Months' WHERE id=2")
    conn.commit()
    print("Database names updated successfully!")
except Exception as e:
    print("Error:", e)
finally:
    conn.close()
