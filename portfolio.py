"""
Position tracking and paper trading portfolio management.
"""
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
import json

from core import Signal, SignalType, Position, Trade


@dataclass
class PortfolioState:
    """Current state of the paper trading portfolio."""
    initial_capital: float = 10000.0
    cash: float = 10000.0
    positions: Dict[str, Position] = field(default_factory=dict)  # strategy -> position
    trades: List[Trade] = field(default_factory=list)
    equity_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def total_value(self, current_price: float) -> float:
        """Calculate total portfolio value including unrealized P&L."""
        position_value = sum(
            pos.unrealized_pnl(current_price) + (pos.size * pos.entry_price)
            for pos in self.positions.values()
        )
        return self.cash + position_value
    
    def record_equity(self, timestamp: datetime, current_price: float):
        """Record equity snapshot."""
        self.equity_history.append({
            "timestamp": timestamp.isoformat(),
            "cash": self.cash,
            "total_value": self.total_value(current_price),
            "unrealized_pnl": sum(
                pos.unrealized_pnl(current_price) 
                for pos in self.positions.values()
            ),
            "positions_count": len(self.positions)
        })
    
    def process_signal(
        self,
        signal: Signal,
        current_price: float,
        timestamp: datetime
    ) -> Optional[Trade]:
        """
        Process a trading signal and update positions.
        
        Returns:
            Trade object if a position was closed, None otherwise
        """
        completed_trade = None
        strategy = signal.strategy
        
        # Check if we have an existing position for this strategy
        existing_pos = self.positions.get(strategy)
        
        if existing_pos:
            # Close existing position
            pnl = existing_pos.unrealized_pnl(current_price)
            pnl_pct = existing_pos.unrealized_pct(current_price)
            
            # Return capital to cash
            position_value = existing_pos.size * existing_pos.entry_price
            self.cash += position_value + pnl
            
            # Record the trade
            trade = Trade(
                strategy=strategy,
                entry_signal=existing_pos.signal_type,
                exit_signal=signal.signal,
                entry_price=existing_pos.entry_price,
                exit_price=current_price,
                size=existing_pos.size,
                entry_time=existing_pos.timestamp,
                exit_time=timestamp,
                pnl=pnl,
                pnl_pct=pnl_pct
            )
            self.trades.append(trade)
            completed_trade = trade
            
            # Remove the position
            del self.positions[strategy]
            
            # If new signal is NEUTRAL, we're done (just closed position)
            if signal.signal == SignalType.NEUTRAL:
                return completed_trade
        
        # Open new position if signal is LONG or SHORT
        if signal.signal in (SignalType.LONG, SignalType.SHORT):
            position_value = self.cash * signal.size
            size = position_value / current_price
            
            # Calculate stop loss and take profit if provided in metadata
            stop_loss = signal.metadata.get("stop_loss")
            take_profit = signal.metadata.get("take_profit")
            
            self.positions[strategy] = Position(
                strategy=strategy,
                signal_type=signal.signal,
                entry_price=current_price,
                size=size,
                timestamp=timestamp,
                entry_confidence=signal.confidence,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            
            # Deduct from cash
            self.cash -= position_value
        
        return completed_trade
    
    def check_stops(self, current_price: float, timestamp: datetime) -> List[Trade]:
        """Check and execute stop losses and take profits."""
        closed_trades = []
        strategies_to_close = []
        
        for strategy, position in self.positions.items():
            if position.check_stop_loss(current_price) or position.check_take_profit(current_price):
                strategies_to_close.append(strategy)
        
        # Close positions that hit stops
        for strategy in strategies_to_close:
            position = self.positions[strategy]
            pnl = position.unrealized_pnl(current_price)
            pnl_pct = position.unrealized_pct(current_price)
            
            position_value = position.size * position.entry_price
            self.cash += position_value + pnl
            
            trade = Trade(
                strategy=strategy,
                entry_signal=position.signal_type,
                exit_signal=SignalType.NEUTRAL,  # Stop exit
                entry_price=position.entry_price,
                exit_price=current_price,
                size=position.size,
                entry_time=position.timestamp,
                exit_time=timestamp,
                pnl=pnl,
                pnl_pct=pnl_pct
            )
            self.trades.append(trade)
            closed_trades.append(trade)
            del self.positions[strategy]
        
        return closed_trades
    
    def get_summary(self, current_price: float) -> Dict[str, Any]:
        """Get portfolio summary."""
        total_value = self.total_value(current_price)
        total_return = ((total_value - self.initial_capital) / self.initial_capital) * 100
        
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "total_value": total_value,
            "total_return_pct": total_return,
            "open_positions": len(self.positions),
            "total_trades": len(self.trades),
            "winning_trades": len([t for t in self.trades if t.pnl > 0]),
            "losing_trades": len([t for t in self.trades if t.pnl < 0]),
            "unrealized_pnl": sum(
                pos.unrealized_pnl(current_price) 
                for pos in self.positions.values()
            )
        }
    
    def to_json(self) -> str:
        """Serialize portfolio state to JSON."""
        return json.dumps({
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "positions": {
                k: {
                    "strategy": v.strategy,
                    "signal_type": v.signal_type.value,
                    "entry_price": v.entry_price,
                    "size": v.size,
                    "timestamp": v.timestamp.isoformat(),
                    "entry_confidence": v.entry_confidence,
                    "stop_loss": v.stop_loss,
                    "take_profit": v.take_profit
                }
                for k, v in self.positions.items()
            },
            "trades": [t.to_dict() for t in self.trades],
            "equity_history": self.equity_history
        }, indent=2)
