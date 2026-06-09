import httpx
import os
from dotenv import load_dotenv

load_dotenv()

DEVIN_API_KEY = os.getenv("DEVIN_API_KEY")
DEVIN_ORG_ID = os.getenv("DEVIN_ORG_ID")
BASE_URL = f"https://api.devin.ai/v3/organizations/{DEVIN_ORG_ID}"

HEADERS = {
    "Authorization": f"Bearer {DEVIN_API_KEY}",
    "Content-Type": "application/json"
}

def start_devin_session(issue_title: str, issue_body: str, issue_url: str) -> dict:
    """Start a Devin session for a given GitHub issue"""
    
    prompt = f"""
    You are working on the company's internal data platform repository,
    which is built on top of Apache Superset.
    
    Please fix the following GitHub issue:
    
    Title: {issue_title}
    
    Description:
    {issue_body}
    
    Issue URL: {issue_url}
    
    Instructions:
    1. Read the issue title and description carefully to understand what needs to be done
    2. Explore the codebase to find the relevant files
    3. Implement the fix or improvement described in the issue
    4. Make sure no existing functionality is broken
    5. Commit your changes with a clear message referencing the issue URL
    6. Open a pull request with your changes
    """
    
    response = httpx.post(
        f"{BASE_URL}/sessions",
        headers=HEADERS,
        json={"prompt": prompt}
    )
    
    return response.json()

def get_session_status(session_id: str) -> dict:
    """Check the status of a Devin session"""
    
    response = httpx.get(
        f"{BASE_URL}/sessions/{session_id}",
        headers=HEADERS
    )
    
    return response.json()


def list_all_sessions() -> dict:
    """List all Devin sessions for the configured repo only, excluding archived"""
    
    repo = os.getenv("GITHUB_REPO", "")
    
    response = httpx.get(
        f"{BASE_URL}/sessions",
        headers=HEADERS,
        timeout=10.0
    )
    
    data = response.json()
    all_sessions = data.get("items", [])
    
    filtered = []
    for s in all_sessions:
        if s.get("is_archived", False):
            continue
        pull_requests = s.get("pull_requests", [])
        if pull_requests:
            if any(repo in pr.get("pr_url", "") for pr in pull_requests):
                filtered.append(s)
        else:
            pass
    
    return {"sessions": filtered}

