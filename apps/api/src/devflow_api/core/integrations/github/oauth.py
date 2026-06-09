"""GitHub OAuth App flow — authorization URL and code→token exchange."""

from dataclasses import dataclass

import httpx

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_SCOPES = "read:user,repo"


@dataclass(frozen=True)
class OAuthTokenResult:
    access_token: str
    scopes: str


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    params = (
        f"client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={GITHUB_SCOPES}"
        f"&state={state}"
    )
    return f"{GITHUB_AUTHORIZE_URL}?{params}"


async def exchange_code_for_token(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> OAuthTokenResult:
    """Exchange an OAuth authorization code for an access token."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
            timeout=15.0,
        )
        response.raise_for_status()
        data: dict[str, object] = response.json()

    error = data.get("error")
    if error:
        description = data.get("error_description")
        raise ValueError(f"GitHub OAuth error: {error} — {description}")

    access_token = str(data["access_token"])
    scopes = str(data.get("scope", ""))
    return OAuthTokenResult(access_token=access_token, scopes=scopes)
