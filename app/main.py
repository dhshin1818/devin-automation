import hmac
import hashlib
import httpx
import os
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
from devin import start_devin_session, get_session_status, list_all_sessions
from dashboard import get_dashboard_html

load_dotenv()

GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

app = FastAPI()

sessions = []


def build_session_entry(raw: dict) -> dict:
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


@app.on_event("startup")
async def load_existing_sessions():
    """On startup, pull all existing Devin sessions into the dashboard"""
    global sessions
    try:
        result = list_all_sessions()
        existing = result.get("sessions", [])
        sessions = [build_session_entry(s) for s in existing]
        print(f"Loaded {len(sessions)} existing Devin sessions on startup")
    except Exception as e:
        print(f"Could not load existing sessions: {e}")


def verify_github_signature(payload: bytes, signature: str) -> bool:
    """Verify the webhook came from GitHub and not someone else"""
    expected = "sha256=" + hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/webhook")
async def github_webhook(request: Request):
    """Receives GitHub issue events and triggers Devin"""

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


def refresh_sessions():
    """Poll Devin API for latest status on all tracked sessions"""
    for session in sessions:
        session_id = session["session_id"]
        if session_id:
            try:
                result = get_session_status(session_id)
                session["status"] = result.get("status", "unknown")
                session["status_detail"] = result.get("status_detail", "")
                session["pr_url"] = result.get("pull_requests", [{}])[0].get("pr_url", "") if result.get("pull_requests") else ""
                session["pr_state"] = result.get("pull_requests", [{}])[0].get("pr_state", "") if result.get("pull_requests") else ""
                session["updated_at"] = result.get("updated_at")
                if not session["created_at"]:
                    session["created_at"] = result.get("created_at")
            except Exception as e:
                print(f"Could not refresh session {session_id}: {e}")


@app.get("/status")
async def get_status():
    """Update and return status of all tracked sessions"""
    refresh_sessions()
    return {"sessions": sessions}


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Visual dashboard showing all Devin sessions"""
    refresh_sessions()
    return get_dashboard_html(sessions)


@app.get("/health")
async def health():
    """Simple health check"""
    return {"status": "ok"}