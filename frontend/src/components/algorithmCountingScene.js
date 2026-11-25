// Counting geometry is stored in original video pixels, independent of the editor scale.
export default {
  data() {
    return { algorithmCountingScene: 'uniqueness', algorithmCountingPoints: [],
      algorithmCountingDirection: 'right', algorithmCountingResidenceFrames: 3,
      algorithmCountingDrawing: false, algorithmCountingGeometryError: '' };
  },
  computed: {
    algorithmCountingBoarding() { return this.algorithmCountingScene === 'boarding'; },
    algorithmCountingEnteringLabel() { return this.algorithmCountingBoarding ? '上车人数（累计）' : '进入人数（累计）'; },
    algorithmCountingExitingLabel() { return this.algorithmCountingBoarding ? '下车人数（累计）' : '离开人数（累计）'; },
    algorithmCountingGeometryHint() {
      return this.algorithmCountingBoarding
        ? '沿乘车点边界绘制闭合区域。目标从区域外进入并在区域内消失计上车；反向计下车。原地消失、进入后折返均不计数，短暂遮挡会继续跟踪。'
        : '依次点击绘制直线或连续折线，完成后点击“完成绘制”。绿色进入、红色离开；使用方向按钮切换进出方向。';
    },
  },
  watch: {
    algorithmPeopleCountVisible(visible) { if (visible) this.initAlgorithmCountingCanvas(); },
    resolution(value, previous) { this.rescaleAlgorithmCountingGeometry(value, previous); },
    'form.cross_line_area': {
      immediate: true,
      handler(value) { this.restoreAlgorithmCountingGeometry(value); },
    },
  },
  methods: {
    parseAlgorithmCountingGeometry(raw) {
      if (typeof raw === 'string') {
        try { raw = JSON.parse(raw); } catch (error) {
          // Older records used Python-style quoted dictionaries.
          try { raw = JSON.parse(raw.replace(/'/g, '"')); } catch (ignored) { return {}; }
        }
      }
      if (Array.isArray(raw)) return { points: raw };
      return raw && typeof raw === 'object' ? raw : {};
    },
    restoreAlgorithmCountingGeometry(raw) {
      const value = this.parseAlgorithmCountingGeometry(raw);
      this._algorithmCountingOriginal = value;
      this._algorithmCountingPointResolution = this.form && (this.form.img_resolution || this.form.conf_img_resolution) || this.resolution;
      this.algorithmCountingScene = value.scene === 'boarding' ? 'boarding' : 'uniqueness';
      this._algorithmCountingPreviousScene = this.algorithmCountingScene;
      const points = Array.isArray(value.points) ? value.points : value.p1 && value.p2 ? [value.p1, value.p2] : [];
      this.algorithmCountingPoints = points.map(point => ({ x: Number(point && point.x), y: Number(point && point.y) }));
      if (this.algorithmCountingPoints.length > 2) {
        const first = this.algorithmCountingPoints[0], last = this.algorithmCountingPoints[this.algorithmCountingPoints.length - 1];
        if (first.x === last.x && first.y === last.y && this.algorithmCountingBoarding) this.algorithmCountingPoints.pop();
      }
      const defaultDirection = Object.prototype.hasOwnProperty.call(value, 'scene') ? 'left' : 'right';
      this.algorithmCountingDirection = value.direction === 'left' || value.direction === 'right' ? value.direction : defaultDirection;
      this.algorithmCountingResidenceFrames = value.min_residence_frames == null ? 3 : Number(value.min_residence_frames);
      this.algorithmCountingDrawing = false;
      this.algorithmCountingGeometryError = '';
      this._algorithmCountingDrafts = {};
      if (this.algorithmPeopleCountVisible) this.initAlgorithmCountingCanvas();
    },
    changeAlgorithmCountingScene(scene) {
      const previous = this._algorithmCountingPreviousScene || (scene === 'boarding' ? 'uniqueness' : 'boarding');
      const drafts = this._algorithmCountingDrafts || (this._algorithmCountingDrafts = {});
      drafts[previous] = { points: this.algorithmCountingPoints.map(point => ({ ...point })),
        direction: this.algorithmCountingDirection, residence: this.algorithmCountingResidenceFrames };
      const draft = drafts[scene];
      this.algorithmCountingPoints = draft ? draft.points.map(point => ({ ...point })) : [];
      this.algorithmCountingDirection = draft ? draft.direction : 'right';
      this.algorithmCountingResidenceFrames = draft ? draft.residence : 3;
      this._algorithmCountingPreviousScene = scene;
      this.algorithmCountingDrawing = false;
      this.algorithmCountingGeometryError = this.algorithmCountingPoints.length ? '' : '版本已切换，请为此版本重新绘制计数' + (scene === 'boarding' ? '区域' : '线');
      this._algorithmOperationalEdited = true;
      this.initAlgorithmCountingCanvas();
    },
    algorithmCountingScale() {
      const dimensions = String(this.resolution || this.form && (this.form.img_resolution || this.form.conf_img_resolution) || '').split(/x/i).map(Number);
      return { x: Number.isFinite(dimensions[0]) && dimensions[0] > 0 ? dimensions[0] / 640 : Number(this.timesX) || 1,
        y: Number.isFinite(dimensions[1]) && dimensions[1] > 0 ? dimensions[1] / 360 : Number(this.timesY) || 1 };
    },
    rescaleAlgorithmCountingGeometry(resolution, previous) {
      const before = String(this._algorithmCountingPointResolution || previous || '').split(/x/i).map(Number);
      const after = String(resolution || '').split(/x/i).map(Number);
      if (before.length !== 2 || after.length !== 2 || [...before, ...after].some(value => !Number.isFinite(value) || value <= 0)) return;
      const project = points => points.map(point => ({ x: point.x * after[0] / before[0], y: point.y * after[1] / before[1] }));
      this.algorithmCountingPoints = project(this.algorithmCountingPoints);
      Object.values(this._algorithmCountingDrafts || {}).forEach(draft => { draft.points = project(draft.points); });
      this._algorithmCountingPointResolution = resolution;
      if (this.algorithmPeopleCountVisible) this.initAlgorithmCountingCanvas();
    },
    algorithmCountingGeometryProblem() {
      const rawPoints = this.algorithmCountingPoints, minimum = this.algorithmCountingBoarding ? 3 : 2;
      if (rawPoints.length < minimum) return this.algorithmCountingBoarding ? '乘车点请绘制至少 3 个顶点的闭合区域' : '唯一性检测装置请绘制至少 2 个点的计数线';
      if (rawPoints.length > 64) return '计数图形最多支持 64 个顶点';
      const scale = this.algorithmCountingScale();
      if (rawPoints.some(point => !Number.isFinite(point.x) || !Number.isFinite(point.y) || point.x < 0 || point.y < 0
        || point.x > 640 * scale.x || point.y > 360 * scale.y)) return '计数图形坐标超出当前视频范围，请重新绘制';
      // The inference engine uses integer video pixels; validate that same geometry before saving.
      const points = rawPoints.map(point => ({ x: Math.trunc(point.x), y: Math.trunc(point.y) }));
      if (new Set(points.map(point => point.x + ',' + point.y)).size !== points.length) return '计数图形不能包含落在同一像素的重复顶点';
      if (!Number.isInteger(this.algorithmCountingResidenceFrames) || this.algorithmCountingResidenceFrames < 1 || this.algorithmCountingResidenceFrames > 120) return '驻留确认帧数须为 1–120 的整数';
      if (this.algorithmCountingBoarding) {
        const cross = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
        const inside = (a, b, c) => Math.abs(cross(a, b, c)) < 1e-8 && c.x >= Math.min(a.x, b.x) && c.x <= Math.max(a.x, b.x) && c.y >= Math.min(a.y, b.y) && c.y <= Math.max(a.y, b.y);
        const intersects = (a, b, c, d) => cross(a, b, c) * cross(a, b, d) < 0 && cross(c, d, a) * cross(c, d, b) < 0
          || inside(a, b, c) || inside(a, b, d) || inside(c, d, a) || inside(c, d, b);
        for (let i = 0; i < points.length; i++) for (let j = i + 1; j < points.length; j++) {
          if (j === i + 1 || i === 0 && j === points.length - 1) continue;
          if (intersects(points[i], points[(i + 1) % points.length], points[j], points[(j + 1) % points.length])) return '乘车点区域边界不能相交，请重新绘制';
        }
        const area = points.reduce((sum, point, index) => {
          const next = points[(index + 1) % points.length]; return sum + point.x * next.y - point.y * next.x;
        }, 0);
        if (Math.abs(area) < 1e-8) return '乘车点区域顶点不能全部位于一条直线';
      }
      return '';
    },
    validateAlgorithmCountingGeometry() {
      if (!this.algorithmPeopleCountVisible) return true;
      const problem = this.algorithmCountingGeometryProblem();
      this.algorithmCountingGeometryError = problem;
      if (problem) this.$message({ type: 'warning', message: problem });
      return !problem;
    },
    algorithmCountingPayload() {
      const points = this.algorithmCountingPoints.map(point => ({ x: Math.trunc(point.x), y: Math.trunc(point.y) }));
      return { ...(this._algorithmCountingOriginal || {}), scene: this.algorithmCountingScene,
        area_type: this.algorithmCountingBoarding ? 'polygon' : 'line', points,
        p1: points[0], p2: points[points.length - 1], direction: this.algorithmCountingDirection,
        min_residence_frames: this.algorithmCountingResidenceFrames };
    },
    startAlgorithmCountingDrawing() {
      this.algorithmCountingPoints = [];
      this.algorithmCountingDrawing = true;
      this.algorithmCountingGeometryError = '';
      this._algorithmOperationalEdited = true;
      this.initAlgorithmCountingCanvas();
    },
    finishAlgorithmCountingDrawing() {
      if (!this.validateAlgorithmCountingGeometry()) return false;
      this.algorithmCountingDrawing = false;
      this.initAlgorithmCountingCanvas();
      return true;
    },
    undoAlgorithmCountingPoint() {
      this.algorithmCountingPoints.pop();
      this.algorithmCountingDrawing = true;
      this.algorithmCountingGeometryError = '';
      this._algorithmOperationalEdited = true;
      this.initAlgorithmCountingCanvas();
    },
    reverseAlgorithmCountingDirection() {
      this.algorithmCountingDirection = this.algorithmCountingDirection === 'left' ? 'right' : 'left';
      this._algorithmOperationalEdited = true;
      this.initAlgorithmCountingCanvas();
    },
    initAlgorithmCountingCanvas() {
      this.$nextTick(() => {
        if (this._algorithmFormClosed || !this.algorithmPeopleCountVisible) return;
        const canvas = this.$refs.mycanvas;
        if (!canvas) return;
        canvas.width = 640; canvas.height = 360; canvas.style.cursor = 'crosshair';
        const context = canvas.getContext('2d'), scale = this.algorithmCountingScale();
        const eventPoint = event => {
          const rect = canvas.getBoundingClientRect();
          return { x: Math.round(Math.max(0, Math.min(640, (event.clientX - rect.left) * 640 / rect.width)) * scale.x),
            y: Math.round(Math.max(0, Math.min(360, (event.clientY - rect.top) * 360 / rect.height)) * scale.y) };
        };
        const draw = preview => {
          context.clearRect(0, 0, 640, 360);
          const points = this.algorithmCountingPoints.map(point => ({ x: point.x / scale.x, y: point.y / scale.y }));
          context.strokeStyle = '#ffd700'; context.fillStyle = 'rgba(255,215,0,.12)'; context.lineWidth = 2;
          if (points.length) {
            context.beginPath(); context.moveTo(points[0].x, points[0].y);
            points.slice(1).forEach(point => context.lineTo(point.x, point.y));
            if (preview && this.algorithmCountingDrawing) context.lineTo(preview.x / scale.x, preview.y / scale.y);
            if (this.algorithmCountingBoarding && points.length > 2) { context.closePath(); context.fill(); }
            context.stroke();
          }
          context.font = '12px sans-serif';
          points.forEach((point, index) => {
            context.beginPath(); context.arc(point.x, point.y, 3, 0, Math.PI * 2); context.fillStyle = '#ffd700'; context.fill();
            context.fillText(String(index + 1), Math.min(625, point.x + 5), Math.max(14, point.y - 5));
          });
          if (!this.algorithmCountingBoarding) points.slice(1).forEach((end, index) => {
            const start = points[index], dx = end.x - start.x, dy = end.y - start.y, length = Math.hypot(dx, dy);
            if (!length) return;
            const sign = this.algorithmCountingDirection === 'left' ? -1 : 1;
            const mid = { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 };
            for (const side of [1, -1]) {
              const tip = { x: mid.x + dy / length * 28 * sign * side, y: mid.y - dx / length * 28 * sign * side };
              const angle = Math.atan2(tip.y - mid.y, tip.x - mid.x);
              context.strokeStyle = side === 1 ? '#44ff44' : '#ff6666'; context.fillStyle = context.strokeStyle;
              context.beginPath(); context.moveTo(mid.x, mid.y); context.lineTo(tip.x, tip.y);
              context.lineTo(tip.x - 7 * Math.cos(angle - .5), tip.y - 7 * Math.sin(angle - .5));
              context.moveTo(tip.x, tip.y); context.lineTo(tip.x - 7 * Math.cos(angle + .5), tip.y - 7 * Math.sin(angle + .5)); context.stroke();
              context.fillText(side === 1 ? '进入' : '离开', Math.max(0, Math.min(610, tip.x)), Math.max(14, Math.min(352, tip.y - 6)));
            }
          });
        };
        canvas.onclick = null; canvas.onmouseup = null; canvas.oncontextmenu = event => event.preventDefault();
        canvas.onmousedown = event => {
          if (event.button !== 0 || event.detail > 1 || !this.algorithmCountingDrawing) return;
          if (this.algorithmCountingPoints.length >= 64) { this.$message.warning('最多支持 64 个顶点'); return; }
          const point = eventPoint(event), last = this.algorithmCountingPoints[this.algorithmCountingPoints.length - 1];
          if (!last || last.x !== point.x || last.y !== point.y) this.algorithmCountingPoints.push(point);
          this._algorithmOperationalEdited = true; draw();
        };
        canvas.onmousemove = event => { if (this.algorithmCountingDrawing) draw(eventPoint(event)); };
        canvas.onmouseleave = () => draw();
        canvas.ondblclick = event => { event.preventDefault(); if (this.algorithmCountingDrawing) this.finishAlgorithmCountingDrawing(); };
        draw();
      });
    },
  },
};
