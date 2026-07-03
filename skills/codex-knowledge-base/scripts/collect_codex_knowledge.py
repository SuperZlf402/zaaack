#!/usr/bin/env python3
"""Collect a sanitized first-pass Codex knowledge-base export."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SKIP_DIRS = {
    ".git",
    ".system",
    ".tmp",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "cache",
    "Cache",
    "GPUCache",
    "Code Cache",
    "plugins",
    "vendor_imports",
    "work",
    "outputs",
}

TEXT_EXTS = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".toml",
    ".yaml",
    ".yml",
    ".log",
}

MEMORY_HINTS = (
    "agent",
    "agents",
    "memory",
    "memories",
    "instruction",
    "instructions",
    "preference",
    "preferences",
    "habit",
    "habits",
    "config",
    "profile",
)

CONVERSATION_HINTS = (
    "conversation",
    "conversations",
    "chat",
    "chats",
    "thread",
    "threads",
    "transcript",
    "history",
    "session",
    "sessions",
)

OMIT_KEYS = {
    "reasoning",
    "analysis",
    "thought",
    "thoughts",
    "chain_of_thought",
    "chain-of-thought",
    "hidden",
    "trace",
    "debug",
    "internal",
}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password|passwd|cookie|authorization)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{16,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
]


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    slug = slug.strip(".-_")
    return slug or "unknown-computer"


def default_sources() -> list[Path]:
    home = Path.home()
    candidates = [
        home / ".codex",
        home / "Documents" / "Codex",
    ]
    appdata = os.environ.get("APPDATA")
    localappdata = os.environ.get("LOCALAPPDATA")
    if appdata:
        candidates.extend([Path(appdata) / "Codex", Path(appdata) / "OpenAI"])
    if localappdata:
        candidates.extend([Path(localappdata) / "Codex", Path(localappdata) / "OpenAI"])
    return [p for p in candidates if p.exists()]


def redact(text: str) -> str:
    result = text
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED_SECRET]", result)
    result = re.sub(r"(?i)(authorization:\s*)[^\n\r]+", r"\1[REDACTED_SECRET]", result)
    return result


def safe_read(path: Path, max_bytes: int) -> tuple[str | None, str | None]:
    try:
        if path.stat().st_size > max_bytes:
            return None, "skipped_large_file"
        data = path.read_text(encoding="utf-8", errors="replace")
        return redact(data), None
    except Exception as exc:  # pragma: no cover - environment dependent
        return None, f"read_error: {exc}"


def walk_sources(sources: Iterable[Path], max_bytes: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in sources:
        if not source.exists():
            rows.append({"path": str(source), "size": 0, "kind": "missing", "status": "missing"})
            continue
        for root, dirs, files in os.walk(source):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".git")]
            for name in files:
                path = Path(root) / name
                ext = path.suffix.lower()
                if ext not in TEXT_EXTS and name.lower() != "agents.md":
                    continue
                lower = str(path).lower()
                kind = "other"
                if any(h in lower for h in MEMORY_HINTS) or name.lower() == "agents.md":
                    kind = "memory"
                if any(h in lower for h in CONVERSATION_HINTS):
                    kind = "conversation"
                try:
                    size = path.stat().st_size
                except OSError:
                    size = 0
                status = "candidate" if size <= max_bytes else "skipped_large_file"
                rows.append({"path": str(path), "size": size, "kind": kind, "status": status})
    return rows


def clean_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            if str(key).lower() in OMIT_KEYS:
                continue
            cleaned[key] = clean_obj(value)
        return cleaned
    if isinstance(obj, list):
        return [clean_obj(item) for item in obj]
    if isinstance(obj, str):
        return redact(obj)
    return obj


def content_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(content_to_text(item.get("text") or item.get("content") or item))
            else:
                parts.append(content_to_text(item))
        return "\n".join(p for p in parts if p).strip()
    if isinstance(value, dict):
        for key in ("text", "content", "message", "value"):
            if key in value:
                return content_to_text(value[key])
        return json.dumps(clean_obj(value), ensure_ascii=False, sort_keys=True)
    return str(value).strip() if value is not None else ""


def find_messages(obj: Any) -> list[tuple[str, str]]:
    messages: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        role = obj.get("role") or obj.get("author") or obj.get("speaker")
        content = obj.get("content") or obj.get("text") or obj.get("message")
        if role and content is not None:
            role_text = content_to_text(role).lower()
            if role_text in {"user", "assistant", "system", "tool"}:
                text = content_to_text(clean_obj(content))
                if text:
                    messages.append((role_text, text))
        for key, value in obj.items():
            if str(key).lower() not in OMIT_KEYS:
                messages.extend(find_messages(value))
    elif isinstance(obj, list):
        for item in obj:
            messages.extend(find_messages(item))
    return messages


def parse_conversation_file(path: Path, max_bytes: int) -> tuple[list[tuple[str, str]], str]:
    text, err = safe_read(path, max_bytes)
    if err:
        return [], err
    assert text is not None
    messages: list[tuple[str, str]] = []
    if path.suffix.lower() == ".jsonl":
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                messages.extend(find_messages(json.loads(line)))
            except json.JSONDecodeError:
                continue
    elif path.suffix.lower() == ".json":
        try:
            messages = find_messages(json.loads(text))
        except json.JSONDecodeError:
            messages = []
    if messages:
        return messages, "extracted"
    if path.suffix.lower() in {".md", ".txt", ".log"}:
        return [("source", text[:20000])], "copied_text_needs_review"
    return [], "no_visible_messages_found"


def write_outputs(out: Path, rows: list[dict[str, Any]], sources: list[Path], computer_name: str, max_bytes: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    manifests = out / "manifests"
    manifests.mkdir(exist_ok=True)
    computer_slug = safe_slug(computer_name)

    with (manifests / "file_inventory.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["path", "size", "kind", "status"])
        writer.writeheader()
        writer.writerows(rows)

    memory_sections = []
    conversation_sections = []
    flags = []
    for row in rows:
        if row["status"] != "candidate":
            continue
        path = Path(row["path"])
        if row["kind"] == "memory":
            text, err = safe_read(path, max_bytes)
            if text:
                memory_sections.append(f"## Source: {path}\n\n{text.strip()}\n")
            elif err:
                flags.append(f"- Review `{path}`: {err}")
        elif row["kind"] == "conversation":
            messages, status = parse_conversation_file(path, max_bytes)
            if messages:
                rendered = [f"## Source: {path}\n"]
                for role, text in messages:
                    rendered.append(f"### {role}\n\n{text.strip()}\n")
                conversation_sections.append("\n".join(rendered))
            if status != "extracted":
                flags.append(f"- Review `{path}`: {status}")

    now = datetime.now(timezone.utc).isoformat()
    readme = f"""# Codex Knowledge Base Export

