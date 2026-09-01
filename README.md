# Aquamain website — GitHub Pages

Static site for **aquamain.com**, migrated from WordPress (June 2026 redesign). 16 pages, all self-contained HTML — no build step, no CMS. Edit the HTML, commit, push: the live site updates in about a minute.

## Structure

- `index.html` — home page. Every other page lives at `<slug>/index.html` so URLs keep their WordPress form (`/about-us/`, `/privacy-policy/`, …).
- `assets/uploads/` — all images (downloaded from the old WordPress media library).
- `assets/favicon/` — favicons.
- `electricity-networks/`, `water-networks/`, `aquamain/` — redirect stubs for retired WordPress URLs (meta-refresh, since GitHub Pages can't do server-side 301s).
- `CNAME` — tells GitHub Pages the custom domain. Don't delete.
- `worker/` — the Cloudflare Worker that handles form submissions. Not part of the published site.
- `sitemap.xml`, `robots.txt`, `404.html` — standard.

## One-time go-live steps

### 1. Create the GitHub repo and push

1. Create a GitHub account (or org), then a **public** repo, e.g. `aquamain-website`.
2. From this folder:
   ```
   git remote add origin https://github.com/<YOUR-USER>/aquamain-website.git
   git push -u origin main
   ```

### 2. Enable GitHub Pages

Repo → **Settings → Pages** → Source: **Deploy from a branch** → Branch `main`, folder `/ (root)` → Save.
Then in **Custom domain** enter `aquamain.com` and save. Tick **Enforce HTTPS** once it becomes available (after DNS, below — the certificate can take up to ~24h).

### 3. Forms (Cloudflare Worker + Resend)

The contact and careers forms post to a small Cloudflare Worker, which sends the mail
via Resend. Free on both services. Full setup steps are in **`worker/README.md`** —
in short: create the Resend account, verify the `send.aquamain.com` subdomain, deploy
the Worker, then paste its URL into `contact/index.html` line 20.

Enquiries go to info@ **and** sales@; CV submissions go to info@ with the file attached —
matching what the old WordPress handler did.

### 4. DNS (at Heart Internet — nameservers ns.mainnameserver.com)

⚠️ **Only change the records below. Do NOT touch MX or any autodiscover/verification records — those run company email (Microsoft 365).**

| Type | Host | Value |
|---|---|---|
| A | `@` (aquamain.com) | `185.199.108.153` |
| A | `@` | `185.199.109.153` |
| A | `@` | `185.199.110.153` |
| A | `@` | `185.199.111.153` |
| CNAME | `www` | `<YOUR-USER>.github.io.` |

Delete/replace only the old A record pointing at `149.255.62.174` (the old web host) and any old `www` record. DNS can take up to 24–48h to propagate (usually under an hour).

### 5. After go-live

- In GitHub Pages settings, confirm the custom domain shows a green tick, then **Enforce HTTPS**.
- Google Search Console: add/verify the property (DNS TXT record is easiest), submit `https://aquamain.com/sitemap.xml`.
- Keep the WordPress hosting live until you've confirmed the new site is serving (check with `nslookup aquamain.com` → should return the 185.199.x IPs). Then the WordPress hosting can be cancelled — but **not the domain registration or DNS service**.

## What changed vs WordPress

- Forms now go through a **Cloudflare Worker + Resend** (`worker/`) instead of the PHP admin-ajax handler (`aquamain-contact-handler`). Same behaviour: info@ + sales@ for enquiries, CV attached for careers.
- All images are served locally from `assets/uploads/` instead of `wp-content/uploads`.
- 301 redirects (SEOPress/Code Snippets) replaced by meta-refresh stub pages.
- Cookie consent: the Complianz banner is gone. The site now sets no cookies itself; the only third-party embed is the SociableKit LinkedIn feed on the home page. Review the Cookie Policy page text against reality when convenient.
- SEO titles/meta descriptions copied verbatim from the live SEOPress values (Aug 2026).

## Editing pages

Each page is one self-contained HTML file (inline CSS, shared header/footer markup duplicated per page — a change to the nav/footer must be applied to all 16 files). Preview locally with:

```
python -m http.server 8000
```

then open <http://localhost:8000>.
