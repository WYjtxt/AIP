/*!
 * 平台配置页：按“解析类型”分流绘制方式（闸机尾随专用编辑方式）
 * ---------------------------------------------------------------------------
 * 人数统计（以及其它解析类型）：
 *     完全沿用平台原有逻辑 —— 计数线 direction = right / left，绿色 IN / 红色 OUT
 *     箭头，本脚本不创建任何界面、不改动任何保存字段。
 *
 * 闸机尾随 / 人员尾随：
 *     配置页改为「画区域（多边形）+ 画警戒线（自动吸成垂直线）」，
 *     警戒线中心画一个红色箭头表示通行方向：
 *         箭头朝下 → 保存 cross_line_area.direction = "down"（朝里）
 *         箭头朝上 → 保存 "up"（朝外）
 *     （警戒线接近竖直时箭头是水平的，此时以箭头指向区域/画面中心为“朝里 down”）
 *     点击箭头（或“切换朝向”按钮）即可翻转方向。
 *
 * 判定依据：解析类型下拉框（form.Algorithm_library_id）在算法字典里的
 * analysis_type / algorithm_name 是否命中“闸机尾随”。
 * 保存不另起接口，仍走页面自己的 sub_fn → algorithm_add / algorithm_update，
 * 通过包装 handleData() 把区域写进 mark_lists、把警戒线与方向写进 form.cross_line。
 */
