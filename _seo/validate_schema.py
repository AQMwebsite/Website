"""Validate every JSON-LD block: parse, check required fields, check @id references resolve."""
import json
import os
import re
import sys

from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED = {
    "ProfessionalService": ["name", "url", "telephone", "address"],
    "Service": ["name", "provider", "areaServed", "url"],
    "FAQPage": ["mainEntity"],
    "BreadcrumbList": ["itemListElement"],
    "ContactPage": ["url"],
    "WebSite": ["name", "url"],
}

errors, summary = [], []

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d not in {".git", "_seo", "worker", "assets"}]
    for fn in sorted(filenames):
        if not fn.endswith(".html"):
            continue
        path = os.path.join(dirpath, fn)
        rel = os.path.relpath(path, ROOT).replace("\\", "/")
        html = open(path, encoding="utf-8").read()
        if 'http-equiv="refresh"' in html or rel.startswith("google") or rel == "404.html":
            continue

        blocks = BeautifulSoup(html, "lxml").find_all("script", type="application/ld+json")
        if not blocks:
            errors.append(f"{rel}: NO JSON-LD")
            continue
        if len(blocks) > 1:
            errors.append(f"{rel}: {len(blocks)} JSON-LD blocks (expected 1)")

        try:
            data = json.loads(blocks[0].string)
        except Exception as e:
            errors.append(f"{rel}: JSON parse error - {e}")
            continue

        if "@context" not in data:
            errors.append(f"{rel}: missing @context")
        nodes = data.get("@graph", [data])
        ids = {n.get("@id") for n in nodes if n.get("@id")}
        types = []

        for n in nodes:
            t = n.get("@type")
            types.append(t)
            for field in REQUIRED.get(t, []):
                if field not in n:
                    errors.append(f"{rel}: {t} missing required field '{field}'")
            # internal @id references must resolve within the same graph
            for k, v in n.items():
                if isinstance(v, dict) and set(v.keys()) == {"@id"}:
                    if v["@id"] not in ids:
                        errors.append(f"{rel}: {t}.{k} references unresolved @id {v['@id']}")

        # breadcrumb positions must be sequential from 1
        for n in nodes:
            if n.get("@type") == "BreadcrumbList":
                pos = [x.get("position") for x in n["itemListElement"]]
                if pos != list(range(1, len(pos) + 1)):
                    errors.append(f"{rel}: BreadcrumbList positions not sequential: {pos}")

        # FAQ answers must match visible page text
        for n in nodes:
            if n.get("@type") == "FAQPage":
                page_text = re.sub(r"\s+", " ", BeautifulSoup(html, "lxml").get_text(" "))
                for q in n["mainEntity"]:
                    name = q["name"]
                    if name.replace("&", "&").split("(")[0].strip()[:30] not in page_text:
                        errors.append(f"{rel}: FAQ question not found in visible text: {name[:40]}")

        summary.append(f"  {rel:<40} {len(blocks[0].string):>5} B  {types}")

print("SCHEMA PER PAGE")
print("\n".join(summary))
print()
if errors:
    print(f"ERRORS ({len(errors)}):")
    for e in errors:
        print("  " + e)
    sys.exit(1)
print("All JSON-LD valid: parsed, required fields present, @id references resolve.")
