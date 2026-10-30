"""Build OAuth authorization URLs."""

from typing import List, Optional
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

from gopher_mcp_python.oauth_scopes import select_oauth_scopes
from gopher_mcp_python.oauth_discovery import (
    OAuthAuthorizationServerMetadata,
    OAuthProtectedResourceMetadata,
)


def build_oauth_authorization_url(
    metadata: OAuthAuthorizationServerMetadata,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
    scopes: Optional[List[str]] = None,
    resource_metadata: Optional[OAuthProtectedResourceMetadata] = None,
    challenge_scopes: Optional[List[str]] = None,
) -> str:
    """Build an authorization-code URL with PKCE parameters."""
    parsed = urlparse(metadata.authorization_endpoint)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    params["response_type"] = "code"
    params["client_id"] = client_id
    params["redirect_uri"] = redirect_uri
    params["state"] = state
    params["code_challenge"] = code_challenge
    params["code_challenge_method"] = "S256"

    selected_scopes = select_oauth_scopes(
        scopes=scopes,
        challenge_scopes=challenge_scopes,
        resource_scopes=(
            resource_metadata.scopes_supported if resource_metadata else None
        ),
    )
    params.pop("scope", None)
    if selected_scopes:
        params["scope"] = " ".join(selected_scopes)
    if resource_metadata is not None and resource_metadata.resource:
        params["resource"] = resource_metadata.resource

    return urlunparse(parsed._replace(query=urlencode(params)))
