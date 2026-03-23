"""Tests for ActionLogEntry dataclass and JsonFormatter."""
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from models.action_log import ActionLogEntry, JsonFormatter, parse_action_history


class TestActionLogEntry:
    """Test ActionLogEntry dataclass creation and serialization."""

    def test_creation_with_required_fields(self):
        """ActionLogEntry can be created with all required fields."""
        entry = ActionLogEntry(
            timestamp=datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc),
            level="INFO",
            action="relist",
            player_name="Mbappé",
            success=True,
            message="Rilist completato",
        )
        assert entry.level == "INFO"
        assert entry.action == "relist"
        assert entry.player_name == "Mbappé"
        assert entry.success is True
        assert entry.message == "Rilist completato"

    def test_to_dict_produces_correct_structure(self):
        """to_dict() returns flat dict suitable for JSON serialization."""
        entry = ActionLogEntry(
            timestamp=datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc),
            level="ERROR",
            action="relist",
            player_name="Haaland",
            success=False,
            message="Errore durante rilist",
            error="TimeoutError: element not found",
            extra={"attempt": 1},
        )
        d = entry.to_dict()
        assert d["level"] == "ERROR"
        assert d["action"] == "relist"
        assert d["player_name"] == "Haaland"
        assert d["success"] is False
        assert d["error"] == "TimeoutError: element not found"
        assert d["extra"] == {"attempt": 1}
        assert "timestamp" in d

    def test_from_dict_round_trips_correctly(self):
        """from_dict() reconstructs ActionLogEntry identical to original."""
        original = ActionLogEntry(
            timestamp=datetime(2026, 3, 23, 12, 0, 0, tzinfo=timezone.utc),
            level="WARNING",
            action="scan",
            player_name=None,
            success=True,
            message="Scansione completata",
            error=None,
            extra={"count": 5},
        )
        d = original.to_dict()
        restored = ActionLogEntry.from_dict(d)
        assert restored.level == original.level
        assert restored.action == original.action
        assert restored.player_name == original.player_name
        assert restored.success == original.success
        assert restored.message == original.message
        assert restored.extra == original.extra


class TestJsonFormatter:
    """Test JsonFormatter logging formatter."""

    def test_produces_valid_json_with_expected_keys(self):
        """JsonFormatter.format() returns valid JSON with timestamp, level, logger, message."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Messaggio di test",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["message"] == "Messaggio di test"
        assert "timestamp" in parsed

    def test_includes_exception_info_when_present(self):
        """JsonFormatter includes exception traceback when exc_info is set."""
        formatter = JsonFormatter()
        try:
            raise ValueError("errore di test")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Errore",
            args=(),
            exc_info=exc_info,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_includes_extra_fields(self):
        """JsonFormatter includes extra fields (action, player_name, success)."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Rilist completato",
            args=(),
            exc_info=None,
        )
        record.action = "relist"
        record.player_name = "Messi"
        record.success = True
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["action"] == "relist"
        assert parsed["player_name"] == "Messi"
        assert parsed["success"] is True


class TestParseActionHistory:
    """Test parse_action_history JSONL reader."""

    def test_parses_jsonl_file(self):
        """parse_action_history reads last N lines of JSONL file."""
        lines = [
            json.dumps({"level": "INFO", "message": "Azione 1"}),
            json.dumps({"level": "ERROR", "message": "Azione 2"}),
            json.dumps({"level": "INFO", "message": "Azione 3"}),
        ]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("\n".join(lines) + "\n")
            f.flush()
            path = Path(f.name)

        result = parse_action_history(path, lines=2)
        assert len(result) == 2
        assert result[0]["message"] == "Azione 2"
        assert result[1]["message"] == "Azione 3"

        path.unlink()
