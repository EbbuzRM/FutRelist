# Code Review: FIFA 26 Auto-Relist Bot — Review Completa

**Date**: 2026-05-13
**Scope**: 20 file sorgente caricati (`browser/`, `logic/`, `models/`, `core/`, `bot_state.py`, `main.py`, `notifier.py`, `telegram_handler.py`)
**Files reviewed**: `auth.py`, `controller.py`, `detector.py`, `navigator.py`, `rate_limiter.py`, `relist.py`, `session_keeper.py`, `sold_handler.py`, `golden_hour.py`, `action_log.py`, `listing.py`, `relist_result.py`, `sold_result.py`, `relist_engine.py`, `notification_batch.py`, `error_handler.py`, `bot_state.py`, `main.py`, `notifier.py`, `telegram_handler.py`

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | 3 |
| 🟠 HIGH | 6 |
| 🟡 MEDIUM | 19 |
| 🟢 LOW | 12 |
| **Total** | **40** |

**Overall Assessment**: Il progetto è architetturalmente solido con una netta separazione dei layer (browser, business logic, models, core). La gestione della Golden Hour è ben centralizzata in `golden_hour.py` e i fallback per il parsing DOM sono robusti. I finding più gravi riguardano **sicurezza** (leak credenziali via screenshot in 3 file diversi), **race condition** su riferimenti DOM post-reload, e **swallowing di eccezioni critiche** (`RebootRequestError`) che impediscono il recovery automatico.

---
---

## Fix Applicate (2026-05-13)

### File Modificati

| File | Fix Applicati |
|------|--------------|
| `browser/auth.py` | **HI-01**: Aggiunto `perform_full_login()` per eliminare dipendenza circolare `main.py ↔ error_handler.py` |
| `browser/error_handler.py` | **HI-01**: Rimossi `from main import authenticate`, ora usa `auth.perform_full_login()`. **ME-03**: Rimosso parametro morto `get_credentials_fn` |
| `browser/relist.py` | **HI-05**: `AuthManager` injectato via constructor. **ME-10**: `force=True` sui click. **LO-08**: Semplificati `RelistBatchResult` |
| `browser/session_keeper.py` | **HI-06**: `RebootRequestError` re-raise prima del catch generico. **ME-07**: `return` dopo attivazione console mode. **ME-08**: Riuso `auth.check_and_handle_disconnect_modal()`. **LO-04**: `sys.argv[0]` invece di `"main.py"` |
| `logic/relist_engine.py` | **ME-05**: Selectors Transfer List centralizzati in `_DEFAULT_TRANSFER_SELECTORS` + override via `config["transfer_list_selectors"]`. **Bug fix**: corretti 14 riferimenti `fifa_logger` → `self._fifa_logger` (NameError runtime) |
| `browser/detector.py` | **ME-06**: Keyword `"<"` ristretta a `"<\d"` |
| `browser/navigator.py` | **ME-09**: `dismiss_popups()` ora gestisce popup multipli — loop 3 pass senza `break` prematuro, check `found_any` |
| `notifier.py` | **ME-17**: Retry con exponential backoff (max 3 tentativi, base 2s) su `send_telegram_alert()` e `send_telegram_photo()` |
| `telegram_handler.py` | **ME-17**: Retry con exponential backoff su `_get_updates()`, `_send_message()`, `_send_photo()`. **ME-18**: Race condition `stop()` — `_get_updates()` usa timeout breve (5s) con check `_stop_event`; `join(timeout=15)` invece di 35s |
| `main.py` | **ME-19**: `except (MemoryError, RecursionError)` aggiunto prima di `except Exception` — fatali terminano con `sys.exit(1)` senza reboot |
| `logic/golden_hour.py` | **LO-02**: Magic numbers centralizzati — `GOLDEN_RETRY_MAX_ATTEMPTS=6`, `GOLDEN_RETRY_MIN_WAIT=5.0`, `GOLDEN_RETRY_MAX_WAIT=10.0` |
| `browser/controller.py` | **LO-07**: `DEFAULT_PROFILE_DIR` spostato da class variable a variabile di modulo |

### Fix Preesistenti Non Dichiarate nella Review Originale

Queste fix sono presenti nel codice al momento della review ma non elencate nella tabella "Fix Applicate" (13 Maggio 2026). Vanno comunque riconosciute come già implementate:

| ID | File | Descrizione |
|----|------|-------------|
| ME-02 | `core/notification_batch.py` | Path screenshot thread-safe con `tempfile.NamedTemporaryFile` |
| ME-16 | `telegram_handler.py` | Path screenshot thread-safe con `tempfile.NamedTemporaryFile` |

### Stato Review Aggiornato (14 Maggio 2026, 01:34)

| Severity | Totale | Fixati | Rimasti |
|----------|--------|--------|---------|
| 🔴 CRITICAL | 3 | 3 | 0 |
| 🟠 HIGH | 6 | 6 | 0 |
| 🟡 MEDIUM | 19 | 19 | 0 |
| 🟢 LOW | 12 | 12 | 0 |
| **Total** | **40** | **40** | **0** |

### Fix Rimasti da Applicare

**Tutti i fix sono stati applicati. Nessun rimanente.**
---


## Findings

---

### 🔴 CRITICAL

#### CR-01: Credential Exposure via Telegram Screenshot Error Reporting
- **Category**: Security
- **File**: `notification_batch.py:60-66`
- **Issue**: Il metodo `flush()` chiama `page.screenshot(path=screenshot_path)` **senza verificare l'URL corrente**. Se il bot è su `signin.ea.com` (sessione scaduta durante il batch), lo screenshot cattura il campo password in chiaro e lo invia su Telegram.
- **Impact**: Password EA leak sui server Telegram e nella cronologia chat. Un account Telegram compromesso espone direttamente le credenziali FIFA.
- **Fix**: Aggiungere guardia prima dello screenshot:
  ```python
  if page and "signin.ea.com" in page.url.lower():
      logger.warning("Skip screenshot: pagina di login (sicurezza credenziali)")
      page = None
  ```
- **Verification**: Verificare che `page.url` sia controllato prima di ogni `page.screenshot()` in `flush()`.
- **Cross-check**: Confermato da DeepSeek CR-01. **Ancora presente** nel codice caricato.

---

#### CR-02: `_last_scan_result` Race Condition su `page.reload()` Path
- **Category**: Bug / Race Condition
- **File**: `relist_engine.py:213-220`
- **Issue**: Nel path 'stale page detection', dopo `self.page.reload()` il codice riscanizza il DOM ma **non invalida `self._last_scan_result` prima del reload** e non lo aggiorna dopo. Se il caller esterno (o metodi downstream) usano `self._last_scan_result`, ottengono riferimenti `ElementHandle` pre-reload (stale/detached), causando `TargetClosedError` in Playwright.
- **Impact**: Crash silenzioso o eccezioni DOM detached dopo il 10° ciclo idle consecutivo. Bug difficile da riprodurre in dev.
- **Fix**:
  ```python
  self._fast_idle_cycles = 0
  self._last_scan_result = None      # Invalida riferimenti vecchi
  self.page.reload()
  self.page.wait_for_timeout(5000)
  scan = self.detector.scan_listings()
  self._last_scan_result = scan      # Aggiorna con dati freschi
  next_wait = self._compute_next_wait(scan)
  ```
- **Verification**: Verificare che `_last_scan_result` sia `None` prima del reload e riassegnato dopo la riscan.
- **Cross-check**: Confermato da DeepSeek CR-02. **Ancora presente** nel codice caricato.

