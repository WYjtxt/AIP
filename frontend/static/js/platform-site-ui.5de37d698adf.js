/* platform-site-ui-v1: unified network configuration for the existing Vue 2 app. */
(function (root) {
  'use strict';
  var PATH = '/platform-site-config', NAME = 'platform_site_config';
  var roles = [
    ['mysql', '数据库'], ['redis', 'Redis'], ['kafka', '消息服务'], ['media', '流媒体'],
    ['analysis', '分析服务器'], ['upload', '上传服务'], ['push', '推流目标'],
    ['backend', '后端服务'], ['dispatch', '配置服务'], ['platform_callback', '平台回调'], ['aifz', 'AIFZ 外部服务']
  ];
  var modes = {node: '跟随平台地址', loopback: '本机连接', fixed: '独立地址'};
  var serviceNames = {backend: '后端服务', web: '访问网关', media: '流媒体', kafka: '消息服务', dispatch: '配置服务', 'dispatch-web': '配置访问网关', 'algorithm-master': '算法服务'};
  var active = ['queued', 'running'];
  var statuses = {queued: '等待执行', running: '正在执行', completed: '已完成', failed: '未完成'};
  var navigation = {token: null, authorized: false, promise: null, home: null};
  function api(path) { return ((root.wgParameter && root.wgParameter.url_5000) || '').replace(/\/$/, '') + '/platform_site/' + path; }
  function data(response) {
    var body = response && response.data;
    if (!body || Number(body.code) !== 200) throw new Error(body && (body.msg || body.error) || '请求未完成，请稍后重试');
    return body.data || {};
  }
  function errorText(error) { var body = error && error.response && error.response.data; return body && (body.msg || body.error) || error && error.message || '连接暂时不可用，请稍后重试'; }
  function denied(error) { return !!(error && error.response && [401, 403].indexOf(Number(error.response.status)) >= 0); }
  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function signature(value) { return JSON.stringify(value || null); }
  function mode(endpoint) { return endpoint && endpoint.ref === 'node' ? 'node' : endpoint && endpoint.ref === 'loopback' ? 'loopback' : 'fixed'; }
  function resolved(endpoint, node) { var kind = mode(endpoint); return kind === 'node' ? node : kind === 'loopback' ? '127.0.0.1' : String(endpoint && endpoint.host || ''); }
  function hostValid(value) {
    if (typeof value !== 'string' || !value || value.length > 253 || value !== value.trim()) return false;
    if (/^[0-9.]+$/.test(value)) {
      var parts = value.split('.');
      return parts.length === 4 && parts.every(function (part) { return /^(0|[1-9][0-9]{0,2})$/.test(part) && Number(part) <= 255; }) && value !== '0.0.0.0' && Number(parts[0]) < 224;
    }
    return value.split('.').every(function (part) { return /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/.test(part); });
  }
  function validate(config) {
    var found = [];
    if (!config || !config.node || !hostValid(config.node.address) || /^(localhost|127\.)/.test(config.node.address)) found.push('平台对外地址须为可访问的 IPv4 地址或主机名');
    Object.keys(config && config.services || {}).forEach(function (key) {
      var endpoint = config.services[key], kind = mode(endpoint);
      if (kind === 'fixed' && !hostValid(endpoint && endpoint.host)) found.push(label(key) + '的独立地址格式不正确');
    });
    return found;
  }
  function label(key) { var row = roles.filter(function (item) { return item[0] === key; })[0]; return row ? row[1] : key; }
  function endpointText(endpoint, node) { return modes[mode(endpoint)] + ' · ' + resolved(endpoint, node); }
  function differences(before, after) {
    var result = [];
    if (!before || !after) return result;
    if (before.node.address !== after.node.address) result.push({label: '平台对外地址', before: before.node.address, after: after.node.address});
    Object.keys(after.services || {}).forEach(function (key) {
      var old = before.services[key], next = after.services[key];
      if (signature(old) !== signature(next) || resolved(old, before.node.address) !== resolved(next, after.node.address)) {
        result.push({label: label(key), before: endpointText(old, before.node.address), after: endpointText(next, after.node.address)});
      }
    });
    return result;
  }
  function backupPath(value) { return typeof value === 'string' ? value : value && (value.path || value.backup) || ''; }
  function jobValue(value) { return value && value.job || value || null; }
  function isActive(job) { return !!(job && active.indexOf(job.status) >= 0); }
  function button(h, title, click, disabled, primary, extra) {
    return h('button', {class: ['site-config-button', primary && 'is-primary', extra], attrs: {type: 'button', disabled: !!disabled}, on: {click: click}}, title);
  }
  function field(h, title, id, value, input, disabled, detail) {
    return h('div', {class: 'site-config-field'}, [h('label', {attrs: {for: id}}, title),
      h('input', {attrs: {id: id, type: 'text', spellcheck: 'false', autocomplete: 'off', disabled: !!disabled}, domProps: {value: value}, on: {input: input}}),
      detail ? h('small', detail) : null]);
  }
  function showConfirm(vm, message, title, action) {
    return vm.$confirm(message, title, {confirmButtonText: action, cancelButtonText: '取消', type: 'warning', customClass: 'site-config-confirm'});
  }

  function networkStatus(network) {
    if (!network || network.available !== true) return '网口信息暂不可用';
    return {ready: '业务地址已就绪', missing: '业务地址未配置', down: '承载网口不可用',
      ambiguous: '地址匹配多个网口', unavailable: '尚未确认承载网口'}[(network.business || {}).status] || '尚未确认承载网口';
  }
  function linkText(iface) {
    var state = String(iface.link_state || 'UNKNOWN').toUpperCase();
    return (iface.admin_up === true ? '已启用' : iface.admin_up === false ? '未启用' : iface.active_connection_uuid ? '已启用' : '启用状态未知') + ' / ' +
      (state === 'UP' ? '链路正常' : state === 'DOWN' ? '链路断开' : '链路状态未知');
  }
  function interfaceType(iface) {
    var type = String(iface.type || 'unknown').toLowerCase();
    return {physical: '物理网口', ether: '以太网', ethernet: '以太网', bond: '聚合网口',
      vlan: 'VLAN', bridge: '网桥', loopback: '回环', veth: '虚拟以太网', tun: '隧道',
      tap: '虚拟网口', unknown: '类型未知'}[type] || type;
  }
  function collectedTime(value) {
    var date = typeof value === 'number' ? new Date(value * 1000) : new Date(value);
    return value && isFinite(date.getTime()) ? date.toLocaleString() : '—';
  }

  var networkPhases = {waiting_link: '等待接线', queued: '等待执行', applying: '正在配置地址', awaiting_confirmation: '等待从新入口确认',
    finalizing: '正在完成地址切换', awaiting_final_confirmation: '等待最终入口确认', completed: '已完成',
    rolling_back: '正在回滚', rolled_back: '已回滚', failed: '执行失败', conflict: '检测到配置冲突', cancelled: '已取消'};
  function networkActive(job) { return !!(job && (job.blocks_operations || job.status === 'conflict' && job.can_rollback || ['completed', 'rolled_back', 'failed', 'conflict', 'cancelled'].indexOf(job.status) < 0)); }
  function ipv4(value) { return typeof value === 'string' && /^[0-9.]+$/.test(value) && hostValid(value) && Number(value.split('.')[0]) > 0 && !/^127\./.test(value); }
  function networkRequestId() { var values = new Uint8Array(16), value = ''; root.crypto.getRandomValues(values); for (var i = 0; i < values.length; i += 1) value += ('0' + values[i].toString(16)).slice(-2); return value; }
  function networkPendingKey() { return 'AiMonitorNetworkJob:' + String(root.localStorage.getItem('userId') || 'current'); }
  function interfaceName(iface) { return iface && (iface.interface || iface.name) || ''; }
  function interfaceEditable(iface) { return !!(iface && iface.editable === true && (iface.physical === true || ['physical', 'ethernet', '802-3-ethernet'].indexOf(String(iface.type || '').toLowerCase()) >= 0) && !iface.internal && !iface.master); }
  function interfaceAddresses(iface, uuid) {
    var profile = (iface && iface.profiles || []).filter(function (item) { return String(item.uuid) === String(uuid); })[0];
    return (profile && profile.addresses || iface && iface.addresses || []).map(function (item) { return typeof item === 'string' ? item : item.cidr || item.address + '/' + item.prefixlen; });
  }
  function networkEntry(value) { if (typeof value !== 'string' || !value.trim()) return ''; try { var url = new root.URL(value, root.location.origin); return /^https?:$/.test(url.protocol) && !url.username && !url.password ? url.href : ''; } catch (ignore) { return ''; } }
  function validNetworkTicket(value, sameOrigin) {
    if (!value || !/^[a-f0-9]{32}$/.test(String(value.job_id || '')) || !/^[A-Za-z0-9_-]{16,1024}$/.test(String(value.token || '')) || ['candidate', 'final'].indexOf(value.phase) < 0) return false;
    try { var url = new root.URL(value.confirm_url); return url.protocol === 'https:' && !url.username && !url.password && (!sameOrigin || url.origin === root.location.origin); } catch (ignore) { return false; }
  }
  function networkHandoffLink(ticket) { if (!validNetworkTicket(ticket, false)) return ''; var url = new root.URL(ticket.confirm_url); url.hash = 'network-handoff=' + encodeURIComponent(JSON.stringify(ticket)); return url.href; }
  function bootstrapNetworkHandoff() {
    var raw = root.__AiMonitorNetworkHandoff || root.location.hash;
    try { delete root.__AiMonitorNetworkHandoff; } catch (ignore) {}
    if (typeof raw !== 'string' || raw.indexOf('#network-handoff=') !== 0) return false;
    var cleanUrl = new root.URL(root.location.href); cleanUrl.hash = ''; cleanUrl.searchParams.delete('_network_handoff');
    root.history.replaceState(null, '', cleanUrl.pathname + cleanUrl.search);
    var ticket, closed = false, timer = null, polls = 0, job = null;
    try { ticket = JSON.parse(decodeURIComponent(raw.slice('#network-handoff='.length))); } catch (ignore) {}
    var panel = root.document.createElement('section'); panel.id = 'platform-network-handoff';
    panel.style.cssText = 'position:fixed;inset:0;z-index:2147483647;background:#f4f7fb;color:#26384c;padding:8vh 8vw;box-sizing:border-box;font:16px system-ui,sans-serif;overflow:auto';
    var title = root.document.createElement('h2'), message = root.document.createElement('p'), links = root.document.createElement('p');
    title.textContent = '网络切换确认'; message.setAttribute('role', 'status'); panel.appendChild(title); panel.appendChild(message); panel.appendChild(links);
    (root.document.body || root.document.documentElement).appendChild(panel);
    function addLink(label, address) { var entry = networkEntry(address); if (!entry) return; var link = root.document.createElement('a'); link.textContent = label; link.href = entry; link.style.marginRight = '20px'; links.appendChild(link); }
    function fail(text) { root.clearTimeout(timer); ticket = null; message.textContent = text + (!job ? ' 请关闭此页返回原平台页面核对。' : ''); while (links.firstChild) links.removeChild(links.firstChild); if (job) addLink('返回原入口', job.old_entry); addLink('返回登录', root.location.origin + '/#/login'); }
    function send() {
      if (closed || !validNetworkTicket(ticket, true)) { fail('确认链接无效或当前地址不匹配，请返回原平台入口核对。'); return; }
      if (++polls > 90) { fail('网络切换仍待确认，请返回原入口核对执行状态。'); return; }
      message.textContent = ticket.phase === 'candidate' ? '已从候选地址访问，正在确认并完成网络配置…' : '正在从最终地址确认网络切换…';
      root.fetch(root.location.origin + '/api/platform_site/network/confirm', {method: 'POST', credentials: 'omit', cache: 'no-store', redirect: 'error',
        headers: {'Content-Type': 'application/json'}, body: JSON.stringify({job_id: ticket.job_id, token: ticket.token, phase: ticket.phase})})
        .then(function (response) { if (response.status >= 500) throw new Error('temporary_network_failure'); return response.json(); }).then(function (body) {
          if (closed) return;
          var value = body && body.data || {}; if (value.job) job = value.job;
          if (!body || Number(body.code) !== 200 || !job || job.id !== ticket.job_id) { fail('本次确认未通过，请返回原入口核对。'); return; }
          if (job.status === 'completed') { root.clearTimeout(timer); ticket = null; message.textContent = '网络切换已完成。请登录平台继续使用。'; while (links.firstChild) links.removeChild(links.firstChild); addLink('登录平台', root.location.origin + '/#/login'); return; }
          if (['failed', 'conflict', 'rolled_back', 'rolling_back', 'cancelled'].indexOf(job.status) >= 0) { fail('网络切换未完成或已回滚，请返回原入口核对。'); return; }
          if (value.handoff) {
            if (!validNetworkTicket(value.handoff, true) || value.handoff.job_id !== ticket.job_id || value.handoff.phase !== 'final' || ticket.phase === 'candidate' && value.handoff.token === ticket.token) { fail('最终确认凭据与当前地址不匹配，请返回原入口核对。'); return; }
            ticket = value.handoff; timer = root.setTimeout(send, 50); return;
          }
          if (job.status === 'finalizing' || job.status === 'awaiting_confirmation' || job.status === 'awaiting_final_confirmation') { timer = root.setTimeout(send, 1500); return; }
          fail('当前执行阶段暂不能确认，请返回原入口核对。');
        }).catch(function () { if (!closed) { message.textContent = '确认连接暂不可用，正在按原阶段重新查询；不会切换或复用其他阶段凭据。'; timer = root.setTimeout(send, 1500); } });
    }
    root.addEventListener('pagehide', function () { closed = true; root.clearTimeout(timer); });
    send(); return true;
  }
  function networkSelect(h, id, value, items, change, disabled) {
    return h('select', {attrs: {id: id, disabled: !!disabled}, domProps: {value: String(value == null ? '' : value)}, on: {change: function (event) { change(event.target.value); }}},
      items.map(function (item) { return h('option', {attrs: {value: String(item.value), disabled: !!item.disabled}}, item.label); }));
  }
  function networkCheck(h, id, title, value, change, disabled) { return h('label', {class: 'site-network-check', attrs: {for: id}}, [h('input', {attrs: {id: id, type: 'checkbox', disabled: !!disabled}, domProps: {checked: !!value}, on: {change: function (event) { change(event.target.checked); }}}), ' ' + title]); }

  var networkEditor = {
    name: 'PlatformNetworkEditor', props: {platformBusy: {type: Boolean, default: false}, hasPlatformDraft: {type: Boolean, default: false}},
    data: function () { return {inventory: null, authorized: true, opened: false, draft: null, preview: null, previewSignature: '',
      loading: false, mutating: false, error: '', notice: '', job: null, pendingId: '', uncertain: false,
      disposed: false, timer: null, sequence: 0, pollSequence: 0, polling: false, confirmedTerminal: '', failures: 0, navigatingJob: ''}; },
    computed: {
      busy: function () { return this.mutating || this.uncertain || networkActive(this.job); },
      selectedInterface: function () { var vm = this; return (this.inventory && this.inventory.interfaces || []).filter(function (item) { return interfaceName(item) === (vm.draft && vm.draft.interface); })[0] || null; },
      config: function () {
        var form = this.draft; if (!form) return null;
        return {interface: form.interface, connection_uuid: form.connection_uuid, operation: form.operation,
          replace_ipv4: form.operation === 'replace' ? form.replace_ipv4 || null : null, address: form.address, prefixlen: Number(form.prefixlen),
          gateway: form.gateway_mode === 'keep' ? null : form.gateway_mode === 'clear' ? '' : form.gateway,
          default_route: form.default_route, metric: form.metric === '' ? null : Number(form.metric),
          dns: form.dns_mode === 'keep' ? null : form.dns_mode === 'clear' ? [] : form.dns.split(/[\s,，]+/).filter(Boolean),
          use_for_platform: form.use_for_platform};
      },
      validation: function () {
        if (!this.draft) return [];
        var result = [], value = this.config;
        if (!interfaceEditable(this.selectedInterface)) result.push('请选择可编辑的独立物理网口。');
        if (!value.connection_uuid || !(this.selectedInterface && this.selectedInterface.profiles || []).some(function (profile) { return String(profile.uuid) === String(value.connection_uuid); })) result.push('请选择明确的网络连接配置。');
        if (value.operation === 'replace' && interfaceAddresses(this.selectedInterface, value.connection_uuid).indexOf(value.replace_ipv4) < 0) result.push('请选择本次要替换的原 IPv4 地址。');
        if (!ipv4(value.address)) result.push('请输入有效的 IPv4 地址。');
        if (!isFinite(value.prefixlen) || value.prefixlen % 1 || value.prefixlen < 1 || value.prefixlen > 32) result.push('前缀长度须为 1 到 32 的整数。');
        if (value.gateway !== null && value.gateway !== '' && !ipv4(value.gateway)) result.push('请输入有效的网关 IPv4 地址。');
        if (value.metric !== null && (!isFinite(value.metric) || value.metric % 1 || value.metric < 0 || value.metric > 4294967295)) result.push('路由 metric 须为有效的非负整数。');
        if (!value.default_route && (value.gateway !== null || value.metric !== null)) result.push('修改网关或路由 metric 须明确允许此连接更改默认出口。');
        if (this.draft.gateway_mode === 'set' && value.metric === null) result.push('指定网关时请同时填写路由 metric。');
        if (this.draft.dns_mode === 'set' && (!value.dns.length || value.dns.some(function (address) { return !ipv4(address); }))) result.push('请输入有效的 DNS IPv4 地址，多个地址用逗号分隔。');
        if (value.dns && value.dns.length > 8) result.push('每个连接最多填写 8 个 DNS 地址。');
        return result;
      },
      canApply: function () { return !!(this.preview && this.preview.plan_id && this.previewSignature === signature(this.config) && !this.validation.length && !this.loading && !this.busy && !this.platformBusy); }
    },
    watch: {busy: function (value) { this.$emit('busy', value); }, config: {deep: true, handler: function () { this.preview = null; this.previewSignature = ''; }}},
    created: function () { this.load(); },
    beforeDestroy: function () { this.disposed = true; this.sequence += 1; this.pollSequence += 1; root.clearTimeout(this.timer); },
    methods: {
      load: function () {
        if (this.disposed || this.loading) return Promise.resolve();
        var vm = this, sequence = ++this.sequence; this.loading = true;
        return this.$http.get(api('network/config')).then(data).then(function (value) {
          if (vm.disposed || sequence !== vm.sequence) return;
          vm.inventory = value; vm.error = ''; vm.authorized = true;
          if (vm.preview && vm.preview.revision && vm.preview.revision !== value.revision) { vm.preview = null; vm.previewSignature = ''; }
          if (value.active_job && value.active_job.id) { if (!vm.uncertain && !networkActive(vm.job)) vm.pendingId = value.active_job.id; vm.acceptJob(value.active_job); return; }
          if (!vm.pendingId && !vm.job) {
            try { var pending = root.localStorage.getItem(networkPendingKey()); if (/^[a-f0-9]{32}$/.test(pending || '')) { vm.pendingId = pending; vm.uncertain = true; vm.poll(); } } catch (ignore) {}
          }
        }).catch(function (error) {
          if (vm.disposed || sequence !== vm.sequence) return;
          if (denied(error)) { vm.authorized = false; vm.$emit('denied'); }
          else vm.error = '网口编辑能力暂无法读取，请稍后重试。';
        }).then(function () { if (!vm.disposed && sequence === vm.sequence) vm.loading = false; });
      },
      open: function () { if (this.busy || this.platformBusy || !this.inventory || !this.inventory.available) return;
        if (!this.draft) this.draft = {interface: '', connection_uuid: '', operation: 'add', replace_ipv4: '', address: '', prefixlen: '24',
          gateway_mode: 'keep', gateway: '', default_route: false, metric: '', dns_mode: 'keep', dns: '', use_for_platform: false}; this.opened = true; },
      set: function (key, value) { if (this.busy) return; this.$set(this.draft, key, value); this.preview = null; this.previewSignature = ''; },
      selectInterface: function (value) { this.set('interface', value); this.set('replace_ipv4', '');
        var iface = this.selectedInterface; this.set('connection_uuid', iface && iface.connection_uuid || ''); },
      previewChanges: function () {
        if (!this.draft || this.validation.length || this.loading || this.busy || this.platformBusy) return;
        var vm = this, snapshot = signature(this.config), revision = this.inventory.revision; this.mutating = true; this.error = ''; this.notice = '';
        return this.$http.post(api('network/preview'), {revision: revision, config: copy(this.config)}).then(data).then(function (value) {
          if (vm.disposed || snapshot !== signature(vm.config) || revision !== vm.inventory.revision) return;
          vm.preview = value; vm.preview.revision = revision; vm.previewSignature = snapshot;
        }).catch(function (error) { if (!vm.disposed) vm.error = denied(error) ? '当前账号没有网口配置权限。' : '网口预览未通过：' + errorText(error); })
          .then(function () { if (!vm.disposed) vm.mutating = false; });
      },
      apply: function () {
        if (!this.canApply) return;
        var vm = this, plan = this.preview.plan_id;
        var message = '将配置 ' + this.draft.interface + ' 的地址 ' + this.draft.address + '/' + this.draft.prefixlen + '。旧地址保留到新入口确认；未接线时等待链路。' +
          (this.draft.use_for_platform ? '链路就绪后将切换平台入口，并可能短暂重启相关服务。' : '本次不切换平台业务入口。') +
          (this.draft.default_route ? '你已允许此配置成为默认路由，请确认路由影响。' : '本次不主动抢占默认路由。');
        this.mutating = true;
        return showConfirm(this, message, '确认应用网口配置', '应用并等待确认').then(function () {
          if (vm.disposed || !vm.preview || plan !== vm.preview.plan_id || vm.previewSignature !== signature(vm.config)) return;
          var request = networkRequestId();
          try { root.localStorage.setItem(networkPendingKey(), request); } catch (ignore) { vm.error = '浏览器无法保存执行标识，请检查存储后再应用。'; return; }
          vm.pendingId = request; vm.uncertain = true; vm.error = ''; vm.preview = null; vm.previewSignature = '';
          return vm.$http.post(api('network/apply'), {plan_id: plan, request_id: request}).then(data).then(function (value) { if (!vm.disposed) vm.acceptJob(jobValue(value)); })
            .catch(function (error) {
              if (vm.disposed) return;
              if (error && error.response && error.response.data && error.response.data.safe_to_repreview === true) {
                vm.clearPending(); vm.pendingId = ''; vm.uncertain = false; vm.error = '本次尚未开始配置，请重新预览。'; return;
              }
              vm.error = '应用结果尚未确认，正在查询原执行记录，请勿重复提交。'; vm.poll();
            });
        }).catch(function () {}).then(function () { if (!vm.disposed) vm.mutating = false; });
      },
      clearPending: function () { try { if (root.localStorage.getItem(networkPendingKey()) === this.pendingId) root.localStorage.removeItem(networkPendingKey()); } catch (ignore) {} },
      acceptJob: function (value) {
        if (!value || !/^[a-f0-9]{32}$/.test(String(value.id || '')) || this.pendingId && value.id !== this.pendingId) { this.error = '网口执行记录尚未确认，请刷新核对。'; return; }
        var wasActive = this.uncertain || networkActive(this.job);
        this.job = value; this.pendingId = value.id; this.uncertain = false; this.failures = 0; this.error = '';
        if (networkActive(value)) { this.schedulePoll(); this.considerHandoff(); return; }
        root.clearTimeout(this.timer); this.clearPending();
        if (wasActive && this.confirmedTerminal !== value.id + ':' + value.status) { this.confirmedTerminal = value.id + ':' + value.status; this.$emit('settled', value); }
      },
      considerHandoff: function () {
        var vm = this; this.$nextTick(function () {
          var job = vm.job, target = job && networkHandoffLink(job.handoff);
          if (vm.disposed || !target || ['awaiting_confirmation', 'awaiting_final_confirmation'].indexOf(job.status) < 0 ||
              vm.hasPlatformDraft || vm.platformBusy || root.document.hidden || root.document.visibilityState === 'hidden' || vm.navigatingJob === job.id + ':' + job.handoff.phase) return;
          vm.navigatingJob = job.id + ':' + job.handoff.phase;
          var destination = new root.URL(target);
          if (destination.origin === root.location.origin && destination.pathname === root.location.pathname && destination.search === root.location.search) destination.searchParams.set('_network_handoff', job.id);
          root.location.assign(destination.href);
        });
      },
      schedulePoll: function () { var vm = this, request = this.pendingId, sequence = this.pollSequence; root.clearTimeout(this.timer);
        if (!this.disposed && this.failures < 12) this.timer = root.setTimeout(function () { if (vm.pendingId === request && vm.pollSequence === sequence) vm.poll(); }, 2000); },
      poll: function () {
        if (this.disposed || !this.pendingId || this.polling) return Promise.resolve();
        var vm = this, request = this.pendingId, sequence = this.pollSequence; this.polling = true; root.clearTimeout(this.timer);
        return this.$http.get(api('network/jobs/' + encodeURIComponent(request))).then(data).then(function (value) { if (!vm.disposed && vm.pendingId === request && vm.pollSequence === sequence) vm.acceptJob(jobValue(value)); })
          .catch(function () { if (vm.disposed || vm.pendingId !== request || vm.pollSequence !== sequence) return;
            vm.failures += 1; vm.error = '暂时无法读取执行状态，原任务会保留。请继续查询，勿重复应用。'; vm.schedulePoll(); })
          .then(function () { if (!vm.disposed && vm.pendingId === request && vm.pollSequence === sequence) vm.polling = false; });
      },
      cancel: function () {
        if (this.mutating || !this.job || !this.job.can_cancel) return;
        var vm = this, request = this.job.id; this.mutating = true;
        return showConfirm(this, '将取消本次网络切换，并按执行记录恢复已暂存的配置。', '取消网口操作', '取消并恢复').then(function () {
          return vm.$http.post(api('network/jobs/' + request + '/cancel'), {}).then(data).then(function (value) { if (!vm.disposed && vm.pendingId === request) vm.acceptJob(jobValue(value)); });
        }).catch(function () { if (!vm.disposed) vm.poll(); }).then(function () { if (!vm.disposed) vm.mutating = false; });
      },
      rollback: function () {
        if (this.mutating || !this.job || !this.job.can_rollback) return;
        var vm = this, request = this.job.id; this.mutating = true;
        return showConfirm(this, '将按本次执行记录恢复网口和平台配置。', '回滚网口操作', '确认回滚').then(function () {
          return vm.$http.post(api('network/jobs/' + request + '/rollback'), {}).then(data).then(function (value) { if (!vm.disposed && vm.pendingId === request) vm.acceptJob(jobValue(value)); });
        }).catch(function () { if (!vm.disposed) vm.poll(); }).then(function () { if (!vm.disposed) vm.mutating = false; });
      }
    },
    render: function (h) {
      if (!this.authorized) return h();
      var vm = this, form = this.draft, locked = this.busy || this.platformBusy, inventory = this.inventory;
      var parts = [h('div', {class: 'site-network-edit-heading'}, [h('h4', '网口地址配置'), button(h, this.loading ? '读取中…' : '刷新连接信息', this.load, this.loading || this.mutating),
        button(h, '编辑网口', this.open, !inventory || !inventory.available || locked)])];
      if (this.error) parts.push(h('p', {class: 'site-network-warning', attrs: {role: 'alert'}}, this.error));
      if (inventory && !inventory.available) parts.push(h('p', {class: 'site-network-footnote'}, inventory.reason || '当前服务器暂不支持网口编辑。'));
      if (this.platformBusy && !this.busy) parts.push(h('p', {class: 'site-network-warning'}, '平台配置正在处理，请完成后再应用网口配置。'));
      if (this.opened && form) {
        var iface = this.selectedInterface, profiles = iface && iface.profiles || [], addresses = interfaceAddresses(iface, form.connection_uuid);
        var controls = [h('div', {class: 'site-network-edit-grid'}, [
          h('div', {class: 'site-config-field'}, [h('label', {attrs: {for: 'network-interface'}}, '物理网口'), networkSelect(h, 'network-interface', form.interface,
            [{value: '', label: '请选择独立物理网口'}].concat((inventory.interfaces || []).map(function (item) { return {value: interfaceName(item), disabled: !interfaceEditable(item), label: interfaceName(item) + ' · ' + linkText(item) + (!interfaceEditable(item) ? '（' + (item.blocked_reason || '不支持编辑') + '）' : '')}; })), this.selectInterface, locked)]),
          h('div', {class: 'site-config-field'}, [h('label', {attrs: {for: 'network-profile'}}, '连接配置'), networkSelect(h, 'network-profile', form.connection_uuid,
            [{value: '', label: '请选择连接配置'}].concat(profiles.map(function (item) { return {value: item.uuid, label: item.name || item.uuid}; })), function (value) { vm.set('connection_uuid', value); vm.set('replace_ipv4', ''); }, locked)]),
          h('div', {class: 'site-config-field'}, [h('label', {attrs: {for: 'network-operation'}}, '地址操作'), networkSelect(h, 'network-operation', form.operation,
            [{value: 'add', label: '新增地址'}, {value: 'replace', label: '替换指定地址'}], function (value) { vm.set('operation', value); }, locked)]),
          form.operation === 'replace' ? h('div', {class: 'site-config-field'}, [h('label', {attrs: {for: 'network-replace'}}, '要替换的原地址'), networkSelect(h, 'network-replace', form.replace_ipv4,
            [{value: '', label: '请选择原 IPv4 / 前缀'}].concat(addresses.map(function (value) { return {value: value, label: value}; })), function (value) { vm.set('replace_ipv4', value); }, locked)]) : null,
          field(h, 'IPv4 地址', 'network-address', form.address, function (event) { vm.set('address', event.target.value); }, locked),
          field(h, '前缀长度', 'network-prefix', form.prefixlen, function (event) { vm.set('prefixlen', event.target.value); }, locked, '例如 24 对应 255.255.255.0。'),
          h('div', {class: 'site-config-field'}, [h('label', {attrs: {for: 'network-gateway-mode'}}, '网关'), networkSelect(h, 'network-gateway-mode', form.gateway_mode,
            [{value: 'keep', label: '保留原网关'}, {value: 'set', label: '指定网关'}, {value: 'clear', label: '清除该连接网关'}], function (value) { vm.set('gateway_mode', value); }, locked),
            form.gateway_mode === 'set' ? field(h, '网关 IPv4', 'network-gateway', form.gateway, function (event) { vm.set('gateway', event.target.value); }, locked) : null]),
          field(h, '路由 metric（可选）', 'network-metric', form.metric, function (event) { vm.set('metric', event.target.value); }, locked, '留空保留原值。'),
          h('div', {class: 'site-config-field'}, [h('label', {attrs: {for: 'network-dns-mode'}}, 'DNS'), networkSelect(h, 'network-dns-mode', form.dns_mode,
            [{value: 'keep', label: '保留原 DNS'}, {value: 'set', label: '指定 DNS'}, {value: 'clear', label: '清除该连接 DNS'}], function (value) { vm.set('dns_mode', value); }, locked),
            form.dns_mode === 'set' ? field(h, 'DNS IPv4', 'network-dns', form.dns, function (event) { vm.set('dns', event.target.value); }, locked, '多个地址用逗号分隔。') : null])]),
          networkCheck(h, 'network-default-route', '允许此连接成为默认路由', form.default_route, function (value) { vm.set('default_route', value); }, locked),
          networkCheck(h, 'network-platform', '平台使用此 IPv4 地址', form.use_for_platform, function (value) { vm.set('use_for_platform', value); }, locked),
          h('p', {class: 'site-network-footnote'}, '仅修改本次选中的连接与地址。未接线时等待链路，旧地址保留至新入口确认。'),
          this.validation.length ? h('ul', {class: 'site-config-error'}, this.validation.map(function (message) { return h('li', message); })) : null,
          button(h, '预览网口变更', this.previewChanges, locked || this.loading || !!this.validation.length, true),
          button(h, '收起编辑', function () { vm.opened = false; }, this.busy)];
        parts.push(h('div', {class: 'site-network-edit-form', attrs: {'data-network-form': 'true'}}, controls));
      }
      if (this.preview) {
        var plan = this.preview, changes = plan.changes || [], restarts = plan.requires_restarts;
        parts.push(h('section', {class: 'site-network-plan', attrs: {'data-network-preview': 'true'}}, [h('h4', '网口变更预览'),
          h('ul', changes.map(function (item) { return h('li', typeof item === 'string' ? item : item.message || (item.label || item.field || item.path || '配置项') + '：' + signature(item.before) + ' → ' + signature(item.after)); })),
          h('ul', {class: 'site-network-warning'}, (plan.warnings || []).map(function (message) { return h('li', String(message)); })),
          h('p', Array.isArray(restarts) && restarts.length ? '需短暂重启：' + restarts.map(function (role) { return serviceNames[role] || role; }).join('、') : restarts && !Array.isArray(restarts) ? '平台入口切换需要短暂重启相关服务。' : '本次无需重启业务服务。'),
          h('p', '原地址在新入口确认前保留；未接线时不会立即切换平台。'), button(h, '应用网口配置', this.apply, !this.canApply, true)]));
      }
      if (this.job || this.uncertain) {
        var job = this.job || {}, handoff = networkHandoffLink(job.handoff), entry = networkEntry(job.confirm_entry || job.new_entry);
        parts.push(h('section', {class: 'site-network-job', attrs: {'data-network-job': this.pendingId}}, [h('h4', '网口执行状态'),
          h('p', [h('strong', networkPhases[job.status] || (this.uncertain ? '执行结果待确认' : '正在处理')), job.message ? ' · ' + job.message : '']),
          job.error ? h('p', {class: 'site-config-error'}, String(job.error)) : null,
          job.status === 'waiting_link' ? h('p', '请将网线接入目标网口。链路就绪后继续，等待期间保留当前平台入口。') : null,
          handoff ? h('p', this.hasPlatformDraft ? '本页有尚未应用的平台草稿，已保留当前页面。请在确认期限内打开新入口完成确认。' : root.document.hidden ? '当前标签在后台，请在确认期限内打开新入口完成确认。' : '将自动前往新入口完成确认。') : null,
          job.deadline ? h('p', '确认期限：' + collectedTime(job.deadline)) : null,
          handoff ? h('p', [h('a', {attrs: {href: handoff, target: '_blank', rel: 'noopener noreferrer', 'data-network-handoff': 'true'}}, '打开新入口并确认切换')]) : entry ? h('p', ['新入口：', h('a', {attrs: {href: entry, target: '_blank', rel: 'noopener noreferrer'}}, '打开新入口')]) : null,
          button(h, this.polling ? '查询中…' : '查询执行状态', this.poll, this.polling || !this.pendingId),
          job.can_cancel ? button(h, '取消并回滚', this.cancel, this.mutating) : null,
          job.can_rollback ? button(h, '恢复本次备份', this.rollback, this.mutating) : null]));
      }
      return h('section', {class: 'site-network-editor', attrs: {'data-network-editor': 'true'}}, parts);
    }
  };

  // Read-only inventory has its own state and refresh lifecycle. It never
  // replaces a configuration draft or stores an interface name in the master.
  var networkPanel = {
    name: 'PlatformSiteNetworkInventory',
    props: {platformBusy: {type: Boolean, default: false}, hasPlatformDraft: {type: Boolean, default: false}},
    data: function () { return {packet: null, authorized: false, loading: false, error: '', timer: null,
      disposed: false, active: true, sequence: 0, sessionToken: null}; },
    created: function () { this.refresh(); this.startTimer(); },
    activated: function () { this.active = true; this.refresh(); this.startTimer(); },
    deactivated: function () { this.active = false; this.sequence += 1; this.loading = false; this.stopTimer(); },
    beforeDestroy: function () { this.disposed = true; this.sequence += 1; this.stopTimer(); },
    methods: {
      startTimer: function () {
        if (this.timer || this.disposed || !this.active) return;
        var vm = this; this.timer = root.setInterval(function () { if (!root.document.hidden) vm.refresh(); }, 60000);
      },
      stopTimer: function () { if (this.timer) root.clearInterval(this.timer); this.timer = null; },
      refresh: function () {
        if (this.disposed || !this.active || this.loading) return Promise.resolve();
        var vm = this, token = root.localStorage && root.localStorage.getItem('token');
        if (token !== this.sessionToken) { this.packet = null; this.authorized = false; this.sessionToken = token; }
        if (!token) { this.stopTimer(); return Promise.resolve(); }
        var sequence = ++this.sequence; this.loading = true;
        return this.$http.get(api('config')).then(data).then(function (value) {
          if (vm.disposed || !vm.active || sequence !== vm.sequence) return;
          vm.authorized = value.can_edit === true;
          if (!vm.authorized) { vm.packet = null; vm.stopTimer(); return; }
          vm.packet = {network: value.network || null, identity: value.host_identity || {},
            applied: value.applied || null};
          vm.error = ''; vm.startTimer();
        }).catch(function (error) {
          if (vm.disposed || !vm.active || sequence !== vm.sequence) return;
          if (denied(error)) {
            vm.authorized = false; vm.packet = null; vm.stopTimer(); authorize(false);
            vm.$emit('denied');
          } else { vm.error = '本次网口信息刷新未完成，请稍后重试。'; }
        }).then(function () { if (!vm.disposed && sequence === vm.sequence) vm.loading = false; });
      }
    },
    render: function (h) {
      if (!this.authorized || !this.packet) return h();
      var network = this.packet.network || {}, business = network.business || {},
        interfaces = Array.isArray(network.interfaces) ? network.interfaces : [],
        names = Array.isArray(business.interface_names) ? business.interface_names : [],
        matched = interfaces.filter(function (iface) { return names.indexOf(iface.name) >= 0; }),
        available = network.available === true, status = business.status || 'unavailable';
      var children = [h('header', {class: 'site-network-heading'}, [h('div', [
        h('h3', '本机网口'),
        h('p', '根据服务器当前配置动态识别，刷新网口信息不会改动本页草稿。')]),
        button(h, this.loading ? '读取中…' : '刷新网口', this.refresh, this.loading)])];
      if (this.error) children.push(h('p', {class: 'site-network-warning', attrs: {role: 'status'}},
        this.error + (available ? ' 以下为上次采集结果，当前状态尚未确认。' : '')));
      children.push(h('div', {class: 'site-network-summary'}, [
        h('div', [h('span', {class: 'site-network-label'}, '当前生效业务 IP'),
          h('strong', {class: 'site-network-business-ip'}, business.address || this.packet.applied && this.packet.applied.node.address || '—')]),
        h('div', [h('span', {class: 'site-network-label'}, '当前承载网口'),
          h('strong', {class: 'site-network-interface-names'}, available && names.length ? names.join('、') : available && status === 'missing' ? '未匹配到本机地址' : '尚未确认')]),
        h('div', [h('span', {class: 'site-network-label'}, '状态'),
          h('strong', {class: ['site-network-status', available && status === 'ready' && !this.error ? 'is-ready' : 'is-unknown']}, this.error ? '当前状态尚未确认' : networkStatus(network)),
          matched.length ? h('small', {class: 'site-network-link'}, matched.map(function (iface) { return iface.name + '：' + linkText(iface); }).join('；')) : null])
      ]));
      if (!available) children.push(h('p', {class: 'site-network-warning'}, network.error || '暂未获取有效的本机网口信息，请检查服务器网络状态或稍后刷新。'));
      else if (business.message && status !== 'ready') children.push(h('p', {class: 'site-network-warning'}, business.message));
      if (available) children.push(h('details', {class: 'site-network-details'}, [h('summary', '查看全部网口与 IPv4 地址（' + interfaces.length + ' 个）'),
        h('div', {class: 'site-network-table-scroll'}, [h('table', {class: 'site-network-table'}, [
          h('thead', [h('tr', [h('th', '网口 / 类型'), h('th', 'IPv4 地址 / 前缀'), h('th', '链路状态'), h('th', '用途')])]),
          h('tbody', interfaces.map(function (iface) {
            var addresses = (iface.addresses || []).filter(function (address) { return address.family === 'inet'; });
            return h('tr', {key: String(iface.name) + ':' + String(iface.index), attrs: {'data-interface-name': iface.name}}, [
              h('th', {attrs: {scope: 'row'}}, [h('strong', String(iface.name || '—')), h('small', interfaceType(iface))]),
              h('td', addresses.length ? addresses.map(function (address) { return h('div', {class: 'site-network-address'}, [
                h('code', String(address.address) + '/' + String(address.prefixlen)),
                address.candidate === true ? h('span', {class: 'site-network-badge'}, '业务候选') : null]); }) : '未配置 IPv4 地址'),
              h('td', linkText(iface)), h('td', iface.internal === true ? '内部网络' : addresses.some(function (address) { return address.candidate === true; }) ? '可作为业务地址' : '暂无业务候选地址')]);
          }))
        ])])
      ]));
      children.push(h('footer', {class: 'site-network-footnote'}, [
        h('span', '采集时间：' + collectedTime(network.collected_at)),
        h('span', '网口名称只作当前网络说明，机器标识和任务关联不随网口变更。'),
        h('span', '去摄像机的出接口由路由决定，可能与平台入口网口不同。')
      ]));
      children.push(h(networkEditor, {props: {platformBusy: this.platformBusy, hasPlatformDraft: this.hasPlatformDraft}, on: {
        busy: function (value) { this.$emit('network-busy', value); }.bind(this),
        settled: function (value) { this.refresh(); this.$emit('network-settled', value); }.bind(this),
        denied: function () { this.$emit('denied'); }.bind(this)}}));
      return h('section', {class: 'site-network-panel', attrs: {'data-site-network': 'configuration'}}, children);
    }
  };

  var component = {
    name: 'PlatformSiteConfig',
    data: function () { return {servicesExpanded: false, state: null, draft: null, preview: null, previewSignature: '', loading: false, mutating: false,
      error: '', success: '', job: null, reconnecting: false, denied: false, disposed: false, pollTimer: null, pollFailures: 0, revision: 0, plannedAddress: '', networkWorking: false, networkSyncing: false}; },
    computed: {
      canEdit: function () { return !!(this.state && this.state.can_edit === true && !this.denied); },
      working: function () { return this.loading || this.mutating || isActive(this.job) || this.networkWorking || this.networkSyncing; },
      validationErrors: function () { return this.draft ? validate(this.draft) : []; },
      hasEdits: function () { return !!(this.state && this.draft && signature(this.draft) !== signature(this.state.desired || this.state.applied)); },
      canApply: function () { return !!(this.canEdit && this.preview && this.preview.plan_id && this.previewSignature === signature(this.draft) && !this.working && !this.validationErrors.length); },
      latestBackup: function () { return backupPath(this.state && this.state.last_backup); },
      destination: function () {
        var target = this.preview && this.preview.desired && this.preview.desired.node && this.preview.desired.node.address
          || this.plannedAddress || this.job && this.job.target_address;
        if (!target || !hostValid(target) || target === root.location.hostname) return '';
        return root.location.protocol + '//' + target + (root.location.port ? ':' + root.location.port : '') + '/#' + PATH;
      }
    },
    created: function () { this.load(false); },
    beforeDestroy: function () { this.disposed = true; root.clearTimeout(this.pollTimer); },
    methods: {
      syncNetworkResult: function () {
        if (this.disposed || !this.state) return Promise.resolve();
        var vm = this, baseline = copy(this.state.desired || this.state.applied), generation = this.state.generation; this.networkSyncing = true; this.changed();
        return this.$http.get(api('config')).then(data).then(function (value) {
          if (vm.disposed || !vm.state || vm.state.generation !== generation) return;
          if (value.can_edit !== true) { vm.denied = true; authorize(false); return; }
          var fresh = value.desired || value.applied, draft = copy(vm.draft || baseline);
          if (signature(draft.node) === signature(baseline.node)) draft.node = copy(fresh.node);
          Object.keys(fresh.services || {}).forEach(function (role) { if (signature(draft.services[role]) === signature(baseline.services[role])) draft.services[role] = copy(fresh.services[role]); });
          vm.state = value; vm.draft = draft; vm.success = '已同步网络执行结果，尚未应用的手动修改已保留。';
        }).catch(function () { if (!vm.disposed) vm.error = '网络任务已有结果，平台配置暂未同步。请重新读取并核对，未应用草稿仍保留。'; })
          .then(function () { if (!vm.disposed) vm.networkSyncing = false; });
      },
      changed: function () { this.revision += 1; this.preview = null; this.previewSignature = ''; this.success = ''; this.plannedAddress = ''; },
      setNode: function (event) { this.draft.node.address = event.target.value; this.changed(); },
      setMode: function (key, value) {
        var old = this.draft.services[key], address = resolved(old, this.draft.node.address);
        this.$set(this.draft.services, key, value === 'fixed' ? {host: address} : {ref: value}); this.changed();
      },
      setHost: function (key, event) { this.$set(this.draft.services[key], 'host', event.target.value); this.changed(); },
      load: function (preserveMessages) {
        if (this.disposed || this.loading) return Promise.resolve();
        var vm = this; this.loading = true;
        return this.$http.get(api('config')).then(data).then(function (value) {
          if (vm.disposed) return;
          vm.state = value; vm.denied = value.can_edit !== true;
          if (vm.denied) { authorize(false); return; }
          authorize(true); vm.draft = copy(value.desired || value.applied); vm.preview = null; vm.previewSignature = '';
          if (!preserveMessages) { vm.error = ''; vm.success = ''; }
          var job = jobValue(value.active_job || value.latest_job);
          if (job && job.id) { vm.job = job; if (isActive(job)) vm.schedulePoll(100); }
        }).catch(function (error) {
          if (vm.disposed) return;
          vm.error = errorText(error);
          if (denied(error)) { vm.denied = true; authorize(false); }
        }).then(function () { if (!vm.disposed) vm.loading = false; });
      },
      reload: function () {
        var vm = this;
        if (this.working) return;
        if (!this.hasEdits) return this.load(false);
        return showConfirm(this, '重新读取会撤销本页尚未应用的修改。', '重新读取配置', '重新读取')
          .then(function () { return vm.load(false); }).catch(function () {});
      },
      reset: function () { if (this.working || !this.state) return; this.draft = copy(this.state.desired || this.state.applied); this.changed(); this.error = ''; },
      previewChanges: function () {
        if (!this.canEdit || this.working || this.validationErrors.length) return;
        var vm = this, revision = this.revision, snapshot = signature(this.draft); this.mutating = true; this.error = ''; this.success = ''; this.preview = null;
        return this.$http.post(api('preview'), {config: copy(this.draft)}, {headers: {'Content-Type': 'application/json'}}).then(data).then(function (value) {
          if (vm.disposed) return;
          if (revision !== vm.revision || snapshot !== signature(vm.draft)) { vm.error = '配置已修改，请重新预览。'; return; }
          vm.preview = value; vm.previewSignature = snapshot;
        }).catch(function (error) { if (!vm.disposed) { vm.error = errorText(error); if (denied(error)) { vm.denied = true; authorize(false); } } })
          .then(function () { if (!vm.disposed) vm.mutating = false; });
      },
      startJob: function (value) {
        this.job = jobValue(value); this.pollFailures = 0; this.reconnecting = false;
        if (!this.job || !this.job.id) throw new Error('未取得执行记录，请刷新核对状态。');
        this.preview = null; this.previewSignature = '';
        if (isActive(this.job)) this.schedulePoll(200);
        else this.finishJob();
      },
      apply: function () {
        if (!this.canApply) return;
        var vm = this, plan = this.preview, expected = this.previewSignature;
        var services = (plan.affected_services || plan.restarts || []).map(function (name) { return serviceNames[name] || name; });
        var summary = (plan.changes || []).length ? '将更新 ' + plan.changes.length + ' 个模块配置。' : '当前配置一致，本次仅核对状态，不重启服务。';
        if (services.length) summary += '\n短暂重启：' + services.join('、') + '。';
        if (plan.node_changed) summary += '\n平台地址将改为 ' + plan.desired.node.address + '，请确认新地址已配置到本机并可访问。';
        summary += '\n系统先备份，应用后检查服务；失败时尝试恢复。现有任务、累计计数和报警记录保留。';
        this.mutating = true; this.error = ''; this.success = '';
        return showConfirm(this, summary, '确认应用配置', '备份并应用').then(function () {
          if (vm.disposed || expected !== signature(vm.draft)) return;
          if (plan.node_changed) vm.plannedAddress = plan.desired.node.address;
          return vm.$http.post(api('apply'), {plan_id: plan.plan_id}, {headers: {'Content-Type': 'application/json'}}).then(data)
            .then(function (value) { if (!vm.disposed) vm.startJob(value); })
            .catch(function (error) { if (!vm.disposed) { vm.error = errorText(error) + '。请刷新查看执行记录，避免重复提交。'; return vm.load(true); } });
        }).catch(function (error) { if (!vm.disposed && error !== 'cancel' && error !== 'close') vm.error = errorText(error); })
          .then(function () { if (!vm.disposed) vm.mutating = false; });
      },
      rollback: function () {
        if (!this.canEdit || this.working || !this.latestBackup) return;
        var vm = this, backup = this.latestBackup; this.mutating = true; this.error = ''; this.success = '';
        return showConfirm(this, '将恢复上一份配置备份并检查服务，相关服务可能短暂重启。现有任务和历史数据保留。', '确认回滚配置', '恢复上一版本')
          .then(function () {
            if (vm.disposed) return;
            return vm.$http.post(api('rollback'), {backup: backup}, {headers: {'Content-Type': 'application/json'}}).then(data)
              .then(function (value) { if (!vm.disposed) vm.startJob(value); })
              .catch(function (error) { if (!vm.disposed) { vm.error = errorText(error) + '。请刷新查看执行记录，避免重复提交。'; return vm.load(true); } });
          }).catch(function (error) { if (!vm.disposed && error !== 'cancel' && error !== 'close') vm.error = errorText(error); })
          .then(function () { if (!vm.disposed) vm.mutating = false; });
      },
      schedulePoll: function (delay) {
        root.clearTimeout(this.pollTimer); if (this.disposed || !isActive(this.job)) return;
        var vm = this; this.pollTimer = root.setTimeout(function () { vm.pollJob(); }, delay);
      },
      pollJob: function () {
        if (this.disposed || !this.job || !this.job.id || !isActive(this.job)) return;
        var vm = this, id = String(this.job.id);
        return this.$http.get(api('jobs/' + encodeURIComponent(id))).then(data).then(function (value) {
          if (vm.disposed || !vm.job || String(vm.job.id) !== id) return;
          var next = jobValue(value);
          if (!next || String(next.id) !== id) throw new Error('执行记录不一致，请刷新核对。');
          vm.job = next; vm.pollFailures = 0; vm.reconnecting = false;
          if (isActive(vm.job)) vm.schedulePoll(2000); else vm.finishJob();
        }).catch(function (error) {
          if (vm.disposed) return;
          if (denied(error)) { vm.error = errorText(error); vm.denied = true; authorize(false); return; }
          vm.pollFailures += 1; vm.reconnecting = true;
          if (vm.pollFailures > 200) { vm.error = '暂时无法读取执行结果，请稍后重新打开本页查看保留的执行记录。'; return; }
          vm.schedulePoll(3000);
        });
      },
      finishJob: function () {
        root.clearTimeout(this.pollTimer); this.reconnecting = false;
        if (!this.job) return;
        if (this.job.status === 'completed') this.success = this.job.operation === 'rollback' ? '上一版本配置已恢复，服务检查通过。' : '配置已应用，服务检查通过。';
        else if (this.job.status === 'failed') this.error = this.job.error || this.job.message || '配置未完成，请查看执行记录。';
        this.load(true);
      },
      serviceRow: function (h, key) {
        var vm = this, endpoint = this.draft.services[key], kind = mode(endpoint), id = 'site-service-' + key;
        return h('tr', {key: key}, [h('th', {attrs: {scope: 'row'}}, label(key)),
          h('td', [h('select', {attrs: {id: id + '-mode', 'aria-label': label(key) + '地址方式', disabled: !this.canEdit || this.working}, domProps: {value: kind},
            on: {change: function (event) { vm.setMode(key, event.target.value); }}}, Object.keys(modes).map(function (value) { return h('option', {domProps: {value: value}}, modes[value]); }))]),
          h('td', kind === 'fixed' ? [h('input', {attrs: {id: id + '-host', 'aria-label': label(key) + '独立地址', type: 'text', disabled: !this.canEdit || this.working, autocomplete: 'off', spellcheck: 'false'},
            domProps: {value: endpoint.host}, on: {input: function (event) { vm.setHost(key, event); }}})] : [h('span', {class: 'site-config-address'}, resolved(endpoint, this.draft.node.address))])]);
      }
    },
    render: function (h) {
      var vm = this, sections = [h('header', {class: 'site-config-heading'}, [h('div', [h('h2', 'IP管理'), h('p', '集中维护平台及各服务地址，预览后统一派发。')]),
        button(h, this.loading ? '读取中…' : '重新读取', this.reload, this.working)])];
      if (this.error) sections.push(h('div', {class: 'site-config-message is-error', attrs: {role: 'alert'}}, this.error));
      if (this.success) sections.push(h('div', {class: 'site-config-message is-success', attrs: {role: 'status'}}, this.success));
      if (this.denied) sections.push(h('p', {class: 'site-config-card'}, '当前账号没有IP管理管理权限。'));
      else if (this.loading && !this.state) sections.push(h('p', {attrs: {role: 'status'}}, '正在读取当前配置…'));
      if (this.state && this.draft && this.canEdit) {
        var identity = this.state.host_identity || {};
        sections.push(h('section', {class: 'site-config-card site-config-summary'}, [h('div', [h('h3', '当前生效配置'),
          h('p', [h('strong', String(this.state.applied && this.state.applied.node.address || '—')), ' · 版本 ' + String(this.state.generation == null ? '—' : this.state.generation)]),
          h('small', '管理 ' + Number(this.state.managed_files || 0) + ' 个配置文件、' + Number(this.state.managed_bindings || 0) + ' 处地址引用')]),
          identity.host_uid ? h('div', {class: 'site-config-identity'}, [h('h3', '稳定设备标识'), h('code', identity.host_uid), h('small', 'IP 可更改，设备和任务关联保留。')]) : null]));
        sections.push(h('section', {class: 'site-config-card'}, [h('h3', '平台地址'),
          field(h, '平台对外地址', 'site-node-address', this.draft.node.address, this.setNode, this.working,
            '修改本页内容后需预览并应用。更换地址前，请先确认新 IP 已配置到服务器。'),
          this.state.pending ? h('p', {class: 'site-config-pending'}, this.state.drift || '平台地址有待同步配置。请先在页面底部“预览派发”并应用，再修改网口地址。') : null]));
        sections.push(h(networkPanel, {key: 'configuration-network-inventory', props: {platformBusy: this.loading || this.mutating || isActive(this.job) || this.networkSyncing, hasPlatformDraft: this.hasEdits}, on: {
          denied: function () { vm.denied = true; }, 'network-busy': function (value) { vm.networkWorking = value; }, 'network-settled': this.syncNetworkResult}}));
        var keys = roles.map(function (item) { return item[0]; }).filter(function (key) { return vm.draft.services[key]; });
        Object.keys(this.draft.services).forEach(function (key) { if (keys.indexOf(key) < 0) keys.push(key); });
        var counts = {node: 0, loopback: 0, fixed: 0};
        keys.forEach(function (key) { counts[mode(vm.draft.services[key])] += 1; });
        var serviceEdits = signature(this.draft.services) !== signature((this.state.desired || this.state.applied).services);
        sections.push(h('section', {class: 'site-config-card config-fold-card site-services-fold'}, [
          h('button', {class: 'config-fold-heading', attrs: {type: 'button', 'aria-expanded': String(this.servicesExpanded), 'aria-controls': 'site-services-body'},
            on: {click: function () { vm.servicesExpanded = !vm.servicesExpanded; }}}, [
            h('span', {class: 'config-fold-caption'}, [h('span', {class: 'config-fold-title'}, '服务地址'),
              h('span', {class: 'config-fold-summary'}, '共 ' + keys.length + ' 项 · 跟随平台 ' + counts.node + ' 项 · 本机连接 ' + counts.loopback + ' 项 · 独立地址 ' + counts.fixed + ' 项'),
              serviceEdits ? h('span', {class: 'config-fold-dirty'}, '有待应用修改') : null]),
            h('span', {class: 'config-fold-action'}, [this.servicesExpanded ? '收起' : '展开', h('span', {attrs: {'aria-hidden': 'true'}}, this.servicesExpanded ? ' ▴' : ' ▾')])
          ]),
          h('div', {class: 'config-fold-body', attrs: {id: 'site-services-body', hidden: !this.servicesExpanded}}, [
            h('p', '跟随平台地址的服务会一起更新；独立地址保持单独配置。摄像机和录像机继续在设备管理中维护。'),
            h('div', {class: 'site-config-table-scroll'}, [h('table', {class: 'site-config-table'}, [h('thead', [h('tr', [h('th', '服务'), h('th', '地址方式'), h('th', '使用地址')])]),
              h('tbody', keys.map(function (key) { return vm.serviceRow(h, key); }))])])])
        ]));
        if (this.validationErrors.length) sections.push(h('div', {class: 'site-config-message is-error', attrs: {role: 'alert'}}, this.validationErrors.map(function (message) { return h('p', message); })));
        sections.push(h('div', {class: 'site-config-actions'}, [button(h, '撤销本页修改', this.reset, this.working || !this.hasEdits),
          button(h, this.mutating && !this.preview ? '处理中…' : '预览派发', this.previewChanges, this.working || !!this.validationErrors.length, true)]));
        if (this.preview) {
          var changes = differences(this.state.applied, this.preview.desired || this.draft), files = this.preview.changes || [], affected = this.preview.affected_services || this.preview.restarts || [];
          var previewChildren = [h('h3', '配置预览'), h('p', files.length || changes.length ? '已核对修改，将更新 ' + files.length + ' 个模块配置。' : '配置一致，无需修改。')];
          if (changes.length) previewChildren.push(h('div', {class: 'site-config-table-scroll'}, [h('table', {class: 'site-config-table'}, [h('thead', [h('tr', [h('th', '配置项'), h('th', '当前生效'), h('th', '修改后')])]),
            h('tbody', changes.map(function (change) { return h('tr', [h('th', {attrs: {scope: 'row'}}, change.label), h('td', change.before), h('td', change.after)]); }))])]));
          previewChildren.push(h('p', affected.length ? '需短暂重启：' + affected.map(function (name) { return serviceNames[name] || name; }).join('、') : '本次无需重启服务。'));
          if (files.length) previewChildren.push(h('details', [h('summary', '查看派发范围'), h('ul', files.map(function (file) { return h('li', String(file.path || file)); }))]));
          if (this.destination) previewChildren.push(h('p', ['新地址：', h('a', {attrs: {href: this.destination, target: '_blank', rel: 'noopener noreferrer'}}, this.destination), '；地址切换后请重新登录。']));
          previewChildren.push(button(h, '应用配置', this.apply, !this.canApply, true));
          sections.push(h('section', {class: 'site-config-card site-config-preview', attrs: {'data-site-preview': 'true'}}, previewChildren));
        }
        if (this.job) {
          sections.push(h('section', {class: 'site-config-card', attrs: {'data-site-job': String(this.job.id)}}, [h('h3', '最近执行记录'),
            h('p', [h('strong', statuses[this.job.status] || this.job.status || '—'), ' · ' + (this.job.operation === 'rollback' ? '恢复配置' : '应用配置')]),
            h('p', this.job.message || ''), this.job.error ? h('p', {class: 'site-config-error'}, this.job.error) : null,
            this.reconnecting ? h('p', {attrs: {role: 'status'}}, '服务可能正在重启，正在重新连接。执行记录会保留，请勿重复提交。') : null,
            this.destination ? h('p', ['新地址：', h('a', {attrs: {href: this.destination, target: '_blank', rel: 'noopener noreferrer'}}, this.destination), '；地址切换后请重新登录。']) : null]));
        }
        if (this.latestBackup) sections.push(h('footer', {class: 'site-config-footer'}, [h('span', '需要恢复时，可回滚上一份配置备份。'), button(h, '回滚上一版本', this.rollback, this.working)]));
      }
      return h('div', {class: 'platform-site-config'}, sections);
    }
  };

  function findHome(vm) {
    if (!vm) return null;
    if (vm.$options && vm.$options.name === 'Home') return vm;
    var children = vm.$children || [];
    for (var i = 0; i < children.length; i += 1) { var found = findHome(children[i]); if (found) return found; }
    return null;
  }
  function own(item) { return item && (item.__platformSiteMenu || item.menu_link === PATH || item.menu_link === PATH.slice(1)); }
  function updateMenu(home) {
    if (!home || home._isDestroyed || !Array.isArray(home.menuData)) return;
    if (!navigation.authorized) {
      for (var index = home.menuData.length - 1; index >= 0; index -= 1) {
        if (home.menuData[index].__platformSiteGroup) home.menuData.splice(index, 1);
      }
    }
    var system = null, copies = 0;
    home.menuData.forEach(function (group) {
      if (String(group.menu_name || '').trim() === '系统管理') system = group;
      (group.children || []).forEach(function (item) { if (own(item)) copies += 1; });
    });
    if (navigation.authorized && system && copies === 1 && (system.children || []).some(own)) return;
    home.menuData.forEach(function (group) { if ((group.children || []).some(own)) home.$set(group, 'children', group.children.filter(function (item) { return !own(item); })); });
    if (!navigation.authorized) return;
    var entry = {id: '__platform_site_config', menu_name: 'IP管理', menu_link: PATH, permissions_list: ['r', 'u'], __platformSiteMenu: true};
    if (system) home.$set(system, 'children', (system.children || []).concat([entry]));
    else home.menuData.push({id: '__platform_site_system', menu_name: '系统管理', menu_link: '', children: [entry], __platformSiteGroup: true});
  }
  function authorize(value) { navigation.authorized = value === true; updateMenu(navigation.home); }
  function watchHome(app) {
    var home = findHome(app); if (!home || home === navigation.home) { updateMenu(home); return; }
    navigation.home = home; updateMenu(home);
    var unwatch = home.$watch('menuData', function () { updateMenu(home); }, {deep: true});
    home.$once('hook:beforeDestroy', function () { unwatch(); if (navigation.home === home) navigation.home = null; });
  }
  function capability(app) {
    var token = root.localStorage && root.localStorage.getItem('token');
    if (!token) { navigation.token = null; navigation.promise = null; authorize(false); return; }
    if (token === navigation.token) return navigation.promise;
    navigation.token = token; authorize(false);
    navigation.promise = app.$http.get(api('config')).then(data).then(function (value) {
      if (navigation.token === token) authorize(value.can_edit === true);
    }).catch(function (error) {
      if (navigation.token !== token) return;
      authorize(false);
      if (!denied(error)) { navigation.token = null; root.setTimeout(function () { if (!app._isDestroyed) capability(app); }, 3000); }
    });
    return navigation.promise;
  }
  function installRoute(router) {
    if (router.__platformSiteInstalled) return;
    var routes = router.options.routes, home = routes.filter(function (route) { return route.name === 'Home'; })[0];
    if (!home) return;
    var children = (home.children || []).slice();
    if (!children.some(function (route) { return route.name === NAME || route.path === PATH.slice(1); })) children.push({path: PATH.slice(1), name: NAME,
      component: component, meta: {title: 'IP管理', requireAuth: true, keepAlive: false}});
    var next = routes.map(function (route) { return route === home ? Object.assign({}, route, {children: children}) : route; });
    router.matcher = new router.constructor({routes: next, mode: router.mode, base: router.options.base}).matcher;
    router.options.routes = next; router.__platformSiteInstalled = true;
    if (router.currentRoute.path === PATH) router.replace(router.currentRoute.fullPath).catch(function () {});
  }
  function styles() {
    if (root.document.getElementById('platform-site-ui-style')) return;
    var element = root.document.createElement('style'); element.id = 'platform-site-ui-style';
    element.textContent = '.platform-site-config{padding:24px;color:#26384c;background:#f4f7fb;min-height:100%;box-sizing:border-box;font-size:14px}.platform-site-config h2{margin:0 0 8px;font-size:22px}.platform-site-config h3{margin:0 0 14px;font-size:16px}.platform-site-config p{line-height:1.65;margin:8px 0}.platform-site-config small{display:block;color:#64758b;line-height:1.7}.site-config-heading,.site-config-actions,.site-config-footer{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:18px}.site-config-heading p{color:#66788f}.site-config-card{background:#fff;border:1px solid #e1e8f1;border-radius:8px;padding:20px;margin:0 0 18px}.site-config-summary{display:grid;grid-template-columns:minmax(220px,1fr) minmax(260px,1fr);gap:28px}.site-config-identity code{display:block;font-size:12px;overflow-wrap:anywhere;margin:8px 0;color:#3d5776}.site-config-field{max-width:620px}.site-config-field label{display:block;margin:10px 0 8px;font-weight:600}.platform-site-config input,.platform-site-config select{height:36px;border:1px solid #cdd8e6;border-radius:5px;padding:0 11px;color:#26384c;background:#fff;box-sizing:border-box;font:inherit}.platform-site-config input{width:100%}.platform-site-config input:focus,.platform-site-config select:focus{outline:2px solid #c7dbff;outline-offset:1px}.platform-site-config input:disabled,.platform-site-config select:disabled{background:#f3f6fa;color:#64758b}.site-config-field small{margin-top:9px}.site-config-button{border:1px solid #c9d5e5;border-radius:5px;background:#fff;color:#35516f;min-height:36px;padding:7px 16px;font:inherit;cursor:pointer}.site-config-button+.site-config-button{margin-left:10px}.site-config-button.is-primary{background:#2f65d9;border-color:#2f65d9;color:#fff}.site-config-button:disabled{opacity:.5;cursor:default}.site-config-table-scroll{overflow-x:auto}.site-config-table{border-collapse:collapse;table-layout:fixed;width:100%;min-width:630px;margin:16px 0}.site-config-table th,.site-config-table td{text-align:left;padding:12px;border-bottom:1px solid #e8edf4;vertical-align:middle;overflow-wrap:anywhere}.site-config-table thead th{background:#f4f7fb;font-weight:600;color:#526983}.site-config-table tbody th{width:22%;font-weight:500}.site-config-table select{width:100%;max-width:240px}.site-config-address{color:#46617e;font-family:ui-monospace,Consolas,monospace}.site-config-message{padding:12px 16px;border-radius:6px;margin-bottom:16px;line-height:1.6}.site-config-message p{margin:2px 0}.site-config-message.is-error{background:#fff0f0;color:#b03333;border:1px solid #f4d0d0}.site-config-message.is-success{background:#eaf8f0;color:#246747;border:1px solid #c9e8d6}.site-config-error{color:#b03333}.site-config-pending{color:#94651e}.site-config-preview{border-color:#b5ccef}.site-config-preview details{margin:14px 0;color:#526983}.site-config-preview summary{cursor:pointer}.site-config-preview li{padding:3px 0;overflow-wrap:anywhere}.site-config-preview a{color:#245ed0}.site-config-footer{color:#64758b}.site-config-confirm .el-message-box__message p{white-space:pre-line}@media(max-width:800px){.platform-site-config{padding:14px}.site-config-summary{grid-template-columns:1fr}.site-config-heading{align-items:flex-start}.site-config-card{padding:16px}.site-config-footer{align-items:flex-start;flex-direction:column}}';
    element.textContent += '.site-network-panel{box-sizing:border-box;background:#fff;border:1px solid #e1e8f1;border-radius:8px;padding:20px;margin:0 0 18px;color:#26384c;font-size:14px}.site-network-panel.is-cloud{margin:20px 20px 0}.site-network-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}.site-network-panel h3{font-size:16px;margin:0 0 8px}.site-network-panel p{line-height:1.6;margin:6px 0}.site-network-heading p,.site-network-label,.site-network-footnote,.site-network-panel small{color:#64758b}.site-network-summary{display:grid;grid-template-columns:1fr 1fr 1.6fr;gap:20px;background:#f5f8fc;border-radius:6px;padding:16px;margin:16px 0}.site-network-label{display:block;font-size:12px;margin-bottom:8px}.site-network-summary strong{font-size:15px;overflow-wrap:anywhere}.site-network-summary small{display:block;line-height:1.6;margin-top:6px}.site-network-status.is-ready{color:#24734f}.site-network-status.is-unknown,.site-network-warning{color:#94651e}.site-network-warning{line-height:1.7}.site-network-details{margin:14px 0}.site-network-details summary{cursor:pointer;color:#315d99;padding:5px 0}.site-network-table-scroll{overflow-x:auto}.site-network-table{border-collapse:collapse;width:100%;min-width:650px;margin:12px 0;table-layout:fixed}.site-network-table th,.site-network-table td{text-align:left;border-bottom:1px solid #e8edf4;padding:11px;overflow-wrap:anywhere;vertical-align:top}.site-network-table thead th{background:#f4f7fb;color:#526983;font-weight:600}.site-network-table tbody th{font-weight:500}.site-network-table small{display:block;font-weight:400;margin-top:5px}.site-network-address{margin-bottom:5px}.site-network-address code,.site-network-identity code{font:12px ui-monospace,Consolas,monospace;overflow-wrap:anywhere}.site-network-badge{display:inline-block;background:#eaf5ee;color:#286846;border-radius:3px;padding:1px 5px;font-size:11px;margin-left:6px}.site-network-footnote{display:flex;flex-wrap:wrap;gap:8px 18px;border-top:1px solid #eef2f7;padding-top:12px;font-size:12px;line-height:1.7}.site-network-identity{color:#526983;font-size:12px}@media(max-width:800px){.site-network-panel{padding:16px}.site-network-panel.is-cloud{margin:14px 14px 0}.site-network-summary{grid-template-columns:1fr;gap:14px}.site-network-heading{gap:8px}.site-network-heading .site-config-button{padding:6px 9px;white-space:nowrap}}';
    element.textContent += '.site-network-editor{border-top:1px solid #e1e8f1;margin-top:20px;padding-top:18px}.site-network-edit-heading{display:flex;align-items:center;flex-wrap:wrap;gap:12px}.site-network-edit-heading h4{font-size:15px;margin:0 auto 0 0}.site-network-edit-form,.site-network-plan,.site-network-job{background:#f8faff;border:1px solid #e1e8f1;padding:18px;margin-top:16px;border-radius:6px}.site-network-edit-grid{display:grid;grid-template-columns:repeat(2,minmax(180px,1fr));gap:12px 24px;margin-bottom:18px}.site-network-editor .site-config-field{max-width:none}.site-network-editor select{width:100%}.site-network-check{display:block;margin:14px 0;line-height:1.8}.site-network-check input{width:16px;height:16px;vertical-align:middle;margin-right:8px}.site-network-plan h4,.site-network-job h4{margin:0 0 12px}.site-network-editor ul{line-height:1.9}.site-network-editor a{color:#245ed0;overflow-wrap:anywhere}@media(max-width:800px){.site-network-edit-grid{grid-template-columns:1fr}.site-network-editor .site-config-button{margin:4px}}';
    root.document.head.appendChild(element);
  }
  function boot(attempt) {
    var element = root.document.getElementById('app'), app = element && element.__vue__;
    if (!app || !app.$router || !app.$http) { if (attempt < 300) root.setTimeout(function () { boot(attempt + 1); }, 100); return; }
    styles();
    app.$router.onReady(function () { installRoute(app.$router); app.$nextTick(function () { watchHome(app); capability(app); }); });
    app.$router.afterEach(function () { app.$nextTick(function () { watchHome(app); capability(app); if (navigation.home && app.$route.path === PATH) navigation.home.menuName = 'IP管理'; }); });
  }
  root.AiMonitorPlatformSiteConfig = {component: component, networkPanel: networkPanel, networkEditor: networkEditor, validate: validate, differences: differences, roles: roles,
    installRoute: installRoute, boot: boot, path: PATH};
  if (!bootstrapNetworkHandoff()) boot(0);
})(window);
