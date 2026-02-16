"""
V3 Aggressive Strategy - Optimized Version
High activity with intelligent filtering and risk management.

Key Improvements:
- Market regime detection (ADX-based)
- ATR-based dynamic stop loss and take profit
- Volatility-adjusted position sizing
- Trend strength filtering
- Minimum holding period to avoid churn
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from strategies.base import BaseStrategy
from core import Signal, SignalType


class V3AggressiveStrategy(BaseStrategy):
    """
    Optimized high-frequency strategy with intelligent filtering.
    
    Improvements over original V3:
    1. Market regime detection (ADX > 25 required for entries)
    2. ATR-based dynamic stop loss (1.5x ATR) and take profit (3x ATR)
    3. Volatility-adjusted position sizing (reduce size in high vol)
    4. Minimum confidence threshold raised to 0.65 (from 0.55)
    5. Minimum holding period (6 periods = 3 hours) to reduce churn
    6. Avoid trading when volatility is in extreme percentiles
    
    Default Parameters:
        ema_fast: 5 (very responsive)
        ema_slow: 13 (trend confirmation)
        rsi_period: 10 (short-term momentum)
        adx_period: 14 (trend strength)
        atr_period: 14 (volatility measure)
        min_confidence: 0.65 (higher bar for entries)
        min_adx: 25.0 (avoid ranging markets)
        max_daily_trades: 2 (limit overtrading)
        min_hold_periods: 6 (3 hours at 30-min intervals)
    """
    
    def __init__(self, config):
        super().__init__(config)
        self._last_trade_time: Optional[datetime] = None
        self._daily_trade_count: int = 0
        self._last_trade_date: Optional[datetime] = None
        
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate indicators for optimized aggressive trading.
        
        Args:
            data: Raw OHLCV DataFrame
            
        Returns:
            DataFrame with all calculated indicators
        """
        df = data.copy()
        
        # Get parameters with defaults
        ema_fast = self.params.get("ema_fast", 5)
        ema_slow = self.params.get("ema_slow", 13)
        rsi_period = self.params.get("rsi_period", 10)
        adx_period = self.params.get("adx_period", 14)
        atr_period = self.params.get("atr_period", 14)
        
        # Trend indicators
        df["ema_fast"] = self._calculate_ema(df["close"], ema_fast)
        df["ema_slow"] = self._calculate_ema(df["close"], ema_slow)
        df["ema_diff"] = df["ema_fast"] - df["ema_slow"]
        df["ema_diff_norm"] = df["ema_diff"] / df["close"]
        
        # Momentum
        df["rsi"] = self._calculate_rsi(df["close"], rsi_period)
        df["rsi_prev"] = df["rsi"].shift(1)
        
        # Volatility
        df["atr"] = self._calculate_atr(df, atr_period)
        df["atr_pct"] = df["atr"] / df["close"]
        
        # Trend strength (ADX)
        df["adx"] = self._calculate_adx(df, adx_period)
        
        # Volume analysis
        df["volume_sma"] = df["volume"].rolling(window=20).mean()
        df["volume_ratio"] = df["volume"] / df["volume_sma"]
        
        # Bollinger Bands for mean reversion detection
        df["bb_upper"], df["bb_middle"], df["bb_lower"] = self._calculate_bollinger_bands(
            df["close"], 20, 2.0
        )
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
        df["bb_position"] = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])
        
        # Price momentum
        df["momentum_3"] = df["close"] - df["close"].shift(3)
        df["momentum_3_norm"] = df["momentum_3"] / df["close"]
        
        # Volatility regime (percentile-based)
        df["atr_percentile"] = df["atr_pct"].rolling(window=50).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
        )
        
        return df
    
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """
        Generate optimized high-frequency signals with risk management.
        
        Args:
            data: DataFrame with OHLCV and indicator data
            
        Returns:
            Signal object with entry/exit recommendation
        """
        df = self.prepare_data(data)
        
        if len(df) < 30:
            return self._neutral_signal(df)
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Get parameters
        min_confidence = self.params.get("min_confidence", 0.65)
        min_adx = self.params.get("min_adx", 25.0)
        max_daily_trades = self.params.get("max_daily_trades", 2)
        min_hold_periods = self.params.get("min_hold_periods", 6)
        
        current_time = df.index[-1]
        current_price = current["close"]
        
        # Reset daily trade count if new day
        if self._last_trade_date is None or current_time.date() != self._last_trade_date.date():
            self._daily_trade_count = 0
            self._last_trade_date = current_time
        
        # Check if we've hit daily trade limit
        if self._daily_trade_count >= max_daily_trades:
            return self._neutral_signal(df, reason="Daily trade limit reached")
        
        # Check minimum holding period
        if self._last_trade_time is not None:
            periods_since_last = len(df[df.index > self._last_trade_time])
            if periods_since_last < min_hold_periods:
                return self._neutral_signal(df, reason="Minimum holding period not met")
        
        # Market regime filter - avoid extreme volatility
        if pd.notna(current["atr_percentile"]) and (current["atr_percentile"] > 0.95 or current["atr_percentile"] < 0.05):
            return self._neutral_signal(df, reason="Extreme volatility regime")
        
        # Calculate ATR-based stops
        atr = current["atr"]
        stop_loss_pct = 1.5 * current["atr_pct"] if pd.notna(current["atr_pct"]) else 0.02
        take_profit_pct = 3.0 * current["atr_pct"] if pd.notna(current["atr_pct"]) else 0.04
        
        # Score long entry conditions
        long_score = 0.0
        long_conditions = []
        
        # 1. Trend alignment with strong ADX
        if (current["ema_fast"] > current["ema_slow"] and 
            current["ema_diff_norm"] > 0.001 and
            pd.notna(current["adx"]) and current["adx"] > min_adx):
            long_score += 0.30
            long_conditions.append("trend_aligned")
        
        # 2. RSI momentum (not overbought, rising)
        if prev["rsi"] < 60 and current["rsi"] > prev["rsi"] and current["rsi"] < 70:
            long_score += 0.25
            long_conditions.append("rsi_momentum")
        
        # 3. Volume confirmation
        if pd.notna(current["volume_ratio"]) and current["volume_ratio"] > 1.2:
            long_score += 0.20
            long_conditions.append("volume_confirm")
        
        # 4. Price above VWAP (BB middle)
        if current["close"] > current["bb_middle"]:
            long_score += 0.15
            long_conditions.append("above_vwap")
        
        # 5. Positive momentum
        if current["momentum_3_norm"] > 0.001:
            long_score += 0.10
            long_conditions.append("positive_momentum")
        
        # Score short entry conditions
        short_score = 0.0
        short_conditions = []
        
        # 1. Trend alignment with strong ADX
        if (current["ema_fast"] < current["ema_slow"] and 
            current["ema_diff_norm"] < -0.001 and
            pd.notna(current["adx"]) and current["adx"] > min_adx):
            short_score += 0.30
            short_conditions.append("trend_aligned")
        
        # 2. RSI momentum (not oversold, falling)
        if prev["rsi"] > 40 and current["rsi"] < prev["rsi"] and current["rsi"] > 30:
            short_score += 0.25
            short_conditions.append("rsi_momentum")
        
        # 3. Volume confirmation
        if pd.notna(current["volume_ratio"]) and current["volume_ratio"] > 1.2:
            short_score += 0.20
            short_conditions.append("volume_confirm")
        
        # 4. Price below VWAP (BB middle)
        if current["close"] < current["bb_middle"]:
            short_score += 0.15
            short_conditions.append("below_vwap")
        
        # 5. Negative momentum
        if current["momentum_3_norm"] < -0.001:
            short_score += 0.10
            short_conditions.append("negative_momentum")
        
        # Generate signal
        if long_score > short_score and long_score >= min_confidence:
            # Volatility-adjusted position sizing
            volatility_factor = max(0.5, min(1.0, 1.0 - current["atr_pct"] * 10))
            adjusted_size = min(
                self.position_size * volatility_factor * (1 + len(long_conditions) * 0.05),
                0.3  # Cap at 30% max
            )
            
            # Calculate stop loss and take profit levels
            stop_loss = current_price * (1 - stop_loss_pct)
            take_profit = current_price * (1 + take_profit_pct)
            
            self._last_trade_time = current_time
            self._daily_trade_count += 1
            
            return Signal(
                strategy=self.name,
                signal=SignalType.LONG,
                confidence=min(long_score + 0.05, 0.95),
                size=adjusted_size,
                timestamp=datetime.now(),
                price=current_price,
                metadata={
                    "conditions_met": len(long_conditions),
                    "conditions": long_conditions,
                    "adx": float(current["adx"]) if pd.notna(current["adx"]) else 0,
                    "rsi": float(current["rsi"]),
                    "atr_pct": float(current["atr_pct"]) if pd.notna(current["atr_pct"]) else 0,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "volatility_factor": volatility_factor
                }
            )
        
        elif short_score > long_score and short_score >= min_confidence:
            # Volatility-adjusted position sizing
            volatility_factor = max(0.5, min(1.0, 1.0 - current["atr_pct"] * 10))
            adjusted_size = min(
                self.position_size * volatility_factor * (1 + len(short_conditions) * 0.05),
                0.3  # Cap at 30% max
            )
            
            # Calculate stop loss and take profit levels
            stop_loss = current_price * (1 + stop_loss_pct)
            take_profit = current_price * (1 - take_profit_pct)
            
            self._last_trade_time = current_time
            self._daily_trade_count += 1
            
            return Signal(
                strategy=self.name,
                signal=SignalType.SHORT,
                confidence=min(short_score + 0.05, 0.95),
                size=adjusted_size,
                timestamp=datetime.now(),
                price=current_price,
                metadata={
                    "conditions_met": len(short_conditions),
                    "conditions": short_conditions,
                    "adx": float(current["adx"]) if pd.notna(current["adx"]) else 0,
                    "rsi": float(current["rsi"]),
                    "atr_pct": float(current["atr_pct"]) if pd.notna(current["atr_pct"]) else 0,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "volatility_factor": volatility_factor
                }
            )
        
        return self._neutral_signal(df)
    
    def reset(self):
        """Reset V3-specific state for fresh backtest runs."""
        super().reset()
        self._last_trade_time = None
        self._daily_trade_count = 0
        self._last_trade_date = None
