"""Environment-backed external client secret provider."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalClient:
    """External client metadata.

    The env-backed Phase 7 provider always creates enabled clients. The enabled
    flag is reserved for a future DB or Secret Manager backed provider.
    """

    client_id: str
    secret: str
    enabled: bool = True

    def __repr__(self) -> str:
        return (
            "ExternalClient("
            f"client_id={self.client_id!r}, secret='<redacted>', "
            f"enabled={self.enabled!r})"
        )


class ClientSecretProvider:
    def __init__(self, raw_secrets: str) -> None:
        self._clients = self._parse(raw_secrets)

    def get_secret(self, client_id: str) -> str | None:
        client = self._clients.get(client_id)
        if client is None or not client.enabled or not client.secret:
            return None
        return client.secret

    def get_client(self, client_id: str) -> ExternalClient | None:
        return self._clients.get(client_id)

    def __repr__(self) -> str:
        client_ids = sorted(self._clients)
        return f"ClientSecretProvider(client_ids={client_ids!r})"

    def _parse(self, raw_secrets: str) -> dict[str, ExternalClient]:
        clients: dict[str, ExternalClient] = {}
        for entry in raw_secrets.split(","):
            normalized = entry.strip()
            if not normalized or ":" not in normalized:
                continue
            client_id, secret = normalized.split(":", 1)
            client_id = client_id.strip()
            secret = secret.strip()
            if not client_id or not secret:
                continue
            clients[client_id] = ExternalClient(client_id=client_id, secret=secret)
        return clients