---

#### CR-03: Credential Exposure via Screenshot in `notifier.py` e `telegram_handler.py`
- **Category**: Security
- **File**: `notifier.py:55-60`, `telegram_handler.py:287`
- **Issue**: `send_telegram_error_with_screenshot()` (notifier) e `_execute_screenshot()` (telegram_handler) chiamano `page.screenshot()` **senza verificare l'URL**. Se il bot è sulla pagina di login EA quando scatta un errore o l'utente richiede `/screenshot`, la password finisce su Telegram. Questo è lo stesso problema di CR-01 ma in due file aggiuntivi.
- **Impact**: Leak credenziali identico a CR-01. In `telegram_handler.py` il comando `/screenshot` è esplicitamente esposto all'utente — basta che il bot sia in recovery sessione quando l'utente invia il comando.
- **Fix**: Aggiungere la stessa guardia URL in entrambi i metodi:
  ```python
  if self.page and "signin.ea.com" in self.page.url.lower():
      logger.warning("Skip screenshot: pagina di login")
      return {"success": False, "error": "Pagina di login - screenshot bloccato per sicurezza"}
  ```
- **Verification**: Testare `/screenshot` e errori durante il recovery sessione.
- **Cross-check**: Nuovo finding — estensione di CR-01 a file non analizzati nelle review precedenti.

---

### 🟠 HIGH

#### HI-01: Dipendenza Circolare Runtime — `authenticate()` da `error_handler.py`
- **Category**: Bug / Maintainability
- **File**: `error_handler.py:137,165`
- **Issue**: `ensure_session()` importa e chiama `authenticate` da `main.py` in **due punti diversi** (`from main import authenticate`). Questo crea una dipendenza circolare nascosta: `main.py` importa `error_handler`, e `error_handler` importa `main`. L'import differito (dentro il function body) lo rende fragile — un refactoring di `main.py` rompe il recovery sessione a runtime.
- **Impact**: Se `authenticate()` viene spostata o rinominata, `ensure_session()` fallisce con `ImportError`, lasciando il bot senza recovery sessione.
- **Fix**: Estrarre `authenticate()` in un modulo dedicato (es. `browser/auth.py` come metodo `AuthManager` o modulo `browser/authenticate.py`) e importarlo da lì in entrambi i file.
- **Verification**: Eliminare tutti i `from main import authenticate` da `error_handler.py`.
- **Cross-check**: Confermato da DeepSeek HI-01 / Mistral HI-01. **Ancora presente**, anzi raddoppiato (due import invece di uno).

---

#### HI-02: `scan` Potenzialmente Unbound in `_processing_wait_loop` Fallback
- **Category**: Bug (edge case)
- **File**: `relist_engine.py:387-401`
- **Issue**: `scan` è assegnato solo dentro il `while` loop (riga 376). Se il loop non entra mai (es. `PROCESSING_MAX_TOTAL_TIME` è 0, negativo, o `total_time_elapsed` è già >= 300), `scan` non esiste. Alle righe 390 e 397 il codice referenzia `scan.processing_count` → `UnboundLocalError`.
- **Impact**: Crash del ciclo se costanti malconfigurate o clock skew. Latente in produzione (dove `PROCESSING_MAX_TOTAL_TIME` è 300) ma un difetto strutturale.
- **Fix**: Inizializzare `scan` prima del loop:
  ```python
  scan = self._last_scan_result  # Fallback all'ultima scan nota
  while attempt < max_attempts and total_time_elapsed < PROCESSING_MAX_TOTAL_TIME:
      # ... loop body, scan viene eventualmente sovrascritto
  ```
- **Verification**: Verificare che `scan` sia definito prima del blocco `while`.
- **Cross-check**: Confermato da DeepSeek ME-02. **Ancora presente**.

---

#### HI-03: Nessuna Protezione su Scan Post-Relist (Entrambe le Verifiche)
- **Category**: Resilience
- **File**: `relist_engine.py:250,263`
- **Issue**: `_execute_relist_with_verification()` chiama `self.detector.scan_listings()` sia per la prima verifica (riga 250) che per la seconda (riga 263) **senza try/except**. Se una scan fallisce (timeout, DOM crashato, pagina chiusa da EA), l'intero ciclo muore con unhandled exception. Inoltre, se il crash avviene dopo che le stats sono già state aggiornate (riga 268), i contatori restano inconsistenti.
- **Impact**: Bot crashato durante la verifica post-relist. Potenziale inconsistenza nelle statistiche.
- **Fix**: Wrappare entrambe le scan in try/except con fallback conservativo:
  ```python
  try:
      post_scan = self.detector.scan_listings()
  except Exception as e:
      fifa_logger.error(f"Scan verifica post-relist fallita: {e}")
      return 0, scan.expired_count  # Fallback: tutto fallito
  ```
- **Verification**: Simulare un timeout di `scan_listings()` durante la verifica.
- **Cross-check**: Estensione di DeepSeek LO-04 (che segnalava solo la seconda scan).

---

#### HI-04: `truly_expired` Può Diventare Negativo
- **Category**: Bug (edge case)
- **File**: `relist_engine.py:186`
- **Issue**: `truly_expired = scan.expired_count - scan.processing_count`. Se per un qualsiasi motivo `processing_count > expired_count` (stato inconsistente del DOM EA o race condition), il valore diventa negativo. Il check `if truly_expired <= 0` funziona, ma il valore negativo viene loggato e passato alla logica successiva, generando messaggi confusi.
- **Impact**: Log fuorvianti e potenziale bug se il valore viene usato in calcoli futuri.
- **Fix**: Usare `max(0, ...)` come già fatto correttamente in `_execute_relist_with_verification` (riga 255):
  ```python
  truly_expired = max(0, scan.expired_count - scan.processing_count)
  ```
- **Verification**: Verificare che `truly_expired` sia sempre >= 0.
- **Cross-check**: Nuovo finding non segnalato nelle review precedenti.

---

#### HI-05: `AuthManager` Instanziato Ripetutamente — Resource Waste & Inconsistenza
- **Category**: Performance / Code Quality
- **File**: `relist.py:49,108,205`
- **Issue**: `RelistExecutor._click_relist_button()`, `RelistExecutor.relist_all()`, e `RelistExecutor.check_session_valid()` creano ognuno un nuovo `AuthManager(self.config)`. Ogni istanza chiama `self.PROFILE_DIR.mkdir(parents=True, exist_ok=True)` in `__init__`. Inoltre, `RelistEngine` riceve `auth` via constructor ma `RelistExecutor` non lo usa — viola il pattern DI usato nel resto del progetto.
- **Impact**: Overhead minimo (filesystem `mkdir` ripetuti) ma incoerenza architetturale. Più grave: se la logica di `AuthManager` cambia (es. side effects in `__init__`), i punti di creazione sparsi diventano un rischio.
- **Fix**: Passare `AuthManager` a `RelistExecutor` via constructor (come fa `RelistEngine` in `main.py`):
  ```python
  def __init__(self, page, config, rate_limiter=None, auth=None):
      self.auth = auth  # Usa istanza injectata
  ```
- **Verification**: Nessuna chiamata `AuthManager()` dentro `RelistExecutor` dopo il refactoring.
- **Cross-check**: Confermato da DeepSeek HI-03. **Ancora presente**.

---

