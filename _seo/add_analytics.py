"""Insert the Cloudflare Web Analytics beacon on every page.

Usage:  python _seo/add_analytics.py <site-token>
        python _seo/add_analytics.py --remove

Where the token comes from:
  Cloudflare dashboard -> Web Analytics -> Add a site -> aquamain.com
  -> copy the value of data-cf-beacon's "token" field (a 32-char hex string).

The token is NOT a secret. It ships in the page HTML and is visible to anyone
viewing source; it only identifies which property the pageview belongs to.

Why Cloudflare Web Analytics: it sets no cookies and stores no personal data,
so under UK PECR it needs no consent banner - which matters because the
Complianz banner went with WordPress and has not been replaced.

Idempotent: re-running with the same token changes nothing.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = "<!-- analytics -->"
BEACON = ('{mark}\n<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
          'data-cf-beacon=\'{{"token": "{token}"}}\'></script>\n')
PATTERN = re.compile(
    re.escape(MARK) + r"\s*\n<script defer src=\"https://static\.cloudflareinsights\.com/"
    r"beacon\.min\.js\"[^>]*></script>\n")


def pages():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {".git", "_seo", "worker", "assets"}]
        for fn in sorted(filenames):
            if not fn.endswith(".html"):
                continue
            path = os.path.join(dirpath, fn)
            html = open(path, encoding="utf-8").read()
            if 'http-equiv="refresh"' in html:
                continue
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            if rel.startswith("google"):
                continue
            yield rel, path, html


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    arg = sys.argv[1]
    remove = arg == "--remove"

    if not remove and not re.fullmatch(r"[0-9a-f]{32}", arg):
        print(f"ERROR: '{arg}' is not a 32-character hex token.\n"
              "Copy it from Cloudflare -> Web Analytics -> your site -> the\n"
              "data-cf-beacon token value.")
        sys.exit(1)

    changed, skipped = [], []
    for rel, path, html in pages():
        if remove:
            new = PATTERN.sub("", html)
        else:
            block = BEACON.format(mark=MARK, token=arg)
            new = PATTERN.sub("", html)          # drop any previous beacon first
            if "</body>" not in new:
                print(f"ABORT: no </body> in {rel}")
                sys.exit(1)
            new = new.replace("</body>", block + "</body>", 1)

        if new != html:
            open(path, "w", encoding="utf-8", newline="\n").write(new)
            changed.append(rel)
        else:
            skipped.append(rel)

    verb = "removed from" if remove else "added to"
    print(f"Beacon {verb} {len(changed)} page(s)"
          + (f"; {len(skipped)} already correct" if skipped else ""))
    for r in changed:
        print("  " + r)


if __name__ == "__main__":
    main()
