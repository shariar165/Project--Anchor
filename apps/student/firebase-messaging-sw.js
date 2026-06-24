// Service worker for FCM background push notifications.
// Must be served from the root of the web server (same origin as the app).
// Config is loaded from firebase-sw-env.js (gitignored; copy firebase-sw-env.example.js → firebase-sw-env.js).

importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js');
importScripts('/firebase-sw-env.js');

firebase.initializeApp(FIREBASE_SW_CONFIG);

const messaging = firebase.messaging();

// Build a single rich notification options object, keyed off data.category, so the
// background (here) and foreground (auth.jsx onMessage) renders look identical and
// native — icon, badge, vibration, action buttons. Kept in sync with buildNotification
// in apps/student/src/auth.jsx.
function buildAnchorNotification(payload) {
  const n = payload.notification || {};
  const data = payload.data || {};
  const category = data.category || 'nearby_alert';
  const isEmergency = category === 'nearby_alert' || category === 'campus_alert';

  const title = n.title
    || (category === 'alert_safe' ? 'Anchor: They are safe now' : 'Anchor Alert');
  const body = n.body || 'Someone nearby needs help.';

  const opts = {
    body,
    icon: '/icons/icon-192.png',
    badge: '/icons/badge.png',
    tag: 'anchor-alert-' + (data.event_id || 'general'),
    renotify: true,
    dir: 'auto',
    timestamp: Date.now(),
    requireInteraction: isEmergency,
    vibrate: isEmergency ? [200, 100, 200, 100, 200] : [120],
    data: {
      event_id: data.event_id,
      lat: data.lat,
      lng: data.lng,
      category,
      deep_link: data.deep_link,
    },
  };

  if (category === 'nearby_alert') {
    opts.actions = [
      { action: 'help', title: "I'm coming" },
      { action: 'view', title: 'View map' },
    ];
  }
  return { title, opts };
}

messaging.onBackgroundMessage(function(payload) {
  const { title, opts } = buildAnchorNotification(payload);
  self.registration.showNotification(title, opts);
});

// Build a same-origin web URL for the click. We deliberately ignore any
// `anchor://` deep link from the payload — this is a web app, so a custom URL
// scheme just opens a blank page. The event id + location are carried as query
// params that app.jsx reads on load. When the user taps "I'm coming", carry a
// `respond=1` flag so the app auto-opens the responder sheet.
function alertUrl(d, respond) {
  const u = new URL('/', self.location.origin);
  if (d.event_id) u.searchParams.set('alert', d.event_id);
  if (d.lat) u.searchParams.set('lat', d.lat);
  if (d.lng) u.searchParams.set('lng', d.lng);
  if (respond) u.searchParams.set('respond', '1');
  return u.href;
}

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  const d = event.notification.data || {};
  const respond = event.action === 'help';
  const url = alertUrl(d, respond);
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (wins) {
      // Reuse an already-open app tab instead of opening a blank duplicate.
      for (const client of wins) {
        if (client.url.indexOf(self.location.origin) === 0 && 'focus' in client) {
          client.focus();
          client.postMessage({
            type: 'anchor-open-alert',
            eventId: d.event_id || null,
            lat: d.lat, lng: d.lng,
            respond: respond,
          });
          return;
        }
      }
      return clients.openWindow(url);
    })
  );
});
