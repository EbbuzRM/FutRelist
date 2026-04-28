# FIFA 26 Auto-Relist Tool — Codebase Map (Updated)

**Analysis Date:** 2026-04-27
**Project Root:** `C:\App\fifa-relist`
**Language:** Python 3.13
**Current State:** Modular Architecture (Phase 9 Complete)

---

## Directory Tree

```
fifa-relist/
├── main.py                 # Entry point — Orchestratore del loop principale
├── bot_state.py            # Stato thread-safe (Remote Control, Stats, Commands)
├── telegram_handler.py     # Gestione comandi Telegram (11 comandi attivi)
├── notifier.py             # Alert Telegram e batch notifications
├── browser/                # Layer Automazione Browser
│   ├── controller.py       # Lifecycle Playwright (persistent context)
│   ├── auth.py             # Login flow, session persistence, console detection
│   ├── navigator.py        # Navigazione WebApp con Quick Check
│   ├── detector.py         # DOM scanning (Bulk extraction)
│   ├── relist.py           # RelistExecutor (Single/All), price logic
│   ├── rate_limiter.py     # Gestione delay anti-detection (2-5s)
│   ├── session_keeper.py   # Supervisione sessione, Heartbeat, Polling in pausa
│   └── error_handler.py    # Detection session expiry, recovery, retry decorator
├── logic/                  # Layer Logica di Business
│   ├── relist_engine.py    # Motore decisionale, Two-Phase Verification
│   └── golden_hour.py      # Unica fonte di verità per i timing Golden
├── config/                 # Configurazione
│   ├── config.py           # ConfigManager con typed dataclasses
│   └── config.json         # Runtime config
├── models/                 # Modelli Dati
│   ├── listing.py          # ListingState, PlayerListing
│   ├── relist_result.py    # Esito azioni relist
│   └── action_log.py       # Struttura log azioni
├── storage/                # Dati persistenti (Profile, Cookies)
└── logs/                   # Log di runtime (app.log, actions.jsonl)
```

---

## Component Map (Detailed)

### `main.py` — The Orchestrator
- **Size:** ~200 lines (Refactored from 1000+).
- **Role:** Carica la configurazione, inizializza i componenti e avvia il loop infinito di `RelistEngine`.
- **Key Flow:** Bootstrap → Auth → Telegram Start → `engine.process_cycle()` → Loop.

### `logic/relist_engine.py` — The Brain
- **Responsibility:** Decide *cosa* e *quando* rilistare.
- **Features:** 
  - **Two-Phase Verification:** Verifica due volte l'esito del relist per gestire i ritardi dei server EA.
  - **Manual Relist Detection:** Identifica se l'utente ha rilistato a mano durante la Golden Hour.
  - **Wait Calculation:** Determina l'attesa ottimale tra i cicli.

### `logic/golden_hour.py` — Timing Authority
- **Constants:** Definizione univoca delle Golden Hours (16, 17, 18) e dei timing precisi (:09, :10, :11).
- **Functions:** Calcolo del prossimo target golden e gestione della "Hold Window".

### `browser/session_keeper.py` — Session Guardian
- **Responsibility:** Garantisce che il bot sia sempre "online" e pronto.
- **Heartbeat:** Esegue un click su 'Transfers' ogni 2-5 minuti.
- **Sleep Management:** Implementa il polling ottimizzato (300s) per Pausa e Console Mode.

### `telegram_handler.py` — Command Center
- **Function:** Gestisce 11 comandi remoti.
- **Thread Safety:** Comunica col main thread tramite una coda di comandi in `BotState`.

---

## Architecture Pattern
**Modular Event-Driven Polling Loop**
1. **Perceive:** `detector` analizza il mercato.
2. **Reason:** `relist_engine` valuta i timer rispetto a `golden_hour`.
3. **Act:** `relist_executor` agisce tramite `navigator`.
4. **Refine:** `error_handler` e `session_keeper` gestiscono imprevisti e manutenzione sessione.

---

## Data Models
- `ListingState`: Enum (ACTIVE, EXPIRED, PROCESSING, SOLD).
- `ListingScanResult`: Snapshot completo della Transfer List dopo una scansione.
- `RelistBatchResult`: Riassunto aggregato per le notifiche Telegram.

---
*Last Updated: 2026-04-27 — Codebase Audit Verified*