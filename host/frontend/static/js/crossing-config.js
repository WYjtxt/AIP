/*!
 * 平台配置页：跨越闸机（翻越闸机）绘制界面
 * ---------------------------------------------------------------------------
 * 只在「解析类型 = 跨越闸机」时接管配置页绘制区，其它类型（人数统计、闸机尾随…）
 * 完全不介入，仍走各自原有逻辑。
 *
 * 交互：
 *   画区域   —— ROI 多边形（≥3 点，点回起点/双击闭合），仅用于显示与参考；
 *   画 L1    —— 闸机挡板线（触碰线，黄色），两点成线；
 *   画 L2    —— 通道前方完成线（蓝色），两点成线；
 *   保存字段：conf_area = ROI；cross_line_area =
 *     {"area_type":"dual_line","l1":{"p1":..,"p2":..},"l2":{"p1":..,"p2":..},"line_touch_dist":30}
 *   L2 的“完成侧”由模板按几何自动判定（远离 L1 的一侧），无需手工填方向。
 */
(function () {
  'use strict';

  if (window.__crossingRegionConfig) return;
  window.__crossingRegionConfig = true;

  var TAG = '[crossing-region]';
  var CROSSING_RE = /跨越闸机/;
  var W = 640, H = 360;

  var S = {
    vm: null, overlay: null, toolbar: null,
    mode: 'roi',           // roi | l1 | l2
    roi: [], roiClosed: false,
    l1: [], l2: [],
    preview: null, sig: '', active: false
  };

  function txt(v) { return v === undefined || v === null ? '' : String(v); }

  function parseJSON(raw) {
    if (typeof raw !== 'string') return raw;
    try { return JSON.parse(raw); } catch (e) {
      try { return JSON.parse(raw.replace(/'/g, '"')); } catch (ignored) { return null; }
    }
  }

  function pointOf(raw) {
    if (raw && typeof raw === 'object' && 'x' in raw && 'y' in raw) {
      var x = Number(raw.x), y = Number(raw.y);
      return isFinite(x) && isFinite(y) ? { x: x, y: y } : null;
    }
    if (Array.isArray(raw) && raw.length >= 2) {
      var a = Number(raw[0]), b = Number(raw[1]);
      return isFinite(a) && isFinite(b) ? { x: a, y: b } : null;
    }
    return null;
  }

  function distance(a, b) { return Math.sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y)); }

  function findVm() {
    var root = document.getElementById('app');
    root = root && root.__vue__;
    if (!root) return null;
    var stack = [root], guard = 0;
    while (stack.length && guard++ < 4000) {
      var vm = stack.pop();
      if (!vm) continue;
      if (vm.form && typeof vm.handleData === 'function' &&
          typeof vm.sub_fn === 'function' && vm.mark_lists !== undefined) return vm;
      var kids = vm.$children;
      if (kids) for (var i = 0; i < kids.length; i++) stack.push(kids[i]);
    }
    return null;
  }

  function typeNames(vm) {
    var id = vm.form && vm.form.Algorithm_library_id;
    var names = [];
    var lists = [vm.dict && vm.dict.algorithm_list, vm.options3];
    for (var l = 0; l < lists.length; l++) {
      var list = lists[l];
      if (!Array.isArray(list)) continue;
      for (var i = 0; i < list.length; i++) {
        if (String(list[i] && list[i].id) !== String(id)) continue;
        names.push(txt(list[i].analysis_type), txt(list[i].algorithm_name));
      }
    }
    if (names.length) return names;
    return [txt(vm.form && vm.form.analysis_type), txt(vm.form && vm.form.algorithm_name), txt(vm.nameif)];
  }

  function isCrossing(vm) {
    if (!vm || !vm.form) return false;
    var names = typeNames(vm);
    for (var i = 0; i < names.length; i++) if (names[i] && CROSSING_RE.test(names[i])) return true;
    return false;
  }

  function scaleOf(vm) {
    var raw = txt((vm.form && (vm.form.conf_img_resolution || vm.form.img_resolution)) || vm.resolution);
    var m = /^(\d+)\s*[xX×*]\s*(\d+)$/.exec(raw);
    if (m && +m[1] > 0 && +m[2] > 0) return { x: +m[1] / W, y: +m[2] / H };
    var tx = Number(vm.timesX), ty = Number(vm.timesY);
    if (isFinite(tx) && tx > 0 && isFinite(ty) && ty > 0) return { x: tx, y: ty };
    return { x: 3, y: 3 };
  }

  // ---------------------------------------------------------------- 界面
  function positionOverlay() {
    var canvas = S.overlay;
    if (!canvas) return;
    var box = canvas.parentNode, img = box && box.querySelector('img');
    var left = 0, top = 0, width = W, height = H;
    if (img) {
      left = img.offsetLeft || 0;
      top = img.offsetTop || 0;
      if (img.clientWidth) width = img.clientWidth;
      if (img.clientHeight) height = img.clientHeight;
    }
    canvas.style.left = left + 'px';
    canvas.style.top = top + 'px';
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
  }

  function buildToolbar() {
    var bar = document.createElement('div');
    bar.id = 'tg-cross-toolbar';
    bar.setAttribute('data-crossing-region', '1');
    bar.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:6px 0 2px;font-size:12px;line-height:22px;color:#606266;';
    bar.innerHTML =
      '<button type="button" data-cx="roi" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">画区域</button>' +
      '<button type="button" data-cx="l1" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">画 L1 挡板线</button>' +
      '<button type="button" data-cx="l2" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">画 L2 完成线</button>' +
      '<button type="button" data-cx="undo" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">撤销一点</button>' +
      '<button type="button" data-cx="clear" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">清空</button>' +
      '<button type="button" data-cx="reload" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">刷新画面</button>';
    bar.addEventListener('click', function (event) {
      var btn = event.target && event.target.closest ? event.target.closest('[data-cx]') : null;
      if (!btn) return;
      var act = btn.getAttribute('data-cx');
      if (act === 'roi' || act === 'l1' || act === 'l2') {
        S.mode = act;
        S.preview = null;
        if (act === 'roi' && S.roiClosed) { S.roi = []; S.roiClosed = false; }
        draw();
      } else if (act === 'undo') {
        undo();
      } else if (act === 'clear') {
        S.roi = []; S.roiClosed = false; S.l1 = []; S.l2 = []; S.preview = null;
        draw(); syncLive();
      } else if (act === 'reload') {
        if (S.vm && typeof S.vm.handleimg === 'function') S.vm.handleimg(1);
      }
    });
    return bar;
  }

  function updateToolbar() {
    var bar = S.toolbar;
    if (!bar) return;
    var map = { roi: 'roi', l1: 'l1', l2: 'l2' };
    Object.keys(map).forEach(function (k) {
      var btn = bar.querySelector('[data-cx="' + map[k] + '"]');
      if (!btn) return;
      var on = S.mode === k;
      btn.style.background = on ? '#ecf5ff' : '#fff';
      btn.style.borderColor = on ? '#b3d8ff' : '#dcdfe6';
      btn.style.color = on ? '#2f7ae5' : '#606266';
    });
  }

  function ensureUi(vm) {
    var box = document.querySelector('.Bcanvas');
    if (!box) return false;
    var canvas = document.getElementById('tg-cross-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'tg-cross-canvas';
      canvas.setAttribute('width', String(W));
      canvas.setAttribute('height', String(H));
      canvas.setAttribute('data-crossing-region', '1');
      canvas.style.cssText = 'position:absolute;left:0;top:0;width:640px;height:360px;z-index:26;cursor:crosshair;touch-action:none;';
      box.style.position = 'relative';
      box.appendChild(canvas);
      bindCanvas(canvas);
    }
    S.overlay = canvas;

    if (!S.toolbar || !S.toolbar.parentNode) {
      var bar = buildToolbar();
      var origin = document.querySelector('.canvasBtn');
      if (origin && origin.parentNode) origin.parentNode.insertBefore(bar, origin);
      else box.parentNode.appendChild(bar);
      S.toolbar = bar;
    }
    S.toolbar.style.display = '';

    var native = document.getElementById('mycanvas');
    if (native) { native.style.visibility = 'hidden'; native.style.pointerEvents = 'none'; }
    var nativeBar = document.querySelector('.canvasBtn');
    if (nativeBar) nativeBar.style.display = 'none';

    var img = box.querySelector('img');
    if (img && !img.__cxBound) {
      img.__cxBound = true;
      img.addEventListener('load', function () { positionOverlay(); draw(); });
    }
    positionOverlay();
    updateToolbar();
    return true;
  }

  function teardownUi() {
    var canvas = document.getElementById('tg-cross-canvas');
    if (canvas && canvas.parentNode) canvas.parentNode.removeChild(canvas);
    var bar = document.getElementById('tg-cross-toolbar');
    if (bar && bar.parentNode) bar.parentNode.removeChild(bar);
    var native = document.getElementById('mycanvas');
    if (native) { native.style.visibility = ''; native.style.pointerEvents = ''; }
    var nativeBar = document.querySelector('.canvasBtn');
    if (nativeBar) nativeBar.style.display = '';
    S.overlay = null; S.toolbar = null; S.active = false;
  }

  // ---------------------------------------------------------------- 绘制
  function draw() {
    var canvas = S.overlay;
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, W, H);

    // ROI
    if (S.roi.length) {
      ctx.beginPath();
      ctx.moveTo(S.roi[0].x, S.roi[0].y);
      for (var i = 1; i < S.roi.length; i++) ctx.lineTo(S.roi[i].x, S.roi[i].y);
      if (S.roiClosed && S.roi.length >= 3) ctx.closePath();
      if (S.roiClosed && S.roi.length >= 3) { ctx.fillStyle = 'rgba(255,215,0,.08)'; ctx.fill(); }
      ctx.strokeStyle = '#ffd700'; ctx.lineWidth = 2; ctx.stroke();
      for (var v = 0; v < S.roi.length; v++) {
        ctx.beginPath(); ctx.arc(S.roi[v].x, S.roi[v].y, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = '#ffd700'; ctx.fill();
      }
    }

    // L1 / L2
    drawLine(ctx, S.l1, '#ffd400', 'L1');
    drawLine(ctx, S.l2, '#4aa3ff', 'L2');

    // 预览
    if (S.preview) {
      var last = S.mode === 'roi' ? S.roi[S.roi.length - 1] : (S.mode === 'l1' ? S.l1[0] : S.l2[0]);
      if (last) {
        ctx.beginPath(); ctx.moveTo(last.x, last.y); ctx.lineTo(S.preview.x, S.preview.y);
        ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 4]); ctx.stroke(); ctx.setLineDash([]);
      }
    }

    if (!S.roi.length && !S.l1.length && !S.l2.length) {
      ctx.font = '13px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = 'rgba(0,0,0,.45)';
      ctx.fillText('先画区域（ROI），再画 L1 挡板线、L2 完成线', W / 2, H - 24);
    }
  }

  function drawLine(ctx, pts, color, label) {
    if (!pts.length) return;
    if (pts.length === 2) {
      ctx.beginPath(); ctx.moveTo(pts[0].x, pts[0].y); ctx.lineTo(pts[1].x, pts[1].y);
      ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = 6; ctx.stroke();
      ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.stroke();
    }
    for (var i = 0; i < pts.length; i++) {
      ctx.beginPath(); ctx.arc(pts[i].x, pts[i].y, 4, 0, Math.PI * 2); ctx.fillStyle = color; ctx.fill();
    }
    if (pts.length) {
      ctx.font = 'bold 13px sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
      ctx.fillStyle = color;
      ctx.fillText(label, Math.min(W - 22, pts[0].x + 6), Math.max(14, pts[0].y - 6));
    }
  }

  // ---------------------------------------------------------------- 交互
  function canvasPoint(event) {
    var canvas = S.overlay, rect = canvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(W, (event.clientX - rect.left) * W / (rect.width || W))),
      y: Math.max(0, Math.min(H, (event.clientY - rect.top) * H / (rect.height || H)))
    };
  }

  function undo() {
    if (S.mode === 'roi') {
      if (S.roiClosed) S.roiClosed = false;
      else S.roi.pop();
    } else if (S.mode === 'l1') {
      S.l1.pop();
    } else {
      S.l2.pop();
    }
    S.preview = null;
    draw(); syncLive();
  }

  function bindCanvas(canvas) {
    canvas.addEventListener('click', function (event) {
      if (!S.active) return;
      var p = canvasPoint(event);
      if (S.mode === 'roi') {
        if (S.roiClosed) return;
        if (S.roi.length >= 3 && distance(p, S.roi[0]) <= 12) {
          S.roiClosed = true; S.preview = null; draw(); syncLive(); return;
        }
        if (!S.roi.length || distance(p, S.roi[S.roi.length - 1]) >= 2) S.roi.push(p);
        draw();
      } else {
        var line = S.mode === 'l1' ? S.l1 : S.l2;
        if (line.length >= 2) line.length = 0;
        line.push(p);
        if (line.length === 2) S.preview = null;
        draw(); syncLive();
      }
    });

    canvas.addEventListener('mousemove', function (event) {
      if (!S.active) return;
      var p = canvasPoint(event);
      if (S.mode === 'roi' && !S.roiClosed && S.roi.length) { S.preview = p; draw(); }
      else if (S.mode !== 'roi') {
        var line = S.mode === 'l1' ? S.l1 : S.l2;
        if (line.length === 1) { S.preview = p; draw(); }
      }
    });

    canvas.addEventListener('mouseleave', function () {
      if (S.preview) { S.preview = null; draw(); }
    });

    canvas.addEventListener('dblclick', function (event) {
      if (!S.active || S.mode !== 'roi') return;
      event.preventDefault();
      if (S.roi.length >= 3) { S.roiClosed = true; S.preview = null; draw(); syncLive(); }
    });

    canvas.addEventListener('contextmenu', function (event) {
      if (!S.active || S.mode !== 'roi') return;
      event.preventDefault();
      if (S.roi.length >= 3) { S.roiClosed = true; draw(); syncLive(); }
    });
  }

  // ---------------------------------------------------------------- 与页面数据互通
  function scaledLine(vm, line) {
    var sc = scaleOf(vm);
    return [
      { x: Math.round(line[0].x * sc.x), y: Math.round(line[0].y * sc.y) },
      { x: Math.round(line[1].x * sc.x), y: Math.round(line[1].y * sc.y) }
    ];
  }

  function payload(vm) {
    if (S.l1.length !== 2 || S.l2.length !== 2) return null;
    var a = scaledLine(vm, S.l1), b = scaledLine(vm, S.l2);
    return { area_type: 'dual_line', l1: { p1: a[0], p2: a[1] }, l2: { p1: b[0], p2: b[1] },
             line_touch_dist: 30 };
  }

  function applyToVm(vm) {
    var sc = scaleOf(vm);
    if (S.roiClosed && S.roi.length >= 3) {
      vm.mark_lists = [S.roi.map(function (p) {
        return { x: Math.round(p.x * sc.x), y: Math.round(p.y * sc.y), type: '告警区域', color: '#FF0000' };
      })];
    }
    var data = payload(vm);
    if (data) vm.form.cross_line = data;
    vm.drawLineOpen = true;
    vm.form.draw_type = '2';
    if ((!S.roiClosed || S.roi.length < 3 || !data) && typeof vm.$message === 'function' && !vm.__cxWarned) {
      vm.__cxWarned = true;
      vm.$message({ type: 'warning', message: '跨越闸机：请先画区域（≥3 点）并画 L1、L2 两条线' });
      setTimeout(function () { vm.__cxWarned = false; }, 1500);
    }
  }

  function syncLive() {
    if (!S.vm || !S.active || !isCrossing(S.vm)) return;
    var data = payload(S.vm);
    if (data) S.vm.form.cross_line = data;
  }

  function patchVm(vm) {
    if (vm.__cxHandleDataWrapped) return;
    var original = vm.handleData;
    vm.handleData = function () {
      var result = original.apply(this, arguments);
      if (isCrossing(this) && this === S.vm) applyToVm(this);
      return result;
    };
    vm.__cxHandleDataWrapped = true;
  }

  function restoreFromVm(vm) {
    var form = vm.form || {};
    var raw = typeof form.cross_line_area === 'string' ? form.cross_line_area
      : JSON.stringify(form.cross_line_area || '');
    var rawArea = typeof form.conf_area === 'string' ? form.conf_area
      : JSON.stringify(form.conf_area || '');
    var sig = [form.id || '', form.Algorithm_library_id || '', raw, rawArea, txt(vm.resolution)].join('~');
    if (sig === S.sig) return;
    S.sig = sig;
    var sc = scaleOf(vm);
    S.roi = []; S.roiClosed = false; S.l1 = []; S.l2 = []; S.preview = null;

    var area = parseJSON(rawArea);
    if (area && !Array.isArray(area[0])) area = [area];
    if (Array.isArray(area) && Array.isArray(area[0]) && area[0].length >= 3) {
      var poly = [];
      for (var i = 0; i < area[0].length; i++) {
        var p = pointOf(area[0][i]);
        if (p) poly.push({ x: p.x / sc.x, y: p.y / sc.y });
      }
      if (poly.length >= 3) { S.roi = poly; S.roiClosed = true; }
    }

    var data = parseJSON(raw);
    if (data && typeof data === 'object') {
      var l1 = data.l1 || data.gate_l1, l2 = data.l2 || data.gate_l2;
      var a = l1 && l1.p1 && l1.p2 ? [pointOf(l1.p1), pointOf(l1.p2)] : null;
      var b = l2 && l2.p1 && l2.p2 ? [pointOf(l2.p1), pointOf(l2.p2)] : null;
      if (a && a[0] && a[1]) S.l1 = [{ x: a[0].x / sc.x, y: a[0].y / sc.y }, { x: a[1].x / sc.x, y: a[1].y / sc.y }];
      if (b && b[0] && b[1]) S.l2 = [{ x: b[0].x / sc.x, y: b[0].y / sc.y }, { x: b[1].x / sc.x, y: b[1].y / sc.y }];
    }
    draw(); updateToolbar();
  }

  // ---------------------------------------------------------------- 主循环
  function tick() {
    var onPage = /#\/sfgl_child/.test((location.hash || '') + ' ' + (location.pathname || '')) ||
                 /\/sfgl_child(?:s)?(?:[\/?#]|$)/.test(location.pathname || '');
    if (!onPage) {
      if (S.active) teardownUi();
      S.vm = null; S.sig = '';
      return;
    }
    var vm = findVm();
    if (!vm) return;
    if (vm !== S.vm) {
      if (S.active) teardownUi();
      S.vm = vm; S.sig = '';
      patchVm(vm);
    }
    if (!isCrossing(vm)) {
      if (S.active) teardownUi();
      return;
    }
    if (!ensureUi(vm)) return;
    S.active = true;
    restoreFromVm(vm);
  }

  function boot() {
    window.addEventListener('resize', function () {
      if (!S.active) return;
      positionOverlay(); draw();
    });
    setInterval(tick, 250);
    tick();
    console.log(TAG, 'active');
  }

  window.__crossingRegion = {
    state: function () {
      return { active: S.active, mode: S.mode, roi: S.roi.length, roiClosed: S.roiClosed,
               l1: S.l1.length, l2: S.l2.length };
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
