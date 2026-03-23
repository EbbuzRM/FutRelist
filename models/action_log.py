"""Action log data model and JSON formatter.

Provides ActionLogEntry dataclass for structured logging and JsonFormatter
for JSONL output to logs/actions.jsonl.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

VALID_LEVELS = {"INFO", "WARNING", "ERROR"}


@dataclass
class ActionLogEntry:
    """Entry di log per un'azione eseguita dal tool.

    Segue lo stesso pattern di RelistResult in models/relist_result.py.
    """

    timestamp: datetime
    level: str
    action: str
    success: bool
    message: str
    player_name: str | None = None
    error: str | None = None
    extra: dict | None = None

    def __post_init__(self):
        if self.level not in VALID_LEVELS:
            raise ValueError(
                f"level deve essere uno di {VALID_LEVELS}, ricevuto '{self.level}'"
            )
        if not self.action:
            raise ValueError("action non può essere vuota")

    def to_dict(self) -> dict:
        """Converte in dizionario per serializzazione JSON."""
        d = {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "action": self.action,
            "player_name": self.player_name,
            "success": self.success,
            "message": self.message,
            "error": self.error,
        }
        if self.extra is not None:
            d["extra"] = self.extra
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ActionLogEntry:
        """Ricostruisce ActionLogEntry da un dizionario parsato."""
        ts = data.get("timestamp", "")
        if isinstance(ts, str):
            timestamp = datetime.fromisoformat(ts)
        else:
            timestamp = ts
        return cls(
            timestamp=timestamp,
            level=data["level"],
            action=data["action"],
            player_name=data.get("player_name"),
            success=data["success"],
            message=data["message"],
            error=data.get("error"),
            extra=data.get("extra"),
        )


class JsonFormatter(logging.Formatter):
    """Formatter che emette un oggetto JSON per riga (JSONL).

    Output: timestamp (UTC ISO), level, logger name, message + campi extra.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_dict = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include extra fields if present
        for key in ("action", "player_name", "success"):
            if hasattr(record, key):
                log_dict[key] = getattr(record, key)

        # Include any other extra fields not in standard LogRecord attrs
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "action", "player_name", "success",
        }
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_dict[key] = value

        # Include exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            log_dict["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_dict, ensure_ascii=False, default=str)


def parse_action_history(path: Path, lines: int = 20) -> list[dict]:
    """Legge le ultime N righe da un file JSONL.

    Ritorna lista di dizionari parsati.
    """
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        all_lines = f.readlines()

    # Take last N non-empty lines
    non_empty = [line.strip() for line in all_lines if line.strip()]
    tail = non_empty[-lines:]

    result = []
    for line in tail:
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result
