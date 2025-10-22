from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
import os, json, uuid
from datetime import datetime

RESOURCE_DIR = os.path.abspath("../resources")

mcp = FastMCP("MCP2_Summarizer")

@mcp.tool()
def summarize_email(ctx: Context[ServerSession, None], data_file: str = "data.json"):
    file_path = os.path.join(RESOURCE_DIR, data_file)
    if not os.path.exists(file_path):
        ctx.error(f"Data file not found: {file_path}")
        return {"error": "Data file missing"}

    with open(file_path, 'r', encoding='utf-8') as f:
        email_data = json.load(f)

    summary_text = email_data.get("body", "")[:200] + "..."
    attachment_names = [att["filename"] for att in email_data.get("attachments", [])]

    summary = {
        "summary_id": str(uuid.uuid4()),
        "date": datetime.now().isoformat(),
        "email_subject": email_data.get("subject", ""),
        "from": email_data.get("from", ""),
        "to": email_data.get("to", ""),
        "summary_text": summary_text,
        "attachment_files": attachment_names,
        "priority": email_data.get("priority", "Normal")
    }

    ctx.info(f"Email summarized: {email_data.get('subject', 'No Subject')}")
    return summary

if __name__ == "__main__":
    print("MCP2 running... Use summarize_email() now.")
