// PEM Archive - theme toggle, archive filter, and dependency-free SVG charts.
(function () {
  'use strict';
  var SVG = 'http://www.w3.org/2000/svg';

  // ---- theme toggle (stored per viewer; storage may be unavailable) ----
  function getStored() { try { return localStorage.getItem('theme'); } catch (e) { return null; } }
  function setStored(v) { try { localStorage.setItem('theme', v); } catch (e) {} }
  var stored = getStored();
  if (stored) document.documentElement.setAttribute('data-theme', stored);
  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.querySelector('.theme-btn');
    if (btn) btn.addEventListener('click', function () {
      var cur = document.documentElement.getAttribute('data-theme') ||
        (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
      var next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      setStored(next);
    });
    initFilter();
    document.querySelectorAll('[data-chart]').forEach(renderChart);
  });

  // ---- archive filter ----
  function initFilter() {
    var q = document.getElementById('q');
    if (!q) return;
    var topic = document.getElementById('f-topic'), design = document.getElementById('f-design');
    var rows = Array.prototype.slice.call(document.querySelectorAll('#papers tbody tr'));
    var count = document.getElementById('count');
    function apply() {
      var s = q.value.trim().toLowerCase(), t = topic.value, d = design.value, n = 0;
      rows.forEach(function (r) {
        var ok = (!s || r.dataset.text.indexOf(s) >= 0) &&
          (!t || r.dataset.topics.split(' ').indexOf(t) >= 0) && (!d || r.dataset.design === d);
        r.hidden = !ok; if (ok) n++;
      });
      count.textContent = n + ' of ' + rows.length + ' papers';
    }
    [q, topic, design].forEach(function (el) { el.addEventListener('input', apply); });
    apply();
  }

  // ---- tooltip ----
  var tip;
  function showTip(evt, title, lines) {
    if (!tip) { tip = document.createElement('div'); tip.className = 'tip'; tip.setAttribute('role', 'status'); document.body.appendChild(tip); }
    tip.textContent = '';
    var b = document.createElement('b'); b.textContent = title; tip.appendChild(b);
    lines.forEach(function (l) { var s = document.createElement('span'); s.textContent = l; tip.appendChild(s); tip.appendChild(document.createElement('br')); });
    var r = evt.target.getBoundingClientRect();
    var x = evt.clientX || (r.left + r.width / 2), y = evt.clientY || r.top;
    tip.style.left = Math.min(x + 14, window.innerWidth - 270) + 'px';
    tip.style.top = (y + 14) + 'px';
    tip.hidden = false;
  }
  function hideTip() { if (tip) tip.hidden = true; }

  function el(name, attrs, parent) {
    var e = document.createElementNS(SVG, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  function text(parent, x, y, str, attrs) {
    var t = el('text', Object.assign({ x: x, y: y }, attrs || {}), parent);
    t.textContent = str; return t;
  }
  // round tick step (1, 2, 5 x 10^k) and an axis max that is a whole number of steps
  function niceScale(v) {
    var raw = Math.max(v, 1) / 4, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p;
    var step = Math.max(1, (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p);
    var n = Math.max(1, Math.ceil(v / step));
    return { step: step, n: n, max: step * n };
  }
  // bar with 4px rounded data-end, square at the baseline
  function hbarPath(x, y, w, h) {
    var r = Math.min(4, w, h / 2);
    return 'M' + x + ',' + y + 'H' + (x + w - r) + 'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) +
      'V' + (y + h - r) + 'Q' + (x + w) + ',' + (y + h) + ' ' + (x + w - r) + ',' + (y + h) + 'H' + x + 'Z';
  }
  function vbarPath(x, y0, w, h) {
    var r = Math.min(4, h, w / 2), y = y0 - h;
    return 'M' + x + ',' + y0 + 'V' + (y + r) + 'Q' + x + ',' + y + ' ' + (x + r) + ',' + y + 'H' + (x + w - r) +
      'Q' + (x + w) + ',' + y + ' ' + (x + w) + ',' + (y + r) + 'V' + y0 + 'Z';
  }
  function bindTip(node, title, lines) {
    node.setAttribute('tabindex', '0');
    node.setAttribute('aria-label', title + ': ' + lines.join(', '));
    node.addEventListener('pointermove', function (e) { showTip(e, title, lines); });
    node.addEventListener('focus', function (e) { showTip(e, title, lines); });
    node.addEventListener('pointerleave', hideTip);
    node.addEventListener('blur', hideTip);
  }

  function renderChart(host) {
    var spec = JSON.parse(document.getElementById(host.dataset.chart).textContent);
    if (spec.type === 'hbar') hbar(host, spec); else columns(host, spec);
    var btn = host.parentNode.querySelector('.toggle-table'), tbl = host.parentNode.querySelector('.table-wrap');
    if (btn && tbl) btn.addEventListener('click', function () {
      tbl.hidden = !tbl.hidden; btn.textContent = tbl.hidden ? 'Show table' : 'Hide table';
    });
  }

  // horizontal ranked bars, one series
  function hbar(host, spec) {
    var rows = spec.rows, labelW = spec.labelWidth || 190, W = 640, bar = 18, gap = 8, top = 4;
    var H = top + rows.length * (bar + gap) + 22, plotW = W - labelW - 44;
    var sc = niceScale(Math.max.apply(null, rows.map(function (r) { return r.value; }))), max = sc.max;
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': spec.title }, host);
    for (var i = 0; i <= sc.n; i++) {
      var gx = labelW + plotW * i / sc.n;
      el('line', { x1: gx, x2: gx, y1: top, y2: H - 20, class: i ? 'grid' : 'base' }, svg);
      text(svg, gx, H - 4, (sc.step * i).toLocaleString(), { 'text-anchor': 'middle' });
    }
    rows.forEach(function (r, i) {
      var y = top + i * (bar + gap), w = Math.max(1, plotW * r.value / max);
      text(svg, labelW - 8, y + bar / 2 + 4, r.label, { 'text-anchor': 'end' });
      var g = el('g', { class: 'mark' }, svg);
      el('rect', { x: labelW, y: y - gap / 2, width: plotW, height: bar + gap, fill: 'transparent' }, g);
      el('path', { d: hbarPath(labelW, y, w, bar), fill: 'var(--series-1)' }, g);
      bindTip(g, r.value.toLocaleString() + ' papers', [r.label].concat(r.detail || []));
      text(svg, labelW + w + 6, y + bar / 2 + 4, r.value.toLocaleString(), { class: 'val' });
    });
  }

  // grouped columns, up to two series
  function columns(host, spec) {
    var cats = spec.categories, series = spec.series, W = 640, H = 240, left = 34, bottom = 30, top = 8;
    var plotW = W - left - 8, plotH = H - top - bottom, band = plotW / cats.length;
    var all = [].concat.apply([], series.map(function (s) { return s.values; }));
    var sc = niceScale(Math.max.apply(null, all)), max = sc.max;
    var bw = Math.min(24, (band - 10) / series.length - 2);
    var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': spec.title }, host);
    for (var i = 0; i <= sc.n; i++) {
      var gy = top + plotH - plotH * i / sc.n;
      el('line', { x1: left, x2: W - 8, y1: gy, y2: gy, class: i ? 'grid' : 'base' }, svg);
      text(svg, left - 6, gy + 4, (sc.step * i).toLocaleString(), { 'text-anchor': 'end' });
    }
    cats.forEach(function (c, ci) {
      var cx = left + band * ci + band / 2, groupW = series.length * bw + (series.length - 1) * 2;
      text(svg, cx, H - 10, c, { 'text-anchor': 'middle' });
      series.forEach(function (s, si) {
        var v = s.values[ci], h = plotH * v / max, x = cx - groupW / 2 + si * (bw + 2);
        var g = el('g', { class: 'mark' }, svg);
        el('rect', { x: x - 1, y: top, width: bw + 2, height: plotH, fill: 'transparent' }, g);
        if (v > 0) el('path', { d: vbarPath(x, top + plotH, bw, Math.max(1, h)), fill: s.color }, g);
        bindTip(g, v + ' papers', [s.name + ', score ' + c]);
      });
    });
  }
})();
