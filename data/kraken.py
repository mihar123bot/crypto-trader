"""
Kraken API data ingestion module.
Fetches OHLCV candles for BTC/USD.
"""
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import time

from core import OHLCV


class KrakenDataSource:
    """Unified data ingestion from Kraken API."""
    
    BASE_URL = "https://api.kraken.com/0/public"
    
    # Interval mapping (in minutes)
    INTERVALS = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
        "1w": 10080
    }
    
    def __init__(self, pair: str = "XBTUSD"):
        self.pair = pair
        self.session = requests.Session()
    
    def fetch_ohlcv(
        self,
        interval: str = "30m",
        since: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[OHLCV]:
        """
        Fetch OHLCV candles from Kraken.
        
        Args:
            interval: Candle interval (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w)
            since: Starting timestamp (optional)
            limit: Maximum candles to fetch (optional, API limits to 720)
        
        Returns:
            List of OHLCV candles
        """
        if interval not in self.INTERVALS:
            raise ValueError(f"Invalid interval: {interval}")
        
        url = f"{self.BASE_URL}/OHLC"
        params = {
            "pair": self.pair,
            "interval": self.INTERVALS[interval]
        }
        if since:
            params["since"] = since
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("error"):
            raise Exception(f"Kraken API error: {data['error']}")
        
        # Parse response
        result_key = list(data["result"].keys())[0]
        candles = data["result"][result_key]
        
        ohlcv_list = []
        for candle in candles:
            # Kraken format: [time, open, high, low, close, vwap, volume, count]
            ohlcv_list.append(OHLCV(
                timestamp=datetime.fromtimestamp(int(candle[0])),
                open=float(candle[1]),
                high=float(candle[2]),
                low=float(candle[3]),
                close=float(candle[4]),
                volume=float(candle[6])
            ))
        
        if limit:
            ohlcv_list = ohlcv_list[-limit:]
        
        return ohlcv_list
    
    def fetch_historical(
        self,
        days: int = 90,
        interval: str = "30m"
    ) -> pd.DataFrame:
        """
        Fetch historical data for backtesting.
        
        Args:
            days: Number of days to fetch
            interval: Candle interval
        
        Returns:
            DataFrame with OHLCV data
        """
        # Calculate how many candles we need
        interval_mins = self.INTERVALS[interval]
        candles_needed = int((days * 24 * 60) / interval_mins)
        
        # Kraken limits to 720 candles per request
        all_candles = []
        since = int((datetime.now() - timedelta(days=days)).timestamp())
        
        while len(all_candles) < candles_needed:
            candles = self.fetch_ohlcv(interval=interval, since=since)
            
            if not candles:
                break
            
            all_candles.extend(candles)
            
            # Update since to last candle + 1 interval
            last_ts = int(candles[-1].timestamp.timestamp())
            since = last_ts + (interval_mins * 60)
            
            # Rate limiting
            time.sleep(0.5)
            
            if len(candles) < 720:
                break
        
        # Convert to DataFrame
        df = pd.DataFrame([
            {
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            }
            for c in all_candles[:candles_needed]
        ])
        
        df.set_index("timestamp", inplace=True)
        return df
    
    def get_ticker(self) -> Dict[str, Any]:
        """Get current ticker price."""
        url = f"{self.BASE_URL}/Ticker"
        params = {"pair": self.pair}
        
        response = self.session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("error"):
            raise Exception(f"Kraken API error: {data['error']}")
        
        result_key = list(data["result"].keys())[0]
        return data["result"][result_key]
    
    def get_current_price(self) -> float:
        """Get current market price."""
        ticker = self.get_ticker()
        return float(ticker["c"][0])  # Last trade closed price
