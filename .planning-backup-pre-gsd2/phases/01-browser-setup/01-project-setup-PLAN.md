---
name: "01-project-setup"
description: "Setup progetto Python + Playwright per FIFA 26 Auto-Relist"
wave: 1
autonomous: true
gap_closure: false
---

## Objective
Creare la struttura del progetto, installare dipendenze, configurare entry point base.

## Tasks

### Task 1: Crea struttura directory progetto
**type:** bash
**description:** Crea la struttura cartelle per fifa-relist

```bash
mkdir -p fifa-relist/browser
mkdir -p fifa-relist/config
mkdir -p fifa-relist/storage
mkdir -p fifa-relist/logs
```

### Task 2: Crea requirements.txt
**type:** file_write
**path:** fifa-relist/requirements.txt
**description:** Dipendenze Python per il progetto

```
playwright>=1.40.0
python-dotenv>=1.0.0
```

### Task 3: Crea config.json template
**type:** file_write
**path:** fifa-relist/config/config.json
**description:** File configurazione iniziale

```json
{
  "fifa_webapp_url": "https://www.ea.com/fifa/ultimate-team/web-app/",
  "browser": {
    "headless": false,
    "slow_mo": 500,
    "viewport_width": 1280,
    "viewport_height": 720
  },
  "scan_interval_seconds": 60,
  "listing_defaults": {
    "duration": "3h",
    "price_adjustment_type": "percentage",
    "price_adjustment_value": 0
  },
  "rate_limiting": {
    "min_delay_ms": 2000,
    "max_delay_ms": 5000
  }
}
```

### Task 4: Crea main.py entry point
**type:** file_write
**path:** fifa-relist/main.py
**description:** Entry point principale con logging base

```python
"""
FIFA 26 Auto-Relist Tool
Browser automation per rilistare automaticamente giocatori su FIFA 26 WebApp
"""
import json
import logging
import sys
from pathlib import Path

def setup_logging():
    """Configura logging con output su file e console."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "fifa-relist.log"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

def load_config():
    """Carica configurazione da config.json."""
    config_path = Path("config/config.json")
    if not config_path.exists():
        raise FileNotFoundError(f"Config non trovato: {config_path}")
    with open(config_path) as f:
        return json.load(f)

def main():
    """Entry point principale."""
    logger = setup_logging()
    logger.info("=== FIFA 26 Auto-Relist Tool avviato ===")
    
    try:
        config = load_config()
        logger.info(f"Config caricata da config/config.json")
        logger.info(f"URL WebApp: {config['fifa_webapp_url']}")
        logger.info(f"Headless: {config['browser']['headless']}")
        
        # TODO: Avvia browser e autenticazione (Fase 1, Plan 02 e 03)
        logger.info("Browser automation non ancora implementato")
        
    except Exception as e:
        logger.error(f"Errore all'avvio: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Task 5: Crea __init__.py per package browser
**type:** file_write
**path:** fifa-relist/browser/__init__.py
**description:** Package init vuoto

```python
```

## Success Criteria
- [ ] Directory fifa-relist/ creata con sotto-cartelle
- [ ] requirements.txt con playwright e python-dotenv
- [ ] config.json con impostazioni default
- [ ] main.py funzionante (esegue senza errori)
- [ ] Package browser/ inizializzato
