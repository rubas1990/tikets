self.addEventListener('install', e => {
    console.log('[PWA] Instalando service worker...');
    e.waitUntil(
        caches.open('v1').then(cache => {
            return cache.addAll(['/']); // solo cachea la raíz
        })
    );
});

self.addEventListener('fetch', e => {
    e.respondWith(fetch(e.request)); // sin caché agresivo
});
