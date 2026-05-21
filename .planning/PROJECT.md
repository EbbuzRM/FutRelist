# FIFA 26 WebApp Auto-Relist Bot

## Core Value
Relisting automatizzato di giocatori scaduti sulla WebApp di FIFA 26. Il bot opera in background con controllo remoto via Telegram, sincronizzazione precisa con le Golden Hours e misure di anti-detection avanzate.

## Current Status: PRODUCTION / STABLE
**Latest Release:** v1.14 Telegram Notification Fixes (2026-05-18)
**Test Suite:** 740 tests passing (155 unit + 531 golden timeline simulation + 54 fix verification)
**Production Verified:** Successo confermato su relist di massa, gestione "Processing", heartbeat stabile e notifiche Telegram affidabili.

## Key Shipped Features

### Browser & Session Management
- **Playwright Controller:** Gestione browser con profilo persistente (evita ripetizioni 2FA).
- **Auth Manager:** Login EA automatico (2-step), persistenza sessioni e click-shield handling.
- **Session Keeper:** Supervisione attiva con **Heartbeat** dinamico (click su 'Transfers' ogni 2-5 min) e recupero automatico sessione scaduta.
- **Error Handler:** Detection automatica di sessioni scadute con recovery immediato e retry decorator.
- **Stale Page Detection:** Reload automatico pagina dopo 10 cicli rapidi senza expired rilevati.

### Auto-Relist & Golden Hour Logic
- **Precision Timing:** Relist focalizzato alle **:10** di ogni ora (finestra :09-:11).
- **Golden Hours:** Target primari 17:10 e 18:10 (fascia HOLD da 16:10).
- **Pre-Navigation:** Navigazione automatica alla Transfer List esattamente alle **:09:00**.
- **Two-Phase Verification:** Doppio controllo post-relist per garantire che nessun oggetto resti scaduto per errori di rete.
- **Quick Navigation:** Verifica se il bot è già nella pagina corretta prima di navigare (risparmio ~10s).
- **Golden Retry Loop:** Gestione atomica item in "Processing" durante golden window (6 tentativi, 5-10s).
- **Processing Outside Golden:** 15 tentativi, 30-60s attesa, 300s timeout totale.
- **Stale Scan Prevention:** Reset `_last_scan_result` a inizio ciclo per evitare dati obsoleti.

### Telegram Control
- **11 Comandi:** `/status`, `/pause`, `/resume`, `/console`, `/online`, `/force_relist`, `/screenshot`, `/del_sold`, `/logs`, `/reboot`, `/help`.
- **Batch Notifications:** Notifiche aggregate ogni 120s per evitare spam (con logica anti-doppio conteggio).
- **Report Dettagliati:** Conteggio distinto tra attivi, scaduti rilevati e appena rilistati.
- **Fix Notifiche:** Reset batch pre-reboot per evitare dati stale, rimozione check ridondanti in `flush_if_any()`.
- **Error Screenshots:** Invio automatico screenshot in caso di errori critici.

### Protection & Stealth
- **Console Mode:** Deep Sleep totale con polling ridotto a 300s.
- **Rate Limiting:** Delay casuali tra 2s e 5s tra ogni azione.
- **Pausa Ottimizzata:** Polling a 300s con risveglio istantaneo su comando `/resume`.
- **Stale Page Handling:** Reload automatico pagina se congestionata (timer congelati).
- **Detector Fix:** Classificazione corretta item `Expired` in sezione `active` (EA bug workaround).

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

## Recent Fixes Summary (Maggio 2026)

### Settimana 18-19 Maggio
- **Telegram Overcount:** Fix detector per `Expired` in sezione `active`
- **Double Notifications:** Reset scan result e accumolo batch corretto
- **Stale Notification:** Reset batch pre-reboot
- **Missing 18:10 Notification:** Rimossa condizione ridondante in `flush_if_any()`
- **Expired Detected Count:** Logica anti-doppio conteggio

### Settimana 11-17 Maggio
- **Golden Retry Loop:** Ottimizzato con dati freschi, skip se non necessario
- **Processing Break:** Corretto per `remaining_processing == 0`
- **Stale Page Detection:** Reload dopo 10 cicli rapidi senza expired
- **Heartbeat Recovery:** Recupero automatico sessione scaduta
- **Reboot os.execv():** Reload completo moduli
- **Processing Timeout:** 15 tentativi, 300s timeout (fuori golden)

*Last Updated: 2026-05-19*
