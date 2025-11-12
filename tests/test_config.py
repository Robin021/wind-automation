import os
from pathlib import Path

from wind_trader.config import ConfigManager


def test_config_manager_loads_env_secret(tmp_path, monkeypatch):
    config_path = tmp_path / "config.yml"
    data_dir = tmp_path / "data"
    log_file = tmp_path / "logs/app.log"
    config_path.write_text(
        f"""
wind:
  broker_id: "0000"
  department_id: "0"
  logon_account: "ACC"
  password: "env:TEST_WIND_PWD"
  account_type: "SHSZ"
strategy:
  short: 3
  long: 24
  n: 24
  min_history_days: 60
orders:
  volume_per_trade: 100
paths:
  data_root: "{data_dir}"
  log_file: "{log_file}"
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_WIND_PWD", "secret")

    manager = ConfigManager(config_path)
    config = manager.get()

    assert config.wind.password == "secret"
    assert config.paths.data_root == data_dir.resolve()
    assert config.paths.log_file == log_file.resolve()
