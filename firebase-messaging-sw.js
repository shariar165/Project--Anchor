// Service worker for FCM background push notifications.
// Must be served from the root of the web server (same origin as the app).
// FILL IN: Replace placeholder values with your actual Firebase project config.
// Get them from: Firebase Console → Project Settings → Your Apps → Web app

importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.12.2/firebase-messaging-compat.js');

firebase.initializeApp({
  apiKey: "AIzaSyBqQtlcZ536HFiNVEFGuURfeeQa37UtVeM",
  authDomain: "project-anchor-76170.firebaseapp.com",
  projectId: "project-anchor-76170",
  storageBucket: "project-anchor-76170.firebasestorage.app",
  messagingSenderId: "915588225145",
  appId: "1:915588225145:web:1a7bb87daa31a1c4fb5ca8",
});

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
