status: production
last_updated: "2026-05-04T22:40:39.352Z"
---

# Project State — FIFA 26 Auto-Relist Bot

## 1. Project Identity & Status
- **Status:** PRODUCTION / STABLE
- **Mission:** Bot automatizzato per FIFA 26 WebApp specializzato nel relist sincronizzato durante le Golden Hours.
- **Core Value:** Massima efficienza di vendita tramite timing preciso (:10 di ogni ora) combinata con logiche di ban-prevention (stealth).

## 2. Core Architecture (AI-Optimized Map)
Questa è la mappatura reale dei componenti dopo il refactoring della Fase 9.

- **Orchestrator (`main.py`):** Entrypoint leggero (~200 righe). Gestisce il bootstrap, il loop principale e il coordinamento tra i moduli.
- **Relist Engine (`logic/relist_engine.py`):** Il "cervello" decisionale. Implementa il ciclo di scansione e il protocollo di **Two-Phase Verification**.
- **Golden Hour Logic (`logic/golden_hour.py`):** Unica fonte di verità per i timing.
  - **Hours:** 16, 17, 18.
  - **Protocol:** :09 (Pre-Nav) → :10 (Relist) → :11 (Ritardatari).
- **Session Keeper (`browser/session_keeper.py`):** Gestisce la salute della sessione, il **Heartbeat** (click su tab 'Transfers') e le attese in Pausa/Console.
- **Bot State (`bot_state.py`):** Gestore dello stato thread-safe (comandi Telegram, statistiche, reboot events).

## 3. Control & Interaction (Telegram Commands)
Il bot risponde a **11 comandi** reali via Telegram.

| Comando | Descrizione | Nota Tecnica |
|:--- |:--- |:--- |
| `/status` | Stato, modalità e statistiche | Lettura diretta da `BotState` |
| `/pause` | Sospende il loop di scansione | Mette il polling a 300s |
| `/resume` | Riprende le operazioni | Sveglia immediata via Event |
| `/console` | Deep Sleep (opz. ore) | Zero interazione WebApp |
| `/online` | Disattiva Deep Sleep | Torna al loop normale |
| `/force_relist` | Forza relist al prossimo ciclo | Bypass dei timer Golden |
| `/screenshot` | Invia screen della WebApp | Eseguito asincrono nel main thread |
| `/del_sold` | Cleanup venduti e crediti | Eseguito asincrono nel main thread |
| `/logs [N]` | Ultime N righe di `app.log` | Lettura file sicura |
| `/reboot` | Riavvio completo del bot | Segnala RebootRequestError |
| `/help` | Elenco comandi | Generato dinamicamente |

## 4. Critical Logic & Guardrails (DA NON MODIFICARE)
Regole fondamentali verificate nel codice sorgente:
- **Stealth Polling:** Durante Pausa o Console Mode, il bot aspetta **300s** (5 min). `wait_interruptible` garantisce che il bot risponda subito ai comandi nonostante il lungo sleep.
- **Heartbeat:** Eseguito ogni 2.5-5 min tramite click sulla tab **'Transfers'** (icon-transfer). Non usare più 'Clear Sold' come heartbeat primario.
- **Verification Protocol:**
  1. Relist → 5s wait → Scan.
  2. Se restano oggetti scaduti (non in "Processing") → Secondo Relist → 3s wait → Scan finale.
- **Fallback Rule:** Ogni blocco decisionale di relist deve sempre prevedere un fallback `else` per la gestione standard.
**Relist Protocol Golden Hour**
:08:00 → Bot si sveglia. Pre-Nav Guard: aspetta fino a :09:00 (zero interazione browser)
:09:00 → Naviga verso Transfer List (~10s)
:09:10 → In posizione. Golden Sync: aspetta :10:00 (SENZA scansionare, item non ancora scaduti)
:10:00 → SCANSIONE (item appena scaduti, già sulla pagina → zero navigazione)
:10:01 → Relist immediato. Se Processing → retry loop (5-10s) → relist ASAP ✓


## 5. Current Activity & Known Issues

