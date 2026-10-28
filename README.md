# CommitCraft ⚡

> **100% Offline, Privacy-First AI Commit & PR Generator with Deterministic Secret Scanning**

CommitCraft is a lightweight desktop application built with Python and CustomTkinter. It analyzes staged Git diffs, flags exposed credentials before they get committed, and leverages a local Ollama model (Qwen) to draft standardized Conventional Commits and 3-bullet Pull Request summaries—all without sending a single byte to the cloud.

---

## 🚀 Key Features

- **100% Offline & Private**: Zero external cloud APIs, zero telemetry. Proprietary code never leaves your local machine.
- **Deterministic Secret Scanner**: Scans diff additions (`+`) with regex patterns to catch hardcoded API keys, bearer tokens, private cryptographic keys, and `.env` references.
- **Conventional Commits Generator**: Converts complex diffs into single-line, standardized Conventional Commits (e.g. `feat(auth): ...`, `fix(api): ...`).
- **3-Bullet PR Markdown**: Auto-generates concise, ready-to-paste Pull Request summaries.
- **Non-Blocking Architecture**: Background threading and thread-safe event queue prevent UI freezing during model inference or Git operations.
- **One-Click Clipboard**: Instant copy feedback for fast developer workflow.

---

## 🛠️ Tech Stack

- **Language**: Python 3.10+
- **GUI**: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
- **Local LLM Engine**: [Ollama](https://ollama.com/) (running `qwen2.5:3b`, `qwen2.5:7b`, or `qwen3.5:4b`)
- **Git Integration**: Built-in Python `subprocess` with Git CLI

---

## 📂 Project Structure

```text
commitcraft/
├── requirements.txt      # Dependency specifications (customtkinter)
├── scanner.py           # Deterministic secret & credential scanner
├── git_engine.py        # Safe Git diff extractor & text truncator
├── ollama_client.py     # Local Ollama HTTP client (urllib standard library)
├── app.py               # Modern dark-mode CustomTkinter desktop interface
└── README.md
```

---

## ⚡ Quick Start

### 1. Prerequisites
- **Git** installed on your system.
- **Ollama** installed and running locally:
  ```bash
  ollama run qwen3.5:4b
  # or
  ollama run qwen2.5:3b
  ```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the Application
```bash
python app.py
```

---

## 🧪 Quick Testing

1. **Clean Generation Demo**: Click **"Run Demo Sample"** in the top right, then click **"⚡ Generate with Local AI"**.
2. **Secret Scanner Demo**: Click **"Demo (With Secret)"** to see the red **Security Alert Banner** flag hardcoded API keys in real time.
3. **Real Git Repo**: Point to any local Git repository, stage changes (`git add .`), and click **"Fetch Staged Diff"**.

---

## 📄 License
MIT License. Free to use and customize.
