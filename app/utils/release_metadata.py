import os
from datetime import datetime


def _database_last_modified_iso(app) -> str:
    db_path = app.config.get("DATABASE_PATH") or "weeds.db"
    absolute_db_path = db_path if os.path.isabs(db_path) else os.path.abspath(db_path)
    if os.path.exists(absolute_db_path):
        return datetime.fromtimestamp(os.path.getmtime(absolute_db_path)).isoformat()
    return ""


def _date_label(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw[:10]
    return parsed.date().isoformat()


def build_release_metadata(app) -> dict:
    version = (
        app.config.get("DATA_RELEASE_VERSION")
        or app.config.get("DATA_VERSION")
        or ""
    )
    generated_at = app.config.get("DATA_RELEASE_GENERATED_AT") or ""
    last_updated = app.config.get("DATA_RELEASE_LAST_UPDATED") or ""
    timestamp = generated_at or last_updated or _database_last_modified_iso(app)
    date_kind = "generated" if generated_at else "refreshed"

    return {
        "version": str(version or "").strip(),
        "timestamp": timestamp,
        "date_label": _date_label(timestamp),
        "date_kind": date_kind,
    }
