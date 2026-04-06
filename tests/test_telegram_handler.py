"""Test per TelegramHandler — parsing comandi, routing e risposte."""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from bot_state import BotState
from telegram_handler import TelegramHandler


@pytest.fixture
def bot_state():
    """BotState pulito per ogni test."""
    return BotState()


@pytest.fixture
def handler(bot_state):
    """TelegramHandler con token/chat_id fittizi."""
    return TelegramHandler(
        token="123456:TEST",
        chat_id="999888",
        bot_state=bot_state,
        log_dir=Path("logs"),
    )


class TestParseCommand:
    """Test per il parsing dei comandi Telegram."""

    def test_parse_status(self, handler):
        """/status → ("status", [])."""
        cmd, args = handler._parse_command("/status")
        assert cmd == "status"
        assert args == []

    def test_parse_logs_with_arg(self, handler):
        """/logs 10 → ("logs", ["10"])."""
        cmd, args = handler._parse_command("/logs 10")
        assert cmd == "logs"
        assert args == ["10"]

    def test_parse_pause(self, handler):
        """/pause → ("pause", [])."""
        cmd, args = handler._parse_command("/pause")
        assert cmd == "pause"
        assert args == []

    def test_parse_unknown(self, handler):
        """/unknown → ("unknown", [])."""
        cmd, args = handler._parse_command("/unknown")
        assert cmd == "unknown"
        assert args == []

    def test_parse_command_no_slash(self, handler):
        """Testo senza slash → ("unknown", [])."""
        cmd, args = handler._parse_command("ciao")
        assert cmd == "unknown"
        assert args == []

    def test_parse_empty_command(self, handler):
        """Solo slash → ("unknown", [])."""
        cmd, args = handler._parse_command("/")
        assert cmd == "unknown"
        assert args == []


class TestHandleCommand:
    """Test per l'esecuzione dei comandi."""

    def test_handle_status(self, handler, bot_state):
        """_handle_command("status") → messaggio formattato con stato."""
        bot_state.set_paused(True)
        bot_state.update_stats(cycle=5, relisted=10, failed=2)
        msg = handler._handle_command("status", [])
        assert "Pausa" in msg or "Sospeso" in msg or "stato" in msg.lower()
        assert "5" in msg  # cycle count

    def test_handle_pause(self, handler, bot_state):
        """/pause → bot_state.set_paused(True), messaggio di pausa."""
        msg = handler._handle_command("pause", [])
        assert bot_state.is_paused() is True
        assert "pausa" in msg.lower() or "⏸" in msg

    def test_handle_resume(self, handler, bot_state):
        """/resume → bot_state.set_paused(False), messaggio di riavvio."""
        bot_state.set_paused(True)
        msg = handler._handle_command("resume", [])
        assert bot_state.is_paused() is False
        assert "riavviat" in msg.lower() or "▶" in msg

    def test_handle_force_relist(self, handler, bot_state):
        """/force_relist → set_force_relist(True), messaggio."""
        msg = handler._handle_command("force_relist", [])
        assert bot_state.consume_force_relist() is True
        assert "force" in msg.lower() or "⚡" in msg

    def test_handle_help(self, handler):
        """/help → lista comandi formattata."""
        msg = handler._handle_command("help", [])
        assert "status" in msg.lower()
        assert "pause" in msg.lower()
        assert "resume" in msg.lower()
        assert "force_relist" in msg.lower() or "force" in msg.lower()

    def test_handle_logs_default(self, handler):
        """/logs → ultime 20 righe di logs/app.log."""
        log_content = "\n".join(f"Line {i}" for i in range(30))
        with patch.object(Path, "read_text", return_value=log_content):
            msg = handler._handle_command("logs", [])
        # Dovrebbe restituire le ultime 20 righe
        assert "Line 29" in msg  # ultima riga
        assert "Line 10" in msg  # prima delle ultime 20 (30-20=10)

    def test_handle_logs_with_count(self, handler):
        """/logs 5 → ultime 5 righe."""
        log_content = "\n".join(f"Line {i}" for i in range(10))
        with patch.object(Path, "read_text", return_value=log_content):
            msg = handler._handle_command("logs", ["5"])
        assert "Line 9" in msg
        assert "Line 5" in msg
        assert "Line 4" not in msg  # solo ultime 5

    def test_handle_unknown(self, handler):
        """/unknown → messaggio di errore."""
        msg = handler._handle_command("unknown", [])
        assert "sconosciuto" in msg.lower() or "❌" in msg

    def test_handle_logs_no_file(self, handler):
        """/logs quando il file non esiste → messaggio di errore."""
        with patch.object(Path, "read_text", side_effect=FileNotFoundError):
            msg = handler._handle_command("logs", [])
        assert "errore" in msg.lower() or "non" in msg.lower() or "❌" in msg


class TestAuthorization:
    """Test per il controllo chat_id autorizzato."""

    def test_authorized_chat_id(self, handler):
        """Chat ID autorizzato → comando elaborato."""
        update = {
            "message": {
                "chat": {"id": 999888},
                "text": "/status",
                "message_id": 1,
            }
        }
        # Non deve lanciare eccezioni
        handler._handle_update(update)

    def test_unauthorized_chat_id(self, handler):
        """Chat ID non autorizzato → comando ignorato."""
        update = {
            "message": {
                "chat": {"id": 111222},
                "text": "/status",
                "message_id": 1,
            }
        }
        # Non deve inviare messaggi né elaborare comandi
        with patch.object(handler, "_send_message") as mock_send:
            handler._handle_update(update)
            mock_send.assert_not_called()


class TestGetUpdates:
    """Test per il polling degli aggiornamenti Telegram."""

    def test_get_updates_mocked(self, handler):
        """_get_updates(offset=0) → lista di update."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "ok": True,
            "result": [
                {"update_id": 1, "message": {"chat": {"id": 999888}, "text": "/status", "message_id": 1}}
            ],
        }).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            updates = handler._get_updates(offset=0)

        assert len(updates) == 1
        assert updates[0]["update_id"] == 1


class TestSendMessage:
    """Test per l'invio messaggi Telegram."""

    def test_send_message_mocked(self, handler):
        """_send_message(text) → POST a sendMessage."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
            handler._send_message("Test message")

        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        # Verifica che la URL contenga sendMessage
        assert "sendMessage" in req.full_url


class TestHandlerLifecycle:
    """Test per start/stop del handler."""

    def test_start_stop(self, handler):
        """start() → thread attivo, stop() → thread terminato."""
        with patch.object(handler, "_poll"):
            handler.start()
            assert handler._running is True
            handler.stop()
            assert handler._running is False
