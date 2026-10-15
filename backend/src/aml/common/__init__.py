"""Shared foundation: settings and logging. Imports nothing else from aml."""

from aml.common.config import Settings, get_settings
from aml.common.logging import configure_logging, get_logger

__all__ = ["Settings", "configure_logging", "get_logger", "get_settings"]
