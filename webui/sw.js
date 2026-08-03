const CACHE_PREFIX = "agent-zero-ui-assets-";
const SCRIPT_VERSION = new URL(self.location.href).searchParams.get("version") || "runtime";
const MAX_RUNTIME_CACHEABLE_TRANSFER_BYTES = 256 * 1024;
const CACHEABLE_FILE_PATTERN = /\.(?:css|html?|xhtml|m?js)$/i;

let activeCacheName = cacheName(SCRIPT_VERSION);
let activeAssetVersion = SCRIPT_VERSION;
let activeBundleEntries = new Map();
let cachePopulation = { name: "", promise: Promise.resolve() };
let persistedBundleRestore = null;

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    Promise.all([
      cleanupCaches(activeCacheName),
      self.clients.claim(),
    ]),
  );
});

self.addEventListener("message", (event) => {
  if (event.data?.type !== "preload-ui-bundle") return;
  const bundle = event.data.bundle;
  const replyPort = event.ports?.[0];
  if (!bundle?.version || !bundle.files || typeof bundle.files !== "object") {
    replyPort?.postMessage({ ok: false, error: "invalid-bundle" });
    return;
  }

  activeAssetVersion = bundle.version;
  activeCacheName = cacheName(activeAssetVersion);
  activeBundleEntries = bundleEntries(bundle.files);
  persistedBundleRestore = null;

  if (cachePopulation.name !== activeCacheName) {
    const targetCacheName = activeCacheName;
    const promise = preloadBundle(bundle, targetCacheName).catch((error) => {
      if (cachePopulation.promise === promise) {
        cachePopulation = { name: "", promise: Promise.resolve() };
      }
      throw error;
    });
    cachePopulation = { name: targetCacheName, promise };
  }

  // The in-memory map is immediately usable by fetch events. Persist it in the
  // background while the message lifetime keeps this worker alive, so the app
  // does not wait for hundreds of Cache Storage writes before it can render.
  replyPort?.postMessage({ ok: true, version: activeAssetVersion });
  event.waitUntil(cachePopulation.promise.catch(() => undefined));
});

self.addEventListener("fetch", (event) => {
  if (!isCacheableRequest(event.request)) return;
  event.respondWith(
    respondToCacheableRequest(event.request).catch(() => fetch(event.request)),
  );
});

async function respondToCacheableRequest(request) {
  let bundledEntry = activeBundleEntries.get(request.url);
  if (!bundledEntry && activeBundleEntries.size === 0) {
    await restorePersistedBundle();
    bundledEntry = activeBundleEntries.get(request.url);
  }
  if (bundledEntry) return responseFromEntry(bundledEntry);

  let cache;
  try {
    cache = await caches.open(activeCacheName);
    const cached = await cache.match(request);
    if (cached) return cached;
  } catch (_error) {
    return fetch(request);
  }

  return fetchBackendAsset(request, cache);
}

async function fetchBackendAsset(request, cache) {
  const networkResponse = await fetch(request);
  if (isCacheableResponse(networkResponse)) {
    try {
      await cacheRuntimeResponse(cache, request, networkResponse.clone());
    } catch (_error) {
      // A cache failure must never hide a successful backend response.
    }
  }
  return networkResponse;
}

function cacheName(version) {
  const safeVersion = String(version).replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 64);
  return `${CACHE_PREFIX}${safeVersion || "runtime"}`;
}

async function preloadBundle(bundle, targetCacheName) {
  await cleanupCaches(targetCacheName);
  const cache = await caches.open(targetCacheName);
  const marker = cacheMarkerRequest(targetCacheName);
  const payloadRequest = cacheBundleRequest(targetCacheName);
  if ((await cache.match(marker)) && (await cache.match(payloadRequest))) return;

  await cache.put(
    payloadRequest,
    new Response(JSON.stringify(bundle), {
      headers: { "Content-Type": "application/json; charset=utf-8" },
    }),
  );
  await cache.put(marker, new Response(bundle.version));
}

async function restorePersistedBundle() {
  if (activeBundleEntries.size > 0) return;
  if (!persistedBundleRestore) {
    const expectedVersion = activeAssetVersion;
    const expectedCacheName = activeCacheName;
    persistedBundleRestore = (async () => {
      const cache = await caches.open(expectedCacheName);
      const response = await cache.match(cacheBundleRequest(expectedCacheName));
      if (!response) return;
      const bundle = await response.json();
      if (
        bundle?.version !== expectedVersion ||
        expectedVersion !== activeAssetVersion ||
        !bundle.files ||
        typeof bundle.files !== "object"
      ) {
        return;
      }
      activeBundleEntries = bundleEntries(bundle.files);
    })().catch(() => undefined);
  }
  await persistedBundleRestore;
}

async function cleanupCaches(targetCacheName) {
  const names = await caches.keys();
  await Promise.all(
    names
      .filter((name) => name.startsWith(CACHE_PREFIX) && name !== targetCacheName)
      .map((name) => caches.delete(name)),
  );
}

function bundleEntries(files) {
  const entries = new Map();
  for (const [url, entry] of Object.entries(files)) {
    try {
      const absoluteUrl = new URL(url, self.location.origin);
      if (absoluteUrl.origin === self.location.origin && isBundleEntry(entry)) {
        entries.set(absoluteUrl.href, entry);
      }
    } catch (_error) {
      continue;
    }
  }
  return entries;
}

function isBundleEntry(entry) {
  return (
    Array.isArray(entry) &&
    entry.length === 3 &&
    entry[1] === "text" &&
    typeof entry[2] === "string"
  );
}

function responseFromEntry(entry) {
  if (!isBundleEntry(entry)) return null;
  const [contentType, _encoding, content] = entry;
  return new Response(content, {
    headers: {
      "Content-Type": contentType || "application/octet-stream",
      "X-Agent-Zero-Cache": "preloaded",
    },
  });
}

function cacheMarkerRequest(targetCacheName) {
  return new Request(
    new URL(`/.agent-zero-cache/${encodeURIComponent(targetCacheName)}`, self.location.origin),
  );
}

function cacheBundleRequest(targetCacheName) {
  return new Request(
    new URL(
      `/.agent-zero-cache/${encodeURIComponent(targetCacheName)}/bundle`,
      self.location.origin,
    ),
  );
}

function isCacheableRequest(request) {
  if (request.method !== "GET" || request.headers.has("range")) return false;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || request.mode === "navigate") return false;
  if (
    url.pathname === "/" ||
    url.pathname === "/login" ||
    url.pathname === "/logout" ||
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/ws") ||
    url.pathname.startsWith("/socket.io/") ||
    url.pathname.startsWith("/mcp/") ||
    url.pathname.startsWith("/a2a/")
  ) {
    return false;
  }
  return CACHEABLE_FILE_PATTERN.test(url.pathname);
}

function isCacheableResponse(response) {
  return response.ok && (response.type === "basic" || response.type === "default");
}

async function cacheRuntimeResponse(cache, request, response) {
  const contentLength = response.headers.get("content-length");
  if (contentLength !== null) {
    const size = Number(contentLength);
    if (!Number.isFinite(size) || size > MAX_RUNTIME_CACHEABLE_TRANSFER_BYTES) return;
  } else {
    const body = await response.clone().arrayBuffer();
    if (body.byteLength > MAX_RUNTIME_CACHEABLE_TRANSFER_BYTES) return;
  }
  await cache.put(request, response);
}
