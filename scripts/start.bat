@echo off
cd /d "%~dp0..\backend\paper-workflow"
echo [Backend] Starting Rust server...
start "ChatHTML-Backend" cargo run

timeout /t 3 /nobreak >nul

cd /d "%~dp0..\frontend\paper-workflow"
echo [Frontend] Starting Vite dev server...
npm run dev

echo Stopping backend...
taskkill /f /fi "WINDOWTITLE eq ChatHTML-Backend" >nul 2>&1
echo ChatHTML stopped.
pause
