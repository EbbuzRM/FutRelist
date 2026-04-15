# FIFA 26 Auto-Relist

Questo script automatizza la rimessa in vendita (relisting) degli oggetti sul mercato trasferimenti della Web App di FIFA, utilizzando Playwright per simulare le azioni nel browser. Include funzionalità come la regolazione automatica del prezzo e le notifiche via Telegram.

## 🚀 Caratteristiche
- **Login Automatico:** Utilizza le credenziali sicure per accedere alla Web App.
- **Relisting Programmato:** Rimette in vendita automaticamente tutti gli oggetti scaduti.
- **Modifica del Prezzo:** Puoi configurare uno sconto in percentuale per ogni nuovo relist (es. abbassare il prezzo del 5% finché non viene venduto).
- **Limiti di Prezzo:** Imposta un prezzo minimo di vendita (es. 200 crediti) e massimo.
- **Notifiche Telegram:** Ricevi aggiornamenti in tempo reale su vendite e relisting.
- **Anti-Ban:** Simulazione fluida dei click, pause randomiche (rate_limiting), ed esecuzione con browser in vista o in background (headless).

---

## 🏆 Golden Hours Logic ✨

Questa logica è stata progettata per massimizzare le vendite sfruttando i momenti di maggior traffico sul mercato FUT.

### Come funziona
Il mercato di FIFA ha picchi di visitatori **esattamente alle 16:10, 17:10 e 18:10** ogni giorno. In questi 2 minuti si concentra oltre il 70% delle ricerche e delle vendite.

Il bot si comporta in questo modo:
✅ **Alle :09:30** → Pre-naviga sulla Transfer List ed è pronto
✅ **Alle :10:00 ESATTO** → Esegue tutti i relist in una sola volta
❌ **Tutto il resto del tempo 15:10 → 18:15** → Rimane in HOLD: gli oggetti scaduti aspettano la prossima golden hour
✅ **Fuori dalla fascia 15:10-18:15** → Relist normale immediato

### Timeline operativa ufficiale
| Fascia oraria       | Comportamento |
|---------------------|---------------|
| Prima delle 15:10   | ✅ Relist istantaneo |
| 15:10 → 16:09       | ⏸️ HOLD → Pre-nav 16:09:30 |
| 16:10 - 16:11       | 🚀 RELIST TASSATIVO |
| 16:12 → 17:08       | ⏸️ HOLD → Pre-nav 17:09:30 |
| 17:10 - 17:11       | 🚀 RELIST TASSATIVO |
| 17:12 → 18:08       | ⏸️ HOLD → Pre-nav 18:09:30 |
| 18:10 - 18:11       | 🚀 RELIST TASSATIVO |
| Dopo le 18:15       | ✅ Relist istantaneo |

---

## ⚙️ Parametri di configurazione aggiornati

**Parametri modificabili in `config.json`:**
  - `browser.headless`: `true` per non mostrare il browser a schermo, `false` per guardare il bot.
  - `listing_defaults.price_adjustment_value`: Sconto (es. `-5.0` = riduci il prezzo del 5%).
  - `listing_defaults.min_price`: Prezzo minimo invalicabile.
  - `scan_interval_seconds`: Intervallo in secondi tra i controlli.

### 🚦 Rate Limiting Configurabile
Nuovi parametri per la velocità del bot:
```json
"rate_limiting": {
  "min_delay_ms": 1200,
  "max_delay_ms": 2800
}
```

- ✅ **Limite hard minimo**: 800ms (non è possibile andare sotto per sicurezza)
- 🟢 **Profilo Sicuro**: `1800 / 3500` → consigliato per uso 24/7
- 🟡 **Profilo Bilanciato**: `1200 / 2800` → default, velocità ottimale
- 🔴 **Profilo Veloce**: `800 / 1800` → solo per golden hours, non usare sempre

---

## 🛡️ Caratteristiche Anti-Ban
- ✅ **Precisione al secondo**: Relist eseguiti esattamente all'inizio del minuto 10
- ✅ **Rate limiting randomico**: Pause variabili tra ogni azione, non fisse
- ✅ **Rilevamento relist manuale**: Se rilevi che tu hai già rilistato manualmente, il bot salta il ciclo
- ✅ **Heartbeat automatico**: Mantiene la sessione attiva senza fare azioni inutili
- ✅ **Skip retry intelligente**: Non ripete il relist se è stato già fatto con successo
- ✅ **Profilo browser persistente**: Non richiede 2FA ad ogni avvio

## 📱 Comandi Telegram

Puoi controllare il bot direttamente da Telegram, anche mentre è in esecuzione:

| Comando | Azione |
|---|---|
| `/status` | Mostra lo stato attuale del bot, numero di listing, ultimo relist |
| `/reboot` | Riavvia il bot in modo pulito (chiude il browser e ricarica tutto il codice) |
| `/force_relist` | Forza un relist immediato, bypassando la hold window |
| `/pause` | Metti in pausa il relist automatico |
| `/resume` | Riprendi il relist automatico |
| `/console [ore]` | Attiva modalità console (deep sleep, zero interazione). Opzionale specifica ore (es. `/console 2`) |
| `/online` | Disattiva modalità console e riprende operazioni normali |
| `/del_sold` | Cancella gli oggetti venduti e raccoglie i crediti |
| `/screenshot` | Richiedi screenshot della WebApp |
| `/logs [righe]` | Mostra le ultime righe del log (default 20, massimo **30**) |
| `/help` | Mostra tutti i comandi disponibili |

> 💡 Tutti i comandi funzionano anche mentre il bot è in attesa. Non è necessario riavviare.
> ⚠️ Limite `/logs`: massimo **30 righe** (oltre Telegram rifiuta il messaggio per limite caratteri)

---

## ▶️ Avvio
Apri il terminale della cartella e avvia il file principale:
```bash
python main.py
```
Il bot avvierà Chrome, effettuerà il login e inizierà a gestire la lista mercato per tuo conto.

---

