"""
V5 VWAP Cross Strategy - VWAP mean reversion strategy.
"""
import pandas as pd
import numpy as np
from datetime import datetime

from strategies.base import BaseStrategy
from core import Signal, SignalType


class V5VWAPStrategy(BaseStrategy):
    """
    Mean reversion strategy based on VWAP deviation.
    
    Logic:
    - LONG: Price significantly below VWAP + volume confirmation
    - SHORT: Price significantly above VWAP + volume confirmation
    - Targets return to VWAP mean
    - Best in ranging markets
    """
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate VWAP and deviation metrics."""
        df = data.copy()
        
        vwap_period = self.params.get("vwap_period", 14)
        
        # Calculate VWAP
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        df["vwap"] = (typical_price * df["volume"]).rolling(window=vwap_period).sum() / \
                     df["volume"].rolling(window=vwap_period).sum()
        
        # VWAP deviation
        df["vwap_deviation"] = (df["close"] - df["vwap"]) / df["vwap"]
        
        # Standard deviation of deviation (for dynamic thresholds)
        df["vwap_dev_std"] = df["vwap_deviation"].rolling(window=20).std()
        
        # Volume analysis
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        # RSI for oversold/overbought
        df["rsi"] = self._calculate_rsi(df["close"], 14)
        
        # Bollinger Bands around VWAP
        df["vwap_upper"] = df["vwap"] + (2 * df["vwap_dev_std"] * df["vwap"])
        df["vwap_lower"] = df["vwap"] - (2 * df["vwap_dev_std"] * df["vwap"])
        
        return df
    
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """Generate mean reversion signals based on VWAP."""
        df = self.prepare_data(data)
        
        if len(df) < 20:
            return self._neutral_signal(df)
        
        current = df.iloc[-1]
        
        mean_reversion_threshold = self.params.get("mean_reversion_threshold", 0.005)
        volume_spike_factor = self.params.get("volume_spike_factor", 1.5)
        
        price = current["close"]
        deviation = current["vwap_deviation"]
        
        # Volume confirmation
        volume_confirmed = current["volume_ratio"] > volume_spike_factor
        
        # Long: Price below VWAP with mean reversion setup
        if deviation < -mean_reversion_threshold and current["rsi"] < 45:
            # Distance from mean affects confidence
            distance_factor = min(abs(deviation) / 0.02, 1.0)
            
            confidence = 0.5 + (distance_factor * 0.3)
            if volume_confirmed:
                confidence += 0.15
            if current["rsi"] < 35:
                confidence += 0.05
            
            # Take profit at VWAP
            take_profit = current["vwap"]
            stop_loss = price * 0.985  # 1.5% stop
            
            return Signal(
                strategy=self.name,
                signal=SignalType.LONG,
                confidence=min(confidence, 0.95),
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "vwap": current["vwap"],
                    "deviation_pct": deviation * 100,
                    "take_profit": take_profit,
                    "stop_loss": stop_loss,
                    "volume_ratio": current["volume_ratio"],
                    "signal_type": "mean_reversion_to_vwap"
                }
            )
        
        # Short: Price above VWAP with mean reversion setup
        elif deviation > mean_reversion_threshold and current["rsi"] > 55:
            distance_factor = min(abs(deviation) / 0.02, 1.0)
            
            confidence = 0.5 + (distance_factor * 0.3)
            if volume_confirmed:
                confidence += 0.15
            if current["rsi"] > 65:
                confidence += 0.05
            
            take_profit = current["vwap"]
            stop_loss = price * 1.015  # 1.5% stop
            
            return Signal(
                strategy=self.name,
                signal=SignalType.SHORT,
                confidence=min(confidence, 0.95),
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "vwap": current["vwap"],
                    "deviation_pct": deviation * 100,
                    "take_profit": take_profit,
                    "stop_loss": stop_loss,
                    "volume_ratio": current["volume_ratio"],
                    "signal_type": "mean_reversion_to_vwap"
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
