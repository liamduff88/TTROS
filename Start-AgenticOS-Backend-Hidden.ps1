$workspace = "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"
$dashboard = Join-Path $workspace "dashboard"
$logs = Join-Path $workspace "logs"
Set-Location $dashboard
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8010 *>> (Join-Path $logs "dashboard_backend.log")
