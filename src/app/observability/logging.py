import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Optional
from contextvars import ContextVar

# Correlation ID context for tracing requests across logs
correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)

# Patterns for masking secrets
SECRET_PATTERNS = [
    re.compile(r"(bot[0-9]{8,10}:[a-zA-Z0-9_-]{35})", re.IGNORECASE),
    re.compile(r"(password[:=]\s*['\"]?)([^'\"\s]+)", re.IGNORECASE),
    re.compile(r"(token[:=]\s*['\"]?)([^'\"\s]+)", re.IGNORECASE),
    re.compile(r"(secret[:=]\s*['\"]?)([^'\"\s]+)", re.IGNORECASE),
]


class SecretMaskingFormatter(logging.Formatter):
    """Custom formatter that automatically scrubs sensitive credentials and attaches correlation IDs."""

    def format(self, record: logging.LogRecord) -> str:
        # Inject correlation_id if available
        cid = correlation_id_ctx.get()
        record.correlation_id = f"[{cid}] " if cid else ""
        formatted = super().format(record)
        for pattern in SECRET_PATTERNS:
            formatted = pattern.sub(r"\1***MASKED***", formatted)
        return formatted


def setup_logging(logs_dir: str = "logs", log_level: str = "INFO") -> None:
    """Configures rotating file logs and console logs."""
    os.makedirs(logs_dir, exist_ok=True)
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    root_logger.handlers.clear()

    log_format = (
        "%(asctime)s | %(levelname)-7s | %(correlation_id)s%(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    formatter = SecretMaskingFormatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")

    # 1. Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 2. General App Rotating File (10 MB x 5 backups)
    app_file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "app.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    app_file_handler.setLevel(logging.INFO)
    app_file_handler.setFormatter(formatter)
    root_logger.addHandler(app_file_handler)

    # 3. Error Rotating File (10 MB x 5 backups)
    error_file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "errors.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(formatter)
    root_logger.addHandler(error_file_handler)

    # 4. Audit logger for financial & security events
    audit_logger = logging.getLogger("audit")
    audit_file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "audit.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    audit_file_handler.setLevel(logging.INFO)
    audit_file_handler.setFormatter(formatter)
    audit_logger.addHandler(audit_file_handler)
    audit_logger.propagate = True


def get_logger(name: str) -> logging.Logger:
    """Convenience accessor for named loggers."""
    return logging.getLogger(name)
