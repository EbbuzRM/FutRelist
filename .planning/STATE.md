status: production
last_updated: "2026-04-27T18:50:00.000Z"
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
:08:XX → Pre-Nav Guard: aspetta fino a :09:00 (nessuna interazione browser)
:09:00 → Naviga verso Transfer List (~10-15s)
:09:xx → [SCANSIONE] — raccoglie listing scaduti
:09:xx → Golden Sync: aspetta fino a :10:00 (con dati già pronti)
:10:00 → Relist diretto (senza ri-scansionare) ✓


## 5. Current Activity & Known Issues
- **Recent (29 Apr):** Fix "Scan-Spam Post-Relist": `_compute_next_wait` non ritorna più 10s ciecamente durante golden window. Polling rapido solo se ci sono ancora expired/processing. Dopo relist con 0 expired, calcola wait verso la prossima golden pre-nav.
- **Recent (29 Apr):** Fix "Processing Items": se TUTTI gli expired sono in realtà PROCESSING, il bot salta il tentativo di relist (bottone non visibile) e delega al `_golden_retry_loop` con attesa 8-15s per la transizione EA.
- **Recent (29 Apr):** Fix "Golden Retry Migliorato": loop con max 6 tentativi, attesa più lunga (8-15s vs 5-10s), skip relist se item ancora in Processing, exit immediata dopo successo.
- **Recent (29 Apr):** `process_cycle` ora riscansiona DOPO il relist per dare a `_compute_next_wait` dati freschi (evita il loop 10s con expired_count stale).
- **Recent (28 Apr):** Fix "Flusso Golden Ristrutturato": scansione spostata a :09 (PRIMA del Golden Sync wait). Il bot ora naviga a :09, scansiona a :09, aspetta fino a :10:00, e rilista direttamente senza ri-scansionare.
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
- **Total:** 674 tests passing.
- **Coverage:** 132 unit tests + 526 golden timeline simulations.