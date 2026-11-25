/* algorithm-runtime-list-v1 */
/* algorithm-model-identity-v1 */

var algorithmFirstEditorIdentity = window.AiMonitorAlgorithmIdentity || (window.AiMonitorAlgorithmIdentity = (function () {
  function meaningful(value) {
    var text = value == null ? '' : String(value).trim();
    return /^(?:0+|null|undefined|None)$/i.test(text) ? '' : text;
  }
  function name(row) {
    if (!row) return '';
    var raw = meaningful(row.algorithm_name || row.name), parts = raw.split('_');
    var packageName = parts.length >= 8 && parts.some(function (part) { return /^V\d/i.test(part); }) ? (parts.slice(1, 4).join('_') === '人数统计_全身_数量统计类' ? '人数统计_全身' : parts[1]) : '';
    return meaningful(row.display_name) || meaningful(row.analysis_type) || packageName || meaningful(row.model_name) || raw;
  }
  function label(row) {
    var version = meaningful(row && (row.algorithm_version || row.version));
    return name(row) + (version ? ' · 版本 ' + version : '');
  }
  function count(vm) {
    var form = vm.form || {}, libraries = vm.dict && vm.dict.algorithm_list;
    var selected = Array.isArray(libraries) && libraries.find(function (row) { return String(row.id) === String(form.Algorithm_library_id); });
    // Display identity and implementation template are independent. Variants
    // retain the person-count geometry without changing their library or labels.
    var values = selected ? [selected.model_name, selected.analysis_type, selected.display_name, selected.algorithm_name] :
      [vm.nameif, form.model_name, form.analysis_type, form.display_name, form.algorithm_name];
    return values.some(function (value) { return typeof value === 'string' && /人数统计|人员计数/.test(value); });
  }
  return {name: name, label: label, count: count};
})());

