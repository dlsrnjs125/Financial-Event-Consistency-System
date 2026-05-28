"""Security domain exceptions."""


class MissingSecurityHeader(Exception):
    def __init__(self, header_name: str) -> None:
        self.header_name = header_name
        super().__init__("Required security header is missing.")


class UnknownClient(Exception):
    def __init__(self) -> None:
        super().__init__("The client is not allowed.")


class DisabledClient(Exception):
    def __init__(self) -> None:
        super().__init__("The client is disabled.")


class InvalidTimestamp(Exception):
    def __init__(self) -> None:
        super().__init__("The request timestamp is invalid.")


class ExpiredTimestamp(Exception):
    def __init__(self) -> None:
        super().__init__("The request timestamp is expired.")


class InvalidSignature(Exception):
    def __init__(self) -> None:
        super().__init__("The request signature is invalid.")
