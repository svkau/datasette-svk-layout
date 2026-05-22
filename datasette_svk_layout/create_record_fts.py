"""Skapa FTS5-index för record-tabellen i Public_360-databaser.

Användning:
    python -m datasette_svk_layout.create_record_fts <db_path> [<db_path> ...]
"""

import sqlite3
import sys


def create_record_fts(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        # Kontrollera att record-tabellen finns
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='record'"
            )
        ]
        if not tables:
            print(f"  Hoppar över {db_path}: ingen record-tabell")
            return

        # Skapa FTS5-tabell
        conn.execute(
            """CREATE VIRTUAL TABLE IF NOT EXISTS record_fts USING fts5(
                objectId, title, sender, receiver, direction, recordType, description
            )"""
        )

        # Skapa triggers
        conn.executescript(
            """
            DROP TRIGGER IF EXISTS insert_record_fts;
            CREATE TRIGGER insert_record_fts AFTER INSERT ON record BEGIN
                INSERT INTO record_fts(objectId, title, sender, receiver, direction, recordType, description)
                VALUES (new.objectId, new.title, new.sender, new.receiver, new.direction, new.recordType, new.description);
            END;

            DROP TRIGGER IF EXISTS update_record_fts;
            CREATE TRIGGER update_record_fts AFTER UPDATE ON record BEGIN
                UPDATE record_fts SET
                    title = new.title,
                    sender = new.sender,
                    receiver = new.receiver,
                    direction = new.direction,
                    recordType = new.recordType,
                    description = new.description
                WHERE objectId = new.objectId;
            END;

            DROP TRIGGER IF EXISTS delete_record_fts;
            CREATE TRIGGER delete_record_fts AFTER DELETE ON record BEGIN
                DELETE FROM record_fts WHERE objectId = old.objectId;
            END;
            """
        )

        # Bygg om FTS-indexet från befintlig data
        conn.execute("DELETE FROM record_fts")
        conn.execute(
            """INSERT INTO record_fts(objectId, title, sender, receiver, direction, recordType, description)
               SELECT objectId, title, sender, receiver, direction, recordType, description FROM record"""
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM record_fts").fetchone()[0]
        print(f"  {db_path}: record_fts skapad med {count} rader")
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Användning: python -m datasette_svk_layout.create_record_fts <db_path> [...]")
        sys.exit(1)

    for path in sys.argv[1:]:
        print(f"Bearbetar {path}...")
        create_record_fts(path)
