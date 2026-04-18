"""Tests for extended payload claims and updated types."""

from gopher_mcp_python.ffi.auth.types import TokenPayload, GopherAuthContext


class TestTokenPayloadExtendedFields:
    """Tests for TokenPayload extended fields."""

    def test_email_field(self):
        payload = TokenPayload(
            subject="user-123", scopes="openid", email="user@example.com"
        )
        assert payload.email == "user@example.com"

    def test_name_field(self):
        payload = TokenPayload(subject="user-123", scopes="openid", name="John Doe")
        assert payload.name == "John Doe"

    def test_organization_id_field(self):
        payload = TokenPayload(
            subject="user-123", scopes="openid", organization_id="org-456"
        )
        assert payload.organization_id == "org-456"

    def test_server_id_field(self):
        payload = TokenPayload(subject="user-123", scopes="openid", server_id="srv-789")
        assert payload.server_id == "srv-789"

    def test_claims_dict(self):
        payload = TokenPayload(
            subject="user-123",
            scopes="openid",
            claims={"tenant": "acme", "role": "admin"},
        )
        assert payload.claims == {"tenant": "acme", "role": "admin"}

    def test_all_extended_fields_default_none(self):
        payload = TokenPayload(subject="user-123", scopes="openid")
        assert payload.email is None
        assert payload.name is None
        assert payload.organization_id is None
        assert payload.server_id is None
        assert payload.claims is None


class TestGopherAuthContextExtendedFields:
    """Tests for GopherAuthContext extended fields."""

    def test_email_field(self):
        ctx = GopherAuthContext(
            user_id="u",
            scopes="s",
            audience="a",
            token_expiry=0,
            authenticated=True,
            email="user@example.com",
        )
        assert ctx.email == "user@example.com"

    def test_name_field(self):
        ctx = GopherAuthContext(
            user_id="u",
            scopes="s",
            audience="a",
            token_expiry=0,
            authenticated=True,
            name="John",
        )
        assert ctx.name == "John"

    def test_organization_id_field(self):
        ctx = GopherAuthContext(
            user_id="u",
            scopes="s",
            audience="a",
            token_expiry=0,
            authenticated=True,
            organization_id="org-1",
        )
        assert ctx.organization_id == "org-1"

    def test_server_id_field(self):
        ctx = GopherAuthContext(
            user_id="u",
            scopes="s",
            audience="a",
            token_expiry=0,
            authenticated=True,
            server_id="srv-1",
        )
        assert ctx.server_id == "srv-1"

    def test_raw_token_field(self):
        ctx = GopherAuthContext(
            user_id="u",
            scopes="s",
            audience="a",
            token_expiry=0,
            authenticated=True,
            raw_token="eyJhbGciOiJSUzI1NiJ9.test.sig",
        )
        assert ctx.raw_token == "eyJhbGciOiJSUzI1NiJ9.test.sig"

    def test_all_extended_fields_default_none(self):
        ctx = GopherAuthContext(
            user_id="u", scopes="s", audience="a", token_expiry=0, authenticated=True
        )
        assert ctx.email is None
        assert ctx.name is None
        assert ctx.organization_id is None
        assert ctx.server_id is None
        assert ctx.raw_token is None
