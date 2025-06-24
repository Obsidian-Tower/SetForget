#!/usr/bin/env python3
"""
cancel_and_prune_buys.py

This script connects to Binance via CCXT and your `gridbot_pairs.sqlite3` database,
then for ETH/USDT and BTC/USDT:
  1. Fetches all open BUY orders on Binance.
  2. Cancels each buy order on Binance.
  3. Deletes corresponding rows in the `grid_pairs` database table.

Usage:
  chmod +x cancel_and_prune_buys.py
  ./cancel_and_prune_buys.py
"""

import os
import socket
import logging
import sqlite3
import time
from datetime import datetime

import ccxt
from dotenv import load_dotenv

# ─── FORCE IPv4 ────────────────────────────────────────────────────────────────
_orig_getaddrinfo = socket.getaddrinfo
def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _getaddrinfo_ipv4

# ─── ENVIRONMENT ───────────────────────────────────────────────────────────────
load_dotenv()
API_KEY    = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# ─── CONFIG ─────────────────────────────────────────────────────────────────────
SYMBOLS = ["ETH/USDT", "BTC/USDT","DOGE/USDT","UNI/USDT","SOL/USDT","XRP/USDT","SHIB/USDT","ADA/USDT","LINK/USDT","DOT/USDT","LTC/USDT","AAVE/USDT","BNB/USDT","FET/USDT","OP/USDT","ARB/USDT","CRV/USDT"]
DB_PATH = "gridbot_pairs.sqlite3"
TABLE   = "grid_pairs"

# ─── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("cancel_and_prune_buys.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("cancel_and_prune_buys")

# ─── EXCHANGE INIT ─────────────────────────────────────────────────────────────
exchange = ccxt.binanceus({
    "apiKey":          API_KEY,
    "secret":          API_SECRET,
    "enableRateLimit": True,
})
exchange.load_markets()

def cancel_and_delete(symbol, conn):
    log.info(f"--- Processing {symbol} ---")
    # 1) Fetch open orders
    try:
        open_orders = exchange.fetch_open_orders(symbol)
    except Exception as e:
        log.error(f"Failed to fetch open orders for {symbol}: {e}")
        return

    # Filter only buy orders
    buy_orders = [o for o in open_orders if o.get("side") == "buy"]
    log.info(f"{symbol}: Found {len(buy_orders)} open BUY order(s)")

    cur = conn.cursor()
    for order in buy_orders:
        oid = order.get("id")
        price = order.get("price")
        amount = order.get("amount")
        # 2) Cancel on Binance
        try:
            exchange.cancel_order(oid, symbol)
            log.info(f"  ⚠️ Canceled Binance BUY order {oid} @ {price} qty={amount}")
        except Exception as e:
            log.error(f"  ❌ Failed to cancel order {oid}: {e}")
        # 3) Delete from database
        cur.execute(
            f"DELETE FROM {TABLE} WHERE symbol=? AND buy_order_id=?",
            (symbol, oid)
        )
        log.info(f"  ➖ Deleted DB row for buy_order_id={oid}")
        # Rate-limit safety
        time.sleep(0.2)

    conn.commit()
    log.info(f"{symbol}: Cancellation and pruning complete.\n")

def main():
    # Connect to DB
    conn = sqlite3.connect(DB_PATH)
    try:
        for sym in SYMBOLS:
            if sym not in exchange.symbols:
                log.warning(f"Skipping {sym}: not listed on exchange")
                continue
            cancel_and_delete(sym, conn)
    finally:
        conn.close()
        log.info("Database connection closed.")

if __name__ == "__main__":
    main()
