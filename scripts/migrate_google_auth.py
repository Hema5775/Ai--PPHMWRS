"""
Safe, idempotent database migration script for Google OAuth support.
Adds the 'auth_provider' column to the 'users' table if it does not already exist,
preserving all existing user records, health profiles, and activity data.
"""

import sys
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DB = BASE_DIR / "instance" / "wellness.db"


def run_migration(db_path: Path = INSTANCE_DB):
    if not db_path.exists():
        print(f"[INFO] Database file not found at {db_path}. Nothing to migrate.")
        return

    print(f"[INFO] Running migration on {db_path}...")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Check existing columns in 'users'
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"[INFO] Existing columns in 'users': {columns}")

        if "auth_provider" not in columns:
            print("[INFO] Adding 'auth_provider' column with default 'local'...")
            cursor.execute("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(50) DEFAULT 'local'")
            conn.commit()
            print("[SUCCESS] Column 'auth_provider' added successfully.")
        else:
            print("[INFO] Column 'auth_provider' already exists. Skipping.")

        # Verify existing users data
        cursor.execute("SELECT id, email, role, auth_provider, google_id FROM users")
        rows = cursor.fetchall()
        print(f"[INFO] Total users verified: {len(rows)}")
        for r in rows:
            print(f"  - User #{r[0]}: {r[1]} (role={r[2]}, auth_provider={r[3]}, google_id={r[4]})")

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run_migration()
