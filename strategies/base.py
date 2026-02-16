"""
Base strategy class that all strategies must implement.

This module provides the abstract base class and utility methods
for implementing trading strategies.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple, Union
import pandas as pd
import numpy as np

from core import Signal, SignalType
from config.manager import StrategyConfig


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    All strategies must inherit from this class and implement
    the generate_signal and prepare_data methods.
    
    Attributes:
        config: Strategy configuration object
        name: Strategy name
        position_size: Default position size as fraction of capital
        params: Strategy-specific parameters dictionary
    
    Example:
        >>> from config.manager import StrategyConfig
        >>> config = StrategyConfig(name="MyStrategy", position_size=0.1)
        >>> strategy = MyStrategy(config)
        >>> signal = strategy.generate_signal(data)
    """
    
    def __init__(self, config: StrategyConfig):
        """
        Initialize strategy with configuration.
        
        Args:
            config: StrategyConfig with parameters and settings
        """
        self.config = config
        self.name = config.name
        self.position_size = config.position_size
        self.params = config.params
    
    def reset(self):
        """
        Reset any mutable state for a fresh backtest run.
        
        Subclasses should override this to reset their own state,
        calling super().reset() first.
        """
        pass
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Signal:
        """
        Generate trading signal from OHLCV data.
        
        This is the main entry point for strategy logic. Implementations
        should analyze the data and return a Signal indicating whether
        to enter a LONG, SHORT, or stay NEUTRAL.
        
        Args:
            data: DataFrame with OHLCV data including indicators
                 from prepare_data(). Must have at least:
                 - open, high, low, close, volume columns
                 - Any indicators added by prepare_data()
        
        Returns:
            Signal object with trading recommendation
        
        Raises:
            ValueError: If data format is invalid
        """
        pass
    
    @abstractmethod
    def prepare_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data with necessary indicators.
        
        Called before generate_signal to calculate any indicators
        needed by the strategy. Should add new columns to the DataFrame.
        
        Args:
            data: Raw OHLCV DataFrame with columns:
                 - open, high, low, close, volume
        
        Returns:
            DataFrame with additional indicator columns
        
        Example:
            >>> df["ema_20"] = self._calculate_ema(df["close"], 20)
            >>> df["rsi"] = self._calculate_rsi(df["close"], 14)
        """
        pass
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Validate that data has required columns.
        
        Args:
            data: DataFrame to validate
        
        Returns:
            True if valid, raises ValueError otherwise
        
        Raises:
            ValueError: If required columns are missing
        """
        required_columns = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required_columns if col not in data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        if len(data) < 2:
            raise ValueError("Data must have at least 2 rows")
        return True
    
    def calculate_confidence(
        self,
        signal_type: SignalType,
        data: pd.DataFrame,
        **factors: float
    ) -> float:
        """
        Calculate confidence score for a signal.
        
        Base implementation provides a simple weighted scoring.
        Strategies can override this for custom logic.
        
        Args:
            signal_type: Type of signal being generated
            data: DataFrame with indicators
            **factors: Additional scoring factors:
                - trend_strength: 0.0 to 1.0
                - volume_ratio: Current volume / average volume
                - volatility_regime: -1.0 (low) to 1.0 (high)
        
        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = 0.5
        
        # Adjust based on trend strength
        if "trend_strength" in factors:
            base_confidence += factors["trend_strength"] * 0.2
        
        # Adjust based on volume
        if "volume_ratio" in factors:
            base_confidence += min(factors["volume_ratio"] - 1, 1) * 0.15
        
        # Adjust based on volatility regime
        if "volatility_regime" in factors:
            base_confidence += factors["volatility_regime"] * 0.1
        
        return min(max(base_confidence, 0.0), 1.0)
    
    def _neutral_signal(
        self,
        df: pd.DataFrame,
        reason: str = ""
    ) -> Signal:
        """
        Generate a neutral (no-op) signal.
        
        Args:
            df: DataFrame with price data
            reason: Optional reason for neutrality
            
        Returns:
            Neutral Signal object
        """
        from datetime import datetime
        price = df.iloc[-1]["close"] if len(df) > 0 else 0
        return Signal(
            strategy=self.name,
            signal=SignalType.NEUTRAL,
            confidence=0.0,
            size=0.0,
            timestamp=datetime.now(),
            price=price,
            metadata={"reason": reason} if reason else {}
        )
    
    def _calculate_ema(
        self, 
        series: pd.Series, 
        period: int
    ) -> pd.Series:
        """
        Calculate exponential moving average.
        
        Args:
            series: Price series data
            period: EMA lookback period
        
        Returns:
            Series with EMA values
        """
        return series.ewm(span=period, adjust=False).mean()
    
    def _calculate_sma(
        self, 
        series: pd.Series, 
        period: int
    ) -> pd.Series:
        """
        Calculate simple moving average.
        
        Args:
            series: Price series data
            period: SMA lookback period
        
        Returns:
            Series with SMA values
        """
        return series.rolling(window=period).mean()
    
    def _calculate_rsi(
        self, 
        series: pd.Series, 
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).
        
        Args:
            series: Price series data
            period: RSI lookback period (default: 14)
        
        Returns:
            Series with RSI values (0-100)
        """
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_vwap(
        self, 
        data: pd.DataFrame, 
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Volume Weighted Average Price (VWAP).
        
        Args:
            data: DataFrame with high, low, close, volume columns
            period: VWAP lookback period
        
        Returns:
            Series with VWAP values
        """
        typical_price = (data["high"] + data["low"] + data["close"]) / 3
        volume = data["volume"]
        
        vwap = (
            (typical_price * volume).rolling(window=period).sum() / 
            volume.rolling(window=period).sum()
        )
        return vwap
    
    def _calculate_atr(
        self, 
        data: pd.DataFrame, 
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average True Range (ATR).
        
        ATR measures market volatility by decomposing the entire
        range of an asset price for that period.
        
        Args:
            data: DataFrame with high, low, close columns
            period: ATR lookback period (default: 14)
        
        Returns:
            Series with ATR values
        """
        high_low = data["high"] - data["low"]
        high_close = np.abs(data["high"] - data["close"].shift())
        low_close = np.abs(data["low"] - data["close"].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def _calculate_adx(
        self,
        data: pd.DataFrame,
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Average Directional Index (ADX).
        
        ADX measures trend strength regardless of direction.
        Values above 25 indicate a strong trend.
        
        Args:
            data: DataFrame with high, low, close columns
            period: Lookback period for ADX (default: 14)
            
        Returns:
            Series with ADX values
        """
        high = data["high"]
        low = data["low"]
        close = data["close"]
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
        minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
        
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
        minus_di = 100 * minus_dm.rolling(window=period).mean() / atr
        
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di) * 100).fillna(0)
        adx = dx.rolling(window=period).mean()
        
        return adx
    
    def _calculate_bollinger_bands(
        self,
        series: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Bollinger Bands.
        
        Bollinger Bands consist of a middle band (SMA) and two
        outer bands (SMA +/- standard deviations).
        
        Args:
            series: Price series data
            period: SMA period for middle band (default: 20)
            std_dev: Number of standard deviations (default: 2.0)
        
        Returns:
            Tuple of (upper_band, middle_band, lower_band)
        """
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return upper, sma, lower
    
    def _calculate_macd(
        self,
        series: pd.Series,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
    ) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).
        
        Args:
            series: Price series data
            fast: Fast EMA period (default: 12)
            slow: Slow EMA period (default: 26)
            signal: Signal line period (default: 9)
        
        Returns:
            Tuple of (macd_line, signal_line, histogram)
        """
        ema_fast = self._calculate_ema(series, fast)
        ema_slow = self._calculate_ema(series, slow)
        macd_line = ema_fast - ema_slow
        signal_line = self._calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def _calculate_stochastic(
        self,
        data: pd.DataFrame,
        k_period: int = 14,
        d_period: int = 3
    ) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Stochastic Oscillator.
        
        Args:
            data: DataFrame with high, low, close columns
            k_period: %K period (default: 14)
            d_period: %D period (default: 3)
        
        Returns:
            Tuple of (%K, %D) series
        """
        lowest_low = data["low"].rolling(window=k_period).min()
        highest_high = data["high"].rolling(window=k_period).max()
        
        k = 100 * (data["close"] - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=d_period).mean()
        
        return k, d
