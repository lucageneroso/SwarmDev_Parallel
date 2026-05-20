"""SeaClip-Lite — Minimal FastAPI Kanban Server.

Drop-in backend for cli-anything-seaclip.
Runs on http://127.0.0.1:5200 with SQLite persistence.

Endpoints match the SeaClipBackend client contract:
  GET  /health
  GET  /api/issues
  POST /api/issues
  POST /api/issues/{id}/move
  POST /api/issues/{id}/status
  DELETE /api/issues/{id}
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Configuration ────────────────────────────────────────────────────
DB_PATH = os.environ.get("SEACLIP_DB", os.path.join(os.path.dirname(__file__), "seaclip.db"))

app = FastAPI(title="SeaClip-Lite", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Database ─────────────────────────────────────────────────────────
def _init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'backlog',
            column_name TEXT DEFAULT 'Backlog',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            issue_id TEXT,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


_init_db()


@contextmanager
def get_db():
    """Yield a SQLite connection with row_factory, auto-commit on success."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _log_activity(conn, event_type: str, issue_id: str, summary: str):
    """Insert an activity log entry."""
    conn.execute(
        "INSERT INTO activity_log (event_type, issue_id, summary, created_at) VALUES (?, ?, ?, ?)",
        (event_type, issue_id, summary, datetime.now(timezone.utc).isoformat()),
    )


