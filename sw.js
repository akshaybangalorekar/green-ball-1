/* East Malvern — Green Ball 1
   Service worker: offline shell, update checks, notifications. */

const SHELL = "gb1-shell-v2";
const META = "gb1-meta-v2";
const SHELL_FILES = ["./", "./index.html", "./manifest.webmanifest", "./icon-192.png", "./icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;

  // Data must be fresh whenever we are online.
  if (url.pathname.endsWith("data.json")) {
    e.respondWith(
      fetch(e.request, { cache: "no-store" }).catch(() => caches.match(e.request))
    );
    return;
  }

  // App shell: network first, cached copy when offline.
  if (e.request.mode === "navigate") {
    e.respondWith(fetch(e.request).catch(() => caches.match("./index.html")));
    return;
  }
});

/* ---------- update detection ---------- */
function signature(d) {
  const draw = (d.draw || []).map((x) => x.opponent || "-").join(",");
  return [d.meta.ladder_loaded, d.results.length, draw].join("|");
}

function describeChanges(prev, next) {
  const bits = [];
  if (!prev) return "Updated from TROLS.";
  const [prevLoad, prevRounds] = prev.split("|");
  const [nextLoad, nextRounds] = next.split("|");
  if (prevRounds !== nextRounds) {
    const latest = next.results[0];
    bits.push(latest ? `Round ${latest.round} results are in` : "New results posted");
  }
  if (prevLoad !== nextLoad && !bits.length) bits.push("Ladder updated");
  if (!bits.length) bits.push("Fixture or ladder details changed");
  return bits.join(" · ");
}


/* ---------- Friday match reminder ---------- */
function ymd(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function first(n) { return String(n || "").split(" ")[0]; }

function reminderFor(data) {
  const now = new Date();
  const day = now.getDay(), hr = now.getHours();
  const inWindow = (day === 5 && hr >= 18) || day === 6 || (day === 0 && hr < 18);
  if (!inWindow) return null;

  const today = ymd(now);
  const next = (data.draw || []).filter((x) => x.date >= today)[0];
  if (!next || !next.opponent) return null;

  const days = Math.round((new Date(next.date + "T12:00:00") - new Date(today + "T12:00:00")) / 86400000);
  if (days < 0 || days > 3) return null;

  const rr = (data.roster && data.roster.rounds || []).find((r) => r.round === next.round);
  const trio = rr ? (rr.in || []).map(first).join(", ") : "";
  const atHome = next.homeAway === "H";
  const club = (data.clubs || []).find((c) => c.name === (atHome ? data.meta.club : next.opponent));
  const place = club ? String(club.venue).replace(/\s*Club House.*$/i, "").replace(/\s*Ph\s*:?\s*[\d\s]+$/i, "").trim() : "";

  return {
    round: next.round,
    title: `Sunday: ${atHome ? "v" : "at"} ${next.opponent}`,
    body: [place, trio].filter(Boolean).join(" · "),
  };
}

async function maybeRemind(data) {
  const msg = reminderFor(data);
  if (!msg) return;
  const cache = await caches.open(META);
  const key = "reminded-" + msg.round;
  if (await cache.match(key)) return;
  await self.registration.showNotification(msg.title, {
    body: msg.body,
    icon: "./icon-192.png",
    badge: "./icon-192.png",
    tag: "gb1-match-" + msg.round,
    data: { url: "./#week" },
  });
  await cache.put(key, new Response("1"));
}

async function checkForUpdates() {
  let data;
  try {
    const res = await fetch("./data.json?sw=" + Date.now(), { cache: "no-store" });
    if (!res.ok) return;
    data = await res.json();
  } catch (e) {
    return;
  }
  const sig = signature(data);
  const cache = await caches.open(META);
  const prevRes = await cache.match("sig");
  const prev = prevRes ? await prevRes.text() : null;

  if (prev && prev !== sig) {
    const body = describeChanges(prev, data);
    await self.registration.showNotification("Advantage", {
      body,
      icon: "./icon-192.png",
      badge: "./icon-192.png",
      tag: "gb1-update",
      renotify: true,
      data: { url: "./#season" },
    });
  }
  await cache.put("sig", new Response(sig));
  await cache.put("last-check", new Response(new Date().toISOString()));
  await maybeRemind(data);
}

self.addEventListener("periodicsync", (e) => {
  if (e.tag === "check-updates") e.waitUntil(checkForUpdates());
});

self.addEventListener("sync", (e) => {
  if (e.tag === "check-updates") e.waitUntil(checkForUpdates());
});

self.addEventListener("message", (e) => {
  if (e.data && e.data.type === "check") e.waitUntil(checkForUpdates());
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const target = (e.notification.data && e.notification.data.url) || "./";
  e.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const c of list) {
        if ("focus" in c) return c.focus();
      }
      return self.clients.openWindow(target);
    })
  );
});
