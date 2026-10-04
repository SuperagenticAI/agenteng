"""Credential parsing shared by transports without importing either SDK."""


def bearer(headers) -> str | None:
    value = headers.get("authorization", "")
    scheme, _, token = value.partition(" ")
    return token if scheme.lower() == "bearer" and token else None