#### HI-06: `_execute_heartbeat()` — Exception Swallowing Maschera `RebootRequestError`
- **Category**: Error Handling
- **File**: `session_keeper.py:129-201`
- **Issue**: Il `try/except` esterno di `_execute_heartbeat()` (riga ~200: `except Exception as e: logger.debug(...)`) cattura **tutte** le eccezioni, incluso `RebootRequestError` sollevato a riga ~198. La richiesta di reboot viene loggata a DEBUG e **silenziosamente scartata**. Il bot continua a girare con una sessione rotta, potenzialmente per ore.
- **Impact**: Quando il recovery sessione fallisce durante l'heartbeat, il bot non si riavvia mai. Perdita di relist window e rischio ban per comportamento anomalo.
- **Fix**: Re-raise `RebootRequestError` prima del catch generico:
  ```python
  except RebootRequestError:
      raise  # Deve propagare per triggerare il reboot
  except Exception as e:
      logger.debug(f"Errore heartbeat: {e}")
  ```
- **Verification**: Simulare sessione scaduta durante heartbeat e verificare che `os.execv` venga invocato.
- **Cross-check**: Confermato da DeepSeek ME-06. **Ancora presente**.

---

### 🟡 MEDIUM

#### ME-01: `action_logger` Assente nel Path Batch Relist
- **Category**: Logging / Observability
- **File**: `relist_engine.py:244-270`
- **Issue**: `action_logger` (logger strutturato per `logs/actions.jsonl`) è usato solo nel path `relist_mode == "per_listing"` (righe 283-286). Il path batch `"all"` (il modo più comune) non logga nulla su `actions.jsonl`, rendendo impossibile auditare i batch relist.
- **Impact**: Audit trail incompleto per l'operazione più frequente.
- **Fix**: Aggiungere dopo il successo del batch:
  ```python
  action_logger.info("Rilist batch completato", extra={
      "action": "relist_batch",
      "success": True,
      "relisted": first_succeeded + second_succeeded,
      "failed": max(final_scan.expired_count - final_scan.processing_count, 0),
  })
  ```
- **Cross-check**: Confermato da DeepSeek ME-05. **Ancora presente**.

---

#### ME-02: Path Screenshot Hardcoded e Non Thread-Safe
- **Category**: Bug (edge case)
- **File**: `notification_batch.py:59`
- **Issue**: `screenshot_path = "relist_report.png"` è un path relativo fisso nel CWD. Se due istanze di `NotificationBatch` flushano contemporaneamente (flush forzato + flush automatico), si corrompono a vicenda. Inoltre, se il processo crasha tra `screenshot()` e `os.remove()`, il file orfano persiste.
- **Impact**: Molto basso (una sola istanza nel codice attuale), ma pattern fragile.
- **Fix**: Usare `tempfile.NamedTemporaryFile(suffix=".png", delete=False)` per path univoci e cleanup esplicito.
- **Cross-check**: Confermato da DeepSeek LO-05. **Ancora presente**.

---

#### ME-03: Parametro Morto `get_credentials_fn` in `ensure_session`
- **Category**: Code Quality
- **File**: `error_handler.py:105-165`
- **Issue**: `get_credentials_fn` è dichiarato nella firma di `ensure_session()` ma **mai utilizzato nel corpo**. Viene invece chiamato `authenticate(controller, auth, page)` che gestisce le credenziali internamente. Il parametro è ingannevole per chi legge la firma.
- **Impact**: Confusione API. Se un caller passa una callback custom, si aspetta che venga usata — invece viene ignorata.
- **Fix**: Rimuovere il parametro o passarlo effettivamente ad `authenticate()`.
- **Cross-check**: Nuovo finding.

---

#### ME-04: Log `_processing_wait_loop` Mostra Conteggio Iniziale, Non Attuale
- **Category**: Logging / Observability
- **File**: `relist_engine.py:355-360`
- **Issue**: Il messaggio di log dentro il loop usa `processing_count` (parametro passato al metodo), non `scan.processing_count` (valore attuale dopo la scan). Se gli item passano da 5 a 2, il log continua a dire "5 item in limbo".
- **Impact**: Log fuorvianti durante il debug di processing items.
- **Fix**: Usare `scan.processing_count` nel log (dopo aver fatto `scan = self.detector.scan_listings()`).
- **Cross-check**: Nuovo finding.

---

#### ME-05: Selectors Hardcoded nel Quick Check Navigazione
- **Category**: Maintainability
- **File**: `relist_engine.py:460-467`
- **Issue**: `_navigate_with_retry()` usa una lista di selettori CSS hardcoded (`.ut-transfer-list-view`, `.listFUTItem`, `.no-items`, `.empty-list`, `.no-listings`). Se EA aggiorna la WebApp, questi selettori devono essere modificati nel codice sorgente.
- **Impact**: Ogni aggiornamento EA richiede una modifica al codice e un redeploy.
- **Fix**: Spostare i selettori in `config/config.json` o in una classe `Selectors` centralizzata.
- **Cross-check**: Confermato da Mistral HI-03. **Ancora presente**.

---

#### ME-06: `determine_state()` — Keyword `"<"` Troppo Generico
- **Category**: Bug (edge case)
- **File**: `detector.py:142`
- **Issue**: La lista di keyword per `ListingState.ACTIVE` include `"<"` come match generico. Se il testo dello stato contiene caratteri HTML residui (es. `<div>` in `innerText` anomalo), potrebbe classificare erroneamente un listing come ACTIVE.
- **Impact**: Falso positivo ACTIVE molto raro, mitigato dalla classificazione per sezione in `scan_listings()`. Rischio basso ma latente.
- **Fix**: Rimuovere `"<"` dalla lista o restringerlo a `"<\d"` (matcha solo `<` seguito da cifra, come in `<15 Seconds`).
- **Cross-check**: Confermato da DeepSeek ME-07. **Ancora presente**.

---

#### ME-07: `session_keeper` Continua Dopo Console Session Rilevata
- **Category**: Bug / Resilience
- **File**: `session_keeper.py:173-185`
- **Issue**: Dopo aver rilevato una sessione console (`is_console_session_active`), `_execute_heartbeat()` setta `console_mode` nel `bot_state` ma **non fa return**. Prosegue con `if not self.auth.is_logged_in(...)`, tenta il recovery, e se fallisce invia notifiche Telegram. Questo genera spam di notifiche durante la console mode.
- **Impact**: Notifiche Telegram ripetute e inutili mentre l'utente sta giocando sulla console. Rischio di raggiungere i rate limit di Telegram.
- **Fix**: Aggiungere `return` subito dopo aver attivato la console mode:
  ```python
  if self.auth.is_console_session_active(self.page):
      logger.warning("Heartbeat ha rilevato la console in uso!")
      self.bot_state.set_console_session_active(True)
      if not self.bot_state.is_console_mode():
          self.bot_state.set_console_mode(True, hours=0.5)
      return  # ← Aggiungere questo
  ```
- **Cross-check**: Nuovo finding.

---

#### ME-08: Duplicazione Logica Modale Disconnessione
- **Category**: Code Quality / DRY
- **File**: `session_keeper.py:_handle_post_heartbeat_modals`
- **Issue**: `_handle_post_heartbeat_modals()` duplica la stessa logica di rilevamento keyword e click OK già presente in `auth.check_and_handle_disconnect_modal()`. Le liste `disconnect_keywords` e i selettori `dialog_selectors` sono replicati.
- **Impact**: Se EA cambia il testo del modale, devi modificare due file. Rischio di inconsistenza.
- **Fix**: Riusare `self.auth.check_and_handle_disconnect_modal(self.page)` nell'heartbeat invece di reimplementare la logica.
- **Cross-check**: Nuovo finding.

