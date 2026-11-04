"""Manager console UI for human-in-the-loop ticket approvals.
Run: python manager_ui.py  ->  http://localhost:5000
"""
import json
import pathlib
from flask import Flask, render_template_string, request, redirect, url_for

APPROVALS_FILE = pathlib.Path("approvals.json")
AUDIT_FILE = pathlib.Path("audit.jsonl")

app = Flask(__name__)

HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Safari Desk — Manager Console</title>
<style>
  :root { --bg:#0b1021; --card:#161e30; --accent:#22d3ee; --danger:#ef4444; --ok:#22c55e; --text:#e2e8f0; --muted:#94a3b8; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif; background:var(--bg); color:var(--text); }
  .container { max-width: 720px; margin: 40px auto; padding: 0 20px; }
  header { display:flex; align-items:center; gap:12px; margin-bottom: 24px; }
  .badge { width:10px; height:10px; border-radius:50%; background:var(--accent); box-shadow:0 0 10px var(--accent); }
  h1 { font-size:1.1rem; margin:0; letter-spacing:-0.02em; }
  .subtitle { color:var(--muted); font-size:0.85rem; margin-top:4px; }
  .stat-row { display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap; }
  .stat { background:var(--card); border:1px solid #1f2a44; border-radius:12px; padding:14px 18px; min-width:110px; }
  .stat .label { font-size:0.75rem; color:var(--muted); text-transform:uppercase; letter-spacing:0.05em; }
  .stat .value { font-size:1.5rem; font-weight:700; margin-top:4px; }
  .stat .value.pending { color:#fbbf24; }
  .stat .value.approved { color:var(--ok); }
  .stat .value.blocked { color:var(--danger); }
  .empty { background:var(--card); border:1px dashed #334155; border-radius:12px; padding:40px 20px; text-align:center; color:var(--muted); }
  .ticket { background:var(--card); border:1px solid #1f2a44; border-radius:12px; padding:18px; margin-bottom:12px; position:relative; overflow:hidden; }
  .ticket::before { content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--accent); }
  .ticket.approved::before { background:var(--ok); }
  .ticket.rejected::before { background:var(--danger); }
  .ticket-header { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:10px; }
  .ticket-id { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-weight:700; font-size:0.95rem; }
  .ticket-status { font-size:0.75rem; font-weight:700; text-transform:uppercase; padding:2px 8px; border-radius:6px; background:#1e293b; color:var(--muted); }
  .ticket-status.pending { background:#451a03; color:#fbbf24; border:1px solid #78350f; }
  .ticket-status.approved { background:#064e3b; color:#86efac; border:1px solid #15803d; }
  .ticket-status.rejected { background:#450a0a; color:#fca5a5; border:1px solid #7f1d1d; }
  .ticket-summary { font-size:0.9rem; line-height:1.5; color:#cbd5e1; margin-bottom:12px; white-space:pre-wrap; }
  .ticket-meta { display:flex; gap:16px; font-size:0.8rem; color:var(--muted); margin-bottom:14px; }
  .actions { display:flex; gap:8px; }
  .btn { border:none; border-radius:8px; padding:8px 14px; font-weight:600; font-size:0.85rem; cursor:pointer; text-decoration:none; display:inline-block; transition:opacity 0.2s; }
  .btn:hover { opacity:0.85; }
  .btn-approve { background:var(--ok); color:#ffffff; }
  .btn-reject { background:var(--danger); color:#ffffff; }
  .btn-disabled { background:#334155; color:#64748b; cursor:not-allowed; }
  .audit-link { margin-top:24px; display:inline-block; color:var(--accent); text-decoration:none; font-size:0.85rem; font-weight:600; }
  .audit-link:hover { text-decoration:underline; }
  .refresh { margin-left:auto; background:transparent; border:1px solid #334155; color:var(--muted); border-radius:6px; padding:4px 10px; cursor:pointer; font-size:0.8rem; }
  .refresh:hover { border-color:var(--accent); color:var(--accent); }
  footer { margin-top:32px; color:var(--muted); font-size:0.75rem; border-top:1px solid #1f2a44; padding-top:16px; }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="badge"></div>
    <div>
      <h1>Safari Desk — Manager Console</h1>
      <div class="subtitle">Human-in-the-loop approval queue &middot; tickets awaiting review</div>
    </div>
    <button class="refresh" onclick="location.reload()">Refresh</button>
  </header>

  <div class="stat-row">
    <div class="stat">
      <div class="label">Total tickets</div>
      <div class="value">{{ total }}</div>
    </div>
    <div class="stat">
      <div class="label">Pending</div>
      <div class="value pending">{{ pending }}</div>
    </div>
    <div class="stat">
      <div class="label">Approved</div>
      <div class="value approved">{{ approved }}</div>
    </div>
    <div class="stat">
      <div class="label">Rejected</div>
      <div class="value blocked">{{ rejected }}</div>
    </div>
  </div>

  {% if not tickets %}
    <div class="empty">
      <div style="font-size:1.1rem; margin-bottom:8px;">No tickets in queue.</div>
      <div style="font-size:0.85rem;">Run the Safari Desk pipeline and a pricing quote will appear here for approval.</div>
    </div>
  {% else %}
    {% for t in tickets %}
    <div class="ticket {{ t.status }}">
      <div class="ticket-header">
        <div>
          <div class="ticket-id">{{ t.ticket }}</div>
          <span class="ticket-status {{ t.status }}">{{ t.status }}</span>
        </div>
      </div>
      <div class="ticket-summary">{{ t.summary }}</div>
      <div class="ticket-meta">
        <span><b>Total:</b> ${{ t.quote.get('total_usd', 0) }}</span>
        <span><b>Discount:</b> {{ t.quote.get('discount_pct', 0) }}%</span>
        {% if t.quote.get('quote_id') %}<span><b>Quote:</b> {{ t.quote.quote_id }}</span>{% endif %}
      </div>
      <div class="actions">
        {% if t.status == "pending" %}
          <a class="btn btn-approve" href="{{ url_for('action', ticket_id=t.ticket, decision='approve') }}">Approve</a>
          <a class="btn btn-reject" href="{{ url_for('action', ticket_id=t.ticket, decision='reject') }}">Reject</a>
        {% else %}
          <span class="btn btn-disabled">{{ t.status }}</span>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  {% endif %}

  <a class="audit-link" href="{{ url_for('audit') }}">View live audit trail &rarr;</a>

  <footer>
    Safari Desk multi-agent demo &middot; Google ADK &middot; DevFest Jinja 2026
  </footer>
</div>
</body>
</html>
"""

AUDIT_HTML = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Safari Desk — Audit Trail</title>
<style>
  :root { --bg:#0b1021; --card:#161e30; --accent:#22d3ee; --text:#e2e8f0; --muted:#94a3b8; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; background:var(--bg); color:var(--text); }
  .container { max-width: 1100px; margin: 0 auto; padding: 24px; }
  header { display:flex; align-items:center; gap:12px; margin-bottom:24px; }
  .badge { width:10px; height:10px; border-radius:50%; background:var(--accent); box-shadow:0 0 10px var(--accent); }
  h1 { font-size:1rem; margin:0; letter-spacing:-0.02em; }
  a.back { margin-left:auto; color:var(--accent); text-decoration:none; font-size:0.85rem; font-weight:600; }
  a.back:hover { text-decoration:underline; }
  .line { background:var(--card); border:1px solid #1f2a44; border-radius:8px; padding:10px 14px; margin-bottom:8px; overflow-x:auto; white-space:pre-wrap; font-size:0.82rem; line-height:1.4; }
  .line:nth-child(even) { background:#12192c; }
  .key { color:var(--accent); font-weight:700; }
  .str { color:#a5b4fc; }
  .num { color:#f472b6; }
  .bool { color:#86efac; }
  .empty { background:var(--card); border:1px dashed #334155; border-radius:12px; padding:40px 20px; text-align:center; color:var(--muted); }
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="badge"></div>
    <div>
      <h1>Audit Trail — audit.jsonl</h1>
    </div>
    <a class="back" href="{{ url_for('index') }}">&larr; Back to console</a>
  </header>

  {% if not lines %}
    <div class="empty">No audit events yet. Run the pipeline to generate events.</div>
  {% else %}
    {% for line in lines %}
    <div class="line">{{ line }}</div>
    {% endfor %}
  {% endif %}
</div>
</body>
</html>
"""

def load_queue():
    if not APPROVALS_FILE.exists():
        return []
    return json.loads(APPROVALS_FILE.read_text() or "[]")


def save_queue(queue):
    APPROVALS_FILE.write_text(json.dumps(queue, indent=2))


@app.route("/")
def index():
    queue = load_queue()
    tickets = queue
    stats = {
        "total": len(tickets),
        "pending": sum(1 for t in tickets if t.get("status") == "pending"),
        "approved": sum(1 for t in tickets if t.get("status") == "approved"),
        "rejected": sum(1 for t in tickets if t.get("status") == "rejected"),
    }
    return render_template_string(HTML, tickets=tickets, **stats)


@app.route("/action/<ticket_id>/<decision>")
def action(ticket_id, decision):
    queue = load_queue()
    for t in queue:
        if t.get("ticket") == ticket_id and t.get("status") == "pending":
            t["status"] = "approved" if decision == "approve" else "rejected"
            break
    save_queue(queue)
    return redirect(url_for("index"))


@app.route("/audit")
def audit():
    lines = []
    if AUDIT_FILE.exists():
        lines = [l.rstrip("\n") for l in AUDIT_FILE.read_text().splitlines() if l.strip()]
        lines = lines[-50:]  # last 50 lines
    return render_template_string(AUDIT_HTML, lines=lines)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)