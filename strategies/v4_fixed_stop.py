"""
V4 Fixed Stop Strategy - Risk-managed with fixed stop-losses.
"""
import pandas as pd
from datetime import datetime

from strategies.base import BaseStrategy
from core import Signal, SignalType


class V4FixedStopStrategy(BaseStrategy):
    """
    Risk-managed strategy with fixed stop-loss and take-profit levels.
    
    Logic:
    - Standard EMA crossover entry
    - Fixed percentage stop-loss (2% default)
    - Fixed percentage take-profit (4% default, 2:1 R/R)
    - No trailing - strict risk management
    """
    
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicators."""
        df = data.copy()
        
        ema_fast = self.params.get("ema_fast", 12)
        ema_slow = self.params.get("ema_slow", 26)
        
        df["ema_fast"] = self._calculate_ema(df["close"], ema_fast)
        df["ema_slow"] = self._calculate_ema(df["close"], ema_slow)
        df["rsi"] = self._calculate_rsi(df["close"], 14)
        df["atr"] = self._calculate_atr(df, 14)
        
        # Trend strength
        df["adx"] = self._calculate_adx(df, 14)
        
        return df
    
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """Generate signal with fixed stops."""
        df = self.prepare_data(data)
        
        if len(df) < 2:
            return self._neutral_signal(df)
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        stop_loss_pct = self.params.get("stop_loss_pct", 2.0)
        take_profit_pct = self.params.get("take_profit_pct", 4.0)
        
        # EMA crossover
        prev_diff = previous["ema_fast"] - previous["ema_slow"]
        curr_diff = current["ema_fast"] - current["ema_slow"]
        
        golden_cross = prev_diff < 0 and curr_diff > 0
        death_cross = prev_diff > 0 and curr_diff < 0
        
        # ADX filter - only trade in trending markets
        strong_trend = current["adx"] > 25
        
        price = current["close"]
        
        if golden_cross and strong_trend and current["rsi"] < 70:
            stop_loss = price * (1 - stop_loss_pct / 100)
            take_profit = price * (1 + take_profit_pct / 100)
            
            confidence = self.calculate_confidence(
                SignalType.LONG,
                df,
                trend_strength=current["adx"] / 100,
                volatility_regime=1 if current["atr"] / price < 0.02 else 0.5
            )
            
            return Signal(
                strategy=self.name,
                signal=SignalType.LONG,
                confidence=confidence,
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "risk_reward_ratio": take_profit_pct / stop_loss_pct,
                    "adx": current["adx"],
                    "atr": current["atr"]
                }
            )
        
        elif death_cross and strong_trend and current["rsi"] > 30:
            stop_loss = price * (1 + stop_loss_pct / 100)
            take_profit = price * (1 - take_profit_pct / 100)
            
            confidence = self.calculate_confidence(
                SignalType.SHORT,
                df,
                trend_strength=current["adx"] / 100,
                volatility_regime=1 if current["atr"] / price < 0.02 else 0.5
            )
            
            return Signal(
                strategy=self.name,
                signal=SignalType.SHORT,
                confidence=confidence,
                size=self.position_size,
                timestamp=datetime.now(),
                price=price,
                metadata={
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "risk_reward_ratio": take_profit_pct / stop_loss_pct,
                    "adx": current["adx"],
                    "atr": current["atr"]
                }
            )
        
        return self._neutral_signal(df)
    
    def _calculate_adx(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average Directional Index."""
        high = data["high"]
        low = data["low"]
        close = data["close"]
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(window=period).mean()
        
        return adx
    
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