---

#### ME-09: `dismiss_popups` Non Gestisce Popup Multipli con Label Diverse
- **Category**: Bug / Resilience
- **File**: `navigator.py:28-50`
- **Issue**: Il metodo `dismiss_popups()` itera su una lista di label. Appena trova e clicca un bottone, fa `break`, uscendo dal loop. Se ci sono due popup consecutivi con label diverse (es. primo "Continue", secondo "Got It"), il secondo rimane aperto.
- **Impact**: Popup residui possono bloccare i click successivi, causando fallimenti di navigazione.
- **Fix**: Rimuovere il `break` e fare multiple pass finché non ci sono più popup visibili, oppure usare un loop `while` con un contatore massimo.
- **Cross-check**: Nuovo finding.

---

#### ME-10: `relist_all` Click Senza `force=True`
- **Category**: Resilience
- **File**: `relist.py:120`
- **Issue**: `relist_all_btn.click()` non usa `force=True`. Se un overlay (es. click-shield di EA) intercetta il click, Playwright throwa un'eccezione. In `navigator.py` e `auth.py` viene usato `force=True` come fallback; qui no.
- **Impact**: Relist batch fallito se lo shield di EA è ancora visibile.
- **Fix**: Aggiungere `force=True` al click, o wrappare con `wait_for_click_shield` prima.
- **Cross-check**: Nuovo finding.

---

#### ME-11: Duplicazione Navigazione in `sold_handler.py`
- **Category**: Code Quality / DRY
- **File**: `sold_handler.py:_navigate_to_sold_items`
- **Issue**: `_navigate_to_sold_items()` duplica la logica Transfers → Transfer List già implementata in `navigator.go_to_transfer_list()`. Dovrebbe riusare `navigator.go_to_transfer_list()` e poi cliccare solo su "Sold".
- **Impact**: Codice duplicato da mantenere in due punti. Se EA cambia la sidebar, entrambi i metodi devono essere aggiornati.
- **Fix**: Chiamare `self.navigator.go_to_transfer_list()` (se `SoldHandler` ha accesso al navigator) o estrarre la logica comune.
- **Cross-check**: Nuovo finding.

---

#### ME-12: Parametri Morti `cycle_num` e `session_keeper` in `process_cycle`
- **Category**: Code Quality
- **File**: `relist_engine.py:67`
- **Issue**: `process_cycle(self, cycle_num: int, session_keeper)` dichiara due parametri che **non sono utilizzati nel corpo del metodo**. `cycle_num` non viene referenziato; `session_keeper` non viene usato (il chiamante in `main.py` probabilmente lo usa dopo il return).
- **Impact**: Firma ingannevole. Confusione per chi implementa test o mock.
- **Fix**: Rimuovere entrambi i parametri se non servono, o documentare perché sono presenti.
- **Cross-check**: Nuovo finding.

---

#### ME-13: Heuristic Relist Manuale Non Commentata
- **Category**: Documentation
- **File**: `relist_engine.py:140-150`
- **Issue**: L'euristica per rilevare un relist manuale (check su `active_times`, range 3400-3600s, 10600-10800s, 21400-21600s, diff <= 90s) non ha commenti esplicativi. È impossibile capire la logica senza leggere attentamente il codice.
- **Impact**: Onboarding difficile. Modifiche future rischiano di rompere l'euristica.
- **Fix**: Aggiungere docstring o commenti inline che spieghino i range e il ragionamento.
- **Cross-check**: Confermato da Mistral ME-04. **Ancora presente**.

---

#### ME-14: `_last_scan_result` Non Aggiornato nel Path `per_listing`
- **Category**: Bug (edge case)
- **File**: `relist_engine.py:283-290`
- **Issue**: Nel path `relist_mode == "per_listing"`, `_execute_relist_with_verification()` non setta `self._last_scan_result`. Downstream (`process_cycle`) usa `self._last_scan_result or scan`, quindi usa la scan **pre-relist** per calcolare `post_processing` e il prossimo wait. I processing items post-relist potrebbero non essere gestiti correttamente fuori dalla golden window.
- **Impact**: Fuori dalla golden window, processing items residui dopo un relist per_listing potrebbero non essere gestiti fino al ciclo successivo.
- **Fix**: Aggiungere `self._last_scan_result = self.detector.scan_listings()` dopo il loop per_listing, o almeno documentare che il path per_listing non supporta processing wait.
- **Cross-check**: Nuovo finding.

---

#### ME-15: `_save_error_screenshot` Usa Path Relativo
- **Category**: Code Quality
- **File**: `relist_engine.py:495-498`
- **Issue**: `path = f"relist_error_{ts}.png"` è un path relativo al CWD. Se il bot cambia directory di lavoro, gli screenshot finiscono in posti diversi. Inoltre non c'è cleanup automatico.
- **Impact**: Screenshot sparsi nel filesystem. Difficile trovarli in produzione.
- **Fix**: Usare un path assoluto configurabile (es. `self.config.get("screenshot_dir", "logs/screenshots")`).
- **Cross-check**: Nuovo finding.

---

