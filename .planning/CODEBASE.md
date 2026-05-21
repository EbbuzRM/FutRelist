# FIFA 26 Auto-Relist Tool — Codebase Map

**Analysis Date:** 2026-05-19
**Project Root:** `C:\App\fifa-relist`
**Language:** Python 3.13
**Current State:** Production / Stable (Post-Phase 9 Refinement)

---

## Directory Tree

```
fifa-relist/
├── main.py # Entry point — Orchestratore del loop principale (~290 righe)
├── bot_state.py # Stato thread-safe (Remote Control, Stats, Commands)
├── telegram_handler.py # Gestione comandi Telegram (11 comandi attivi)
├── notifier.py # Alert Telegram e batch notifications (con screenshot)
├── browser/ # Layer Automazione Browser
│ ├── controller.py # Lifecycle Playwright (persistent context)
│ ├── auth.py # Login flow, session persistence, console detection, click-shield
│ ├── navigator.py # Navigazione WebApp con Quick Check
│ ├── detector.py # DOM scanning (Bulk extraction, stale page detection)
│ ├── relist.py # RelistExecutor (Single/All), price logic
│ ├── rate_limiter.py # Gestione delay anti-detection (2-5s)
│ ├── session_keeper.py # Supervisione sessione, Heartbeat, Polling in pausa
│ ├── error_handler.py # Detection session expiry, recovery, retry decorator
│ └── sold_handler.py # Gestione venduti e crediti
├── logic/ # Layer Logica di Business
│ ├── relist_engine.py # Motore decisionale, Two-Phase Verification, Golden Retry
│ └── golden_hour.py # Unica fonte di verità per i timing Golden
├── config/ # Configurazione
│ ├── config.py # ConfigManager con typed dataclasses
│ └── log_config.py # Setup logging strutturato
├── core/ # Core Business Logic
│ └── notification_batch.py # Batch notifications per Telegram
├── models/ # Modelli Dati
│ ├── listing.py # ListingState, PlayerListing
│ ├── relist_result.py # Esito azioni relist
│ ├── sold_result.py # Esito pulizia venduti
│ └── action_log.py # Struttura log azioni
├── tests/ # Test Suite (740 test)
│ ├── test_*.py # 18 file di test
│ └── conftest.py # Fixture pytest
├── storage/ # Dati persistenti (Profile, Cookies)
└── logs/ # Log di runtime (app.log, actions.jsonl)
```

---

## Component Map (Detailed)

### `main.py` — The Orchestrator
- **Size:** ~290 lines (Refactored from 1000+).
- **Role:** Carica la configurazione, inizializza i componenti e avvia il loop infinito di `RelistEngine`.
- **Key Flow:** Bootstrap → Auth → Telegram Start → `engine.process_cycle()` → Loop.
- **Recent Updates:** Gestione reboot con `os.execv()` per reload completo moduli, reset batch notification pre-reboot.

### `logic/relist_engine.py` — The Brain
- **Responsibility:** Decide *cosa* e *quando* rilistare.
- **Features:**
- **Two-Phase Verification:** Verifica due volte l'esito del relist per gestire i ritardi dei server EA.
- **Manual Relist Detection:** Identifica se l'utente ha rilistato a mano durante la Golden Hour.
- **Wait Calculation:** Determina l'attesa ottimale tra i cicli.
- **Golden Retry Loop:** Gestisce gli item in "Processing" durante la golden window.
- **Stale Page Detection:** Rileva pagina congelata e forza reload dopo 10 cicli rapidi senza expired.

### `logic/golden_hour.py` — Timing Authority
- **Constants:** Definizione univoca delle Golden Hours `(17, 18)`, periodo HOLD `(16:10 → 18:15)` e timing precisi (:09, :10, :11).
- **Functions:** Calcolo del prossimo target golden e gestione della "Hold Window".
- **Processing Constants:** Parametri per gestione item in processing fuori golden window (15 tentativi, 30-60s, 300s timeout).

### `browser/session_keeper.py` — Session Guardian
- **Responsibility:** Garantisce che il bot sia sempre "online" e pronto.
- **Heartbeat:** Esegue un click su 'Transfers' ogni 2-5 minuti (con rilevamento sessione scaduta).
- **Sleep Management:** Implementa il polling ottimizzato (300s) per Pausa e Console Mode.
- **Session Recovery:** Recupero automatico sessione scaduta durante heartbeat.

### `telegram_handler.py` — Command Center
- **Function:** Gestisce 11 comandi remoti.
- **Thread Safety:** Comunica col main thread tramite una coda di comandi in `BotState`.
- **Commands:** `/status`, `/pause`, `/resume`, `/console`, `/online`, `/force_relist`, `/screenshot`, `/del_sold`, `/logs`, `/reboot`, `/help`.

---

## Architecture Pattern
**Modular Event-Driven Polling Loop**
1. **Perceive:** `detector` analizza il mercato (DOM scanning con stale page detection).
2. **Reason:** `relist_engine` valuta i timer rispetto a `golden_hour`.
3. **Act:** `relist_executor` agisce tramite `navigator`.
4. **Refine:** `error_handler` e `session_keeper` gestiscono imprevisti e manutenzione sessione.
5. **Notify:** `notification_batch` accumula e invia report Telegram (batch 120s).

---

## Data Models
- `ListingState`: Enum (ACTIVE, EXPIRED, PROCESSING, SOLD).
- `ListingScanResult`: Snapshot completo della Transfer List dopo una scansione.
- `RelistBatchResult`: Riassunto aggregato per le notifiche Telegram.
- `NotificationBatch`: Gestisce accumulo e invio notifiche (con logica anti-doppio conteggio).

---

## Recent Changes (Maggio 2026)
- **Fix Notifica Stale:** Reset batch pre-reboot per evitare dati fuorivianti.
- **Fix Double Check:** Rimossa condizione ridondante in `flush_if_any()` che causava notifiche perse.
- **Fix Scaduti Rilevati:** Logica migliorata per evitare doppio conteggio (es. 78+54 → 78, non 132).
- **Fix Golden Retry:** Ottimizzato per usare dati freschi e saltare se non necessario.
- **Fix Processing Break:** Corretto break prematuro se `f == 0` ma processing residuo.
- **Fix Heartbeat:** Recupero automatico sessione scaduta.
- **Fix Reboot:** `os.execv()` per reload completo moduli.
- **Fix Processing Timeout:** Aumentati tentativi da 3 a 15 (fuori golden window).
- **Fix Telegram Overcount:** Rilevamento `Expired` in sezione `active` (EA bug).
- **Fix Stale Page:** Reload automatico dopo 10 cicli rapidi senza expired.
- **Fix Quick Nav:** Verifica pagina corrente prima di navigare.

---
*Last Updated: 2026-05-19 — Codebase Audit Verified*