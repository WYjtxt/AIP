(function (root) {
  'use strict';

  /* platform-auto-token-v1 */
  var autoDefaults = {login_url:'',method:'POST',body_format:'json',body_json:'{"username":"{{username}}","password":"{{password}}"}',headers_json:'{}',
    token_path:'data.access_token',expires_path:'',ttl_seconds:3600,renew_before_seconds:60,token_header:'Authorization',token_prefix:'Bearer ',
    refresh_url:'',refresh_body_json:'{"refresh_token":"{{refresh_token}}"}',refresh_token_path:''};
  function autoDraft(settings) {
    var value=Object.assign({},autoDefaults),saved=settings&&settings.auto_token||{};
    Object.keys(autoDefaults).forEach(function(k){if(saved[k]!==undefined)value[k]=saved[k];});
    ['body_json','headers_json','refresh_body_json'].forEach(function(k){if(saved[k+'_configured'])value[k]='';});
    return value;
  }
  function autoFields(h,vm) {
    var a=vm.draft.auto_token,saved=vm.status.settings.auto_token||{};
    function text(key,label,hint,type) {return field(h,label,h(type==='json'?'textarea':'input',{
      attrs:{type:type==='number'?'number':'text',rows:4,disabled:vm.busy,autocomplete:'off','aria-label':label,
        placeholder: type==='json'?(saved[key+'_configured']?'已保存；留空保留，修改时请填写完整 JSON':autoDefaults[key]):undefined},
      domProps:{value:a[key]},on:{input:function(e){vm.$set(a,key,e.target.value);}}}),hint);}
    function select(key,label,choices) {return field(h,label,h('select',{attrs:{disabled:vm.busy,'aria-label':label},domProps:{value:a[key]},
      on:{change:function(e){vm.$set(a,key,e.target.value);}}},choices.map(function(x){return h('option',{attrs:{value:x[0]}},x[1]);})));}
    return [h('p',{class:'ai-push-detail-note'},'发送时自动获取并缓存 Token，到期前自动更新；接收端返回 401 时自动更新并重试一次。登录接口未确认时，可先暂停推送后保存草稿。'),
      text('login_url','Token 登录接口地址','填写接收方提供的完整 HTTP 或 HTTPS 登录地址。'),
      h('div',{class:'ai-push-form-row'},[select('method','登录请求方法',[['POST','POST'],['GET','GET']]),select('body_format','登录参数格式',[['json','JSON'],['form','表单（Form）']])]),
      text('body_json','登录参数（JSON 对象）','按接收方字段名填写；{{username}} 和 {{password}} 分别使用上方账号和密码。参数和请求头保存后不回显。','json'),
      text('headers_json','登录附加请求头（JSON 对象）','例如应用标识等；没有附加请求头时填写 {}。','json'),
      h('div',{class:'ai-push-form-row'},[text('token_path','Token 返回字段','例如 token、access_token 或 data.access_token。'),text('expires_path','有效期返回字段（可选）','例如 expires_in；值须为剩余秒数。留空使用固定有效期。')]),
      h('div',{class:'ai-push-form-row'},[text('ttl_seconds','固定有效期（秒）','未填写有效期返回字段时使用。','number'),text('renew_before_seconds','提前更新时间（秒）','短有效期会自动缩短提前更新时间。','number')]),
      h('div',{class:'ai-push-form-row'},[text('token_header','报警 Token 请求头名称','默认 Authorization；也可按接收端要求填写。'),text('token_prefix','Token 前缀','默认 Bearer 后有一个空格；无需前缀时清空。')]),
      h('details',[h('summary','可选：Refresh Token 接口'),text('refresh_url','Token 刷新接口地址（可选）','留空时，Token 到期后自动重新登录。刷新请求使用 POST 和上方参数格式、附加请求头。'),
        text('refresh_token_path','Refresh Token 返回字段（可选）','例如 data.refresh_token；登录和刷新使用相同的返回字段规则。'),
        text('refresh_body_json','刷新参数（JSON 对象）','使用 {{refresh_token}} 填入接口返回的刷新令牌。','json')])];
  }

  var states = {pending: '待发送', sending: '发送中', retry: '等待重试', failed: '需处理', sent: 'HTTP 接收成功', quarantined: '数据格式异常'};
  function base() { return String(root.wgParameter && root.wgParameter.url_5000 || '').replace(/\/$/, '') + '/platform_ops/push'; }
  function result(response) {
    var body = response && response.data;
    if (!body || Number(body.code) !== 200) throw new Error(body && body.msg || '操作失败，请稍后重试');
    return body;
  }
  function errorText(error) { return error && error.response && error.response.data && error.response.data.msg || error && error.message || '请求失败，请检查网络'; }
  function date(value) { return value ? new Date(Number(value) * 1000).toLocaleString('zh-CN', {hour12: false}) : '—'; }
  function control(h, label, action, disabled, primary) {
    return h('button', {class: ['ai-push-button', primary && 'is-primary'], attrs: {type: 'button', disabled: !!disabled}, on: {click: action}}, label);
  }
  function field(h, label, input, hint) { return h('label', {class: 'ai-push-field'}, [h('span', label), input, hint && h('small', hint)]); }
  function input(h, vm, name, type, attrs) {
    return h('input', {attrs: Object.assign({type: type || 'text', disabled: vm.busy, autocomplete: 'off'}, attrs || {}),
      domProps: {value: vm.draft[name]}, on: {input: function (event) { vm.draft[name] = event.target.value; }}});
  }
  function metric(h, value, label, warning) { return h('div', {class: ['ai-push-metric', warning && 'has-warning']}, [h('strong', String(value || 0)), h('span', label)]); }
  function jsonText(value) { return typeof value === 'string' ? value : JSON.stringify(value == null ? null : value, null, 2); }
  function entry(h, label, value) { return h('div', {class: 'ai-push-detail-entry'}, [h('dt', label), h('dd', value == null || value === '' ? '—' : String(value))]); }
  function code(h, value, label) { return h('pre', {class: 'ai-push-code', attrs: {tabindex: '0', 'aria-label': label}}, jsonText(value)); }
  var outcomes = {in_flight: '请求处理中', http_accepted: 'HTTP 接收成功', http_error: 'HTTP 接收失败', transport_error: '连接或发送失败', interrupted: '发送中断，结果待核实'};
  root.AiMonitorDataPush = {
    name: 'DataPushManagement',
    data: function () { return {status: null, draft: {target_url: '', enabled: true, timeout_seconds: '5', auth_mode: 'none', auth_username: '', auth_password: '', auth_token: '', auto_token: autoDraft(null)},
      loadedRevision: null, loading: false, loadError: '', busy: false, error: '', success: '', timer: null, disposed: false, tab: 'recent', selected: [], newConfig: false,
      detailId: null, detail: null, detailLoading: false, detailError: '', detailGeneration: 0, detailOpener: null, detailBefore: null}; },
    created: function () {
      this.load(false);
      var vm = this;
      this.timer = root.setInterval(function () { if (!root.document.hidden && !vm.busy) { vm.load(true); if (vm.detailId !== null) vm.loadDetail(true); } }, 10000);
    },
    beforeDestroy: function () { this.disposed = true; this.detailGeneration++; root.clearInterval(this.timer); },
    computed: {
      dirty: function () {
        var settings = this.status && this.status.settings;
        return !!(settings && (this.draft.target_url !== settings.target_url || this.draft.enabled !== settings.enabled || Number(this.draft.timeout_seconds) !== Number(settings.timeout_seconds) ||
          (this.draft.auth_mode === 'auto_token' && JSON.stringify(this.draft.auto_token) !== JSON.stringify(autoDraft(settings))) || this.draft.auth_mode !== settings.auth_mode || this.draft.auth_username || this.draft.auth_password || this.draft.auth_token));
      },
      records: function () { return this.status ? this.status[this.tab === 'failures' ? 'failures' : 'recent'] || [] : []; },
      canTest: function () { return !!(this.status && this.status.settings.enabled && this.status.worker.healthy && !this.dirty && !this.newConfig); },
      canDeleteSelected: function () {
        var vm = this;
        if (!this.status || this.status.can_delete !== true || !this.selected.length || this.selected.length > 200) return false;
        var failed = this.records.filter(function (row) {return row.state === 'failed';}).map(function (row) {return row.id;});
        return this.selected.every(function (id) {return failed.indexOf(id) >= 0;});
      },
      selectedRetryable: function () { var vm = this; return this.records.filter(function (row) {return vm.selected.indexOf(row.id) >= 0 && (row.state === 'failed' || row.state === 'retry');}).map(function (row) {return row.id;}); },
    },
    methods: {
      adopt: function (settings) {
        this.draft = {target_url: settings.target_url, enabled: settings.enabled, timeout_seconds: String(settings.timeout_seconds), auth_mode: settings.auth_mode,
          auth_username: '', auth_password: '', auth_token: '', auto_token: autoDraft(settings)};
        this.loadedRevision = settings.revision; this.newConfig = false;
      },
      load: function (quiet) {
        if (this.loading || this.disposed) return;
        this.loading = true; var vm = this;
        if (!quiet) this.error = '';
        this.$http.get(base() + '/status').then(function (response) {
          if (vm.disposed) return;
          var body = result(response), wasDirty = vm.dirty;
          vm.loadError = '';
          vm.status = body.data;
          if (vm.loadedRevision === null || (!wasDirty && !vm.busy)) vm.adopt(body.data.settings);
          else if (vm.loadedRevision !== body.data.settings.revision) vm.newConfig = true;
          var available = (body.data.failures || []).concat(body.data.recent || []).map(function (row) {return row.id;});
          vm.selected = vm.selected.filter(function (id) {return available.indexOf(id) >= 0;});
        }).catch(function (error) {if (!vm.disposed) vm.loadError = errorText(error);}).then(function () {vm.loading = false;});
      },
      action: function (path, data, done) {
        if (this.busy) return;
        var vm = this; this.busy = true; this.error = ''; this.success = '';
        this.$http.post(base() + path, data).then(function (response) {
          if (vm.disposed) return;
          var body = result(response); vm.success = body.msg || '操作成功'; if (done) done(body.data);
        }).catch(function (error) {if (!vm.disposed) vm.error = errorText(error);}).then(function () {vm.busy = false; vm.load(true);});
      },
      save: function () {
        var vm = this;
        if (!this.status || this.newConfig) return;
        var body = {revision: this.loadedRevision, target_url: this.draft.target_url, enabled: this.draft.enabled,
          timeout_seconds: Number(this.draft.timeout_seconds), auth_mode: this.draft.auth_mode};
        ['auth_username', 'auth_password', 'auth_token'].forEach(function (key) {if (vm.draft[key]) body[key] = vm.draft[key];});
        if (this.draft.auth_mode === 'auto_token') {
          body.auto_token = Object.assign({}, this.draft.auto_token);
          ['ttl_seconds','renew_before_seconds'].forEach(function(k){body.auto_token[k]=Number(body.auto_token[k]);});
        }
        this.action('/settings', body, function (settings) {vm.status.settings = settings; vm.adopt(settings);});
      },
      discard: function () { if (this.status) this.adopt(this.status.settings); this.error = ''; this.success = ''; },
      test: function () {
        var vm = this;
        this.$confirm('将向已保存的接收地址发送一条明确标记的测试数据，接收端可能生成测试记录。是否发送？', '发送测试数据',
          {confirmButtonText: '发送测试数据', cancelButtonText: '取消', type: 'warning'})
          .then(function () {vm.action('/test', {}, function () {vm.tab = 'recent'; vm.selected = [];});}).catch(function () {});
      },
      retry: function (all) {
        var vm = this, count = this.selectedRetryable.length;
        if (this.dirty || this.newConfig) {this.error = '请先保存或取消配置修改，再重试'; return;}
        this.$confirm((all ? '全部等待重试及需处理的记录' : '选中的 ' + count + ' 条记录') + '将使用当前已保存的地址和鉴权重新发送。', '重试发送',
          {confirmButtonText: '重新排队', cancelButtonText: '取消', type: 'warning'})
          .then(function () {vm.action('/retry', all ? {all_failed: true} : {ids: vm.selectedRetryable}, function () {vm.selected = [];});}).catch(function () {});
      },
      deleteSelected: function () {
        if (this.busy || !this.canDeleteSelected) return;
        var vm = this, ids = this.selected.slice();
        this.$confirm('将永久删除选中的 ' + ids.length + ' 条失败推送记录及其发送详情。对应报警将保留。', '删除失败推送记录',
          {confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning', distinguishCancelAndClose: true})
          .then(function () {
            vm.action('/delete', {ids: ids}, function () {
              vm.selected = vm.selected.filter(function (id) {return ids.indexOf(id) < 0;});
            });
          }).catch(function () {});
      },
      toggle: function (id, enabled) { var index = this.selected.indexOf(id); if (enabled && index < 0) this.selected.push(id); else if (!enabled && index >= 0) this.selected.splice(index, 1); },
      openDetail: function (id, event) {
        this.detailGeneration++; this.detailId = id; this.detail = null; this.detailError = ''; this.detailLoading = false; this.detailBefore = null;
        this.detailOpener = event && event.currentTarget || root.document.activeElement; this.loadDetail(false);
        var vm = this; this.$nextTick(function () { if (vm.$refs.detailClose) vm.$refs.detailClose.focus(); });
      },
      closeDetail: function () {
        this.detailGeneration++; this.detailId = null; this.detail = null; this.detailLoading = false; this.detailError = ''; this.detailBefore = null;
        var opener = this.detailOpener; this.detailOpener = null; if (opener && opener.isConnected && opener.focus) opener.focus();
      },
      detailKey: function (event) {
        if (event.key === 'Escape') { event.preventDefault(); this.closeDetail(); return; }
        if (event.key !== 'Tab' || !this.$refs.detailDialog) return;
        var controls = this.$refs.detailDialog.querySelectorAll('button:not([disabled]), [tabindex="0"]');
        if (!controls.length) return;
        if (event.shiftKey && root.document.activeElement === controls[0]) { event.preventDefault(); controls[controls.length - 1].focus(); }
        else if (!event.shiftKey && root.document.activeElement === controls[controls.length - 1]) { event.preventDefault(); controls[0].focus(); }
      },
      loadDetail: function (quiet) {
        if (this.detailId === null || this.detailLoading || this.disposed) return Promise.resolve();
        var vm = this, id = this.detailId, generation = this.detailGeneration; this.detailLoading = true;
        if (!quiet) this.detailError = '';
        return this.$http.get(base() + '/deliveries/' + encodeURIComponent(id) + '?limit=10' + (this.detailBefore ? '&before_attempt_id=' + encodeURIComponent(this.detailBefore) : '')).then(function (response) {
          if (vm.disposed || generation !== vm.detailGeneration) return;
          vm.detail = result(response).data; vm.detailError = '';
        }).catch(function (error) { if (!vm.disposed && generation === vm.detailGeneration) vm.detailError = errorText(error); })
          .then(function () { if (generation === vm.detailGeneration) vm.detailLoading = false; });
      },
      detailPage: function (before) {
        if (this.detailLoading) return;
        this.detailGeneration++; this.detailBefore = before || null; this.detail = null; this.detailError = ''; return this.loadDetail(false);
      },
      detailView: function (h) {
        if (this.detailId === null) return null;
        var vm = this, detail = this.detail, delivery = detail && detail.delivery || {}, source = delivery.source || {}, payload = detail && detail.payload || {};
        var content = [h('div', {class: 'ai-push-heading'}, [h('div', [h('h3', {attrs: {id: 'ai-push-detail-title'}}, '报警推送详情 · ' + this.detailId), h('p', '队列内容、实际请求与接收端回执')]),
          h('div', {class: 'ai-push-actions'}, [control(h, this.detailLoading ? '刷新中…' : '刷新详情', function () { vm.loadDetail(false); }, this.detailLoading),
            h('button', {ref: 'detailClose', class: 'ai-push-button', attrs: {type: 'button', 'aria-label': '关闭报警推送详情'}, on: {click: this.closeDetail}}, '关闭')])]),
          h('p', {class: 'ai-push-detail-note'}, 'HTTP 2xx 只表示接收端已接受请求，不能证明业务已入库。下方展示接收端实际返回的回执；敏感信息会脱敏。')];
        if (this.detailError) content.push(h('div', {class: 'ai-push-message is-error', attrs: {role: 'alert'}}, this.detailError));
        if (!detail) content.push(h('p', {attrs: {role: 'status'}}, this.detailLoading ? '正在读取详情…' : '详情暂不可用，请刷新重试。'));
        else {
          content.push(h('section', {class: 'ai-push-detail-section'}, [h('h4', '报警详情'), h('dl', {class: 'ai-push-detail-list'}, [entry(h, '报警摘要', delivery.title), entry(h, '设备', delivery.device_name),
            entry(h, '报警时间', payload.alarmTime), entry(h, '报警级别', payload.alarmLevel), entry(h, '设备 IP', payload.ip), entry(h, '分析类型', payload.analysis_type),
            entry(h, '统计区间开始', payload.resultCountStartTime), entry(h, '统计数量', payload.resultCount), entry(h, '本次进入人数', payload.Entering_num), entry(h, '本次离开人数', payload.Exiting_num),
            entry(h, '累计进入人数', payload.all_Entering_num), entry(h, '累计离开人数', payload.all_Exiting_num), entry(h, '报警说明', payload.warning_message),
            entry(h, '队列状态', states[delivery.state] || delivery.state), entry(h, '生成时间', date(delivery.created_at)), entry(h, '来源', {kafka: 'Kafka 报警', test: '测试数据', manual: '手动创建', unknown: '未记录'}[source.type] || '未记录'),
            entry(h, '来源事件标识', source.event_key || delivery.event_key), entry(h, '排队接收地址', delivery.target_url), entry(h, '当前重试周期次数', delivery.attempts)]),
            (payload.httpUrlList || payload.httpUrl) && h('details', [h('summary', '报警图片地址'), code(h, payload.httpUrlList || payload.httpUrl, '报警图片地址')]),
            payload.warning_video && h('details', [h('summary', '报警录像地址'), code(h, payload.warning_video, '报警录像地址')]),
            h('p', {class: 'ai-push-note'}, '报警字段以队列中的完整 JSON 为准。来源事件标识用于排查重复消息，不代表 Kafka 原始消息全文。')]));
          content.push(h('section', {class: 'ai-push-detail-section'}, [h('h4', '排队的报警 JSON'), code(h, detail.payload_json == null ? detail.payload : detail.payload_json, '排队的报警 JSON')]));
          var attempts = detail.attempts || [];
          content.push(h('section', {class: 'ai-push-detail-section'}, [h('h4', '请求与回执记录（本页 ' + attempts.length + ' 条，已留存 ' + Number(detail.attempts_total || attempts.length) + ' 条）'), h('p', {class: 'ai-push-note'}, detail.history_note || '旧记录未采集的请求与回执无法补录。'),
            !attempts.length && h('p', {class: 'ai-push-empty'}, delivery.attempts ? '此记录的历史尝试未留存详情，无法还原实际请求或回执。' : '尚未发送，没有实际请求和回执。'), attempts.map(function (attempt) {
              var duration = Number(attempt.finished_at) >= Number(attempt.started_at) && attempt.finished_at ? Math.round((Number(attempt.finished_at) - Number(attempt.started_at)) * 1000) + ' 毫秒' : '—';
              return h('article', {key: attempt.id, class: 'ai-push-attempt'}, [h('h4', '发送记录 ' + attempt.attempt_no + ' · ' + (outcomes[attempt.outcome] || attempt.outcome || '结果待核实')),
                h('dl', {class: 'ai-push-detail-list'}, [entry(h, '请求开始', date(attempt.started_at)), entry(h, '请求结束', date(attempt.finished_at)), entry(h, '耗时', duration), entry(h, '实际接收地址', attempt.target_url),
                  entry(h, 'HTTP 状态', attempt.response_status ? 'HTTP ' + attempt.response_status : '未收到 HTTP 响应'), entry(h, '业务入库结果', '未确认，请核对接收端回执'), entry(h, '请求 JSON SHA256', attempt.request_sha256)]),
                attempt.error && h('p', {class: 'ai-push-message is-error'}, attempt.error), h('h5', '实际发送的 JSON'), code(h, attempt.request_json, '发送记录 ' + attempt.attempt_no + ' 的实际发送 JSON'),
                h('details', [h('summary', '请求头（已脱敏）'), code(h, attempt.request_headers || {}, '请求头')]),
                h('h5', '接收端回执'), attempt.response_truncated && h('p', {class: 'ai-push-note'}, '回执内容较长，仅保留受限长度，已截断。'),
                code(h, attempt.response_body == null || attempt.response_body === '' ? '未返回响应正文' : attempt.response_body, '接收端回执正文'),
                h('details', [h('summary', '响应头（已过滤敏感信息）'), code(h, attempt.response_headers || {}, '响应头')])]);
            }), h('div', {class: 'ai-push-actions'}, [this.detailBefore && control(h, '返回最近记录', function () { vm.detailPage(null); }, this.detailLoading),
              detail.has_more && detail.next_before_attempt_id && control(h, '查看更早回执', function () { vm.detailPage(detail.next_before_attempt_id); }, this.detailLoading), h('span', {class: 'ai-push-note'}, '每页最多显示 10 条实际请求与回执。')])]));
        }
        return h('div', {class: 'ai-push-modal-backdrop', on: {click: function (event) { if (event.target === event.currentTarget) vm.closeDetail(); }}},
          [h('section', {ref: 'detailDialog', class: 'ai-push-modal', attrs: {role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'ai-push-detail-title'}, on: {keydown: this.detailKey}}, content)]);
      },
    },
    render: function (h) {
      var vm = this, status = this.status, settings = status && status.settings, counts = status && status.counts || {};
      var sections = [h('div', {class: 'ai-push-heading'}, [h('div', [h('h2', '数据推送'), h('p', '统一管理报警数据接收地址、发送状态与失败重试。')]), control(h, this.loading ? '刷新中…' : '刷新', function () {vm.load(false);}, this.loading || this.busy)])];
      if (this.error) sections.push(h('div', {class: 'ai-push-message is-error', attrs: {role: 'alert'}}, this.error));
      if (this.loadError) sections.push(h('div', {class: 'ai-push-message is-error', attrs: {role: 'alert'}}, (status ? '刷新失败，当前显示上次加载的记录。' : '读取推送记录失败。') + this.loadError));
      if (this.success) sections.push(h('div', {class: 'ai-push-message is-success', attrs: {role: 'status'}}, this.success));
      if (!status) {sections.push(h('div', {class: 'ai-push-card'}, this.loading ? '正在读取推送配置…' : '暂时无法读取推送配置，请重试。')); return h('div', {class: 'ai-push'}, sections);}
      sections.push(h('div', {class: 'ai-push-metrics'}, [metric(h, counts.pending, '待发送'), metric(h, counts.sending, '发送中'), metric(h, counts.retry, '等待重试', counts.retry > 0), metric(h, counts.failed, '需处理', counts.failed > 0), metric(h, counts.sent, 'HTTP 接收成功'), metric(h, counts.quarantined, '数据格式异常', counts.quarantined > 0)]));
      sections.push(h('div', {class: ['ai-push-service', !status.worker.healthy && 'has-warning']}, [
        h('span', {class: 'ai-push-dot'}), h('strong', status.worker.healthy ? '发送服务心跳正常' : '发送服务无有效心跳'),
        h('span', '最近心跳：' + date(status.worker.heartbeat_at)), h('span', settings.enabled ? '推送已启用' : '推送已暂停，新报警继续保留在队列中')
      ]));
      if (status.storage.free_bytes < status.limits.min_free_bytes) sections.push(h('div', {class: 'ai-push-message is-error'}, '推送存储空间不足，当前消息将保留在来源队列等待恢复。请尽快清理磁盘。'));
      var authInput = [field(h, '鉴权方式', h('select', {attrs: {disabled: this.busy}, domProps: {value: this.draft.auth_mode}, on: {change: function (event) {vm.draft.auth_mode = event.target.value;}}}, [h('option', {attrs: {value: 'none'}}, '无需鉴权'), h('option', {attrs: {value: 'bearer'}}, 'Bearer 令牌'), h('option', {attrs: {value: 'basic'}}, '账号密码（Basic）'), h('option', {attrs: {value: 'auto_token'}}, '自动登录获取 Token')]), settings.auth_configured ? '已有鉴权信息，空白输入会保留原值。' : '按接收端要求填写。')];
      if (this.draft.auth_mode === 'basic' || this.draft.auth_mode === 'auto_token') {authInput.push(field(h, '接收端账号', input(h, this, 'auth_username', 'text', {placeholder: settings.auth_configured ? '留空保留现有账号' : '请输入账号'}))); authInput.push(field(h, '接收端密码', input(h, this, 'auth_password', 'password', {placeholder: settings.auth_configured ? '留空保留现有密码' : '请输入密码', autocomplete: 'new-password'})));}
      if (this.draft.auth_mode === 'bearer') authInput.push(field(h, '接收端令牌', input(h, this, 'auth_token', 'password', {placeholder: settings.auth_configured ? '留空保留现有令牌' : '请输入令牌', autocomplete: 'new-password'})));
      if (this.draft.auth_mode === 'auto_token') authInput = authInput.concat(autoFields(h, this));
      sections.push(h('section', {class: 'ai-push-card'}, [h('h3', '接收端配置'),
        h('div', {class: 'ai-push-form'}, [field(h, '接收地址', input(h, this, 'target_url', 'url', {placeholder: 'http://接收地址:端口/接收路径', maxlength: 2048}), '填写完整地址。已有积压使用原地址；重试操作可切换到当前地址。'),
          h('div', {class: 'ai-push-form-row'}, [field(h, '推送开关', h('select', {attrs: {disabled: this.busy}, domProps: {value: String(this.draft.enabled)}, on: {change: function (event) {vm.draft.enabled = event.target.value === 'true';}}}, [h('option', {attrs: {value: 'true'}}, '启用'), h('option', {attrs: {value: 'false'}}, '暂停')])), field(h, '请求超时（秒）', input(h, this, 'timeout_seconds', 'number', {min: 1, max: 30, step: 1}), '可设置 1 至 30 秒。')])].concat(authInput)),
        this.newConfig && h('div', {class: 'ai-push-message is-error'}, '其他管理员已更新配置。请点击“重新载入配置”后再编辑。'),
        h('div', {class: 'ai-push-actions'}, [control(h, this.busy ? '处理中…' : '保存配置', this.save, this.busy || !this.dirty || this.newConfig, true), control(h, this.newConfig ? '重新载入配置' : '取消修改', this.discard, this.busy || (!this.dirty && !this.newConfig)), control(h, '发送测试数据', this.test, this.busy || !this.canTest)]),
        h('p', {class: 'ai-push-note'}, '测试会向接收端真实发送一条带测试标记的数据。保存配置后可发送。')
      ]));
      var rows = this.records.map(function (row) {
        var retryable = row.state === 'failed' || row.state === 'retry';
        return h('tr', {key: row.id}, [h('td', [h('input', {attrs: {type: 'checkbox', disabled: !retryable || vm.busy, 'aria-label': '选择记录 ' + row.id}, domProps: {checked: vm.selected.indexOf(row.id) >= 0}, on: {change: function (event) {vm.toggle(row.id, event.target.checked);}}})]),
          h('td', String(row.id)), h('td', [h('span', {class: ['ai-push-badge', 'state-' + row.state]}, states[row.state] || row.state)]),
          h('td', [h('strong', row.title), row.kind === 'test' && h('small', '测试数据'), row.device_name && h('small', row.device_name)]), h('td', String(row.attempts)),
          h('td', date(row.created_at)), h('td', [h('span', row.last_http_status ? 'HTTP ' + row.last_http_status : '—'), row.last_error && h('small', row.last_error), row.state === 'retry' && h('small', '下次：' + date(row.next_attempt_at)), row.sent_at && h('small', '送达：' + date(row.sent_at))]),
          h('td', {attrs: {title: row.target_url}}, row.target_url), h('td', [control(h, '查看详情', function (event) {vm.openDetail(row.id, event);}, false)])]);
      });
      sections.push(h('section', {class: 'ai-push-card'}, [h('div', {class: 'ai-push-heading'}, [h('h3', '发送记录'), h('div', {class: 'ai-push-actions'}, [control(h, '最近记录', function () {vm.tab = 'recent'; vm.selected = [];}, this.busy, this.tab === 'recent'), control(h, '失败与重试', function () {vm.tab = 'failures'; vm.selected = [];}, this.busy, this.tab === 'failures')])]),
        h('div', {class: 'ai-push-actions'}, [control(h, '重试选中记录', function () {vm.retry(false);}, this.busy || !this.selectedRetryable.length || this.dirty || this.newConfig, true), control(h, '重试全部失败记录', function () {vm.retry(true);}, this.busy || !(counts.failed + counts.retry) || this.dirty || this.newConfig), status.can_delete === true && control(h, '删除选中失败记录', function () {vm.deleteSelected();}, this.busy || !this.canDeleteSelected), h('span', {class: 'ai-push-note'}, '重试使用当前已保存的接收地址和鉴权。')]),
        h('div', {class: 'ai-push-table-wrap'}, [h('table', {class: 'ai-push-table'}, [h('thead', [h('tr', ['选择', '编号', '状态', '报警 / 设备', '本轮尝试次数', '生成时间', '最近结果', '接收地址', '详情'].map(function (text) {return h('th', text);}))]), h('tbody', rows.length ? rows : [h('tr', [h('td', {attrs: {colspan: 9}, class: 'ai-push-empty'}, '暂无' + (this.tab === 'failures' ? '失败或待重试' : '发送') + '记录')])])])]),
        h('p', {class: 'ai-push-note'}, (this.tab === 'failures' ? '显示最近 100 条异常记录。' : '显示最近 50 条记录。') + status.history_note),
        h('p', {class: 'ai-push-note'}, '网络异常会自动退避重试，最多 ' + status.limits.max_attempts + ' 次。格式异常的数据已隔离，不会发送。' + status.delivery_note)
      ]));
      sections.push(this.detailView(h));
      return h('div', {class: 'ai-push'}, sections);
    }
  };
}(window));
