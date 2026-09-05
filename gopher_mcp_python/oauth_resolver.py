"""OAuth runtime-option resolver for SDK-side agent creation."""

import base64
import json
import os
import sys
from dataclasses import replace
from typing import Any, Awaitable, Callable, Dict, List, Optional

from gopher_mcp_python.oauth_authorization_url import build_oauth_authorization_url
from gopher_mcp_python.oauth_browser import open_authorization_url
from gopher_mcp_python.oauth_discovery import (
    McpOAuthChallenge,
    OAuthAuthorizationServerMetadata,
    OAuthProtectedResourceMetadata,
    fetch_oauth_authorization_server_metadata,
    fetch_oauth_protected_resource_metadata,
    probe_mcp_oauth_challenge,
)
from gopher_mcp_python.oauth_loopback import create_oauth_loopback_callback_server
from gopher_mcp_python.oauth_pkce import create_code_challenge, create_code_verifier
from gopher_mcp_python.oauth_registration import (
    OAuthRegisteredClient,
    register_oauth_client,
)
from gopher_mcp_python.oauth_runtime_options import merge_oauth_token_into_runtime_options
from gopher_mcp_python.oauth_server_targets import extract_mcp_server_targets
from gopher_mcp_python.oauth_token_exchange import (
    exchange_oauth_code_for_token,
    refresh_oauth_token,
)
from gopher_mcp_python.oauth_token_store import (
    InMemoryGopherAgentTokenStore,
    create_oauth_token_cache_key,
    resolve_oauth_token_from_store,
)
from gopher_mcp_python.runtime_options import (
    GopherAgentOAuthOptions,
    GopherAgentRuntimeOptions,
    GopherAgentTokenRecord,
    normalize_oauth_options,
    normalize_runtime_options,
)


OAuthChallengeProbe = Callable[[str], Awaitable[McpOAuthChallenge]]
OAuthTokenAcquirer = Callable[
    [List[McpOAuthChallenge], GopherAgentOAuthOptions],
    Awaitable[Optional[GopherAgentRuntimeOptions]],
]
OAuthUrlRuntimeOptionsResolver = Callable[
    [str, Optional[GopherAgentRuntimeOptions], Optional[GopherAgentOAuthOptions]],
    Awaitable[Optional[GopherAgentRuntimeOptions]],
]


_default_token_store = InMemoryGopherAgentTokenStore()


async def _default_probe_challenge(url: str) -> McpOAuthChallenge:
    return probe_mcp_oauth_challenge(url)


async def _default_acquire_token(
    challenges: List[McpOAuthChallenge],
    oauth: GopherAgentOAuthOptions,
) -> GopherAgentRuntimeOptions:
    challenge = challenges[0]
    resource_metadata = _resolve_resource_metadata_for_challenge(challenge)
    authorization_server = _select_authorization_server(challenge, resource_metadata)
    authorization_metadata = fetch_oauth_authorization_server_metadata(
        authorization_server
    )
    if challenge.registration_endpoint is not None:
        authorization_metadata = replace(
            authorization_metadata,
            registration_endpoint=challenge.registration_endpoint,
        )
    scopes = _select_scopes(oauth, resource_metadata, authorization_metadata)
    state = create_code_verifier()
    loopback = await create_oauth_loopback_callback_server(state=state)

    try:
        client = register_oauth_client(
            metadata=authorization_metadata,
            redirect_uri=loopback.redirect_uri,
            scopes=scopes,
            oauth=oauth,
        )
        cache_key = create_oauth_token_cache_key(
            resource=resource_metadata.resource,
            issuer=authorization_metadata.issuer,
            client_id=client.client_id,
            scopes=scopes,
        )
        store = oauth.token_store or _default_token_store
        token = await resolve_oauth_token_from_store(
            store=store,
            key=cache_key,
            refresh_token=lambda refresh: _refresh_token(
                refresh, authorization_metadata, client
            ),
            acquire_token=lambda: _run_authorization_code_flow(
                oauth=oauth,
                resource_metadata=resource_metadata,
                authorization_metadata=authorization_metadata,
                client=client,
                redirect_uri=loopback.redirect_uri,
                wait_for_callback=loopback.wait_for_callback,
                state=state,
            ),
        )
        _log_oauth_debug("resolved access token claims", _decode_jwt_claims(token.access_token))
        return merge_oauth_token_into_runtime_options(None, token)
    finally:
        await loopback.close()


