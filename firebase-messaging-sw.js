// Service worker for FCM background push notifications.
// Must be served from the root of the web server (same origin as the app).
// Config is loaded from firebase-sw-env.js (gitignored; copy firebase-sw-env.example.js → firebase-sw-env.js).

importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js');
importScripts('/firebase-sw-env.js');

firebase.initializeApp(FIREBASE_SW_CONFIG);

const messaging = firebase.messaging();

messaging.onBackgroundMessage(function(payload) {
  const { title, body } = payload.notification || {};
  const data = payload.data || {};
  self.registration.showNotification(title || 'Anchor Alert', {
    body: body || 'Someone nearby needs help.',
    data: { url: data.deep_link || '/', event_id: data.event_id },
    tag: 'anchor-alert-' + (data.event_id || 'general'),
    renotify: true,
  });
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(clients.openWindow(url));
});
