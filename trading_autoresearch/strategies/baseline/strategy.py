"""
Baseline strategy placeholder.

Replace this with your actual baseline strategy implementation.
The strategy class must be named 'Strategy' and implement
generate_signals() and on_bar() methods for the backtest adapter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StrategyConfig:
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    ema_fast: int = 12
    ema_slow: int = 26
    atr_sl_multiplier: float = 2.0
    atr_tp_multiplier: float = 3.0
    max_hold_bars: int = 24


class Strategy:
    """
    Baseline RSI + EMA crossover strategy.

    This is a placeholder. Replace with your actual strategy.
    The backtest adapter will import this class and call its methods.
    """

    def __init__(self, config: StrategyConfig | None = None):
        self.config = config or StrategyConfig()

    def generate_signals(self, df):
        """
        Given a DataFrame with OHLCV columns, return a Series of signals.
        +1 = long, -1 = short, 0 = flat.

        Implement your signal logic here.
        """
        raise NotImplementedError("Replace with your signal logic")

    def on_bar(self, bar):
        """
        Called on each new bar during event-driven simulation.
        Used by the paper trading adapter.
        """
        raise NotImplementedError("Replace with your bar handler")
