"""
app.py – FairShift Flask Application
Dual-mode Database Engine:
  - Defaults to local SQLite (`fairshift.db`) for instant local preview/testing.
  - Automatically switches to cloud PostgreSQL when `DATABASE_URL` is set (for Vercel serverless).
"""

import os
from datetime import datetime, date
from flask import Flask, request, jsonify, render_template

DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor
else:
    import sqlite3

# ── App Configuration ────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(32))

LOCAL_SQLITE_PATH = os.getenv("FAIRSHIFT_DB", "fairshift.db")


# ── Dual Database Connection Helper ──────────────────────────────
class DBWrapper:
    def __init__(self, conn, is_pg=False):
        self.conn = conn
        self.is_pg = is_pg

    def cursor(self):
        return self.conn.cursor()

    def execute(self, sql, params=None):
        if not self.is_pg:
            # Convert PostgreSQL '%s' parameter syntax to SQLite '?' parameter syntax
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PAGE ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/init-db", methods=["GET", "POST"])
def auto_init_db():
    """
    Convenient one-click endpoint to initialize Neon tables
    directly from the browser once deployed to Vercel.
    """
    try:
        from init_neon_tables import init
        msg = init()
        return jsonify({"status": "success", "message": msg}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/")
@app.route("/worker")
def worker_page():
    return render_template("worker.html")


@app.route("/admin")
def admin_page():
    return render_template("admin.html")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API – WORKERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/workers", methods=["GET"])
def list_workers():
    db = get_db()
    cur = db.execute("SELECT id, name, industry, language_pref FROM workers ORDER BY id ASC")
    rows = [dict(r) for r in cur.fetchall()]
    db.close()
    return jsonify(rows)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API – SHIFT TRACKING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/clock-in", methods=["POST"])
def clock_in():
    data = request.get_json(force=True)
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
    if cur.fetchone():
        db.close()
        return jsonify({"error": "Already clocked in today"}), 409

    db.execute(
        "INSERT INTO shifts (worker_id, clock_in, date) VALUES (%s, %s, %s)",
        (worker_id, now.isoformat(), today)
    )
    db.commit()
    db.close()
    return jsonify({"message": "Clocked in", "time": now.isoformat()}), 201


@app.route("/api/clock-out", methods=["POST"])
def clock_out():
    data = request.get_json(force=True)
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
    return jsonify({"message": "Clocked out", "time": now.isoformat()}), 200


@app.route("/api/shift-status/<int:worker_id>", methods=["GET"])
def shift_status(worker_id):
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
#  API – SAFETY / HAZARD REPORTING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/hazard-report", methods=["POST"])
def submit_hazard():
    data = request.get_json(force=True)
    required = ("industry", "description", "severity")
    missing = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    if data["industry"] not in ("campus", "construction"):
        return jsonify({"error": "Industry must be 'campus' or 'construction'"}), 400
    if data["severity"] not in ("low", "medium", "high"):
        return jsonify({"error": "Severity must be 'low', 'medium', or 'high'"}), 400

    db = get_db()
    db.execute(
        "INSERT INTO hazard_reports (industry, location, description, severity) VALUES (%s, %s, %s, %s)",
        (data["industry"], data.get("location", ""), data["description"], data["severity"])
    )
    db.commit()
    db.close()
    return jsonify({"message": "Hazard report submitted anonymously"}), 201


@app.route("/api/hazards", methods=["GET"])
def list_hazards():
    industry = request.args.get("industry")
    db = get_db()
    if industry:
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
    return jsonify({"message": "Report escalated"})


@app.route("/api/hazard/<int:hazard_id>/resolve", methods=["POST"])
def resolve_hazard(hazard_id):
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
    return jsonify({"message": "Report resolved"})


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API – ATTENDANCE (Admin Dashboard)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/attendance", methods=["GET"])
def attendance():
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
    if industry:
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
