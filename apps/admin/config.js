// Auto-detect API URL: localhost in dev, Railway in production.
(function () {
  var h = window.location.hostname;
  var local = h === 'localhost' || h === '127.0.0.1';
  window.ANCHOR_API_URL = local
    ? 'http://localhost:8000'
    : 'https://project-anchor-production-e5ae.up.railway.app';
})();
