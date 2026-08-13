"""PKCE helpers for SDK-side OAuth flows."""

import base64
import hashlib
import secrets


def create_code_verifier() -> str:
    """Create a high-entropy OAuth PKCE code verifier."""
    return base64_url_encode(secrets.token_bytes(32))


def create_code_challenge(verifier: str) -> str:
    """Create an S256 PKCE code challenge for a verifier."""
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64_url_encode(digest)


def base64_url_encode(value: bytes) -> str:
    """Base64url encode bytes without padding."""
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")
