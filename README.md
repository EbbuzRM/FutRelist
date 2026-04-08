# FIFA 26 Auto-Relist

Questo script automatizza la rimessa in vendita (relisting) degli oggetti sul mercato trasferimenti della Web App di FIFA, utilizzando Playwright per simulare le azioni nel browser. Include funzionalità come la regolazione automatica del prezzo e le notifiche via Telegram.

## 🚀 Caratteristiche
- **Login Automatico:** Utilizza le credenziali sicure per accedere alla Web App.
- **Relisting Programmato:** Rimette in vendita automaticamente tutti gli oggetti scaduti.
- **Modifica del Prezzo:** Puoi configurare uno sconto in percentuale per ogni nuovo relist (es. abbassare il prezzo del 5% finché non viene venduto).
- **Limiti di Prezzo:** Imposta un prezzo minimo di vendita (es. 200 crediti) e massimo.
- **Notifiche Telegram:** Ricevi aggiornamenti in tempo reale su vendite e relisting.
- **Anti-Ban:** Simulazione fluida dei click, pause randomiche (rate_limiting), ed esecuzione con browser in vista o in background (headless).

## 🛠 Requisiti
- Python 3.9+
- [Git](https://git-scm.com/)

## ⚙️ Installazione e Configurazione Rapida (Automatica)
Il modo più semplice per iniziare è utilizzare lo script di installazione, che scaricherà i requisiti e ti guiderà nella creazione dei file di configurazione (`.env` e `config.json`).

1. **Clona o scarica questo progetto**.
2. **Avvia il Setup:**
   - **Su Windows:** Fai doppio click su `setup.bat` (oppure avvialo da terminale).
   - **Su Mac/Linux:** Apri il terminale ed esegui `bash setup.sh` (oppure `python3 setup.py`).
3. Rispondi alle domande nel terminale inserendo la tua email FIFA, la password e i dati del Bot Telegram. Lo script genererà in automatico tutto il necessario!

## 📝 Configurazione Manuale (Avanzata)
Se preferisci configurare tutto manualmente:
1. Esegui `pip install -r requirements.txt` e `playwright install`.
2. Rinomina `.env.example` in `.env` e inserisci le tue credenziali FIFA.
3. Rinomina `config/config.example.json` in `config/config.json` e modifica i parametri.

**Parametri modificabili in `config.json`:**
  - `browser.headless`: `true` per non mostrare il browser a schermo, `false` per guardare il bot.
  - `listing_defaults.price_adjustment_value`: Sconto (es. `-5.0` = riduci il prezzo del 5%).
  - `listing_defaults.min_price`: Prezzo minimo invalicabile.
  - `scan_interval_seconds`: Intervallo in secondi tra i controlli.

## ▶️ Avvio
Apri il terminale della cartella e avvia il file principale:
```bash
python main.py
```
Il bot avvierà Chrome, effettuerà il login e inizierà a gestire la lista mercato per tuo conto.
