"""
V1 Legacy Strategy - Baseline momentum strategy.
Uses EMA crossover with RSI confirmation for classic momentum trading.
"""
import pandas as pd
from datetime import datetime

from strategies.base import BaseStrategy
from core import Signal, SignalType


class V1LegacyStrategy(BaseStrategy):
    """
    Baseline momentum strategy using EMA crossover with RSI filter.
    
    Logic:
    - LONG: Fast EMA crosses above Slow EMA + RSI not overbought
    - SHORT: Fast EMA crosses below Slow EMA + RSI not oversold
    - Confidence based on trend strength and RSI distance from 50
    """
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate EMAs and RSI."""
        df = data.copy()
        
        ema_fast = self.params.get("ema_fast", 9)
        ema_slow = self.params.get("ema_slow", 21)
        rsi_period = self.params.get("rsi_period", 14)
        
        df["ema_fast"] = self._calculate_ema(df["close"], ema_fast)
        df["ema_slow"] = self._calculate_ema(df["close"], ema_slow)
        df["rsi"] = self._calculate_rsi(df["close"], rsi_period)
        df["ema_diff"] = df["ema_fast"] - df["ema_slow"]
        
        return df
    
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """Generate signal based on EMA crossover and RSI."""
        df = self.prepare_data(data)
        
        if len(df) < 2:
            return self._neutral_signal(df)
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        rsi_overbought = self.params.get("rsi_overbought", 70)
        rsi_oversold = self.params.get("rsi_oversold", 30)
        
        # EMA crossover detection
        prev_diff = previous["ema_fast"] - previous["ema_slow"]
        curr_diff = current["ema_fast"] - current["ema_slow"]
        
        golden_cross = prev_diff < 0 and curr_diff > 0
        death_cross = prev_diff > 0 and curr_diff < 0
        
        price = current["close"]
        
        if golden_cross and current["rsi"] < rsi_overbought:
            # Long signal
            confidence = self.calculate_confidence(
                SignalType.LONG,
                df,
                trend_strength=abs(curr_diff) / current["ema_slow"],
                rsi_distance=(rsi_overbought - current["rsi"]) / 100
            )
            return Signal(
                strategy=self.name,
                signal=SignalType.LONG,
                confidence=confidence,
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "ema_fast": current["ema_fast"],
                    "ema_slow": current["ema_slow"],
                    "rsi": current["rsi"],
                    "signal_type": "ema_crossover"
                }
            )
        
        elif death_cross and current["rsi"] > rsi_oversold:
            # Short signal
            confidence = self.calculate_confidence(
                SignalType.SHORT,
                df,
                trend_strength=abs(curr_diff) / current["ema_slow"],
                rsi_distance=(current["rsi"] - rsi_oversold) / 100
            )
            return Signal(
                strategy=self.name,
                signal=SignalType.SHORT,
                confidence=confidence,
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "ema_fast": current["ema_fast"],
                    "ema_slow": current["ema_slow"],
                    "rsi": current["rsi"],
                    "signal_type": "ema_crossover"
                }
            )
        
        return self._neutral_signal(df)
