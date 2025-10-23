Automated Email Companion — Developer README

Overview
--------
This repository contains two MCP services for extracting and summarizing emails:

- mcp1_gmail_extractor — fetches emails from Gmail and exposes tools via an Inspector UI.
- mcp2_summarizer — summarizes email content, extracts text from attachments, and can enrich results with YouTube/web links.

Quick flow
----------
1. Start MCP2 (summarizer) on port 6278.
2. Start MCP1 (Gmail extractor + Inspector) on port 6277.
3. In the Inspector UI open http://127.0.0.1:6277/ and run get_email_details and send_to_mcp2.
4. Outputs are written to resources/data.json and resources/summary.json.

Secrets
-------
Place these files in the secrets/ directory:
- client_secret.json (Google OAuth client) — already present for MCP1.
- token.pickle — created after first OAuth consent (run test.py or use Inspector to trigger OAuth).
- mcp2.json — optional: contains YOUTUBE_API_KEY and GOOGLE_CX for enrichment. If missing, MCP2 will run but skip external enrichments.

Start commands (PowerShell)
---------------------------
Start MCP2 (from repo root, or change to the mcp2_summarizer folder):

Set-Location "<repo>/mcp2_summarizer"
.\.venv\Scripts\python.exe -m uvicorn mcp2_server:app --port 6278 --app-dir "<repo>\mcp2_summarizer"

Start MCP1 (Inspector):

Set-Location "<repo>/mcp1_gmail_extractor"
..\auto\Scripts\python.exe mcp1_server.py

Inspector UI
------------
Open http://127.0.0.1:6277/ in a browser. The Inspector lists tools annotated with @mcp.tool().
- Use get_email_details to fetch an email and write resources/data.json.
- Use send_to_mcp2 (or directly POST to MCP2) to create resources/summary.json.

Direct HTTP call to MCP2 (example)
---------------------------------
POST JSON to http://127.0.0.1:6278/tools/summarize_context with payload like:

{
  "keywords": ["aws", "email", "serverless"],
  "attachments": []
}

Outputs
-------
- resources/data.json — created by get_email_details.
- resources/summary.json — created by MCP2 summarizer.

Troubleshooting
---------------
- Token missing: run test.py or run get_email_details and follow the OAuth flow to create secrets/token.pickle.
- Port in use: run Get-NetTCPConnection -LocalPort 6278 and Stop-Process -Id <PID> to free it.
- Missing libs (PyPDF2, docx): install them into your venv with pip.
- Enrichment not present: add secrets/mcp2.json with YOUTUBE_API_KEY and GOOGLE_CX and restart MCP2.

Scripts
-------
There is a scripts/ folder with helper PowerShell scripts to start MCP1, MCP2, or both. Use those if you prefer a one-click approach.

Git: commit & push
------------------
After verifying everything locally, commit and push the new files:

```powershell
Set-Location "C:\Users\visha\Desktop\automated-email-companion-with-mcp-aws-integration"
git add README.md scripts/start_*.ps1
git commit -m "docs: add README and helper start scripts"
git push origin main
```

Make sure you do NOT commit sensitive files from `secrets/` (client_secret.json, token.pickle). Add them to `.gitignore` if they're not already ignored.

