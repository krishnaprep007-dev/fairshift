"""
init_neon_tables.py
A one-time setup script that can also run on Vercel at /api/init-db
"""

from app import app, get_db

def init():
    db = get_db()
    
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
    
    with db.conn.cursor() as cur:
        cur.execute(schema)
        # Check if workers exist
        cur.execute("SELECT count(*) FROM workers")
        count = cur.fetchone()[0]
        if count == 0:
            workers = [
                ("Anbu Selvan",   "campus",       "ta"),
                ("Kavitha Ravi",  "campus",       "ta"),
                ("Raj Kumar",     "construction", "ta"),
                ("Meena Devi",    "construction", "ta"),
                ("Suresh Babu",   "campus",       "en"),
                ("Priya Lakshmi", "construction", "en"),
            ]
            cur.executemany("INSERT INTO workers (name, industry, language_pref) VALUES (%s, %s, %s)", workers)
    db.commit()
    db.close()
    return "Database initialized successfully"
