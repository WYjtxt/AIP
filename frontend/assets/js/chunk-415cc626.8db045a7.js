(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["chunk-415cc626"],{"13d5":function(t,e,i){"use strict";var s=i("23e7"),a=i("d58f").left,l=i("a640"),o=i("2d00"),r=i("605d"),n=!r&&o>79&&o<83,m=n||!l("reduce");s({target:"Array",proto:!0,forced:m},{reduce:function(t){var e=arguments.length;return a(this,t,e,e>1?arguments[1]:void 0)}})},"4b0f":function(t,e,i){},"605d":function(t,e,i){"use strict";var s=i("da84"),a=i("c6b6");t.exports="process"===a(s.process)},"646e":function(t,e,i){"use strict";i("4b0f")},"907f":function(t,e,i){},a640:function(t,e,i){"use strict";var s=i("d039");t.exports=function(t,e){var i=[][t];return!!i&&s((function(){i.call(null,e||function(){return 1},1)}))}},c9aa:function(t,e,i){"use strict";i("907f")},cee7:function(t,e,i){
"use strict";i.r(e);
i("14d9");i("d9e2");i("13d5");i("4360");i("896f");i("de4a");i("dc58");i("c329");i("8f15");i("ed5a");i("c9aa");i("2877");i("646e");
var store=i("4360").a,draw_test=i("896f").a,draw_test2=i("de4a").a,draw_test3=i("dc58").a,draw_test4=i("c329").a;var compute=i("8f15").b,findModelName=i("8f15").d,modelApi=i("ed5a").a;
// Shared source selection and snapshot lifetime for the original algorithm forms.
var algorithmStreamMixin={
  data() {
    return { streamCapabilities: null, streamCapabilitiesDeviceId: null, streamCapabilitiesLoading: false, streamCapabilitiesError: '', algorithmSnapshotReadyKey: null };
  },
  computed: {
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
    if (this.algorithmEquipmentId() && !this.streamCapabilitiesDeviceId) this.loadStreamCapabilities(this.algorithmEquipmentId());
    if (this.type_qy) this.ensureVisibleAlgorithmSnapshot();
  },
  beforeDestroy() {
    this._algorithmFormClosed = true;
    this.invalidateAlgorithmImage();
    this._algorithmCapabilityGeneration++;
    if (this._algorithmCapabilityController) this._algorithmCapabilityController.abort();
    this._algorithmCapabilityController = null;
  },
  methods: {
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
            return { id: card.id, devId: card.dev_id, label: (card.dev_get_target || '计算卡') + ' · 卡 ' + (card.dev_id == null ? '—' : card.dev_id) };
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
      if (!this._algorithmResourceDefaultPending) return;
      if (this.form.resource_id != null && this.form.resource_id !== '' && this.form.resource_id !== 0) { this._algorithmResourceDefaultPending = false; return; }
      var cards = [];
      (this.computeOptions || []).forEach(function (host) { cards = cards.concat(host.children || []); });
      var number = function (value) { return value == null || value === '' || !Number.isFinite(Number(value)) ? Infinity : Number(value); };
      cards.sort(function (a, b) { return number(a.devId) - number(b.devId) || number(a.id) - number(b.id); });
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

var cavdiv=(function(){










var Component={
  mixins: [algorithmStreamMixin],
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
      form: this.item,
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
      confidence:'60',
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
    sub_fn() {
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
            if(this.dict.algorithm_list_five.length != 0){
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
              conf_area: this.drawLineOpen ? this.mark_lists3 : this.mark_lists,
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.jclxslist),
              shield_status: this.shield_status,
              tem_frames: this.form.tem_frames,
              confidence: this.form.confidence,
              tem_conf_area: this.mark_lists2,
              draw_type: this.drawLineOpen ? '2' : '1',
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
              conf_area: this.drawLineOpen ? JSON.stringify(this.mark_lists3) : JSON.stringify(this.mark_lists),
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.jclxslist),
              shield_status: this.shield_status,
              tem_frames: this.form.tem_frames,
              confidence: this.form.confidence,
              tem_conf_area: JSON.stringify(this.mark_lists2),
              draw_type: this.drawLineOpen ? '2' : '1',
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
      // 检查是否有任何一个 key 或 value 为空
      // if (this.form.template_data.length != 0) {
      //   for (const item of this.form.template_data) {
      //     if (!item.key || item.key.trim() === '' || !item.value || item.value.trim() === '') {
      //       return false;
      //     }
      //   }
      // }
      return this.form.template_data.map(item => {
        const obj = {};
        obj[item.key] = item.value;
        return obj;
      });
    },
    // 提交数据处理
    handleData() {
      if (this.mark_list.length != 0 && !this.drawLineOpen) {
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
      this.form.template_data.splice(index, 1)
    },
    // 新增一个小类详情
    addItem() {
      this.form.template_data.push({ key: '', value: '' })
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
            // id: 1,
          },
        })
        .then(async (response) => {
          if (!current()) return;
          const data = response.data.data || {};
          const model = (data.model_data || [])[0];
          const type = (data.model_type_data || [])[0];
          const small = (data.template_small_data || [])[0];
          this.options4 = data.algorithm_data || [];
          this.selectedOption = data.show_status;
          this.selectedOption_type_s = data.show_status;
          const selectedByUser = userSelected || this._algorithmSelectedModelId === String(id);
          const useDefaults = selectedByUser || !this.algorithmIsEditing();
          if (useDefaults && model && this.form.model_template_config_id === modelBefore) this.$set(this.form, 'model_template_config_id', model.id);
          const smallOptions = type ? this.getModelSmallDict2(type.id, current) : Promise.resolve();
          let details = Promise.resolve();
          if (useDefaults && small && this.form.template_small_id === smallBefore) {
            this.$set(this.form, 'template_small_id', small.id);
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
    handleChangeTemplateSmall(isCurrent) {
      const form = this.form, smallId = this.form.template_small_id;
      const current = () => !this._algorithmFormClosed && form === this.form && smallId === this.form.template_small_id && (typeof isCurrent !== 'function' || isCurrent());
      return this.$http.get(modelApi.getModelSmallDetail, {
        params: {
          id: this.form.template_small_id
        }
      }).then(response => {
        if (!current()) return;
        if (response.data.code == 200) {
            this.form.template_data = response.data.data.list_data.reduce((acc, obj) => {
                if (Object.keys(obj).length > 0) {
                  const key = Object.keys(obj)[0];
                  acc.push({
                    key: key,
                    value: obj[key][0],
                    msg: obj[key][1]
                  });
                }
              return acc;
            }, []);
        } else {
          this.form.template_data = []
        }
      }).catch(rek => {
        if (current()) this.form.template_data = [];
        console.log(rek)
      })
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
    handleChangeLabelList() {
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
            this.form = response.data.datalist;
            this.restoreAlgorithmSource();
            this.$set(this.form, 'stream_type', this.configStreamType === 'main' || this.configStreamType === 'sub' ? this.configStreamType : null);
            this.form.model_two_type = response.data.datalist.model_two_type*1
            if(this.form.model_two_data.length){
              this.label_list = this.form.model_two_data[0].label_list;
              this.confidence = this.form.model_two_data[0].confidence;
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
            this.form.template_data = []
            if (this.form.tem_frames == '') {
              this.form.tem_frames = '[27,37]'
            }
            if (this.form.confidence == null || this.form.confidence == '') {
              this.form.confidence = "60"
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

var render=function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"sfgl_child algorithm-config-model"},[_c('div',{staticClass:"sfpzs"},[_c('el-form',{ref:"form",attrs:{"model":_vm.form,"rules":_vm.rules,"size":"mini","label-width":"110px"}},[(_vm.type_jx)?_c('div',{staticStyle:{"width":"100%","border":"1px dashed #e5e5e5","background":"#f9fafb","border-radius":"10px"}},[_c('el-form-item',{directives:[{name:"show",rawName:"v-show",value:(_vm.model_template_config_id_num != 4),expression:"model_template_config_id_num != 4"}],staticStyle:{"margin-top":"16px"},attrs:{"label":"检测类型"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择检测类型","size":"mini","clearable":"","filterable":"","multiple":""},on:{"change":_vm.handleChangeLabelList},model:{value:(_vm.jclxslist),callback:function ($$v) {_vm.jclxslist=$$v},expression:"jclxslist"}},_vm._l((_vm.options4),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.test_type_cname,"value":item.test_type_ename}})}),1)],1),(_vm.usertype == 1)?_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"模型类型"}},[_c('el-cascader',{staticStyle:{"width":"50%"},attrs:{"options":_vm.modelOptions,"props":_vm.modelProps,"clearable":""},model:{value:(_vm.form.model_template_config_id),callback:function ($$v) {_vm.$set(_vm.form, "model_template_config_id", $$v)},expression:"form.model_template_config_id"}})],1):_vm._e(),(_vm.usertype == 1)?_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"模型小类"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择模型小类","clearable":"","filterable":""},model:{value:(_vm.form.template_small_id),callback:function ($$v) {_vm.$set(_vm.form, "template_small_id", $$v)},expression:"form.template_small_id"}},_vm._l((_vm.modelSmallOption),function(item){return _c('el-option',{key:item.id,attrs:{"label":item.template_small_name,"value":item.id}})}),1)],1):_vm._e()],1):_vm._e(),_c('el-form-item',{directives:[{name:"show",rawName:"v-show",value:(_vm.model_template_config_id_num == 5),expression:"model_template_config_id_num == 5"}],staticStyle:{"margin-top":"16px"},attrs:{"label":"扩增比例参数","prop":"amp"}},[_c('el-input-number',{staticStyle:{"width":"50%","float":"left"},attrs:{"controls-position":"right","min":1,"max":100},model:{value:(_vm.form.amp),callback:function ($$v) {_vm.$set(_vm.form, "amp", $$v)},expression:"form.amp"}})],1),_c('el-form-item',{directives:[{name:"show",rawName:"v-show",value:(_vm.model_template_config_id_num == 5),expression:"model_template_config_id_num == 5"}],staticStyle:{"margin-top":"16px"},attrs:{"label":"图像类型","prop":"alg_select_type"}},[_c('el-radio-group',{model:{value:(_vm.form.alg_select_type),callback:function ($$v) {_vm.$set(_vm.form, "alg_select_type", $$v)},expression:"form.alg_select_type"}},[_c('el-radio',{attrs:{"label":'1'}},[_vm._v("裁剪")]),_c('el-radio',{attrs:{"label":'2'}},[_vm._v("屏蔽")]),_c('el-radio',{attrs:{"label":'3'}},[_vm._v("原图")])],1)],1),(_vm.model_template_config_id_num == 5)?_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"级联解析类型","prop":"model_two_type"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择级联解析类型","size":"mini","clearable":"","filterable":""},model:{value:(_vm.form.model_two_type),callback:function ($$v) {_vm.$set(_vm.form, "model_two_type", $$v)},expression:"form.model_two_type"}},_vm._l((_vm.dict.algorithm_list_five),function(item){return _c('el-option',{key:'级联解析类型'+item.id,attrs:{"label":item.algorithm_name,"value":item.id}})}),1)],1):_vm._e(),_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"报警等级","prop":"res_type"}},[_c('el-select',{staticStyle:{"width":"50%"},attrs:{"placeholder":"请选择报警等级","size":"mini","clearable":"","filterable":""},on:{"change":_vm.markAlgorithmAlarmEdited},model:{value:(_vm.form.res_type),callback:function ($$v) {_vm.$set(_vm.form, "res_type", $$v)},expression:"form.res_type"}},_vm._l((_vm.alarmTypeDictOptions),function(item){return _c('el-option',{key:'报警等级'+item.value,attrs:{"label":item.label,"value":item.value}})}),1)],1),_c('el-form-item',{attrs:{"label":"算力资源","prop":"resource_id"}},[_c('el-cascader',{staticStyle:{"width":"50%"},attrs:{"options":_vm.computeOptions,"props":_vm.computeProps,"show-all-levels":false,"clearable":""},on:{"change":_vm.markAlgorithmResourceEdited},model:{value:(_vm.form.resource_id),callback:function ($$v) {_vm.$set(_vm.form, "resource_id", $$v)},expression:"form.resource_id"}})],1),(_vm.type_qy)?_c('div',{staticClass:"algorithm-drawing-scroll",staticStyle:{"width":"100%","height":"590px","border":"1px dashed #e5e5e5","background":"#f9fafb","border-radius":"10px"}},[_c('div',{staticStyle:{"width":"100%","height":"400px"}},[_c('div',{staticStyle:{"width":"120px","height":"30px","border":"2px solid #5b65eb","text-align":"center","color":"#5b65eb","background":"#ddefff","display":"flex","align-items":"center","justify-content":"center","font-size":"0.8vw","margin":"12px 0 0 12px","float":"left"}},[_vm._v("\n            绘制检测区域\n          ")]),_c('div',{staticStyle:{"width":"640px","height":"419px","float":"left","margin":"12px 0 0 12px"}},[_c('div',{directives:[{name:"loading",rawName:"v-loading",value:(_vm.loading),expression:"loading"}],staticClass:"Bcanvas"},[(!_vm.imgOpen)?_c('div',{staticClass:"jia_div"},[_vm._v(_vm._s(_vm.algorithmSnapshotHint))]):_vm._e(),(_vm.imgOpen)?_c('img',{staticStyle:{"width":"640px","height":"360px"},attrs:{"src":_vm.imgurl,"alt":""},on:{"load":function($event){_vm.loading = false}}}):_vm._e(),(_vm.isTypeTFS)?_c('canvas',{ref:"mycanvas",attrs:{"id":"mycanvas","tabindex":"0"}}):_vm._e(),(_vm.shield_status == 1||_vm.image_draw_type == 2)?_c('div',{staticClass:"jia_div"}):_vm._e()]),(_vm.isTypeTFS)?_c('div',{staticClass:"canvasBtn"},[_c('el-button',{attrs:{"type":"text","icon":"el-icon-refresh"},on:{"click":function($event){return _vm.handleimg(1)}}},[_vm._v("刷新")]),_c('el-button',{attrs:{"type":"text","icon":"el-icon-edit"},on:{"click":_vm.handleDrewAgain}},[_vm._v("重新绘制")]),_c('el-button',{attrs:{"type":"text","icon":"el-icon-refresh-left"},on:{"click":_vm.resole}},[_vm._v("撤销")])],1):_vm._e()])]),_c('div',{staticStyle:{"width":"100%","height":"180px"}},[_c('div',{staticStyle:{"width":"38%","height":"100%","float":"left","margin-left":"15%"}},[_c('el-form-item',{staticStyle:{"padding-top":"16px"},attrs:{"prop":"confidence"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                置信度\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"触发报警阈值，值越小越容易触发报警。取值范围：（1-100）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入置信度","maxlength":"4"},model:{value:(_vm.form.confidence),callback:function ($$v) {_vm.$set(_vm.form, "confidence", _vm._n($$v))},expression:"form.confidence"}})],1),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"prop":"sensitivity"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                间隔帧\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"视频流检测频率，如设置为25，1s检测一次。取值范围：（1-100）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"disabled":_vm.indexnum != 0,"placeholder":"请输入间隔帧","maxlength":"4"},model:{value:(_vm.form.sensitivity),callback:function ($$v) {_vm.$set(_vm.form, "sensitivity", _vm._n($$v))},expression:"form.sensitivity"}})],1):_vm._e()],1),(_vm.isTypeTFS)?_c('div',{staticStyle:{"width":"38%","height":"100%","float":"left"}},[_c('el-form-item',{staticStyle:{"padding-top":"16px"},attrs:{"prop":"duration_time"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                持续时长\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"需求行为的持续时长。取值范围：（1-100）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入持续时长","maxlength":"4"},model:{value:(_vm.form.duration_time),callback:function ($$v) {_vm.$set(_vm.form, "duration_time", _vm._n($$v))},expression:"form.duration_time"}},[_c('template',{slot:"append"},[_vm._v("秒")])],2)],1),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"prop":"interval_time"}},[_c('span',{staticStyle:{"display":"inline-block"},attrs:{"slot":"label"},slot:"label"},[_vm._v("\n                告警间隔\n                "),_c('el-tooltip',{attrs:{"effect":"dark","content":"当满足触发报警条件达到一定间隔时长以后才会上报。取值范围：（1-3600秒）","placement":"bottom"}},[_c('i',{staticClass:"el-icon-question"})])],1),_c('el-input',{staticStyle:{"width":"100%"},attrs:{"placeholder":"请输入告警间隔","maxlength":"4"},model:{value:(_vm.form.interval_time),callback:function ($$v) {_vm.$set(_vm.form, "interval_time", _vm._n($$v))},expression:"form.interval_time"}},[_c('template',{slot:"append"},[_vm._v("秒")])],2)],1):_vm._e(),(_vm.isTypeTFS)?_c('el-form-item',{attrs:{"label":"开始时间","prop":"defense_time_start"}},[_c('el-time-picker',{staticStyle:{"width":"100%"},attrs:{"disabled":_vm.indexnum != 0,"value-format":"HH:mm:ss","picker-options":{selectableRange: '00:00:00 - 23:59:59'},"placeholder":"任意时间点","default-value":new Date().setHours(0, 0, 0, 0)},model:{value:(_vm.form.defense_time_start),callback:function ($$v) {_vm.$set(_vm.form, "defense_time_start", $$v)},expression:"form.defense_time_start"}})],1):_vm._e(),_c('el-form-item',{attrs:{"label":"结束时间","prop":"defense_time_end"}},[_c('el-time-picker',{staticStyle:{"width":"100%"},attrs:{"disabled":_vm.indexnum != 0,"value-format":"HH:mm:ss","picker-options":{selectableRange: '00:00:00 - 23:59:59'},"placeholder":"任意时间点","default-value":new Date().setHours(0, 0, 0, 0)},model:{value:(_vm.form.defense_time_end),callback:function ($$v) {_vm.$set(_vm.form, "defense_time_end", $$v)},expression:"form.defense_time_end"}})],1)],1):_vm._e()])]):_vm._e(),_c('el-form-item',{staticStyle:{"margin-top":"16px"},attrs:{"label":"任务说明"}},[_c('el-input',{staticStyle:{"width":"50%","float":"left"},attrs:{"placeholder":"请输入备注","type":"textarea"},model:{value:(_vm.form.Algorithm_config_ps),callback:function ($$v) {_vm.$set(_vm.form, "Algorithm_config_ps", $$v)},expression:"form.Algorithm_config_ps"}})],1)],1)],1),_c('el-dialog',{attrs:{"title":_vm.title2,"id":"alarmTypeBox","visible":_vm.dialogVisible2,"width":"500px","close-on-click-modal":false},on:{"update:visible":function($event){_vm.dialogVisible2=$event},"close":_vm.handleClose2}},[_c('div',{staticClass:"radio-group-title"},[_vm._v("告警区域")]),_c('br'),_c('el-radio-group',{staticClass:"radio-grid",model:{value:(_vm.selectedOption),callback:function ($$v) {_vm.selectedOption=$$v},expression:"selectedOption"}},[_c('el-radio',{staticClass:"grid-item",attrs:{"label":'告警区域'}},[_vm._v("告警区域")])],1),_c('br'),_c('br'),_c('div',{staticClass:"radio-group-title"},[_vm._v("后处理区域")]),_c('br'),_c('el-radio-group',{staticClass:"radio-grid",model:{value:(_vm.selectedOption),callback:function ($$v) {_vm.selectedOption=$$v},expression:"selectedOption"}},[_c('el-radio',{staticClass:"grid-item",attrs:{"label":_vm.selectedOption_type}},[_vm._v(_vm._s(_vm.selectedOption_type))])],1),_c('span',{staticClass:"dialog-footer",attrs:{"slot":"footer"},slot:"footer"},[_c('el-button',{on:{"click":function($event){_vm.dialogVisible2 = false;_vm.handleDeleteList()}}},[_vm._v("取 消")]),_c('el-button',{attrs:{"type":"primary"},on:{"click":function($event){return _vm.handleUpdateList()}}},[_vm._v("确 定")])],1)],1)],1)};
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
          confidence: "60",
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
          confidence: "60",
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
          //   confidence: "60",
          //   tem_frames: "[27,37]",
          //   duration_time: 10,
          //   interval_time: 300,
          //   sensitivity: 25,
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
    sub_fn() {
      
      this.$refs['form'].validate(async (valid) => {
          if (valid) {
      // console.log(this.$refs.canvasRef);
      // this.$refs.canvasRef.setF()
      const refs = this.$refs.canvasRef || [];
      const children = this.jxlxlist.map((item, index) => refs.find((child) => Number(child.indexnum) === index));
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
        model_data: this.jxlxlist,
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
                this.goback()
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
                this.goback()
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
      this.form = obj
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
//# sourceMappingURL=chunk-415cc626.8db045a7.js.map
