/* Bounded time-series store shared by all charts.
 * Arrays are mutated in place (never replaced) so Chart.js datasets can keep
 * referencing them, and they are trimmed to `max` points so memory use stays flat. */
(function (g) {
  'use strict';
  var F = g.SM.format;
  var KEYS = ['cpu', 'mem', 'swap', 'load1', 'load5', 'load15',
              'net_rx', 'net_tx', 'disk_r', 'disk_w', 'cores'];

  var state = { max: 300, t: [], labels: [], series: {} };
  KEYS.forEach(function (k) { state.series[k] = []; });
  var lastT = 0;

  function clear() {
    state.t.length = 0; state.labels.length = 0;
    KEYS.forEach(function (k) { state.series[k].length = 0; });
    lastT = 0;
  }

  function trim() {
    var over = state.t.length - state.max;
    if (over <= 0) return;
    state.t.splice(0, over); state.labels.splice(0, over);
    KEYS.forEach(function (k) { state.series[k].splice(0, over); });
  }

  /* Replace everything with the server-side history (called on load / tab resume). */
  function load(h) {
    clear();
    if (!h || !Array.isArray(h.t) || !h.series) return 0;
    if (F.isNum(h.max_points) && h.max_points >= 10) state.max = h.max_points;
    var n = h.t.length;
    for (var i = 0; i < n; i++) {
      state.t.push(h.t[i]);
      state.labels.push(F.clock(h.t[i]));
      KEYS.forEach(function (k) {
        if (k === 'cores') { state.series.cores.push(F.isNum(h.cores) ? h.cores : null); return; }
        var col = h.series[k];
        var v = col ? col[i] : null;
        state.series[k].push(F.isNum(v) ? v : null);
      });
    }
    lastT = n ? h.t[n - 1] : 0;
    trim();
    return state.t.length;
  }

  function ok(s, name) { return s && s[name] && s[name].status === 'ok'; }

  /* Build one chart sample from a /api/v1/snapshot payload. */
  function sample(s) {
    var cpu = ok(s, 'cpu') ? s.cpu : null, mem = ok(s, 'memory') ? s.memory : null;
    var net = ok(s, 'network') ? s.network : null, dsk = ok(s, 'disks') ? s.disks : null;
    return {
      t: s.collected_at,
      cpu: cpu ? cpu.percent : null,
      mem: mem ? mem.percent : null,
      swap: mem ? mem.swap_percent : null,
      load1: cpu ? cpu.load1 : null, load5: cpu ? cpu.load5 : null, load15: cpu ? cpu.load15 : null,
      net_rx: net ? net.rx_bps : null, net_tx: net ? net.tx_bps : null,
      disk_r: dsk ? dsk.read_bps : null, disk_w: dsk ? dsk.write_bps : null,
      cores: cpu ? cpu.cores : null
    };
  }

  /* Append a sample. Returns false for duplicates / out-of-order samples. */
  function push(p) {
    if (!p || !F.isNum(p.t) || p.t <= lastT) return false;
    lastT = p.t;
    state.t.push(p.t);
    state.labels.push(F.clock(p.t));
    KEYS.forEach(function (k) { state.series[k].push(F.isNum(p[k]) ? p[k] : null); });
    trim();
    return true;
  }

  function last(key) {
    var a = state.series[key];
    return a.length ? a[a.length - 1] : null;
  }
  function peak(key) {
    var m = null;
    state.series[key].forEach(function (v) { if (F.isNum(v) && (m === null || v > m)) m = v; });
    return m;
  }
  function spanSeconds() { return state.t.length > 1 ? state.t[state.t.length - 1] - state.t[0] : 0; }

  g.SM.store = { state: state, load: load, push: push, sample: sample, last: last, peak: peak,
                 spanSeconds: spanSeconds, clear: clear };
})(window);