### Today's Fixes (May 04, 2026)
- **Today (04 May):** Code Review Fixes & Test Coverage
  - **CR-02:** Fix `_golden_retry_loop` return values (3 not 4, remove undef `last_scan`)
  - **HI-01:** Fix logger warning format in `config.py` and `rate_limiter.py` (`%s` → `{var}`)
  - **ME-02:** Fix `sys` import order in `log_config.py`
  - **ME-03:** Use `deque` for `BotState` pending commands (O(1) `popleft` vs O(n) `pop(0)`)
  - **ME-01:** Move `AuthManager` imports to module level in `relist.py`)
  - **LO-01:** Centralize `RateLimiter` via dependency injection (navigator, relist, sold_handler)
  - **Tests:** Added `test_relist_engine.py`, `test_relist_imports.py` and updated existing test files
  - **Test Results:** 686 tests passing ✓

### Today's Fixes (May 02, 2026)
- **Today (02 May):** Click-Shield Fix & Error Screenshots
  - `browser/auth.py`: `wait_for_click_shield()` con `wait_for_function()` (best practice Playwright)
  - `notifier.py`: `send_telegram_error_with_screenshot()` per diagnostica visiva errori
  - `main.py` + `session_keeper.py`: Errori critici includono ora screenshot automatico
  - Skill cleanup: 3 eliminate, 2 fuse, 4 description disambiguate (dei 19 skill → 16)

- **Recent (01 May):** Test Suite Stabilization. Aggiornata l'intera suite di test (`test_golden_timeline.py`, `test_golden_retry.py`) per riflettere le nuove logiche di timing (:08 wake up) e il retry loop senza navigazione. Tutti i 535 test passano correttamente. ✓
- **Recent (01 May):** Fix "HOLD Wait Bug": corretto `_compute_next_wait` nel caso `is_in_hold_window`. Ora calcola l'attesa precisa verso il minuto `:08` della prossima golden hour, invece di ritornare sempre 60s hardcoded. Questo elimina decine di scansioni inutili e permette al Pre-Nav Guard di scattare sempre.
- **Recent (29 Apr):** Fix "Scan-Spam Post-Relist": `_compute_next_wait` non ritorna più 10s ciecamente durante golden window. Polling rapido solo se ci sono ancora expired/processing. Dopo relist con 0 expired, calcola wait verso la prossima golden pre-nav.
- **Recent (29 Apr):** Fix "Processing Items": se TUTTI gli expired sono in realtà PROCESSING, il bot salta il tentativo di relist (bottone non visibile) e delega al `_golden_retry_loop` con attesa 5-10s per la transizione EA.
- **Recent (29 Apr):** `process_cycle` ora riscansiona DOPO il relist per dare a `_compute_next_wait` dati freschi (evita il loop 10s con expired_count stale).
- **Recent (04 May):** Risolto log ridondante "Scansione completata" post-relist: le funzioni di rilist ora restituiscono l'ultima scansione di verifica, eliminando la scansione superflua alla fine di `process_cycle`.
- **Recent (29 Apr):** Fix "Flusso Golden Ristrutturato": wake up a `:08`, navigazione a `:09`, scansione e relist immediato a `:10`. Eliminata la navigazione superflua dal golden retry loop.
- **Recent (28 Apr):** Fix "Console Heartbeat Spam": quando l'heartbeat rileva EA console attiva, ora attiva automaticamente `console_mode` con auto-resume a 30 min.
- **Recent (27 Apr):** Fix critico "Processing Limbo": corretto un bug in `relist_engine.py` in cui oggetti in processing fuori dalla golden hour causavano un wait errato di 3600s invece di 30s.
- **Recent (27 Apr):** Introdotto **Quick Check** nella navigazione della Transfer List (se già in pagina, risparmia ~10s).
- **Recent (27 Apr):** Ottimizzato polling Pausa/Console a 300s con wake-up istantaneo.
- **Known Issue:** Inosservanza saltuaria dei conflitti 409 Telegram (gestita con backoff di 5s).

---

## 5b. Fix Implementati (DA VERIFICARE — 05 Maggio 2026)