async def _default_url_runtime_options_resolver(
    url: str,
    runtime_options: Optional[GopherAgentRuntimeOptions],
    oauth: Optional[GopherAgentOAuthOptions],
) -> Optional[GopherAgentRuntimeOptions]:
    return await resolve_runtime_options_with_oauth(
        urls=[url],
        runtime_options=runtime_options,
        oauth=oauth,
    )


_probe_challenge: OAuthChallengeProbe = _default_probe_challenge
_acquire_token: OAuthTokenAcquirer = _default_acquire_token
_url_runtime_options_resolver: OAuthUrlRuntimeOptionsResolver = (
    _default_url_runtime_options_resolver
)


async def resolve_runtime_options_with_oauth(
    urls: Optional[List[str]] = None,
    server_config: Optional[str] = None,
    runtime_options: Optional[GopherAgentRuntimeOptions] = None,
    oauth: Optional[GopherAgentOAuthOptions] = None,
) -> Optional[GopherAgentRuntimeOptions]:
    """Resolve runtime options, acquiring OAuth credentials when needed."""
    normalized_runtime_options = normalize_runtime_options(runtime_options)
    normalized_oauth = normalize_oauth_options(oauth)
    if (
        normalized_oauth is not None
        and normalized_oauth.mode == "disabled"
    ) or _has_runtime_authorization(normalized_runtime_options):
        return normalized_runtime_options

    target_urls = list(urls or [])
    target_urls.extend(
        target["url"]
        for target in extract_mcp_server_targets(server_config=server_config)
    )
    challenges = [await _probe_challenge(url) for url in target_urls]
    oauth_challenges = [
        challenge for challenge in challenges if challenge.requires_oauth
    ]
    if len(oauth_challenges) == 0:
        return normalized_runtime_options

    _assert_compatible_oauth_challenges(oauth_challenges)
    token_options = await _acquire_token(
        oauth_challenges,
        normalized_oauth or GopherAgentOAuthOptions(),
    )
    return _merge_runtime_options(normalized_runtime_options, token_options)


async def resolve_url_runtime_options_with_oauth(
    url: str,
    runtime_options: Optional[GopherAgentRuntimeOptions] = None,
    oauth: Optional[GopherAgentOAuthOptions] = None,
) -> Optional[GopherAgentRuntimeOptions]:
    """Resolve runtime options for a direct MCP URL."""
    return await _url_runtime_options_resolver(url, runtime_options, oauth)


def set_oauth_resolver_hooks_for_test(
    probe_challenge: Optional[OAuthChallengeProbe] = None,
    acquire_token: Optional[OAuthTokenAcquirer] = None,
) -> None:
    """Replace resolver hooks for tests, or reset omitted hooks to defaults."""
    global _probe_challenge, _acquire_token
    _probe_challenge = probe_challenge or _default_probe_challenge
    _acquire_token = acquire_token or _default_acquire_token


def set_oauth_url_runtime_options_resolver_for_test(
    resolver: Optional[OAuthUrlRuntimeOptionsResolver] = None,
) -> None:
    """Replace direct-URL resolver for tests, or reset to default."""
    global _url_runtime_options_resolver
    _url_runtime_options_resolver = resolver or _default_url_runtime_options_resolver


def _has_runtime_authorization(
    options: Optional[GopherAgentRuntimeOptions],
) -> bool:
    if options is None:
        return False
    if options.access_token is not None:
        return True
    return any(name.lower() == "authorization" for name in options.headers)


def _assert_compatible_oauth_challenges(challenges: List[McpOAuthChallenge]) -> None:
    keys = set()
    for challenge in challenges:
        issuer = (
            challenge.authorization_server
            or challenge.resource_metadata_url
            or challenge.url
        )
        resource = challenge.resource or challenge.resource_metadata_url or challenge.url
        scopes = " ".join(sorted(challenge.scopes or []))
        keys.add(json.dumps({"issuer": issuer, "resource": resource, "scopes": scopes}))
    if len(keys) > 1:
        raise RuntimeError(
            "OAuth auto-flow found multiple protected MCP servers with different "
            "OAuth issuers.\nPer-server OAuth tokens are not supported yet."
        )


