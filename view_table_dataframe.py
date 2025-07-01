import sqlite3
import pandas as pd

# Optional: pip install tabulate
try:
    from tabulate import tabulate
    USE_TABULATE = True
except ImportError:
    USE_TABULATE = False

# Path to your local DB file
db_path = "gridbot_pairs.sqlite3"

# Connect to the database
conn = sqlite3.connect(db_path)

# Load specific columns from active rows, parsing timestamps
df = pd.read_sql_query(
    """
    SELECT symbol,
           buy_order_submitted,
           buy_order_filled,
           buy_cost,
           buy_price,
           sell_order_submitted,
           sell_price,
           sell_cost,
           status
      FROM grid_pairs
     WHERE status != 'completed'
    """,
    conn,
    parse_dates=["buy_order_submitted", "buy_order_filled", "sell_order_submitted"]
)

# Close DB connection
conn.close()

# Sort by symbol and buy_order_submitted
df = df.sort_values(by=["symbol", "buy_order_submitted"], ascending=[True, True])

# Print concise view
if df.empty:
    print("No active records found in 'grid_pairs'.")
else:
    print("\n📊 Current grid_pairs summary:\n")
    if USE_TABULATE:
        print(tabulate(df, headers="keys", tablefmt="psql", showindex=False))
    else:
        print(df.to_string(index=False))
