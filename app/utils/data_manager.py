import hashlib
import json
import os
import threading
import time
import urllib.parse
import urllib.request


class DataManager:
    def __init__(
        self,
        app,
        mode: str,
        base_url: str,
        token: str,
        manifest_path: str,
        cache_dir: str,
        manifest_ttl_seconds: int = 3600,
    ):
        self.app = app
        self.mode = (mode or "local_sample").strip()
        self.base_url = (base_url or "").strip()
        self.token = (token or "").strip()
        self.manifest_path = manifest_path or "/manifest.json"
        self.cache_dir = cache_dir or "data_cache"
        self.manifest_ttl_seconds = max(0, int(manifest_ttl_seconds or 0))
        self.last_checked = 0.0
        self.current_version = None
        self.lock = threading.Lock()

    @classmethod
    def from_app(cls, app):
        return cls(
            app=app,
            mode=app.config.get("DATA_MODE", "local_sample"),
            base_url=app.config.get("DATA_REMOTE_BASE_URL"),
            token=app.config.get("DATA_REMOTE_TOKEN"),
            manifest_path=app.config.get("DATA_MANIFEST_PATH", "/manifest.json"),
            cache_dir=app.config.get("DATA_CACHE_DIR", "data_cache"),
            manifest_ttl_seconds=app.config.get("DATA_MANIFEST_TTL_SECONDS", 3600),
        )

    def ensure_ready(self, force: bool = False):
        if self.mode != "remote_production":
            data_paths = self._local_paths()
            self._apply_data_paths(data_paths, version="local_sample")
            return data_paths

        if not self.base_url:
            raise ValueError("DATA_REMOTE_BASE_URL is required for remote_production mode")

        with self.lock:
            if not force and self._within_ttl():
                return self._current_paths()

            self.last_checked = time.time()
            try:
                data_paths, version, changed = self._sync_remote_data()
                self._apply_data_paths(data_paths, version=version, changed=changed)
                return data_paths
            except Exception as exc:
                if self._cache_is_ready():
                    self.app.logger.error(f"Data refresh failed; using cached artifacts: {exc}")
                    return self._current_paths()
                raise

    def maybe_refresh(self):
        if self.mode != "remote_production" or self.manifest_ttl_seconds <= 0:
            return
        if self._within_ttl():
            return
        try:
            self.ensure_ready(force=True)
        except Exception as exc:
            self.app.logger.error(f"Periodic data refresh failed: {exc}")

    def _within_ttl(self) -> bool:
        if self.manifest_ttl_seconds <= 0:
            return False
        if self.last_checked <= 0:
            return False
        return (time.time() - self.last_checked) < self.manifest_ttl_seconds

    def _project_root(self) -> str:
        return os.path.abspath(os.path.join(self.app.root_path, os.pardir))

    def _resolve_path(self, path: str) -> str:
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(self._project_root(), path))

    def _local_paths(self) -> dict:
        db_path = self._resolve_path(self.app.config.get("LOCAL_SAMPLE_DB_PATH", "weeds.db"))
        csv_path = self._resolve_path(
            self.app.config.get(
                "LOCAL_SAMPLE_CSV_PATH",
                os.path.join("app", "static", "data", "regulatory_sources.csv"),
            )
        )
        geojson_dir = self._resolve_path(
            self.app.config.get(
                "LOCAL_SAMPLE_GEOJSON_DIR",
                os.path.join("app", "static", "data", "geographic"),
            )
        )
        return {
            "database_path": db_path,
            "regulatory_sources_path": csv_path,
            "geojson_dir": geojson_dir,
            "geojson_url_path": "/data/geojson/",
        }

    def _current_paths(self) -> dict:
        return {
            "database_path": self.app.config.get("DATABASE_PATH"),
            "regulatory_sources_path": self.app.config.get("REGULATORY_SOURCES_PATH"),
            "geojson_dir": self.app.config.get("GEOJSON_DIR"),
            "geojson_url_path": self.app.config.get("GEOJSON_URL_PATH", "/data/geojson/"),
        }

    def _cache_is_ready(self) -> bool:
        db_path = self.app.config.get("DATABASE_PATH")
        csv_path = self.app.config.get("REGULATORY_SOURCES_PATH")
        geojson_dir = self.app.config.get("GEOJSON_DIR")
        if not db_path or not csv_path or not geojson_dir:
            return False
        return os.path.exists(db_path) and os.path.exists(csv_path) and os.path.isdir(geojson_dir)

    def _cache_paths_ready(self, cache_dir: str) -> bool:
        db_path = os.path.join(cache_dir, "weeds.db")
        csv_path = os.path.join(cache_dir, "regulatory_sources.csv")
        geojson_dir = os.path.join(cache_dir, "geojson")
        if not (os.path.exists(db_path) and os.path.exists(csv_path) and os.path.isdir(geojson_dir)):
            return False
        return any(name.lower().endswith(".geojson") for name in os.listdir(geojson_dir))

    def _apply_data_paths(self, data_paths: dict, version: str = None, changed: bool = False):
        if not data_paths:
            return
        self.app.config["DATABASE_PATH"] = data_paths["database_path"]
        self.app.config["REGULATORY_SOURCES_PATH"] = data_paths["regulatory_sources_path"]
        self.app.config["GEOJSON_DIR"] = data_paths["geojson_dir"]
        self.app.config["GEOJSON_URL_PATH"] = data_paths.get("geojson_url_path", "/data/geojson/")
        if version:
            self.app.config["DATA_VERSION"] = version

        if changed or version != self.current_version:
            self.app.extensions.pop("state_db", None)
            self.app.extensions.pop("species_db", None)

        self.current_version = version

    def _sync_remote_data(self):
        cache_dir = self._resolve_path(self.cache_dir)
        os.makedirs(cache_dir, exist_ok=True)

        manifest_url = urllib.parse.urljoin(self.base_url.rstrip("/") + "/", self.manifest_path.lstrip("/"))
        manifest = self._fetch_json(manifest_url)
        local_manifest_path = os.path.join(cache_dir, "manifest.json")
        local_manifest = self._read_json(local_manifest_path)

        changed = manifest != local_manifest
        version = (
            manifest.get("version")
            or manifest.get("generated_at")
            or manifest.get("last_updated")
            or "remote"
        )

        cache_ready = self._cache_paths_ready(cache_dir)
        if changed or not cache_ready:
            self._download_artifacts(manifest, cache_dir)
            self._write_json(local_manifest_path, manifest)
            if not cache_ready:
                changed = True

        data_paths = {
            "database_path": os.path.join(cache_dir, "weeds.db"),
            "regulatory_sources_path": os.path.join(cache_dir, "regulatory_sources.csv"),
            "geojson_dir": os.path.join(cache_dir, "geojson"),
            "geojson_url_path": "/data/geojson/",
        }
        return data_paths, version, changed

    def _download_artifacts(self, manifest: dict, cache_dir: str):
        artifacts = manifest.get("artifacts", {})
        db_entry = artifacts.get("weeds_db") or manifest.get("weeds_db")
        csv_entry = artifacts.get("regulatory_sources_csv") or manifest.get("regulatory_sources_csv")
        geojson_files = manifest.get("geojson_files") or manifest.get("geojson", {}).get("files") or []
        geojson_base = (
            artifacts.get("geojson_base_path")
            or manifest.get("geojson_base_path")
            or "/artifacts/geojson"
        )

        if not db_entry:
            raise ValueError("Manifest missing weeds_db artifact")
        if not csv_entry:
            raise ValueError("Manifest missing regulatory_sources_csv artifact")

        db_entry = self._normalize_entry(db_entry)
        csv_entry = self._normalize_entry(csv_entry)

        self._download_entry(db_entry, os.path.join(cache_dir, "weeds.db"))
        self._download_entry(csv_entry, os.path.join(cache_dir, "regulatory_sources.csv"))

        geojson_dir = os.path.join(cache_dir, "geojson")
        os.makedirs(geojson_dir, exist_ok=True)

        for item in geojson_files:
            if isinstance(item, str):
                entry = {"path": self._join_path(geojson_base, item)}
            else:
                entry = self._normalize_entry(item)
                if not entry.get("path"):
                    name = entry.get("name") or entry.get("filename")
                    if name:
                        entry["path"] = self._join_path(geojson_base, name)
                    else:
                        continue

            filename = os.path.basename(entry["path"])
            if not filename:
                continue
            dest_path = os.path.join(geojson_dir, filename)
            self._download_entry(entry, dest_path)

    def _normalize_entry(self, entry):
        if isinstance(entry, dict):
            return dict(entry)
        if isinstance(entry, str):
            return {"path": entry}
        return {}

    def _join_path(self, base: str, name: str) -> str:
        base = (base or "").rstrip("/")
        name = (name or "").lstrip("/")
        return f"{base}/{name}"

    def _download_entry(self, entry: dict, dest_path: str):
        path = entry.get("path")
        if not path:
            return
        url = urllib.parse.urljoin(self.base_url.rstrip("/") + "/", path.lstrip("/"))
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        headers["Accept"] = "application/octet-stream"
        data = self._fetch_bytes(url, headers=headers)

        tmp_path = dest_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, dest_path)

        expected = entry.get("sha256") or entry.get("checksum")
        if expected:
            actual = self._sha256(dest_path)
            if actual.lower() != expected.lower():
                raise ValueError(f"Checksum mismatch for {dest_path}")

    def _fetch_json(self, url: str) -> dict:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        data = self._fetch_bytes(url, headers=headers)
        return json.loads(data.decode("utf-8"))

    def _fetch_bytes(self, url: str, headers: dict = None) -> bytes:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def _sha256(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _read_json(self, path: str) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _write_json(self, path: str, data: dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
