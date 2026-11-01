/* Application controller.
 *  - loads server-side history once so charts survive page reloads
 *  - polls /api/v1/snapshot with a single request in flight at a time
 *  - pauses while the tab is hidden, backs off while the server is unreachable */
(function (g) {
  'use strict';
  var F = g.SM.format, S = g.SM.store, C = g.SM.charts, UI = g.SM.ui;

  var SNAPSHOT_URL = '/api/v1/snapshot';
  var HISTORY_URL = '/api/v1/history';
  var REQUEST_TIMEOUT_MS = 8000;
  var MAX_BACKOFF_FACTOR = 5;

  var intervalMs = 3000;      // replaced by the collector's real interval after the first snapshot
  var failures = 0;
  var timer = null;
  var running = false;
  var inflight = false;
  var chartsReady = false;

  function getJSON(url) {
    var ctl = new AbortController();
    var to = setTimeout(function () { ctl.abort(); }, REQUEST_TIMEOUT_MS);
    return fetch(url, { cache: 'no-store', credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: ctl.signal })
      .then(function (r) {
        if (r.status === 401 || r.status === 403) { var e = new Error('auth'); e.code = 'auth'; throw e; }
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .finally(function () { clearTimeout(to); });
  }

  function loadHistory() {
    return getJSON(HISTORY_URL).then(function (h) {
      S.load(h);
      if (chartsReady) C.update();
      UI.setPerfHint();
    }).catch(function () { /* charts simply start empty and fill from live samples */ });
  }

  function schedule(ms) {
    clearTimeout(timer);
    if (running) timer = setTimeout(tick, ms);
  }

  function describeError(e) {
    if (e && e.code === 'auth') return 'Authentication required \u2014 reload the page to sign in again.';
    if (e && e.name === 'AbortError') return 'The server did not answer in time. Retrying\u2026';
    return 'Cannot reach the monitoring server. Retrying\u2026';
  }

  function tick() {
    if (inflight) return;          // never stack requests
    inflight = true;
    getJSON(SNAPSHOT_URL).then(function (s) {
      failures = 0;
      if (!s || s.status === 'starting') {
        UI.setConn('connecting');
        return schedule(1000);
      }
      if (F.isNum(s.interval) && s.interval > 0) intervalMs = Math.max(1000, s.interval * 1000);

      UI.render(s);
      if (S.push(S.sample(s)) && chartsReady) { C.update(); UI.setPerfHint(); }

      var age = F.isNum(s.age_seconds) ? s.age_seconds : 0;
      if (s.stale) UI.setConn('stale', 'Data is stale \u2014 the collector has not produced a sample for ' + Math.round(age) + ' s.');
      else UI.setConn('live');
      UI.pulseRefresh(intervalMs);
      schedule(intervalMs);
    }).catch(function (e) {
      failures++;
      UI.setConn('error', describeError(e));
      UI.setPaused('Retrying');
      schedule(intervalMs * Math.min(Math.pow(2, failures), MAX_BACKOFF_FACTOR));
    }).finally(function () { inflight = false; });
  }

  function start() {
    if (running) return;
    running = true;
    // Refresh history first (fills the gap after a pause), then begin polling.
    loadHistory().then(tick);
  }
  function stop() {
    running = false;
    clearTimeout(timer);
    UI.setPaused('Paused');
  }

  function boot() {
    chartsReady = C.init();
    document.addEventListener('visibilitychange', function () { document.hidden ? stop() : start(); });
    window.addEventListener('online', function () { if (running) { clearTimeout(timer); tick(); } });
    setInterval(function () { if (!document.hidden) UI.tickAge(); }, 1000);
    if (document.hidden) { UI.setPaused('Paused'); } else { start(); }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})(window);
