from __future__ import annotations

import contextlib
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_LOG_DIR = "logs"
_LOG_FILE = "logs/looking_glass.log"
_DATE_FORMAT = "%d/%m/%Y %H:%M:%S"
_FORMAT = "[{asctime}] [{levelname:<8}] {name}: {message}"


def setup_logging(dev: bool) -> logging.Logger:
    os.makedirs(_LOG_DIR, exist_ok=True)
    logger = logging.getLogger("looking-glass")
    logger.setLevel(logging.DEBUG if dev else logging.INFO)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(_FORMAT, _DATE_FORMAT, style="{")

    file_handler = RotatingFileHandler(
        filename=_LOG_FILE,
        encoding="utf-8",
        maxBytes=50 * 1024 * 1024,
        backupCount=5,
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream = sys.stdout
    if hasattr(stream, "reconfigure"):
        with contextlib.suppress(ValueError, OSError):
            stream.reconfigure(encoding="utf-8", errors="replace")

    console_handler = logging.StreamHandler(stream)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