# ── Pydantic Models ──────────────────────────────────────────────────
class IssueCreate(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"


class IssueMove(BaseModel):
    column: str


class IssueStatus(BaseModel):
    status: str


# ── Routes ───────────────────────────────────────────────────────────

KANBAN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SeaClip-Lite | Kanban Board</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Inter', sans-serif;
    background: #0f0f1a;
    color: #e0e0e0;
    min-height: 100vh;
    overflow-x: hidden;
  }
  .header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border-bottom: 1px solid rgba(255,255,255,0.06);
    padding: 16px 32px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .header h1 {
    font-size: 20px;
    font-weight: 700;
    background: linear-gradient(90deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .header .status {
    font-size: 12px;
    color: #4ade80;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .header .status .dot {
    width: 8px; height: 8px;
    background: #4ade80;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
  }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  .board {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    padding: 24px 32px;
    min-height: calc(100vh - 240px);
  }
  .column {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    min-height: 300px;
  }
  .column-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }
  .column-title {
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .column-count {
    font-size: 11px;
    background: rgba(255,255,255,0.08);
    padding: 2px 8px;
    border-radius: 10px;
    font-weight: 500;
  }
  .col-backlog .column-title { color: #94a3b8; }
  .col-inprogress .column-title { color: #fbbf24; }
  .col-inprogress .column-count { background: rgba(251,191,36,0.15); color: #fbbf24; }
  .col-review .column-title { color: #818cf8; }
  .col-review .column-count { background: rgba(129,140,248,0.15); color: #818cf8; }
  .col-done .column-title { color: #4ade80; }
  .col-done .column-count { background: rgba(74,222,128,0.15); color: #4ade80; }
  .cards { flex: 1; display: flex; flex-direction: column; gap: 10px; }
  .card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 14px;
    transition: all 0.3s ease;
    animation: slideIn 0.4s ease;
  }
  @keyframes slideIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .card:hover {
    border-color: rgba(255,255,255,0.15);
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
  }
  .card-title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .card-desc {
    font-size: 12px;
    color: #888;
    margin-bottom: 10px;
    line-height: 1.4;
    max-height: 40px;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .card-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .priority {
    font-size: 10px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 3px 8px;
    border-radius: 4px;
  }
  .priority-high { background: rgba(239,68,68,0.15); color: #f87171; }
  .priority-medium { background: rgba(251,191,36,0.15); color: #fbbf24; }
  .priority-low { background: rgba(74,222,128,0.15); color: #4ade80; }
  .priority-critical { background: rgba(239,68,68,0.25); color: #ef4444; }
  .card-id {
    font-size: 10px;
    color: #555;
    font-family: monospace;
  }
  .empty-col {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #333;
    font-size: 13px;
    font-style: italic;
  }
  .activity-panel {
    margin: 0 32px 24px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 16px;
    max-height: 180px;
    overflow-y: auto;
  }
  .activity-panel h3 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #667;
    margin-bottom: 12px;
  }
  .activity-item {
    font-size: 12px;
    padding: 6px 0;
    border-bottom: 1px solid rgba(255,255,255,0.03);
    display: flex;
    justify-content: space-between;
    color: #888;
  }
  .activity-item .event { color: #aaa; }
  .activity-item .time { color: #555; font-family: monospace; font-size: 11px; }
</style>
</head>
<body>
  <div class="header">
    <h1>SeaClip-Lite Kanban</h1>
    <div class="status"><div class="dot"></div> Live - auto-refresh 3s</div>
  </div>
  <div class="board" id="board">
    <div class="column col-backlog">
      <div class="column-header">
        <span class="column-title">Backlog</span>
        <span class="column-count" id="count-backlog">0</span>
      </div>
      <div class="cards" id="col-Backlog"></div>
    </div>
    <div class="column col-inprogress">
      <div class="column-header">
        <span class="column-title">In Progress</span>
        <span class="column-count" id="count-inprogress">0</span>
      </div>
      <div class="cards" id="col-In Progress"></div>
    </div>
    <div class="column col-review">
      <div class="column-header">
        <span class="column-title">Review</span>
        <span class="column-count" id="count-review">0</span>
      </div>
      <div class="cards" id="col-Review"></div>
    </div>
    <div class="column col-done">
      <div class="column-header">
        <span class="column-title">Done</span>
        <span class="column-count" id="count-done">0</span>
      </div>
      <div class="cards" id="col-Done"></div>
    </div>
  </div>
  <div class="activity-panel">
    <h3>Activity Log</h3>
    <div id="activity"></div>
  </div>
<script>
const COLUMNS = ['Backlog', 'In Progress', 'Review', 'Done'];
const COUNT_IDS = { 'Backlog': 'count-backlog', 'In Progress': 'count-inprogress', 'Review': 'count-review', 'Done': 'count-done' };

function renderCard(issue) {
  const pClass = 'priority-' + (issue.priority || 'medium');
  return `<div class="card">
    <div class="card-title">${esc(issue.title)}</div>
    <div class="card-desc">${esc(issue.description || '')}</div>
    <div class="card-meta">
      <span class="priority ${pClass}">${esc(issue.priority || 'medium')}</span>
      <span class="card-id">${(issue.id || '').slice(0,8)}</span>
    </div>
  </div>`;
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

async function refresh() {
  try {
    const [issues, activity] = await Promise.all([
      fetch('/api/issues').then(r => r.json()),
      fetch('/api/activity?limit=10').then(r => r.json())
    ]);
    COLUMNS.forEach(col => {
      const el = document.getElementById('col-' + col);
      const colIssues = issues.filter(i => i.column_name === col);
      document.getElementById(COUNT_IDS[col]).textContent = colIssues.length;
      if (colIssues.length === 0) {
        el.innerHTML = '<div class="empty-col">No issues</div>';
      } else {
        el.innerHTML = colIssues.map(renderCard).join('');
      }
    });
    const actEl = document.getElementById('activity');
    if (activity.length === 0) {
      actEl.innerHTML = '<div class="activity-item"><span class="event">No activity yet</span></div>';
    } else {
      actEl.innerHTML = activity.map(a =>
        `<div class="activity-item"><span class="event">${esc(a.summary)}</span><span class="time">${(a.created_at||'').slice(11,19)}</span></div>`
      ).join('');
    }
  } catch(e) { console.error('Refresh error:', e); }
}

refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Serve the Kanban board dashboard."""
    return KANBAN_HTML


@app.get("/health")
def health():
    return {"status": "ok", "service": "seaclip-lite", "version": "1.0.0"}


@app.get("/api/issues")
def list_issues(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: Optional[int] = Query(None),
):
    with get_db() as conn:
        sql = "SELECT * FROM issues WHERE 1=1"
        params = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if priority:
            sql += " AND priority = ?"
            params.append(priority)
        if search:
            sql += " AND (title LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        sql += " ORDER BY created_at DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


@app.post("/api/issues")
def create_issue(payload: IssueCreate):
    issue_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO issues (id, title, description, priority, status, column_name, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'backlog', 'Backlog', ?, ?)",
            (issue_id, payload.title, payload.description, payload.priority, now, now),
        )
        _log_activity(conn, "issue_created", issue_id, f"Issue created: {payload.title}")
    return {
        "id": issue_id,
        "title": payload.title,
        "description": payload.description,
        "priority": payload.priority,
        "status": "backlog",
        "column_name": "Backlog",
        "created_at": now,
    }


@app.post("/api/issues/{issue_id}/move")
def move_issue(issue_id: str, payload: IssueMove):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        row = conn.execute("SELECT id FROM issues WHERE id = ?", (issue_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")
        conn.execute(
            "UPDATE issues SET column_name = ?, updated_at = ? WHERE id = ?",
            (payload.column, now, issue_id),
        )
        _log_activity(conn, "issue_moved", issue_id, f"Moved to column: {payload.column}")
    return {"id": issue_id, "column": payload.column, "updated_at": now}


@app.post("/api/issues/{issue_id}/status")
def update_status(issue_id: str, payload: IssueStatus):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as conn:
        row = conn.execute("SELECT id FROM issues WHERE id = ?", (issue_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")
        conn.execute(
            "UPDATE issues SET status = ?, updated_at = ? WHERE id = ?",
            (payload.status, now, issue_id),
        )
        _log_activity(conn, "status_changed", issue_id, f"Status set to: {payload.status}")
    return {"id": issue_id, "status": payload.status, "updated_at": now}


@app.delete("/api/issues/{issue_id}")
def delete_issue(issue_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT id FROM issues WHERE id = ?", (issue_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")
        conn.execute("DELETE FROM issues WHERE id = ?", (issue_id,))
        _log_activity(conn, "issue_deleted", issue_id, f"Issue deleted: {issue_id}")
    return {"deleted": True, "id": issue_id}


# ── Activity log (for CLI `activity list`) ───────────────────────────
@app.get("/api/activity")
def list_activity(limit: int = Query(default=20)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT event_type, issue_id, summary, created_at FROM activity_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("[SeaClip-Lite] Starting on http://127.0.0.1:5200")
    uvicorn.run(app, host="127.0.0.1", port=5200, log_level="info")
