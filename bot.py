#!/usr/bin/env python3
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
    "CRV/USDT": {"grid_file":"CRV-USDT-10.csv","usd_per_order":10,"bands":1},
}

# ─── LOGGING ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler("gridbot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("gridbot")

# ─── EXCHANGE INIT ─────────────────────────────────────────────────────────────
exchange = ccxt.binanceus({
    "apiKey":          API_KEY,
    "secret":          API_SECRET,
    "enableRateLimit": True,
})
markets = exchange.load_markets()

# ─── DB INIT ───────────────────────────────────────────────────────────────────
DB = sqlite3.connect("gridbot_pairs.sqlite3", check_same_thread=False)
DB.execute("""
CREATE TABLE IF NOT EXISTS grid_pairs (
    symbol                    TEXT,
    buy_price                 REAL,
    sell_price                REAL,
    qty                       REAL,
    buy_order_id              TEXT,
    buy_submitted             TIMESTAMP,
    buy_filled                TIMESTAMP,
    buy_exchange_price        REAL,
    buy_maker_fee             REAL,
    buy_maker_fee_currency    TEXT,
    buy_net_real              REAL,
    sell_order_id             TEXT,
    sell_submitted            TIMESTAMP,
    sell_filled               TIMESTAMP,
    sell_exchange_price       REAL,
    sell_maker_fee            REAL,
    sell_maker_fee_currency   TEXT,
    sell_net_real             REAL,
    status                    TEXT
)
""")
DB.commit()

# ─── HELPERS ───────────────────────────────────────────────────────────────────
def load_price_grid(path):
    with open(path, newline="") as f:
        prices = sorted(float(line.strip()) for line in f if line.strip())
    return list(reversed([(prices[i], prices[i+1]) for i in range(len(prices)-1)]))

def get_price(sym):
    return float(exchange.fetch_ticker(sym)["last"])

def submit_buy_pair(sym, buy_price, sell_price, qty):
    log.info(f"▶️ ATTEMPT BUY {sym}: qty={qty} @ buy@{buy_price}")
    o = exchange.create_limit_buy_order(sym, qty, buy_price)
    DB.execute("""
        INSERT INTO grid_pairs(
           symbol, buy_price, sell_price, qty,
           buy_order_id, buy_submitted, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'waiting')
    """, (sym, buy_price, sell_price, qty, o["id"], datetime.utcnow()))
    DB.commit()
    log.info(
        f"✅ BUY PLACED {sym}: qty={qty} "
        f"$~{round(qty*buy_price,2)} buy@{buy_price} (id={o['id']})"
    )

def submit_sell_pair(sym, r, qty):
    sell_price = r["sell_price"]
    log.info(f"▶️ ATTEMPT SELL {sym}: qty={qty} @ sell@{sell_price}")
    o = exchange.create_limit_sell_order(sym, qty, sell_price)
    DB.execute("""
        UPDATE grid_pairs
           SET sell_order_id=?, sell_submitted=?, status='holding'
         WHERE buy_order_id=?
    """, (o["id"], datetime.utcnow(), r["buy_order_id"]))
    DB.commit()
    log.info(
        f"✅ SELL PLACED {sym}: qty={qty} "
        f"$~{round(qty*sell_price,2)} sell@{sell_price} (id={o['id']})"
    )

def check_fills_for_symbol(sym, cfg):
    # --- log current open orders ---
    open_orders = exchange.fetch_open_orders(sym)
    if open_orders:
        items = [
            f"{o['side']}@{o['price']} qty={o['amount']} id={o['id']}"
            for o in open_orders
        ]
        log.info(f"{sym} 🔍 OPEN ORDERS: {'; '.join(items)}")
    else:
        log.info(f"{sym} 🔍 OPEN ORDERS: none")

    open_ids = {o["id"] for o in open_orders}
    cur = DB.execute("""
        SELECT rowid, * FROM grid_pairs
         WHERE symbol=? AND status IN ('waiting','holding')
    """, (sym,))
    rows = cur.fetchall()
    cols = [c[0] for c in cur.description]

    for row in rows:
        r = dict(zip(cols, row))

        # BUY filled?
        if r["status"] == "waiting" and r["buy_order_id"] not in open_ids:
            order       = exchange.fetch_order(r["buy_order_id"], sym)
            if not order:
                log.error(f"{sym} ⚠️ missing buy order {r['buy_order_id']}")
                continue

            filled      = float(order["filled"])
            fee_obj     = order.get("fee") or {}
            fee_cost    = fee_obj.get("cost", 0.0)
            fee_currency= fee_obj.get("currency", "")
            net         = filled - fee_cost
            price_exec  = (order["cost"] / filled) if filled else r["buy_price"]

            DB.execute("""
                UPDATE grid_pairs
                   SET buy_filled=?,
                       buy_exchange_price=?,
                       buy_maker_fee=?,
                       buy_maker_fee_currency=?,
                       buy_net_real=?,
                       status='ready_to_sell'
                 WHERE rowid=?
            """, (
                datetime.utcnow(),
                price_exec,
                fee_cost,
                fee_currency,
                net,
                r["rowid"]
            ))
            DB.commit()

            log.info(
                f"🟢 {sym} BUY FILLED: qty={filled} "
                f"fee={fee_cost} {fee_currency} net={net:.8f} buy@{price_exec:.8f}"
            )
            submit_sell_pair(sym, r, net)

        # SELL filled?
        elif r["status"] == "holding" and r["sell_order_id"] not in open_ids:
            order       = exchange.fetch_order(r["sell_order_id"], sym)
            if not order:
                log.error(f"{sym} ⚠️ missing sell order {r['sell_order_id']}")
                continue

            filled      = float(order["filled"])
            fee_obj     = order.get("fee") or {}
            fee_cost    = fee_obj.get("cost", 0.0)
            fee_currency= fee_obj.get("currency", "")
            net         = filled - fee_cost
            price_exec  = (order["cost"] / filled) if filled else r["sell_price"]

            DB.execute("""
                UPDATE grid_pairs
                   SET sell_filled=?,
                       sell_exchange_price=?,
                       sell_maker_fee=?,
                       sell_maker_fee_currency=?,
                       sell_net_real=?,
                       status='completed'
                 WHERE rowid=?
            """, (
                datetime.utcnow(),
                price_exec,
                fee_cost,
                fee_currency,
                net,
                r["rowid"]
            ))
            DB.commit()

            log.info(
                f"🔴 {sym} SELL FILLED: qty={filled} "
                f"fee={fee_cost} {fee_currency} net={net:.8f} sell@{price_exec:.8f}"
            )
            log.info(f"🏁 {sym} PAIR DONE: buy@{r['buy_price']} → sell@{r['sell_price']}")

