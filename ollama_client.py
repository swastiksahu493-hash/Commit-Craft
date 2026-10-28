"""
CommitCraft - Local Ollama Client
Interfaces strictly with local Ollama instance (http://localhost:11434) using standard library urllib.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request


OLLAMA_API_URL = "http://localhost:11434/api/generate"


def _build_prompt(diff_text: str) -> str:
    """Constructs a strict one-shot prompt forcing conventional commit and 3-bullet PR format."""
    return f"""You are an expert developer assistant specialized in Conventional Commits and clean Pull Request documentation.
Analyze the following Git diff and generate:
1. A Conventional Commit message adhering to: <type>(<scope>): <concise imperative description>
2. A Pull Request summary consisting of exactly 3 concise Markdown bullet points.

You MUST follow this EXACT format with no other text, no preamble, and no markdown code blocks:

COMMIT: feat(auth): add logout token invalidation
PR:
- Add token blacklist check to authentication middleware
- Invalidate active JWT refresh tokens upon user logout
- Add integration test suite for session termination

Git Diff:
{diff_text}

Output:"""


def _parse_llm_response(raw_text: str) -> tuple[str, str]:
    """
    Extracts the commit message and 3-bullet PR summary from the model response.
    Handles potential LLM quirks such as reasoning tags, markdown fences, and minor formatting drift.
    """
    if not raw_text:
        return "", ""

    # Strip thinking tags (e.g., <think>...</think> from reasoning models)
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", raw_text).strip()

    # Strip markdown code blocks if the model enclosed its response in them
    cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned).strip()

    commit_msg = ""
    pr_body = ""

    # Case 1: Standard COMMIT: and PR: markers present
    commit_match = re.search(r"COMMIT\s*:\s*([^\n\r]+)", cleaned, re.IGNORECASE)
    pr_match = re.search(r"PR\s*:\s*([\s\S]*)", cleaned, re.IGNORECASE)

    if commit_match:
        commit_msg = commit_match.group(1).strip()
        # Clean up any surrounding quotes or backticks
        commit_msg = commit_msg.strip("`'\" ")

    if pr_match:
        raw_pr = pr_match.group(1).strip()
        bullets: list[str] = []
        for line in raw_pr.splitlines():
            line_str = line.strip()
            if not line_str:
                continue
            # Match lines starting with -, *, or numbered bullets
            bullet_match = re.match(r"^[-*•\d\.)]+\s*(.*)$", line_str)
            if bullet_match:
                content = bullet_match.group(1).strip()
                if content:
                    bullets.append(f"- {content}")
            else:
                # If model omitted bullet marker, still preserve the line
                bullets.append(f"- {line_str}")

        if bullets:
            pr_body = "\n".join(bullets[:3])
        else:
            pr_body = raw_pr

    # Case 2: Fallback if markers were omitted by the model
    if not commit_msg or not pr_body:
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if lines:
            if not commit_msg:
                commit_msg = lines[0].replace("COMMIT:", "").strip("`'\" ")
            if not pr_body and len(lines) > 1:
                bullets = []
                for line in lines[1:]:
                    if line.upper().startswith("PR:"):
                        continue
                    bullet_match = re.match(r"^[-*•\d\.)]+\s*(.*)$", line)
                    if bullet_match:
                        content = bullet_match.group(1).strip()
                        if content:
                            bullets.append(f"- {content}")
                    else:
                        bullets.append(f"- {line}")
                pr_body = "\n".join(bullets[:3]) if bullets else "\n".join(lines[1:4])

    return commit_msg, pr_body


def generate_commit_and_pr(diff_text: str, model_name: str = "qwen2.5:3b") -> tuple[bool, str, str]:
    """
    Sends diff to local Ollama instance and returns generated commit and PR body.

    Args:
        diff_text: The Git diff string.
        model_name: Ollama model name (e.g., 'qwen2.5:3b' or 'qwen2.5:7b').

    Returns:
        tuple[bool, str, str]: (True, commit_msg, pr_body) on success,
                               or (False, "", error_details) on failure.
    """
    if not diff_text or not diff_text.strip():
        return False, "", "Empty diff provided. Please provide a staged Git diff or paste code changes."

    prompt = _build_prompt(diff_text.strip())

    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 350,
        },
    }

    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_API_URL,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        # Timeout after 60s for local inference
        with urllib.request.urlopen(req, timeout=60.0) as response:
            if response.status != 200:
                return False, "", f"Ollama returned HTTP status {response.status}."

            response_body = response.read().decode("utf-8")
            response_json = json.loads(response_body)

    except urllib.error.HTTPError as http_err:
        try:
            err_content = http_err.read().decode("utf-8")
            err_json = json.loads(err_content)
            err_msg = err_json.get("error", err_content)
        except Exception:
            err_msg = str(http_err)
        return False, "", f"Ollama HTTP {http_err.code} Error: {err_msg}"

    except urllib.error.URLError:
        return (
            False,
            "",
            "Cannot reach Ollama at http://localhost:11434. "
            "Ensure Ollama is installed and running locally ('ollama serve').",
        )

    except TimeoutError:
        return (
            False,
            "",
            "Ollama inference timed out (60s limit). Ensure the model is downloaded and your system has sufficient RAM/VRAM.",
        )

    except json.JSONDecodeError:
        return False, "", "Failed to parse JSON response from Ollama endpoint."

    except Exception as exc:
        return False, "", f"Unexpected error during Ollama generation: {str(exc)}"

    raw_response = response_json.get("response", "")
    if not raw_response and isinstance(response_json.get("message"), dict):
        raw_response = response_json.get("message", {}).get("content", "")
    raw_response = raw_response.strip()

    if not raw_response:
        return False, "", "Ollama returned an empty response. Verify model availability."

    commit_msg, pr_body = _parse_llm_response(raw_response)

    if not commit_msg:
        commit_msg = "feat: update staged changes"
    if not pr_body:
        pr_body = "- Implement staged changes\n- Update codebase\n- Verify functionality"

    return True, commit_msg, pr_body
