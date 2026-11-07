"""TITAN AI: conservative, candle-based BTC/USDT Spot strategy for Freqtrade."""
from datetime import datetime, timedelta, timezone
import logging

import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

logger = logging.getLogger(__name__)


class TitanAI(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = "5m"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 200
    minimal_roi = {"0": 0.04, "60": 0.02, "240": 0.01}
    stoploss = -0.02
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    position_adjustment_enable = False

    risk_per_trade = 0.01
    daily_loss_limit = 0.02
    max_consecutive_losses = 3
    _risk_check_interval = timedelta(minutes=1)

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        """Halt new entries on a realized daily loss limit or three losses in a row."""
        last_check = getattr(self, "_risk_checked_at", None)
        if last_check and current_time - last_check < self._risk_check_interval:
            return
        self._risk_checked_at = current_time

        try:
            # Freqtrade stores close_date in UTC. Only today's closed trades count toward
            # the daily limit; the rolling recent-trade check counts consecutive losses.
            closed = Trade.get_trades_proxy(is_open=False)
            today = [t for t in closed if t.close_date and t.close_date.date() == current_time.date()]
            today_profit = sum(float(t.close_profit_abs or 0.0) for t in today)
            recent = sorted(
                (t for t in closed if t.close_date),
                key=lambda trade: trade.close_date,
                reverse=True,
            )[: self.max_consecutive_losses]
            consecutive_losses = len(recent) == self.max_consecutive_losses and all(
                float(t.close_profit_abs or 0.0) < 0 for t in recent
            )
            wallet = float(self.config.get("dry_run_wallet", 2.0))
            daily_limit_amount = wallet * self.daily_loss_limit
            self._risk_halt = today_profit <= -daily_limit_amount or consecutive_losses
            if self._risk_halt:
                logger.warning(
                    "TITAN AI risk halt active: today's realized P&L %.6f USDT; "
                    "daily loss threshold %.6f USDT; three-loss guard=%s",
                    today_profit,
                    daily_limit_amount,
                    consecutive_losses,
                )
        except Exception:
            # Fail closed: if the trade history cannot be checked, do not add exposure.
            self._risk_halt = True
            logger.exception("Could not verify risk limits; TITAN AI is halting new entries.")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        close = dataframe["close"]
        dataframe["ema20"] = close.ewm(span=20, adjust=False).mean()
        dataframe["ema50"] = close.ewm(span=50, adjust=False).mean()

        delta = close.diff()
        gains = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        losses = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
        relative_strength = gains / losses.replace(0, np.nan)
        dataframe["rsi"] = (100 - (100 / (1 + relative_strength))).fillna(50)

        macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
        dataframe["macd"] = macd
        dataframe["macd_signal"] = macd.ewm(span=9, adjust=False).mean()

        typical_price = (dataframe["high"] + dataframe["low"] + close) / 3
        volume_sum = dataframe["volume"].rolling(20, min_periods=20).sum()
        dataframe["vwap"] = (
            (typical_price * dataframe["volume"]).rolling(20, min_periods=20).sum()
            / volume_sum.replace(0, np.nan)
        )

        middle = close.rolling(20, min_periods=20).mean()
        deviation = close.rolling(20, min_periods=20).std(ddof=0)
        dataframe["bb_mid"] = middle
        dataframe["bb_upper"] = middle + 2 * deviation
        dataframe["bb_lower"] = middle - 2 * deviation
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_tag"] = None
        if getattr(self, "_risk_halt", False):
            return dataframe

        bullish_macd_cross = (dataframe["macd"] > dataframe["macd_signal"]) & (
            dataframe["macd"].shift(1) <= dataframe["macd_signal"].shift(1)
        )
        bullish_band_cross = (dataframe["close"] > dataframe["bb_mid"]) & (
            dataframe["close"].shift(1) <= dataframe["bb_mid"].shift(1)
        )
        entry = (
            (dataframe["volume"] > 0)
            & (dataframe["ema20"] > dataframe["ema50"])
            & dataframe["rsi"].between(45, 68)
            & bullish_macd_cross
            & (dataframe["close"] > dataframe["vwap"])
            & bullish_band_cross
        )
        dataframe.loc[entry, ["enter_long", "enter_tag"]] = (1, "trend_macd_vwap_bb")
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_tag"] = None
        bearish_macd_cross = (dataframe["macd"] < dataframe["macd_signal"]) & (
            dataframe["macd"].shift(1) >= dataframe["macd_signal"].shift(1)
        )
        exit_signal = (
            (dataframe["volume"] > 0)
            & (
                bearish_macd_cross
                | (dataframe["close"] < dataframe["ema20"])
                | (dataframe["rsi"] >= 72)
            )
        )
        dataframe.loc[exit_signal, ["exit_long", "exit_tag"]] = (1, "trend_or_momentum_exit")
        return dataframe

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        """Size to 1% wallet risk at the configured initial stop; skip undersized orders."""
        if getattr(self, "_risk_halt", False) or side != "long":
            return 0.0
        try:
            wallet = float(self.wallets.get_total_stake_amount())
        except Exception:
            wallet = float(self.config.get("dry_run_wallet", 2.0))
        risk_budget = wallet * self.risk_per_trade
        risk_fraction = abs(float(self.stoploss))
        if wallet <= 0 or risk_fraction <= 0:
            return 0.0
        stake = min(max_stake, risk_budget / risk_fraction)
        if min_stake is not None and stake < min_stake:
            logger.info("Skipping %s: risk-sized stake %.4f is below minimum %.4f", pair, stake, min_stake)
            return 0.0
        return max(0.0, stake)
