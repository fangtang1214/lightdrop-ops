@echo off
setlocal
cd /d "%~dp0"
echo Starting LightDrop LiveOps Assistant...
echo.
node_modules\electron\dist\electron.exe apps\desktop\main.js
echo.
echo Program exited. Press any key to close this window.
pause >nul
