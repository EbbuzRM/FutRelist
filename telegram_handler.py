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
from models.sold_result import SoldCreditsResult

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
        "console": "Modalità console: deep sleep (es. /console 2 per 2 ore)",
        "online": "Disattiva modalità console e riprendi",
        "force_relist": "Forza un relist al prossimo ciclo",
        "screenshot": "Invia uno screenshot della WebApp",
        "del_sold": "Cancella gli oggetti venduti e raccoglie i crediti",
        "logs": "Mostra le ultime righe del log (default: 20)",
        "reboot": "Riavvia il bot (per applicare modifiche)",
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
        self._sold_handler = None

    def set_sold_handler(self, sold_handler) -> None:
        """Imposta l'handler per il comando /del_sold."""
        self._sold_handler = sold_handler

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
            
        # Conferma l'ultimo offset elaborato prima di chiudere
        # per evitare che Telegram reinvii gli stessi comandi (es. /reboot doppio)
        if self._offset > 0:
            try:
                self._get_updates(offset=self._offset, timeout=1)
            except Exception as e:
                logger.debug(f"Errore conferma offset finale: {e}")
                
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
                    try:
                        self._handle_update(update)
                    except Exception as e:
                        logger.error(f"Errore elaborazione update: {e}")
                    finally:
                        # Always update offset even if message send failed
                        # to prevent Telegram from resending the same message
                        self._offset = update.get("update_id", 0) + 1
            except Exception as e:
                logger.error(f"Errore polling Telegram: {e}")
                self._stop_event.wait(timeout=5)  # Pausa prima di riprovare

    def _get_updates(self, offset: int = 0, timeout: int = 30) -> list[dict]:
        """Chiama getUpdates API Telegram con long polling."""
        url = f"{self._api_base}/getUpdates?offset={offset}&timeout={timeout}"
        req = urllib.request.Request(url)

        try:
            with urllib.request.urlopen(req, timeout=timeout + 5) as response:
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
            "console": self._cmd_console,
            "online": self._cmd_online,
            "force_relist": self._cmd_force_relist,
            "screenshot": self._cmd_screenshot,
            "del_sold": self._cmd_del_sold,
            "logs": self._cmd_logs,
            "reboot": self._cmd_reboot,
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

        mode = "▶️ Attivo"
        if status.get("console_mode"):
            until = status.get("console_until")
            mode = f"🎮 Console (fino {until})" if until else "🎮 Console"
        elif status["paused"]:
            mode = "⏸️ In Pausa"

        return (
            f"📊 Stato Bot\n\n"
            f"Modalità: {mode}\n"
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
        # Se siamo in console mode, avvisa l'utente
        if self.bot_state.is_console_mode():
            return "⚠️ Bot in modalità console. Usa /online prima di forzare il relist."
        self.bot_state.set_force_relist(True)
        return "⚡ Force relist attivato"

    def _cmd_console(self, args: list[str]) -> str:
        """Attiva la modalità console: il bot va in deep sleep.

        Uso:
            /console     — deep sleep indefinito (fino a /online)
            /console 2   — deep sleep per 2 ore, poi auto-resume
            /console 0.5 — deep sleep per 30 minuti
        """
        hours = None
        if args:
            try:
                hours = float(args[0])
            except ValueError:
                return "❌ Usa: /console [ore] (es. /console 2)"

        self.bot_state.set_console_mode(True, hours=hours)

        if hours:
            from datetime import datetime, timedelta
            resume_at = (datetime.now() + timedelta(hours=hours)).strftime("%H:%M")
            return (
                f"🎮 Modalità Console ATTIVA\n"
                f"💤 Deep sleep per {hours}h (auto-resume alle {resume_at})\n"
                f"🚫 Zero interazione WebApp\n"
                f"Usa /online per riprendere prima"
            )
        return (
            "🎮 Modalità Console ATTIVA\n"
            "💤 Deep sleep indefinito\n"
            "🚫 Zero interazione WebApp\n"
            "Usa /online quando hai finito di giocare"
        )

    def _cmd_online(self, args: list[str]) -> str:
        """Disattiva la modalità console e riprende il bot."""
        if not self.bot_state.is_console_mode():
            return "ℹ️ Il bot non è in modalità console."
        self.bot_state.set_console_mode(False)
        return (
            "✅ Modalità Console DISATTIVATA\n"
            "▶️ Bot riprende le operazioni normali"
        )

    def _cmd_screenshot(self, args: list[str]) -> str:
        """Invia uno screenshot della WebApp (richiede page)."""
        if self.page is None:
            return "⚠️ Screenshot non disponibile: browser non connesso"
        # Implementazione effettiva richiede Playwright page — stub per ora
        logger.info("Screenshot richiesto (non implementato senza page)")
        return "📸 Screenshot richiesto (in arrivo...)"

    def _cmd_del_sold(self, args: list[str]) -> str:
        """Cancella gli oggetti venduti e raccoglie i crediti (richiede page).

        Instead of executing directly (which causes thread issues),
        queue the command to be executed in the main thread.
        """
        if self.page is None:
            return "⚠️ Cleanup venduti non disponibile: browser non connesso"
        if self._sold_handler is None:
            return "⚠️ Sold handler non configurato"

        # Queue the command to be executed in main thread
        self.bot_state.queue_command(
            "del_sold",
            callback=self._execute_del_sold,
        )
        return "⏳ Comando in coda: /del_sold sarà eseguito al prossimo ciclo del bot..."

    def _execute_del_sold(self) -> SoldCreditsResult:
        """Esegue il del_sold nel contesto del main thread."""
        if self._sold_handler is None:
            return SoldCreditsResult(success=False, error="Sold handler not configured")
        try:
            result = self._sold_handler.process_sold_items()
            return result
        except Exception as e:
            logger.error(f"Errore durante del_sold: {e}")
            return SoldCreditsResult(success=False, error=str(e))

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

    def _cmd_reboot(self, args: list[str]) -> str:
        """Riavvia il bot segnalando il main loop.

        Il reboot viene gestito dal main thread che chiude il browser
        in modo pulito e poi rilancia il processo. sys.exit() da un thread
        secondario non termina il processo — uccide solo quel thread.
        """
        self.bot_state.request_reboot()
        return "🔄 Reboot in corso..."

    def _cmd_help(self, args: list[str]) -> str:
        """Restituisce la lista di tutti i comandi disponibili."""
        lines = ["🤖 *Comandi disponibili:*\n"]
        for cmd, desc in self.COMMANDS.items():
            lines.append(f"/{cmd} — {desc}")
        return "\n".join(lines)

    # --- Telegram API ---

    def _send_message(self, text: str) -> None:
        """Invia un messaggio tramite Telegram API sendMessage.

        Usa parse_mode=Markdown solo se il testo contiene formattazione intenzionale
        (bold *...* o code blocks ```...```). Altrimenti invia senza parse_mode
        per evitare errori 400 da caratteri speciali non escapati (es. _ in /del_sold).
        """
        url = f"{self._api_base}/sendMessage"

        # Rileva se il testo contiene formattazione Markdown intenzionale
        has_markdown = "*" in text or "```" in text
        payload = {
            "chat_id": self.chat_id,
            "text": text,
        }
        if has_markdown:
            payload["parse_mode"] = "Markdown"

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
