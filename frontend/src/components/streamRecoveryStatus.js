// The panel reads recovery status and never changes camera or task settings.
export default {
  data() {
    return { streamRecoverySnapshot: null, streamRecoveryError: '', streamRecoveryLoading: false };
  },
  computed: {
    streamRecoveryCheckedAt() {
      return this.streamRecoverySnapshot ? this.formatStreamRecoveryTime(this.streamRecoverySnapshot.checked_at) : '尚未读取';
    },
    streamRecoveryDetails() {
      const devices = this.streamRecoverySnapshot && this.streamRecoverySnapshot.devices;
      return Array.isArray(devices) ? devices.filter(device => device && device.state !== 'healthy') : [];
    },
    streamRecoverySummary() {
      const summary = this.streamRecoverySnapshot && this.streamRecoverySnapshot.summary || {};
      const devices = this.streamRecoverySnapshot && this.streamRecoverySnapshot.devices || [];
      const count = states => states.reduce((sum, state) => {
        const value = Object.prototype.hasOwnProperty.call(summary, state) ? Number(summary[state]) : devices.filter(device => device.state === state).length;
        return sum + (Number.isFinite(value) && value > 0 ? value : 0);
      }, 0);
      const known = ['healthy', 'observing_video', 'waiting_video', 'proxy_connecting', 'recovering', 'backoff', 'source_auth_paused', 'needs_attention'];
      const unknown = Array.from(new Set([...Object.keys(summary), ...devices.map(device => device.state)])).filter(state => !known.includes(state));
      return { abnormal: count(['waiting_video', 'backoff']), recovering: count(['observing_video', 'proxy_connecting', 'recovering']),
        auth: count(['source_auth_paused']), attention: count(['needs_attention', ...unknown]) };
    },
  },
  created() {
    this._streamRecoveryMounted = false;
    this._streamRecoveryDenied = false;
    this._streamRecoveryGeneration = 0;
    this._streamRecoveryTimer = null;
    this._streamRecoveryController = null;
  },
  mounted() {
    this._streamRecoveryMounted = true;
    this._streamRecoveryVisibility = () => {
      if (typeof document !== 'undefined' && document.hidden) this.stopStreamRecoveryPolling();
      else this.refreshStreamRecoveryStatus();
    };
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', this._streamRecoveryVisibility);
    this.refreshStreamRecoveryStatus();
  },
  beforeDestroy() {
    this._streamRecoveryMounted = false;
    this.stopStreamRecoveryPolling();
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', this._streamRecoveryVisibility);
  },
  watch: {
    '$route.path'() {
      if (this.streamRecoveryPageActive()) this.refreshStreamRecoveryStatus();
      else this.stopStreamRecoveryPolling();
    },
  },
  methods: {
    streamRecoveryPageActive() {
      if (!this._streamRecoveryMounted || this._isDestroyed || this._isBeingDestroyed) return false;
      if (typeof document !== 'undefined' && document.hidden) return false;
      const route = this.$route;
      return !route || !route.path || /\/lmtgl\/?$/.test(route.path);
    },
    formatStreamRecoveryTime(value) {
      const epoch = Number(value);
      if (!Number.isFinite(epoch) || epoch <= 0) return '暂无';
      const date = new Date(epoch < 1000000000000 ? epoch * 1000 : epoch);
      return Number.isNaN(date.getTime()) ? '暂无' : date.toLocaleString('zh-CN', { hour12: false });
    },
    streamRecoveryStateLabel(state) {
      return { healthy: '正常', observing_video: '画面观察中', waiting_video: '等待画面', proxy_connecting: '连接中',
        recovering: '恢复中', backoff: '等待重试', source_auth_paused: '认证待维护', needs_attention: '需要关注' }[state] || '待确认';
    },
    streamRecoveryReasonLabel(device) {
      const known = { account_maintenance: '账号认证需要维护，已暂停自动尝试', authentication_failed: '账号认证未通过，请维护账号',
        source_authentication_failed: '源设备账号认证未通过，请维护账号', source_unavailable: '源设备暂时不可用',
        waiting_video: '等待源设备恢复画面', no_video: '暂未检测到有效画面', no_frames: '暂未检测到有效画面',
        retry_backoff: '等待下次自动尝试', recovering: '正在恢复画面', proxy_connecting: '正在连接源设备',
        needs_attention: '多次尝试后仍未恢复，需要人工查看' };
      if (known[device.reason]) return known[device.reason];
      return { healthy: '画面正常', observing_video: '正在确认画面稳定性', waiting_video: '等待源设备恢复画面',
        proxy_connecting: '正在连接源设备', recovering: '正在恢复画面', backoff: '等待下次自动尝试',
        source_auth_paused: '账号认证需要维护，已暂停自动尝试', needs_attention: '请查看源设备和网络状态' }[device.state] || '状态待进一步确认';
    },
    streamRecoveryNextAttempt(device) {
      if (device.state === 'source_auth_paused') return '账号维护后再尝试';
      return this.formatStreamRecoveryTime(device.next_retry);
    },
    stopStreamRecoveryPolling() {
      this._streamRecoveryGeneration++;
      clearTimeout(this._streamRecoveryTimer); this._streamRecoveryTimer = null;
      if (this._streamRecoveryController) this._streamRecoveryController.abort();
      this._streamRecoveryController = null;
      this.streamRecoveryLoading = false;
    },
    pauseStreamRecoveryPolling(code) {
      this._streamRecoveryDenied = true;
      this.streamRecoveryError = Number(code) === 401 ? '登录状态已失效，已暂停读取后台恢复状态' : '没有读取后台恢复状态的权限，已暂停自动刷新';
      this.stopStreamRecoveryPolling();
    },
    refreshStreamRecoveryStatus() {
      if (!this.streamRecoveryPageActive() || this._streamRecoveryDenied || this._streamRecoveryController) return Promise.resolve(false);
      clearTimeout(this._streamRecoveryTimer); this._streamRecoveryTimer = null;
      const generation = this._streamRecoveryGeneration;
      const current = () => generation === this._streamRecoveryGeneration && this.streamRecoveryPageActive();
      const controller = new AbortController(); this._streamRecoveryController = controller;
      this.streamRecoveryLoading = true;
      return this.$http.get(this.$url.url_5000 + '/zlmediakit_view/recovery/status', { signal: controller.signal, timeout: 8000 }).then(response => {
        if (!current()) return false;
        const body = response && response.data;
        if (body && [401, 403].includes(Number(body.code))) { this.pauseStreamRecoveryPolling(body.code); return false; }
        const data = body && body.data;
        if (!body || Number(body.code) !== 200 || !data || typeof data.enabled !== 'boolean' || !Array.isArray(data.devices)
          || !data.summary || typeof data.summary !== 'object' || Array.isArray(data.summary)) throw new Error('Unavailable recovery status');
        this.streamRecoverySnapshot = data;
        this.streamRecoveryError = '';
        return true;
      }).catch(error => {
        if (!current()) return false;
        const code = error && error.response && error.response.status;
        if ([401, 403].includes(Number(code))) this.pauseStreamRecoveryPolling(code);
        else this.streamRecoveryError = '后台恢复状态暂时不可用，保留最近结果；数据可能已过期';
        return false;
      }).finally(() => {
        if (this._streamRecoveryController === controller) this._streamRecoveryController = null;
        if (generation === this._streamRecoveryGeneration) this.streamRecoveryLoading = false;
        if (current() && !this._streamRecoveryDenied) this._streamRecoveryTimer = setTimeout(() => this.refreshStreamRecoveryStatus(), 10000);
      });
    },
  },
};
