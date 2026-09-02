"""Full SEO + GEO audit of the static aquamain.com site.

Runs against the LOCAL repo files (source of truth) so it can be re-run before
every push. Live-only checks (headers, crawler access) are done separately.
"""
import json
import os
import re
import sys
from collections import Counter

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://aquamain.com"

SKIP_DIRS = {".git", "_seo", "worker", "assets"}


def page_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith(".html"):
                p = os.path.join(dirpath, fn)
                rel = os.path.relpath(p, ROOT).replace("\\", "/")
                out.append((rel, p))
    return sorted(out)


def url_for(rel):
    if rel == "index.html":
        return SITE + "/"
    if rel.endswith("/index.html"):
        return f"{SITE}/{rel[:-len('index.html')]}"
    return f"{SITE}/{rel}"


def audit():
    pages, issues = [], []

    def flag(sev, cat, page, msg):
        issues.append({"severity": sev, "category": cat, "page": page, "issue": msg})

    for rel, path in page_files():
        html = open(path, encoding="utf-8", errors="replace").read()
        s = BeautifulSoup(html, "lxml")
        url = url_for(rel)

        is_redirect = bool(s.find("meta", attrs={"http-equiv": "refresh"}))
        is_verify = rel.startswith("google") and rel.endswith(".html")
        is_404 = rel == "404.html"

        title = s.title.string.strip() if s.title and s.title.string else None
        desc_el = s.find("meta", attrs={"name": "description"})
        desc = desc_el.get("content", "").strip() if desc_el else None
        canon_el = s.find("link", rel="canonical")
        canon = canon_el.get("href") if canon_el else None

        text_soup = BeautifulSoup(html, "lxml")
        for x in text_soup(["script", "style", "nav", "footer"]):
            x.extract()
        body_words = len(re.sub(r"\s+", " ", text_soup.get_text(" ")).split())

        imgs = s.find_all("img")
        ld_blocks = s.find_all("script", type="application/ld+json")
        ld_types = []
        for b in ld_blocks:
            try:
                o = json.loads(b.string or "{}")
                ld_types += ([n.get("@type") for n in o["@graph"]]
                             if "@graph" in o else [o.get("@type")])
            except Exception:
                ld_types.append("PARSE-ERROR")

        rec = {
            "rel": rel, "url": url, "redirect_stub": is_redirect,
            "verify_file": is_verify, "is_404": is_404,
            "title": title, "title_len": len(title or ""),
            "desc": desc, "desc_len": len(desc or ""),
            "canonical": canon,
            "lang": (s.find("html") or {}).get("lang") if s.find("html") else None,
            "viewport": bool(s.find("meta", attrs={"name": "viewport"})),
            "h1": [re.sub(r"\s+", " ", h.get_text(" ")).strip() for h in s.find_all("h1")],
            "h2": [re.sub(r"\s+", " ", h.get_text(" ")).strip() for h in s.find_all("h2")],
            "h3": [re.sub(r"\s+", " ", h.get_text(" ")).strip() for h in s.find_all("h3")],
            "words": body_words,
            "imgs": len(imgs),
            "img_no_alt": sum(1 for i in imgs if not (i.get("alt") or "").strip()),
            "img_no_dims": sum(1 for i in imgs
                               if not (i.get("width") and i.get("height"))
                               and "aspect-ratio" not in (i.get("style") or "")
                               and not re.search(r"height:\s*\d+px", i.get("style") or "")),
            "img_no_lazy": sum(1 for i in imgs if i.get("loading") != "lazy"),
            "ld_types": ld_types,
            "og_image": bool(s.find("meta", property="og:image")),
            "og_title": bool(s.find("meta", property="og:title")),
            "twitter_card": bool(s.find("meta", attrs={"name": "twitter:card"})),
            "has_analytics": bool(re.search(
                r"gtag|googletagmanager|cloudflareinsights|plausible|umami|fathom|matomo",
                html, re.I)),
            "internal_links": len({a["href"] for a in s.find_all("a", href=True)
                                   if a["href"].startswith("/") and not a["href"].startswith("//")}),
            "breadcrumb_nav": bool(s.find("nav", class_="crumbs")),
        }
        pages.append(rec)

        if is_redirect or is_verify:
            continue

        # ---- checks ----
        if not title:
            flag("Critical", "On-Page", url, "missing <title>")
        elif len(title) > 62:
            flag("Low", "On-Page", url, f"title {len(title)} chars (>62 may truncate)")
        if not is_404:
            if not desc:
                flag("High", "On-Page", url, "missing meta description")
            elif len(desc) > 160:
                flag("Low", "On-Page", url, f"meta description {len(desc)} chars (>160 truncates)")
            if not canon:
                flag("High", "Technical", url, "missing canonical")
            if len(rec["h1"]) == 0:
                flag("High", "On-Page", url, "no H1")
            elif len(rec["h1"]) > 1:
                flag("Medium", "On-Page", url, f"{len(rec['h1'])} H1s")
            if not ld_types:
                flag("High", "Schema", url, "no JSON-LD structured data")
            if not rec["og_image"]:
                flag("Medium", "Social", url, "no og:image - link shares render without a preview")
            if not rec["twitter_card"]:
                flag("Low", "Social", url, "no twitter:card")
            if not rec["has_analytics"]:
                flag("High", "Measurement", url, "no analytics tag")
        if not rec["lang"]:
            flag("Medium", "Technical", url, "no lang attribute")
        if not rec["viewport"]:
            flag("High", "Technical", url, "no viewport meta")
        if rec["img_no_alt"]:
            flag("Medium", "Images", url, f"{rec['img_no_alt']} images missing alt")
        if rec["img_no_dims"]:
            flag("Low", "Images", url, f"{rec['img_no_dims']} images with no dimension guard (CLS)")

    # ---- site-wide ----
    real = [p for p in pages if not p["redirect_stub"] and not p["verify_file"] and not p["is_404"]]
    for field, sev in (("title", "High"), ("desc", "Medium")):
        c = Counter(p[field] for p in real if p[field])
        for val, n in c.items():
            if n > 1:
                flag(sev, "On-Page", "(site)", f"duplicate {field} on {n} pages: {str(val)[:50]}")

    # sitemap coverage
    sm_path = os.path.join(ROOT, "sitemap.xml")
    if os.path.exists(sm_path):
        sm = open(sm_path, encoding="utf-8").read()
        listed = set(re.findall(r"<loc>([^<]+)</loc>", sm))
        actual = {p["url"] for p in real}
        for u in sorted(actual - listed):
            flag("Medium", "Technical", u, "page not in sitemap.xml")
        for u in sorted(listed - actual):
            flag("Medium", "Technical", u, "sitemap lists a URL with no page file")
        if "image:image" not in sm:
            flag("Low", "Images", "(site)", "sitemap has no image entries")
        if "<lastmod>" not in sm:
            flag("Low", "Technical", "(site)", "sitemap has no <lastmod> dates")
    else:
        flag("Critical", "Technical", "(site)", "no sitemap.xml")

    if not os.path.exists(os.path.join(ROOT, "robots.txt")):
        flag("High", "Technical", "(site)", "no robots.txt")
    if not os.path.exists(os.path.join(ROOT, "llms.txt")):
        flag("Low", "GEO", "(site)", "no llms.txt")

    return pages, issues


