(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["chunk-640b8cf2"],{"2f7e":function(e,t,a){},5750:function(e,t,a){},"7bc5":function(e,t,a){},"856c":function(e,t,a){"use strict";a("2f7e")},"8f15":function(e,t,a){"use strict";a.d(t,"b",(function(){return r})),a.d(t,"d",(function(){return i})),a.d(t,"e",(function(){return n})),a.d(t,"a",(function(){return o})),a.d(t,"c",(function(){return l})),a.d(t,"f",(function(){return s}));const r=window.wgParameter.url_5000+"/resource_view/resource_data",i=window.wgParameter.url_5000+"/model_view/config_name_check",n=window.wgParameter.url_5000+"/resource_view/computing_show",o=window.wgParameter.url_5000+"/resource_view/computing_insert",l=window.wgParameter.url_5000+"/resource_view/computing_delete",s=window.wgParameter.url_5000+"/resource_view/computing_update"},dc64:function(e,t,a){},dccc:function(e,t,a){"use strict";a("dc64")},dfde:function(e,t,a){"use strict";a("5750")},e5c5:function(e,t,a){
"use strict";
a.r(t);a("fad2");
var compute=a("8f15")["b"];



var Component = {
  name: 'DeviceMonitor',
  data() {
    return {
      activeNames: [], tableData: [], loading: false, lastError: '', lastRefreshAt: null,
      refreshSeconds: 60, intervalChoice: 60, customSeconds: 60,
      intervalOptions: [15, 30, 60, 120, 300], intervalError: '',
      paused: false, countdown: 60, nowMs: Date.now(), nextRefreshAt: null, hasLoaded: false,
    };
  },
  created() {
    this._monitorClosed = false;
    this._monitorRequestGeneration = 0;
    this._monitorController = null;
    this._monitorTicker = null;
    this.restoreRefreshSettings();
  },
  mounted() {
    this._monitorTicker = setInterval(this.tick, 1000);
    this.getTableData();
  },
  beforeDestroy() {
    this._monitorClosed = true;
    this._monitorRequestGeneration++;
    clearInterval(this._monitorTicker);
    this._monitorTicker = null;
    if (this._monitorController) this._monitorController.abort();
    this._monitorController = null;
  },
  methods: {
    percentValue(value) {
      if (value === null || value === undefined || value === '') return null;
      var text = String(value).trim();
      if (!/^\d+(?:\.\d+)?\s*%?$/.test(text)) return null;
      var number = Number(text.replace('%', '').trim());
      return Number.isFinite(number) && number >= 0 && number <= 100 ? number : null;
    },
    percentText(value) { return value === null ? '—' : value.toFixed(1) + '%'; },
    temperatureText(value) {
      if (value === null || value === undefined || value === '') return '—';
      var text = String(value).trim().replace(/(?:℃|°C)\s*$/i, '');
      if (!/^[+-]?\d+(?:\.\d+)?$/.test(text)) return '—';
      var number = Number(text);
      return Number.isFinite(number) ? number.toFixed(1) + '℃' : '—';
    },
    countText(value) {
      if (value === null || value === undefined || value === '') return '—';
      var number = Number(value);
      return Number.isSafeInteger(number) && number >= 0 ? number : '—';
    },
    cardIdentity(card) {
      return [card.model || card.device_name, card.dev_id === null || card.dev_id === undefined || card.dev_id === '' ? '' : '卡 ' + card.dev_id].filter(Boolean).join(' · ');
    },
    metricColor(value) { return value >= 90 ? '#e77755' : value >= 75 ? '#e6a23c' : '#0569ff'; },
    formatTime(value) {
      if (value === null || value === undefined || value === '') return '—';
      var time = new Date(value);
      return Number.isFinite(time.getTime()) ? time.toLocaleString('zh-CN', { hour12: false }) : '—';
    },
    timestamp(value) {
      if (value === null || value === undefined || value === '') return null;
      var time = new Date(value).getTime();
      return Number.isFinite(time) ? time : null;
    },
    hostStale(host) {
      var time = this.timestamp(host.host_metrics_sampled_at);
      var serverNow = this.nowMs - (Number.isFinite(host.serverClockOffsetMs) ? host.serverClockOffsetMs : 0);
      return time !== null && serverNow - time > Math.max(120000, this.refreshSeconds * 2000);
    },
    cardStale(host) {
      var time = this.timestamp(host.card_data_updated_at);
      var serverNow = this.nowMs - (Number.isFinite(host.serverClockOffsetMs) ? host.serverClockOffsetMs : 0);
      return time !== null && serverNow - time > Math.max(120000, this.refreshSeconds * 2000);
    },
    hostWarning(host) {
      return this.hostStale(host) || host.host_metrics_status === 'error' || host.host_metrics_status === 'partial';
    },
    hostStatusText(host) {
      if (this.hostStale(host)) return '数据已过期';
      return { ok: '采集正常', partial: '部分采集失败', error: '采集失败', collecting: '正在采集' }[host.host_metrics_status] || '尚无采样';
    },
    intervalText(seconds) { return seconds < 60 ? seconds + ' 秒' : seconds % 60 === 0 ? seconds / 60 + ' 分钟' : seconds + ' 秒'; },
    scheduleNextRefresh() {
      this.nowMs = Date.now();
      this.nextRefreshAt = this.paused ? null : this.nowMs + this.refreshSeconds * 1000;
      this.countdown = this.paused ? 0 : this.refreshSeconds;
    },
    tick() {
      if (this._monitorClosed) return;
      this.nowMs = Date.now();
      if (this.paused || this.loading || this.nextRefreshAt === null) return;
      this.countdown = Math.max(0, Math.ceil((this.nextRefreshAt - this.nowMs) / 1000));
      if (this.countdown === 0) this.getTableData();
    },
    chooseInterval(value) {
      this.intervalError = '';
      if (value === 'custom') { this.customSeconds = this.refreshSeconds; return; }
      this.setIntervalSeconds(value);
    },
    applyCustomInterval() { this.setIntervalSeconds(this.customSeconds); },
    restoreRefreshSettings() {
      try {
        var saved = JSON.parse(window.localStorage.getItem('ai-monitor.device-monitor-refresh') || 'null');
        if (!saved || !Number.isSafeInteger(saved.seconds) || saved.seconds < 15 || saved.seconds > 3600) return;
        this.refreshSeconds = saved.seconds;
        this.customSeconds = saved.seconds;
        this.intervalChoice = this.intervalOptions.indexOf(saved.seconds) >= 0 ? saved.seconds : 'custom';
        this.countdown = saved.seconds;
      } catch (error) { /* Storage may be unavailable in private browsing. */ }
    },
    saveRefreshSettings() {
      try { window.localStorage.setItem('ai-monitor.device-monitor-refresh', JSON.stringify({ seconds: this.refreshSeconds })); }
      catch (error) { /* A storage failure must not stop monitoring. */ }
    },
    setIntervalSeconds(value) {
      var seconds = Number(value);
      if (!Number.isSafeInteger(seconds) || seconds < 15 || seconds > 3600) {
        this.intervalError = '刷新间隔请输入 15–3600 秒的整数'; return false;
      }
      this.refreshSeconds = seconds;
      this.intervalError = '';
      this.scheduleNextRefresh();
      this.saveRefreshSettings();
      return true;
    },
    togglePaused() { this.paused = !this.paused; this.scheduleNextRefresh(); },
    normalizeResources(data) {
      var vm = this, hosts = new Map(), receivedAt = Date.now();
      data.forEach(function (item) {
        var serverTime = vm.timestamp(item.host_metrics_server_time);
        var serverClockOffsetMs = serverTime === null ? null : receivedAt - serverTime;
        var key = 'host-' + String(item.computing_id == null ? (item.computing_ip || item.computing_name || 'unknown') : item.computing_id);
        var cards = [], cardKeys = new Set();
        Object.entries(item.grouped_resources || {}).forEach(function (entry) {
          var chipName = entry[0], rows = Array.isArray(entry[1]) ? entry[1] : [];
          rows.forEach(function (card, index) {
            var cardKey = key + '-card-' + String(card.id == null ? chipName + '-' + (card.dev_id == null ? index : card.dev_id) : card.id);
            if (cardKeys.has(cardKey)) return;
            cardKeys.add(cardKey);
            cards.push({ key: cardKey, device_name: chipName, model: card.dev_get_target || '', dev_id: card.dev_id,
              board_temp: card.board_temp, chip_temp: card.chip_temp,
              memory_usage_rate: vm.percentValue(card.memory_usage_rate), resource_num: card.resource_num,
              tpu_util: vm.percentValue(card.tpu_util), card_data_updated_at: card.card_data_updated_at,
              serverClockOffsetMs: serverClockOffsetMs });
          });
        });
        var timestamps = cards.map(function (card) { return vm.timestamp(card.card_data_updated_at); }).filter(function (time) { return time !== null; });
        hosts.set(key, { key: key, computing_id: item.computing_id, computing_name: item.computing_name,
          computing_ip: item.computing_ip, computing_arr: cards,
          cpu: vm.percentValue(item.cpu_usage), memory: vm.percentValue(item.host_mem_usage),
          host_metrics_sampled_at: item.host_metrics_sampled_at, host_metrics_attempted_at: item.host_metrics_attempted_at,
          host_metrics_status: item.host_metrics_status, host_metrics_error: item.host_metrics_error || '',
          host_metrics_server_time: item.host_metrics_server_time, serverClockOffsetMs: serverClockOffsetMs,
          card_data_updated_at: timestamps.length ? new Date(Math.min.apply(Math, timestamps)).toISOString() : null,
          card_timestamp_missing: timestamps.length < cards.length });
      });
      return Array.from(hosts.values());
    },
    async getTableData() {
      if (this.loading || this._monitorClosed) return false;
      this.loading = true;
      var generation = ++this._monitorRequestGeneration;
      var controller = new AbortController();
      this._monitorController = controller;
      try {
        var response = await this.$http.get(compute, { signal: controller.signal, timeout: 45000 });
        if (this._monitorClosed || generation !== this._monitorRequestGeneration) return false;
        var result = response.data || {};
        if (result.code !== undefined && Number(result.code) !== 200) throw new Error(result.msg || '读取设备状态失败');
        if (!Array.isArray(result.data)) throw new Error('设备状态数据格式异常');
        var hosts = this.normalizeResources(result.data), hostKeys = new Set(hosts.map(function (host) { return host.key; }));
        this.activeNames = this.hasLoaded ? this.activeNames.filter(function (key) { return hostKeys.has(key); }) : Array.from(hostKeys);
        this.tableData = hosts;
        this.hasLoaded = true;
        this.lastRefreshAt = Date.now();
        this.lastError = '';
        return true;
      } catch (error) {
        if (!this._monitorClosed && generation === this._monitorRequestGeneration) {
          this.lastError = '刷新失败：' + (error.message || '请检查平台连接');
        }
        return false;
      } finally {
        if (!this._monitorClosed && generation === this._monitorRequestGeneration) {
          this.loading = false;
          if (this._monitorController === controller) this._monitorController = null;
          this.scheduleNextRefresh();
        }
      }
    },
  },
};

var render = function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"data-table device-monitor"},[_c('div',{staticClass:"monitor-toolbar"},[_vm._m(0),_c('div',{staticClass:"monitor-refresh-controls"},[_c('span',[_vm._v("刷新间隔")]),_c('el-select',{staticClass:"monitor-interval-select",attrs:{"size":"small","aria-label":"刷新间隔"},on:{"change":_vm.chooseInterval},model:{value:(_vm.intervalChoice),callback:function ($$v) {_vm.intervalChoice=$$v},expression:"intervalChoice"}},[_vm._l((_vm.intervalOptions),function(seconds){return _c('el-option',{key:seconds,attrs:{"label":_vm.intervalText(seconds),"value":seconds}})}),_c('el-option',{attrs:{"label":"自定义","value":"custom"}})],2),(_vm.intervalChoice === 'custom')?[_c('input',{directives:[{name:"model",rawName:"v-model.number",value:(_vm.customSeconds),expression:"customSeconds",modifiers:{"number":true}}],staticClass:"monitor-custom-interval",attrs:{"type":"number","min":"15","max":"3600","step":"1","aria-label":"自定义刷新秒数"},domProps:{"value":(_vm.customSeconds)},on:{"input":function($event){if($event.target.composing){ return; }_vm.customSeconds=_vm._n($event.target.value)},"blur":function($event){return _vm.$forceUpdate()}}}),_c('span',[_vm._v("秒")]),_c('el-button',{attrs:{"size":"small"},on:{"click":_vm.applyCustomInterval}},[_vm._v("应用")])]:_vm._e(),_c('el-button',{attrs:{"size":"small"},on:{"click":_vm.togglePaused}},[_vm._v(_vm._s(_vm.paused ? '继续自动刷新' : '暂停自动刷新'))]),_c('el-button',{attrs:{"type":"primary","size":"small","loading":_vm.loading,"disabled":_vm.loading},on:{"click":_vm.getTableData}},[_vm._v("刷新")])],2)]),_c('div',{staticClass:"monitor-refresh-status",attrs:{"aria-live":"polite"}},[_c('span',[_vm._v(_vm._s(_vm.loading ? '正在刷新…' : _vm.paused ? '自动刷新已暂停' : _vm.countdown + ' 秒后自动刷新'))]),(_vm.lastRefreshAt)?_c('span',[_vm._v("页面更新："+_vm._s(_vm.formatTime(_vm.lastRefreshAt)))]):_c('span',[_vm._v("尚未完成刷新")])]),(_vm.intervalError)?_c('div',{staticClass:"monitor-alert",attrs:{"role":"status"}},[_vm._v(_vm._s(_vm.intervalError))]):_vm._e(),(_vm.lastError)?_c('div',{staticClass:"monitor-alert",attrs:{"role":"status"}},[_vm._v(_vm._s(_vm.lastError)+"；保留上次成功获取的数据，可点击刷新重试。")]):_vm._e(),(_vm.tableData.length)?_c('el-collapse',{staticClass:"monitor-hosts",model:{value:(_vm.activeNames),callback:function ($$v) {_vm.activeNames=$$v},expression:"activeNames"}},_vm._l((_vm.tableData),function(host){return _c('el-collapse-item',{key:host.key,attrs:{"name":host.key},scopedSlots:_vm._u([{key:"title",fn:function(){return [_c('div',{staticClass:"monitor-host-header"},[_c('div',{staticClass:"monitor-host-identity"},[_c('strong',[_vm._v(_vm._s(host.computing_name || '未命名设备'))]),_c('span',[_vm._v("设备 IP："+_vm._s(host.computing_ip || '—'))]),_c('span',{class:['monitor-host-status', { 'is-warning': _vm.hostWarning(host) }]},[_vm._v(_vm._s(_vm.hostStatusText(host)))])]),_c('div',{staticClass:"monitor-host-metric"},[_c('span',{staticClass:"monitor-metric-label"},[_vm._v("CPU占用比例 "),_c('small',[_vm._v("主机")])]),_c('strong',[_vm._v(_vm._s(_vm.percentText(host.cpu)))]),(host.cpu !== null)?_c('el-progress',{attrs:{"percentage":host.cpu,"show-text":false,"stroke-width":7,"color":_vm.metricColor(host.cpu)}}):_c('span',{staticClass:"monitor-missing"},[_vm._v("暂无采样")])],1),_c('div',{staticClass:"monitor-host-metric"},[_c('span',{staticClass:"monitor-metric-label"},[_vm._v("内存占用比例 "),_c('small',[_vm._v("主机")])]),_c('strong',[_vm._v(_vm._s(_vm.percentText(host.memory)))]),(host.memory !== null)?_c('el-progress',{attrs:{"percentage":host.memory,"show-text":false,"stroke-width":7,"color":_vm.metricColor(host.memory)}}):_c('span',{staticClass:"monitor-missing"},[_vm._v("暂无采样")])],1)])]},proxy:true}],null,true)},[_c('div',{staticClass:"monitor-host-details"},[_c('div',{staticClass:"monitor-collection-info"},[_c('span',[_vm._v("主机采集时间："+_vm._s(_vm.formatTime(host.host_metrics_sampled_at)))]),(host.host_metrics_attempted_at && host.host_metrics_status !== 'ok')?_c('span',[_vm._v("最近尝试："+_vm._s(_vm.formatTime(host.host_metrics_attempted_at)))]):_vm._e(),(_vm.hostStale(host))?_c('span',{staticClass:"monitor-stale"},[_vm._v("主机数据已过期")]):_vm._e()]),(host.host_metrics_error)?_c('div',{staticClass:"monitor-host-error",attrs:{"role":"status"}},[_vm._v(_vm._s(host.host_metrics_error))]):_vm._e(),_c('div',{staticClass:"monitor-card-caption"},[_c('strong',[_vm._v("加速卡")]),_c('span',[_vm._v("已存资源数据")]),_c('span',[_vm._v("卡数据更新（最早）："+_vm._s(_vm.formatTime(host.card_data_updated_at)))]),(host.card_timestamp_missing)?_c('span',[_vm._v("部分卡暂无更新时间")]):_vm._e(),(_vm.cardStale(host))?_c('span',{staticClass:"monitor-stale"},[_vm._v("卡数据较旧")]):_vm._e()]),_c('el-table',{staticClass:"monitor-card-table",attrs:{"data":host.computing_arr,"row-key":"key","size":"mini","border":"","empty-text":"暂无加速卡数据"}},[_c('el-table-column',{attrs:{"label":"芯片号","min-width":"155","align":"center"},scopedSlots:_vm._u([{key:"default",fn:function(scope){return [_c('span',{attrs:{"title":scope.row.device_name + '\n卡数据更新：' + _vm.formatTime(scope.row.card_data_updated_at)}},[_vm._v(_vm._s(_vm.cardIdentity(scope.row)))]),(_vm.cardStale(scope.row))?_c('small',{staticClass:"monitor-chip-stale"},[_vm._v("数据较旧")]):_vm._e()]}}],null,true)}),_c('el-table-column',{attrs:{"label":"主板温度","min-width":"100","align":"center"},scopedSlots:_vm._u([{key:"default",fn:function(scope){return [_vm._v(_vm._s(_vm.temperatureText(scope.row.board_temp)))]}}],null,true)}),_c('el-table-column',{attrs:{"label":"芯片温度","min-width":"100","align":"center"},scopedSlots:_vm._u([{key:"default",fn:function(scope){return [_vm._v(_vm._s(_vm.temperatureText(scope.row.chip_temp)))]}}],null,true)}),_c('el-table-column',{attrs:{"label":"加速卡内存占用比例","min-width":"175","align":"center"},scopedSlots:_vm._u([{key:"default",fn:function(scope){return [_c('div',{staticClass:"monitor-card-metric"},[_c('strong',[_vm._v(_vm._s(_vm.percentText(scope.row.memory_usage_rate)))]),(scope.row.memory_usage_rate !== null)?_c('el-progress',{attrs:{"percentage":scope.row.memory_usage_rate,"show-text":false,"stroke-width":6,"color":_vm.metricColor(scope.row.memory_usage_rate)}}):_vm._e()],1)]}}],null,true)}),_c('el-table-column',{attrs:{"label":"算法任务运行数量","min-width":"150","align":"center"},scopedSlots:_vm._u([{key:"default",fn:function(scope){return [_vm._v(_vm._s(_vm.countText(scope.row.resource_num)))]}}],null,true)}),_c('el-table-column',{attrs:{"label":"TPU/NPU利用率","min-width":"150","align":"center"},scopedSlots:_vm._u([{key:"default",fn:function(scope){return [_c('div',{staticClass:"monitor-card-metric"},[_c('strong',[_vm._v(_vm._s(_vm.percentText(scope.row.tpu_util)))]),(scope.row.tpu_util !== null)?_c('el-progress',{attrs:{"percentage":scope.row.tpu_util,"show-text":false,"stroke-width":6,"color":_vm.metricColor(scope.row.tpu_util)}}):_vm._e()],1)]}}],null,true)})],1)],1)])}),1):_c('div',{staticClass:"monitor-empty"},[_vm._v(_vm._s(_vm.loading ? '正在加载设备…' : '暂无设备监测数据'))])],1)};
var staticRenderFns = [function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"monitor-toolbar-title"},[_c('strong',[_vm._v("设备运行监测")]),_c('span',[_vm._v("主机资源与加速卡状态")])])}];
Component.render=render;Component.staticRenderFns=staticRenderFns;Component._compiled=true;Component._scopeId="data-v-13321630";Component.__file="src/components/cloudMsg/hardware/index.vue";
t["default"]=Component;
},fad2:function(e,t,a){"use strict";a("7bc5")}}]);
//# sourceMappingURL=chunk-640b8cf2.e0f6ad65.js.map
