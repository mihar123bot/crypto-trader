#!/usr/bin/env python3
"""
CLI interface for the crypto trading bot.
Usage: python trade.py --strategy V3 --backtest 90d
"""
import argparse
import sys
import json
from datetime import datetime
from pathlib import Path
import pandas as pd

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from strategies import get_strategy
from config.manager import ConfigManager
from data.kraken import KrakenDataSource
from backtest.engine import BacktestEngine
from portfolio import PortfolioState


def parse_duration(duration_str: str) -> int:
    """Parse duration string like '90d', '6m', '1y'."""
    unit = duration_str[-1].lower()
    value = int(duration_str[:-1])
    
    if unit == 'd':
        return value
    elif unit == 'm':
        return value * 30
    elif unit == 'y':
        return value * 365
    else:
        raise ValueError(f"Invalid duration format: {duration_str}")


def cmd_backtest(args):
    """Run backtest for a strategy."""
    print(f"🔄 Loading strategy: {args.strategy}")
    
    # Load config
    config_manager = ConfigManager(args.config_dir)
    config = config_manager.get(args.strategy.lower())
    
    if not config:
        print(f"❌ Config not found for {args.strategy}")
        print("Creating default configs...")
        config_manager.create_default_configs()
        config = config_manager.get(args.strategy.lower())
    
    # Get strategy
    strategy = get_strategy(args.strategy, config)
    
    # Fetch data
    days = parse_duration(args.backtest)
    print(f"📊 Fetching {days} days of historical data...")
    
    data_source = KrakenDataSource(pair=args.pair)
    data = data_source.fetch_historical(days=days, interval=args.interval)
    
    print(f"✅ Loaded {len(data)} candles")
    
    # Run backtest
    print(f"🚀 Running backtest...")
    engine = BacktestEngine(
        data,
        initial_capital=args.capital,
        commission=args.commission,
        slippage=args.slippage
    )
    
    result = engine.run(strategy, verbose=args.verbose)
    
    # Print results
    print(result.summary())
    
    # Save results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Save trades CSV
        trades_df = pd.DataFrame([t.to_dict() for t in result.trades])
        trades_path = output_path.with_suffix('.trades.csv')
        trades_df.to_csv(trades_path, index=False)
        
        # Save equity curve
        equity_df = pd.DataFrame(result.equity_curve)
        equity_path = output_path.with_suffix('.equity.csv')
        equity_df.to_csv(equity_path, index=False)
        
        print(f"📁 Results saved to {output_path}")
        print(f"📁 Trades saved to {trades_path}")
        print(f"📁 Equity curve saved to {equity_path}")
    
    return result


def cmd_paper_trade(args):
    """Run paper trading mode."""
    print(f"📝 Starting paper trading mode")
    print(f"Strategy: {args.strategy}")
    print(f"Interval: {args.interval}")
    print("Press Ctrl+C to stop\n")
    
    # Load config
    config_manager = ConfigManager(args.config_dir)
    config = config_manager.get(args.strategy.lower())
    
    if not config:
        config_manager.create_default_configs()
        config = config_manager.get(args.strategy.lower())
    
    strategy = get_strategy(args.strategy, config)
    data_source = KrakenDataSource(pair=args.pair)
    portfolio = PortfolioState(initial_capital=args.capital)
    
    # Data buffer for indicators
    data_buffer = pd.DataFrame()
    
    import time
    
    try:
        while True:
            # Fetch latest data
            candles = data_source.fetch_ohlcv(
                interval=args.interval,
                limit=100
            )
            
            df = pd.DataFrame([
                {
                    "timestamp": c.timestamp,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume
                }
                for c in candles
            ])
            df.set_index("timestamp", inplace=True)
            
            current_price = df.iloc[-1]["close"]
            current_time = df.index[-1]
            
            # Check stops
            portfolio.check_stops(current_price, current_time)
            
            # Generate signal
            signal = strategy.generate_signal(df)
            
            # Process signal
            trade = portfolio.process_signal(signal, current_price, current_time)
            
            # Record equity
            portfolio.record_equity(current_time, current_price)
            
            # Print status
            summary = portfolio.get_summary(current_price)
            print(f"\r[{current_time}] Price: ${current_price:,.2f} | "
                  f"Signal: {signal.signal.value:>8} | "
                  f"Equity: ${summary['total_value']:,.2f} | "
                  f"Return: {summary['total_return_pct']:+.2f}% | "
                  f"Trades: {summary['total_trades']}", end="")
            
            if trade:
                print(f"\n💰 Trade closed: {trade.pnl:+.2f} USD ({trade.pnl_pct:+.2f}%)")
            
            # Sleep until next interval
            interval_seconds = {
                "1m": 60, "5m": 300, "15m": 900,
                "30m": 1800, "1h": 3600, "4h": 14400
            }
            time.sleep(interval_seconds.get(args.interval, 1800))
            
    except KeyboardInterrupt:
        print("\n\n🛑 Paper trading stopped")
        summary = portfolio.get_summary(current_price)
        print(f"\nFinal Summary:")
        print(f"  Initial Capital: ${summary['initial_capital']:,.2f}")
        print(f"  Final Equity: ${summary['total_value']:,.2f}")
        print(f"  Total Return: {summary['total_return_pct']:+.2f}%")
        print(f"  Total Trades: {summary['total_trades']}")
        print(f"  Win Rate: {summary['winning_trades']/max(summary['total_trades'],1)*100:.1f}%")
        
        if args.output:
            with open(args.output, 'w') as f:
                f.write(portfolio.to_json())
            print(f"\n📁 Portfolio state saved to {args.output}")


