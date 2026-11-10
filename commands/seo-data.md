---
description: Read Search Console and Core Web Vitals data for a site
argument-hint: "[property or url]"
---

Get real search data$ARGUMENTS. Do not estimate anything.

## Step 1: find the tools

```bash
H="${HOME:-}"; [ -n "$H" ] || H="${USERPROFILE:-}"
CLI=""
for c in "@SKILL_DIR@/scripts" \
         "${PLUGIN_ROOT:-}/skills/better-seo-data/scripts" \
         "${CLAUDE_PLUGIN_ROOT:-}/skills/better-seo-data/scripts" \
         "$H/.omp/plugins/node_modules/better-seo/skills/better-seo-data/scripts" \
         "$H/.agents/skills/better-seo-data/scripts" \
         "$H/.claude/skills/better-seo-data/scripts" \
         "$H/.codex/skills/better-seo-data/scripts"; do
  case "$c" in *@*) continue ;; esac
  [ -d "$c" ] && CLI="$c" && break
done
if [ -z "$CLI" ]; then
  for c in "$H"/.omp/plugins/cache/plugins/better-seo___*/skills/better-seo-data/scripts; do
    [ -d "$c" ] && CLI="$c" && break
  done
fi
case "$CLI" in
  /*) command -v cygpath >/dev/null 2>&1 && CLI="$(cygpath -m "$CLI")" ;;
esac
echo "CLI=$CLI"
```

If empty, say the skill is not installed and stop.

## Step 2: decide what is being asked

- Clicks, impressions, CTR, position, "why no traffic" → **Search Console**.
- LCP, INP, CLS, "is it slow" → **Lighthouse**.
- If both are asked, run Search Console first: it is cheap, and it tells you
  which pages are worth spending a 60-second Lighthouse run on.

## Step 3: Search Console

```bash
python "$CLI/gsc.py" sites
python "$CLI/gsc.py" report --property <property> --days 28 --json gsc.json
python "$CLI/gsc.py" opportunities --property <property>
```

`--property` is either `sc-domain:example.com` or a full `https://example.com/`
URL. Use `sites` first if you do not know which form is verified.

If it exits **3**, credentials are missing. Print the setup instructions from the
error verbatim and stop. Do not estimate numbers, do not try scraping Google.

Then report:

- totals for the window, and the exact `start`/`end` dates the API returned
- the pages worth acting on from `opportunities`, each with its impressions
- note that GSC data lags about `lag_days`; the last day is partial

Reminder: `position` is an average across queries. Never phrase it as "you rank
#3 for X".

## Step 4: Core Web Vitals

```bash
python "$CLI/cwv.py" <url> --json cwv.json
```

Use `--mobile` for the mobile profile. Takes 30-60s.

If it exits **3**, the Lighthouse/Chrome toolchain is missing. Print the install
steps from the error and stop; never install it yourself without asking.

Then report `failing`, the top `opportunities` by `savings_ms`, and repeat the
`caveat`: this is lab data from one synthetic run, not what real users
experience. Field INP requires CrUX.

## Step 5: hand off

These two tools find problems; they do not fix them.

- Head tags, canonical, sitemap → `/seo-build`
- Page structure, schema, robots policy → `/seo-audit`

Never invent traffic, positions, or vitals. "Not configured" is a complete and
correct answer.
