import json
import tempfile
from pathlib import Path

import pytest
from datasette.app import Datasette

import datasette_svk_layout
from datasette_svk_layout.metadata_db import MetadataDB


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset the global MetadataDB singleton between tests."""
    old = datasette_svk_layout._metadata_db_instance
    yield
    datasette_svk_layout._metadata_db_instance = old


@pytest.fixture
def mdb(tmp_path):
    db = MetadataDB(tmp_path / "test_metadata.db")
    yield db
    db.close()


class TestMetadataDB:
    def test_schema_creation(self, mdb):
        """Tables should be created on init."""
        tables = mdb._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [t["name"] for t in tables]
        assert "database_metadata" in names
        assert "database_permissions" in names

    def test_set_and_get_metadata(self, mdb):
        mdb.set_database_metadata("hrm_123", title="HR System", description="Test")
        meta = mdb.get_database_metadata("hrm_123")
        assert meta["title"] == "HR System"
        assert meta["description"] == "Test"

    def test_get_nonexistent_database(self, mdb):
        assert mdb.get_database_metadata("nonexistent") is None

    def test_upsert_metadata(self, mdb):
        mdb.set_database_metadata("hrm_123", title="Old")
        mdb.set_database_metadata("hrm_123", title="New")
        meta = mdb.get_database_metadata("hrm_123")
        assert meta["title"] == "New"

    def test_update_metadata(self, mdb):
        mdb.set_database_metadata("hrm_123", title="Title", description="Desc")
        mdb.update_database_metadata("hrm_123", title="New Title")
        meta = mdb.get_database_metadata("hrm_123")
        assert meta["title"] == "New Title"
        assert meta["description"] == "Desc"

    def test_delete_database(self, mdb):
        mdb.set_database_metadata("hrm_123", title="Title")
        mdb.set_database_permissions("hrm_123", "view-database", {"roles": ["admin"]})
        mdb.delete_database("hrm_123")
        assert mdb.get_database_metadata("hrm_123") is None
        assert mdb.get_database_permissions("hrm_123") == {}

    def test_list_databases(self, mdb):
        mdb.set_database_metadata("hrm_111", title="HRM 1")
        mdb.set_database_metadata("aveny_222", title="Aveny 1")
        mdb.set_database_metadata("hrm_333", title="HRM 2")

        all_dbs = mdb.list_databases()
        assert len(all_dbs) == 3

        hrm_dbs = mdb.list_databases(db_type="hrm")
        assert len(hrm_dbs) == 2

        search_dbs = mdb.list_databases(search="Aveny")
        assert len(search_dbs) == 1

    def test_set_and_get_permissions(self, mdb):
        mdb.set_database_permissions("hrm_123", "view-database", {
            "roles": ["hr-admin", "arkivarie"],
            "id": ["user1"],
        })
        perms = mdb.get_database_permissions("hrm_123")
        assert "view-database" in perms
        assert sorted(perms["view-database"]["roles"]) == ["arkivarie", "hr-admin"]
        assert perms["view-database"]["id"] == ["user1"]

    def test_replace_permissions(self, mdb):
        mdb.set_database_permissions("hrm_123", "view-database", {"roles": ["old"]})
        mdb.set_database_permissions("hrm_123", "view-database", {"roles": ["new"]})
        perms = mdb.get_database_permissions("hrm_123")
        assert perms["view-database"]["roles"] == ["new"]

    def test_clear_permissions(self, mdb):
        mdb.set_database_permissions("hrm_123", "view-database", {"roles": ["admin"]})
        mdb.set_database_permissions("hrm_123", "view-database", None)
        perms = mdb.get_database_permissions("hrm_123")
        assert "view-database" not in perms


class TestAllowDictAssembly:
    def test_allow_dict_in_datasette_format(self, mdb):
        mdb.set_database_metadata("hrm_123", title="HR")
        mdb.set_database_permissions("hrm_123", "view-database", {"roles": ["admin", "hr"]})
        mdb.set_database_permissions("hrm_123", "execute-sql", {"roles": ["admin"]})

        result = mdb.get_all_metadata_as_datasette_dict()
        db_meta = result["databases"]["hrm_123"]
        assert db_meta["title"] == "HR"
        assert db_meta["allow"] == {"roles": ["admin", "hr"]}
        assert db_meta["allow_sql"] == {"roles": ["admin"]}

    def test_cache_invalidation(self, mdb):
        mdb.set_database_metadata("test_db", title="V1")
        result1 = mdb.get_all_metadata_as_datasette_dict()
        assert result1["databases"]["test_db"]["title"] == "V1"

        mdb.set_database_metadata("test_db", title="V2")
        result2 = mdb.get_all_metadata_as_datasette_dict()
        assert result2["databases"]["test_db"]["title"] == "V2"

    def test_empty_db_returns_empty(self, mdb):
        result = mdb.get_all_metadata_as_datasette_dict()
        assert result == {}


class TestImport:
    def test_import_from_metadata_json(self, mdb):
        metadata = {
            "databases": {
                "employees": {
                    "title": "Personalregister",
                    "description": "HR data",
                    "source": "HR-system",
                    "license": "Internt",
                    "allow": {"roles": ["hr-admin"]},
                    "allow_sql": {"roles": ["admin"]},
                    "tables": {"should": "be ignored"},
                    "queries": {"should": "be ignored"},
                },
                "sakila": {
                    "title": "Sakila",
                },
            }
        }
        result = mdb.import_from_metadata_json(metadata)
        assert result["imported_metadata"] == 2
        assert result["imported_permissions"] == 2

        meta = mdb.get_database_metadata("employees")
        assert meta["title"] == "Personalregister"
        assert meta["source"] == "HR-system"

        perms = mdb.get_database_permissions("employees")
        assert perms["view-database"]["roles"] == ["hr-admin"]
        assert perms["execute-sql"]["roles"] == ["admin"]

        meta2 = mdb.get_database_metadata("sakila")
        assert meta2["title"] == "Sakila"


@pytest.mark.asyncio
async def test_get_metadata_hook(tmp_path):
    """Test that the get_metadata hook injects SQLite metadata into Datasette."""
    import datasette_svk_layout

    # Set up a temp metadata db
    db_path = tmp_path / "test_metadata.db"
    mdb = MetadataDB(db_path)
    mdb.set_database_metadata("test_db", title="From SQLite")
    mdb.set_database_permissions("test_db", "view-database", {"roles": ["tester"]})

    # Patch the global singleton
    old_instance = datasette_svk_layout._metadata_db_instance
    datasette_svk_layout._metadata_db_instance = mdb

    try:
        datasette = Datasette(memory=True)
        await datasette.invoke_startup()

        # The metadata should include our injected data
        title = datasette.metadata("title", database="test_db")
        assert title == "From SQLite"

        allow = datasette.metadata("allow", database="test_db")
        assert allow == {"roles": ["tester"]}
    finally:
        datasette_svk_layout._metadata_db_instance = old_instance
        mdb.close()


@pytest.mark.asyncio
async def test_metadata_json_overrides_sqlite(tmp_path):
    """metadata.json should have higher priority than SQLite metadata."""
    import datasette_svk_layout

    db_path = tmp_path / "test_metadata.db"
    mdb = MetadataDB(db_path)
    mdb.set_database_metadata("mydb", title="From SQLite")

    old_instance = datasette_svk_layout._metadata_db_instance
    datasette_svk_layout._metadata_db_instance = mdb

    try:
        # metadata.json override
        datasette = Datasette(
            memory=True,
            metadata={"databases": {"mydb": {"title": "From metadata.json"}}},
        )
        await datasette.invoke_startup()

        title = datasette.metadata("title", database="mydb")
        assert title == "From metadata.json"
    finally:
        datasette_svk_layout._metadata_db_instance = old_instance
        mdb.close()
