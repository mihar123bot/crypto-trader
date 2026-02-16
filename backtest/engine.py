"""
Backtesting engine for strategy performance evaluation.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json

from core import Signal, SignalType, Trade
from portfolio import PortfolioState
from strategies.base import BaseStrategy


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    strategy_name: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_equity: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    equity_curve: List[Dict[str, Any]]
    trades: List[Trade]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_name": self.strategy_name,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "initial_capital": self.initial_capital,
            "final_equity": self.final_equity,
            "total_return_pct": self.total_return_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
        }
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        return f"""
{'='*60}
Backtest Results: {self.strategy_name}
{'='*60}
Period: {self.start_date.date()} to {self.end_date.date()}
Initial Capital: ${self.initial_capital:,.2f}
Final Equity: ${self.final_equity:,.2f}
Total Return: {self.total_return_pct:+.2f}%

Trades:
  Total: {self.total_trades}
  Winning: {self.winning_trades}
  Losing: {self.losing_trades}
  Win Rate: {self.win_rate:.1f}%
  Avg Win: ${self.avg_win:,.2f}
  Avg Loss: ${self.avg_loss:,.2f}

Risk Metrics:
  Profit Factor: {self.profit_factor:.2f}
  Max Drawdown: {self.max_drawdown_pct:.2f}%
  Sharpe Ratio: {self.sharpe_ratio:.2f}
{'='*60}
"""


class BacktestEngine:
    """Backtesting engine for strategy evaluation."""
    
    def __init__(
        self,
        data: pd.DataFrame,
        initial_capital: float = 10000.0,
        commission: float = 0.001,  # 0.1% per trade
        slippage: float = 0.0005    # 0.05% slippage
    ):
        self.data = data
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
    
    def run(
        self,
        strategy: BaseStrategy,
        verbose: bool = False
    ) -> BacktestResult:
        """
        Run backtest for a strategy.
        
        Args:
            strategy: Strategy instance to test
            verbose: Print progress
        
        Returns:
            BacktestResult with performance metrics
        """
        strategy.reset()
        portfolio = PortfolioState(initial_capital=self.initial_capital)
        
        equity_curve = []
        
        # Minimum data needed for indicators
        min_periods = 50
        
        for i in range(min_periods, len(self.data)):
            # Get data up to current point
            current_data = self.data.iloc[:i+1]
            current_price = current_data.iloc[-1]["close"]
            current_time = current_data.index[-1]
            
            # Check stops first
            portfolio.check_stops(current_price, current_time)
            
            # Generate signal
            signal = strategy.generate_signal(current_data)
            
            # Apply slippage to execution price
            if signal.signal == SignalType.LONG:
                exec_price = current_price * (1 + self.slippage)
            elif signal.signal == SignalType.SHORT:
                exec_price = current_price * (1 - self.slippage)
            else:
                exec_price = current_price
            
            # Process signal
            trade = portfolio.process_signal(
                signal,
                exec_price,
                current_time
            )
            
            # Apply commission on trades (both entry and exit)
            if trade:
                entry_commission = trade.size * trade.entry_price * self.commission
                exit_commission = trade.size * trade.exit_price * self.commission
                portfolio.cash -= (entry_commission + exit_commission)
            
            # Record equity
            portfolio.record_equity(current_time, current_price)
            
            if verbose and i % 100 == 0:
                print(f"Progress: {i}/{len(self.data)} - Equity: ${portfolio.total_value(current_price):,.2f}")
        
        # Calculate metrics
        return self._calculate_metrics(portfolio, strategy.name)
    
    def _calculate_metrics(
        self,
        portfolio: PortfolioState,
        strategy_name: str
    ) -> BacktestResult:
        """Calculate performance metrics."""
        trades = portfolio.trades
        
        if not trades:
            return BacktestResult(
                strategy_name=strategy_name,
                start_date=self.data.index[0],
                end_date=self.data.index[-1],
                initial_capital=self.initial_capital,
                final_equity=portfolio.cash,
                total_return_pct=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                avg_win=0.0,
                avg_loss=0.0,
                profit_factor=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                equity_curve=portfolio.equity_history,
                trades=[]
            )
        
        # Trade statistics
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl < 0]
        
        total_return_pct = (
            (portfolio.total_value(self.data.iloc[-1]["close"]) - self.initial_capital)
            / self.initial_capital * 100
        )
        
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t.pnl for t in losing_trades]) if losing_trades else 0
        
        gross_profit = sum(t.pnl for t in winning_trades)
        gross_loss = abs(sum(t.pnl for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Calculate max drawdown
        equity_values = [e["total_value"] for e in portfolio.equity_history]
        max_drawdown_pct = self._calculate_max_drawdown(equity_values)
        
        # Calculate Sharpe ratio
        returns = pd.Series(equity_values).pct_change().dropna()
        sharpe_ratio = self._calculate_sharpe(returns)
        
        return BacktestResult(
            strategy_name=strategy_name,
            start_date=self.data.index[0],
            end_date=self.data.index[-1],
            initial_capital=self.initial_capital,
            final_equity=portfolio.total_value(self.data.iloc[-1]["close"]),
            total_return_pct=total_return_pct,
            total_trades=len(trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=len(winning_trades) / len(trades) * 100,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=sharpe_ratio,
            equity_curve=portfolio.equity_history,
            trades=trades
        )
    
    def _calculate_max_drawdown(self, equity_values: List[float]) -> float:
        """Calculate maximum drawdown percentage."""
        peak = equity_values[0]
        max_dd = 0
        
        for value in equity_values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def _calculate_sharpe(self, returns: pd.Series, risk_free_rate: float = 0.0) -> float:
        """Calculate annualized Sharpe ratio."""
        if returns.std() == 0:
            return 0.0
        
        # Assuming 48 periods per day (30-min candles)
        periods_per_year = 48 * 365
        sharpe = (returns.mean() - risk_free_rate) / returns.std()
        return sharpe * np.sqrt(periods_per_year)
    
    def walk_forward_analysis(
        self,
        strategy: BaseStrategy,
        train_size: int = 30,
        test_size: int = 10
    ) -> List[BacktestResult]:
        """
        Perform walk-forward analysis.
        
        Args:
            strategy: Strategy to test
            train_size: Training period size in days
            test_size: Testing period size in days
        
        Returns:
            List of backtest results for each period
        """
        # Convert days to periods (30-min candles = 48 per day)
        train_periods = train_size * 48
        test_periods = test_size * 48
        
        results = []
        start_idx = train_periods
        
        while start_idx + test_periods <= len(self.data):
            # Test period
            test_data = self.data.iloc[start_idx:start_idx + test_periods]
            
            # Create engine for just test period
            engine = BacktestEngine(
                test_data,
                self.initial_capital,
                self.commission,
                self.slippage
            )
            
            result = engine.run(strategy, verbose=False)
            results.append(result)
            
            start_idx += test_periods
        
        return results