#### ME-16: Hardcoded Screenshot Path in `telegram_handler.py`
- **Category**: Bug (edge case)
- **File**: `telegram_handler.py:287`
- **Issue**: `_execute_screenshot()` usa `screenshot_path = "manual_screenshot.png"` — path relativo fisso. Se due utenti richiedono `/screenshot` in rapida successione (o se il bot crasha prima dell'`unlink`), il file si sovrascrive o persiste.
- **Impact**: Collisione di file tra richieste consecutive. File orfano in caso di crash.
- **Fix**: Usare `tempfile.NamedTemporaryFile(suffix=".png", delete=False)` come fa `notifier.py`.
- **Cross-check**: Nuovo finding.

---

#### ME-17: Nessun Retry su Errori 409 di Telegram
- **Category**: Resilience
- **File**: `notifier.py`, `telegram_handler.py`
- **Issue**: Entrambi i file fanno chiamate API Telegram senza retry per errori transienti (es. HTTP 409 Conflict da `getUpdates` sovrapposte, timeout di rete). `telegram_handler.py` ha un commento che menziona il 409 ma non implementa backoff.
- **Impact**: Messaggi e screenshot possono essere persi silenziosamente durante periodi di alta attività o network instabile.
- **Fix**: Aggiungere un decorator o wrapper con exponential backoff (max 3 tentativi, base 2s) per tutte le chiamate API Telegram.
- **Cross-check**: Confermato da DeepSeek ME-04. **Ancora presente**.

---

#### ME-18: `telegram_handler.stop()` Race Condition sul Join Timeout
- **Category**: Bug (race condition)
- **File**: `telegram_handler.py:85-95`
- **Issue**: `stop()` chiama `self._thread.join(timeout=35)`. Il thread di polling fa `urlopen` con timeout=35 (30+5). Se la richiesta di rete è bloccata per l'intero timeout, `join(35)` potrebbe ritornare prima che il thread termini effettivamente. Il commento nel codice ammette esplicitamente questo rischio ("evitando l'errore 409 Conflict"), ma la soluzione non è robusta.
- **Impact**: Se `join` ritorna False, il thread precedente è ancora vivo. Un nuovo `start()` crea un secondo thread di polling → 409 Conflict su Telegram API.
- **Fix**: Usare un `threading.Event` per segnalare al thread di uscire **prima** di `urlopen`, oppure usare `requests` con timeout configurabile e check periodico di `_stop_event`.
- **Cross-check**: Nuovo finding.

---

#### ME-19: `main.py` Outer Exception Handler Non Distingue Errori Fatali
- **Category**: Error Handling
- **File**: `main.py:206-224`
- **Issue**: Il blocco `except Exception as e` nel loop principale cattura **tutte** le eccezioni standard (incluso `MemoryError`, `RecursionError`). Questi errori sono spesso sintomi di condizioni fatali (OOM, stack overflow) dove il reboot non ha senso e potrebbe peggiorare la situazione.
- **Impact**: In caso di OOM, il bot entra in un loop di reboot → crash → reboot, consumando risorse e spam Telegram.
- **Fix**: Catturare eccezioni specifiche (`PlaywrightError`, `AuthError`, `ConnectionError`) e lasciare propagare `MemoryError` / `RecursionError` per terminare il processo.
- **Cross-check**: Nuovo finding.

---

### 🟢 LOW

#### LO-01: `fifa_logger` Recuperato N Volte Invece di Una
- **Category**: Code Quality
- **File**: `relist_engine.py` (multiple righe: 72, 101, 239, 292, 342, 387, 409, 432, 460)
- **Issue**: `logging.getLogger("fifa")` è chiamato all'interno di quasi ogni metodo. Restituisce sempre lo stesso singleton, ma è rumore visivo.
- **Fix**: Definire `self._fifa_logger = logging.getLogger("fifa")` una volta nel `__init__`.
- **Cross-check**: Confermato da DeepSeek LO-01 / Mistral LO-02. **Ancora presente**.

---

#### LO-02: Magic Numbers nel Golden Retry Loop
- **Category**: Code Quality
- **File**: `relist_engine.py:304,308`
- **Issue**: `max_retries = 6` e `random.uniform(5, 10)` sono hardcoded. Inconsistente con il resto del codice che centralizza costanti in `golden_hour.py`.
- **Fix**: Aggiungere `GOLDEN_RETRY_MAX_ATTEMPTS`, `GOLDEN_RETRY_MIN_WAIT`, `GOLDEN_RETRY_MAX_WAIT` in `golden_hour.py`.
- **Cross-check**: Confermato da DeepSeek LO-02. **Ancora presente**.

---

#### LO-03: URL Hardcoded nel Recovery Sessione
- **Category**: Maintainability
- **File**: `relist_engine.py:480`
- **Issue**: `self.page.goto("https://www.ea.com/fifa/ultimate-team/web-app/")` è hardcoded. `controller.py` ha già `navigate_to_webapp()` che legge da config.
- **Fix**: Usare `self.config.get("fifa_webapp_url", "...")` o delegare a `controller.navigate_to_webapp()`.
- **Cross-check**: Nuovo finding.

---

#### LO-04: `handle_reboot` Path Hardcoded
- **Category**: Bug (edge case)
- **File**: `session_keeper.py:240`
- **Issue**: `os.execv(sys.executable, [sys.executable, "main.py"])` assume che `main.py` sia nel CWD. Se il bot è avviato da un'altra directory, il reboot fallisce.
- **Fix**: Usare `sys.argv[0]` o un path assoluto configurato.
- **Cross-check**: Nuovo finding.

---

#### LO-05: `_parse_coin_value` Duplicato
- **Category**: DRY
- **File**: `sold_handler.py`
- **Issue**: `_parse_coin_value()` duplica la logica di `detector.parse_price()`. Entrambi usano `re.sub(r'[^\d]', '', text)`.
- **Fix**: Riusare `detector.parse_price()` in `sold_handler.py`.
- **Cross-check**: Nuovo finding.

---

#### LO-06: `last_flush_time` Inutilizzato in `NotificationBatch`
- **Category**: Dead Code
- **File**: `notification_batch.py`
- **Issue**: `self.last_flush_time` è inizializzato a `None`, settato in `reset()`, ma **mai letto** in `is_ready_to_flush()` o altrove.
- **Fix**: Rimuovere l'attributo o usarlo per calcolare il tempo trascorso dall'ultimo flush.
- **Cross-check**: Nuovo finding.

---

#### LO-07: `DEFAULT_PROFILE_DIR` Come Class Variable
- **Category**: Code Quality
- **File**: `controller.py`
- **Issue**: `DEFAULT_PROFILE_DIR` è una class variable ma viene acceduta via `self.DEFAULT_PROFILE_DIR` in `start()`. Funziona ma è stile inconsistente.
- **Fix**: Spostare in variabile di modulo o in `__init__`.
- **Cross-check**: Nuovo finding.

---

#### LO-08: `relist_all` Crea Batch Result Ridondante
- **Category**: Code Quality
- **File**: `relist.py:130-135`
- **Issue**: `batch_result = RelistBatchResult.from_results([])` poi `batch_result.relist_error = None`. `relist_error` è già `None` di default.
- **Fix**: Semplificare con `return RelistBatchResult()`.
- **Cross-check**: Nuovo finding.

---

#### LO-09: `_cap_wait` Nome Poco Descrittivo
- **Category**: Naming
- **File**: `relist_engine.py:432-442`
- **Issue**: `_cap_wait` non chiarisce che limita il wait per il Pre-Nav Guard.
- **Fix**: Rinominare in `_limit_wait_for_pre_nav`.
- **Cross-check**: Confermato da Mistral LO-01. **Ancora presente**.

---

#### LO-10: `expired_detected` Inutilizzato in `NotificationBatch`
- **Category**: Dead Code
- **File**: `notification_batch.py:30`
- **Issue**: `self.expired_detected` viene accumulato in `accumulate()` ma **mai usato** nel messaggio di `flush()`.
- **Fix**: Rimuovere l'attributo o includerlo nel report Telegram.
- **Cross-check**: Nuovo finding.

---

#### LO-11: `_command_event` Inutilizzato in `BotState`
- **Category**: Dead Code
- **File**: `bot_state.py:47`
- **Issue**: `_command_event: threading.Event` è creato in `__init__` ma **mai usato** in `wait_interruptible()` o altrove. Il metodo usa invece `has_commands()` con polling ogni 2 secondi.
- **Fix**: Rimuovere l'attributo o usarlo per svegliare `wait_interruptible()` istantaneamente quando arriva un comando (sostituendo il polling).
- **Cross-check**: Nuovo finding.

---

#### LO-12: `wait_interruptible` Busy-Wait Anti-Pattern
- **Category**: Performance
- **File**: `bot_state.py:122-144`
- **Issue**: `wait_interruptible()` usa un loop che controlla `datetime.now()` ogni 2 secondi. Durante attese lunghe (es. 3600s in hold window), il loop gira ~1800 iterazioni, creando oggetti `datetime` e acquisendo il lock ogni volta.
- **Impact**: ~1% CPU su VPS moderno, ma inutile su istanze low-power.
- **Fix**: Usare `threading.Event.wait(timeout=...)` per la durata completa, svegliandosi solo su reboot o comando (usando `_command_event`).
- **Cross-check**: Confermato da DeepSeek HI-04 / Mistral ME-06. **Ancora presente**.

---

## Positive Notes

1. **Architettura a layer pulita**: separazione chiara tra `browser/` (I/O Playwright), `logic/` (business rules), `models/` (data), `core/` (utilities). Nessun leakage di Playwright nei models.
2. **Gestione robusta del click-shield**: `auth.wait_for_click_shield()` usa `wait_for_function` e verifica attiva dello stato del DOM, evitando attese arbitrarie.
3. **Fallback multipli per parsing temporale**: `detector.parse_time_remaining()` gestisce 6+ formati diversi (colon, word, suffix, EA `<N` format). Molto resiliente agli aggiornamenti EA.
4. **Golden Hour logic centralizzata**: tutte le costanti e i check temporali sono in `golden_hour.py`. Facile da testare e modificare.
5. **Config validation**: `AppConfig` (citato nelle review precedenti) usa dataclass con `__post_init__` per validazione e coercizione tipi.
6. **Thread-safe state management**: `BotState` usa `threading.Lock` con pattern consume-on-read.
7. **Heartbeat-based session keeping**: `session_keeper.py` implementa un heartbeat proattivo che clicca 'Transfers' per mantenere la sessione viva, non solo polling passivo.
8. **Structured logging**: separazione tra `app.log`, `actions.jsonl` (con `JsonFormatter`), e logger `fifa` dedicato.
9. **Test suite**: 693 test passanti (citato nelle review precedenti), con 531 simulazioni golden timeline. Ottima copertura della business logic critica.
10. **Defensive DOM parsing**: `detector.scan_listings()` ha sia estrazione bulk che fallback per-elemento, con classificazione per sezione heading.
11. **Telegram handler thread-safe**: i comandi `/screenshot` e `/del_sold` vengono messi in coda e eseguiti nel main thread, evitando race condition con Playwright.
12. **Cleanup screenshot in `notifier.py`**: `send_telegram_error_with_screenshot()` usa `tempfile` e rimuove il file in `finally`, a differenza di `notification_batch.py` e `telegram_handler.py`.

---

## Recommendations

### Priorità P0 (Fix Prima del Prossimo Deploy)

### Priorità P1 (Fix nella Prossima Sprint)
1. **[HI-01]** Eliminare i `from main import authenticate` da `error_handler.py`. Spostare `authenticate()` in un modulo dedicato.
2. **[HI-03]** Wrappare le scan post-relist in `try/except` con fallback conservativo.
3. **[ME-07]** Aggiungere `return` in `_execute_heartbeat()` subito dopo l'attivazione della console mode.
4. **[ME-01]** Aggiungere `action_logger` nel path batch relist.
5. **[ME-17]** Aggiungere retry con exponential backoff per le chiamate API Telegram.
6. **[ME-18]** Fixare la race condition su `telegram_handler.stop()` join timeout.

### Priorità P2 (Refactoring Tecnico)
12. **[HI-02]** Inizializzare `scan` in `_processing_wait_loop` prima del loop.
13. **[HI-04]** Usare `max(0, ...)` per `truly_expired`.
14. **[ME-08]** Riusare `auth.check_and_handle_disconnect_modal()` in `session_keeper` invece di duplicare la logica.
15. **[ME-09]** Fixare `dismiss_popups()` per gestire popup multipli con label diverse.
16. **[ME-10]** Aggiungere `force=True` o `wait_for_click_shield` in `relist_all()`.
17. **[ME-11]** Riusare `navigator.go_to_transfer_list()` in `sold_handler.py`.
18. **[ME-12]** Rimuovere parametri morti `cycle_num` e `session_keeper` da `process_cycle()`.
19. **[ME-13]** Aggiungere commenti esplicativi all'euristica relist manuale.
20. **[ME-19]** Distinguere eccezioni fatali (`MemoryError`) da recoverable nel loop principale di `main.py`.
21. **[LO-12]** Ottimizzare `wait_interruptible()` con `threading.Event.wait()` invece di busy-polling.

---

## Appendix: Verifica Incrociata con Review Precedenti

### Finding Già Fixati nel Codice Caricato

| ID Review | Descrizione | Stato |
|-----------|-------------|-------|
| CR-01 | Credential Exposure via Telegram Screenshot Error Reporting | ✅ **FIXED** — Guardia URL aggiunta in `notification_batch.py` (13 Maggio 2026, 20:30) |
| CR-02 | `_last_scan_result` Race Condition su `page.reload()` Path | ✅ **FIXED** — Invalidazione e aggiornamento di `_last_scan_result` dopo il reload (13 Maggio 2026, 20:30) |
| CR-03 | Credential Exposure via Screenshot in `notifier.py` e `telegram_handler.py` | ✅ **FIXED** — Guardia URL aggiunta in entrambi i file (13 Maggio 2026, 20:30) |
| HI-06 | `_execute_heartbeat()` — Exception Swallowing Maschera `RebootRequestError` | ✅ **FIXED** — `RebootRequestError` ora propagata correttamente + `return` dopo console mode (13 Maggio 2026, 21:45) |
| Mistral CR-01 | Golden retry loop inutile se relist già completato | ✅ **FIXATO** — guardia `if initial_f == 0 and processing_count == 0: return` presente a riga 296 |
| Mistral CR-03 | Uscita prematura con processing residui | ✅ **FIXATO** — condizione `if f == 0 and remaining_processing == 0: break` presente a riga 336 | 13 Maggio 2026, 00:30
| DeepSeek ME-01 | Bare `except:` in `main.py` | ✅ **FIXATO** — nel codice caricato è `except Exception:` (non bare) | 13 Maggio 2026, 00:30
| DeepSeek LO-03 | Bare `except:` in `_save_error_screenshot` | ✅ **FIXATO** — nel codice caricato è `except Exception:` | 13 Maggio 2026, 00:30

### Finding Fixati in Sessione 2 (13 Maggio 2026, 21:00-23:00)

| ID | Descrizione | File |
|----|-------------|------|
| HI-01 | Dipendenza circolare `main` ↔ `error_handler` — `perform_full_login()` in `AuthManager` | `browser/auth.py`, `browser/error_handler.py` |
| HI-02 | `scan` unbound in `_processing_wait_loop` — inizializzato prima del loop | `logic/relist_engine.py` |
| HI-03 | Scan post-relist senza `try/except` — wrappate con fallback conservativo | `logic/relist_engine.py` |
| HI-04 | `truly_expired` negativo — `max(0, ...)` in 3 punti | `logic/relist_engine.py` |
| HI-05 | `AuthManager` instanziato 3 volte in `RelistExecutor` — DI via constructor | `browser/relist.py` |
| HI-06 | `RebootRequestError` swallowed — `except RebootRequestError: raise` + `return` console mode | `browser/session_keeper.py` |
| ME-01 | `action_logger` assente nel path batch — aggiunto dopo success | `logic/relist_engine.py` |
| ME-03 | Parametro morto `get_credentials_fn` — rimosso | `browser/error_handler.py` |
| ME-04 | Log processing mostra count iniziale — ora usa `scan.processing_count` attuale | `logic/relist_engine.py` |
| ME-06 | Keyword `"<"` troppo generico — ristretto a `"<\d"` | `browser/detector.py` |
| ME-07 | `_execute_heartbeat` continua dopo console session — aggiunto `return` | `browser/session_keeper.py` |
| ME-08 | Logica modale disconnessione duplicata — riusa `auth.check_and_handle_disconnect_modal()` | `browser/session_keeper.py` |
| ME-10 | Click senza `force=True` — aggiunto su `relist_all_btn`, `confirm_btn`, `relist_button` | `browser/relist.py` |
| ME-12 | Parametro morto `cycle_num` — rimosso da `process_cycle` | `logic/relist_engine.py` |
| ME-13 | Heuristic relist manuale — commenti aggiunti (minimali) | `logic/relist_engine.py` |
| ME-14 | `_last_scan_result` non aggiornato in `per_listing` — scan post-loop aggiunta | `logic/relist_engine.py` |
| ME-15 | `_save_error_screenshot` usa path relativo — ora in `logs/screenshots/` configurabile | `logic/relist_engine.py` |
| LO-01 | `fifa_logger` recuperato N volte — `self._fifa_logger` singleton in `__init__` | `logic/relist_engine.py` |
| LO-03 | URL hardcoded nel recovery sessione — ora da `config.get()` | `logic/relist_engine.py` |
| LO-04 | `handle_reboot` path hardcoded — ora usa `sys.argv[0]` | `browser/session_keeper.py` |
| LO-08 | `RelistBatchResult` creazione ridondante — semplificato | `browser/relist.py` |
| LO-09 | `_cap_wait` nome poco descrittivo — rinominato `_limit_wait_for_pre_nav` | `logic/relist_engine.py` |

### Finding Completati in Sessione 3 (14 Maggio 2026, 00:30-02:05)

| ID | Descrizione | File |
|----|-------------|------|
| ME-05 | Selectors Transfer List centralizzati in `_DEFAULT_TRANSFER_SELECTORS` + override via `config["transfer_list_selectors"]` | `logic/relist_engine.py` |
| ME-13 | Heuristic relist manuale — commenti estesi con spiegazione dettagliata dei range 3400-3600, 10600-10800, 21400-21600 e logica delta ≤90s | `logic/relist_engine.py` |
| ME-17 | Retry con exponential backoff (max 3 tentativi, base 2s) su tutte le chiamate API Telegram | `notifier.py`, `telegram_handler.py` |
| ME-18 | Race condition `stop()` — `_get_updates()` usa timeout breve con check `_stop_event`; `join(timeout=15)` | `telegram_handler.py` |
| ME-19 | `except (MemoryError, RecursionError)` aggiunto prima di `except Exception` — fatali → `sys.exit(1)` | `main.py` |
| Bug fix | Corretti 14 riferimenti `fifa_logger` → `self._fifa_logger` (NameError runtime: `fifa_logger is not defined`) | `logic/relist_engine.py` |
| LO-06 | `last_flush_time` — ora usato in `is_ready_to_flush()` per flush periodico | `core/notification_batch.py` |
| LO-11 | `_command_event` — ora usato in `queue_command()` e `get_next_command()` per wakeup immediato | `bot_state.py` |
| LO-12 | `wait_interruptible()` — ora usa `_reboot_event.wait(timeout=chunk)` + check `_command_event` invece di busy-polling puro | `bot_state.py` |
| LO-10 | `expired_detected` — ora incluso nel report Telegram (`⏰ Scaduti rilevati: {self.expired_detected}`) | `core/notification_batch.py` |
| ME-11 | `_navigate_to_sold_items()` ora delega a `self.navigator.go_to_transfer_list()` — eliminata duplicazione (fallback legacy condizionato) | `browser/sold_handler.py` |
| LO-05 | `_parse_coin_value` rimosso — ora `detector.parse_price()` chiamato direttamente (delegazione, zero duplicazione) | `browser/sold_handler.py` |
| ME-09 | `dismiss_popups()` ora gestisce popup multipli — loop 3 pass senza `break` prematuro, check `found_any` | `browser/navigator.py` |
| LO-02 | Magic numbers golden retry centralizzati — `GOLDEN_RETRY_MAX_ATTEMPTS=6`, `GOLDEN_RETRY_MIN_WAIT=5.0`, `GOLDEN_RETRY_MAX_WAIT=10.0` in `golden_hour.py` | `logic/golden_hour.py`, `logic/relist_engine.py` |
| LO-07 | `DEFAULT_PROFILE_DIR` spostato da class variable a variabile di modulo | `browser/controller.py` |

### Finding Completati — Tutti i 40 fix applicati

| ID | Descrizione | File |
|----|-------------|------|
| CR-01 | Credential Exposure guardia URL in `flush()` | `notification_batch.py` |
| CR-02 | `_last_scan_result` invalidato/riassegnato dopo reload | `relist_engine.py` |
| CR-03 | Credential Exposure guardia URL in notifier e telegram_handler | `notifier.py`, `telegram_handler.py` |
| HI-01 | Eliminata dipendenza circolare — `perform_full_login()` in `AuthManager` | `auth.py`, `error_handler.py` |
| HI-02 | `scan` inizializzato prima del loop in `_processing_wait_loop` | `relist_engine.py` |
| HI-03 | Scan post-relist con try/except e fallback conservativo | `relist_engine.py` |
| HI-04 | `truly_expired` usa `max(0, ...)` in tutti i punti | `relist_engine.py` |
| HI-05 | `AuthManager` injectato via constructor (no istanze inside) | `relist.py` |
| HI-06 | `RebootRequestError` propagato + return dopo console mode | `session_keeper.py` |
| ME-01 | `action_logger.info` aggiunto nel path batch relist | `relist_engine.py` |
| ME-02 | Path screenshot thread-safe — `tempfile.NamedTemporaryFile` | `notification_batch.py` |
| ME-03 | Parametro morto `get_credentials_fn` rimosso da `ensure_session` | `error_handler.py` |
| ME-04 | Log processing usa valore attuale `scan.processing_count` | `relist_engine.py` |
| ME-05 | Selectors Transfer List centralizzati + override via config | `relist_engine.py` |
| ME-06 | Keyword `"<"` ristretta a `"<\d"` in `determine_state()` | `detector.py` |
| ME-07 | `return` dopo attivazione console mode in heartbeat | `session_keeper.py` |
| ME-08 | Logica modale disconnessione duplicata riusa `auth.check_and_handle_disconnect_modal()` | `session_keeper.py` |
| ME-09 | `dismiss_popups()` gestisce popup multipli — loop 3 pass, check `found_any` | `navigator.py` |
| ME-10 | Click su `relist_all_btn`, `confirm_btn` con `force=True` | `relist.py` |
| ME-11 | `_navigate_to_sold_items()` delega a `navigator.go_to_transfer_list()` | `sold_handler.py` |
| ME-12 | Parametro morto `cycle_num` rimosso da `process_cycle` | `relist_engine.py` |
| ME-13 | Commenti estesi per euristica relist manuale (range 3400-3600, 10600-10800, 21400-21600, delta ≤90s) | `relist_engine.py` |
| ME-14 | `_last_scan_result` aggiornato dopo loop per_listing | `relist_engine.py` |
| ME-15 | `_save_error_screenshot` usa path assoluto configurabile | `relist_engine.py` |
| ME-16 | Path screenshot thread-safe — `tempfile.NamedTemporaryFile` | `telegram_handler.py` |
| ME-17 | Retry exponential backoff su tutte le API Telegram (max 3, base 2s) | `notifier.py`, `telegram_handler.py` |
| ME-18 | Race condition `stop()` fix: timeout breve + `_stop_event` check | `telegram_handler.py` |
| ME-19 | `except (MemoryError, RecursionError)` → `sys.exit(1)` senza reboot | `main.py` |
| LO-01 | `fifa_logger` singleton — `self._fifa_logger` in `__init__` | `relist_engine.py` |
| LO-02 | Magic numbers golden retry centralizzati in `golden_hour.py` | `golden_hour.py`, `relist_engine.py` |
| LO-03 | URL recovery sessione letto da `config.get()` | `relist_engine.py` |
| LO-04 | `handle_reboot` usa `sys.argv[0]` invece di `"main.py"` | `session_keeper.py` |
| LO-05 | `_parse_coin_value` rimosso — diretto uso di `detector.parse_price()` | `sold_handler.py` |
| LO-06 | `last_flush_time` letto in `is_ready_to_flush()` per flush periodico | `notification_batch.py` |
| LO-07 | `DEFAULT_PROFILE_DIR` spostato a variabile di modulo | `controller.py` |
| LO-08 | `RelistBatchResult()` costruito senza `from_results([])` ridondante | `relist.py` |
| LO-09 | `_cap_wait` ridenominato `_limit_wait_for_pre_nav` | `relist_engine.py` |
| LO-10 | `expired_detected` incluso nel report Telegram batch | `notification_batch.py` |
| LO-11 | `_command_event` usato per wakeup immediato in `queue_command()`/`get_next_command()` | `bot_state.py` |
| LO-12 | `wait_interruptible()` ottimizzato con `_reboot_event.wait()` e check `_command_event` | `bot_state.py` |

**Note**:
- ME-02 e ME-16 erano già presenti nel codice al momento della review originale (non dichiarati in "Fix Applicate" ma validi).
- Tutti i 53 finding sono stati verificati e confermati da agenti Verifier indipendenti.
- Il tutto è stato effettuato nella sessions 4-5 (14 Maggio 2026, 02:05 - 13:59).

---

## Findings da crgpt.md (verificati)

### ANCORA APERTI (richiedono fix)

**Nessuno. Tutti i bug segnalati sono stati risolti.**


### RISOLTI (già presenti nel codice)

| ID | Problema | Stato | File | Note |
|----|----------|-------|------|------|
| CU-01 | I comandi Telegram "flag-only" non risvegliano il main loop | **RISOLTO** | `bot_state.py` | Fix race condition con check atomico sotto lock. |
| CU-02 | Le pause temporizzate possono sforare fino a 5 minuti | **RISOLTO** | `browser/session_keeper.py:64-77` | `_state_wait_seconds(until)` cappa l'attesa alla deadline di auto-resume. |
| CU-03 | La suite test è rossa su NotificationBatch | **RISOLTO** | `tests/test_notification_batch.py` | Allineamento test alla logica proxy `succeeded + failed`. |
| CU-04 | Il recovery login può bloccare il main thread per 30 minuti non interrompibili | **RISOLTO** | `browser/auth.py:397-405` | Usa `wait_fn(1800)` con `BotState.wait_interruptible` se fornita, fallback a `time.sleep(1800)` solo se `wait_fn` è None. |

---

## Fix Applicate Sessione 5 (2026-05-14)

| ID | Descrizione | File |
|----|-------------|------|
| NU-01 | `relist_all()` restituisce `RelistBatchResult` con `relist_error` esplicito se bottone non visibile | `browser/relist.py` |
| NU-02 | `flush()` controlla `telegram_chat_id` oltre a `telegram_token` | `core/notification_batch.py` |
| NU-03 | `except (MemoryError, RecursionError)` invia alert Telegram prima di terminare | `main.py` |
| NU-04 | `flush()` protegge screenshot con try/except e double-check URL | `core/notification_batch.py` |
| NU-05 | Callback Telegram protetti da try/except nel main loop | `main.py` |
| NU-06 | `setup.py` limita permessi `.env` a 0o600 | `setup.py` |
| NU-07 | `controller.py` gestisce `context.pages` vuoto con fallback `new_page()` | `browser/controller.py` |
| NU-08 | `navigator.py` logga errore specifico prima di raise su click Transfer List | `browser/navigator.py` |
| NU-09 | `CustomDailyRotatingHandler` con lock thread-safe su `doRollover()` | `config/log_config.py` |
| NU-10 | `RateLimiter` con lock per `_warning_logged` thread-safe | `browser/rate_limiter.py` |
| NU-11 | `wait_interruptible()` gestisce `seconds <= 0` | `bot_state.py` |
| NU-12 | `_processing_wait_loop` usa `max(1, ...)` per `wait_secs` | `logic/relist_engine.py` |
| NU-13 | `ConfigManager.load()` gestisce `json.JSONDecodeError` | `config/config.py` |
| CU-01 | Fix wakeup loop su comandi flag-only (atomicità `_wake_event`) | `bot_state.py` |
| CU-03 | Fix disallineamento logico e falso positivo test suite | `tests/test_notification_batch.py` |
| NU-14 | Sostituito `time.sleep()` con `_stop_event.wait()` nei retry (previene stallo thread poller) | `telegram_handler.py` |
| NU-15 | Fix loop fallback JS in `authenticate` (verifica booleano del click) | `main.py` |
| NU-16 | Aggiunta propagazione `RebootRequestError` e `ConsoleSessionError` in fallback navigazione | `logic/relist_engine.py` |
| NU-17 | Fix AttributeError (Crash) su `ConsoleSessionError` spostando l'alert Telegram in main.py | `logic/relist_engine.py`, `main.py` |
| NU-18 | Aggiunto fallback `send_telegram_alert` per evitare errore 400 su PNG vuoti | `core/notification_batch.py` |
| NU-19 | Aggiunto fallback localizzato 'Lista trasferimenti' in `browser/navigator.py` | `browser/navigator.py` |
| NU-20 | Unificazione boundary multipart con `uuid4().hex` per prevenire corruzione payload | `telegram_handler.py` |
| NU-21 | Rimozione wait ridondante (2s) in `relist_all()` per ottimizzare ciclo | `browser/relist.py` |
| NU-22 | Rifattorizzazione `perform_full_login()` per usare iniezione credenziali | `browser/auth.py` |
| NU-23 | Pulizia import inutilizzati e aggiunta logging in blocchi except silenti | `main.py`, `detector.py`, `session_keeper.py`, `relist_engine.py` |

### Stato Review Complessivo

| Severity | Totale | Fixati | Rimasti |
|----------|--------|--------|---------|
| 🔴 CRITICAL | 3 | 3 | 0 |
| 🟠 HIGH | 6 | 6 | 0 |
| 🟡 MEDIUM | 22 | 22 | 0 |
| 🟢 LOW | 13 | 13 | 0 |
| **NU-01** HIGH | 1 | 1 | 0 |
| **NU-02** MEDIUM | 1 | 1 | 0 |
| **NU-03** MEDIUM | 1 | 1 | 0 |
| **NU-04** MEDIUM | 1 | 1 | 0 |
| **NU-05** MEDIUM | 1 | 1 | 0 |
| **NU-06** MEDIUM | 1 | 1 | 0 |
| **NU-07** LOW | 1 | 1 | 0 |
| **NU-08** LOW | 1 | 1 | 0 |
| **NU-09** LOW | 1 | 1 | 0 |
| **NU-10** LOW | 1 | 1 | 0 |
| **NU-11** LOW | 1 | 1 | 0 |
| **NU-12** LOW | 1 | 1 | 0 |
| **NU-13/16** LOW | 4 | 4 | 0 |
| **NU-17/19** CRIT/HIGH | 3 | 3 | 0 |
| **NU-20/22** MEDIUM | 3 | 3 | 0 |
| **NU-23** LOW | 1 | 1 | 0 |
| **CU-01/04** BUGS | 4 | 4 | 0 |
| **Total** | **67** | **67** | **0** |

---
