"""Structured-event emitter to CloudWatch Logs.

Anything tagged ACCESS_DENIED is matched by the metric filter installed by
infra/create_cloudwatch_alarm.sh and feeds the EHR-AccessDenied-Burst alarm.
"""
import json
import time
from typing import Any, Dict

from . import config

_initialized = False


def _ensure_stream() -> None:
    global _initialized
    if _initialized:
        return
    try:
        config.logs().create_log_group(logGroupName=config.LOG_GROUP)
    except Exception:
        pass
    try:
        config.logs().create_log_stream(
            logGroupName=config.LOG_GROUP, logStreamName=config.LOG_STREAM
        )
    except Exception:
        pass
    _initialized = True


def emit(event: str, **fields: Any) -> None:
    _ensure_stream()
    msg = {"event": event, **fields}
    try:
        config.logs().put_log_events(
            logGroupName=config.LOG_GROUP,
            logStreamName=config.LOG_STREAM,
            logEvents=[{
                "timestamp": int(time.time() * 1000),
                "message": json.dumps(msg),
            }],
        )
    except Exception:
        # Logging must never break the app
        pass
