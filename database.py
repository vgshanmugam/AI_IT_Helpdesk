import sqlite3
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "tickets.db")

SLA_HOURS_MAP = {
    "High": 2,
    "Medium": 8,
    "Low": 24,
}


def get_sla_hours(priority: str) -> int:
    return SLA_HOURS_MAP.get(priority.strip().title(), 8)


def compute_sla_status(status: str, sla_due_at: str) -> str:
    if status in ("Resolved", "Closed"):
        return "Met"
    if not sla_due_at:
        return "On Track"
    try:
        due_dt = datetime.strptime(sla_due_at, "%Y-%m-%d %H:%M:%S")
        remaining_minutes = (due_dt - datetime.now()).total_seconds() / 60.0
        if remaining_minutes < 0:
            return "Breached"
        elif remaining_minutes <= 60:
            return "At Risk"
        return "On Track"
    except Exception:
        return "On Track"


def create_table():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue TEXT NOT NULL,
            category TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT,
            sla_hours INTEGER,
            sla_due_at TEXT
        )
    """)

    # Safely migrate existing tables if SLA columns are missing
    cursor.execute("PRAGMA table_info(tickets)")
    existing_cols = {row[1] for row in cursor.fetchall()}

    if "created_at" not in existing_cols:
        cursor.execute("ALTER TABLE tickets ADD COLUMN created_at TEXT")
    if "sla_hours" not in existing_cols:
        cursor.execute("ALTER TABLE tickets ADD COLUMN sla_hours INTEGER")
    if "sla_due_at" not in existing_cols:
        cursor.execute("ALTER TABLE tickets ADD COLUMN sla_due_at TEXT")

    # Backfill legacy rows so every ticket has valid SLA timestamps
    cursor.execute("SELECT ticket_id, priority FROM tickets WHERE created_at IS NULL OR sla_due_at IS NULL")
    legacy_rows = cursor.fetchall()
    now = datetime.now()
    for tid, prio in legacy_rows:
        hours = get_sla_hours(prio or "Medium")
        created_str = now.strftime("%Y-%m-%d %H:%M:%S")
        due_str = (now + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE tickets SET created_at = ?, sla_hours = ?, sla_due_at = ? WHERE ticket_id = ?",
            (created_str, hours, due_str, tid),
        )

    conn.commit()
    conn.close()


def create_ticket(issue, category, priority):
    create_table()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    norm_priority = priority.strip().title() if priority else "Medium"
    if norm_priority not in SLA_HOURS_MAP:
        norm_priority = "Medium"

    sla_hours = get_sla_hours(norm_priority)
    now = datetime.now()
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    sla_due_at = (now + timedelta(hours=sla_hours)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO tickets (issue, category, priority, status, created_at, sla_hours, sla_due_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (issue, category, norm_priority, "Open", created_at, sla_hours, sla_due_at))

    ticket_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return ticket_id


def get_all_tickets():
    create_table()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ticket_id, issue, category, priority, status, created_at, sla_hours, sla_due_at
        FROM tickets
        ORDER BY ticket_id DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    enriched = []
    for row in rows:
        tid, issue, category, priority, status, created_at, sla_hours, sla_due_at = row
        sla_status = compute_sla_status(status, sla_due_at)
        enriched.append((
            tid, issue, category, priority, status,
            created_at or "-", f"{sla_hours or 8}h", sla_due_at or "-", sla_status
        ))
    return enriched


def get_ticket_by_id(ticket_id: int):
    create_table()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT ticket_id, issue, category, priority, status, created_at, sla_hours, sla_due_at
        FROM tickets
        WHERE ticket_id = ?
    """, (ticket_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "ticket_id": f"HD-{row[0]:04d}",
        "raw_id": row[0],
        "issue": row[1],
        "category": row[2],
        "priority": row[3],
        "status": row[4],
        "created_at": row[5],
        "sla_hours": row[6],
        "sla_due_at": row[7],
        "sla_status": compute_sla_status(row[4], row[7]),
    }


def search_tickets(keyword: str = "", category: str = "", status: str = ""):
    create_table()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    query = """
        SELECT ticket_id, issue, category, priority, status, created_at, sla_hours, sla_due_at
        FROM tickets WHERE 1=1
    """
    params = []

    if keyword and keyword.strip():
        query += " AND LOWER(issue) LIKE ?"
        params.append(f"%{keyword.strip().lower()}%")

    if category and category.strip():
        query += " AND LOWER(category) = ?"
        params.append(category.strip().lower())

    if status and status.strip():
        query += " AND LOWER(status) = ?"
        params.append(status.strip().lower())

    query += " ORDER BY ticket_id DESC LIMIT 20"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for row in rows:
        results.append({
            "ticket_id": f"HD-{row[0]:04d}",
            "raw_id": row[0],
            "issue": row[1],
            "category": row[2],
            "priority": row[3],
            "status": row[4],
            "sla_due_at": row[7],
            "sla_status": compute_sla_status(row[4], row[7]),
        })
    return results


def update_ticket_status(ticket_id: int, new_status: str):
    create_table()
    valid_statuses = ["Open", "In Progress", "Resolved", "Closed"]
    normalized = new_status.strip().title()
    if normalized not in valid_statuses:
        return False, f"Invalid status '{new_status}'. Allowed values: {', '.join(valid_statuses)}"

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE tickets
        SET status = ?
        WHERE ticket_id = ?
    """, (normalized, ticket_id))

    updated_rows = cursor.rowcount
    conn.commit()
    conn.close()

    if updated_rows == 0:
        return False, f"Ticket HD-{ticket_id:04d} not found."

    return True, f"Ticket HD-{ticket_id:04d} status updated to '{normalized}'."