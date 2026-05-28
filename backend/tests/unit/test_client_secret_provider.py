"""Unit tests for environment-backed client secret provider."""

from app.security.client_secret_provider import ClientSecretProvider, ExternalClient


def test_registered_client_secret_is_returned():
    provider = ClientSecretProvider("bank-a:secret-a,broker-b:secret-b")

    assert provider.get_secret("bank-a") == "secret-a"
    assert provider.get_secret("broker-b") == "secret-b"


def test_unknown_client_returns_none():
    provider = ClientSecretProvider("bank-a:secret-a")

    assert provider.get_secret("missing") is None


def test_empty_secret_and_blank_entries_are_ignored():
    provider = ClientSecretProvider(" , bank-a: , :secret, broker-b:secret-b")

    assert provider.get_secret("bank-a") is None
    assert provider.get_secret("broker-b") == "secret-b"


def test_secret_is_not_exposed_in_repr():
    client = ExternalClient(client_id="bank-a", secret="super-secret")
    provider = ClientSecretProvider("bank-a:super-secret")

    assert "super-secret" not in repr(client)
    assert "super-secret" not in repr(provider)
