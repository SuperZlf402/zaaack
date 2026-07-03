---
name: codex-knowledge-base
description: Build a portable knowledge base from Codex memories, user preferences, habits, instructions, and chat history across one or more computers. Use when the user asks to extract or consolidate Codex memory, Codex habits, AGENTS.md instructions, Codex conversations, chat transcripts without reasoning, or prepare a sanitized GitHub repository for cross-device Codex knowledge sharing.
---

# Codex Knowledge Base

## Purpose

Create a reviewable, privacy-aware knowledge base that can be collected from multiple computers and uploaded to GitHub. Preserve what helps future Codex sessions serve the user: stable user preferences, working habits, project instructions, reusable decisions, and user/assistant chat history. Exclude hidden reasoning, chain-of-thought, secrets, credentials, cookies, raw tokens, and unrelated personal/work files.

Zi's default private GitHub repository for this knowledge base is `https://github.com/SuperZlf402/zach_knowledge_database`. Treat this repository as the preferred destination unless Zi specifies another repo.

## Default Outcome

Produce a folder that is safe to inspect before publishing:

- `README.md`: scope, computer/source list, and how to use the knowledge base.
- `codex_memory_and_habits.md`: durable preferences, standing instructions, recurring workflows, and useful facts.
- `conversations.md`: user/assistant messages only, with reasoning fields omitted.
- `manifests/file_inventory.csv`: source file list, sizes, and extraction status.
- `sources.json`: machine-readable source summary.
- `import_checklist.md`: manual review checklist before GitHub upload.

## Workflow

1. Confirm the intended scope in plain language:
   - Which computers are included.
   - Whether GitHub should be private or public; recommend private by default.
   - Whether chat history should include all projects or only selected folders.
2. Locate likely Codex sources without deleting or modifying originals:
   - `~/.codex`
   - project-level `AGENTS.md`
   - Codex workspace folders under `Documents/Codex`
   - app data folders that visibly belong to Codex or OpenAI, if accessible
3. Extract only useful knowledge:
   - Treat `AGENTS.md`, `config`, `memory`, `instructions`, and preference-like files as memory/habit candidates.
   - Treat JSON/JSONL/Markdown transcript-like files as conversation candidates.
   - For conversations, keep only speaker and message text for user/assistant/system/tool-visible messages. Omit keys such as `reasoning`, `analysis`, `thought`, `chain_of_thought`, `hidden`, `trace`, and similar fields.
4. Redact sensitive content:
   - Mask API keys, access tokens, bearer tokens, cookies, passwords, private keys, and long opaque secrets.
   - Flag possible sensitive business or personal content for manual review instead of silently publishing it.
5. Create a local knowledge-base draft first. Do not upload to GitHub until the user has reviewed the result or explicitly authorized upload.
6. If uploading, use Zi's private repo `SuperZlf402/zach_knowledge_database` by default. Commit only the sanitized output folder, not raw source files.

## Automation

Use `scripts/collect_codex_knowledge.py` when the user wants a first-pass collection from the current computer. Read or patch the script if the local Codex storage format differs.

Example:

```bash
python scripts/collect_codex_knowledge.py --output ./codex-kb-export --computer-name "zi-laptop"
```

Add explicit sources if the user points to another drive or copied folder:

```bash
python scripts/collect_codex_knowledge.py --source "D:/OldComputer/.codex" --source "D:/OldComputer/Documents/Codex" --output ./codex-kb-export --computer-name "old-laptop"
```

After running the script, inspect the generated Markdown files and `import_checklist.md`. Summarize the result for the user in business terms: what was found, what was excluded, what needs review, and whether it is ready for GitHub.

## Multi-Computer Merge

For each computer, generate one export folder using a unique `--computer-name`. Then combine them into one repository structure:

```text
codex-knowledge-base/
  README.md
  computers/
    zi-laptop/
    office-desktop/
    old-laptop/
  consolidated/
    codex_memory_and_habits.md
    conversations_index.md
```

When merging, deduplicate stable preferences and keep the newest version if instructions conflict. Preserve source labels so future updates can be traced back to the computer or folder they came from.

For Zi's private GitHub repo, prefer this layout:

```text
zach_knowledge_database/
  codex/
    computers/
      current-computer/
      office-desktop/
      old-laptop/
    consolidated/
      codex_memory_and_habits.md
      conversations_index.md
    import_checklist.md
```

## GitHub Publishing Rules

Before publishing:

- Ask for confirmation if the repository is public.
- Use `https://github.com/SuperZlf402/zach_knowledge_database` as the default private destination when Zi asks to upload the Codex knowledge base.
- Never upload raw Codex databases, raw app data, `.env` files, SSH keys, browser data, cookies, logs containing tokens, or whole home-directory snapshots.
- Prefer private GitHub repos for personal memory/history; Zi has already created `SuperZlf402/zach_knowledge_database` for this purpose.
- Include a clear `README.md` warning that the repository may contain personal working preferences and should be reviewed before sharing.
- If using GitHub tools, create a normal commit with a concise message such as `Add sanitized Codex knowledge export`.

## Quality Bar

The task is complete only when:

- The output is organized enough for another Codex session to use.
- Reasoning traces are excluded.
- Sensitive strings are redacted or flagged.
- The user can review the generated files before any upload.
- Any remaining uncertainty is clearly listed.
