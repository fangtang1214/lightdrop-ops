@echo off
setlocal
cd /d "%~dp0"
echo Starting LightDrop LiveOps Assistant...
echo.
npm run dev
echo.
echo Program exited. Press any key to close this window.
pause >nul
