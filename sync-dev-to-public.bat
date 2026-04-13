@echo off
echo ==============================================
echo  SYNC DEV -> PUBLIC FOLDER (SAFE)
echo ==============================================
echo.

REM Elimina vecchia cartella public
rd /s /q public
timeout /t 1 /nobreak >nul

REM Copia solo i file pubblici, ESCLUDENDO TUTTO QUELLO PRIVATO
robocopy . public /MIR ^
  /XD .git .kilo .planning storage logs __pycache__ .pytest_cache .stfolder node_modules ^
  /XF .env config.json .gitignore .stignore sync-dev-to-public.bat AGENTS.md ^
  /NFL /NDL /NJH /NJS /NC /NS

echo.
echo ✅ Copia completata
echo.

cd public

echo Status repository pubblico:
git status

echo.
echo Ora esegui:
echo   cd public
echo   git add .
echo   git commit -m "Update"
echo   git push
echo.

pause
