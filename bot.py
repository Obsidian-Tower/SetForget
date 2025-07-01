#!/usr/bin/env python3
import os
import socket
import time
import logging
import sqlite3
import json
from datetime import datetime,timezone

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
    "ETH/USDT": {"grid_file": "ETH-USDT-06.csv"},
    "BTC/USDT": {"grid_file": "BTC-USDT-05.csv"},
    "DOGE/USDT": {"grid_file": "DOGE-USDT-10.csv"},
    "UNI/USDT": {"grid_file": "UNI-USDT-10.csv"},
    "SOL/USDT": {"grid_file": "SOL-USDT-10.csv"},
    "XRP/USDT": {"grid_file": "XRP-USDT-10.csv"},
    "SHIB/USDT": {"grid_file": "SHIB-USDT-10.csv"},
    "ADA/USDT": {"grid_file": "ADA-USDT-06.csv"},
    "LINK/USDT": {"grid_file": "LINK-USDT-10.csv"},
    "DOT/USDT": {"grid_file": "DOT-USDT-11.csv"},
    "LTC/USDT": {"grid_file": "LTC-USDT-08.csv"},
    "AAVE/USDT": {"grid_file": "AAVE-USDT-12.csv"},
    "BNB/USDT": {"grid_file": "BNB-USDT-04.csv"},
    "FET/USDT": {"grid_file": "FET-USDT-10.csv"},
    "OP/USDT": {"grid_file": "OP-USDT-10.csv"},
    "ARB/USDT": {"grid_file": "ARB-USDT-06.csv"},
    "CRV/USDT": {"grid_file": "CRV-USDT-10.csv"},
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
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol                  TEXT NOT NULL,

    buy_trade_id            TEXT,
    buy_order_id            TEXT,
    buy_order_submitted     TIMESTAMP,
    buy_order_filled        TIMESTAMP,
    buy_amount              REAL,
    buy_price               REAL,
    buy_cost                REAL,
    buy_fee_cost            REAL,
    buy_fee_currency        TEXT,
    buy_fees                INTEGER,
    buy_fees_data           TEXT,

    sell_trade_id           TEXT,
    sell_order_id           TEXT,
    sell_order_submitted    TIMESTAMP,
    sell_order_filled       TIMESTAMP,
    sell_amount             REAL,
    sell_price              REAL,
    sell_cost               REAL,
    sell_fee_cost           REAL,
    sell_fee_currency       TEXT,
    sell_fees               INTEGER,
    sell_fees_data          TEXT,

    buy_raw_json            TEXT,
    sell_raw_json           TEXT,
    status                  TEXT
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

