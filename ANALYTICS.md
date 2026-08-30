# Website analytics

The GitHub Pages documentation site loads Cloudflare Web Analytics from `docs/analytics.js` only when `docs/analytics-config.js` contains a beacon token and the visitor is on `vinodspattar.in`.

Set the public browser beacon token in `docs/analytics-config.js`; leave it blank to disable tracking. The loader records Cloudflare's standard page views only, adds no user identifiers or custom event data, and does not load during local development. After deployment, confirm page views in the Cloudflare Web Analytics dashboard.
