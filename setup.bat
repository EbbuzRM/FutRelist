@echo off
:: Per configurare le notifiche Telegram ti serviranno:
::   - Token bot: cerca @BotFather su Telegram, crea un bot con /newbot
::   - Chat ID: cerca @userinfobot su Telegram e invia /start
:: Entrambi ti verranno chiesti durante il setup guidato.
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERRORE] Python non trovato. Assicurati di aver installato Python 3.10+ da https://python.org
    echo Assicurati anche di aver spuntato "Add Python to PATH" durante l'installazione.
    pause
    exit /b 1
)
echo Avvio del setup automatico...
python setup.py
pause
