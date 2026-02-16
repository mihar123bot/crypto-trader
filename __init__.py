"""
crypto-trader — Paper trading and backtesting system for crypto strategies.
"""

from core import Signal, SignalType, Position, Trade, OHLCV
from config.manager import StrategyConfig, ConfigManager
from strategies import get_strategy, list_strategies
from strategies.base import BaseStrategy
from portfolio import PortfolioState
from backtest.engine import BacktestEngine, BacktestResult

__all__ = [
    "Signal",
    "SignalType",
    "Position",
    "Trade",
    "OHLCV",
    "StrategyConfig",
    "ConfigManager",
    "get_strategy",
    "list_strategies",
    "BaseStrategy",
    "PortfolioState",
    "BacktestEngine",
    "BacktestResult",
]
