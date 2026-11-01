/* Formatting helpers. Every function returns "—" for a missing value so the UI
 * never shows NaN / undefined / a fake zero. */
(function (g) {
  'use strict';
  var NA = '\u2014';
  var UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];

  function isNum(n) { return typeof n === 'number' && isFinite(n); }

  function bytes(n, digits) {
    if (!isNum(n)) return NA;
    var v = Math.abs(n), i = 0;
    while (v >= 1024 && i < UNITS.length - 1) { v /= 1024; i++; }
    var d = digits != null ? digits : (i === 0 ? 0 : v >= 100 ? 0 : v >= 10 ? 1 : 2);
    return (n < 0 ? '-' : '') + v.toFixed(d) + ' ' + UNITS[i];
  }
  function rate(n) { return isNum(n) ? bytes(n) + '/s' : NA; }
  function pct(n, d) { return isNum(n) ? n.toFixed(d == null ? 0 : d) + '%' : NA; }
  function num(n, d) { return isNum(n) ? n.toFixed(d == null ? 2 : d) : NA; }
  function int(n) { return isNum(n) ? String(Math.round(n)) : NA; }

  function uptime(sec) {
    if (!isNum(sec) || sec < 0) return NA;
    var d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600),
        m = Math.floor(sec % 3600 / 60), s = Math.floor(sec % 60);
    if (d > 0) return d + 'd ' + h + 'h ' + m + 'm';
    if (h > 0) return h + 'h ' + m + 'm';
    return m + 'm ' + s + 's';
  }
  function clock(ts) {
    if (!isNum(ts)) return NA;
    var d = new Date(ts * 1000);
    var p = function (x) { return (x < 10 ? '0' : '') + x; };
    return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
  }
  function dateTime(ts) {
    if (!isNum(ts)) return NA;
    try {
      return new Date(ts * 1000).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
    } catch (e) { return new Date(ts * 1000).toLocaleString(); }
  }
  function ago(sec) {
    if (!isNum(sec) || sec < 0) return '';
    if (sec < 1.5) return 'just now';
    if (sec < 90) return Math.round(sec) + ' s ago';
    return Math.round(sec / 60) + ' min ago';
  }
  function link(mbps) { return isNum(mbps) && mbps > 0 ? (mbps >= 1000 ? (mbps / 1000) + ' Gb/s' : mbps + ' Mb/s') : NA; }
  function clamp(n, lo, hi) { return Math.min(hi, Math.max(lo, n)); }

  g.SM = g.SM || {};
  g.SM.format = { NA: NA, isNum: isNum, bytes: bytes, rate: rate, pct: pct, num: num, int: int,
                  uptime: uptime, clock: clock, dateTime: dateTime, ago: ago, link: link, clamp: clamp };
})(window);
