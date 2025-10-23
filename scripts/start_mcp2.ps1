# Start MCP2 Summarizer (ASGI)
Set-Location -Path "$PSScriptRoot\..\mcp2_summarizer"
Write-Host "Starting MCP2 (mcp2_summarizer) on port 6278..."

# Use call operator & and correct path quoting
$pythonPath = "$PSScriptRoot\..\mcp2_summarizer\.venv\Scripts\python.exe"
& $pythonPath -m uvicorn mcp2_server:app --port 6278 --app-dir "$PSScriptRoot\..\mcp2_summarizer"
