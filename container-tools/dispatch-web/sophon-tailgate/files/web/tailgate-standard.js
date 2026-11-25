/* 尾随算法：标准“智能算法配置”页的箭头交互补丁（仅对 闸机尾随 模板生效）
 *
 * 行为（只在选中尾随算法时激活，人数统计等其它算法完全不受影响）：
 *   1. 画完警戒线后，线中点自动绘制一个方向箭头（红色）；
 *   2. 点箭头即可翻转方向，不新增顶点；
 *   3. 画布上原来的 IN / OUT 标签与双向箭头不再绘制，改为 “里 ↓ down / 外 ↑ up”；
 *   4. 提交时把 cross_line_area 改写为 {area_type:'line', points, p1, p2, direction:'up'|'down'}，
 *      并去掉 in_point / out_point 字段。
 *
 * 注入位置：frontend/index.html，脚本挂载后自行轮询 Vue 组件实例（Vue 2）。
 */
(function () {
  'use strict';
  var LIB_IDS = { '100': 1, '101': 1 };      // 闸机尾随算法库 id
  var TEMPLATE_IDS = { '100': 1 };           // 闸机尾随模板大类 id
  var NAME_RE = /闸机尾随/;
  var ATTACHED = '__tgArrowAttached';
  var UP = '__tgUp';

  function log() {
    try { console.log.apply(console, ['[tailgate]'].concat([].slice.call(arguments))); } catch (e) {}
  }

  function str(v) { return v === undefined || v === null ? '' : String(v); }

  /* ---------- 组件定位 ---------- */
  function walk(vm, out, depth) {
    if (!vm || depth > 20) return;
    try {
      var refs = vm.$refs || {};
      var name = vm.$options && vm.$options.name;
      if ((name === 'sfgl_child' || refs.mycanvas) && refs.mycanvas && vm.$data && ('lineDirection' in vm.$data)) {
        out.push(vm);
      }
      var kids = vm.$children || [];
      for (var i = 0; i < kids.length; i++) walk(kids[i], out, depth + 1);
    } catch (e) {}
  }

  function allVms() {
    var out = [];
    try {
      var rootEl = document.querySelector('#app') || document.body;
      var root = rootEl && rootEl.__vue__;
      if (root) walk(root, out, 0);
    } catch (e) {}
    return out;
  }

  /* ---------- 是否尾随配置 ---------- */
  function isTailgate(vm) {
    try {
      var f = (vm && vm.form) || {};
      if (LIB_IDS[str(f.Algorithm_library_id)]) return true;
      if (TEMPLATE_IDS[str(f.model_template_config_id)]) return true;
      var name = str(f.model_name) + str(f.algorithm_name) + str(f.template_name) + str(f.conf_name);
      if (NAME_RE.test(name)) return true;
      // 回显的老配置：cross_line_area 里已经带 direction=up/down
      var cl = f.cross_line || {};
      if (cl.direction === 'up' || cl.direction === 'down') return true;
    } catch (e) {}
    return false;
  }

  /* ---------- 方向状态 ---------- */
  function isUp(vm) {
    if (typeof vm[UP] === 'boolean') return vm[UP];
    var d = '';
    try { d = str((vm.form && vm.form.cross_line && vm.form.cross_line.direction) || '').toLowerCase(); } catch (e) {}
    if (d === 'up') return true;
    if (d === 'down') return false;
    // 平台原生 left/right：left 视为向外(up)，right 视为向里(down)
    return str(vm.lineDirection).toLowerCase() === 'left';
  }

  function setUp(vm, up) {
    vm[UP] = !!up;
    try {
      if (vm.form && vm.form.cross_line) {
        vm.form.cross_line.direction = up ? 'up' : 'down';
      }
    } catch (e) {}
  }

  /* ---------- 几何 ---------- */
  function linePoints(vm) {
    var pts = [];
    try {
      var list = vm.polylinePoints || [];
      for (var i = 0; i < list.length; i++) {
        var p = list[i];
        if (p && isFinite(p.x) && isFinite(p.y)) pts.push({ x: +p.x, y: +p.y });
      }
      if (pts.length < 2) {
        var cl = (vm.form && vm.form.cross_line) || {};
        if (cl.p1 && cl.p2) {
          var tx = vm.timesX || 1, ty = vm.timesY || 1;
          pts = [
            { x: +cl.p1.x / tx, y: +cl.p1.y / ty },
            { x: +cl.p2.x / tx, y: +cl.p2.y / ty }
          ];
        }
      }
    } catch (e) {}
    return pts;
  }

  function arrowGeom(vm, cv) {
    var pts = linePoints(vm);
    if (pts.length < 2) return null;
    var W = cv.width || 640, H = cv.height || 360;
    var mid = { x: (pts[0].x + pts[pts.length - 1].x) / 2, y: (pts[0].y + pts[pts.length - 1].y) / 2 };
    var up = isUp(vm);
    var len = Math.max(30, Math.min(60, H * 0.13));
    var tip = { x: mid.x, y: mid.y + (up ? -len : len) };
    tip.x = Math.max(8, Math.min(W - 8, tip.x));
    tip.y = Math.max(8, Math.min(H - 8, tip.y));
    // 箭头贴边时中点也要在画布内
    mid.x = Math.max(8, Math.min(W - 8, mid.x));
    mid.y = Math.max(8, Math.min(H - 8, mid.y));
    return { mid: mid, tip: tip, up: up, pts: pts, W: W, H: H };
  }

  /* ---------- 重绘（覆盖原生 IN/OUT 绘制） ---------- */
  function redraw(vm) {
    var cv = vm.$refs && vm.$refs.mycanvas;
    if (!cv) return false;
    if (!isTailgate(vm)) return false;
    if (vm.isDrawingPolyline) return false;      // 正在拖拽画线时让原生渲染，避免打断手感
    if (!vm.drawLineOpen || !vm.isPolylineCompleted) return false;  // 只在“线已画完”后接管渲染
    var ctx = cv.getContext && cv.getContext('2d');
    if (!ctx) return false;
    var W = cv.width || 640, H = cv.height || 360;

    ctx.clearRect(0, 0, W, H);

    // 1) 检测框（沿用配置里的颜色，缺省红色）
    var polys = vm.mark_list || [];
    for (var i = 0; i < polys.length; i++) {
      var poly = polys[i];
      if (!poly || poly.length < 3) continue;
      ctx.beginPath();
      ctx.strokeStyle = (poly[0] && poly[0].color) || '#ff2d2d';
      ctx.lineWidth = 2;
      ctx.moveTo(+poly[0].x, +poly[0].y);
      for (var j = 1; j < poly.length; j++) ctx.lineTo(+poly[j].x, +poly[j].y);
      ctx.closePath();
      ctx.stroke();
    }

    var g = arrowGeom(vm, cv);
    if (!g) return true;

    // 2) 警戒线（黄色）
    ctx.beginPath();
    ctx.strokeStyle = '#ffd400';
    ctx.lineWidth = 2;
    ctx.moveTo(g.pts[0].x, g.pts[0].y);
    for (var k = 1; k < g.pts.length; k++) ctx.lineTo(g.pts[k].x, g.pts[k].y);
    ctx.stroke();
    ctx.fillStyle = '#ffd400';
    for (var m = 0; m < g.pts.length; m++) {
      ctx.beginPath();
      ctx.arc(g.pts[m].x, g.pts[m].y, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    // 3) 方向箭头 + 文案（去掉 IN/OUT）
    var mx = g.mid.x, my = g.mid.y, tx = g.tip.x, ty = g.tip.y;
    ctx.beginPath();
    ctx.arc(mx, my, 26, 0, Math.PI * 2);
    ctx.strokeStyle = 'rgba(255,59,48,.35)';
    ctx.lineWidth = 1;
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(mx, my);
    ctx.lineTo(tx, ty);
    ctx.strokeStyle = '#ff3b30';
    ctx.lineWidth = 4;
    ctx.stroke();

    var ang = Math.atan2(ty - my, tx - mx);
    ctx.beginPath();
    ctx.moveTo(tx, ty);
    ctx.lineTo(tx - 14 * Math.cos(ang - 0.42), ty - 14 * Math.sin(ang - 0.42));
    ctx.lineTo(tx - 14 * Math.cos(ang + 0.42), ty - 14 * Math.sin(ang + 0.42));
    ctx.closePath();
    ctx.fillStyle = '#ff3b30';
    ctx.fill();

    ctx.font = 'bold 14px Arial';
    ctx.textAlign = 'left';
    ctx.fillStyle = '#ff3b30';
    var label = g.up ? '外 ↑ up' : '里 ↓ down';
    var lx = Math.min(W - 76, mx + 32), ly = Math.max(16, Math.min(H - 8, my + 5));
    ctx.fillText(label, lx, ly);
    return true;
  }

  /* ---------- 交互：点箭头翻转 ---------- */
  function canvasPoint(cv, ev) {
    var r = cv.getBoundingClientRect();
    var sx = (cv.width || 640) / (r.width || 1);
    var sy = (cv.height || 360) / (r.height || 1);
    return { x: (ev.clientX - r.left) * sx, y: (ev.clientY - r.top) * sy };
  }

  function hitArrow(vm, cv, p) {
    var g = arrowGeom(vm, cv);
    if (!g) return false;
    var d1 = Math.hypot(p.x - g.mid.x, p.y - g.mid.y);
    var d2 = Math.hypot(p.x - g.tip.x, p.y - g.tip.y);
    return d1 <= 34 || d2 <= 30;
  }

  function attach(vm) {
    if (!vm) return;
    var cv = vm.$refs && vm.$refs.mycanvas;
    if (!cv || !cv.addEventListener) return;
    if (vm[ATTACHED] && vm.__tgCanvas === cv) return;   // 同一个 canvas 已挂过
    vm[ATTACHED] = true;
    vm.__tgCanvas = cv;
    var handler = function (ev) {
      try {
        if (!isTailgate(vm)) return;
        var p = canvasPoint(cv, ev);
        if (!hitArrow(vm, cv, p)) return;
        setUp(vm, !isUp(vm));
        ev.stopImmediatePropagation();
        ev.preventDefault();
        redraw(vm);
        try { vm.$forceUpdate && vm.$forceUpdate(); } catch (e) {}
      } catch (e) {}
    };
    cv.addEventListener('mousedown', handler, true);
    cv.addEventListener('click', handler, true);
    log('canvas hooked', cv.width, cv.height);
  }

  /* ---------- 提交改写 ---------- */
  function rewriteCross(body, force) {
    if (typeof body !== 'string' || body.indexOf('cross_line_area') < 0) return body;
    var isTg = !!force;
    var s = body;
    try { s = decodeURIComponent(body.replace(/\+/g, ' ')); } catch (e) { s = body; }
    if (/"Algorithm_library_id"\s*:\s*"?(\d+)"?/.test(s)) {
      var m0 = /"Algorithm_library_id"\s*:\s*"?(\d+)"?/.exec(s);
      if (m0 && LIB_IDS[m0[1]]) isTg = true;
    }
    if (!isTg && /(^|[&"])Algorithm_library_id=?"?(\d+)/.test(s)) {
      var m1 = /(?:^|[&"])Algorithm_library_id=?"?(\d+)/.exec(s);
      if (m1 && LIB_IDS[m1[1]]) isTg = true;
    }
    if (!isTg && /"model_template_config_id"\s*:\s*"?(\d+)"?/.test(s)) {
      var m2 = /"model_template_config_id"\s*:\s*"?(\d+)"?/.exec(s);
      if (m2 && TEMPLATE_IDS[m2[1]]) isTg = true;
    }
    if (!isTg && NAME_RE.test(s)) isTg = true;
    if (!isTg) return body;

    var up = null;
    try {
      var vms = allVms();
      for (var i = 0; i < vms.length; i++) {
        if (isTailgate(vms[i]) && vms[i].$refs && vms[i].$refs.mycanvas) { up = isUp(vms[i]); break; }
      }
    } catch (e) {}

    function fixLine(cl) {
      if (typeof cl === 'string') {
        try { cl = JSON.parse(cl.replace(/'/g, '"')); } catch (e) { return null; }
      }
      if (!cl || typeof cl !== 'object') return null;
      var pts = cl.points || (cl.p1 && cl.p2 ? [cl.p1, cl.p2] : null);
      if (!pts || pts.length < 2) return null;
      var dir = up === null ? (cl.direction === 'up' ? 'up' : 'down') : (up ? 'up' : 'down');
      return {
        area_type: 'line',
        points: pts,
        p1: pts[0],
        p2: pts[pts.length - 1],
        direction: dir
      };
    }

    function fixValue(raw) {
      var obj;
      try { obj = JSON.parse(raw); } catch (e) { return raw; }
      if (!obj || typeof obj !== 'object') return raw;
      var out = fixLine(obj.cross_line_area);
      if (!out) return raw;
      obj.cross_line_area = JSON.stringify(out);
      return JSON.stringify(obj);
    }

    // JSON 请求体
    if (/^\s*\{/.test(body)) {
      var fixed = fixValue(body);
      if (fixed !== body) log('rewrite json body ->', fixed.slice(0, 200));
      return fixed;
    }
    // 表单编码请求体
    var mForm = /(^|&)cross_line_area=([^&]*)/.exec(body);
    if (!mForm) return body;
    var rawVal = decodeURIComponent(mForm[2].replace(/\+/g, ' '));
    var parsedVal;
    try { parsedVal = JSON.parse(rawVal); } catch (e) { return body; }
    var lineOut = fixLine(parsedVal);
    if (!lineOut) return body;
    log('rewrite form body');
    return body.replace(mForm[0], mForm[1] + 'cross_line_area=' + encodeURIComponent(JSON.stringify(lineOut)));
  }

  function hookXHR() {
    var X = window.XMLHttpRequest;
    if (!X || X.prototype.__tgHooked) return;
    X.prototype.__tgHooked = true;
    var open = X.prototype.open, send = X.prototype.send;
    X.prototype.open = function (m, u) {
      try { this.__tgUrl = u; } catch (e) {}
      return open.apply(this, arguments);
    };
    X.prototype.send = function (body) {
      try {
        if (this.__tgUrl && /algorithm_(add|update|edit)/i.test(str(this.__tgUrl))) {
          if (typeof body === 'string') {
            body = rewriteCross(body);
          } else if (typeof URLSearchParams !== 'undefined' && body instanceof URLSearchParams) {
            var s = body.toString();
            var ns = rewriteCross(s);
            if (ns !== s) body = ns;
          } else if (typeof FormData !== 'undefined' && body instanceof FormData && body.get && body.set) {
            var v = body.get('cross_line_area');
            var forceTg = !!(LIB_IDS[str(body.get('Algorithm_library_id'))]
              || TEMPLATE_IDS[str(body.get('model_template_config_id'))]
              || NAME_RE.test(str(body.get('conf_name')) + str(body.get('algorithm_name'))));
            if (typeof v === 'string' && v) {
              var wrapper = 'cross_line_area=' + encodeURIComponent(v);
              var fixed = rewriteCross(wrapper, forceTg);
              if (fixed !== wrapper) {
                var m = /cross_line_area=([\s\S]*)$/.exec(fixed);
                if (m) body.set('cross_line_area', decodeURIComponent(m[1]));
              }
            }
          }
        }
      } catch (e) {}
      return send.call(this, body);
    };
  }

  function hookFetch() {
    if (!window.fetch || window.fetch.__tgHooked) return;
    var of = window.fetch;
    var nf = function (input, init) {
      try {
        if (init && typeof init.body === 'string' && /algorithm_(add|update|edit)/i.test(str(input && (input.url || input)))) {
          init = Object.assign({}, init, { body: rewriteCross(init.body) });
        }
      } catch (e) {}
      return of.call(this, input, init);
    };
    nf.__tgHooked = true;
    window.fetch = nf;
  }

  /* ---------- 轮询挂载 ---------- */
  var timer = null;
  function tick() {
    var vms = allVms();
    for (var i = 0; i < vms.length; i++) {
      var vm = vms[i];
      attach(vm);
      if (vm[ATTACHED] && isTailgate(vm)) {
        try { redraw(vm); } catch (e) {}
      }
    }
  }

  function start() {
    hookXHR();
    hookFetch();
    if (timer) return;
    timer = setInterval(function () { try { tick(); } catch (e) {} }, 150);
    log('patch active');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
  window.__tailgateStandard = { rewrite: rewriteCross, isTailgate: isTailgate };
})();
