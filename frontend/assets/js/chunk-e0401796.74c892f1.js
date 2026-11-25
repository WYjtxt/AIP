(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["chunk-e0401796"],{"13d5":function(t,e,i){"use strict";var a=i("23e7"),l=i("d58f").left,s=i("a640"),o=i("2d00"),r=i("605d"),n=!r&&o>79&&o<83,m=n||!s("reduce");a({target:"Array",proto:!0,forced:m},{reduce:function(t){var e=arguments.length;return l(this,t,e,e>1?arguments[1]:void 0)}})},"271a":function(t,e,i){"use strict";var a=i("cb2d"),l=i("e330"),s=i("577e"),o=i("d6d6"),r=URLSearchParams,n=r.prototype,m=l(n.getAll),d=l(n.has),h=new r("a=1");!h.has("a",2)&&h.has("a",void 0)||a(n,"has",(function(t){var e=arguments.length,i=e<2?void 0:arguments[1];if(e&&void 0===i)return d(this,t);var a=m(this,t);o(e,1);var l=s(i),r=0;while(r<a.length)if(a[r++]===l)return!0;return!1}),{enumerable:!0,unsafe:!0})},"3ce8":function(t,e,i){
"use strict";i.r(e);
i("d9e2");i("14d9");i("88a7");i("271a");i("5494");i("13d5");i("4360");i("896f");i("de4a");i("dc58");i("c329");i("8f15");i("ed5a");i("4ad5");i("2877");
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
      if (!this.algorithmIsEditing() || Object.prototype.hasOwnProperty.call(this, 'configStreamType') || this._algorithmOperationalEdited || !this.form.id) return false;
      if (this._algorithmMetadataSaving) return true;
      this._algorithmMetadataSaving = true;
      this.$http.post(this.$url.url_5000 + '/resource_view/algorithm_metadata', {
        id: this.form.id, conf_name: this.form.conf_name, Algorithm_config_ps: this.form.Algorithm_config_ps
      }).then(response => {
        if (response.data.code === 200) { this.$message.success(response.data.msg); this.goback(); }
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

e["default"]=(function(){













var Component={
  mixins: [algorithmStreamMixin, algorithmTemplateParameters, algorithmPeopleCounts, algorithmCountingScene],
  components: {
    
  },
  name: "sfgl_child",
  data() {
    return {
      lineDirection: 'right',
      equipment_alogrithm_info_list: null,
      inOnArrow1: true,
      clickSide: null,
      isShow: false,
      show_cxsc: false,
      isTypeTFS: true,
      selectedOption_type: '',
      dict: {
        equipment_list: [],
      },
      type_jx: false,
      type_qy: false,
      StartTime: "",
      EndTime: "",
      nameif:'',
      form: {
        all_Entering_num: 0,
        all_Exiting_num: 0,
        resource_id: 0,
        conf_name: '',
        "Mine_id": "",
        "Equipment_id": "",
        "conf_area": [],
        "shield_status": "",
        "tem_conf_area": [],
        "draw_type": "1",
        "img_resolution": "",
        "image_draw_type": 1,
        uwb_distance: "10",
        "template_list_area": [],
        priority: "",
        run_time: "",
        mine_name: "",
        algorithm_name: "",
        equipment_name: "",
        Algorithm_library_id: "",
        type: 0,
        confidence: "60",
        tem_frames: "[27,37]",
        duration_time: 10,
        interval_time: 2,
        sensitivity: 2,
        defense_time_start: '00:00:00',
        defense_time_end: '23:59:59',
        image_count: 5,
        template_data: [],
        test_type_id: "",
        label_list: [],
        amp: 10,
        alg_select_type: '3',
        model_two_data: [],
        model_two_type: '',
      },
      model_two_type: '',
      label_list: [],
      confidence: '60',
      model_path: '',
      selectedOption_model: '类型一',
      title2_model: '',
      dialogVisible2_model: false,
      title2: "",
      selectedOption: '报警',
      dialogVisible2: false,
      type_list: [],
      alarmTypeDictOptions: [
        {
          label: '一级报警',
          value: '1',
        },
        {
          label: '二级报警',
          value: '2',
        },
        {
          label: '三级报警',
          value: '3',
        },
        {
          label: '四级报警',
          value: '4',
        },
        {
          label: '五级报警',
          value: '5',
        },
        {
          label: '六级报警',
          value: '6',
        },
        {
          label: '七级报警',
          value: '7',
        },
        {
          label: '八级报警',
          value: '8',
        },
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
        value: 'model_id',
        label: 'model_type_name',
      },
      modelOptions: [],
      modelSmallOption: [],
      computeOptions: [],
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
      options8: [],
      options7: [],
      resolution: '',
      resolutionOption: [
        { value: '1920x1080', name: '普通' },
        { value: '2688x1520', name: '热成像' },
        { value: '2560x1440', name: '热成像' },
        { value: '1280x720', name: '热成像' },
        { value: '720x576', name: '热成像2' }
      ],

      imgurl: "",
      isdraw: false,
      coordinates: [],
      cor_index: 0,
      endtip: false,
      mark_list: [],
      mark_lists: [],
      PointInArea: false,
      index: null,
      loading: false,
      area2: false,
      isdraw2: false,
      coordinates2: [],
      cor_index2: 0,
      endtip2: false,
      mark_list2: [],
      mark_lists2: [],
      PointInArea2: false,
      index2: null,
      loading2: false,
      area3: false,
      isdraw3: false,
      coordinates3: [],
      cor_index3: 0,
      endtip3: false,
      mark_list3: [],
      PointInArea3: false,
      index3: null,
      loading3: false,
      imgOpen: false,
      title: "",
      title3: "",
      shield_status: 2,
      image_draw_type: 1,
      drawLineOpen: false,
      selectedOption_type_s: '',
      pickerOptions: {
        disabledDate(time) {
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          return time.getTime() > today.getTime();
        },
      },
      coordinates: [],
      coordinates2: [],
      coordinates3: [],
      checkStatusTime: null,
      flvPlayer: null,
      coordinates_model: [],
      mark_list_model: [],
      mark_lists_model: [],
      selectedOption_model: '类型一',
      title2_model: '',
      dialogVisible2_model: false,
      modelTypeOptions: [],
      template_type_id: '',
      stepActive: 0,
      modelSmallOption: [],
      modelNameOpen: false,
      modelNamemsg: '',
      model_template_config_id_num: 1,
      analysisSrc: '',
      analysisId: '',
      rules: {
        amp: [
          { required: true, message: '扩增比例参数(0-100)', trigger: 'blur' },
        ],
        model_two_type: [
          { required: true, message: '请选择级联解析类型', trigger: 'change' },
        ],
        uwb_distance: [
          { required: true, message: '请输入识别距离', trigger: 'blur' },
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
              if (value < 1 || value > 100) {
                callback(new Error('数字必须在1到100之间'));
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
              if (value < 1 || value > 1800) {
                callback(new Error('数字必须在1到1800之间'));
              } else {
                callback();
              }
            },
            trigger: 'blur'
          }
        ],
        interval_time: [
          { required: true, message: '请输入告警间隔', trigger: 'blur' }, {
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
  computed: {
    
  },
  created() {
    if(localStorage.getItem('user_role_id')){
      this.usertype = localStorage.getItem('user_role_id')
    }
    this.getCompute();
  },
  methods: {
    switchDrawMode(isLine) {
      this.drawLineOpen = isLine
      if (isLine) {
        this.initCanvas4()
      } else {
        this.initCanvas()
      }
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
    sub_fn() {
      if (!this.validateAlgorithmTemplateParameters()) return false;
      if (this.trySaveAlgorithmMetadata()) return;
      if (!this.validateAlgorithmCountingGeometry()) return false;
      if (!this.canSaveAlgorithmSource()) return false;
      const validationSourceKey = this.streamSourceKey;
      this.$refs['form'].validate((valid) => {
          if (this._algorithmFormClosed || validationSourceKey !== this.streamSourceKey || !this.canSaveAlgorithmSource()) return;
          if (valid) {
            const timestamp1 = this.timeToTimestamp(this.form.defense_time_start);
          const timestamp2 = this.timeToTimestamp(this.form.defense_time_end);
          if (timestamp1 > timestamp2) {
            this.$message({
              message: '结束时间不能小于开始时间，请重新选择结束时间!',
              type: "warning",
            });
            this.form.defense_time_end = '23:59:59';
            return;
          }
          if (this.shield_status == "1") {
            let parts = this.resolution.split("x");
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
            this.handleData_model()
            if (this.model_template_config_id_num == 4) {
              this.form.test_type_id = this.options4[0].id
              this.form.label_list = [this.options4[0].test_type_ename]
            }
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
            this.options7.forEach((item)=>{
              all_type_list.push(item.test_type_ename)
            })
            let strs = '';
            if(this.dict.algorithm_list_five.length != 0){
              var list_paths = this.dict.algorithm_list_five
              list_paths.forEach(item => {
                if(item.id == this.form.model_two_type){
                  strs = item.algorithm_path
                }
              })
            }
            // 逆向寻找设备ID
            const resource = this.resolveAlgorithmResource(this.form.resource_id);
            if (!resource) { this.$message({ type: 'warning', message: '请选择有效的计算资源卡' }); return; }
            const computing_id = resource.computingId;
            this.$set(this.form, 'resource_id', resource.resourceId);
          let obj = this.algorithmPeopleCountVisible ? this.algorithmCountingPayload() : {
            ...this.form.cross_line,
            in_point: this.form.in_point,
            out_point: this.form.out_point,
          }
            let forms = {
                uwb_distance: this.form.uwb_distance,
              conf_name: this.form.conf_name,
              Algorithm_library_id: this.form.Algorithm_library_id,
              Mine_id: this.form.Mine_id,
              Equipment_id: this.form.equipment_name,
              stream_type: this.streamTypeRequest(),
            conf_area: JSON.stringify(this.mark_lists),
            cross_line_area: JSON.stringify(obj),
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.form.label_list),
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
            let forms2 = {
                uwb_distance: this.form.uwb_distance,
              id: this.form.id,
              conf_name: this.form.conf_name,
              Algorithm_library_id: this.form.Algorithm_library_id,
              Mine_id: this.form.Mine_id,
              Equipment_id: this.form.equipment_name,
              stream_type: this.streamTypeRequest(),
            conf_area: JSON.stringify(this.mark_lists),
            cross_line_area: JSON.stringify(obj),
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.form.label_list),
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
            if(this.$route.query.conf_id){
              const params = new URLSearchParams();
              for (const key in forms2) {
                params.append(key, forms2[key]);
              }
              this.$http
                .post(this.$url.url_5000 + "/model_view/algorithm_update", params, {
                  headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                  },
                })
                .then((response) => {
                  if (response.data.code === 200) {
                    this.$message({
                      message: response.data.msg,
                      type: "success",
                    });
                    this.goback()
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
                .post(this.$url.url_5000 + "/model_view/algorithm_add", forms)
                .then((response) => {
                  if (response.data.code === 200) {
                    this.$message({
                      message: response.data.msg,
                      type: "success",
                    });
                    this.goback()
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
            return false;
          }
        });
    },
    getModelSmallDetail() {
      return this.algorithmTemplatePayload();
    },
    handleData() {
  // 框数据处理
  if (this.mark_list.length > 0) {
    let arr = []
    for (let i = 0; i < this.mark_list.length; i++) {
      arr.push(
        this.mark_list[i].map(v => ({
          x: Number((Math.min(Math.max(v.x, 0), 640) * this.timesX).toFixed(0)),
          y: Number((Math.min(Math.max(v.y, 0), 360) * this.timesY).toFixed(0)),
          type: v.type,
          color: v.color,
        }))
      )
    }
    this.mark_lists = arr
  } else {
    this.mark_lists = [];
  }

  // 线数据处理 - 只保存线的端点和方向
  if (this.mark_list3.length > 0 && this.mark_list3[0].length >= 2) {
    const line = this.mark_list3[0];
    const p1x = Math.min(Math.max(line[0].x, 0), 640);
    const p1y = Math.min(Math.max(line[0].y, 0), 360);
    const p2x = Math.min(Math.max(line[1].x, 0), 640);
    const p2y = Math.min(Math.max(line[1].y, 0), 360);
    
    const crossLineObj = {
      p1: {
        x: Number((p1x * this.timesX).toFixed(0)),
        y: Number((p1y * this.timesY).toFixed(0))
      },
      p2: {
        x: Number((p2x * this.timesX).toFixed(0)),
        y: Number((p2y * this.timesY).toFixed(0))
      },
      // 【关键修改】只保存方向，不保存具体坐标
      direction: this.lineDirection // 'left' 或 'right'
    };
    
    this.form.cross_line = crossLineObj;
    console.log('保存时的数据:', crossLineObj);
  } else {
    this.form.cross_line = {};
  }

  this.form.draw_type = this.drawLineOpen ? '2' : '1';
},
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
    countfns(e){
      if(this.form.equipment_name != '' && this.form.equipment_name != null && this.form.equipment_name != undefined){
        if(this.form.Algorithm_library_id != '' && this.form.Algorithm_library_id != null && this.form.Algorithm_library_id != undefined){
          this.options8 = []
          let list_b = this.dict.algorithm_list_five
          if(!e){
            this.form.label_list = []
            this.form.model_two_type = '';
            this.label_list = [];
          }
          this.dict.algorithm_list.forEach((item)=>{
            if(item.id == this.form.Algorithm_library_id){
              console.log(item.algorithm_name)
              list_b.forEach((items)=>{
                if(item.algorithm_name == items.algorithm_name){
                  this.options8.push(items)
                }
              })
              if(item.algorithm_name == '探放水'){
                this.isTypeTFS = false;
              }else{
                this.isTypeTFS = true;
              }
            }
          })
          this.handleChangeCanvas2();
          this.updateConfName();
          this.handleChangeSf(this.form.Algorithm_library_id, !e);
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
      this.coordinates3 = [];
      this.mark_list.pop()
    },
    handleUpdateList() {
      let color = {
        'I级报警': '#FF0000',
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
      this.dialogVisible2 = false
    },
    removeItem(index) {
      this.removeAlgorithmTemplateParameter(index);
    },
    addItem() {
      this.addAlgorithmTemplateParameter();
    },
    handleChangeSf(id, userSelected = false) {
      const generation = ++this._algorithmModelGeneration;
      const form = this.form;
      const modelBefore = form.model_template_config_id, smallBefore = form.template_small_id;
      if (userSelected) { this._algorithmModelWasSelected = true; this._algorithmScrollPending = true; this._algorithmDetectionEdited = false; this._algorithmSelectedModelId = String(id); }
      const current = () => !this._algorithmFormClosed && generation === this._algorithmModelGeneration && form === this.form && String(id) === String(this.form.Algorithm_library_id);
      return this.$http
        .get(this.$url.url_5000 + "/model_view/Algorithm_type_select", {
          params: {
            id,
          },
        })
        .then(async (response) => {
          if (!current()) return;
          const data = response.data.data || {};
          const model = (data.model_data || [])[0];
          const type = (data.model_type_data || [])[0];
          const small = (data.template_small_data || [])[0];
          this.nameif = model ? model.model_name : '';
          this.options4 = data.algorithm_data || [];
          this.options7 = data.algorithm_child_data || [];
          this.selectedOption = data.show_status;
          this.selectedOption_type_s = data.show_status;
          const selectedByUser = userSelected || this._algorithmSelectedModelId === String(id);
          const useDefaults = selectedByUser || !this.algorithmIsEditing();
          if (useDefaults && model && this.form.model_template_config_id === modelBefore) this.$set(this.form, 'model_template_config_id', model.id);
          const typeId = type ? type.id : null;
          const smallOptions = type ? this.getModelSmallDict2(type.id, current) : Promise.resolve();
          if(typeId == 1 || typeId == 2){
            this.show_cxsc = true
          }else{
            this.show_cxsc = false
            if (useDefaults) this.form.duration_time = 1;
          }
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
      }).catch(rek => {
        console.log(rek)
      })
    },
    handleChangeShield_status() {
      this.handleDrewAgain();
    },
    equipment_alogrithm_info(){
      this.$http
        .get(this.$url.url_5000 + "/ai_camera_view/equipment_alogrithm_info", {
          params: { equipment_id: this.form.equipment_name },
        })
        .then((response) => {
          this.equipment_alogrithm_info_list = response.data.data;
        });
    },
    async handleChangeCanvas2(data) {
      var info = await this.loadStreamCapabilities(data || this.algorithmEquipmentId());
      if (!info || this._algorithmFormClosed) return false;
      this.area2 = String(info.data && info.data.equipment_code) === '201';
      return this.handleimg();
    },
    handleTimesData(resolution) {
      var parts = String(resolution || '').split('x');
      var width = Number(parts[0]), height = Number(parts[1]);
      if (parts.length !== 2 || !Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return false;
      this.timesX = width / 640;
      this.timesY = height / 360;
      return true;
    },
    
    handleimg(num) { return this.requestAlgorithmImage(num); },
    
    initCanvas() {
      if (this.algorithmPeopleCountVisible) return this.initAlgorithmCountingCanvas();
      this.$nextTick(() => {
        let cav = this.$refs.mycanvas;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        let list = this.mark_list;
        let coordinates = this.coordinates
        let this_ = this
        draw_test(cav, list, this.handleChooseType, coordinates);
      });
    },
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
    handleChooseType_model() {
      this.selectedOption_model = '类型一'
      this.title2_model = '模型类型选择'
      this.dialogVisible2_model = true
    },
    initCanvas_model() {
    },
    initCanvas2() {
      this.$nextTick(() => {
        let cav = this.$refs.mycanvas2;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        let list = this.mark_list2;
        let coordinates = this.coordinates2
        draw_test3(cav, list, coordinates);
      });
    },
    // 统一的计算箭头位置函数
// 统一的计算箭头位置函数（输入和输出都是画布坐标 640x360）
// 统一的计算箭头位置函数（输入和输出都是画布坐标 640x360）
getArrowPositions(p1, p2) {
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len === 0) return null;
  
  const ux = dx / len;
  const uy = dy / len;
  const perpLen = 40;
  const mx = (p1.x + p2.x) / 2;
  const my = (p1.y + p2.y) / 2;
  
  // 计算两个箭头端点（确保是数字类型）
  const arrow1X = mx + uy * perpLen;
  const arrow1Y = my - ux * perpLen;
  const arrow2X = mx - uy * perpLen;
  const arrow2Y = my + ux * perpLen;
  
  const arrow1 = {
    x: Number(arrow1X.toFixed(2)),
    y: Number(arrow1Y.toFixed(2))
  };
  const arrow2 = {
    x: Number(arrow2X.toFixed(2)),
    y: Number(arrow2Y.toFixed(2))
  };
  
  console.log('getArrowPositions 计算结果:', { arrow1, arrow2, mx, my, ux, uy });
  
  return { arrow1, arrow2 };
},
    initCanvas4() {
      if (this.algorithmPeopleCountVisible) return this.initAlgorithmCountingCanvas();
  this.$nextTick(() => {
    const cav = this.$refs.mycanvas;
    if (!cav) return;
    
    cav.width = 640;
    cav.height = 360;
    cav.style.cursor = "crosshair";
    
    if (!this.imgOpen) {
      console.log('图片未加载完成，等待...');
      return;
    }
    
    let isDrawing = false;
    let tempStart = null;
    
    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
    const clampX = (x) => clamp(Math.round(x), 0, 640);
    const clampY = (y) => clamp(Math.round(y), 0, 360);
    
    const drawAllBoxes = (ctx) => {
      this.mark_list.forEach(polygon => {
        if (polygon.length < 3) return;
        ctx.beginPath();
        ctx.strokeStyle = polygon[0].color || '#f00';
        ctx.lineWidth = 2;
        ctx.moveTo(clampX(polygon[0].x), clampY(polygon[0].y));
        polygon.forEach(point => ctx.lineTo(clampX(point.x), clampY(point.y)));
        ctx.closePath();
        ctx.stroke();
      });
    };
    
    const renderAll = () => {
      const ctx = cav.getContext("2d");
      ctx.clearRect(0, 0, cav.width, cav.height);
      drawAllBoxes(ctx);
      
      if (this.mark_list3.length > 0 && this.mark_list3[0].length >= 2) {
        const line = this.mark_list3[0];
        let p1 = { x: clampX(line[0].x), y: clampY(line[0].y) };
        let p2 = { x: clampX(line[1].x), y: clampY(line[1].y) };
        
        this.mark_list3[0] = [p1, p2];
        
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#ffd700";
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
        
        // 计算箭头位置
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len === 0) return;
        
        const ux = dx / len;
        const uy = dy / len;
        const perpLen = 40;
        const mx = (p1.x + p2.x) / 2;
        const my = (p1.y + p2.y) / 2;
        
        // 计算两个箭头端点（右侧箭头和左侧箭头）
        let rightArrowX = mx + uy * perpLen;
        let rightArrowY = my - ux * perpLen;
        let leftArrowX = mx - uy * perpLen;
        let leftArrowY = my + ux * perpLen;
        
        // 四舍五入并限制范围
        rightArrowX = clamp(Math.round(rightArrowX), 15, 625);
        rightArrowY = clamp(Math.round(rightArrowY), 15, 345);
        leftArrowX = clamp(Math.round(leftArrowX), 15, 625);
        leftArrowY = clamp(Math.round(leftArrowY), 15, 345);
        
        const drawArrow = (fromX, fromY, toX, toY, color, text) => {
          ctx.strokeStyle = color;
          ctx.fillStyle = color;
          ctx.lineWidth = 2;
          const headLen = 6;
          const angle = Math.atan2(toY - fromY, toX - fromX);
          
          ctx.beginPath();
          ctx.moveTo(fromX, fromY);
          ctx.lineTo(toX, toY);
          ctx.stroke();
          
          ctx.beginPath();
          const arrowX1 = toX - headLen * Math.cos(angle - Math.PI / 6);
          const arrowY1 = toY - headLen * Math.sin(angle - Math.PI / 6);
          const arrowX2 = toX - headLen * Math.cos(angle + Math.PI / 6);
          const arrowY2 = toY - headLen * Math.sin(angle + Math.PI / 6);
          ctx.moveTo(toX, toY);
          ctx.lineTo(arrowX1, arrowY1);
          ctx.lineTo(arrowX2, arrowY2);
          ctx.fill();
          
          ctx.font = "bold 14px Arial";
          ctx.textAlign = "center";
          let textY = toY - 8;
          textY = clamp(textY, 12, 352);
          ctx.fillStyle = color;
          ctx.fillText(text, toX, textY);
        };
        
        const mxDraw = (p1.x + p2.x) / 2;
        const myDraw = (p1.y + p2.y) / 2;
        
        // 【关键修改】根据 lineDirection 决定哪个箭头显示 IN
        if (this.lineDirection === 'left') {
          // IN 在左侧箭头，OUT 在右侧箭头
          drawArrow(mxDraw, myDraw, leftArrowX, leftArrowY, '#44ff44', 'IN');
          drawArrow(mxDraw, myDraw, rightArrowX, rightArrowY, '#ff4444', 'OUT');
        } else {
          // IN 在右侧箭头，OUT 在左侧箭头（默认）
          drawArrow(mxDraw, myDraw, rightArrowX, rightArrowY, '#44ff44', 'IN');
          drawArrow(mxDraw, myDraw, leftArrowX, leftArrowY, '#ff4444', 'OUT');
        }
        
        console.log('渲染: lineDirection=', this.lineDirection);
      }
    };
    
    renderAll();
    
    // 鼠标按下开始绘制
    cav.onmousedown = (e) => {
      if (this.mark_list3.length >= 1) return;
      const rect = cav.getBoundingClientRect();
      const scaleX = cav.width / rect.width;
      const scaleY = cav.height / rect.height;
      let x = (e.clientX - rect.left) * scaleX;
      let y = (e.clientY - rect.top) * scaleY;
      x = clampX(x);
      y = clampY(y);
      if (!isDrawing) {
        isDrawing = true;
        tempStart = { x: x, y: y };
      } else {
        isDrawing = false;
        const endX = clampX(x);
        const endY = clampY(y);
        if (tempStart.x !== endX || tempStart.y !== endY) {
          this.mark_list3 = [[tempStart, { x: endX, y: endY }]];
          // 新绘制的线，默认 IN 在右侧
          this.lineDirection = 'right';
          renderAll();
        }
        tempStart = null;
        if (this.mark_list3.length > 0) {
          this.$message.success("警戒线绘制完成，点击线条左右切换进出方向");
        }
      }
    };
    
    // 鼠标移动绘制中
    cav.onmousemove = (e) => {
      if (!isDrawing || !tempStart) return;
      const rect = cav.getBoundingClientRect();
      const scaleX = cav.width / rect.width;
      const scaleY = cav.height / rect.height;
      let x = (e.clientX - rect.left) * scaleX;
      let y = (e.clientY - rect.top) * scaleY;
      x = clampX(x);
      y = clampY(y);
      const ctx = cav.getContext("2d");
      ctx.clearRect(0, 0, 640, 360);
      drawAllBoxes(ctx);
      ctx.strokeStyle = "#ffd700";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(tempStart.x, tempStart.y);
      ctx.lineTo(x, y);
      ctx.stroke();
    };
    
    // 点击线条切换方向
    cav.onclick = (e) => {
      if (this.mark_list3.length === 0) return;
      // 切换方向
      this.lineDirection = this.lineDirection === 'left' ? 'right' : 'left';
      console.log('切换方向: lineDirection=', this.lineDirection);
      renderAll();
    };
    
    // 双击结束绘制
    cav.ondblclick = () => {
      isDrawing = false;
      tempStart = null;
      renderAll();
    };
  });
},
    tableCanvas(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10);
      var HH = parseInt(parts[1], 10);
      this.$nextTick(() => {
        let cav = this.$refs[`tableCanvas_${id}`];
        cav.width = "96";
        cav.height = "54";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        let XX = parseInt(WW / 96, 10)
        let YY = parseInt(HH / 54, 10)
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
        draw_test2(cav, [...arr_w]);
      });
    },
    tableCanvasMax(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10);
      var HH = parseInt(parts[1], 10);
      this.$nextTick(() => {
        let cav = this.$refs[`tableCanvas_tableMax`];
        cav.width = "800";
        cav.height = "400";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        let XX = WW / 800
        let YY = HH / 400
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
        draw_test2(cav, [...arr_w]);
      });
    },
    handleChangeLabelList() {
      this.markAlgorithmDetectionEdited();
      if (this.form.label_list.length != 0) {
        const selected = this.options4.find(v => v.test_type_ename == this.form.label_list[0]);
        this.form.test_type_id = selected ? selected.id : '';
      } else {
        this.form.test_type_id = '';
      }
    },
    updateConfName() {
      const { equipment_name, Algorithm_library_id } = this.form;
      let algorithmName = '';
      let monitorPointName = '';
      if (Algorithm_library_id) {
        const selectedAlgorithm = this.options3.find(option => option.id === Algorithm_library_id);
        algorithmName = selectedAlgorithm ? selectedAlgorithm.algorithm_name : '';
      }
      if (equipment_name) {
        for (let item of this.options2) {
          if (Array.isArray(item.children)) {
            const foundChild = item.children.find(child => child.id === equipment_name);
            if (foundChild) {
              monitorPointName = foundChild.equipment_name;
            }
          }
        }
      }
    },
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
      return Math.random().toString(36).substr(2, 9);
    },
    transformData(rawData) {
      return this.sortAlgorithmResources(rawData);
    },
    handleDrewAgain() {
      if (this.algorithmPeopleCountVisible) return this.startAlgorithmCountingDrawing();
      this.mark_list = [];
      this.coordinates = [];
      this.mark_list3 = [];
      this.coordinates3 = [];
      this.clickSide = null;
      this.form.cross_line = {};
      this.form.in_point = {};
      this.form.out_point = {};
      this.drawLineOpen = false;
      this.initCanvas();
      this.$message.success("已清空所有绘制内容");
    },
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
    resole() {
      if (this.algorithmPeopleCountVisible) return this.undoAlgorithmCountingPoint();
      if (!this.drawLineOpen) {
        this.coordinates.pop()
        this.initCanvas()
      } else {
        this.mark_list3 = []
        this.initCanvas4()
      }
    },
    resole_model() {
      this.coordinates_model.pop()
    },
    resole2() {
      this.coordinates2.pop()
    },
    init(){
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: '',
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
            this.options2 = response.data.equipment_list;
            this.options3 = response.data.algorithm_list;
            this.type_list = response.data.type_list
            
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
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    
    handlechange(data) {
  this.stepActive = 0
  this.coordinates = [];
  this.coordinates_model = [];
  this.coordinates2 = [];
  this.coordinates3 = [];
  this.$http
    .get(this.$url.url_5000 + "/model_view/algorithm_data_show", {
      params: {
        conf_id: data,
      },
    })
    .then((response) => {
      if (this._algorithmFormClosed || this._algorithmModelWasSelected) return;
      if (response.data.code === 200) {
        this.title = "算法修改";
        this.form = response.data.datalist;
            this.restoreAlgorithmCountingGeometry(this.form.cross_line_area);
        this.restoreAlgorithmSource();
        this.form.equipment_name = this.form.Equipment_id
        // this.equipment_alogrithm_info()
        this.form.model_two_type = response.data.datalist.model_two_type * 1

        if (this.form.img_resolution) {
          this.resolution = this.form.img_resolution;
          this.handleTimesData(this.resolution);
        }
        
        if (this.form.model_two_data && this.form.model_two_data.length) {
          this.label_list = this.form.model_two_data[0].label_list;
          this.confidence = this.form.model_two_data[0].confidence;
          this.model_path = this.form.model_two_data[0].model_path;
        }
        
        // 框数据回显
        if (response.data.datalist.conf_area && response.data.datalist.conf_area != '[]') {
          let arr = JSON.parse(response.data.datalist.conf_area.replace(/'/g, '"'));
          let jia = [], jia_w = [];
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
            jia_w.push(jia);
            jia = [];
          }
          this.mark_list = [...jia_w];
        } else {
          this.mark_list = [];
        }
        
        // 线数据回显
this.mark_list3 = [];
this.form.cross_line = {};
this.lineDirection = 'right'; // 默认值

if (response.data.datalist.cross_line_area && 
    response.data.datalist.cross_line_area !== '' && 
    response.data.datalist.cross_line_area !== '{}') {
  
  try {
    let crossData = typeof response.data.datalist.cross_line_area === 'string' 
      ? JSON.parse(response.data.datalist.cross_line_area.replace(/'/g, '"')) 
      : response.data.datalist.cross_line_area;
    
    console.log('原始线数据:', crossData);
    
    if (crossData.p1 && crossData.p2) {
      // 线的端点：除以倍率，转换回画布坐标
      let p1 = {
        x: parseFloat(crossData.p1.x) / this.timesX,
        y: parseFloat(crossData.p1.y) / this.timesY
      };
      let p2 = {
        x: parseFloat(crossData.p2.x) / this.timesX,
        y: parseFloat(crossData.p2.y) / this.timesY
      };
      
      p1.x = Math.min(640, Math.max(0, p1.x));
      p1.y = Math.min(360, Math.max(0, p1.y));
      p2.x = Math.min(640, Math.max(0, p2.x));
      p2.y = Math.min(360, Math.max(0, p2.y));
      
      this.mark_list3 = [[p1, p2]];
      this.form.cross_line = { p1, p2 };
      
      // 【关键修改】读取保存的方向
      if (crossData.direction) {
        this.lineDirection = crossData.direction;
      } else if (crossData.in_point && crossData.out_point) {
        // 兼容旧数据：如果有 in_point/out_point，根据位置判断方向
        // 这里可以添加兼容逻辑，但最终还是要转换为 direction
        this.lineDirection = this.calcDirectionFromPoints(p1, p2, crossData.in_point);
      }
      
      console.log('回显方向:', this.lineDirection);
      
      this.drawLineOpen = true;
    }
  } catch(e) {
    console.error('解析cross_line_area失败:', e);
  }
}
        
        this.form.template_data = this.normalizeAlgorithmTemplateRows(this.form.template_data);
        
        if (this.form.tem_frames == '') {
          this.form.tem_frames = '[27,37]';
        }
        if (this.form.confidence == null || this.form.confidence == '') {
          this.form.confidence = "60";
        }
        
        this.image_draw_type = this.form.image_draw_type;
        this.form.resource_id_old = this.form.resource_id;
        this.shield_status = Number(response.data.datalist.shield_status);
        this.dialogVisible = true;
        this.handleSelect();
        this.handleChangeSf(this.form.Algorithm_library_id);
        this.form.equipment_name = response.data.datalist.Equipment_id;
        
        this.handleimg();
        
        // 模型区域数据回显
        (() => {
          if (response.data.datalist.template_list_area && response.data.datalist.template_list_area != '[]') {
            let arr = JSON.parse(response.data.datalist.template_list_area.replace(/'/g, '"'));
            let jia = [];
            let jia_w = [];
            for (let w = 0; w < arr.length; w++) {
              for (let i = 0; i < arr[w].length; i++) {
                let x = parseFloat(arr[w][i].x);
                let y = parseFloat(arr[w][i].y);
                jia.push({
                  x: x,
                  y: y,
                  type: arr[w][i].type,
                  color: arr[w][i].color,
                });
              }
              jia_w.push(jia);
              jia = [];
            }
            this.mark_list_model = [...jia_w];
          } else {
            this.mark_list_model = [];
          }
        })();

        let tem_conf_area = response.data.datalist.tem_conf_area;
        const editedSourceKey = this.streamSourceKey;
        this.loadStreamCapabilities(this.algorithmEquipmentId())
          .then((info) => {
            if (!info || this._algorithmFormClosed || editedSourceKey !== this.streamSourceKey) return;
            const response = { data: info };
            if (response.data.data.equipment_code == "201") {
              this.area2 = true;
              if (tem_conf_area && tem_conf_area != '[]') {
                let arr2 = JSON.parse(tem_conf_area.replace(/'/g, '"'));
                let jia2 = [];
                for (let i = 0; i < arr2[0].length; i++) {
                  let x = parseFloat(arr2[0][i].x);
                  let y = parseFloat(arr2[0][i].y);
                  jia2.push({
                    x: x,
                    y: y,
                  });
                }
                this.mark_list2 = [jia2];
              } else {
                this.mark_list2 = [];
              }
              if (this.$refs.mycanvas2) this.initCanvas2();
            } else {
              this.area2 = false;
            }
          });
      }
    })
    .catch(function (response) {
      console.log(response);
    });
},
    
    handleSelect(a) {
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
          if (response.data.code === 200) {
            this.options1 = response.data.mine_list;
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
  mounted() {
    this.init()
    if (this.$route.query.conf_id) {
      this.type_jx = true;
      this.type_qy = true;
      this.handlechange(this.$route.query.conf_id);
    }
  },
  beforeDestroy() {
    
  },
  destroyed() {
    
  },
};

var render=function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"sfgl_child algorithm-config-page algorithm-config-split"},[_c('el-button',{staticStyle:{"margin":"12px"},attrs:{"size":"mini"},on:{"click":_vm.goback}},[_vm._v("返回")]),_c('div',{staticClass:"sfpzs"},[_c('el-form',{ref:"form",attrs:{"model":_vm.form,"rules":_vm.rules,"size":"mini","label-width":"110px"}},[_c('div',{staticClass:"algorithm-config-top",class:{ 'algorithm-top-with-model': _vm.type_jx || _vm.model_template_config_id_num == 5 || _vm.form.model_two_type != '' }},[_c('section',{staticClass:"algorithm-basic-panel",attrs:{"aria-label":"基础信息"}},[_c('h3',{staticClass:"algorithm-panel-title"},[_vm._v("基础信息")]),_c('el-form-item',{staticStyle:{"padding-top":"16px"},attrs:{"label":"任务名称","prop":"conf_name"}},[_c('el-input',{staticStyle:{"width":"50%","float":"left"},model:{value:(_vm.form.conf_name),callback:function ($$v) {_vm.$set(_vm.form, "conf_name", $$v)},expression:"form.conf_name"}}),_c('div',{staticClass:"w-1\\2 algorithm-field-hint",staticStyle:{"color":"red"}},[_vm._v("*例:报警设备_解析类型名称")])],1),_c('el-form-item',{attrs:{"label":"单位名称","prop":"Mine_id"}},[_c('el-select',{staticStyle:{"width":"50%","float":"left"},attrs:{"placeholder":"请选择单位名称","size":"small","clearable":"","filterable":""},model:{value:(_vm.form.Mine_id),callback:function ($$v) {_vm.$set(_vm.form, "Mine_id", $$v)},expression:"form.Mine_id"}},_vm._l((_vm.options1),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.mine_name,"value":item.id}})}),1)],1),_c('el-form-item',{attrs:{"label":"报警设备","prop":"equipment_name"}},[_c('el-cascader',{staticStyle:{"width":"50%","float":"left"},attrs:{"options":_vm.dict.equipment_list,"props":_vm.props,"clearable":"","filterable":""},on:{"change":_vm.onAlarmDeviceChange},model:{value:(_vm.form.equipment_name),callback:function ($$v) {_vm.$set(_vm.form, "equipment_name", $$v)},expression:"form.equipment_name"}})],1),_c('el-form-item',{staticClass:"algorithm-stream-row",attrs:{"label":"视频码流"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"disabled":_vm.streamSelectionDisabled},model:{value:(_vm.streamSelection),callback:function ($$v) {_vm.streamSelection=$$v},expression:"streamSelection"}},_vm._l((_vm.streamOptions),function(option){return _c('el-option',{key:option.value,attrs:{"value":option.value,"label":option.label,"disabled":option.disabled}})}),1),_c('div',{staticClass:"algorithm-stream-help"},[_vm._v(_vm._s(_vm.streamCapabilityHint))])],1),_c('el-form-item',{attrs:{"label":"解析类型","prop":"Algorithm_library_id"}},[_c('el-select',{staticStyle:{"width":"50%","float":"left"},attrs:{"placeholder":"请选择解析类型","clearable":"","filterable":""},on:{"change":function($event){return _vm.countfns()}},model:{value:(_vm.form.Algorithm_library_id),callback:function ($$v) {_vm.$set(_vm.form, "Algorithm_library_id", $$v)},expression:"form.Algorithm_library_id"}},_vm._l((_vm.dict.algorithm_list),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.algorithm_name,"value":item.id}})}),1)],1),_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"报警等级","prop":"res_type"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择报警等级","size":"mini","clearable":"","filterable":""},on:{"change":_vm.markAlgorithmAlarmEdited},model:{value:(_vm.form.res_type),callback:function ($$v) {_vm.$set(_vm.form, "res_type", $$v)},expression:"form.res_type"}},_vm._l((_vm.dict.type_list),function(item){return _c('el-option',{key:'报警等级'+item.id,attrs:{"label":item.value,"value":item.id}})}),1)],1),_c('el-form-item',{attrs:{"label":"算力资源","prop":"resource_id"}},[_c('el-cascader',{staticStyle:{"width":"50%"},attrs:{"options":_vm.computeOptions,"props":_vm.computeProps,"show-all-levels":false,"clearable":""},on:{"change":_vm.markAlgorithmResourceEdited},model:{value:(_vm.form.resource_id),callback:function ($$v) {_vm.$set(_vm.form, "resource_id", $$v)},expression:"form.resource_id"}}),_c('div',{staticClass:"algorithm-resource-status",attrs:{"role":"status","aria-live":"polite"}},[_vm._v(_vm._s(_vm.algorithmAdmissionHint))])],1)],1),(_vm.type_jx || _vm.model_template_config_id_num == 5 || _vm.form.model_two_type != '')?_c('section',{staticClass:"algorithm-model-settings",attrs:{"aria-label":"模型配置"}},[_c('h3',{staticClass:"algorithm-panel-title"},[_vm._v("模型配置")]),(_vm.type_jx)?_c('div',{staticStyle:{"width":"100%","border":"1px dashed #e5e5e5","background":"#f9fafb","border-radius":"10px"}},[_c('el-form-item',{directives:[{name:"show",rawName:"v-show",value:(_vm.model_template_config_id_num != 4),expression:"model_template_config_id_num != 4"}],staticStyle:{"margin-top":"16px"},attrs:{"label":"检测类型"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择检测类型","size":"mini","clearable":"","filterable":"","multiple":""},on:{"change":_vm.handleChangeLabelList},model:{value:(_vm.form.label_list),callback:function ($$v) {_vm.$set(_vm.form, "label_list", $$v)},expression:"form.label_list"}},_vm._l((_vm.options4),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.test_type_cname,"value":item.test_type_ename}})}),1)],1),(_vm.algorithmPeopleCountVisible)?_c('div',{staticClass:"algorithm-people-counts",staticStyle:{"font-size":"12px","line-height":"20px"}},[_c('el-form-item',{attrs:{"label":"人数统计版本"}},[_c('el-select',{attrs:{"aria-label":"人数统计版本"},on:{"change":_vm.changeAlgorithmCountingScene},model:{value:(_vm.algorithmCountingScene),callback:function ($$v) {_vm.algorithmCountingScene=$$v},expression:"algorithmCountingScene"}},[_c('el-option',{attrs:{"label":"唯一性检测装置","value":"uniqueness"}}),_c('el-option',{attrs:{"label":"乘车点","value":"boarding"}})],1)],1),(_vm.algorithmCountingBoarding)?_c('el-form-item',{attrs:{"label":"驻留确认帧数"}},[_c('el-input-number',{attrs:{"min":1,"max":120,"step":1,"precision":0,"aria-label":"驻留确认帧数"},on:{"change":function($event){_vm._algorithmOperationalEdited = true}},model:{value:(_vm.algorithmCountingResidenceFrames),callback:function ($$v) {_vm.algorithmCountingResidenceFrames=$$v},expression:"algorithmCountingResidenceFrames"}}),_c('div',{staticStyle:{"color":"#78869a","font-size":"12px"}},[_vm._v("连续处于区域另一侧达到此帧数后确认，避免边界抖动。")])],1):_vm._e(),_c('el-form-item',{attrs:{"label":_vm.algorithmCountingEnteringLabel}},[_c('el-input',{attrs:{"value":_vm.algorithmPeopleEnteringDisplay,"readonly":"","aria-label":_vm.algorithmCountingEnteringLabel}})],1),_c('el-form-item',{attrs:{"label":_vm.algorithmCountingExitingLabel}},[_c('el-input',{attrs:{"value":_vm.algorithmPeopleExitingDisplay,"readonly":"","aria-label":_vm.algorithmCountingExitingLabel}})],1),_c('div',{staticStyle:{"color":"#78869a"},attrs:{"role":"status"}},[_vm._v(_vm._s(_vm.algorithmPeopleCountHint))])],1):_vm._e(),(_vm.usertype == 1)?_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"模型类型"}},[_c('el-cascader',{staticStyle:{"width":"50%"},attrs:{"options":_vm.modelOptions,"props":_vm.modelProps,"clearable":""},model:{value:(_vm.form.model_template_config_id),callback:function ($$v) {_vm.$set(_vm.form, "model_template_config_id", $$v)},expression:"form.model_template_config_id"}})],1):_vm._e(),(_vm.usertype == 1)?_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"模型小类"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择模型小类","clearable":"","filterable":""},on:{"change":_vm.onAlgorithmTemplateSmallChange},model:{value:(_vm.form.template_small_id),callback:function ($$v) {_vm.$set(_vm.form, "template_small_id", $$v)},expression:"form.template_small_id"}},_vm._l((_vm.modelSmallOption),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.template_small_name,"value":item.id}})}),1)],1):_vm._e(),_c('div',{staticClass:"algorithm-template-parameters",staticStyle:{"width":"90%","height":"auto","margin-left":"32px","padding-bottom":"12px"}},[(_vm.usertype == 1)?_c('div',{staticStyle:{"display":"flex","flex-wrap":"wrap","gap":"8px","margin":"8px 0"}},[_c('el-button',{attrs:{"type":"success","icon":"el-icon-plus","size":"mini"},on:{"click":_vm.addItem}},[_vm._v("新增参数")]),_c('el-button',{staticStyle:{"margin-left":"0"},attrs:{"icon":"el-icon-refresh","loading":_vm.algorithmTemplateLoading,"disabled":!_vm.form.template_small_id,"size":"mini"},on:{"click":_vm.completeAlgorithmTemplateParameters}},[_vm._v("补齐模板参数")])],1):_vm._e(),(_vm.algorithmTemplateError)?_c('div',{staticStyle:{"color":"#c45656","font-size":"12px","line-height":"20px"},attrs:{"role":"alert"}},[_vm._v(_vm._s(_vm.algorithmTemplateError))]):_vm._e(),_vm._l((_vm.form.template_data),function(item,index){return _c('div',{directives:[{name:"show",rawName:"v-show",value:(!_vm.isAlgorithmPeopleCountParameter(item.key)),expression:"!isAlgorithmPeopleCountParameter(item.key)"}],key:index,staticClass:"form-group"},[_c('span',{staticStyle:{"display":"inline-block","width":"20px"},attrs:{"slot":"label"},slot:"label"},[(item.msg)?_c('el-tooltip',{attrs:{"effect":"dark","content":item.msg,"placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})]):_vm._e()],1),(_vm.usertype==1)?_c('el-input',{staticStyle:{"width":"15%","margin-right":"10px","margin-top":"10px"},attrs:{"placeholder":"请输入键名","size":"mini","disabled":_vm.usertype != 1},model:{value:(item.key),callback:function ($$v) {_vm.$set(item, "key", $$v)},expression:"item.key"}}):_c('el-input',{staticStyle:{"width":"15%","margin-right":"10px","margin-top":"10px"},attrs:{"placeholder":"请输入键名","size":"mini","disabled":_vm.model_template_config_id_num != 2},model:{value:(item.key),callback:function ($$v) {_vm.$set(item, "key", $$v)},expression:"item.key"}}),(_vm.usertype==1)?_c('el-input',{staticStyle:{"width":"39%","margin-right":"10px","margin-top":"10px"},attrs:{"placeholder":"请输入值","size":"mini","disabled":_vm.usertype != 1},model:{value:(item.value),callback:function ($$v) {_vm.$set(item, "value", $$v)},expression:"item.value"}}):_c('el-input',{staticStyle:{"width":"39%","margin-right":"10px","margin-top":"10px"},attrs:{"placeholder":"请输入值","size":"mini","disabled":_vm.model_template_config_id_num != 2},model:{value:(item.value),callback:function ($$v) {_vm.$set(item, "value", $$v)},expression:"item.value"}}),(_vm.usertype == 1)?_c('el-button',{staticStyle:{"margin-right":"10px","margin-top":"10px"},attrs:{"type":"danger","icon":"el-icon-delete","size":"mini"},on:{"click":function($event){return _vm.removeItem(index)}}},[_vm._v("删除")]):_vm._e()],1)})],2)],1):_vm._e(),_c('el-form-item',{directives:[{name:"show",rawName:"v-show",value:(_vm.model_template_config_id_num == 5),expression:"model_template_config_id_num == 5"}],staticStyle:{"margin-top":"16px"},attrs:{"label":"扩增比例参数","prop":"amp"}},[_c('el-input-number',{staticStyle:{"width":"50%","float":"left"},attrs:{"controls-position":"right","min":1,"max":100},model:{value:(_vm.form.amp),callback:function ($$v) {_vm.$set(_vm.form, "amp", $$v)},expression:"form.amp"}})],1),_c('el-form-item',{directives:[{name:"show",rawName:"v-show",value:(_vm.model_template_config_id_num == 5),expression:"model_template_config_id_num == 5"}],staticStyle:{"margin-top":"16px"},attrs:{"label":"图像类型","prop":"alg_select_type"}},[_c('el-radio-group',{model:{value:(_vm.form.alg_select_type),callback:function ($$v) {_vm.$set(_vm.form, "alg_select_type", $$v)},expression:"form.alg_select_type"}},[_c('el-radio',{attrs:{"label":'1'}},[_vm._v("裁剪")]),_c('el-radio',{attrs:{"label":'2'}},[_vm._v("屏蔽")]),_c('el-radio',{attrs:{"label":'3'}},[_vm._v("原图")])],1)],1),(_vm.model_template_config_id_num == 5)?_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"级联解析类型","prop":"model_two_type"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择级联解析类型","size":"mini","clearable":"","filterable":""},model:{value:(_vm.form.model_two_type),callback:function ($$v) {_vm.$set(_vm.form, "model_two_type", $$v)},expression:"form.model_two_type"}},_vm._l((_vm.options8),function(item){return _c('el-option',{key:'级联解析类型'+item.id,attrs:{"label":item.algorithm_name,"value":item.id}})}),1)],1):_vm._e(),(_vm.form.model_two_type != '')?_c('div',{staticStyle:{"width":"100%","border":"1px dashed #e5e5e5","background":"#f9fafb","border-radius":"10px"}},[_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"检测类型"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择检测类型","size":"mini","clearable":"","filterable":"","multiple":""},model:{value:(_vm.label_list),callback:function ($$v) {_vm.label_list=$$v},expression:"label_list"}},_vm._l((_vm.options7),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.test_type_cname,"value":item.test_type_ename}})}),1)],1),_c('el-form-item',{attrs:{"prop":"confidence"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                置信度\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"触发报警阈值，值越小越容易触发报警。取值范围：（1-100）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请输入置信度","maxlength":"4"},model:{value:(_vm.confidence),callback:function ($$v) {_vm.confidence=_vm._n($$v)},expression:"confidence"}})],1)],1):_vm._e()],1):_vm._e()]),(_vm.type_qy)?_c('div',{staticClass:"algorithm-drawing-scroll",staticStyle:{"width":"100%","height":"680px","border":"1px dashed #e5e5e5","background":"#f9fafb","border-radius":"10px"}},[_c('div',{staticStyle:{"width":"100%","height":"400px"}},[_c('div',{staticStyle:{"width":"120px","height":"30px","border":"2px solid #5b65eb","text-align":"center","color":"#5b65eb","background":"#ddefff","display":"flex","align-items":"center","justify-content":"center","font-size":"0.8vw","margin":"12px 0 0 12px","float":"left"}},[_vm._v("\n            绘制检测区域\n          ")]),_c('div',{staticStyle:{"width":"640px","height":"419px","float":"left","margin":"12px 0 0 12px"}},[_c('div',{directives:[{name:"loading",rawName:"v-loading",value:(_vm.loading),expression:"loading"}],staticClass:"Bcanvas"},[(!_vm.imgOpen)?_c('div',{staticClass:"jia_div"},[_vm._v(_vm._s(_vm.algorithmSnapshotHint))]):_vm._e(),(_vm.imgOpen)?_c('img',{staticStyle:{"width":"640px","height":"360px"},attrs:{"src":_vm.imgurl,"alt":""},on:{"load":function($event){_vm.loading = false}}}):_vm._e(),(_vm.isTypeTFS)?_c('canvas',{ref:"mycanvas",attrs:{"id":"mycanvas","tabindex":"0"}}):_vm._e(),(_vm.shield_status == 1||_vm.image_draw_type == 2)?_c('div',{staticClass:"jia_div"}):_vm._e()]),(_vm.algorithmPeopleCountVisible)?_c('div',{staticClass:"algorithm-counting-tools",staticStyle:{"display":"flex","flex-wrap":"wrap","gap":"8px","align-items":"center","padding":"6px 0"}},[_c('el-button',{attrs:{"type":"text","icon":"el-icon-refresh"},on:{"click":function($event){return _vm.handleimg(1)}}},[_vm._v("刷新图片")]),_c('el-button',{attrs:{"type":"text","icon":"el-icon-edit"},on:{"click":_vm.startAlgorithmCountingDrawing}},[_vm._v(_vm._s(_vm.algorithmCountingPoints.length ? '重新绘制' : '开始绘制')+_vm._s(_vm.algorithmCountingBoarding ? '区域' : '计数线'))]),_c('el-button',{attrs:{"type":"text","disabled":!_vm.algorithmCountingPoints.length},on:{"click":_vm.undoAlgorithmCountingPoint}},[_vm._v("撤销顶点")]),_c('el-button',{attrs:{"type":"text","disabled":!_vm.algorithmCountingDrawing},on:{"click":_vm.finishAlgorithmCountingDrawing}},[_vm._v("完成绘制")]),(!_vm.algorithmCountingBoarding)?_c('el-button',{attrs:{"type":"text","disabled":_vm.algorithmCountingPoints.length < 2},on:{"click":_vm.reverseAlgorithmCountingDirection}},[_vm._v("切换进出方向")]):_vm._e(),_c('div',{staticStyle:{"width":"100%","font-size":"12px","line-height":"1.6","color":"#78869a"},attrs:{"role":"status"}},[_vm._v(_vm._s(_vm.algorithmCountingGeometryHint))]),(_vm.algorithmCountingGeometryError)?_c('div',{staticStyle:{"color":"#c45656","font-size":"12px"},attrs:{"role":"alert"}},[_vm._v(_vm._s(_vm.algorithmCountingGeometryError))]):_vm._e()],1):_vm._e(),(_vm.isTypeTFS && !_vm.algorithmPeopleCountVisible)?_c('div',{staticClass:"canvasBtn"},[_c('el-button',{attrs:{"type":"text","icon":"el-icon-refresh"},on:{"click":function($event){return _vm.handleimg(1)}}},[_vm._v("刷新")]),_c('el-button',{attrs:{"type":"text","icon":"el-icon-edit"},on:{"click":_vm.handleDrewAgain}},[_vm._v("重新绘制")]),_c('el-button',{attrs:{"type":"text","icon":"el-icon-refresh-left"},on:{"click":_vm.resole}},[_vm._v("撤销")]),_c('el-button',{attrs:{"type":"text","show":!_vm.drawLineOpen ? 'primary' : ''},on:{"click":function($event){return _vm.switchDrawMode(false)}}},[_vm._v("绘制区域")]),_c('el-button',{attrs:{"type":"text","show":_vm.drawLineOpen ? 'primary' : ''},on:{"click":function($event){return _vm.switchDrawMode(true)}}},[_vm._v("绘制警戒线")])],1):_vm._e()])]),_c('div',{staticStyle:{"width":"100%","height":"180px"}},[_c('div',{staticStyle:{"width":"38%","height":"100%","float":"left","margin-left":"15%"}},[_c('el-form-item',{staticStyle:{"padding-top":"16px"},attrs:{"prop":"confidence"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                置信度\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"触发报警阈值，值越小越容易触发报警。取值范围：（1-100）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入置信度","maxlength":"4"},model:{value:(_vm.form.confidence),callback:function ($$v) {_vm.$set(_vm.form, "confidence", _vm._n($$v))},expression:"form.confidence"}})],1),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"prop":"sensitivity"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                间隔帧\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"视频流检测频率，如设置为25，1s检测一次。取值范围：（1-100）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入间隔帧","maxlength":"4"},model:{value:(_vm.form.sensitivity),callback:function ($$v) {_vm.$set(_vm.form, "sensitivity", _vm._n($$v))},expression:"form.sensitivity"}})],1):_vm._e(),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"prop":"interval_time"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                告警间隔\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"当满足触发报警条件达到一定间隔时长以后才会上报。取值范围：（1-3600秒）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入告警间隔","maxlength":"4"},model:{value:(_vm.form.interval_time),callback:function ($$v) {_vm.$set(_vm.form, "interval_time", _vm._n($$v))},expression:"form.interval_time"}},[_c('template',{slot:"append"},[_vm._v("秒")])],2)],1):_vm._e(),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"label":"目标框显示"}},[_c('el-select',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请选择","clearable":"","filterable":""},model:{value:(_vm.form.image_draw_type),callback:function ($$v) {_vm.$set(_vm.form, "image_draw_type", $$v)},expression:"form.image_draw_type"}},[_c('el-option',{attrs:{"label":"是","value":1}}),_c('el-option',{attrs:{"label":"否","value":2}})],1)],1):_vm._e()],1),(_vm.isTypeTFS)?_c('div',{staticStyle:{"width":"38%","height":"100%","float":"left"}},[_c('div',{staticStyle:{"width":"100%","height":"16px"}}),(_vm.show_cxsc)?_c('el-form-item',{attrs:{"prop":"duration_time"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                持续时长\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"需求行为的持续时长。取值范围：（1-1800）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入持续时长","maxlength":"4"},model:{value:(_vm.form.duration_time),callback:function ($$v) {_vm.$set(_vm.form, "duration_time", _vm._n($$v))},expression:"form.duration_time"}},[_c('template',{slot:"append"},[_vm._v("秒")])],2)],1):_vm._e(),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"label":"开始时间","prop":"defense_time_start"}},[_c('el-time-picker',{staticStyle:{"width":"100%"},attrs:{"value-format":"HH:mm:ss","picker-options":{selectableRange: '00:00:00 - 23:59:59'},"placeholder":"任意时间点","default-value":new Date().setHours(0, 0, 0, 0)},model:{value:(_vm.form.defense_time_start),callback:function ($$v) {_vm.$set(_vm.form, "defense_time_start", $$v)},expression:"form.defense_time_start"}})],1):_vm._e(),_c('el-form-item',{attrs:{"label":"结束时间","prop":"defense_time_end"}},[_c('el-time-picker',{staticStyle:{"width":"100%"},attrs:{"value-format":"HH:mm:ss","picker-options":{selectableRange: '00:00:00 - 23:59:59'},"placeholder":"任意时间点","default-value":new Date().setHours(0, 0, 0, 0)},model:{value:(_vm.form.defense_time_end),callback:function ($$v) {_vm.$set(_vm.form, "defense_time_end", $$v)},expression:"form.defense_time_end"}})],1)],1):_vm._e()])]):_vm._e(),_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"任务说明"}},[_c('el-input',{staticStyle:{"width":"50%","float":"left"},attrs:{"placeholder":"请输入备注","type":"textarea"},model:{value:(_vm.form.Algorithm_config_ps),callback:function ($$v) {_vm.$set(_vm.form, "Algorithm_config_ps", $$v)},expression:"form.Algorithm_config_ps"}})],1),_c('el-form-item',{staticClass:"algorithm-form-actions"},[_c('div',{staticClass:"algorithm-action-buttons",staticStyle:{"text-align":"-end","margin-bottom":"24px"}},[_c('el-button',{attrs:{"type":"primary"},on:{"click":_vm.sub_fn}},[_vm._v("保存")]),_c('el-button',{on:{"click":_vm.goback}},[_vm._v("取消")])],1)])],1)],1),_c('el-dialog',{attrs:{"title":_vm.title2,"id":"alarmTypeBox","visible":_vm.dialogVisible2,"width":"500px","close-on-click-modal":false},on:{"update:visible":function($event){_vm.dialogVisible2=$event},"close":_vm.handleClose2}},[_c('div',{staticClass:"radio-group-title"},[_vm._v("告警区域")]),_c('br'),_c('el-radio-group',{staticClass:"radio-grid",model:{value:(_vm.selectedOption),callback:function ($$v) {_vm.selectedOption=$$v},expression:"selectedOption"}},[_c('el-radio',{staticClass:"grid-item",attrs:{"label":'告警区域'}},[_vm._v("告警区域")])],1),_c('br'),_c('br'),_c('div',{staticClass:"radio-group-title"},[_vm._v("后处理区域")]),_c('br'),_c('el-radio-group',{staticClass:"radio-grid",model:{value:(_vm.selectedOption),callback:function ($$v) {_vm.selectedOption=$$v},expression:"selectedOption"}},[_c('el-radio',{staticClass:"grid-item",attrs:{"label":_vm.selectedOption_type}},[_vm._v(_vm._s(_vm.selectedOption_type))])],1),_c('span',{staticClass:"dialog-footer",attrs:{"slot":"footer"},slot:"footer"},[_c('el-button',{on:{"click":function($event){_vm.dialogVisible2 = false;_vm.handleDeleteList()}}},[_vm._v("取 消")]),_c('el-button',{attrs:{"type":"primary"},on:{"click":function($event){return _vm.handleUpdateList()}}},[_vm._v("确 定")])],1)],1)],1)};
var staticRenderFns=[];
Component.render=render;Component.staticRenderFns=staticRenderFns;Component._compiled=true;Component._scopeId="data-v-77b543f0";Component.__file="src/components/sfgl_child.vue";return Component;
})();
},"4ad5":function(t,e,i){"use strict";i("6b8f")},5494:function(t,e,i){"use strict";var a=i("83ab"),l=i("e330"),s=i("edd0"),o=URLSearchParams.prototype,r=l(o.forEach);a&&!("size"in o)&&s(o,"size",{get:function(){var t=0;return r(this,(function(){t++})),t},configurable:!0,enumerable:!0})},"605d":function(t,e,i){"use strict";var a=i("da84"),l=i("c6b6");t.exports="process"===l(a.process)},"6b8f":function(t,e,i){},"88a7":function(t,e,i){"use strict";var a=i("cb2d"),l=i("e330"),s=i("577e"),o=i("d6d6"),r=URLSearchParams,n=r.prototype,m=l(n.append),d=l(n["delete"]),h=l(n.forEach),_=l([].push),c=new r("a=1&a=2&b=3");c["delete"]("a",1),c["delete"]("b",void 0),c+""!=="a=2"&&a(n,"delete",(function(t){var e=arguments.length,i=e<2?void 0:arguments[1];if(e&&void 0===i)return d(this,t);var a=[];h(this,(function(t,e){_(a,{key:e,value:t})})),o(e,1);var l,r=s(t),n=s(i),c=0,p=0,f=!1,u=a.length;while(c<u)l=a[c++],f||l.key===r?(f=!0,d(this,l.key)):p++;while(p<u)l=a[p++],l.key===r&&l.value===n||m(this,l.key,l.value)}),{enumerable:!0,unsafe:!0})},a640:function(t,e,i){"use strict";var a=i("d039");t.exports=function(t,e){var i=[][t];return!!i&&a((function(){i.call(null,e||function(){return 1},1)}))}},d58f:function(t,e,i){"use strict";var a=i("59ed"),l=i("7b0b"),s=i("44ad"),o=i("07fa"),r=TypeError,n=function(t){return function(e,i,n,m){var d=l(e),h=s(d),_=o(d);a(i);var c=t?_-1:0,p=t?-1:1;if(n<2)while(1){if(c in h){m=h[c],c+=p;break}if(c+=p,t?c<0:_<=c)throw new r("Reduce of empty array with no initial value")}for(;t?c>=0:_>c;c+=p)c in h&&(m=i(m,h[c],c,d));return m}};t.exports={left:n(!1),right:n(!0)}},d6d6:function(t,e,i){"use strict";var a=TypeError;t.exports=function(t,e){if(t<e)throw new a("Not enough arguments");return t}},edd0:function(t,e,i){"use strict";var a=i("13d2"),l=i("9bf2");t.exports=function(t,e,i){return i.get&&a(i.get,e,{getter:!0}),i.set&&a(i.set,e,{setter:!0}),l.f(t,e,i)}}}]);







//# sourceMappingURL=chunk-e0401796.c81b8c13.js.map