### Root Cause Fix: `get_next_golden_hour()`
- **Problema**: La funzione restituiva la golden hour **corrente** se siamo nella sua finestra (:09-:11), invece della **prossima futura**
- **Fix**: Modificato `logic/golden_hour.py` → `get_next_golden_hour()` usa confronto stretto `target > now`
- **Impatto**: Tutti i chiamanti ottengono sempre la prossima golden hour futura
- **Commit**: `fix: get_next_golden_hour always returns future (root cause fix)`

### Semplificazione `_compute_deadline()`
- **Problema**: Codice difensivo per gestire `deadline <= now` (non serve più)
- **Fix**: Rimossa logica difensiva in `logic/relist_engine.py::_compute_deadline()`
- **Impatto**: Codice più pulito e manutenibile

### Deadline Check in `wait_with_heartbeat()`
- **Problema**: Durante i wait lunghi, il bot poteva oversleepare la :08:00
- **Fix**: In `browser/session_keeper.py`:
  - Calcola `secs_to_deadline` prima di ogni chunk
  - Cappa `chunk` alla deadline (con 1s safety)
  - **Uscita immediata** quando `now >= deadline` (prima dell'heartbeat)
  - Gestione caso `secs_to_deadline <= 0` (deadline già passata)
- **Commit**: `fix: cap wait_with_heartbeat a deadline :08:00 per Pre-Nav Guard`
- **Commit**: `fix: immediate exit at deadline for Pre-Nav Guard`
- **Commit**: `fix: immediate exit if deadline already reached before sleep`

### Risultato Atteso
Domani, dopo la golden hour delle 18:10, l'utente verificherà:
1. **Alle 18:08:00** → Pre-Nav Guard scatta puntuale ✅
2. **Alle 18:09:00** → Navigazione Transfer List ✅
3. **Alle 18:10:00** → Relist eseguito con Pre-Nav completo ✅
4. **Sessione morta durante il wait** → Rilevata dall'heartbeat PRIMA delle 18:08 ✅

**Stato**: ⏳ IN ATTESA VERIFICA (dopo 18:10 di domani)

---

## 6. Historical Archive (Changelog)

<details>
<summary>Aprile 2026 — Rafforzamento Stabilità & Refactoring</summary>

### Today's Fixes (April 27, 2026) — Navigazione & Polling
- **Fix 3: Navigazione Transfer List — Quick Check**: Il bot ora verifica se è già nella pagina corretta prima di navigare.
- **Fix 1 & 2: Polling Pausa/Console**: Ridotto a 300s per pulizia log, mantenendo reattività istantanea via Telegram.

### Today's Fixes (April 21, 2026) — Golden Stability & Heartbeat
- **Fix 1: Golden Hour Pre-Nav Timing**: Navigazione fissata esattamente alle :09:00.
- **Fix 2: HOLD Window Behavior**: Rimosso cap di 60s, ora il bot aspetta i secondi effettivi fino alla prossima golden.
- **Fix 3: Heartbeat via Transfers**: Sostituito 'Clear Sold' con click su sidebar 'Transfers' per maggiore stabilità.

### Today's Fixes (April 20, 2026) — Metrics & Reboot
- **Refactoring: RebootRequestError**: Gestione pulita dei riavvii asincroni.
- **Metrics Decoupling**: Separazione tra `total_*` (sessione) e `last_*` (ciclo corrente).

### Today's Fixes (April 18, 2026) — Phase 9 Completion
- **Modularizzazione**: Estrazione logica in `logic/`, `core/`, `config/`. `main.py` ridotto a ~170 righe.
- **Notification Batch**: Invio summary solo se ci sono risultati reali.
</details>

<details>
<summary>Shipment History & Milestones</summary>

- **v1.10** — Golden Stability & Session Heartbeat (2026-04-21)
- **v1.8** — Two-Phase Post-Relist Verification (2026-04-16)
- **v1.5** — PROCESSING State Fix (2026-04-13)
- **v1.2** — Protection & Stealth (2026-04-11)
- **v1.1** — Telegram Commands (2026-04-06)
- **v1.0** — Auto-Relist MVP (2026-03-23)
</details>

### Test Suite Summary
- **Total:** 686 tests passing.
- **Coverage:** 155 unit tests + 531 golden timeline simulations (added test_relist_engine.py, test_relist_imports.py)