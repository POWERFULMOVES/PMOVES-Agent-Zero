from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(*parts: str) -> str:
    return PROJECT_ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_root_service_worker_prepares_one_bundle_and_caches_runtime_misses() -> None:
    worker = read("webui", "sw.js")

    assert 'event.data?.type !== "preload-ui-bundle"' in worker
    assert "const replyPort = event.ports?.[0];" in worker
    assert 'replyPort?.postMessage({ ok: true, version: activeAssetVersion })' in worker
    assert worker.index("replyPort?.postMessage({ ok: true") < worker.index(
        "event.waitUntil(cachePopulation.promise"
    )
    assert "await cache.put(request, response);" in worker
    assert "activeBundleEntries.get(request.url)" in worker
    assert "responseFromEntry(bundledEntry)" in worker
    assert "const cached = await cache.match(request);" in worker
    assert "const MAX_RUNTIME_CACHEABLE_TRANSFER_BYTES = 256 * 1024;" in worker
    assert "CACHEABLE_FILE_PATTERN" in worker
    assert "cacheRuntimeResponse(" in worker
    assert 'entry[1] === "text"' in worker
    assert "decodeBase64" not in worker
    assert "body.byteLength > MAX_RUNTIME_CACHEABLE_TRANSFER_BYTES" in worker
    assert "cacheMarkerRequest(targetCacheName)" in worker
    assert "cacheBundleRequest(targetCacheName)" in worker
    assert "new Response(JSON.stringify(bundle)" in worker
    assert "const bundle = await response.json();" in worker
    assert "await restorePersistedBundle();" in worker
    assert "return fetchBackendAsset(request, cache);" in worker
    assert "cleanupCaches(activeCacheName)" in worker
    assert "catch(() => fetch(event.request))" in worker
    assert "asset-graph" not in worker
    assert "queueGraphRequest" not in worker
    assert "preloadNetworkFiles" not in worker
    assert "self.clients.get" not in worker
    assert "CompressionStream" not in worker
    assert 'url.pathname.startsWith("/api/")' in worker
    assert 'request.mode === "navigate"' in worker


def test_splash_registers_root_cache_without_frontend_loader_hooks() -> None:
    index = read("webui", "index.html")
    splash = read("webui", "splash.html")
    components = read("webui", "js", "components.js")
    extensions = read("webui", "js", "extensions.js")
    init_fw = read("webui", "js", "initFw.js")

    assert 'fetch("/ui/asset-bundle"' in splash
    assert 'fetch("/ui/asset-bundle"' not in index
    assert 'id="ui-asset-bundle"' not in index
    assert 'navigator.serviceWorker.register(expectedUrl' in splash
    assert 'updateViaCache: "none"' in splash
    assert "preload-ui-bundle" in splash
    assert "new MessageChannel()" in splash
    assert "await sendBundle(worker, bundle, true)" in splash
    assert "webuiComponentCache" not in components
    assert "preload-ui-bundle" not in components
    assert "preload-ui-bundle" not in extensions
    assert "preload-ui-bundle" not in init_fw
