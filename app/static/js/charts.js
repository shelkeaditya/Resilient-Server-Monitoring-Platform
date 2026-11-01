/* Chart definitions and rendering (Chart.js, vendored). Datasets reference the
 * shared SM.store arrays, so a new sample is one push + one update per chart. */
(function (g) {
  'use strict';
  var F = g.SM.format, S = g.SM.store;

  var DEFS = [
    { id: 'chart-cpu', fmt: 'pct', max: 100, series: [
      { key: 'cpu', label: 'CPU', color: '--c-cpu' }] },
    { id: 'chart-memory', fmt: 'pct', max: 100, series: [
      { key: 'mem', label: 'Memory', color: '--c-mem' },
      { key: 'swap', label: 'Swap', color: '--c-swap' }] },
    { id: 'chart-load', fmt: 'num', dynamicMax: true, series: [
      { key: 'load1', label: '1 min', color: '--c-load1' },
      { key: 'load5', label: '5 min', color: '--c-load5', fill: false },
      { key: 'load15', label: '15 min', color: '--c-load15', fill: false },
      { key: 'cores', label: 'vCPUs', color: '--c-ref', fill: false, dash: [5, 4], width: 1, noPoint: true }] },
    { id: 'chart-network', fmt: 'rate', series: [
      { key: 'net_rx', label: 'Download', color: '--c-rx' },
      { key: 'net_tx', label: 'Upload', color: '--c-tx' }] },
    { id: 'chart-disk', fmt: 'rate', series: [
      { key: 'disk_r', label: 'Read', color: '--c-read' },
      { key: 'disk_w', label: 'Write', color: '--c-write' }] }
  ];

  var FORMATTERS = {
    pct: function (v) { return F.pct(v, 1); },
    rate: function (v) { return F.rate(v); },
    num: function (v) { return F.num(v, 2); }
  };
  var TICKS = {
    pct: function (v) { return v + '%'; },
    rate: function (v) { return F.bytes(v) + '/s'; },
    num: function (v) { return F.num(v, v < 10 ? 1 : 0); }
  };

  var built = [];   // { def, chart, legend: { key: element } }

  /* Smallest "round" byte value (1, 2, 4 ... 512 x 1024^k) that fits v with a little headroom.
   * Used for throughput axes so gridlines land on clean KB/MB values instead of 195 KB, 391 KB... */
  var MULTS = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512];
  function niceCeil(v) {
    var need = Math.max(v * 1.1, 1024), k = 0;
    while (need >= Math.pow(1024, k + 1)) k++;
    var base = Math.pow(1024, k);
    for (var i = 0; i < MULTS.length; i++) if (MULTS[i] * base >= need) return MULTS[i] * base;
    return Math.pow(1024, k + 1);
  }

  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || '#5aa9ff';
  }

  function buildLegend(def) {
    var host = document.querySelector('[data-legend-for="' + def.id + '"]');
    var refs = {};
    if (!host) return refs;
    host.textContent = '';
    def.series.forEach(function (s) {
      var item = document.createElement('span');
      item.className = 'legend__item';
      var sw = document.createElement('i');
      sw.className = 'legend__swatch' + (s.dash ? ' legend__swatch--dash' : '');
      sw.style.background = css(s.color);
      sw.style.color = css(s.color);
      var name = document.createElement('span');
      name.textContent = s.label;
      var val = document.createElement('span');
      val.className = 'legend__val';
      val.textContent = F.NA;
      item.append(sw, name, val);
      host.appendChild(item);
      refs[s.key] = val;
    });
    return refs;
  }

  function init() {
    if (typeof Chart === 'undefined') {
      document.querySelectorAll('.chart').forEach(function (c) { c.classList.add('chart--unavailable'); });
      return false;
    }
    var textColor = css('--text-3'), grid = 'rgba(148,163,184,0.09)';
    Chart.defaults.devicePixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    Chart.defaults.font.family = css('--font');
    Chart.defaults.font.size = 11;
    Chart.defaults.color = textColor;

    // Only charts on screen are redrawn; off-screen ones are marked dirty and drawn when scrolled into view.
    var observer = typeof IntersectionObserver === 'function'
      ? new IntersectionObserver(function (entries) {
          entries.forEach(function (e) {
            var b = built.filter(function (x) { return x.canvas === e.target; })[0];
            if (!b) return;
            b.visible = e.isIntersecting;
            if (b.visible && b.dirty) { b.dirty = false; b.chart.update('none'); }
          });
        }, { rootMargin: '120px' })
      : null;

    DEFS.forEach(function (def) {
      var canvas = document.getElementById(def.id);
      if (!canvas) return;
      var datasets = def.series.map(function (s) {
        var color = css(s.color);
        return {
          label: s.label, data: S.state.series[s.key],
          borderColor: color, borderWidth: s.width || 1.8, borderDash: s.dash || [],
          backgroundColor: color + '26', fill: s.fill !== false,
          tension: 0.35, pointRadius: 0, pointHoverRadius: s.noPoint ? 0 : 3.5,
          pointHoverBackgroundColor: color, spanGaps: false
        };
      });
      var yScale = {
        beginAtZero: true,
        grid: { color: grid }, border: { display: false },
        ticks: { maxTicksLimit: 5, callback: TICKS[def.fmt], padding: 6 }
      };
      if (def.max) { yScale.max = def.max; yScale.ticks.stepSize = 25; }
      if (def.fmt === 'rate') { yScale.max = 1024; yScale.ticks.stepSize = 256; }
      if (def.dynamicMax) yScale.suggestedMax = 1.25;

      var chart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: { labels: S.state.labels, datasets: datasets },
        options: {
          responsive: true, maintainAspectRatio: false,
          animation: { duration: 250, easing: 'easeOutQuart' },
          interaction: { mode: 'index', intersect: false },
          layout: { padding: { top: 4, right: 2 } },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: 'rgba(8,13,24,0.96)', borderColor: 'rgba(148,163,184,0.28)', borderWidth: 1,
              titleColor: '#e7edf7', bodyColor: '#a9b6ca', padding: 10, boxPadding: 4,
              callbacks: { label: function (c) { return ' ' + c.dataset.label + ': ' + FORMATTERS[def.fmt](c.parsed.y); } }
            }
          },
          scales: {
            x: { grid: { display: false }, border: { color: grid },
                 ticks: { maxTicksLimit: 5, maxRotation: 0, autoSkip: true, padding: 6 } },
            y: yScale
          }
        }
      });
      var entry = { def: def, chart: chart, canvas: canvas, legend: buildLegend(def), visible: true, dirty: false };
      built.push(entry);
      if (observer) observer.observe(canvas);
    });
    return true;
  }

  /* Refresh every chart, legend value and accessible label from the store. */
  function update() {
    built.forEach(function (b) {
      var parts = [];
      b.def.series.forEach(function (s) {
        var v = S.last(s.key);
        var text = FORMATTERS[b.def.fmt](v);
        if (b.legend[s.key]) b.legend[s.key].textContent = (s.key === 'cores' && F.isNum(v)) ? F.int(v) : text;
        if (!s.noPoint) parts.push(s.label + ' ' + text);
      });
      if (b.def.fmt === 'rate') {
        var top = 0;
        b.def.series.forEach(function (s) { var m = S.peak(s.key); if (F.isNum(m) && m > top) top = m; });
        var nice = niceCeil(top);
        b.chart.options.scales.y.max = nice;
        b.chart.options.scales.y.ticks.stepSize = nice / 4;
      }
      if (b.def.dynamicMax) {
        var cores = S.last('cores');
        b.chart.options.scales.y.suggestedMax = Math.max(1, F.isNum(cores) ? cores : 1) * 1.25;
      }
      b.canvas.setAttribute('aria-label', b.canvas.getAttribute('aria-label').split(' — ')[0] + ' — latest: ' + parts.join(', '));
      if (!b.visible) { b.dirty = true; return; }
      b.chart.update(scrolling ? 'none' : undefined);
    });
  }

  var scrolling = false, scrollTimer = null;
  window.addEventListener('scroll', function () {
    scrolling = true;
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(function () { scrolling = false; }, 200);
  }, { passive: true });

  g.SM.charts = { init: init, update: update, defs: DEFS };
})(window);