def cmd_compare(args):
    """Compare all strategies."""
    print("📊 Running comparison of all 6 strategies...")
    
    # Create default configs
    config_manager = ConfigManager(args.config_dir)
    configs = config_manager.create_default_configs()
    
    # Fetch data
    days = parse_duration(args.duration)
    print(f"📈 Fetching {days} days of historical data...")
    
    data_source = KrakenDataSource(pair=args.pair)
    data = data_source.fetch_historical(days=days, interval=args.interval)
    
    print(f"✅ Loaded {len(data)} candles")
    
    results = []
    
    for name, config in configs.items():
        print(f"\n🔄 Testing {config.name}...")
        
        strategy = get_strategy(name, config)
        engine = BacktestEngine(data, initial_capital=args.capital)
        result = engine.run(strategy, verbose=False)
        
        results.append(result)
        print(f"   Return: {result.total_return_pct:+.2f}% | "
              f"Win Rate: {result.win_rate:.1f}% | "
              f"Sharpe: {result.sharpe_ratio:.2f}")
    
    # Sort by total return
    results.sort(key=lambda x: x.total_return_pct, reverse=True)
    
    # Print comparison table
    print("\n" + "="*100)
    print(f"{'Rank':<5} {'Strategy':<20} {'Return %':<12} {'Win Rate':<10} {'Trades':<8} {'Max DD':<10} {'Sharpe':<8} {'P.F.':<8}")
    print("="*100)
    
    for i, r in enumerate(results, 1):
        print(f"{i:<5} {r.strategy_name:<20} {r.total_return_pct:>+10.2f}% "
              f"{r.win_rate:>8.1f}% {r.total_trades:>6} {r.max_drawdown_pct:>8.2f}% "
              f"{r.sharpe_ratio:>6.2f} {r.profit_factor:>6.2f}")
    
    print("="*100)
    
    # Save comparison
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        comparison_data = [r.to_dict() for r in results]
        with open(output_path, 'w') as f:
            json.dump(comparison_data, f, indent=2)
        
        # Save CSV
        df = pd.DataFrame(comparison_data)
        csv_path = output_path.with_suffix('.csv')
        df.to_csv(csv_path, index=False)
        
        print(f"\n📁 Comparison saved to {output_path}")
        print(f"📁 CSV saved to {csv_path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Crypto Trading Bot - Paper Trading & Backtesting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python trade.py --strategy V3 --backtest 90d
  python trade.py --strategy V1 --paper --interval 30m
  python trade.py --compare --duration 90d --output results.json
        """
    )
    
    parser.add_argument("--strategy", "-s", 
                       help="Strategy to use (V1-V6)")
    parser.add_argument("--backtest", "-b", 
                       metavar="DURATION",
                       help="Run backtest (e.g., 90d, 6m, 1y)")
    parser.add_argument("--paper", "-p", action="store_true",
                       help="Run paper trading mode")
    parser.add_argument("--compare", "-c", action="store_true",
                       help="Compare all strategies")
    parser.add_argument("--duration", "-d", default="90d",
                       help="Duration for comparison (default: 90d)")
    parser.add_argument("--interval", "-i", default="30m",
                       choices=["1m", "5m", "15m", "30m", "1h", "4h"],
                       help="Candle interval (default: 30m)")
    parser.add_argument("--pair", default="XBTUSD",
                       help="Trading pair (default: XBTUSD)")
    parser.add_argument("--capital", type=float, default=10000.0,
                       help="Initial capital (default: 10000)")
    parser.add_argument("--commission", type=float, default=0.001,
                       help="Commission rate (default: 0.001)")
    parser.add_argument("--slippage", type=float, default=0.0005,
                       help="Slippage rate (default: 0.0005)")
    parser.add_argument("--config-dir", default="config",
                       help="Config directory (default: config)")
    parser.add_argument("--output", "-o",
                       help="Output file for results")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    args = parser.parse_args()
    
    if args.backtest and args.strategy:
        cmd_backtest(args)
    elif args.paper and args.strategy:
        cmd_paper_trade(args)
    elif args.compare:
        cmd_compare(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
