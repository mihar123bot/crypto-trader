"""
Core data models and types for the crypto trading system.

This module defines the fundamental data structures used throughout
the trading system including signals, positions, trades, and OHLCV data.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Dict, Any, Union
import json


class SignalType(Enum):
    """
    Enumeration of possible trading signal types.
    
    Attributes:
        LONG: Bullish signal - enter long position
        SHORT: Bearish signal - enter short position  
        NEUTRAL: No clear signal - stay flat or exit existing position
    """
    LONG = "LONG"
    SHORT = "SHORT"
    NEUTRAL = "NEUTRAL"


@dataclass
class Signal:
    """
    Standardized signal format across all strategies.
    
    Attributes:
        strategy: Name of the strategy generating the signal
        signal: Type of signal (LONG, SHORT, or NEUTRAL)
        confidence: Confidence score from 0.0 to 1.0
        size: Position size as fraction of capital (0.0 to 1.0)
        timestamp: When the signal was generated
        price: Current market price at signal generation
        metadata: Additional strategy-specific data (stop_loss, take_profit, etc.)
    
    Example:
        >>> signal = Signal(
        ...     strategy="V4_Fixed_Stop",
        ...     signal=SignalType.LONG,
        ...     confidence=0.75,
        ...     size=0.15,
        ...     timestamp=datetime.now(),
        ...     price=50000.0,
        ...     metadata={"stop_loss": 49000.0, "take_profit": 52000.0}
        ... )
    """
    strategy: str
    signal: SignalType
    confidence: float
    size: float
    timestamp: datetime
    price: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate signal parameters after initialization."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")
        if not 0.0 <= self.size <= 1.0:
            raise ValueError(f"Size must be between 0.0 and 1.0, got {self.size}")
        if self.price <= 0:
            raise ValueError(f"Price must be positive, got {self.price}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert signal to dictionary representation.
        
        Returns:
            Dictionary with all signal fields serialized
        """
        return {
            "strategy": self.strategy,
            "signal": self.signal.value,
            "confidence": self.confidence,
            "size": self.size,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """
        Convert signal to JSON string.
        
        Returns:
            JSON formatted string representation
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Signal":
        """
        Create Signal from dictionary.
        
        Args:
            data: Dictionary with signal fields
            
        Returns:
            Signal instance
        """
        return cls(
            strategy=data["strategy"],
            signal=SignalType(data["signal"]),
            confidence=data["confidence"],
            size=data["size"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            price=data["price"],
            metadata=data.get("metadata", {})
        )
    
    def is_entry(self) -> bool:
        """Check if signal is an entry signal (LONG or SHORT)."""
        return self.signal in (SignalType.LONG, SignalType.SHORT)
    
    def is_neutral(self) -> bool:
        """Check if signal is neutral."""
        return self.signal == SignalType.NEUTRAL


@dataclass
class OHLCV:
    """
    OHLCV candle data structure.
    
    Attributes:
        timestamp: Candle timestamp
        open: Opening price
        high: Highest price during period
        low: Lowest price during period
        close: Closing price
        volume: Trading volume
    """
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    def __post_init__(self):
        """Validate OHLCV data integrity."""
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("High must be >= open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("Low must be <= open, close, and high")
        if self.volume < 0:
            raise ValueError("Volume must be non-negative")
    
    def to_dict(self) -> Dict[str, Union[float, int]]:
        """Convert to dictionary."""
        return {
            "timestamp": int(self.timestamp.timestamp()),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume
        }
    
    @property
    def range(self) -> float:
        """Calculate price range (high - low)."""
        return self.high - self.low
    
    @property
    def body(self) -> float:
        """Calculate candle body (close - open)."""
        return self.close - self.open
    
    @property
    def is_bullish(self) -> bool:
        """Check if candle is bullish (close > open)."""
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        """Check if candle is bearish (close < open)."""
        return self.close < self.open


@dataclass
class Position:
    """
    Track open positions for paper trading.
    
    Attributes:
        strategy: Strategy that opened the position
        signal_type: Type of position (LONG or SHORT)
        entry_price: Entry price
        size: Position size in base currency (e.g., BTC)
        timestamp: When position was opened
        entry_confidence: Confidence of entry signal
        stop_loss: Optional stop loss price
        take_profit: Optional take profit price
    """
    strategy: str
    signal_type: SignalType
    entry_price: float
    size: float
    timestamp: datetime
    entry_confidence: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    
    def __post_init__(self):
        """Validate position parameters."""
        if self.entry_price <= 0:
            raise ValueError(f"Entry price must be positive, got {self.entry_price}")
        if self.size <= 0:
            raise ValueError(f"Size must be positive, got {self.size}")
        if self.signal_type == SignalType.NEUTRAL:
            raise ValueError("Position cannot be NEUTRAL")
    
    def unrealized_pnl(self, current_price: float) -> float:
        """
        Calculate unrealized P&L in quote currency (e.g., USD).
        
        Args:
            current_price: Current market price
            
        Returns:
            Unrealized profit/loss amount
        """
        if self.signal_type == SignalType.LONG:
            return (current_price - self.entry_price) * self.size
        elif self.signal_type == SignalType.SHORT:
            return (self.entry_price - current_price) * self.size
        return 0.0
    
    def unrealized_pct(self, current_price: float) -> float:
        """
        Calculate unrealized P&L as percentage.
        
        Args:
            current_price: Current market price
            
        Returns:
            Unrealized profit/loss percentage
        """
        if self.entry_price == 0:
            return 0.0
        if self.signal_type == SignalType.LONG:
            return ((current_price - self.entry_price) / self.entry_price) * 100
        elif self.signal_type == SignalType.SHORT:
            return ((self.entry_price - current_price) / self.entry_price) * 100
        return 0.0
    
    def check_stop_loss(self, current_price: float) -> bool:
        """
        Check if stop loss has been hit.
        
        Args:
            current_price: Current market price
            
        Returns:
            True if stop loss triggered
        """
        if self.stop_loss is None:
            return False
        if self.signal_type == SignalType.LONG:
            return current_price <= self.stop_loss
        else:  # SHORT
            return current_price >= self.stop_loss
    
    def check_take_profit(self, current_price: float) -> bool:
        """
        Check if take profit has been hit.
        
        Args:
            current_price: Current market price
            
        Returns:
            True if take profit triggered
        """
        if self.take_profit is None:
            return False
        if self.signal_type == SignalType.LONG:
            return current_price >= self.take_profit
        else:  # SHORT
            return current_price <= self.take_profit
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary."""
        return {
            "strategy": self.strategy,
            "signal_type": self.signal_type.value,
            "entry_price": self.entry_price,
            "size": self.size,
            "timestamp": self.timestamp.isoformat(),
            "entry_confidence": self.entry_confidence,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit
        }


@dataclass
class Trade:
    """
    Completed trade record.
    
    Attributes:
        strategy: Strategy that executed the trade
        entry_signal: Entry signal type (LONG or SHORT)
        exit_signal: Exit signal type
        entry_price: Entry price
        exit_price: Exit price
        size: Position size
        entry_time: When trade was opened
        exit_time: When trade was closed
        pnl: Realized profit/loss in quote currency
        pnl_pct: Realized profit/loss percentage
    """
    strategy: str
    entry_signal: SignalType
    exit_signal: SignalType
    entry_price: float
    exit_price: float
    size: float
    entry_time: datetime
    exit_time: datetime
    pnl: float
    pnl_pct: float
    
    def __post_init__(self):
        """Validate trade data."""
        if self.entry_price <= 0 or self.exit_price <= 0:
            raise ValueError("Prices must be positive")
        if self.size <= 0:
            raise ValueError("Size must be positive")
        if self.exit_time < self.entry_time:
            raise ValueError("Exit time must be after entry time")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            "strategy": self.strategy,
            "entry_signal": self.entry_signal.value,
            "exit_signal": self.exit_signal.value,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "size": self.size,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct
        }
    
    def is_win(self) -> bool:
        """Check if trade was profitable."""
        return self.pnl > 0
    
    def is_loss(self) -> bool:
        """Check if trade was unprofitable."""
        return self.pnl < 0
    
    def duration(self) -> float:
        """
        Calculate trade duration in seconds.
        
        Returns:
            Duration in seconds
        """
        return (self.exit_time - self.entry_time).total_seconds()
    
    @property
    def risk_reward_ratio(self) -> Optional[float]:
        """
        Calculate risk/reward ratio if stop loss and take profit were set.
        
        Returns:
            Risk/reward ratio or None if not applicable
        """
        if abs(self.pnl_pct) < 0.01:
            return None
        # Simplified calculation based on actual result
        return abs(self.pnl_pct) / 100
