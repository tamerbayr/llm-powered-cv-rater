"""
tablolar:
    jobs - ilan ve işlenmiş gereksinimler
    cvs - işlenmiş cv
    scores - job veya cv skorları
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path("./data/recruitment.db")

def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(DB_PATH)
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA journal_mode=WAL")
    return database

def init_db():
    with _connect() as database:
        database.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                filename     TEXT NOT NULL UNIQUE,
                title        TEXT,
                raw_text     TEXT,
                requirements TEXT,
                created_at   TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS cvs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                filename   TEXT NOT NULL UNIQUE,
                parsed     TEXT,
                file_hash  TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS scores (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id          INTEGER NOT NULL REFERENCES jobs(id),
                cv_id           INTEGER NOT NULL REFERENCES cvs(id),
                overall_score   REAL,
                details         TEXT,
                logistics_notes TEXT,
                scored_at       TEXT DEFAULT (datetime('now')),
                UNIQUE(job_id, cv_id)
            );
        """)


# --JOB

def is_job_changed(filename, raw_text):
    """ilan içeriği değişmişse True"""
    existing = get_job_by_filename(filename)
    if not existing:
        return True
    return existing.get("raw_text", "") != raw_text #hashlib eklenebilir?


def upsert_job(filename, title, raw_text, requirements):
    """iş ilanını ekler veya günceller, ID döndürür"""
    with _connect() as database:
        database.execute("""
            INSERT INTO jobs (filename, title, raw_text, requirements)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                title        = excluded.title,
                raw_text     = excluded.raw_text,
                requirements = excluded.requirements
        """, (filename, title, raw_text, json.dumps(requirements, ensure_ascii=False)))
        return database.execute("SELECT id FROM jobs WHERE filename = ?", (filename,)).fetchone()["id"]


def list_jobs():
    with _connect() as database:
        rows = database.execute(
            "SELECT id, filename, title, created_at FROM jobs ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_job_by_id(job_id) -> dict | None:
    with _connect() as database:
        a = database.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not a:
            return None
        result = dict(a)
        result["requirements"] = json.loads(result["requirements"] or "[]")
        return result


def get_job_by_filename(filename) -> dict | None:
    with _connect() as database:
        row = database.execute("SELECT * FROM jobs WHERE filename = ?", (filename,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["requirements"] = json.loads(d["requirements"] or "[]")
        return d


def delete_job(filename):
    with _connect() as database:
        a = database.execute("SELECT id FROM jobs WHERE filename = ?", (filename,)).fetchone()
        if a:
            database.execute("DELETE FROM scores WHERE job_id = ?", (a["id"],))
            database.execute("DELETE FROM jobs WHERE filename = ?", (filename,))
        else:
            print(f"HATA: İlan bulunamadı: {filename}")


# --CV

def upsert_cv(filename, parsed: dict, file_hash):
    """cv'yi ekler veya günceller, ID döndürür"""
    with _connect() as database:
        database.execute("""
            INSERT INTO cvs (filename, parsed, file_hash)
            VALUES (?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                parsed    = excluded.parsed,
                file_hash = excluded.file_hash
        """, (filename, json.dumps(parsed, ensure_ascii=False, default=str), file_hash))
        return database.execute("SELECT id FROM cvs WHERE filename = ?", (filename,)).fetchone()["id"]


def get_all_cvs():
    with _connect() as database:
        rows = database.execute("SELECT * FROM cvs ORDER BY filename").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["parsed"] = json.loads(d["parsed"] or "{}")
            result.append(d)
        return result


def delete_cv(filename):
    with _connect() as database:
        row = database.execute("SELECT id FROM cvs WHERE filename = ?", (filename,)).fetchone()
        if row:
            database.execute("DELETE FROM scores WHERE cv_id = ?", (row["id"],))
            database.execute("DELETE FROM cvs WHERE filename = ?", (filename,))


# -score

def upsert_score(job_id, cv_id, match_result):
    """skoru ekler ve aynı job-cv çifti varsa günceller"""
    with _connect() as database:
        database.execute("""
            INSERT INTO scores (job_id, cv_id, overall_score, details, logistics_notes, scored_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(job_id, cv_id) DO UPDATE SET
                overall_score   = excluded.overall_score,
                details         = excluded.details,
                logistics_notes = excluded.logistics_notes,
                scored_at       = excluded.scored_at
        """, (
            job_id,
            cv_id,
            match_result["overall_score"],
            json.dumps(match_result.get("details", []), ensure_ascii=False),
            json.dumps(match_result.get("logistics_notes", []), ensure_ascii=False),
        ))


def get_scores_for_job(job_id) -> list[dict]:
    """ilana göre skor ve cv bilgisi döndürür"""
    with _connect() as database:
        rows = database.execute("""
            SELECT s.overall_score, s.details, s.logistics_notes, s.scored_at,
                   c.filename AS cv_filename, c.id AS cv_id
            FROM scores s
            JOIN cvs c ON c.id = s.cv_id
            WHERE s.job_id = ?
            ORDER BY s.overall_score DESC
        """, (job_id,)).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["details"] = json.loads(d["details"] or "[]")
            d["logistics_notes"] = json.loads(d["logistics_notes"] or "[]")
            result.append(d)
        return result