def seed_grid_for_symbol(sym, cfg):
    # 1) get current price and log it
    price     = get_price(sym)
    log.info(f"{sym} ⇒ Current price: {price:.8f}")

    usd       = cfg["usd_per_order"]
    bands     = cfg["bands"]
    all_pairs = load_price_grid("grids/"+cfg["grid_file"])

    # 2) eligible bands under current price
    eligible = [(b, s) for b, s in all_pairs if b < price]
    eligible.sort(key=lambda x: x[0], reverse=True)

    # 3) fetch and count all active bands (waiting, ready_to_sell, holding) under price
    cur = DB.execute("""
        SELECT buy_price FROM grid_pairs
         WHERE symbol=?
           AND status IN ('waiting','ready_to_sell','holding')
    """, (sym,))
    all_active = {r[0] for r in cur.fetchall()}
    active_under = {bp for bp in all_active if bp < price}
    active_count = len(active_under)
    log.info(f"{sym} ⇒ Active bands under price: {active_count}/{bands}")

    # 4) how many new buys are needed?
    needed = bands - active_count
    if needed <= 0:
        log.info(f"{sym} ➡️ No new buys needed.")
        return

    # 5) seed next `needed` buys
    seeded = 0
    for buy_price, sell_price in eligible:
        if seeded >= needed:
            break
        if buy_price in active_under:
            continue

        raw_qty = usd / buy_price
        qty     = float(exchange.amount_to_precision(sym, raw_qty))
        log.info(
            f"{sym} Seeding band: qty={qty:.8f} "
            f"@ buy@{buy_price:.8f} / sell@{sell_price:.8f}"
        )
        submit_buy_pair(sym, buy_price, sell_price, qty)
        seeded += 1
        time.sleep(1)

    log.info(
        f"{sym} ➡️ Seeded {seeded} new buy(s); "
        f"now {active_count+seeded}/{bands} active bands."
    )
def retry_failed_sells_for_symbol(sym):
    log.info(f"{sym} 🔁 Checking for stranded 'ready_to_sell' rows...")
    try:
        open_orders = exchange.fetch_open_orders(sym)
        open_sell_ids = {o["id"] for o in open_orders if o["side"] == "sell"}
    except Exception as e:
        log.error(f"{sym} ⚠️ Failed to fetch open orders for retry: {e}")
        return

    cur = DB.execute("""
        SELECT rowid, * FROM grid_pairs
         WHERE symbol=? AND status='ready_to_sell'
    """, (sym,))
    rows = cur.fetchall()
    cols = [c[0] for c in cur.description]

    for row in rows:
        r = dict(zip(cols, row))
        rowid = r["rowid"]
        buy_net = r["buy_net_real"]
        sell_price = r["sell_price"]
        existing_sell_id = r.get("sell_order_id")

        # Already active?
        if existing_sell_id and existing_sell_id in open_sell_ids:
            log.info(f"{sym} ✅ Existing sell order still active for buy@{r['buy_price']}")
            continue

        # Get live price
        try:
            current_price = get_price(sym)
            log.info(f"{sym} 🔎 Price check: now {current_price:.8f}, target sell@{sell_price:.8f}")
        except Exception as e:
            log.error(f"{sym} ⚠️ Failed to fetch price for retry: {e}")
            continue

        # If price already above sell_price, execute market sell
        if current_price >= sell_price:
            log.info(f"{sym} ⏫ Price above target, selling immediately at market price!")
            try:
                o = exchange.create_market_sell_order(sym, buy_net)
                DB.execute("""
                    UPDATE grid_pairs
                       SET sell_order_id=?,
                           sell_submitted=?,
                           sell_filled=?,
                           sell_exchange_price=?,
                           sell_maker_fee=?,
                           sell_maker_fee_currency=?,
                           sell_net_real=?,
                           status='completed'
                     WHERE rowid=?
                """, (
                    o["id"],
                    datetime.utcnow(),
                    datetime.utcnow(),
                    current_price,
                    o.get("fee", {}).get("cost", 0.0),
                    o.get("fee", {}).get("currency", ""),
                    buy_net - o.get("fee", {}).get("cost", 0.0),
                    rowid
                ))
                DB.commit()
                log.info(f"🏁 {sym} MARKET SELL COMPLETE: qty={buy_net} sell@{current_price:.8f}")
            except Exception as e:
                log.error(f"{sym} ❌ Market sell failed: {e}")
        else:
            # Re-attempt limit sell
            log.warning(f"{sym} 🛑 Sell order missing, retrying limit sell...")
            try:
                submit_sell_pair(sym, r, buy_net)
            except Exception as e:
                log.error(f"{sym} ❌ Retry limit sell failed: {e}")
