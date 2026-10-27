"""
app.py – FairShift: Mobile-First Workforce Management Platform
Target: UN SDG 8.8 (Decent Work & Safe Working Environments)
"""

import os
import re
import secrets
from datetime import datetime, date
from functools import wraps
from flask import Flask, request, jsonify, render_template

# ── App & Security Configuration ─────────────────────────────────
app = Flask(__name__)
# Cryptographically secure key with no exposed credentials
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))

DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
else:
    import sqlite3

LOCAL_SQLITE_PATH = os.getenv("FAIRSHIFT_DB", "fairshift.db")


# ── Security Headers Middleware (OWASP Compliance) ───────────────
@app.after_request
def set_security_headers(response):
    """Inject strict security headers to prevent XSS, clickjacking, and MIME-sniffing."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "microphone=(self)"
    return response


# ── Dual-Mode Database Connection Wrapper ────────────────────────
class DBWrapper:
    """Stateless DB adapter handling both SQLite (local) and PostgreSQL (cloud)."""
    def __init__(self, conn, is_pg=False):
        self.conn = conn
        self.is_pg = is_pg

    def execute(self, sql, params=None):
        if not self.is_pg:
            # Convert PostgreSQL parameterized %s syntax to SQLite ?
            sql = sql.replace("%s", "?")
        cur = self.conn.cursor()
        if params:
            cur.execute(sql, tuple(params))
        else:
            cur.execute(sql)
        return cur

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def get_db():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return DBWrapper(conn, is_pg=True)
    else:
        conn = sqlite3.connect(LOCAL_SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return DBWrapper(conn, is_pg=False)


# ── Input Sanitization Helper (Security) ─────────────────────────
def sanitize_text(text: str, max_length: int = 500) -> str:
    """Sanitize user input against injection and trim length."""
    if not text:
        return ""
    clean = re.sub(r"[<>]", "", str(text).strip())
    return clean[:max_length]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PAGE ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/init-db", methods=["GET", "POST"])
def auto_init_db():
    """One-click setup endpoint for cloud PostgreSQL on Vercel."""
    try:
        from init_neon_tables import init
        msg = init()
        return jsonify({"status": "success", "message": msg}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/")
@app.route("/worker")
def worker_page():
    """Mobile-first interface for campus support staff and construction workers."""
    return render_template("worker.html")


@app.route("/admin")
def admin_page():
    """Dual-interface admin dashboard tracking live attendance and hazards."""
    return render_template("admin.html")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API – WORKERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/workers", methods=["GET"])
def list_workers():
    """List registered workers for dual-industry workforce management."""
    db = get_db()
    cur = db.execute("SELECT id, name, industry, language_pref FROM workers ORDER BY id ASC")
    rows = [dict(r) for r in cur.fetchall()]
    db.close()
    return jsonify(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API – SHIFT TRACKING (SDG 8 Auditable Labor Records)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/clock-in", methods=["POST"])
def clock_in():
    """Clock in worker with tamper-resistant server timestamps."""
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    if not worker_id:
        return jsonify({"error": "worker_id is required"}), 400

    now = datetime.now()
    today = date.today().isoformat()
    db = get_db()

    # Prevent double clock-in
    cur = db.execute(
        "SELECT id FROM shifts WHERE worker_id = %s AND date = %s AND clock_out IS NULL",
        (worker_id, today)
    )
    if cur.fetchone():
        db.close()
        return jsonify({"error": "Already clocked in today"}), 409

    db.execute(
        "INSERT INTO shifts (worker_id, clock_in, date) VALUES (%s, %s, %s)",
        (worker_id, now.isoformat(), today)
    )
    db.commit()
    db.close()
    return jsonify({"message": "Clocked in successfully", "time": now.isoformat()}), 201


@app.route("/api/clock-out", methods=["POST"])
def clock_out():
    """Clock out worker and record completed shift duration."""
    data = request.get_json(silent=True) or {}
    worker_id = data.get("worker_id")
    if not worker_id:
        return jsonify({"error": "worker_id is required"}), 400

    now = datetime.now()
    today = date.today().isoformat()
    db = get_db()

    cur = db.execute(
        "SELECT id FROM shifts WHERE worker_id = %s AND date = %s AND clock_out IS NULL",
        (worker_id, today)
    )
    shift = cur.fetchone()
    if not shift:
        db.close()
        return jsonify({"error": "No open shift found for today"}), 404

    shift_id = dict(shift)["id"] if not isinstance(shift, dict) else shift["id"]
    db.execute(
        "UPDATE shifts SET clock_out = %s WHERE id = %s",
        (now.isoformat(), shift_id)
    )
    db.commit()
    db.close()
    return jsonify({"message": "Clocked out successfully", "time": now.isoformat()}), 200


@app.route("/api/shift-status/<int:worker_id>", methods=["GET"])
def shift_status(worker_id):
    """Retrieve current shift status for real-time mobile display."""
    today = date.today().isoformat()
    db = get_db()
    cur = db.execute(
        "SELECT id, clock_in FROM shifts WHERE worker_id = %s AND date = %s AND clock_out IS NULL",
        (worker_id, today)
    )
    shift = cur.fetchone()
    db.close()
    if shift:
        shift_data = dict(shift)
        cin = shift_data["clock_in"]
        clock_in_time = cin.isoformat() if hasattr(cin, "isoformat") else str(cin)
        return jsonify({"clocked_in": True, "clock_in": clock_in_time})
    return jsonify({"clocked_in": False})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API – ANONYMOUS SAFETY & HAZARD REPORTING (SDG 8.8)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/hazard-report", methods=["POST"])
def submit_hazard():
    """
    Submit hazard report anonymously with voice dictation support.
    Zero worker identity fields stored to eliminate retaliation risks.
    """
    data = request.get_json(silent=True) or {}
    required = ("industry", "description", "severity")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    industry = data.get("industry")
    severity = data.get("severity")
    location = sanitize_text(data.get("location", ""), max_length=150)
    description = sanitize_text(data.get("description", ""), max_length=1000)

    if industry not in ("campus", "construction"):
        return jsonify({"error": "Industry must be 'campus' or 'construction'"}), 400
    if severity not in ("low", "medium", "high"):
        return jsonify({"error": "Severity must be 'low', 'medium', or 'high'"}), 400
    if not description:
        return jsonify({"error": "Description cannot be empty"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO hazard_reports (industry, location, description, severity) VALUES (%s, %s, %s, %s)",
        (industry, location, description, severity)
    )
    db.commit()
    db.close()
    return jsonify({"message": "Hazard report submitted anonymously"}), 201


@app.route("/api/hazards", methods=["GET"])
def list_hazards():
    """Retrieve safety hazard queue with optional industry filtering."""
    industry = request.args.get("industry")
    db = get_db()
    if industry and industry in ("campus", "construction"):
        cur = db.execute("SELECT * FROM hazard_reports WHERE industry = %s ORDER BY created_at DESC", (industry,))
    else:
        cur = db.execute("SELECT * FROM hazard_reports ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    db.close()

    for r in rows:
        if "created_at" in r and hasattr(r["created_at"], "isoformat"):
            r["created_at"] = r["created_at"].isoformat()

    return jsonify(rows)


@app.route("/api/hazard/<int:hazard_id>/escalate", methods=["POST"])
def escalate_hazard(hazard_id):
    """Escalate high-risk hazard to site supervisors."""
    db = get_db()
    cur = db.execute(
        "UPDATE hazard_reports SET status = 'escalated' WHERE id = %s AND status = 'open'",
        (hazard_id,)
    )
    changed = cur.rowcount
    db.commit()
    db.close()
    if changed == 0:
        return jsonify({"error": "Report not found or already escalated/resolved"}), 404
    return jsonify({"message": "Report escalated successfully"})


@app.route("/api/hazard/<int:hazard_id>/resolve", methods=["POST"])
def resolve_hazard(hazard_id):
    """Mark verified hazard as remediated."""
    db = get_db()
    cur = db.execute(
        "UPDATE hazard_reports SET status = 'resolved' WHERE id = %s",
        (hazard_id,)
    )
    changed = cur.rowcount
    db.commit()
    db.close()
    if changed == 0:
        return jsonify({"error": "Report not found"}), 404
    return jsonify({"message": "Report resolved successfully"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API – LIVE ATTENDANCE DASHBOARD
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/attendance", methods=["GET"])
def attendance():
    """Live daily workforce presence query with zero N+1 latency."""
    today = date.today().isoformat()
    industry = request.args.get("industry")

    query = """
        SELECT w.id AS worker_id, w.name, w.industry,
               s.clock_in, s.clock_out
        FROM shifts s
        JOIN workers w ON s.worker_id = w.id
        WHERE s.date = %s
    """
    params = [today]
    if industry and industry in ("campus", "construction"):
        query += " AND w.industry = %s"
        params.append(industry)

    query += " ORDER BY s.clock_in DESC"

    db = get_db()
    cur = db.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    db.close()

    for r in rows:
        if r.get("clock_in") and hasattr(r["clock_in"], "isoformat"):
            r["clock_in"] = r["clock_in"].isoformat()
        if r.get("clock_out") and hasattr(r["clock_out"], "isoformat"):
            r["clock_out"] = r["clock_out"].isoformat()

    return jsonify(rows)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
