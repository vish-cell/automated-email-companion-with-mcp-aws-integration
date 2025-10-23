# Start both MCP2 and MCP1. MCP2 is started in a background job; MCP1 is started in the foreground.
Set-Location -Path "${PSScriptRoot}\..\mcp2_summarizer"
Write-Host "Starting MCP2 in background..."
Start-Job -ScriptBlock { Set-Location "${PSScriptRoot}\..\mcp2_summarizer"; & "${PSScriptRoot}\..\mcp2_summarizer\.venv\Scripts\python.exe" -m uvicorn mcp2_server:app --port 6278 --app-dir "${PSScriptRoot}\..\mcp2_summarizer" }
Start-Sleep -s 2
Write-Host "Starting MCP1 (Inspector) in foreground..."
Set-Location -Path "${PSScriptRoot}\..\mcp1_gmail_extractor"
& "${PSScriptRoot}\..\auto\Scripts\python.exe" mcp1_server.py
