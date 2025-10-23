# Start MCP1 (Gmail extractor + Inspector)
Set-Location -Path "${PSScriptRoot}\..\mcp1_gmail_extractor"
Write-Host "Starting MCP1 (mcp1_gmail_extractor) in dev mode on port 6277..."
& "${PSScriptRoot}\..\auto\Scripts\python.exe" mcp1_server.py
