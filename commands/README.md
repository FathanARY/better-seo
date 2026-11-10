# Commands

`seo-audit.md` is the `/seo-audit` slash command. It is a template: the body
contains `@SKILL_DIR@`, and `install.sh` substitutes the absolute path of the
skill tree each agent loads, so every copy points at its own `audit.py`.

| Consumer | Destination | Skill dir substituted |
|---|---|---|
| Claude Code | `~/.claude/commands/seo-audit.md` | `~/.claude/skills/better-seo` |
| omp native | `~/.omp/agent/commands/seo-audit.md` | `~/.agents/skills/better-seo` |
| omp agents provider | `~/.agents/commands/seo-audit.md` | `~/.agents/skills/better-seo` |
| omp codex provider | `~/.codex/commands/seo-audit.md` | `~/.codex/skills/better-seo` |

Usage: `/seo-audit https://example.com`

Native Codex is not a target: OpenAI deprecated custom prompts in favour of
skills, and the skill already covers it.
