# AGENTS.md — FIFA 26 Auto-Relist Bot

Questo file contiene regole e contesto per qualsiasi AI agent che lavora su questo progetto.

## 📋 Panoramica del Progetto

Bot Python che automatizza il relisting dei giocatori sulla Web App di FIFA Ultimate Team usando Playwright (browser automation).

**Stack:** Python 3.9+, Playwright, python-dotenv, rich, tenacity, python-telegram-bot
**Struttura:**
- `main.py` — Entry point, orchestratore principale (loop, reboot, supervisor)
- `logic/` — Business logic: `relist_engine.py` (ciclo operativo) e `golden_hour.py` (timing constants)
- `browser/` — Controller, auth, navigator, detector, relist, rate_limiter, error_handler, session_keeper, sold_handler
- `config/` — ConfigManager con typed dataclasses e validazione, log_config
- `models/` — Data model: `listing.py`, `relist_result.py`, `sold_result.py`, `action_log.py`
- `core/` — Utility core come `notification_batch.py`
- `bot_state.py` — Singleton per la gestione dello stato globale e statistiche
- `telegram_handler.py` — Gestore dei comandi Telegram in arrivo
- `notifier.py` — Notifiche Telegram in uscita (messaggi + screenshot)
- `tests/` — Unit tests con pytest

## 🏆 REGOLA CRITICA: Golden Hours Logic (NON MODIFICARE)

La logica delle **Golden Hours** è il cuore del bot. **NON deve mai essere modificata o rimossa** senza esplicita approvazione dell'utente.

### Golden Hours: 16:10, 17:10, 18:10
- Il relist durante la fascia **15:10 → 18:15** è consentito **SOLO** alle :10 precise delle ore 16, 17, 18
- Finestra di tolleranza: **:09 → :11** (pre-nav + relist + ritardatari)
- **Pre-nav**: automatica alle **:09:00** prima di ogni golden (naviga per essere pronto al :10)
- **Golden Retry**: loop di tentativi extra per gli oggetti in stato "Processing" durante la finestra golden
- **Hold window**: tutto il resto della fascia 15:10→18:15 è HOLD — gli scaduti aspettano la prossima golden
- **Fuori fascia golden** (prima delle 15:10 e dopo le 18:15): relist normale (immediato)

### Funzioni chiave (in `logic/golden_hour.py`):
- `get_next_golden_hour(now)` — calcola la prossima golden (16:10/17:10/18:10)
- `is_in_golden_period(now)` — True se siamo nella fascia 15:10→18:15
- `is_in_hold_window(now)` — True se siamo in hold (golden period ma NON nel momento :09-:11)

### Timeline operativa:
| Fascia | Comportamento |
|--------|---------------|
| Prima 15:10 | Relist normale (subito) |
| 15:10 → 16:07 | HOLD → attesa heartbeat |
| **16:08** | HOLD — **NON navigare**, aspetta heartbeat fino a :09:00 |
| **16:09:00** | **PRE-NAV**: naviga alla Transfer List |
| **16:09:xx** | Transfer List caricata — attesa precisa fino a :10:00 |
| **16:10:00** | RELIST TASSATIVO |
| 16:10-16:11 | Golden Retry (ritardatari / Processing) |
| 16:12 → 17:08 | HOLD → attesa heartbeat |
| **17:09:00** | PRE-NAV: naviga alla Transfer List |
| **17:10:00** | RELIST TASSATIVO + Golden Retry |
| 17:12 → 18:08 | HOLD → attesa heartbeat |
| **18:09:00** | PRE-NAV: naviga alla Transfer List |
| **18:10:00** | RELIST TASSATIVO + Golden Retry |
| Dopo 18:15 | Relist normale (subito) |

### 🕐 REGOLA CRITICA: Timing esatto del Pre-Nav (NON MODIFICARE)

> ⛔ **Questa logica NON deve essere modificata senza esplicita istruzione dell'utente.**

Il pre-nav funziona in **due fasi distinte** implementate in `logic/relist_engine.py → process_cycle()`:

**Fase 1 — Pre-Nav Guard (PRIMA della navigazione):**
- Al minuto `:08` durante la golden period, il bot **NON naviga**.
- Aspetta (via `wait_interruptible`) fino a `:09:00` senza toccare il browser.
- Implementato come guard all'inizio di `process_cycle`, prima di `_navigate_with_retry()`.

**Fase 2 — Precision Wait (DOPO la navigazione):**
- Dopo aver navigato al `:09`, la Transfer List è già caricata.
- Il bot aspetta precisamente fino alle `:10:00` prima di scansionare e rilistare.
- Implementato dopo `_navigate_with_retry()`, solo se `now.minute == 9`.

**Perché questa separazione è fondamentale:**
- Prima del fix (bug storico): il bot navigava all'`:08` e aspettava 87s sulla Transfer List → relist all'`:10` ma con margine ridotto e timing instabile.
- Con questa logica: navigazione garantita al `:09:00`, pagina caricata in ~10-15s, attesa precisa di ~45s → relist **esattamente** alle `:10:00`.

