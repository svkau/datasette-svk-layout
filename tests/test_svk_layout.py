from datasette.app import Datasette
from unittest.mock import patch
import pytest


@pytest.mark.asyncio
async def test_plugin_is_installed():
    datasette = Datasette(memory=True)
    response = await datasette.client.get("/-/plugins.json")
    assert response.status_code == 200
    installed_plugins = {p["name"] for p in response.json()}
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
