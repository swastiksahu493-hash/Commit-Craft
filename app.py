"""
CommitCraft - Offline AI Commit & PR Generator
Desktop Application built with CustomTkinter.
100% offline, privacy-first, zero telemetry.
"""

from __future__ import annotations

import os
import queue
import sys
import threading
from tkinter import filedialog
import customtkinter as ctk

from git_engine import get_staged_diff, truncate_diff
from ollama_client import generate_commit_and_pr
from scanner import scan_diff_for_secrets

# Sample diffs for instantaneous demo / hackathon evaluation
DEMO_DIFF_CLEAN = """diff --git a/src/auth/jwt_handler.py b/src/auth/jwt_handler.py
index a1b2c3d..e4f5g6h 100644
--- a/src/auth/jwt_handler.py
+++ b/src/auth/jwt_handler.py
@@ -42,6 +42,18 @@ class JWTHandler:
         return jwt.encode(payload, self.secret_key, algorithm="HS256")
 
+    def revoke_token(self, token_jti: str, expires_in: int = 3600) -> bool:
+        \"\"\"Add token unique identifier to the revocation blacklist cache.\"\"\"
+        cache_key = f"revoked_token:{token_jti}"
+        return self.redis_client.setex(cache_key, expires_in, "revoked")
+
     def is_token_revoked(self, token_jti: str) -> bool:
         \"\"\"Verify whether a token has been revoked prior to expiration.\"\"\"
         cache_key = f"revoked_token:{token_jti}"
         return bool(self.redis_client.exists(cache_key))
 
     def decode_token(self, token: str) -> dict:
         payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
+        if self.is_token_revoked(payload.get("jti")):
+            raise TokenRevokedError("Provided authentication token has been invalidated.")
         return payload
"""

DEMO_DIFF_WITH_SECRET = """diff --git a/config/payment_service.py b/config/payment_service.py
index 88f21bc..99e44ab 100644
--- a/config/payment_service.py
+++ b/config/payment_service.py
@@ -10,6 +10,10 @@ class PaymentGateway:
     def __init__(self):
+        # CRITICAL VULNERABILITY: Hardcoded production credentials
+        self.api_key = "sk_live_994827492817492817492"
+        self.bearer_token = "Bearer_secret_token_abcdef123456"
+        self.env_file = ".env.production"
         self.endpoint = "https://payments.internal.net"
"""


