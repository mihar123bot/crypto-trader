# Crypto Trading Bot - Paper Trading System

A Python-based paper trading system for algorithmic crypto trading with 6 distinct strategies, backtesting, and performance analysis.

## Current Status (Feb 15, 2025)

| Strategy | Status | Last Trade | P&L | Notes |
|----------|--------|------------|-----|-------|
| **V3 Aggressive** | ✅ Active | Closed +1.40% | +$1.40 | Best performer, optimized version with ADX filter |
| **V4 Fixed Stop** | ✅ Active | Closed +0.89% | +$0.89 | Risk-managed, stable returns |
| **V5 VWAP Cross** | ✅ Active | Closed +4.03% | +$0.60 | Mean reversion, strong R-multiple |

**Last Updated**: Feb 15, 2025 17:25 EST  
**Monitoring**: Every 5 minutes via cron  
**Mode**: Paper trading (no real capital risk)

## Features

- **6 Trading Strategies**: From baseline momentum to aggressive breakout detection
- **Backtesting Engine**: Historical performance analysis with walk-forward validation
- **Paper Trading**: Live simulation without real capital risk
- **Kraken API Integration**: Real-time and historical market data
- **Performance Metrics**: Sharpe ratio, max drawdown, win rate, profit factor

## Strategies

| Strategy | Description | Best For |
|----------|-------------|----------|
| **V1 Legacy** | EMA crossover with RSI filter | Baseline momentum |
| **V2 Profit Max** | Aggressive take-profits (3%+) | Profit-focused trading |
| **V3 Aggressive** | Optimized high-frequency with ADX filter | Active trading (+1.40% current best) |
| **V4 Fixed Stop** | Fixed 2% stop, 4% target | Risk management |
| **V5 VWAP Cross** | Mean reversion to VWAP | Ranging markets |
| **V6 Breakout** | Support/resistance breakouts | Trending markets |

## Installation

```bash
git clone <repo-url>
cd crypto-trader
pip install -r requirements.txt
```

## Quick Start

### Run Backtest

```bash
# Backtest V3 strategy for 90 days
python trade.py --strategy V3 --backtest 90d

# Backtest with custom capital
python trade.py --strategy V1 --backtest 6m --capital 50000

# Save results to file
python trade.py --strategy V5 --backtest 90d --output results.json
```

### Paper Trading

```bash
# Run paper trading with V3
python trade.py --strategy V3 --paper

# Custom interval
python trade.py --strategy V1 --paper --interval 1h
```

### Compare All Strategies

```bash
# Compare all 6 strategies
python trade.py --compare --duration 90d

# Save comparison
python trade.py --compare --duration 90d --output comparison.json
```

## CLI Reference

```
usage: trade.py [-h] [--strategy STRATEGY] [--backtest DURATION] [--paper]
                [--compare] [--duration DURATION] [--interval {1m,5m,15m,30m,1h,4h}]
                [--pair PAIR] [--capital CAPITAL] [--commission COMMISSION]
                [--slippage SLIPPAGE] [--config-dir CONFIG_DIR] [--output OUTPUT]
                [--verbose]

Options:
  -s, --strategy    Strategy to use (V1-V6)
  -b, --backtest    Run backtest (e.g., 90d, 6m, 1y)
  -p, --paper       Run paper trading mode
  -c, --compare     Compare all strategies
  -d, --duration    Duration for comparison (default: 90d)
  -i, --interval    Candle interval (default: 30m)
  --pair            Trading pair (default: XBTUSD)
  --capital         Initial capital (default: 10000)
  --commission      Commission rate (default: 0.001)
  --slippage        Slippage rate (default: 0.0005)
  -o, --output      Output file for results
  -v, --verbose     Verbose output
```

## Configuration

Strategy configurations are stored in `config/` as JSON files:

```json
{
  "name": "V3 Aggressive",
  "enabled": true,
  "position_size": 0.25,
  "max_positions": 1,
  "params": {
    "ema_fast": 5,
    "ema_slow": 13,
    "rsi_period": 10,
    "volatility_threshold": 0.015,
    "min_confidence": 0.55
  }
}
```

