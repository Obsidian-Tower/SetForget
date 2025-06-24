#!/usr/bin/env python3
"""
prune_and_cancel_excess_bands.py

For each symbol in CONFIG:
  • Fetch current price
  • Count active bands (status != 'completed' AND buy_price < current price)
  • If count > bands, cancel & delete the lowest-price excess bands
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
    "ETH/USDT": {"grid_file":"ETH-USDT-06.csv","usd_per_order":10,"bands":1},
    "BTC/USDT": {"grid_file":"BTC-USDT-05.csv","usd_per_order":10,"bands":1},
    "DOGE/USDT":{"grid_file":"DOGE-USDT-10.csv","usd_per_order":10,"bands":1},
    "UNI/USDT": {"grid_file":"UNI-USDT-10.csv","usd_per_order":10,"bands":1},
    "SOL/USDT": {"grid_file":"SOL-USDT-10.csv","usd_per_order":10,"bands":1},
    "XRP/USDT": {"grid_file":"XRP-USDT-10.csv","usd_per_order":10,"bands":1},
    "SHIB/USDT":{"grid_file":"SHIB-USDT-10.csv","usd_per_order":10,"bands":1},
    "ADA/USDT":{"grid_file":"ADA-USDT-06.csv","usd_per_order":10,"bands":1},
    "LINK/USDT":{"grid_file":"LINK-USDT-10.csv","usd_per_order":10,"bands":1},
    "DOT/USDT":{"grid_file":"DOT-USDT-11.csv","usd_per_order":10,"bands":1},
    "LTC/USDT":{"grid_file":"LTC-USDT-08.csv","usd_per_order":10,"bands":1},
    "AAVE/USDT": {"grid_file":"AAVE-USDT-12.csv","usd_per_order":10,"bands":1},
    "BNB/USDT": {"grid_file":"BNB-USDT-04.csv","usd_per_order":10,"bands":1},
    "FET/USDT": {"grid_file":"FET-USDT-10.csv","usd_per_order":10,"bands":1},
    "OP/USDT": {"grid_file":"OP-USDT-10.csv","usd_per_order":10,"bands":1},
    "ARB/USDT": {"grid_file":"ARB-USDT-06.csv","usd_per_order":10,"bands":1},
    "CRV/USDT": {"grid_file":"CRV-USDT-10.csv","usd_per_order":14,"bands":1},
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

def prune_and_cancel(conn, symbol, max_bands):
    # 1) Fetch current market price
    ticker = exchange.fetch_ticker(symbol)
    price = float(ticker["last"])
    log.info(f"{symbol} ⇒ Current price: {price:.6f}")

    cur = conn.cursor()
    # 2) Select active bands under current price
    cur.execute(f"""
        SELECT rowid, buy_order_id, buy_price
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
        for rowid, order_id, buy_price in to_prune:
            # 3) Cancel the order on Binance
            try:
                exchange.cancel_order(order_id, symbol)
                log.info(f"  ⚠️ Canceled order {order_id} at buy@{buy_price:.6f}")
            except Exception as e:
                log.error(f"  ❌ Failed to cancel {order_id}: {e}")

            # 4) Delete the row from the database
            cur.execute(f"DELETE FROM {TABLE} WHERE rowid = ?", (rowid,))
            log.info(f"  ➖ Removed DB row {rowid} (buy@{buy_price:.6f})")

            # rate-limit safety
            time.sleep(0.2)

        conn.commit()
        log.info(f"  ✅ Pruned {excess} excess band(s).")
    else:
        log.info("  ✅ No pruning needed.")

def main():
    conn = sqlite3.connect(DB_PATH)
    try:
        for sym, cfg in CONFIG.items():
            if sym not in exchange.symbols:
                log.warning(f"Skipping {sym}: not on exchange")
                continue
            log.info(f"--- Processing {sym} ---")
            prune_and_cancel(conn, sym, cfg["bands"])
    finally:
        conn.close()
        log.info("Database connection closed.")

if __name__ == "__main__":
    main()
