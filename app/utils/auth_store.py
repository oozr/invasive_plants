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


def normalize_affiliation_name(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def parse_allowed_domains(value) -> tuple:
    if isinstance(value, (list, tuple, set)):
        raw_parts = value
    else:
        raw_parts = str(value or "").split(",")

    domains = []
    for raw in raw_parts:
        domain = str(raw or "").strip().lower()
        if not domain:
            continue
        domains.append(domain.lstrip("@"))
    return tuple(domains)


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


def is_allowed_researcher_email(email: str, allowed_suffixes, allowed_domains=None) -> bool:
    normalized = normalize_email(email)
    domain = email_domain(normalized)
    if not normalized or not domain:
        return False
    if domain in parse_allowed_domains(allowed_domains):
        return True
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
                    affiliation_name TEXT NOT NULL DEFAULT '',
                    affiliation_ror_id TEXT,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT NOT NULL
                )
                """
            )
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(researcher_logins)").fetchall()}
            if "email_domain" in columns or "affiliation_name" not in columns or "affiliation_ror_id" not in columns:
                conn.execute(
                    """
                    CREATE TABLE researcher_logins_new (
                        email TEXT PRIMARY KEY,
                        affiliation_name TEXT NOT NULL DEFAULT '',
                        affiliation_ror_id TEXT,
                        created_at TEXT NOT NULL,
                        last_login_at TEXT NOT NULL
                    )
                    """
                )
                affiliation_expr = (
                    "COALESCE(NULLIF(TRIM(affiliation_name), ''), '')"
                    if "affiliation_name" in columns
                    else "''"
                )
                ror_expr = (
                    "COALESCE(NULLIF(TRIM(affiliation_ror_id), ''), NULL)"
                    if "affiliation_ror_id" in columns
                    else "NULL"
                )
                conn.execute(
                    f"""
                    INSERT OR REPLACE INTO researcher_logins_new (email, affiliation_name, affiliation_ror_id, created_at, last_login_at)
                    SELECT email, {affiliation_expr}, {ror_expr}, created_at, last_login_at
                    FROM researcher_logins
                    """
                )
                conn.execute("DROP TABLE researcher_logins")
                conn.execute("ALTER TABLE researcher_logins_new RENAME TO researcher_logins")
            conn.commit()
        finally:
            conn.close()

    def record_login(self, email: str, affiliation_name: str, affiliation_ror_id: str = None):
        normalized = normalize_email(email)
        affiliation = normalize_affiliation_name(affiliation_name)
        ror_id = str(affiliation_ror_id or "").strip() or None
        now = utc_now_iso()

        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO researcher_logins (email, affiliation_name, affiliation_ror_id, created_at, last_login_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    affiliation_name = excluded.affiliation_name,
                    affiliation_ror_id = excluded.affiliation_ror_id,
                    last_login_at = excluded.last_login_at
                """,
                (normalized, affiliation, ror_id, now, now),
            )
            conn.commit()
        finally:
            conn.close()
