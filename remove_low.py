#!/usr/bin/env python3
import sqlite3

# ─── CONFIG ─────────────────────────────────────────────────────────────────────
DB_PATH = "gridbot_pairs.sqlite3"

# ─── FUNCTION TO DELETE ROWS ────────────────────────────────────────────────────
def remove_sol_orders(db_path, symbol="SOL/USDT", price_threshold=129):
    """
    Connects to the given SQLite database and deletes all rows in `grid_pairs`
    where symbol matches `symbol` and buy_price is below `price_threshold`.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Count matching rows
    cursor.execute(
        "SELECT COUNT(*) FROM grid_pairs WHERE symbol = ? AND buy_price < ?",
        (symbol, price_threshold)
    )
    count = cursor.fetchone()[0]
    print(f"🔴 Deleting {count} row(s) where symbol = '{symbol}' and buy_price < {price_threshold}")
    # Perform deletion
    cursor.execute(
        "DELETE FROM grid_pairs WHERE symbol = ? AND buy_price < ?",
        (symbol, price_threshold)
    )
    conn.commit()
    conn.close()
    print("✅ Deletion complete.")

# ─── MAIN EXECUTION ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    remove_sol_orders(DB_PATH)
