/* algorithm-first-editor-contract-v4 */

var algorithmFirstEditorConfidence = (window.AiMonitorAlgorithmFirstConfidence && window.AiMonitorAlgorithmFirstConfidence.secondary && window.AiMonitorAlgorithmFirstConfidence.cascadeReady && window.AiMonitorAlgorithmFirstConfidence.restoreDetection) ? window.AiMonitorAlgorithmFirstConfidence : (window.AiMonitorAlgorithmFirstConfidence = (function () {
  var hydrated = new WeakSet();
  var detectionChecked = new WeakMap();
  function detectionState(form) {
    var state = detectionChecked.get(form);
    if (!state) { state = {}; detectionChecked.set(form, state); }
    return state;
  }
  function blankLabels(value) {
    if (value == null || value === '') return true;
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'string') {
      try { var parsed = JSON.parse(value); return Array.isArray(parsed) && parsed.length === 0; } catch (_) {}
    }
    return false;
  }
  function markDetection(vm) {
    if (vm.form && typeof vm.form === 'object') detectionState(vm.form)[String(vm.form.Algorithm_library_id)] = true;
  }
  function restoreDetection(vm, rows, request) {
    var form = vm.form;
    if (!form || !request || form !== request.form || vm._algorithmFormClosed ||
        String(request.id) !== String(form.Algorithm_library_id) || !Array.isArray(rows)) return;
    var library = String(form.Algorithm_library_id), state = detectionState(form);
    if (state[library] || vm._algorithmDetectionEdited) return;
    var advanced = Object.prototype.hasOwnProperty.call(vm, 'jclxslist');
    if (!blankLabels(form.label_list) || advanced && !blankLabels(vm.jclxslist)) {
      // The advanced child has a second display value. Reflect an existing
      // saved array without replacing any existing selection on either side.
      if (advanced && blankLabels(vm.jclxslist) && Array.isArray(form.label_list)) vm.jclxslist = form.label_list.slice();
      state[library] = true;
      return;
    }
    var choices = rows.filter(function (row) {
      return row && typeof row.test_type_ename === 'string' && row.test_type_ename.trim() &&
        (row.Algorithm_library_id == null || String(row.Algorithm_library_id) === library);
    });
    var hasId = form.test_type_id != null && form.test_type_id !== '' && String(form.test_type_id) !== '0';
    var matches = hasId ? choices.filter(function (row) { return String(row.id) === String(form.test_type_id); }) : choices;
    // A stored test ID is authoritative. Several unselected classes require
    // an operator choice; never guess from a different algorithm or row order.
    if (matches.length !== 1) return;
    var selected = matches[0];
    vm.$set(form, 'label_list', [selected.test_type_ename]);
    if (advanced) vm.jclxslist = [selected.test_type_ename];
    if (!hasId) vm.$set(form, 'test_type_id', selected.id);
    state[library] = true;
  }
  function empty(value) { return value === null || value === undefined || value === ''; }
  function fromStored(value) {
    if (empty(value)) return 0.6;
    var number = Number(value);
    if (!Number.isFinite(number) || number < 0 || number > 100) return value;
    var decimal = typeof value === 'string' ? /[.eE]/.test(value) : !Number.isInteger(number);
    return number <= 1 && decimal ? number : number / 100;
  }
  function valid(value) {
    if (empty(value) || typeof value === 'boolean') return false;
    var number = Number(value);
    return Number.isFinite(number) && number >= 0 && number <= 1 && Math.abs(number * 100 - Math.round(number * 100)) < 1e-8;
  }
  function toStored(value) {
    if (!valid(value)) throw new Error('置信度必须为0到1之间、以0.01为步长的数字');
    return String(Math.round(Number(value) * 100));
  }
  function activeCascade(value) { return Number.isInteger(Number(value)) && Number(value) > 0; }
  function secondary(value, kind) { return activeCascade(kind) || valid(value) ? toStored(value) : value; }
  function cascadeReady(vm) {
    if (!activeCascade(vm.form && vm.form.model_two_type)) return true;
    var rows = vm.dict && vm.dict.algorithm_list_five, selected = Array.isArray(rows) && rows.find(function (row) { return String(row.id) === String(vm.form.model_two_type); });
    if (selected && typeof selected.algorithm_path === 'string' && selected.algorithm_path.trim()) return true;
    vm.$message({type: 'warning', message: '级联算法信息尚未加载完整，请刷新后重试'});
    return false;
  }
  function hydrate(value) {
    if (!value || typeof value !== 'object' || hydrated.has(value)) return value;
    hydrated.add(value);
    if (Array.isArray(value)) value.forEach(hydrate);
    else Object.keys(value).forEach(function (key) {
      if (key === 'confidence') value[key] = fromStored(value[key]);
      else if (value[key] && typeof value[key] === 'object') hydrate(value[key]);
    });
    return value;
  }
  function payload(value) {
    if (Array.isArray(value)) return value.map(payload);
    if (!value || typeof value !== 'object') return value;
    var result = {};
    Object.keys(value).forEach(function (key) {
      if (key === 'confidence') result[key] = toStored(value[key]);
      else if (key === 'model_two_data' && !activeCascade(value.model_two_type)) {
        result[key] = typeof value[key] === 'object' ? JSON.parse(JSON.stringify(value[key])) : value[key];
      } else if (key === 'model_two_data' && typeof value[key] === 'string') {
        var parsed;
        try { parsed = JSON.parse(value[key]); } catch (ignore) { result[key] = value[key]; return; }
        result[key] = JSON.stringify(payload(parsed));
      } else result[key] = payload(value[key]);
    });
    return result;
  }
  function confidenceOf(value) { return hydrated.has(value) ? value.confidence : fromStored(value.confidence); }
  return {fromStored: fromStored, toStored: toStored, valid: valid, hydrate: hydrate, payload: payload, confidenceOf: confidenceOf, secondary: secondary, cascadeReady: cascadeReady, restoreDetection: restoreDetection, markDetection: markDetection};
})());

