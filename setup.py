import json
import os
import subprocess
import sys


def main():
    print("=" * 50)
    print("FIFA 26 AUTO-RELIST - SETUP AUTOMATICO")
    print("=" * 50)

    try:
        print("\n1. Installazione librerie (pip)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

        print("\n2. Installazione browser virtuali (playwright)...")
        # Chiamata a playwright direttamente tramite module python per compatibilità OS
        subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    except Exception as e:
        print(f"\n[ERRORE] Impossibile installare le dipendenze: {e}")
        print("Assicurati di aver installato Python correttamente e di avere i permessi necessari.")
        return

    print("\n" + "=" * 50)
    print("3. CONFIGURAZIONE CREDENZIALI E BOT TELEGRAM")
    print("=" * 50)
    print("Inserisci i dati per generare automaticamente i tuoi file di configurazione.\n")

    email = ""
    while not email:
        email = input("Inserisci la tua Email FIFA (obbligatorio): ").strip()
    
    password = ""
    while not password:
        password = input("Inserisci la tua Password FIFA (obbligatorio): ").strip()

    print("\n--- Notifiche Telegram (opzionale) ---")
    print("Per ricevere notifiche sul telefono, hai bisogno di un bot Telegram.")
    print("1. Apri Telegram e cerca @BotFather, invia /newbot e segui le istruzioni")
    print("   per creare il tuo bot. Riceverai un token tipo: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    print("2. Cerca il tuo nuovo bot su Telegram, avvia una chat e invia /start")
    print("3. Cerca @userinfobot, invia /start e trova il tuo Chat ID (numerico)")
    print("   Oppure invia un messaggio al bot e visita: https://api.telegram.org/bot<IL_TUO_TOKEN>/getUpdates")
    print()
    token = input("Inserisci il tuo Bot Token Telegram (o premi invio per saltare): ").strip()
    chat_id = input("Inserisci il tuo Chat ID Telegram (o premi invio per saltare): ").strip()

    with open(".env", "w") as f:
        f.write(f"FIFA_EMAIL={email}\n")
        f.write(f"FIFA_PASSWORD={password}\n")
        f.write(f"TELEGRAM_TOKEN={token}\n")
        f.write(f"TELEGRAM_CHAT_ID={chat_id}\n")
    
    if sys.platform == "win32":
        subprocess.run(
            ["icacls", ".env", "/inheritance:r", "/grant", f"{os.environ['USERNAME']}:F"],
            capture_output=True, timeout=5
        )
    else:
        os.chmod(".env", 0o600)

    config = {
        "browser": {
            "headless": True,  # Cambiare a falso se si vuole vedere il browser
            "slow_mo": 500,
            "viewport": {"width": 1280, "height": 720},
        },
        "listing_defaults": {
            "relist_mode": "all",
            "duration": "1h",
            "price_adjustment_type": "percentage",
            "price_adjustment_value": 0.0,
            "min_price": 200,
            "max_price": 15000000,
            "sync_minute_offset": 10,
        },
        "scan_interval_seconds": 3600,
        "rate_limiting": {"min_delay_ms": 1200, "max_delay_ms": 2800},
        "notifications": {"telegram_token": token, "telegram_chat_id": chat_id},
    }

    os.makedirs("config", exist_ok=True)
    with open("config/config.json", "w") as f:
        json.dump(config, f, indent=2)
    print(" -> File config/config.json creato con successo.\n")

    print("=" * 50)
    print("SETUP COMPLETATO CON SUCCESSO!")
    print("=" * 50)
    print("\nTutto pronto! Ora puoi avviare il bot in qualsiasi momento eseguendo:")
    print("python main.py")
    print("\nSe vuoi modificare le configurazioni, puoi farlo editando i file '.env' o 'config/config.json'")
    print("")


if __name__ == "__main__":
    main()
