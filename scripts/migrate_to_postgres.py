"""
Supabase / PostgreSQL Database Migration Script for Vitalis AI.

Safely migrates all existing records from the SQLite database (instance/wellness.db)
to a PostgreSQL / Supabase instance without altering or deleting the SQLite database.

Workflow:
1. Creates a safe timestamped backup of instance/wellness.db
2. Connects to target PostgreSQL / Supabase database
3. Initializes relational schema via SQLAlchemy metadata
4. Migrates all 10 tables preserving primary and foreign keys in dependency order
5. Updates PostgreSQL sequences to maintain auto-increment continuity
6. Verifies row counts across both databases
"""

import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy import create_engine, MetaData, Table, select, text
from sqlalchemy.orm import sessionmaker
from config import Config


TABLE_ORDER = [
    "model_versions",
    "users",
    "health_profiles",
    "daily_activities",
    "wellness_scores",
    "recommendations",
    "daily_tasks",
    "weekly_reports",
    "system_errors",
    "audit_logs",
]


def backup_sqlite_database(sqlite_path: Path) -> Path:
    """Create a timestamped backup copy of the SQLite database."""
    if not sqlite_path.exists():
        raise FileNotFoundError(f"Source database not found at {sqlite_path}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = sqlite_path.parent / f"wellness_backup_{timestamp}.db"
    shutil.copy2(sqlite_path, backup_path)
    print(f"[OK] Database backed up to: {backup_path}")
    return backup_path


def migrate(target_url: str = None, dry_run: bool = False):
    sqlite_path = BASE_DIR / "instance" / "wellness.db"
    sqlite_url = f"sqlite:///{sqlite_path}"

    if not target_url:
        target_url = os.getenv("TARGET_DATABASE_URL") or os.getenv("DATABASE_URL")

    if not target_url or "sqlite" in target_url:
        print("[INFO] No PostgreSQL / Supabase TARGET_DATABASE_URL configured.")
        print(f"[INFO] Source SQLite database: {sqlite_path} ({sqlite_path.stat().st_size if sqlite_path.exists() else 0} bytes)")
        print("[INFO] Migration script is ready for Supabase / PostgreSQL deployment.")
        print("[INFO] Usage: python scripts/migrate_to_postgres.py postgresql://user:password@host:port/dbname")
        return

    # Normalize postgres:// to postgresql://
    if target_url.startswith("postgres://"):
        target_url = target_url.replace("postgres://", "postgresql://", 1)

    print("=" * 60)
    print("VITALIS AI — SUPABASE / POSTGRESQL MIGRATION")
    print("=" * 60)

    # 1. Safe Backup
    backup_sqlite_database(sqlite_path)

    if dry_run:
        print("[DRY RUN] Backup completed. Skipping remote transfer.")
        return

    # 2. Engines
    print(f"[CONNECT] Connecting to source SQLite: {sqlite_url}")
    source_engine = create_engine(sqlite_url)
    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)

    print(f"[CONNECT] Connecting to target PostgreSQL/Supabase...")
    target_engine = create_engine(target_url, pool_pre_ping=True)

    # 3. Create tables on target
    from app.extensions import db
    from app import create_app
    app_instance = create_app("production")
    with app_instance.app_context():
        # Bind target engine to create tables
        db.metadata.create_all(bind=target_engine)
        print("[OK] All application tables initialized on target database.")

    # 4. Copy records table by table
    target_metadata = MetaData()
    target_metadata.reflect(bind=target_engine)

    with source_engine.connect() as src_conn, target_engine.begin() as tgt_conn:
        for tbl_name in TABLE_ORDER:
            if tbl_name not in source_metadata.tables:
                print(f"[-] Table '{tbl_name}' not in source, skipping.")
                continue

            src_table = source_metadata.tables[tbl_name]
            tgt_table = target_metadata.tables[tbl_name]

            rows = src_conn.execute(select(src_table)).mappings().all()
            row_count = len(rows)

            if row_count == 0:
                print(f"[>] Table '{tbl_name}': 0 rows to migrate.")
                continue

            # Convert row mappings to dicts
            data = [dict(row) for row in rows]
            tgt_conn.execute(tgt_table.insert(), data)
            print(f"[OK] Migrated {row_count} rows for table '{tbl_name}'.")

            # Update PostgreSQL sequence if table has serial 'id'
            try:
                tgt_conn.execute(text(f"""
                    SELECT setval(pg_get_serial_sequence('{tbl_name}', 'id'), COALESCE(max(id), 1))
                    FROM {tbl_name};
                """))
            except Exception:
                pass  # Non-serial or non-Postgres sequence

    # 5. Verification
    print("-" * 60)
    print("VERIFICATION OF ROW COUNTS:")
    with source_engine.connect() as src_conn, target_engine.connect() as tgt_conn:
        all_match = True
        for tbl_name in TABLE_ORDER:
            if tbl_name in source_metadata.tables:
                src_count = src_conn.execute(text(f"SELECT COUNT(*) FROM {tbl_name}")).scalar()
                tgt_count = tgt_conn.execute(text(f"SELECT COUNT(*) FROM {tbl_name}")).scalar()
                status = "MATCH" if src_count == tgt_count else "MISMATCH"
                if status == "MISMATCH":
                    all_match = False
                print(f"  {tbl_name:<20}: Source={src_count:<5} Target={tgt_count:<5} [{status}]")

    print("-" * 60)
    if all_match:
        print("[SUCCESS] All records successfully migrated to PostgreSQL / Supabase!")
        print("[NOTE] The SQLite database at instance/wellness.db has been safely preserved.")
        print("[NOTE] Update DATABASE_URL in your .env file to switch to Supabase.")
    else:
        print("[WARNING] Discrepancies detected during row count verification.")
    print("=" * 60)


if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else None
    migrate(target_url=url_arg)
