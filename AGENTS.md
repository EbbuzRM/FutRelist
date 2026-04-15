# AGENTS.md — FIFA 26 Auto-Relist Bot

Questo file contiene regole e contesto per qualsiasi AI agent che lavora su questo progetto.

## 📋 Panoramica del Progetto

Bot Python che automatizza il relisting dei giocatori sulla Web App di FIFA Ultimate Team usando Playwright (browser automation).

**Stack:** Python 3.9+, Playwright, python-dotenv, rich, tenacity
**Struttura:**
- `main.py` — Entry point, loop principale, autenticazione, golden hour logic
- `browser/` — Controller, auth, navigator, detector, relist, rate_limiter, error_handler
- `config/` — ConfigManager con typed dataclasses e validazione
- `models/` — Data model: ListingState, PlayerListing, ListingScanResult, RelistResult
- `notifier.py` — Notifiche Telegram (messaggi + screenshot)
- `tests/` — Unit tests con pytest

## 🏆 REGOLA CRITICA: Golden Hours Logic (NON MODIFICARE)

La logica delle **Golden Hours** è il cuore del bot. **NON deve mai essere modificata o rimossa** senza esplicita approvazione dell'utente.

### Golden Hours: 16:10, 17:10, 18:10
- Il relist durante la fascia **15:10 → 18:15** è consentito **SOLO** alle :10 precise delle ore 16, 17, 18
- Finestra di tolleranza: **:09 → :11** (pre-nav + relist + ritardatari)
- **Pre-nav**: automatica alle **:09:30** prima di ogni golden (naviga per essere pronto al :10)
- **Hold window**: tutto il resto della fascia 15:10→18:15 è HOLD — gli scaduti aspettano la prossima golden
- **Fuori fascia golden** (prima delle 15:10 e dopo le 18:15): relist normale (immediato)

### Funzioni chiave (NON rimuovere):
- `get_next_golden_hour(now)` — calcola la prossima golden (16:10/17:10/18:10)
- `is_in_golden_period(now)` — True se siamo nella fascia 15:10→18:15
- `is_in_hold_window(now)` — True se siamo in hold (golden period ma NON nel momento :09-:11)

### Timeline operativa:
| Fascia | Comportamento |
|--------|---------------|
| Prima 15:10 | Relist normale (subito) |
| 15:10 → 16:09 | HOLD → pre-nav 16:09:30 → relist 16:10 |
| 16:10-16:11 | RELIST TASSATIVO + ritardatari |
| 16:12 → 17:08 | HOLD → pre-nav 17:09:30 → relist 17:10 |
| 17:10-17:11 | RELIST TASSATIVO + ritardatari |
| 17:12 → 18:08 | HOLD → pre-nav 18:09:30 → relist 18:10 |
| 18:10-18:11 | RELIST TASSATIVO + ritardatari |
| Dopo 18:15 | Relist normale (subito) |

### 🕐 REGOLA CRITICA: Relist SOLO al minuto 10
Durante la fascia golden, il relist deve avvenire **ESATTAMENTE al minuto 10** (16:10, 17:10, 18:10), **MAI prima**.

**Regole ferree:**
1. Se siamo nella golden window (:09-:11) ma i minuti sono **:09**, il relist **DEVE essere posticipato** - il bot deve attendere fino al minuto 10
2. L'heuristica di "relist manuale rilevato" **NON deve attivarsi** se il bot stesso ha fatto il relist da poco (entro 3 minuti dal relist recente)
3. Se il relist viene eseguito dal bot, impostare un flag `last_relisted_by_bot` con timestamp - questo flag disattiva l'heuristica di rilevamento relist manuale

Questo impede che il bot faccia relist alle 16:09 (quando dovrebbe solo navigare/prepararsi) e poi l'heuristica pensi erroneamente che qualcuno ha già agito manualmente.

## ⚠️ REGOLA CRITICA: Relist Normale (NON DIMENTICARE)

Il relist **fuori dalla fascia golden** (prima delle 15:10 e dopo le 18:15) deve essere **SEMPRE immediato**.

### Struttura obbligatoria per il blocco relist
Quando modifichi la logica di relist in `main.py`, la struttura DEVE avere SEMPRE un ramo `else` finale:

```python
if scan.expired_count > 0:
    in_hold = is_in_hold_window(datetime.now())
    force_relist = bot_state.consume_force_relist()
    if in_hold and not force_relist:
        # HOLD: aspetta la prossima golden
        ...
    else:
        # RELIST NORMALE (fuori hold) O FORCE RELIST
        # Questo ramo DEVE esistere SEMPRE!
        if force_relist:
            logger.info("[Telegram] Force relist — bypass hold window")
        fifa_logger.info(f"Trovati {scan.expired_count} oggetti scaduti. Rilisto...")
        # ... esegui il relist ...
```

### 🚨 BUG STORICO (NON RIPETERE)
Un bug critico ha reso il relist normale **completamente morto**: la struttura `if/elif` senza `else` faceva sì che quando `in_hold=False` e `force_relist=False`, il bot vedesse gli scaduti ma **non facesse nulla**. Gli oggetti rimanevano scaduti senza essere relistati.

### Regola d'oro
**OGNI volta che aggiungi una condizione speciale (hold, force, ecc.), il ramo `else` per il relist normale DEVE rimanere.** Se trasformi un `else` in `elif`, devi aggiungere un nuovo `else` alla fine.

## 📐 Architettura

### Flusso principale (main.py)
1. Load config → Start browser → Authenticate → Navigate to Transfer List
2. Loop continuo:
   - `ensure_session()` — verifica/ripristina sessione
   - Golden sync — attende pre-nav se in fascia golden
   - `navigate_with_retry()` — va alla Transfer List
   - `detector.scan_listings()` — legge gli elementi dal DOM
   - Se scaduti e NON in hold → `executor.relist_all()` o `relist_single()`
   - Calcolo wait dinamico basato sui listing attivi
   - Notifica Telegram batch (ogni 5 min o 5+ oggetti)
3. Ctrl+C → stop browser

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

1. **NON modificare la golden hour logic** senza approvazione esplicita
2. **NON committare** `.env`, `config/config.json`, `storage/`, `logs/`, `.planning/`
3. **Testare** le modifiche con `pytest` prima di proporre cambiamenti
4. **Leggere** i log in `logs/app.log` e `logs/actions.jsonl` per debug
5. **Mantenere** il rate limiting (2-5s) — non ridurlo senza approvazione
6. **Usare** `get_by_role()` per i selettori — più robusto ai cambi CSS di EA
7. **Preservare** la compatibilità con italiano e inglese (UI EA bilingue)
8. **OGNI blocco relist deve avere un `else` finale** per il relist normale — mai lasciare `if/elif` senza fallback
