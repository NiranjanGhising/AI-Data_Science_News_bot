import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


_LOGGER: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    logger = logging.getLogger("opportunity_radar")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    os.makedirs("logs", exist_ok=True)
    handler = logging.FileHandler(os.path.join("logs", "opportunity_radar.log"), encoding="utf-8")
    handler.setLevel(logging.INFO)

    class JsonLineFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload: dict[str, Any]
            if isinstance(record.msg, dict):
                payload = record.msg
            else:
                payload = {"message": str(record.getMessage())}
            payload.setdefault("ts", datetime.now(timezone.utc).isoformat())
            payload.setdefault("level", record.levelname)
            return json.dumps(payload, ensure_ascii=False)

    handler.setFormatter(JsonLineFormatter())
    logger.addHandler(handler)

    # In GitHub Actions, also log to stdout so run logs show pipeline counts/errors.
    if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
        sh = logging.StreamHandler(stream=sys.stdout)
        sh.setLevel(logging.INFO)
        sh.setFormatter(JsonLineFormatter())
        logger.addHandler(sh)

    _LOGGER = logger
    return logger


def log_event(event: str, **fields: Any) -> None:
    logger = get_logger()
    logger.info({"event": event, **fields})
