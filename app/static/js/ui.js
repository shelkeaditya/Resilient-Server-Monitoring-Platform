/* DOM rendering. Everything shown comes from the /api/v1/snapshot payload.
 * Text is only ever assigned through textContent / createTextNode, so values
 * such as interface or device names can never inject markup. */
(function (g) {
  'use strict';
  var F = g.SM.format, S = g.SM.store;
  var NA = F.NA;
  var SVG_NS = 'http://www.w3.org/2000/svg';

  var LEVEL_TEXT = { ok: 'Normal', warn: 'Warning', crit: 'Critical', unknown: NA };
  var LEVEL_ICON = { ok: '#i-check', warn: '#i-alert', crit: '#i-octagon', unknown: '#i-help' };
  var LEVEL_TITLE = {
    ok: 'All systems healthy', warn: 'Attention needed',
    crit: 'Critical issues detected', unknown: 'Status unknown'
  };

  /* ---------- DOM helpers ------------------------------------------------ */
  var warned = {};
  function el(id) {
    var e = document.getElementById(id);
    if (!e) {
      if (!warned[id]) { warned[id] = true; console.warn('[monitor] missing element #' + id); }
      return document.createElement('span');   // detached stand-in: updates become harmless no-ops
    }
    return e;
  }
  function text(id, value) { el(id).textContent = value == null ? NA : value; }

  function h(tag, props) {
    var e = document.createElement(tag);
    if (props) Object.keys(props).forEach(function (k) {
      var v = props[k];
      if (v == null || v === false) return;
      if (k === 'class') e.className = v;
      else if (k === 'text') e.textContent = v;
      else e.setAttribute(k, v);
    });
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null || c === false) continue;
      e.appendChild(c.nodeType ? c : document.createTextNode(String(c)));
    }
    return e;
  }
  function icon(href, cls) {
    var svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('class', 'icon' + (cls ? ' ' + cls : ''));
    svg.setAttribute('aria-hidden', 'true');
    var use = document.createElementNS(SVG_NS, 'use');
    use.setAttribute('href', href);
    svg.appendChild(use);
    return svg;
  }
  function meter(percent, level) {
    var fill = h('div', { class: 'meter__fill' });
    fill.style.width = F.isNum(percent) ? F.clamp(percent, 0, 100) + '%' : '0%';
    return h('div', { class: 'meter', 'data-level': level || 'neutral' }, fill);
  }

  function ok(s, name) { return s && s[name] && s[name].status === 'ok' ? s[name] : null; }
  function levelOf(health, id) {
    if (!health || !health.items) return 'unknown';
    for (var i = 0; i < health.items.length; i++) if (health.items[i].id === id) return health.items[i].level;
    return 'unknown';
  }
  function levelByPercent(p) { return !F.isNum(p) ? 'unknown' : p >= 90 ? 'crit' : p >= 75 ? 'warn' : 'ok'; }

  function setRing(id, percent) {
    var ring = el(id);
    if (F.isNum(percent)) {
      var p = F.clamp(percent, 0, 100);
      ring.style.strokeDasharray = p + ' 100';
      ring.style.opacity = p < 0.4 ? '0' : '1';
    } else {
      ring.style.strokeDasharray = '0 100';
      ring.style.opacity = '0';
    }
  }

  /* Fill one metric card. `d` = null marks the collector as unavailable. */
  function setCard(name, level, d) {
    var card = el('card-' + name);
    card.setAttribute('data-level', level);
    card.setAttribute('data-state', d ? 'ready' : 'unavailable');
    var chip = document.getElementById(name + '-chip');
    if (chip) chip.textContent = LEVEL_TEXT[level];
    if (!d) { d = { val: NA, cap: 'Collector unavailable', foot: NA, ring: null }; }
    text(name + '-val', d.val);
    text(name + '-cap', d.cap);
    text(name + '-foot', d.foot);
    if (document.getElementById(name + '-ring')) setRing(name + '-ring', d.ring);
  }

  /* ---------- Connection / chrome --------------------------------------- */
  var CONN_TEXT = { connecting: 'Connecting', live: 'Live', stale: 'Stale data', error: 'Disconnected' };
  var ageBase = null, receivedAt = 0;   // age reported by the server + time elapsed locally (immune to clock skew)

  function setConn(state, detail) {
    var pill = el('conn-pill');
    pill.setAttribute('data-state', state);
    text('conn-text', CONN_TEXT[state] || state);
    var banner = el('banner');
    if (state === 'stale' || state === 'error') {
      banner.hidden = false;
      banner.setAttribute('data-level', state === 'error' ? 'crit' : 'warn');
      text('banner-text', detail || '');
    } else {
      banner.hidden = true;
    }
    el('refresh').classList.toggle('is-paused', state === 'error' || state === 'connecting');
  }

  function pulseRefresh(intervalMs) {
    var r = el('refresh');
    r.style.setProperty('--interval', (intervalMs / 1000) + 's');
    r.classList.remove('is-running', 'is-paused');
    void r.offsetWidth;               // restart the CSS animation
    r.classList.add('is-running');
    text('refresh-text', 'Auto-refresh \u00b7 ' + F.num(intervalMs / 1000, intervalMs % 1000 ? 1 : 0) + ' s');
  }
  function setPaused(reason) {
    var r = el('refresh');
    r.classList.remove('is-running');
    r.classList.add('is-paused');
    text('refresh-text', reason || 'Paused');
  }

  /* Keeps "x s ago" honest between polls, so a failing poll becomes visible. */
  function tickAge() {
    if (ageBase == null) return;
    var label = F.ago(ageBase + (performance.now() - receivedAt) / 1000);
    text('last-ago', label ? '(' + label + ')' : '');
  }

  /* ---------- Top bar ---------------------------------------------------- */
  function renderTopbar(s) {
    var sys = ok(s, 'system');
    text('host-name', sys && sys.hostname ? sys.hostname : NA);
    if (sys && sys.hostname) document.title = sys.hostname + ' \u00b7 Server Monitor';
    text('last-updated', F.clock(s.collected_at));
    ageBase = F.isNum(s.age_seconds) ? Math.max(0, s.age_seconds) : 0;
    receivedAt = performance.now();
    tickAge();
  }

  /* ---------- Overview cards -------------------------------------------- */
  function renderCards(s) {
    var health = s.health, cpu = ok(s, 'cpu'), mem = ok(s, 'memory'), dsk = ok(s, 'disks'),
        net = ok(s, 'network'), up = ok(s, 'uptime');

    setCard('cpu', levelOf(health, 'cpu'), cpu && {
      val: F.pct(cpu.percent, 0),
      cap: cpu.cores + ' vCPU \u00b7 load ' + F.num(cpu.load1, 2),
      foot: 'user ' + F.pct(cpu.user_percent, 1) + ' \u00b7 system ' + F.pct(cpu.system_percent, 1) +
            ' \u00b7 iowait ' + F.pct(cpu.iowait_percent, 1) + ' \u00b7 steal ' + F.pct(cpu.steal_percent, 1),
      ring: cpu.percent
    });

    setCard('memory', levelOf(health, 'memory'), mem && {
      val: F.pct(mem.percent, 0),
      cap: F.bytes(mem.used) + ' of ' + F.bytes(mem.total),
      foot: F.bytes(mem.available) + ' available \u00b7 cache ' + F.bytes((mem.cached || 0) + (mem.buffers || 0)),
      ring: mem.percent
    });

    setCard('swap', levelOf(health, 'swap'), mem && (mem.swap_total > 0 ? {
      val: F.pct(mem.swap_percent, 1),
      cap: F.bytes(mem.swap_used) + ' of ' + F.bytes(mem.swap_total),
      foot: 'swap-in ' + F.rate(mem.swap_in_bps) + ' \u00b7 swap-out ' + F.rate(mem.swap_out_bps),
      ring: mem.swap_percent
    } : { val: 'None', cap: 'No swap configured', foot: NA, ring: 0 }));

    var worst = null;
    if (dsk && dsk.mounts.length) {
      worst = dsk.mounts.reduce(function (a, b) { return b.percent > a.percent ? b : a; });
    }
    setCard('disk', levelOf(health, 'disk'), dsk && (worst ? {
      val: F.pct(worst.percent, 0),
      cap: worst.mount + ' \u00b7 ' + F.bytes(worst.used) + ' of ' + F.bytes(worst.total),
      foot: 'inodes ' + F.pct(worst.inode_percent, 1) + ' \u00b7 read ' + F.rate(dsk.read_bps) + ' \u00b7 write ' + F.rate(dsk.write_bps),
      ring: worst.percent
    } : { val: NA, cap: 'No filesystems reported', foot: NA, ring: null }));

    // Network has no capacity to compare against, so it shows rates, totals and the observed peak.
    var card = el('card-network');
    card.setAttribute('data-state', net ? 'ready' : 'unavailable');
    text('net-down', net ? F.rate(net.rx_bps) : NA);
    text('net-up', net ? F.rate(net.tx_bps) : NA);
    var span = S.spanSeconds();
    text('net-foot', net
      ? 'Since boot: \u2193 ' + F.bytes(net.rx_total) + ' \u00b7 \u2191 ' + F.bytes(net.tx_total) +
        (span > 30 ? ' \u00b7 peak (' + Math.round(span / 60) + ' min): \u2193 ' + F.rate(S.peak('net_rx')) + ' \u2191 ' + F.rate(S.peak('net_tx')) : '')
      : NA);

    var sys = ok(s, 'system');
    var upCard = el('card-uptime');
    upCard.setAttribute('data-state', up ? 'ready' : 'unavailable');
    text('uptime-val', up ? F.uptime(up.seconds) : NA);
    text('uptime-cap', sys ? 'Since ' + F.dateTime(sys.boot_time) : (up ? NA : 'Collector unavailable'));
    text('uptime-foot', up ? F.num(up.seconds / 86400, 1) + ' days of continuous operation' : NA);

    var perCore = cpu && cpu.cores ? cpu.load1 / cpu.cores : null;
    setCard('load', levelOf(health, 'load'), cpu && {
      val: F.num(cpu.load1, 2),
      cap: '5 min ' + F.num(cpu.load5, 2) + ' \u00b7 15 min ' + F.num(cpu.load15, 2),
      foot: F.num(perCore, 2) + ' per core \u00b7 ' + cpu.cores + ' vCPU',
      ring: F.isNum(perCore) ? perCore * 100 : null
    });
  }

  /* ---------- Health overview ------------------------------------------- */
  var PRESSURE = { psi_cpu: 'psi-cpu', psi_memory: 'psi-memory', psi_io: 'psi-io' };

  function renderHealth(s) {
    var hl = s.health;
    var overall = hl ? hl.overall : 'unknown';
    el('health-card').setAttribute('data-level', overall);
    el('health-icon').setAttribute('href', LEVEL_ICON[overall]);
    text('health-title', LEVEL_TITLE[overall]);

    var counts = hl ? hl.counts : {};
    ['ok', 'warn', 'crit', 'unknown'].forEach(function (k) { text('cnt-' + k, F.isNum(counts[k]) ? counts[k] : NA); });

    var items = hl && hl.items ? hl.items : [];
    var bad = items.filter(function (i) { return i.level === 'warn' || i.level === 'crit'; });
    text('health-sub', !hl ? 'No health data.'
      : bad.length ? bad.map(function (i) { return i.label; }).join(', ') + (bad.length === 1 ? ' needs' : ' need') + ' attention.'
      : 'All monitored indicators are within their thresholds.');

    // Indicator list (everything except the pressure meters, shown separately)
    var list = el('indicators');
    var rows = items.filter(function (i) { return !PRESSURE[i.id]; }).map(function (i) {
      return h('li', { class: 'indicator', 'data-level': i.level },
        icon(LEVEL_ICON[i.level]),
        h('div', { class: 'indicator__body' },
          h('div', { class: 'indicator__label' }, i.label, h('span', { class: 'sr-only', text: ' \u2014 ' + LEVEL_TEXT[i.level] })),
          h('div', { class: 'indicator__msg', text: i.message || NA })));
    });
    if (!rows.length) rows.push(h('li', { class: 'indicators__empty', text: 'No indicators available.' }));
    list.replaceChildren.apply(list, rows);

    // Resource pressure (kernel PSI)
    items.forEach(function (i) {
      var base = PRESSURE[i.id];
      if (!base) return;
      el(base).setAttribute('data-level', i.level);
      text(base + '-val', F.isNum(i.value) ? F.pct(i.value, 1) : 'Unsupported');
      el(base + '-bar').style.width = F.isNum(i.value) ? Math.max(i.value > 0 ? 2 : 0, F.clamp(i.value, 0, 100)) + '%' : '0%';
    });

    // Collection status
    var state = s.stale ? 'Stale' : (levelOf(hl, 'collection') === 'ok' ? 'Healthy' : 'Degraded');
    text('coll-state', state);
    text('coll-age', F.isNum(s.age_seconds) ? F.num(s.age_seconds, 1) + ' s' : NA);
    text('coll-interval', F.isNum(s.interval) ? F.num(s.interval, s.interval % 1 ? 1 : 0) + ' s' : NA);
  }

  /* ---------- Detail panels --------------------------------------------- */
  function emptyRow(cols, msg) {
    return h('tr', null, h('td', { class: 'empty', colspan: String(cols), text: msg }));
  }

  function renderDetails(s) {
    var sys = ok(s, 'system'), cpu = ok(s, 'cpu'), mem = ok(s, 'memory'), up = ok(s, 'uptime'),
        dsk = ok(s, 'disks'), nics = ok(s, 'interfaces');

    text('sys-hostname', sys && sys.hostname);
    text('sys-os', sys && sys.os);
    text('sys-kernel', sys && sys.kernel);
    text('sys-arch', sys && sys.arch);
    text('sys-cpu', sys && sys.cpu_model);
    text('sys-cores', sys ? sys.cores_logical + ' logical' + (sys.cores_physical ? ' \u00b7 ' + sys.cores_physical + ' physical' : '') : NA);
    text('sys-ram', mem ? F.bytes(mem.total) + ' total \u00b7 ' + F.bytes(mem.available) + ' available' : NA);
    text('sys-swap', mem ? (mem.swap_total ? F.bytes(mem.swap_used) + ' of ' + F.bytes(mem.swap_total) + ' used' : 'Not configured') : NA);
    text('sys-uptime', up ? F.uptime(up.seconds) : NA);
    text('sys-boot', sys ? F.dateTime(sys.boot_time) : NA);

    // Per-core usage
    var coreList = el('core-list');
    var cores = cpu && Array.isArray(cpu.per_core) ? cpu.per_core : [];
    var coreRows = cores.map(function (p, i) {
      return h('div', { class: 'core' }, h('span', { text: 'CPU ' + i }), meter(p, levelByPercent(p)), h('span', { class: 'core__pct', text: F.pct(p, 0) }));
    });
    if (!coreRows.length) coreRows.push(h('p', { class: 'note', text: 'Per-core data unavailable.' }));
    coreList.replaceChildren.apply(coreList, coreRows);

    // Filesystems
    var fs = el('fs-body');
    var fsRows = dsk && dsk.mounts.length ? dsk.mounts.map(function (m) {
      var lvl = levelByPercent(m.percent);
      return h('tr', null,
        h('td', { class: 'mono' }, m.mount,
          m.aliases && m.aliases.length ? h('span', { class: 'alias', title: 'Also mounted at ' + m.aliases.join(', '), text: ' +' + m.aliases.length }) : null),
        h('td', { class: 'mono', text: m.device }),
        h('td', { text: m.fstype }),
        h('td', { class: 'num', text: F.bytes(m.used) + ' / ' + F.bytes(m.total) }),
        h('td', { class: 'usage' }, h('div', { class: 'cell-usage' }, meter(m.percent, lvl), h('span', { class: 'cell-usage__pct', text: F.pct(m.percent, 0) }))),
        h('td', { class: 'num', text: F.pct(m.inode_percent, 1) }));
    }) : [emptyRow(6, dsk ? 'No filesystems reported' : 'Disk collector unavailable')];
    fs.replaceChildren.apply(fs, fsRows);

    // Disk I/O
    var io = el('io-body');
    var devs = dsk && Array.isArray(dsk.devices) ? dsk.devices : [];
    var ioRows = devs.length ? devs.map(function (d) {
      return h('tr', null,
        h('td', { class: 'mono', text: d.name }),
        h('td', { class: 'num', text: F.rate(d.read_bps) }),
        h('td', { class: 'num', text: F.rate(d.write_bps) }),
        h('td', { class: 'num', text: F.num(d.read_iops, 1) }),
        h('td', { class: 'num', text: F.num(d.write_iops, 1) }),
        h('td', { class: 'num', text: F.pct(d.busy_percent, 0) }));
    }) : [emptyRow(6, dsk ? 'No block devices reported' : 'Disk collector unavailable')];
    io.replaceChildren.apply(io, ioRows);

    // Network interfaces
    var nb = el('nic-body');
    var list = nics && Array.isArray(nics.interfaces) ? nics.interfaces : [];
    var nicRows = list.length ? list.map(function (n) {
      return h('tr', null,
        h('td', { class: 'mono', text: n.name }),
        h('td', null, h('span', { class: 'state-dot', 'data-level': n.is_up ? 'ok' : 'unknown', text: n.is_up ? 'Up' : 'Down' })),
        h('td', { class: 'mono', text: n.ipv4 && n.ipv4.length ? n.ipv4.join(', ') : NA }),
        h('td', { class: 'num', text: F.link(n.speed_mbps) + (n.mtu ? ' \u00b7 MTU ' + n.mtu : '') }),
        h('td', { class: 'num', text: F.rate(n.rx_bps) }),
        h('td', { class: 'num', text: F.rate(n.tx_bps) }),
        h('td', { class: 'num', text: F.int((n.rx_errors || 0) + (n.tx_errors || 0)) + ' / ' + F.int((n.rx_drops || 0) + (n.tx_drops || 0)) }));
    }) : [emptyRow(7, nics ? 'No interfaces reported' : 'Interface collector unavailable')];
    nb.replaceChildren.apply(nb, nicRows);
  }

  /* ---------- Entry points ---------------------------------------------- */
  function render(s) {
    renderTopbar(s);
    renderCards(s);
    renderHealth(s);
    renderDetails(s);
    document.body.setAttribute('data-state', 'ready');
  }

  function setPerfHint() {
    var sp = S.spanSeconds();
    text('perf-hint', sp > 0 ? 'Last ' + (sp >= 90 ? Math.round(sp / 60) + ' min' : Math.round(sp) + ' s') + ' of live history from the collector'
                              : 'Collecting history\u2026');
  }

  g.SM.ui = { render: render, setConn: setConn, pulseRefresh: pulseRefresh, setPaused: setPaused,
              tickAge: tickAge, setPerfHint: setPerfHint };
})(window);
