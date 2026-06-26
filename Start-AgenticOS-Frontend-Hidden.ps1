$workspace = "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"
$frontend = Join-Path $workspace "dashboard\frontend"
$logs = Join-Path $workspace "logs"
Set-Location $frontend
npm run dev -- --host 127.0.0.1 --port 3010 *>> (Join-Path $logs "dashboard_frontend.log")
