# Commands

`seo-audit.md` is the `/seo-audit` slash command, shared by both install paths.

`install.sh` substitutes `@SKILL_DIR@` with the absolute path of the skill tree
that agent loads. A plugin manager leaves the placeholder, so the command body
also probes the plugin roots at runtime: `${PLUGIN_ROOT}`,
`${CLAUDE_PLUGIN_ROOT}`, `~/.omp/plugins/node_modules/better-seo`,
`~/.omp/plugins/cache/plugins/better-seo___*`, then the `~/.agents`, `~/.claude`
and `~/.codex` skill trees, the current directory, and finally a `find` over the
plugin roots. One file, both install modes.

| Consumer | Destination | Skill dir substituted |
|---|---|---|
| Claude Code | `~/.claude/commands/seo-audit.md` | `~/.claude/skills/better-seo` |
| omp native | `~/.omp/agent/commands/seo-audit.md` | `~/.agents/skills/better-seo` |
| omp agents provider | `~/.agents/commands/seo-audit.md` | `~/.agents/skills/better-seo` |
| omp codex provider | `~/.codex/commands/seo-audit.md` | `~/.codex/skills/better-seo` |

Usage: `/seo-audit https://example.com`

Native Codex is not a target: OpenAI deprecated custom prompts in favour of
skills, and the skill already covers it.

Installed as a plugin, most agents discover `commands/` from the plugin tree
directly, so none of the four paths above is needed.
