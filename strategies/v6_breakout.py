"""
V6 Breakout Strategy - Support/resistance breakout detection.
"""
import pandas as pd
import numpy as np
from datetime import datetime

from strategies.base import BaseStrategy
from core import Signal, SignalType


class V6BreakoutStrategy(BaseStrategy):
    """
    Support and resistance breakout strategy.
    
    Logic:
    - Identifies support/resistance levels from recent highs/lows
    - LONG: Break above resistance with volume
    - SHORT: Break below support with volume
    - Uses multiple timeframe confirmation
    """
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate support/resistance levels."""
        df = data.copy()
        
        lookback = self.params.get("lookback_periods", 20)
        
        # Support and resistance levels
        df["resistance"] = df["high"].rolling(window=lookback).max()
        df["support"] = df["low"].rolling(window=lookback).min()
        
        # Previous levels (for breakout detection)
        df["prev_resistance"] = df["resistance"].shift(1)
        df["prev_support"] = df["support"].shift(1)
        
        # Distance to levels
        df["dist_to_resistance"] = (df["resistance"] - df["close"]) / df["close"]
        df["dist_to_support"] = (df["close"] - df["support"]) / df["close"]
        
        # Volume analysis
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        # Volatility for stop placement
        df["atr"] = self._calculate_atr(df, 14)
        
        # Price momentum
        df["momentum_3"] = (df["close"] - df["close"].shift(3)) / df["close"].shift(3)
        
        return df
    
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """Generate breakout signals."""
        df = self.prepare_data(data)
        
        if len(df) < 25:
            return self._neutral_signal(df)
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        breakout_threshold_pct = self.params.get("breakout_threshold_pct", 1.0)
        volume_confirmation = self.params.get("volume_confirmation", True)
        
        price = current["close"]
        
        # Breakout detection
        # Resistance breakout: price > previous resistance
        broke_resistance = price > current["prev_resistance"] and prev["close"] <= prev["resistance"]
        
        # Support breakdown: price < previous support  
        broke_support = price < current["prev_support"] and prev["close"] >= prev["support"]
        
        # Volume confirmation
        volume_ok = not volume_confirmation or current["volume_ratio"] > 1.2
        
        # Momentum confirmation
        momentum_ok = current["momentum_3"] > 0.005 or current["momentum_3"] < -0.005
        
        if broke_resistance and volume_ok and momentum_ok:
            # Calculate confidence based on breakout strength
            breakout_strength = (price - current["prev_resistance"]) / current["prev_resistance"]
            
            confidence = 0.6 + min(breakout_strength * 10, 0.2)
            if current["volume_ratio"] > 1.5:
                confidence += 0.1
            if current["momentum_3"] > 0.01:
                confidence += 0.05
            
            # Set stops beyond the broken level
            stop_loss = current["prev_resistance"] * 0.995
            take_profit = price + (price - stop_loss) * 2  # 2:1 R/R
            
            return Signal(
                strategy=self.name,
                signal=SignalType.LONG,
                confidence=min(confidence, 0.95),
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "breakout_level": current["prev_resistance"],
                    "breakout_strength_pct": breakout_strength * 100,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "volume_ratio": current["volume_ratio"],
                    "lookback_periods": self.params.get("lookback_periods", 20),
                    "signal_type": "resistance_breakout"
                }
            )
        
        elif broke_support and volume_ok and momentum_ok:
            breakout_strength = (current["prev_support"] - price) / current["prev_support"]
            
            confidence = 0.6 + min(breakout_strength * 10, 0.2)
            if current["volume_ratio"] > 1.5:
                confidence += 0.1
            if current["momentum_3"] < -0.01:
                confidence += 0.05
            
            stop_loss = current["prev_support"] * 1.005
            take_profit = price - (stop_loss - price) * 2  # 2:1 R/R
            
            return Signal(
                strategy=self.name,
                signal=SignalType.SHORT,
                confidence=min(confidence, 0.95),
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "breakout_level": current["prev_support"],
                    "breakout_strength_pct": breakout_strength * 100,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "volume_ratio": current["volume_ratio"],
                    "lookback_periods": self.params.get("lookback_periods", 20),
                    "signal_type": "support_breakdown"
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
