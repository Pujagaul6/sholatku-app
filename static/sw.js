const CACHE_VERSION = 'sholatku-v4';
const CACHE_STATIC = `${CACHE_VERSION}-static`;
const CACHE_DYNAMIC = `${CACHE_VERSION}-dynamic`;
const CACHE_API = `${CACHE_VERSION}-api`;
const CACHE_IMAGES = `${CACHE_VERSION}-images`;

// App Shell — files to cache on install
const APP_SHELL = [
    '/',
    '/manifest.json',
    '/static/icon-192.png',
    '/static/icon-512.png',
];

// Max cache items
const MAX_DYNAMIC_ITEMS = 100;
const MAX_IMAGE_ITEMS = 50;
const MAX_API_ITEMS = 30;

// ─── INSTALL ──────────────────────────────────────────────────
self.addEventListener('install', event => {
    console.log('[SW] Installing v4...');
    event.waitUntil(
        caches.open(CACHE_STATIC)
            .then(cache => {
                console.log('[SW] Caching app shell');
                return cache.addAll(APP_SHELL);
            })
            .then(() => self.skipWaiting())
    );
});

// ─── ACTIVATE ─────────────────────────────────────────────────
self.addEventListener('activate', event => {
    console.log('[SW] Activating v4...');
    event.waitUntil(
        caches.keys()
            .then(keys => {
                return Promise.all(
                    keys
                        .filter(key => key.startsWith('sholatku-') && !key.startsWith(CACHE_VERSION))
                        .map(key => {
                            console.log('[SW] Deleting old cache:', key);
                            return caches.delete(key);
                        })
                );
            })
            .then(() => self.clients.claim())
    );
});

// ─── FETCH STRATEGIES ─────────────────────────────────────────
self.addEventListener('fetch', event => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') return;

    // Skip chrome-extension and other non-http
    if (!url.protocol.startsWith('http')) return;

    // Strategy 1: App Shell — Cache First
    if (isAppShell(url)) {
        event.respondWith(cacheFirst(request, CACHE_STATIC));
        return;
    }

    // Strategy 2: API calls — Network First with cache fallback
    if (isApiRoute(url)) {
        event.respondWith(networkFirst(request, CACHE_API));
        return;
    }

    // Strategy 3: Images — Cache First
    if (isImage(request)) {
        event.respondWith(cacheFirst(request, CACHE_IMAGES));
        return;
    }

    // Strategy 4: Fonts — Cache First
    if (isFont(url)) {
        event.respondWith(cacheFirst(request, CACHE_STATIC));
        return;
    }

    // Strategy 5: External CDN — Stale While Revalidate
    if (isExternalCDN(url)) {
        event.respondWith(staleWhileRevalidate(request, CACHE_STATIC));
        return;
    }

    // Strategy 6: HTML pages — Network First (cache the main page)
    if (isHTML(request)) {
        event.respondWith(networkFirstWithCache(request, CACHE_DYNAMIC));
        return;
    }

    // Default: Network First
    event.respondWith(networkFirst(request, CACHE_DYNAMIC));
});

// ─── CACHE STRATEGIES ─────────────────────────────────────────

// Cache First — for static assets
async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request);
    if (cached) {
        return cached;
    }
    try {
        const response = await fetch(request);
        if (response && response.status === 200) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
            await limitCacheSize(cacheName, MAX_DYNAMIC_ITEMS);
        }
        return response;
    } catch (error) {
        // Return offline fallback for HTML
        if (request.headers.get('accept')?.includes('text/html')) {
            return caches.match('/');
        }
        return new Response('Offline', { status: 503 });
    }
}

