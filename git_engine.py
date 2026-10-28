"""
CommitCraft - Git Engine
Safely interfaces with local Git repository to extract staged diffs.
"""

from __future__ import annotations

import os
import subprocess


def get_staged_diff(repo_path: str = ".") -> tuple[bool, str]:
    """
    Executes 'git diff --staged' in the specified repository path.

    Args:
        repo_path: Filesystem path to the Git repository (defaults to current directory).

    Returns:
        tuple[bool, str]: (True, diff_text) on success, or (False, error_message) on failure.
    """
    normalized_path = os.path.abspath(os.path.expanduser(repo_path.strip()))

    if not os.path.exists(normalized_path):
        return False, f"Path does not exist: '{normalized_path}'"

    if not os.path.isdir(normalized_path):
        return False, f"Path is not a directory: '{normalized_path}'"

    try:
        # First verify if target directory is inside a valid Git repository
        check_repo = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=normalized_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if check_repo.returncode != 0:
            return False, f"Not a Git repository: '{normalized_path}'"

        result = subprocess.run(
            ["git", "diff", "--staged"],
            cwd=normalized_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
    except FileNotFoundError:
        return False, "Git command not found. Please ensure Git is installed and available in your system PATH."
    except subprocess.TimeoutExpired:
        return False, "Git command timed out after 15 seconds."
    except PermissionError:
        return False, f"Permission denied while trying to access repository at: '{normalized_path}'"
    except Exception as exc:
        return False, f"Unexpected error while querying Git: {str(exc)}"

    if result.returncode != 0:
        stderr_msg = result.stderr.strip()
        if "not a git repository" in stderr_msg.lower():
            return False, f"Not a Git repository: '{normalized_path}'"
        return False, f"Git error (exit code {result.returncode}): {stderr_msg or 'Unknown error'}"

    diff_text = result.stdout.strip()
    if not diff_text:
        return False, "No staged changes detected. Please stage files using 'git add <files>' or paste a diff manually."

    return True, diff_text


def truncate_diff(diff_text: str, max_chars: int = 1500) -> str:
    """
    Truncates large diff text to ensure local AI models remain responsive.

    Args:
        diff_text: Full Git diff text.
        max_chars: Maximum character budget (default: 1500 chars).

    Returns:
        Compact diff string with truncation notice if exceeded.
    """
    if not diff_text:
        return ""

    if len(diff_text) <= max_chars:
        return diff_text

    trimmed = diff_text[:max_chars].rstrip()
    return f"{trimmed}\n\n[Diff truncated to {max_chars} characters for local AI performance]"