**Regole ferree:**
1. Al minuto **:08** → nessuna navigazione, solo heartbeat/wait
2. Al minuto **:09** → naviga, poi aspetta `:10:00` prima di scansionare
3. Al minuto **:10/:11** → già nella golden window, procedi subito
4. L'heuristica di "relist manuale rilevato" **NON deve attivarsi** se il bot stesso ha fatto il relist da poco (entro 3 minuti)
5. Se il relist viene eseguito dal bot, `bot_state.update_stats(relisted=...)` aggiorna il timestamp di ultimo rilist bot

## ⚠️ REGOLA CRITICA: Relist Normale (NON DIMENTICARE)

Il relist **fuori dalla fascia golden** (prima delle 15:10 e dopo le 18:15) deve essere **SEMPRE immediato**.

### Struttura obbligatoria (in `logic/relist_engine.py`)
La logica di decisione relist DEVE gestire sempre il fallback normale:

```python
if scan.expired_count > 0:
    in_hold = is_in_hold_window(datetime.now())
    force_relist = self.bot_state.consume_force_relist()
    
    # Minuto :09 posticipa a :10 (Golden window)
    if is_in_golden_window(now_relist) and now_relist.minute == 9:
        return 0, 0, seconds_to_10

    if in_hold and not force_relist:
        # HOLD: aspetta la prossima golden
        ...
    else:
        # RELIST NORMALE O FORCE RELIST O GOLDEN WINDOW (:10-:11)
        Questo ramo DEVE esistere SEMPRE!
        fifa_logger.info(f"Trovati {scan.expired_count} oggetti scaduti. Rilisto...")
        # ... esegui il relist ...
```

### 🚨 BUG STORICO (NON RIPETERE)
Non dimenticare mai il ramo `else` per il rilist quando `in_hold` è `False`. Se gli oggetti rimangono scaduti senza azione fuori dalla fascia golden, il bot è rotto.

## 📐 Architettura

### Orchestrazione (main.py)
1. Inizializza `BotState`, `ConfigManager`, `BrowserController`.
2. Loop esterno gestisce reboot e sessioni console.
3. Loop interno delega a `RelistEngine.process_cycle`.
4. `SessionKeeper` monitora la salute della sessione e gestisce gli heartbeat di attesa.

### Business Logic (logic/)
- `RelistEngine`: Gestisce la scansione, l'euristica manuale, la decisione di rilist e la doppia verifica (due round di rilist se necessario).
- `GoldenHour`: Gestisce tutti i calcoli temporali e le costanti della finestra golden.

### Stato e Notifiche
- `BotState`: Singleton che tiene traccia di statistiche, comandi Telegram in coda (es. `/force`, `/screenshot`, `/del_sold`) e stato del bot.
- `NotificationBatch`: Accumula i risultati di più cicli per evitare spam su Telegram, flushando ogni 5 minuti o se ci sono stati rilist/errori significativi.

### Moduli browser/
- `controller.py` — Playwright wrapper con profilo persistente (no 2FA ripetuta)
- `auth.py` — Login EA a 2 step (email→NEXT→password→Sign in), gestione 2FA, detection sessione console
- `navigator.py` — Navigazione Home → Transfers → Transfer List con popup dismissal
- `detector.py` — Scansione DOM per listing (stato, prezzi, tempo rimanente)
- `relist.py` — Esecuzione relist (single + all), error detection post-relist, session check
- `rate_limiter.py` — Delay randomico 2-5s tra azioni (anti-detection)
- `error_handler.py` — Session expiry detection e recovery

### Config (config/config.json)
- `browser.headless` — true/false
- `listing_defaults.duration` — 1h, 3h, 6h, 12h, 24h, 3d
- `listing_defaults.relist_mode` — "all" o "per_listing"
- `listing_defaults.price_adjustment_type` — "percentage" o "fixed"
- `listing_defaults.price_adjustment_value` — valore sconto (es. -5.0 = -5%)
- `listing_defaults.min_price` — prezzo minimo (default 200)
- `listing_defaults.max_price` — prezzo massimo (default 15_000_000)
- `scan_interval_seconds` — intervallo check (default 60)
- `rate_limiting.min_delay_ms` / `max_delay_ms` — range delay anti-bot
- `notifications.telegram_token` / `telegram_chat_id` — notifiche Telegram

## 🛠 Regole per gli Agent

1. **NON modificare la golden hour logic** (costanti in `logic/golden_hour.py`) senza approvazione
2. **NON committare** `.env`, `config/config.json`, `storage/`, `logs/`, `.planning/`
3. **Testare** le modifiche con `pytest` prima di proporre cambiamenti
4. **Leggere** i log in `logs/app.log` (generale) e `logs/actions.jsonl` (azioni specifiche)
5. **Mantenere** il rate limiting (2-5s) tra le azioni Playwright
6. **Usare** `get_by_role()` per i selettori — più robusto ai cambi CSS di EA
7. **Preservare** la compatibilità con italiano e inglese (UI EA bilingue)
8. **Gestire sempre** gli item in stato `Processing` (limbo EA post-scadenza)
9. **Verificare** sempre la presenza di sessione console attiva per evitare ban
