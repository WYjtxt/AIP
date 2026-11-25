// Runtime counters are displayed separately from the editable task configuration.
export default {
  data() {
    return { algorithmPeopleEnteringCount: null, algorithmPeopleExitingCount: null,
      algorithmPeopleCountUpdatedAt: '', algorithmPeopleCountError: '' };
  },
  computed: {
    algorithmPeopleCountVisible() {
      const id = this.form && this.form.Algorithm_library_id;
      const libraries = this.dict && this.dict.algorithm_list;
      const selected = Array.isArray(libraries) && libraries.find(item => String(item.id) === String(id));
      const names = selected ? [selected.analysis_type, selected.algorithm_name]
        : [this.nameif, this.form && this.form.analysis_type, this.form && this.form.algorithm_name];
      return names.some(name => typeof name === 'string' && /人数统计|人员计数/.test(name));
    },
    algorithmPeopleCountTaskId() {
      const query = this.$route && this.$route.query || {};
      return this.conf_id || query.conf_id || this.form && this.form.id || null;
    },
    algorithmPeopleCountTargetKey() {
      return [this.algorithmPeopleCountTaskId || '', this.form && this.form.Algorithm_library_id || '',
        this.indexnum == null ? '' : this.indexnum, this.algorithmPeopleCountVisible ? 'people' : 'other'].join('|');
    },
    algorithmPeopleEnteringDisplay() {
      return this.algorithmPeopleEnteringCount == null ? (this.algorithmPeopleCountTaskId ? '暂无' : '0') : String(this.algorithmPeopleEnteringCount);
    },
    algorithmPeopleExitingDisplay() {
      return this.algorithmPeopleExitingCount == null ? (this.algorithmPeopleCountTaskId ? '暂无' : '0') : String(this.algorithmPeopleExitingCount);
    },
    algorithmPeopleCountHint() {
      if (!this.algorithmPeopleCountTaskId) return '新任务尚未运行；每天23:59清零，算法重启保留累计';
      const updated = this.algorithmPeopleCountUpdatedAt ? '上次更新 ' + this.algorithmPeopleCountUpdatedAt : '正在读取实时累计';
      return (this.algorithmPeopleCountError ? this.algorithmPeopleCountError + '；' : '每5秒刷新；') + updated + '；每天23:59清零，算法重启保留累计';
    },
  },
  watch: {
    algorithmPeopleCountTargetKey() { this.restartAlgorithmPeopleCountPolling(); },
    form() { this.restartAlgorithmPeopleCountPolling(); },
  },
  created() {
    this._algorithmPeoplePollGeneration = 0;
    this._algorithmPeoplePollTimer = null;
    this._algorithmPeoplePollController = null;
  },
  mounted() {
    this.restartAlgorithmPeopleCountPolling();
  },
  beforeDestroy() {
    this.stopAlgorithmPeopleCountPolling();
  },
  methods: {
    isAlgorithmPeopleCountParameter(key) {
      return this.algorithmPeopleCountVisible && /^(进入人数|离开人数|进人数|出人数)$/.test(String(key));
    },
    removeAlgorithmPeopleCountFields(item) {
      ['Entering_num', 'Exiting_num', 'all_Entering_num', 'all_Exiting_num'].forEach(key => { delete item[key]; });
    },
    applyAlgorithmPeopleCountSnapshot(detail) {
      // Null means unavailable, while a real zero must be shown as zero.
      for (const [field, destination] of [['all_Entering_num', 'algorithmPeopleEnteringCount'], ['all_Exiting_num', 'algorithmPeopleExitingCount']]) {
        if (Object.prototype.hasOwnProperty.call(detail, field)) {
          const value = detail[field];
          this[destination] = value == null || value === '' ? null : value;
        }
      }
      this.algorithmPeopleCountUpdatedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false });
    },
    stopAlgorithmPeopleCountPolling() {
      this._algorithmPeoplePollGeneration++;
      if (this._algorithmPeoplePollTimer) clearTimeout(this._algorithmPeoplePollTimer);
      this._algorithmPeoplePollTimer = null;
      if (this._algorithmPeoplePollController) this._algorithmPeoplePollController.abort();
      this._algorithmPeoplePollController = null;
    },
    restartAlgorithmPeopleCountPolling() {
      const seedCurrentForm = this._algorithmPeopleSnapshotForm !== this.form
        || String(this._algorithmPeopleSnapshotLibraryId) === String(this.form && this.form.Algorithm_library_id);
      this._algorithmPeopleSnapshotForm = this.form;
      this._algorithmPeopleSnapshotLibraryId = this.form && this.form.Algorithm_library_id;
      this.stopAlgorithmPeopleCountPolling();
      this.algorithmPeopleEnteringCount = null;
      this.algorithmPeopleExitingCount = null;
      this.algorithmPeopleCountUpdatedAt = '';
      this.algorithmPeopleCountError = '';
      if (this._algorithmFormClosed || !this.algorithmPeopleCountVisible) return;
      if (seedCurrentForm && this.form && this.algorithmPeopleCountTaskId && (Object.prototype.hasOwnProperty.call(this.form, 'all_Entering_num')
        || Object.prototype.hasOwnProperty.call(this.form, 'all_Exiting_num'))) this.applyAlgorithmPeopleCountSnapshot(this.form);
      if (this.algorithmPeopleCountTaskId) return this.refreshAlgorithmPeopleCounts();
    },
    refreshAlgorithmPeopleCounts() {
      if (this._algorithmFormClosed || !this.algorithmPeopleCountVisible || !this.algorithmPeopleCountTaskId) return Promise.resolve(false);
      const generation = this._algorithmPeoplePollGeneration, targetKey = this.algorithmPeopleCountTargetKey;
      const current = () => !this._algorithmFormClosed && generation === this._algorithmPeoplePollGeneration && targetKey === this.algorithmPeopleCountTargetKey;
      const controller = new AbortController();
      this._algorithmPeoplePollController = controller;
      const params = { conf_id: this.algorithmPeopleCountTaskId };
      if (this.indexnum != null) params.data_id = this.indexnum;
      return this.$http.get(this.$url.url_5000 + '/model_view/algorithm_data_show', { params, signal: controller.signal, timeout: 8000 }).then(response => {
        if (!current()) return false;
        const detail = response && response.data && response.data.datalist;
        if (!response || !response.data || response.data.code != 200 || !detail || typeof detail !== 'object') throw new Error('Invalid count response');
        if (String(detail.Algorithm_library_id) !== String(this.form.Algorithm_library_id)) {
          this.algorithmPeopleCountError = '新选择的算法尚未保存，暂无实时计数';
          return false;
        }
        if (!Object.prototype.hasOwnProperty.call(detail, 'all_Entering_num') || !Object.prototype.hasOwnProperty.call(detail, 'all_Exiting_num')) throw new Error('Missing counters');
        this.applyAlgorithmPeopleCountSnapshot(detail);
        this.algorithmPeopleCountError = '';
        return true;
      }).catch(() => {
        if (current()) this.algorithmPeopleCountError = '刷新失败，保留最近读数';
        return false;
      }).finally(() => {
        if (this._algorithmPeoplePollController === controller) this._algorithmPeoplePollController = null;
        if (current()) this._algorithmPeoplePollTimer = setTimeout(() => this.refreshAlgorithmPeopleCounts(), 5000);
      });
    },
  },
};