if __name__ == "__main__":
    pages, issues = audit()
    real = [p for p in pages if not p["redirect_stub"] and not p["verify_file"]]

    print(f"{'page':<34}{'T':<5}{'D':<5}{'H1':<4}{'wds':<6}{'img':<5}"
          f"{'noalt':<7}{'ld':<4}{'og':<4}{'ga':<4}crumb")
    print("-" * 92)
    for p in sorted(real, key=lambda x: x["rel"]):
        print(f"{p['rel']:<34}{p['title_len']:<5}{p['desc_len']:<5}{len(p['h1']):<4}"
              f"{p['words']:<6}{p['imgs']:<5}{p['img_no_alt']:<7}"
              f"{len(p['ld_types']):<4}{'y' if p['og_image'] else '-':<4}"
              f"{'y' if p['has_analytics'] else '-':<4}"
              f"{'y' if p['breadcrumb_nav'] else '-'}")

    print("\n" + "=" * 92)
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    issues.sort(key=lambda i: (order[i["severity"]], i["category"], i["page"]))
    counts = Counter(i["severity"] for i in issues)
    print("ISSUES:", ", ".join(f"{k} {counts[k]}" for k in
                               ["Critical", "High", "Medium", "Low"] if counts[k]))
    print("=" * 92)
    grouped = {}
    for i in issues:
        grouped.setdefault((i["severity"], i["category"], i["issue"]), []).append(i["page"])
    for (sev, cat, msg), pgs in sorted(grouped.items(), key=lambda kv: order[kv[0][0]]):
        where = "all pages" if len(pgs) >= len(real) - 1 else f"{len(pgs)} page(s)"
        print(f"  [{sev:<8}] {cat:<12} {msg}  -> {where}")

    json.dump({"pages": pages, "issues": issues},
              open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit.json"),
                   "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\n{len(issues)} issues written to _seo/audit.json")
