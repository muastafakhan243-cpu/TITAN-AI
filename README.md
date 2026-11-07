# TITAN AI — Freqtrade (dry-run only)

TITAN AI is a rules-based BTC/USDT Spot strategy for Freqtrade. It uses RSI, MACD, EMA, rolling VWAP and Bollinger Bands to create candle-based entry/exit signals. It is not a machine-learning model and does not guarantee profits.

**Safety defaults:** dry-run is forced on, Spot only, BTC/USDT only, no API exchange keys, one open trade maximum, and a $2 simulated wallet. The dashboard is password-protected. Do not change dry-run to live trading without carefully reviewing the risks and explicitly deciding to do so.

## Important limits

- A $2 wallet cannot meet the usual Binance BTC/USDT minimum order size (often around 10 USDT; check the current `exchangeInfo` symbol filters). The risk-based stake is also intentionally skipped when it is below the exchange minimum. Therefore, this setup may make **no simulated trades** with the configured wallet. Dry-run is a simulator, not a way around exchange minimums.
- Freqtrade updates its strategy from candle data. This project uses 5-minute candles and checks its bot loop every 5 seconds; it does not fetch new BTC market candles every second. Faster polling is not a reliable way to obtain new candles and can hit rate limits. Binance WebSocket streaming is not configured for strategy candles here.
- The 1% per-trade risk calculation estimates stake using the configured 2% initial stop. Fees, slippage, gaps, and exchange execution can make actual loss larger. The 2% daily halt uses realized closed-trade P&L, and is not a guarantee against intraday or open-position losses.
- Built-in Freqtrade protections include a three-loss StoplossGuard. The strategy also halts new entries after three consecutive losing closed trades or when that day's realized losses reach 2% of the configured simulated starting wallet. A restart does not erase the trade database.

## Start from a GitHub Codespace on Android

1. Open this repository in a Codespace: tap **Code → Codespaces → Create codespace on main** (or open your existing Codespace for this repository).
2. In the Codespace terminal, create your local dashboard login file:

   ```bash
   cp .env.example .env
   nano .env
   ```

   Replace the example dashboard username and password with your own. Use a long, unique password. This is only for the local Freqtrade dashboard, **not** a Binance key. Do not share it. `.env` is ignored by Git.

3. Build and start the bot:

   ```bash
   docker compose up -d --build
   ```

4. In Codespaces, open the **Ports** tab and tap port **8080**. Keep the port visibility set to **Private**. Sign in with the username/password you set in `.env`. The Freqtrade WebUI is responsive and usable on a phone.
5. Check status and logs in the terminal:

   ```bash
   docker compose ps
   docker compose logs -f titan
   ```

   Press `Ctrl+C` to stop viewing logs; this does not stop the bot.

### Stop, restart, and view status

```bash
docker compose stop       # Stop the bot; keeps its data
docker compose start      # Start it again
docker compose ps         # Running/stopped status
docker compose logs -f titan
```

To stop and remove the container while preserving local user data, run `docker compose down` (not `down -v`). The bot runs only while its Codespace is running; Codespaces can stop after inactivity. This repository does not configure an always-on server.

## Validate configuration and inspect Freqtrade

After creating `.env`, these commands run inside the Docker image:

```bash
docker compose run --rm titan show-config --config /freqtrade/user_data/config.json
docker compose run --rm titan list-strategies --config /freqtrade/user_data/config.json
```

For Binance public candle data (no API key needed), download history before starting if desired:

```bash
docker compose run --rm titan download-data --exchange binance --pairs BTC/USDT --timeframes 5m --days 60
```

A download or config check needs working internet and Docker in the Codespace. No shell is attached to this repository through GitHub, so these commands must be run in your Codespace to verify its environment. Do not enter Binance API credentials; this dry-run setup does not need them.

## Risk and strategy notes

- Entry signals combine an EMA trend filter, RSI range, bullish MACD crossover, price above rolling VWAP, Bollinger mid-band breakout, and nonzero volume.
- Exit signals include a bearish MACD crossover, an EMA trend break, and high RSI. Configured ROI provides take-profit targets; a 2% stop and trailing stop are also configured.
- Stake sizing aims to risk at most 1% of the simulated wallet at the initial stop. It refuses to open a trade if the calculated stake is below the exchange minimum or available stake. It never rounds an undersized risk budget up to the exchange minimum.
- The dashboard API is bound to the container and mapped on port 8080. Keep Codespaces port visibility **Private** and use a strong local dashboard password.
- Never add exchange keys to this repository. Do not enable withdrawal permissions. No live trading has been enabled.
