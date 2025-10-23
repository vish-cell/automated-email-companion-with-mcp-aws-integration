from mcp.server.fastmcp import FastMCP, Context
from mcp.server.session import ServerSession
import base64, os, pickle, uuid, json, threading
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# ----------------- Configuration -----------------
SHOULD_SAVE_TOKEN = False
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
TOKEN_PATH = os.path.abspath('../secrets/token.pickle')
CLIENT_SECRET_PATH = os.path.abspath('../secrets/client_secret.json')
RESOURCE_DIR = os.path.abspath("../resources")

# ----------------- Initialize MCP -----------------
mcp = FastMCP("MCP1_GmailExtractor")

# ----------------- Gmail Service Resource -----------------
@mcp.resource("gmail://service")
def gmail_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            with open(TOKEN_PATH, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Error loading token.pickle: {e}")

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

    if SHOULD_SAVE_TOKEN:
        with open(TOKEN_PATH, 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)
    return service

# ----------------- Helper: Extract email body -----------------
def extract_body(msg_data):
    parts = msg_data['payload'].get('parts', [])

    def find_text_part(parts_list):
        for part in parts_list:
            if part.get('mimeType') == 'text/plain':
                return part['body'].get('data')
            if part.get('parts'):
                result = find_text_part(part['parts'])
                if result:
                    return result
        return None

    body_data = find_text_part(parts)
    if not body_data and msg_data['payload']['body'].get('data'):
        body_data = msg_data['payload']['body'].get('data')
    if not body_data:
        return ""
    return base64.urlsafe_b64decode(body_data).decode('utf-8', errors='ignore')

# ----------------- Async Attachment Handling -----------------
def save_attachment(service, msg_id, part, subfolder="misc"):
    filename = part.get('filename')
    if not filename:
        return None

    folder = os.path.join(RESOURCE_DIR, subfolder)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)

    data = part['body'].get('data')
    if not data and 'attachmentId' in part['body']:
        attachment_id = part['body']['attachmentId']
        att = service.users().messages().attachments().get(
            userId='me', messageId=msg_id, id=attachment_id
        ).execute()
        data = att.get('data')

    if data:
        with open(path, 'wb') as f:
            f.write(base64.urlsafe_b64decode(data))

    return os.path.relpath(path, RESOURCE_DIR)

