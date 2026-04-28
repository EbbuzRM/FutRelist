# FIFA 26 WebApp Auto-Relist Bot

## Core Value
Relisting automatizzato di giocatori scaduti sulla WebApp di FIFA 26. Il bot opera in background con controllo remoto via Telegram, sincronizzazione precisa con le Golden Hours e misure di anti-detection avanzate.

## Current Status: PRODUCTION / STABLE
**Latest Release:** v1.11 Polling Optimization & Quick Navigation (2026-04-27)
**Test Suite:** 674 tests passing (148 unit + 526 golden timeline simulation)
**Production Verified:** Successo confermato su relist di massa, gestione "Processing" e heartbeat stabile.

## Key Shipped Features

### Browser & Session Management
- **Playwright Controller:** Gestione browser con profilo persistente (evita ripetizioni 2FA).
- **Auth Manager:** Login EA automatico (2-step) e persistenza delle sessioni.
- **Session Keeper:** Supervisione attiva con **Heartbeat** dinamico (click sulla tab 'Transfers' ogni 2-5 min).
- **Error Handler:** Detection automatica di sessioni scadute con recovery immediato.

### Auto-Relist & Golden Hour Logic
- **Precision Timing:** Relist focalizzato alle **:10** di ogni ora (finestra :09-:11).
- **Golden Hours:** Target primari 16:10, 17:10, 18:10.
- **Pre-Navigation:** Navigazione automatica alla Transfer List esattamente alle **:09:00**.
- **Two-Phase Verification:** Doppio controllo post-relist per garantire che nessun oggetto resti scaduto per errori di rete.
- **Quick Navigation:** Verifica se il bot è già nella pagina corretta prima di navigare (risparmio ~10s).

### Telegram Control
- **11 Comandi:** `/status`, `/pause`, `/resume`, `/console`, `/online`, `/force_relist`, `/screenshot`, `/del_sold`, `/logs`, `/reboot`, `/help`.
- **Batch Notifications:** Notifiche aggregate ogni 120s per evitare spam.
- **Report Dettagliati:** Conteggio distinto tra attivi, scaduti rilevati e appena rilistati.

### Protection & Stealth
- **Console Mode:** Deep Sleep totale con polling ridotto a 300s.
- **Rate Limiting:** Delay casuali tra 2s e 5s tra ogni azione.
- **Pausa Ottimizzata:** Polling a 300s con risveglio istantaneo su comando `/resume`.

## Tech Stack
- **Language:** Python 3.13
- **Automation:** Playwright (Chromium)
- **Notifications:** Telegram Bot API (urllib)
- **UI & Logging:** Rich (Console), JSONL (Actions history)
- **Testing:** Pytest (Timeline Simulation)

## Architecture Overview
Il bot è strutturato in modo modulare per separare le responsabilità:
1. **`main.py`**: Orchestratore del boot e del loop.
2. **`logic/`**: Motore decisionale (`relist_engine`) e gestione timing (`golden_hour`).
3. **`browser/`**: Interazione WebApp, navigazione, auth e session keep-alive.
4. **`bot_state.py`**: Gestione stato thread-safe per i comandi remoti.

## Constraints & Rules
- **Golden Hour Priority:** La logica del minuto :09/:10 è sacra e non va alterata.
- **Anti-Detection:** Mai scendere sotto i delay minimi di sicurezza (800ms).
- **Wait Policy:** Utilizzare sempre `wait_interruptible` per i lunghi sleep.
- **Fallback:** Ogni azione di relist deve prevedere una gestione standard per i casi fuori finestra.

---
*Last Updated: 2026-04-27*
