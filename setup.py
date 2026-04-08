import os
import json
import subprocess
import sys

def main():
    print("="*50)
    print("FIFA 26 AUTO-RELIST - SETUP AUTOMATICO")
    print("="*50)
    
    try:
        print("\n1. Installazione librerie (pip)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        
        print("\n2. Installazione browser virtuali (playwright)...")
        # Chiamata a playwright direttamente tramite module python per compatibilità OS
        subprocess.check_call([sys.executable, "-m", "playwright", "install"])
    except Exception as e:
        print(f"\n[ERRORE] Impossibile installare le dipendenze: {e}")
        print("Assicurati di aver installato Python correttamente e di avere i permessi necessari.")
        return
        
    print("\n" + "="*50)
    print("3. CONFIGURAZIONE CREDENZIALI E BOT TELEGRAM")
    print("="*50)
    print("Inserisci i dati per generare automaticamente i tuoi file di configurazione.\n")
    
    email = input("Inserisci la tua Email FIFA: ").strip()
    password = input("Inserisci la tua Password FIFA: ").strip()
    
    with open(".env", "w") as f:
        f.write(f"FIFA_EMAIL={email}\n")
        f.write(f"FIFA_PASSWORD={password}\n")
    print(" -> File .env creato con successo.")
    
    token = input("\nInserisci il tuo Bot Token di Telegram (o premi invio se non vuoi usarlo): ").strip()
    chat_id = input("Inserisci il tuo Chat ID di Telegram (o premi invio se non vuoi usarlo): ").strip()
    
    config = {
        "browser": {
            "headless": True, # Cambiare a falso se si vuole vedere il browser
            "slow_mo": 500,
            "viewport": {"width": 1280, "height": 720}
        },
        "listing_defaults": {
            "relist_mode": "all",
            "duration": "1h",
            "price_adjustment_type": "percentage",
            "price_adjustment_value": 0.0,
            "min_price": 200,
            "max_price": 15000000,
            "sync_minute_offset": 10
        },
        "scan_interval_seconds": 3600,
        "rate_limiting": {
            "min_delay_ms": 2000,
            "max_delay_ms": 5000
        },
        "notifications": {
            "telegram_token": token,
            "telegram_chat_id": chat_id
        }
    }
    
    os.makedirs("config", exist_ok=True)
    with open("config/config.json", "w") as f:
        json.dump(config, f, indent=2)
    print(" -> File config/config.json creato con successo.\n")
    
    print("="*50)
    print("SETUP COMPLETATO CON SUCCESSO!")
    print("="*50)
    print("\nTutto pronto! Ora puoi avviare il bot in qualsiasi momento eseguendo:")
    print("python main.py")
    print("\nSe vuoi modificare le configurazioni, puoi farlo editando i file '.env' o 'config/config.json'")
    print("")

if __name__ == "__main__":
    main()