class CommitCraftApp(ctk.CTk):
    """Main CommitCraft Desktop Application Window."""

    def __init__(self) -> None:
        super().__init__()

        # Window configuration
        self.title("CommitCraft - 100% Offline AI Commit & PR Generator")
        self.geometry("1060x680")
        self.minsize(960, 620)

        # Set default appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Application state
        self._is_busy = False
        self._event_queue: queue.Queue = queue.Queue()

        # Build UI layout
        self._build_top_bar()
        self._build_security_banner()
        self._build_main_columns()
        self._build_bottom_bar()

        # Start thread-safe event queue listener
        self._schedule_queue_check()

        # Update initial diff stats
        self._on_diff_text_changed()

    # -------------------------------------------------------------------------
    # Thread-Safe Event Queue Processing
    # -------------------------------------------------------------------------

    def _schedule_queue_check(self) -> None:
        """Polls the thread-safe queue periodically on the main UI thread."""
        self._process_event_queue()
        self.after(50, self._schedule_queue_check)

    def _process_event_queue(self) -> None:
        """Executes all pending UI updates queued by background worker threads."""
        while not self._event_queue.empty():
            try:
                callback, args = self._event_queue.get_nowait()
                callback(*args)
            except queue.Empty:
                break
            except Exception as exc:
                print(f"Error handling UI event: {exc}", file=sys.stderr)

    # -------------------------------------------------------------------------
    # UI Builder Methods
    # -------------------------------------------------------------------------

    def _build_top_bar(self) -> None:
        """Constructs the top bar with repo path selector and demo triggers."""
        self.top_frame = ctk.CTkFrame(self, corner_radius=8, fg_color="#1E2024")
        self.top_frame.pack(fill="x", padx=16, pady=(14, 8))

        # Title & Privacy Badge
        title_row = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        title_row.pack(fill="x", padx=12, pady=(10, 8))

        app_title = ctk.CTkLabel(
            title_row,
            text="⚡ CommitCraft",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#FFFFFF",
        )
        app_title.pack(side="left")

        badge = ctk.CTkLabel(
            title_row,
            text="100% OFFLINE • PRIVACY-FIRST • LOCAL QWEN",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#153E2B",
            text_color="#4ADE80",
            corner_radius=6,
            padx=8,
            pady=3,
        )
        badge.pack(side="left", padx=12)

        # Action Buttons on Top Right
        self.demo_secret_btn = ctk.CTkButton(
            title_row,
            text="Demo (With Secret)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#4A1D24",
            hover_color="#6A2B35",
            text_color="#FCA5A5",
            width=135,
            height=28,
            command=self._load_demo_secret,
        )
        self.demo_secret_btn.pack(side="right", padx=(6, 0))

        self.demo_clean_btn = ctk.CTkButton(
            title_row,
            text="Run Demo Sample",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2B3545",
            hover_color="#3C4B60",
            width=125,
            height=28,
            command=self._load_demo_clean,
        )
        self.demo_clean_btn.pack(side="right", padx=(6, 0))

        # Git Repo Path Controls
        repo_row = ctk.CTkFrame(self.top_frame, fg_color="transparent")
        repo_row.pack(fill="x", padx=12, pady=(0, 10))

        repo_label = ctk.CTkLabel(
            repo_row,
            text="Git Repo:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#CBD5E1",
        )
        repo_label.pack(side="left", padx=(0, 8))

        self.repo_entry = ctk.CTkEntry(
            repo_row,
            font=ctk.CTkFont(family="Consolas", size=11),
            placeholder_text="Enter path to Git repository...",
            height=32,
        )
        self.repo_entry.insert(0, os.getcwd())
        self.repo_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.browse_btn = ctk.CTkButton(
            repo_row,
            text="Browse...",
            font=ctk.CTkFont(size=11),
            fg_color="#2C3038",
            hover_color="#3D434E",
            width=80,
            height=32,
            command=self._browse_repository,
        )
        self.browse_btn.pack(side="left", padx=(0, 8))

        self.fetch_diff_btn = ctk.CTkButton(
            repo_row,
            text="Fetch Staged Diff",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#1D4ED8",
            hover_color="#1E40AF",
            width=130,
            height=32,
            command=self._start_fetch_diff,
        )
        self.fetch_diff_btn.pack(side="left")

    def _build_security_banner(self) -> None:
        """Constructs the expandable red alert banner for flagged secrets."""
        self.alert_frame = ctk.CTkFrame(
            self,
            corner_radius=8,
            fg_color="#450A0A",
            border_width=1,
            border_color="#DC2626",
        )
        # Not packed initially - packed only when secrets are detected

        header_row = ctk.CTkFrame(self.alert_frame, fg_color="transparent")
        header_row.pack(fill="x", padx=12, pady=(8, 4))

        self.alert_icon_label = ctk.CTkLabel(
            header_row,
            text="⚠️ SECURITY ALERT: Potential Exposed Secrets Detected in Diff!",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#FCA5A5",
        )
        self.alert_icon_label.pack(side="left")

        self.dismiss_alert_btn = ctk.CTkButton(
            header_row,
            text="Dismiss",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#5F1616",
            hover_color="#7F1D1D",
            text_color="#FEE2E2",
            width=65,
            height=24,
            command=self._hide_security_banner,
        )
        self.dismiss_alert_btn.pack(side="right")

        self.alert_details_label = ctk.CTkLabel(
            self.alert_frame,
            text="",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#FECACA",
            justify="left",
            anchor="w",
        )
        self.alert_details_label.pack(fill="x", padx=14, pady=(0, 8))

    def _build_main_columns(self) -> None:
        """Constructs the two-column main workspace."""
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=16, pady=4)

        self.main_container.grid_columnconfigure(0, weight=1, uniform="group1")
        self.main_container.grid_columnconfigure(1, weight=1, uniform="group1")
        self.main_container.grid_rowconfigure(0, weight=1)

        # ================= LEFT COLUMN: Staged Diff Input =================
        left_card = ctk.CTkFrame(self.main_container, corner_radius=8, fg_color="#1E2024")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
        left_card.grid_rowconfigure(1, weight=1)
        left_card.grid_columnconfigure(0, weight=1)

        # Left Header
        left_header = ctk.CTkFrame(left_card, fg_color="transparent")
        left_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 6))

        left_title = ctk.CTkLabel(
            left_header,
            text="Staged Diff / Code Input",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#E2E8F0",
        )
        left_title.pack(side="left")

        clear_btn = ctk.CTkButton(
            left_header,
            text="Clear",
            font=ctk.CTkFont(size=10),
            fg_color="#2C3038",
            hover_color="#3D434E",
            width=50,
            height=24,
            command=self._clear_diff,
        )
        clear_btn.pack(side="right", padx=(4, 0))

        paste_btn = ctk.CTkButton(
            left_header,
            text="Paste",
            font=ctk.CTkFont(size=10),
            fg_color="#2C3038",
            hover_color="#3D434E",
            width=50,
            height=24,
            command=self._paste_clipboard,
        )
        paste_btn.pack(side="right")

        # Diff Textbox
        self.diff_textbox = ctk.CTkTextbox(
            left_card,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#141619",
            text_color="#E2E8F0",
            corner_radius=6,
            wrap="none",
        )
        self.diff_textbox.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 8))
        self.diff_textbox.bind("<KeyRelease>", lambda e: self._on_diff_text_changed())

        # Diff Stats Footer
        self.diff_stats_label = ctk.CTkLabel(
            left_card,
            text="Lines: 0 | Chars: 0",
            font=ctk.CTkFont(size=10),
            text_color="#64748B",
            anchor="w",
        )
        self.diff_stats_label.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 8))

        # ================= RIGHT COLUMN: Generated Output =================
        right_card = ctk.CTkFrame(self.main_container, corner_radius=8, fg_color="#1E2024")
        right_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=0)
        right_card.grid_columnconfigure(0, weight=1)
        right_card.grid_rowconfigure(3, weight=1)

        # 1. Conventional Commit Section
        commit_header = ctk.CTkFrame(right_card, fg_color="transparent")
        commit_header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))

        commit_title = ctk.CTkLabel(
            commit_header,
            text="Conventional Commit",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#E2E8F0",
        )
        commit_title.pack(side="left")

        self.copy_commit_btn = ctk.CTkButton(
            commit_header,
            text="Copy Commit",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            width=95,
            height=26,
            command=self._copy_commit_to_clipboard,
        )
        self.copy_commit_btn.pack(side="right")

        self.commit_entry = ctk.CTkEntry(
            right_card,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#141619",
            text_color="#F8FAFC",
            height=34,
            placeholder_text="feat(scope): concise commit message will appear here...",
        )
        self.commit_entry.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        # 2. PR Summary (Markdown) Section
        pr_header = ctk.CTkFrame(right_card, fg_color="transparent")
        pr_header.grid(row=2, column=0, sticky="ew", padx=12, pady=(4, 4))

        pr_title = ctk.CTkLabel(
            pr_header,
            text="PR Summary (Markdown)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#E2E8F0",
        )
        pr_title.pack(side="left")

        self.copy_pr_btn = ctk.CTkButton(
            pr_header,
            text="Copy PR",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            width=95,
            height=26,
            command=self._copy_pr_to_clipboard,
        )
        self.copy_pr_btn.pack(side="right")

        self.pr_textbox = ctk.CTkTextbox(
            right_card,
            font=ctk.CTkFont(family="Consolas", size=11),
            fg_color="#141619",
            text_color="#E2E8F0",
            corner_radius=6,
            wrap="word",
        )
        self.pr_textbox.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 10))

    def _build_bottom_bar(self) -> None:
        """Constructs the bottom bar with model selector, status label, and generate button."""
        self.bottom_frame = ctk.CTkFrame(self, corner_radius=8, fg_color="#1E2024")
        self.bottom_frame.pack(fill="x", padx=16, pady=(8, 14))

        # Status indicator
        status_container = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        status_container.pack(side="left", fill="x", expand=True, padx=14, pady=10)

        self.status_dot = ctk.CTkLabel(
            status_container,
            text="●",
            font=ctk.CTkFont(size=14),
            text_color="#10B981",
        )
        self.status_dot.pack(side="left", padx=(0, 6))

        self.status_label = ctk.CTkLabel(
            status_container,
            text="Ready. Paste a diff or fetch staged changes from Git.",
            font=ctk.CTkFont(size=12),
            text_color="#94A3B8",
            anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        # Model selector dropdown
        model_label = ctk.CTkLabel(
            self.bottom_frame,
            text="Ollama Model:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#CBD5E1",
        )
        model_label.pack(side="left", padx=(8, 6))

        self.model_dropdown = ctk.CTkOptionMenu(
            self.bottom_frame,
            values=["qwen3.5:4b", "qwen2.5:3b", "qwen2.5:7b", "qwen2.5:1.5b", "qwen2.5:0.5b"],
            font=ctk.CTkFont(size=11),
            width=120,
            height=34,
            fg_color="#2C3038",
            button_color="#3D434E",
        )
        self.model_dropdown.set("qwen3.5:4b")
        self.model_dropdown.pack(side="left", padx=(0, 14))

        # Main Generation Action Button
        self.generate_btn = ctk.CTkButton(
            self.bottom_frame,
            text="⚡ Generate with Local AI",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#16A34A",
            hover_color="#15803D",
            text_color="#FFFFFF",
            width=210,
            height=38,
            command=self._start_generation,
        )
        self.generate_btn.pack(side="right", padx=(0, 12), pady=8)

    # -------------------------------------------------------------------------
    # Helper & Event Handlers
    # -------------------------------------------------------------------------

    def _set_status(self, text: str, state: str = "normal") -> None:
        """
        Updates the status bar message and dot indicator.
        state: 'normal' (green), 'working' (yellow), 'warning' (orange), 'error' (red)
        """
        color_map = {
            "normal": "#10B981",
            "working": "#F59E0B",
            "warning": "#F97316",
            "error": "#EF4444",
        }
        self.status_dot.configure(text_color=color_map.get(state, "#10B981"))
        self.status_label.configure(text=text)

    def _set_busy(self, is_busy: bool, busy_text: str = "") -> None:
        """Toggles UI interactive state during background work."""
        self._is_busy = is_busy
        if is_busy:
            self.generate_btn.configure(state="disabled", text=busy_text or "Processing...")
            self.fetch_diff_btn.configure(state="disabled")
            self.demo_clean_btn.configure(state="disabled")
            self.demo_secret_btn.configure(state="disabled")
        else:
            self.generate_btn.configure(state="normal", text="⚡ Generate with Local AI")
            self.fetch_diff_btn.configure(state="normal")
            self.demo_clean_btn.configure(state="normal")
            self.demo_secret_btn.configure(state="normal")

    def _on_diff_text_changed(self) -> None:
        """Updates line and character counts for the diff text area."""
        text = self.diff_textbox.get("1.0", "end-1c")
        chars = len(text)
        lines = len(text.splitlines()) if chars > 0 else 0
        self.diff_stats_label.configure(text=f"Lines: {lines} | Chars: {chars}")

    def _clear_diff(self) -> None:
        """Clears diff input, outputs, and any active security banner."""
        self.diff_textbox.delete("1.0", "end")
        self.commit_entry.delete(0, "end")
        self.pr_textbox.delete("1.0", "end")
        self._hide_security_banner()
        self._on_diff_text_changed()
        self._set_status("Cleared diff and generated fields.", "normal")

    def _paste_clipboard(self) -> None:
        """Pastes current clipboard contents into the diff input area."""
        try:
            content = self.clipboard_get()
            self.diff_textbox.delete("1.0", "end")
            self.diff_textbox.insert("1.0", content)
            self._on_diff_text_changed()
            self._set_status("Pasted diff from clipboard.", "normal")
        except Exception:
            self._set_status("Clipboard is empty or does not contain valid text.", "warning")

    def _browse_repository(self) -> None:
        """Opens a folder selection dialog to choose a Git repository."""
        initial_dir = self.repo_entry.get().strip() or os.getcwd()
        selected_path = filedialog.askdirectory(
            initialdir=initial_dir if os.path.isdir(initial_dir) else os.getcwd(),
            title="Select Local Git Repository Directory",
        )
        if selected_path:
            self.repo_entry.delete(0, "end")
            self.repo_entry.insert(0, selected_path)
            self._set_status(f"Selected repo: {selected_path}", "normal")

    def _load_demo_clean(self) -> None:
        """Loads clean realistic Git diff into the editor for instant testing."""
        self.diff_textbox.delete("1.0", "end")
        self.diff_textbox.insert("1.0", DEMO_DIFF_CLEAN.strip())
        self._hide_security_banner()
        self._on_diff_text_changed()
        self._set_status("Loaded clean demo sample diff. Click 'Generate with Local AI'.", "normal")

    def _load_demo_secret(self) -> None:
        """Loads sample diff containing exposed secrets to showcase security scanner."""
        self.diff_textbox.delete("1.0", "end")
        self.diff_textbox.insert("1.0", DEMO_DIFF_WITH_SECRET.strip())
        self._on_diff_text_changed()
        # Scan immediately to demonstrate the deterministic alert banner
        warnings = scan_diff_for_secrets(DEMO_DIFF_WITH_SECRET)
        self._show_security_banner(warnings)
        self._set_status(f"Loaded demo diff with {len(warnings)} exposed secrets detected!", "error")

    # -------------------------------------------------------------------------
    # Security Banner Controls
    # -------------------------------------------------------------------------

    def _show_security_banner(self, warnings: list[str]) -> None:
        """Displays the red alert banner with specific line warnings."""
        if not warnings:
            self._hide_security_banner()
            return

        formatted_warnings = "\n".join(f"• {w}" for w in warnings[:4])
        if len(warnings) > 4:
            formatted_warnings += f"\n• ...and {len(warnings) - 4} more security warnings."

        self.alert_details_label.configure(text=formatted_warnings)
        self.alert_frame.pack(fill="x", padx=16, pady=(0, 6), before=self.main_container)

    def _hide_security_banner(self) -> None:
        """Hides the red alert banner."""
        self.alert_frame.pack_forget()

    # -------------------------------------------------------------------------
    # Clipboard Helpers
    # -------------------------------------------------------------------------

    def _copy_commit_to_clipboard(self) -> None:
        """Copies conventional commit message to system clipboard."""
        text = self.commit_entry.get().strip()
        if not text:
            self._set_status("Commit message is empty. Generate one first.", "warning")
            return

        self.clipboard_clear()
        self.clipboard_append(text)
        self._flash_button(self.copy_commit_btn, "✓ Copied!", "Copy Commit")
        self._set_status("Commit message copied to clipboard.", "normal")

    def _copy_pr_to_clipboard(self) -> None:
        """Copies PR summary Markdown to system clipboard."""
        text = self.pr_textbox.get("1.0", "end-1c").strip()
        if not text:
            self._set_status("PR summary is empty. Generate one first.", "warning")
            return

        self.clipboard_clear()
        self.clipboard_append(text)
        self._flash_button(self.copy_pr_btn, "✓ Copied!", "Copy PR")
        self._set_status("PR summary copied to clipboard.", "normal")

    def _flash_button(self, btn: ctk.CTkButton, flash_text: str, normal_text: str) -> None:
        """Temporarily changes button text and color to provide positive copy feedback."""
        original_fg = btn.cget("fg_color")
        btn.configure(text=flash_text, fg_color="#15803D")

        def _reset() -> None:
            btn.configure(text=normal_text, fg_color=original_fg)

        self.after(2000, _reset)

    # -------------------------------------------------------------------------
    # Non-Blocking Background Operations
    # -------------------------------------------------------------------------

    def _start_fetch_diff(self) -> None:
        """Launches Git diff fetch inside a background thread."""
        if self._is_busy:
            return

        repo_path = self.repo_entry.get().strip()
        if not repo_path:
            self._set_status("Please provide a repository path.", "warning")
            return

        self._set_busy(True, "Fetching...")
        self._set_status(f"Reading staged diff from '{repo_path}'...", "working")

        def _worker() -> None:
            success, result_or_err = get_staged_diff(repo_path)
            self._event_queue.put((self._on_diff_fetched, (success, result_or_err)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_diff_fetched(self, success: bool, result_or_err: str) -> None:
        """Main-thread callback after Git diff operation finishes."""
        self._set_busy(False)
        if success:
            self.diff_textbox.delete("1.0", "end")
            self.diff_textbox.insert("1.0", result_or_err)
            self._on_diff_text_changed()

            # Automatic security scan upon diff retrieval
            warnings = scan_diff_for_secrets(result_or_err)
            if warnings:
                self._show_security_banner(warnings)
                self._set_status(
                    f"Diff fetched, but {len(warnings)} potential secret(s) detected!",
                    "warning",
                )
            else:
                self._hide_security_banner()
                self._set_status("Staged diff loaded successfully and verified clean.", "normal")
        else:
            self._set_status(result_or_err, "error")

    def _start_generation(self) -> None:
        """Performs secret scanning and triggers background Ollama inference."""
        if self._is_busy:
            return

        diff_text = self.diff_textbox.get("1.0", "end-1c").strip()
        if not diff_text:
            self._set_status("Diff text is empty. Fetch from Git or paste diff first.", "warning")
            return

        # Step 1: Run deterministic secret scan
        self._set_status("Scanning diff additions for exposed secrets...", "working")
        warnings = scan_diff_for_secrets(diff_text)
        if warnings:
            self._show_security_banner(warnings)
            self._set_status("Security warnings detected! Check alert banner.", "error")
        else:
            self._hide_security_banner()

        # Step 2: Truncate diff to protect context budget and speed up local inference
        compact_diff = truncate_diff(diff_text, max_chars=1500)
        selected_model = self.model_dropdown.get()

        self._set_busy(True, "Generating...")
        self._set_status(f"Querying local Ollama model ({selected_model})...", "working")

        def _worker() -> None:
            success, commit_msg, pr_or_err = generate_commit_and_pr(
                compact_diff, model_name=selected_model
            )
            self._event_queue.put(
                (self._on_generation_completed, (success, commit_msg, pr_or_err))
            )

        threading.Thread(target=_worker, daemon=True).start()

    def _on_generation_completed(self, success: bool, commit_msg: str, pr_or_err: str) -> None:
        """Main-thread callback after Ollama generation completes."""
        self._set_busy(False)
        if success:
            # Populate commit
            self.commit_entry.delete(0, "end")
            self.commit_entry.insert(0, commit_msg)

            # Populate PR Markdown
            self.pr_textbox.delete("1.0", "end")
            self.pr_textbox.insert("1.0", pr_or_err)

            self._set_status("Generation complete! Ready to copy commit & PR.", "normal")
        else:
            self._set_status(pr_or_err, "error")


def main() -> None:
    """Application entry point."""
    app = CommitCraftApp()
    app.mainloop()


if __name__ == "__main__":
    main()
