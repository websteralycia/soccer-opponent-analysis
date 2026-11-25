"""UI regressions must never write to an analyst's real findings database."""
import pytest

@pytest.fixture(autouse=True)
def isolated_local_database(tmp_path,monkeypatch):
    monkeypatch.setenv('SOCCER_INTELLIGENCE_DB',str(tmp_path/'scouting.sqlite3'))
