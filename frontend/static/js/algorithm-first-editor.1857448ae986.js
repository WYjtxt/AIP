/* Algorithm-first batch continuation: existing editors keep their own geometry. */
(function (root) {
  'use strict';
  var installed = false, app = null;
  function id(value) { return /^[1-9][0-9]*$/.test(String(value || '')) ? String(Number(value)) : ''; }
  function formCamera(form) { return id(form && (form.Equipment_id || form.equipment_name)); }
  function context(vm) {
    var route = vm && vm.$route, query = route && route.query || {};
    if (!route || !/^\/(?:sfgl_childs?|sxtpz_childs?)$/.test(route.path)) return null;
    var taskId = id(query.conf_id || query.id), inferred = vm._algorithmFirstInferredContext;
    if (!query.batch_request_id && inferred && inferred.path === route.path && inferred.task === taskId &&
        (!inferred.formRef || inferred.formRef === vm.form && inferred.camera === formCamera(vm.form) && inferred.library === id(vm.form.Algorithm_library_id))) return inferred;
    if (!/^[a-f0-9]{32}$/.test(query.batch_request_id || '')) return null;
    var camera = id(query.batch_equipment_id), task = id(query.conf_id || query.id);
    return camera && task ? {request: query.batch_request_id, camera: camera, task: task,
      key: route.path + ':' + query.batch_request_id + ':' + camera + ':' + task} : null;
  }
  function isBatch(vm) { return !!context(vm); }
  function endpoint(request) { return ((root.wgParameter && root.wgParameter.url_5000) || '').replace(/\/$/, '') + '/model_view/algorithm_first/jobs/' + request; }
  function taskContextEndpoint(task) { return ((root.wgParameter && root.wgParameter.url_5000) || '').replace(/\/$/, '') + '/model_view/algorithm_first/task-context?conf_id=' + encodeURIComponent(task); }
  function resultPath(request) { return '/algorithm-first?request_id=' + encodeURIComponent(request); }
  function sameItem(item, ctx) { return item && item.status === 'created' && id(item.equipment_id) === ctx.camera && id(item.conf_id) === ctx.task; }
  function pending(item) { return item && item.status === 'created' && id(item.conf_id) && !item.deleted && item.setup_complete !== true && item.needs_setup === true; }
  function running(item) { return !!item && String(item.run_status) === '1' && item.runtime_healthy === true; }
  function newIntent() { var bytes = new Uint8Array(16), value = ''; root.crypto.getRandomValues(bytes); for (var i = 0; i < bytes.length; i += 1) value += ('0' + bytes[i].toString(16)).slice(-2); return value; }
  function startKey(state) { return 'AiMonitorAlgorithmFirstStart:' + String(root.localStorage.getItem('userId') || 'current') + ':' + state.ctx.request + ':' + state.ctx.task + ':' + state.ctx.camera; }
  function rememberStart(state) { try { root.localStorage.setItem(startKey(state), JSON.stringify({intent_id: state.intent, task: state.ctx.task, camera: state.ctx.camera})); return true; } catch (ignore) { return false; } }
  function forgetStart(state) { try { var saved = JSON.parse(root.localStorage.getItem(startKey(state)) || 'null'); if (saved && saved.intent_id === state.intent) root.localStorage.removeItem(startKey(state)); } catch (ignore) {} }
  function stopStartPoll(state) { if (state.startTimer) root.clearTimeout(state.startTimer); state.startTimer = null; }
  function currentState(state) { var ctx = context(state.vm); return !state.disposed && ctx && ctx.key === state.ctx.key; }
  function text(tag, value, className) { var node = root.document.createElement(tag); node.textContent = value; if (className) node.className = className; return node; }
  function button(label, action, disabled) { var node = text('button', label, 'af-editor-button'); node.type = 'button'; node.disabled = !!disabled; node.addEventListener('click', action); return node; }
  function push(router, path, replace) { var result = router[replace ? 'replace' : 'push'](path); return result && typeof result.then === 'function' ? result : Promise.resolve(); }
  function editorPath(item, request) {
    var path = item.edit_path;
    if (typeof path !== 'string' || !/^\/(?:sfgl_childs?|sxtpz_childs?)\?/.test(path)) return null;
    var url = new root.URL(path, root.location.origin), task = id(url.searchParams.get('conf_id') || url.searchParams.get('id'));
    if (url.origin !== root.location.origin || task !== id(item.conf_id) || !id(item.equipment_id)) return null;
    url.searchParams.set('batch_request_id', request); url.searchParams.set('batch_equipment_id', id(item.equipment_id));
    return url.pathname + url.search;
  }
  function invokes(listener, method) {
    if (listener === method) return true;
    if (listener && listener.fns) return Array.isArray(listener.fns) ? listener.fns.indexOf(method) >= 0 : listener.fns === method;
    return false;
  }
  function hideOriginalSave(state) {
    var nodes = state.vm.$el && state.vm.$el.querySelectorAll('button');
    if (!nodes) return;
    Array.prototype.forEach.call(nodes, function (node) {
      if (state.panel && state.panel.contains(node)) return;
      var view = node.__vue__, listener = view && view.$listeners && view.$listeners.click;
      if (!invokes(listener, state.vm.sub_fn) || state.hidden.some(function (item) { return item.node === node; })) return;
      state.hidden.push({node: node, display: node.style.display}); node.style.display = 'none';
    });
  }
  function emptyParameters(value) {
    if (value === null || value === undefined || value === '') return true;
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'string') { try { var parsed = JSON.parse(value); return Array.isArray(parsed) && parsed.length === 0; } catch (ignore) {} }
    return false;
  }
  function applySetupDraft(state) {
    var vm = state.vm, form = vm.form, defaults = state.item && state.item.setup_defaults;
    if (state.defaultsChecked || !state.valid || !form || id(form.id) !== state.ctx.task) return;
    if (defaults && (!id(form.Algorithm_library_id) || !id(form.model_template_config_id))) return;
    state.defaultsChecked = true;
    if (!defaults || !emptyParameters(form.template_data) || typeof vm.normalizeAlgorithmTemplateRows !== 'function' ||
        id(defaults.equipment_id) !== state.ctx.camera || id(defaults.Algorithm_library_id) !== id(form.Algorithm_library_id) ||
        id(defaults.model_template_config_id) !== id(form.model_template_config_id) || !Array.isArray(defaults.template_data)) return;
    var rows = vm.normalizeAlgorithmTemplateRows(JSON.parse(JSON.stringify(defaults.template_data)));
    if (!Array.isArray(rows) || !rows.length) return;
    vm.$set(form, 'template_data', rows);
    state.notice = '已补入本模板的建议参数，请确认后保存；已有参数与间隔保持原值。';
  }
  function render(state) {
    if (!currentState(state) || !state.vm.$el || state.vm.$el.nodeType !== 1) return;
    applySetupDraft(state);
    var items = state.job && state.job.items || [];
    var labels = items.filter(function (item) { return item.status === 'created'; }).map(function (item) {
      var current = sameItem(item, state.ctx);
      var label = item.deleted ? '任务已删除' : running(item) ? '已启动' : item.setup_complete === true ? '已配置待启动' : item.needs_setup === true ? '待配置' : '状态待确认';
      if (String(item.run_status) === '1' && !running(item)) label = item.runtime_healthy === false ? '运行异常' : '启动中';
      if (current && state.startPhase === 'failed') label = '已配置 · 启动失败';
      return (current ? '当前：' : '') + String(item.name || '摄像机' + item.equipment_id) + ' · ' + label;
    });
    var awaiting = state.startPhase === 'unknown' || state.startPhase === 'pending' || state.startPhase === 'warming', retry = state.startPhase === 'failed';
    var refreshDisabled = state.loading || state.checking;
    var startDisabled = !state.valid || refreshDisabled || state.queryingStart || state.clickUntil > Date.now();
    var retryDisabled = !state.retryAllowed || refreshDisabled;
    var view = JSON.stringify([state.error, state.notice, labels, awaiting, retry, startDisabled, retryDisabled,
      refreshDisabled, state.confirmed, state.checking]);
    var panel = state.panel;
    if (!panel) { panel = state.panel = text('section', '', 'af-editor-panel'); panel.setAttribute('data-algorithm-first-editor', ''); panel.setAttribute('aria-label', '本批次逐路配置'); }
    if (panel.parentNode !== state.vm.$el) state.vm.$el.insertBefore(panel, state.vm.$el.firstChild);
    // Vue also updates this page for input drafts, preview and count polling.
    // Reuse the existing buttons and their listeners if the batch display did not change.
    if (state.renderedView === view) { hideOriginalSave(state); return; }
    while (panel.firstChild) panel.removeChild(panel.firstChild);
    panel.appendChild(text('h3', '本批次逐路配置'));
    panel.appendChild(text('p', '各摄像机独立配置。点击“保存并启动”会一并保存区域和参数，通过校验后自动启动，再进入下一路；未完成时会提示具体缺项。'));
    if (state.error) { var error = text('p', state.error, 'af-editor-error'); error.setAttribute('role', 'alert'); panel.appendChild(error); }
    if (state.notice) panel.appendChild(text('p', state.notice, 'af-editor-notice'));
    var list = text('ul', '', 'af-editor-list');
    labels.forEach(function (label) { list.appendChild(text('li', label)); });
    if (list.childNodes.length) panel.appendChild(list);
    var actions = text('div', '', 'af-editor-actions');
    actions.appendChild(button(awaiting ? '查询运行状态' : '保存并启动', function () {
      if (!state.valid || state.loading || state.checking || !currentState(state)) return;
      if (awaiting) { queryStart(state); return; }
      if (retry) { forgetStart(state); state.startPhase = ''; state.intent = ''; state.retryAllowed = false; }
      state.error = ''; state.notice = ''; state.vm._algorithmOperationalEdited = true;
      var calibration = root.AiMonitorUniquenessEditor;
      if (calibration && calibration.supported(state.vm) && typeof calibration.saveBeforeBatch === 'function') {
        state.checking = true; state.notice = '正在保存本路区域与检测参数…'; render(state);
        calibration.saveBeforeBatch(state.vm).then(function () {
          if (!currentState(state)) return;
          state.checking = false; state.notice = ''; render(state); state.vm.sub_fn();
        }).catch(function (error) {
          if (!currentState(state)) return;
          state.checking = false; state.notice = ''; state.error = error.message || '区域配置保存失败，请检查后重试。'; render(state);
        });
      } else state.vm.sub_fn();
    }, startDisabled));
    if (retry) actions.appendChild(button('仅重试启动', function () {
      var calibration = state.vm._uniquenessPanel;
      if (calibration && (calibration.dirty || calibration.drawing)) { state.error = '区域或参数已修改，请点击“保存并启动”保存后启动。'; render(state); return; }
      if (state.retryAllowed) beginStart(state);
    }, retryDisabled));
    actions.appendChild(button(state.confirmed ? '重新检查保存结果' : '刷新本批次状态', function () {
      if (awaiting || retry) queryStart(state); else refresh(state);
    }, refreshDisabled));
    actions.appendChild(button('返回本批次结果', function () { push(state.vm.$router, resultPath(state.ctx.request)); }, state.checking));
    panel.appendChild(actions); state.renderedView = view; hideOriginalSave(state);
  }
  function refresh(state) {
    if (!currentState(state)) return Promise.resolve(false);
    var sequence = ++state.sequence; state.loading = true; render(state);
    return state.vm.$http.get(endpoint(state.ctx.request)).then(function (response) {
      if (!currentState(state) || sequence !== state.sequence) return false;
      var body = response && response.data, value = body && body.data;
      if (!body || Number(body.code) !== 200 || !value || value.request_id !== state.ctx.request || !Array.isArray(value.items)) throw new Error('invalid_job');
      var item = value.items.filter(function (row) { return sameItem(row, state.ctx); })[0];
      state.job = value; state.item = item;
      state.valid = !!item && !item.deleted;
      if (!state.valid) state.error = '当前任务不属于本批次已创建结果，或已被删除。请返回本批次结果核对。';
      else if (state.vm.form && state.vm.form.id && id(state.vm.form.id) !== state.ctx.task) { state.valid = false; state.error = '编辑页尚未加载当前任务，请刷新页面后再配置。'; }
      else if (!state.startPhase) state.error = '';
      if (state.valid) state.vm._algorithmOperationalEdited = true;
      return state.valid;
    }).catch(function () {
      if (currentState(state) && sequence === state.sequence) { state.valid = false; state.error = '本批次状态暂无法确认，请刷新状态后重试。不会自动跳转或再次提交保存。'; }
      return false;
    }).then(function (value) { if (currentState(state) && sequence === state.sequence) { state.loading = false; render(state); } return value; });
  }
  function attach(vm) {
    var ctx = context(vm);
    if (!ctx || typeof vm.sub_fn !== 'function' || typeof vm.goback !== 'function') return null;
    var state = vm._algorithmFirstEditor;
    if (state && state.ctx.key === ctx.key && !state.disposed) { render(state); return state; }
    if (state) dispose(vm);
    state = vm._algorithmFirstEditor = {vm: vm, ctx: ctx, job: null, item: null, valid: false, loading: false,
      checking: false, confirmed: false, disposed: false, sequence: 0, panel: null, hidden: [], error: '', notice: '', clickUntil: 0, defaultsChecked: false,
      startPhase: '', intent: '', startSequence: 0, startTimer: null, startPolls: 0, queryingStart: false, retryAllowed: false, saveSequence: 0};
    vm._algorithmFirstWasBatch = true;
    render(state); refresh(state).then(function (valid) {
      if (!valid || !currentState(state)) return;
      var saved; try { saved = JSON.parse(root.localStorage.getItem(startKey(state)) || 'null'); } catch (ignore) {}
      if (saved && /^[a-f0-9]{32}$/.test(saved.intent_id || '') && saved.task === state.ctx.task && saved.camera === state.ctx.camera) {
        state.intent = saved.intent_id; state.confirmed = true; state.startPhase = 'unknown'; queryStart(state);
      }
    }); return state;
  }
  function dispose(vm) {
    var state = vm._algorithmFirstEditor;
    if (!state) return;
    state.disposed = true; state.sequence += 1;
    state.startSequence += 1; stopStartPoll(state);
    if (state.panel && state.panel.parentNode) state.panel.parentNode.removeChild(state.panel);
    state.hidden.forEach(function (item) { item.node.style.display = item.display; });
    vm._algorithmFirstEditor = null;
  }
  function beforeSave(vm) {
    var ctx = context(vm);
    if (!ctx) return null;
    var state = attach(vm);
    if (!state || !state.valid || state.loading || state.checking || state.startPhase === 'pending' || state.startPhase === 'unknown' || state.startPhase === 'warming' || state.clickUntil > Date.now()) return false;
    state.clickUntil = Date.now() + 600;
    root.setTimeout(function () { if (currentState(state)) render(state); }, 650);
    vm._algorithmOperationalEdited = true;
    render(state);
    state.saveSequence += 1; return {key: ctx.key, save: state.saveSequence};
  }
  function advance(state) {
    if (!currentState(state) || !state.valid || !state.confirmed || state.item.setup_complete !== true || !running(state.item)) return;
    if (state.job.status !== 'completed' && state.job.status !== 'failed') { state.notice = '本路已启动；本批次仍在创建，请稍后刷新结果。'; render(state); return; }
    var next = state.job.items.filter(function (item) { return pending(item) && !sameItem(item, state.ctx); })[0];
    if (!next) { push(state.vm.$router, resultPath(state.ctx.request)); return; }
    var target = editorPath(next, state.ctx.request), request = state.ctx.request, router = state.vm.$router;
    if (!target) { state.error = '下一路编辑地址暂无法确认，请返回本批次结果操作。'; render(state); return; }
    push(router, resultPath(request), true).then(function () { return new Promise(function (resolve) { (app || state.vm).$nextTick(resolve); }); })
      .then(function () { if (router.currentRoute.path === '/algorithm-first' && router.currentRoute.query.request_id === request) return push(router, target, true); }).catch(function () {});
  }
  function acceptStart(state, value) {
    if (!currentState(state)) return;
    if (!value || value.intent_id !== state.intent || id(value.conf_id) !== state.ctx.task || id(value.equipment_id) !== state.ctx.camera) { unknownStart(state); return; }
    state.checking = false; state.queryingStart = false;
    if ((value.status === 'started' || value.status === 'already_running') && String(value.run_status) === '1' && value.setup_complete === true && value.activation_accepted === true && value.runtime_healthy === true) {
      state.startPhase = 'running'; state.error = ''; state.notice = '本路已启动，正在进入下一路。';
      state.item.run_status = '1'; state.item.stopped = false; state.item.setup_complete = true; state.item.runtime_healthy = true; forgetStart(state); stopStartPoll(state); render(state); advance(state); return;
    }
    if (value.activation_accepted === true && String(value.run_status) === '1') {
      state.startPhase = 'warming'; state.retryAllowed = false; state.item.run_status = '1'; state.item.stopped = false;
      state.item.runtime_healthy = value.runtime_healthy; state.error = '';
      state.notice = value.runtime_message || '启动已提交，正在等待实际推理正常。';
      if (value.runtime_healthy === false) { state.error = state.notice; state.notice = '请检查任务运行状态；修改配置前请先在列表停止任务。'; }
      stopStartPoll(state); render(state);
      if (state.startPolls < 60) state.startTimer = root.setTimeout(function () { queryStart(state); }, 2000);
      return;
    }
    if (value.status === 'unknown' || value.status === 'pending' || value.terminal !== true) { unknownStart(state); return; }
    stopStartPoll(state); state.startPhase = 'failed'; state.retryAllowed = value.retry_allowed === true;
    if (value.status === 'blocked' && value.setup_complete !== true) { forgetStart(state); state.startPhase = ''; state.confirmed = false; state.retryAllowed = false; }
    state.notice = ''; state.error = value.message || (String(value.run_status) === '2' ? '本路当前未运行，请核对后明确重试启动。' : '本路启动失败，请重试启动。'); render(state);
  }
  function unknownStart(state) {
    if (!currentState(state)) return;
    state.checking = false; state.queryingStart = false; state.startPhase = 'unknown'; state.retryAllowed = false;
    state.notice = ''; state.error = '启动结果尚未确认，系统只查询本次请求，不会再次提交启动。'; render(state);
    stopStartPoll(state); if (state.startPolls < 10) state.startTimer = root.setTimeout(function () { queryStart(state); }, 2000);
  }
  function queryStart(state) {
    if (!currentState(state) || !state.intent || state.queryingStart) return;
    stopStartPoll(state); state.queryingStart = true; state.startPolls += 1; var intent = state.intent, sequence = state.startSequence;
    return state.vm.$http.get(endpoint(state.ctx.request) + '/start?intent_id=' + encodeURIComponent(intent)).then(function (response) {
      if (!currentState(state) || intent !== state.intent || sequence !== state.startSequence) return;
      var body = response && response.data; if (!body || Number(body.code) !== 200) throw new Error('unconfirmed_start'); acceptStart(state, body.data);
    }).catch(function () { if (currentState(state) && intent === state.intent && sequence === state.startSequence) unknownStart(state); });
  }
  function beginStart(state) {
    if (!currentState(state) || !state.valid || state.item.setup_complete !== true || !state.confirmed || state.checking) return;
    if (running(state.item)) { state.startPhase = 'running'; advance(state); return; }
    state.intent = newIntent(); state.startSequence += 1; state.startPolls = 0; stopStartPoll(state);
    if (!rememberStart(state)) { state.startPhase = 'failed'; state.retryAllowed = true; state.error = '浏览器无法保存启动请求标识，请检查存储后重试启动。'; render(state); return; }
    var intent = state.intent, sequence = state.startSequence; state.checking = true; state.startPhase = 'pending'; state.error = ''; state.notice = '配置已确认完整，正在启动本路。'; render(state);
    return state.vm.$http.post(endpoint(state.ctx.request) + '/start', {equipment_id: Number(state.ctx.camera), conf_id: Number(state.ctx.task), intent_id: intent})
      .then(function (response) { if (!currentState(state) || state.intent !== intent || state.startSequence !== sequence) return;
        var body = response && response.data; if (!body || Number(body.code) !== 200) throw new Error('unconfirmed_start'); acceptStart(state, body.data); })
      .catch(function () { if (currentState(state) && state.intent === intent && state.startSequence === sequence) unknownStart(state); });
  }
  function afterSaved(vm, savedContext) {
    var active = context(vm);
    if (vm._isDestroyed || vm._isBeingDestroyed || (savedContext && (!active || savedContext.key !== active.key))) return !!savedContext || !!vm._algorithmFirstWasBatch;
    if (!active) return !!vm._algorithmFirstWasBatch;
    var state = attach(vm);
    if (!state || state.checking) return true;
    if (savedContext && savedContext.save && savedContext.save !== state.saveSequence) return true;
    if (state.startPhase === 'unknown' || state.startPhase === 'pending' || state.startPhase === 'warming') { queryStart(state); return true; }
    state.confirmed = true; state.checking = true; state.notice = '已保存，正在核对本路配置状态。'; render(state);
    refresh(state).then(function (valid) {
      if (!currentState(state)) return;
      state.checking = false;
      if (!valid) { render(state); return; }
      if (state.item.setup_complete !== true) {
        var missing = Array.isArray(state.item.setup_missing) ? state.item.setup_missing.filter(function (value) { return typeof value === 'string'; }).join('、') : '';
        state.notice = ''; state.error = state.item.setup_message || ('本路配置尚未完成' + (missing ? '：' + missing : '，请确认场景、绘制及参数。')); render(state); return;
      }
      beginStart(state);
    });
    return true;
  }
  function candidate(vm) {
    if (!vm || !vm.$vnode || !vm.$vnode.data || !vm.$vnode.data.routerView) return;
    if (isBatch(vm)) attach(vm);
    else { if (vm._algorithmFirstEditor) dispose(vm); discover(vm); }
  }
  function discover(vm) {
    var route = vm.$route, query = route && route.query || {}, form = vm.form;
    if (!route || !/^\/(?:sfgl_childs?|sxtpz_childs?)$/.test(route.path) || query.batch_request_id || !form || typeof vm.sub_fn !== 'function') return;
    var task = id(query.conf_id || query.id), marker = typeof form.Algorithm_config_ps === 'string' && /\[batch:([a-f0-9]{32})\]/.exec(form.Algorithm_config_ps);
    var camera = formCamera(form), library = id(form.Algorithm_library_id);
    if (!task || id(form.id) !== task || !camera || !library) return;
    var key = route.path + ':' + task + ':' + camera + ':' + library + ':' + (marker ? marker[1] : 'lookup');
    var previous = vm._algorithmFirstDiscovery;
    if (previous && previous.key === key && previous.form === form) return;
    var attempt = vm._algorithmFirstDiscovery = {key: key, form: form};
    function current() {
      var now = vm.$route, query = now && now.query || {};
      return !vm._isDestroyed && !vm._isBeingDestroyed && vm._algorithmFirstDiscovery === attempt &&
        vm.form === form && now && now.path === route.path && !query.batch_request_id && id(query.conf_id || query.id) === task &&
        id(form.id) === task && formCamera(form) === camera && id(form.Algorithm_library_id) === library;
    }
    function loadJob(request) {
      if (!current()) return;
      return vm.$http.get(endpoint(request)).then(function (response) {
        if (!current()) return;
        var body = response && response.data, job = body && body.data;
        if (!body || Number(body.code) !== 200 || !job || job.request_id !== request || !Array.isArray(job.items)) return;
        var item = job.items.filter(function (row) { return row.status === 'created' && id(row.conf_id) === task && id(row.equipment_id) === camera && !row.deleted; })[0];
        if (!item) return;
        vm._algorithmFirstInferredContext = {request: request, camera: camera, task: task, path: route.path,
          library: library, formRef: form, key: route.path + ':' + request + ':' + camera + ':' + task};
        attach(vm);
      });
    }
    // Historical markers remain a lookup hint. Membership is always checked
    // against the actor-owned journal; visible remarks are never rewritten.
    var lookup = marker ? loadJob(marker[1]) : vm.$http.get(taskContextEndpoint(task)).then(function (response) {
      if (!current()) return;
      var body = response && response.data, value = body && body.data;
      if (!body || Number(body.code) !== 200 || !value || !/^[a-f0-9]{32}$/.test(value.request_id || '') ||
          id(value.conf_id) !== task || id(value.equipment_id) !== camera || id(value.algorithm_id) !== library) return;
      return loadJob(value.request_id);
    });
    if (lookup && lookup.catch) lookup.catch(function () {});
  }
  function visit(vm) { candidate(vm); (vm.$children || []).forEach(visit); }
  function styles() {
    if (root.document.getElementById('algorithm-first-editor-style')) return;
    var node = text('style', '.af-editor-panel{background:#f0f6ff;border:1px solid #bfd2f4;border-radius:6px;padding:14px 18px;margin:12px 0 18px;color:#26384c}.af-editor-panel h3{margin:0 0 8px}.af-editor-panel p{line-height:1.6;margin:7px 0}.af-editor-list{display:flex;gap:8px 24px;flex-wrap:wrap;padding-left:20px}.af-editor-actions{display:flex;gap:10px;flex-wrap:wrap}.af-editor-button{padding:8px 14px;border:1px solid #8caee8;border-radius:4px;color:#2456a5;background:white;cursor:pointer}.af-editor-button:first-child{background:#2f65d9;color:white}.af-editor-button:disabled{opacity:.5;cursor:default}.af-editor-error{color:#a33434}.af-editor-notice{color:#506887}');
    node.id = 'algorithm-first-editor-style'; root.document.head.appendChild(node);
  }
  function boot(attempt) {
    var element = root.document.getElementById('app'); app = element && element.__vue__;
    if (!app || !app.$router || !app.$http || !app.$options._base) { if (attempt < 300) root.setTimeout(function () { boot(attempt + 1); }, 100); return; }
    if (!installed) {
      installed = true; styles();
      app.$options._base.mixin({mounted: function () { candidate(this); }, updated: function () { candidate(this); }, beforeDestroy: function () { dispose(this); }});
      app.$router.afterEach(function () { app.$nextTick(function () { visit(app); }); });
    }
    app.$nextTick(function () { visit(app); });
  }
  root.AiMonitorAlgorithmFirstEditor = {isBatch: isBatch, beforeSave: beforeSave, afterSaved: afterSaved, attach: attach, boot: boot, editorPath: editorPath};
  boot(0);
})(window);