Computer: `{computer_name}`

Recommended GitHub folder: `codex/computers/{computer_slug}/`

Generated: `{now}`

This folder is a sanitized first-pass export of Codex-related memories, habits, instructions, and chat history. Review before uploading to GitHub.

## Contents

- `codex_memory_and_habits.md`
- `conversations.md`
- `manifests/file_inventory.csv`
- `sources.json`
- `import_checklist.md`
"""
    (out / "README.md").write_text(readme, encoding="utf-8")
    (out / "codex_memory_and_habits.md").write_text(
        "# Codex Memory And Habits\n\n" + ("\n\n".join(memory_sections) if memory_sections else "No memory-like files were extracted.\n"),
        encoding="utf-8",
    )
    (out / "conversations.md").write_text(
        "# Conversations\n\nOnly visible-style user/assistant/system/tool messages are included when detected. Reasoning-like fields are omitted.\n\n"
        + ("\n\n".join(conversation_sections) if conversation_sections else "No conversation-like files were extracted.\n"),
        encoding="utf-8",
    )
    checklist = [
        "# Import Checklist",
        "",
        "- Confirm this GitHub repository will be private unless Zi explicitly approves public publishing.",
        "- Search for client names, personal information, passwords, API keys, tokens, and confidential audit material.",
        "- Confirm `conversations.md` does not include hidden reasoning or internal analysis.",
        "- Confirm each computer export has a clear computer/source name.",
        f"- Upload this export to `codex/computers/{computer_slug}/`, not to a generic `current-computer` folder.",
        "- Commit only sanitized output files, not raw Codex app folders.",
        "",
        "## Items Flagged For Review",
        "",
        "\n".join(flags) if flags else "No parser warnings.",
    ]
    (out / "import_checklist.md").write_text("\n".join(checklist), encoding="utf-8")
    summary = {
        "computer_name": computer_name,
        "computer_slug": computer_slug,
        "recommended_github_folder": f"codex/computers/{computer_slug}",
        "generated_at": now,
        "sources": [str(p) for p in sources],
        "file_count": len(rows),
        "memory_candidates": sum(1 for r in rows if r["kind"] == "memory"),
        "conversation_candidates": sum(1 for r in rows if r["kind"] == "conversation"),
    }
    (out / "sources.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect sanitized Codex memory and conversation knowledge.")
    parser.add_argument("--source", action="append", default=[], help="Codex source folder. Can be repeated.")
    parser.add_argument("--output", required=True, help="Output folder for the sanitized knowledge-base draft.")
    parser.add_argument("--computer-name", default=socket.gethostname(), help="Label for this computer/source.")
    parser.add_argument("--max-file-mb", type=int, default=20, help="Skip individual files larger than this size.")
    args = parser.parse_args()

    sources = [Path(s).expanduser() for s in args.source] if args.source else default_sources()
    max_bytes = args.max_file_mb * 1024 * 1024
    rows = walk_sources(sources, max_bytes)
    write_outputs(Path(args.output).expanduser(), rows, sources, args.computer_name, max_bytes)
    print(f"Created Codex knowledge-base draft at: {Path(args.output).expanduser()}")
    print(f"Recommended GitHub folder: codex/computers/{safe_slug(args.computer_name)}")
    print(f"Sources scanned: {len(sources)}")
    print(f"Candidate files indexed: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
