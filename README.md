# SetForget Crypto Trading Bot

An automated, “set-and-forget” cryptocurrency trading bot in Python.  
Starts with \$500 and runs a simple EMA crossover strategy on your exchange of choice.

---

## 🧩 Features

- **Trend-following** via EMA(20) / EMA(50) crossover  
- Supports any **CCXT-compatible** exchange (Binance, KuCoin, etc.)  
- Configurable symbol, timeframe, trade size  
- Runs on an **hourly loop** (or adjust to your own interval)  
- **Systemd** service for 24/7 uptime on any VPS  
- **Environment-driven** settings via `.env`  

---

## 🚀 Getting Started

### 1. Clone & enter project
```bash
git clone https://your.repo.url/SetForget.git
cd SetForget