/* native-template-administrator-v1 */
(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["chunk-415cc626"],{"13d5":function(t,e,i){"use strict";var s=i("23e7"),a=i("d58f").left,l=i("a640"),o=i("2d00"),r=i("605d"),n=!r&&o>79&&o<83,m=n||!l("reduce");s({target:"Array",proto:!0,forced:m},{reduce:function(t){var e=arguments.length;return a(this,t,e,e>1?arguments[1]:void 0)}})},"4b0f":function(t,e,i){},"605d":function(t,e,i){"use strict";var s=i("da84"),a=i("c6b6");t.exports="process"===a(s.process)},"646e":function(t,e,i){"use strict";i("4b0f")},"907f":function(t,e,i){},a640:function(t,e,i){"use strict";var s=i("d039");t.exports=function(t,e){var i=[][t];return!!i&&s((function(){i.call(null,e||function(){return 1},1)}))}},c9aa:function(t,e,i){"use strict";i("907f")},cee7:function(t,e,i){
"use strict";i.r(e);
i("14d9");i("d9e2");i("13d5");i("4360");i("896f");i("de4a");i("dc58");i("c329");i("8f15");i("ed5a");i("c9aa");i("2877");i("646e");
var store=i("4360").a,draw_test=i("896f").a,draw_test2=i("de4a").a,draw_test3=i("dc58").a,draw_test4=i("c329").a;var compute=i("8f15").b,findModelName=i("8f15").d,modelApi=i("ed5a").a;
// Shared source selection and snapshot lifetime for the original algorithm forms.
var algorithmStreamMixin={
  data() {
    return { algorithmAdmissionCards: {}, algorithmAdmissionFailed: false, streamCapabilities: null, streamCapabilitiesDeviceId: null, streamCapabilitiesLoading: false, streamCapabilitiesError: '', algorithmSnapshotReadyKey: null };
  },
  computed: {
    algorithmAdmissionHint() {
      var selected = this.resolveAlgorithmResource(this.form && this.form.resource_id);
      var card = selected && this.algorithmAdmissionCards[String(selected.resourceId)];
      if (this.algorithmAdmissionFailed) return '资源状态暂不可用，暂停新增部署；名称与备注仍可保存';
      if (card && card.disabled) return card.reason + (this.algorithmIsEditing() ? '；已有任务保持原卡，名称与备注仍可保存' : '');
      if (card && card.cpu_warning) return '主机 CPU 持续高于 ' + card.cpu_warning_threshold + '%，建议使用负载较低的卡';
      if (card) return '资源可用 · 当前卡利用率 ' + card.utilization + '%';
      var states = Object.keys(this.algorithmAdmissionCards).map(key => this.algorithmAdmissionCards[key]);
      if (states.length && states.every(item => item.disabled)) return '当前无可用算力资源：' + states[0].reason;
      return '正在获取资源状态…';
    },
    streamSelection: {
      get() {
        if (this.streamCapabilities && !this.streamOptions.length) return '';
        if (this.form && (this.form.stream_type === 'main' || this.form.stream_type === 'sub')) return this.form.stream_type;
        var current = this.streamCapabilities && this.streamCapabilities.current_source_stream_type;
        return current === 'main' || current === 'sub' ? current : '';
      },
      set(value) {
        if (value !== 'main' && value !== 'sub') return;
        // Selecting the displayed mode of an old NULL task is still an explicit
        // switch from its saved input address to the device's native stream.
        if (value !== this.form.stream_type) this._algorithmSourceEdited = true;
        this._algorithmDefaultStreamPending = false;
        this.$set(this.form, 'stream_type', value);
        if (typeof this.syncModelStreams === 'function') this.syncModelStreams();
      },
    },
    streamSourceKey() { return String(this.algorithmEquipmentId() || '') + '|' + this.streamTypeRequest(); },
    streamOptions() {
      var options = this.streamCapabilities && this.streamCapabilities.stream_type_options;
      options = Array.isArray(options) ? options : [];
      var supported = options.filter(function (option) { return (option.value === 'main' || option.value === 'sub') && option.supported !== false && option.disabled !== true; });
      if (this.streamCapabilities && !supported.length) return [];
      return ['main', 'sub'].map(function (value) {
        return { value: value, label: value === 'main' ? '主码流' : '子码流', disabled: !supported.some(function (option) { return option.value === value; }) };
      });
    },
    streamSelectionDisabled() {
      return this.streamCapabilitiesLoading || !this.algorithmEquipmentId() || !this.streamOptions.some(function (option) { return !option.disabled; });
    },
    algorithmSnapshotHint() {
      if (!this.algorithmEquipmentId()) return '暂未选择监控点，无图片展示';
      if (this.loading || this.streamCapabilitiesLoading) return '正在获取所选码流画面…';
      return '所选设备暂无画面，请刷新或检查视频源';
    },
    streamCapabilityHint() {
      if (!this.algorithmEquipmentId()) return '请先选择报警设备';
      if (this.streamCapabilitiesLoading) return '正在读取设备码流选项…';
      if (this.streamCapabilitiesError) return this.streamCapabilitiesError;
      var capabilities = this.streamCapabilities || {};
      var reason = typeof capabilities.stream_capability_reason === 'string' ? capabilities.stream_capability_reason.trim() : '';
      var available = this.streamOptions.filter(function (option) { return !option.disabled; });
      if (!available.length && reason) return reason + '；当前输入地址保持不变';
      if (!available.length) return '此来源无法确认主/子码流，当前输入地址保持不变';
      if (capabilities.stream_source_kind === 'hik_platform_api') return '通过安防平台接口获取所选码流；选择仅影响本算法配置';
      if (reason) return reason + '；选择仅影响本算法配置';
      var current = capabilities.current_source_stream_type;
      return current === 'main' || current === 'sub' ? '原设备地址使用' + (current === 'main' ? '主码流' : '子码流') + '；选择仅影响本算法配置' : '选择仅影响本算法配置';
    },
  },
  watch: {
    'dict.type_list'() { this.applyAlgorithmAlarmDefault(); },
    async streamSourceKey() {
      // A visible-region watcher or an existing explicit refresh may already
      // have started the image for this key before Vue flushes this watcher.
      if (this._lastAlgorithmImageKey !== this.streamSourceKey) this.invalidateAlgorithmImage();
      var equipmentId = this.algorithmEquipmentId(), key = this.streamSourceKey;
      if (String(equipmentId || '') !== String(this.streamCapabilitiesDeviceId || '') || this.streamCapabilitiesLoading) await this.loadStreamCapabilities(equipmentId);
      if (this._algorithmFormClosed || key !== this.streamSourceKey) return;
      return this.ensureVisibleAlgorithmSnapshot();
    },
    type_qy(visible) { if (visible) return this.ensureVisibleAlgorithmSnapshot(); },
  },
  created() {
    this._algorithmFormClosed = false; this._algorithmSourceEdited = false;
    this._algorithmModelGeneration = 0; this._algorithmModelWasSelected = false; this._algorithmResourceDefaultPending = false; this._algorithmAlarmDefaultPending = false; this._algorithmScrollPending = false; this._algorithmSelectedModelId = null;
    this._algorithmImageGeneration = 0; this._algorithmImageController = null; this._algorithmSnapshotImage = null; this._lastAlgorithmImageKey = null; this._algorithmImageObjectUrl = null;
    this._algorithmCapabilityGeneration = 0; this._algorithmCapabilityController = null; this._algorithmCapabilityPromise = null;
    var query = this.$route && this.$route.query || {};
    var editing = query.conf_id != null || query.map != null || this.conf_id;
    var childSource = Object.prototype.hasOwnProperty.call(this, 'configStreamType');
    this._algorithmDefaultStreamPending = !editing && !childSource && this.form && !Object.prototype.hasOwnProperty.call(this.form, 'stream_type');
    if (this.form && !Object.prototype.hasOwnProperty.call(this.form, 'stream_type')) this.$set(this.form, 'stream_type', this._algorithmDefaultStreamPending ? 'main' : null);
    if (childSource) this.$set(this.form, 'stream_type', this.configStreamType === 'main' || this.configStreamType === 'sub' ? this.configStreamType : null);
  },
  mounted() {
    if (Object.prototype.hasOwnProperty.call(this, 'computeOptions')) {
      this.refreshAlgorithmAdmission();
      this._algorithmAdmissionTimer = setInterval(() => this.refreshAlgorithmAdmission(), 5000);
      this._algorithmOperationalEdited = false;
      this._algorithmEditListener = (event) => {
        var field = event.target.closest && event.target.closest('.el-form-item');
        var label = field && field.querySelector('.el-form-item__label');
        if (label && /^(任务名称|任务说明)$/.test(label.textContent.trim())) return;
        var button = event.target.closest && event.target.closest('button');
        if (button && /^(保存|取消|返回)$/.test(button.textContent.trim())) return;
        if (field || event.target.closest && event.target.closest('.algorithm-drawing-scroll')) this._algorithmOperationalEdited = true;
      };
      ['click', 'input', 'change', 'keydown'].forEach(name => this.$el.addEventListener(name, this._algorithmEditListener, true));
    }
    if (this.algorithmEquipmentId() && !this.streamCapabilitiesDeviceId) this.loadStreamCapabilities(this.algorithmEquipmentId());
    if (this.type_qy) this.ensureVisibleAlgorithmSnapshot();
  },
  beforeDestroy() {
    clearInterval(this._algorithmAdmissionTimer);
    if (this._algorithmAdmissionController) this._algorithmAdmissionController.abort();
    if (this._algorithmEditListener) ['click', 'input', 'change', 'keydown'].forEach(name => this.$el.removeEventListener(name, this._algorithmEditListener, true));
    this._algorithmFormClosed = true;
    this.invalidateAlgorithmImage();
    this._algorithmCapabilityGeneration++;
    if (this._algorithmCapabilityController) this._algorithmCapabilityController.abort();
    this._algorithmCapabilityController = null;
  },
  methods: {
    trySaveAlgorithmMetadata() {
      if (window.AiMonitorAlgorithmFirstEditor && window.AiMonitorAlgorithmFirstEditor.isBatch(this)) return false;
      if (!this.algorithmIsEditing() || Object.prototype.hasOwnProperty.call(this, 'configStreamType') || this._algorithmOperationalEdited || !this.form.id) return false;
      if (this._algorithmMetadataSaving) return true;
      this._algorithmMetadataSaving = true;
      this.$http.post(this.$url.url_5000 + '/resource_view/algorithm_metadata', {
        id: this.form.id, conf_name: this.form.conf_name, Algorithm_config_ps: this.form.Algorithm_config_ps
      }).then(response => {
        if (response.data.code === 200) { this.$message.success(response.data.msg); (window.AiMonitorAlgorithmFirstEditor && window.AiMonitorAlgorithmFirstEditor.afterSaved(this, typeof _algorithmFirstSavedContext === "undefined" ? null : _algorithmFirstSavedContext)) || this.goback(); }
        else this.$message.warning(response.data.msg || '保存失败');
      }).catch(() => this.$message.warning('保存失败，请稍后重试'))
        .finally(() => { this._algorithmMetadataSaving = false; });
      return true;
    },
    refreshAlgorithmAdmission() {
      if (this._algorithmFormClosed || this._algorithmAdmissionLoading) return;
      this._algorithmAdmissionLoading = true;
      var controller = new AbortController(); this._algorithmAdmissionController = controller;
      return this.$http.get(this.$url.url_5000 + '/resource_view/admission', { signal: controller.signal, timeout: 8000 })
        .then(response => {
          if (this._algorithmFormClosed) return;
          if (response.data.code !== 200 || !response.data.data || !response.data.data.cards) throw new Error('unavailable');
          this.algorithmAdmissionCards = response.data.data.cards;
          this.algorithmAdmissionFailed = false;
          this.applyAlgorithmAdmission();
        }).catch(() => {
          if (this._algorithmFormClosed) return;
          this.algorithmAdmissionFailed = true;
          this.applyAlgorithmAdmission();
        }).finally(() => { this._algorithmAdmissionLoading = false; });
    },
    applyAlgorithmAdmission() {
      var selected = this.resolveAlgorithmResource(this.form && this.form.resource_id), chosen = null;
      this.computeOptions = (this.computeOptions || []).map(host => Object.assign({}, host, { children: (host.children || []).map(card => {
        var status = this.algorithmAdmissionFailed ? null : this.algorithmAdmissionCards[String(card.id)];
        status = status || { disabled: true, reason: '资源状态未知，暂停新增部署', utilization: null };
        var next = Object.assign({}, card, { admission: status, disabled: status.disabled !== false,
          label: (card.baseLabel || card.label) + (status.disabled ? ' · ' + status.reason : '') });
        if (selected && String(card.id) === String(selected.resourceId)) chosen = next;
        return next;
      }) }));
      if (!this.algorithmIsEditing() && !this._algorithmResourceEdited && (!chosen || chosen.disabled)) {
        this.$set(this.form, 'resource_id', 0);
        this._algorithmResourceDefaultPending = true;
        this.applyAlgorithmResourceDefault();
        if (selected && this.form.resource_id && String(selected.resourceId) !== String(this.form.resource_id)) this.$message.info('原算力卡暂不可用，已自动切换至另一张可用卡');
      } else if (!this.algorithmIsEditing() && !this._algorithmResourceEdited && selected && chosen) {
        var host = this.computeOptions.find(item => String(item.deviceId) === String(selected.computingId));
        var primary = host && host.children.find(card => card.devId != null && String(card.devId) === '0'
          && !card.disabled && card.admission.primary_return_ready === true);
        if (primary && String(primary.id) !== String(selected.resourceId)) {
          this.$set(this.form, 'resource_id', primary.id);
          this.$message.info('CPU 与卡 0 负载已持续恢复，已自动回选卡 0');
        }
      }
    },
    algorithmIsEditing() {
      var query = this.$route && this.$route.query || {};
      return query.conf_id != null || query.map != null || !!this.conf_id;
    },
    sortAlgorithmResources(rawData) {
      var number = function (value) { return value == null || value === '' || !Number.isFinite(Number(value)) ? Infinity : Number(value); };
      return (Array.isArray(rawData) ? rawData : []).map(function (host) {
        var groups = host.grouped_resources || {};
        var cards = Object.keys(groups).reduce(function (all, key) { return all.concat(Array.isArray(groups[key]) ? groups[key] : []); }, []);
        cards.sort(function (a, b) { return number(a.dev_id) - number(b.dev_id) || number(a.id) - number(b.id); });
        return { id: '设备' + host.computing_id, deviceId: host.computing_id, computing_ip: host.computing_ip,
          label: host.computing_name, children: cards.map(function (card) {
            var status = card.admission || { disabled: true, reason: '正在获取资源状态' };
            return { id: card.id, devId: card.dev_id, baseLabel: (card.dev_get_target || '计算卡') + ' · 卡 ' + (card.dev_id == null ? '—' : card.dev_id),
              label: (card.dev_get_target || '计算卡') + ' · 卡 ' + (card.dev_id == null ? '—' : card.dev_id) + (status.disabled ? ' · ' + status.reason : ''),
              disabled: status.disabled !== false, admission: status };
          }) };
      }).sort(function (a, b) { return number(a.deviceId) - number(b.deviceId); });
    },
    markAlgorithmResourceEdited() { this._algorithmResourceDefaultPending = false; this._algorithmResourceEdited = true; },
    markAlgorithmDetectionEdited() { this._algorithmDetectionEdited = true; },
    markAlgorithmAlarmEdited() { this._algorithmAlarmEdited = true; this._algorithmAlarmDefaultPending = false; },
    applyAlgorithmAlarmDefault() {
      if (!this._algorithmAlarmDefaultPending || this._algorithmAlarmEdited) return;
      if (this.form.res_type != null && this.form.res_type !== '') { this._algorithmAlarmDefaultPending = false; return; }
      // The single form stores dictionary IDs; the model child uses its fixed
      // string-valued choices. Wait for the matching source before assigning.
      var choices = Object.prototype.hasOwnProperty.call(this, 'jclxslist') ? this.alarmTypeDictOptions : this.dict && this.dict.type_list;
      if (!Array.isArray(choices) || !choices.length) return;
      var first = choices.find(function (item) { return /^(?:I|Ⅰ|一|1)级报警$|^1类$/.test(item.label || item.value || ''); }) || choices.find(function (item) { return String(item.id == null ? item.value : item.id) === '1'; }) || choices[0];
      this.$set(this.form, 'res_type', first.id == null ? first.value : first.id);
      this._algorithmAlarmDefaultPending = false;
    },
    applyAlgorithmResourceDefault() {
      if (!this._algorithmResourceDefaultPending || this._algorithmResourceEdited || this.algorithmIsEditing()) return;
      if (this.form.resource_id != null && this.form.resource_id !== '' && this.form.resource_id !== 0) { this._algorithmResourceDefaultPending = false; return; }
      var cards = [];
      (this.computeOptions || []).forEach(function (host) { cards = cards.concat(host.children || []); });
      var number = function (value) { return value == null || value === '' || !Number.isFinite(Number(value)) ? Infinity : Number(value); };
      cards.sort(function (a, b) { return number(a.devId) - number(b.devId) || number(a.id) - number(b.id); });
      cards = cards.filter(function (card) { return card.disabled === false; });
      if (!cards.length) return;
      this.$set(this.form, 'resource_id', cards[0].id);
      this._algorithmResourceDefaultPending = false;
    },
    applyAlgorithmDefaults(labels, userSelected) {
      if (!userSelected && this.algorithmIsEditing()) return;
      var selectedLabels = (labels || []).map(function (item) { return item.test_type_ename; }).filter(function (value) { return value != null && value !== ''; });
      if (!this._algorithmDetectionEdited) {
        this.$set(this.form, 'label_list', selectedLabels);
        if (Object.prototype.hasOwnProperty.call(this, 'jclxslist')) this.jclxslist = selectedLabels.slice();
        this.$set(this.form, 'test_type_id', labels && labels.length ? labels[0].id : '');
      }
      this._algorithmAlarmDefaultPending = !this._algorithmAlarmEdited;
      this.applyAlgorithmAlarmDefault();
      this._algorithmResourceDefaultPending = !this._algorithmResourceEdited;
      this.applyAlgorithmResourceDefault();
    },
    scrollToAlgorithmSave() {
      if (!this._algorithmScrollPending || this._algorithmFormClosed) return;
      this._algorithmScrollPending = false;
      this.$nextTick(() => {
        if (this._algorithmFormClosed || !this.$el) return;
        var page = this.$el.closest('.algorithm-config-page') || this.$el;
        var actions = page.querySelector('.algorithm-action-buttons');
        if (actions && typeof actions.scrollIntoView === 'function') actions.scrollIntoView({ behavior: 'smooth', block: 'end' });
      });
    },
    algorithmEquipmentId() {
      if (!this.form) return null;
      return Object.prototype.hasOwnProperty.call(this.form, 'equipment_name') ? (this.form.equipment_name || null) : (this.form.Equipment_id || null);
    },
    streamTypeRequest() { return this.form && (this.form.stream_type === 'main' || this.form.stream_type === 'sub') ? this.form.stream_type : 'legacy'; },
    async ensureVisibleAlgorithmSnapshot() {
      var equipmentId = this.algorithmEquipmentId(), key = this.streamSourceKey;
      if (!equipmentId || !this.type_qy || this._algorithmFormClosed || typeof this.handleimg !== 'function') return false;
      if (this.algorithmSnapshotReadyKey === key || this._algorithmImageController || (this.loading && this._lastAlgorithmImageKey === key)) return false;
      if (String(equipmentId) !== String(this.streamCapabilitiesDeviceId || '') || this.streamCapabilitiesLoading) await this.loadStreamCapabilities(equipmentId);
      if (this._algorithmFormClosed || !this.type_qy || key !== this.streamSourceKey || this.algorithmSnapshotReadyKey === key || this._algorithmImageController || (this.loading && this._lastAlgorithmImageKey === key)) return false;
      this.handleimg();
      return true;
    },
    restoreAlgorithmSource() {
      this._algorithmModelGeneration++;
      this._algorithmResourceDefaultPending = false; this._algorithmAlarmDefaultPending = false; this._algorithmScrollPending = false; this._algorithmSelectedModelId = null;
      this._algorithmDefaultStreamPending = false;
      this._algorithmSourceEdited = false;
      if (!Object.prototype.hasOwnProperty.call(this.form, 'stream_type')) this.$set(this.form, 'stream_type', null);
      if (Array.isArray(this.form.resource_id)) this.$set(this.form, 'resource_id', this.form.resource_id[this.form.resource_id.length - 1]);
    },
    resolveAlgorithmResource(value) {
      var resourceId = Array.isArray(value) ? value[value.length - 1] : value;
      if (resourceId == null || resourceId === '') return null;
      var result = null;
      function find(nodes, hostId) {
        return (nodes || []).some(function (node) {
          if (node.children && node.children.length) return find(node.children, hostId);
          if (String(node.id) !== String(resourceId)) return false;
          result = { resourceId: node.id, computingId: hostId }; return true;
        });
      }
      (this.computeOptions || []).some(function (host) { return find(host.children, host.deviceId); });
      return result;
    },
    onAlarmDeviceChange() {
      this._algorithmSourceEdited = true;
      this._algorithmDefaultStreamPending = true;
      this.$set(this.form, 'stream_type', 'main');
      this.streamCapabilities = null; this.streamCapabilitiesDeviceId = null;
      if (typeof this.syncModelStreams === 'function') this.syncModelStreams();
      this.loadStreamCapabilities(this.algorithmEquipmentId());
    },
    loadStreamCapabilities(equipmentId) {
      if (this._algorithmCapabilityPromise && String(equipmentId || '') === String(this.streamCapabilitiesDeviceId || '')) return this._algorithmCapabilityPromise;
      var promise = this.fetchStreamCapabilities(equipmentId);
      this._algorithmCapabilityPromise = promise;
      promise.then(() => { if (this._algorithmCapabilityPromise === promise) this._algorithmCapabilityPromise = null; });
      return promise;
    },
    async fetchStreamCapabilities(equipmentId) {
      if (this._algorithmFormClosed) return null;
      if (this._algorithmCapabilityController) this._algorithmCapabilityController.abort();
      var generation = ++this._algorithmCapabilityGeneration;
      this.streamCapabilitiesDeviceId = equipmentId || null;
      this.streamCapabilities = null; this.streamCapabilitiesError = '';
      if (!equipmentId) { this.streamCapabilitiesLoading = false; return null; }
      var controller = new AbortController(); this._algorithmCapabilityController = controller; this.streamCapabilitiesLoading = true;
      try {
        var response = await this.$http.get(this.$url.url_5000 + '/model_view/equipment_one_info', {
          params: { equipment_id: equipmentId }, signal: controller.signal, timeout: 15000,
        });
        if (this._algorithmFormClosed || generation !== this._algorithmCapabilityGeneration || String(equipmentId) !== String(this.algorithmEquipmentId())) return null;
        if (response.data.code !== 200) throw new Error(response.data.msg || '设备信息读取失败');
        this.streamCapabilities = response.data.stream_capabilities || null;
        if (this._algorithmDefaultStreamPending) {
          var mainSupported = this.streamOptions.some(function (option) { return option.value === 'main' && !option.disabled; });
          this.$set(this.form, 'stream_type', mainSupported ? 'main' : null);
          this._algorithmDefaultStreamPending = false;
          if (typeof this.syncModelStreams === 'function') this.syncModelStreams();
        }
        if (typeof this.handleimg === 'function') this.area2 = String(response.data.data && response.data.data.equipment_code) === '201';
        return response.data;
      } catch (error) {
        if (!this._algorithmFormClosed && generation === this._algorithmCapabilityGeneration && !controller.signal.aborted) this.streamCapabilitiesError = '码流选项读取失败，请重新选择设备或刷新';
        return null;
      } finally {
        if (generation === this._algorithmCapabilityGeneration) {
          this.streamCapabilitiesLoading = false;
          if (this._algorithmCapabilityController === controller) this._algorithmCapabilityController = null;
        }
      }
    },
    invalidateAlgorithmImage() {
      this._algorithmImageGeneration++;
      this.algorithmSnapshotReadyKey = null;
      if ('imgOpen' in this) this.imgOpen = false;
      if ('loading' in this) this.loading = false;
      if (this._algorithmImageController) this._algorithmImageController.abort();
      this._algorithmImageController = null;
      if (this._algorithmSnapshotImage) {
        this._algorithmSnapshotImage.onload = null; this._algorithmSnapshotImage.onerror = null;
        this._algorithmSnapshotImage.src = ''; this._algorithmSnapshotImage = null;
      }
      this.releaseAlgorithmImageObjectUrl();
    },
    releaseAlgorithmImageObjectUrl() {
      if (this._algorithmImageObjectUrl) {
        URL.revokeObjectURL(this._algorithmImageObjectUrl);
        this._algorithmImageObjectUrl = null;
      }
    },
    snapshotStillCurrent(generation, key) { return !this._algorithmFormClosed && generation === this._algorithmImageGeneration && key === this.streamSourceKey; },
    async requestAlgorithmImage(num) {
      var equipmentId = this.algorithmEquipmentId();
      if (!equipmentId || this._algorithmFormClosed) return false;
      this.invalidateAlgorithmImage();
      var generation = this._algorithmImageGeneration, key = this.streamSourceKey;
      var streamType = this.streamTypeRequest();
      var sourceChanged = this._lastAlgorithmImageKey !== null && this._lastAlgorithmImageKey !== key;
      var nativeResolution = streamType !== 'legacy' || sourceChanged;
      var forceFresh = num === 1 || nativeResolution;
      this._lastAlgorithmImageKey = key;
      var controller = new AbortController(); this._algorithmImageController = controller;
      this.loading = true; this.loading2 = true; this.imgOpen = false;
      try {
        var response = await this.$http.get(this.$url.url_5000 + '/model_view/image_show', {
          params: { equipment_id: equipmentId, type: forceFresh ? 1 : this.form.type,
            img_resolution: nativeResolution ? '' : this.resolution, stream_type: streamType },
          signal: controller.signal, timeout: 20000,
        });
        if (!this.snapshotStillCurrent(generation, key)) return false;
        var data = response.data;
        if (data.code !== 200) throw new Error(data.msg || '设备截图读取失败');
        if (!/^\d+x\d+$/.test(data.img_resolution || '') || !this.handleTimesData(data.img_resolution)) throw new Error('摄像头未返回有效图像分辨率');
        this.resolution = data.img_resolution;
        this.$set(this.form, 'img_resolution', data.img_resolution);
        // The API static route requires the same Bearer identity as image_show.
        // Native Image requests cannot send that header. Read the JPEG through
        // the authenticated client and share its browser-local URL with both
        // the existing image and canvas code. Keep credentials out of URLs.
        if (!/^\/static\/em_\d+(?:_(?:main|sub))?\.jpg$/.test(data.msg || '')) throw new Error('设备截图地址无效');
        var imageResponse = await this.$http.get(this.$url.url_5000 + data.msg, {
          params: { timestamp: Date.now() }, responseType: 'blob',
          signal: controller.signal, timeout: 20000,
        });
        if (!this.snapshotStillCurrent(generation, key)) return false;
        var blob = imageResponse.data;
        if (!blob || !blob.size || !/^image\/(?:jpeg|png)$/i.test(blob.type || '')) throw new Error('设备未返回有效图片，请刷新重试');
        this._algorithmImageObjectUrl = URL.createObjectURL(blob);
        this.imgurl = this._algorithmImageObjectUrl;
        var image = new Image(); this._algorithmSnapshotImage = image;
        image.onload = () => {
          if (!this.snapshotStillCurrent(generation, key)) return;
          this.algorithmSnapshotReadyKey = key;
          this.imgOpen = true; this.loading = false;
          this.$nextTick(() => {
            if (!this.snapshotStillCurrent(generation, key)) return;
            if (this.area2 && this.$refs.mycanvas2) this.initCanvas2();
            else if (this.$refs.mycanvas) {
              if (this.drawLineOpen || (this.mark_list3 && this.mark_list3.length)) this.initCanvas4();
              else this.initCanvas();
            }
            if (typeof this.initCanvas_model === 'function') this.initCanvas_model();
          });
        };
        image.onerror = () => {
          if (!this.snapshotStillCurrent(generation, key)) return;
          this.loading = false; this.imgOpen = false;
          this.releaseAlgorithmImageObjectUrl();
          this.$message({ type: 'warning', message: '图片加载失败，请刷新重试' });
        };
        image.src = this.imgurl;
        return true;
      } catch (error) {
        if (this.snapshotStillCurrent(generation, key) && !controller.signal.aborted) {
          this.loading = false; this.imgOpen = false;
          this.$message({ type: 'warning', message: error.message || '截图读取失败，请刷新重试' });
        }
        return false;
      } finally {
        if (this._algorithmImageController === controller) this._algorithmImageController = null;
      }
    },
    canSaveAlgorithmSource() {
      if (!this._algorithmSourceEdited || (!this.loading && this.algorithmSnapshotReadyKey === this.streamSourceKey)) return true;
      this.$message({ type: 'warning', message: '请等待所选码流图片加载完成后保存' });
      return false;
    },
  },
};

// Keep task values independent from the template defaults used to fill new keys.
var algorithmTemplateParameters={
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

// Runtime counters are displayed separately from the editable task configuration.
var algorithmPeopleCounts={
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
      return this.algorithmPeopleEnteringCount == null ? '0' : String(this.algorithmPeopleEnteringCount);
    },
    algorithmPeopleExitingDisplay() {
      return this.algorithmPeopleExitingCount == null ? '0' : String(this.algorithmPeopleExitingCount);
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

// Counting geometry is stored in original video pixels, independent of the editor scale.
var algorithmCountingScene={
  data() {
    return { algorithmCountingScene: 'uniqueness', algorithmCountingPoints: [],
      algorithmCountingDirection: 'right', algorithmCountingResidenceFrames: 3,
      algorithmCountingDrawing: false, algorithmCountingGeometryError: '' };
  },
  computed: {
    algorithmCountingBoarding() { return this.algorithmCountingScene === 'boarding'; },
    algorithmCountingEnteringLabel() { return '进入人数（累计）'; },
    algorithmCountingExitingLabel() { return '离开人数（累计）'; },
    algorithmCountingGeometryHint() {
      return this.algorithmCountingBoarding
        ? '沿乘车点边界绘制闭合区域。绿色IN进入区域，红色OUT离开区域。目标从区域外进入并在区域内消失计上车；反向计下车。原地消失、进入后折返均不计数，短暂遮挡会继续跟踪。'
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
          if (window.PlatformCountGeometry && window.PlatformCountGeometry.render(canvas, [], {
              scene: this.algorithmCountingScene, area_type: this.algorithmCountingBoarding ? 'polygon' : 'line',
              points: this.algorithmCountingPoints, direction: this.algorithmCountingDirection
            }, [scale.x * 640, scale.y * 360], {width:640, height:360, vertices:true,
              fillPolygon:true, drawing:this.algorithmCountingDrawing, preview:preview})) return;

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


// Detection polygons and counting geometry use independent source-pixel state.
var algorithmDetectionRoi = {
  data() {
    return {algorithmDetectionRegions: [], algorithmDetectionDraft: [],
      algorithmDetectionDrawing: false, algorithmCountingDrawMode: 'roi',
      algorithmDetectionEdited: false};
  },
  watch: {
    'form.conf_area': {immediate:true, handler(value) {this.restoreAlgorithmDetectionRegions(value);}},
    'form.Algorithm_library_id'(value, previous) {if(String(value)!==String(previous))this.algorithmCountingDrawMode='roi';},
  },
  methods: {
    restoreAlgorithmDetectionRegions(raw) {
      let value = raw;
      if (typeof value === 'string') {
        try {value = JSON.parse(value);} catch (_) {
          try {value = JSON.parse(value.replace(/'/g, '"'));} catch (ignored) {value = [];}
        }
      }
      value = Array.isArray(value) ? value : [];
      this._algorithmDetectionOriginal = JSON.parse(JSON.stringify(value));
      this.algorithmDetectionRegions = value.filter(Array.isArray).map(region => region.map(point => ({...point,x:Number(point.x),y:Number(point.y)})));
      this.algorithmDetectionRegions.forEach(region=>{
        if(region.length>1&&region[0].x===region[region.length-1].x&&region[0].y===region[region.length-1].y)region.pop();
      });
      this.algorithmDetectionDraft = [];
      this.algorithmDetectionDrawing = false;
      this.algorithmDetectionEdited = false;
      this._algorithmDetectionPointResolution = this.form && (this.form.img_resolution || this.form.conf_img_resolution) || this.resolution;
      if (this.algorithmPeopleCountVisible) this.initAlgorithmCountingCanvas();
    },
    algorithmDetectionPayload() {
      const value = this.algorithmDetectionEdited ? this.algorithmDetectionRegions : this._algorithmDetectionOriginal || this.algorithmDetectionRegions;
      return JSON.parse(JSON.stringify(value || []));
    },
    algorithmDetectionProblem(raw) {
      const points = raw.map(point=>({x:Math.trunc(point.x),y:Math.trunc(point.y)}));
      const scale=this.algorithmCountingScale();
      if (points.length<3 || points.length>64) return '检测区域需要3至64个顶点';
      if (raw.some(point=>!Number.isFinite(point.x)||!Number.isFinite(point.y)||point.x<0||point.y<0||point.x>640*scale.x||point.y>360*scale.y)) return '检测区域超出视频范围';
      if (new Set(points.map(point=>point.x+','+point.y)).size!==points.length) return '检测区域不能包含重复顶点';
      const cross=(a,b,c)=>(b.x-a.x)*(c.y-a.y)-(b.y-a.y)*(c.x-a.x);
      const on=(a,b,c)=>cross(a,b,c)===0&&c.x>=Math.min(a.x,b.x)&&c.x<=Math.max(a.x,b.x)&&c.y>=Math.min(a.y,b.y)&&c.y<=Math.max(a.y,b.y);
      const hits=(a,b,c,d)=>cross(a,b,c)*cross(a,b,d)<0&&cross(c,d,a)*cross(c,d,b)<0||on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b);
      let area=0;
      for(let i=0;i<points.length;i++){
        const a=points[i],b=points[(i+1)%points.length];area+=a.x*b.y-b.x*a.y;
        for(let j=i+1;j<points.length;j++){
          if(j===i+1||i===0&&j===points.length-1)continue;
          if(hits(a,b,points[j],points[(j+1)%points.length]))return '检测区域不能自相交';
        }
      }
      return area ? '' : '检测区域面积不能为零';
    },
    startAlgorithmDetectionDrawing(append) {
      this.algorithmCountingDrawMode='roi';
      this.algorithmDetectionDraft=[];
      this.algorithmDetectionDrawing=true;
      this._algorithmDetectionAppend=append===true;
      this.algorithmCountingGeometryError='';
      this.initAlgorithmCountingCanvas();
    },
    finishAlgorithmDetectionDrawing() {
      const points=this.algorithmDetectionDraft.map(point=>({...point}));
      if(points.length>1&&points[0].x===points[points.length-1].x&&points[0].y===points[points.length-1].y)points.pop();
      const problem=this.algorithmDetectionProblem(points);
      if(problem){this.algorithmCountingGeometryError=problem;this.$message({type:'warning',message:problem});return false;}
      const polygon=points.map(point=>({...point,x:Math.trunc(point.x),y:Math.trunc(point.y),type:'告警区域',color:'#ff0000'}));
      this.algorithmDetectionRegions=this._algorithmDetectionAppend ? this.algorithmDetectionRegions.concat([polygon]) : [polygon];
      this.algorithmDetectionDraft=[];this.algorithmDetectionDrawing=false;this.algorithmDetectionEdited=true;
      this.algorithmCountingGeometryError='';this._algorithmOperationalEdited=true;
      this.initAlgorithmCountingCanvas();return true;
    },
    undoAlgorithmDetectionPoint() {
      this.algorithmDetectionDraft.pop();this.algorithmDetectionDrawing=true;
      this.algorithmCountingGeometryError='';this.initAlgorithmCountingCanvas();
    },
    cancelAlgorithmDetectionDrawing() {
      this.algorithmDetectionDraft=[];this.algorithmDetectionDrawing=false;this.algorithmCountingGeometryError='';
      this.initAlgorithmCountingCanvas();
    },
    clearAlgorithmDetectionRegions() {
      this.algorithmDetectionRegions=[];this.algorithmDetectionDraft=[];this.algorithmDetectionDrawing=false;
      this.algorithmDetectionEdited=true;this._algorithmOperationalEdited=true;this.algorithmCountingGeometryError='';
      this.initAlgorithmCountingCanvas();
    },
    startAlgorithmCountingDrawing() {
      this.algorithmCountingDrawMode='line';
      return algorithmCountingScene.methods.startAlgorithmCountingDrawing.call(this);
    },
    rescaleAlgorithmCountingGeometry(resolution, previous) {
      algorithmCountingScene.methods.rescaleAlgorithmCountingGeometry.call(this,resolution,previous);
      const before=String(this._algorithmDetectionPointResolution||previous||'').split(/x/i).map(Number);
      const after=String(resolution||'').split(/x/i).map(Number);
      if(before.length===2&&after.length===2&&[...before,...after].every(n=>Number.isFinite(n)&&n>0)&&
          (before[0]!==after[0]||before[1]!==after[1])){
        const project=points=>points.map(point=>({...point,x:point.x*after[0]/before[0],y:point.y*after[1]/before[1]}));
        this.algorithmDetectionRegions=this.algorithmDetectionRegions.map(project);
        this.algorithmDetectionDraft=project(this.algorithmDetectionDraft);
        this.algorithmDetectionEdited=true;
      }
      this._algorithmDetectionPointResolution=resolution;
      if(this.algorithmPeopleCountVisible)this.initAlgorithmCountingCanvas();
    },
    validateAlgorithmCountingGeometry() {
      if(this.algorithmPeopleCountVisible&&!this.algorithmCountingBoarding){
        const problem=this.algorithmDetectionDrawing ? '请先完成检测区域绘制，或清空未完成区域' :
          this.algorithmDetectionRegions.map(region=>this.algorithmDetectionProblem(region)).find(Boolean);
        if(problem){this.algorithmCountingGeometryError=problem;this.$message({type:'warning',message:problem});return false;}
      }
      return algorithmCountingScene.methods.validateAlgorithmCountingGeometry.call(this);
    },
    initAlgorithmCountingCanvas() {
      this.$nextTick(()=>{
        if(this._algorithmFormClosed||!this.algorithmPeopleCountVisible)return;
        const canvas=this.$refs.mycanvas;if(!canvas)return;
        canvas.width=640;canvas.height=360;canvas.style.cursor='crosshair';
        const context=canvas.getContext('2d'),scale=this.algorithmCountingScale();
        const roiMode=()=>this.algorithmCountingDrawMode==='roi'&&!this.algorithmCountingBoarding;
        const eventPoint=event=>{const rect=canvas.getBoundingClientRect();return {
          x:Math.round(Math.max(0,Math.min(640,(event.clientX-rect.left)*640/rect.width))*scale.x),
          y:Math.round(Math.max(0,Math.min(360,(event.clientY-rect.top)*360/rect.height))*scale.y)};};
        const draw=preview=>{
          const regions=!this.algorithmCountingBoarding&&this.algorithmDetectionDrawing&&!this._algorithmDetectionAppend ? [] : this.algorithmDetectionRegions;
          window.PlatformCountGeometry.render(canvas,regions,{
            scene:this.algorithmCountingScene,area_type:this.algorithmCountingBoarding?'polygon':'line',
            points:this.algorithmCountingPoints,direction:this.algorithmCountingDirection,boarding_direction:this.algorithmBoardingDirection
          },[scale.x*640,scale.y*360],{width:640,height:360,allowEmpty:true,vertices:!roiMode(),
            fillPolygon:true,drawing:!roiMode()&&this.algorithmCountingDrawing,preview:!roiMode()?preview:null});
          if(!this.algorithmCountingBoarding&&this.algorithmDetectionDraft.length){
            const points=this.algorithmDetectionDraft.map(point=>({x:point.x/scale.x,y:point.y/scale.y}));
            context.strokeStyle='#ff0000';context.fillStyle='#ff0000';context.lineWidth=2;
            context.beginPath();context.moveTo(points[0].x,points[0].y);
            points.slice(1).forEach(point=>context.lineTo(point.x,point.y));
            if(preview&&roiMode()&&this.algorithmDetectionDrawing)context.lineTo(preview.x/scale.x,preview.y/scale.y);
            context.stroke();context.font='12px sans-serif';
            points.forEach((point,index)=>{context.beginPath();context.arc(point.x,point.y,3,0,2*Math.PI);context.fill();
              context.fillText(String(index+1),Math.min(625,point.x+5),Math.max(14,point.y-5));});
          }
        };
        canvas.onclick=null;canvas.onmouseup=null;canvas.oncontextmenu=event=>event.preventDefault();
        canvas.onmousedown=event=>{
          if(event.button!==0||event.detail>1)return;
          const active=roiMode()?this.algorithmDetectionDrawing:this.algorithmCountingDrawing;if(!active)return;
          const points=roiMode()?this.algorithmDetectionDraft:this.algorithmCountingPoints;
          if(points.length>=64){this.$message.warning('最多支持64个顶点');return;}
          const point=eventPoint(event),last=points[points.length-1];
          if(!last||last.x!==point.x||last.y!==point.y)points.push(point);
          if(!roiMode())this._algorithmOperationalEdited=true;
          draw();
        };
        canvas.onmousemove=event=>{if(roiMode()?this.algorithmDetectionDrawing:this.algorithmCountingDrawing)draw(eventPoint(event));};
        canvas.onmouseleave=()=>draw();
        canvas.ondblclick=event=>{event.preventDefault();if(roiMode()){if(this.algorithmDetectionDrawing)this.finishAlgorithmDetectionDrawing();}
          else if(this.algorithmCountingDrawing)this.finishAlgorithmCountingDrawing();};
        draw();
      });
    },
  },
};

var renderAlgorithmDetectionTools=function(){
  const h=this.$createElement,vm=this,roi=this.algorithmCountingDrawMode==='roi'&&!this.algorithmCountingBoarding;
  const button=(label,action,disabled,type)=>h('el-button',{props:{type:type||'text',size:'mini',disabled:!!disabled},on:{click:action}},label);
  const children=[button('刷新图片',()=>vm.handleimg(1))];
  if(!this.algorithmCountingBoarding)children.push(
    button('绘制检测区域',()=>vm.startAlgorithmDetectionDrawing(),false,roi?'primary':'default'),
    button('绘制警戒线',()=>vm.startAlgorithmCountingDrawing(),false,!roi?'primary':'default'));
  else children.push(button('绘制计数区域',()=>vm.startAlgorithmCountingDrawing()));
  if(roi)children.push(button('新增区域',()=>vm.startAlgorithmDetectionDrawing(true)),
    button('撤销区域顶点',()=>vm.undoAlgorithmDetectionPoint(),!vm.algorithmDetectionDraft.length),
    button('完成区域',()=>vm.finishAlgorithmDetectionDrawing(),!vm.algorithmDetectionDrawing),
    button('取消区域绘制',()=>vm.cancelAlgorithmDetectionDrawing(),!vm.algorithmDetectionDrawing),
    button('清空检测区域',()=>vm.clearAlgorithmDetectionRegions(),!vm.algorithmDetectionRegions.length&&!vm.algorithmDetectionDrawing));
  else children.push(button('撤销线顶点',()=>vm.undoAlgorithmCountingPoint(),!vm.algorithmCountingPoints.length),
    button('完成绘制',()=>vm.finishAlgorithmCountingDrawing(),!vm.algorithmCountingDrawing));
  if(!this.algorithmCountingBoarding)children.push(button('切换进出方向',()=>vm.reverseAlgorithmCountingDirection(),vm.algorithmCountingPoints.length<2));
  children.push(h('div',{style:{width:'100%',fontSize:'12px',lineHeight:'1.6',color:'#78869a'},attrs:{role:'status'}},
    this.algorithmCountingBoarding ? this.algorithmCountingGeometryHint :
    '红色闭合区域过滤目标，黄色警戒线判断进出，两者独立保存。按目标脚底点判断是否在区域内；区域外目标不显示、不跟踪、不计数。清空检测区域后按全画面检测。'));
  if(this.algorithmCountingGeometryError)children.push(h('div',{style:{color:'#c45656',fontSize:'12px'},attrs:{role:'alert'}},this.algorithmCountingGeometryError));
  return h('div',{class:'algorithm-counting-tools',style:{display:'flex',flexWrap:'wrap',gap:'8px',alignItems:'center',padding:'6px 0'}},children);
};

var cavdiv=(function(){













var Component={
  mixins: [window.PlatformAlgorithmTemplateAdministrator, algorithmStreamMixin, algorithmTemplateParameters, algorithmPeopleCounts, algorithmCountingScene, algorithmDetectionRoi],
  components: {
    
  },
  name: "sfgl_child",
  props: ['item','conf_id','indexnum','types','configStreamType'],
  watch: {
    configStreamType: {
      immediate: true,
      handler(value) {
        if (!this.form) return;
        var streamType = value === 'main' || value === 'sub' ? value : null;
        if (this.form.stream_type !== streamType) this._algorithmSourceEdited = true;
        this._algorithmDefaultStreamPending = false;
        this.$set(this.form, 'stream_type', streamType);
      },
    },
    // item: {
    //   handler(newVal) {
    //   this.jclxslist = [];
    //   // this.handleChangeCanvas2();
    //   // this.updateConfName();
    //   this.handleChangeSf(newVal.Algorithm_library_id);
    //   // this.getCompute();//获取资源信息
    //   },
    //   deep: true
    // }
    // 'form.algorithm_name': function () {
    //   alert(3)
    //   this.handleChangeCanvas2();
    //   this.updateConfName();
    //   console.log(this.form.Algorithm_library_id)
    //   alert(2)
    //   this.handleChangeSf(this.form.Algorithm_library_id);
    //   this.getCompute();//获取资源信息
    // },
  },
  data() {
    return {
      form: algorithmFirstEditorConfidence.hydrate(this.item),
      // form.Algorithm_library_id:'',
      jclxslist:[],
      isTypeTFS:true,
      selectedOption_type:'',
      dict:{
        equipment_list:[],
      },
      type_jx:false,
      type_qy:false,
      system: window.wgParameter.system,
      version: store.state.version,
      url_5000: this.$url.url_5000,
      StartTime: "",
      EndTime: "",
      model_two_type:'',
      label_list:[],
      confidence:0.6,
      model_path:'',
      selectedOption_model: '类型一',
      title2_model: '',
      dialogVisible2_model: false,
      title2: "",
      selectedOption: '报警',
      dialogVisible2: false,

      alarmTypeDictOptions: [
        {
          label: 'I级报警',
          value: '1',
        },
        {
          label: 'II级报警',
          value: '2',
        },
        {
          label: 'III级报警',
          value: '3',
        }
      ],
      props: {
        checkStrictly: false,
        emitPath: false,
        value: "id",
        label: "equipment_name",
      },
      modelProps: {
        checkStrictly: false,
        emitPath: false,
        value: 'model_id', // 动态选择值字段
        label: 'model_type_name', // 动态选择标签字段
        // children: "children" // 如果子级还有下一级，确保正确指向子选项数组
      },
      modelOptions:[],
      modelSmallOption:[],
      computeOptions: [],//算力资源信息字典
      computeProps: {
        checkStrictly: false,
        emitPath: false,
        value: "id",
        label: "label",
      },
      timesX: 3,
      timesY: 3,
      options1: [],
      options2: [],
      options3: [],
      options4: [],
      resolution: '',
      resolutionOption: [
        { value: '1920x1080', name: '普通' },
        { value: '2688x1520', name: '热成像' },
        { value: '2560x1440', name: '热成像' },
        { value: '1280x720', name: '热成像' },
        { value: '720x576', name: '热成像2' }
      ],
      
      imgurl: "",
      // 图形绘制相关参数（开始）
      isdraw: false, //是否在画图形
      coordinates: [], //一个多边形的坐标信息
      cor_index: 0, //当前多边形的索引
      endtip: false, //是否结束一个多边形的绘制
      //    mark_list: [], //所有多边形的信息
      mark_list: [
        // [
        //   {
        //     x: 135,
        //     y: 49,
        //   },
        //   {
        //     x: 509,
        //     y: 50,
        //   },
        //   {
        //     x: 230,
        //     y: 198,
        //   },
        // ],
      ], //所有多边形的信息
      mark_lists: [], //多边形的信息,最终提交的数据
      PointInArea: false,
      index: null,
      loading: false,
      // 图形绘制相关参数（结束）
      // 图形绘制相关参数（开始）特殊热成像区域
      area2: false,
      isdraw2: false, //是否在画图形
      coordinates2: [], //一个多边形的坐标信息
      cor_index2: 0, //当前多边形的索引
      endtip2: false, //是否结束一个多边形的绘制
      //    mark_list: [], //所有多边形的信息
      mark_list2: [
        // [
        //   {
        //     x: 135,
        //     y: 49,
        //   },
        //   {
        //     x: 509,
        //     y: 50,
        //   },
        //   {
        //     x: 230,
        //     y: 198,
        //   },
        // ],
      ], //所有多边形的信息
      mark_lists2: [], //多边形的信息,最终提交的数据
      PointInArea2: false,
      index2: null,
      loading2: false,
      // 图形绘制相关参数（结束）

      // 图形绘制相关参数（开始）划线相关参数
      area3: false,
      isdraw3: false, //是否在画图形
      coordinates3: [], //一个多边形的坐标信息
      cor_index3: 0, //当前多边形的索引
      endtip3: false, //是否结束一个多边形的绘制
      //    mark_list: [], //所有多边形的信息
      mark_list3: [
        // [
        //   {
        //     x: 135,
        //     y: 49,
        //   },
        //   {
        //     x: 509,
        //     y: 50,
        //   },
        //   {
        //     x: 230,
        //     y: 198,
        //   },
        // ],
      ], //所有多边形的信息
      mark_lists3: [], //多边形的信息,最终提交的数据
      PointInArea3: false,
      index3: null,
      loading3: false,
      // 图形绘制相关参数（结束）

      imgOpen: false, //控制图片的开关
      title: "",
      title2: "",
      title3: "",
      shield_status: 2,
      image_draw_type: 1,
      // 画线相关操作
      drawLineOpen: false,
      selectedOption: '报警',
      usertype:'',
      // 图形绘制相关参数（开始）
      isdraw: false, //是否在画图形
      coordinates: [], //一个多边形的坐标信息
      cor_index: 0, //当前多边形的索引
      endtip: false, //是否结束一个多边形的绘制
      //    mark_list: [], //所有多边形的信息
      mark_list: [
        // [
        //   {
        //     x: 135,
        //     y: 49,
        //   },
        //   {
        //     x: 509,
        //     y: 50,
        //   },
        //   {
        //     x: 230,
        //     y: 198,
        //   },
        // ],
      ], //所有多边形的信息
      mark_lists: [], //多边形的信息,最终提交的数据
      PointInArea: false,
      index: null,
      loading: false,
      // 图形绘制相关参数（结束）
      // 图形绘制相关参数（开始）特殊热成像区域
      area2: false,
      isdraw2: false, //是否在画图形
      coordinates2: [], //一个多边形的坐标信息
      cor_index2: 0, //当前多边形的索引
      endtip2: false, //是否结束一个多边形的绘制
      //    mark_list: [], //所有多边形的信息
      mark_list2: [
        // [
        //   {
        //     x: 135,
        //     y: 49,
        //   },
        //   {
        //     x: 509,
        //     y: 50,
        //   },
        //   {
        //     x: 230,
        //     y: 198,
        //   },
        // ],
      ], //所有多边形的信息
      mark_lists2: [], //多边形的信息,最终提交的数据
      PointInArea2: false,
      index2: null,
      loading2: false,
      // 图形绘制相关参数（结束）

      // 图形绘制相关参数（开始）划线相关参数
      area3: false,
      isdraw3: false, //是否在画图形
      coordinates3: [], //一个多边形的坐标信息
      cor_index3: 0, //当前多边形的索引
      endtip3: false, //是否结束一个多边形的绘制
      //    mark_list: [], //所有多边形的信息
      mark_list3: [
        // [
        //   {
        //     x: 135,
        //     y: 49,
        //   },
        //   {
        //     x: 509,
        //     y: 50,
        //   },
        //   {
        //     x: 230,
        //     y: 198,
        //   },
        // ],
      ], //所有多边形的信息
      mark_lists3: [], //多边形的信息,最终提交的数据
      PointInArea3: false,
      index3: null,
      loading3: false,
      // 图形绘制相关参数（结束）

      imgOpen: false, //控制图片的开关
      title: "",
      title2: "",
      title3: "",
      shield_status: 2,
      image_draw_type: 1,
      // 画线相关操作
      drawLineOpen: false,
      selectedOption: '报警',
      selectedOption_type_s:'',
      pickerOptions: {
        disabledDate(time) {
          // 获取当前日期的零时零分零秒
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          // 禁用今天之后的所有日期和时间
          return time.getTime() > today.getTime();
        },
      },
      coordinates: [],
      coordinates2: [],
      coordinates3: [],
      computeOptions: [],//算力资源信息字典
      computeProps: {
        checkStrictly: false,
        emitPath: false,
        value: "id",
        label: "label",
      },
      checkStatusTime: null,
      flvPlayer: null,
      coordinates_model: [],//类型
      mark_list_model: [],
      mark_lists_model: [],
      selectedOption_model: '类型一',
      title2_model: '',
      dialogVisible2_model: false,
      modelOptions: [],//类型字典
      modelTypeOptions: [],//模板大类
      template_type_id: '',
      stepActive: 0,//步骤条初始为0
      modelSmallOption: [],//小类字典
      modelNameOpen: false,
      modelNamemsg: '',
      // template_data: [],//小类详情信息
      model_template_config_id_num: 1,
      analysisSrc: '',
      // analysisCanvas: '',
      analysisId: '',
      rules:{
        amp: [
          { required: true, message: '扩增比例参数(0-100)', trigger: 'blur' },
        ],
        model_two_type: [
          { required: true, message: '请选择级联解析类型', trigger: 'change' },
        ],
        conf_name: [
          { required: true, message: '请输入任务名称', trigger: 'blur' },
        ],
        Mine_id: [
          { required: true, message: '请选择单位名称', trigger: 'change' },
        ],
        equipment_name: [
          { required: true, message: '请选择报警设备', trigger: 'change' },
        ],
        Algorithm_library_id: [
          { required: true, message: '请选择解析类型', trigger: 'change' },
        ],
        res_type: [
          { required: true, message: '请选择报警等级', trigger: 'change' },
        ],
        resource_id: [
          { required: true, message: '请选择算力资源', trigger: 'change' },
        ],
        confidence: [
          { required: true, message: '请输入置信度', trigger: 'blur' },
          {
          validator: (rule, value, callback) => {
            if (!algorithmFirstEditorConfidence.valid(value)) {
              callback(new Error('置信度必须为0到1之间、以0.01为步长的数字'));
            } else {
              callback();
            }
          },
          trigger: 'blur'
        }
        ],
        sensitivity: [
          { required: true, message: '请输入间隔帧', trigger: 'blur' },
          {
          validator: (rule, value, callback) => {
            if (value < 1 || value > 100) {
              callback(new Error('数字必须在1到100之间'));
            } else {
              callback();
            }
          },
          trigger: 'blur'
        }
        ],
        defense_time_start: [
          { required: true, message: '请选择开始时间', trigger: 'change' },
        ],
        defense_time_end: [
          { required: true, message: '请选择结束时间', trigger: 'change' },
        ],
        duration_time: [
          { required: true, message: '请输入持续时长', trigger: 'blur' },
          {
          validator: (rule, value, callback) => {
            if (value < 1 || value > 100) {
              callback(new Error('数字必须在1到100之间'));
            } else {
              callback();
            }
          },
          trigger: 'blur'
        }
        ],
        interval_time: [
          { required: true, message: '请输入告警间隔', trigger: 'blur' },
          {
          validator: (rule, value, callback) => {
            if (!Number.isInteger(Number(value)) || value < 1 || value > 3600) {
              callback(new Error('告警间隔必须为1到3600秒的整数'));
            } else {
              callback();
            }
          },
          trigger: 'blur'
        }
        ],
      }
    };
  },
  // watch:{
  //     form(val){
  //       this.updateItem()
  //     },
  // },
  computed: {
    
  },
  created() {
    if(localStorage.getItem('user_role_id')){
      this.usertype = localStorage.getItem('user_role_id')
    }
    this.form.Algorithm_library_id = this.form.Algorithm_library_id
    this.jclxslist = this.form.label_list
    this.handleChangeCanvas2();
    this.updateConfName();
    this.handleChangeSf(this.form.Algorithm_library_id);
    this.getCompute();//获取资源信息
  },
  mounted() {
    this.init()
      // setTimeout(()=>{
      //   this.handleimg(1)
      // },1000)
  },
  beforeDestroy() {
    
  },
  destroyed() {
    
  },
  methods: {
    clearss(e){
      this.jclxslist = [];
      return this.handleChangeSf(e, true);
    },
    updateItem(event) {
      this.$emit('update:item', event.target.value); // 发送更新事件到父组件
    },
    goback(){
      this.$router.push({
        path: '/sfgl',
      })
    },
    timeToTimestamp(time) {
        const [hours, minutes, seconds] = time.split(':').map(Number);
        return hours * 3600 + minutes * 60 + seconds;
    },
    sub_fn() { if (!algorithmFirstEditorConfidence.cascadeReady(this)) return false; var _algorithmFirstSavedContext = window.AiMonitorAlgorithmFirstEditor ? window.AiMonitorAlgorithmFirstEditor.beforeSave(this) : null; if (_algorithmFirstSavedContext === false) return false;
      if (!this.validateAlgorithmTemplateParameters()) return Promise.resolve(false);
      if (!this.validateAlgorithmCountingGeometry()) return Promise.resolve(false);
      const validationSourceKey = this.streamSourceKey;
      const validationAlgorithmId = this.form.Algorithm_library_id;
      return new Promise((resolve, reject) => {
      this.$refs['form'].validate((valid) => {
        try {
          if (this._algorithmFormClosed || validationSourceKey !== this.streamSourceKey || validationAlgorithmId !== this.form.Algorithm_library_id) { resolve(false); return; }
          if (valid) {
            // 判断开始结束时间时间
            const timestamp1 = this.timeToTimestamp(this.form.defense_time_start);
            const timestamp2 = this.timeToTimestamp(this.form.defense_time_end);
            if (timestamp1 > timestamp2) {
              this.$message({
                      message: '结束时间不能小于开始时间，请重新选择结束时间!',
                      type: "warning",
                    });
                this.form.defense_time_end = '23:59:59';
                resolve(false);
                return;
            }
            // 1、无需绘制点，2、正常操作
            if (this.shield_status == "1") {
              //拿到分辨率，并赋值
              // 使用 split() 方法将字符串分割成数组
              let parts = this.resolution.split("x");

              // 获取 x 前后的两个数字
              let beforeX = parseInt(parts[0]);
              let afterX = parseInt(parts[1]);
              this.mark_lists = [
                [
                  {
                    x: 0,
                    y: 0,
                    type: 'I级报警',
                    color: '#FF0000',
                  },
                  {
                    x: beforeX,
                    y: 0,
                    type: 'I级报警',
                    color: '#FF0000',
                  },
                  {
                    x: beforeX,
                    y: afterX,
                    type: 'I级报警',
                    color: '#FF0000',
                  },
                  {
                    x: 0,
                    y: afterX,
                    type: 'I级报警',
                    color: '#FF0000',
                  },
                ],
              ];
              this.mark_lists2 = [
                [
                  {
                    x: 0,
                    y: 0,
                  },
                  {
                    x: beforeX,
                    y: 0,
                  },
                  {
                    x: beforeX,
                    y: afterX,
                  },
                  {
                    x: 0,
                    y: afterX,
                  },
                ],
              ];
            } else {
              this.handleData();
            }
            // 模型类型区域标注点处理
            this.handleData_model()
            // 只有模型类型选择为4，深度适配类的时候才需要主动去赋值的情况，其他情况自己选值
            if (this.model_template_config_id_num == 4) {
              this.form.test_type_id = this.options4[0].id
              this.jclxslist = [this.options4[0].test_type_ename]
            }
            // 逆向寻找设备ID
            const resource = this.resolveAlgorithmResource(this.form.resource_id);
            if (!resource) { this.$message({ type: 'warning', message: '请选择有效的计算资源卡' }); resolve(false); return; }
            const computing_id = resource.computingId;
            this.$set(this.form, 'resource_id', resource.resourceId);
            // 取出小类详情信息template_data
            let template_data = JSON.stringify(this.getModelSmallDetail())
          
            let model_template_type_id
            this.modelOptions.forEach(item => {
              item.children.forEach(v => {
                if (v.id == this.form.model_template_config_id) {
                  model_template_type_id = item.id
                }
              })
            })
            const all_type_list = [];
            this.options4.forEach((item)=>{
              all_type_list.push(item.test_type_ename)
            })
            let strs = '';
            if((Array.isArray(this.dict && this.dict.algorithm_list_five) ? this.dict.algorithm_list_five.length : 0) != 0){
              strs = this.dict.algorithm_list_five[0].algorithm_path
            }
            // 新增
            var forms = {
              conf_name: this.form.conf_name,
              Algorithm_library_id: this.form.Algorithm_library_id,
              Mine_id: this.form.Mine_id,
              Equipment_id: this.form.equipment_name,
              stream_type: this.streamTypeRequest(),
              // conf_object: "",
              conf_area: this.algorithmPeopleCountVisible ? this.algorithmDetectionPayload() : this.drawLineOpen ? this.mark_lists3 : this.mark_lists,
              cross_line_area: this.algorithmPeopleCountVisible ? JSON.stringify(this.algorithmCountingPayload()) : this.form.cross_line_area,
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.jclxslist),
              shield_status: this.shield_status,
              tem_frames: this.form.tem_frames,
              confidence: this.form.confidence,
              tem_conf_area: this.mark_lists2,
              draw_type: this.algorithmPeopleCountVisible ? '1' : this.drawLineOpen ? '2' : '1',
              img_resolution: this.resolution,
              duration_time: this.form.duration_time,
              interval_time: this.form.interval_time,
              image_draw_type: this.image_draw_type,
              Algorithm_config_ps: this.form.Algorithm_config_ps,
              scene_typename: this.form.scene_typename,
              sensitivity: this.form.sensitivity,
              resource_id: this.form.resource_id,
              computing_id: computing_id,
              resource_id_old: this.form.resource_id_old,
              defense_time_start: this.form.defense_time_start,
              defense_time_end: this.form.defense_time_end,
              model_template_config_id: this.form.model_template_config_id,
              model_template_type_id: model_template_type_id,
              template_list_area: this.mark_lists_model,
              template_small_id: this.form.template_small_id,
              res_type: this.form.res_type,
              run_time: this.form.run_time,
              priority: this.form.priority,
              template_data: template_data,
              model_two_data: JSON.stringify([{
                label_list:this.label_list,
                confidence:this.confidence,
                model_path: strs,
                algorithm_type_list: all_type_list
              }]),
              amp: this.form.amp,
              alg_select_type: this.form.alg_select_type,
              model_two_type: this.form.model_two_type,
            };
            // 修改(修改的时候list标注数据记得处理)
            let forms2 = {
              id: this.form.id,
              conf_name: this.form.conf_name,
              Algorithm_library_id: this.form.Algorithm_library_id,
              Mine_id: this.form.Mine_id,
              Equipment_id: this.form.equipment_name,
              stream_type: this.streamTypeRequest(),
              // conf_object: "",
              conf_area: this.algorithmPeopleCountVisible ? JSON.stringify(this.algorithmDetectionPayload()) : this.drawLineOpen ? JSON.stringify(this.mark_lists3) : JSON.stringify(this.mark_lists),
              cross_line_area: this.algorithmPeopleCountVisible ? JSON.stringify(this.algorithmCountingPayload()) : this.form.cross_line_area,
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.jclxslist),
              shield_status: this.shield_status,
              tem_frames: this.form.tem_frames,
              confidence: this.form.confidence,
              tem_conf_area: JSON.stringify(this.mark_lists2),
              draw_type: this.algorithmPeopleCountVisible ? '1' : this.drawLineOpen ? '2' : '1',
              img_resolution: this.resolution,
              duration_time: this.form.duration_time,
              interval_time: this.form.interval_time,
              image_draw_type: this.image_draw_type,
              Algorithm_config_ps: this.form.Algorithm_config_ps,
              scene_typename: this.form.scene_typename,
              sensitivity: this.form.sensitivity,
              resource_id: this.form.resource_id,
              computing_id: computing_id,
              resource_id_old: this.form.resource_id_old,
              defense_time_start: this.form.defense_time_start,
              defense_time_end: this.form.defense_time_end,
              model_template_config_id: this.form.model_template_config_id,
              model_template_type_id: model_template_type_id,
              template_list_area: JSON.stringify(this.mark_lists_model),
              template_small_id: this.form.template_small_id,
              res_type: this.form.res_type,
              template_data: template_data,
              run_time: this.form.run_time,
              priority: this.form.priority,
              model_two_data: JSON.stringify([{
                label_list:this.label_list,
                confidence:this.confidence,
                model_path: strs,
                algorithm_type_list: all_type_list
              }]),
              amp: this.form.amp,
              alg_select_type: this.form.alg_select_type,
              model_two_type: this.form.model_two_type,
            };
            if(this.conf_id){
              this.item.model_template_type_id = this.form.model_template_config_id
              this.item.conf_area= forms2.conf_area
              this.item.cross_line_area = forms2.cross_line_area;
              if (this.algorithmPeopleCountVisible) this.item.draw_type = '1';
              this.item.img_resolution = forms2.img_resolution
              this.item.stream_type = this.form.stream_type;
              this.item.computing_id = forms2.computing_id
              this.item.shield_status = forms2.shield_status
              this.item.label_list = forms2.label_list
              
              this.item.confidence = forms2.confidence
              this.item.sensitivity = forms2.sensitivity
              this.item.defense_time_start = forms2.defense_time_start
              this.item.defense_time_end = forms2.defense_time_end
              this.item.duration_time = forms2.duration_time
              this.item.interval_time = forms2.interval_time
              this.item.Algorithm_config_ps = forms2.Algorithm_config_ps
              
              this.item.model_template_config_id = forms2.model_template_config_id
              this.item.template_small_id = forms2.template_small_id
              this.item.template_data = forms2.template_data
              this.item.amp = forms2.amp
              this.item.model_two_type = forms2.model_two_type
              this.item.res_type = forms2.res_type
              this.item.resource_id = forms2.resource_id
              
            }else{
              this.item.model_template_type_id = this.form.model_template_config_id
              this.item.conf_area= forms.conf_area
              this.item.cross_line_area = forms.cross_line_area;
              if (this.algorithmPeopleCountVisible) this.item.draw_type = '1';
              this.item.img_resolution = forms.img_resolution
              this.item.stream_type = this.form.stream_type;
              this.item.computing_id = forms.computing_id
              this.item.shield_status = forms.shield_status
              this.item.label_list = forms.label_list
              
              this.item.confidence = forms.confidence
              this.item.sensitivity = forms.sensitivity
              this.item.defense_time_start = forms.defense_time_start
              this.item.defense_time_end = forms.defense_time_end
              this.item.duration_time = forms.duration_time
              this.item.interval_time = forms.interval_time
              this.item.Algorithm_config_ps = forms.Algorithm_config_ps
              
              this.item.model_template_config_id = forms.model_template_config_id
              this.item.template_small_id = forms.template_small_id
              this.item.template_data = forms.template_data
              this.item.amp = forms.amp
              this.item.model_two_type = forms.model_two_type
              this.item.res_type = forms.res_type
              this.item.resource_id = forms.resource_id
            }
             this.removeAlgorithmPeopleCountFields(this.item);
             resolve(true);
          } else {
            resolve(false);
          }
        } catch (error) { reject(error); }
        });
      });
    },
    // 获取小类详情的数据
    getModelSmallDetail() {
      return this.algorithmTemplatePayload();
    },
    // 提交数据处理
    handleData() {
      if (this.mark_list.length != 0 && (!this.drawLineOpen || this.algorithmPeopleCountVisible)) {
        let data = this.mark_list
        let arr = []
        for (let i = 0; i < data.length; i++) {
          arr.push(
            this.mark_list[i].map(v => ({
              x: (v.x * this.timesX).toFixed(0),
              y: (v.y * this.timesY).toFixed(0),
              type: v.type,
              color: v.color,
            }))
          )
        }
        this.mark_lists = arr
      } else {
        this.mark_lists = [];
      }
      // 热成像
      if (this.mark_list2.length != 0) {
        let data2 = this.mark_list2[0];
        let arr2 = [];
        for (let i = 0; i < data2.length; i++) {
          let x = (data2[i].x * this.timesX).toFixed(0);
          let y = (data2[i].y * this.timesY).toFixed(0);
          arr2.push({
            x,
            y,
          });
        }
        this.mark_lists2 = [arr2];
      } else {
        this.mark_lists2 = [];
      }

      // 画线
      if (this.mark_list3.length != 0 && this.drawLineOpen) {
        let data = this.mark_list3;
        let arr3 = [];
        let arr_w = [];
        for (let w = 0; w < data.length; w++) {
          for (let i = 0; i < data[w].length; i++) {
            // let x = data[w][i].x * 3;
            // let y = data[w][i].y * 3;
            let x = (data[w][i].x * this.timesX).toFixed(0);
            let y = (data[w][i].y * this.timesY).toFixed(0);
            arr3.push({
              x,
              y,
              type: '报警',
            });
          }
          arr_w.push(arr3)
          arr3 = []
        }
        this.mark_lists3 = [...arr_w];
        this.mark_lists3.sort((a, b) => {
          // 按照第一个对象的x值进行比较
          return b[0].y - a[0].y;
        });
      } else {
        this.mark_lists3 = [];
      }
    },
    // 处理模型区域数据
    handleData_model() {
      if (this.mark_list_model.length != 0) {
        let data = this.mark_list_model
        let brr = []
        for (let i = 0; i < data.length; i++) {
          brr.push(
            this.mark_list_model[i].map(v => ({
              x: (v.x * this.timesX).toFixed(0),
              y: (v.y * this.timesY).toFixed(0),
              type: v.type,
              color: v.color,
            }))
          )
        }
        this.mark_lists_model = brr
      } else {
        this.mark_lists_model = [];
      }
    },
    countfns(){
      if(this.form.equipment_name != '' && this.form.equipment_name != null && this.form.equipment_name != undefined){
        if(this.form.Algorithm_library_id != '' && this.form.Algorithm_library_id != null && this.form.Algorithm_library_id != undefined){
          this.dict.algorithm_list.forEach((item)=>{
            console.log(item)
            if(item.id == this.form.Algorithm_library_id){
              if(item.algorithm_name == '探放水'){
                this.isTypeTFS = false;
              }else{
                this.isTypeTFS = true;
              }
            }
          })
          this.handleChangeCanvas2();
          this.updateConfName();
          this.handleChangeSf(this.form.Algorithm_library_id);
          this.type_jx=true;
          this.type_qy=true;
        }else{
          this.type_jx = false;
          this.type_qy = false;
        }
      }else{
        this.form.Algorithm_library_id = '';
        this.$message({
          message: '请选择报警设备!',
          type: "warning",
        });
      }
    },
    handleClose2() {
      this.dialogVisible2 = false;
      this.handleUpdateList();
    },
    handleDeleteList() {
      this.coordinates = [];
      this.coordinates2 = [];
      this.coordinates3 = [];//清除当前标注数据
      // 由于鼠标双击的时候，数据已经被提交，所以要从根源上删除该数据
      this.mark_list.pop()
    },
    handleUpdateList() {
      // console.log(this.mark_list);
      // console.log(this.selectedOption);
      let color = {
        'I级报警': '#FF0000',
        // 'II级报警': '#FFA500',
        // 'III级报警': '#FCFF00',
        // '消除': '#8a8383',
        '类型一': '#67C23A',
        '类型二': '#FFA500',
        '类型三': '#FCFF00',
      }
      this.mark_list[this.mark_list.length - 1] = this.mark_list[this.mark_list.length - 1].map(v => ({
        ...v,
        type: this.selectedOption,
        color: color[this.selectedOption]
      }));
      this.coordinates = []
      this.initCanvas()
      // console.log("数据一致性检查-------------------------");
      // console.log(this.mark_list);
      this.dialogVisible2 = false
    },
    // 删除一个小类详情
    removeItem(index) {
      this.removeAlgorithmTemplateParameter(index);
    },
    // 新增一个小类详情
    addItem() {
      this.addAlgorithmTemplateParameter();
    },
    handleChangeSf(id, userSelected = false) { const _algorithmFirstDetectionRequest = {form: this.form, id: id};
      const generation = ++this._algorithmModelGeneration;
      const form = this.form;
      const modelBefore = form.model_template_config_id, smallBefore = form.template_small_id;
      if (userSelected) { this._algorithmModelWasSelected = true; this._algorithmScrollPending = true; this._algorithmDetectionEdited = false; this._algorithmSelectedModelId = String(id); }
      const current = () => !this._algorithmFormClosed && generation === this._algorithmModelGeneration && form === this.form && String(id) === String(this.form.Algorithm_library_id);
      return this.$http
        .get(this.$url.url_5000 + "/model_view/Algorithm_type_select", {
          params: {
            id,
            // id: 1,
          },
        })
        .then(async (response) => {
          if (!current()) return;
          const data = response.data.data || {};
          const model = (data.model_data || [])[0];
          const type = (data.model_type_data || [])[0];
          const small = (data.template_small_data || [])[0];
          (this.options4 = data.algorithm_data || [], algorithmFirstEditorConfidence.restoreDetection(this, this.options4, _algorithmFirstDetectionRequest));
          this.selectedOption = data.show_status;
          this.selectedOption_type_s = data.show_status;
          const selectedByUser = userSelected || this._algorithmSelectedModelId === String(id);
          const useDefaults = selectedByUser || !this.algorithmIsEditing();
          if (useDefaults && model && this.form.model_template_config_id === modelBefore) this.$set(this.form, 'model_template_config_id', model.id);
          const smallOptions = type ? this.getModelSmallDict2(type.id, current) : Promise.resolve();
          let details = Promise.resolve();
          if (useDefaults && small && this.form.template_small_id === smallBefore) {
            this.$set(this.form, 'template_small_id', small.id);
            details = this.handleChangeTemplateSmall(current, true);
          } else if (!useDefaults && this.form.template_small_id) {
            details = this.handleChangeTemplateSmall(current);
          }
          this.applyAlgorithmDefaults(this.options4, selectedByUser);
          await Promise.all([smallOptions, details, this._algorithmComputePromise]);
          if (current()) { this._algorithmSelectedModelId = null; this.scrollToAlgorithmSave(); }
        })
        .catch((rek) => {
          console.log(rek);
        });
    },
    //选择小类，查询相关配置详情
    handleChangeTemplateSmall(isCurrent, replace = false) {
      return this.loadAlgorithmTemplateParameters(modelApi.getModelSmallDetail, isCurrent, replace);
    },
    getModelSmallDict2(id, isCurrent) {
      this.model_template_config_id_num = id
      return this.$http.get(modelApi.getModelSmallList, {
        params: {
          page: 1,
          per_page: 15,
          model_template_type_id: id,
        }
      }).then(response => {
        if (this._algorithmFormClosed || typeof isCurrent === 'function' && !isCurrent()) return;
        this.modelSmallOption = response.data.data.data;
        // console.log("===================",this.modelSmallOption)
      }).catch(rek => {
        console.log(rek)
      })
    },
    // 当遮挡配置选择为遮挡的时候，清空标注区域。
    handleChangeShield_status() {
      this.handleDrewAgain();
    },
    // 热成像区域相关
    async handleChangeCanvas2(data) {
      var info = await this.loadStreamCapabilities(data || this.algorithmEquipmentId());
      if (!info || this._algorithmFormClosed) return false;
      this.area2 = String(info.data && info.data.equipment_code) === '201';
      return this.handleimg();
    },
    // 通过选中的分辨率，来计算渲染比值timesX和timesY
    handleTimesData(resolution) {
      var parts = String(resolution || '').split('x');
      var width = Number(parts[0]), height = Number(parts[1]);
      if (parts.length !== 2 || !Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return false;
      this.timesX = width / 640;
      this.timesY = height / 360;
      return true;
    },
    
    handleimg(num) { return this.requestAlgorithmImage(num); },
    
    /* 画布初始化 */
    initCanvas() {
      if (this.algorithmPeopleCountVisible) return this.initAlgorithmCountingCanvas();
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs.mycanvas;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        // 计算使用变量
        // this.mark_list = []
        var list = this.mark_list; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        var coordinates = this.coordinates
        // 若list长度不为0, 则显示已标记框
        let this_ = this
        draw_test(cav, list, this.handleChooseType, coordinates);
      });
    },
    // 区域标注类型选择
    handleChooseType() {
      if(this.selectedOption_type_s == '空区域'){
        this.selectedOption = '告警区域'
        this.handleUpdateList()
      }else if(this.selectedOption_type_s == '屏蔽区域'){
        this.title2 = '区域标注类型选择'
        this.selectedOption_type = '屏蔽区域'
        this.dialogVisible2 = true
      }else if(this.selectedOption_type_s == '检测区域'){
        this.title2 = '区域标注类型选择'
        this.selectedOption_type = '检测区域'
        this.dialogVisible2 = true
      }else{
        this.selectedOption = '告警区域'
        this.title2 = '区域标注类型选择'
        this.dialogVisible2 = true
        this.handleUpdateList()
      }
    },
    // 类型标注类型选择
    handleChooseType_model() {
      this.selectedOption_model = '类型一'
      this.title2_model = '模型类型选择'
      this.dialogVisible2_model = true
    },
    initCanvas_model() {
      // this.$nextTick(() => {
      //   // 初始化canvas宽高
      //   let cav = this.$refs.mycanvas_model;
      //   cav.width = "640";
      //   cav.height = "360";
      //   let ctx = cav.getContext("2d");
      //   ctx.strokeStyle = "red";
      //   cav.style.cursor = "crosshair";
      //   // 计算使用变量
      //   // this.mark_list = []
      //   let list = this.mark_list_model; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
      //   let coordinates = this.coordinates_model
      //   // 若list长度不为0, 则显示已标记框
      //   let this_ = this
      //   draw_test(cav, list, this.handleChooseType_model, coordinates);
      // });
    },
    initCanvas2() {
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs.mycanvas2;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        // 计算使用变量
        // this.mark_list = []
        let list = this.mark_list2; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        let coordinates = this.coordinates2
        // 若list长度不为0, 则显示已标记框
        draw_test3(cav, list, coordinates);
      });
    },
    initCanvas4() {
      if (this.algorithmPeopleCountVisible) return this.initAlgorithmCountingCanvas();
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs.mycanvas;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        // 计算使用变量
        // this.mark_list = []
        let list = this.mark_list3; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        let coordinates = this.coordinates3
        // 若list长度不为0, 则显示已标记框
        draw_test4(cav, list, coordinates);
      });
    },
    /* 画布初始化 */
    tableCanvas(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10); // 将宽度转换为整数
      var HH = parseInt(parts[1], 10); // 将高度转换为整数
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs[`tableCanvas_${id}`];
        cav.width = "96";
        cav.height = "54";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        // cav.style.cursor = "crosshair";
        let XX = parseInt(WW / 96, 10)
        let YY = parseInt(HH / 54, 10)
        // if (type == '2') {
        // 计算使用变量
        let res = list;
        let arr = [], arr_w = [];
        for (let w = 0; w < res.length; w++) {
          for (let i = 0; i < res[w].length; i++) {
            let x = Number(res[w][i].x) / XX;
            let y = Number(res[w][i].y) / YY;
            arr.push({
              x,
              y,
              color: res[w][i].color,
            });
          }
          arr_w.push(arr)
          arr = []
        }

        // this.mark_list = []
        // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        // 若list长度不为0, 则显示已标记框
        draw_test2(cav, [...arr_w]);
        // } else {
        //   // 计算使用变量
        //   let res = list[0];
        //   let arr = [];
        //   for (let i = 0; i < res.length; i++) {
        //     let x = Number(res[i].x) / XX;
        //     let y = Number(res[i].y) / YY;
        //     arr.push({
        //       x,
        //       y,
        //     });
        //   }
        //   // this.mark_list = []
        //   // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        //   // 若list长度不为0, 则显示已标记框
        //   draw_test2(cav, [arr]);
        // }
      });
    },
    tableCanvas(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10); // 将宽度转换为整数
      var HH = parseInt(parts[1], 10); // 将高度转换为整数
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs[`tableCanvas_${id}`];
        cav.width = "96";
        cav.height = "54";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        // cav.style.cursor = "crosshair";
        let XX = WW / 96
        let YY = HH / 54
        // if (type == '2') {
        // 计算使用变量
        let res = list;
        let arr = [], arr_w = [];
        for (let w = 0; w < res.length; w++) {
          for (let i = 0; i < res[w].length; i++) {
            let x = Number(res[w][i].x) / XX;
            let y = Number(res[w][i].y) / YY;
            arr.push({
              x,
              y,
              color: res[w][i].color,
            });
          }
          arr_w.push(arr)
          arr = []
        }

        // this.mark_list = []
        // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        // 若list长度不为0, 则显示已标记框
        draw_test2(cav, [...arr_w]);
        // } else {
        //   // 计算使用变量
        //   let res = list[0];
        //   let arr = [];
        //   for (let i = 0; i < res.length; i++) {
        //     let x = Number(res[i].x) / XX;
        //     let y = Number(res[i].y) / YY;
        //     arr.push({
        //       x,
        //       y,
        //     });
        //   }
        //   // this.mark_list = []
        //   // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        //   // 若list长度不为0, 则显示已标记框
        //   draw_test2(cav, [arr]);
        // }
      });
    },
    tableCanvasMax(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10); // 将宽度转换为整数
      var HH = parseInt(parts[1], 10); // 将高度转换为整数
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs[`tableCanvas_tableMax`];
        cav.width = "800";
        cav.height = "400";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        // cav.style.cursor = "crosshair";
        let XX = WW / 800
        let YY = HH / 400
        // if (type == '2') {
        // 计算使用变量
        let res = list;
        let arr = [], arr_w = [];
        for (let w = 0; w < res.length; w++) {
          for (let i = 0; i < res[w].length; i++) {
            let x = Number(res[w][i].x) / XX;
            let y = Number(res[w][i].y) / YY;
            arr.push({
              x,
              y,
              color: res[w][i].color,
            });
          }
          arr_w.push(arr)
          arr = []
        }

        // this.mark_list = []
        // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        // 若list长度不为0, 则显示已标记框
        draw_test2(cav, [...arr_w]);
        // } else {
        //   // 计算使用变量
        //   let res = list[0];
        //   let arr = [];
        //   for (let i = 0; i < res.length; i++) {
        //     let x = Number(res[i].x) / XX;
        //     let y = Number(res[i].y) / YY;
        //     arr.push({
        //       x,
        //       y,
        //     });
        //   }
        //   // this.mark_list = []
        //   // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        //   // 若list长度不为0, 则显示已标记框
        //   draw_test2(cav, [arr]);
        // }
      });
    },
    handleChangeLabelList() { algorithmFirstEditorConfidence.markDetection(this);
      this.markAlgorithmDetectionEdited();
      this.$set(this.form, 'label_list', this.jclxslist.slice());
      if (this.jclxslist.length != 0) {
        const selected = this.options4.find(v => v.test_type_ename == this.jclxslist[0]);
        this.form.test_type_id = selected ? selected.id : '';
      } else {
        this.form.test_type_id = '';
      }
    },
    // 任务名称名字自动化获取
    updateConfName() {
      const { equipment_name, Algorithm_library_id } = this.form;
      console.log(equipment_name, Algorithm_library_id)
      let algorithmName = '';
      let monitorPointName = '';
      // 查找解析类型名称
      if (Algorithm_library_id) {
        const selectedAlgorithm = this.options3.find(option => option.id === Algorithm_library_id);
        algorithmName = selectedAlgorithm ? selectedAlgorithm.algorithm_name : '';
        // algorithmName = (algorithmName.split('_'))[1]
      }

      // 组合监控点名称和解析类型名称
      if (equipment_name) {
        // 假设 cascader 的最后一级是监控点名称
        for (let item of this.options2) {
          // 检查 children 属性是否存在并且是数组
          if (Array.isArray(item.children)) {
            // 使用 find 方法查找具有指定 id 的子项
            const foundChild = item.children.find(child => child.id === equipment_name);
            // 如果找到了匹配项，则返回它的 equipment_name
            if (foundChild) {
              monitorPointName = foundChild.equipment_name;
            }
          }
        }
      }
      // if (equipment_name && Algorithm_library_id) {
      //   this.form.conf_name = `${monitorPointName}-${algorithmName}`;
      //   // this.form.conf_name = `${monitorPointName}-${algorithmName}`;
      //   this.$http.post(findModelName, {
      //     conf_name: this.form.conf_name
      //   }).then(response => {
      //     if (response.data.code == 400) {
      //       this.modelNameOpen = true
      //       this.modelNamemsg = response.data.msg
      //     } else {
      //       this.modelNamemsg = response.data.msg
      //       this.modelNameOpen = false
      //     }
      //   }).catch(rek => {
      //     console.log(rek)
      //   })
      // } else {
      //   this.form.conf_name = '';
      // }
      // if(this.form.conf_name == '' || this.form.conf_name == null || this.form.conf_name == undefined){
      //   this.conf_name_note = '';
      //   this.conf_name_type = false;
      //   this.form.conf_name = '';
      // }else{
      //   this.conf_name_note = this.form.conf_name;
      //   this.conf_name_type = true;
      //   this.form.conf_name = '';
      // }
    },
    // 获取算力资源信息
    getCompute() {
      this._algorithmComputePromise = this.$http.get(compute)
        .then(response => {
          if (this._algorithmFormClosed) return;
          this.computeOptions = this.transformData(response.data.data);
          this.applyAlgorithmAdmission();
          this.applyAlgorithmResourceDefault();
        }).catch(() => {});
      return this._algorithmComputePromise;
    },
    generateRandomId() {
      return Math.random().toString(36).substr(2, 9); // 生成随机 ID
    },
    transformData(rawData) {
      return this.sortAlgorithmResources(rawData);
    },
    // 重绘
    handleDrewAgain() {
      if (this.algorithmPeopleCountVisible) return this.startAlgorithmCountingDrawing();
      this.mark_list3 = [];
      this.mark_list = [];
      this.coordinates = [];
      this.coordinates3 = [];
      if (this.drawLineOpen) {
        this.initCanvas4();
      } else {
        this.initCanvas();
      }
    },
    // 类型重绘
    handleDrewAgain_model() {
      this.mark_list_model = [];
      this.coordinates_model = [];
      this.initCanvas_model();
    },
    handleDrewAgain2() {
      this.mark_list2 = [];
      this.coordinates2 = [];
      this.initCanvas2();
    },
    // 撤销
    resole() {
      if (this.algorithmPeopleCountVisible) return this.undoAlgorithmCountingPoint();
      if (!this.drawLineOpen) {
        // console.log("当前标注区域", this.coordinates);
        this.coordinates.pop()
      } else {
        this.coordinates3.pop()
      }
    },
    resole_model() {
      this.coordinates_model.pop()
    },
    resole2() {
      this.coordinates2.pop()
    },
    init(){//字典
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: '',
              type: 1
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          if (response.data.code === 200) {
            this.dict = response.data;
            this.options1 = response.data.mine_list;
            // this.form.Mine_id = response.data.mine_list[0].id
            this.options2 = response.data.equipment_list;
            this.options3 = response.data.algorithm_list;
            this.modelOptions = response.data.model_type_template.map(v => {
              return {
                ...v,
                model_id: 'F' + v.id,
                children: v.template_model_data_list.map(child => {
                  return {
                    ...child,
                    model_id: child.id,
                    model_type_name: child.model_name
                  }
                })
              }
            })
            if(this.conf_id){
              this.type_jx = true;
              this.type_qy = true;
              if(this.item.conf_area != '[]' && !this._algorithmModelWasSelected){
                this.handlechange(this.conf_id,this.indexnum)
              }
            }else{
            // setTimeout(() => {
              this.countfns()
            // }, 1000);
            }
            // console.log(9527,this.modelOptions)
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    
    handlechange(data,id) {
      const requestedForm = this.form, requestedAlgorithmId = this.form.Algorithm_library_id;
      this.stepActive = 0
      this.coordinates = [];
      this.coordinates_model = [];
      this.coordinates2 = [];
      this.coordinates3 = [];
      this.$http
        .get(this.$url.url_5000 + "/model_view/algorithm_data_show", {
          params: {
            // algorithm_name: this.conf_name,
            // start_time: this.StartTime,
            // end_time: this.EndTime,
            // page: this.pagenumber,
            // per_page: this.pagesize
            conf_id: data,
            data_id: id,
          },
        })
        .then((response) => {
          if (this._algorithmFormClosed || this._algorithmModelWasSelected || this.form !== requestedForm || this.form.Algorithm_library_id !== requestedAlgorithmId) return;
          if (response.data.code === 200) {
            this.title = "算法修改";
            this.form = algorithmFirstEditorConfidence.hydrate(response.data.datalist);
            this.restoreAlgorithmCountingGeometry(this.form.cross_line_area);
            this.restoreAlgorithmSource();
            this.$set(this.form, 'stream_type', this.configStreamType === 'main' || this.configStreamType === 'sub' ? this.configStreamType : null);
            this.form.model_two_type = response.data.datalist.model_two_type*1
            if(this.form.model_two_data.length){
              this.label_list = this.form.model_two_data[0].label_list;
              this.confidence = algorithmFirstEditorConfidence.confidenceOf(this.form.model_two_data[0]);
              this.model_path = this.form.model_two_data[0].model_path;
            }
            console.log(this.form)
            // this.jclxslist = this.stringToArray(this.jclxslist)
            // console.log(12121212121212121, this.jclxslist)
            this.findModelBigDict(this.form.model_template_config_id)
            // this.handleChangeTemplateSmall()
            // if(this.form.template_data){
            //   this.form.template_data = this.form.template_data.reduce((acc, obj) => {
            //     if (Object.keys(obj).length > 0) {
            //       const key = Object.keys(obj)[0];
            //       acc.push({
            //         key: key,
            //         value: obj[key]
            //       });
            //     }
            //     return acc;
            //   }, []);
            // }
            this.form.template_data = this.normalizeAlgorithmTemplateRows(this.form.template_data);
            if (this.form.tem_frames == '') {
              this.form.tem_frames = '[27,37]'
            }
            if (this.form.confidence == null || this.form.confidence === '') {
              this.form.confidence = 0.6
            }
            this.drawLineOpen = this.form.draw_type == '2' ? true : false
            this.image_draw_type = this.form.image_draw_type
            this.resolution = this.form.img_resolution
            this.form.resource_id_old = this.form.resource_id
            this.handleTimesData(this.resolution)
            // console.log(this.form);
            // console.log("147369", this.drawLineOpen, this.area2);
            // this.form.Mine_id = response.data.datalist.Mine_id;
            this.shield_status = Number(response.data.datalist.shield_status);
            this.dialogVisible = true;
            this.handleSelect();
            this.handleChangeSf(this.form.Algorithm_library_id);
            this.form.equipment_name = response.data.datalist.Equipment_id;

            this.handleimg();

            // 将list字符串转为可用数组
            if (this.form.draw_type == '2') {
              let arr = JSON.parse(response.data.datalist.conf_area.replace(/'/g, '"')); //这里拿到的数据是字符串，需要转换为数组
              let jia = [];
              let jia_w = [];
              for (let w = 0; w < arr.length; w++) {
                for (let i = 0; i < arr[w].length; i++) {
                  // let x = arr[w][i].x / 3;
                  // let y = arr[w][i].y / 3;
                  let x = arr[w][i].x / this.timesX;
                  let y = arr[w][i].y / this.timesY;
                  jia.push({
                    x,
                    y,
                  });
                }
                jia_w.push(jia)
                jia = []
              }
              this.mark_list3 = [...jia_w]; //给数组赋值，方便再次修改的时候提交数据
            } else {
              let arr = JSON.parse(response.data.datalist.conf_area.replace(/'/g, '"')); //这里拿到的数据是字符串，需要转换为数组
              let jia = [];
              let jia_w = [];
              for (let w = 0; w < arr.length; w++) {
                for (let i = 0; i < arr[w].length; i++) {
                  let x = arr[w][i].x / this.timesX;
                  let y = arr[w][i].y / this.timesY;
                  jia.push({
                    x,
                    y,
                    type: arr[w][i].type,
                    color: arr[w][i].color,
                  });
                }
                jia_w.push(jia)
                jia = []
              }
              this.mark_list = [...jia_w]; //给数组赋值，方便再次修改的时候提交数据
            }
            (() => {
              let arr = JSON.parse(response.data.datalist.template_list_area.replace(/'/g, '"')); //这里拿到的数据是字符串，需要转换为数组
              let jia = [];
              let jia_w = [];
              for (let w = 0; w < arr.length; w++) {
                for (let i = 0; i < arr[w].length; i++) {
                  let x = arr[w][i].x / this.timesX;
                  let y = arr[w][i].y / this.timesY;
                  jia.push({
                    x,
                    y,
                    type: arr[w][i].type,
                    color: arr[w][i].color,
                  });
                }
                jia_w.push(jia)
                jia = []
              }
              this.mark_list_model = [...jia_w]; //给数组赋值，方便再次修改的时候提交数据
            })();

            // this.handleimg();

            let tem_conf_area = response.data.datalist.tem_conf_area;
            const editedSourceKey = this.streamSourceKey;
            this.loadStreamCapabilities(this.algorithmEquipmentId())
              .then((info) => {
                if (!info || this._algorithmFormClosed || editedSourceKey !== this.streamSourceKey) return;
                const response = { data: info };
                if (response.data.data.equipment_code == "201") {
                  this.area2 = true;
                  let arr2 = Array.isArray(tem_conf_area) ? tem_conf_area : tem_conf_area ? JSON.parse(String(tem_conf_area).replace(/'/g, '"')) : [];
                  const thermalPoints = Array.isArray(arr2) && Array.isArray(arr2[0]) ? arr2[0] : [];
                  let jia2 = [];
                  for (let i = 0; i < thermalPoints.length; i++) {
                    // let x = arr2[0][i].x / 3;
                    // let y = arr2[0][i].y / 3;
                    let x = thermalPoints[i].x / this.timesX;
                    let y = thermalPoints[i].y / this.timesY;
                    jia2.push({
                      x,
                      y,
                    });
                  }
                  this.mark_list2 = jia2.length ? [jia2] : []; // Empty thermal regions stay empty.
                  // 进行热成像区域的canvas加载
                  if (this.$refs.mycanvas2) this.initCanvas2();
                } else {
                  this.area2 = false;
                }
              });
            // this.handleChangeCanvas2(this.form.equipment_name);
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    
    handleSelect(a) {
      // let param = new URLSearchParams();
      // param.append("mine_id", this.mkname);
      if (a === 1) {
        this.form.equipment_name = "";
      }
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: this.form.Mine_id,
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          // console.log(response);
          if (response.data.code === 200) {
            this.options1 = response.data.mine_list;
            // this.form.Mine_id = response.data.mine_list[0].id
            this.options2 = response.data.equipment_list;
            this.options3 = response.data.algorithm_list;
            // this.options4=response.data.test_type_list
            this.modelOptions = response.data.model_type_template.map(v => {
              return {
                ...v,
                model_id: 'F' + v.id,
                children: v.template_model_data_list.map(child => {
                  return {
                    ...child,
                    model_id: child.id,
                    model_type_name: child.model_name
                  }
                })
              }
            })
            // console.log(9527,this.modelOptions)
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    findModelBigDict(id) {
      this.modelOptions.forEach(item => {
        let res = item.children.find(v => v.id == id)
        if (res) {
          this.getModelSmallDict([item.model_id])
          return
        }
      })
    },
    extractNumberFromF(str) {
      const match = str.match(/^F(\d+)$/);
      return match ? parseInt(match[1], 10) : NaN;
    },
    getModelSmallDict(value) {
      let id = this.extractNumberFromF(value[0])
      this.model_template_config_id_num = id
      this.$http.get(modelApi.getModelSmallList, {
        params: {
          page: 1,
          per_page: 15,
          model_template_type_id: id,
        }
      }).then(response => {
        this.modelSmallOption = response.data.data.data;
      }).catch(rek => {
        console.log(rek)
      })
    },
  },
};

/* algorithm-drawing-repair-v1 */
(function () {
  'use strict';
  var boardingSupported = true;
  function resetCanvas(canvas) {
    if (!canvas) return;
    if (canvas._algorithmDragCleanup) canvas._algorithmDragCleanup();
    ['onclick', 'onmousedown', 'onmouseup', 'onmousemove', 'onmouseleave',
      'ondblclick', 'oncontextmenu', 'onkeydown'].forEach(function (key) { canvas[key] = null; });
  }
  function undoPolygon(view, coordinates, polygons, initialize) {
    var draft = view[coordinates];
    if (!draft.length && view[polygons].length) {
      draft = view[polygons].pop().map(function (point) { return Object.assign({}, point); });
      if (draft.length > 1 && draft[0].x === draft[draft.length - 1].x && draft[0].y === draft[draft.length - 1].y) draft.pop();
      view[coordinates] = draft;
    }
    if (!draft.length) return;
    draft.pop();
    view._algorithmOperationalEdited = true;
    view[initialize]();
  }
  var methods = Component.methods;
  methods.resole = function () {
    if (this.algorithmPeopleCountVisible) {
      if (!this.algorithmCountingBoarding && this.algorithmCountingDrawMode === 'roi') return this.undoAlgorithmDetectionPoint();
      return this.undoAlgorithmCountingPoint();
    }
    if (this.drawLineOpen) {
      this.mark_list3 = []; this.coordinates3 = []; this._algorithmOperationalEdited = true;
      this.initCanvas4();
    } else undoPolygon(this, 'coordinates', 'mark_list', 'initCanvas');
  };
  methods.resole2 = function () { undoPolygon(this, 'coordinates2', 'mark_list2', 'initCanvas2'); };
  methods.resole_model = function () { undoPolygon(this, 'coordinates_model', 'mark_list_model', 'initCanvas_model'); };

  // Keep the same canvas element while replacing all handlers when tools change.
  // The original initializers still own drawing, dragging and coordinate scale.
  ['initCanvas', 'initCanvas4', 'initCanvas2', 'initCanvas_model'].forEach(function (name) {
    var original = methods[name];
    if (!original) return;
    methods[name] = function () {
      var canvas = this.$refs && this.$refs[name === 'initCanvas2' ? 'mycanvas2' : name === 'initCanvas_model' ? 'mycanvas_model' : 'mycanvas'];
      resetCanvas(canvas);
      return original.apply(this, arguments);
    };
  });
  var originalCanvas = algorithmDetectionRoi.methods.initAlgorithmCountingCanvas;
  algorithmDetectionRoi.methods.initAlgorithmCountingCanvas = function () {
    resetCanvas(this.$refs && this.$refs.mycanvas);
    return originalCanvas.apply(this, arguments);
  };
  var undoCounting = algorithmCountingScene.methods.undoAlgorithmCountingPoint;
  algorithmCountingScene.methods.undoAlgorithmCountingPoint = function () {
    if (!this.algorithmCountingPoints.length) return;
    this.algorithmCountingDrawMode = 'line';
    return undoCounting.apply(this, arguments);
  };
  var undoRegion = algorithmDetectionRoi.methods.undoAlgorithmDetectionPoint;
  algorithmDetectionRoi.methods.undoAlgorithmDetectionPoint = function () {
    if (!this.algorithmDetectionDraft.length) return;
    this.algorithmCountingDrawMode = 'roi';
    return undoRegion.apply(this, arguments);
  };

  // Legacy boarding configurations ignored left/right. A separate optional
  // field keeps their existing inward meaning, including historical "left".
  var sceneData = algorithmCountingScene.data;
  algorithmCountingScene.data = function () {
    return Object.assign(sceneData.call(this), { algorithmBoardingDirection: 'inward' });
  };
  var restore = algorithmCountingScene.methods.restoreAlgorithmCountingGeometry;
  algorithmCountingScene.methods.restoreAlgorithmCountingGeometry = function (raw) {
    var value = this.parseAlgorithmCountingGeometry(raw);
    this.algorithmBoardingDirection = value.boarding_direction === 'outward' ? 'outward' : 'inward';
    return restore.apply(this, arguments);
  };
  var sceneChange = algorithmCountingScene.methods.changeAlgorithmCountingScene;
  algorithmCountingScene.methods.changeAlgorithmCountingScene = function (scene) {
    var direction = this.algorithmBoardingDirection;
    var result = sceneChange.apply(this, arguments);
    this.algorithmBoardingDirection = direction;
    return result;
  };
  var payload = algorithmCountingScene.methods.algorithmCountingPayload;
  algorithmCountingScene.methods.algorithmCountingPayload = function () {
    var result = payload.apply(this, arguments);
    if (this.algorithmCountingBoarding && boardingSupported) result.boarding_direction = this.algorithmBoardingDirection;
    return result;
  };
  var reverse = algorithmCountingScene.methods.reverseAlgorithmCountingDirection;
  algorithmCountingScene.methods.reverseAlgorithmCountingDirection = function () {
    if (!this.algorithmCountingBoarding) return reverse.apply(this, arguments);
    if (!boardingSupported) return;
    this.algorithmBoardingDirection = this.algorithmBoardingDirection === 'outward' ? 'inward' : 'outward';
    this._algorithmOperationalEdited = true;
    this.initAlgorithmCountingCanvas();
  };
  algorithmCountingScene.computed.algorithmCountingGeometryHint = function () {
    if (!this.algorithmCountingBoarding) return '依次绘制计数线，完成后点击“完成绘制”。绿色 IN 表示进入，红色 OUT 表示离开；可切换进出方向。';
    return this.algorithmBoardingDirection === 'outward'
      ? '绿色 IN 指向区域外，红色 OUT 指向区域内。区域内到区域外计进入，反向计离开；仅在轨迹结束后确认，原地消失和折返不计数。'
      : '绿色 IN 指向区域内，红色 OUT 指向区域外。区域外到区域内计进入，反向计离开；仅在轨迹结束后确认，原地消失和折返不计数。';
  };
  var tools = renderAlgorithmDetectionTools;
  renderAlgorithmDetectionTools = function () {
    var result = tools.apply(this, arguments), view = this;
    if (this.algorithmCountingBoarding && boardingSupported) result.children.splice(3, 0, this.$createElement('el-button', {
      props: { type: 'text', size: 'mini', disabled: this.algorithmCountingPoints.length < 3 || Boolean(this.algorithmCountingGeometryProblem()) },
      on: { click: function () { view.reverseAlgorithmCountingDirection(); } }
    }, '切换进出方向'));
    return result;
  };
})();

var render=function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"sfgl_child algorithm-config-model"},[_c('div',{staticClass:"sfpzs"},[_c('el-form',{ref:"form",attrs:{"model":_vm.form,"rules":_vm.rules,"size":"mini","label-width":"110px"}},[(_vm.type_jx)?_c('div',{staticStyle:{"width":"100%","border":"1px dashed #e5e5e5","background":"#f9fafb","border-radius":"10px"}},[_c('el-form-item',{directives:[{name:"show",rawName:"v-show",value:(_vm.model_template_config_id_num != 4),expression:"model_template_config_id_num != 4"}],staticStyle:{"margin-top":"16px"},attrs:{"label":"检测类型"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择检测类型","size":"mini","clearable":"","filterable":"","multiple":""},on:{"change":_vm.handleChangeLabelList},model:{value:(_vm.jclxslist),callback:function ($$v) {_vm.jclxslist=$$v},expression:"jclxslist"}},_vm._l((_vm.options4),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.test_type_cname,"value":item.test_type_ename}})}),1)],1),(_vm.algorithmPeopleCountVisible)?_c('div',{staticClass:"algorithm-people-counts",staticStyle:{"font-size":"12px","line-height":"20px"}},[_c('el-form-item',{attrs:{"label":"人数统计版本"}},[_c('el-select',{attrs:{"aria-label":"人数统计版本"},on:{"change":_vm.changeAlgorithmCountingScene},model:{value:(_vm.algorithmCountingScene),callback:function ($$v) {_vm.algorithmCountingScene=$$v},expression:"algorithmCountingScene"}},[_c('el-option',{attrs:{"label":"唯一性检测装置","value":"uniqueness"}}),_c('el-option',{attrs:{"label":"乘车点","value":"boarding"}})],1)],1),(_vm.algorithmCountingBoarding)?_c('el-form-item',{attrs:{"label":"驻留确认帧数"}},[_c('el-input-number',{attrs:{"min":1,"max":120,"step":1,"precision":0,"aria-label":"驻留确认帧数"},on:{"change":function($event){_vm._algorithmOperationalEdited = true}},model:{value:(_vm.algorithmCountingResidenceFrames),callback:function ($$v) {_vm.algorithmCountingResidenceFrames=$$v},expression:"algorithmCountingResidenceFrames"}}),_c('div',{staticStyle:{"color":"#78869a","font-size":"12px"}},[_vm._v("连续处于区域另一侧达到此帧数后确认，避免边界抖动。")])],1):_vm._e(),_c('el-form-item',{attrs:{"label":_vm.algorithmCountingEnteringLabel}},[_c('el-input',{staticStyle:{"width":"50%"},attrs:{"value":_vm.algorithmPeopleEnteringDisplay,"readonly":"","aria-label":_vm.algorithmCountingEnteringLabel}})],1),_c('el-form-item',{attrs:{"label":_vm.algorithmCountingExitingLabel}},[_c('el-input',{staticStyle:{"width":"50%"},attrs:{"value":_vm.algorithmPeopleExitingDisplay,"readonly":"","aria-label":_vm.algorithmCountingExitingLabel}})],1),_c('div',{staticStyle:{"color":"#78869a"},attrs:{"role":"status"}},[_vm._v(_vm._s(_vm.algorithmPeopleCountHint))])],1):_vm._e(),(_vm.algorithmTemplateAdministrator)?_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"模型类型"}},[_c('el-cascader',{staticStyle:{"width":"50%"},attrs:{"options":_vm.modelOptions,"props":_vm.modelProps,"clearable":""},model:{value:(_vm.form.model_template_config_id),callback:function ($$v) {_vm.$set(_vm.form, "model_template_config_id", $$v)},expression:"form.model_template_config_id"}})],1):_vm._e(),(_vm.algorithmTemplateAdministrator)?_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"模型小类"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择模型小类","clearable":"","filterable":""},on:{"change":_vm.onAlgorithmTemplateSmallChange},model:{value:(_vm.form.template_small_id),callback:function ($$v) {_vm.$set(_vm.form, "template_small_id", $$v)},expression:"form.template_small_id"}},_vm._l((_vm.modelSmallOption),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.template_small_name,"value":item.id}})}),1)],1):_vm._e(),_c('div',{staticClass:"algorithm-template-parameters",staticStyle:{"width":"90%","height":"auto","margin-left":"32px","padding-bottom":"12px"}},[(_vm.algorithmTemplateAdministrator)?_c('div',{staticStyle:{"display":"flex","flex-wrap":"wrap","gap":"8px","margin":"8px 0"}},[_c('el-button',{attrs:{"type":"success","icon":"el-icon-plus","size":"mini"},on:{"click":_vm.addItem}},[_vm._v("新增参数")]),_c('el-button',{staticStyle:{"margin-left":"0"},attrs:{"icon":"el-icon-refresh","loading":_vm.algorithmTemplateLoading,"disabled":!_vm.form.template_small_id,"size":"mini"},on:{"click":_vm.completeAlgorithmTemplateParameters}},[_vm._v("补齐模板参数")])],1):_vm._e(),(_vm.algorithmTemplateError)?_c('div',{staticStyle:{"color":"#c45656","font-size":"12px","line-height":"20px"},attrs:{"role":"alert"}},[_vm._v(_vm._s(_vm.algorithmTemplateError))]):_vm._e(),_vm._l((_vm.form.template_data),function(item,index){return _c('div',{directives:[{name:"show",rawName:"v-show",value:(!_vm.isAlgorithmPeopleCountParameter(item.key)),expression:"!isAlgorithmPeopleCountParameter(item.key)"}],key:index,staticClass:"form-group"},[_c('span',{staticStyle:{"display":"inline-block","width":"20px"},attrs:{"slot":"label"},slot:"label"},[(item.msg)?_c('el-tooltip',{attrs:{"effect":"dark","content":item.msg,"placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})]):_vm._e()],1),(_vm.algorithmTemplateAdministrator)?_c('el-input',{staticStyle:{"width":"15%","margin-right":"10px","margin-top":"10px"},attrs:{"placeholder":"请输入键名","size":"mini","disabled":!_vm.algorithmTemplateAdministrator},model:{value:(item.key),callback:function ($$v) {_vm.$set(item, "key", $$v)},expression:"item.key"}}):_c('el-input',{staticStyle:{"width":"15%","margin-right":"10px","margin-top":"10px"},attrs:{"placeholder":"请输入键名","size":"mini","disabled":_vm.model_template_config_id_num != 2},model:{value:(item.key),callback:function ($$v) {_vm.$set(item, "key", $$v)},expression:"item.key"}}),(_vm.algorithmTemplateAdministrator)?_c('el-input',{staticStyle:{"width":"39%","margin-right":"10px","margin-top":"10px"},attrs:{"placeholder":"请输入值","size":"mini","disabled":!_vm.algorithmTemplateAdministrator},model:{value:(item.value),callback:function ($$v) {_vm.$set(item, "value", $$v)},expression:"item.value"}}):_c('el-input',{staticStyle:{"width":"39%","margin-right":"10px","margin-top":"10px"},attrs:{"placeholder":"请输入值","size":"mini","disabled":_vm.model_template_config_id_num != 2},model:{value:(item.value),callback:function ($$v) {_vm.$set(item, "value", $$v)},expression:"item.value"}}),(_vm.algorithmTemplateAdministrator)?_c('el-button',{staticStyle:{"margin-right":"10px","margin-top":"10px"},attrs:{"type":"danger","icon":"el-icon-delete","size":"mini"},on:{"click":function($event){return _vm.removeItem(index)}}},[_vm._v("删除")]):_vm._e()],1)})],2)],1):_vm._e(),_c('el-form-item',{directives:[{name:"show",rawName:"v-show",value:(_vm.model_template_config_id_num == 5),expression:"model_template_config_id_num == 5"}],staticStyle:{"margin-top":"16px"},attrs:{"label":"扩增比例参数","prop":"amp"}},[_c('el-input-number',{staticStyle:{"width":"50%","float":"left"},attrs:{"controls-position":"right","min":1,"max":100},model:{value:(_vm.form.amp),callback:function ($$v) {_vm.$set(_vm.form, "amp", $$v)},expression:"form.amp"}})],1),_c('el-form-item',{directives:[{name:"show",rawName:"v-show",value:(_vm.model_template_config_id_num == 5),expression:"model_template_config_id_num == 5"}],staticStyle:{"margin-top":"16px"},attrs:{"label":"图像类型","prop":"alg_select_type"}},[_c('el-radio-group',{model:{value:(_vm.form.alg_select_type),callback:function ($$v) {_vm.$set(_vm.form, "alg_select_type", $$v)},expression:"form.alg_select_type"}},[_c('el-radio',{attrs:{"label":'1'}},[_vm._v("裁剪")]),_c('el-radio',{attrs:{"label":'2'}},[_vm._v("屏蔽")]),_c('el-radio',{attrs:{"label":'3'}},[_vm._v("原图")])],1)],1),(_vm.model_template_config_id_num == 5)?_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"级联解析类型","prop":"model_two_type"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择级联解析类型","size":"mini","clearable":"","filterable":""},model:{value:(_vm.form.model_two_type),callback:function ($$v) {_vm.$set(_vm.form, "model_two_type", $$v)},expression:"form.model_two_type"}},_vm._l((_vm.dict.algorithm_list_five),function(item){return _c('el-option',{key:'级联解析类型'+item.id,attrs:{"label":item.algorithm_name,"value":item.id}})}),1)],1):_vm._e(),_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"报警等级","prop":"res_type"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择报警等级","size":"mini","clearable":"","filterable":""},on:{"change":_vm.markAlgorithmAlarmEdited},model:{value:(_vm.form.res_type),callback:function ($$v) {_vm.$set(_vm.form, "res_type", $$v)},expression:"form.res_type"}},_vm._l((_vm.alarmTypeDictOptions),function(item){return _c('el-option',{key:'报警等级'+item.value,attrs:{"label":item.label,"value":item.value}})}),1)],1),_c('el-form-item',{attrs:{"label":"算力资源","prop":"resource_id"}},[_c('el-cascader',{staticStyle:{"width":"50%"},attrs:{"options":_vm.computeOptions,"props":_vm.computeProps,"show-all-levels":false,"clearable":""},on:{"change":_vm.markAlgorithmResourceEdited},model:{value:(_vm.form.resource_id),callback:function ($$v) {_vm.$set(_vm.form, "resource_id", $$v)},expression:"form.resource_id"}}),_c('div',{staticClass:"algorithm-resource-status",attrs:{"role":"status","aria-live":"polite"}},[_vm._v(_vm._s(_vm.algorithmAdmissionHint))])],1),(_vm.type_qy)?_c('div',{staticClass:"algorithm-drawing-scroll",staticStyle:{"width":"100%","height":"590px","border":"1px dashed #e5e5e5","background":"#f9fafb","border-radius":"10px"}},[_c('div',{staticStyle:{"width":"100%","height":"400px"}},[_c('div',{staticStyle:{"width":"120px","height":"30px","border":"2px solid #5b65eb","text-align":"center","color":"#5b65eb","background":"#ddefff","display":"flex","align-items":"center","justify-content":"center","font-size":"0.8vw","margin":"12px 0 0 12px","float":"left"}},[_vm._v(_vm.algorithmPeopleCountVisible&&!_vm.algorithmCountingBoarding?"检测区域与警戒线":"绘制检测区域")]),_c('div',{staticStyle:{"width":"640px","height":"419px","float":"left","margin":"12px 0 0 12px"}},[_c('div',{directives:[{name:"loading",rawName:"v-loading",value:(_vm.loading),expression:"loading"}],staticClass:"Bcanvas"},[(!_vm.imgOpen)?_c('div',{staticClass:"jia_div"},[_vm._v(_vm._s(_vm.algorithmSnapshotHint))]):_vm._e(),(_vm.imgOpen)?_c('img',{staticStyle:{"width":"640px","height":"360px"},attrs:{"src":_vm.imgurl,"alt":""},on:{"load":function($event){_vm.loading = false}}}):_vm._e(),(_vm.isTypeTFS)?_c('canvas',{ref:"mycanvas",attrs:{"id":"mycanvas","tabindex":"0"}}):_vm._e(),(_vm.shield_status == 1||_vm.image_draw_type == 2)?_c('div',{staticClass:"jia_div"}):_vm._e()]),(_vm.algorithmPeopleCountVisible)?renderAlgorithmDetectionTools.call(_vm):_vm._e(),(_vm.isTypeTFS && !_vm.algorithmPeopleCountVisible)?_c('div',{staticClass:"canvasBtn"},[_c('el-button',{attrs:{"type":"text","icon":"el-icon-refresh"},on:{"click":function($event){return _vm.handleimg(1)}}},[_vm._v("刷新")]),_c('el-button',{attrs:{"type":"text","icon":"el-icon-edit"},on:{"click":_vm.handleDrewAgain}},[_vm._v("重新绘制")]),_c('el-button',{attrs:{"type":"text","icon":"el-icon-refresh-left"},on:{"click":_vm.resole}},[_vm._v("撤销")])],1):_vm._e()])]),_c('div',{staticStyle:{"width":"100%","height":"180px"}},[_c('div',{staticStyle:{"width":"38%","height":"100%","float":"left","margin-left":"15%"}},[_c('el-form-item',{staticStyle:{"padding-top":"16px"},attrs:{"prop":"confidence"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                置信度\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"触发报警阈值，值越小越容易触发报警。取值范围：0–1，步长0.01","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入置信度","type":"number","min":"0","max":"1","step":"0.01","maxlength":"4"},model:{value:(_vm.form.confidence),callback:function ($$v) {_vm.$set(_vm.form, "confidence", _vm._n($$v))},expression:"form.confidence"}})],1),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"prop":"sensitivity"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                间隔帧\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"视频流检测频率，如设置为25，1s检测一次。取值范围：（1-100）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"disabled":_vm.indexnum != 0,"placeholder":"请输入间隔帧","maxlength":"4"},model:{value:(_vm.form.sensitivity),callback:function ($$v) {_vm.$set(_vm.form, "sensitivity", _vm._n($$v))},expression:"form.sensitivity"}})],1):_vm._e()],1),(_vm.isTypeTFS)?_c('div',{staticStyle:{"width":"38%","height":"100%","float":"left"}},[_c('el-form-item',{staticStyle:{"padding-top":"16px"},attrs:{"prop":"duration_time"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                持续时长\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"需求行为的持续时长。取值范围：（1-100）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入持续时长","maxlength":"4"},model:{value:(_vm.form.duration_time),callback:function ($$v) {_vm.$set(_vm.form, "duration_time", _vm._n($$v))},expression:"form.duration_time"}},[_c('template',{slot:"append"},[_vm._v("秒")])],2)],1),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"prop":"interval_time"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                告警间隔\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"当满足触发报警条件达到一定间隔时长以后才会上报。取值范围：（1-3600秒）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入告警间隔","maxlength":"4"},model:{value:(_vm.form.interval_time),callback:function ($$v) {_vm.$set(_vm.form, "interval_time", _vm._n($$v))},expression:"form.interval_time"}},[_c('template',{slot:"append"},[_vm._v("秒")])],2)],1):_vm._e(),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"label":"开始时间","prop":"defense_time_start"}},[_c('el-time-picker',{staticStyle:{"width":"100%"},attrs:{"disabled":_vm.indexnum != 0,"value-format":"HH:mm:ss","picker-options":{selectableRange: '00:00:00 - 23:59:59'},"placeholder":"任意时间点","default-value":new Date().setHours(0, 0, 0, 0)},model:{value:(_vm.form.defense_time_start),callback:function ($$v) {_vm.$set(_vm.form, "defense_time_start", $$v)},expression:"form.defense_time_start"}})],1):_vm._e(),_c('el-form-item',{attrs:{"label":"结束时间","prop":"defense_time_end"}},[_c('el-time-picker',{staticStyle:{"width":"100%"},attrs:{"disabled":_vm.indexnum != 0,"value-format":"HH:mm:ss","picker-options":{selectableRange: '00:00:00 - 23:59:59'},"placeholder":"任意时间点","default-value":new Date().setHours(0, 0, 0, 0)},model:{value:(_vm.form.defense_time_end),callback:function ($$v) {_vm.$set(_vm.form, "defense_time_end", $$v)},expression:"form.defense_time_end"}})],1)],1):_vm._e()])]):_vm._e(),_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"任务说明"}},[_c('el-input',{staticStyle:{"width":"50%","float":"left"},attrs:{"placeholder":"请输入备注","type":"textarea"},model:{value:(_vm.form.Algorithm_config_ps),callback:function ($$v) {_vm.$set(_vm.form, "Algorithm_config_ps", $$v)},expression:"form.Algorithm_config_ps"}})],1)],1)],1),_c('el-dialog',{attrs:{"title":_vm.title2,"id":"alarmTypeBox","visible":_vm.dialogVisible2,"width":"500px","close-on-click-modal":false},on:{"update:visible":function($event){_vm.dialogVisible2=$event},"close":_vm.handleClose2}},[_c('div',{staticClass:"radio-group-title"},[_vm._v("告警区域")]),_c('br'),_c('el-radio-group',{staticClass:"radio-grid",model:{value:(_vm.selectedOption),callback:function ($$v) {_vm.selectedOption=$$v},expression:"selectedOption"}},[_c('el-radio',{staticClass:"grid-item",attrs:{"label":'告警区域'}},[_vm._v("告警区域")])],1),_c('br'),_c('br'),_c('div',{staticClass:"radio-group-title"},[_vm._v("后处理区域")]),_c('br'),_c('el-radio-group',{staticClass:"radio-grid",model:{value:(_vm.selectedOption),callback:function ($$v) {_vm.selectedOption=$$v},expression:"selectedOption"}},[_c('el-radio',{staticClass:"grid-item",attrs:{"label":_vm.selectedOption_type}},[_vm._v(_vm._s(_vm.selectedOption_type))])],1),_c('span',{staticClass:"dialog-footer",attrs:{"slot":"footer"},slot:"footer"},[_c('el-button',{on:{"click":function($event){_vm.dialogVisible2 = false;_vm.handleDeleteList()}}},[_vm._v("取 消")]),_c('el-button',{attrs:{"type":"primary"},on:{"click":function($event){return _vm.handleUpdateList()}}},[_vm._v("确 定")])],1)],1)],1)};
var staticRenderFns=[];
Component.render=render;Component.staticRenderFns=staticRenderFns;Component._compiled=true;Component._scopeId="data-v-969b2714";Component.__file="src/components/sfgl_childsCom.vue";return Component;
})();
e["default"]=(function(){



var Component={
  mixins: [algorithmStreamMixin],
  components: {
    cavdiv
  },
  name: "sfgl_child",
  data() {
    return {
      ddds: 0,
      aaas: true,
      conf_ids:'',
      btnCli: 0,
      listMap: [],
      jxlxlist: [],
      dict: [],
      options1: [],
      options2: [],
      options3: [],
      modelOptions: [],
      props: {
        checkStrictly: false,
        emitPath: false,
        value: "id",
        label: "equipment_name",
      },
      modelProps: {
        checkStrictly: false,
        emitPath: false,
        value: 'model_id', // 动态选择值字段
        label: 'model_type_name', // 动态选择标签字段
        // children: "children" // 如果子级还有下一级，确保正确指向子选项数组
      },
      form: {
        conf_name: '',
        Mine_id: '',
        equipment_name: '',
      },
      rules:{
        conf_name: [
          { required: true, message: '请输入任务名称', trigger: 'blur' },
        ],
        Mine_id: [
          { required: true, message: '请选择单位名称', trigger: 'change' },
        ],
        equipment_name: [
          { required: true, message: '请选择报警设备', trigger: 'change' },
        ],
      }
    };
  },
  computed: {

  },
  created() {

  },
  methods: {
    modelKey(item) {
      if (!this._algorithmModelKeys) { this._algorithmModelKeys = new WeakMap(); this._algorithmModelSequence = 0; }
      if (!this._algorithmModelKeys.has(item)) this._algorithmModelKeys.set(item, 'model-' + (++this._algorithmModelSequence));
      return this._algorithmModelKeys.get(item);
    },
    onAdvancedDeviceChange() {
      this.onAlarmDeviceChange();
      this.addfn(1);
      this.syncModelStreams();
    },
    syncModelStreams() {
      var streamType = this.form.stream_type === 'main' || this.form.stream_type === 'sub' ? this.form.stream_type : null;
      this.jxlxlist.forEach((item) => this.$set(item, 'stream_type', streamType));
    },
    btnClick(index) {
      this.btnCli = index
    },
    addfn(e) {
      if(e == 1){
        this.jxlxlist = []
        this.jxlxlist.push({
          equipment_name: this.form.equipment_name,
          stream_type: this.form.stream_type,
          "Mine_id": "",
          "Equipment_id": "",
          "conf_area": '[]',
          "shield_status": "",
          "tem_conf_area": '[]',
          "draw_type": "1",
          "img_resolution": "",
          "image_draw_type": 1,
          "template_list_area": '[]',
          priority: "",
          run_time: "",
          mine_name: "",
          algorithm_name: "",
          Algorithm_library_id: "",
          type: 0,
          confidence: 0.6,
          tem_frames: "[27,37]",
          duration_time: 10,
          interval_time: 2,
          sensitivity: 2,
          defense_time_start: '00:00:00',
          defense_time_end: '23:59:59',
          image_count: 5,
          template_data: '[]',
          test_type_id: "",
          label_list: '[]',
          amp: 10,
          alg_select_type: '3',
          model_two_data: '[]',
          model_two_type: '',
        })
      }else if (this.jxlxlist.length < 3) {
        this.jxlxlist.push({
          equipment_name: this.form.equipment_name,
          stream_type: this.form.stream_type,
          "Mine_id": "",
          "Equipment_id": "",
          "conf_area": '[]',
          "shield_status": "",
          "tem_conf_area": '[]',
          "draw_type": "1",
          "img_resolution": "",
          "image_draw_type": 1,
          "template_list_area": '[]',
          priority: "",
          run_time: "",
          mine_name: "",
          algorithm_name: "",
          Algorithm_library_id: "",
          type: 0,
          confidence: 0.6,
          tem_frames: "[27,37]",
          duration_time: 10,
          interval_time: 2,
          sensitivity: 2,
          defense_time_start: '00:00:00',
          defense_time_end: '23:59:59',
          image_count: 5,
          template_data: '[]',
          test_type_id: "",
          label_list: '[]',
          amp: 10,
          alg_select_type: '3',
          model_two_data: '[]',
          model_two_type: '',
        })
      }
    },
    deletefn(e) {
      this.btnCli = 0
      this.jxlxlist.splice(e, 1);
    },
    countfns(index) {
      this.btnCli = index
      this.jxlxlist[index].algorithm_name = null;
      this.jxlxlist[index].label_list = [];
      for (var i = 0; i < this.dict.algorithm_list.length; i++) {
        if (this.dict.algorithm_list[i].id == this.jxlxlist[index].Algorithm_library_id) {
          this.jxlxlist[index].Algorithm_library_id = this.dict.algorithm_list[i].id;
          this.jxlxlist[index].algorithm_name = this.dict.algorithm_list[i].algorithm_name;
          const selectedId = this.dict.algorithm_list[i].id;
          const selectedModel = this.jxlxlist[index];
          this.$nextTick(() => {
            if (this._algorithmFormClosed || this.jxlxlist[index] !== selectedModel || selectedModel.Algorithm_library_id !== selectedId) return;
            const refs = this.$refs.canvasRef || [];
            const child = refs.find((item) => Number(item.indexnum) === index);
            if (child && typeof child.clearss === 'function') child.clearss(selectedId);
          });
          // this.ssa(index)
          // this.jxlxlist[index] = {
          //   equipment_name: this.dict.algorithm_list[i].algorithm_name,
          //   "Mine_id": "",
          //   "Equipment_id": "",
          //   "conf_area": '[]',
          //   "shield_status": "",
          //   "tem_conf_area": '[]',
          //   "draw_type": "1",
          //   "img_resolution": "",
          //   "image_draw_type": 1,
          //   "template_list_area": '[]',
          //   priority: "",
          //   run_time: "",
          //   mine_name: "",
          //   algorithm_name: "",
          //   Algorithm_library_id: this.dict.algorithm_list[i].Algorithm_library_id,
          //   type: 0,
          //   confidence: 0.6,
          //   tem_frames: "[27,37]",
          //   duration_time: 10,
          //   interval_time: 2,
          //   sensitivity: 2,
          //   defense_time_start: '00:00:00',
          //   defense_time_end: '23:59:59',
          //   image_count: 5,
          //   template_data: '[]',
          //   test_type_id: "",
          //   label_list: '[]',
          //   amp: 10,
          //   alg_select_type: '3',
          //   model_two_data: '[]',
          //   model_two_type: '',
          // }
        }
      }
    },
    goback() {
      this.$router.push({
        path: '/sfgl',
      })
    },
    sub_fn() { if (!algorithmFirstEditorConfidence.cascadeReady(this)) return false; var _algorithmFirstSavedContext = window.AiMonitorAlgorithmFirstEditor ? window.AiMonitorAlgorithmFirstEditor.beforeSave(this) : null; if (_algorithmFirstSavedContext === false) return false;
      
      this.$refs['form'].validate(async (valid) => {
          if (valid) {
      // console.log(this.$refs.canvasRef);
      // this.$refs.canvasRef.setF()
      const refs = this.$refs.canvasRef || [];
      const children = this.jxlxlist.map((item, index) => refs.find((child) => Number(child.indexnum) === index));
      if (children.filter(child => child && child.algorithmPeopleCountVisible).length > 1) {
        this.$message({ message: '一个任务最多配置一个人数统计算法，请为另一计数版本创建独立任务', type: 'warning' }); return;
      }
      if (!children.length || children.some((child, index) => !child || !this.jxlxlist[index].algorithm_name)) {
        this.$message({ message: '请选择每一项解析类型并等待配置加载完成', type: 'warning' }); return;
      }
      if (this._algorithmSourceEdited && children.some((child) => child.loading || child.algorithmSnapshotReadyKey !== child.streamSourceKey)) {
        this.$message({ message: '请等待所有解析类型的码流图片加载完成后保存', type: 'warning' }); return;
      }
      try {
        const validatedModels = this.jxlxlist.slice();
        const validatedAlgorithmIds = validatedModels.map((item) => String(item.Algorithm_library_id));
        const validationSourceKey = this.streamSourceKey;
        const validModels = await Promise.all(children.map((child) => child.sub_fn()));
        if (validModels.some((result) => result === false) || this._algorithmFormClosed) return;
        if (validationSourceKey !== this.streamSourceKey || validatedModels.length !== this.jxlxlist.length || validatedModels.some((item, index) => item !== this.jxlxlist[index] || String(item.Algorithm_library_id) !== validatedAlgorithmIds[index])) {
          this.$message({ message: '配置内容已变化，请重新点击保存', type: 'warning' }); return;
        }
      } catch (error) {
        this.$message({ message: '配置数据尚未准备好，请刷新后重试', type: 'warning' }); return;
      }
      var objmap = {
        conf_name: this.form.conf_name,
        Mine_id: this.form.Mine_id,
        id: this.$route.query.id,
        equipment_name: this.form.equipment_name,
        stream_type: this.streamTypeRequest(),
        model_data: algorithmFirstEditorConfidence.payload(this.jxlxlist),
      }
      console.log(objmap);
        console.log(this.jxlxlist)
        if(this.$route.query.map){
          this.$http
            .post(this.$url.url_5000 + "/model_view/algorithm_update_models", objmap)
            .then((response) => {
              // console.log(response);
              if (response.data.code === 200) {
                this.$message({
                  message: response.data.msg,
                  type: "success",
                });
                (window.AiMonitorAlgorithmFirstEditor && window.AiMonitorAlgorithmFirstEditor.afterSaved(this, typeof _algorithmFirstSavedContext === "undefined" ? null : _algorithmFirstSavedContext)) || this.goback()
                // this.axioss();
                // this.handleClose();
              } else {
                this.$message({
                  message: response.data.msg,
                  type: "warning",
                });
              }
            })
            .catch(function (response) {
              console.log(response);
            });
        }else{
          this.$http
            .post(this.$url.url_5000 + "/model_view/algorithm_add_models", objmap)
            .then((response) => {
              // console.log(response);
              if (response.data.code === 200) {
                this.$message({
                  message: response.data.msg,
                  type: "success",
                });
                (window.AiMonitorAlgorithmFirstEditor && window.AiMonitorAlgorithmFirstEditor.afterSaved(this, typeof _algorithmFirstSavedContext === "undefined" ? null : _algorithmFirstSavedContext)) || this.goback()
                // this.axioss();
                // this.handleClose();
              } else {
                this.$message({
                  message: response.data.msg,
                  type: "warning",
                });
              }
            })
            .catch(function (response) {
              console.log(response);
            });
        }
        } else {
                this.$message({
                  message: '算法配置数据有未填写项',
                  type: "warning",
                });
          }
        });
    },
    init() {//字典
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: '',
              type: 1
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          if (response.data.code === 200) {
            this.dict = response.data;
            this.options1 = response.data.mine_list;
            // this.form.Mine_id = response.data.mine_list[0].id
            this.options2 = response.data.equipment_list;
            this.options3 = response.data.algorithm_list;
            this.modelOptions = response.data.model_type_template.map(v => {
              return {
                ...v,
                model_id: 'F' + v.id,
                children: v.template_model_data_list.map(child => {
                  return {
                    ...child,
                    model_id: child.id,
                    model_type_name: child.model_name
                  }
                })
              }
            })
            // console.log(9527,this.modelOptions)
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
  },
  mounted() {
    this.init()
    if(this.$route.query.map){
      var obj = JSON.parse(this.$route.query.map)
      this.conf_ids = this.$route.query.id
      this.form = algorithmFirstEditorConfidence.hydrate(obj)
      this.restoreAlgorithmSource();
      this.jxlxlist = obj.model_data
      this.syncModelStreams();
      this.jxlxlist.forEach(item =>{
        if(!Array.isArray(item.label_list)){
          item.label_list = JSON.parse(item.label_list)
        }
      })
    }
  },
  beforeDestroy() {

  },
  destroyed() {

  },
};

var render=function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"sfgl_child algorithm-config-page"},[_c('el-button',{staticStyle:{"margin":"12px"},attrs:{"size":"mini"},on:{"click":_vm.goback}},[_vm._v("返回")]),_c('div',{staticClass:"sfpzs"},[_c('el-form',{ref:"form",attrs:{"model":_vm.form,"rules":_vm.rules,"size":"mini","label-width":"110px"}},[_c('el-form-item',{staticStyle:{"padding-top":"16px"},attrs:{"label":"任务名称","prop":"conf_name"}},[_c('el-input',{staticStyle:{"width":"50%","float":"left"},model:{value:(_vm.form.conf_name),callback:function ($$v) {_vm.$set(_vm.form, "conf_name", $$v)},expression:"form.conf_name"}}),_c('div',{staticClass:"w-1\\2 algorithm-field-hint",staticStyle:{"color":"red"}},[_vm._v("*例:报警设备_解析类型名称")])],1),_c('el-form-item',{attrs:{"label":"单位名称","prop":"Mine_id"}},[_c('el-select',{staticStyle:{"width":"50%","float":"left"},attrs:{"placeholder":"请选择单位名称","size":"small","clearable":"","filterable":""},model:{value:(_vm.form.Mine_id),callback:function ($$v) {_vm.$set(_vm.form, "Mine_id", $$v)},expression:"form.Mine_id"}},_vm._l((_vm.options1),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.mine_name,"value":item.id}})}),1)],1),_c('el-form-item',{attrs:{"label":"报警设备","prop":"equipment_name"}},[_c('el-cascader',{staticStyle:{"width":"50%","float":"left"},attrs:{"options":_vm.dict.equipment_list,"props":_vm.props,"clearable":"","filterable":""},on:{"change":_vm.onAdvancedDeviceChange},model:{value:(_vm.form.equipment_name),callback:function ($$v) {_vm.$set(_vm.form, "equipment_name", $$v)},expression:"form.equipment_name"}})],1),_c('el-form-item',{staticClass:"algorithm-stream-row",attrs:{"label":"视频码流"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"disabled":_vm.streamSelectionDisabled},model:{value:(_vm.streamSelection),callback:function ($$v) {_vm.streamSelection=$$v},expression:"streamSelection"}},_vm._l((_vm.streamOptions),function(option){return _c('el-option',{key:option.value,attrs:{"value":option.value,"label":option.label,"disabled":option.disabled}})}),1),_c('div',{staticClass:"algorithm-stream-help"},[_vm._v(_vm._s(_vm.streamCapabilityHint)+"；所有解析类型使用同一码流")])],1),_vm._l((_vm.jxlxlist),function(item,index){return (_vm.form.equipment_name)?_c('el-form-item',{key:index,staticClass:"algorithm-model-selector",attrs:{"label":"解析类型"}},[_c('el-select',{staticStyle:{"width":"50%","float":"left","margin-right":"12px"},attrs:{"placeholder":"请选择解析类型","filterable":""},on:{"change":function($event){return _vm.countfns(index)}},model:{value:(item.Algorithm_library_id),callback:function ($$v) {_vm.$set(item, "Algorithm_library_id", $$v)},expression:"item.Algorithm_library_id"}},_vm._l((_vm.dict.algorithm_list),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.algorithm_name,"value":item.id}})}),1),_c('div',{staticClass:"w-1\\2 algorithm-model-actions"},[(index == 0)?_c('el-button',{attrs:{"icon":"el-icon-plus","circle":"","size":"mini"},on:{"click":_vm.addfn}}):_vm._e(),(_vm.jxlxlist.length > 1)?_c('el-button',{attrs:{"icon":"el-icon-minus","circle":"","size":"mini"},on:{"click":function($event){return _vm.deletefn(index)}}}):_vm._e()],1)],1):_vm._e()}),_c('el-divider'),(_vm.jxlxlist.length > 0 && _vm.jxlxlist[0].algorithm_name)?_c('div',{staticClass:"btnlist"},_vm._l((_vm.jxlxlist),function(item,index){return _c('div',{directives:[{name:"show",rawName:"v-show",value:(item.algorithm_name),expression:"item.algorithm_name"}],key:index+'i',class:[{ is_active: _vm.btnCli+'i' == index+'i' }],on:{"click":function($event){return _vm.btnClick(index)}}},[_vm._v(_vm._s(item.algorithm_name))])}),0):_vm._e(),(_vm.aaas)?_c('div',_vm._l((_vm.jxlxlist),function(item,index){return _c('div',{directives:[{name:"show",rawName:"v-show",value:(index == _vm.btnCli),expression:"index == btnCli"}],key:_vm.modelKey(item),staticClass:"algorithm-model-panel"},[(_vm.jxlxlist[index].algorithm_name)?_c('cavdiv',{ref:"canvasRef",refInFor:true,attrs:{"item":item,"config-stream-type":_vm.form.stream_type,"conf_id":_vm.conf_ids,"indexnum":index,"types":_vm.ddds},on:{"update:item":function($event){item[index] = $event}}}):_vm._e()],1)}),0):_vm._e(),_c('el-form-item',{staticClass:"algorithm-form-actions"},[_c('div',{staticClass:"algorithm-action-buttons",staticStyle:{"text-align":"-end","margin-bottom":"24px"}},[_c('el-button',{attrs:{"type":"primary"},on:{"click":_vm.sub_fn}},[_vm._v("保存")]),_c('el-button',{on:{"click":_vm.goback}},[_vm._v("取消")])],1)])],2)],1)],1)};
var staticRenderFns=[];
Component.render=render;Component.staticRenderFns=staticRenderFns;Component._compiled=true;Component._scopeId="data-v-a5801dae";Component.__file="src/components/sfgl_childs.vue";return Component;
})();
},d58f:function(t,e,i){"use strict";var s=i("59ed"),a=i("7b0b"),l=i("44ad"),o=i("07fa"),r=TypeError,n=function(t){return function(e,i,n,m){var d=a(e),_=l(d),h=o(d);s(i);var c=t?h-1:0,p=t?-1:1;if(n<2)while(1){if(c in _){m=_[c],c+=p;break}if(c+=p,t?c<0:h<=c)throw new r("Reduce of empty array with no initial value")}for(;t?c>=0:h>c;c+=p)c in _&&(m=i(m,_[c],c,d));return m}};t.exports={left:n(!1),right:n(!0)}}}]);





//# sourceMappingURL=chunk-415cc626.cc1cbfe2.js.map
