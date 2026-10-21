@echo off
setlocal
cd /d "%~dp0"

rem ===========================================================================
rem  Boveda DAI - local launcher (backend :8012, frontend :3001)
rem  First time: see README.md ("Run locally") to create backend\.venv and run npm install.
rem ===========================================================================

if not exist "backend\.venv\Scripts\python.exe" (
  echo [ERROR] Falta backend\.venv. Crealo con:
  echo     python -m venv backend\.venv
  echo     backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
  pause
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo [ERROR] Faltan las dependencias del frontend. Ejecuta:
  echo     cd frontend ^&^& npm install
  pause
  exit /b 1
)

start "Boveda DAI - backend :8012" cmd /k "cd /d %~dp0backend && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8012 --reload-include .env"
start "Boveda DAI - frontend :3001" cmd /k "cd /d %~dp0frontend && npm run dev"

echo Esperando a que arranquen los servidores...
timeout /t 8 /nobreak >nul
start "" "http://127.0.0.1:3001"
endlocal
