"""
_migrate_auth.py
Safely migrates the existing users table to support email-based auth,
adds is_active column, and removes hard-coded demo seeding approach.
Run ONCE: python _migrate_auth.py
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "heat_risk.db")

def safe_add_column(cur, table, col, defn):
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
        print(f"  Added column: {table}.{col}")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print(f"  Already exists: {table}.{col}")
        else:
            raise

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("Migrating users table for email-based auth...")

# 1. Add email column (may already exist as nullable)
safe_add_column(cur, "users", "email_new", "TEXT")
safe_add_column(cur, "users", "is_active",  "INTEGER DEFAULT 1")

# 2. Copy existing email values into email_new (in case email column existed)
try:
    cur.execute("UPDATE users SET email_new = email WHERE email_new IS NULL")
    print("  Copied existing emails to email_new")
except Exception as e:
    print(f"  Note: {e}")

conn.commit()

# 3. Check if we need to rebuild users table with proper UNIQUE email constraint
cols = {c["name"] for c in cur.execute("PRAGMA table_info(users)").fetchall()}
print(f"  Current columns: {sorted(cols)}")

# Check if email has UNIQUE constraint by checking index
indexes = cur.execute("PRAGMA index_list(users)").fetchall()
has_email_unique = any("email" in (i["name"] or "") for i in indexes)

if not has_email_unique:
    print("  Rebuilding users table with UNIQUE email constraint...")
    # Create new table
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users_v2 (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name     TEXT NOT NULL,
        email         TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL CHECK(role IN ('Administrator','Health Officer','Field Officer')),
        username      TEXT,
        is_active     INTEGER DEFAULT 1,
        created_at    TEXT DEFAULT (datetime('now'))
    );
    """)
    # Copy existing users — use email_new or email, fallback to username@healthdept.local
    users = cur.execute("SELECT * FROM users").fetchall()
    for u in users:
        uid    = u["id"]
        fname  = u["full_name"] if "full_name" in u.keys() else "Staff User"
        pwhash = u["password_hash"]
        role   = u["role"]
        uname  = u["username"] if "username" in u.keys() else None

        # Determine email
        try:
            email = u["email_new"] or u["email"]
        except:
            email = None
        if not email and uname:
            email = f"{uname}@healthdept.local"
        elif not email:
            email = f"user{uid}@healthdept.local"

        cur.execute(
            "INSERT OR IGNORE INTO users_v2 (id,full_name,email,password_hash,role,username,is_active) VALUES (?,?,?,?,?,?,1)",
            (uid, fname, email, pwhash, role, uname)
        )
    print(f"  Migrated {len(users)} users to users_v2")

    # Drop old, rename new
    cur.executescript("""
    DROP TABLE users;
    ALTER TABLE users_v2 RENAME TO users;
    """)
    print("  users table rebuilt with UNIQUE email constraint")
else:
    print("  users table already has UNIQUE email index")

conn.commit()
conn.close()
print("Migration complete.")
