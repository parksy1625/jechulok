"""JeChulOK v2.1 explicit, read-only check for a published stable GitHub release.

Network is ONLY used when the user invokes setup_mcp.py updates --online.
Never downloads, executes an update, modifies configuration, or transmits a
notice. The endpoint is fixed, HTTPS-only; output is bounded and sanitized.
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://api.github.com/repos/parksy1625/jechulok/releases/latest"
RELEASE_PAGE = "https://github.com/parksy1625/jechulok/releases"
MAX_JSON_BYTES = 65536
VERSION_PATTERN = re.compile(r"^v?(\d{1,4})\.(\d{1,4})\.(\d{1,4})$")


def version_tuple(value: str) -> tuple[int, int, int]:
    """Strict stable-version comparison (no prerelease or arbitrary URLs)."""
    if type(value) is not str:
        raise ValueError("Invalid semantic version")
    match = VERSION_PATTERN.fullmatch(value)
    if not match:
        raise ValueError("Invalid stable version")
    return tuple(map(int, match.groups()))


def check_latest(current_version: str, *, online: bool = False, timeout: float = 5.0) -> dict:
    current = version_tuple(current_version)
    report = {
        "current_version": current_version,
        "release_page": RELEASE_PAGE,
        "download_performed": False,
        "automatic_update": False,
        "client_config_changed": False,
        "user_documents_transmitted": False,
        "publisher_identity_verified": False,
    }
    if not online:
        return {
            **report, "status": "offline",
            "message": "No network check was performed. Add --online to contact GitHub explicitly.",
            "latest_version": None,
        }
    try:
        req = Request(
            ENDPOINT, headers={"Accept": "application/vnd.github+json",
                               "User-Agent": "JeChulOK-local-version-check/2.1"},
        )
        with urlopen(req, timeout=timeout) as response:
            # Limit memory and reject unexpectedly large or malformed replies.
            payload = response.read(MAX_JSON_BYTES + 1)
            if len(payload) > MAX_JSON_BYTES:
                raise ValueError("Oversized release metadata")
        parsed = json.loads(payload)
        if type(parsed) is not dict or type(parsed.get("tag_name")) is not str:
            raise ValueError("Invalid release metadata")
        remote = version_tuple(parsed["tag_name"])
    except HTTPError as exc:
        if exc.code == 404:
            return {
                **report, "status": "no_published_release", "latest_version": None,
                "message": "GitHub reports no published stable release; local version was not changed.",
            }
        return {
            **report, "status": "unavailable", "latest_version": None,
            "message": "GitHub release API could not be read (rate limit, server or permissions).",
        }
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError, json.JSONDecodeError):
        return {
            **report, "status": "unavailable", "latest_version": None,
            "message": "Release metadata was unavailable or invalid. No update was performed.",
        }
    latest = ".".join(map(str, remote))
    return {
        **report,
        "status": "update_available" if remote > current else
                  "up_to_date" if remote == current else "local_newer",
        "latest_version": latest,
        "message": (
            "A newer published stable release exists; verify its source and review before upgrading."
            if remote > current else
            "The local version is not older than the latest published stable release."
        ),
    }
