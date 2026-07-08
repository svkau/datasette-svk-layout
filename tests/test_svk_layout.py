from datasette.app import Datasette
from unittest.mock import patch
import pytest


@pytest.mark.asyncio
async def test_plugin_is_installed():
    datasette = Datasette(memory=True)
    response = await datasette.client.get("/-/plugins.json")
    assert response.status_code == 200
    data = response.json()
    # Datasette 1.0 wraps the list as {"ok": true, "plugins": [...]};
    # Datasette 0.x returns a bare list.
    plugins = data["plugins"] if isinstance(data, dict) else data
    installed_plugins = {p["name"] for p in plugins}
    assert "datasette-svk-layout" in installed_plugins


# -- permission_allowed tests --

from datasette_svk_layout import permission_allowed

MOCK_DB_CONFIG = {
    "tables": {
        "Kundreskontra": {
            "allow": {
                "permissions": [
                    "access.search_economics",
                    "access.search_everything"
                ]
            },
            "title": "Kundreskontra"
        },
        "budgetar": {
            "title": "Budgetar"
        }
    }
}


@pytest.fixture
def mock_db_config():
    with patch("datasette_svk_layout.get_database_config", return_value=MOCK_DB_CONFIG):
        yield


def test_permission_denied_without_actor(mock_db_config):
    """Tabell med allow.permissions ska neka åtkomst utan aktör."""
    result = permission_allowed(
        datasette=None, actor=None, action="view-table",
        resource=("aveny_2520026135", "Kundreskontra")
    )
    assert result is False


