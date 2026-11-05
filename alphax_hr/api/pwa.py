"""Installable app (PWA): the service worker is served through the API with the headers it needs."""
import frappe

SW = r"""// AlphaX HR service worker {version}
const CACHE = 'alphax-{version}';
const SHELL = '/alphax/';
self.addEventListener('install', (e) => {{ self.skipWaiting(); }});
// Keep the app shell and its built files so the app opens without a connection.
async function precache() {{
  const c = await caches.open(CACHE);
  const r = await fetch(SHELL, {{ credentials: 'include' }});
  if (!r.ok || r.redirected) return;
  const html = await r.clone().text();
  await c.put(SHELL, r);
  const urls = [...html.matchAll(/(?:src|href)="(\/assets\/alphax_hr\/frontend\/[^"]+)"/g)].map((m) => m[1]);
  await Promise.all(urls.map((u) => fetch(u).then((x) => x.ok && c.put(u, x)).catch(() => null)));
}}
self.addEventListener('activate', (e) => {{
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k.startsWith('alphax-') && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => precache().catch(() => null)).then(() => self.clients.claim()));
}});
// Phone notifications (approvals, decisions, messages, announcements).
self.addEventListener('push', (e) => {{
  let d = {{}};
  try {{ d = e.data ? e.data.json() : {{}}; }} catch (_) {{ d = {{ title: 'AlphaX HR', body: e.data ? e.data.text() : '' }}; }}
  e.waitUntil(self.registration.showNotification(d.title || 'AlphaX HR', {{
    body: d.body || '', tag: d.tag || undefined, data: {{ url: d.url || '/alphax/' }},
    icon: '/assets/alphax_hr/frontend/icons/icon-192.png', badge: '/assets/alphax_hr/frontend/icons/icon-192.png'
  }}));
}});
self.addEventListener('notificationclick', (e) => {{
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || '/alphax/';
  e.waitUntil(self.clients.matchAll({{ type: 'window', includeUncontrolled: true }}).then((list) => {{
    for (const c of list) {{ if (c.url.includes('/alphax') && 'focus' in c) {{ c.navigate(url); return c.focus(); }} }}
    return self.clients.openWindow(url);
  }}));
}});
self.addEventListener('fetch', (e) => {{
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  // Built files have hashed names: cache first.
  if (url.pathname.startsWith('/assets/alphax_hr/frontend/')) {{
    e.respondWith(caches.open(CACHE).then(async (c) => (await c.match(req)) || fetch(req).then((r) => {{ if (r.ok) {{ const copy = r.clone(); c.put(req, copy); }} return r; }})));
    return;
  }}
  // App pages: network first, last good copy when offline. API calls are never cached.
  if (req.mode === 'navigate' && url.pathname.startsWith('/alphax')) {{
    e.respondWith(fetch(req).then((r) => {{ if (r.ok && !r.redirected) {{ const copy = r.clone(); caches.open(CACHE).then((c) => c.put(SHELL, copy)); }} return r; }})
      .catch(() => caches.open(CACHE).then((c) => c.match(SHELL)).then((r) => r || new Response('<h1>Offline</h1><p>Connect to the internet and try again.</p>', {{ headers: {{ 'Content-Type': 'text/html' }} }}))));
  }}
}});
"""


# Public: the service worker script is loaded before sign-in; it contains no data.
@frappe.whitelist(allow_guest=True, methods=["GET"])  # nosemgrep
def service_worker():
	import alphax_hr

	frappe.response.filename = "alphax-sw.js"
	frappe.response.filecontent = SW.format(version=alphax_hr.__version__)
	frappe.response.type = "binary"


def after_request(response=None, request=None):
	"""Turn the service-worker download into a script the browser accepts for the /alphax scope."""
	if request is not None and response is not None and request.path == "/api/method/alphax_hr.api.branding.manifest":
		response.headers.pop("Content-Disposition", None)
		response.mimetype = "application/manifest+json"
		response.headers["Cache-Control"] = "no-cache"
		return
	if request is not None and response is not None and request.path == "/api/method/alphax_hr.api.pwa.service_worker":
		response.headers.pop("Content-Disposition", None)
		response.mimetype = "application/javascript"
		response.headers["Service-Worker-Allowed"] = "/alphax"
		response.headers["Cache-Control"] = "no-cache"
