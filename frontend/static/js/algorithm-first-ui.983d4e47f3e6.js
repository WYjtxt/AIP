/* Algorithm-first creation for the existing authenticated Vue 2 platform. */
(function (root) {
  'use strict';
  var PATH = '/algorithm-first', NAME = 'algorithm_first';
  function api(path) { return ((root.wgParameter && root.wgParameter.url_5000) || '').replace(/\/$/, '') + '/model_view/algorithm_first/' + path; }
  function unpack(response) {
    var body = response && response.data;
    if (!body || Number(body.code) !== 200) throw new Error('request_failed');
    return body.data || {};
  }
  function copy(value) { return JSON.parse(JSON.stringify(value)); }
  function same(left, right) { return String(left) === String(right); }
  function signature(value) { return JSON.stringify(value); }
  function algorithmName(item) {
    if (!item) return '尚未选择';
    var value = String(item.display_name || item.model_name || item.name || item.algorithm_name || '').trim();
    if (!value || /\.(?:om|bmodel|rknn|onnx|pt|zip|tar)(?:\.|$)/i.test(value) || (value.length > 80 && value.indexOf('_') >= 0)) return '算法 ' + String(item.id || item.algorithm_id || '');
    return value;
  }
  function algorithmVersion(item) { return item && item.version != null && String(item.version).trim() ? '版本 ' + String(item.version).trim() : ''; }
  function failure(error, fallback) {
    var status = error && error.response && Number(error.response.status);
    return status === 401 ? '登录已失效，请重新登录。' : status === 403 ? '当前账号没有新增算法配置权限。' : fallback;
  }
  function navigate(vm, path) {
    var result = vm.$router.push(path);
    if (result && typeof result.catch === 'function') result.catch(function () {});
  }
  function editPath(item) {
    var path = item && item.edit_path;
    if (typeof path === 'string' && /^\/(?:sfgl_childs?|sxtpz_childs?|sfgl)(?:\?|$)/.test(path)) return path;
    return item && item.conf_id ? '/sfgl_child?conf_id=' + encodeURIComponent(String(item.conf_id)) : '/sfgl';
  }
  function bareCreation(path, query) {
    return (['/sfgl_child', '/sxtpz_child'].indexOf(path) >= 0 && !query.conf_id) ||
      (['/sfgl_childs', '/sxtpz_childs'].indexOf(path) >= 0 && !query.id);
  }
  function batchEditorPath(item, id) {
    var path = editPath(item);
    if (!item || item.status !== 'created' || !/^[0-9a-f]{32}$/.test(String(id || '')) || !item.conf_id || !/^\/(?:sfgl_child|sxtpz_child)\?/.test(path)) return path;
    var position = path.indexOf('?'), query = path.slice(position + 1).split('&').filter(function (part) { return part && !/^batch_(?:request_id|equipment_id)=/.test(part); });
    query.push('batch_request_id=' + encodeURIComponent(id), 'batch_equipment_id=' + encodeURIComponent(String(item.equipment_id)));
    return path.slice(0, position) + '?' + query.join('&');
  }
  function pendingKey() { return 'AiMonitorAlgorithmFirstPending:' + String(root.localStorage.getItem('userId') || 'current'); }
  function requestId() {
    var bytes = new Uint8Array(16), result = '';
    if (root.crypto && root.crypto.getRandomValues) root.crypto.getRandomValues(bytes);
    else for (var i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
    for (var j = 0; j < bytes.length; j += 1) result += ('0' + bytes[j].toString(16)).slice(-2);
    return result;
  }
  function button(h, text, click, disabled, primary, attrs) {
    return h('button', {class: ['af-button', primary && 'is-primary'], attrs: Object.assign({type: 'button', disabled: !!disabled}, attrs || {}), on: {click: click}}, text);
  }
  function select(h, id, value, options, change, disabled) {
    return h('select', {attrs: {id: id, disabled: !!disabled}, domProps: {value: String(value == null ? '' : value)},
      on: {change: function (event) { change(event.target.value); }}}, options.map(function (item) {
      return h('option', {key: String(item.id), attrs: {value: String(item.id), disabled: !!item.disabled}}, item.name);
    }));
  }
  function input(h, id, value, change, disabled, attrs) {
    return h('input', {attrs: Object.assign({id: id, type: 'text', disabled: !!disabled, autocomplete: 'off'}, attrs || {}),
      domProps: {value: value}, on: {input: function (event) { change(event.target.value); }}});
  }
  function field(h, title, id, control, note) {
    return h('div', {class: 'af-field'}, [h('label', {attrs: {for: id}}, title), control, note ? h('small', note) : null]);
  }
  function stateText(value) { return value === 1 || value === '1' || value === 'running' ? '运行中' : value === 2 || value === '2' || value === 'stopped' ? '已停用' : '已配置'; }
  function onlineText(value) { return value === true || value === 1 || value === '1' ? '在线' : value === false || value === 0 || value === '0' ? '离线' : '状态未知'; }
  function geometryNote(template) {
    if (!template) return '新任务创建时停用；逐路保存完整后自动启动，确认已运行再进入下一路。';
    if (typeof template.message === 'string' && template.message.trim()) return template.message.replace(/[。；]$/, '') + '。逐路保存完整后自动启动，未完整时保持停用。';
    if (template.should_confirm_geometry || template.requires_geometry) return '此模板需要逐路确认' +
      ({line: '计数线和进出方向', polygon: '检测区域', roi: '检测区域', mixed: '检测区域与计数线',
        count_scene: '人数统计场景、计数线或乘车点区域及进出方向', per_camera: '检测区域及场景参数'}[template.geometry_kind] || '检测区域或计数线') + '。逐路保存完整后自动启动，未完整时保持停用。';
    return '新任务创建时停用；逐路保存完整后自动启动，确认已运行再进入下一路。';
  }
  function needsSetup(item) { return item && item.status === 'created' && !item.deleted && (typeof item.setup_complete === 'boolean' ? !item.setup_complete : item.needs_setup === true); }
  function resultState(item) {
    if (item.deleted) return '任务已删除';
    if (item.status !== 'created') return {skipped: '已跳过', failed: '创建失败'}[item.status] || item.status;
    var running = item.stopped === false || item.run_status === 1 || item.run_status === '1' || item.run_status === 'running';
    if (running) return needsSetup(item) ? '已启动 · 运行中（待完善）' : '已启动 · 运行中';
    if (!needsSetup(item) && (item.start_status === 'failed' || item.start_status === 'blocked')) return '已配置 · 启动失败';
    return needsSetup(item) ? '已创建 · 待完善（停用）' : '已配置 · 待启动';
  }

  var component = {
    name: 'AlgorithmFirstConfig',
    data: function () { return {stage: 0, catalog: null, algorithmId: '', items: [], total: 0, page: 1, perPage: 20,
      filters: {mine_id: '', parent_id: '', search: ''}, selected: {}, names: {}, optionData: null, options: {}, edited: {},
      loadingCatalog: false, loadingCameras: false, loadingOptions: false, loadingPreview: false, confirming: false,
      error: '', notice: '', preview: null, previewSignature: '', job: null, creating: false, uncertain: false,
      requestId: '', pollTimer: null, pollFailures: 0, polling: false, disposed: false, cameraSequence: 0, optionSequence: 0,
      previewSequence: 0, catalogSequence: 0, jobSequence: 0, deferredResultQuery: null}; },
    computed: {
      canCreate: function () { return !!(this.catalog && this.catalog.can_create === true); },
      algorithm: function () { var vm = this; return (this.catalog && this.catalog.algorithms || []).filter(function (item) { return same(item.id, vm.algorithmId); })[0] || null; },
      cameras: function () { var vm = this; return Object.keys(this.selected).sort().map(function (key) { return vm.selected[key]; }); },
      busy: function () { return this.loadingCatalog || this.loadingCameras || this.loadingOptions || this.loadingPreview || this.confirming || this.creating; },
      locked: function () { return this.creating || this.uncertain || !!(this.job && this.job.status === 'running'); },
      pendingTasks: function () { return (this.job && this.job.items || []).filter(function (item) { return needsSetup(item) && item.conf_id; }); },
      currentTemplate: function () { var vm = this; return (this.optionData && this.optionData.templates || []).filter(function (item) { return same(item.id, vm.options.template_id); })[0] || null; },
      currentResource: function () { var vm = this; return (this.optionData && this.optionData.resources || []).filter(function (item) { return same(item.id, vm.options.resource_id); })[0] || null; },
      payload: function () { var vm = this; return {algorithm_id: this.algorithmId, camera_ids: this.cameras.map(function (item) { return item.id; }),
        options: copy(this.options), overrides: this.cameras.map(function (item) { return {equipment_id: item.id, conf_name: vm.taskName(item)}; })}; },
      payloadSignature: function () { return signature(this.payload); },
      validPreview: function () { return !!(this.preview && this.previewSignature === this.payloadSignature); },
      validation: function () {
        var vm = this, errors = [];
        if (!this.algorithm || this.algorithm.enabled === false) errors.push('请选择可用算法。');
        if (!this.cameras.length) errors.push('请至少选择一路可配置摄像机。');
        if (this.cameras.length > 50) errors.push('每批最多选择 50 路摄像机，请分批创建。');
        if (!this.currentTemplate) errors.push('请选择算法模板。');
        if (!this.currentResource || this.currentResource.disabled) errors.push('请选择可用算力资源。');
        if (!isFinite(Number(this.options.confidence)) || Number(this.options.confidence) < 0 || Number(this.options.confidence) > 1) errors.push('算法默认置信度无效，请刷新可用信息。');
        if (!isFinite(Number(this.options.interval_time)) || Number(this.options.interval_time) % 1 !== 0 || Number(this.options.interval_time) < 1 || Number(this.options.interval_time) > 3600) errors.push('告警间隔须为 1 到 3600 秒的整数。');
        if (['legacy', 'main', 'sub'].indexOf(String(this.options.stream_type)) < 0) errors.push('请选择有效的视频码流。');
        if (this.cameras.some(function (item) { return !vm.taskName(item).trim(); })) errors.push('任务名称不能为空。');
        if (this.cameras.some(function (item) { return vm.taskName(item).length > 32; })) errors.push('任务名称不能超过 32 字。');
        return errors;
      }
    },
    watch: {
      payloadSignature: function () { if (!this.creating) { this.preview = null; this.previewSignature = ''; } },
      '$route.query.request_id': function (value, previous) {
        if (!this.catalog || String(value || '') === String(previous || '')) return;
        var requested = /^[0-9a-f]{32}$/.test(String(value || '')) ? String(value) : '';
        if (this.creating) { this.deferredResultQuery = requested; return; }
        this.openResultRequest(requested);
      }
    },
    created: function () { var vm = this; this.loadCatalog().then(function () { if (vm.catalog && (vm.canCreate || /^[0-9a-f]{32}$/.test(String((vm.$route.query || {}).request_id || '')))) vm.resumePending(); }); },
    beforeDestroy: function () { this.disposed = true; this.cameraSequence += 1; this.optionSequence += 1; this.previewSequence += 1; this.catalogSequence += 1; this.jobSequence += 1; this.stopPoll(); },
    methods: {
      taskName: function (item) { return Object.prototype.hasOwnProperty.call(this.names, String(item.id)) ? this.names[String(item.id)] : item.default_name || (item.name + '_' + algorithmName(this.algorithm)); },
      setName: function (item, value) { this.$set(this.names, String(item.id), value); },
      setOption: function (key, value) { this.$set(this.options, key, ['confidence', 'interval_time'].indexOf(key) >= 0 ? Number(value) : value); this.$set(this.edited, key, true); },
      loadCatalog: function () {
        var vm = this, sequence = ++this.catalogSequence; this.loadingCatalog = true;
        return this.$http.get(api('catalog')).then(unpack).then(function (value) {
          if (vm.disposed || sequence !== vm.catalogSequence) return;
          vm.catalog = value; vm.error = value.can_create === true || /^[0-9a-f]{32}$/.test(String((vm.$route.query || {}).request_id || '')) ? '' : '当前账号没有新增算法配置权限。';
        }).catch(function (error) { if (!vm.disposed && sequence === vm.catalogSequence) vm.error = failure(error, '算法目录读取失败，请稍后重试。'); })
          .then(function () { if (!vm.disposed && sequence === vm.catalogSequence) vm.loadingCatalog = false; });
      },
      chooseAlgorithm: function (item) {
        if (this.locked || item.enabled === false || same(item.id, this.algorithmId)) return;
        this.algorithmId = item.id; this.selected = {}; this.names = {}; this.options = {}; this.edited = {}; this.optionData = null;
        this.items = []; this.total = 0; this.page = 1; this.preview = null; this.error = ''; this.notice = '';
        this.loadCameras(1); this.loadOptions();
      },
      loadCameras: function (page) {
        if (!this.algorithmId || this.locked) return Promise.resolve();
        var vm = this, sequence = ++this.cameraSequence, algorithm = this.algorithmId;
        var params = {algorithm_id: algorithm, page: page || this.page, per_page: this.perPage};
        Object.keys(this.filters).forEach(function (key) { if (vm.filters[key]) params[key] = vm.filters[key]; });
        this.loadingCameras = true;
        return this.$http.get(api('cameras'), {params: params}).then(unpack).then(function (value) {
          if (vm.disposed || sequence !== vm.cameraSequence || !same(algorithm, vm.algorithmId)) return;
          vm.items = value.items || []; vm.total = Number(value.total || 0); vm.page = Number(value.page || params.page);
          var removed = 0;
          vm.items.forEach(function (item) {
            var key = String(item.id);
            if (!vm.selected[key]) return;
            if (item.disabled) { vm.$delete(vm.selected, key); removed += 1; }
            else vm.$set(vm.selected, key, item);
          });
          if (removed) vm.notice = '部分摄像机已有相同算法配置或当前不可用，已移出本次选择。';
        }).catch(function (error) { if (!vm.disposed && sequence === vm.cameraSequence) vm.error = failure(error, '摄像机列表读取失败，请稍后刷新。'); })
          .then(function () { if (!vm.disposed && sequence === vm.cameraSequence) vm.loadingCameras = false; });
      },
      loadOptions: function () {
        if (!this.algorithmId || this.locked) return Promise.resolve();
        var vm = this, sequence = ++this.optionSequence, algorithm = this.algorithmId; this.loadingOptions = true;
        return this.$http.get(api('options'), {params: {algorithm_id: algorithm}}).then(unpack).then(function (value) {
          if (vm.disposed || sequence !== vm.optionSequence || !same(algorithm, vm.algorithmId)) return;
          vm.optionData = value;
          Object.keys(value.defaults || {}).forEach(function (key) { if (!vm.edited[key]) vm.$set(vm.options, key, value.defaults[key]); });
        }).catch(function (error) { if (!vm.disposed && sequence === vm.optionSequence) vm.error = failure(error, '模板与算力信息读取失败，请稍后刷新。'); })
          .then(function () { if (!vm.disposed && sequence === vm.optionSequence) vm.loadingOptions = false; });
      },
      refresh: function () { if (this.locked || this.busy) return; this.error = ''; this.loadCatalog(); this.loadCameras(); this.loadOptions(); },
      changeFilter: function (key, value) { if (this.locked) return; this.$set(this.filters, key, value); if (key === 'mine_id') this.filters.parent_id = ''; this.loadCameras(1); },
      toggleCamera: function (item, checked) { if (this.locked || item.disabled) return; if (checked) this.$set(this.selected, String(item.id), item); else this.$delete(this.selected, String(item.id)); },
      togglePage: function (checked) { var vm = this; this.items.forEach(function (item) { vm.toggleCamera(item, checked); }); },
      showPreview: function () {
        if (this.busy || this.locked || this.validation.length) return;
        var vm = this, body = copy(this.payload), marker = signature(body), sequence = ++this.previewSequence;
        this.loadingPreview = true; this.error = '';
        return this.$http.post(api('preview'), body).then(unpack).then(function (value) {
          if (vm.disposed || sequence !== vm.previewSequence || marker !== vm.payloadSignature) return;
          vm.preview = value; vm.previewSignature = marker; vm.stage = 3;
        }).catch(function (error) { if (!vm.disposed && sequence === vm.previewSequence) vm.error = failure(error, '预览未完成，请刷新摄像机可用状态后重试。'); })
          .then(function () { if (!vm.disposed && sequence === vm.previewSequence) vm.loadingPreview = false; });
      },
      savePending: function () { try { root.localStorage.setItem(pendingKey(), JSON.stringify({request_id: this.requestId, created_at: Date.now()})); return true; } catch (ignore) { return false; } },
      clearPending: function () { try { var stored = JSON.parse(root.localStorage.getItem(pendingKey()) || 'null'); if (stored && stored.request_id === this.requestId) root.localStorage.removeItem(pendingKey()); } catch (ignore) {} },
      resumePending: function () {
        var value;
        var requested = String((this.$route.query || {}).request_id || '');
        if (/^[0-9a-f]{32}$/.test(requested)) value = {request_id: requested};
        if (!value) try { value = JSON.parse(root.localStorage.getItem(pendingKey()) || 'null'); } catch (ignore) {}
        if (!value || !/^[0-9a-f]{32}$/.test(value.request_id || '')) return;
        this.openResultRequest(value.request_id);
      },
      openResultRequest: function (requested) {
        this.jobSequence += 1; this.stopPoll(); this.polling = false; this.pollFailures = 0;
        this.previewSequence += 1; this.loadingPreview = false; this.preview = null; this.previewSignature = '';
        this.job = null; this.requestId = requested; this.error = ''; this.uncertain = !!requested;
        this.stage = requested ? 4 : 0;
        if (requested) this.poll();
      },
      applyDeferredResultQuery: function () {
        if (this.creating || this.deferredResultQuery === null) return false;
        var requested = this.deferredResultQuery; this.deferredResultQuery = null;
        this.openResultRequest(requested); return true;
      },
      createBatch: function () {
        if (this.busy || this.locked || !this.validPreview || !this.preview.summary || !this.preview.summary.eligible) return;
        var vm = this, plan = this.preview.plan_id; this.confirming = true;
        return this.$confirm('将新增 ' + this.preview.summary.eligible + ' 路算法任务。新任务创建时停用；逐路保存完整后自动启动，未完整或启动失败时停留当前。已有任务保持原状。',
          '确认新增算法配置', {confirmButtonText: '确认创建', cancelButtonText: '取消', type: 'warning'}).then(function () {
          if (vm.disposed || !vm.validPreview || plan !== vm.preview.plan_id) return;
          vm.creating = true; vm.confirming = false; vm.requestId = requestId();
          vm.jobSequence += 1; vm.stopPoll(); vm.polling = false;
          var creatingRequest = vm.requestId, creatingSequence = vm.jobSequence;
          if (!vm.savePending()) { vm.creating = false; vm.requestId = ''; vm.error = '浏览器无法保存本次请求标识，请检查浏览器存储后再创建。'; return; }
          vm.error = ''; vm.stage = 4;
          return vm.$http.post(api('create'), {plan_id: plan, request_id: vm.requestId}).then(unpack).then(function (value) {
            if (!vm.disposed && vm.requestId === creatingRequest && vm.jobSequence === creatingSequence) vm.acceptJob(value);
          }).catch(function (error) {
            if (vm.disposed || vm.requestId !== creatingRequest || vm.jobSequence !== creatingSequence) return;
            if (error && error.response && error.response.data && error.response.data.safe_to_repreview === true) {
              vm.creating = false; vm.uncertain = false; vm.clearPending(); vm.requestId = ''; vm.preview = null; vm.previewSignature = ''; vm.stage = 2;
              vm.error = '本次请求未开始创建，预览已失效或条件发生变化，请刷新可用信息后重新预览。'; vm.applyDeferredResultQuery(); return;
            }
            vm.creating = false; vm.uncertain = true; vm.error = '创建结果尚未确认，正在查询本次结果，请勿重复提交。'; if (!vm.applyDeferredResultQuery()) vm.poll();
          });
        }).catch(function () {}).then(function () { if (!vm.disposed) vm.confirming = false; });
      },
      acceptJob: function (value) {
        if (!value || !same(value.request_id, this.requestId)) { this.uncertain = true; this.creating = false; this.error = '本次创建结果尚未确认，请查询结果。'; return; }
        this.job = value; this.creating = false; this.pollFailures = 0;
        if (value.status === 'completed' || value.status === 'failed') { this.uncertain = false; this.error = ''; this.stopPoll(); this.clearPending(); }
        else { this.uncertain = true; this.schedulePoll(); }
        this.applyDeferredResultQuery();
      },
      stopPoll: function () { if (this.pollTimer) root.clearTimeout(this.pollTimer); this.pollTimer = null; },
      schedulePoll: function () { var vm = this, requested = this.requestId, sequence = this.jobSequence; this.stopPoll(); if (!this.disposed && this.pollFailures < 10) this.pollTimer = root.setTimeout(function () { if (vm.requestId === requested && vm.jobSequence === sequence) vm.poll(); }, 2500); },
      poll: function () {
        if (!this.requestId || this.disposed || this.polling) return Promise.resolve();
        var vm = this, requested = this.requestId, sequence = this.jobSequence; this.stopPoll(); this.polling = true;
        return this.$http.get(api('jobs/' + encodeURIComponent(requested))).then(unpack).then(function (value) { if (!vm.disposed && vm.requestId === requested && vm.jobSequence === sequence) vm.acceptJob(value); })
          .catch(function (error) {
            if (vm.disposed || vm.requestId !== requested || vm.jobSequence !== sequence) return;
            vm.creating = false; vm.uncertain = true; vm.pollFailures += 1;
            vm.error = failure(error, '暂未确认本次创建结果，可继续查询；系统不会再次提交创建请求。');
            vm.schedulePoll();
          }).then(function () { if (!vm.disposed && vm.requestId === requested && vm.jobSequence === sequence) vm.polling = false; });
      },
      newBatch: function () { if (!this.canCreate || this.locked || this.busy) return; this.jobSequence += 1; this.stopPoll(); this.polling = false; this.job = null; this.requestId = ''; this.preview = null; this.stage = 0; this.selected = {}; this.names = {}; this.notice = ''; this.error = ''; if ((this.$route.query || {}).request_id) navigate(this, PATH); this.loadCameras(1); },
      openEditor: function (item) { navigate(this, this.stage === 4 ? batchEditorPath(item, this.requestId) : editPath(item)); }
    },
    render: function (h) {
      var vm = this, children = [h('header', {class: 'af-heading'}, [h('div', [h('h2', '新增算法配置'), h('p', '先选择算法，再为多路摄像机配置任务。')]),
        button(h, '返回算法配置', function () { navigate(vm, '/sfgl'); }, this.confirming)])];
      if (this.error) children.push(h('div', {class: 'af-message is-error', attrs: {role: 'alert'}}, this.error));
      if (this.notice) children.push(h('div', {class: 'af-message'}, this.notice));
      if (!this.catalog || (!this.canCreate && this.stage !== 4)) {
        children.push(h('section', {class: 'af-card'}, [h('p', this.loadingCatalog ? '正在读取算法目录…' : this.error || '当前账号没有新增算法配置权限。'),
          button(h, '重新读取', this.loadCatalog, this.loadingCatalog)]));
        return h('div', {class: 'algorithm-first-page'}, children);
      }
      children.push(h('ol', {class: 'af-steps'}, ['选择算法', '选择摄像机', '参数与算力', '预览', '创建结果'].map(function (title, index) {
        return h('li', {class: index === vm.stage ? 'is-current' : index < vm.stage ? 'is-complete' : '', attrs: {'aria-current': index === vm.stage ? 'step' : null}}, (index + 1) + ' ' + title);
      })));
      if (this.stage < 4) children.push(h('div', {class: 'af-context'}, [h('span', '当前算法：' + algorithmName(this.algorithm) + (algorithmVersion(this.algorithm) ? '（' + algorithmVersion(this.algorithm) + '）' : '')),
        h('span', '已选 ' + this.cameras.length + ' 路'), button(h, '刷新可用信息', this.refresh, this.busy || this.locked)]));
      if (this.stage === 0) children.push(h('section', {class: 'af-card', attrs: {'data-af-step': 'algorithms'}}, [h('h3', '选择算法'),
        h('div', {class: 'af-algorithms'}, (this.catalog.algorithms || []).map(function (item) {
          return h('button', {key: String(item.id), class: ['af-algorithm', same(item.id, vm.algorithmId) && 'is-selected'],
            attrs: {type: 'button', disabled: item.enabled === false, 'data-algorithm-id': item.id, 'aria-pressed': same(item.id, vm.algorithmId) ? 'true' : 'false'},
            on: {click: function () { vm.chooseAlgorithm(item); }}}, [h('strong', algorithmName(item)), h('small', algorithmVersion(item)), item.enabled === false ? h('span', '当前不可用') : null]);
        })), !(this.catalog.algorithms || []).length ? h('p', '暂无可配置算法。') : null]));
      if (this.stage === 1) {
        var recorders = (this.catalog.recorders || []).filter(function (item) { return !vm.filters.mine_id || same(item.mine_id, vm.filters.mine_id); });
        var selectable = this.items.filter(function (item) { return !item.disabled; });
        children.push(h('section', {class: 'af-card', attrs: {'data-af-step': 'cameras'}}, [h('h3', '选择摄像机'), h('div', {class: 'af-filters'}, [
          field(h, '单位', 'af-mine', select(h, 'af-mine', this.filters.mine_id, [{id: '', name: '全部单位'}].concat(this.catalog.units || []), function (value) { vm.changeFilter('mine_id', value); }, this.locked)),
          field(h, '录像机', 'af-recorder', select(h, 'af-recorder', this.filters.parent_id, [{id: '', name: '全部录像机'}].concat(recorders), function (value) { vm.changeFilter('parent_id', value); }, this.locked)),
          field(h, '摄像机名称', 'af-search', input(h, 'af-search', this.filters.search, function (value) { vm.filters.search = value; }, this.locked)),
          button(h, '查询', function () { vm.loadCameras(1); }, this.loadingCameras || this.locked)]),
          h('p', {class: 'af-note'}, '相同算法已有配置的摄像机不可重复添加；配置了其他算法的摄像机仍可选择。'),
          this.loadingCameras ? h('p', '正在读取摄像机可用状态…') : null,
          h('div', {class: 'af-table-scroll'}, [h('table', {class: 'af-table'}, [h('thead', [h('tr', [h('th', [h('input', {attrs: {type: 'checkbox', 'aria-label': '选择本页可用摄像机', disabled: !selectable.length || vm.locked},
            domProps: {checked: !!selectable.length && selectable.every(function (item) { return !!vm.selected[String(item.id)]; })}, on: {change: function (event) { vm.togglePage(event.target.checked); }}})]),
            h('th', '摄像机 / 单位'), h('th', '状态'), h('th', '已有算法'), h('th', '本次配置')])]),
            h('tbody', this.items.map(function (item) { return h('tr', {key: String(item.id), class: item.disabled && 'is-disabled', attrs: {'data-camera-id': item.id}}, [
              h('td', [h('input', {attrs: {type: 'checkbox', disabled: !!item.disabled || vm.locked, 'aria-label': '选择' + item.name}, domProps: {checked: !!vm.selected[String(item.id)]}, on: {change: function (event) { vm.toggleCamera(item, event.target.checked); }}})]),
              h('th', {attrs: {scope: 'row'}}, [h('strong', item.name), h('small', [item.mine_name, item.parent_name, item.channel != null ? '通道 ' + item.channel : ''].filter(Boolean).join(' · '))]),
              h('td', onlineText(item.online)),
              h('td', (item.existing || []).length ? item.existing.map(function (task) { return h('div', {class: 'af-existing'}, [h('span', algorithmName(task) + ' · ' + stateText(task.status)),
                button(h, '查看任务', function () { vm.openEditor(task); }, false, false, {'aria-label': '查看' + item.name + '的' + task.algorithm_name + '任务'})]); }) : '暂无配置'),
              h('td', item.disabled ? item.disabled_reason || '当前不可添加' : '可添加本算法')]); }))])]),
          !this.items.length && !this.loadingCameras ? h('p', '当前筛选条件下没有摄像机。') : null,
          h('div', {class: 'af-pagination'}, [h('span', '共 ' + this.total + ' 路，已选 ' + this.cameras.length + ' 路'),
            button(h, '上一页', function () { vm.loadCameras(vm.page - 1); }, this.page <= 1 || this.loadingCameras), h('span', '第 ' + this.page + ' 页'),
            button(h, '下一页', function () { vm.loadCameras(vm.page + 1); }, this.page * this.perPage >= this.total || this.loadingCameras)])]));
      }
      if (this.stage === 2) children.push(h('section', {class: 'af-card', attrs: {'data-af-step': 'options'}}, [h('h3', '参数与算力'),
        h('p', {class: 'af-note'}, '已带入算法默认参数。刷新只更新未修改的默认项，任务所属单位按各摄像机保留。模板中的其他参数保持默认，可创建后逐路编辑。'),
        h('div', {class: 'af-option-grid'}, [
          field(h, '算法模板', 'af-template', select(h, 'af-template', this.options.template_id, (this.optionData && this.optionData.templates || []).map(function (item) { return {id: item.id, name: item.name}; }), function (value) { vm.setOption('template_id', value); }, this.locked)),
          field(h, '算力资源', 'af-resource', select(h, 'af-resource', this.options.resource_id, (this.optionData && this.optionData.resources || []).map(function (item) { return {id: item.id, disabled: item.disabled,
            name: item.name + (item.computing_name ? ' · ' + item.computing_name : '') + (item.recommended ? '（推荐）' : '') + (item.disabled ? '（' + (item.reason || '不可用') + '）' : '')}; }), function (value) { vm.setOption('resource_id', value); }, this.locked)),
          field(h, '视频码流', 'af-stream', select(h, 'af-stream', this.options.stream_type, [{id: 'legacy', name: '沿用设备码流'}, {id: 'main', name: '主码流'}, {id: 'sub', name: '子码流'}], function (value) { vm.setOption('stream_type', value); }, this.locked), '已有运行任务的摄像机沿用其当前码流，避免影响原任务。')]),
        h('p', {class: this.currentTemplate && (this.currentTemplate.should_confirm_geometry || this.currentTemplate.requires_geometry) ? 'af-geometry-note' : 'af-note'}, geometryNote(this.currentTemplate)),
        h('div', {class: 'af-table-scroll'}, [h('table', {class: 'af-table'}, [h('thead', [h('tr', [h('th', '摄像机'), h('th', '单位'), h('th', '任务名称')])]),
          h('tbody', this.cameras.map(function (item) { return h('tr', {key: String(item.id)}, [h('th', item.name), h('td', item.mine_name || '—'), h('td', [input(h, 'af-name-' + item.id, vm.taskName(item), function (value) { vm.setName(item, value); }, vm.locked, {maxlength: '32'})])]); }))])]),
        this.validation.length ? h('ul', {class: 'af-validation'}, this.validation.map(function (message) { return h('li', message); })) : null]));
      if (this.stage === 3) children.push(h('section', {class: 'af-card', attrs: {'data-af-step': 'preview'}}, [h('h3', '创建预览'),
        !this.validPreview ? h('p', '选择或参数已变化，请返回参数页重新预览。') : h('div', [
          h('p', '可新增 ' + Number(this.preview.summary && this.preview.summary.eligible || 0) + ' 路，跳过 ' + Number(this.preview.summary && this.preview.summary.skipped || 0) + ' 路。新任务创建时停用，逐路保存完整后自动启动。'),
          h('div', {class: 'af-table-scroll'}, [h('table', {class: 'af-table'}, [h('thead', [h('tr', [h('th', '摄像机'), h('th', '任务名称'), h('th', '处理'), h('th', '后续操作')])]),
            h('tbody', (this.preview.items || []).map(function (item) { return h('tr', {key: String(item.equipment_id)}, [h('th', item.name || String(item.equipment_id)), h('td', item.conf_name || '—'),
              h('td', item.eligible ? '新增 · 停用' : '跳过：' + (item.reason || '当前不可添加')), h('td', item.needs_setup ? '逐路完善，保存后启动' : '逐路确认并保存后启动')]); }))])])]) ]));
      if (this.stage === 4) children.push(h('section', {class: 'af-card', attrs: {'data-af-step': 'result'}}, [h('h3', this.job && this.job.status === 'completed' ? '创建结果' : '正在确认创建结果'),
        h('p', this.locked ? '当前批次正在处理或等待结果。离开后可重新打开此入口查询，不会重复提交。' : '新任务创建时停用。逐路保存完整后自动启动，确认运行后进入下一路；启动失败可在当前编辑页重试，当前状态以各任务显示为准。'),
        this.pendingTasks.length ? h('div', {class: 'af-batch-next'}, [button(h, '连续配置本批任务（' + this.pendingTasks.length + ' 路待完善）', function () { vm.openEditor(vm.pendingTasks[0]); }, this.locked || this.busy, true, {'data-batch-configure': 'true'}),
          h('p', {class: 'af-note'}, '按本批次顺序逐路保存，各摄像机的检测区域与场景参数独立保留。')]) : null,
        this.job ? h('div', [h('p', '已创建 ' + (this.job.items || []).filter(function (item) { return item.status === 'created'; }).length + ' 路，跳过 ' + (this.job.items || []).filter(function (item) { return item.status === 'skipped'; }).length + ' 路，失败 ' + (this.job.items || []).filter(function (item) { return item.status === 'failed'; }).length + ' 路。'),
          h('div', {class: 'af-table-scroll'}, [h('table', {class: 'af-table'}, [h('thead', [h('tr', [h('th', '摄像机'), h('th', '结果'), h('th', '说明'), h('th', '配置')])]),
            h('tbody', (this.job.items || []).map(function (item) { return h('tr', {key: String(item.equipment_id), attrs: {'data-result-camera-id': item.equipment_id}}, [h('th', item.name || String(item.equipment_id)),
              h('td', {class: item.status === 'failed' && 'af-failed'}, resultState(item)),
              h('td', item.stopped === false || String(item.run_status) === '1' ? '本路已启动' : item.start_message || item.setup_message || item.reason || (needsSetup(item) ? '需要逐路完善区域、线或方向' : '—')),
              h('td', !item.deleted && (item.conf_id || item.edit_path) ? [button(h, needsSetup(item) ? '继续配置' : '查看配置', function () { vm.openEditor(item); }, false)] : '—')]); }))])])]) : null,
        button(h, '查询本次结果', this.poll, this.creating || this.polling || !this.requestId), button(h, '新建另一批', this.newBatch, !this.canCreate || this.locked || this.busy)]));
      if (this.stage < 4) children.push(h('footer', {class: 'af-actions'}, [button(h, '上一步', function () { vm.stage = Math.max(0, vm.stage - 1); }, this.stage === 0 || this.busy || this.locked),
        this.stage < 2 ? button(h, '下一步', function () { vm.stage += 1; }, this.busy || !this.algorithm || this.algorithm.enabled === false || (this.stage === 1 && !this.cameras.length), true) :
          this.stage === 2 ? button(h, this.loadingPreview ? '正在预览…' : '预览创建', this.showPreview, this.busy || this.locked || !!this.validation.length, true) :
            button(h, '确认创建', this.createBatch, this.busy || this.locked || !this.validPreview || !this.preview.summary || !this.preview.summary.eligible, true)]));
      return h('div', {class: 'algorithm-first-page'}, children);
    }
  };

  function installRoute(router) {
    if (router.__algorithmFirstInstalled) return;
    var routes = router.options.routes, home = routes.filter(function (route) { return route.name === 'Home'; })[0];
    if (!home) return;
    var children = (home.children || []).slice();
    if (!children.some(function (route) { return route.name === NAME || route.path === PATH.slice(1); })) children.push({path: PATH.slice(1), name: NAME,
      component: component, meta: {title: '新增算法配置', requireAuth: true, keepAlive: false}});
    var next = routes.map(function (route) { return route === home ? Object.assign({}, route, {children: children}) : route; });
    router.matcher = new router.constructor({routes: next, mode: router.mode, base: router.options.base}).matcher;
    router.options.routes = next; router.__algorithmFirstInstalled = true;
    router.beforeEach(function (to, from, proceed) {
      var query = to.query || {};
      if (bareCreation(to.path, query)) proceed({path: PATH, replace: true});
      else proceed();
    });
    var current = router.currentRoute, currentQuery = current.query || {}, target = current.path === PATH ? current.fullPath :
      bareCreation(current.path, currentQuery) ? PATH : '';
    if (target) { var result = router.replace(target); if (result && result.catch) result.catch(function () {}); }
  }
  function styles() {
    if (root.document.getElementById('algorithm-first-ui-style')) return;
    var style = root.document.createElement('style'); style.id = 'algorithm-first-ui-style';
    style.textContent = '.algorithm-first-page{padding:24px;background:#f4f7fb;min-height:100%;box-sizing:border-box;color:#26384c;font-size:14px}.algorithm-first-page h2{margin:0 0 8px;font-size:22px}.algorithm-first-page h3{margin:0 0 16px;font-size:16px}.algorithm-first-page p{line-height:1.7;margin:8px 0}.af-heading,.af-context,.af-actions,.af-pagination{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px}.af-heading p,.af-note,.af-field small{color:#65758a}.af-card{background:#fff;border:1px solid #e1e8f1;border-radius:8px;padding:20px;margin-bottom:18px}.af-steps{display:flex;list-style:none;padding:0;margin:0 0 20px;gap:12px}.af-steps li{flex:1;border-bottom:3px solid #dce4ef;padding:12px 5px;color:#728198}.af-steps .is-current{border-color:#2f65d9;color:#2456b9;font-weight:600}.af-steps .is-complete{border-color:#9bb8eb}.af-algorithms{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}.af-algorithm{border:1px solid #d3deec;background:#fff;color:#26384c;text-align:left;padding:18px;border-radius:6px;cursor:pointer;min-height:90px;font:inherit}.af-algorithm strong,.af-algorithm small{display:block;margin-bottom:7px}.af-algorithm small{color:#65758a}.af-algorithm.is-selected{border:2px solid #2f65d9;background:#f1f6ff;padding:17px}.af-button{border:1px solid #c9d5e5;border-radius:5px;background:#fff;color:#35516f;min-height:36px;padding:7px 14px;font:inherit;cursor:pointer}.af-button.is-primary{background:#2f65d9;border-color:#2f65d9;color:#fff}.af-button:disabled,.af-algorithm:disabled{opacity:.5;cursor:default}.af-button+.af-button{margin-left:8px}.af-message{padding:12px 16px;background:#fff8e9;color:#835d1d;border-radius:6px;margin-bottom:16px;line-height:1.6}.af-message.is-error{background:#fff0f0;color:#a33434}.af-filters{display:flex;align-items:flex-end;gap:14px;flex-wrap:wrap;margin-bottom:16px}.af-field label{display:block;margin:0 0 8px;font-weight:600}.af-field input,.af-field select,.af-table input[type=text]{width:100%;box-sizing:border-box;height:36px;padding:0 10px;border:1px solid #cdd8e6;border-radius:5px;background:#fff;color:#26384c;font:inherit}.af-field small{display:block;line-height:1.6;margin-top:7px}.af-filters .af-field{flex:1;min-width:170px;max-width:330px}.af-option-grid{display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:20px;margin:20px 0}.af-table-scroll{overflow-x:auto}.af-table{width:100%;min-width:700px;border-collapse:collapse;table-layout:fixed;margin:16px 0}.af-table th,.af-table td{text-align:left;padding:12px;border-bottom:1px solid #e8edf4;overflow-wrap:anywhere;vertical-align:middle}.af-table thead th{background:#f4f7fb;color:#526983;font-weight:600}.af-table tbody th{font-weight:500}.af-table small{display:block;color:#65758a;line-height:1.6;margin-top:5px}.af-table input[type=checkbox]{width:17px;height:17px}.af-table .is-disabled{background:#f7f8fa;color:#7c899b}.af-existing{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:4px 0}.af-existing .af-button{font-size:12px;padding:3px 7px;min-height:28px}.af-pagination{justify-content:flex-end;margin-top:12px}.af-pagination>span:first-child{margin-right:auto}.af-geometry-note{padding:12px 15px;background:#fff8e9;border-radius:5px;color:#835d1d}.af-validation,.af-failed{color:#a33434}.af-validation li{line-height:1.8}.af-actions{justify-content:flex-end}.af-actions>.af-button:first-child{margin-right:auto}@media(max-width:800px){.algorithm-first-page{padding:14px}.af-card{padding:16px}.af-steps{gap:6px;font-size:12px}.af-option-grid{grid-template-columns:1fr}.af-heading{align-items:flex-start}.af-context{flex-wrap:wrap}}';
    root.document.head.appendChild(style);
  }
  function boot(attempt) {
    var element = root.document.getElementById('app'), app = element && element.__vue__;
    if (!app || !app.$router || !app.$http) { if (attempt < 300) root.setTimeout(function () { boot(attempt + 1); }, 100); return; }
    styles(); app.$router.onReady(function () { installRoute(app.$router); });
  }
  root.AiMonitorAlgorithmFirst = {component: component, installRoute: installRoute, path: PATH, editPath: editPath, batchEditorPath: batchEditorPath};
  boot(0);
})(window);