def _merge_runtime_options(
    base: Optional[GopherAgentRuntimeOptions],
    token_options: Optional[GopherAgentRuntimeOptions],
) -> Optional[GopherAgentRuntimeOptions]:
    base = normalize_runtime_options(base)
    token_options = normalize_runtime_options(token_options)
    if base is None:
        return token_options
    if token_options is None:
        return base
    headers = base.headers
    headers.update(token_options.headers)
    return normalize_runtime_options(
        {
            "access_token": token_options.access_token or base.access_token,
            "headers": headers,
            "elicitation": base.elicitation or token_options.elicitation,
        }
    )


async def _run_authorization_code_flow(
    oauth: GopherAgentOAuthOptions,
    resource_metadata: OAuthProtectedResourceMetadata,
    authorization_metadata: OAuthAuthorizationServerMetadata,
    client: OAuthRegisteredClient,
    redirect_uri: str,
    wait_for_callback,
    state: str,
) -> GopherAgentTokenRecord:
    code_verifier = create_code_verifier()
    code_challenge = create_code_challenge(code_verifier)
    authorization_url = build_oauth_authorization_url(
        metadata=authorization_metadata,
        client_id=client.client_id,
        redirect_uri=redirect_uri,
        state=state,
        code_challenge=code_challenge,
        scopes=oauth.scopes,
        resource_metadata=resource_metadata,
    )
    opened = open_authorization_url(
        authorization_url,
        open_browser=oauth.open_browser,
    )
    if not opened["opened"]:
        print(f"Open this OAuth authorization URL:\n{opened['url']}", file=sys.stderr)

    callback = await wait_for_callback()
    return exchange_oauth_code_for_token(
        code=callback.code,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
        token_endpoint=authorization_metadata.token_endpoint,
        client_id=client.client_id,
        client_secret=client.client_secret,
    )


async def _refresh_token(
    refresh_token: str,
    authorization_metadata: OAuthAuthorizationServerMetadata,
    client: OAuthRegisteredClient,
) -> GopherAgentTokenRecord:
    return refresh_oauth_token(
        refresh_token=refresh_token,
        token_endpoint=authorization_metadata.token_endpoint,
        client_id=client.client_id,
        client_secret=client.client_secret,
    )


def _select_authorization_server(
    challenge: McpOAuthChallenge,
    metadata: OAuthProtectedResourceMetadata,
) -> str:
    if challenge.authorization_server is not None:
        return challenge.authorization_server
    if len(metadata.authorization_servers) == 0:
        raise RuntimeError(
            "oauth_metadata_fetch_failed: Protected resource metadata is "
            "missing authorization_servers"
        )
    return metadata.authorization_servers[0]


def _resolve_resource_metadata_for_challenge(
    challenge: McpOAuthChallenge,
) -> OAuthProtectedResourceMetadata:
    if challenge.resource_metadata_url is not None:
        return fetch_oauth_protected_resource_metadata(challenge.resource_metadata_url)
    if challenge.authorization_server is None:
        raise RuntimeError(
            f"oauth_metadata_missing: MCP OAuth challenge for {challenge.url} "
            "is missing resource_metadata"
        )
    return OAuthProtectedResourceMetadata(
        resource=challenge.resource or challenge.url,
        authorization_servers=[challenge.authorization_server],
        scopes_supported=list(challenge.scopes or []),
        raw_json="{}",
    )


def _select_scopes(
    oauth: GopherAgentOAuthOptions,
    resource_metadata: OAuthProtectedResourceMetadata,
    authorization_metadata: OAuthAuthorizationServerMetadata,
) -> List[str]:
    if oauth.scopes:
        return oauth.scopes
    if resource_metadata.scopes_supported:
        return resource_metadata.scopes_supported
    return authorization_metadata.scopes_supported


def _decode_jwt_claims(token: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        return {"jwt": False}
    try:
        payload = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii")).decode("utf-8")
        parsed = json.loads(decoded)
        if not isinstance(parsed, dict):
            return {"jwt": True, "claims_decode_error": "JWT payload is not an object"}
        names = ["iss", "aud", "azp", "client_id", "scope", "scp", "sub", "exp", "iat"]
        return {"jwt": True, **{name: parsed[name] for name in names if name in parsed}}
    except Exception as exc:
        return {"jwt": True, "claims_decode_error": str(exc)}


def _log_oauth_debug(label: str, values: Any) -> None:
    if os.environ.get("GOPHER_MCP_OAUTH_DEBUG") != "1" and os.environ.get("DEBUG") != "1":
        return
    print(f"[gopher-mcp-python oauth] {label}: {json.dumps(values)}", file=sys.stderr)
