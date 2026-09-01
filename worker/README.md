# Form handler — Cloudflare Worker

Replaces the old WordPress `admin-ajax` PHP handler. Free on Cloudflare's Workers plan
(100,000 requests/day) and Resend's free tier (3,000 emails/month), which is far beyond
what this site will ever use.

| Form | Goes to | Attachment |
|---|---|---|
| Enquiry (`form_type=enquiry`) | info@ **and** sales@ | — |
| Careers (`form_type=career`) | info@ | CV attached |

`reply_to` is set to the sender, so hitting Reply in Outlook goes straight back to them.

## Setup — one time

### 1. Resend account + sending domain

1. Sign up at <https://resend.com> with **info@aquamain.com**.
2. Add the domain **`send.aquamain.com`** (the subdomain, not the bare domain).
3. Resend shows a few DNS records to add. Send those to IT.

   ⚠️ **These are all on the `send.` subdomain.** They do not alter, replace or
   interfere with the Microsoft 365 mail flow on `aquamain.com` itself. The root
   MX record must not be touched. Using a subdomain is deliberate: it keeps
   website-generated mail entirely separate from company email, so a
   misconfiguration here can never affect staff inboxes.

4. Wait for Resend to show the domain as **Verified**.
5. Create an API key (Full access is fine) and copy it.

### 2. Deploy the Worker

From this `worker/` folder:

```
npx wrangler login
npx wrangler secret put RESEND_API_KEY
npx wrangler deploy
```

`secret put` prompts for the key and stores it encrypted at Cloudflare — it is
never written to this repo.

`deploy` prints the Worker URL, e.g. `https://aquamain-forms.<something>.workers.dev`.

### 3. Point the site at it

Put that URL into `contact/index.html`, line 20, replacing `REPLACE_WITH_WORKER_URL`:

```html
<script>window.FORM_ENDPOINT='https://aquamain-forms.xxxx.workers.dev';</script>
```

Commit and push. Done.

## Testing

Submit both forms for real and confirm the mail arrives — enquiry to info@ *and*
sales@, careers to info@ with the CV attached. Do this once before the DNS switch
and once after.

The honeypot returns success without sending, so a "successful" test that produces
no email means something ticked the hidden `botcheck` field — check you are not
autofilling it.

## Rate limiting

| Guard | Limit | Scope |
|---|---|---|
| `IP_LIMITER` | 3 submissions / 60s | per visitor IP |
| `CV_LIMITER` | 2 CV uploads / 60s | per visitor IP |
| `GLOBAL_LIMITER` | 20 submissions / 60s | everyone (flood backstop) |
| KV daily cap | 10 / day per IP, 200 / day total | protects the Resend monthly quota |
| Body size | 12MB, rejected before parsing | any submission |

Blocked requests get **429** and a message pointing them at info@aquamain.com.

Cloudflare's limiter only accepts a `period` of 10 or 60 seconds, which is why the
daily caps are kept separately in KV. Without them, 3/minute still works out at
over 4,000 emails a day from a single address — enough to exhaust the Resend free
tier in under 24 hours.

Two deliberate choices:

- **Only valid submissions count** toward the daily cap, so a bot spraying malformed
  requests cannot use up a real visitor's allowance.
- **The KV check fails open.** If KV is unavailable the submission goes through, on
  the grounds that losing a genuine enquiry is worse than allowing an extra one —
  the 60-second limiters are still in force regardless.

To change any limit, edit `wrangler.toml` (or the constants at the top of `index.js`
for the daily caps) and redeploy.

## Notes

- `ALLOWED_ORIGINS` in `index.js` restricts who may post. It already lists
  aquamain.com, www, the GitHub Pages preview host, and localhost:8765 for local
  testing. Anything else gets a 403.
- CVs are capped at 10MB and must be `.pdf`, `.doc` or `.docx`.
- If Resend is down or the key is wrong, the Worker returns 502 and the page tells
  the visitor to email info@ directly — it never reports a false success.
- Worker logs: `npx wrangler tail`.
