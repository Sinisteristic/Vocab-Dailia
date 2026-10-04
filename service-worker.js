const CACHE_NAME = "vocab-dailia-v2"; // เปลี่ยนเลขทุกครั้งที่แก้ index.html/style.css/app.js เพื่อบังคับให้ผู้ใช้ได้ของใหม่
const APP_SHELL = ["./", "./index.html", "./style.css", "./app.js", "./manifest.json"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = event.request.url;
  const isGithubData = url.includes("raw.githubusercontent.com");
  if (isGithubData) {
    // ข้อมูลคำศัพท์: network-first (อยากได้ของใหม่สุดเสมอถ้ามีเน็ต) ถ้าออฟไลน์ค่อย fallback cache
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
  } else {
    // ตัวแอปเอง: cache-first (เปิดไวและใช้ออฟไลน์ได้)
    event.respondWith(caches.match(event.request).then((cached) => cached || fetch(event.request)));
  }
});
