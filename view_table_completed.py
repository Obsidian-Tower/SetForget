import sqlite3
import pandas as pd
from datetime import timedelta

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

# Load only completed rows
df = pd.read_sql_query(
    """
    SELECT *
      FROM grid_pairs
     WHERE status = 'completed'
    """,
    conn,
    parse_dates=["buy_submitted"]
)

conn.close()

# Sort by symbol, then buy_submitted
df = df.sort_values(by=["symbol", "buy_submitted"], ascending=[True, True])

# Print table
if df.empty:
    print("No completed records found in 'grid_pairs'.")
else:
    print("\n✅ Completed grid_pairs (sorted by symbol, buy_submitted):\n")
    if USE_TABULATE:
        print(tabulate(df, headers="keys", tablefmt="psql", showindex=False))
    else:
        print(df.to_string(index=False))

    # Overall average per 24 hours
    start = df["buy_submitted"].min()
    end = df["buy_submitted"].max()
    duration_days = (end - start).total_seconds() / (24 * 3600)

    if duration_days > 0:
        avg_total = len(df) / duration_days
        print(f"\n📈 Overall average completed bands per 24 hours: {avg_total:.2f}")

        # Per-symbol average trades per day
        token_stats = (
            df.groupby("symbol")
              .size()
              .reset_index(name="total_trades")
              .sort_values("total_trades", ascending=False)
        )
        token_stats["avg_per_day"] = token_stats["total_trades"] / duration_days
        print(f"\n📦 Total completed trades (all time): {len(df)}")
        print("\n📊 Average completed bands per token per 24 hours:\n")
        if USE_TABULATE:
            print(tabulate(token_stats, headers="keys", tablefmt="psql", showindex=False))
        else:
            print(token_stats.to_string(index=False))
    else:
        print("\n📈 Not enough time range to compute daily average.")
