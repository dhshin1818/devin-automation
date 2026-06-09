import hmac
import hashlib
import os
import json
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from dotenv import load_dotenv
from devin import start_devin_session, list_all_sessions
from dashboard import get_dashboard_html

load_dotenv()

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

sessions = []


def build_session_entry(raw: dict) -> dict:
    """Normalise a raw Devin API session dict into the flat shape used internally."""
    pull_requests = raw.get("pull_requests", [])
    pr_url = pull_requests[0].get("pr_url", "") if pull_requests else ""
    pr_state = pull_requests[0].get("pr_state", "") if pull_requests else ""

    return {
        "issue_title": raw.get("title", "Unknown"),
        "issue_url": pr_url or "#",
        "session_id": raw.get("session_id", ""),
        "status": raw.get("status", "unknown"),
        "status_detail": raw.get("status_detail", ""),
        "pr_url": pr_url,
        "pr_state": pr_state,
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at")
    }


def refresh_sessions():
    """Poll Devin API once and update all active tracked sessions"""
    try:
        result = list_all_sessions()
        latest = {s["session_id"]: s for s in result.get("sessions", [])}

        for session in sessions:
            if session["status"] in ("exit", "error"):
                continue
            session_id = session["session_id"]
            if session_id in latest:
                updated = latest[session_id]
                session["status"] = updated.get("status", "unknown")
                session["status_detail"] = updated.get("status_detail", "")
                pull_requests = updated.get("pull_requests", [])
                session["pr_url"] = pull_requests[0].get("pr_url", "") if pull_requests else ""
                session["pr_state"] = pull_requests[0].get("pr_state", "") if pull_requests else ""
                session["updated_at"] = updated.get("updated_at")
                if not session["created_at"]:
                    session["created_at"] = updated.get("created_at")
    except Exception as e:
        print(f"Could not refresh sessions: {e}")


async def poll_loop():
    """Background task that polls Devin every 5 seconds and updates session state in memory."""
    while True:
        await asyncio.sleep(5)
        await asyncio.to_thread(refresh_sessions)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Load existing sessions from Devin on startup and run the background poll loop."""
    global sessions
    try:
        result = list_all_sessions()
        existing = result.get("sessions", [])
        sessions = [build_session_entry(s) for s in existing]
        print(f"Loaded {len(sessions)} existing Devin sessions on startup")
    except Exception as e:
        print(f"Could not load existing sessions: {e}")
    task = asyncio.create_task(poll_loop())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)


def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Return True if the request signature matches the shared webhook secret."""
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def github_webhook(request: Request):
    """Receive a GitHub issue event, verify its signature, and start a Devin session."""
    signature = request.headers.get("X-Hub-Signature-256", "")
    payload = await request.body()

    if not verify_github_signature(payload, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = json.loads(payload)
    action = data.get("action")
    issue = data.get("issue", {})

    if action != "opened":
        return {"message": "Ignored — not an opened issue event"}

    issue_title = issue.get("title", "")
    issue_body = issue.get("body", "")
    issue_url = issue.get("html_url", "")
    issue_number = issue.get("number")

    print(f"New issue received: #{issue_number} - {issue_title}")

    devin_response = start_devin_session(issue_title, issue_body, issue_url)
    session_id = devin_response.get("session_id")

    print(f"Devin session started: {session_id}")

    existing_ids = [s["session_id"] for s in sessions]
    if session_id not in existing_ids:
        sessions.append({
            "issue_title": issue_title,
            "issue_url": issue_url,
            "session_id": session_id,
            "status": "running",
            "status_detail": "",
            "pr_url": "",
            "pr_state": "",
            "created_at": None,
            "updated_at": None
        })

    return {
        "message": "Devin session started",
        "issue": issue_title,
        "session_id": session_id
    }


@app.get("/stream")
async def stream():
    """SSE endpoint that pushes the current session list to the browser every 5 seconds."""
    async def event_generator():
        while True:
            yield f"data: {json.dumps(sessions)}\n\n"
            await asyncio.sleep(5)
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.get("/status")
async def get_status():
    """Return current session state as JSON."""
    return {"sessions": sessions}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the live HTML dashboard."""
    return get_dashboard_html(sessions)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
