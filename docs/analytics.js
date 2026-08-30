(function () {
  "use strict";

  const config = window.SITE_ANALYTICS;
  if (!config?.token || !config.productionHosts?.includes(window.location.hostname)) return;

  const beacon = document.createElement("script");
  beacon.src = "https://static.cloudflareinsights.com/beacon.min.js";
  beacon.dataset.cfBeacon = JSON.stringify({ token: config.token });
  beacon.defer = true;
  document.head.appendChild(beacon);
})();
