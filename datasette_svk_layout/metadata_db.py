import sqlite3
import json
from pathlib import Path


class MetadataDB:
    """SQLite-backed metadata store for database-level configuration.

    Stores titles, descriptions, and permissions per database.
    Integrates with Datasette's get_metadata hook.
    """

    ACTION_TO_METADATA_KEY = {
        "view-database": "allow",
        "execute-sql": "allow_sql",
    }

    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._cache = None
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS database_metadata (
                database_name TEXT PRIMARY KEY,
                title TEXT,
                description TEXT,
                source TEXT,
                license TEXT
            );

            CREATE TABLE IF NOT EXISTS database_permissions (
                database_name TEXT NOT NULL,
                action TEXT NOT NULL,
                actor_key TEXT NOT NULL,
                actor_value TEXT NOT NULL,
                PRIMARY KEY (database_name, action, actor_key, actor_value)
            );

            CREATE TABLE IF NOT EXISTS site_content (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS site_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                sort_order INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS site_news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                author TEXT NOT NULL,
                created TEXT NOT NULL DEFAULT (datetime('now')),
                updated TEXT
            );
        """)

    def _invalidate_cache(self):
        self._cache = None

    @staticmethod
    def _coerce_value(value):
        """Convert numeric strings back to int for Datasette allow-dict matching."""
        if value.isdigit():
            return int(value)
        return value

    # --- Read operations ---

    def get_database_metadata(self, database_name):
        """Return metadata dict for a database, or None if not found."""
        row = self._conn.execute(
            "SELECT title, description, source, license FROM database_metadata WHERE database_name = ?",
            (database_name,),
        ).fetchone()
        if row is None:
            return None
        return {k: row[k] for k in ("title", "description", "source", "license") if row[k] is not None}

    def get_database_permissions(self, database_name):
        """Return permissions as {action: {actor_key: [actor_values]}}."""
        rows = self._conn.execute(
            "SELECT action, actor_key, actor_value FROM database_permissions WHERE database_name = ? ORDER BY action, actor_key",
            (database_name,),
        ).fetchall()
        result = {}
        for row in rows:
            action = row["action"]
            key = row["actor_key"]
            value = row["actor_value"]
            result.setdefault(action, {}).setdefault(key, []).append(self._coerce_value(value))
        return result

    def _build_allow_dict(self, database_name, action):
        """Build a Datasette allow dict for a specific action."""
        rows = self._conn.execute(
            "SELECT actor_key, actor_value FROM database_permissions WHERE database_name = ? AND action = ?",
            (database_name, action),
        ).fetchall()
        if not rows:
            return None
        allow = {}
        for row in rows:
            allow.setdefault(row["actor_key"], []).append(self._coerce_value(row["actor_value"]))
        return allow

    def get_all_metadata_as_datasette_dict(self):
        """Return full metadata structure for the get_metadata hook.

        Returns: {"databases": {"db_name": {"title": ..., "allow": {...}, ...}}}
        Uses cache; invalidated on writes.
        """
        if self._cache is not None:
            return self._cache

        databases = {}

        # Load all metadata
        for row in self._conn.execute("SELECT * FROM database_metadata").fetchall():
            db_name = row["database_name"]
            entry = {}
            for col in ("title", "description", "source", "license"):
                if row[col] is not None:
                    entry[col] = row[col]
            if entry:
                databases[db_name] = entry

        # Load all permissions and assemble allow dicts
        perm_rows = self._conn.execute(
            "SELECT database_name, action, actor_key, actor_value FROM database_permissions ORDER BY database_name"
        ).fetchall()

        for row in perm_rows:
            db_name = row["database_name"]
            action = row["action"]
            metadata_key = self.ACTION_TO_METADATA_KEY.get(action)
            if metadata_key is None:
                continue
            db_entry = databases.setdefault(db_name, {})
            allow = db_entry.setdefault(metadata_key, {})
            allow.setdefault(row["actor_key"], []).append(self._coerce_value(row["actor_value"]))

        result = {"databases": databases} if databases else {}
        self._cache = result
        return result

    def list_databases(self, search=None, db_type=None):
        """List databases with optional filtering. Returns list of dicts.

        Includes databases from both database_metadata and database_permissions tables.
        """
        query = """
            SELECT
                d.database_name,
                m.title,
                m.description,
                m.source,
                m.license
            FROM (
                SELECT database_name FROM database_metadata
                UNION
                SELECT DISTINCT database_name FROM database_permissions
            ) d
            LEFT JOIN database_metadata m ON d.database_name = m.database_name
        """
        params = []
        conditions = []

        if search:
            conditions.append("(d.database_name LIKE ? OR m.title LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        if db_type:
            conditions.append("d.database_name LIKE ?")
            params.append(f"{db_type}_%")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY d.database_name"

        rows = self._conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    # --- Write operations ---

    def set_database_metadata(self, database_name, title=None, description=None, source=None, license=None):
        """Upsert database metadata."""
        self._conn.execute(
            """INSERT INTO database_metadata (database_name, title, description, source, license)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(database_name) DO UPDATE SET
                   title = COALESCE(excluded.title, title),
                   description = COALESCE(excluded.description, description),
                   source = COALESCE(excluded.source, source),
                   license = COALESCE(excluded.license, license)""",
            (database_name, title, description, source, license),
        )
        self._conn.commit()
        self._invalidate_cache()

    def update_database_metadata(self, database_name, **kwargs):
        """Update specific fields for a database. Pass field=None to clear it."""
        allowed = {"title", "description", "source", "license"}
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [database_name]
        self._conn.execute(
            f"UPDATE database_metadata SET {set_clause} WHERE database_name = ?",
            values,
        )
        self._conn.commit()
        self._invalidate_cache()

    def set_database_permissions(self, database_name, action, allow_dict):
        """Replace all permission rows for (database, action) with new allow_dict.

        allow_dict format: {"organizations_ids": ["510"]} or {"permissions": ["access.search_admin"]}
        Pass empty dict or None to remove all permissions for this action.
        """
        self._conn.execute(
            "DELETE FROM database_permissions WHERE database_name = ? AND action = ?",
            (database_name, action),
        )
        if allow_dict:
            for actor_key, actor_values in allow_dict.items():
                if isinstance(actor_values, str):
                    actor_values = [actor_values]
                for actor_value in actor_values:
                    self._conn.execute(
                        "INSERT INTO database_permissions (database_name, action, actor_key, actor_value) VALUES (?, ?, ?, ?)",
                        (database_name, action, actor_key, str(actor_value)),
                    )
        self._conn.commit()
        self._invalidate_cache()

    def delete_database(self, database_name):
        """Remove all metadata and permissions for a database."""
        self._conn.execute("DELETE FROM database_metadata WHERE database_name = ?", (database_name,))
        self._conn.execute("DELETE FROM database_permissions WHERE database_name = ?", (database_name,))
        self._conn.commit()
        self._invalidate_cache()

    # --- Migration ---

    def import_from_metadata_json(self, metadata_dict):
        """Import database-level fields from a parsed metadata.json dict.

        Imports: title, description, source, license, allow, allow_sql.
        Skips table/query metadata.
        Returns: dict with counts of imported items.
        """
        databases = metadata_dict.get("databases", {})
        imported_metadata = 0
        imported_permissions = 0

        for db_name, db_config in databases.items():
            # Import metadata fields
            title = db_config.get("title")
            description = db_config.get("description")
            source = db_config.get("source")
            license_val = db_config.get("license")

            if any(v is not None for v in (title, description, source, license_val)):
                self.set_database_metadata(db_name, title, description, source, license_val)
                imported_metadata += 1

            # Import allow -> view-database permissions
            allow = db_config.get("allow")
            if isinstance(allow, dict):
                self.set_database_permissions(db_name, "view-database", allow)
                imported_permissions += 1

            # Import allow_sql -> execute-sql permissions
            allow_sql = db_config.get("allow_sql")
            if isinstance(allow_sql, dict):
                self.set_database_permissions(db_name, "execute-sql", allow_sql)
                imported_permissions += 1

        return {"imported_metadata": imported_metadata, "imported_permissions": imported_permissions}

    # --- Site content ---

    def get_site_content(self, key, default=None):
        row = self._conn.execute(
            "SELECT value FROM site_content WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_site_content(self, key, value):
        self._conn.execute(
            "INSERT INTO site_content (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    # --- Site links ---

    def get_site_links(self):
        rows = self._conn.execute(
            "SELECT id, title, url, sort_order FROM site_links ORDER BY sort_order, id"
        ).fetchall()
        return [dict(row) for row in rows]

    def set_site_links(self, links):
        """Replace all links. links = [{"title": ..., "url": ..., "sort_order": ...}, ...]"""
        self._conn.execute("DELETE FROM site_links")
        for i, link in enumerate(links):
            self._conn.execute(
                "INSERT INTO site_links (title, url, sort_order) VALUES (?, ?, ?)",
                (link["title"], link["url"], link.get("sort_order", i)),
            )
        self._conn.commit()

    # --- Site news ---

    def get_site_news(self, limit=10):
        rows = self._conn.execute(
            "SELECT id, title, body, author, created, updated FROM site_news ORDER BY created DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def get_news_item(self, news_id):
        row = self._conn.execute(
            "SELECT id, title, body, author, created, updated FROM site_news WHERE id = ?",
            (news_id,),
        ).fetchone()
        return dict(row) if row else None

    def add_news(self, title, body, author):
        cursor = self._conn.execute(
            "INSERT INTO site_news (title, body, author) VALUES (?, ?, ?)",
            (title, body, author),
        )
        self._conn.commit()
        return cursor.lastrowid

    def update_news(self, news_id, title, body, author):
        self._conn.execute(
            "UPDATE site_news SET title = ?, body = ?, author = ?, updated = datetime('now') WHERE id = ?",
            (title, body, author, news_id),
        )
        self._conn.commit()

    def delete_news(self, news_id):
        self._conn.execute("DELETE FROM site_news WHERE id = ?", (news_id,))
        self._conn.commit()

    def close(self):
        self._conn.close()