def set_band_close(sym, cfg):
    try:
        price = get_price(sym)
        log.info(f"{sym} ⬆️ set_band_close(): current price: {price:.8f}")

        # Load all configured grid bands
        all_pairs = load_price_grid("grids/" + cfg["grid_file"])
        valid_bands = [(b, s) for b, s in all_pairs if b < price]
        if not valid_bands:
            log.info(f"{sym} ❌ No valid buy bands under current price.")
            return

        next_buy, next_sell = valid_bands[0]
        log.info(f"{sym} 🎯 Closest eligible band: buy@{next_buy} → sell@{next_sell}")

        # Fetch all 'waiting' orders for this symbol
        cur = DB.execute("""
            SELECT rowid, * FROM grid_pairs
             WHERE symbol = ? AND status = 'waiting'
        """, (sym,))
        rows = cur.fetchall()
        cols = [c[0] for c in cur.description]

        # Cancel all stale 'waiting' orders BELOW the closest band
        stale_orders = [
            dict(zip(cols, row)) for row in rows
            if row[cols.index("buy_price")] < next_buy
        ]

        for r in stale_orders:
            try:
                exchange.cancel_order(r["buy_order_id"], sym)
                log.info(f"{sym} ❎ Canceled stale buy order {r['buy_order_id']} @ {r['buy_price']}")
            except Exception as e:
                log.warning(f"{sym} ⚠️ Failed to cancel {r['buy_order_id']}: {e}")
            DB.execute("DELETE FROM grid_pairs WHERE rowid = ?", (r["rowid"],))
        DB.commit()

        # 🔍 Check if next_buy already exists with an INCOMPLETE status
        cur = DB.execute("""
            SELECT COUNT(*) FROM grid_pairs
             WHERE symbol = ?
               AND buy_price = ?
               AND status != 'completed'
        """, (sym, next_buy))
        count = cur.fetchone()[0]

        if count > 0:
            log.info(f"{sym} 🚫 Band {next_buy} already has an active or pending buy. Skipping new order.")
            return

        # ✅ Safe to place a new buy
        raw_qty = cfg["usd_per_order"] / next_buy
        qty     = float(exchange.amount_to_precision(sym, raw_qty))
        log.info(
            f"{sym} ➕ Placing replacement buy: qty={qty:.8f} "
            f"@ buy@{next_buy:.8f} / sell@{next_sell:.8f}"
        )
        submit_buy_pair(sym, next_buy, next_sell, qty)

    except Exception as e:
        log.error(f"{sym} ❌ set_band_close failed: {e}")
def update_config_with_dynamic_usdt(CONFIG, exchange, percent=0.04):
    try:
        balance_info = exchange.fetch_balance()
        usdt_balance = balance_info["USDT"]["free"]
        dynamic_usd = round(usdt_balance * percent, 4)
        log.info(f"💰 Available USDT: {usdt_balance:.4f}, 4% per order: {dynamic_usd:.4f}")

        for sym in CONFIG:
            CONFIG[sym]["usd_per_order"] = dynamic_usd

    except Exception as e:
        log.error(f"❌ Failed to fetch balance or update config: {e}")


# ─── MAIN EXECUTION ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("=== GridBot Multi-Symbol Run STARTED ===")
    try:
        update_config_with_dynamic_usdt(CONFIG, exchange, percent=0.02)
        for sym, cfg in CONFIG.items():
            if sym not in markets:
                log.warning(f"Skipping {sym}: not on exchange")
                continue
            log.info(f"--- Processing {sym} ---")
            check_fills_for_symbol(sym, cfg)
            retry_failed_sells_for_symbol(sym)
            seed_grid_for_symbol(sym, cfg)
            set_band_close(sym, cfg)

    except Exception as e:
        log.error(f"ERROR DURING RUN: {e}")
    finally:
        DB.close()
        log.info("=== Database connection closed ===")
        log.info("=== GridBot Multi-Symbol Run FINISHED ===")
