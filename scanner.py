"""
CommitCraft - Deterministic Secret Scanner
Scans staged Git diff additions for exposed credentials, tokens, and private keys.
"""

from __future__ import annotations

import re

# Primary pattern requested by specification
PATTERN_CREDENTIAL_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|secret|password|token|bearer)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{8,}['\"]"
)

# Unquoted assignment or environment file style key=val
PATTERN_UNQUOTED_CREDENTIAL = re.compile(
    r"(?i)^\s*(api[_-]?key|secret|password|token|bearer)\s*[:=]\s*([a-zA-Z0-9_\-]{12,})\s*$"
)

# Common SSH / RSA / EC private key headers
PATTERN_PRIVATE_KEY_HEADER = re.compile(
    r"-----BEGIN\s+(?:[A-Z0-9_-]+\s+)?PRIVATE\s+KEY-----"
)

# Well-known API token signatures (AWS, GitHub, Slack)
PATTERN_WELL_KNOWN_TOKENS = re.compile(
    r"(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{36,}|xox[baprs]-[0-9a-zA-Z]{10,})"
)

# Sensitive .env file references or additions
PATTERN_ENV_REFERENCE = re.compile(
    r"(?i)\.env(?:\.[a-zA-Z0-9_-]+)?\b"
)


def scan_diff_for_secrets(diff_text: str) -> list[str]:
    """
    Inspects diff additions (lines starting with '+') for exposed credentials.

    Args:
        diff_text: Raw Git diff string.

    Returns:
        List of human-readable security warning strings.
        Returns an empty list if no secrets or credentials are found.
    """
    if not diff_text or not diff_text.strip():
        return []

    warnings: list[str] = []
    lines = diff_text.splitlines()

    for line_idx, raw_line in enumerate(lines, start=1):
        # Only inspect added lines in the diff, excluding diff file headers (+++ b/...)
        if not raw_line.startswith("+") or raw_line.startswith("+++"):
            continue

        added_content = raw_line[1:].strip()
        if not added_content:
            continue

        line_warnings: list[str] = []

        # 1. Private Key Header
        if PATTERN_PRIVATE_KEY_HEADER.search(added_content):
            line_warnings.append(
                f"Line {line_idx}: Private cryptographic key header detected (e.g., -----BEGIN PRIVATE KEY-----)."
            )

        # 2. Credential assignment (API key, token, secret, password)
        elif cred_match := PATTERN_CREDENTIAL_ASSIGNMENT.search(added_content):
            matched_key = cred_match.group(1)
            line_warnings.append(
                f"Line {line_idx}: Hardcoded {matched_key.lower()} assignment detected."
            )

        # 3. Unquoted credential assignment
        elif unquoted_match := PATTERN_UNQUOTED_CREDENTIAL.search(added_content):
            matched_key = unquoted_match.group(1)
            line_warnings.append(
                f"Line {line_idx}: Unquoted {matched_key.lower()} assignment detected."
            )

        # 4. Well-known token formats (AWS, GitHub, Slack)
        elif PATTERN_WELL_KNOWN_TOKENS.search(added_content):
            line_warnings.append(
                f"Line {line_idx}: Well-known cloud/service access token format detected."
            )

        # 5. Sensitive .env file references
        if PATTERN_ENV_REFERENCE.search(added_content):
            if not line_warnings:
                line_warnings.append(
                    f"Line {line_idx}: Reference to sensitive '.env' file detected. Verify credentials are not committed."
                )

        warnings.extend(line_warnings)

    return warnings
