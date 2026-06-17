// Auto-detect API URL: localhost in dev, Railway in production.
// Set window.ANCHOR_API_URL before any src/ scripts load.
(function () {
  var h = window.location.hostname;
  var local = h === 'localhost' || h === '127.0.0.1';
  window.ANCHOR_API_URL = local
    ? 'http://localhost:8000'
    : 'https://REPLACE_WITH_RAILWAY_API_URL';
  // Alias used by chat-pro.jsx and screens.jsx
  window.ANCHOR_AI_URL = window.ANCHOR_API_URL;
})();