(function () {
  'use strict';

  if (window.__tailgateRegionConfig) return;
  window.__tailgateRegionConfig = true;

  var TAG = '[tailgate-region]';
  var TAILGATE_RE = /闸机尾随|人员尾随/;
  var W = 640, H = 360;

  var S = {
    vm: null,
    overlay: null,
    toolbar: null,
    mode: 'area',       // area | line
    area: [],           // 画布坐标（640x360）
    areaClosed: false,
    line: [],
    dir: 'down',        // down = 朝里, up = 朝外
    preview: null,
    sig: '',
    active: false
  };

  // ---------------------------------------------------------------- 基础工具

  function txt(v) { return v === undefined || v === null ? '' : String(v); }

  function parseJSON(raw) {
    if (typeof raw !== 'string') return raw;
    try { return JSON.parse(raw); } catch (e) {
      try { return JSON.parse(raw.replace(/'/g, '"')); } catch (ignored) { return null; }
    }
  }

  function pointOf(raw) {
    var x = Number(raw && raw.x), y = Number(raw && raw.y);
    return isFinite(x) && isFinite(y) ? { x: x, y: y } : null;
  }

  function centroid(points) {
    var x = 0, y = 0;
    for (var i = 0; i < points.length; i++) { x += points[i].x; y += points[i].y; }
    return { x: x / points.length, y: y / points.length };
  }

  function distance(a, b) { return Math.sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y)); }

  // ---------------------------------------------------------------- 实例定位

  function findVm() {
    var root = document.getElementById('app');
    root = root && root.__vue__;
    if (!root) return null;
    var stack = [root], guard = 0;
    while (stack.length && guard++ < 4000) {
      var vm = stack.pop();
      if (!vm) continue;
      if (vm.form && typeof vm.handleData === 'function' &&
          typeof vm.sub_fn === 'function' && vm.mark_lists !== undefined) {
        return vm;
      }
      var children = vm.$children;
      if (children) for (var i = 0; i < children.length; i++) stack.push(children[i]);
    }
    return null;
  }

  // 解析类型名称：优先按当前选中的解析类型（Algorithm_library_id）查算法字典。
  // 注意：修改已有配置时 form.algorithm_name 是这条记录原来的名称，用户切换下拉框后
  // 它不会立刻变，所以只有字典里查不到时才用它兜底，避免“切到人数统计仍按尾随处理”。
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

  function isTailgate(vm) {
    if (!vm || !vm.form) return false;
    var names = typeNames(vm);
    for (var i = 0; i < names.length; i++) if (names[i] && TAILGATE_RE.test(names[i])) return true;
    return false;
  }

  // 画布坐标 → 原图坐标的倍率。
  // 页面自身 handleData() 用的是 timesX / timesY（默认 3，即 1920x1080 / 640x360），
  // 这里保持同一套换算，避免与平台已保存的坐标空间不一致。
  function scaleOf(vm) {
    var raw = txt((vm.form && (vm.form.conf_img_resolution || vm.form.img_resolution)) || vm.resolution);
    var m = /^(\d+)\s*[xX×*]\s*(\d+)$/.exec(raw);
    if (m && +m[1] > 0 && +m[2] > 0) return { x: +m[1] / W, y: +m[2] / H, resolution: raw };
    var tx = Number(vm.timesX), ty = Number(vm.timesY);
    if (isFinite(tx) && tx > 0 && isFinite(ty) && ty > 0) return { x: tx, y: ty, resolution: raw };
    return { x: 3, y: 3, resolution: raw };
  }

  // ---------------------------------------------------------------- 方向计算
  //
  // 方向语义（按用户约定）：箭头朝下 = 朝里 = down；箭头朝上 = 朝外 = up。
  // 警戒线多数是“横跨通道”的（接近水平），此时箭头法线接近竖直，正好直接取朝下的
  // 那一侧作为 down。警戒线接近竖直时箭头是水平的，没有上下之分，就退化为
  // “箭头指向区域重心（没有区域则指向画面中心）为朝里 = down”。

  // 返回“朝里（down）”那一侧的单位向量
  function inwardNormal() {
    if (S.line.length !== 2) return { x: 0, y: 1 };
    var a = S.line[0], b = S.line[1];
    var dx = b.x - a.x, dy = b.y - a.y, len = Math.sqrt(dx * dx + dy * dy) || 1;
    var n = { x: -dy / len, y: dx / len };

    // 法线有明显上下分量：朝下的那侧就是“里”（箭头朝下 = down）
    if (Math.abs(n.y) >= 0.28) {
      return n.y > 0 ? n : { x: -n.x, y: -n.y };
    }

    // 线接近竖直，箭头水平：以“朝向区域/画面中心”为里
    var mid = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    var target = (S.areaClosed && S.area.length >= 3) ? centroid(S.area) : { x: W / 2, y: H / 2 };
    var dot = n.x * (target.x - mid.x) + n.y * (target.y - mid.y);
    if (dot < 0) return { x: -n.x, y: -n.y };
    return n;
  }

  function arrowVector() {
    var n = inwardNormal();
    return S.dir === 'down' ? n : { x: -n.x, y: -n.y };
  }

  function arrowGeometry() {
    if (S.line.length !== 2) return null;
    var mid = { x: (S.line[0].x + S.line[1].x) / 2, y: (S.line[0].y + S.line[1].y) / 2 };
    var vec = arrowVector();
    return { mid: mid, vec: vec, tip: { x: mid.x + vec.x * 54, y: mid.y + vec.y * 54 } };
  }

  function hitArrow(p) {
    var g = arrowGeometry();
    if (!g) return false;
    return distance(p, g.mid) <= 34 || distance(p, g.tip) <= 30;
  }

  // ---------------------------------------------------------------- 界面构建

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
    bar.id = 'tg-toolbar';
    bar.setAttribute('data-tailgate-region', '1');
    bar.style.cssText = 'display:flex;flex-wrap:wrap;align-items:center;gap:6px;padding:6px 0 2px;font-size:12px;line-height:22px;color:#606266;';
    bar.innerHTML =
      '<button type="button" data-tg="mode-area" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">画区域</button>' +
      '<button type="button" data-tg="mode-line" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">画警戒线</button>' +
      '<button type="button" data-tg="undo" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">撤销一点</button>' +
      '<button type="button" data-tg="clear" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">清空</button>' +
      '<button type="button" data-tg="reload" style="padding:3px 10px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;font-size:12px;cursor:pointer;">刷新画面</button>' +
      '<span style="margin-left:6px;color:#8a94a6;">通行方向</span>' +
      '<span data-tg="dir-text" style="margin:0 6px;font-weight:600;color:#e6422e;">朝里（down）</span>' +
      '<button type="button" data-tg="dir" style="padding:3px 10px;border:1px solid #f0b4ab;border-radius:4px;background:#fff5f3;color:#d93a26;font-size:12px;cursor:pointer;">切换朝向</button>';
    bar.addEventListener('click', function (event) {
      var btn = event.target && event.target.closest ? event.target.closest('[data-tg]') : null;
      if (!btn) return;
      var act = btn.getAttribute('data-tg');
      if (act === 'mode-area' || act === 'mode-line') {
        S.mode = act === 'mode-line' ? 'line' : 'area';
        S.preview = null;
        // 已经闭合的区域再点“画区域”，视为重新绘制
        if (S.mode === 'area' && S.areaClosed) { S.area = []; S.areaClosed = false; }
        draw();
      } else if (act === 'undo') {
        undo();
      } else if (act === 'clear') {
        S.area = []; S.areaClosed = false; S.line = []; S.preview = null;
        draw(); syncLive();
      } else if (act === 'reload') {
        if (S.vm && typeof S.vm.handleimg === 'function') S.vm.handleimg(1);
      } else if (act === 'dir') {
        toggleDirection();
      }
    });
    return bar;
  }

  function updateToolbar() {
    var bar = S.toolbar;
    if (!bar) return;
    var areaBtn = bar.querySelector('[data-tg="mode-area"]');
    var lineBtn = bar.querySelector('[data-tg="mode-line"]');
    var paint = function (btn, on) {
      if (!btn) return;
      btn.style.background = on ? '#ecf5ff' : '#fff';
      btn.style.borderColor = on ? '#b3d8ff' : '#dcdfe6';
      btn.style.color = on ? '#2f7ae5' : '#606266';
    };
    paint(areaBtn, S.mode === 'area');
    paint(lineBtn, S.mode === 'line');
    var dirText = bar.querySelector('[data-tg="dir-text"]');
    if (dirText) dirText.textContent = S.dir === 'down' ? '朝里（down）' : '朝外（up）';
  }

  function ensureUi(vm) {
    var box = document.querySelector('.Bcanvas');
    if (!box) return false;
    var canvas = document.getElementById('tg-canvas');
    if (!canvas) {
      canvas = document.createElement('canvas');
      canvas.id = 'tg-canvas';
      canvas.setAttribute('width', String(W));
      canvas.setAttribute('height', String(H));
      canvas.setAttribute('data-tailgate-region', '1');
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

    // 原画布只做隐藏，不用 display:none，避免影响页面原有布局
    var native = document.getElementById('mycanvas');
    if (native) { native.style.visibility = 'hidden'; native.style.pointerEvents = 'none'; }
    var nativeBar = document.querySelector('.canvasBtn');
    if (nativeBar) nativeBar.style.display = 'none';

    var img = box.querySelector('img');
    if (img && !img.__tgBound) {
      img.__tgBound = true;
      img.addEventListener('load', function () { positionOverlay(); draw(); });
    }

    positionOverlay();
    updateToolbar();
    return true;
  }

  function teardownUi() {
    var canvas = document.getElementById('tg-canvas');
    if (canvas && canvas.parentNode) canvas.parentNode.removeChild(canvas);
    var bar = document.getElementById('tg-toolbar');
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

    // 区域（多边形）
    if (S.area.length) {
      var pts = S.area;
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      for (var i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y);
      if (S.areaClosed && pts.length >= 3) ctx.closePath();
      if (S.areaClosed && pts.length >= 3) { ctx.fillStyle = 'rgba(255,45,45,.10)'; ctx.fill(); }
      ctx.strokeStyle = '#ff2d2d'; ctx.lineWidth = 2; ctx.stroke();
      ctx.font = 'bold 12px sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
      for (var v = 0; v < pts.length; v++) {
        ctx.beginPath(); ctx.arc(pts[v].x, pts[v].y, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = '#ff2d2d'; ctx.fill();
        ctx.fillText(String(v + 1), Math.min(W - 14, pts[v].x + 5), Math.max(12, pts[v].y - 5));
      }
    }

    // 警戒线
    if (S.line.length === 2) {
      var a = S.line[0], b = S.line[1];
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
      ctx.strokeStyle = 'rgba(255,255,255,.75)'; ctx.lineWidth = 6; ctx.stroke();
      ctx.strokeStyle = '#ffd700'; ctx.lineWidth = 3; ctx.stroke();
      [a, b].forEach(function (p) {
        ctx.beginPath(); ctx.arc(p.x, p.y, 4, 0, Math.PI * 2); ctx.fillStyle = '#ffd700'; ctx.fill();
      });

      // 中心红色箭头：箭头方向 = 通行方向，朝里 = down，朝外 = up
      var g = arrowGeometry();
      if (g) {
        ctx.beginPath(); ctx.arc(g.mid.x, g.mid.y, 30, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(255,59,48,.35)'; ctx.lineWidth = 1; ctx.stroke();

        ctx.beginPath(); ctx.moveTo(g.mid.x, g.mid.y); ctx.lineTo(g.tip.x, g.tip.y);
        ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.lineWidth = 9; ctx.stroke();
        ctx.strokeStyle = '#ff3b30'; ctx.lineWidth = 6; ctx.stroke();

        var angle = Math.atan2(g.tip.y - g.mid.y, g.tip.x - g.mid.x);
        ctx.beginPath();
        ctx.moveTo(g.tip.x, g.tip.y);
        ctx.lineTo(g.tip.x - 19 * Math.cos(angle - 0.42), g.tip.y - 19 * Math.sin(angle - 0.42));
        ctx.lineTo(g.tip.x - 19 * Math.cos(angle + 0.42), g.tip.y - 19 * Math.sin(angle + 0.42));
        ctx.closePath();
        ctx.fillStyle = '#ff3b30'; ctx.fill();

        // 文字挂在箭头的侧面，避免压住箭头和区域边线
        var label = S.dir === 'down' ? '朝里 down' : '朝外 up';
        var perp = { x: -g.vec.y, y: g.vec.x };
        ctx.font = 'bold 13px sans-serif';
        var textWidth = ctx.measureText(label).width;
        var lx = g.tip.x + perp.x * 20;
        var ly = g.tip.y + perp.y * 20;
        lx = Math.max(textWidth / 2 + 4, Math.min(W - textWidth / 2 - 4, lx));
        ly = Math.max(12, Math.min(H - 10, ly));
        ctx.fillStyle = 'rgba(255,255,255,.88)';
        ctx.fillRect(lx - textWidth / 2 - 5, ly - 9, textWidth + 10, 18);
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillStyle = '#ff3b30';
        ctx.fillText(label, lx, ly);
      }
    } else if (S.line.length === 1) {
      ctx.beginPath(); ctx.arc(S.line[0].x, S.line[0].y, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = '#ffd700'; ctx.fill();
    }

    // 绘制预览
    if (S.preview) {
      var last = S.mode === 'line' ? S.line[0] : S.area[S.area.length - 1];
      if (last) {
        ctx.beginPath(); ctx.moveTo(last.x, last.y); ctx.lineTo(S.preview.x, S.preview.y);
        ctx.strokeStyle = 'rgba(255,215,0,.85)'; ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 4]); ctx.stroke(); ctx.setLineDash([]);
      }
    }

    // 无内容时给一句提示
    if (!S.area.length && !S.line.length) {
      ctx.font = '13px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillStyle = 'rgba(0,0,0,.45)';
      ctx.fillText(S.mode === 'area' ? '点击画面依次落点，画闭合区域（≥3 点）' : '点击画面画一条警戒线（两个点，自动吸成垂直线）', W / 2, H - 24);
    }
  }

  // ---------------------------------------------------------------- 交互

  function canvasPoint(event) {
    var canvas = S.overlay, rect = canvas.getBoundingClientRect();
    var x = (event.clientX - rect.left) * W / (rect.width || W);
    var y = (event.clientY - rect.top) * H / (rect.height || H);
    return { x: Math.max(0, Math.min(W, x)), y: Math.max(0, Math.min(H, y)) };
  }

  function closeArea() {
    // 双击闭合时，双击产生的两个点几乎重合，去掉最后一个
    if (S.area.length >= 2 && distance(S.area[S.area.length - 1], S.area[S.area.length - 2]) < 6) S.area.pop();
    if (S.area.length < 3) return;
    if (distance(S.area[0], S.area[S.area.length - 1]) < 8) S.area.pop();
    S.areaClosed = true;
    S.preview = null;
    draw(); syncLive();
  }

  function snapLine() {
    var a = S.line[0], b = S.line[1];
    var dx = Math.abs(a.x - b.x), dy = Math.abs(a.y - b.y);
    if (dx <= Math.max(10, dy * 0.35)) {
      var x = Math.round((a.x + b.x) / 2);
      S.line = [{ x: x, y: a.y }, { x: x, y: b.y }];
    }
  }

  function undo() {
    if (S.mode === 'area') {
      if (S.areaClosed) S.areaClosed = false;
      else S.area.pop();
    } else {
      S.line.pop();
    }
    S.preview = null;
    draw(); syncLive();
  }

  function toggleDirection() {
    S.dir = S.dir === 'down' ? 'up' : 'down';
    updateToolbar(); draw(); syncLive();
  }

  function bindCanvas(canvas) {
    canvas.addEventListener('click', function (event) {
      if (!S.active) return;
      var p = canvasPoint(event);
      if (hitArrow(p)) { toggleDirection(); return; }
      if (S.mode === 'area') {
        if (S.areaClosed) return;
        if (S.area.length >= 3 && distance(p, S.area[0]) <= 10) { closeArea(); return; }
        if (S.area.length >= 64) return;
        if (!S.area.length || distance(p, S.area[S.area.length - 1]) >= 2) S.area.push(p);
        draw();
      } else {
        if (S.line.length >= 2) S.line = [];
        S.line.push(p);
        if (S.line.length === 2) snapLine();
        draw(); syncLive();
      }
    });

    canvas.addEventListener('mousemove', function (event) {
      if (!S.active) return;
      var p = canvasPoint(event);
      if (S.mode === 'area' && !S.areaClosed && S.area.length) { S.preview = p; draw(); }
      else if (S.mode === 'line' && S.line.length === 1) { S.preview = p; draw(); }
      else if (S.preview) { S.preview = null; draw(); }
    });

    canvas.addEventListener('mouseleave', function () {
      if (S.preview) { S.preview = null; draw(); }
    });

    canvas.addEventListener('dblclick', function (event) {
      if (!S.active || S.mode !== 'area') return;
      event.preventDefault();
      closeArea();
    });

    canvas.addEventListener('contextmenu', function (event) {
      if (!S.active || S.mode !== 'area') return;
      event.preventDefault();
      closeArea();
    });
  }

  // ---------------------------------------------------------------- 与页面数据互通

  function applyToVm(vm) {
    if (!vm || !vm.form) return;
    var scale = scaleOf(vm);
    if (S.areaClosed && S.area.length >= 3) {
      vm.mark_lists = [S.area.map(function (p) {
        return { x: Math.round(p.x * scale.x), y: Math.round(p.y * scale.y), type: '告警区域', color: '#FF0000' };
      })];
    }
    if (S.line.length === 2) {
      var p1 = { x: Math.round(S.line[0].x * scale.x), y: Math.round(S.line[0].y * scale.y) };
      var p2 = { x: Math.round(S.line[1].x * scale.x), y: Math.round(S.line[1].y * scale.y) };
      vm.form.cross_line = { area_type: 'line', points: [p1, p2], p1: p1, p2: p2, direction: S.dir };
    }
    vm.drawLineOpen = true;
    vm.form.draw_type = '2';

    // 闸机尾随必须同时有区域和警戒线，缺一个就提示（不阻断保存）
    if ((!S.areaClosed || S.area.length < 3 || S.line.length !== 2) &&
        typeof vm.$message === 'function' && !vm.__tgWarned) {
      vm.__tgWarned = true;
      vm.$message({ type: 'warning', message: '闸机尾随：请先画完区域（≥3 点）并画一条警戒线' });
      setTimeout(function () { vm.__tgWarned = false; }, 1500);
    }
  }

  // 只在“闸机尾随”下同步；其它类型绝不碰 form
  function syncLive() {
    if (!S.vm || !S.active) return;
    if (!isTailgate(S.vm)) return;
    var scale = scaleOf(S.vm);
    if (S.line.length === 2) {
      var p1 = { x: Math.round(S.line[0].x * scale.x), y: Math.round(S.line[0].y * scale.y) };
      var p2 = { x: Math.round(S.line[1].x * scale.x), y: Math.round(S.line[1].y * scale.y) };
      S.vm.form.cross_line = { area_type: 'line', points: [p1, p2], p1: p1, p2: p2, direction: S.dir };
    }
  }

  function patchVm(vm) {
    if (vm.__tgHandleDataWrapped) return;
    var original = vm.handleData;
    vm.handleData = function () {
      var result = original.apply(this, arguments);
      // 只要当前是“闸机尾随”且已经画过东西，就把几何写回页面自己的保存字段。
      // 不依赖 S.active：界面短暂重绘时也不至于把旧区域保存出去。
      if (isTailgate(this) && this === S.vm && (S.areaClosed || S.line.length === 2)) applyToVm(this);
      return result;
    };
    vm.__tgHandleDataWrapped = true;
  }

  // 旧数据可能是 left / right（原计数线方向），按“IN 朝哪边”折算成 up / down
  function legacyDirection(obj, points) {
    var d = txt(obj.direction).toLowerCase();
    if (points.length !== 2) return 'down';
    var a = points[0], b = points[1];
    var dx = b.x - a.x, dy = b.y - a.y, len = Math.sqrt(dx * dx + dy * dy) || 1;
    var inVec = d === 'right' ? { x: dy / len, y: -dx / len } : { x: -dy / len, y: dx / len };
    var n = inwardNormal();
    return (inVec.x * n.x + inVec.y * n.y) >= 0 ? 'down' : 'up';
  }

  function restoreFromVm(vm) {
    var form = vm.form || {};
    var rawLine = typeof form.cross_line_area === 'string' ? form.cross_line_area
      : JSON.stringify(form.cross_line_area || '');
    var rawArea = typeof form.conf_area === 'string' ? form.conf_area
      : JSON.stringify(form.conf_area || '');
    var sig = [form.id || '', form.Algorithm_library_id || '', rawLine, rawArea, txt(vm.resolution)].join('~');
    if (sig === S.sig) return;
    S.sig = sig;

    var scale = scaleOf(vm);
    S.area = []; S.areaClosed = false; S.line = []; S.dir = 'down'; S.preview = null;

    // 区域
    var area = parseJSON(rawArea);
    if (area && Array.isArray(area.points)) area = [area.points];
    if (area && !Array.isArray(area[0])) area = [area];
    if (Array.isArray(area)) {
      for (var i = 0; i < area.length; i++) {
        var ring = area[i];
        if (!Array.isArray(ring) || ring.length < 3) continue;
        var poly = [];
        for (var j = 0; j < ring.length; j++) {
          var p = pointOf(ring[j]);
          if (p) poly.push({ x: p.x / scale.x, y: p.y / scale.y });
        }
        if (poly.length >= 3) { S.area = poly; S.areaClosed = true; break; }
      }
    }

    // 警戒线 + 方向
    var line = parseJSON(rawLine);
    if (line && typeof line === 'object') {
      var source = Array.isArray(line.points) ? line.points : (line.p1 && line.p2 ? [line.p1, line.p2] : []);
      if (Array.isArray(source) && source.length >= 2) {
        var a = pointOf(source[0]), b = pointOf(source[source.length - 1]);
        if (a && b) {
          S.line = [{ x: a.x / scale.x, y: a.y / scale.y }, { x: b.x / scale.x, y: b.y / scale.y }];
          var d = txt(line.direction).toLowerCase();
          if (d === 'up' || d === 'down') S.dir = d;
          else if (d === 'left' || d === 'right') S.dir = legacyDirection(line, S.line);
        }
      }
    }
    draw(); updateToolbar();
  }

  // ---------------------------------------------------------------- 主循环

  function tick() {
    var route = (location.hash || '') + ' ' + (location.pathname || '');
    var onPage = /#\/sfgl_child/.test(route) || /\/sfgl_child(?:s)?(?:[\/?#]|$)/.test(location.pathname || '');
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
    if (!isTailgate(vm)) {
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

  // 排障用：控制台执行 __tailgateRegion.state() 可看当前绘制状态
  window.__tailgateRegion = {
    state: function () {
      return {
        active: S.active, mode: S.mode, area: S.area.length, areaClosed: S.areaClosed,
        line: S.line.length, dir: S.dir, sample: S.line.slice(0, 2)
      };
    }
  };

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
