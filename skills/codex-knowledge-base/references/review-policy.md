# Review Policy

Use this policy when deciding whether extracted content is safe to include.

## Include

- User preferences about communication style, language, formatting, and workflow.
- Durable professional context the user has intentionally provided.
- Reusable instructions such as AGENTS.md content.
- User/assistant chat messages that help preserve continuity.
- Project names only when they are already part of intentional instructions or needed for context.

## Exclude

- Hidden reasoning, chain-of-thought, model analysis, traces, debug internals, and non-visible planning notes.
- API keys, access tokens, refresh tokens, session IDs, cookies, passwords, SSH keys, private keys, certificates, and `.env` values.
- Client confidential data, audit working papers, financial records, payroll data, personal IDs, addresses, phone numbers, and bank/payment details.
- Raw databases or app storage files when a sanitized Markdown export is available.

## Flag For User Review

- Any content naming clients, employers, transactions, audit files, or live project deliverables.
- Any conversation containing copied documents, legal text, contracts, financial data, or personal matters.
- Any file where the parser is uncertain whether assistant text is visible answer text or hidden reasoning.

## GitHub Default

Use Zi's private repository `https://github.com/SuperZlf402/zach_knowledge_database` as the default destination for sanitized Codex knowledge-base exports. Public publishing requires explicit confirmation after the user has seen the review checklist.

Even for this private repository, review for secrets, client names, audit-sensitive details, personal identifiers, and hidden reasoning before upload.
