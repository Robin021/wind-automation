from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass(frozen=True)
class WindAccountConfig:
    broker_id: str
    department_id: str
    logon_account: str
    password: str
    account_type: str


@dataclass(frozen=True)
class StrategyConfig:
    short: int
    long: int
    n: int
    min_history_days: int


@dataclass(frozen=True)
class RetryConfig:
    attempts: int = 3
    backoff_seconds: List[int] = field(default_factory=lambda: [1, 2, 4])


@dataclass(frozen=True)
class OrderConfig:
    volume_per_trade: int
    retry: RetryConfig


@dataclass(frozen=True)
class PathsConfig:
    data_root: Path
    log_file: Path

    @property
    def stocks_dir(self) -> Path:
        return self.data_root / "stocks"

    @property
    def trades_dir(self) -> Path:
        return self.data_root / "trades"

    @property
    def pending_orders_dir(self) -> Path:
        return self.data_root / "pending_orders"

    @property
    def reports_dir(self) -> Path:
        return self.data_root / "reports"


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    max_bytes: int = 1_048_576
    backup_count: int = 10


@dataclass(frozen=True)
class AppConfig:
    wind: WindAccountConfig
    strategy: StrategyConfig
    orders: OrderConfig
    paths: PathsConfig
    logging: LoggingConfig


class ConfigManager:
    """Load and validate configuration from YAML."""

    def __init__(self, config_path: str | Path):
        self._config_path = Path(config_path)
        self._config: Optional[AppConfig] = None

    @property
    def config_path(self) -> Path:
        return self._config_path

    def load(self) -> AppConfig:
        raw = self._read_yaml()
        self._config = self._build_config(raw)
        return self._config

    def get(self) -> AppConfig:
        if self._config is None:
            return self.load()
        return self._config

    def _read_yaml(self) -> Dict[str, Any]:
        if not self._config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self._config_path}")
        with self._config_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        if not isinstance(data, dict):
            raise ValueError("Configuration root must be a mapping.")
        return data

    def _build_config(self, data: Dict[str, Any]) -> AppConfig:
        base_dir = self._config_path.parent
        wind_cfg = self._build_wind_config(data.get("wind", {}))
        strategy_cfg = self._build_strategy_config(data.get("strategy", {}))
        order_cfg = self._build_order_config(data.get("orders", {}))
        paths_cfg = self._build_paths_config(data.get("paths", {}), base_dir)
        logging_cfg = self._build_logging_config(data.get("logging", {}))
        return AppConfig(
            wind=wind_cfg,
            strategy=strategy_cfg,
            orders=order_cfg,
            paths=paths_cfg,
            logging=logging_cfg,
        )

    def _build_wind_config(self, section: Dict[str, Any]) -> WindAccountConfig:
        required = ["broker_id", "department_id", "logon_account", "password", "account_type"]
        missing = [key for key in required if key not in section]
        if missing:
            raise ValueError(f"Missing wind config keys: {missing}")
        return WindAccountConfig(
            broker_id=str(section["broker_id"]),
            department_id=str(section["department_id"]),
            logon_account=str(section["logon_account"]),
            password=self._resolve_secret(section["password"]),
            account_type=str(section["account_type"]),
        )

    def _build_strategy_config(self, section: Dict[str, Any]) -> StrategyConfig:
        required = ["short", "long", "n", "min_history_days"]
        missing = [key for key in required if key not in section]
        if missing:
            raise ValueError(f"Missing strategy config keys: {missing}")
        return StrategyConfig(
            short=int(section["short"]),
            long=int(section["long"]),
            n=int(section["n"]),
            min_history_days=int(section["min_history_days"]),
        )

    def _build_order_config(self, section: Dict[str, Any]) -> OrderConfig:
        if "volume_per_trade" not in section:
            raise ValueError("orders.volume_per_trade is required.")
        retry_section = section.get("retry", {})
        attempts = int(retry_section.get("attempts", 3))
        backoff = retry_section.get("backoff_seconds", [1, 2, 4])
        if not isinstance(backoff, list) or not backoff:
            raise ValueError("orders.retry.backoff_seconds must be a non-empty list.")
        backoff_list = [int(x) for x in backoff]
        retry = RetryConfig(attempts=attempts, backoff_seconds=backoff_list)
        return OrderConfig(volume_per_trade=int(section["volume_per_trade"]), retry=retry)

    def _build_paths_config(self, section: Dict[str, Any], base_dir: Path) -> PathsConfig:
        if "data_root" not in section or "log_file" not in section:
            raise ValueError("paths.data_root and paths.log_file are required.")
        data_root = (base_dir / section["data_root"]).resolve()
        log_file = (base_dir / section["log_file"]).resolve()
        return PathsConfig(data_root=data_root, log_file=log_file)

    def _build_logging_config(self, section: Dict[str, Any]) -> LoggingConfig:
        return LoggingConfig(
            level=str(section.get("level", "INFO")),
            max_bytes=int(section.get("max_bytes", 1_048_576)),
            backup_count=int(section.get("backup_count", 10)),
        )

    def _resolve_secret(self, value: Any) -> str:
        if isinstance(value, str) and value.startswith("env:"):
            env_key = value.split("env:", maxsplit=1)[1]
            env_value = _get_env(env_key)
            if env_value is None:
                raise ValueError(f"Environment variable {env_key!r} is not set.")
            return env_value
        return str(value)


def _get_env(key: str) -> Optional[str]:
    from os import getenv

    return getenv(key)
