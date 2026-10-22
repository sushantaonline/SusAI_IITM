
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "rfp_evaluation.db"


def get_connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evaluation_criteria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                weight REAL NOT NULL CHECK(weight >= 0 AND weight <= 100),
                max_score REAL NOT NULL DEFAULT 10,
                active INTEGER NOT NULL DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS rfp_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'CREATED'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS supplier_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                supplier_name TEXT NOT NULL,
                submission_date TEXT,
                experience_rating REAL,
                evaluation_json TEXT,
                absolute_weighted_score REAL,
                ppi REAL,
                rank INTEGER,
                FOREIGN KEY (run_id) REFERENCES rfp_runs(run_id)
            )
        """)

        criteria = [
            ("Technical Capability", 30),
            ("Implementation Plan", 20),
            ("Commercial Value", 20),
            ("Security & Compliance", 20),
            ("Support & Experience", 10),
        ]

        conn.executemany("""
            INSERT OR IGNORE INTO evaluation_criteria
                (name, weight, max_score, active)
            VALUES (?, ?, 10, 1)
        """, criteria)


if __name__ == "__main__":
    initialize_database()
    print(f"Database initialized: {DB_PATH}")


    
import json


def save_supplier_result(
    run_id,
    supplier_name,
    submission_date,
    experience_rating,
    evaluation,
    weighted_score,
    ppi,
    rank,
):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO supplier_results (
                run_id, supplier_name, submission_date,
                experience_rating, evaluation_json,
                absolute_weighted_score, ppi, rank
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                supplier_name,
                submission_date,
                experience_rating,
                json.dumps(evaluation),
                weighted_score,
                ppi,
                rank,
            ),
        )

