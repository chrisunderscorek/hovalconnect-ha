#!/usr/bin/env python3
"""Debug helper for Hoval OAuth tokens.

This tool is intentionally local-only: it never writes credentials or tokens to
disk. It prints tokens to stdout because it is meant for manual debugging.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


AUTH_TOKEN_URL = "https://akwc5scsc.accounts.ondemand.com/oauth2/token"
API_BASE_URL = "https://azure-iot-prod.hoval.com/core"
CLIENT_ID = "991b54b2-7e67-47ef-81fe-572e21c59899"
DEFAULT_SCOPE = "openid offline_access"

APP_HEADERS = {
    "User-Agent": "HovalConnect/6022 CFNetwork/3860.400.51 Darwin/25.3.0",
    "Accept": "application/json",
    "x-requested-with": "XMLHttpRequest",
    "hovalconnect-frontend-app-version": "3.1.4",
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
    return parser


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
            **APP_HEADERS,
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


def print_token_response(token_data: dict, json_output: bool) -> None:
    if json_output:
        print(json.dumps(token_data, indent=2, sort_keys=True))
        return

    for key in ("access_token", "refresh_token", "id_token", "token_type", "expires_in", "scope"):
        if key in token_data:
            print(f"{key}:")
            print(token_data[key])

    extra_keys = sorted(
        key
        for key in token_data
        if key not in {"access_token", "refresh_token", "id_token", "token_type", "expires_in", "scope"}
    )
    if extra_keys:
        print("extra_response_keys:")
        print(", ".join(extra_keys))


def print_sample_curl(access_token: str | None = None) -> None:
    token = access_token or "<ACCESS_TOKEN>"
    print("sample_curl:")
    print(
        "curl -sS "
        "-H 'Accept: application/json' "
        f"-H 'Authorization: Bearer {token}' "
        f"'{API_BASE_URL}/v3/api-docs'"
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.sample_curl and not args.username:
        print_sample_curl()
        return 0

    if not args.username:
        parser.error("--username is required unless only --sample-curl is used")

    if args.password and args.password_stdin:
        parser.error("--password and --password-stdin cannot be used together")

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

    print_token_response(token_data, args.json)

    if args.sample_curl:
        access_token = token_data.get("access_token") or token_data.get("id_token")
        print()
        print_sample_curl(access_token)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
