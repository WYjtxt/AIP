// Shared source selection and snapshot lifetime for the original algorithm forms.
export default {
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
