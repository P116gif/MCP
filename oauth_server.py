#https://auth0.com/blog/an-introduction-to-mcp-and-authorization/#The-MCP-Lifecycle
#^^^^ Diagram that explains clearly OAuth with MCP Lifecycle
from dotenv import load_dotenv

import logging
import secrets
import time 
from typing import Any, Literal
import base64
import hashlib
from jose import jwt 

import click
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    OAuthAuthorizationServerProvider,
    construct_redirect_uri
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp.server import FastMCP
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

logger = logging.getLogger(__name__)
load_dotenv()

class ServerSettings(BaseSettings):
    """Settings for this mcp server"""

    model_config = SettingsConfigDict(env_prefix="MCP_", extra="forbid")

    host: str = "localhost"
    port: int = 8000
    server_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000/mcp")

    #keys(VVIP)
    private_key: str = "1405198632"
    public_key: str = "867473"
    token_expiration: int = 3600

    #oauth settings
    client_id: str 
    client_secret: str
    callback_path: str = "http://localhost:8000/callback"

    #auth urls
    auth_url: str = "http://localhost:8000/auth_url"
    token_url: str = "http://localhost:8000/token_url"

    mcp_scope: str = "user"

    def __init__(self, **data):
        """
            Initialise settings using .env data
        """
        super().__init__(**data)

