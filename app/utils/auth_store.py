import os
import sqlite3
from datetime import datetime, timezone
from email.utils import parseaddr


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_email(value: str) -> str:
    _, parsed = parseaddr(value or "")
    return parsed.strip().lower()


def email_domain(email: str) -> str:
    if "@" not in email:
        return ""
    return email.rsplit("@", 1)[1].strip().lower()


def parse_allowed_suffixes(value) -> tuple:
    if isinstance(value, (list, tuple, set)):
        raw_parts = value
    else:
        raw_parts = str(value or ".edu,.gov").split(",")

    suffixes = []
    for raw in raw_parts:
        suffix = str(raw or "").strip().lower()
        if not suffix:
            continue
        if not suffix.startswith("."):
            suffix = f".{suffix}"
        suffixes.append(suffix)
    return tuple(suffixes)


def is_allowed_researcher_email(email: str, allowed_suffixes) -> bool:
    normalized = normalize_email(email)
    domain = email_domain(normalized)
    if not normalized or not domain:
        return False
    return any(domain.endswith(suffix) for suffix in parse_allowed_suffixes(allowed_suffixes))


class AuthStore:
    def __init__(self, db_path: str, project_root: str):
        self.db_path = self._resolve_path(db_path, project_root)
        self._ensure_schema()

    @staticmethod
    def _resolve_path(path: str, project_root: str) -> str:
        configured = path or "auth_users.db"
        if os.path.isabs(configured):
            return configured
        return os.path.abspath(os.path.join(project_root, configured))

    def _connect(self):
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        conn = self._connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS researcher_logins (
                    email TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(researcher_logins)").fetchall()}
            if "email_domain" in columns:
                conn.execute(
                    """
                    CREATE TABLE researcher_logins_new (
                        email TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        last_login_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO researcher_logins_new (email, created_at, last_login_at)
                    SELECT email, created_at, last_login_at
                    FROM researcher_logins
                    """
                )
                conn.execute("DROP TABLE researcher_logins")
                conn.execute("ALTER TABLE researcher_logins_new RENAME TO researcher_logins")
            conn.commit()
        finally:
            conn.close()

    def record_login(self, email: str):
        normalized = normalize_email(email)
        now = utc_now_iso()

        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO researcher_logins (email, created_at, last_login_at)
                VALUES (?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    last_login_at = excluded.last_login_at
                """,
                (normalized, now, now),
            )
            conn.commit()
        finally:
            conn.close()
