"""Structured JSON logging with a per-request id, and PII-safe by construction.

AC11 requires that no scan/mask/redact/tokenize/detokenize event ever write an original
sensitive value or a vault mapping's plaintext to the log. This module gives every log
line a fixed, closed set of fields (see ``audit.service.log_event``): callers pass counts
and categories, never raw values, and this formatter additionally redacts any field whose
key looks like a secret or credential as defence in depth.
"""

from __future__ import annotations

import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

import orjson

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

_RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}
_TOKEN_IN_URL = re.compile(r"((?:^|[?&\s])token=)[^&\s\"']+")
_REDACT = {
    "authorization",
    "api_key",
    "password",
    "secret",
    "secret_hash",
    "token",
    "x-api-key",
    "plaintext",
    "value",
    "original_value",
    "ciphertext",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "msg": _TOKEN_IN_URL.sub(r"\1[redacted]", record.getMessage()),
        }
        rid = request_id_var.get()
        if rid:
            payload["request_id"] = rid
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = "[redacted]" if key.lower() in _REDACT else value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return orjson.dumps(payload, default=str).decode()


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("uvicorn.access", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
