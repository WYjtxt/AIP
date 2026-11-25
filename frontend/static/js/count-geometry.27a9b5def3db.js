/* boarding-direction-v1 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PlatformCountGeometry = api;
})(typeof window !== 'undefined' ? window : null, function () {
  'use strict';
  function parse(raw) {
    if (typeof raw === 'string') {
      try { return JSON.parse(raw); } catch (_) {
        try { return JSON.parse(raw.replace(/'/g, '"')); } catch (ignored) { return null; }
      }
    }
    return raw;
  }
  function point(raw) {
    var x = Number(Array.isArray(raw) ? raw[0] : raw && raw.x);
    var y = Number(Array.isArray(raw) ? raw[1] : raw && raw.y);
    return Number.isFinite(x) && Number.isFinite(y) ? [x, y] : null;
  }
  function normalized(raw) {
    var value = parse(raw);
    if (!value || typeof value !== 'object') return null;
    var source = Array.isArray(value) ? value : value.points || (value.p1 && value.p2 ? [value.p1, value.p2] : []);
    if (!Array.isArray(source)) return null;
    var points = source.map(point);
    if (points.some(function (p) { return !p; })) return null;
    var polygon = value.scene === 'boarding' || value.area_type === 'polygon';
    if (polygon && points.length > 1 && points[0][0] === points[points.length - 1][0] && points[0][1] === points[points.length - 1][1]) points.pop();
    if (points.length < (polygon ? 3 : 2)) return null;
    return { polygon: polygon, points: points, boarding_direction: value.boarding_direction === 'outward' ? 'outward' : 'inward',
      direction: value.direction === 'left' || value.direction === 'right' ? value.direction : Object.prototype.hasOwnProperty.call(value, 'scene') ? 'left' : 'right' };
  }
  function inside(p, points) {
    var result = false;
    points.forEach(function (a, i) {
      var b = points[(i + 1) % points.length];
      if ((a[1] > p[1]) !== (b[1] > p[1]) && p[0] < (b[0] - a[0]) * (p[1] - a[1]) / (b[1] - a[1]) + a[0]) result = !result;
    });
    return result;
  }
  // Match Python's nearest-even rounding for rasterized algorithm arrows.
  function round(value) {
    var low = Math.floor(value), part = value - low;
    return Math.abs(part - .5) < 1e-10 ? (low % 2 ? low + 1 : low) : Math.round(value);
  }
  function arrowPlan(mid, normal, length) {
    return { mid: mid.map(round), in_tip: [mid[0] + normal[0] * length, mid[1] + normal[1] * length].map(round),
      out_tip: [mid[0] - normal[0] * length, mid[1] - normal[1] * length].map(round),
      in_dir: normal, out_dir: [-normal[0], -normal[1]] };
  }
  function polygonPlan(points, size) {
    var area = 0, total = 0;
    var edges = points.map(function (a, i) {
      var b = points[(i + 1) % points.length], dx = b[0] - a[0], dy = b[1] - a[1], length = Math.hypot(dx, dy);
      area += a[0] * b[1] - b[0] * a[1]; total += length;
      return { a: a, b: b, dx: dx, dy: dy, length: length, index: i };
    }).filter(function (e) { return e.length > 0; });
    if (!area) return null;
    edges.sort(function (a, b) { return b.length - a.length || a.index - b.index; });
    var fallback = null;
    for (var e = 0; e < edges.length; e++) {
      var edge = edges[e], sign = area > 0 ? 1 : -1;
      var normal = [-edge.dy / edge.length * sign, edge.dx / edge.length * sign];
      var mid = [(edge.a[0] + edge.b[0]) / 2, (edge.a[1] + edge.b[1]) / 2];
      var length = Math.max(30, Math.min(total * .05, 140));
      for (var attempt = 0; attempt < 10 && length >= 2; attempt++, length /= 2) {
        var inward = [mid[0] + normal[0] * length, mid[1] + normal[1] * length];
        var outward = [mid[0] - normal[0] * length, mid[1] - normal[1] * length];
        if (inside(inward, points) && !inside(outward, points)) {
          var plan = arrowPlan(mid, normal, length); plan.kind = 'polygon';
          if (!fallback) fallback = plan;
          if (!size) return plan;
          var margin = Math.min(24, size[0] * .04, size[1] * .04);
          if ([inward, outward].every(function (p) { return p[0] >= margin && p[0] <= size[0] - margin && p[1] >= margin && p[1] <= size[1] - margin; })) return plan;
        }
      }
    }
    return fallback;
  }
  function build(raw, size) {
    var geometry = normalized(raw);
    if (!geometry) return null;
    var points = geometry.points;
    if (geometry.polygon) {
      geometry.plan = polygonPlan(points, size);
      if (geometry.plan && geometry.boarding_direction === 'outward') {
        var plan = geometry.plan, tip = plan.in_tip, direction = plan.in_dir;
        plan.in_tip = plan.out_tip; plan.out_tip = tip;
        plan.in_dir = plan.out_dir; plan.out_dir = direction;
      }
    }
    else {
      var best = null, total = 0;
      points.slice(1).forEach(function (b, i) {
        var a = points[i], dx = b[0] - a[0], dy = b[1] - a[1], length = Math.hypot(dx, dy);
        total += length;
        if (length > 0 && (!best || length > best.length)) best = { a: a, b: b, dx: dx, dy: dy, length: length };
      });
      if (best) {
        var sign = geometry.direction === 'left' ? -1 : 1;
        geometry.plan = arrowPlan([(best.a[0] + best.b[0]) / 2, (best.a[1] + best.b[1]) / 2],
          [best.dy / best.length * sign, -best.dx / best.length * sign], Math.max(30, Math.min(total * .05, 140)));
      }
    }
    return geometry;
  }
  function dimensions(raw) {
    if (Array.isArray(raw) && raw.length === 2 && raw[0] > 0 && raw[1] > 0) return raw.map(Number);
    var match = String(raw || '').match(/^\s*(\d+)\s*[xX×*,]\s*(\d+)\s*$/);
    return match && +match[1] > 0 && +match[2] > 0 ? [+match[1], +match[2]] : null;
  }
  function render(canvas, regions, raw, resolution, options) {
    options = options || {};
    var size = dimensions(resolution), geometry = build(raw, size);
    if (!size || (!geometry && !options.allowEmpty)) return false;
    if (!geometry) {
      var partial = parse(raw) || {}, draft = Array.isArray(partial.points) ? partial.points.map(point) : [];
      geometry = {polygon:partial.scene === 'boarding' || partial.area_type === 'polygon',
        points:draft.some(function (p) { return !p; }) ? [] : draft};
    }
    var width = options.width || canvas.width, height = options.height || canvas.height;
    canvas.width = width; canvas.height = height;
    var context = canvas.getContext('2d'), sx = width / size[0], sy = height / size[1];
    var projected = function (p) { return [p[0] * sx, p[1] * sy]; };
    var stroke = function (points, closed, color, fill) {
      if (points.length < 2) return;
      context.beginPath(); var first = projected(points[0]); context.moveTo(first[0], first[1]);
      points.slice(1).forEach(function (p) { p = projected(p); context.lineTo(p[0], p[1]); });
      if (closed) context.closePath();
      if (fill) { context.fillStyle = 'rgba(255,0,0,.10)'; context.fill(); }
      context.strokeStyle = color; context.lineWidth = options.thumbnail ? 1.2 : 2; context.stroke();
    };
    if (!geometry.polygon) {
      var decoded = parse(regions);
      (Array.isArray(decoded) ? decoded : []).forEach(function (region) {
        if (!Array.isArray(region) || region.length < 3) return;
        var converted = region.map(point); if (converted.some(function (p) { return !p; })) return;
        stroke(converted, true, region[0].color || '#f00', false);
      });
    }
    stroke(geometry.points, geometry.polygon, geometry.polygon ? '#f00' : '#ffd700', !!options.fillPolygon && geometry.polygon);
    if (options.preview && options.drawing && geometry.points.length) stroke([geometry.points[geometry.points.length - 1], [options.preview.x, options.preview.y]], false, '#ffd700', false);
    if (options.vertices) geometry.points.forEach(function (p, i) {
      p = projected(p); context.fillStyle = '#ffd700'; context.beginPath(); context.arc(p[0], p[1], 3, 0, 2 * Math.PI); context.fill();
      context.font = '12px sans-serif'; context.textAlign = 'left'; context.fillText(String(i + 1), Math.min(width - 15, p[0] + 5), Math.max(14, p[1] - 5));
    });
    var plan = geometry.plan;
    if (plan) [['in_tip', 'in_dir', '#44ff44', 'IN'], ['out_tip', 'out_dir', '#ff4444', 'OUT']].forEach(function (side) {
      var mid = projected(plan.mid), tip = projected(plan[side[0]]), angle = Math.atan2(tip[1] - mid[1], tip[0] - mid[0]);
      context.strokeStyle = side[2]; context.fillStyle = side[2]; context.lineWidth = options.thumbnail ? 1 : 2;
      var head = options.thumbnail ? 3 : 8;
      context.beginPath(); context.moveTo(mid[0], mid[1]); context.lineTo(tip[0], tip[1]);
      context.lineTo(tip[0] - head * Math.cos(angle - .5), tip[1] - head * Math.sin(angle - .5));
      context.moveTo(tip[0], tip[1]); context.lineTo(tip[0] - head * Math.cos(angle + .5), tip[1] - head * Math.sin(angle + .5)); context.stroke();
      if (!options.thumbnail) {
        context.font = 'bold 18px Arial'; context.textAlign = 'center';
        var half = context.measureText(side[3]).width / 2 + 2;
        context.fillText(side[3], Math.max(half, Math.min(width - half, tip[0] + Math.cos(angle) * 20)),
          Math.max(18, Math.min(height - 3, tip[1] + Math.sin(angle) * 20)));
      }
    });
    return true;
  }
  return { normalized: normalized, build: build, polygonPlan: polygonPlan, inside: inside, render: render };
});

/* AiMonitorCountDrawing: preserve saved geometry; start empty drawings on demand. */
(function(root){
  'use strict';
  if(!root || !root.document)return;
  function supported(vm){return !!(vm && typeof vm.initAlgorithmCountingCanvas==='function' &&
    typeof vm.startAlgorithmDetectionDrawing==='function' && typeof vm.finishAlgorithmDetectionDrawing==='function');}
  function countLine(vm){return !!vm.algorithmPeopleCountVisible && !vm.algorithmCountingBoarding;}
  function hasRegions(vm){return (vm.algorithmDetectionRegions||[]).some(function(p){return p.length>=3;});}
  function hasLine(vm){return (vm.algorithmCountingPoints||[]).length>=2;}
  function ready(vm){
    if(!countLine(vm) || vm.algorithmDetectionDrawing || vm.algorithmCountingDrawing)return;
    vm.algorithmCountingDrawMode=hasRegions(vm)?'line':'roi';
  }
  function decorate(vm){
    if(!vm.$el || !vm.$el.querySelectorAll)return;
    vm.$el.querySelectorAll('.algorithm-counting-tools').forEach(function(toolbar){
      toolbar.querySelectorAll('button').forEach(function(button){
        if(countLine(vm) && button.textContent.trim()==='清空检测区域')button.setAttribute('data-count-redundant-clear','');
        else button.removeAttribute('data-count-redundant-clear');
      });
      if(countLine(vm))toolbar.querySelectorAll('[role="status"]').forEach(function(hint){
        if(hint.textContent.indexOf('清空检测区域后按全画面检测。')>=0)
          hint.textContent=hint.textContent.replace('清空检测区域后按全画面检测。','空白配置可直接点击画布绘制检测区域，完成后自动切换警戒线。重绘区域不会清除已有警戒线；取消保留原区域。');
      });
    });
  }
  function bindCanvas(vm){
    if(!vm.$refs)return;
    var canvas=vm.$refs.mycanvas;
    if(!canvas || canvas._countDirectVm===vm)return;
    if(canvas._countDirectHandler)canvas.removeEventListener('mousedown',canvas._countDirectHandler,true);
    var handler=function(event){
      if(event.button!==0 || event.detail>1 || !countLine(vm) || vm._algorithmFormClosed)return;
      if(vm.algorithmCountingDrawMode==='roi'){
        if(!vm.algorithmDetectionDrawing && !hasRegions(vm)){
          vm.algorithmDetectionDraft=[];vm.algorithmDetectionDrawing=true;
          vm._algorithmDetectionAppend=false;vm.algorithmCountingGeometryError='';
        }
      }else if(!vm.algorithmCountingDrawing && !hasLine(vm)){
        vm.algorithmCountingPoints=[];vm.algorithmCountingDrawing=true;vm.algorithmCountingGeometryError='';
      }
      // The original mousedown handler adds this very first point, using its
      // existing canvas-to-source coordinate transform and validity checks.
    };
    canvas._countDirectVm=vm;canvas._countDirectHandler=handler;
    canvas.addEventListener('mousedown',handler,true);vm._countDirectCanvas=canvas;
  }
  function attach(vm){
    if(!supported(vm))return;
    if(!vm._countDirectInstalled){
      vm._countDirectInstalled=true;
      var originalInit=vm.initAlgorithmCountingCanvas;
      vm.initAlgorithmCountingCanvas=function(){
        var result=originalInit.apply(this,arguments),self=this;
        this.$nextTick(function(){bindCanvas(self);decorate(self);});return result;
      };
      var originalRestore=vm.restoreAlgorithmDetectionRegions;
      vm.restoreAlgorithmDetectionRegions=function(){var result=originalRestore.apply(this,arguments);ready(this);return result;};
      var originalFinish=vm.finishAlgorithmDetectionDrawing;
      vm.finishAlgorithmDetectionDrawing=function(){
        var result=originalFinish.apply(this,arguments);
        if(result && countLine(this)){
          this.algorithmCountingDrawMode='line';
          // Do not reset a configured line when an ROI is redrawn or appended.
          this.algorithmCountingDrawing=!hasLine(this);this.initAlgorithmCountingCanvas();
        }
        return result;
      };
      var originalCancel=vm.cancelAlgorithmDetectionDrawing;
      vm.cancelAlgorithmDetectionDrawing=function(){var result=originalCancel.apply(this,arguments);ready(this);this.initAlgorithmCountingCanvas();return result;};
      ready(vm);vm.initAlgorithmCountingCanvas();
    }
    bindCanvas(vm);decorate(vm);
  }
  function cleanup(vm){var c=vm._countDirectCanvas;if(c && c._countDirectVm===vm){c.removeEventListener('mousedown',c._countDirectHandler,true);delete c._countDirectVm;delete c._countDirectHandler;}delete vm._countDirectCanvas;}
  function visit(vm){attach(vm);(vm.$children||[]).forEach(visit);}
  function boot(attempt){
    var el=root.document.getElementById('app'),app=el&&el.__vue__;
    if(!app || !app.$options || !app.$options._base){if(attempt<300)root.setTimeout(function(){boot(attempt+1);},100);return;}
    var style=root.document.createElement('style');style.textContent='.algorithm-counting-tools button[data-count-redundant-clear]{display:none!important}';root.document.head.appendChild(style);
    app.$options._base.mixin({mounted:function(){attach(this);},updated:function(){attach(this);},beforeDestroy:function(){cleanup(this);}});
    visit(app);
  }
  root.AiMonitorCountDrawing={attach:attach,cleanup:cleanup};boot(0);
})(typeof window!=='undefined'?window:null);
