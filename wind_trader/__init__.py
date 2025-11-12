"""Wind 夜间委托自动化系统核心包。"""

from importlib.metadata import version, PackageNotFoundError


def get_version() -> str:
    """Return package version if installed, otherwise development marker."""
    try:
        return version("wind_trader")
    except PackageNotFoundError:
        return "0.1.0-dev"


__all__ = ["get_version"]
