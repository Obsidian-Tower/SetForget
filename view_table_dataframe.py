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

# Load the table into a DataFrame, parsing the buy_submitted column as datetime
df = pd.read_sql_query(
    """
    SELECT *
      FROM grid_pairs
     WHERE status != 'completed'
    """,
    conn,
    parse_dates=["buy_submitted"]
)

# Close DB connection
conn.close()

# Sort by symbol, then by buy_submitted timestamp
df = df.sort_values(by=["symbol", "buy_submitted"], ascending=[True, True])

# Nice console print
if df.empty:
    print("No records found in 'grid_pairs'.")
else:
    print("\n📊 Current grid_pairs table (sorted by symbol, buy_submitted):\n")
    if USE_TABULATE:
        # pretty print via tabulate
        print(tabulate(df, headers="keys", tablefmt="psql", showindex=False))
    else:
        # fallback to pandas default
        print(df.to_string(index=False))
