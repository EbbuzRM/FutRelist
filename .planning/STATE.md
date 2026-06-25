status: production
last_updated: "2026-05-25T00:00:00.000Z"
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
  - **Hours:** 17, 18 (solo 17:10 e 18:10).
  - **HOLD period start:** 16:10 (non è una golden hour).
  - **Protocol:** :09 (Pre-Nav) → :10 (Relist) → :11 (Ritardatari).
- **Session Keeper (`browser/session_keeper.py`):** Gestisce la salute della sessione, il **Heartbeat** con menu probe attivo e le attese in Pausa/Console.
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
- **Heartbeat:** Eseguito ogni 2.5-5 min tramite **menu probe** (`Home/Casa/Club -> Transfers`) con controllo modali logout, console session e URL login. Dopo fallimenti consecutivi del probe usa refresh completo come fallback estremo. Non usare piu 'Clear Sold' come heartbeat primario.
- **Verification Protocol:**
  1. Relist → 5s wait → Scan.
  2. Se restano oggetti scaduti (non in "Processing") → Secondo Relist → 3s wait → Scan finale.
- **Fallback Rule:** Ogni blocco decisionale di relist deve sempre prevedere un fallback `else` per la gestione standard.
**Relist Protocol Golden Hour**
| Orario | Azione | Risultato nei Log |
|--------|--------|-------------------|
| **17:08:00** | Pre-Nav Guard scatta | `Minuto :08 — attendo pre-nav slot :09:00` 
| **17:09:00** | Navigazione Transfer List | `Transfer List caricata con successo` 
| **17:10:00** | SCANSIONE + Relist (4 item) | `4 rilistati, 0 falliti` | ✅ |
| **18:07:55** | Deadline check | `Deadline 18:08:00 tra 4.1s, cappo chunk a 4.1s` 
| **18:08:00** | **Immediate exit** dal wait | `Deadline 18:08:00 raggiunta, esco dal wait` 
| **18:08:00** | Pre-Nav Guard scatta | `Minuto :08 — attendo pre-nav slot :09:00`
| **18:09:00** | Navigazione Transfer List | `Transfer List caricata con successo` 
| **18:10:00** | SCANSIONE + Relist (4 item) | `4 rilistati, 0 falliti` se processing Golden Retry 


## 5. Current Activity & Known Issues

### Today's Fixes (May 28, 2026)
### Feature: Rilevamento e Gestione Nuovo Metodo di Login EA (Remember Me)
- **Problema**: L'introduzione della nuova schermata di login EA con utente pre-selezionato (e solo campo password) interrompeva il flusso di login classico del bot.
- **Fix**: Integrato il rilevamento dinamico della schermata "Remember Me" in `AuthManager.perform_login()`. Il bot inserisce la password direttamente se l'utente corrisponde a quello di sistema, altrimenti esegue uno switch utente in automatico verso il flusso classico.
- **File modificati**: `browser/auth.py`
- **Verifica**: Flusso approvato dall'utente e validato sintatticamente con successo. Massima resilienza per entrambe le tipologie di accesso.

### Today's Fixes (May 25, 2026)
### Fix: Menu probe per rilevamento sessione scaduta
- **Problema**: La shell WebApp poteva restare visibile anche con sessione EA scaduta; `is_logged_in()` vedeva Home/Transfers e produceva falsi positivi.
- **Root cause**: L'heartbeat basato sul solo click `Transfers` non forzava sempre EA a mostrare logout/modale; cambiando menu il problema emergeva piu spesso.
- **Fix**: `AuthManager.probe_session_alive()` forza un cambio menu `Home/Casa/Club -> Transfers`, controlla modali di disconnessione, console session e URL login. `SessionKeeper` ed `ensure_session()` usano il probe prima di fidarsi della UI.
- **Fallback**: dopo 3 probe non conclusivi parte un refresh completo (`session_probe_refresh_after_failures` configurabile).
- **File modificati**: `browser/auth.py`, `browser/session_keeper.py`, `browser/error_handler.py`, `tests/test_auth_probe.py`, `tests/test_session_keeper.py`, `tests/test_error_handler.py`.
- **Verifica**: `python -m pytest` -> 746 test passano.

### IMPORTANTE — Golden Hour 16:10 RIMOSSA (maggio 2026)

**Decisione prodotto (intenzionale, non regressione):**

