from datetime import datetime, timezone


def format_time(unix_timestamp):
    """Convert Unix timestamp to readable string"""
    if not unix_timestamp:
        return "—"
    dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    return dt.strftime("%d %b %Y %H:%M UTC")


def get_dashboard_html(sessions: list) -> str:

    total = len(sessions)
    completed = sum(1 for s in sessions if s.get("status") == "exit")
    running = sum(1 for s in sessions if s.get("status") in ("running", "claimed", "new", "resuming"))
    waiting = sum(1 for s in sessions if s.get("status_detail") == "waiting_for_user")
    failed = sum(1 for s in sessions if s.get("status") == "error")
    merged = sum(1 for s in sessions if s.get("pr_state") == "merged")

    rows = ""
    for s in sorted(sessions, key=lambda s: s.get("created_at") or 0, reverse=True):
        status = s.get("status", "unknown")
        status_detail = s.get("status_detail", "")
        session_id = s.get("session_id", "")
        devin_url = f"https://app.devin.ai/sessions/{session_id}" if session_id else "#"
        pr_url = s.get("pr_url", "")
        pr_state = s.get("pr_state", "")
        created_at = s.get("created_at")
        updated_at = s.get("updated_at")

        if pr_url:
            parts = pr_url.rstrip("/").split("/")
            try:
                owner = parts[3]
                repo = parts[4]
                pr_number = parts[6]
                review_url = f"https://app.devin.ai/review/{owner}/{repo}/pull/{pr_number}"
                pr_link = f'<a href="{pr_url}" target="_blank">#{pr_number}</a>'
                review_link = f'<a href="{review_url}" target="_blank">Review</a>'
            except IndexError:
                pr_link = f'<a href="{pr_url}" target="_blank">View PR</a>'
                review_link = "—"
        else:
            pr_link = "—"
            review_link = "—"

        if pr_state == "merged":
            pr_state_badge = '<span style="color:green">merged</span>'
        elif pr_state == "open":
            pr_state_badge = '<span style="color:#3b82f6">open</span>'
        elif pr_state == "closed":
            pr_state_badge = '<span style="color:gray">closed</span>'
        else:
            pr_state_badge = "—"

        if status_detail == "waiting_for_user":
            color = "orange"
            emoji = "💬"
            display_status = "WAITING FOR USER"
        elif status == "new":
            color = "#8b949e"
            emoji = "🆕"
            display_status = "NEW"
        elif status == "claimed":
            color = "#8b949e"
            emoji = "📋"
            display_status = "CLAIMED"
        elif status == "running":
            color = "#3b82f6"
            emoji = "⏳"
            display_status = "RUNNING"
        elif status == "suspended":
            color = "orange"
            emoji = "⏸️"
            display_status = "SUSPENDED"
        elif status == "resuming":
            color = "#3b82f6"
            emoji = "▶️"
            display_status = "RESUMING"
        elif status == "exit":
            color = "green"
            emoji = "✅"
            display_status = "COMPLETED"
        elif status == "error":
            color = "red"
            emoji = "❌"
            display_status = "ERROR"
        else:
            color = "gray"
            emoji = "❓"
            display_status = status.upper()

        rows += f"""
        <tr>
            <td><a href="{s.get('issue_url', '#')}" target="_blank">{s.get('issue_title', '—')}</a></td>
            <td><a href="{devin_url}" target="_blank">{session_id[:16]}...</a></td>
            <td style="color:{color}"><strong>{emoji} {display_status}</strong></td>
            <td>{pr_link}</td>
            <td>{review_link}</td>
            <td>{pr_state_badge}</td>
            <td style="font-size:12px;color:#8b949e">{format_time(created_at)}</td>
            <td style="font-size:12px;color:#8b949e">{format_time(updated_at)}</td>
        </tr>
        """

    if not rows:
        rows = "<tr><td colspan='8' style='text-align:center;padding:24px;color:#8b949e'>No sessions yet — waiting for GitHub issues...</td></tr>"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Devin Remediation Dashboard</title>
        <meta http-equiv="refresh" content="5">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #0d1117;
                color: #c9d1d9;
                padding: 40px;
            }}
            h1 {{ color: #58a6ff; margin-bottom: 4px; }}
            p {{ color: #8b949e; font-size: 13px; margin-top: 4px; }}
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 24px;
            }}
            .badge {{
                background: #238636;
                color: white;
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
            }}
            .metrics {{
                display: flex;
                gap: 12px;
                margin-bottom: 28px;
                flex-wrap: wrap;
            }}
            .metric {{
                background: #161b22;
                border: 0.5px solid #30363d;
                border-radius: 8px;
                padding: 14px 20px;
                min-width: 100px;
                text-align: center;
            }}
            .metric-label {{
                font-size: 11px;
                color: #8b949e;
                margin-bottom: 6px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            .metric-value {{
                font-size: 28px;
                font-weight: 600;
                color: #c9d1d9;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 8px;
            }}
            th {{
                background: #161b22;
                padding: 12px;
                text-align: left;
                color: #58a6ff;
                border-bottom: 1px solid #30363d;
                font-size: 13px;
            }}
            td {{
                padding: 12px;
                border-bottom: 1px solid #21262d;
                font-size: 13px;
                vertical-align: middle;
            }}
            tr:hover {{ background: #161b22; }}
            a {{ color: #58a6ff; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .legend {{
                margin-top: 24px;
                font-size: 12px;
                color: #8b949e;
                display: flex;
                gap: 20px;
                flex-wrap: wrap;
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h1>Devin Session Dashboard</h1>
                <p>For Repo: superset-cognition-demo</p>
            </div>
            <span class="badge">Auto-refreshes every 5s</span>
        </div>

        <div class="metrics">
            <div class="metric">
                <div class="metric-label">Total</div>
                <div class="metric-value">{total}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Completed</div>
                <div class="metric-value" style="color:green">{completed}</div>
            </div>
            <div class="metric">
                <div class="metric-label">In progress</div>
                <div class="metric-value" style="color:#3b82f6">{running}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Waiting</div>
                <div class="metric-value" style="color:orange">{waiting}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Failed</div>
                <div class="metric-value" style="color:red">{failed}</div>
            </div>
            <div class="metric">
                <div class="metric-label">PRs merged</div>
                <div class="metric-value" style="color:#238636">{merged}</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Title</th>
                    <th>Devin session</th>
                    <th>Status</th>
                    <th>GitHub PR</th>
                    <th>Devin review</th>
                    <th>PR state</th>
                    <th>Created</th>
                    <th>Last updated</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>

        <div class="legend">
            <span>🆕 New</span>
            <span>📋 Claimed</span>
            <span>⏳ Running</span>
            <span>💬 Waiting for user</span>
            <span>⏸️ Suspended</span>
            <span>▶️ Resuming</span>
            <span>✅ Completed</span>
            <span>❌ Error</span>
        </div>
    </body>
    </html>
    """
    return html