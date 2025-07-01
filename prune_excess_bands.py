#!/usr/bin/env python3
"""
prune_and_cancel_excess_bands.py

For each symbol in CONFIG:
  • Fetch current price
  • Count active bands (status != 'completed' AND buy_price < current price)
  • If more than 1 band, cancel & delete the lowest-price excess bands
"""

import os
import socket
import time
import logging
import sqlite3
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
CONFIG = {
    "ETH/USDT":  {"grid_file": "ETH-USDT-06.csv"},
    "BTC/USDT":  {"grid_file": "BTC-USDT-05.csv"},
    "DOGE/USDT": {"grid_file": "DOGE-USDT-10.csv"},
    "UNI/USDT":  {"grid_file": "UNI-USDT-10.csv"},
    "SOL/USDT":  {"grid_file": "SOL-USDT-10.csv"},
    "XRP/USDT":  {"grid_file": "XRP-USDT-10.csv"},
    "SHIB/USDT": {"grid_file": "SHIB-USDT-10.csv"},
    "ADA/USDT":  {"grid_file": "ADA-USDT-06.csv"},
    "LINK/USDT": {"grid_file": "LINK-USDT-10.csv"},
    "DOT/USDT":  {"grid_file": "DOT-USDT-11.csv"},
    "LTC/USDT":  {"grid_file": "LTC-USDT-08.csv"},
    "AAVE/USDT": {"grid_file": "AAVE-USDT-12.csv"},
    "BNB/USDT":  {"grid_file": "BNB-USDT-04.csv"},
    "FET/USDT":  {"grid_file": "FET-USDT-10.csv"},
    "OP/USDT":   {"grid_file": "OP-USDT-10.csv"},
    "ARB/USDT":  {"grid_file": "ARB-USDT-06.csv"},
    "CRV/USDT":  {"grid_file": "CRV-USDT-10.csv"},
}
DB_PATH = "gridbot_pairs.sqlite3"
TABLE   = "grid_pairs"

# ─── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("prune_and_cancel.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("prune_and_cancel")

# ─── EXCHANGE INIT ─────────────────────────────────────────────────────────────
exchange = ccxt.binanceus({
    "apiKey":          API_KEY,
    "secret":          API_SECRET,
    "enableRateLimit": True,
})
exchange.load_markets()

# ─── PRUNE FUNCTION ────────────────────────────────────────────────────────────
def prune_and_cancel(conn, symbol):
    max_bands = 1  # Always keep only 1 band under current price

    # 1) Fetch current market price
    ticker = exchange.fetch_ticker(symbol)
    price = float(ticker["last"])
    log.info(f"{symbol} ⇒ Current price: {price:.6f}")

    cur = conn.cursor()
    # 2) Select active bands under current price
    cur.execute(f"""
        SELECT id, buy_order_id, buy_price
          FROM {TABLE}
         WHERE symbol = ?
           AND status != 'completed'
           AND buy_price < ?
         ORDER BY buy_price ASC
    """, (symbol, price))
    rows = cur.fetchall()

    total = len(rows)
    excess = total - max_bands
    log.info(f"{symbol} ⇒ {total} active bands under price (limit {max_bands})")

    if excess > 0:
        to_prune = rows[:excess]
        for record_id, order_id, buy_price in to_prune:
            # 3) Cancel the order on Binance
            try:
                exchange.cancel_order(order_id, symbol)
                log.info(f"  ⚠️ Canceled order {order_id} at buy@{buy_price:.6f}")
            except Exception as e:
                log.error(f"  ❌ Failed to cancel {order_id}: {e}")

            # 4) Delete the row from the database
            cur.execute(f"DELETE FROM {TABLE} WHERE id = ?", (record_id,))
            log.info(f"  ➖ Removed DB row {record_id} (buy@{buy_price:.6f})")

            # rate-limit safety
            time.sleep(0.2)

        conn.commit()
        log.info(f"  ✅ Pruned {excess} excess band(s).")
    else:
        log.info("  ✅ No pruning needed.")

# ─── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        for sym in CONFIG.keys():
            if sym not in exchange.symbols:
                log.warning(f"Skipping {sym}: not on exchange")
                continue
            log.info(f"--- Processing {sym} ---")
            prune_and_cancel(conn, sym)
    finally:
        conn.close()
        log.info("Database connection closed.")

if __name__ == "__main__":
    main()
