// Background reads update only runtime fields on existing rows.
export default {
  data() {
    return { algorithmRuntimeHealthUpdatedAt: '', algorithmRuntimeHealthError: '' };
  },
  created() {
    this._algorithmRuntimeMounted = false;
    this._algorithmRuntimeDenied = false;
    this._algorithmRuntimeGeneration = 0;
    this._algorithmRuntimeController = null;
    this._algorithmRuntimeQuery = null;
  },
  mounted() {
    this._algorithmRuntimeMounted = true;
    this._algorithmRuntimeVisibility = () => {
      if (typeof document !== 'undefined' && document.hidden) this.stopAlgorithmRuntimeRefresh();
      else this.scheduleAlgorithmRuntimeRefresh();
    };
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', this._algorithmRuntimeVisibility);
    this.scheduleAlgorithmRuntimeRefresh();
  },
  beforeDestroy() {
    this._algorithmRuntimeMounted = false;
    this.stopAlgorithmRuntimeRefresh();
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', this._algorithmRuntimeVisibility);
  },
  methods: {
    algorithmRuntimePageActive() {
      if (!this._algorithmRuntimeMounted || this._isDestroyed || this._isBeingDestroyed) return false;
      if (typeof document !== 'undefined' && document.hidden) return false;
      const route = this.$route;
      return !route || !route.path || /\/sfgl\/?$/.test(route.path);
    },
    captureAlgorithmRuntimeQuery() {
      this._algorithmRuntimeQuery = { conf_name: this.conf_name, Mine_id: this.mkname,
        algorithm_library_id: this.algorithm_library_id, start_time: this.StartTime, end_time: this.EndTime,
        page: this.pagenumber, per_page: this.pagesize };
    },
    pauseAlgorithmRuntimeRefresh(code) {
      this._algorithmRuntimeDenied = true;
      this.algorithmRuntimeHealthError = Number(code) === 401 ? '登录状态已失效，自动刷新已暂停' : '没有读取运行状态的权限，自动刷新已暂停';
      this.stopAlgorithmRuntimeRefresh();
    },
    stopAlgorithmRuntimeRefresh() {
      this._algorithmRuntimeGeneration++;
      clearTimeout(this.statusRefreshTimer);
      this.statusRefreshTimer = null;
      if (this._algorithmRuntimeController) this._algorithmRuntimeController.abort();
      this._algorithmRuntimeController = null;
    },
    scheduleAlgorithmRuntimeRefresh() {
      clearTimeout(this.statusRefreshTimer);
      this.statusRefreshTimer = null;
      if (!this.algorithmRuntimePageActive() || this._algorithmRuntimeDenied) return;
      const pending = this.tableData.some(row => (row.status === '停止' && String(row.model_status) !== '4')
        || (row.status === '运行' && String(row.model_status) === '2'));
      this.statusRefreshTimer = setTimeout(() => {
        this.statusRefreshTimer = null;
        if (this.batchStatusBusy || Object.keys(this.statusPending || {}).length) return this.scheduleAlgorithmRuntimeRefresh();
        return this.refreshAlgorithmRuntimeStates();
      }, pending ? 3000 : 10000);
    },
    refreshAlgorithmRuntimeStates() {
      if (!this.algorithmRuntimePageActive() || this._algorithmRuntimeDenied) return Promise.resolve(false);
      if (this.batchStatusBusy || Object.keys(this.statusPending || {}).length) { this.scheduleAlgorithmRuntimeRefresh(); return Promise.resolve(false); }
      if (this._algorithmRuntimeController) return Promise.resolve(false);
      if (!this._algorithmRuntimeQuery) this.captureAlgorithmRuntimeQuery();
      const generation = this._algorithmRuntimeGeneration, sequence = this.listRequestSequence;
      const current = () => generation === this._algorithmRuntimeGeneration && sequence === this.listRequestSequence
        && this.algorithmRuntimePageActive() && !this.batchStatusBusy && !Object.keys(this.statusPending || {}).length;
      const controller = new AbortController(); this._algorithmRuntimeController = controller;
      return this.$http.get(this.$url.url_5000 + '/model_view/algorithm_data_show', {
        params: { ...this._algorithmRuntimeQuery }, signal: controller.signal, timeout: 8000,
      }).then(response => {
        if (!current()) return false;
        const body = response && response.data;
        if (body && [401, 403].includes(Number(body.code))) { this.pauseAlgorithmRuntimeRefresh(body.code); return false; }
        if (!body || Number(body.code) !== 200 || !body.data_list || !Array.isArray(body.data_list.data)) throw new Error('Unavailable status');
        const byId = new Map(body.data_list.data.map(row => [String(row.id), row]));
        this.tableData.forEach(row => {
          const fresh = byId.get(String(row.id));
          if (!fresh) return;
          if (fresh.model_status != null) this.$set(row, 'model_status', fresh.model_status);
          if (fresh.status === '运行' || fresh.status === '停止') this.$set(row, 'status', fresh.status);
        });
        this.algorithmRuntimeHealthUpdatedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false });
        this.algorithmRuntimeHealthError = '';
        return true;
      }).catch(error => {
        if (!current()) return false;
        const code = error && error.response && error.response.status;
        if ([401, 403].includes(Number(code))) this.pauseAlgorithmRuntimeRefresh(code);
        else this.algorithmRuntimeHealthError = '运行状态刷新失败，保留最近结果';
        return false;
      }).finally(() => {
        if (this._algorithmRuntimeController === controller) this._algorithmRuntimeController = null;
        if (generation === this._algorithmRuntimeGeneration && this.algorithmRuntimePageActive()) this.scheduleAlgorithmRuntimeRefresh();
      });
    },
  },
};
