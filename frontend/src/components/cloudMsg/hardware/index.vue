<!-- Restored from the server's original hardware/index.vue source map. -->
<template>
  <div class="data-table device-monitor">
    <div class="monitor-toolbar">
      <div class="monitor-toolbar-title">
        <strong>设备运行监测</strong>
        <span>主机资源与加速卡状态</span>
      </div>
      <div class="monitor-refresh-controls">
        <span>刷新间隔</span>
        <el-select v-model="intervalChoice" size="small" class="monitor-interval-select" aria-label="刷新间隔" @change="chooseInterval">
          <el-option v-for="seconds in intervalOptions" :key="seconds" :label="intervalText(seconds)" :value="seconds" />
          <el-option label="自定义" value="custom" />
        </el-select>
        <template v-if="intervalChoice === 'custom'">
          <input v-model.number="customSeconds" type="number" min="15" max="3600" step="1" class="monitor-custom-interval" aria-label="自定义刷新秒数">
          <span>秒</span>
          <el-button size="small" @click="applyCustomInterval">应用</el-button>
        </template>
        <el-button size="small" @click="togglePaused">{{ paused ? '继续自动刷新' : '暂停自动刷新' }}</el-button>
        <el-button type="primary" size="small" :loading="loading" :disabled="loading" @click="getTableData">刷新</el-button>
      </div>
    </div>
    <div class="monitor-refresh-status" aria-live="polite">
      <span>{{ loading ? '正在刷新…' : paused ? '自动刷新已暂停' : countdown + ' 秒后自动刷新' }}</span>
      <span v-if="lastRefreshAt">页面更新：{{ formatTime(lastRefreshAt) }}</span>
      <span v-else>尚未完成刷新</span>
    </div>
    <div v-if="intervalError" class="monitor-alert" role="status">{{ intervalError }}</div>
    <div v-if="lastError" class="monitor-alert" role="status">{{ lastError }}；保留上次成功获取的数据，可点击刷新重试。</div>
    <el-collapse v-if="tableData.length" v-model="activeNames" class="monitor-hosts">
      <el-collapse-item v-for="host in tableData" :key="host.key" :name="host.key">
        <template #title>
          <div class="monitor-host-header">
            <div class="monitor-host-identity">
              <strong>{{ host.computing_name || '未命名设备' }}</strong>
              <span>设备 IP：{{ host.computing_ip || '—' }}</span>
              <span :class="['monitor-host-status', { 'is-warning': hostWarning(host) }]">{{ hostStatusText(host) }}</span>
            </div>
            <div class="monitor-host-metric">
              <span class="monitor-metric-label">CPU占用比例 <small>主机</small></span>
              <strong>{{ percentText(host.cpu) }}</strong>
              <el-progress v-if="host.cpu !== null" :percentage="host.cpu" :show-text="false" :stroke-width="7" :color="metricColor(host.cpu)" />
              <span v-else class="monitor-missing">暂无采样</span>
            </div>
            <div class="monitor-host-metric">
              <span class="monitor-metric-label">内存占用比例 <small>主机</small></span>
              <strong>{{ percentText(host.memory) }}</strong>
              <el-progress v-if="host.memory !== null" :percentage="host.memory" :show-text="false" :stroke-width="7" :color="metricColor(host.memory)" />
              <span v-else class="monitor-missing">暂无采样</span>
            </div>
          </div>
        </template>
        <div class="monitor-host-details">
          <div class="monitor-collection-info">
            <span>主机采集时间：{{ formatTime(host.host_metrics_sampled_at) }}</span>
            <span v-if="host.host_metrics_attempted_at && host.host_metrics_status !== 'ok'">最近尝试：{{ formatTime(host.host_metrics_attempted_at) }}</span>
            <span v-if="hostStale(host)" class="monitor-stale">主机数据已过期</span>
          </div>
          <div v-if="host.host_metrics_error" class="monitor-host-error" role="status">{{ host.host_metrics_error }}</div>
          <div class="monitor-card-caption">
            <strong>加速卡</strong>
            <span>已存资源数据</span>
            <span>卡数据更新（最早）：{{ formatTime(host.card_data_updated_at) }}</span>
            <span v-if="host.card_timestamp_missing">部分卡暂无更新时间</span>
            <span v-if="cardStale(host)" class="monitor-stale">卡数据较旧</span>
          </div>
          <el-table :data="host.computing_arr" row-key="key" size="mini" border class="monitor-card-table" empty-text="暂无加速卡数据">
            <el-table-column label="芯片号" min-width="155" align="center">
              <template slot-scope="scope">
                <span :title="scope.row.device_name + '\n卡数据更新：' + formatTime(scope.row.card_data_updated_at)">{{ cardIdentity(scope.row) }}</span>
                <small v-if="cardStale(scope.row)" class="monitor-chip-stale">数据较旧</small>
              </template>
            </el-table-column>
            <el-table-column label="主板温度" min-width="100" align="center">
              <template slot-scope="scope">{{ temperatureText(scope.row.board_temp) }}</template>
            </el-table-column>
            <el-table-column label="芯片温度" min-width="100" align="center">
              <template slot-scope="scope">{{ temperatureText(scope.row.chip_temp) }}</template>
            </el-table-column>
            <el-table-column label="加速卡内存占用比例" min-width="175" align="center">
              <template slot-scope="scope">
                <div class="monitor-card-metric">
                  <strong>{{ percentText(scope.row.memory_usage_rate) }}</strong>
                  <el-progress v-if="scope.row.memory_usage_rate !== null" :percentage="scope.row.memory_usage_rate" :show-text="false" :stroke-width="6" :color="metricColor(scope.row.memory_usage_rate)" />
                </div>
              </template>
            </el-table-column>
            <el-table-column label="算法任务运行数量" min-width="150" align="center">
              <template slot-scope="scope">{{ countText(scope.row.resource_num) }}</template>
            </el-table-column>
            <el-table-column label="TPU/NPU利用率" min-width="150" align="center">
              <template slot-scope="scope">
                <div class="monitor-card-metric">
                  <strong>{{ percentText(scope.row.tpu_util) }}</strong>
                  <el-progress v-if="scope.row.tpu_util !== null" :percentage="scope.row.tpu_util" :show-text="false" :stroke-width="6" :color="metricColor(scope.row.tpu_util)" />
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-collapse-item>
    </el-collapse>
    <div v-else class="monitor-empty">{{ loading ? '正在加载设备…' : '暂无设备监测数据' }}</div>
  </div>
