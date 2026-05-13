"""Migrate database-level metadata from metadata.json to SQLite.

Usage:
    python -m datasette_svk_layout.migrate_metadata [metadata_path] [db_path]

Defaults:
    metadata_path: data/metadata.json
    db_path: datasette_svk_layout/datasette_svk_layout/data/svk_metadata.db
"""
import json
import sys
from pathlib import Path
from datasette_svk_layout.metadata_db import MetadataDB


def migrate(metadata_path="data/metadata.json", db_path="datasette_svk_layout/data/svk_metadata.db"):
    metadata_path = Path(metadata_path)
    if not metadata_path.exists():
        print(f"Fel: {metadata_path} hittades inte.")
        return False

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    mdb = MetadataDB(db_path)
    result = mdb.import_from_metadata_json(metadata)
    mdb.close()

    print(f"Import klar:")
    print(f"  {result['imported_metadata']} databas(er) med metadata")
    print(f"  {result['imported_permissions']} behörighetspost(er)")
    return True


if __name__ == "__main__":
    metadata_path = sys.argv[1] if len(sys.argv) > 1 else "data/metadata.json"
    db_path = sys.argv[2] if len(sys.argv) > 2 else "datasette_svk_layout/data/svk_metadata.db"
    success = migrate(metadata_path, db_path)
    sys.exit(0 if success else 1)
