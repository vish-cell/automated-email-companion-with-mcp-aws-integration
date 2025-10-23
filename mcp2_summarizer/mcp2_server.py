from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
import os, json, requests, pickle, docx
from PyPDF2 import PdfReader
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ----------------- Configuration -----------------
RESOURCE_DIR = os.path.abspath("../resources")
CLIENT_SECRET_PATH = "../secrets/client_secret.json"
TOKEN_PATH = "../secrets/token_mcp2.pickle"

# ----------------- Load YouTube + Google CSE keys -----------------
KEY_FILE = "../secrets/mcp2.json"
if not os.path.exists(KEY_FILE):
    raise FileNotFoundError(f"❌ API key file not found at expected path: {KEY_FILE}")

with open(KEY_FILE, "r") as f:
    key_data = json.load(f)
YOUTUBE_API_KEY = key_data.get("YOUTUBE_API_KEY", "")
GOOGLE_CX = key_data.get("GOOGLE_CX", "")

if not YOUTUBE_API_KEY:
    raise ValueError("❌ Missing YOUTUBE_API_KEY in mcp2.json")

# ----------------- Initialize MCP -----------------
mcp = FastMCP("MCP2_Summarizer")

# ----------------- Google Resource Auth -----------------
@mcp.resource("google://mcp2-service")
def google_service():
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/documents.readonly",
    ]

    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, "rb") as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"⚠️ Error loading {TOKEN_PATH}: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "wb") as token:
            pickle.dump(creds, token)

    return creds


# ----------------- Helper: Extract text from attachments -----------------
def extract_text_from_file(filepath):
    full_path = os.path.join(RESOURCE_DIR, filepath)
    text = ""
    if not os.path.exists(full_path):
        return f"[File not found: {filepath}]"

    if filepath.endswith(".pdf"):
        try:
            reader = PdfReader(full_path)
            for page in reader.pages:
                text += page.extract_text() + " "
        except Exception as e:
            print(f"Error reading PDF {filepath}: {e}")
    elif filepath.endswith(".docx") or filepath.endswith(".doc"):
        try:
            doc = docx.Document(full_path)
            for para in doc.paragraphs:
                text += para.text + " "
        except Exception as e:
            print(f"Error reading DOC {filepath}: {e}")
    return text.strip()


# ----------------- Helper: Generate summary -----------------
def generate_summary(keywords, attachment_texts):
    combined_text = " ".join(attachment_texts)
    summary = f"🧩 Summary based on keywords: {', '.join(keywords)}.\n\n"
    if combined_text:
        summary += "📄 Attachment Highlights:\n" + combined_text[:700] + "..."
    else:
        summary += "No attachment content found."
    return summary


# ----------------- Helper: Fetch top YouTube videos -----------------
def fetch_youtube_videos(keywords, max_results=5):
    query = " ".join(keywords)
    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&type=video&q={query}&key={YOUTUBE_API_KEY}&maxResults={max_results}"
    try:
        resp = requests.get(url).json()
        items = resp.get("items", [])
        videos = []
        for item in items:
            video_id = item["id"]["videoId"]
            stats_url = f"https://www.googleapis.com/youtube/v3/videos?part=statistics,snippet&id={video_id}&key={YOUTUBE_API_KEY}"
            stats_resp = requests.get(stats_url).json()
            if stats_resp.get("items"):
                info = stats_resp["items"][0]
                title = info["snippet"]["title"]
                views = int(info["statistics"].get("viewCount", 0))
                url = f"https://www.youtube.com/watch?v={video_id}"
                videos.append({"title": title, "url": url, "views": views})
        videos.sort(key=lambda x: x["views"], reverse=True)
        return videos[:max_results]
    except Exception as e:
        print(f"⚠️ YouTube API error: {e}")
        return []


# ----------------- Helper: Web search (Google CSE) -----------------
def fetch_web_resources(keywords, max_results=5):
    if not GOOGLE_CX:
        print("⚠️ GOOGLE_CX not provided — skipping web search.")
        return []
    web_resources = []
    for kw in keywords[:3]:
        url = f"https://www.googleapis.com/customsearch/v1?key={YOUTUBE_API_KEY}&cx={GOOGLE_CX}&q={kw}"
        try:
            resp = requests.get(url).json()
            for item in resp.get("items", []):
                web_resources.append({
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "snippet": item.get("snippet", "")
                })
        except Exception as e:
            print(f"⚠️ Web search error for '{kw}': {e}")
    return web_resources[:max_results]


# ----------------- MCP Tool: Summarize context -----------------
@mcp.tool()
def summarize_context(payload: dict, ctx: Context[ServerSession, None]):
    ctx.info("📩 Received payload from MCP1.")
    keywords = payload.get("keywords", [])
    attachments = payload.get("attachments", [])
    ctx.info(f"🔑 Keywords received: {keywords}")
    ctx.info(f"📎 Attachments received: {attachments}")

    attachment_texts = [extract_text_from_file(f) for f in attachments]
    summary = generate_summary(keywords, attachment_texts)
    youtube_videos = fetch_youtube_videos(keywords)
    web_resources = fetch_web_resources(keywords)

    result = {
        "summary": summary,
        "keywords": keywords,
        "attachments": attachments,
        "youtube_videos": youtube_videos,
        "web_resources": web_resources
    }

    os.makedirs(RESOURCE_DIR, exist_ok=True)
    with open(os.path.join(RESOURCE_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    ctx.info("✅ Summarization complete. Saved to summary.json.")
    ctx.debug(result)
    return result


# ----------------- MCP Tool: Receive from MCP1 -----------------
@mcp.tool()
def receive_emails(payload: dict, ctx: Context[ServerSession, None]):
    """
    Receives structured email data from MCP1 and triggers summarization automatically.
    """
    ctx.info("📨 MCP2 received email data from MCP1.")
    print("\n========== MCP2: RECEIVED PAYLOAD FROM MCP1 ==========\n")
    print(json.dumps(payload, indent=2))
    print("\n=====================================================\n")

    # Automatically process the email context
    result = summarize_context(payload, ctx)

    return {
        "status": "success",
        "message": "Data received from MCP1 and summarized successfully.",
        "summary_result": result
    }


# ----------------- Main Execution -----------------
if __name__ == "__main__":
    print("Starting MCP2 Summarizer Service on port 6278...")
    mcp.run(port=6278)