class SimpleOauthProvider(OAuthAuthorizationServerProvider):
    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.tokens: dict[str, AccessToken] = {}
        self.state_mapping: dict[str, dict[str, str]] = {}


    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        """Get OAuth client information"""
        return self.clients.get(client_id)
    
    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Register a new OAuth client"""
        self.clients[client_info.client_id] = client_info

    async def authorize(self, client: OAuthClientInformationFull, params:AuthorizationParams) -> str:
        """Generate an authorization url for the client"""

        state = params.state or secrets.token_hex(16)

        #store the state mapping
        self.state_mapping[state] = {
            "redirect_uri": str(params.redirect_uri),
            "code_challenge": params.code_challenge,
            "redirected_uri_provided_explicitly": str(params.redirect_uri_provided_explicitly),
            "client_id": client.client_id,
            "code_verifier": ""
        }

        #build auth code

        code = secrets.token_urlsafe(32)
        auth_code = AuthorizationCode(
            code = code,
            client_id=self.settings.client_id,
            redirect_uri= AnyHttpUrl(self.settings.callback_path),
            scopes = [self.settings.mcp_scope],
            code_challenge=self.state_mapping[state]["code_challenge"],
            expires_at=time.time() + 300,
            redirect_uri_provided_explicitly= True
        ) 

        self.auth_codes[code] = auth_code

        #build auth url

        auth_url = (
            f"{self.settings.auth_url}"
            f"?client_id={self.settings.client_id}"
            f"?code={code}"
            f"&redirect_uri={self.settings.callback_path}"
            f"&scope={self.settings.mcp_scope}"
            f"&state={state}"
        )

        return auth_url
    
    def _verify_code_challenge(self, code_verifier: str, code_challenge: str) -> bool:
        """Validate Proof Key for Code Exchange (PKCE) using SHA256 method"""
        try:
            challenge = base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            ).decode().rstrip("=")
            return challenge == code_challenge
        except Exception as e:
            logger.error(f"PKCE verification failed: {str(e)}")
            return False 
    
    def _generate_access_token(self, client_id: str, scopes: list[str], expires_in: int) -> str:
        """Genrate JWT access token with server-signed claims"""
        return jwt.encode(
            {
                "iss":self.settings.server_url,
                "sub":client_id,
                "exp":time.time() + expires_in,
                "scopes": " ".join(scopes),
                "aud": "mcp-server"
            },
            self.settings.private_key,
            algorithm="RS256"
        )

    async def handle_callback(self, code: str, state: str) -> str:
        """Handle OAuth callback"""

        state_data = self.state_mapping.get(state)
        if not state_data:
            raise HTTPException(400, "Invalid state parameter")

        redirect_uri = state_data["redirect_uri"]
        code_challenge = state_data["code_challenge"]
        redirect_uri_provided_explicitly = (state_data["redirect_uri_provided_explicitly"])
        client_id = state_data["client_id"]

        #validate authorization code 
        try:
            auth_code = self.auth_codes.get(code)

            if not auth_code:
                raise HTTPException(400, "Invalid authentication code")
            if  auth_code.expires_at < time.time():
                raise HTTPException(400, "Expired auth code")

            #verify code challenge
            code_verifier = state_data.get("code_verifier")
            
            if not self._verify_code_challenge(code_verifier, code_challenge): # type: ignore
                raise HTTPException(400, "Code challenge verification failed")
            
            access_token = self._generate_access_token(
                    client_id=client_id,
                    scopes=auth_code.scopes,
                    expires_in=3600
            )

            self.tokens[access_token] = AccessToken(
                token = access_token,
                client_id=client_id,
                scopes=[self.settings.mcp_scope],
                expires_at= None
            )

            del self.state_mapping[state]

            return construct_redirect_uri(
                redirect_uri,
                access_token=access_token,
                token_type="Bearer",
                expires_in= "3600"
            )

        except KeyError as e:
            logger.error(f"Missing critical parameter: {str(e)}")
            raise HTTPException(500, "Internal server error")




    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str) -> Any | None:
        """Load the auth code"""
        return self.auth_codes.get(authorization_code)
    
    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code: Any) -> OAuthToken:
        """Exchange auth code for access and refresh tokens"""
        if authorization_code.code not in self.auth_codes:
            raise ValueError("Invalid auth code")
        
        mcp_token = f"mcp_{secrets.token_hex(32)}"

        self.tokens[mcp_token] = AccessToken(
            token = mcp_token,
            client_id = client.client_id,
            scopes = authorization_code.scopes,
            expires_at= int(time.time()) + 3600
        )

        del self.auth_codes[authorization_code.code]

        return OAuthToken(
            access_token=mcp_token,
            token_type="bearer",
            expires_in=3600,
            scope="".join(authorization_code.scopes)
        )
    
    async def load_access_token(self, token: str) -> Any | None:
        """Load and validate an access token"""
        access_token = self.tokens.get(token)
        if not access_token:
            return None
        
        if access_token.expires_at and access_token.expires_at < time.time():
            del self.tokens[token]
            return None
        
        return access_token
    

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> Any | None:
        """Load a refresh token not supported lol"""
        return None
    
    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: Any, scopes: list[str]) -> OAuthToken:
        """Bigger lol"""
        raise NotImplementedError("Function not supported. Please redo authorisation process")
    

    async def revoke_token(self, token: str, token_type_hint: str | None = None) -> None:
        """Revoke a token"""
        if token in self.tokens:
            del self.tokens[token]


def create_simple_mcp_server(settings: ServerSettings) -> FastMCP:
    """Create a simple FastMCP server with Github OAut"""
    oauth_provider = SimpleOauthProvider(settings)

    auth_settings = AuthSettings(
        issuer_url = settings.server_url,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[settings.mcp_scope],
            default_scopes=[settings.mcp_scope]
        ),
        required_scopes=[settings.mcp_scope]
    )

    app = FastMCP(
        name = "Simple Weather Server",
        instructions = "A simple MCP Server with OAuth authentication for checking the weather of a location",
        auth_server_provider=oauth_provider,
        host=settings.host,
        port=settings.port,
        debug=True,
        auth=auth_settings
    )

    @app.custom_route("/callback", methods=["POST"])
    async def callback_handler(request: Request) -> Response:
        """Handle callback"""
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code or not state:
            raise HTTPException(400, "Missing code or state parameter. We don't check which one, please do so on your own.")
        
        try:
            redirect_uri = await oauth_provider.handle_callback(code, state)
            return RedirectResponse(status_code=302, url=redirect_uri)
        
        except HTTPException:
            raise 

        except Exception as e:
            logger.error("Unexpected error", exc_info=e)
            return JSONResponse(
                status_code=500,
                content={
                    "error":"server_error",
                    "error_desription":"Unexpected Error"
                },
            )
    
    @app.custom_route("/mcp/register", methods=["POST"])
    async def register_client(request: Request):
        client_metadata = await request.json()
        client_id = secrets.token_urlsafe(16)
        client_secret = secrets.token_urlsafe(32)
        
        # Store client in your provider's registry
        client_info = OAuthClientInformationFull(
            client_id=client_id,
            client_secret=client_secret,
            **client_metadata
        )

        await oauth_provider.register_client(client_info=client_info)
        
        return JSONResponse({
            "client_id": client_id,
            "client_secret": client_secret,
            "token_endpoint_auth_method": "client_secret_post"
        })


    def get_token() -> AccessToken:
        """Get the token for the authenticated user"""
        access_token = get_access_token()
        if not access_token:
            raise ValueError("Not authenticated")
        
        token = oauth_provider.tokens.get(access_token.token)

        if not token:
            raise ValueError("No token found for the user")
        
        return token
    
    @app.tool()
    async def get_weather() -> str:
        """Get weather information"""
        return "It is very hot in Hyderabad, Telangana, India,"
    

    return app 

@click.command()
@click.option("--port", default=8000, help="Port to listen on")
@click.option("--host", default="localhost", help="Host to bind to")
@click.option(
    "--transport",
    default="streamable-http",
    type=click.Choice(["sse", "streamable-http"]),
    help="Transport protocol to use ('sse' or 'streamable-http')",
)

def main(port: int, host: str, transport: Literal["sse", "streamable-http"]) -> int:
    """Run the simple GitHub MCP server."""
    logging.basicConfig(level=logging.INFO)

    try:
        # No hardcoded credentials - all from environment variables
        settings = ServerSettings(host=host, port=port)
    except ValueError as e:
        logger.error(
            "Failed to load settings. Make sure environment variables are set:"
        )
        logger.error("MCP_CLIENT_ID=<your-client-id>")
        logger.error("MCP_CLIENT_SECRET=<your-client-secret>")
        logger.error(f"Error: {e}")
        return 1

    mcp_server = create_simple_mcp_server(settings)
    logger.info(f"Starting server with {transport} transport")
    mcp_server.run(transport=transport)
    return 0

if __name__ == "__main__":
    main()