Generate default configs:
```bash
python -c "from config.manager import ConfigManager; ConfigManager().create_default_configs()"
```

## Project Structure

```
crypto-trader/
├── trade.py                 # Main CLI entry point
├── core.py                  # Data models (Signal, Trade, Position)
├── portfolio.py             # Paper trading portfolio management
├── requirements.txt         # Python dependencies
├── strategies/
│   ├── base.py             # Base strategy class
│   ├── v1_legacy.py        # V1: Baseline momentum
│   ├── v2_profit_max.py    # V2: Profit-focused
│   ├── v3_aggressive.py    # V3: High-frequency
│   ├── v4_fixed_stop.py    # V4: Risk-managed
│   ├── v5_vwap.py          # V5: VWAP mean reversion
│   ├── v6_breakout.py      # V6: Breakout detection
│   └── __init__.py         # Strategy registry
├── backtest/
│   └── engine.py           # Backtesting engine
├── data/
│   └── kraken.py           # Kraken API client
├── config/
│   └── manager.py          # Configuration management
└── tests/                  # Unit tests
```

## Strategy Logic

### V1 Legacy (Baseline Momentum)
- **Entry**: EMA crossover (9/21) with RSI confirmation
- **Filter**: RSI < 70 for longs, RSI > 30 for shorts
- **Confidence**: Based on trend strength and RSI distance

### V2 Profit Max
- **Entry**: Fast EMA alignment with momentum
- **Take Profit**: 3% aggressive targets
- **Stop Loss**: 1.5% trailing stop
- **Boost**: Volume spike adds 15% confidence

### V3 Aggressive (Current Best - Optimized)
- **Entry**: Multiple condition scoring with ADX trend filter (>25)
- **Threshold**: 0.65 minimum confidence (raised from 0.55)
- **Stop Loss**: Dynamic 1.5x ATR-based
- **Take Profit**: 3x ATR-based
- **Position Size**: Volatility-adjusted sizing
- **Daily Limit**: Max 2 trades/day to prevent overtrading
- **Best for**: High-activity trading with risk management

### V4 Fixed Stop
- **Entry**: EMA crossover with ADX filter (>25)
- **Stop Loss**: Fixed 2%
- **Take Profit**: Fixed 4% (2:1 R/R)
- **Risk**: Strict, no trailing

### V5 VWAP Cross
- **Entry**: Price deviation from VWAP > 0.5%
- **Take Profit**: VWAP mean reversion
- **Stop Loss**: 1.5% fixed
- **Best for**: Ranging, mean-reverting markets

### V6 Breakout
- **Entry**: 20-period support/resistance breakout
- **Confirmation**: Volume spike > 1.2x
- **Stop Loss**: Beyond broken level
- **Take Profit**: 2:1 risk/reward

## Performance Metrics

The backtester calculates:

- **Total Return**: Overall profit/loss percentage
- **Win Rate**: Percentage of winning trades
- **Profit Factor**: Gross profit / Gross loss
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted returns (annualized)
- **Avg Win/Loss**: Average trade outcomes

## Notes for PM (Mihar)

### Recommended Optimizations

1. **V3 Aggressive (Current Best)**
   - Consider reducing position size from 0.25 to 0.20 for lower drawdown
   - Test volatility threshold between 0.012-0.018
   - Monitor for overfitting on high-frequency signals

2. **Parameter Tuning**
   - All strategies: Optimize EMA periods using walk-forward analysis
   - V4: Test stop-loss between 1.5-2.5% for better R/R
   - V5: VWAP period could be extended to 20 for less noise

3. **Portfolio Considerations**
   - Running multiple strategies together may improve Sharpe ratio
   - Consider correlation analysis between strategies
   - Position sizing could be volatility-adjusted

4. **Next Steps**
   - Implement walk-forward optimization
   - Add regime detection (trending vs ranging)
   - Consider dynamic position sizing based on Kelly criterion
   - Add multi-timeframe confirmation

## License

MIT License - For educational and paper trading use only.

**Warning**: This software is for paper trading and backtesting only. No live trading functionality is implemented.