/* algorithm-first-entry-v1 */
/* native-template-administrator-v1 */
(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["chunk-32a3ec07"],{"13d5":function(e,t,i){"use strict";var a=i("23e7"),l=i("d58f").left,s=i("a640"),o=i("2d00"),r=i("605d"),n=!r&&o>79&&o<83,m=n||!s("reduce");a({target:"Array",proto:!0,forced:m},{reduce:function(e){var t=arguments.length;return l(this,e,t,t>1?arguments[1]:void 0)}})},"269f":function(e,t){e.exports="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAOCAYAAAAfSC3RAAAAAXNSR0IArs4c6QAAAjBJREFUOE9tks1rU0EUxc+9kxdeqqSKQhdBY1REorgqiN3YLFqoG6UgwmtNDVnkD3AnCMGlG1ddlCxCbHiLiCClqy7Ej01VFKwfRSgtKC1ClYpG0857M9cOWGgls7sz5zfn3LlD+G81Go1DSqmr1tpTRBSLyEdjzKNSqfRjt5R2F61WK6m1HjTGnGfmGXdmrR1RSj3PZDIvCoVCvKPfA9br9QOJROKatXZ1ZWVlLp/PY2trawhAWms9Wy6Xf3UFJycn96fT6UvW2hQzz2mtKZlMFkRko9PpPKlUKn+6giJCYRietNbeBLAoboPoODPfGxsb+wxAuoLVapVzuVw/M18WkQ9OxMxniagVBMFbIuoO1mq1vmQyWSSil77vv9Zas4gMAMgrpe4HQfBtj6NzymazaaXUADOfMMaEExMT353IXeb7/nVjzEIikZhfWlpqV6tVS1NTU72pVOo0M58RkXMA6uPj4ws7sVybzWbzAhEFAN4AeAfgE01PTxe3xVkAvwEctdbObm5uPq1UKpFz/DfbYWvtEBEtA9gnIssOvCMiLaXUahzHx4joCoDHzLwexzExcx8RDRLRgyiKvnied0RERh14O47jWqlU+tpoNDLMfAvAOoANF5OZD4pIr9b6brlcXgvD8LAx5oYDqwDmmXlxO2a/iLi4M9bany5qT09POoqiERFZ8zzvVbvdFt/3c67xYRG5CEAB6IjIw2Kx+H73H242m3lr7SgATynlHujZX3CbFEHQqXHzAAAAAElFTkSuQmCC"},"5ba6":function(e,t){e.exports="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA4AAAAPCAYAAADUFP50AAAAAXNSR0IArs4c6QAAAmBJREFUOE9dkztolFEQhc+Z+++SxSIR0YASxSeKD5A02qgIgiII2qgQNMFiwcbaRn8IKIKFglqa7G4gshZiIfho4gPExkpW8ZGoGB9BVy3W3WTvP2NGgojT3dd8c2bOJf6LUqm0gOQRkmvNzE9fNJvNSrFY/PrvVfoiTVPp7e3tqNfrhRDCHgAb2+32aJIkRvIggFqj0bhdKBSa4+PjzTRNldVqtXN6eno9gGUAlgDYQfJmlmV3siyzEMIukvtJ3if50czexhhrHBkZOZ5l2XLfFJFVZrYCwBSAjrnSWgAWAJgwszckFwN4z0qlcsXMrorI59nDo2bm9B8i8kVVYWZexTwAz2aTlkWkG8AxJ14kebHdbru+wbnMQyLy3okxxp4QQr9XkiTJqRjjL5InWC6XT5KMZuYa14QQzqpqoqq1Vqv1PZfLOW11Lpc7DeAlgHcA8iyVSntEZJBkTVW/mdkXkrtJ3ogxPgkhbBURT7wSQBcAl5I68RiAnQByTgZQJbkpxjimqs/z+fzCLMu6QwhFM/PxtVV1zDWejzGOhhB6AJxQ1crMzMzdycnJz2maxqGhoa4kSfaR7FfVS2Y2EUI45F29HGO8ICJ1kq53jZk9MrOHIkIz205yC4DXqnpGROY7wInnAHwA8FRVt3mDAASf11xpn0jOmNkrVX0QQtgMYKlrXAfA3eHzWQRgg5ndEpHHquqWc9pet50bQ1WnQgj3/njVbddoNApJknQCOGxmP2aNcD2fz1uM8cCcc67FGH8CaA0MDPz88/DfGB4eXu8D946SVP8lJMt9fX1O/Bu/AXk8OrGkwhHgAAAAAElFTkSuQmCC"},"605d":function(e,t,i){"use strict";var a=i("da84"),l=i("c6b6");e.exports="process"===l(a.process)},"6e4f":function(e,t,i){"use strict";i("9506")},9506:function(e,t,i){},9542:function(e,t,i){"use strict";
// Background reads update only runtime fields on existing rows.
function algorithmRuntimeLabel(row) {
  if (row.runtime_state === 'health_unknown') return '状态待确认';
  if (row.runtime_state === 'output_unknown') return '推流待确认';
  if (row.runtime_state === 'recovering') return '恢复中';
  if (row.runtime_state === 'dispatch_pending') return '等待调度';
  var reason = row.runtime_reason || '';
  if (reason.includes('加载模型')) return '加载模型';
  if (reason.includes('连接视频源')) return '连接视频源';
  if (/视频输出|分析输出|视频编码|输出视频/.test(reason)) return '等待视频输出';
  if (reason.includes('有效推理结果')) return '等待推理';
  if (reason.includes('确认持续稳定')) return '确认运行';
  return reason ? '启动中' : '等待调度';
}
var algorithmRuntimeHealthMixin={
  data() {
    return { algorithmRuntimeHealthUpdatedAt: '', algorithmRuntimeHealthError: '' };
  },
  created() {
    this._algorithmRuntimeMounted = false;
    this._algorithmRuntimeDenied = false;
    this._algorithmRuntimeGeneration = 0;
    this._algorithmRuntimeController = null;
    this._algorithmListController = null;
    this._algorithmSearchTimer = null;
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
      if (!this.algorithmRuntimePageActive() || this._algorithmRuntimeDenied || !this.tableData.length) return;
      const pending = this.tableData.some(row => (row.status === '停止' && String(row.model_status) !== '4')
        || (row.status === '运行' && String(row.model_status) === '2'));
      this.statusRefreshTimer = setTimeout(() => {
        this.statusRefreshTimer = null;
        if (this.batchStatusBusy || Object.keys(this.statusPending || {}).length) return this.scheduleAlgorithmRuntimeRefresh();
        return this.refreshAlgorithmRuntimeStates();
      }, pending ? 1500 : 10000);
    },
    refreshAlgorithmRuntimeStates() {
      if (!this.algorithmRuntimePageActive() || this._algorithmRuntimeDenied) return Promise.resolve(false);
      if (this.batchStatusBusy || Object.keys(this.statusPending || {}).length) { this.scheduleAlgorithmRuntimeRefresh(); return Promise.resolve(false); }
      if (this._algorithmRuntimeController) return Promise.resolve(false);
      const ids = this.tableData.map(row => String(row.id));
      if (!ids.length) return Promise.resolve(false);
      const generation = this._algorithmRuntimeGeneration, sequence = this.listRequestSequence;
      const current = () => generation === this._algorithmRuntimeGeneration && sequence === this.listRequestSequence
        && this.algorithmRuntimePageActive() && !this.batchStatusBusy && !Object.keys(this.statusPending || {}).length;
      const controller = new AbortController(); this._algorithmRuntimeController = controller;
      return this.$http.get(this.$url.url_5000 + '/model_view/algorithm_data_show', {
        params: { runtime_ids: ids.join(',') }, signal: controller.signal, timeout: 8000,
      }).then(response => {
        if (!current()) return false;
        const body = response && response.data;
        if (body && [401, 403].includes(Number(body.code))) { this.pauseAlgorithmRuntimeRefresh(body.code); return false; }
        if (!body || Number(body.code) !== 200 || !body.data_list || !Array.isArray(body.data_list.data)) throw new Error('Unavailable status');
        const byId = new Map(body.data_list.data.map(row => [String(row.id), row]));
        this.tableData.forEach(row => {
          const fresh = byId.get(String(row.id));
          if (!fresh) return;
          if (fresh.model_status != null && row.model_status !== fresh.model_status) this.$set(row, 'model_status', fresh.model_status);
          const state = fresh.runtime_state || null, reason = fresh.runtime_reason || null;
          if (row.runtime_state !== state) this.$set(row, 'runtime_state', state);
          if (row.runtime_reason !== reason) this.$set(row, 'runtime_reason', reason);
          if (row.status !== fresh.status && (fresh.status === '运行' || fresh.status === '停止')) this.$set(row, 'status', fresh.status);
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

var renderAlgorithmHealthToolbar=function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"batch-toolbar",staticStyle:{"display":"flex","align-items":"center","gap":"10px","height":"48px","padding":"0 16px","box-sizing":"border-box"}},[_c('span',{staticStyle:{"margin-right":"auto","color":"#66758c"}},[_vm._v("当前页已选 "+_vm._s(_vm.multipleSelection.length)+" 项"),(_vm.multipleSelection.length > 100)?_c('span',{staticStyle:{"color":"#c45656"}},[_vm._v("，单次最多 100 项")]):_vm._e(),_c('span',{staticStyle:{"display":"block","font-size":"12px","line-height":"18px","color":"#78869a"},attrs:{"role":"status"}},[_vm._v(_vm._s(_vm.algorithmRuntimeHealthError || (_vm.algorithmRuntimeHealthUpdatedAt ? '运行状态更新于 ' + _vm.algorithmRuntimeHealthUpdatedAt : '运行状态自动刷新')))])]),_c('el-button',{attrs:{"size":"small","type":"success","icon":"el-icon-video-play","disabled":_vm.batchStatusUnavailable(),"loading":_vm.batchStatusBusy && _vm.batchRequestedStatus === '运行'},on:{"click":function($event){return _vm.handleBatchStatus('运行')}}},[_vm._v("批量启动")]),_c('el-button',{attrs:{"size":"small","type":"danger","icon":"el-icon-video-pause","disabled":_vm.batchStatusUnavailable(),"loading":_vm.batchStatusBusy && _vm.batchRequestedStatus === '停止'},on:{"click":function($event){return _vm.handleBatchStatus('停止')}}},[_vm._v("批量停止")])],1)};

// Retain list context only for a round trip through an algorithm editor.
// Each router (and browser tab) owns its own short-lived snapshot.
const algorithmListReturnStates = new WeakMap();
const algorithmEditorPaths = ['/sfgl_child', '/sfgl_childs'];
const algorithmListContextFields = [
  'conf_name', 'algorithm_library_id', 'mkname', 'StartTime', 'EndTime',
  'currentPage', 'pagenumber', 'pagesize', 'pagelength'
];

function clearAlgorithmListReturnState(router) {
  const pending = algorithmListReturnStates.get(router);
  if (!pending) return;
  algorithmListReturnStates.delete(router);
  pending.removeRouteHook();
}

const algorithmListReturnStateMixin = {
  created() {
    const pending = algorithmListReturnStates.get(this.$router);
    if (!pending) return;
    const context = pending.context;
    clearAlgorithmListReturnState(this.$router);
    // Restore before mounted() sends the first list request. The previous total
    // also keeps the pagination control from clamping a restored page to 1.
    algorithmListContextFields.forEach(field => { this[field] = context[field]; });
  },
  beforeRouteLeave(to, from, next) {
    const router = this.$router;
    clearAlgorithmListReturnState(router);
    if (algorithmEditorPaths.includes(to.path)) {
      const context = {};
      algorithmListContextFields.forEach(field => { context[field] = this[field]; });
      const removeRouteHook = router.afterEach(destination => {
        if (destination.path !== '/sfgl' && !algorithmEditorPaths.includes(destination.path)) {
          clearAlgorithmListReturnState(router);
        }
      });
      algorithmListReturnStates.set(router, { context, removeRouteHook });
    }
    next();
  }
};



var renderAlgorithmBatchToolbar=function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('div',{staticClass:"batch-toolbar",staticStyle:{"display":"flex","align-items":"center","gap":"10px","height":"48px","padding":"0 16px","box-sizing":"border-box"}},[_c('span',{staticStyle:{"margin-right":"auto","color":"#66758c"}},[_vm._v("当前页已选 "+_vm._s(_vm.multipleSelection.length)+" 项"),(_vm.multipleSelection.length > 100)?_c('span',{staticStyle:{"color":"#c45656"}},[_vm._v("，单次最多 100 项")]):_vm._e()]),_c('el-button',{attrs:{"size":"small","type":"success","icon":"el-icon-video-play","disabled":_vm.batchStatusUnavailable(),"loading":_vm.batchStatusBusy && _vm.batchRequestedStatus === '运行'},on:{"click":function($event){return _vm.handleBatchStatus('运行')}}},[_vm._v("批量启动")]),_c('el-button',{attrs:{"size":"small","type":"danger","icon":"el-icon-video-pause","disabled":_vm.batchStatusUnavailable(),"loading":_vm.batchStatusBusy && _vm.batchRequestedStatus === '停止'},on:{"click":function($event){return _vm.handleBatchStatus('停止')}}},[_vm._v("批量停止")])],1)};
var renderAlgorithmBatchResults=function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('el-dialog',{attrs:{"title":"批量启停结果","visible":_vm.batchResultVisible,"width":"min(760px, 92vw)","close-on-click-modal":false,"append-to-body":""},on:{"update:visible":function($event){_vm.batchResultVisible=$event}}},[_c('p',[_vm._v("本次"+_vm._s(_vm.batchRequestedStatus === '运行' ? '启动' : '停止')+" "+_vm._s(_vm.batchSummary.total)+" 项：已提交 "+_vm._s(_vm.batchSummary.succeeded)+" 项，失败 "+_vm._s(_vm.batchSummary.failed)+" 项"),(_vm.batchSummary.unconfirmed)?_c('span',[_vm._v("，未确认 "+_vm._s(_vm.batchSummary.unconfirmed)+" 项")]):_vm._e(),_vm._v("。")]),_c('p',{staticStyle:{"color":"#66758c","font-size":"12px","line-height":"1.6"}},[_vm._v("已提交表示服务端已接受请求，实际运行状态以列表为准；停止任务需等待运行进程确认退出。")]),_c('el-table',{staticStyle:{"width":"100%"},attrs:{"data":_vm.batchResults,"max-height":"360"}},[_c('el-table-column',{attrs:{"prop":"id","label":"任务 ID","width":"85"}}),_c('el-table-column',{attrs:{"prop":"name","label":"任务名称","min-width":"130","show-overflow-tooltip":""}}),_c('el-table-column',{attrs:{"label":"结果","width":"90"},scopedSlots:_vm._u([{key:"default",fn:function(scope){return [_c('span',{style:({ color: scope.row.success === true ? '#2c8a3e' : scope.row.success === false ? '#c45656' : '#b26a00' })},[_vm._v(_vm._s(scope.row.success === true ? '已提交' : scope.row.success === false ? '失败' : '未确认'))])]}}])}),_c('el-table-column',{attrs:{"prop":"msg","label":"说明","min-width":"240"}})],1),_c('span',{attrs:{"slot":"footer"},slot:"footer"},[_c('el-button',{on:{"click":function($event){_vm.batchResultVisible = false}}},[_vm._v("关闭")])],1)],1)};

// Keep list JPEGs and full-size previews separate, with an authenticated cache
// scoped to this page. Status-only row updates leave these bindings intact.
const ROI_IMAGE_PLACEHOLDER = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="54"><rect width="96" height="54" fill="#edf1f6"/></svg>');

function roiSnapshotPath(value, base) {
  if (typeof value !== 'string') return '';
  var path = value.indexOf(base + '/') === 0 ? value.slice(base.length) : value;
  return /^\/static\/em_\d+(?:_(?:main|sub))?\.jpg$/.test(path) ? path : '';
}

function roiTaskSnapshotPath(row) {
  var equipment = String(row.Equipment_id || ''), stream = row.stream_type || 'legacy';
  if (!/^\d+$/.test(equipment) || !['legacy', 'main', 'sub'].includes(stream)) return '';
  return '/static/em_' + equipment + (stream === 'legacy' ? '' : '_' + stream) + '.jpg';
}

function createRoiThumbnailPool(options) {
  var env = options.environment, base = String(options.base || '').replace(/\/$/, '');
  var entries = new Map(), records = new Map(), captures = new Map();
  var queues = [[], []], active = [0, 0], limit = [4, 1];
  var revision = 0, stamp = Date.now(), closed = false;

  function placeholder(record, message) {
    var image = record.element;
    image.onerror = null;
    if (image.src !== ROI_IMAGE_PLACEHOLDER) image.src = ROI_IMAGE_PLACEHOLDER;
    image.alt = message;
    image.title = message;
  }
  function valid(entry) { return !closed && entries.get(entry.key) === entry; }
  function apply(record, entry) {
    if (record.entry !== entry || !valid(entry)) return;
    var image = record.element;
    image.alt = '分析区域截图';
    image.title = '点击查看分析区域';
    if (image.src === entry.url) return;
    image.onerror = function () {
      if (record.entry === entry && valid(entry)) placeholder(record, '截图读取失败，请刷新重试');
    };
    image.src = entry.url;
  }
  function dispose(entry) {
    if (entries.get(entry.key) !== entry) return;
    entries.delete(entry.key);
    if (entry.controller) entry.controller.abort();
    if (entry.url) env.URL.revokeObjectURL(entry.url);
    entry.clients.forEach(record => { record.entry = null; });
    entry.clients.clear();
  }
  function trim() {
    for (const entry of entries.values()) {
      if (entries.size <= 48) break;
      if (!entry.clients.size) dispose(entry);
    }
  }
  function capture(path, params) {
    if (captures.has(path)) return captures.get(path).promise;
    var controller = new env.AbortController();
    var promise = options.request(base + '/model_view/image_show', {
      params: Object.assign({type: 1}, params), signal: controller.signal, timeout: 20000,
    }).then(response => {
      if (response.data.code !== 200 || response.data.msg !== path) throw new Error('Snapshot capture unavailable');
    });
    captures.set(path, {controller: controller, promise: promise});
    if (captures.size > 64) captures.delete(captures.keys().next().value);
    return promise;
  }
  async function fetchSnapshot(entry, controller, attemptRevision) {
    var signal = controller.signal;
    var parts = /^\/static\/em_(\d+)(?:_(main|sub))?\.jpg$/.exec(entry.path);
    var source = {equipment_id: parts[1], stream_type: parts[2] || 'legacy'};
    var url = base + (entry.detail ? entry.path : '/model_view/image_show');
    function readFile(generation) {
      var params = {timestamp: stamp + '-' + attemptRevision + '-' + generation};
      if (!entry.detail) Object.assign(params, source, {thumbnail: 1});
      return options.request(url, {responseType: 'blob', timeout: 15000, signal: signal, params: params});
    }
    try {
      return await readFile(0);
    } catch (error) {
      if (!valid(entry) || signal.aborted || !error.response || error.response.status !== 404) throw error;
    }
    await capture(entry.path, source);
    if (!valid(entry) || signal.aborted) return null;
    return await readFile(1);
  }
  function enqueue(entry) {
    if (!entry.clients.size || entry.state === 'queued' || entry.controller) return;
    entry.state = 'queued';
    queues[entry.detail].push(entry);
  }
  function begin(entry) {
    var attemptRevision = revision, controller = new env.AbortController();
    entry.controller = controller;
    entry.state = 'loading';
    ++active[entry.detail];
    fetchSnapshot(entry, controller, attemptRevision).then(response => {
      if (!valid(entry) || attemptRevision !== revision || !response) return;
      var blob = response.data;
      if (!blob || !blob.size || !/^image\/(?:jpeg|png)$/i.test(blob.type || '')) throw new Error('Invalid snapshot');
      var previous = entry.url;
      entry.url = env.URL.createObjectURL(blob);
      entry.state = 'ready';
      entry.clients.forEach(record => apply(record, entry));
      if (previous) env.URL.revokeObjectURL(previous);
    }).catch(() => {
      if (!valid(entry) || attemptRevision !== revision) return;
      entry.state = 'error';
      if (!entry.url) entry.clients.forEach(record => placeholder(record, '截图读取失败，请刷新重试'));
    }).finally(() => {
      --active[entry.detail];
      entry.controller = null;
      if (valid(entry) && attemptRevision !== revision) enqueue(entry);
      drain();
    });
  }
  function drain() {
    if (closed) return;
    for (const detail of [1, 0]) {
      var queue = queues[detail];
      while (active[detail] < limit[detail] && queue.length) {
        var entry = queue.shift();
        if (valid(entry) && entry.clients.size && entry.state === 'queued') begin(entry);
      }
    }
  }
  function paint(record) {
    if (!record.visible || !record.row) return;
    var row = record.row;
    var geometry = [row.id, row.conf_area, row.cross_line_area, row.draw_type, row.img_resolution];
    if (record.geometry && geometry.every((value, i) => value === record.geometry[i])) return;
    record.geometry = geometry;
    options.paint(row);
  }
  function load(record) {
    paint(record);
    if (closed || record.entry || !record.path) return;
    var key = record.detail + ':' + record.path, entry = entries.get(key);
    if (entry) entries.delete(key);
    else entry = {key: key, path: record.path, detail: record.detail, clients: new Set(), state: 'idle', url: '', controller: null};
    entries.set(key, entry);
    record.entry = entry;
    entry.clients.add(record);
    if (entry.url) apply(record, entry);
    else if (entry.state === 'error') placeholder(record, '截图读取失败，请刷新重试');
    else placeholder(record, '正在读取画面…');
    if (entry.state === 'idle') enqueue(entry);
    trim();
    drain();
  }
  function release(record) {
    var entry = record.entry;
    if (!entry) return;
    record.entry = null;
    entry.clients.delete(record);
    if (!entry.clients.size && entry.state === 'queued') dispose(entry);
    trim();
  }
  var observer = env.IntersectionObserver ? new env.IntersectionObserver(changes => {
    changes.forEach(change => {
      var record = records.get(change.target);
      if (!record || record.detail) return;
      record.visible = change.isIntersecting;
      if (record.visible) load(record);
      else {
        release(record);
        placeholder(record, record.path ? '画面将在滚动到此处时加载' : '暂无截图');
      }
    });
  }, {rootMargin: '160px 0px'}) : null;

  function attach(element, value, detail, row) {
    var record = {element: element, path: roiSnapshotPath(value, base), entry: null,
      detail: Number(Boolean(detail)), visible: Boolean(detail || !observer), row: row, geometry: null};
    records.set(element, record);
    placeholder(record, record.path ? '正在读取画面…' : '暂无截图');
    if (record.visible) load(record);
    else observer.observe(element);
    return {
      update: function (row) { record.row = row; paint(record); },
      dispose: function () {
        release(record);
        if (records.get(element) === record) records.delete(element);
        if (observer) observer.unobserve(element);
        placeholder(record, '暂无截图');
      },
    };
  }
  function clearCaptures() {
    captures.forEach(entry => entry.controller.abort());
    captures.clear();
  }
  return {
    attach: attach,
    refresh: function () {
      ++revision;
      stamp = Date.now();
      clearCaptures();
      entries.forEach(entry => {
        if (!entry.clients.size) dispose(entry);
        else if (entry.controller) entry.controller.abort();
        else enqueue(entry);
      });
      drain();
    },
    destroy: function () {
      closed = true;
      if (observer) observer.disconnect();
      clearCaptures();
      entries.forEach(dispose);
      records.clear();
    },
  };
}

const roiImageBindings = new WeakMap();
const roiImageDirective = {
  inserted: function (element, binding, vnode) { roiImageDirective.componentUpdated(element, binding, vnode); },
  componentUpdated: function (element, binding, vnode) {
    var pool = vnode.context._roiThumbnailPool, value = binding.value || {};
    var prior = roiImageBindings.get(element);
    if (prior && prior.pool === pool && prior.path === value.path) {
      prior.handle.update(value.row);
      return;
    }
    if (prior) prior.handle.dispose();
    if (!pool) return;
    roiImageBindings.set(element, {pool: pool, path: value.path,
      handle: pool.attach(element, value.path, binding.modifiers && binding.modifiers.eager, value.row)});
  },
  unbind: function (element) {
    var prior = roiImageBindings.get(element);
    if (prior) prior.handle.dispose();
    roiImageBindings.delete(element);
  },
};

function readRoiGeometry(value, fallback) {
  if (!value || typeof value !== 'string') return value || fallback;
  try { return JSON.parse(value.replace(/'/g, '"')); }
  catch (error) { return fallback; }
}

const roiThumbnailMixin = {
  created: function () {
    this._roiThumbnailPool = createRoiThumbnailPool({base: this.$url.url_5000,
      request: (url, options) => this.$http.get(url, options), environment: window,
      paint: row => this.tableCanvasForTable(row.id, readRoiGeometry(row.conf_area, []),
        readRoiGeometry(row.cross_line_area, null), row.draw_type, row.img_resolution || '1920x1080')});
  },
  beforeDestroy: function () { if (this._roiThumbnailPool) this._roiThumbnailPool.destroy(); },
};


i.r(t);var a=function(){var e=this,t=e._self._c;return t("div",{staticClass:"sfgl"},[t("div",{staticClass:"serch"},[t("el-form",{staticClass:"demo-ruleForm"},[t("el-form-item",{attrs:{label:"任务名称","label-width":"130px"}},[t("el-input",{staticStyle:{width:"100%"},attrs:{autocomplete:"off",placeholder:"请输入任务名称",clearable:""},on:{input:function(t){e.queueAlgorithmSearch()}},model:{value:e.conf_name,callback:function(t){e.conf_name=t},expression:"conf_name"}})],1),t("el-form-item",{attrs:{label:"解析类型","label-width":"80px"}},[t("el-select",{staticStyle:{width:"90%"},attrs:{placeholder:"请选择解析类型",size:"small",clearable:"",filterable:""},on:{change:function(t){e.queryAlgorithms()}},model:{value:e.algorithm_library_id,callback:function(t){e.algorithm_library_id=t},expression:"algorithm_library_id"}},[t("span",{staticClass:"select-icon",attrs:{slot:"prefix"},slot:"prefix"},[t("img",{staticClass:"selectImg",attrs:{src:i("5ba6"),alt:""}})]),e._l(e.options3,(function(e){return t("el-option",{key:e.id,attrs:{label:algorithmFirstEditorIdentity.label(e),value:e.id}})}))],2)],1),t("el-form-item",{attrs:{label:"单位名称","label-width":"80px"}},[t("el-select",{attrs:{placeholder:"请选择单位名称",size:"small",clearable:"",filterable:""},on:{change:function(t){e.queryAlgorithms()}},model:{value:e.mkname,callback:function(t){e.mkname=t},expression:"mkname"}},[t("span",{staticClass:"select-icon",attrs:{slot:"prefix"},slot:"prefix"},[t("img",{staticClass:"selectImg",attrs:{src:i("269f"),alt:""}})]),e._l(e.options1,(function(e){return t("el-option",{key:e.id,attrs:{label:e.mine_name,value:e.id}})}))],2)],1),t("el-form-item",[t("el-button",{attrs:{icon:"el-icon-search",type:"primary",size:"small"},on:{click:function(t){return e.queryAlgorithms()}}},[e._v("查询")])],1),t("el-form-item",[t("el-button",{attrs:{icon:"el-icon-setting",type:"success",size:"small"},on:{click:function(t){return e.handleadds()}}},[e._v("配置")])],1),t("el-form-item",[t("el-button",{attrs:{icon:"el-icon-setting",type:"success",size:"small"},on:{click:function(t){return e.handleaddss()}}},[e._v("高级配置")])],1),t("el-form-item",[t("el-button",{attrs:{icon:"el-icon-delete",type:"danger",size:"small",disabled:e.batchStatusBusy},on:{click:function(t){return e.handledel()}}},[e._v("删除")])],1),t("el-form-item",[t("el-button",{attrs:{icon:"el-icon-refresh",size:"small"},on:{click:function(t){return e.refreshListThumbnails()}}},[e._v("刷新")])],1)],1)],1),t("div",{staticClass:"table"},[renderAlgorithmHealthToolbar.call(e),t("div",{staticClass:"jia_table",staticStyle:{height:"calc(100% - 48px)"}},[t("el-table",{ref:"singleTable",staticStyle:{width:"100%"},attrs:{data:e.tableData,"row-key":e.getRowKey,height:"95%","header-cell-style":{background:"#f9fbff",height:"48.5px",fontSize:"14px"}},on:{select:e.handleRow,"select-all":e.handleRows}},[t("el-table-column",{attrs:{type:"selection",width:"55",selectable:e.canSelectBatchRow}}),t("el-table-column",{attrs:{prop:"index",label:"序号",width:"50"},scopedSlots:e._u([{key:"default",fn:function(t){return[e._v(" "+e._s((Number(e.currentPage)-1)*Number(e.pagesize)+t.$index+1)+" ")]}}])}),t("el-table-column",{attrs:{prop:"mine_name",label:"单位名称","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"conf_name",label:"任务名称","show-overflow-tooltip":!0,width:"230px"}}),t("el-table-column",{attrs:{prop:"algorithm_name",label:"解析类型","show-overflow-tooltip":!0,width:"230px"},scopedSlots:e._u([{key:"default",fn:function(i){return["[]"==i.row.merged_model_data?t("div",[e._v(" "+e._s(algorithmFirstEditorIdentity.name(i.row))+" ")]):t("div",e._l(i.row.merged_model_data.model_data,(function(i,a){return t("span",{key:a},[e._v(e._s(algorithmFirstEditorIdentity.name(i))+";")])})),0)]}}])}),t("el-table-column",{attrs:{prop:"equipment_name",label:"报警设备",width:"180px","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"conf_time",label:"创建时间",width:"160px"}}),t("el-table-column",{attrs:{prop:"conf_area",label:"分析区域",width:"180px"},scopedSlots:e._u([{key:"default",fn:function(i){return[t("div",{staticStyle:{width:"96px",height:"54px",position:"relative"},on:{click:function(t){return e.handleOpenTableImg(i.row.id)}}},[t("img",{staticStyle:{width:"96px",height:"54px",position:"absolute",top:"0",left:"30px","z-index":"9"},directives:[{name:"roi-image",rawName:"v-roi-image",value:{path:roiTaskSnapshotPath(i.row),row:i.row},expression:"{ path: roiTaskSnapshotPath(scope.row), row: scope.row }"}]}),t("canvas",{ref:"tableCanvas_"+i.row.id,staticStyle:{position:"absolute",top:"0",left:"30px","z-index":"10",cursor:"none"},attrs:{id:"tableCanvas_"+i.row.id,tabindex:"0"}})])]}}])}),t("el-table-column",{attrs:{prop:"model_status",label:"算法运行状态",width:"120",align:"center"},scopedSlots:e._u([{key:"default",fn:function(i){return["停止"==i.row.status&&"4"!=i.row.model_status?t("span",{staticStyle:{color:"#b26a00",cursor:"pointer"},attrs:{title:"停止请求已提交，等待运行进程确认退出"}},[e._v("停止中 "),t("i",{staticClass:"el-icon-loading"})]):1==i.row.model_status?t("span",{staticStyle:{cursor:"pointer"},attrs:{title:i.row.runtime_reason||"画面帧、推理与分析输出均正常"}},[e._v("正常")]):"2"==i.row.model_status?t("span",{staticStyle:{color:"#956114",cursor:"help"},attrs:{title:i.row.runtime_reason||"已提交启动，正在等待调度及首帧推理"}},[e._v(algorithmRuntimeLabel(i.row)+" "),t("i",{staticClass:"el-icon-loading"})]):"3"==i.row.model_status?t("span",{staticStyle:{color:"red",cursor:"pointer"},attrs:{title:i.row.runtime_reason||"算法运行异常或正在恢复，请检查画面、推理与分析输出"}},[e._v(({startup_timeout:"推理无输出",output_timeout:"编码无输出",output_offline:"推流离线"})[i.row.runtime_state]||"异常"),t("i",{staticClass:"el-icon-warning-outline"})]):"4"==i.row.model_status?t("span",{staticStyle:{color:"red",cursor:"pointer"},attrs:{title:"算法停止运行"}},[e._v(" 停止 "),t("i",{staticClass:"el-icon-warning-outline"})]):e._e()]}}])}),t("el-table-column",{attrs:{prop:"update_time",label:"更新时间",width:"160"}}),t("el-table-column",{attrs:{prop:"Algorithm_config_ps",label:"备注"},scopedSlots:e._u([{key:"default",fn:function(t){return[e._v(" "+e._s(t.row.Algorithm_config_ps||"暂无备注")+" ")]}}])}),t("el-table-column",{attrs:{label:"操作",width:"320px","class-name":"jia_btn_class",position:"right"},scopedSlots:e._u([{key:"default",fn:function(i){return[e._v(" "+e._s(i.row.status)+" "),t("el-switch",{attrs:{disabled:e.batchStatusBusy||!!e.statusPending[i.row.id],"active-color":"#13ce66","inactive-color":"#ff4949","active-value":"运行","inactive-value":"停止"},on:{change:function(t){return e.handleChangeStatus(i.row)}},model:{value:i.row.status,callback:function(t){e.$set(i.row,"status",t)},expression:"scope.row.status"}}),t("el-button",{attrs:{type:"text",icon:"el-icon-edit",size:"mini"},on:{click:function(t){return e.handlechanges(i.row)}}},[e._v("修改")]),t("el-button",{attrs:{type:"text",icon:"el-icon-warning-outline",size:"mini"},on:{click:function(t){return e.handleToBjlb(i.row)}}},[e._v("报警列表")])]}}])})],1),0===e.tableData.length?t("el-empty",{attrs:{image:"/static/img/home/placeholder_kong.png","image-size":307,description:"暂时没有数据~"}}):e._e()],1),t("div",{staticClass:"page"},[t("el-pagination",{attrs:{"current-page":e.currentPage,"page-size":e.pagesize,"page-sizes":e.pagesizes,background:"",layout:"total, prev, pager, next, jumper,sizes",total:e.pagelength},on:{"current-change":e.handleCurrentChange,"size-change":e.handleSizeChange,"update:currentPage":function(t){e.currentPage=t},"update:current-page":function(t){e.currentPage=t}}})],1)]),renderAlgorithmBatchResults.call(e),t("el-dialog",{staticClass:"jia_algoBox",attrs:{title:e.title,visible:e.dialogVisible,width:"900px","close-on-click-modal":!1,id:"stepDialog"},on:{"update:visible":function(t){e.dialogVisible=t},close:e.handleClose}},[t("el-steps",{staticStyle:{"margin-top":"0px"},attrs:{active:e.stepActive,"finish-status":"success",simple:""}},[t("el-step",{attrs:{title:"步骤 1"}}),t("el-step",{attrs:{title:"步骤 2"}}),t("el-step",{attrs:{title:"步骤 3"}})],1),t("el-form",{ref:"ruleForms",staticClass:"sfgl_diaForm",attrs:{model:e.ruleForm,rules:e.rules,"label-position":"top"}},[t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:0==e.stepActive,expression:"stepActive == 0"}],attrs:{label:"报警设备","label-width":e.formLabelWidth,prop:"equipment_name"}},[t("el-cascader",{staticStyle:{width:"90%"},attrs:{options:e.options2,props:e.props,clearable:"",filterable:"",size:"small"},on:{change:function(t){e.handleChangeCanvas2(),e.updateConfName()}},model:{value:e.ruleForm.equipment_name,callback:function(t){e.$set(e.ruleForm,"equipment_name",t)},expression:"ruleForm.equipment_name"}})],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:0==e.stepActive,expression:"stepActive == 0"}],attrs:{label:"解析类型","label-width":e.formLabelWidth,prop:"Algorithm_library_id"}},[t("el-select",{staticStyle:{width:"90%"},attrs:{placeholder:"请选择解析类型",size:"small",clearable:"",filterable:""},on:{change:function(t){e.handleChangeSf(e.ruleForm.Algorithm_library_id),e.updateConfName()}},model:{value:e.ruleForm.Algorithm_library_id,callback:function(t){e.$set(e.ruleForm,"Algorithm_library_id",t)},expression:"ruleForm.Algorithm_library_id"}},e._l(e.options3,(function(e){return t("el-option",{key:e.id,attrs:{label:algorithmFirstEditorIdentity.label(e),value:e.id}})})),1)],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:0==e.stepActive,expression:"stepActive == 0"}],attrs:{label:"任务名称","label-width":e.formLabelWidth,prop:"conf_name"}},[t("el-input",{staticStyle:{width:"90%"},attrs:{placeholder:"请输入任务名称",size:"small"},on:{input:function(t){e.checkShieldStatus(),e.handlesearchModelName()}},model:{value:e.ruleForm.conf_name,callback:function(t){e.$set(e.ruleForm,"conf_name",t)},expression:"ruleForm.conf_name"}}),t("br"),t("div",{directives:[{name:"show",rawName:"v-show",value:e.conf_name_type,expression:"conf_name_type"}]},[e._v("例:"+e._s(e.conf_name_note))]),e.modelNameOpen?t("span",{staticStyle:{"font-size":"12px",color:"red"}},[e._v(e._s(e.modelNamemsg))]):e._e()],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:0==e.stepActive,expression:"stepActive == 0"}],attrs:{label:"报警等级","label-width":e.formLabelWidth,prop:"res_type"}},[t("el-select",{staticStyle:{width:"90%"},attrs:{placeholder:"请选择报警等级",size:"small",clearable:"",filterable:""},model:{value:e.ruleForm.res_type,callback:function(t){e.$set(e.ruleForm,"res_type",t)},expression:"ruleForm.res_type"}},e._l(e.alarmTypeDictOptions,(function(e){return t("el-option",{key:"报警等级"+e.value,attrs:{label:e.label,value:e.value}})})),1)],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:e.drawLineOpen&&0==e.stepActive,expression:"drawLineOpen && stepActive == 0"}],attrs:{label:"场景类型","label-width":e.formLabelWidth,prop:"scene_typename"}},[t("el-select",{staticStyle:{width:"90%"},attrs:{placeholder:"请选择场景类型",size:"small",clearable:"",filterable:""},model:{value:e.ruleForm.scene_typename,callback:function(t){e.$set(e.ruleForm,"scene_typename",t)},expression:"ruleForm.scene_typename"}},e._l(e.areaOption,(function(e){return t("el-option",{key:e,attrs:{label:e,value:e}})})),1)],1),e.algorithmTemplateAdministrator?t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:1==e.stepActive,expression:"stepActive == 1"}],attrs:{label:"模型类型选择","label-width":e.formLabelWidth,prop:"model_template_config_id"}},[t("el-cascader",{staticStyle:{width:"90%"},attrs:{options:e.modelOptions,props:e.modelProps,clearable:"",size:"small"},on:{"expand-change":e.getModelSmallDict},model:{value:e.ruleForm.model_template_config_id,callback:function(t){e.$set(e.ruleForm,"model_template_config_id",t)},expression:"ruleForm.model_template_config_id"}})],1):e._e(),e.algorithmTemplateAdministrator?t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:1==e.stepActive,expression:"stepActive == 1"}],attrs:{label:"模型小类","label-width":e.formLabelWidth,prop:"template_small_id"}},[t("el-select",{staticStyle:{width:"90%"},attrs:{placeholder:"请选择模型小类",size:"small",clearable:"",filterable:""},on:{change:function(t){return e.handleChangeTemplateSmall()}},model:{value:e.ruleForm.template_small_id,callback:function(t){e.$set(e.ruleForm,"template_small_id",t)},expression:"ruleForm.template_small_id"}},e._l(e.modelSmallOption,(function(e){return t("el-option",{key:e.id,attrs:{label:e.template_small_name,value:e.id}})})),1)],1):e._e(),t("div",{directives:[{name:"show",rawName:"v-show",value:1==e.stepActive&&0!=e.ruleForm.template_data.length,expression:"stepActive == 1 && ruleForm.template_data.length!=0"}],staticStyle:{width:"100%",height:"auto"}},[e._l(e.ruleForm.template_data,(function(i,a){return t("div",{key:a,staticClass:"form-group"},[t("el-input",{staticStyle:{width:"150px","margin-right":"10px","margin-top":"10px"},attrs:{placeholder:"请输入键名",size:"small",disabled:!e.algorithmTemplateAdministrator},model:{value:i.key,callback:function(t){e.$set(i,"key",t)},expression:"item.key"}}),t("el-input",{staticStyle:{width:"230px","margin-right":"10px","margin-top":"10px"},attrs:{placeholder:"请输入值",size:"small",disabled:!e.algorithmTemplateAdministrator},model:{value:i.value,callback:function(t){e.$set(i,"value",t)},expression:"item.value"}}),e.algorithmTemplateAdministrator?t("el-button",{staticStyle:{"margin-right":"10px","margin-top":"10px"},attrs:{type:"danger",icon:"el-icon-delete",size:"small"},on:{click:function(t){return e.removeItem(a)}}},[e._v("删除")]):e._e(),a!=e.ruleForm.template_data.length-1&&0!=e.ruleForm.template_data.length||!e.algorithmTemplateAdministrator?e._e():t("el-button",{staticStyle:{"margin-right":"10px","margin-top":"10px"},attrs:{type:"success",icon:"el-icon-plus",size:"small"},on:{click:function(t){return e.addItem(a)}}},[e._v("新增")])],1)})),0==e.ruleForm.template_data.length&&e.algorithmTemplateAdministrator?t("el-button",{staticStyle:{"margin-right":"10px","margin-top":"10px"},attrs:{type:"success",icon:"el-icon-plus",size:"small"},on:{click:function(t){return e.addItem(e.index)}}},[e._v("新增")]):e._e()],2),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:1==e.stepActive&&4!=e.model_template_config_id_num,expression:"stepActive == 1 && model_template_config_id_num != 4"}],attrs:{label:"检测类型","label-width":e.formLabelWidth,prop:"label_list"}},[t("el-select",{staticStyle:{width:"90%"},attrs:{placeholder:"请选择检测类型",size:"small",clearable:"",filterable:"",multiple:""},on:{change:e.handleChangeLabelList},model:{value:e.ruleForm.label_list,callback:function(t){e.$set(e.ruleForm,"label_list",t)},expression:"ruleForm.label_list"}},e._l(e.options4,(function(e){return t("el-option",{key:e.id,attrs:{label:e.test_type_cname,value:e.test_type_ename}})})),1)],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:e.showShieldConfig&&0==e.stepActive,expression:"showShieldConfig && stepActive == 0"}],attrs:{label:"遮挡配置","label-width":e.formLabelWidth,prop:"shield_status"}},[t("el-radio",{attrs:{label:1},on:{input:e.handleChangeShield_status},model:{value:e.shield_status,callback:function(t){e.shield_status=t},expression:"shield_status"}},[e._v("遮挡")]),t("el-radio",{attrs:{label:2},model:{value:e.shield_status,callback:function(t){e.shield_status=t},expression:"shield_status"}},[e._v("未遮挡")])],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:2==e.stepActive,expression:"stepActive == 2 "}],attrs:{label:"置信度","label-width":e.formLabelWidth,prop:"confidence"}},[t("el-input",{staticStyle:{width:"90%"},attrs:{autocomplete:"off",placeholder:"请输入置信度",size:"small"},model:{value:e.ruleForm.confidence,callback:function(t){e.$set(e.ruleForm,"confidence",t)},expression:"ruleForm.confidence"}})],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:2==e.stepActive,expression:"stepActive == 2 "}],attrs:{label:"持续时长","label-width":e.formLabelWidth,prop:"duration_time"}},[t("el-input",{staticStyle:{width:"90%"},attrs:{autocomplete:"off",placeholder:"请输入持续时长",size:"small"},model:{value:e.ruleForm.duration_time,callback:function(t){e.$set(e.ruleForm,"duration_time",t)},expression:"ruleForm.duration_time"}},[t("template",{slot:"append"},[e._v("秒")])],2)],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:2==e.stepActive,expression:"stepActive == 2 "}],attrs:{label:"告警间隔","label-width":e.formLabelWidth,prop:"interval_time"}},[t("el-input",{staticStyle:{width:"90%"},attrs:{autocomplete:"off",placeholder:"请输入告警间隔",size:"small"},model:{value:e.ruleForm.interval_time,callback:function(t){e.$set(e.ruleForm,"interval_time",t)},expression:"ruleForm.interval_time"}},[t("template",{slot:"append"},[e._v("秒")])],2)],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:2==e.stepActive,expression:"stepActive == 2 "}],attrs:{label:"间隔帧","label-width":e.formLabelWidth,prop:"sensitivity"}},[t("el-input",{staticStyle:{width:"90%"},attrs:{placeholder:"请输入间隔帧",size:"small"},model:{value:e.ruleForm.sensitivity,callback:function(t){e.$set(e.ruleForm,"sensitivity",e._n(t))},expression:"ruleForm.sensitivity"}})],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:"JY"==e.system&&2==e.stepActive,expression:"system == 'JY' && stepActive == 2 "}],attrs:{label:"算力资源信息","label-width":e.formLabelWidth,prop:"resource_id"}},[t("el-cascader",{staticStyle:{width:"90%"},attrs:{options:e.computeOptions,props:e.computeProps,clearable:"",size:"small"},model:{value:e.ruleForm.resource_id,callback:function(t){e.$set(e.ruleForm,"resource_id",t)},expression:"ruleForm.resource_id"}})],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:2==e.stepActive,expression:"stepActive == 2 "}],attrs:{label:"报警图片目标框是否显示","label-width":e.formLabelWidth,prop:"image_draw_type"}},[t("el-select",{staticStyle:{width:"90%"},attrs:{placeholder:"请选择",size:"small",clearable:"",filterable:""},model:{value:e.image_draw_type,callback:function(t){e.image_draw_type=t},expression:"image_draw_type"}},[t("el-option",{attrs:{label:"是",value:1}}),t("el-option",{attrs:{label:"否",value:2}})],1)],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:2==e.stepActive,expression:"stepActive == 2 "}],attrs:{label:"布防开始时间","label-width":e.formLabelWidth,prop:"defense_time_start"}},[t("el-time-picker",{attrs:{"value-format":"HH:MM:ss","picker-options":{selectableRange:"00:00:00 - 23:59:59"},placeholder:"任意时间点","default-value":(new Date).setHours(0,0,0,0)},model:{value:e.ruleForm.defense_time_start,callback:function(t){e.$set(e.ruleForm,"defense_time_start",t)},expression:"ruleForm.defense_time_start"}})],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:2==e.stepActive,expression:"stepActive == 2 "}],attrs:{label:"布防结束时间","label-width":e.formLabelWidth,prop:"defense_time_end"}},[t("el-time-picker",{attrs:{"value-format":"HH:MM:ss","picker-options":{selectableRange:"00:00:00 - 23:59:59"},placeholder:"任意时间点","default-value":(new Date).setHours(0,0,0,0)},model:{value:e.ruleForm.defense_time_end,callback:function(t){e.$set(e.ruleForm,"defense_time_end",t)},expression:"ruleForm.defense_time_end"}})],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:2==e.stepActive,expression:"stepActive == 2 "}],staticClass:"jia_formItm",attrs:{label:"备注","label-width":e.formLabelWidth,prop:"Algorithm_config_ps"}},[t("el-input",{attrs:{autocomplete:"off",placeholder:"请输入备注",type:"textarea"},model:{value:e.ruleForm.Algorithm_config_ps,callback:function(t){e.$set(e.ruleForm,"Algorithm_config_ps",t)},expression:"ruleForm.Algorithm_config_ps"}})],1),t("el-form-item",{directives:[{name:"show",rawName:"v-show",value:0==e.stepActive,expression:"stepActive == 0"}],staticClass:"jia_formItem2",staticStyle:{width:"100%"},attrs:{label:"绘制监测区域","label-width":e.formLabelWidth}},[t("div",{staticClass:"jia_btn"}),t("div",{directives:[{name:"loading",rawName:"v-loading",value:e.loading,expression:"loading"}],staticClass:"Bcanvas"},[e.imgOpen?e._e():t("div",{staticClass:"jia_div"},[e._v("暂未选择监控点，无图片展示")]),e.imgOpen?t("img",{staticStyle:{width:"640px",height:"360px"},attrs:{src:e.imgurl,alt:""},on:{load:function(t){e.loading=!1}}}):e._e(),t("canvas",{ref:"mycanvas",attrs:{id:"mycanvas",tabindex:"0"}}),1==e.shield_status||2==e.image_draw_type?t("div",{staticClass:"jia_div"}):e._e()]),t("div",{staticClass:"canvasBtn"},[t("el-button",{attrs:{type:"text",icon:"el-icon-refresh"},on:{click:function(t){return e.handleimg(1)}}},[e._v("刷新")]),t("el-button",{attrs:{type:"text",icon:"el-icon-edit"},on:{click:e.handleDrewAgain}},[e._v("重新绘制")]),t("el-button",{attrs:{type:"text",icon:"el-icon-refresh-left"},on:{click:e.resole}},[e._v("撤销")])],1)])],1),t("span",{staticClass:"dialog-footer",attrs:{slot:"footer"},slot:"footer"},[t("el-button",{on:{click:e.stepUp}},[e._v("上一步")]),t("el-button",{on:{click:e.stepNext}},[e._v("下一步")]),t("el-button",{on:{click:function(t){return e.handleCloseDialog()}}},[e._v("取 消")]),3==e.stepActive?t("el-button",{attrs:{type:"primary"},on:{click:function(t){return e.handleSure()}}},[e._v("确 定")]):e._e()],1)],1),t("el-dialog",{attrs:{title:e.title2_model,visible:e.dialogVisible2_model,width:"500px"},on:{"update:visible":function(t){e.dialogVisible2_model=t},close:e.handleClose2_model}},[t("el-radio-group",{model:{value:e.selectedOption_model,callback:function(t){e.selectedOption_model=t},expression:"selectedOption_model"}},[t("el-radio",{attrs:{label:"类型一"}},[e._v("类型一")])],1),t("span",{staticClass:"dialog-footer",attrs:{slot:"footer"},slot:"footer"},[t("el-button",{on:{click:function(t){e.dialogVisible2_model=!1,e.handleDeleteList_model()}}},[e._v("取 消")]),t("el-button",{attrs:{type:"primary"},on:{click:function(t){return e.handleUpdateList_model()}}},[e._v("确 定")])],1)],1),t("el-dialog",{attrs:{title:e.title2,id:"alarmTypeBox",visible:e.dialogVisible2,width:"500px","close-on-click-modal":!1},on:{"update:visible":function(t){e.dialogVisible2=t},close:e.handleClose2}},[t("div",{staticClass:"radio-group-title"},[e._v("告警区域")]),t("br"),t("el-radio-group",{staticClass:"radio-grid",model:{value:e.selectedOption,callback:function(t){e.selectedOption=t},expression:"selectedOption"}},[t("el-radio",{staticClass:"grid-item",attrs:{label:"告警区域"}},[e._v("告警区域")])],1),t("br"),t("br"),t("div",{staticClass:"radio-group-title"},[e._v("后处理区域")]),t("br"),t("el-radio-group",{staticClass:"radio-grid",model:{value:e.selectedOption,callback:function(t){e.selectedOption=t},expression:"selectedOption"}},[t("el-radio",{staticClass:"grid-item",attrs:{label:"类型一"}},[e._v("类型一")])],1),t("span",{staticClass:"dialog-footer",attrs:{slot:"footer"},slot:"footer"},[t("el-button",{on:{click:function(t){e.dialogVisible2=!1,e.handleDeleteList()}}},[e._v("取 消")]),t("el-button",{attrs:{type:"primary"},on:{click:function(t){return e.handleUpdateList()}}},[e._v("确 定")])],1)],1),t("el-dialog",{attrs:{title:e.title3,visible:e.dialogVisible3,width:"80%"},on:{"update:visible":function(t){e.dialogVisible3=t},close:e.handleClose3}},[t("History",{key:e.historyKey,ref:"historyTable"})],1),t("el-dialog",{attrs:{title:"视频分析",visible:e.dialogVisible4,width:"80%"},on:{"update:visible":function(t){e.dialogVisible4=t},close:e.handleClose4}},[t("video",{ref:"videoPlayer",attrs:{width:"100%",height:"100%",controls:""}})]),t("el-dialog",{attrs:{title:"分析区域",visible:e.dialogVisible5,width:"850px"},on:{"update:visible":function(t){e.dialogVisible5=t},close:e.handleClose5}},[t("div",{staticStyle:{width:"800px",height:"400px",position:"relative"}},[t("img",{staticStyle:{width:"800px",height:"400px",position:"absolute",top:"0",left:"0","z-index":"9"},directives:[{name:"roi-image",rawName:"v-roi-image.eager",value:{path:e.dialogVisible5?e.analysisSrc:""},expression:"{ path: dialogVisible5 ? analysisSrc : '' }",modifiers:{eager:true}}]}),t("canvas",{ref:"tableCanvas_tableMax",staticStyle:{position:"absolute",top:"0",left:"0","z-index":"10",cursor:"none"},attrs:{id:"tableCanvas_tableMax",tabindex:"0"}})]),t("div",{staticClass:"btn_group",staticStyle:{"margin-top":"10px",width:"100%",height:"50px",display:"flex","justify-content":"center"}},[t("el-button-group",[t("el-button",{attrs:{type:"primary",icon:"el-icon-arrow-left"},on:{click:e.handleUpImg}},[e._v("上一条")]),t("el-button",{attrs:{type:"primary"},on:{click:e.handleNextImg}},[e._v("下一条"),t("i",{staticClass:"el-icon-arrow-right el-icon--right"})])],1)],1)])],1)},l=[],s=(i("14d9"),i("d9e2"),i("88a7"),i("271a"),i("5494"),i("13d5"),i("8f15")),o=i("896f"),r=i("de4a"),n=i("dc58"),m=i("c329"),d=i("4360"),h=i("8156"),c=i("fc78"),p=i.n(c),_=i("2ecc"),u=i("ed5a"),g={components:{History:h["a"]},mixins:[window.PlatformAlgorithmTemplateAdministrator,roiThumbnailMixin,algorithmListReturnStateMixin],directives:{roiImage:roiImageDirective},name:"sfgl",data(){return{mkname:"",system:window.wgParameter.system,version:d["a"].state.version,url_5000:this.$url.url_5000,StartTime:"",EndTime:"",startTimePickerOptions:{disabledDate:e=>e.getTime()>Date.now()},endTimePickerOptions:{disabledDate:e=>{if(this.StartTime){const t=new Date(this.StartTime);return t.setHours(0,0,0,0),e.getTime()>Date.now()||e.getTime()<t.getTime()}return e.getTime()>Date.now()}},conf_name:"",algorithm_name:"",algorithm_library_id:"",tableData:[],listRequestSequence:0,statusPending:{},statusRefreshTimer:null,batchStatusBusy:false,batchRequestedStatus:"",batchResultVisible:false,batchResults:[],batchSummary:{total:0,succeeded:0,failed:0,unconfirmed:0},currentPage:1,pagenumber:1,pagesize:15,pagelength:0,pagesizes:[15,35,50,100,150,200,300],multipleSelection:[],dialogVisible:!1,dialogVisible2:!1,dialogVisible3:!1,dialogVisible4:!1,dialogVisible5:!1,historyKey:0,formLabelWidth:"140px",conf_name_note:"",conf_name_type:!1,resolution:"",resolutionOption:[{value:"1920x1080",name:"普通"},{value:"2688x1520",name:"热成像"},{value:"2560x1440",name:"热成像"},{value:"1280x720",name:"热成像"},{value:"720x576",name:"热成像2"}],areaOption:["掘进机","转载点-运输皮带仓内","转载点-运输皮带仓外"],alarmTypeDictOptions:[{label:"I级报警",value:"1"},{label:"II级报警",value:"2"},{label:"III级报警",value:"3"}],timesX:3,timesY:3,options1:[],options2:[],options3:[],options4:[],ruleForm:{mine_name:"",algorithm_name:"",equipment_name:"",Algorithm_library_id:"",type:0,confidence:"80",tem_frames:"[27,37]",duration_time:10,interval_time:300,image_draw_type:1,Algorithm_config_ps:"",scene_typename:"",sensitivity:25,resource_id:"",resource_id_old:"",defense_time_start:"",defense_time_end:"",image_count:5,template_small_id:"",res_type:"",template_data:[],test_type_id:"",label_list:[]},rules:{sensitivity:[{type:"number",min:1,message:"间隔帧必须是正整数",trigger:"blur"},{validator:this.validateInteger,trigger:["blur","change"]}],confidence:[{validator:this.validateConfidence,trigger:["blur","change"]}],duration_time:[{validator:this.validateDurationTime,trigger:["blur","change"]}],interval_time:[{validator:this.validateDurationTime,trigger:["blur","change"]}],image_count:[{pattern:/^[1-9]\d*$/,message:"图片数量必须为正整数",trigger:["blur","change"]}]},props:{checkStrictly:!1,emitPath:!1,value:"id",label:"equipment_name"},modelProps:{checkStrictly:!1,emitPath:!1,value:"model_id",label:"model_type_name"},imgurl:"",isdraw:!1,coordinates:[],cor_index:0,endtip:!1,mark_list:[],mark_lists:[],PointInArea:!1,index:null,loading:!1,area2:!1,isdraw2:!1,coordinates2:[],cor_index2:0,endtip2:!1,mark_list2:[],mark_lists2:[],PointInArea2:!1,index2:null,loading2:!1,area3:!1,isdraw3:!1,coordinates3:[],cor_index3:0,endtip3:!1,mark_list3:[],mark_lists3:[],PointInArea3:!1,index3:null,loading3:!1,imgOpen:!1,title:"",title2:"",title3:"",shield_status:2,image_draw_type:1,drawLineOpen:!1,selectedOption:"报警",pickerOptions:{disabledDate(e){const t=new Date;return t.setHours(0,0,0,0),e.getTime()>t.getTime()}},coordinates:[],coordinates2:[],coordinates3:[],computeOptions:[],computeProps:{checkStrictly:!1,emitPath:!1,value:"id",label:"label"},checkStatusTime:null,flvPlayer:null,coordinates_model:[],mark_list_model:[],mark_lists_model:[],selectedOption_model:"类型一",title2_model:"",dialogVisible2_model:!1,modelOptions:[],modelTypeOptions:[],template_type_id:"",stepActive:0,modelSmallOption:[],modelNameOpen:!1,modelNamemsg:"",model_template_config_id_num:1,analysisSrc:"",analysisId:""}},computed:{showShieldConfig(){const e=this.ruleForm.conf_name||"",t=this.options3.find(e=>e.id===this.ruleForm.Algorithm_library_id),i=t?t.algorithm_name:"",a=e.includes("遮挡"),l=i.includes("遮挡");return a||l},drawAreaOpen:{get(){return!this.drawLineOpen},set(e){this.drawLineOpen=!e}}},methods:{getModelSmallDict(e){let t=this.extractNumberFromF(e[0]);this.model_template_config_id_num=t,this.$http.get(u["a"].getModelSmallList,{params:{page:1,per_page:15,model_template_type_id:t}}).then(e=>{this.modelSmallOption=e.data.data.data}).catch(e=>{console.log(e)})},getModelSmallDict2(e){this.model_template_config_id_num=e,this.$http.get(u["a"].getModelSmallList,{params:{page:1,per_page:15,model_template_type_id:e}}).then(e=>{this.modelSmallOption=e.data.data.data}).catch(e=>{console.log(e)})},extractNumberFromF(e){const t=e.match(/^F(\d+)$/);return t?parseInt(t[1],10):NaN},handleToBjlb(e){"人数统计_全身"==e.algorithm_name||"人数统计"==e.algorithm_name||"车辆统计"==e.algorithm_name?this.$router.push({path:"/bjlb",query:{Algorithm_config_id:e.id,type:"tj"}}):this.$router.push({path:"/bjlb",query:{Algorithm_config_id:e.id}})},getCompute(){this.$http.get(s["b"]).then(e=>{this.computeOptions=this.transformData(e.data.data),console.log("算力资源信息",this.computeOptions)}).catch(e=>{console.log(e)})},transformData(e){let t=[];return e.forEach(e=>{let i=e.grouped_resources,a=Object.entries(i).flatMap(([e,t])=>{let i={id:this.generateRandomId(),label:""+e},a=t.map(e=>({id:e.id,label:"TPU"+e.dev_id}));return{...i,children:a}}),l={id:"设备"+e.computing_id,deviceId:e.computing_id,computing_ip:e.computing_ip,label:e.computing_name,children:a};t.push(l)}),t},generateRandomId(){return Math.random().toString(36).substr(2,9)},validateInteger(e,t,i){""===t||Number.isInteger(Number(t))?i():i(new Error("请输入一个整数"))},validateConfidence(e,t,i){const a=/^(?:[1-9][0-9]?|100)$/;a.test(t)?i():i(new Error("置信度必须为大于0且小于等于100的整数"))},validateNumber(e,t,i){const a=parseFloat(t);""===t?i(new Error("请输入数字")):isNaN(a)?i(new Error("必须是数字")):i()},validateDurationTime(e,t,i){/^\d+$/.test(t)?i():i(new Error("时间必须是正整数"))},checkShieldStatus(){this.$forceUpdate()},resole(){this.drawLineOpen?this.coordinates3.pop():this.coordinates.pop()},resole_model(){this.coordinates_model.pop()},resole2(){this.coordinates2.pop()},getRowKey(e){return e.id},handleRow(val) {
      // console.log(val)
      if (!this.batchStatusBusy) this.multipleSelection = val;
    },
    handleRows(val) {
      // console.log(val)
      if (!this.batchStatusBusy) this.multipleSelection = val;
    },
    canSelectBatchRow(row) {
      return !this.batchStatusBusy && !this.statusPending[row.id];
    },
    clearBatchSelection() {
      this.multipleSelection = [];
      const table = this.$refs.singleTable;
      if (table && table.clearSelection) table.clearSelection();
    },
    restoreBatchSelection() {
      const ids = new Set(this.multipleSelection.map(row => String(row.id)));
      this.multipleSelection = this.tableData.filter(row => ids.has(String(row.id)));
      this.$nextTick(() => {
        if (this._isDestroyed || this._isBeingDestroyed) return;
        const table = this.$refs.singleTable;
        if (!table || !table.clearSelection || !table.toggleRowSelection) return;
        table.clearSelection();
        this.multipleSelection.forEach(row => table.toggleRowSelection(row, true));
      });
    },
    batchStatusUnavailable() {
      return this.batchStatusBusy || !this.multipleSelection.length || this.multipleSelection.length > 100 || Object.keys(this.statusPending).length > 0;
    },
    showBatchResults(body, selected) {
      const payload = body && body.data && typeof body.data === 'object' ? body.data : {};
      const results = Array.isArray(payload.results) ? payload.results : [];
      this.batchResults = selected.map(row => {
        const result = results.find(item => item && Number(item.id) === row.id);
        const rejected = !result && body && Number(body.code) === 400;
        const success = result && typeof result.success === 'boolean' ? result.success : rejected ? false : null;
        const fallback = success === true ? '请求已提交' : success === false ? body.msg || '操作失败' : '未收到该任务的明确回执，请刷新列表确认';
        return { id: row.id, name: row.name, success,
          code: result ? result.code : body && body.code,
          msg: String(result && result.msg || fallback) };
      });
      this.batchSummary = { total: this.batchResults.length,
        succeeded: this.batchResults.filter(item => item.success === true).length,
        failed: this.batchResults.filter(item => item.success === false).length,
        unconfirmed: this.batchResults.filter(item => item.success === null).length };
      this.batchResultVisible = true;
    },
    handleBatchStatus(status) {
      if (this.batchStatusUnavailable() || (status !== '运行' && status !== '停止')) return;
      const selected = [];
      for (const row of this.multipleSelection) {
        const validSource = typeof row.id === 'number' || (typeof row.id === 'string' && /^\d+$/.test(row.id));
        const id = Number(row.id);
        if (!validSource || !Number.isSafeInteger(id) || id <= 0) {
          this.$message({ type: 'warning', message: '所选任务 ID 无效，请刷新后重新选择' });
          return;
        }
        if (!selected.some(item => item.id === id)) selected.push({ id, name: String(row.conf_name || '任务 ' + id) });
      }
      this.batchStatusBusy = true;
      this.batchRequestedStatus = status;
      selected.forEach(row => this.$set(this.statusPending, row.id, true));
      ++this.listRequestSequence;
      clearTimeout(this.statusRefreshTimer);
      this.statusRefreshTimer = null;
      const release = () => {
        selected.forEach(row => this.$delete(this.statusPending, row.id));
        this.batchStatusBusy = false;
      };
      return this.$http.post(this.$url.url_5000 + '/model_view/algorithm_conf_batch_update',
        { ids: selected.map(row => row.id), status }, { headers: { 'Content-Type': 'application/json' } })
        .then(response => {
          this.showBatchResults(response.data, selected);
          return this.axioss();
        })
        .catch(error => {
          const body = error.response && error.response.data;
          if (body && (Number(body.code) === 400 || body.data && Array.isArray(body.data.results))) {
            this.showBatchResults(body, selected);
          } else {
            this.showBatchResults(null, selected);
          }
          return this.axioss();
        })
        .then(release, release);
    },
    handleCurrentChange(val) {
      this.clearBatchSelection();
      this.currentPage = val;
      this.pagenumber = val;
      return this.axioss();
    },
    handleSizeChange(val) {
      this.pagesize = val;
      return this.queryAlgorithms();
    },
    queueAlgorithmSearch() {
      clearTimeout(this._algorithmSearchTimer);
      this._algorithmSearchTimer = setTimeout(() => this.queryAlgorithms(), 250);
    },
    queryAlgorithms() {
      this.clearBatchSelection();
      this.currentPage = 1;
      this.pagenumber = 1;
      return this.axioss();
    },
    scheduleStatusRefresh() {
      return this.scheduleAlgorithmRuntimeRefresh();
    },
    refreshListThumbnails() {
      this._roiThumbnailPool.refresh();
      return this.axioss();
    },
    axioss() {
      const requestSequence = ++this.listRequestSequence;
      clearTimeout(this._algorithmSearchTimer);
      this._algorithmSearchTimer = null;
      this.stopAlgorithmRuntimeRefresh();
      if (this._algorithmListController) this._algorithmListController.abort();
      const controller = new AbortController();
      this._algorithmListController = controller;
      return this.$http
        .get(this.$url.url_5000 + "/model_view/algorithm_data_show", {
          signal: controller.signal,
          params: {
            conf_name: this.conf_name,
            // algorithm_name: this.algorithm_name,
            Mine_id: this.mkname,
            algorithm_library_id: this.algorithm_library_id,
            start_time: this.StartTime,
            end_time: this.EndTime,
            page: this.pagenumber,
            per_page: this.pagesize,
            // template_type_id:this.template_type_id,
          },
        })
        .then((response) => {
          if (requestSequence !== this.listRequestSequence || this._isDestroyed || this._isBeingDestroyed) return;
          if ([401, 403].includes(Number(response.data.code))) this.pauseAlgorithmRuntimeRefresh(response.data.code);
          if (response.data.code === 200) {
            this.algorithmRuntimeHealthUpdatedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false });
            this.algorithmRuntimeHealthError = '';
            this.tableData = response.data.data_list.data;
            this.pagelength = response.data.data_list.total_items;
            this.restoreBatchSelection();
          } else {
            this.$message({ type: 'warning', message: response.data.msg || '查询算法配置失败' });
          }
          this.scheduleStatusRefresh();
        })
        .catch((error) => {
          if (requestSequence !== this.listRequestSequence || this._isDestroyed || this._isBeingDestroyed) return;
          if ([401, 403].includes(Number(error.response && error.response.status))) this.pauseAlgorithmRuntimeRefresh(error.response.status);
          this.$message({ type: 'error', message: error.response && error.response.data && error.response.data.msg || '查询算法配置失败，请重试' });
          this.scheduleStatusRefresh();
        }).finally(() => {
          if (this._algorithmListController === controller) this._algorithmListController = null;
        });
    },tableCanvasForTable(e,t,i,a,l){if(window.PlatformCountGeometry&&window.PlatformCountGeometry.normalized(i)){this.$nextTick(()=>{let countCanvas=this.$refs["tableCanvas_"+e];if(Array.isArray(countCanvas))countCanvas=countCanvas[0];if(countCanvas)window.PlatformCountGeometry.render(countCanvas,t,i,l,{width:96,height:54,thumbnail:true});});return;}var s=l.split("x"),o=parseInt(s[0],10),r=parseInt(s[1],10);this.$nextTick(()=>{let a=this.$refs["tableCanvas_"+e];if(!a)return;a.width="96",a.height="54";let l=a.getContext("2d"),s=o/96,n=r/54;if(l.clearRect(0,0,96,54),t&&t.length>0)for(let e=0;e<t.length;e++)if(!(t[e].length<3)){l.beginPath(),l.strokeStyle=t[e][0].color||"#f00",l.lineWidth=1,l.moveTo(t[e][0].x/s,t[e][0].y/n);for(let i=1;i<t[e].length;i++)l.lineTo(t[e][i].x/s,t[e][i].y/n);l.closePath(),l.stroke()}if(i&&i.p1&&i.p2)try{const e={x:Number(i.p1.x)/s,y:Number(i.p1.y)/n},t={x:Number(i.p2.x)/s,y:Number(i.p2.y)/n};e.x=Math.min(96,Math.max(0,e.x)),e.y=Math.min(54,Math.max(0,e.y)),t.x=Math.min(96,Math.max(0,t.x)),t.y=Math.min(54,Math.max(0,t.y)),l.beginPath(),l.moveTo(e.x,e.y),l.lineTo(t.x,t.y),l.strokeStyle="#ffd700",l.lineWidth=1.5,l.stroke();const a=t.x-e.x,o=t.y-e.y,r=Math.sqrt(a*a+o*o);if(r>0){const s=a/r,n=o/r,m=15,d=(e.x+t.x)/2,h=(e.y+t.y)/2;let c=d-n*m,p=h+s*m,_=d+n*m,u=h-s*m;c=Math.min(94,Math.max(2,c)),p=Math.min(52,Math.max(2,p)),_=Math.min(94,Math.max(2,_)),u=Math.min(52,Math.max(2,u)),"left"===i.direction?(l.beginPath(),l.fillStyle="#44ff44",l.arc(c,p,3,0,2*Math.PI),l.fill(),l.beginPath(),l.fillStyle="#ff4444",l.arc(_,u,3,0,2*Math.PI),l.fill()):(i.direction,l.beginPath(),l.fillStyle="#ff4444",l.arc(c,p,3,0,2*Math.PI),l.fill(),l.beginPath(),l.fillStyle="#44ff44",l.arc(_,u,3,0,2*Math.PI),l.fill())}}catch(m){console.error("绘制线失败:",m)}})},getDefaultEndTime(){const e=new Date;return new Date(e.setHours(23,59,59,999))},handleadds(){this.$router.push("/algorithm-first")},handleaddss(){this.$router.push("/algorithm-first")},handleadd(){this.resolution="",this.modelNameOpen=!1,this.stepActive=0,this.area2=!1,this.title="算法配置",this.ruleForm={mine_name:"",algorithm_name:"",equipment_name:"",Algorithm_library_id:"",type:0,confidence:"80",tem_frames:"[27,37]",duration_time:10,interval_time:300,sensitivity:25,defense_time_start:"00:00:00",defense_time_end:"23:59:59",image_count:5,template_data:[],test_type_id:"",label_list:[]},this.shield_status=2,this.dialogVisible=!0,this.mark_list=[],this.mark_list_model=[],this.mark_list2=[],this.mark_list3=[],this.coordinates=[],this.coordinates_model=[],this.coordinates2=[],this.coordinates3=[],this.initCanvas(),this.initCanvas_model(),this.handleSelect()},findDeviceIdById(e,t){for(const i of e)if(console.log("current option",i),i.children){const e=i.children.find(e=>e.id===t);if(e)return i.deviceId;const a=this.findDeviceIdById(i.children,t);if(void 0!==a)return a}},handleSure(){if(1==this.modelNameOpen)return void this.$message({type:"warning",message:"任务名称名字重复，请检查数据后重新提交"});if("1"==this.shield_status){let e=this.resolution.split("x"),t=parseInt(e[0]),i=parseInt(e[1]);this.mark_lists=[[{x:0,y:0,type:"I级报警",color:"#FF0000"},{x:t,y:0,type:"I级报警",color:"#FF0000"},{x:t,y:i,type:"I级报警",color:"#FF0000"},{x:0,y:i,type:"I级报警",color:"#FF0000"}]],this.mark_lists2=[[{x:0,y:0},{x:t,y:0},{x:t,y:i},{x:0,y:i}]]}else this.handleData();let e;this.handleData_model(),4==this.model_template_config_id_num&&(this.ruleForm.test_type_id=this.options4[0].id,this.ruleForm.label_list=[this.options4[0].test_type_ename]),this.computeOptions.some(t=>!!t.children&&t.children.some(i=>!!i.children&&i.children.some(i=>i.id===this.ruleForm.resource_id&&(e=t.deviceId,!0))));let t,i=JSON.stringify(this.getModelSmallDetail());this.modelOptions.forEach(e=>{e.children.forEach(i=>{i.id==this.ruleForm.model_template_config_id&&(t=e.id)})});let a={conf_name:this.ruleForm.conf_name,Algorithm_library_id:this.ruleForm.Algorithm_library_id,Mine_id:this.ruleForm.mine_name,Equipment_id:this.ruleForm.equipment_name,conf_area:this.drawLineOpen?this.mark_lists3:this.mark_lists,test_type_id:this.ruleForm.test_type_id,label_list:JSON.stringify(this.ruleForm.label_list),shield_status:this.shield_status,tem_frames:this.ruleForm.tem_frames,confidence:this.ruleForm.confidence,tem_conf_area:this.mark_lists2,draw_type:this.drawLineOpen?"2":"1",img_resolution:this.resolution,duration_time:this.ruleForm.duration_time,interval_time:this.ruleForm.interval_time,image_draw_type:this.image_draw_type,Algorithm_config_ps:this.ruleForm.Algorithm_config_ps,scene_typename:this.ruleForm.scene_typename,sensitivity:this.ruleForm.sensitivity,resource_id:this.ruleForm.resource_id,computing_id:e,resource_id_old:this.ruleForm.resource_id_old,defense_time_start:this.ruleForm.defense_time_start,defense_time_end:this.ruleForm.defense_time_end,model_template_config_id:this.ruleForm.model_template_config_id,model_template_type_id:t,template_list_area:this.mark_lists_model,template_small_id:this.ruleForm.template_small_id,res_type:this.ruleForm.res_type,template_data:i},l={id:this.ruleForm.id,conf_name:this.ruleForm.conf_name,Algorithm_library_id:this.ruleForm.Algorithm_library_id,Mine_id:this.ruleForm.mine_name,Equipment_id:this.ruleForm.equipment_name,conf_area:this.drawLineOpen?JSON.stringify(this.mark_lists3):JSON.stringify(this.mark_lists),test_type_id:this.ruleForm.test_type_id,label_list:JSON.stringify(this.ruleForm.label_list),shield_status:this.shield_status,tem_frames:this.ruleForm.tem_frames,confidence:this.ruleForm.confidence,tem_conf_area:JSON.stringify(this.mark_lists2),draw_type:this.drawLineOpen?"2":"1",img_resolution:this.resolution,duration_time:this.ruleForm.duration_time,interval_time:this.ruleForm.interval_time,image_draw_type:this.image_draw_type,Algorithm_config_ps:this.ruleForm.Algorithm_config_ps,scene_typename:this.ruleForm.scene_typename,sensitivity:this.ruleForm.sensitivity,resource_id:this.ruleForm.resource_id,computing_id:e,resource_id_old:this.ruleForm.resource_id_old,defense_time_start:this.ruleForm.defense_time_start,defense_time_end:this.ruleForm.defense_time_end,model_template_config_id:this.ruleForm.model_template_config_id,model_template_type_id:t,template_list_area:JSON.stringify(this.mark_lists_model),template_small_id:this.ruleForm.template_small_id,res_type:this.ruleForm.res_type,template_data:i};if("算法配置"==this.title)this.$http.post(this.$url.url_5000+"/model_view/algorithm_add",a).then(e=>{200===e.data.code?(this.$message({message:e.data.msg,type:"success"}),this.axioss(),this.handleClose()):this.$message({message:e.data.msg,type:"warning"})}).catch((function(e){console.log(e)}));else if("算法修改"==this.title){const e=new URLSearchParams;for(const t in l)e.append(t,l[t]);this.$http.post(this.$url.url_5000+"/model_view/algorithm_update",e,{headers:{"Content-Type":"application/x-www-form-urlencoded"}}).then(e=>{200===e.data.code?(this.$message({message:e.data.msg,type:"success"}),this.axioss(),this.handleClose()):this.$message({message:e.data.msg,type:"warning"})}).catch((function(e){console.log(e)}))}},loadAlgorithmListOptions() {
      return this.$http.get(this.$url.url_5000 + '/model_view/type_select', { params: { scope: 'algorithm_tasks' } })
        .then(({ data }) => {
          if (this._isDestroyed || this._isBeingDestroyed || this._algorithmLegacyOptionsRequested) return;
          if (Number(data.code) !== 200) throw new Error('Unavailable task filters');
          this.options1 = data.mine_list || [];
          this.options3 = data.algorithm_list || [];
        }).catch(() => {
          if (!this._isDestroyed && !this._isBeingDestroyed) this.$message({type: 'warning', message: '筛选项读取失败，请重新进入页面'});
        });
    },handleSelect(a) {
      if (!this._algorithmLegacyOptionsRequested) {
        this._algorithmLegacyOptionsRequested = true;
        this.getCompute();
        this.$http.get(u["a"].getModelType,{params:{page:1,per_page:999}})
          .then(e=>{this.modelTypeOptions=e.data.data.data}).catch(e=>{console.log(e)});
      }
      // let param = new URLSearchParams();
      // param.append("mine_id", this.mkname);
      if (a === 1) {
        this.ruleForm.equipment_name = "";
      }
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: this.ruleForm.mine_name, 
              // List filters use the server algorithm library across categories.
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
            this.ruleForm.mine_name = response.data.mine_list[0].id
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
    },handleimg(e){this.loading=!0,this.loading2=!0,this.imgOpen=!1,this.$http.get(this.$url.url_5000+"/model_view/image_show",{params:{equipment_id:this.ruleForm.equipment_name,type:1==e?e:this.ruleForm.type,img_resolution:this.resolution}},{withCredentials:!0}).then(e=>{if(this.loading=!0,200===e.data.code){this.resolution=e.data.img_resolution,this.handleTimesData(this.resolution);let t=this.$url.url_5000+""+e.data.msg;this.imgurl=`${t}?timestamp=${(new Date).getTime()}`,this.loading=!1,this.loading2=!0,this.drawLineOpen?this.initCanvas4():this.initCanvas(),this.initCanvas_model(),this.imgOpen=!0}else this.$message({message:e.data.msg,type:"warning"}),this.imgurl="",this.loading=!1,this.loading2=!0,this.imgOpen=!1}).catch((function(e){console.log(e)}))},handledel(){this.multipleSelection.length>0?this.$confirm("此操作将永久删除选中信息, 是否继续?","提示",{confirmButtonText:"确定",cancelButtonText:"取消",type:"warning"}).then(()=>{this.$http.post(this.$url.url_5000+"/model_view/algorithm_data_delete",{id:this.multipleSelection}).then(e=>{200===e.data.code?(this.$message({message:e.data.msg,type:"success"}),this.axioss()):this.$message({message:e.data.msg,type:"warning"})}).catch((function(e){console.log(e)}))}).catch(()=>{this.$message({type:"info",message:"已取消删除"})}):this.$message({type:"warning",message:"没有选中删除的信息"})},handlechanges(e){0==e.multimodels_type?this.$router.push({path:"/sfgl_child",query:{conf_id:e.id}}):this.$router.push({path:"/sfgl_childs",query:{id:e.id,map:JSON.stringify(e.merged_model_data)}})},handlechange(e){this.modelNameOpen=!1,this.stepActive=0,this.coordinates=[],this.coordinates_model=[],this.coordinates2=[],this.coordinates3=[],this.$http.get(this.$url.url_5000+"/model_view/algorithm_data_show",{params:{conf_id:e.id}}).then(e=>{if(200===e.data.code){if(this.title="算法修改",this.ruleForm=e.data.datalist,console.log(this.ruleForm),this.findModelBigDict(this.ruleForm.model_template_config_id),this.ruleForm.template_data=this.ruleForm.template_data.reduce((e,t)=>{if(Object.keys(t).length>0){const i=Object.keys(t)[0];e.push({key:i,value:t[i]})}return e},[]),""==this.ruleForm.tem_frames&&(this.ruleForm.tem_frames="[27,37]"),null!=this.ruleForm.confidence&&""!=this.ruleForm.confidence||(this.ruleForm.confidence="80"),this.drawLineOpen="2"==this.ruleForm.draw_type,this.image_draw_type=this.ruleForm.image_draw_type,this.resolution=this.ruleForm.img_resolution,this.ruleForm.resource_id_old=this.ruleForm.resource_id,this.handleTimesData(this.resolution),this.ruleForm.mine_name=this.ruleForm.Mine_id,this.shield_status=Number(e.data.datalist.shield_status),this.dialogVisible=!0,this.handleSelect(),this.handleChangeSf(this.ruleForm.Algorithm_library_id),this.ruleForm.equipment_name=e.data.datalist.Equipment_id,this.handleimg(),"2"==this.ruleForm.draw_type){let t=JSON.parse(e.data.datalist.conf_area.replace(/'/g,'"')),i=[],a=[];for(let e=0;e<t.length;e++){for(let a=0;a<t[e].length;a++){let l=t[e][a].x/this.timesX,s=t[e][a].y/this.timesY;i.push({x:l,y:s})}a.push(i),i=[]}this.mark_list3=[...a]}else{let t=JSON.parse(e.data.datalist.conf_area.replace(/'/g,'"')),i=[],a=[];for(let e=0;e<t.length;e++){for(let a=0;a<t[e].length;a++){let l=t[e][a].x/this.timesX,s=t[e][a].y/this.timesY;i.push({x:l,y:s,type:t[e][a].type,color:t[e][a].color})}a.push(i),i=[]}this.mark_list=[...a]}(()=>{let t=JSON.parse(e.data.datalist.template_list_area.replace(/'/g,'"')),i=[],a=[];for(let e=0;e<t.length;e++){for(let a=0;a<t[e].length;a++){let l=t[e][a].x/this.timesX,s=t[e][a].y/this.timesY;i.push({x:l,y:s,type:t[e][a].type,color:t[e][a].color})}a.push(i),i=[]}this.mark_list_model=[...a]})();let t=e.data.datalist.tem_conf_area;this.$http.get(this.$url.url_5000+"/model_view/equipment_one_info",{params:{equipment_id:this.ruleForm.equipment_name}}).then(e=>{if(console.log(e),"201"==e.data.data.equipment_code){this.area2=!0;let e=JSON.parse(t.replace(/'/g,'"')),i=[];for(let t=0;t<e[0].length;t++){let a=e[0][t].x/this.timesX,l=e[0][t].y/this.timesY;i.push({x:a,y:l})}this.mark_list2=[i],this.initCanvas2()}else this.area2=!1})}}).catch((function(e){console.log(e)}))},findModelBigDict(e){this.modelOptions.forEach(t=>{let i=t.children.find(t=>t.id==e);i&&this.getModelSmallDict([t.model_id])})},handleClose(){this.$refs.ruleForms.resetFields(),this.imgurl="",this.$nextTick(()=>{this.dialogVisible=!1})},handleClose2(){this.dialogVisible2=!1,this.handleUpdateList()},handleClose2_model(){this.dialogVisible2_model=!1,this.handleUpdateList_model()},handleClose3(){this.dialogVisible3=!1},handleClose4(){this.stopVideo(),this.dialogVisible4=!1,clearInterval(this.checkStatusTime),this.flvPlayer&&this.flvPlayer.destroy&&this.flvPlayer.destroy()},handleClose5(){this.dialogVisible5=!1},initCanvas(){this.$nextTick(()=>{let e=this.$refs.mycanvas;e.width="640",e.height="360";let t=e.getContext("2d");t.strokeStyle="red",e.style.cursor="crosshair";let i=this.mark_list,a=this.coordinates;Object(o["a"])(e,i,this.handleChooseType,a)})},initCanvas_model(){this.$nextTick(()=>{let e=this.$refs.mycanvas_model;e.width="640",e.height="360";let t=e.getContext("2d");t.strokeStyle="red",e.style.cursor="crosshair";let i=this.mark_list_model,a=this.coordinates_model;Object(o["a"])(e,i,this.handleChooseType_model,a)})},initCanvas2(){this.$nextTick(()=>{let e=this.$refs.mycanvas2;e.width="640",e.height="360";let t=e.getContext("2d");t.strokeStyle="red",e.style.cursor="crosshair";let i=this.mark_list2,a=this.coordinates2;Object(n["a"])(e,i,a)})},initCanvas4(){this.$nextTick(()=>{let e=this.$refs.mycanvas;e.width="640",e.height="360";let t=e.getContext("2d");t.strokeStyle="red",e.style.cursor="crosshair";let i=this.mark_list3,a=this.coordinates3;Object(m["a"])(e,i,a)})},tableCanvas(e,t,i,a){var l=a.split("x"),s=parseInt(l[0],10),o=parseInt(l[1],10);this.$nextTick(()=>{let i=this.$refs["tableCanvas_"+e];i.width="96",i.height="54";let a=i.getContext("2d");a.strokeStyle="red";let l=parseInt(s/96,10),n=parseInt(o/54,10),m=t,d=[],h=[];for(let e=0;e<m.length;e++){for(let t=0;t<m[e].length;t++){let i=Number(m[e][t].x)/l,a=Number(m[e][t].y)/n;d.push({x:i,y:a,color:m[e][t].color})}h.push(d),d=[]}Object(r["a"])(i,[...h])})},tableCanvas(e,t,i,a){var l=a.split("x"),s=parseInt(l[0],10),o=parseInt(l[1],10);this.$nextTick(()=>{let i=this.$refs["tableCanvas_"+e];i.width="96",i.height="54";let a=i.getContext("2d");a.strokeStyle="red";let l=s/96,n=o/54,m=t,d=[],h=[];for(let e=0;e<m.length;e++){for(let t=0;t<m[e].length;t++){let i=Number(m[e][t].x)/l,a=Number(m[e][t].y)/n;d.push({x:i,y:a,color:m[e][t].color})}h.push(d),d=[]}Object(r["a"])(i,[...h])})},tableCanvasMax(e,t,i,a,l){if(window.PlatformCountGeometry&&window.PlatformCountGeometry.normalized(i)){this.$nextTick(()=>{let countCanvas=this.$refs["tableCanvas_tableMax"];if(Array.isArray(countCanvas))countCanvas=countCanvas[0];if(countCanvas)window.PlatformCountGeometry.render(countCanvas,t,i,l,{width:800,height:400,thumbnail:false});});return;}var s=l.split("x"),o=parseInt(s[0],10),r=parseInt(s[1],10);this.$nextTick(()=>{let e=this.$refs["tableCanvas_tableMax"];if(!e)return;e.width="800",e.height="400";let a=e.getContext("2d"),l=o/800,s=r/400;if(a.clearRect(0,0,800,400),t&&t.length>0)for(let i=0;i<t.length;i++)if(!(t[i].length<3)){a.beginPath(),a.strokeStyle=t[i][0].color||"#f00",a.lineWidth=2,a.moveTo(t[i][0].x/l,t[i][0].y/s);for(let e=1;e<t[i].length;e++)a.lineTo(t[i][e].x/l,t[i][e].y/s);a.closePath(),a.stroke()}if(i&&i.p1&&i.p2)try{const e={x:Number(i.p1.x)/l,y:Number(i.p1.y)/s},t={x:Number(i.p2.x)/l,y:Number(i.p2.y)/s};e.x=Math.min(800,Math.max(0,e.x)),e.y=Math.min(400,Math.max(0,e.y)),t.x=Math.min(800,Math.max(0,t.x)),t.y=Math.min(400,Math.max(0,t.y)),a.beginPath(),a.moveTo(e.x,e.y),a.lineTo(t.x,t.y),a.strokeStyle="#ffd700",a.lineWidth=2,a.stroke();const o=t.x-e.x,r=t.y-e.y,n=Math.sqrt(o*o+r*r);if(n>0){const l=o/n,s=r/n,m=70,d=(e.x+t.x)/2,h=(e.y+t.y)/2;let c,p,_,u,g=d-s*m,f=h+l*m,b=d+s*m,y=h-l*m;g=Math.min(780,Math.max(20,g)),f=Math.min(380,Math.max(20,f)),b=Math.min(780,Math.max(20,b)),y=Math.min(380,Math.max(20,y)),"left"===i.direction?(c="IN",p="OUT",_="#44ff44",u="#ff4444"):(i.direction,c="OUT",p="IN",_="#ff4444",u="#44ff44");const v=(e,t,i,l,s)=>{a.strokeStyle=s,a.fillStyle=s,a.lineWidth=2;const o=10,r=Math.atan2(l-t,i-e);a.beginPath(),a.moveTo(e,t),a.lineTo(i,l),a.stroke(),a.beginPath(),a.moveTo(i,l);let n=i-o*Math.cos(r-Math.PI/6),m=l-o*Math.sin(r-Math.PI/6);a.lineTo(n,m),a.moveTo(i,l);let d=i-o*Math.cos(r+Math.PI/6),h=l-o*Math.sin(r+Math.PI/6);a.lineTo(d,h),a.stroke()},x=(e,t,i,l)=>{a.font="bold 18px Arial",a.textAlign="center",a.fillStyle=l,a.fillText(i,e,t-12)};v(d,h,g,f,_),v(d,h,b,y,u),x(g,f,c,_),x(b,y,p,u)}}catch(n){console.error("绘制线失败:",n)}})},handleData(){if(0==this.mark_list.length||this.drawLineOpen)this.mark_lists=[];else{let e=this.mark_list,t=[];for(let i=0;i<e.length;i++)t.push(this.mark_list[i].map(e=>({x:(e.x*this.timesX).toFixed(0),y:(e.y*this.timesY).toFixed(0),type:e.type,color:e.color})));this.mark_lists=t}if(0!=this.mark_list2.length){let e=this.mark_list2[0],t=[];for(let i=0;i<e.length;i++){let a=(e[i].x*this.timesX).toFixed(0),l=(e[i].y*this.timesY).toFixed(0);t.push({x:a,y:l})}this.mark_lists2=[t]}else this.mark_lists2=[];if(0!=this.mark_list3.length&&this.drawLineOpen){let e=this.mark_list3,t=[],i=[];for(let a=0;a<e.length;a++){for(let i=0;i<e[a].length;i++){let l=(e[a][i].x*this.timesX).toFixed(0),s=(e[a][i].y*this.timesY).toFixed(0);t.push({x:l,y:s,type:"报警"})}i.push(t),t=[]}this.mark_lists3=[...i],this.mark_lists3.sort((e,t)=>t[0].y-e[0].y)}else this.mark_lists3=[]},handleData_model(){if(0!=this.mark_list_model.length){let e=this.mark_list_model,t=[];for(let i=0;i<e.length;i++)t.push(this.mark_list_model[i].map(e=>({x:(e.x*this.timesX).toFixed(0),y:(e.y*this.timesY).toFixed(0),type:e.type,color:e.color})));this.mark_lists_model=t}else this.mark_lists_model=[]},openFullScreen(){this.loading=!0,setTimeout(()=>{this.loading=!1},2e3)},handleChangeSf(e){this.$http.get(this.$url.url_5000+"/model_view/Algorithm_type_select",{params:{id:e}}).then(e=>{this.options4=e.data.data.algorithm_data,"算法配置"==this.title?(this.ruleForm.model_template_config_id=e.data.data.model_data[0].id,this.getModelSmallDict2(e.data.data.model_type_data[0].id),this.ruleForm.template_small_id=e.data.data.template_small_data[0].id,this.handleChangeTemplateSmall()):"算法修改"==this.title&&(this.ruleForm.model_template_config_id=e.data.data.model_data[0].id,this.getModelSmallDict2(e.data.data.model_type_data[0].id),this.ruleForm.template_small_id=e.data.data.template_small_data[0].id)}).catch(e=>{console.log(e)})},handleDrewAgain(){this.mark_list3=[],this.mark_list=[],this.coordinates=[],this.coordinates3=[],this.drawLineOpen?this.initCanvas4():this.initCanvas()},handleDrewAgain_model(){this.mark_list_model=[],this.coordinates_model=[],this.initCanvas_model()},handleDrewAgain2(){this.mark_list2=[],this.coordinates2=[],this.initCanvas2()},handleChangeDrawLine(){this.mark_list3=[],this.mark_list=[],this.drawLineOpen?this.initCanvas4():this.initCanvas()},handleChangeDrawArea(){this.handleChangeDrawLine()},handleChangeStatus(data) {
      if (this.batchStatusBusy || this.statusPending[data.id]) return;
      const requestedStatus = data.status;
      const previousStatus = requestedStatus === '运行' ? '停止' : '运行';
      this.$set(this.statusPending, data.id, true);
      // Any read started before this change must not restore the previous state.
      ++this.listRequestSequence;
      clearTimeout(this.statusRefreshTimer);
      this.statusRefreshTimer = null;
      return this.$http
        .post(
          this.$url.url_5000 + "/model_view/algorithm_conf_update",
          {
            id: data.id,
            status: requestedStatus,
          },
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
          }
        )
        .then((response) => {
          if (response.data.code == 200) {
            this.$message({ type: "success", message: response.data.msg });
          } else {
            data.status = previousStatus;
            this.$message({ type: "warning", message: response.data.msg });
          }
          return this.axioss();
        })
        .catch((rek) => {
          data.status = previousStatus;
          this.$message({ type: "error", message: rek.response && rek.response.data && rek.response.data.msg || "更新运行状态失败，请刷新后重试" });
          return this.axioss();
        })
        .then(() => {
          this.$delete(this.statusPending, data.id);
        }, () => {
          this.$delete(this.statusPending, data.id);
        });
    },handleChangeShield_status(){this.handleDrewAgain()},handleChangeCanvas2(e){this.$http.get(this.$url.url_5000+"/model_view/equipment_one_info",{params:{equipment_id:e||this.ruleForm.equipment_name}}).then(e=>{"201"==e.data.data.equipment_code?(this.area2=!0,this.handleTimesData(this.resolution),this.initCanvas2()):(this.area2=!1,this.handleTimesData(this.resolution),this.mark_list3=[],this.mark_list=[],this.drawLineOpen=!1,this.initCanvas()),this.handleimg()})},handleTimesData(e){let t=640,i=360;var a=e.split("x"),l=a[0],s=a[1];this.timesX=(l/t).toFixed(2),this.timesY=(s/i).toFixed(2)},handleChooseType(){this.selectedOption="告警区域",this.title2="区域标注类型选择",this.dialogVisible2=!0},handleChooseType_model(){this.selectedOption_model="类型一",this.title2_model="模型类型选择",this.dialogVisible2_model=!0},handleUpdateList(){let e={"I级报警":"#FF0000","类型一":"#67C23A","类型二":"#FFA500","类型三":"#FCFF00"};this.mark_list[this.mark_list.length-1]=this.mark_list[this.mark_list.length-1].map(t=>({...t,type:this.selectedOption,color:e[this.selectedOption]})),this.coordinates=[],this.initCanvas(),this.dialogVisible2=!1},handleUpdateList_model(){let e={"类型一":"#FF0000","类型二":"#FFA500","类型三":"#FCFF00"};this.mark_list_model[this.mark_list_model.length-1]=this.mark_list_model[this.mark_list_model.length-1].map(t=>({...t,type:this.selectedOption_model,color:e[this.selectedOption_model]})),this.coordinates_model=[],this.initCanvas_model(),this.dialogVisible2_model=!1},handleDeleteList(){this.coordinates=[],this.coordinates2=[],this.coordinates3=[],this.mark_list.pop()},handleDeleteList_model(){this.coordinates_model=[],this.mark_list_model.pop()},handleOpenHistory(e){this.title3="历史信息记录",this.dialogVisible3=!0,this.historyKey++,e?this.$nextTick(()=>{this.$refs.historyTable.historyValue="2",this.$refs.historyTable.queryParams={id:e},this.$refs.historyTable.axioss2()}):this.$nextTick(()=>{this.$refs.historyTable.historyValue="2",this.$refs.historyTable.axioss()})},handleCloseDialog(){this.dialogVisible=!1},handleOpenSpfx(e){this.$http.get(_["a"].getAlgConfVideo,{params:{config_id:e.id,width:360,height:200,frame_r:5,baud_b:1200,stream_data_flag:1}}).then(e=>{200==e.data.code&&(this.$message.success(e.data.message),this.dialogVisible4=!0,this.checkStatusTime=setInterval(()=>{this.startCheckStatus()},1e3))}).catch(e=>{console.log(e)})},startCheckStatus(){this.$http.get(_["a"].getAlgStatusVideo).then(e=>{203==e.data.code?(clearInterval(this.checkStatusTime),this.$message.warning("无法查看")):200==e.data.code&&(clearInterval(this.checkStatusTime),this.playVideo(e.data.video_type))}).catch(e=>{console.log(e)})},playVideo(e){if(p.a.isSupported()){const t=this.$refs.videoPlayer;this.flvPlayer=p.a.createPlayer({type:"flv",url:e}),this.flvPlayer.attachMediaElement(t),this.flvPlayer.load(),this.flvPlayer.play()}else this.$message.warning("浏览器不支持 FLV.js")},stopVideo(){this.$http.get(_["a"].stopVideoSfgl,{params:{stream_data_flag:3}}).then(e=>{this.flvPlayer&&this.flvPlayer.destroy&&this.flvPlayer.destroy()}).catch(e=>{console.log(e)})},stepUp(){if(document.getElementById("stepDialog").click(),this.stepActive>0){const e=this.$loading({lock:!0,text:"Loading",spinner:"el-icon-loading",background:"rgba(0, 0, 0, 0.7)"});this.stepActive--,e.close()}},stepNext(){if(document.getElementById("stepDialog").click(),this.stepActive<=2){const e=this.$loading({lock:!0,text:"Loading",spinner:"el-icon-loading",background:"rgba(0, 0, 0, 0.7)"});this.stepActive++,e.close()}},updateConfName(){const{equipment_name:e,Algorithm_library_id:t}=this.ruleForm;console.log(e,t);let i="",a="";if(t){const e=this.options3.find(e=>e.id===t);i=e?e.algorithm_name:""}if(e)for(let l of this.options2)if(Array.isArray(l.children)){const t=l.children.find(t=>t.id===e);t&&(a=t.equipment_name)}e&&t?(this.ruleForm.conf_name=`${a}-${i}`,this.$http.post(s["d"],{conf_name:this.ruleForm.conf_name}).then(e=>{400==e.data.code?(this.modelNameOpen=!0,this.modelNamemsg=e.data.msg):(this.modelNamemsg=e.data.msg,this.modelNameOpen=!1)}).catch(e=>{console.log(e)})):this.ruleForm.conf_name="",""==this.ruleForm.conf_name||null==this.ruleForm.conf_name||void 0==this.ruleForm.conf_name?(this.conf_name_note="",this.conf_name_type=!1,this.ruleForm.conf_name=""):(this.conf_name_note=this.ruleForm.conf_name,this.conf_name_type=!0,this.ruleForm.conf_name="")},handlesearchModelName(){this.$http.post(s["d"],{conf_name:this.ruleForm.conf_name}).then(e=>{400==e.data.code?(this.modelNameOpen=!0,this.modelNamemsg=e.data.msg):(this.modelNamemsg=e.data.msg,this.modelNameOpen=!1)}).catch(e=>{console.log(e)})},handleChangeTemplateSmall(){this.$http.get(u["a"].getModelSmallDetail,{params:{id:this.ruleForm.template_small_id}}).then(e=>{200==e.data.code?this.ruleForm.template_data=e.data.data.list_data.reduce((e,t)=>{if(Object.keys(t).length>0){const i=Object.keys(t)[0];e.push({key:i,value:t[i]})}return e},[]):this.ruleForm.template_data=[]}).catch(e=>{this.ruleForm.template_data=[],console.log(e)})},removeItem(e){this.ruleForm.template_data.splice(e,1)},addItem(){this.ruleForm.template_data.push({key:"",value:""})},getModelSmallDetail(){return this.ruleForm.template_data.map(e=>{const t={};return t[e.key]=e.value,t})},handleChangeLabelList(){console.log("slect选中值输出====",this.ruleForm.label_list),0!=this.ruleForm.label_list.length&&(this.ruleForm.test_type_id=this.options4.find(e=>e.test_type_ename==this.ruleForm.label_list[0]).id)},handleOpenTableImg(e){this.dialogVisible5=!0,this.analysisId=e;let t=this.tableData.find(t=>t.id==e);this.analysisSrc=roiTaskSnapshotPath(t);let i=[];t.conf_area&&"[]"!=t.conf_area&&(i=JSON.parse(t.conf_area.replace(/'/g,'"')));let a=null;if(t.cross_line_area&&""!==t.cross_line_area&&"{}"!==t.cross_line_area)try{a="string"===typeof t.cross_line_area?JSON.parse(t.cross_line_area.replace(/'/g,'"')):t.cross_line_area}catch(l){console.error("解析线数据失败:",l)}this.tableCanvasMax(t.id,i,a,t.draw_type,t.img_resolution)},handleUpImg(){let e=this.tableData.findIndex(e=>e.id==this.analysisId);if(0==e)this.$message({type:"success",message:"当前是第一条信息！！！"});else{e-=1,this.analysisId=this.tableData[e].id,this.analysisSrc=roiTaskSnapshotPath(this.tableData[e]);let i=[];this.tableData[e].conf_area&&"[]"!=this.tableData[e].conf_area&&(i=JSON.parse(this.tableData[e].conf_area.replace(/'/g,'"')));let a=null;if(this.tableData[e].cross_line_area&&""!==this.tableData[e].cross_line_area&&"{}"!==this.tableData[e].cross_line_area)try{a="string"===typeof this.tableData[e].cross_line_area?JSON.parse(this.tableData[e].cross_line_area.replace(/'/g,'"')):this.tableData[e].cross_line_area}catch(t){console.error("解析线数据失败:",t)}this.tableCanvasMax(this.tableData[e].id,i,a,this.tableData[e].draw_type,this.tableData[e].img_resolution)}},handleNextImg(){let e=this.tableData.findIndex(e=>e.id==this.analysisId);if(e==this.tableData.length-1)this.$message({type:"success",message:"当前是最后一条信息！！！"});else{e+=1,this.analysisId=this.tableData[e].id,this.analysisSrc=roiTaskSnapshotPath(this.tableData[e]);let i=[];this.tableData[e].conf_area&&"[]"!=this.tableData[e].conf_area&&(i=JSON.parse(this.tableData[e].conf_area.replace(/'/g,'"')));let a=null;if(this.tableData[e].cross_line_area&&""!==this.tableData[e].cross_line_area&&"{}"!==this.tableData[e].cross_line_area)try{a="string"===typeof this.tableData[e].cross_line_area?JSON.parse(this.tableData[e].cross_line_area.replace(/'/g,'"')):this.tableData[e].cross_line_area}catch(t){console.error("解析线数据失败:",t)}this.tableCanvasMax(this.tableData[e].id,i,a,this.tableData[e].draw_type,this.tableData[e].img_resolution)}}},mounted(){this.axioss(),this.loadAlgorithmListOptions()},beforeDestroy() {
    ++this.listRequestSequence;
    clearTimeout(this._algorithmSearchTimer);
    if (this._algorithmListController) this._algorithmListController.abort();
    clearTimeout(this.statusRefreshTimer);
    this.statusRefreshTimer = null;
    this.stopVideo()
  },destroyed(){this.stopVideo()}},f=g,b=(i("6e4f"),i("2877")),y=Object(b["a"])(f,a,l,!1,null,"78597ddd",null);y.exports.mixins=(y.exports.mixins||[]).concat([algorithmRuntimeHealthMixin]);t["default"]=y.exports},a640:function(e,t,i){"use strict";var a=i("d039");e.exports=function(e,t){var i=[][e];return!!i&&a((function(){i.call(null,t||function(){return 1},1)}))}},d58f:function(e,t,i){"use strict";var a=i("59ed"),l=i("7b0b"),s=i("44ad"),o=i("07fa"),r=TypeError,n=function(e){return function(t,i,n,m){var d=l(t),h=s(d),c=o(d);a(i);var p=e?c-1:0,_=e?-1:1;if(n<2)while(1){if(p in h){m=h[p],p+=_;break}if(p+=_,e?p<0:c<=p)throw new r("Reduce of empty array with no initial value")}for(;e?p>=0:c>p;p+=_)p in h&&(m=i(m,h[p],p,d));return m}};e.exports={left:n(!1),right:n(!0)}}}]);



//# sourceMappingURL=chunk-32a3ec07.322b5c1d.js.map
