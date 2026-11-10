#!/usr/bin/env python3
"""Scaffold SEO configuration into an existing project. Stdlib only.

Lives inside the better-seo-build skill; run it by path.

Usage:
    python <skill-dir>/scripts/seo_build.py                 # detect + plan, writes nothing
    python <skill-dir>/scripts/seo_build.py --write         # apply
    python <skill-dir>/scripts/seo_build.py --site https://example.com --write
    python <skill-dir>/scripts/seo_build.py --inject index.html --write

Dry-run is the default. Nothing is ever overwritten: a path that already exists
is reported as "exists" and left alone.

Exit 0 on success, 2 when the project cannot be read.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

AI_CRAWLERS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot",
               "ClaudeBot", "Google-Extended", "bingbot", "CCBot"]

# framework -> (detect predicate on the project root, artifact paths)
# Paths are relative to the project root. A None means "this framework has no
# native form for it, fall back to the static file".
FRAMEWORKS = {
    "nextjs-app": {
        "evidence": ["next.config.js", "next.config.mjs", "next.config.ts",
                     "app", "src/app"],
        "robots": "app/robots.ts",
        "sitemap": "app/sitemap.ts",
        "llms": "public/llms.txt",
        "head": "lib/seo.ts",
    },
    "nextjs-pages": {
        "evidence": ["next.config.js", "pages", "src/pages"],
        "robots": "public/robots.txt",
        "sitemap": "public/sitemap.xml",
        "llms": "public/llms.txt",
        "head": "lib/seo.ts",
    },
    "astro": {
        "evidence": ["astro.config.mjs", "astro.config.ts", "src/pages"],
        "robots": "public/robots.txt",
        "sitemap": "src/pages/sitemap.xml.ts",
        "llms": "public/llms.txt",
        "head": "src/components/Seo.astro",
    },
    "sveltekit": {
        "evidence": ["svelte.config.js", "src/routes"],
        "robots": "static/robots.txt",
        "sitemap": "src/routes/sitemap.xml/+server.ts",
        "llms": "static/llms.txt",
        "head": "src/lib/Seo.svelte",
    },
    "nuxt": {
        "evidence": ["nuxt.config.ts", "nuxt.config.js"],
        "robots": "public/robots.txt",
        "sitemap": "server/routes/sitemap.xml.ts",
        "llms": "public/llms.txt",
        "head": "composables/useSeo.ts",
    },
    "hugo": {
        "evidence": ["hugo.toml", "config.toml", "hugo.yaml"],
        "robots": "static/robots.txt",
        "sitemap": "layouts/sitemap.xml",
        "llms": "static/llms.txt",
        "head": "layouts/partials/seo.html",
    },
    "jekyll": {
        "evidence": ["_config.yml", "_posts"],
        "robots": "robots.txt",
        "sitemap": "sitemap.xml",
        "llms": "llms.txt",
        "head": "_includes/seo.html",
    },
    "eleventy": {
        "evidence": [".eleventy.js", "eleventy.config.js"],
        "robots": "src/robots.txt",
        "sitemap": "src/sitemap.xml",
        "llms": "src/llms.txt",
        "head": "src/_includes/seo.njk",
    },
    "wordpress": {
        "evidence": ["wp-config.php", "wp-content"],
        "robots": "robots.txt",
        "sitemap": None,
        "llms": "llms.txt",
        "head": None,
    },
    "static": {
        "evidence": [],
        "robots": "robots.txt",
        "sitemap": "sitemap.xml",
        "llms": "llms.txt",
        "head": "seo-head.html",
    },
}


# Config files name one framework unambiguously. Directories like src/pages are
# shared by several (astro and Next.js Pages both use it), so a config file wins
# and directory-only evidence is resolved by the ranking below.
CONFIG_FILES = {
    "next.config.js": "nextjs-app", "next.config.mjs": "nextjs-app",
    "next.config.ts": "nextjs-app",
    "astro.config.mjs": "astro", "astro.config.ts": "astro",
    "svelte.config.js": "sveltekit",
    "nuxt.config.ts": "nuxt", "nuxt.config.js": "nuxt",
    "hugo.toml": "hugo", "hugo.yaml": "hugo", "config.toml": "hugo",
    "_config.yml": "jekyll",
    ".eleventy.js": "eleventy", "eleventy.config.js": "eleventy",
    "wp-config.php": "wordpress",
}

# Directory evidence, strongest signal first. A directory shared by two
# frameworks must be disambiguated by that framework's own marker file.
DIR_EVIDENCE = [
    ("app", ("layout.tsx", "layout.ts", "layout.jsx"), "nextjs-app"),
    ("src/routes", ("+page.svelte", "+layout.svelte"), "sveltekit"),
    ("src/pages", ("index.astro", "*.astro"), "astro"),
    ("src/pages", ("_app.tsx", "index.tsx", "index.jsx"), "nextjs-pages"),
    ("pages", ("_app.tsx", "index.tsx", "index.jsx"), "nextjs-pages"),
    ("wp-content", (), "wordpress"),
    ("_posts", (), "jekyll"),
]


def detect(root: Path) -> tuple[str, list[str]]:
    """Pick a framework from files that are actually there.

    A config file is authoritative. Without one, directory evidence decides, and
    a directory shared by two frameworks is disambiguated by that framework's
    own marker file inside it.
    """
    for rel, kind in CONFIG_FILES.items():
        if (root / rel).exists():
            # A Next.js project with an app/ dir uses the App Router paths.
            if kind == "nextjs-app" or (root / "app").is_dir():
                if (root / "app").is_dir():
                    return "nextjs-app", [rel, "app"]
            return kind, [rel]

    for rel, markers, kind in DIR_EVIDENCE:
        d = root / rel
        if not d.is_dir():
            continue
        for marker in markers:
            if marker.startswith("*"):
                if any(d.rglob(marker)):
                    return kind, [rel]
            elif (d / marker).exists():
                return kind, [rel]
        # No marker needed: unambiguous directory.
        if not markers:
            return kind, [rel]

    # src/pages and pages exist but nothing identified them: Next.js is the
    # likelier default than guessing astro without an astro config.
    for rel in ("app", "src/app"):
        if (root / rel).is_dir():
            return "nextjs-app", [rel]
    for rel in ("src/pages", "pages"):
        if (root / rel).is_dir():
            return "nextjs-pages", [rel]

    return "static", []


def read_site(root: Path) -> tuple[str, str]:
    """Site origin and project name, from package.json when present."""
    pkg = root / "package.json"
    site = name = ""
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        name = str(data.get("name") or "")
        home = data.get("homepage") or ""
        if home:
            site = str(home)
        else:
            repo = data.get("repository")
            if isinstance(repo, dict):
                repo = repo.get("url")
            if isinstance(repo, str) and "github.com" in repo:
                slug = repo.rstrip("/").removesuffix(".git").split("github.com")[-1].strip("/:")
                if slug:
                    site = f"https://{slug.split('/')[0]}.github.io/{slug.split('/')[1]}"
    if not name:
        name = root.name
    return site.rstrip("/"), name


def robots_txt(site: str) -> str:
    lines = [
        "# Managed by better-seo-build. Review before deploying.",
        "",
        "# Standard crawlers: everything is allowed.",
        "User-agent: *",
        "Allow: /",
        "",
        "# AI search crawlers. Blocking these removes the site from that engine's",
        "# answers. Allow them unless you have a reason to opt out.",
    ]
    for ua in AI_CRAWLERS:
        lines += [f"User-agent: {ua}", "Allow: /", ""]
    if site:
        lines.append(f"Sitemap: {site}/sitemap.xml")
    else:
        lines.append("# Add once you know the origin: Sitemap: https://example.com/sitemap.xml")
    return "\n".join(lines) + "\n"


def sitemap_xml(site: str) -> str:
    """A static sitemap can only know the routes you list. Say so, do not fake.

    Framework targets get a generated sitemap instead; this is the fallback.
    """
    origin = site or "https://example.com"
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<!-- Generated by better-seo-build. Replace the placeholder <url> entries with
     your real routes, or switch to the framework sitemap generator. -->
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{origin}/</loc>
  </url>
  <!-- Add one <url><loc>...</loc></url> per page. Remove entries you do not have. -->
</urlset>
'''


def llms_txt(site: str, name: str) -> str:
    origin = site or "https://example.com"
    return f'''# {name}

> One sentence describing what this site is and who it is for. Replace this.

# Optional, not a standard. Unproven as a ranking factor. Ship it only if the
# links below are real and curated; never use it to hide content from users.

## Core pages
- [Home]({origin}/): what the site offers in one line
- [About]({origin}/about): who runs it
- [Contact]({origin}/contact): how to reach a human
'''


def seo_head(site: str, name: str, title: str, description: str, path: str = "/") -> str:
    """The <head> block every page needs, plus JSON-LD."""
    origin = site or "https://example.com"
    canonical = origin + path
    t = title or f"{name} — replace with a 50-60 character title"
    d = description or ("Replace with a 120-155 character description that states "
                        "what the page delivers and to whom.")
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "WebSite", "@id": f"{origin}/#website", "url": f"{origin}/",
             "name": name},
            {"@type": "WebPage", "@id": f"{canonical}#webpage",
             "url": canonical, "isPartOf": {"@id": f"{origin}/#website"}},
        ],
    }
    return f'''<title>{t}</title>
<meta name="description" content="{d}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{canonical}">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">
{json.dumps(ld, indent=2)}
</script>
'''


def framework_wrappers(kind: str, site: str, name: str, title: str, description: str) -> dict:
    """Framework-native replacements for the generic static artifacts."""
    origin = site or "https://example.com"
    if kind == "nextjs-app":
        return {
            "robots": '''import type { MetadataRoute } from "next";

// Generated by better-seo-build. AI crawlers are allowed on purpose: blocking
// them removes the site from that engine's answers.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/" }],
    sitemap: "SITE/sitemap.xml",
  };
}
'''.replace("SITE", origin),
            "sitemap": '''import type { MetadataRoute } from "next";

// Generated by better-seo-build. Add the real routes; this only lists the root.
export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: "SITE/", lastModified: new Date(), changeFrequency: "weekly", priority: 1 }];
}
'''.replace("SITE", origin),
            "head": '''import type { Metadata } from "next";

// Generated by better-seo-build. Export from your root layout:
//   export const metadata = siteMetadata({ title: "...", description: "..." });
export function siteMetadata({ title, description, path = "/" }: {
  title: string;
  description: string;
  path?: string;
}): Metadata {
  const url = "SITE" + path;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: { title, description, url, type: "website" },
    twitter: { card: "summary_large_image", title, description },
  };
}

export function websiteJsonLd(name: string) {
  return {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": "SITE/#website",
    url: "SITE/",
    name,
  };
}
'''.replace("SITE", origin),
        }
    if kind == "astro":
        return {
            "sitemap": '''// Generated by better-seo-build. Lists the routes Astro can see at build time.
import type { APIRoute } from "astro";

const SITE = "SITE";

export const GET: APIRoute = async () => {
  const pages = import.meta.glob("../pages/**/*.{astro,md,mdx}");
  const urls = Object.keys(pages)
    .map((p) => p.replace("../pages", "").replace(/\\.(astro|md|mdx)$/, ""))
    .map((p) => (p.endsWith("/index") ? p.slice(0, -5) : p))
    .filter((p) => !p.includes("["))
    .map((p) => `  <url><loc>${SITE}${p || "/"}</loc></url>`);
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\\n${urls.join("\\n")}\\n</urlset>`;
  return new Response(xml, { headers: { "Content-Type": "application/xml" } });
};
'''.replace("\\n", "\n"),
            "head": '''---
// Generated by better-seo-build. Usage: <Seo title={...} description={...} />
interface Props { title: string; description: string; path?: string }
const { title, description, path = "/" } = Astro.props;
const canonical = "SITE" + path;
---
<title>{title}</title>
<meta name="description" content={description} />
<link rel="canonical" href={canonical} />
<meta property="og:type" content="website" />
<meta property="og:title" content={title} />
<meta property="og:description" content={description} />
<meta property="og:url" content={canonical} />
<meta name="twitter:card" content="summary_large_image" />
'''.replace("SITE", origin),
        }
    if kind == "hugo":
        return {
            "head": '''{{/* Generated by better-seo-build. Include inside <head>:
       {{ partial "seo.html" . }} */}}
<title>{{ if .Title }}{{ .Title }} — {{ end }}{{ .Site.Title }}</title>
{{ with .Description }}<meta name="description" content="{{ . }}">{{ end }}
<link rel="canonical" href="{{ .Permalink }}">
<meta property="og:type" content="website">
<meta property="og:title" content="{{ .Title }}">
<meta property="og:url" content="{{ .Permalink }}">
<meta name="twitter:card" content="summary_large_image">
''',
        }
    if kind == "jekyll":
        return {
            "head": '''{% comment %} Generated by better-seo-build. {% include seo.html %} from <head>. {% endcomment %}
<title>{{ page.title | default: site.title }}</title>
<meta name="description" content="{{ page.description | default: site.description }}">
<link rel="canonical" href="{{ page.url | absolute_url }}">
<meta property="og:type" content="website">
<meta property="og:title" content="{{ page.title | default: site.title }}">
<meta property="og:url" content="{{ page.url | absolute_url }}">
<meta name="twitter:card" content="summary_large_image">
''',
        }
    if kind == "sveltekit":
        return {
            "sitemap": '''// Generated by better-seo-build. Add real routes; this lists the root only.
import type { RequestHandler } from "./$types";

const SITE = "SITE";

export const GET: RequestHandler = () => {
  const body = `<?xml version="1.0" encoding="UTF-8"?>\\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\\n  <url><loc>${SITE}/</loc></url>\\n</urlset>`;
  return new Response(body, { headers: { "Content-Type": "application/xml" } });
};
'''.replace("\\n", "\n").replace("SITE", origin),
            "head": '''<!-- Generated by better-seo-build. Place inside <svelte:head>,
     passing title and description from the page load: -->
<script lang="ts">
  export let title: string;
  export let description: string;
  export let path = "/";
  $: canonical = "SITE" + path;
</script>
<title>{title}</title>
<meta name="description" content={description} />
<link rel="canonical" href={canonical} />
<meta property="og:type" content="website" />
<meta property="og:title" content={title} />
<meta property="og:description" content={description} />
<meta property="og:url" content={canonical} />
<meta name="twitter:card" content="summary_large_image" />
'''.replace("SITE", origin),
        }
    if kind == "nuxt":
        return {
            "sitemap": '''// Generated by better-seo-build. Add real routes; this lists the root only.
const SITE = "SITE";

export default defineEventHandler(() => {
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\\n  <url><loc>${SITE}/</loc></url>\\n</urlset>`;
  setHeader("Content-Type", "application/xml");
  return xml;
});
'''.replace("\\n", "\n").replace("SITE", origin),
            "head": '''// Generated by better-seo-build. Use in a page's setup:
//   useSeo({ title: "...", description: "..." })
export function useSeo({ title, description, path = "/" }: {
  title: string; description: string; path?: string;
}) {
  const url = "SITE" + path;
  useHead({
    title,
    link: [{ rel: "canonical", href: url }],
    meta: [
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
      { property: "og:url", content: url },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  });
}
'''.replace("SITE", origin),
        }
    return {}


def plan(root: Path, site: str, name: str, title: str, description: str,
         inject: Path | None) -> list[dict]:
    kind, evidence = detect(root)
    spec = FRAMEWORKS[kind]
    native = framework_wrappers(kind, site, name, title, description)

    steps: list[dict] = []

    def add(key: str, label: str):
        rel = spec.get(key)
        if not rel:
            steps.append({"kind": key, "path": None,
                          "note": f"{kind} has no native {label}; handle manually"})
            return
        content = native.get(key) or {
            "robots": robots_txt(site),
            "sitemap": sitemap_xml(site),
            "llms": llms_txt(site, name),
            "head": seo_head(site, name, title, description),
        }[key]
        target = root / rel
        steps.append({"kind": key, "path": rel, "exists": target.exists(),
                      "content": content})

    add("robots", "robots.txt")
    if kind == "wordpress":
        steps.append({"kind": "sitemap", "path": None,
                      "note": "WordPress ships /sitemap.xml via core; verify before adding"})
    else:
        add("sitemap", "sitemap.xml")
    add("llms", "llms.txt")
    add("head", "head metadata")

    if inject is not None:
        steps.append({"kind": "inject", "path": str(inject), "exists": inject.exists()})

    return steps


def inject_head(path: Path, block: str) -> tuple[bool, str]:
    """Merge the SEO tags into <head>: replace what exists, add what is missing.

    A second <title> or <meta name=description> is worse than none, so existing
    tags are replaced rather than appended.
    """
    if not path.is_file():
        return False, "file does not exist"
    html = path.read_text(encoding="utf-8", errors="replace")
    head_match = re.search(r"<head[^>]*>(.*?)</head>", html, re.S | re.I)
    if not head_match:
        return False, "no <head> to merge into"

    head = head_match.group(1)
    replaced: list[str] = []

    # Replace an existing title in place with the block's title, keep the rest.
    title_match = re.search(r"<title>(.*?)</title>", block, re.S)
    if title_match:
        new_title = title_match.group(0)
        if re.search(r"<title>.*?</title>", head, re.S | re.I):
            head = re.sub(r"<title>.*?</title>", new_title.replace("\\", "\\\\"), head,
                          count=1, flags=re.S | re.I)
            replaced.append("title")
        else:
            head = "\n" + new_title + head

    # Everything except the title goes in as new tags. Where the head already
    # has an equivalent, drop the OLD one from the head so the merged result has
    # exactly one of each.
    rest = re.sub(r"<title>.*?</title>\s*", "", block, count=1, flags=re.S)
    if 'rel="canonical"' in head or "rel='canonical'" in head:
        head = re.sub(r'<link[^>]+rel=["\']canonical["\'][^>]*>\s*', "", head, flags=re.I)
        replaced.append("canonical")
    if re.search(r'<meta[^>]+name=["\']description["\']', head, re.I):
        head = re.sub(r'<meta[^>]+name=["\']description["\'][^>]*>\s*', "", head, flags=re.I)
        replaced.append("description")
    if "application/ld+json" in head:
        head = re.sub(r'<script type="application/ld\+json">.*?</script>\s*', "", head, flags=re.S)
        replaced.append("json-ld")

    merged = head.rstrip() + "\n" + rest
    html = html[:head_match.start(1)] + merged + html[head_match.end(1):]
    path.write_text(html, encoding="utf-8")
    detail = "injected SEO head"
    if replaced:
        detail += f" (replaced existing {', '.join(replaced)})"
    return True, detail


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scaffold SEO configuration into a project.")
    ap.add_argument("--root", default=".", help="project directory (default: cwd)")
    ap.add_argument("--site", help="site origin, e.g. https://example.com")
    ap.add_argument("--name", help="site name for schema and llms.txt")
    ap.add_argument("--title", default="", help="default page title")
    ap.add_argument("--description", default="", help="default meta description")
    ap.add_argument("--inject", help="an HTML file to patch: adds the SEO head block")
    ap.add_argument("--write", action="store_true", help="apply (default is a dry run)")
    ap.add_argument("--json", help="write the plan/report to this path")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"error": f"not a directory: {root}"}), file=sys.stderr)
        return 2

    site_guessed, name_guessed = read_site(root)
    site = (args.site or site_guessed).rstrip("/")
    name = args.name or name_guessed
    title, description = args.title, args.description

    inject = Path(args.inject) if args.inject else None
    if inject is not None and not inject.is_absolute():
        inject = root / inject

    kind, evidence = detect(root)
    steps = plan(root, site, name, title, description, inject)

    report = {
        "root": str(root),
        "framework": kind,
        "evidence": evidence,
        "site": site,
        "site_source": "explicit" if args.site else ("package.json" if site_guessed else "placeholder"),
        "name": name,
        "write": bool(args.write),
        "steps": [],
    }

    for step in steps:
        entry = {k: v for k, v in step.items() if k != "content"}
        if step.get("path") and step["kind"] != "inject":
            target = root / step["path"]
            if target.exists():
                entry["action"] = "skipped (exists)"
            elif args.write:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(step["content"], encoding="utf-8")
                entry["action"] = "written"
            else:
                entry["action"] = "would write"
        elif step["kind"] == "inject" and inject is not None:
            block = seo_head(site, name, title, description)
            if args.write:
                ok, why = inject_head(inject, block)
                entry["action"] = "injected" if ok else f"skipped ({why})"
            else:
                entry["action"] = "would inject"
        else:
            entry.setdefault("action", "manual")
        report["steps"].append(entry)

    blob = json.dumps(report, indent=2, ensure_ascii=False)
    if args.json:
        Path(args.json).write_text(blob, encoding="utf-8")
    if not args.quiet:
        print(blob)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