// Network First — for API and dynamic content
async function networkFirst(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response && response.status === 200) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
            await limitCacheSize(cacheName, MAX_API_ITEMS);
        }
        return response;
    } catch (error) {
        const cached = await caches.match(request);
        if (cached) {
            return cached;
        }
        // Return offline fallback for HTML
        if (request.headers.get('accept')?.includes('text/html')) {
            return caches.match('/');
        }
        return new Response(JSON.stringify({ error: 'Offline' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

// Network First with Cache — for HTML pages (always cache the response)
async function networkFirstWithCache(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response && response.status === 200) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch (error) {
        const cached = await caches.match(request);
        if (cached) {
            return cached;
        }
        // Return the main page as fallback
        return caches.match('/');
    }
}

// Stale While Revalidate — for CDN resources
async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);
    
    const fetchPromise = fetch(request).then(response => {
        if (response && response.status === 200) {
            cache.put(request, response.clone());
        }
        return response;
    }).catch(() => cached);

    return cached || fetchPromise;
}

// ─── HELPER FUNCTIONS ─────────────────────────────────────────

function isAppShell(url) {
    return APP_SHELL.some(path => url.pathname === path) ||
           url.pathname === '/' ||
           url.pathname === '/manifest.json' ||
           url.pathname.startsWith('/static/icon-');
}

function isApiRoute(url) {
    return url.pathname.startsWith('/api/');
}

function isImage(request) {
    const destination = request.destination;
    return destination === 'image' ||
           /\.(jpg|jpeg|png|gif|webp|svg|ico)$/i.test(request.url);
}

function isFont(url) {
    return url.hostname === 'fonts.gstatic.com' ||
           /\.(woff|woff2|ttf|eot)$/i.test(url.pathname);
}

function isExternalCDN(url) {
    return url.hostname === 'cdn.tailwindcss.com' ||
           url.hostname === 'fonts.googleapis.com';
}

function isHTML(request) {
    return request.headers.get('accept')?.includes('text/html');
}

// Limit cache size
async function limitCacheSize(cacheName, maxItems) {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    if (keys.length > maxItems) {
        await cache.delete(keys[0]);
        await limitCacheSize(cacheName, maxItems);
    }
}

// ─── BACKGROUND SYNC ──────────────────────────────────────────
self.addEventListener('sync', event => {
    if (event.tag === 'sync-reviews') {
        event.waitUntil(syncReviews());
    }
    if (event.tag === 'sync-events') {
        event.waitUntil(syncEvents());
    }
});

async function syncReviews() {
    // Sync pending reviews when back online
    const cache = await caches.open('pending-reviews');
    const requests = await cache.keys();
    
    for (const request of requests) {
        try {
            const response = await cache.match(request);
            const data = await response.json();
            await fetch('/api/reviews', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            await cache.delete(request);
        } catch (error) {
            console.log('[SW] Sync review failed:', error);
        }
    }
}

async function syncEvents() {
    // Sync pending events when back online
    const cache = await caches.open('pending-events');
    const requests = await cache.keys();
    
    for (const request of requests) {
        try {
            const response = await cache.match(request);
            const data = await response.json();
            await fetch('/api/suggest-event', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            await cache.delete(request);
        } catch (error) {
            console.log('[SW] Sync event failed:', error);
        }
    }
}

// ─── PUSH NOTIFICATIONS ───────────────────────────────────────
self.addEventListener('push', event => {
    const data = event.data?.json() || {};
    const options = {
        body: data.body || 'Waktu shalat telah tiba',
        icon: '/static/icon-192.png',
        badge: '/static/icon-192.png',
        vibrate: [200, 100, 200],
        data: { url: data.url || '/' },
        actions: [
            { action: 'open', title: 'Buka' },
            { action: 'close', title: 'Tutup' }
        ]
    };
    
    event.waitUntil(
        self.registration.showNotification(data.title || 'SholatKu', options)
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    
    if (event.action === 'close') return;
    
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then(clientList => {
                if (clientList.length > 0) {
                    return clientList[0].focus();
                }
                return clients.openWindow(event.notification.data.url);
            })
    );
});

// ─── PERIODIC SYNC (for prayer times) ─────────────────────────
self.addEventListener('periodicsync', event => {
    if (event.tag === 'update-prayer-times') {
        event.waitUntil(updatePrayerTimes());
    }
});

async function updatePrayerTimes() {
    try {
        const response = await fetch('/api/prayer-times');
        if (response.ok) {
            const cache = await caches.open(CACHE_API);
            cache.put('/api/prayer-times', response);
        }
    } catch (error) {
        console.log('[SW] Periodic sync failed:', error);
    }
}

console.log('[SW] Service Worker v4 loaded');
