"""
Strategy registry for easy access to all strategies.
"""
from strategies.base import BaseStrategy
from strategies.v1_legacy import V1LegacyStrategy
from strategies.v2_profit_max import V2ProfitMaxStrategy
from strategies.v3_aggressive import V3AggressiveStrategy
from strategies.v4_fixed_stop import V4FixedStopStrategy
from strategies.v5_vwap import V5VWAPStrategy
from strategies.v6_breakout import V6BreakoutStrategy
from config.manager import StrategyConfig


STRATEGY_MAP = {
    "v1": V1LegacyStrategy,
    "v1_legacy": V1LegacyStrategy,
    "v2": V2ProfitMaxStrategy,
    "v2_profit_max": V2ProfitMaxStrategy,
    "v3": V3AggressiveStrategy,
    "v3_aggressive": V3AggressiveStrategy,
    "v4": V4FixedStopStrategy,
    "v4_fixed_stop": V4FixedStopStrategy,
    "v5": V5VWAPStrategy,
    "v5_vwap": V5VWAPStrategy,
    "v6": V6BreakoutStrategy,
    "v6_breakout": V6BreakoutStrategy,
}


def get_strategy(name: str, config: StrategyConfig) -> BaseStrategy:
    """
    Get a strategy instance by name.
    
    Args:
        name: Strategy name (e.g., 'v1', 'v3_aggressive')
        config: Strategy configuration
    
    Returns:
        Strategy instance
    """
    name_lower = name.lower()
    
    if name_lower not in STRATEGY_MAP:
        raise ValueError(f"Unknown strategy: {name}. Available: {list(STRATEGY_MAP.keys())}")
    
    strategy_class = STRATEGY_MAP[name_lower]
    return strategy_class(config)


def list_strategies() -> list:
    """List all available strategy names."""
    return list(set(STRATEGY_MAP.values()))
