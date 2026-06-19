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
    data: { event_id: data.event_id, lat: data.lat, lng: data.lng },
    tag: 'anchor-alert-' + (data.event_id || 'general'),
    renotify: true,
  });
});

// Build a same-origin web URL for the click. We deliberately ignore any
// `anchor://` deep link from the payload — this is a web app, so a custom URL
// scheme just opens a blank page. The event id + location are carried as query
// params that app.jsx reads on load.
function alertUrl(d) {
  const u = new URL('/', self.location.origin);
  if (d.event_id) u.searchParams.set('alert', d.event_id);
  if (d.lat) u.searchParams.set('lat', d.lat);
  if (d.lng) u.searchParams.set('lng', d.lng);
  return u.href;
}

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const d = event.notification.data || {};
  const url = alertUrl(d);
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (wins) {
      // Reuse an already-open app tab instead of opening a blank duplicate.
      for (const client of wins) {
        if (client.url.indexOf(self.location.origin) === 0 && 'focus' in client) {
          client.focus();
          client.postMessage({ type: 'anchor-open-alert', eventId: d.event_id || null, lat: d.lat, lng: d.lng });
          return;
        }
      }
      return clients.openWindow(url);
    })
  );
});
