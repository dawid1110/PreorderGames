'use strict';
// Backward compatibility: existing bookmarks with query/hash still open the SPA.
const params = new URLSearchParams(location.search);
if (params.get('demo') === '1' || params.get('register') === '1' || ['#dashboard','#preorders','#calendar','#budget','#collection','#settings'].includes(location.hash)) {
  location.replace('./v3/index.html' + location.search + location.hash);
}
