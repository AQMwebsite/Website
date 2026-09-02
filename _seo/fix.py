"""Apply SEO + GEO fixes to the static site.

Idempotent: every insertion is guarded, so re-running changes nothing.
Aborts without writing if any expected anchor is missing.
"""
import json
import os
import re
import sys
from datetime import date

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://aquamain.com"
ORG_ID = f"{SITE}/#organization"
OG_IMG = f"{SITE}/assets/uploads/aquamain-social-1200x630.jpg"
OG_ALT = "Aquamain site team reviewing drawings during utility ground works"

AREA = [{"@type": "AdministrativeArea", "name": "Southern England"},
        {"@type": "AdministrativeArea", "name": "Wales"}]

ORG = {
    "@type": "ProfessionalService",
    "@id": ORG_ID,
    "name": "Aquamain (UK) Ltd",
    "alternateName": "Aquamain",
    "url": SITE,
    "description": ("Independent SLP and ICP multi-utility contractor designing, building and "
                    "commissioning water and electricity networks for residential, commercial "
                    "and industrial developments across Southern England and Wales."),
    "logo": {"@type": "ImageObject",
             "url": f"{SITE}/assets/uploads/Aquamain-Full-Colour-logo.svg"},
    "image": OG_IMG,
    "telephone": "+441749345842",
    "email": "info@aquamain.com",
    "address": {"@type": "PostalAddress", "streetAddress": "Unit 22, Evercreech",
                "addressLocality": "Shepton Mallet", "addressRegion": "Somerset",
                "postalCode": "BA4 6NA", "addressCountry": "GB"},
    "geo": {"@type": "GeoCoordinates", "latitude": 51.1279472, "longitude": -2.5171886},
    "hasMap": "https://www.google.com/maps/place/Aquamain+UK+Ltd/@51.1279472,-2.5171886,15z/",
    "areaServed": AREA,
    "openingHoursSpecification": [{
        "@type": "OpeningHoursSpecification",
        "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "opens": "08:00", "closes": "17:00"}],
    "sameAs": ["https://www.linkedin.com/company/aquamain-uk-ltd/"],
    "vatID": "GB291813588",
    "identifier": {"@type": "PropertyValue", "name": "Companies House number",
                   "value": "05248553"},
    "hasCredential": [
        {"@type": "EducationalOccupationalCredential", "credentialCategory": "certification",
         "name": n} for n in [
            "WIRS - Water Industry Registration Scheme",
            "NERS - National Electricity Registration Scheme",
            "ISO 9001 Quality Management",
            "ISO 14001 Environmental Management",
            "ISO 45001 Occupational Health and Safety Management"]],
    "contactPoint": [
        {"@type": "ContactPoint", "contactType": "sales",
         "name": "Project enquiries and quotations", "telephone": "+441749345842",
         "email": "mains@aquamain.com", "areaServed": "GB", "availableLanguage": "en-GB"},
        {"@type": "ContactPoint", "contactType": "technical support",
         "name": "Pre-construction advice", "email": "pre-construction@aquamain.com",
         "areaServed": "GB", "availableLanguage": "en-GB"},
        {"@type": "ContactPoint", "contactType": "reservations",
         "name": "Services and plot connection bookings", "email": "services@aquamain.com",
         "areaServed": "GB", "availableLanguage": "en-GB"},
        {"@type": "ContactPoint", "contactType": "billing support",
         "name": "Accounts queries", "email": "accounts@aquamain.com",
         "areaServed": "GB", "availableLanguage": "en-GB"}],
}

SERVICES = {
    "residential": ("Residential Multi-Utility Connections",
        "Water and electricity connections for residential housing developments, from early "
        "advisory through design and construction to final adoption.",
        "Utility connections for residential developments", "Residential"),
    "industrial-commercial": ("Industrial and Commercial Utility Infrastructure",
        "WIRS and NERS accredited design, construction and commissioning of water and HV "
        "electricity networks for commercial and industrial developments.",
        "Utility infrastructure for industrial and commercial sites", "Industrial & Commercial"),
    "ev-charging": ("EV Charging Hub Design and Build",
        "Design and build of electrical infrastructure for electric vehicle charging hubs, from "
        "the incoming power connection through to a fully energised site. Approved contractor to "
        "multiple charge point operators.",
        "EV charging hub electrical infrastructure", "EV Charging"),
    "testing-and-commissioning": ("Water and Electricity Testing and Commissioning",
        "Water main and non-potable pipe commissioning including pressure testing and "
        "chlorination, riser main pressure testing, and LV/HV cable testing, fault finding and "
        "energisation.",
        "Testing and commissioning of water and electricity networks", "Testing & Commissioning"),
    "design": ("WIRS Accredited Potable and Fire Main Design",
        "Standalone WIRS-accredited design service for potable water mains and fire mains, "
        "producing adoptable designs with no obligation to build with us.",
        "Water main and fire main design", "Design"),
    "maintenance": ("Water and Electricity Network Maintenance",
        "Planned and emergency maintenance, repairs and alterations to water and electricity "
        "networks for NAVs and IDNOs, delivered under framework agreements.",
        "Ongoing network maintenance and repairs", "Maintenance"),
}

FAQ = [
    ("What is a Self-Lay Provider (SLP)?",
     "If your development or building project requires a new water network, you have the option "
     "to have this carried out by the water company, or to work with an approved third-party "
     "contractor like us to do the contestable work - commonly known as self-lay, or SLP. "
     "Aquamain is WIRS accredited."),
    ("What is an Independent Connection Provider (ICP)?",
     "An ICP is an accredited company that can build electricity networks to the agreed standards "
     "and quality required for them to be owned by either a Distribution Network Operator (DNO) "
     "or an Independent Distribution Network Operator (IDNO). Aquamain is NERS accredited."),
]

POLICY_TITLES = {
    "environmental-policy": "Environmental Policy",
    "equal-opportunities-policy": "Equal Opportunities Policy",
    "health-and-safety-policy": "Health & Safety Policy",
    "quality-policy": "Quality Policy",
    "modern-slavery-act-statement": "Modern Slavery Act Statement",
    "privacy-policy": "Privacy Policy",
    "cookie-policy-uk": "Cookie Policy",
}

TITLE_FIXES = {
    "about-us/index.html": (
        "About Aquamain | WIRS &amp; NERS Accredited Multi-Utility Contractor",
        "About Aquamain | WIRS &amp; NERS Multi-Utility Contractor"),
    "residential/index.html": (
        "Residential Utility Connections for Housing Developers | Aquamain",
        "Residential Utility Connections for Housebuilders | Aquamain"),
}


def crumbs(slug, label, mid=None):
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": SITE + "/"}]
    if mid:
        items.append({"@type": "ListItem", "position": 2, "name": mid})
        items.append({"@type": "ListItem", "position": 3, "name": label,
                      "item": f"{SITE}/{slug}/"})
    else:
        items.append({"@type": "ListItem", "position": 2, "name": label,
                      "item": f"{SITE}/{slug}/"})
    return {"@type": "BreadcrumbList", "@id": f"{SITE}/{slug}/#breadcrumb",
            "itemListElement": items}


def graph_for(rel):
    g = [ORG]
    if rel == "index.html":
        g.append({"@type": "WebSite", "@id": f"{SITE}/#website", "name": "Aquamain",
                  "url": SITE, "inLanguage": "en-GB",
                  "publisher": {"@id": ORG_ID}})
        return g
    slug = rel.split("/")[0]
    if slug in SERVICES:
        name, desc, stype, label = SERVICES[slug]
        g.append({"@type": "Service", "@id": f"{SITE}/{slug}/#service", "name": name,
                  "description": desc, "serviceType": stype,
                  "provider": {"@id": ORG_ID}, "areaServed": AREA,
                  "url": f"{SITE}/{slug}/"})
        g.append(crumbs(slug, label, "Services"))
    elif slug == "about-us":
        g.append({"@type": "FAQPage", "@id": f"{SITE}/about-us/#faq",
                  "mainEntity": [{"@type": "Question", "name": q,
                                  "acceptedAnswer": {"@type": "Answer", "text": a}}
                                 for q, a in FAQ]})
        g.append(crumbs("about-us", "About Us"))
    elif slug == "contact":
        g.append({"@type": "ContactPage", "@id": f"{SITE}/contact/#contactpage",
                  "url": f"{SITE}/contact/", "name": "Contact Aquamain",
                  "about": {"@id": ORG_ID}})
        g.append(crumbs("contact", "Contact"))
    elif slug in POLICY_TITLES:
        g.append(crumbs(slug, POLICY_TITLES[slug]))
    return g


def social_block(html, rel):
    """og:image + twitter card, derived from the page's own title/description."""
    t = re.search(r'<meta property="og:title" content="([^"]*)"', html)
    d = re.search(r'<meta property="og:description" content="([^"]*)"', html)
    title = t.group(1) if t else ""
    desc = d.group(1) if d else ""
    return (
        f'<meta property="og:image" content="{OG_IMG}">\n'
        f'<meta property="og:image:width" content="1200">\n'
        f'<meta property="og:image:height" content="630">\n'
        f'<meta property="og:image:alt" content="{OG_ALT}">\n'
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{title}">\n'
        f'<meta name="twitter:description" content="{desc}">\n'
        f'<meta name="twitter:image" content="{OG_IMG}">\n'
        f'<meta name="twitter:image:alt" content="{OG_ALT}">\n'
    )


def add_image_dims(html):
    """Add width/height to <img> tags that have no dimension guard."""
    n = 0

    def repl(m):
        nonlocal n
        tag = m.group(0)
        if re.search(r'\swidth=', tag) or 'aspect-ratio' in tag:
            return tag
        style = re.search(r'style="([^"]*)"', tag)
        if style and re.search(r'height:\s*\d+px', style.group(1)):
            return tag
        src = re.search(r'src="([^"]*)"', tag)
        if not src:
            return tag
        p = src.group(1)
        if not p.startswith("/assets/"):
            return tag
        fp = os.path.join(ROOT, p.lstrip("/"))
        if not os.path.exists(fp) or fp.lower().endswith(".svg"):
            return tag
        try:
            with Image.open(fp) as im:
                w, h = im.size
        except Exception:
            return tag
        n += 1
        return tag.replace("<img", f'<img width="{w}" height="{h}"', 1)

    return re.sub(r"<img[^>]*>", repl, html), n


def main():
    changed, report = {}, []

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
            if "</head>" not in html:
                print(f"ABORT: no </head> in {rel}")
                sys.exit(1)

            did = []

            # title trim
            if rel in TITLE_FIXES:
                old, new = TITLE_FIXES[rel]
                if old in html:
                    html = html.replace(f"<title>{old}</title>", f"<title>{new}</title>")
                    html = html.replace(f'content="{old}"', f'content="{new}"')
                    did.append("title")

            # social meta
            if 'property="og:image"' not in html:
                html = html.replace("</head>", social_block(html, rel) + "</head>", 1)
                did.append("og+twitter")

            # schema
            if "application/ld+json" not in html:
                payload = {"@context": "https://schema.org", "@graph": graph_for(rel)}
                block = ('<script type="application/ld+json">'
                         + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                         + "</script>\n")
                html = html.replace("</head>", block + "</head>", 1)
                did.append(f"schema({len(payload['@graph'])})")

            # image dimensions
            html, n = add_image_dims(html)
            if n:
                did.append(f"dims({n})")

            if did:
                changed[path] = html
                report.append(f"  {rel:<40} {', '.join(did)}")

    for path, html in changed.items():
        open(path, "w", encoding="utf-8", newline="\n").write(html)

    print("PAGES UPDATED" if report else "no page changes needed")
    print("\n".join(report))
    return len(changed)


if __name__ == "__main__":
    n = main()
    print(f"\n{n} files written.")