#updated needs test
def submit_buy_pair(sym, buy_price, sell_price, qty):
    log.info(f"▶️ ATTEMPT BUY {sym}: qty={qty} @ buy@{buy_price}")
    o = exchange.create_limit_buy_order(sym, qty, buy_price)

    DB.execute("""
        INSERT INTO grid_pairs (
            symbol,
            buy_order_id,
            buy_order_submitted,
            buy_price,
            buy_amount,
            buy_cost,
            buy_raw_json,
            status,
            sell_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sym,
        o["id"],
        datetime.now(timezone.utc),
        float(o["price"]),
        float(o["amount"]),
        float(o["cost"]),
        json.dumps(o),
        'waiting',
        sell_price
    ))
    DB.commit()

    log.info(
        f"✅ BUY PLACED {sym}: qty={qty} "
        f"$~{round(qty * buy_price, 2)} buy@{buy_price} (id={o['id']})"
    )

#updated needs test
def submit_sell_pair(sym, r, qty):
    sell_price = r["sell_price"]
    log.info(f"▶️ ATTEMPT SELL {sym}: qty={qty} @ sell@{sell_price}")
    o = exchange.create_limit_sell_order(sym, qty, sell_price)

    DB.execute("""
        UPDATE grid_pairs
           SET sell_order_id = ?,
               sell_order_submitted = ?,
               status = 'holding',
               sell_price = ?
         WHERE buy_order_id = ?
    """, (
        o["id"],
        datetime.now(timezone.utc),
        float(o["price"]),
        r["buy_order_id"]
    ))
    DB.commit()

    log.info(
        f"✅ SELL PLACED {sym}: qty={qty} "
        f"$~{round(qty * sell_price, 2)} sell@{sell_price} (id={o['id']})"
    )

#updated needs test
def check_fills_for_symbol(sym, cfg):
    import json
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
        SELECT id, * FROM grid_pairs
         WHERE symbol=? AND status IN ('waiting','holding')
    """, (sym,))
    rows = cur.fetchall()
    cols = [c[0] for c in cur.description]

    for row in rows:
        r = dict(zip(cols, row))

        # BUY filled?
        if r["status"] == "waiting" and r["buy_order_id"] not in open_ids:
            order = exchange.fetch_order(r["buy_order_id"], sym)
            if not order:
                log.error(f"{sym} ⚠️ missing buy order {r['buy_order_id']}")
                continue

            filled = float(order["filled"])
            cost = order["cost"]

            # Pull trade info
            trades = exchange.fetch_my_trades(symbol=sym)
            trades = [t for t in trades if t.get("order") == r["buy_order_id"]]
            trade = trades[0] if trades else {}
            fee = trade.get("fee", {})
            fee_cost = fee.get("cost", 0.0)
            fee_currency = fee.get("currency", "")
            fees_list = trade.get("fees", [])
            fees_count = len(fees_list)
            fees_json = json.dumps(fees_list)

            net = filled - fee_cost

            DB.execute("""
                UPDATE grid_pairs
                   SET buy_order_filled=?,
                       buy_cost=?,
                       buy_fee_cost=?,
                       buy_fee_currency=?,
                       buy_fees=?,
                       buy_fees_data=?,
                       buy_net_real=?,
                       status='ready_to_sell'
                 WHERE id=?
            """, (
                datetime.utcnow(),
                cost,
                fee_cost,
                fee_currency,
                fees_count,
                fees_json,
                net,
                r["id"]
            ))
            DB.commit()

            log.info(
                f"🟢 {sym} BUY FILLED: qty={filled} "
                f"fee={fee_cost} {fee_currency} net={net:.8f} buy@{price_exec:.8f}"
            )
            submit_sell_pair(sym, r, net)

        # SELL filled?
        elif r["status"] == "holding" and r["sell_order_id"] not in open_ids:
            order = exchange.fetch_order(r["sell_order_id"], sym)
            if not order:
                log.error(f"{sym} ⚠️ missing sell order {r['sell_order_id']}")
                continue

            filled = float(order["filled"])
            cost = order["cost"]

            # Pull trade info
            trades = exchange.fetch_my_trades(symbol=sym)
            trades = [t for t in trades if t.get("order") == r["sell_order_id"]]
            trade = trades[0] if trades else {}
            fee = trade.get("fee", {})
            fee_cost = fee.get("cost", 0.0)
            fee_currency = fee.get("currency", "")
            fees_list = trade.get("fees", [])
            fees_count = len(fees_list)
            fees_json = json.dumps(fees_list)

            net = filled - fee_cost

            DB.execute("""
                UPDATE grid_pairs
                   SET sell_order_filled=?,
                       sell_cost=?,
                       sell_fee_cost=?,
                       sell_fee_currency=?,
                       sell_fees=?,
                       sell_fees_data=?,
                       sell_net_real=?,
                       status='completed'
                 WHERE id=?
            """, (
                datetime.utcnow(),
                cost,
                fee_cost,
                fee_currency,
                fees_count,
                fees_json,
                net,
                r["id"]
            ))
            DB.commit()

            log.info(
                f"🔴 {sym} SELL FILLED: qty={filled} "
                f"fee={fee_cost} {fee_currency} net={net:.8f} sell@{price_exec:.8f}"
            )
            log.info(f"🏁 {sym} PAIR DONE: buy@{r['buy_price']} → sell@{r['sell_price']}")

#updated needs test
def seed_grid_for_symbol(sym, cfg):
    import time

    # 1) Get current price
    price = get_price(sym)
    log.info(f"{sym} ⇒ Current price: {price:.8f}")

    usd       = cfg["usd_per_order"]
    bands     = 1
    all_pairs = load_price_grid("grids/" + cfg["grid_file"])

    # 2) Eligible buy/sell pairs below current price
    eligible = [(b, s) for b, s in all_pairs if b < price]
    eligible.sort(key=lambda x: x[0], reverse=True)

    # 3) Count existing active bands under current price
    cur = DB.execute("""
        SELECT buy_price FROM grid_pairs
         WHERE symbol=?
           AND status IN ('waiting','ready_to_sell','holding')
    """, (sym,))
    all_active = {r[0] for r in cur.fetchall()}
    active_under = {bp for bp in all_active if bp < price}
    active_count = len(active_under)
    log.info(f"{sym} ⇒ Active bands under price: {active_count}/{bands}")

    # 4) Determine how many new buys are needed
    needed = bands - active_count
    if needed <= 0:
        log.info(f"{sym} ➡️ No new buys needed.")
        return

    # 5) Submit new buys for next needed bands
    seeded = 0
    for buy_price, sell_price in eligible:
        if seeded >= needed:
            break
        if buy_price in active_under:
            continue

        # Calculate qty with precision handling
        raw_qty = usd / buy_price
        qty = float(exchange.amount_to_precision(sym, raw_qty))

        log.info(
            f"{sym} Seeding band: qty={qty:.8f} "
            f"@ buy@{buy_price:.8f} / sell@{sell_price:.8f}"
        )

        # Submit order (submit_buy_pair must conform to new schema expectations)
        submit_buy_pair(sym, buy_price, sell_price, qty)
        seeded += 1
        time.sleep(1)

    log.info(
        f"{sym} ➡️ Seeded {seeded} new buy(s); "
        f"now {active_count + seeded}/{bands} active bands."
    )