- L'orario **16:10 NON è più una golden hour** — nessun relist tassativo alle 16:10.
- Restano **solo 17:10 e 18:10** come picchi di relist (`GOLDEN_HOURS = (17, 18)` in `logic/golden_hour.py`).
- Il **periodo HOLD** inizia alle **16:10** (`GOLDEN_PERIOD_START = (16, 10)`): un'ora prima del primo picco 17:10, gli scaduti restano in attesa.
- Fine fascia invariata: **18:15** (`GOLDEN_PERIOD_END`).

**Scopo:** evitare confusione per IA e sviluppatori che leggono vecchia documentazione o planning che citava «16:10, 17:10, 18:10» come tre golden hour attive.

**Data modifica:** 19 maggio 2026.

### Today's Fixes (May 18, 2026)
### Fix: Notifica Telegram con dati stale dopo reboot
- **Problema**: Dopo un reboot, il bot inviava una notifica Telegram con conteggi di relist vecchi (es. "Relistati: 1" alle 15:30 per un relist fatto alle 14:36).
- **Root cause**: Il notification batch non veniva resettato prima del reboot. Il `flush_if_any(force=True)` inviava dati accumulati anche ore prima.
- **Fix**: Sostituito `batch.flush_if_any(..., force=True)` con `batch.reset()` in `main.py` prima del reboot. I dati stale vengono scartati silenziosamente invece di essere inviati all'utente.
- **File modificato**: `main.py` — riga 222 (circa)
- **Verifica**: 740 test passano. ✅

### Fix 2: Notifica Telegram mancante alle 18:10 — Doppio check ridondante
- **Problema**: La notifica Telegram del relist delle 18:10 non veniva inviata, mentre quelle delle 16:10 e 17:10 funzionavano regolarmente.
- **Root cause**: Doppio check ridondante in `flush_if_any()`. In `main.py:201`, `is_ready_to_flush(next_wait)` passava correttamente (next_wait=3520 > 120). Ma dentro `flush_if_any()`, un secondo check `is_ready_to_flush(0)` usava `current_wait=0` hardcoded. Dopo un reboot, `last_flush_time` era `None` (nuovo oggetto NotificationBatch), quindi nessuna delle 3 condizioni era soddisfatta: `0 > 120` False, `cycles >= 5` False, `elapsed` saltato perché `last_flush_time is None`.
- **Fix**: Sostituito `if not force and not self.is_ready_to_flush(0): return` con `if not force and self.relisted == 0 and self.failed == 0: return` in `core/notification_batch.py`. Il chiamante (main.py) ha già verificato le condizioni di flush — il check interno era ridondante e causava notifiche perse.
- **File modificato**: `core/notification_batch.py` — righe 109-113
- **Verifica**: 740 test passano. ✅

### Today's Fixes (May 17, 2026)
### Fix 1: Telegram Report — Conteggio `Scaduti rilevati` senza doppio conteggio
- **Problema**: Il report Telegram poteva mostrare un numero impossibile di scaduti rilevati (es. `132`) anche se la Transfer List EA accetta massimo 100 oggetti.
- **Root cause**: `NotificationBatch.expired_detected` sommava gli `expired_count` delle scansioni batch. Durante cicli rapidi, processing wait o retry, il bot puo rileggere gli stessi slot della Transfer List; sommare le scansioni produceva doppio conteggio.
- **Fix**: `expired_detected` ora rappresenta gli oggetti realmente emersi nel batch:
  - usa il totale processato (`relisted + failed`) come base quando il bot lavora su piu cicli;
  - non somma scansioni duplicate quando un ciclo successivo rilegge gli stessi item senza processarne altri;
  - resta limitato alla capienza reale della Transfer List (`100`).
- **Esempi verificati**:
  - `78` rilistati + scansione successiva `54` senza lavoro extra -> `Scaduti rilevati: 78`, non `132`.
  - Tre cicli reali `30 + 20 + 10` -> `Scaduti rilevati: 60`.
- **File modificati**: `core/notification_batch.py`, `tests/test_notification_batch.py`
- **Verifica**: `python -m pytest tests\test_notification_batch.py tests\test_notification_batch_fix.py tests\test_notification_batch_user_concern.py -q` -> 20 test passano. ✅

