@echo off
setlocal
echo Stopping LightDrop residual services...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports = 8000,5173; foreach ($port in $ports) { $ids = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; $childIds = @(); foreach ($id in $ids) { $childIds += Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.ParentProcessId -eq $id } | Select-Object -ExpandProperty ProcessId; }; foreach ($id in ($childIds + $ids | Select-Object -Unique)) { if ($id) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue; } } };"
echo Done. Press any key to close this window.
pause >nul
