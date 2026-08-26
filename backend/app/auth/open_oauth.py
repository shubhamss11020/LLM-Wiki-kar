"""
Open OAuth Provider for MCP — auto-approves all clients and tokens.

Satisfies Claude.ai's OAuth 2.1 requirement for remote MCP servers
without enforcing any real passwords or friction.
"""

import uuid
import time
import logging
from typing import Any

from mcp.server.auth.provider import (
    OAuthAuthorizationServerProvider,
    AuthorizationParams,
    AuthorizationCode,
    AccessToken,
    RefreshToken,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions

logger = logging.getLogger(__name__)

_clients: dict[str, OAuthClientInformationFull] = {}
_auth_codes: dict[str, AuthorizationCode] = {}
_access_tokens: dict[str, AccessToken] = {}
_refresh_tokens: dict[str, RefreshToken] = {}


class OpenOAuthProvider(OAuthAuthorizationServerProvider[AuthorizationCode, AccessToken, RefreshToken]):
    """
    Open OAuth provider that auto-registers clients and auto-approves authorizations.
    """

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return _clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        logger.info(f"OAuth: Registering client '{client_info.client_id}' ({client_info.client_name})")
        _clients[client_info.client_id] = client_info

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        """Auto-approve authorization request and return redirect URI with auth code."""
        code_str = f"open-code-{uuid.uuid4().hex}"
        auth_code = AuthorizationCode(
            code=code_str,
            client_id=client.client_id,
            scopes=params.scopes or [],
            expires_at=int(time.time()) + 600,
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
            subject="anonymous_user",
        )
        _auth_codes[code_str] = auth_code

        logger.info(f"OAuth: Auto-approved authorization for client '{client.client_id}'")

        redirect = str(params.redirect_uri)
        separator = "&" if "?" in redirect else "?"
        redirect += f"{separator}code={code_str}"
        if params.state:
            redirect += f"&state={params.state}"
        return redirect

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        return _auth_codes.get(authorization_code)

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        """Exchange authorization code for access token."""
        token_str = f"open-access-{uuid.uuid4().hex}"
        refresh_str = f"open-refresh-{uuid.uuid4().hex}"

        access_token = AccessToken(
            token=token_str,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + 86400 * 365,
            resource=authorization_code.resource,
            subject=authorization_code.subject,
        )
        refresh_token = RefreshToken(
            token=refresh_str,
            client_id=client.client_id,
            scopes=authorization_code.scopes,
            expires_at=int(time.time()) + 86400 * 365,
            subject=authorization_code.subject,
        )

        _access_tokens[token_str] = access_token
        _refresh_tokens[refresh_str] = refresh_token

        # Clean up used authorization code
        _auth_codes.pop(authorization_code.code, None)

        logger.info(f"OAuth: Issued access token for client '{client.client_id}'")
        return OAuthToken(
            access_token=token_str,
            token_type="Bearer",
            expires_in=86400 * 365,
            refresh_token=refresh_str,
            scope=" ".join(authorization_code.scopes) if authorization_code.scopes else None,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token in _access_tokens:
            return _access_tokens[token]
        # In open mode, treat any incoming token as valid if not found
        fallback = AccessToken(
            token=token,
            client_id="open-client",
            scopes=[],
            expires_at=int(time.time()) + 86400 * 365,
            subject="anonymous_user",
        )
        _access_tokens[token] = fallback
        return fallback

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        return _refresh_tokens.get(refresh_token)

    async def exchange_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]
    ) -> OAuthToken:
        new_token_str = f"open-access-{uuid.uuid4().hex}"
        access_token = AccessToken(
            token=new_token_str,
            client_id=client.client_id,
            scopes=scopes or refresh_token.scopes,
            expires_at=int(time.time()) + 86400 * 365,
            subject=refresh_token.subject,
        )
        _access_tokens[new_token_str] = access_token

        return OAuthToken(
            access_token=new_token_str,
            token_type="Bearer",
            expires_in=86400 * 365,
        )

    async def revoke_token(self, token: str) -> None:
        _access_tokens.pop(token, None)
        _refresh_tokens.pop(token, None)

    async def exchange_identity_assertion(self, client, params):
        token_str = f"open-access-{uuid.uuid4().hex}"
        return OAuthToken(
            access_token=token_str,
            token_type="Bearer",
            expires_in=86400 * 365,
        )


def create_auth_settings(server_url: str) -> AuthSettings:
    return AuthSettings(
        issuer_url=server_url,
        resource_server_url=server_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[],
            default_scopes=[],
        ),
    )
