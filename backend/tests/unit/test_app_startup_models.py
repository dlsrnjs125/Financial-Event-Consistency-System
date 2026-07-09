"""Application startup model registry tests."""

from sqlalchemy.orm import configure_mappers

from app.main import app


def test_app_import_configures_all_model_relationships() -> None:
    assert app.title
    configure_mappers()
