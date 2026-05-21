#!/bin/bash
# Per configurare le notifiche Telegram ti serviranno:
#   - Token bot: cerca @BotFather su Telegram, crea un bot con /newbot
#   - Chat ID: cerca @userinfobot su Telegram e invia /start
# Entrambi ti verranno chiesti durante il setup guidato.
PYTHON_CMD=$(command -v python3 || command -v python)
if [ -z "$PYTHON_CMD" ]; then
    echo "[ERRORE] Python non trovato. Installa Python 3.10+ da https://python.org"
    exit 1
fi
echo "Avvio del setup automatico..."
"$PYTHON_CMD" setup.py
