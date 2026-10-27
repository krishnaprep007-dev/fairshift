"""
init_neon_tables.py
A robust one-time setup script for PostgreSQL on Vercel at /api/init-db
"""

import traceback
from app import get_db

def init():
    try:
        db = get_db()
        cur = db.conn.cursor()
        
        schema = """
        CREATE TABLE IF NOT EXISTS workers (
            id            SERIAL PRIMARY KEY,
            name          VARCHAR(100) NOT NULL,
            industry      VARCHAR(20)  NOT NULL CHECK(industry IN ('campus', 'construction')),
            language_pref VARCHAR(10)  NOT NULL DEFAULT 'en'
        );

        CREATE TABLE IF NOT EXISTS shifts (
            id        SERIAL PRIMARY KEY,
            worker_id INTEGER NOT NULL REFERENCES workers(id),
            clock_in  TIMESTAMP NOT NULL,
            clock_out TIMESTAMP,
            date      DATE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hazard_reports (
            id          SERIAL PRIMARY KEY,
            industry    VARCHAR(20)  NOT NULL CHECK(industry IN ('campus', 'construction')),
            location    VARCHAR(255),
            description TEXT         NOT NULL,
            severity    VARCHAR(10)  NOT NULL CHECK(severity IN ('low', 'medium', 'high')),
            status      VARCHAR(15)  NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'escalated', 'resolved')),
            created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
        cur.execute(schema)
        
        # Check workers table count
        cur.execute("SELECT count(*) FROM workers;")
        res = cur.fetchone()
        count = res[0] if isinstance(res, (tuple, list)) else res.get("count", 0)
        
        if count == 0:
            workers = [
                ("Anbu Selvan",   "campus",       "ta"),
                ("Kavitha Ravi",  "campus",       "ta"),
                ("Raj Kumar",     "construction", "ta"),
                ("Meena Devi",    "construction", "ta"),
                ("Suresh Babu",   "campus",       "en"),
                ("Priya Lakshmi", "construction", "en"),
            ]
            cur.executemany("INSERT INTO workers (name, industry, language_pref) VALUES (%s, %s, %s);", workers)
        
        db.conn.commit()
        db.conn.close()
        return "Database initialized successfully"
    except Exception as e:
        return f"Error details: {str(e)} -> {traceback.format_exc()}"