</template>

<script>
import { compute } from "../../../api/sfgl";

export default {
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
</script>

<style scoped>
.device-monitor { width: 100%; height: 100%; overflow: auto; padding: 14px; box-sizing: border-box; border-radius: 6px; background: #f5f7fb; color: #303133; }
.device-monitor * { box-sizing: border-box; }
.device-monitor .monitor-toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 16px; background: #fff; border: 1px solid #e4e9f1; border-radius: 6px; }
.device-monitor .monitor-toolbar-title { display: flex; flex-direction: column; gap: 4px; }
.device-monitor .monitor-toolbar-title strong { font-size: 15px; color: #232e66; }
.device-monitor .monitor-toolbar-title span { color: #8691a3; font-size: 12px; }
.device-monitor .monitor-refresh-controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 12px; }
.device-monitor .monitor-refresh-controls .el-button { margin-left: 0; }
.device-monitor .monitor-interval-select { width: 108px; }
.device-monitor .monitor-custom-interval { width: 82px; height: 32px; padding: 4px 8px; border: 1px solid #dcdfe6; border-radius: 4px; }
.device-monitor .monitor-refresh-status { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px; padding: 10px 2px; font-size: 12px; color: #7b8799; }
.device-monitor .monitor-alert { margin-bottom: 10px; padding: 9px 12px; border: 1px solid #ffe3ad; border-radius: 5px; background: #fff8e8; color: #8a5c0c; font-size: 12px; }
.device-monitor .monitor-hosts { border: 0; }
.device-monitor .el-collapse-item { margin-bottom: 14px; border: 1px solid #e1e7f0; border-radius: 6px; overflow: hidden; background: #fff; }
.device-monitor .el-collapse-item__header { height: auto; min-height: 120px; padding: 16px; line-height: 1.5; border-bottom-color: #edf0f5; }
.device-monitor .el-collapse-item__content { padding-bottom: 0; }
.device-monitor .el-collapse-item__wrap { border-bottom: 0; }
.device-monitor .monitor-host-header { flex: 1; min-width: 0; display: grid; grid-template-columns: minmax(190px,1.2fr) repeat(2,minmax(140px,1fr)); align-items: center; gap: 26px; padding-right: 18px; }
.device-monitor .monitor-host-identity { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; min-width: 0; }
.device-monitor .monitor-host-identity strong { font-size: 16px; color: #232e66; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.device-monitor .monitor-host-identity span { font-size: 12px; color: #7b8799; }
.device-monitor .monitor-host-identity .monitor-host-status { display: inline-block; padding: 1px 7px; color: #26805f; background: #eaf8f1; border-radius: 3px; }
.device-monitor .monitor-host-identity .monitor-host-status.is-warning { color: #9b6b24; background: #fff3df; }
.device-monitor .monitor-host-metric { display: flex; flex-direction: column; gap: 7px; min-width: 0; }
.device-monitor .monitor-metric-label { color: #65728a; font-size: 13px; }
.device-monitor .monitor-metric-label small { margin-left: 5px; color: #9ba5b4; font-size: 11px; }
.device-monitor .monitor-host-metric strong { font-size: 26px; line-height: 1.2; color: #0569ff; font-weight: 600; }
.device-monitor .monitor-missing { min-height: 7px; color: #a2abba; font-size: 11px; }
.device-monitor .monitor-host-details { padding: 0 16px 16px; }
.device-monitor .monitor-collection-info { display: flex; flex-wrap: wrap; gap: 8px 20px; padding: 10px 0; color: #8994a5; font-size: 12px; }
.device-monitor .monitor-host-error { padding-bottom: 8px; color: #b67936; font-size: 12px; }
.device-monitor .monitor-card-caption { display: flex; flex-wrap: wrap; gap: 7px 14px; align-items: center; padding: 5px 0 10px; font-size: 12px; color: #8994a5; }
.device-monitor .monitor-card-caption strong { color: #53617c; font-size: 13px; }
.device-monitor .monitor-stale { color: #c5893e; }
.device-monitor .monitor-chip-stale { display: block; margin-top: 3px; color: #c5893e; font-size: 10px; }
.device-monitor .monitor-card-table .el-table__header th { background: #f5f8ff; color: #53617c; }
.device-monitor .monitor-card-table .el-table__cell { padding: 12px 0; }
.device-monitor .monitor-card-metric { display: flex; flex-direction: column; gap: 5px; max-width: 180px; margin: 0 auto; }
.device-monitor .monitor-card-metric strong { font-size: 13px; color: #53617c; }
.device-monitor .monitor-empty { padding: 50px 20px; border: 1px solid #e1e7f0; border-radius: 6px; background: #fff; color: #8994a5; text-align: center; }
@media (max-width: 1000px) { .device-monitor .monitor-host-header { gap: 18px; grid-template-columns: minmax(165px,1fr) repeat(2,minmax(115px,1fr)); } .device-monitor .monitor-host-metric strong { font-size: 23px; } }
@media (max-width: 700px) { .device-monitor { padding: 8px; } .device-monitor .monitor-host-header { grid-template-columns: repeat(2,minmax(100px,1fr)); gap: 14px; } .device-monitor .monitor-host-identity { grid-column: 1 / -1; } .device-monitor .el-collapse-item__header { padding: 12px; } .device-monitor .monitor-host-details { padding: 0 10px 10px; } }
</style>
