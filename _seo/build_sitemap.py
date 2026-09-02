"""Regenerate sitemap.xml with <lastmod> and <image:image> entries.

lastmod comes from git's last-commit date per file, falling back to mtime -
a real content date rather than "today", which search engines learn to ignore.
"""
import os
import re
import subprocess
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://aquamain.com"

PRIORITY = {"": "1.0", "about-us": "0.8", "contact": "0.8",
            "residential": "0.9", "industrial-commercial": "0.9", "ev-charging": "0.9",
            "testing-and-commissioning": "0.9", "design": "0.9", "maintenance": "0.9"}
DEFAULT_PRIORITY = "0.3"


def git_date(path):
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", path],
                             cwd=ROOT, capture_output=True, text=True, timeout=20)
        d = out.stdout.strip()
        if d:
            return d[:10]
    except Exception:
        pass
    return datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%d")


def pages():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {".git", "_seo", "worker", "assets"}]
        for fn in filenames:
            if fn != "index.html":
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            html = open(path, encoding="utf-8", errors="replace").read()
            if 'http-equiv="refresh"' in html:
                continue                      # redirect stubs stay out of the sitemap
            slug = "" if rel == "index.html" else rel[:-len("/index.html")]
            out.append((slug, path, html))
    return sorted(out, key=lambda x: (PRIORITY.get(x[0], DEFAULT_PRIORITY) != "1.0", x[0]))


def build():
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
             '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    n_img = 0
    for slug, path, html in pages():
        loc = f"{SITE}/" if slug == "" else f"{SITE}/{slug}/"
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{git_date(path)}</lastmod>")
        lines.append(f"    <priority>{PRIORITY.get(slug, DEFAULT_PRIORITY)}</priority>")

        seen = set()
        for img in BeautifulSoup(html, "lxml").find_all("img"):
            src = img.get("src") or ""
            if not src.startswith("/assets/") or src in seen:
                continue
            seen.add(src)
            alt = (img.get("alt") or "").strip()

            # Only Aquamain's own work belongs in an image sitemap. Client logos
            # and accreditation badges are other organisations' marks and carry no
            # image-search value here.
            #   - anything in the footer is an accreditation badge strip
            #   - the banner logo sits in span.logo-box
            #   - client logos have 1-2 word alts ("MER", "Barratt Redrow"), whereas
            #     real photos are described properly ("Cable terminations by Aquamain")
            if img.find_parent("footer") or img.find_parent(class_="logo-box"):
                continue
            if len(alt.split()) < 4:
                continue
            # Accreditation badges also appear in body sections on some pages;
            # they are the awarding bodies' marks, not Aquamain's own imagery.
            if re.search(r"LRQA|UKAS|CHAS|SMAS|constructionline|accredited|certified",
                         alt, re.I):
                continue
            lines.append("    <image:image>")
            lines.append(f"      <image:loc>{SITE}{escape(src)}</image:loc>")
            if alt:
                lines.append(f"      <image:title>{escape(alt)}</image:title>")
            lines.append("    </image:image>")
            n_img += 1
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")

    out = "\n".join(lines)
    open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8", newline="\n").write(out)
    return out.count("<url>"), n_img


if __name__ == "__main__":
    urls, imgs = build()
    print(f"sitemap.xml: {urls} URLs, {imgs} image entries")
