// Keep task values independent from the template defaults used to fill new keys.
export default {
  data() {
    return { algorithmTemplateLoading: false, algorithmTemplateError: '' };
  },
  created() {
    this._algorithmTemplateGeneration = 0;
    if (this.form) this.$set(this.form, 'template_data', this.normalizeAlgorithmTemplateRows(this.form.template_data));
  },
  beforeDestroy() {
    this._algorithmTemplateGeneration++;
  },
  methods: {
    normalizeAlgorithmTemplateRows(input, definition = false) {
      if (typeof input === 'string') {
        try { input = JSON.parse(input); } catch (error) { return []; }
      }
      if (!Array.isArray(input)) return [];
      const rows = [];
      input.forEach(item => {
        if (!item || typeof item !== 'object' || Array.isArray(item)) return;
        if (!definition && Object.prototype.hasOwnProperty.call(item, 'key') && Object.prototype.hasOwnProperty.call(item, 'value')) {
          rows.push({ key: String(item.key), value: item.value, msg: item.msg });
          return;
        }
        Object.keys(item).forEach(key => {
          const value = item[key];
          rows.push({ key, value: definition && Array.isArray(value) ? value[0] : value,
            msg: definition && Array.isArray(value) ? value[1] : undefined });
        });
      });
      return rows;
    },
    mergeAlgorithmTemplateRows(saved, defaults) {
      const rows = this.normalizeAlgorithmTemplateRows(saved);
      const byKey = new Map();
      rows.forEach(row => { if (!byKey.has(row.key)) byKey.set(row.key, row); });
      defaults.forEach(parameter => {
        if (byKey.has(parameter.key)) {
          byKey.get(parameter.key).msg = parameter.msg;
        } else {
          const row = { key: parameter.key, value: parameter.value, msg: parameter.msg };
          rows.push(row);
          byKey.set(parameter.key, row);
        }
      });
      return rows;
    },
    algorithmTemplatePayload() {
      return this.normalizeAlgorithmTemplateRows(this.form.template_data)
        .filter(item => typeof this.isAlgorithmPeopleCountParameter !== 'function' || !this.isAlgorithmPeopleCountParameter(item.key))
        .map(item => ({ [item.key]: item.value }));
    },
    validateAlgorithmTemplateParameters() {
      const keys = new Set();
      for (const item of this.normalizeAlgorithmTemplateRows(this.form.template_data)) {
        if (typeof this.isAlgorithmPeopleCountParameter === 'function' && this.isAlgorithmPeopleCountParameter(item.key)) continue;
        if (!item.key.trim()) {
          this.$message({ type: 'warning', message: '请填写参数名称，或删除空白参数行' });
          return false;
        }
        if (keys.has(item.key)) {
          this.$message({ type: 'warning', message: '参数名称不能重复：' + item.key });
          return false;
        }
        keys.add(item.key);
      }
      return true;
    },
    addAlgorithmTemplateParameter() {
      this._algorithmOperationalEdited = true;
      this.$set(this.form, 'template_data', this.normalizeAlgorithmTemplateRows(this.form.template_data));
      this.form.template_data.push({ key: '', value: '', msg: '' });
    },
    removeAlgorithmTemplateParameter(index) {
      this._algorithmOperationalEdited = true;
      this.$set(this.form, 'template_data', this.normalizeAlgorithmTemplateRows(this.form.template_data));
      this.form.template_data.splice(index, 1);
    },
    onAlgorithmTemplateSmallChange() {
      this._algorithmOperationalEdited = true;
      return this.handleChangeTemplateSmall(undefined, true);
    },
    completeAlgorithmTemplateParameters() {
      return this.handleChangeTemplateSmall();
    },
    loadAlgorithmTemplateParameters(url, isCurrent, replace = false) {
      const form = this.form, smallId = form.template_small_id;
      const generation = ++this._algorithmTemplateGeneration;
      const current = () => !this._algorithmFormClosed && generation === this._algorithmTemplateGeneration && form === this.form
        && String(smallId) === String(this.form.template_small_id) && (typeof isCurrent !== 'function' || isCurrent());
      if (smallId == null || smallId === '') {
        this.algorithmTemplateLoading = false;
        this.algorithmTemplateError = '请先选择模型小类，再补齐模板参数';
        return Promise.resolve(false);
      }
      // Edits made while defaults are loading take priority over the response.
      const requestedRows = JSON.stringify(this.normalizeAlgorithmTemplateRows(form.template_data));
      this.algorithmTemplateLoading = true;
      this.algorithmTemplateError = '';
      return this.$http.get(url, { params: { id: smallId } }).then(response => {
        if (!current()) return false;
        if (!response || !response.data || response.data.code != 200 || !response.data.data || !Array.isArray(response.data.data.list_data)) {
          throw new Error('Invalid template response');
        }
        const defaults = this.normalizeAlgorithmTemplateRows(response.data.data.list_data, true);
        const currentRows = this.normalizeAlgorithmTemplateRows(form.template_data);
        const editedWhileLoading = requestedRows !== JSON.stringify(currentRows);
        const currentKeys = new Set(currentRows.map(row => row.key));
        const removedWhileLoading = new Set(JSON.parse(requestedRows).filter(row => !currentKeys.has(row.key)).map(row => row.key));
        const rows = replace && !editedWhileLoading ? defaults
          : this.mergeAlgorithmTemplateRows(currentRows, defaults.filter(row => !removedWhileLoading.has(row.key)));
        const beforePayload = JSON.stringify(this.algorithmTemplatePayload());
        this.$set(form, 'template_data', rows);
        if (beforePayload !== JSON.stringify(this.algorithmTemplatePayload())) this._algorithmOperationalEdited = true;
        return true;
      }).catch(() => {
        if (current()) this.algorithmTemplateError = '模板参数读取失败，已保留现有参数，请重试';
        return false;
      }).finally(() => {
        if (generation === this._algorithmTemplateGeneration) this.algorithmTemplateLoading = false;
      });
    },
  },
};