def test_permission_denied_wrong_role(mock_db_config):
    """Tabell med allow.permissions ska neka aktör utan rätt roll."""
    actor = {"permissions": ["access.search_salaries"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-table",
        resource=("aveny_2520026135", "Kundreskontra")
    )
    assert result is False


def test_permission_granted_matching_role(mock_db_config):
    """Tabell med allow.permissions ska tillåta aktör med matchande roll."""
    actor = {"permissions": ["access.search_economics"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-table",
        resource=("aveny_2520026135", "Kundreskontra")
    )
    assert result is True


def test_permission_granted_any_matching_role(mock_db_config):
    """Det räcker med en matchande roll av flera."""
    actor = {"permissions": ["access.search_everything"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-table",
        resource=("aveny_2520026135", "Kundreskontra")
    )
    assert result is True


def test_permission_applies_to_all_table_actions(mock_db_config):
    """allow.permissions ska gälla för alla table actions, inte bara view-table."""
    actor_denied = {"permissions": ["access.search_salaries"]}
    actor_allowed = {"permissions": ["access.search_economics"]}
    for action in ["view-table", "insert-row", "update-row", "delete-row"]:
        assert permission_allowed(
            datasette=None, actor=actor_denied, action=action,
            resource=("aveny_2520026135", "Kundreskontra")
        ) is False
        assert permission_allowed(
            datasette=None, actor=actor_allowed, action=action,
            resource=("aveny_2520026135", "Kundreskontra")
        ) is True


def test_permission_fallback_no_allow_block(mock_db_config):
    """Tabell utan allow-block ska returnera None (Datasette-default)."""
    actor = {"permissions": ["access.search_salaries"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-table",
        resource=("aveny_2520026135", "budgetar")
    )
    assert result is None


def test_permission_fallback_non_table_action(mock_db_config):
    """Icke-tabell-actions (t.ex. execute-sql) ska returnera None."""
    result = permission_allowed(
        datasette=None, actor={"permissions": []}, action="execute-sql",
        resource=("aveny_2520026135",)
    )
    assert result is None


# -- view-database permission tests --

def test_view_database_denied_without_actor(mock_db_config):
    """Databas med tabellbehörigheter ska döljas utan aktör."""
    result = permission_allowed(
        datasette=None, actor=None, action="view-database",
        resource="aveny_2520026135"
    )
    assert result is False


def test_view_database_denied_wrong_role(mock_db_config):
    """Databas ska döljas om aktören saknar alla tabellroller."""
    actor = {"permissions": ["access.search_salaries"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-database",
        resource="aveny_2520026135"
    )
    assert result is False


def test_view_database_allowed_matching_role(mock_db_config):
    """Databas ska visas om aktören har minst en tabellroll."""
    actor = {"permissions": ["access.search_economics"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-database",
        resource="aveny_2520026135"
    )
    assert result is None


MOCK_DB_CONFIG_NO_PERMISSIONS = {
    "tables": {
        "budgetar": {
            "title": "Budgetar"
        }
    }
}


def test_view_database_no_restriction_without_allow(mock_db_config):
    """Databas utan tabellbehörigheter ska inte begränsas."""
    with patch("datasette_svk_layout.get_database_config", return_value=MOCK_DB_CONFIG_NO_PERMISSIONS):
        result = permission_allowed(
            datasette=None, actor={"permissions": []}, action="view-database",
            resource="some_database"
        )
    assert result is None


# -- Public_360 permission tests --

MOCK_P360_CONFIG = {
    "tables": {
        "aggregation": {
            "allow": {
                "permissions": [
                    "access.search_casefiles",
                    "access.search_casefiles_confidentiality",
                    "access.search_everything"
                ]
            },
            "title": "Ärenden"
        },
        "record": {
            "allow": {
                "permissions": [
                    "access.search_casefiles",
                    "access.search_casefiles_confidentiality",
                    "access.search_everything"
                ]
            },
            "title": "Handlingar"
        }
    }
}


@pytest.fixture
def mock_p360_config():
    with patch("datasette_svk_layout.get_database_config", return_value=MOCK_P360_CONFIG):
        yield


def test_p360_denied_without_casefiles_role(mock_p360_config):
    """Public_360-tabell ska neka aktör utan ärendebehörighet."""
    actor = {"permissions": ["access.search_salaries"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-table",
        resource=("Public_360_2520026135", "aggregation")
    )
    assert result is False


def test_p360_granted_casefiles_role(mock_p360_config):
    """Public_360-tabell ska tillåta aktör med search_casefiles."""
    actor = {"permissions": ["access.search_casefiles"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-table",
        resource=("Public_360_2520026135", "aggregation")
    )
    assert result is True


def test_p360_granted_confidentiality_role(mock_p360_config):
    """Public_360-tabell ska tillåta aktör med search_casefiles_confidentiality."""
    actor = {"permissions": ["access.search_casefiles_confidentiality"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-table",
        resource=("Public_360_2520026135", "aggregation")
    )
    assert result is True


def test_p360_view_database_denied_wrong_role(mock_p360_config):
    """Public_360-databas ska döljas utan ärendebehörighet."""
    actor = {"permissions": ["access.search_salaries"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-database",
        resource="Public_360_2520026135"
    )
    assert result is False


def test_p360_view_database_allowed(mock_p360_config):
    """Public_360-databas ska visas med search_casefiles."""
    actor = {"permissions": ["access.search_casefiles"]}
    result = permission_allowed(
        datasette=None, actor=actor, action="view-database",
        resource="Public_360_2520026135"
    )
    assert result is None


# -- permission_resources_sql integration tests (Datasette 1.0) --

import sqlite3
import datasette_svk_layout
from datasette import hookspecs
from datasette_svk_layout.metadata_db import MetadataDB


@pytest.mark.asyncio
async def test_permission_resources_sql_org_gating(tmp_path):
    """view-database and its tables must be gated on organizations_ids under 1.0.

    Exercises the permission_resources_sql hook end-to-end through real HTTP
    requests: a database registered with organizations_ids in svk_metadata.db is
    visible to an actor from that org (200) and forbidden to an actor from
    another org (403), for both the database page and its tables (the org DENY
    at the database level cascades to tables).
    """
    if not hasattr(hookspecs, "permission_resources_sql"):
        pytest.skip("permission_resources_sql requires Datasette 1.0+")

    db_file = tmp_path / "testdb_510.db"
    con = sqlite3.connect(db_file)
    con.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, x TEXT)")
    con.execute("INSERT INTO t (x) VALUES ('hi')")
    con.commit()
    con.close()

    mdb = MetadataDB(tmp_path / "svk_metadata.db")
    mdb.set_database_permissions(
        "testdb_510", "view-database", {"organizations_ids": ["510"]}
    )

    old_instance = datasette_svk_layout._metadata_db_instance
    datasette_svk_layout._metadata_db_instance = mdb
    try:
        datasette = Datasette([str(db_file)])
        await datasette.invoke_startup()

        def cookies(org):
            actor = {"id": "u", "organizations_ids": [org]}
            return {"ds_actor": datasette.sign({"a": actor}, "actor")}

        # Right enhet -> allowed
        assert (await datasette.client.get("/testdb_510", cookies=cookies(510))).status_code == 200
        assert (await datasette.client.get("/testdb_510/t", cookies=cookies(510))).status_code == 200
        # Wrong enhet -> forbidden (database-level DENY cascades to tables)
        assert (await datasette.client.get("/testdb_510", cookies=cookies(999))).status_code == 403
        assert (await datasette.client.get("/testdb_510/t", cookies=cookies(999))).status_code == 403
    finally:
        datasette_svk_layout._metadata_db_instance = old_instance
        mdb.close()