### Today's Fixes (May 12, 2026)
### Fix 1: Golden Retry Loop — Ottimizzazione e Dati Freschi
- **Problema**: Il `_golden_retry_loop` veniva avviato anche se il relist principale era andato a buon fine (0 expired), causando un'attesa di 9s e una scansione DOM inutile. Inoltre, usava i dati di processing "stale" della scansione iniziale.
- **Root cause**: 
  1. Passaggio di `scan.processing_count` (pre-relist) invece del valore post-relist alla funzione di retry.
  2. Guardia interna `initial_f == 0 and processing_count == 0` che non scattava con dati stale.
- **Fix**: Il bot ora calcola `post_processing` usando l'ultimo risultato disponibile (`self._last_scan_result`) aggiornato durante la verifica del relist. Se non ci sono falliti né oggetti in processing dopo il relist, il retry loop viene saltato istantaneamente.
- **File modificato**: `logic/relist_engine.py` — `process_cycle()` (righe 183-187)
- **Verifica**: Log confermano l'uscita immediata e il calcolo del wait corretto verso la prossima golden hour. ✅

### Fix 2: Golden Retry Loop — Correzione Break Prematuro
- **Problema**: Il loop di retry usciva prematuramente se il numero di falliti era zero (`f == 0`), anche se c'erano ancora oggetti in stato "Processing" (limbo EA). Questo delegava il lavoro al ciclo principale (polling ogni 10s), invece di gestirlo internamente.
- **Root cause**: Condizione di `break` troppo semplice: `if f == 0: break`.
- **Fix**: La condizione di uscita ora è `if f == 0 and remaining_processing == 0`. Il loop rimane attivo e continua ad aspettare la transizione degli oggetti in limbo EA finché la golden window è aperta o i tentativi non finiscono.
- **File modificato**: `logic/relist_engine.py` — `_golden_retry_loop()` (righe 331-338)
- **Verifica**: Logica verificata per garantire che tutto il lavoro "golden" rimanga atomico dentro il loop di retry. ✅

### Today's Fixes (May 11, 2026)
### Fix 1: Heartbeat — Recupero Automatico Sessione Scaduta
- **Problema**: L'heartbeat rilevava la sessione scaduta ma non eseguiva alcun recupero. Il bot continuava a battere heartbeat per ore senza mai ristabilire la connessione EA.
- **Root cause**: `_execute_heartbeat()` in `browser/session_keeper.py` loggava l'errore ma non chiamava `ensure_session()` per il recupero.
- **Fix**: Dopo il rilevamento di sessione scaduta nell'heartbeat, il bot ora tenta automaticamente il recupero con `ensure_session()`. Se il recupero riesce, il bot continua normalmente. Se fallisce, invia notifica Telegram con screenshot e solleva `RebootRequestError` per riavvio controllato.
- **File modificato**: `browser/session_keeper.py` — `_execute_heartbeat()` (righe 173-198)
- **Verifica**: 693 test passano. ✅

### Fix 2: Reboot con os.execv() — Ricaricamento Completo dei Moduli
- **Problema**: Il commento in `telegram_handler.py` diceva "poi rilancia il processo" ma `handle_reboot()` fermava solo il browser. Il `while True` di `main.py` ripartiva nello stesso processo Python → `sys.modules` già popolato → zero moduli ricaricati → le modifiche al codice non venivano viste dopo un `/reboot`.
- **Root cause**: `handle_reboot()` non sostituiva il processo, faceva solo `controller.stop()` e il loop ricominciava nello stesso interprete.
- **Fix**: `handle_reboot()` ora usa `os.execv(sys.executable, [sys.executable, "main.py"])` per sostituire completamente il processo corrente con uno nuovo. Tutti i moduli vengono ricaricati da zero. Pulizia minimale: solo `controller.stop()` (try/except) + `os.execv()`.
- **File modificato**: `browser/session_keeper.py` — `handle_reboot()` (riga 301-308), `main.py` — chiamata semplificata senza parametri (riga 198)
- **Verifica**: 693 test passano. ✅

### Fix 3: Aumento Tentativi Processing Items Fuori Golden Window
- **Problema**: Gli item in stato "Processing" fuori dalla golden window avevano solo 3 tentativi con attese di 15-30s (totale ~90s). EA spesso impiega più tempo per processare gli item, specialmente sotto carico, e il bot li abbandonava troppo presto.
- **Root cause**: Parametri troppo conservativi in `_processing_wait_loop()`: max 3 tentativi, attesa 15-30s, nessun timeout totale.
- **Fix**: Aumentati i parametri per la fascia fuori golden window:
  - Tentativi: 3 → 15
  - Attesa: 15-30s → 30-60s
  - Timeout totale: nessuno → 300s (5 minuti)
  - Le 4 costanti sono in `logic/golden_hour.py` per centralizzazione
  - La golden window (`_golden_retry_loop`) rimane invariata (6 tentativi, 5-10s)
