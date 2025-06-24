#!/usr/bin/env python3
import sqlite3

def delete_bnb_ready_to_sell():
    db_path = "gridbot_pairs.sqlite3"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Preview count before deletion
    cursor.execute("""
        SELECT COUNT(*) FROM grid_pairs
         WHERE symbol = 'BTC/USDT' AND status = 'ready_to_sell'
    """)
    count = cursor.fetchone()[0]
    print(f"Found {count} BNB/USDT rows with status 'ready_to_sell'.")

    if count > 0:
        confirm = input("Delete these rows? Type 'yes' to confirm: ")
        if confirm.strip().lower() == 'yes':
            cursor.execute("""
                DELETE FROM grid_pairs
                 WHERE symbol = 'BTC/USDT' AND status = 'ready_to_sell'
            """)
            conn.commit()
            print("✅ Rows deleted.")
        else:
            print("❌ Deletion aborted.")
    else:
        print("✅ No matching rows to delete.")

    conn.close()

if __name__ == "__main__":
    delete_bnb_ready_to_sell()
