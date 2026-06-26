$root = "C:\Users\Admin\Documents\A-Time to revenue\Agentic OS Live"
Write-Host "Telegram bridge running. Leave this window open."
wsl.exe -d AgenticOSClean -- bash -lc "pkill -f '[t]elegram_bridge.py' 2>/dev/null || true; cd '/mnt/c/Users/Admin/Documents/A-Time to revenue/Agentic OS Live' && exec python3 -u connectors/telegram_bridge/telegram_bridge.py"