def download_attachments_async(service, msg_id, parts, ctx):
    for part in parts:
        if part.get('mimeType', '').startswith("image/"):
            save_attachment(service, msg_id, part, "image")
        elif part.get('mimeType', '') == "application/pdf":
            save_attachment(service, msg_id, part, "pdf")
        elif part.get('mimeType', '') in ["application/msword",
                                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
            save_attachment(service, msg_id, part, "word")
        else:
            save_attachment(service, msg_id, part, "misc")
    ctx.info("Attachments downloaded asynchronously.")

# ----------------- Tool: Get structured email details -----------------
@mcp.tool()
async def get_email_details(ctx: Context[ServerSession, None],
                            sender_email: str = "vishal2k4gopal@gmail.com",
                            receiver_email: str = "vishal.g2022@vitstudent.ac.in",
                            max_results: int = 1):
    if not os.path.exists(TOKEN_PATH):
        return {"error": "Token file missing"}

    with open(TOKEN_PATH, 'rb') as token_file:
        creds = pickle.load(token_file)
    service = build('gmail', 'v1', credentials=creds)

    query = f'from:{sender_email} to:{receiver_email}'
    results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    messages = results.get('messages', [])

    if not messages:
        return {"error": f"No emails found from {sender_email} to {receiver_email}"}

    msg_id = messages[0]['id']
    msg_data = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
    headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
    body = extract_body(msg_data)
    parts = msg_data['payload'].get('parts', [])

    # Download attachments asynchronously
    threading.Thread(target=download_attachments_async, args=(service, msg_id, parts, ctx), daemon=True).start()

    attachments = []
    for part in parts:
        if part.get('filename'):
            subfolder = "misc"
            if part.get('mimeType', '').startswith("image/"):
                subfolder = "image"
            elif part.get('mimeType', '') == "application/pdf":
                subfolder = "pdf"
            elif part.get('mimeType', '') in ["application/msword",
                                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]:
                subfolder = "word"

            relative_path = os.path.join(subfolder, part['filename'])
            attachments.append({
                "filename": part['filename'],
                "mime_type": part.get('mimeType', 'application/octet-stream'),
                "size_bytes": part.get('body', {}).get('size', 0),
                "relative_path": relative_path
            })

    email_data = {
        "id": str(uuid.uuid4()),
        "date": headers.get('Date', ''),
        "subject": headers.get('Subject', ''),
        "from": headers.get('From', ''),
        "to": headers.get('To', ''),
        "cc": headers.get('Cc', ''),
        "reply_to": headers.get('Reply-To', 'noreply@system.com'),
        "priority": "High",
        "body": body,
        "body_type": "text/plain",
        "attachments": attachments
    }

    os.makedirs(RESOURCE_DIR, exist_ok=True)
    with open(os.path.join(RESOURCE_DIR, 'data.json'), 'w', encoding='utf-8') as f:
        json.dump(email_data, f, indent=2)

    ctx.info("Saved email metadata to data.json.")
    return email_data

# ----------------- Tool: Fetch meeting summaries -----------------
@mcp.tool()
def fetch_meeting_summaries(sender_email: str, ctx: Context[ServerSession, None], max_results: int = 5):
    if not os.path.exists(TOKEN_PATH):
        ctx.error("Token file missing")
        return []

    with open(TOKEN_PATH, 'rb') as token_file:
        creds = pickle.load(token_file)
    service = build('gmail', 'v1', credentials=creds)

    query = f'from:{sender_email} subject:(meeting OR summary OR discussion OR minutes)'
    results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    messages = results.get('messages', [])

    if not messages:
        ctx.info(f"No meeting summary emails found for query: {query}")
        return []

    emails_data = []
    for msg in messages:
        msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
        headers = {h['name']: h['value'] for h in msg_data['payload']['headers']}
        body = extract_body(msg_data)

        emails_data.append({
            'subject': headers.get('Subject', ''),
            'from': headers.get('From', ''),
            'date': headers.get('Date', ''),
            'body': body
        })
        ctx.debug(f"Processed email: {headers.get('Subject','No Subject')}")

    ctx.info(f"Retrieved {len(emails_data)} email summaries.")
    return emails_data

@mcp.tool()
def send_to_mcp2(payload: dict, ctx: Context[ServerSession, None]):
    ctx.info("Preparing data to send to MCP2...")

    emails = payload.get("emails", [])
    filtered_payload = []

    for email in emails:
        filtered_payload.append({
            "id": email.get("id"),
            "subject": email.get("subject"),
            "from": email.get("from"),
            "to": email.get("to"),
            "body": email.get("body"),
            "attachments": [att["relative_path"] for att in email.get("attachments", [])]
        })

    ctx.info(f"Sending {len(filtered_payload)} emails to MCP2...")

    try:
        # Send request to MCP2 server
        import requests
        response = requests.post(
            "http://127.0.0.1:6278/tools/summarize_context",
            json={"emails": filtered_payload}
        )

        if response.status_code == 200:
            ctx.info("✅ MCP2 accepted the payload successfully.")
            return {"status": "success", "response": response.json()}
        else:
            ctx.error(f"❌ MCP2 responded with error: {response.status_code}")
            return {"status": "error", "code": response.status_code, "text": response.text}

    except Exception as e:
        ctx.error(f"⚠️ Failed to connect to MCP2: {e}")
        return {"status": "failed", "error": str(e)}


# ----------------- Main -----------------
if __name__ == "__main__":
    print("Starting MCP1 Email Companion in DEV mode on port 6277...")

    # Preload last 2 emails manually
    from asyncio import run

    async def preload_last_two_emails():
        ctx = Context(session=None)  # temporary context for logging
        preloaded_emails = []
        sender_email = "vishal2k4gopal@gmail.com"
        receiver_email = "vishal.g2022@vitstudent.ac.in"

        for _ in range(2):
            try:
                email_data = await get_email_details(ctx, sender_email=sender_email, receiver_email=receiver_email)
                preloaded_emails.append(email_data)
            except Exception as e:
                print(f"Error fetching email: {e}")

        print(f"✅ Preloaded {len(preloaded_emails)} emails for Inspector.")
        return preloaded_emails

    preloaded_emails = run(preload_last_two_emails())

    # Run MCP server
    mcp.run(dev_mode=True, port=6277)
