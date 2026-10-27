"""
init_db.py – Initialises the FairShift database with mock data.
Dual-mode:
  - If DATABASE_URL is set, connects to PostgreSQL.
  - Otherwise, seeds local SQLite ('fairshift.db') for instant local preview.
"""

import os
import sys
from datetime import datetime, timedelta

DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

if USE_POSTGRES:
    import psycopg2
else:
    import sqlite3


def get_connection():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    else:
        db_path = os.getenv("FAIRSHIFT_DB", "fairshift.db")
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass
        return sqlite3.connect(db_path)


def create_tables(conn):
    if USE_POSTGRES:
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
        with conn.cursor() as cur:
            cur.execute(schema)
    else:
        schema = """
        CREATE TABLE IF NOT EXISTS workers (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            industry      TEXT NOT NULL CHECK(industry IN ('campus', 'construction')),
            language_pref TEXT NOT NULL DEFAULT 'en'
        );

        CREATE TABLE IF NOT EXISTS shifts (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL REFERENCES workers(id),
            clock_in  TIMESTAMP NOT NULL,
            clock_out TIMESTAMP,
            date      DATE NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hazard_reports (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            industry    TEXT NOT NULL CHECK(industry IN ('campus', 'construction')),
            location    TEXT,
            description TEXT NOT NULL,
            severity    TEXT NOT NULL CHECK(severity IN ('low', 'medium', 'high')),
            status      TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open', 'escalated', 'resolved')),
            created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
        conn.executescript(schema)
    conn.commit()


def seed_mock_data(conn):
    workers = [
        ("Anbu Selvan",   "campus",       "ta"),
        ("Kavitha Ravi",  "campus",       "ta"),
        ("Raj Kumar",     "construction", "ta"),
        ("Meena Devi",    "construction", "ta"),
        ("Suresh Babu",   "campus",       "en"),
        ("Priya Lakshmi", "construction", "en"),
    ]

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    shifts = [
        (1, datetime.combine(yesterday, datetime.min.time().replace(hour=8)),
            datetime.combine(yesterday, datetime.min.time().replace(hour=16)), yesterday),
        (2, datetime.combine(yesterday, datetime.min.time().replace(hour=9)),
            datetime.combine(yesterday, datetime.min.time().replace(hour=17)), yesterday),
        (3, datetime.combine(today, datetime.min.time().replace(hour=7)),
            None, today),
        (4, datetime.combine(today, datetime.min.time().replace(hour=6, minute=30)),
            None, today),
        (5, datetime.combine(today, datetime.min.time().replace(hour=8)),
            datetime.combine(today, datetime.min.time().replace(hour=12)), today),
    ]

    hazards = [
        ("campus",       "Library Block B",        "Wet floor near staircase – no warning sign.",     "medium", "open"),
        ("construction", "Site 4 – East Wing",     "Loose scaffolding bolts on the third level.",     "high",   "open"),
        ("campus",       "Hostel Mess Kitchen",    "Gas leak smell reported by cleaning staff.",      "high",   "escalated"),
        ("construction", "Site 2 – Foundation",    "Workers lack hard-hats in active pour zone.",     "high",   "open"),
        ("campus",       "Admin Building Terrace", "Broken railing along terrace walkway.",           "medium", "open"),
    ]

    if USE_POSTGRES:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE shifts, hazard_reports, workers RESTART IDENTITY CASCADE;")
            cur.executemany("INSERT INTO workers (name, industry, language_pref) VALUES (%s, %s, %s)", workers)
            cur.executemany("INSERT INTO shifts (worker_id, clock_in, clock_out, date) VALUES (%s, %s, %s, %s)", shifts)
            cur.executemany("INSERT INTO hazard_reports (industry, location, description, severity, status) VALUES (%s, %s, %s, %s, %s)", hazards)
    else:
        cur = conn.cursor()
        cur.executemany("INSERT INTO workers (name, industry, language_pref) VALUES (?, ?, ?)", workers)
        cur.executemany("INSERT INTO shifts (worker_id, clock_in, clock_out, date) VALUES (?, ?, ?, ?)",
            [(w, ci.isoformat(), co.isoformat() if co else None, str(d)) for w, ci, co, d in shifts])
        cur.executemany("INSERT INTO hazard_reports (industry, location, description, severity, status) VALUES (?, ?, ?, ?, ?)", hazards)
    conn.commit()


def main():
    conn = get_connection()
    create_tables(conn)
    seed_mock_data(conn)
    conn.close()
    target = "Cloud PostgreSQL" if USE_POSTGRES else "Local SQLite (fairshift.db)"
    print(f"✔ Database initialized and seeded successfully [{target}].")


if __name__ == "__main__":
    main()