#updated needs test
def retry_failed_sells_for_symbol(sym):
    import json

    log.info(f"{sym} 🔁 Checking for stranded 'ready_to_sell' rows...")
    try:
        open_orders = exchange.fetch_open_orders(sym)
        open_sell_ids = {o["id"] for o in open_orders if o["side"] == "sell"}
    except Exception as e:
        log.error(f"{sym} ⚠️ Failed to fetch open orders for retry: {e}")
        return

    cur = DB.execute("""
        SELECT id, * FROM grid_pairs
         WHERE symbol=? AND status='ready_to_sell'
    """, (sym,))
    rows = cur.fetchall()
    cols = [c[0] for c in cur.description]

    for row in rows:
        r = dict(zip(cols, row))
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
                o = exchange.create_market_sell_order(sym, r["buy_amount"])  # temporary qty guess

                # Fetch trade by order ID
                trades = exchange.fetch_my_trades(symbol=sym, params={"order": o["id"]})
                trade = trades[0] if trades else {}
                amount = trade.get("amount", 0.0)

                fee = trade.get("fee", {}) or {}
                fee_cost = fee.get("cost", 0.0)
                fee_currency = fee.get("currency", "")
                fees = trade.get("fees", [])
                fee_count = len(fees)
                fees_json = json.dumps(fees)
                cost = trade.get("cost", current_price * amount)

                DB.execute("""
                    UPDATE grid_pairs
                       SET sell_order_id=?,
                           sell_order_submitted=?,
                           sell_order_filled=?,
                           sell_amount=?,
                           sell_price=?,
                           sell_cost=?,
                           sell_fee_cost=?,
                           sell_fee_currency=?,
                           sell_fees=?,
                           sell_fees_data=?,
                           sell_raw_json=?,
                           status='completed'
                     WHERE id=?
                """, (
                    o["id"],
                    datetime.utcnow(),
                    datetime.utcnow(),
                    amount,
                    current_price,
                    cost,
                    fee_cost,
                    fee_currency,
                    fee_count,
                    fees_json,
                    json.dumps(o),
                    r["id"]
                ))
                DB.commit()
                log.info(f"🏁 {sym} MARKET SELL COMPLETE: qty={amount} sell@{current_price:.8f}")
            except Exception as e:
                log.error(f"{sym} ❌ Market sell failed: {e}")
        else:
            # Re-attempt limit sell
            log.warning(f"{sym} 🛑 Sell order missing, retrying limit sell...")
            try:
                submit_sell_pair(sym, r, r["buy_amount"])
            except Exception as e:
                log.error(f"{sym} ❌ Retry limit sell failed: {e}")

#updated needs test
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
            SELECT id, buy_order_id, buy_price FROM grid_pairs
             WHERE symbol = ? AND status = 'waiting'
        """, (sym,))
        rows = cur.fetchall()

        # Cancel all stale 'waiting' orders BELOW the closest band
        stale_orders = [row for row in rows if row[2] < next_buy]

        for row in stale_orders:
            row_id, order_id, buy_price = row
            try:
                exchange.cancel_order(order_id, sym)
                log.info(f"{sym} ❎ Canceled stale buy order {order_id} @ {buy_price}")
            except Exception as e:
                log.warning(f"{sym} ⚠️ Failed to cancel {order_id}: {e}")
            DB.execute("DELETE FROM grid_pairs WHERE id = ?", (row_id,))
        DB.commit()

        # 🔍 Check if next_buy already exists with an INCOMPLETE status
        cur = DB.execute("""
            SELECT COUNT(*) FROM grid_pairs
             WHERE symbol = ? AND buy_price = ? AND status != 'completed'
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

#chillin
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