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
    var analysis = String(item.analysis_type || '').trim();
    if (/^(?:0+|null|undefined|None)$/i.test(analysis)) analysis = '';
    var raw = String(item.algorithm_name || item.name || '').trim(), parts = raw.split('_');
    var packageName = parts.length >= 8 && parts.some(function(part){return /^V\d/i.test(part);}) ? parts[1] : '';
    var value = String(item.display_name || analysis || packageName || item.model_name || item.name || item.algorithm_name || '').trim();
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

  // Each algorithm retains the server's existing signed preview, request receipt and editor.
  function cameraPageSize() {
    try { var value=Number(root.localStorage.getItem('AiMonitorCameraPageSize')); if([10,20,50].indexOf(value)>=0) return value; } catch(ignore) {}
    return 10;
  }
  var component = {
    name: 'AlgorithmFirstConfig',
    data: function () { return {stage: 0, catalog: null, algorithmIds: [], activeId: '', groups: {},
      items: [], selected: {}, total: 0, page: 1, perPage: cameraPageSize(), filters: {mine_id: '', parent_id: '', search: ''},
      loading: false, confirming: false, submitting: false, polling: false, error: '', notice: '', previews: [], previewSignature: '',
      jobs: [], multiId: '', timer: null, pollFailures: 0, sequence: 0, disposed: false}; },
    computed: {
      canCreate: function () { return !!(this.catalog && this.catalog.can_create); },
      algorithms: function () { var vm = this; return (this.catalog && this.catalog.algorithms || []).filter(function (a) { return vm.algorithmIds.some(function (id) { return same(id, a.id); }); }); },
      cameras: function () { var vm = this; return Object.keys(this.selected).map(function (id) { return vm.selected[id]; }); },
      pageCount: function () { return Math.max(1, Math.ceil(this.total / this.perPage)); },
      pageRange: function () { return this.items.length ? ((this.page-1)*this.perPage+1)+'–'+Math.min(this.total,(this.page-1)*this.perPage+this.items.length) : '0'; },
      activeGroup: function () { return this.groups[String(this.activeId)] || null; },
      busy: function () { return this.loading || this.confirming || this.submitting || this.polling; },
      pending: function () { return this.jobs.some(function (j) { return j.state === 'submitted' || j.state === 'unknown' || j.state === 'ready'; }); },
      payloads: function () { var vm = this; return this.algorithms.reduce(function (payloads, a) {
        var cameras = vm.configuredCameras(a.id);
        if (!cameras.length) return payloads;
        var g = vm.groups[String(a.id)], options = copy(g.options);
        // An automatic recommendation is not an explicit choice: each camera
        // can already be bound to a different chip. The preview resolves it.
        if (!g.edited.resource_id || !options.resource_id) delete options.resource_id;
        payloads.push({algorithm_id: a.id, camera_ids: cameras.map(function (c) { return c.id; }),
          options: options, overrides: cameras.map(function (c) {
            return {equipment_id: c.id, conf_name: vm.taskName(a.id, c)};
          })});
        return payloads;
      }, []); },
      payloadSignature: function () { return signature(this.payloads); },
      validPreview: function () { return this.previews.length > 0 && this.previewSignature === this.payloadSignature; },
      eligibleCount: function () { return this.previews.reduce(function (sum, p) { return sum + Number(p.data.summary.eligible || 0); }, 0); },
      validation: function () {
        var vm = this, errors = [];
        if (!this.algorithms.length) errors.push('请至少选择一个算法。');
        if (!this.cameras.length) errors.push('请至少选择一路摄像机。');
        if (this.cameras.length > 50) errors.push('每批最多选择 50 路摄像机。');
        if (this.algorithms.length && this.cameras.length && !this.payloads.length) errors.push('请为至少一个算法勾选摄像机。');
        this.cameras.forEach(function(c) {
          var streams = vm.algorithms.filter(function(a){return vm.pairSelected(a.id,c);}).map(function(a){return vm.groups[String(a.id)].options.stream_type;});
          if(streams.some(function(s){return s!==streams[0];})) errors.push(c.name+'：同一摄像机各算法请选择相同的视频码流。');
        });
        this.algorithms.forEach(function (a) {
          var cameras = vm.configuredCameras(a.id);
          if (!cameras.length) return;
          var g = vm.groups[String(a.id)], label = algorithmName(a) + '：';
          if (!a.enabled) { errors.push(label + '算法已停用。'); return; }
          if (!g || !g.data) { errors.push(label + '参数尚未加载。'); return; }
          if (!g.data.templates.some(function (t) { return same(t.id, g.options.template_id); })) errors.push(label + '请选择算法模板。');
          if (!g.data.resources.some(function (r) { return (!g.edited.resource_id || !g.options.resource_id || same(r.id, g.options.resource_id)) && !r.disabled; })) errors.push(label + '请选择兼容算力。');
          if (!isFinite(Number(g.options.confidence)) || Number(g.options.confidence) < 0 || Number(g.options.confidence) > 1) errors.push(label + '置信度须为 0 到 1。');
          if (!isFinite(Number(g.options.interval_time)) || Number(g.options.interval_time) % 1 || Number(g.options.interval_time) < 1 || Number(g.options.interval_time) > 3600) errors.push(label + '告警间隔须为 1 到 3600 秒的整数。');
          if (cameras.some(function (c) { var name = vm.taskName(a.id,c); return !name.trim() || name.length > 32; })) errors.push(label + '任务名称须为 1 到 32 字。');
        });
        return errors;
      }
    },
    watch: {
      payloadSignature: function () { if (this.stage < 4) { this.previews = []; this.previewSignature = ''; } },
      '$route.query': function () { if (!this.submitting) this.restore(); }
    },
    created: function () { var vm = this; this.loadCatalog().then(function () { vm.restore(); }); },
    beforeDestroy: function () { this.disposed = true; this.sequence++; root.clearTimeout(this.timer); },
    methods: {
      loadCatalog: async function () {
        this.loading = true;
        try { this.catalog = unpack(await this.$http.get(api('catalog'))); }
        catch (e) { this.error = failure(e, '算法目录读取失败，请重试。'); }
        finally { this.loading = false; }
      },
      label: function (a) { return algorithmName(a) + (algorithmVersion(a) ? ' · ' + algorithmVersion(a) : ''); },
      existingLabel: function (task) {
        var a = (this.catalog && this.catalog.algorithms || []).filter(function (row) { return same(row.id, task.algorithm_id); })[0];
        return this.label(a || task);
      },
      chooseAlgorithm: function (a) {
        if (this.busy || !a.enabled) return;
        var ids = this.algorithmIds.slice(), i = ids.findIndex(function (id) { return same(id, a.id); });
        if (i >= 0) ids.splice(i, 1); else ids.push(a.id);
        this.algorithmIds = ids; this.activeId = ids[0] || ''; this.previews = [];
      },
      taskName: function (aid, camera) {
        var g = this.groups[String(aid)], row = g && g.cameras[String(camera.id)];
        if(g && Object.prototype.hasOwnProperty.call(g.names,String(camera.id))) return g.names[String(camera.id)];
        var name=row && row.default_name || camera.name;
        var a=this.algorithms.filter(function(a){return same(a.id,aid);})[0];
        if(a && this.algorithms.some(function(other){return !same(other.id,aid)&&algorithmName(other)===algorithmName(a);})) {
          var suffix='-'+aid;name=name.slice(0,32-suffix.length)+suffix;
        }
        return name;
      },
      canPair: function (aid, camera) { var g = this.groups[String(aid)], row = g && g.cameras[String(camera.id)]; return !!(row && !row.disabled); },
      pairReason: function (aid, camera) { var g = this.groups[String(aid)], row = g && g.cameras[String(camera.id)]; return row ? row.disabled_reason : '信息尚未加载'; },
      pairSelected: function (aid, camera) {
        return this.canPair(aid, camera) && !this.groups[String(aid)].excluded[String(camera.id)];
      },
      configuredCameras: function (aid) {
        var vm = this;
        return this.cameras.filter(function (camera) { return vm.pairSelected(aid, camera); });
      },
      togglePair: function (aid, camera, checked) {
        if (this.busy || !this.canPair(aid, camera)) return;
        var excluded = this.groups[String(aid)].excluded, key = String(camera.id);
        if (checked) this.$delete(excluded, key);
        else this.$set(excluded, key, true);
      },
      loadSelection: async function (page, pageSize) {
        if (!this.algorithms.length || this.submitting) return;
        var vm = this, seq = ++this.sequence; this.loading = true; this.error = '';
        var requestedSize=[10,20,50].indexOf(Number(pageSize))>=0?Number(pageSize):this.perPage;
        var requestedPage=Math.max(1,Math.floor(Number(page)||this.page));
        var fetchPage=function(number) { return Promise.all(vm.algorithms.map(async function (a) {
          var params = Object.assign({algorithm_id:a.id, page:number, per_page:requestedSize}, vm.filters);
          var values = await Promise.all([vm.$http.get(api('cameras'), {params:params}), vm.$http.get(api('options'), {params:{algorithm_id:a.id}})]);
          return {a:a, cameras:unpack(values[0]), options:unpack(values[1])};
        })); };
        try {
          var responses = await fetchPage(requestedPage);
          if (this.disposed || seq !== this.sequence) return;
          var lastPage=Math.max(1,Math.ceil(Number(responses[0].cameras.total)/requestedSize));
          if(requestedPage>lastPage) { requestedPage=lastPage; responses=await fetchPage(requestedPage); }
          if (this.disposed || seq !== this.sequence) return;
          responses.forEach(function (r) {
            var key = String(r.a.id), previous = vm.groups[key], g = previous || {names:{}, edited:{}, options:{}, cameras:{}, excluded:{}, data:null};
            g.data = r.options;
            Object.keys(r.options.defaults || {}).forEach(function (name) { if (!g.edited[name]) vm.$set(g.options, name, r.options.defaults[name]); });
            r.cameras.items.forEach(function (c) { vm.$set(g.cameras, String(c.id), c); });
            vm.$set(vm.groups, key, g);
          });
          this.items = responses[0].cameras.items.map(function (c) {
            var row = Object.assign({}, c);
            row.disabled = !vm.algorithms.some(function (a) { return vm.canPair(a.id, row); });
            return row;
          });
          this.items.forEach(function (c) { if (vm.selected[String(c.id)]) { if (c.disabled) vm.$delete(vm.selected,String(c.id)); else vm.$set(vm.selected,String(c.id),c); } });
          this.total = Number(responses[0].cameras.total); this.page = Number(responses[0].cameras.page); this.perPage=requestedSize;
          try { root.localStorage.setItem('AiMonitorCameraPageSize',String(requestedSize)); } catch(ignore) {}
        } catch (e) { if (seq === this.sequence) { this.items = []; this.error = failure(e,'摄像机或算法参数读取失败，请重试。'); } }
        finally { if (seq === this.sequence) this.loading = false; }
      },
      changePageSize: function (value) { if(this.busy || [10,20,50].indexOf(Number(value))<0 || Number(value)===this.perPage) return; return this.loadSelection(1,Number(value)); },
      renderPagination: function (h, position) {
        var vm=this,id='af-page-size-'+position;
        return h('nav',{class:'af-pagination',attrs:{'aria-label':position==='top'?'摄像机列表上方分页':'摄像机列表下方分页','data-camera-pagination':position}},[
          h('span',{class:'af-page-summary'},'共 '+this.total+' 路 · 当前 '+this.pageRange+' 路 · 已选 '+this.cameras.length+' 路'),
          h('label',{class:'af-page-size',attrs:{for:id}},['每页 ',select(h,id,this.perPage,[{id:10,name:'10 路'},{id:20,name:'20 路'},{id:50,name:'50 路'}],this.changePageSize,this.busy)]),
          button(h,'首页',function(){vm.loadSelection(1);},this.busy||this.page<=1),
          button(h,'上一页',function(){vm.loadSelection(vm.page-1);},this.busy||this.page<=1),
          h('span',{attrs:{'aria-live':'polite'}},'第 '+this.page+' / '+this.pageCount+' 页'),
          button(h,'下一页',function(){vm.loadSelection(vm.page+1);},this.busy||this.page>=this.pageCount),
          button(h,'末页',function(){vm.loadSelection(vm.pageCount);},this.busy||this.page>=this.pageCount)
        ]);
      },
      renderPairCameras: function (h, aid, group) {
        var vm = this;
        var eligible = this.cameras.filter(function (camera) { return vm.canPair(aid, camera); });
        var selected = this.configuredCameras(aid).length;
        var allChecked = eligible.length > 0 && selected === eligible.length;
        return h('div', [
          h('p', {class:'af-note', attrs:{'aria-live':'polite'}}, '当前算法已选 ' + selected + ' 路，共 ' + eligible.length + ' 路可选'),
          h('div', {class:'af-table-scroll'}, [h('table', {class:'af-table', key:aid, attrs:{'data-pair-algorithm-id':aid}}, [
            h('thead', [h('tr', [
              h('th', [h('input', {
                attrs:{type:'checkbox','aria-label':'全选当前算法可用摄像机',disabled:this.busy || !eligible.length},
                domProps:{checked:allChecked,indeterminate:selected > 0 && !allChecked},
                on:{change:function (event) {
                  eligible.forEach(function (camera) { vm.togglePair(aid, camera, event.target.checked); });
                }}
              })]), h('th','摄像机'), h('th','任务名称 / 状态')
            ])]),
            h('tbody', this.cameras.map(function (camera) {
              var available = vm.canPair(aid,camera), checked = vm.pairSelected(aid,camera);
              return h('tr', {key:camera.id,class:!available && 'is-disabled',attrs:{'data-pair-camera-id':camera.id}}, [
                h('td', [h('input', {
                  attrs:{type:'checkbox','aria-label':'部署到 '+camera.name,disabled:vm.busy || !available},
                  domProps:{checked:checked},
                  on:{change:function (event) { vm.togglePair(aid, camera, event.target.checked); }}
                })]),
                h('th', {attrs:{scope:'row'}}, [camera.name, h('small',[camera.mine_name,camera.parent_name,
                  camera.channel == null ? '' : '通道 '+camera.channel].filter(Boolean).join(' · '))]),
                h('td', available ? [input(h,'af-name-'+aid+'-'+camera.id,vm.taskName(aid,camera),
                  function (value) { vm.$set(group.names,String(camera.id),value); },vm.busy || !checked,
                  {maxlength:'32','aria-label':camera.name+'任务名称'})] : '跳过：'+vm.pairReason(aid,camera))
              ]);
            }))
          ])])
        ]);
      },
      refresh: async function () { await this.loadCatalog(); await this.loadSelection(this.page); },
      next: async function () {
        if (this.busy) return;
        if (this.stage === 0) { this.selected = {}; this.page = 1; await this.loadSelection(1); if (!this.error) this.stage = 1; }
        else if (this.stage === 1 && this.cameras.length) this.stage = 2;
      },
      toggleCamera: function (c, checked) { if (this.busy || c.disabled) return; if (checked) this.$set(this.selected,String(c.id),c); else this.$delete(this.selected,String(c.id)); },
      setOption: function (key, value) { var g=this.activeGroup; this.$set(g.options,key,['confidence','interval_time'].indexOf(key)>=0?Number(value):value); this.$set(g.edited,key,true); },
      showPreview: async function () {
        if (this.busy || this.validation.length) return;
        this.loading = true; this.error = ''; var marker = this.payloadSignature, payloads = copy(this.payloads), rows = [];
        try {
          for (var i=0;i<payloads.length;i++) {
            var p=payloads[i], a=this.algorithms.filter(function (a) { return same(a.id,p.algorithm_id); })[0];
            rows.push({algorithm_id:p.algorithm_id,label:this.label(a),data:unpack(await this.$http.post(api('preview'),p))});
          }
          if (!this.disposed && marker===this.payloadSignature) { this.previews=rows; this.previewSignature=marker; this.stage=3; }
        } catch(e) { this.error=failure(e,'预览失败，请刷新可用信息后重试。'); }
        finally { this.loading=false; }
      },
      storageKey: function (id) { return 'AiMonitorAlgorithmMulti:' + String(root.localStorage.getItem('userId') || 'current') + ':' + id; },
      indexKey: function () { return this.storageKey('latest'); },
      save: function () {
        if (!this.multiId) return true;
        try { root.localStorage.setItem(this.storageKey(this.multiId),JSON.stringify({id:this.multiId,jobs:this.jobs})); root.localStorage.setItem(this.indexKey(),this.multiId); return true; }
        catch(e) { this.error='浏览器无法保存本批创建记录，请检查存储后重试。'; return false; }
      },
      restore: function () {
        if (this.submitting) return;
        root.clearTimeout(this.timer);
        var q=this.$route.query||{}, id=q.multi_request_id, record;
        try {
          // Returning from a child editor restores the whole multi-algorithm result.
          var recent=root.localStorage.getItem(this.indexKey());
          if (!id && recent) {
            var candidate=JSON.parse(root.localStorage.getItem(this.storageKey(recent)) || 'null');
            if (candidate && (q.request_id ? candidate.jobs.some(function(j){return j.request_id===q.request_id;}) : candidate.jobs.some(function(j){return ['ready','submitted','unknown'].indexOf(j.state)>=0;}))) id=recent;
          }
          if (/^[a-f0-9]{32}$/.test(id||'')) record=JSON.parse(root.localStorage.getItem(this.storageKey(id))||'null');
          if (record && record.id===id && Array.isArray(record.jobs) && record.jobs.length<=50 && record.jobs.every(function(j){return /^[a-f0-9]{32}$/.test(j.request_id||'');})) {
            this.multiId=id; this.jobs=record.jobs; this.stage=4; this.poll(); return;
          }
          if (/^[a-f0-9]{32}$/.test(q.request_id||'')) { this.multiId=''; this.jobs=[{request_id:q.request_id,state:'submitted',label:'算法任务'}]; this.stage=4; this.poll(); return; }
          var legacy=JSON.parse(root.localStorage.getItem(pendingKey())||'null');
          if(legacy && /^[a-f0-9]{32}$/.test(legacy.request_id||'')){this.jobs=[{request_id:legacy.request_id,state:'submitted',label:'算法任务'}];this.stage=4;this.poll();}
        } catch(e) { this.error='本地批次记录无法读取，请从算法配置列表核对已有任务。'; }
      },
      createBatch: async function () {
        if (this.busy || this.stage!==3 || !this.validPreview || !this.eligibleCount) return;
        var marker=this.previewSignature; this.confirming=true;
        try { await this.$confirm('将创建 '+this.eligibleCount+' 个独立算法任务。创建后逐项设置区域及场景参数，保存完整后启动。','确认新增算法配置',{confirmButtonText:'确认创建',cancelButtonText:'取消',type:'warning'}); }
        catch(e) { this.confirming=false; return; }
        this.confirming=false;
        if(this.stage!==3 || !this.validPreview || marker!==this.previewSignature || this.disposed || this.submitting) return;
        this.multiId=requestId();
        this.jobs=this.previews.map(function(p){return {algorithm_id:p.algorithm_id,label:p.label,request_id:requestId(),plan_id:p.data.plan_id,state:Number(p.data.summary.eligible)>0?'ready':'skipped',job:Number(p.data.summary.eligible)>0?null:{items:p.data.items.map(function(item){return Object.assign({},item,{status:'skipped'});})}};});
        if(!this.save()){this.jobs=[];this.multiId='';return;}
        this.stage=4; navigate(this,PATH+'?multi_request_id='+this.multiId); await this.submitReady();
      },
      submitReady: async function () {
        if(this.submitting || !this.canCreate) return;
        this.submitting=true; this.error='';
        try {
          for(var i=0;i<this.jobs.length;i++) {
            var j=this.jobs[i]; if(j.state!=='ready') continue;
            j.state='submitted'; if(!this.save()){j.state='ready';break;}
            try {
              var value=unpack(await this.$http.post(api('create'),{plan_id:j.plan_id,request_id:j.request_id}));
              if(value.request_id!==j.request_id) throw new Error('wrong_receipt');
              this.$set(j,'job',value); j.state=['completed','failed'].indexOf(value.status)>=0?'done':'submitted';
            } catch(e) {
              if(e.response && e.response.data && e.response.data.safe_to_repreview===true) { j.state='rejected'; this.$set(j,'message','预览已过期或可用条件变化，未创建。请新建批次重新预览。'); }
              else { j.state='unknown'; this.error='部分创建结果尚未确认，正在查询原请求，请勿重复创建。'; }
            }
            this.save(); if(j.state==='unknown' || j.state==='submitted' || this.disposed) break;
          }
        } finally { this.submitting=false; if(!this.disposed) this.poll(); }
      },
      poll: async function () {
        if(this.polling || this.submitting || this.disposed) return;
        root.clearTimeout(this.timer); this.polling=true; var failed=false;
        try {
          for(var i=0;i<this.jobs.length;i++) {
            var j=this.jobs[i]; if(['ready','skipped','rejected'].indexOf(j.state)>=0) continue;
            try {
              var value=unpack(await this.$http.get(api('jobs/'+j.request_id)));
              if(value.request_id!==j.request_id) throw new Error('wrong_receipt');
              this.$set(j,'job',value);j.state=['completed','failed'].indexOf(value.status)>=0?'done':'submitted';
            } catch(e) { failed=true; if(j.state!=='done') j.state='unknown'; this.error=failure(e,'部分结果暂无法查询，请稍后重试。'); }
          }
          if(!failed) this.error=''; this.pollFailures=failed?this.pollFailures+1:0; this.save();
        } finally { this.polling=false; }
        var vm=this;
        if(!this.disposed && this.pollFailures<10 && this.jobs.some(function(j){return j.state==='submitted'||j.state==='unknown';})) this.timer=root.setTimeout(function(){vm.poll();},3000);
      },
      openEditor: function (item,j) { navigate(this,j?batchEditorPath(item,j.request_id):editPath(item)); },
      newBatch: function () {
        if(this.busy || this.jobs.some(function(j){return j.state==='submitted'||j.state==='unknown';})) return;
        root.clearTimeout(this.timer); root.localStorage.removeItem(this.indexKey()); root.localStorage.removeItem(pendingKey());
        this.jobs=[];this.multiId='';this.previews=[];this.selected={};this.algorithmIds=[];this.groups={};this.stage=0;this.error=''; navigate(this,PATH);
      }
    },
    render: function(h) {
      var vm=this, children=[h('header',{class:'af-heading'},[h('div',[h('h2','新增算法配置'),h('p','勾选多个算法，为同一摄像机分别配置参数与检测区域。')]),button(h,'返回算法配置',function(){navigate(vm,'/sfgl');},this.submitting)])];
      if(this.error) children.push(h('div',{class:'af-message is-error',attrs:{role:'alert'}},this.error));
      if(!this.catalog){children.push(button(h,'重新读取',this.loadCatalog,this.busy));return h('div',{class:'algorithm-first-page'},children);}
      if(!this.canCreate && this.stage!==4){children.push(h('p','当前账号没有新增算法配置权限。'));return h('div',{class:'algorithm-first-page'},children);}
      children.push(h('ol',{class:'af-steps'},['选择算法','选择摄像机','分别设置参数','预览','创建结果'].map(function(t,i){return h('li',{class:i===vm.stage?'is-current':i<vm.stage?'is-complete':''},(i+1)+' '+t);} )));
      if(this.stage<4) children.push(h('div',{class:'af-context'},[h('span','已选 '+this.algorithms.length+' 个算法 / '+this.cameras.length+' 路摄像机'),button(h,'刷新可用信息',this.refresh,this.busy)]));
      if(this.stage===0) children.push(h('section',{class:'af-card'},[h('h3','选择算法（可多选）'),h('div',{class:'af-algorithms'},(this.catalog.algorithms||[]).map(function(a){var checked=vm.algorithmIds.some(function(id){return same(id,a.id);});return h('button',{class:['af-algorithm',checked&&'is-selected'],attrs:{type:'button',role:'checkbox','aria-checked':String(checked),disabled:!a.enabled||vm.busy,'data-algorithm-id':a.id},on:{click:function(){vm.chooseAlgorithm(a);}}},[h('strong',(checked?'☑ ':'☐ ')+algorithmName(a)),h('small',algorithmVersion(a)),!a.enabled?h('small','当前不可用'):null]);}))]));
      if(this.stage===1){
        var selectable=this.items.filter(function(c){return !c.disabled;});
        children.push(h('section',{class:'af-card'},[h('h3','选择摄像机'),h('div',{class:'af-filters'},[
          field(h,'单位','af-mine',select(h,'af-mine',this.filters.mine_id,[{id:'',name:'全部单位'}].concat(this.catalog.units||[]),function(v){vm.filters.mine_id=v;vm.filters.parent_id='';vm.loadSelection(1);},this.busy)),
          field(h,'录像机','af-recorder',select(h,'af-recorder',this.filters.parent_id,[{id:'',name:'全部录像机'}].concat((this.catalog.recorders||[]).filter(function(r){return !vm.filters.mine_id||same(r.mine_id,vm.filters.mine_id);})),function(v){vm.filters.parent_id=v;vm.loadSelection(1);},this.busy)),
          field(h,'摄像机名称','af-search',input(h,'af-search',this.filters.search,function(v){vm.filters.search=v;},this.busy)),button(h,'查询',function(){vm.loadSelection(1);},this.busy)]),
          h('p',{class:'af-note'},'同一摄像机可配置多个算法；已有相同算法自动跳过，其余算法仍可添加。翻页保留已选，每批最多 50 路。'),
          this.renderPagination(h,'top'),
          h('div',{class:'af-table-scroll'},[h('table',{class:'af-table'},[h('thead',[h('tr',[h('th',[h('input',{attrs:{type:'checkbox','aria-label':'选择本页可用摄像机',disabled:this.busy||!selectable.length},domProps:{checked:!!selectable.length&&selectable.every(function(c){return !!vm.selected[String(c.id)];})},on:{change:function(e){selectable.forEach(function(c){vm.toggleCamera(c,e.target.checked);});}}})]),h('th','摄像机 / 单位'),h('th','状态'),h('th','已有算法'),h('th','本次配置')])]),h('tbody',this.items.map(function(c){return h('tr',{key:c.id,class:c.disabled&&'is-disabled',attrs:{'data-camera-id':c.id}},[
            h('td',[h('input',{attrs:{type:'checkbox',disabled:c.disabled||vm.busy,'aria-label':'选择'+c.name},domProps:{checked:!!vm.selected[String(c.id)]},on:{change:function(e){vm.toggleCamera(c,e.target.checked);}}})]),h('th',[h('strong',c.name),h('small',[c.mine_name,c.parent_name,'通道 '+c.channel].filter(Boolean).join(' · '))]),h('td',onlineText(c.online)),
            h('td',(c.existing||[]).length?c.existing.map(function(t){return h('div',{class:'af-existing'},[h('span',vm.existingLabel(t)+' · '+stateText(t.status)),button(h,'查看任务',function(){vm.openEditor(t);},false)]);}):'暂无配置'),
            h('td',vm.algorithms.map(function(a){return h('div',[h('strong',vm.label(a)),h('small',vm.canPair(a.id,c)?'可添加':vm.pairReason(a.id,c))]);}))]);}))])]),
          this.loading?h('p','正在读取…'):null,!this.items.length&&!this.loading?h('p','没有符合条件的摄像机。'):null,
          this.renderPagination(h,'bottom')]));
      }
      if(this.stage===2){
        var g=this.activeGroup,a=this.algorithms.filter(function(a){return same(a.id,vm.activeId);})[0];
        children.push(h('section',{class:'af-card'},[h('h3','分别设置算法参数'),h('div',{class:'af-algorithm-tabs',attrs:{role:'tablist'}},this.algorithms.map(function(a){return button(h,vm.label(a),function(){vm.activeId=a.id;},vm.busy,same(a.id,vm.activeId),{role:'tab','aria-selected':String(same(a.id,vm.activeId)),'data-option-algorithm':a.id});})),a&&g&&g.data?h('div',[
          h('p',{class:'af-note'},'各算法默认勾选可部署的摄像机，切换算法可分别调整。'),
          h('div',{class:'af-option-grid'},[
            field(h,'算法模板','af-template',select(h,'af-template',g.options.template_id,g.data.templates,function(v){vm.setOption('template_id',v);},this.busy)),
            field(h,'算力资源','af-resource',select(h,'af-resource',g.edited.resource_id?g.options.resource_id:'',[{id:'',name:'自动选择：沿用摄像机绑定，未绑定优先芯片 0'}].concat(g.data.resources.map(function(r){return {id:r.id,disabled:r.disabled,name:r.name+' · '+r.computing_name+(r.reason?'（'+r.reason+'）':r.recommended?'（未绑定时推荐）':'')};})),function(v){vm.setOption('resource_id',v);},this.busy),'逐摄像机的最终芯片会在创建预览中显示；观察中可以保存配置，启动时再检查资源。'),
            field(h,'置信度（0–1）','af-confidence',input(h,'af-confidence',g.options.confidence,function(v){vm.setOption('confidence',v);},this.busy,{type:'number',min:'0',max:'1',step:'0.05'})),
            field(h,'告警间隔（秒）','af-interval',input(h,'af-interval',g.options.interval_time,function(v){vm.setOption('interval_time',v);},this.busy,{type:'number',min:'1',max:'3600',step:'1'})),
            field(h,'视频码流','af-stream',select(h,'af-stream',g.options.stream_type,[{id:'legacy',name:'沿用设备码流'},{id:'main',name:'主码流'},{id:'sub',name:'子码流'}],function(v){vm.setOption('stream_type',v);},this.busy))]),
          h('p',{class:'af-geometry-note'},geometryNote(g.data.templates.filter(function(t){return same(t.id,g.options.template_id);})[0])),
          this.renderPairCameras(h,a.id,g)]):null,
          this.validation.length?h('ul',{class:'af-validation'},this.validation.map(function(t){return h('li',t);})):null]));
      }
      if(this.stage===3)children.push(h('section',{class:'af-card'},[h('h3','创建预览'),h('p','共新增 '+this.eligibleCount+' 个独立任务；已有相同算法不会重复创建。'),this.previews.map(function(p){return h('div',[h('h3',p.label),h('table',{class:'af-table'},[h('thead',[h('tr',[h('th','摄像机'),h('th','任务名称'),h('th','算力资源'),h('th','处理')])]),h('tbody',p.data.items.map(function(c){return h('tr',[h('th',c.name),h('td',c.conf_name||'—'),h('td',c.resource_id?[h('span',[c.computing_name,c.resource_name||('资源 '+c.resource_id)].filter(Boolean).join(' · ')),h('small',c.resource_source==='explicit'?'手动选择':/^camera_/.test(c.resource_source||'')?'沿用摄像机绑定':'未绑定，优先芯片 0'),c.admission_note?h('small',c.admission_note):null]:'—'),h('td',c.eligible?'新增 · 待配置（停用）':'跳过：'+c.reason)]);}))])]);})]));
      if(this.stage===4)children.push(h('section',{class:'af-card'},[h('h3','创建结果'),h('p','逐项设置各算法的检测区域和场景参数。保存完整后启动；返回本批次结果可继续配置其他算法。'),this.jobs.map(function(j){return h('section',{attrs:{'data-result-algorithm':j.algorithm_id}},[h('h3',j.label),j.message?h('p',j.message):null,j.state==='ready'?h('p','等待提交；点击“继续提交未创建算法”。'):null,j.state==='unknown'||j.state==='submitted'?h('p','正在查询原请求结果…'):null,
          h('table',{class:'af-table'},[h('thead',[h('tr',[h('th','摄像机'),h('th','状态'),h('th','配置')])]),h('tbody',(j.job&&j.job.items||[]).map(function(c){return h('tr',{attrs:{'data-result-camera-id':c.equipment_id}},[h('th',c.name||String(c.equipment_id)),h('td',resultState(c)+(c.reason?' · '+c.reason:'')),h('td',c.conf_id&&!c.deleted?[button(h,needsSetup(c)?'配置参数与区域':'查看配置',function(){vm.openEditor(c,j);},vm.submitting)]:[]) ]);} ))])]);}),
          button(h,'查询本批结果',this.poll,this.busy),this.jobs.some(function(j){return j.state==='ready';})?button(h,'继续提交未创建算法',this.submitReady,this.busy||this.jobs.some(function(j){return j.state==='unknown'||j.state==='submitted';}),true):null,
          button(h,'新建另一批',this.newBatch,this.busy||this.jobs.some(function(j){return j.state==='unknown'||j.state==='submitted';}))]));
      if(this.stage<4)children.push(h('footer',{class:'af-actions'},[button(h,'上一步',function(){vm.stage--;},this.busy||this.stage===0),this.stage<2?button(h,'下一步',this.next,this.busy||!this.algorithms.length||(this.stage===1&&!this.cameras.length),true):this.stage===2?button(h,'预览创建',this.showPreview,this.busy||!!this.validation.length,true):button(h,'确认创建',this.createBatch,this.busy||!this.validPreview||!this.eligibleCount,true)]));
      return h('div',{class:'algorithm-first-page'},children);
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
    style.textContent = '.algorithm-first-page{padding:24px;background:#f4f7fb;min-height:100%;box-sizing:border-box;color:#26384c;font-size:14px}.algorithm-first-page h2{margin:0 0 8px;font-size:22px}.algorithm-first-page h3{margin:0 0 16px;font-size:16px}.algorithm-first-page p{line-height:1.7;margin:8px 0}.af-heading,.af-context,.af-actions,.af-pagination{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:18px}.af-heading p,.af-note,.af-field small{color:#65758a}.af-card{background:#fff;border:1px solid #e1e8f1;border-radius:8px;padding:20px;margin-bottom:18px}.af-steps{display:flex;list-style:none;padding:0;margin:0 0 20px;gap:12px}.af-steps li{flex:1;border-bottom:3px solid #dce4ef;padding:12px 5px;color:#728198}.af-steps .is-current{border-color:#2f65d9;color:#2456b9;font-weight:600}.af-steps .is-complete{border-color:#9bb8eb}.af-algorithms{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}.af-algorithm{border:1px solid #d3deec;background:#fff;color:#26384c;text-align:left;padding:18px;border-radius:6px;cursor:pointer;min-height:90px;font:inherit}.af-algorithm strong,.af-algorithm small{display:block;margin-bottom:7px}.af-algorithm small{color:#65758a}.af-algorithm.is-selected{border:2px solid #2f65d9;background:#f1f6ff;padding:17px}.af-button{border:1px solid #c9d5e5;border-radius:5px;background:#fff;color:#35516f;min-height:36px;padding:7px 14px;font:inherit;cursor:pointer}.af-button.is-primary{background:#2f65d9;border-color:#2f65d9;color:#fff}.af-button:disabled,.af-algorithm:disabled{opacity:.5;cursor:default}.af-button+.af-button{margin-left:8px}.af-message{padding:12px 16px;background:#fff8e9;color:#835d1d;border-radius:6px;margin-bottom:16px;line-height:1.6}.af-message.is-error{background:#fff0f0;color:#a33434}.af-filters{display:flex;align-items:flex-end;gap:14px;flex-wrap:wrap;margin-bottom:16px}.af-field label{display:block;margin:0 0 8px;font-weight:600}.af-field input,.af-field select,.af-table input[type=text]{width:100%;box-sizing:border-box;height:36px;padding:0 10px;border:1px solid #cdd8e6;border-radius:5px;background:#fff;color:#26384c;font:inherit}.af-field small{display:block;line-height:1.6;margin-top:7px}.af-filters .af-field{flex:1;min-width:170px;max-width:330px}.af-option-grid{display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:20px;margin:20px 0}.af-table-scroll{overflow-x:auto}.af-table{width:100%;min-width:700px;border-collapse:collapse;table-layout:fixed;margin:16px 0}.af-table th,.af-table td{text-align:left;padding:12px;border-bottom:1px solid #e8edf4;overflow-wrap:anywhere;vertical-align:middle}.af-table thead th{background:#f4f7fb;color:#526983;font-weight:600}.af-table tbody th{font-weight:500}.af-table small{display:block;color:#65758a;line-height:1.6;margin-top:5px}.af-table input[type=checkbox]{width:17px;height:17px}.af-table .is-disabled{background:#f7f8fa;color:#7c899b}.af-algorithm-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:18px}.af-table th:first-child:has(input[type=checkbox]){width:40px}.af-existing{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:4px 0}.af-existing .af-button{font-size:12px;padding:3px 7px;min-height:28px}.af-pagination{justify-content:flex-end;flex-wrap:wrap;margin:16px 0;gap:10px}.af-page-summary{white-space:nowrap}.af-page-size{display:flex;align-items:center;gap:7px;white-space:nowrap}.af-page-size select{height:36px;padding:0 9px;border:1px solid #cdd8e6;border-radius:5px;background:#fff;color:#26384c;font:inherit}.af-pagination .af-button+.af-button{margin-left:0}.af-pagination>span:first-child{margin-right:auto}.af-geometry-note{padding:12px 15px;background:#fff8e9;border-radius:5px;color:#835d1d}.af-validation,.af-failed{color:#a33434}.af-validation li{line-height:1.8}.af-actions{justify-content:flex-end}.af-actions>.af-button:first-child{margin-right:auto}@media(max-width:800px){.algorithm-first-page{padding:14px}.af-card{padding:16px}.af-steps{gap:6px;font-size:12px}.af-option-grid{grid-template-columns:1fr}.af-heading{align-items:flex-start}.af-context{flex-wrap:wrap}}';
    root.document.head.appendChild(style);
  }
  function boot(attempt) {
    var element = root.document.getElementById('app'), app = element && element.__vue__;
    if (!app || !app.$router || !app.$http) { if (attempt < 300) root.setTimeout(function () { boot(attempt + 1); }, 100); return; }
    styles(); app.$router.onReady(function () { installRoute(app.$router); });
  }
  root.AiMonitorAlgorithmFirst = {component: component, installRoute: installRoute, path: PATH, editPath: editPath, batchEditorPath: batchEditorPath, algorithmName: algorithmName};
  boot(0);
})(window);
