/**
 * Aquamain website form handler — Cloudflare Worker.
 *
 * Replaces the old WordPress admin-ajax handler (aquamain-contact-handler.php).
 * Accepts multipart/form-data from the contact page, sends email via Resend.
 *
 *   form_type=enquiry  -> info@ + sales@
 *   form_type=career   -> info@, with the CV attached
 *
 * Secrets (set with `npx wrangler secret put <NAME>`, never committed):
 *   RESEND_API_KEY
 */

const ALLOWED_ORIGINS = [
  'https://aquamain.com',
  'https://www.aquamain.com',
  'https://aqmwebsite.github.io',
  'http://localhost:8765',
];

const FROM = 'Aquamain website <website@send.aquamain.com>';
const TO_ENQUIRY = ['info@aquamain.com', 'sales@aquamain.com'];
const TO_CAREER = ['info@aquamain.com'];

const MAX_CV_BYTES = 10 * 1024 * 1024; // 10MB, matches the "up to 10MB" hint on the form
const ALLOWED_CV_TYPES = ['.pdf', '.doc', '.docx'];

function corsHeaders(origin) {
  const allow = ALLOWED_ORIGINS.includes(origin) ? origin : ALLOWED_ORIGINS[0];
  return {
    'Access-Control-Allow-Origin': allow,
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
    Vary: 'Origin',
  };
}

function json(body, status, origin) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...corsHeaders(origin) },
  });
}

const esc = (s) =>
  String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

/** Build a simple definition-list email body from label/value pairs. */
function buildHtml(heading, rows) {
  const body = rows
    .filter(([, v]) => v !== '' && v != null)
    .map(
      ([k, v]) =>
        `<tr><td style="padding:6px 14px 6px 0;vertical-align:top;color:#64748b;font:600 13px/1.5 system-ui,sans-serif;white-space:nowrap">${esc(
          k
        )}</td><td style="padding:6px 0;vertical-align:top;color:#0f172a;font:400 14px/1.6 system-ui,sans-serif;white-space:pre-wrap">${esc(
          v
        )}</td></tr>`
    )
    .join('');
  return `<div style="max-width:600px;margin:0 auto;padding:24px"><h2 style="font:700 18px/1.3 system-ui,sans-serif;color:#0f172a;margin:0 0 16px">${esc(
    heading
  )}</h2><table style="border-collapse:collapse;width:100%">${body}</table><p style="margin:20px 0 0;font:400 12px/1.5 system-ui,sans-serif;color:#94a3b8">Sent from the form on aquamain.com</p></div>`;
}

/** Plain-text fallback, so the mail isn't HTML-only. */
function buildText(heading, rows) {
  return (
    heading +
    '\n\n' +
    rows
      .filter(([, v]) => v !== '' && v != null)
      .map(([k, v]) => `${k}: ${v}`)
      .join('\n') +
    '\n\nSent from the form on aquamain.com'
  );
}

async function sendViaResend(apiKey, payload) {
  const r = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => '');
    throw new Error(`Resend ${r.status}: ${detail.slice(0, 300)}`);
  }
  return r.json();
}

/** Base64 without blowing the stack on a multi-MB file. */
function toBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get('Origin') || '';

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }
    if (request.method !== 'POST') {
      return json({ success: false, message: 'Method not allowed.' }, 405, origin);
    }
    if (origin && !ALLOWED_ORIGINS.includes(origin)) {
      return json({ success: false, message: 'Origin not allowed.' }, 403, origin);
    }

    let form;
    try {
      form = await request.formData();
    } catch {
      return json({ success: false, message: 'Could not read the form.' }, 400, origin);
    }

    // Honeypot: real people never tick a field that is off-screen and hidden.
    // Return success so bots see no signal worth adapting to.
    if (form.get('botcheck')) {
      return json({ success: true }, 200, origin);
    }

    const get = (k) => (form.get(k) || '').toString().trim();
    const type = get('form_type') === 'career' ? 'career' : 'enquiry';

    const firstName = get('first_name');
    const lastName = get('last_name');
    const email = get('email');

    if (!firstName || !lastName || !email) {
      return json({ success: false, message: 'Please fill in your name and email.' }, 400, origin);
    }
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
      return json({ success: false, message: 'That email address does not look valid.' }, 400, origin);
    }
    if (!form.get('consent')) {
      return json({ success: false, message: 'Please tick the consent box.' }, 400, origin);
    }

    const name = `${firstName} ${lastName}`;
    const attachments = [];
    let heading, subject, to, rows;

    if (type === 'career') {
      const cv = form.get('cv');
      if (!cv || typeof cv === 'string' || cv.size === 0) {
        return json({ success: false, message: 'Please attach your CV.' }, 400, origin);
      }
      const ext = ('.' + (cv.name.split('.').pop() || '')).toLowerCase();
      if (!ALLOWED_CV_TYPES.includes(ext)) {
        return json({ success: false, message: 'CV must be a PDF or Word document.' }, 400, origin);
      }
      if (cv.size > MAX_CV_BYTES) {
        return json({ success: false, message: 'That file is larger than 10MB.' }, 400, origin);
      }
      attachments.push({
        filename: `${name.replace(/[^\w\s-]/g, '')} CV${ext}`,
        content: toBase64(await cv.arrayBuffer()),
      });

      to = TO_CAREER;
      heading = 'CV submission';
      subject = `CV submission — ${name}`;
      rows = [
        ['Name', name],
        ['Email', email],
        ['Phone', get('phone')],
        ['Role / expertise', get('role')],
        ['Message', get('message')],
        ['CV', `${cv.name} (${Math.round(cv.size / 1024)} KB, attached)`],
      ];
    } else {
      to = TO_ENQUIRY;
      heading = 'Website enquiry';
      subject = `Website enquiry — ${name}${get('company') ? ' (' + get('company') + ')' : ''}`;
      rows = [
        ['Name', name],
        ['Email', email],
        ['Company', get('company')],
        ['Service', get('service')],
        ['Message', get('message')],
      ];
    }

    try {
      await sendViaResend(env.RESEND_API_KEY, {
        from: FROM,
        to,
        reply_to: email,
        subject,
        html: buildHtml(heading, rows),
        text: buildText(heading, rows),
        ...(attachments.length ? { attachments } : {}),
      });
    } catch (err) {
      console.error('send failed', err.message);
      return json(
        { success: false, message: 'We could not send your message. Please email info@aquamain.com.' },
        502,
        origin
      );
    }

    return json({ success: true }, 200, origin);
  },
};
