# FIFA 26 Auto-Relist Bot

Automated relisting bot for the FIFA 26 WebApp market, synchronized to Golden Hours for maximum sell-through.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Tests](https://img.shields.io/badge/tests-740%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-production-success)

---

FIFA 26 Auto-Relist Bot automatizza il relisting degli oggetti scaduti sul mercato trasferimenti della WebApp EA. È progettato per operare durante le **Golden Hours** (17:10 e 18:10), i due minuti giornalieri in cui si concentra la maggior parte delle transazioni. Il bot include protezioni anti-ban, heartbeat automatico, notifiche Telegram e un sistema di verifica in due fasi per garantire che ogni oggetto venda al momento giusto.

---

## Features

- **Golden Hour sync** — relist tassativo sincronizzato alle :10 di ogni ora (17:10 e 18:10)
- **HOLD window intelligente** — dalle 16:10 alle 18:15 gli oggetti scaduti aspettano la prossima Golden Hour invece di essere rilistati subito
- **Two-Phase Verification** — dopo il relist, riscansiona e ritenta eventuali residui
- **Telegram control** — 11 comandi per monitorare e controllare il bot da remoto
- **Rate limiting configurabile** — tre profili di velocità (Sicuro, Bilanciato, Veloce)
- **Price adjustment** — modifica percentuale del prezzo a ogni relist
- **Heartbeat automatico** — mantiene la sessione attiva con click sulla tab Transfers ogni 2.5-5 min
- **Stale page detection** — se il bot rileva timer congelati (sessione scaduta), ricarica la pagina automaticamente
- **Error screenshots** — su errori critici, il bot invia screenshot per diagnostica via Telegram
- **Profilo browser persistente** — login salvato, nessuna richiesta 2FA a ogni avvio

---

## Quick Start

### Setup automatico (consigliato)

Il modo più rapido per iniziare. Lo script `setup.py` guida passo passo e configura tutto in automatico.

| Piattaforma | Comando |
|:---|---|
| **Windows** | Doppio click su `setup.bat` |
| **Linux / Mac** | `bash setup.sh` nel terminale |

Lo script esegue automaticamente:
- Installa le dipendenze pip da `requirements.txt`
- Installa Chromium per Playwright
- Chiede interattivamente email FIFA, password, Telegram token e chat ID
- Genera il file `.env` con le credenziali
- Genera `config/config.json` con le configurazioni di default

Al termine, avvia il bot con:

```bash
python main.py
```

### Setup manuale

Se preferisci configurare tutto manualmente:

```bash
pip install -r requirements.txt
playwright install chromium
# Crea .env con FIFA_EMAIL, FIFA_PASSWORD, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
# Configura config/config.json (rate limiting, prezzi, notifiche)
python main.py
```

Il bot avvia Chromium, effettua il login e inizia a monitorare la Transfer List. In assenza di configurazioni Telegram, puoi comunque seguire i log su terminale.

---

## Golden Hours Logic

Questa è la logica centrale del bot. Il mercato FUT ha picchi di traffico **esattamente alle 17:10 e 18:10** ogni giorno. Il bot sincronizza i relist su questi slot per massimizzare la visibilità.

### Costanti attuali (maggio 2026)

| Parametro | Valore |
|---|---|
| Golden Hours attive | **17:10**, **18:10** |
| Golden minute | `:10` |
| Pre-Nav minute | `:09` |
| Golden window | `:09` → `:11` |
| HOLD period start | `16:10` |
| HOLD period end | `18:15` |

> **Nota**: La Golden Hour delle 16:10 è stata rimossa. L'orario 16:10 è ora solo l'inizio del periodo HOLD.

### Timeline operativa

| Orario | Comportamento |
|---|---|
| Prima delle 16:10 | Relist istantaneo — ogni oggetto scaduto viene subito rilistato |
| 16:10 → 17:08 | **HOLD** — nessun relist. Gli scaduti accumulano in attesa della finestra 17:09-17:11 |
| 17:08 | **Pre-Nav Guard** — preparazione alla navigazione |
| 17:09 | Navigazione verso Transfer List |
| 17:10 → 17:11 | **Relist tassativo** — tutti gli scaduti vengono rilistati con golden retry loop |
| 17:12 → 18:08 | **HOLD** — attesa della prossima finestra |
| 18:08 | **Pre-Nav Guard** — preparazione |
| 18:09 | Navigazione verso Transfer List |
| 18:10 → 18:11 | **Relist tassativo** — secondo e ultimo picco |
| Dopo 18:15 | Relist istantaneo — si torna al comportamento normale |

### Protocollo di verifica (Two-Phase Verification)

1. **Relist** → attendi 5 secondi → **scansiona** la Transfer List
2. Se restano oggetti con stato `Expired` (non in `Processing`): **secondo relist** → attendi 3 secondi → **scansiona final**
3. Se restano oggetti in `Processing` (limbo EA): il **golden retry loop** continua con attesa 5-10s (max 6 tentativi) durante la finestra

### Processing Items fuori Golden Window

Fuori dalla finestra Golden, gli oggetti in stato `Processing` ricevono fino a **15 tentativi** con attesa 30-60s e timeout totale di **5 minuti** prima di essere abbandonati al ciclo successivo.

---

## Telegram Commands

Configura `notifications.telegram_token` e `notifications.telegram_chat_id` in `config.json` per abilitare il controllo remoto.

| Comando | Azione |
|---|---|
| `/status` | Stato attuale, modalità (normale/pausa/console), statistiche di sessione |
| `/pause [ore]` | Sospende la scansione. Polling ogni 5 minuti. Opzionale: specifica ore |
| `/resume` | Riprende le operazioni immediatamente |
| `/console [ore]` | Deep sleep — zero interazione con la WebApp. Opzionale: specifica ore |
| `/online` | Disattiva la modalità console e torna al loop normale |
| `/force_relist` | Forza un relist immediato, bypassando la HOLD window |
| `/screenshot` | Invia uno screenshot live della WebApp |
| `/del_sold` | Cancella gli oggetti venduti e raccoglie i crediti |
| `/logs [N]` | Mostra le ultime N righe di `app.log` (max 30) |
| `/reboot` | Riavvio completo del bot. Il browser viene chiuso e il processo Python sostituito |
| `/help` | Mostra l'elenco completo dei comandi disponibili |

Tutti i comandi funzionano mentre il bot è in attesa — non serve riavviarlo.

---

## Configuration

### Rate Limiting Profiles

Il ritardo tra le azioni è randomico all'interno del range configurato, per simulare comportamento umano.

| Profilo | Min (ms) | Max (ms) | Quando usarlo |
|:---|---|---:|---|
| 🟢 Sicuro | 1800 | 3500 | Uso 24/7, massima sicurezza |
| 🟡 Bilanciato | 1200 | 2800 | **Default** — rapporto velocità/sicurezza ottimale |
| 🔴 Veloce | 800 | 1800 | Solo durante le Golden Hours |

Hard limit assoluto: **800ms**. Il bot non accetta valori inferiori.

### Config Parameters (`config.json`)

```json
{
  "browser": {
    "headless": false,
    "slow_mo": 500
  },
  "listing_defaults": {
    "relist_mode": "all",
    "duration": "1h",
    "price_adjustment_value": 0.0,
    "min_price": 200
  },
  "rate_limiting": {
    "min_delay_ms": 1200,
    "max_delay_ms": 2800
  },
  "notifications": {
    "telegram_token": "",
    "telegram_chat_id": ""
  }
}
```

| Chiave | Descrizione |
|---|---|
| `browser.headless` | `false` = browser visibile, `true` = esecuzione in background |
| `listing_defaults.price_adjustment_value` | Riduzione percentuale prezzo a ogni relist (es. `-5.0` = -5%) |
| `listing_defaults.min_price` | Prezzo minimo invalicabile |
| `rate_limiting.min_delay_ms` | Ritardo minimo tra azioni (ms) |
| `rate_limiting.max_delay_ms` | Ritardo massimo tra azioni (ms) |
| `listing_defaults.max_price` | Prezzo massimo invalicabile (default: 15.000.000) |
| `scan_interval_seconds` | Intervallo base di scansione in secondi |

---

## Anti-Ban & Reliability

- **Stealth polling**: 300s durante pausa/console, ma risposta immediata ai comandi Telegram
- **Stale page detection**: se ≥10 cicli rapidi senza expired trovati, forza `page.reload()` per dati freschi
- **Rate limiting randomico**: range configurabile, mai ritardi fissi
- **Heartbeat via Transfers**: click sulla tab Transfers ogni 2.5-5 minuti, non su pulsanti distruttivi
- **Click-shield protection**: uso di `wait_for_function()` per attendere che gli elementi siano interagibili
- **Automatic error screenshots**: su errori critici, il bot cattura screenshot e li invia su Telegram
- **Reboot via os.execv**: `/reboot` sostituisce completamente il processo, ricaricando tutti i moduli da zero
- **Processing wait loop**: fino a 15 tentativi (30-60s) per oggetti in limbo EA fuori Golden Window
- **Golden retry loop**: fino a 6 tentativi (5-10s) per oggetti in limbo EA durante la finestra Golden
- **Browser profile persistente**: credenziali salvate, nessuna richiesta 2FA a ogni riavvio

---

## Architecture

```
main.py                    # Entrypoint, loop principale, coordinamento moduli
├── logic/
│   ├── relist_engine.py   # Engine decisionale: scan, relist, verifica
│   └── golden_hour.py     # Logica timing: Golden Hours, HOLD, processing wait
├── browser/
│   ├── controller.py      # Gestione browser Playwright
│   ├── auth.py            # Login e ripristino sessione
│   ├── detector.py        # Rilevamento stato listing (DOM parsing)
│   ├── navigator.py       # Navigazione pagine WebApp
│   ├── relist.py          # Esecuzione relist sul DOM
│   ├── session_keeper.py  # Heartbeat, wait interruptible, reboot
│   ├── rate_limiter.py    # Delay randomici configurabili
│   ├── sold_handler.py    # Gestione venduti e crediti
│   └── error_handler.py   # Screenshot e recupero errori
├── core/
│   └── notification_batch.py  # Notifiche Telegram in batch
├── config/
│   ├── config.py          # Schema validato con dataclass
│   ├── config.json        # Configurazione utente
│   └── log_config.py      # Logging strutturato
├── models/
│   ├── listing.py         # Enum ListingState, ListingScanResult
│   ├── relist_result.py   # RelistResult dataclass
│   └── sold_result.py     # SoldResult dataclass
├── bot_state.py           # Stato thread-safe (comandi, metriche, eventi)
├── telegram_handler.py    # Dispatcher comandi Telegram
├── notifier.py            # Client notifiche Telegram
└── tests/                 # 740 test (24 file) con pytest
```

---

## Project Status

**Production** · 740 test passanti con `pytest` · Manutenzione attiva.

Il bot è in uso continuativo dal marzo 2026 e viene aggiornato regolarmente per allinearsi ai cambiamenti della WebApp EA e alle migliori pratiche di anti-ban.

---

## License

MIT
