"""
Configuration management for trading strategies.

This module handles loading, saving, and managing strategy configurations
from JSON or YAML files.
"""
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Union
from dataclasses import dataclass, asdict, field


@dataclass
class StrategyConfig:
    """
    Base configuration for a trading strategy.
    
    Attributes:
        name: Human-readable strategy name
        enabled: Whether strategy is active (default: True)
        position_size: Position size as fraction of capital (default: 0.1 = 10%)
        max_positions: Maximum concurrent positions for this strategy (default: 1)
        params: Strategy-specific parameters dictionary
    
    Example:
        >>> config = StrategyConfig(
        ...     name="V4 Fixed Stop",
        ...     position_size=0.15,
        ...     params={"stop_loss_pct": 2.0, "take_profit_pct": 4.0}
        ... )
        >>> config.save("config/v4_fixed_stop.json")
    """
    name: str
    enabled: bool = True
    position_size: float = 0.1
    max_positions: int = 1
    params: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if not 0 < self.position_size <= 1:
            raise ValueError(f"position_size must be in (0, 1], got {self.position_size}")
        if self.max_positions < 1:
            raise ValueError(f"max_positions must be >= 1, got {self.max_positions}")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyConfig":
        """
        Create config from dictionary.
        
        Args:
            data: Dictionary with config fields
        
        Returns:
            StrategyConfig instance
        """
        params = data.pop("params", {})
        return cls(params=params, **data)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert config to dictionary.
        
        Returns:
            Dictionary representation of config
        """
        return asdict(self)
    
    @classmethod
    def load(cls, path: Union[str, Path]) -> "StrategyConfig":
        """
        Load config from JSON or YAML file.
        
        Args:
            path: Path to config file (.json or .yaml/.yml)
        
        Returns:
            StrategyConfig instance
        
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        path = Path(path)
        
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        with open(path, "r", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                data = yaml.safe_load(f)
            elif path.suffix == ".json":
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported config format: {path.suffix}")
        
        return cls.from_dict(data)
    
    def save(self, path: Union[str, Path]) -> None:
        """
        Save config to file.
        
        Args:
            path: Destination path (.json or .yaml/.yml)
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding="utf-8") as f:
            if path.suffix in (".yaml", ".yml"):
                yaml.dump(self.to_dict(), f, default_flow_style=False, sort_keys=False)
            else:
                json.dump(self.to_dict(), f, indent=2)
    
    def get_param(self, key: str, default: Any = None) -> Any:
        """
        Get a parameter value with optional default.
        
        Args:
            key: Parameter name
            default: Default value if key not found
        
        Returns:
            Parameter value or default
        """
        return self.params.get(key, default)
    
    def set_param(self, key: str, value: Any) -> None:
        """
        Set a parameter value.
        
        Args:
            key: Parameter name
            value: Parameter value
        """
        self.params[key] = value


class ConfigManager:
    """
    Manage configurations for multiple strategies.
    
    Provides centralized access to strategy configurations with
    automatic loading and caching.
    
    Example:
        >>> mgr = ConfigManager("config")
        >>> config = mgr.get("v3_aggressive")
        >>> configs = mgr.load_all()
    """
    
    def __init__(self, config_dir: Union[str, Path] = "config"):
        """
        Initialize config manager.
        
        Args:
            config_dir: Directory containing config files
        """
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self._configs: Dict[str, StrategyConfig] = {}
    
    def load_all(self) -> Dict[str, StrategyConfig]:
        """
        Load all strategy configs from the config directory.
        
        Returns:
            Dictionary mapping config names to StrategyConfig objects
        """
        # Load JSON configs
        for config_file in self.config_dir.glob("*.json"):
            name = config_file.stem
            try:
                self._configs[name] = StrategyConfig.load(config_file)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Warning: Failed to load {config_file}: {e}")
        
        # Load YAML configs
        for config_file in self.config_dir.glob("*.yaml"):
            name = config_file.stem
            try:
                self._configs[name] = StrategyConfig.load(config_file)
            except (yaml.YAMLError, ValueError) as e:
                print(f"Warning: Failed to load {config_file}: {e}")
        
        return self._configs
    
    def get(self, name: str) -> Optional[StrategyConfig]:
        """
        Get config by name.
        
        Args:
            name: Strategy name (e.g., "v3_aggressive")
        
        Returns:
            StrategyConfig or None if not found
        """
        if name not in self._configs:
            # Try to load from disk
            for ext in [".json", ".yaml", ".yml"]:
                config_path = self.config_dir / f"{name}{ext}"
                if config_path.exists():
                    try:
                        self._configs[name] = StrategyConfig.load(config_path)
                        break
                    except Exception as e:
                        print(f"Warning: Failed to load {config_path}: {e}")
        
        return self._configs.get(name)
    
    def save(self, name: str, config: StrategyConfig) -> None:
        """
        Save a config to disk.
        
        Args:
            name: Config name (used as filename)
            config: StrategyConfig to save
        """
        self._configs[name] = config
        config_path = self.config_dir / f"{name}.json"
        config.save(config_path)
    
    def create_default_configs(self) -> Dict[str, StrategyConfig]:
        """
        Create default configs for all 6 strategies.
        
        Creates optimized default configurations for V1-V6 strategies.
        
        Returns:
            Dictionary of all created configs
        """
        configs = {
            "v1_legacy": StrategyConfig(
                name="V1 Legacy",
                position_size=0.15,
                params={
                    "ema_fast": 9,
                    "ema_slow": 21,
                    "rsi_period": 14,
                    "rsi_overbought": 70,
                    "rsi_oversold": 30
                }
            ),
            "v2_profit_max": StrategyConfig(
                name="V2 Profit Max",
                position_size=0.20,
                params={
                    "ema_fast": 8,
                    "ema_slow": 20,
                    "rsi_period": 12,
                    "take_profit_pct": 3.0,
                    "trailing_stop_pct": 1.5
                }
            ),
            "v3_aggressive": StrategyConfig(
                name="V3 Aggressive",
                position_size=0.20,
                params={
                    "ema_fast": 5,
                    "ema_slow": 13,
                    "rsi_period": 10,
                    "adx_period": 14,
                    "atr_period": 14,
                    "min_confidence": 0.65,
                    "min_adx": 25.0,
                    "max_daily_trades": 2,
                    "min_hold_periods": 6
                }
            ),
            "v4_fixed_stop": StrategyConfig(
                name="V4 Fixed Stop",
                position_size=0.10,
                params={
                    "ema_fast": 12,
                    "ema_slow": 26,
                    "stop_loss_pct": 2.0,
                    "take_profit_pct": 4.0
                }
            ),
            "v5_vwap": StrategyConfig(
                name="V5 VWAP",
                position_size=0.15,
                params={
                    "vwap_period": 14,
                    "mean_reversion_threshold": 0.005,
                    "volume_spike_factor": 1.5
                }
            ),
            "v6_breakout": StrategyConfig(
                name="V6 Breakout",
                position_size=0.20,
                params={
                    "lookback_periods": 20,
                    "breakout_threshold_pct": 1.0,
                    "volume_confirmation": True
                }
            )
        }
        
        for name, config in configs.items():
            self.save(name, config)
        
        return configs
    
    def list_configs(self) -> list:
        """
        List all available config names.
        
        Returns:
            List of config names (without extensions)
        """
        configs = set()
        for ext in [".json", ".yaml", ".yml"]:
            for config_file in self.config_dir.glob(f"*{ext}"):
                configs.add(config_file.stem)
        return sorted(list(configs))
    
    def delete(self, name: str) -> bool:
        """
        Delete a config file.
        
        Args:
            name: Config name to delete
        
        Returns:
            True if deleted, False if not found
        """
        deleted = False
        for ext in [".json", ".yaml", ".yml"]:
            config_path = self.config_dir / f"{name}{ext}"
            if config_path.exists():
                config_path.unlink()
                deleted = True
        
        if name in self._configs:
            del self._configs[name]
        
        return deleted
