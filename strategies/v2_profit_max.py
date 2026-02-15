"""
V2 Profit Max Strategy - Profit-focused with aggressive take-profits.
Uses tighter EMAs with aggressive take-profit levels.
"""
import pandas as pd
from datetime import datetime

from strategies.base import BaseStrategy
from core import Signal, SignalType


class V2ProfitMaxStrategy(BaseStrategy):
    """
    Profit-focused strategy with aggressive take-profit targets.
    
    Logic:
    - Faster EMAs for quicker entry
    - Aggressive take-profit levels (3%+ default)
    - Trailing stops to lock in profits
    - Higher confidence on volume spikes
    """
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicators."""
        df = data.copy()
        
        ema_fast = self.params.get("ema_fast", 8)
        ema_slow = self.params.get("ema_slow", 20)
        rsi_period = self.params.get("rsi_period", 12)
        
        df["ema_fast"] = self._calculate_ema(df["close"], ema_fast)
        df["ema_slow"] = self._calculate_ema(df["close"], ema_slow)
        df["rsi"] = self._calculate_rsi(df["close"], rsi_period)
        df["atr"] = self._calculate_atr(df, 14)
        
        # Volume analysis
        df["volume_sma"] = self._calculate_sma(df["volume"], 20)
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        return df
    
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """Generate signal with aggressive profit targets."""
        df = self.prepare_data(data)
        
        if len(df) < 2:
            return self._neutral_signal(df)
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        take_profit_pct = self.params.get("take_profit_pct", 3.0)
        trailing_stop_pct = self.params.get("trailing_stop_pct", 1.5)
        
        # Price momentum
        price_change = (current["close"] - previous["close"]) / previous["close"]
        
        # EMA alignment
        ema_aligned_bull = current["ema_fast"] > current["ema_slow"] > df.iloc[-5]["ema_slow"]
        ema_aligned_bear = current["ema_fast"] < current["ema_slow"] < df.iloc[-5]["ema_slow"]
        
        # Volume confirmation
        volume_spike = current["volume_ratio"] > 1.3
        
        price = current["close"]
        
        if ema_aligned_bull and price_change > 0.001 and current["rsi"] < 75:
            # Long signal with aggressive take profit
            confidence = self.calculate_confidence(
                SignalType.LONG,
                df,
                trend_strength=abs(current["close"] - current["ema_slow"]) / current["ema_slow"],
                volume_ratio=current["volume_ratio"]
            )
            
            # Boost confidence on volume spike
            if volume_spike:
                confidence = min(confidence + 0.15, 1.0)
            
            take_profit = price * (1 + take_profit_pct / 100)
            stop_loss = price * (1 - trailing_stop_pct / 100)
            
            return Signal(
                strategy=self.name,
                signal=SignalType.LONG,
                confidence=confidence,
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "take_profit": take_profit,
                    "stop_loss": stop_loss,
                    "trailing_stop_pct": trailing_stop_pct,
                    "volume_ratio": current["volume_ratio"],
                    "price_momentum": price_change
                }
            )
        
        elif ema_aligned_bear and price_change < -0.001 and current["rsi"] > 25:
            # Short signal
            confidence = self.calculate_confidence(
                SignalType.SHORT,
                df,
                trend_strength=abs(current["close"] - current["ema_slow"]) / current["ema_slow"],
                volume_ratio=current["volume_ratio"]
            )
            
            if volume_spike:
                confidence = min(confidence + 0.15, 1.0)
            
            take_profit = price * (1 - take_profit_pct / 100)
            stop_loss = price * (1 + trailing_stop_pct / 100)
            
            return Signal(
                strategy=self.name,
                signal=SignalType.SHORT,
                confidence=confidence,
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "take_profit": take_profit,
                    "stop_loss": stop_loss,
                    "trailing_stop_pct": trailing_stop_pct,
                    "volume_ratio": current["volume_ratio"],
                    "price_momentum": price_change
                }
            )
        
        return self._neutral_signal(df)
    
    def _neutral_signal(self, df: pd.DataFrame) -> Signal:
        price = df.iloc[-1]["close"] if len(df) > 0 else 0
        return Signal(
            strategy=self.name,
            signal=SignalType.NEUTRAL,
            confidence=0.0,
            size=0.0,
            timestamp=datetime.now(),
            price=price,
            metadata={}
        )
