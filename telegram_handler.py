"""TelegramHandler — gestione comandi Telegram via long polling.

Permette di controllare il bot da remoto tramite comandi Telegram:
/status, /pause, /resume, /force_relist, /screenshot, /del_sold, /logs, /help.

Utilizza urllib per le chiamate API Telegram (nessuna dipendenza aggiuntiva).
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

from bot_state import BotState

logger = logging.getLogger(__name__)


class TelegramHandler:
    """Gestisce il polling e l'esecuzione dei comandi Telegram.

    Args:
        token: Token del bot Telegram.
        chat_id: Chat ID autorizzato a inviare comandi.
        bot_state: Istanza condivisa di BotState.
        page: Playwright page (opzionale, per screenshot e sold cleanup).
        log_dir: Directory dei log (default: logs/).
    """

    # Mappa comandi → descrizioni (per /help)
    COMMANDS = {
        "status": "Mostra lo stato corrente del bot",
        "pause": "Mette in pausa il bot",
        "resume": "Riavvia il bot dalla pausa",
        "force_relist": "Forza un relist al prossimo ciclo",
        "screenshot": "Invia uno screenshot della WebApp",
        "del_sold": "Cancella gli oggetti venduti e raccoglie i crediti",
        "logs": "Mostra le ultime righe del log (default: 20)",
        "help": "Mostra questa lista di comandi",
    }

    def __init__(
        self,
        token: str,
        chat_id: str,
        bot_state: BotState,
        page=None,
        log_dir: Path | None = None,
    ):
        self.token = token
        self.chat_id = chat_id
        self.bot_state = bot_state
        self.page = page
        self.log_dir = log_dir or Path("logs")
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._offset = 0
        self._api_base = f"https://api.telegram.org/bot{self.token}"

    # --- Public API ---

    def start(self) -> None:
        """Avvia il thread di polling Telegram."""
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll, daemon=True, name="telegram-poller")
        self._thread.start()
        logger.info("TelegramHandler avviato (polling attivo)")

    def stop(self) -> None:
        """Ferma il thread di polling Telegram."""
        self._running = False
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("TelegramHandler fermato")

    def send_message(self, text: str) -> None:
        """Invia un messaggio Telegram (API pubblica per uso esterno)."""
        self._send_message(text)

    # --- Polling ---

    def _poll(self) -> None:
        """Loop di polling principale (long polling con offset tracking)."""
        logger.info("Polling Telegram iniziato")
        while self._running and not self._stop_event.is_set():
            try:
                updates = self._get_updates(offset=self._offset)
                for update in updates:
                    self._offset = update.get("update_id", 0) + 1
                    self._handle_update(update)
            except Exception as e:
                logger.error(f"Errore polling Telegram: {e}")
                self._stop_event.wait(timeout=5)  # Pausa prima di riprovare

    def _get_updates(self, offset: int = 0) -> list[dict]:
        """Chiama getUpdates API Telegram con long polling (timeout 30s)."""
        url = f"{self._api_base}/getUpdates?offset={offset}&timeout=30"
        req = urllib.request.Request(url)

        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("result", [])
                logger.warning(f"Telegram API error: {data}")
                return []
        except Exception as e:
            logger.debug(f"getUpdates fallito: {e}")
            return []

    def _handle_update(self, update: dict) -> None:
        """Elabora un singolo update Telegram."""
        message = update.get("message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "")

        # Controllo autorizzazione chat_id
        if str(chat_id) != str(self.chat_id):
            logger.debug(f"Chat ID non autorizzato ignorato: {chat_id}")
            return

        if not text or not text.startswith("/"):
            return

        cmd, args = self._parse_command(text)
        response = self._handle_command(cmd, args)

        if response:
            self._send_message(response)

    # --- Command parsing ---

    def _parse_command(self, text: str) -> tuple[str, list[str]]:
        """Parsa un messaggio Telegram in (comando, argomenti).

        Esempi:
            "/status" → ("status", [])
            "/logs 10" → ("logs", ["10"])
            "/unknown" → ("unknown", [])
        """
        text = text.strip()
        if not text.startswith("/"):
            return "unknown", []

        parts = text[1:].split()  # Rimuove lo slash iniziale
        if not parts:
            return "unknown", []

        cmd = parts[0].lower()
        args = parts[1:]

        if cmd not in self.COMMANDS:
            return "unknown", args

        return cmd, args

    # --- Command routing ---

    def _handle_command(self, cmd: str, args: list[str]) -> str:
        """Instrada il comando al handler appropriato e restituisce la risposta."""
        handlers = {
            "status": self._cmd_status,
            "pause": self._cmd_pause,
            "resume": self._cmd_resume,
            "force_relist": self._cmd_force_relist,
            "screenshot": self._cmd_screenshot,
            "del_sold": self._cmd_del_sold,
            "logs": self._cmd_logs,
            "help": self._cmd_help,
        }

        handler = handlers.get(cmd)
        if handler:
            return handler(args)
        return "❌ Comando sconosciuto. Usa /help per la lista dei comandi."

    # --- Command handlers ---

    def _cmd_status(self, args: list[str]) -> str:
        """Restituisce lo stato corrente del bot."""
        status = self.bot_state.get_status()
        scan_time = status["last_scan_time"] or "Mai"
        return (
            f"📊 *Stato Bot*\n\n"
            f"Pausa: {'Sì ⏸️' if status['paused'] else 'No ▶️'}\n"
            f"Force Relist: {'Sì ⚡' if status['force_relist'] else 'No'}\n"
            f"Cicli: {status['cycle_count']}\n"
            f"Ultimo relist: {status['last_relisted']} listing\n"
            f"Ultimi falliti: {status['last_failed']}\n"
            f"Ultima scansione: {scan_time}"
        )

    def _cmd_pause(self, args: list[str]) -> str:
        """Mette il bot in pausa."""
        self.bot_state.set_paused(True)
        return "⏸️ Bot in pausa"

    def _cmd_resume(self, args: list[str]) -> str:
        """Riavvia il bot dalla pausa."""
        self.bot_state.set_paused(False)
        return "▶️ Bot riavviato"

    def _cmd_force_relist(self, args: list[str]) -> str:
        """Attiva il force relist per il prossimo ciclo."""
        self.bot_state.set_force_relist(True)
        return "⚡ Force relist attivato"

    def _cmd_screenshot(self, args: list[str]) -> str:
        """Invia uno screenshot della WebApp (richiede page)."""
        if self.page is None:
            return "⚠️ Screenshot non disponibile: browser non connesso"
        # Implementazione effettiva richiede Playwright page — stub per ora
        logger.info("Screenshot richiesto (non implementato senza page)")
        return "📸 Screenshot richiesto (in arrivo...)"

    def _cmd_del_sold(self, args: list[str]) -> str:
        """Cancella gli oggetti venduti e raccoglie i crediti (richiede page)."""
        if self.page is None:
            return "⚠️ Cleanup venduti non disponibile: browser non connesso"
        # Implementazione effettiva richiede Playwright page — stub per ora
        logger.info("Delete sold richiesto (non implementato senza page)")
        return "🧹 Cleanup venduti richiesto (in arrivo...)"

    def _cmd_logs(self, args: list[str]) -> str:
        """Restituisce le ultime N righe del log (default: 20)."""
        try:
            n = int(args[0]) if args else 20
        except (ValueError, IndexError):
            n = 20

        log_file = self.log_dir / "app.log"
        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
            last_n = lines[-n:] if len(lines) > n else lines
            if not last_n:
                return "📋 Log vuoto"
            return "📋 *Ultime righe del log:*\n```\n" + "\n".join(last_n) + "\n```"
        except FileNotFoundError:
            return "❌ File di log non trovato"
        except Exception as e:
            return f"❌ Errore lettura log: {e}"

    def _cmd_help(self, args: list[str]) -> str:
        """Restituisce la lista di tutti i comandi disponibili."""
        lines = ["🤖 *Comandi disponibili:*\n"]
        for cmd, desc in self.COMMANDS.items():
            lines.append(f"/{cmd} — {desc}")
        return "\n".join(lines)

    # --- Telegram API ---

    def _send_message(self, text: str) -> None:
        """Invia un messaggio tramite Telegram API sendMessage."""
        url = f"{self._api_base}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.debug(f"Telegram message inviato: {text[:50]}...")
        except Exception as e:
            logger.error(f"Errore invio messaggio Telegram: {e}")