- **File modificati**: `logic/golden_hour.py` — 4 nuove costanti (righe 19-23), `logic/relist_engine.py` — `_processing_wait_loop()` riscritto (righe 330-389) + import costanti (righe 20-23)
- **Verifica**: 693 test passano. ✅

### Today's Fixes (May 07, 2026)
### Root Cause Fix: Telegram Relist Overcount (`17` invece di `16`)
- **Problema**: Durante la Golden Hour, EA puo lasciare per pochi secondi un item appena scaduto nella sezione DOM `active` con timer/testo `Expired`.
- **Sintomo osservato**: Dopo `Re-list All` di 16 oggetti, il post-scan contava falsamente `0 scaduti`; il bot calcolava quindi `16` successi invece dei reali `15`. Il Golden Retry rilistava poi l'ultimo item rimasto e la notifica Telegram riportava `17 rilistati`.
- **Root cause**: `browser/detector.py` classificava qualsiasi item in `section == "active"` come `ACTIVE`, salvo il caso `Processing...`. Mancava l'override per `Expired`/`Scaduto` dentro la sezione active.
- **Fix (Detector)**: Gli item in sezione `active` con testo `Expired`, `Scaduto` o varianti `expir` vengono ora classificati come `ListingState.EXPIRED`.
- **Test**: Aggiunto test di regressione in `tests/test_detector.py` per il caso `state='Expired'` + `section='active'`.
- **Verifica**: `python -m pytest` -> 687 test passano. Nessuna modifica alla Golden Hour logic. ✅

### Root Cause Fix: "Processing" Limbo & Double Notifications
- **Problema 1**: Gli item in stato "Processing" fuori dalla Golden Window venivano rilevati, ma il bot aspettava il ciclo successivo per relistarli, causando latenza inutile.
- **Problema 2**: Doppia notifica Telegram in caso di "mix" (alcuni item scaduti, altri in processing). Il primo relist triggerava un report, e il secondo relist (al ciclo dopo) ne triggerava un altro.
- **Fix (Relist Engine)**: 
  - `_processing_wait_loop` ora esegue il relist **immediatamente** dopo aver rilevato la transizione da Processing a Expired, tutto nello stesso ciclo.
  - La logica di decisione in `process_cycle` ora cattura i processing residui post-relist, garantendo che l'intera "ondata" venga gestita in un unico ciclo (e quindi un'unica notifica batch).
- **Fix (Stale Scan Reset)**: `self._last_scan_result` viene resettato a `None` all'inizio di ogni `process_cycle`. Evita che un valore stale da un ciclo precedente causi il bypass del `_processing_wait_loop` nel Caso 1 (solo processing items).

### Fix: Stale Page Detection (Polling Frenetico su Sessione Scaduta)
- **Problema**: Quando la sessione EA scade di notte, la pagina si congela. I timer JavaScript si bloccano su valori bassi (es. "< 15 Seconds"). Il bot interpreta i timer come "item in scadenza" e polla ogni ~10s per ore senza trovare mai expired.
- **Root cause**: `get_min_active_seconds` legge timer congelati → `_compute_next_wait` calcola `max(15 - 20, 10) = 10` → loop infinito di scansioni vuote.
- **Fix**: Aggiunto **stale page detector** in `process_cycle`: se il bot fa ≥10 cicli rapidi (wait ≤ 30s) consecutivi senza mai trovare expired, forza un `page.reload()` per ottenere dati freschi dal server EA.
- **Verifica**: Sintassi Python verificata, tutti i 686 test passano. ✅

### Today's Fixes (May 06, 2026)
### Root Cause Fix: `get_next_golden_hour()`
- **Problema**: La funzione restituiva la golden hour **corrente** se siamo nella sua finestra (:09-:11), invece della **prossima futura**
- **Fix**: Modificato `logic/golden_hour.py` → `get_next_golden_hour()` usa confronto stretto `target > now`
- **Impatto**: Tutti i chiamanti ottengono sempre la prossima golden hour futura

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
- **Total:** 740 tests passing.
- **Coverage:** 155 unit tests + 531 golden timeline simulations (added test_relist_engine.py, test_relist_imports.py)
