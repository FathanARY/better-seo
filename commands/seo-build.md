---
description: Set up SEO in a website project that has none or is half-built
argument-hint: "[project-dir]"
---

Configure SEO in this project$ARGUMENTS. Build, do not audit: if the user wants a
score for a live URL, that is `/seo-audit`.

## Step 1: find the scaffolder

```bash
H="${HOME:-}"; [ -n "$H" ] || H="${USERPROFILE:-}"
CLI=""
for c in "@SKILL_DIR@/scripts/seo_build.py" \
         "${PLUGIN_ROOT:-}/skills/better-seo-build/scripts/seo_build.py" \
         "${CLAUDE_PLUGIN_ROOT:-}/skills/better-seo-build/scripts/seo_build.py" \
         "$H/.omp/plugins/node_modules/better-seo/skills/better-seo-build/scripts/seo_build.py" \
         "$H/.agents/skills/better-seo-build/scripts/seo_build.py" \
         "$H/.claude/skills/better-seo-build/scripts/seo_build.py" \
         "$H/.codex/skills/better-seo-build/scripts/seo_build.py"; do
  case "$c" in *@*) continue ;; esac
  [ -f "$c" ] && CLI="$c" && break
done
if [ -z "$CLI" ]; then
  for c in "$H"/.omp/plugins/cache/plugins/better-seo___*/skills/better-seo-build/scripts/seo_build.py; do
    [ -f "$c" ] && CLI="$c" && break
  done
fi
case "$CLI" in
  /*) command -v cygpath >/dev/null 2>&1 && CLI="$(cygpath -m "$CLI")" ;;
esac
echo "CLI=$CLI"
```

If `CLI=` is empty, say the skill is not installed and stop.

## Step 2: read the project, then plan

```bash
ls
cat package.json 2>/dev/null || cat _config.yml 2>/dev/null || cat hugo.toml 2>/dev/null
python "$CLI" --root .
```

This is a dry run. Report the detected framework, the evidence files, whether the
site origin came from `package.json` or is a placeholder, and the planned steps.

## Step 3: resolve what only the user knows, then write

Ask once, batched, for the values you cannot read from the repo:

- the real origin (scheme, and `www` or not)
- the site name for schema
- default page title, 50-60 chars
- default meta description, 120-155 chars

Then:

```bash
python "$CLI" --root . --site <origin> --name <name> \
  --title "<title>" --description "<description>" --write
```

For a plain HTML page, also merge the head block:

```bash
python "$CLI" --root . --inject index.html --site <origin> --name <name> \
  --title "<title>" --description "<description>" --write
```

It never overwrites: an existing path reports `skipped (exists)`. Read that file
and merge by hand instead. Leave nothing guessed; unverified values stay `TODO`.

## Step 4: the rest of the checklist

The scaffolder covers robots, sitemap, llms.txt, canonical, title, description,
Open Graph and `WebSite`/`WebPage` JSON-LD. Verify or add, in this order:

1. `<html lang="...">` on every page.
2. Exactly one `<h1>` per page, matching intent.
3. Per-page-type JSON-LD: `Article`, `Product`, `FAQPage`, `LocalBusiness`.
4. Server-rendered body text, not JS-only.
5. Internal links with descriptive anchors.

## Step 5: verify, do not assert

```bash
python "$CLI" --root .                    # every step should now read skipped (exists)
```

Then audit what you produced, using the audit skill's CLI if present:

```bash
python <audit-dir>/scripts/audit.py http://localhost:3000
```

Or, if it cannot be served, the built file:

```bash
python <audit-dir>/scripts/audit.py --fixture dist/index.html
```

Report the score and what changed. If you could not run it, say so plainly
instead of claiming success.

Never invent traffic, rankings, or competitor data. Never promise a ranking.
Never add `noindex` to make a score look better. Never delete existing SEO work
to make the output uniform: merge, do not reset.
