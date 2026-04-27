#!/usr/bin/env python3
"""Debug helper for Hoval OAuth tokens.

This tool is intentionally local-only: it never writes credentials or tokens to
disk. It prints tokens to stdout because it is meant for manual debugging.
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


AUTH_TOKEN_URL = "https://akwc5scsc.accounts.ondemand.com/oauth2/token"
API_BASE_URL = "https://azure-iot-prod.hoval.com/core"
CLIENT_ID = "991b54b2-7e67-47ef-81fe-572e21c59899"
DEFAULT_SCOPE = "openid offline_access"
DEFAULT_FRONTEND_APP_VERSION = "3.2.0"
DEFAULT_USER_AGENT = "HovalConnect/6022 CFNetwork/3860.400.51 Darwin/25.3.0"
GOOGLE_PLAY_URL = "https://play.google.com/store/apps/details?id=com.hoval.connect2&hl=en_US&gl=US"
APPLE_APP_STORE_URL = "https://apps.apple.com/pl/app/hovalconnect/id1594860714"
APPLE_LOOKUP_URL = "https://itunes.apple.com/lookup?id=1594860714&country=pl"


def app_headers(frontend_version: str, user_agent: str) -> dict[str, str]:
    return {
        "User-Agent": user_agent,
        "Accept": "application/json",
        "x-requested-with": "XMLHttpRequest",
        "hovalconnect-frontend-app-version": frontend_version,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Exchange HovalConnect username/password for OAuth token data and "
            "print the result for debugging."
        )
    )
    parser.add_argument("-u", "--username", "--email", dest="username", help="HovalConnect username/email")
    parser.add_argument(
        "-p",
        "--password",
        help="HovalConnect password. Omit this to read it via a hidden prompt.",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the password from stdin instead of prompting.",
    )
    parser.add_argument("--token-url", default=AUTH_TOKEN_URL, help=f"OAuth token URL (default: {AUTH_TOKEN_URL})")
    parser.add_argument("--client-id", default=CLIENT_ID, help="OAuth client_id")
    parser.add_argument("--scope", default=DEFAULT_SCOPE, help=f"OAuth scope (default: {DEFAULT_SCOPE!r})")
    parser.add_argument("--timeout", type=float, default=20.0, help="HTTP timeout in seconds")
    parser.add_argument("--store-timeout", type=float, default=8.0, help="Store version lookup timeout in seconds")
    parser.add_argument(
        "--frontend-version",
        "--bump-app-version",
        dest="frontend_version",
        help="Skip store probing and use this Hoval frontend app version header",
    )
    parser.add_argument(
        "--store-versions",
        action="store_true",
        help="Fetch and print Google Play / Apple App Store versions, then exit if no token action is requested.",
    )
    parser.add_argument(
        "--only-tokens",
        action="store_true",
        help="Suppress store probing output and diagnostics; print token fields only.",
    )
    parser.add_argument("--google-play-url", default=GOOGLE_PLAY_URL, help="Google Play app details URL")
    parser.add_argument("--apple-app-store-url", default=APPLE_APP_STORE_URL, help="Apple App Store page URL")
    parser.add_argument("--apple-lookup-url", default=APPLE_LOOKUP_URL, help="Apple iTunes lookup URL")
    parser.add_argument(
        "--probe-frontend-versions",
        help=(
            "Comma-separated frontend versions to test with --test-api-docs, "
            "for example: 3.2.0,3.1.4,2.8.3"
        ),
    )
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="HTTP User-Agent header")
    parser.add_argument("--access-token", help="Existing OAuth access_token to inspect or use if it is JWT-shaped.")
    parser.add_argument("--id-token", help="Existing OIDC id_token to inspect or use if it is JWT-shaped.")
    parser.add_argument("--api-bearer-token", help="Existing API bearer token to use directly.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete token response as JSON.",
    )
    parser.add_argument(
        "--sample-curl",
        action="store_true",
        help="Print a sample curl call for GET /v3/api-docs on the Hoval API base URL.",
    )
    parser.add_argument(
        "--test-api-docs",
        action="store_true",
        help="Call GET /v3/api-docs with the selected API bearer token and print the response status.",
    )
    return parser


@dataclass(frozen=True)
class StoreVersion:
    source: str
    version: str | None
    url: str
    error: str | None = None


def fetch_text(url: str, timeout: float, user_agent: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": user_agent,
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_google_play_version(html: str) -> str | None:
    # Google Play embeds the current version in page data instead of exposing a
    # stable public API. Keep parsing conservative and let callers fall back.
    patterns = (
        r'"141":\[\[\["([0-9]+(?:\.[0-9]+)+)"\]\]',
        r'\[\[\["([0-9]+(?:\.[0-9]+)+)"\]\],\[\[\[[0-9]+\]\]',
    )
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return None


def parse_apple_lookup_version(payload: str) -> str | None:
    data = json.loads(payload)
    results = data.get("results", [])
    if not results:
        return None
    version = results[0].get("version")
    return str(version) if version else None


def parse_apple_app_store_page_version(html: str) -> str | None:
    match = re.search(r'"softwareVersion"\s*:\s*"([^"]+)"', html)
    if match:
        return match.group(1)
    match = re.search(r'\bVersion\s+([0-9]+(?:\.[0-9]+)+)\b', html)
    if match:
        return match.group(1)
    return None


def fetch_store_versions(args: argparse.Namespace) -> list[StoreVersion]:
    results: list[StoreVersion] = []

    try:
        google_html = fetch_text(args.google_play_url, args.store_timeout, args.user_agent)
        google_version = parse_google_play_version(google_html)
        if google_version:
            results.append(StoreVersion("google_play", google_version, args.google_play_url))
        else:
            results.append(StoreVersion("google_play", None, args.google_play_url, "Version not found"))
    except Exception as err:
        results.append(StoreVersion("google_play", None, args.google_play_url, str(err)))

    try:
        apple_payload = fetch_text(args.apple_lookup_url, args.store_timeout, args.user_agent)
        apple_version = parse_apple_lookup_version(apple_payload)
        if not apple_version:
            apple_html = fetch_text(args.apple_app_store_url, args.store_timeout, args.user_agent)
            apple_version = parse_apple_app_store_page_version(apple_html)
        if apple_version:
            results.append(StoreVersion("apple_app_store", apple_version, args.apple_app_store_url))
        else:
            results.append(StoreVersion("apple_app_store", None, args.apple_app_store_url, "Version not found"))
    except Exception as err:
        results.append(StoreVersion("apple_app_store", None, args.apple_app_store_url, str(err)))

    return results


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", version))


def select_frontend_version(
    args: argparse.Namespace,
    store_versions: list[StoreVersion],
) -> tuple[str, str]:
    if args.frontend_version:
        return args.frontend_version, "manual"

    found_versions = [item for item in store_versions if item.version]
    if not found_versions:
        return DEFAULT_FRONTEND_APP_VERSION, "fallback"

    selected = max(found_versions, key=lambda item: version_key(item.version or "0"))
    return selected.version or DEFAULT_FRONTEND_APP_VERSION, selected.source


def print_store_versions(store_versions: list[StoreVersion], selected_version: str, selected_source: str) -> None:
    print("store_versions:")
    for item in store_versions:
        if item.version:
            print(f"{item.source}: {item.version}")
        else:
            print(f"{item.source}: <not found>")
            if item.error:
                print(f"{item.source}_error: {item.error}")
        print(f"{item.source}_url: {item.url}")
    print("selected_frontend_version:")
    print(f"{selected_version} ({selected_source})")


def post_token_request(args: argparse.Namespace, password: str) -> dict:
    form = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "client_id": args.client_id,
            "username": args.username,
            "password": password,
            "scope": args.scope,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        args.token_url,
        data=form,
        headers={
            **app_headers(args.frontend_version, args.user_agent),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Token request failed with HTTP {err.code}: {body}") from err
    except urllib.error.URLError as err:
        raise RuntimeError(f"Token request failed: {err.reason}") from err

    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Token response is not JSON: {raw}") from err


@dataclass(frozen=True)
class ApiDocsResponse:
    status: int
    headers: dict[str, str]
    body: str


def get_api_docs(
    bearer_token: str,
    timeout: float,
    frontend_version: str,
    user_agent: str,
) -> ApiDocsResponse:
    request = urllib.request.Request(
        f"{API_BASE_URL}/v3/api-docs",
        headers={
            **app_headers(frontend_version, user_agent),
            "Authorization": f"Bearer {bearer_token}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return ApiDocsResponse(
                status=response.status,
                headers=dict(response.headers.items()),
                body=response.read().decode("utf-8", errors="replace"),
            )
    except urllib.error.HTTPError as err:
        return ApiDocsResponse(
            status=err.code,
            headers=dict(err.headers.items()),
            body=err.read().decode("utf-8", errors="replace"),
        )
    except urllib.error.URLError as err:
        raise RuntimeError(f"API docs request failed: {err.reason}") from err


def print_token_response(token_data: dict, json_output: bool, only_tokens: bool = False) -> None:
    if json_output:
        print(json.dumps(token_data, indent=2, sort_keys=True))
        return

    bearer_token, bearer_source = api_bearer_token(token_data)
    if bearer_token and not only_tokens:
        print("api_bearer_token_source:")
        print(bearer_source)
        print("api_bearer_token:")
        print(bearer_token)

    if not only_tokens:
        print("token_diagnostics:")
        for key in ("access_token", "id_token", "api_bearer_token"):
            if token_data.get(key):
                print(f"{key}.looks_like_jwt: {str(looks_like_jwt(token_data[key])).lower()}")

    for key in ("access_token", "refresh_token", "id_token", "token_type", "expires_in", "scope"):
        if key in token_data:
            print(f"{key}:")
            print(token_data[key])

    if not only_tokens:
        extra_keys = sorted(
            key
            for key in token_data
            if key not in {"access_token", "refresh_token", "id_token", "token_type", "expires_in", "scope"}
        )
        if extra_keys:
            print("extra_response_keys:")
            print(", ".join(extra_keys))


def looks_like_jwt(token: str | None) -> bool:
    return bool(token and token.count(".") == 2)


def api_bearer_token(token_data: dict) -> tuple[str | None, str]:
    explicit_bearer = token_data.get("api_bearer_token")
    id_token = token_data.get("id_token")
    access_token = token_data.get("access_token")

    # The Hoval API rejects opaque OAuth access tokens as malformed JWTs. Prefer
    # a JWT-shaped id_token/access_token, or an explicit override for testing.
    if explicit_bearer:
        return explicit_bearer, "api_bearer_token"
    if looks_like_jwt(id_token):
        return id_token, "id_token"
    if looks_like_jwt(access_token):
        return access_token, "access_token"
    return None, "none"


def print_sample_curl(
    bearer_token: str | None = None,
    frontend_version: str = DEFAULT_FRONTEND_APP_VERSION,
) -> None:
    token = bearer_token or "<API_BEARER_TOKEN>"
    print("sample_curl:")
    print(
        "curl -sS "
        "-H 'Accept: application/json' "
        "-H 'x-requested-with: XMLHttpRequest' "
        f"-H 'hovalconnect-frontend-app-version: {frontend_version}' "
        f"-H 'Authorization: Bearer {token}' "
        f"'{API_BASE_URL}/v3/api-docs'"
    )


def frontend_versions_to_test(args: argparse.Namespace) -> list[str]:
    if not args.probe_frontend_versions:
        return [args.frontend_version]
    versions = [item.strip() for item in args.probe_frontend_versions.split(",")]
    return [version for version in versions if version]


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    should_fetch_store_versions = (not args.only_tokens) and (not args.frontend_version or args.store_versions)
    store_versions = fetch_store_versions(args) if should_fetch_store_versions else []
    selected_frontend_version, selected_frontend_source = select_frontend_version(args, store_versions)
    args.frontend_version = selected_frontend_version

    provided_token_data = {
        key: value
        for key, value in {
            "access_token": args.access_token,
            "id_token": args.id_token,
            "api_bearer_token": args.api_bearer_token,
        }.items()
        if value
    }
    wants_token_action = bool(
        args.username
        or provided_token_data
        or args.sample_curl
        or args.test_api_docs
    )

    if store_versions and not args.json and not args.only_tokens:
        print_store_versions(store_versions, selected_frontend_version, selected_frontend_source)
        if wants_token_action:
            print()

    if args.store_versions and not wants_token_action:
        if args.json:
            print(
                json.dumps(
                    {
                        "store_versions": [item.__dict__ for item in store_versions],
                        "selected_frontend_version": selected_frontend_version,
                        "selected_frontend_source": selected_frontend_source,
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        return 0

    if args.sample_curl and not args.username and not provided_token_data and not args.test_api_docs:
        print_sample_curl(frontend_version=args.frontend_version)
        return 0

    if not args.username and not provided_token_data:
        parser.error("--username or an existing token is required")

    if args.password and args.password_stdin:
        parser.error("--password and --password-stdin cannot be used together")

    if provided_token_data:
        token_data = provided_token_data
    else:
        if args.password_stdin:
            password = sys.stdin.read().rstrip("\r\n")
        else:
            password = args.password if args.password is not None else getpass.getpass("Hoval password: ")

        if not password:
            parser.error("password must not be empty")

        try:
            token_data = post_token_request(args, password)
        except RuntimeError as err:
            print(err, file=sys.stderr)
            return 1

    print_token_response(token_data, args.json, args.only_tokens)
    bearer_token, bearer_source = api_bearer_token(token_data)

    if args.sample_curl:
        print()
        if bearer_token:
            print_sample_curl(bearer_token, args.frontend_version)
        else:
            print(
                "No JWT-shaped API bearer token found. Use --id-token or --api-bearer-token.",
                file=sys.stderr,
            )
            return 1

    if args.test_api_docs:
        if not bearer_token:
            print(
                "No JWT-shaped API bearer token found. Use --id-token or --api-bearer-token.",
                file=sys.stderr,
            )
            return 1
        last_response = None
        for frontend_version in frontend_versions_to_test(args):
            try:
                response = get_api_docs(
                    bearer_token,
                    args.timeout,
                    frontend_version,
                    args.user_agent,
                )
            except RuntimeError as err:
                print(err, file=sys.stderr)
                return 1
            last_response = response

            print()
            print("api_docs_test:")
            print(f"frontend_version: {frontend_version}")
            print(f"status: {response.status}")
            if response.headers.get("WWW-Authenticate"):
                print("www_authenticate:")
                print(response.headers["WWW-Authenticate"])
            if response.status == 426 and response.body:
                print("upgrade_required_body:")
                print(response.body)
            elif response.status < 400:
                print("api_docs_body:")
                print(response.body)
                return 0

        if last_response and last_response.status >= 400:
            print(f"API docs request failed using {bearer_source}.", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
