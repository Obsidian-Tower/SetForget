#!/usr/bin/env python3
"""
add_fee_currency_columns.py

This script connects to the `gridbot_pairs.sqlite3` database and ensures that
the table `grid_pairs` has the columns:
  - buy_maker_fee_currency TEXT
  - sell_maker_fee_currency TEXT

If either column is missing, it will be added via ALTER TABLE.
"""

import sqlite3

DB_PATH = "gridbot_pairs.sqlite3"
TABLE_NAME = "grid_pairs"
COLUMNS_TO_ADD = [
    ("buy_maker_fee_currency", "TEXT"),
    ("sell_maker_fee_currency", "TEXT"),
]

def get_existing_columns(conn, table):
    """Return a set of column names existing in the given table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}  # row[1] is column name

def add_missing_columns(db_path, table, columns):
    conn = sqlite3.connect(db_path)
    existing = get_existing_columns(conn, table)
    for col_name, col_type in columns:
        if col_name in existing:
            print(f"✔ Column '{col_name}' already exists, skipping.")
        else:
            sql = f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"
            conn.execute(sql)
            print(f"➕ Added column: {col_name} {col_type}")
    conn.commit()
    conn.close()
    print("✅ Schema migration complete.")

if __name__ == "__main__":
    add_missing_columns(DB_PATH, TABLE_NAME, COLUMNS_TO_ADD)
