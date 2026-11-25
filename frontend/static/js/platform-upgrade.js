/* platform-container-upgrade-ui-v1 */
(function (root) {
  'use strict';
  function api(path) { return ((root.wgParameter && root.wgParameter.url_5000) || '').replace(/\/$/, '') + '/platform_ops/upgrade/' + path; }
  function data(response) { var body = response && response.data; if (!body || Number(body.code) !== 200) throw new Error(body && body.msg || '操作失败'); return body.data || {}; }
  function message(error) { return error && error.response && error.response.data && error.response.data.msg || error && error.message || '请求失败，请稍后重试'; }
  function button(h, label, action, disabled, primary) { return h('button', {class: ['storage-button', primary && 'storage-button-primary'], attrs: {type: 'button', disabled: !!disabled}, on: {click: action}}, label); }
  var labels = {validating: '校验中', ready: '校验通过，等待确认', backing_up: '备份中', applying: '更新中', health_check: '验证中', rolling_back: '回退中', rolled_back: '已回退', completed: '已完成', failed: '失败', interrupted: '需核查'};
  var roles = {application: '平台', middleware: '中间件', algorithm: '算法', frontend: '前端', backend: '后端'};
  var types = {image: '离线镜像更新', deployment: '容器部署'};
  var exampleLabels = {container_images: '离线镜像更新'};
  var activeStates = ['validating', 'backing_up', 'applying', 'health_check', 'rolling_back'];
  function componentLabel(component) { return (roles[component.role] || component.role || '组件') + ' · ' + (types[component.type] || component.type || '更新'); }
  function json(value) { return typeof value === 'string' ? value : JSON.stringify(value == null ? {} : value, null, 2); }
  function textList(h, values) { return h('ul', {class: 'ops-file-list'}, (values || []).map(function (value) { return h('li', String(value)); })); }
  function proof(h, title, value) { return h('div', {class: 'ops-proof-row'}, [h('dt', title), h('dd', value == null || value === '' ? '—' : String(value))]); }
  function identityVersion(job) { return String(job.updated_at || job.created_at || '') + '|' + String(job.status || ''); }
  function version(job) { var steps = job.steps || [], last = steps[steps.length - 1] || {}; return identityVersion(job) + '|' + String(job.steps_total == null ? steps.length : job.steps_total) + '|' + String(last.action || '') + '|' + String(last.state || '') + '|' + String(last.at || ''); }
  root.AiMonitorPlatformUpgrade = {
    name: 'AiMonitorPlatformUpgrade',
    data: function () { return {state: {}, loading: false, uploading: false, mutating: false, preparingJob: '', progress: 0, phase: '', file: null, uploadId: '', error: '', success: '', timer: null, disposed: false, exampleId: 'frontend_patch', jobDetails: {}, jobDetailLoading: {}, jobDetailErrors: {}, expandedFiles: {}}; },
    created: function () { this.load(); var vm = this; this.timer = root.setInterval(function () { if (!root.document.hidden && !vm.loading) vm.load(true); }, 5000); },
    beforeDestroy: function () { this.disposed = true; root.clearInterval(this.timer); },
    computed: {
      active: function () { return (this.state.jobs || []).some(function (job) { return activeStates.indexOf(job.status) >= 0; }); },
      examples: function () { return this.state.package_examples || {}; }
    },
    methods: {
      load: function (quiet) {
        if (this.loading || this.disposed) return Promise.resolve();
        var vm = this; vm.loading = true;
        return vm.$http.get(api('status')).then(data).then(function (result) {
          if (vm.disposed) return; vm.state = result; if (!quiet) vm.error = '';
          Object.keys(vm.jobDetails).forEach(function (id) { var current = (result.jobs || []).find(function (job) { return String(job.id) === id; }); if (!current || vm.jobDetails[id].version !== version(current)) vm.$delete(vm.jobDetails, id); });
          var choices = Object.keys(result.package_examples || {}); if (choices.length && choices.indexOf(vm.exampleId) < 0) vm.exampleId = choices[0];
        }).catch(function (error) { if (!quiet && !vm.disposed) vm.error = message(error); }).finally(function () { vm.loading = false; });
      },
      post: function (path, body) { return this.$http.post(api(path), body || {}, {headers: {'Content-Type': 'application/json'}}).then(data); },
      needsFullJob: function (job) {
        var preview = job.preview || {}, evidence = job.evidence || {};
        return !!(job.details_truncated || job.components_truncated || (job.components || []).some(function (component) { return component.files_truncated || Number(component.files_total) > (component.files || []).length; }) ||
          preview.removed_files_truncated || Number(preview.removed_files_total) > (preview.removed_files || []).length || preview.changes_truncated || (preview.changes || []).some(function (change) { return change.files_truncated; }) ||
          preview.verification_steps_truncated || evidence.steps_truncated || evidence.algorithm_models_truncated || job.steps_truncated || job.evidence_truncated);
      },
      displayedJob: function (job) {
        var cached = this.jobDetails[String(job.id)];
        return cached && cached.version === version(job) ? Object.assign({}, cached.job, {rollback_eligible: job.rollback_eligible, rollback_block_reason: job.rollback_block_reason}) : job;
      },
      fetchFullJob: function (job) {
        var vm = this, id = String(job.id), cached = vm.jobDetails[id];
        if (cached && cached.version === version(job)) return Promise.resolve(cached.job);
        if (vm.jobDetailLoading[id]) return Promise.reject(new Error('正在读取完整校验内容，请稍候。'));
        vm.$set(vm.jobDetailLoading, id, true); vm.$set(vm.jobDetailErrors, id, '');
        return vm.$http.get(api('jobs/' + encodeURIComponent(id))).then(data).then(function (result) {
          if (vm.disposed) throw new Error('页面已关闭');
          var full = result.job || result;
          if (String(full.id) !== id || vm.needsFullJob(full)) throw new Error('未取得完整校验内容，请刷新后重试。');
          var current = (vm.state.jobs || []).find(function (item) { return String(item.id) === id; });
          if (current && identityVersion(current) !== identityVersion(full)) throw new Error('升级任务状态已变化，请刷新后重新核对。');
          if (current) vm.$set(vm.state.jobs, vm.state.jobs.indexOf(current), full);
          vm.$set(vm.jobDetails, id, {version: version(full), job: full}); return full;
        }).catch(function (error) { if (!vm.disposed) vm.$set(vm.jobDetailErrors, id, message(error)); throw error; })
          .finally(function () { vm.$set(vm.jobDetailLoading, id, false); });
      },
      showFullJob: function (job) { return this.fetchFullJob(job).catch(function () {}); },
      upload: async function () {
        if (!this.file || this.uploading || this.active || this.mutating || this.preparingJob) return;
        var vm = this, file = vm.file; vm.error = ''; vm.success = ''; vm.uploading = true; vm.progress = 0; vm.phase = '正在上传升级包';
        try {
          var task = await vm.post('uploads', {filename: file.name, size: file.size}); vm.uploadId = task.upload_id;
          if (!Number.isFinite(Number(task.chunk_bytes)) || Number(task.chunk_bytes) <= 0) throw new Error('上传分片配置异常，请重试');
          for (var offset = 0; offset < file.size; offset += Number(task.chunk_bytes)) {
            if (vm.disposed) return;
            var part = file.slice(offset, Math.min(offset + Number(task.chunk_bytes), file.size));
            await vm.$http.post(api('uploads/' + task.upload_id + '/chunk'), part, {headers: {'Content-Type': 'application/octet-stream', 'X-Upload-Offset': String(offset)}, timeout: 120000}).then(data);
            vm.progress = Math.round(100 * Math.min(offset + Number(task.chunk_bytes), file.size) / file.size);
          }
          if (vm.disposed) return;
          await vm.post('uploads/' + task.upload_id + '/finish'); vm.phase = '正在检查文件完整性';
          var complete = false;
          for (var checks = 0; checks < 480; checks++) {
            if (vm.disposed) return;
            var uploadState = await vm.$http.get(api('uploads/' + task.upload_id)).then(data);
            if (uploadState.error) throw new Error(uploadState.error);
            if (uploadState.finished) { complete = true; break; }
            await new Promise(function (resolve) { root.setTimeout(resolve, 1000); });
          }
          if (!complete) throw new Error('文件完整性检查仍在进行，请稍后刷新。');
          if (vm.disposed) return;
          await vm.post('plan', {upload_id: task.upload_id}); vm.success = '上传完成，正在校验升级包。校验通过后，请核对更新范围再执行。'; vm.phase = ''; await vm.load(true);
        } catch (error) { if (!vm.disposed) vm.error = message(error); }
        finally { vm.uploading = false; }
      },
      apply: async function (job) {
        if (this.active || this.uploading || this.mutating || this.preparingJob || job.status !== 'ready') return;
        var vm = this; vm.preparingJob = String(job.id); vm.error = '';
        try {
        if (vm.needsFullJob(job)) { job = await vm.fetchFullJob(job); await vm.$nextTick(); }
        if (vm.disposed || vm.active || job.status !== 'ready') return;
        var preview = job.preview || {}, components = job.components || [], services = preview.restart_services || [];
        var summary = '升级版本：' + job.release + '\n更新内容：' + (components.map(componentLabel).join('；') || '平台镜像') +
          '\n需要重启：' + (services.join('、') || '以校验清单为准') + '\n系统会先备份本次受影响的镜像，再执行更新和服务验证。' +
          (preview.removed_files && preview.removed_files.length ? '\n完整目录更新将移除 ' + preview.removed_files.length + ' 个旧镜像归档，具体路径已在校验结果列出。' : '') +
          '\n现有配置、累计人数与历史报警保留。验证失败将恢复原镜像或服务，备份保留供核查。\n是否开始？';
        return await vm.$confirm(summary, '确认备份并更新', {confirmButtonText: '备份并更新', cancelButtonText: '取消', type: 'warning', customClass: 'ops-confirm-summary'})
          .then(function () {
            if (vm.disposed || vm.active || vm.mutating) return; vm.mutating = true; vm.error = ''; vm.success = '';
            return vm.post('apply', {upload_id: job.upload_id}).then(function () { if (!vm.disposed) { vm.success = '更新任务已开始，请查看备份、验证和恢复进度。'; return vm.load(true); } });
          }).catch(function (error) { if (error !== 'cancel' && error !== 'close' && !vm.disposed) vm.error = message(error); }).finally(function () { vm.mutating = false; });
        } catch (error) { if (!vm.disposed) vm.error = message(error); }
        finally { vm.preparingJob = ''; }
      },
      rollback: function (job) {
        if (!job || !job.rollback_eligible || this.active || this.uploading || this.mutating || this.preparingJob) return;
        var vm=this, services=job.preview&&job.preview.restart_services||[], previous=job.previous_release||vm.state.previous_version;
        var target=typeof previous==='string'?previous:previous&&previous.release||'上一版本';
        vm.preparingJob='rollback:'+String(job.id);vm.error='';
        var summary='当前版本：'+job.release+'\n回退到：'+target+'\n需要重启：'+(services.join('、')||'本次变更涉及的服务')+
          '\n系统保留当前镜像，再恢复上一镜像版本并检查容器。回退失败时恢复操作前的镜像版本。'+
          '\n现有配置、账号、授权、数据库、累计人数和历史媒体保留；本次涉及的容器会重新启动。\n是否回退？';
        return vm.$confirm(summary,'确认回退到上一版本',{confirmButtonText:'备份并回退',cancelButtonText:'取消',type:'warning',customClass:'ops-confirm-summary'})
          .then(function(){
            if(vm.disposed||vm.active||vm.mutating)return;vm.mutating=true;vm.error='';vm.success='';
            return vm.post('rollback',{job_id:job.id}).then(function(){if(!vm.disposed){vm.success='回退任务已开始，请查看备份、恢复和服务验证结果。';return vm.load(true);}});
          }).catch(function(error){if(error!=='cancel'&&error!=='close'&&!vm.disposed)vm.error=message(error);})
          .finally(function(){vm.mutating=false;vm.preparingJob='';});
      },
      format: function () {
        var manifest = this.examples[this.exampleId];
        if (!manifest) { this.error = '升级清单示例尚未载入，请刷新后重试。'; return; }
        var link = root.document.createElement('a'), url = root.URL.createObjectURL(new Blob([JSON.stringify(manifest, null, 2)], {type: 'application/json'}));
        link.href = url; link.download = 'manifest.' + this.exampleId + '.example.json'; link.click(); root.setTimeout(function () { root.URL.revokeObjectURL(url); }, 1000);
      },
      componentsView: function (h, job) {
        var vm = this;
        return (job.components || []).map(function (component, index) {
          var key = String(job.id) + ':' + index, files = component.files || [], total = component.files_total == null ? files.length : Number(component.files_total);
          return h('div', {class: 'ops-component', key: component.role + '-' + index}, [h('strong', componentLabel(component)),
            h('dl', [component.image && proof(h, '镜像标签', component.image), component.image_id && proof(h, '镜像ID', component.image_id), component.base_revision && proof(h, '要求算法版本', component.base_revision), component.file && proof(h, '包内归档', component.file)]),
            files.length > 0 && h('details', {on: {toggle: function (event) { vm.$set(vm.expandedFiles, key, event.target.open); }}}, [h('summary', '更新文件（共 ' + total + ' 个' + (component.files_truncated ? '，当前预览 ' + files.length + ' 个' : '') + '）'), vm.expandedFiles[key] && h('div', {class: 'ops-table-wrap'}, [h('table', {class: 'ops-table'}, [
              h('thead', [h('tr', ['目标文件', '包内文件', '新文件 SHA256', '当前文件 SHA256'].map(function (title) { return h('th', title); }))]),
              h('tbody', files.map(function (file) { return h('tr', [h('td', file.path), h('td', file.file), h('td', file.sha256), h('td', file.base_sha256 === null ? '新增文件（必须不存在）' : file.base_sha256 || '—')]); }))])])])]);
        });
      },
      jobView: function (h, job) {
        var vm = this; job = vm.displayedJob(job);
        var preview = job.preview || {}, evidence = job.evidence || {}, blocked = vm.active || vm.uploading || vm.mutating || !!vm.preparingJob, id = String(job.id);
        var reverting=job.operation==='rollback', stage=reverting?['backing_up','rolling_back','health_check']:['backing_up','applying','health_check'], current=stage.indexOf(job.status), completed=job.status==='completed'||job.status==='rolled_back';
        return h('article', {class: 'ops-job', key: job.id}, [h('div', {class: 'ops-job-heading'}, [h('strong', (job.operation==='rollback'?'回退至 ':'') + (job.release || '升级包校验') + ' · ' + (labels[job.status] || job.status)), h('span', {class: 'storage-muted storage-small'}, job.updated_at || job.created_at)]),
          h('p', {attrs: {role: 'status'}}, job.message || ''), job.error && h('p', {class: 'storage-notice storage-notice-error', attrs: {role: 'alert'}}, typeof job.error === 'string' ? job.error : json(job.error)),
          job.failure_reason && h('p', {class: 'storage-notice storage-notice-error'}, '失败原因：' + job.failure_reason),
          vm.needsFullJob(job) && h('div', {class: 'ops-actions'}, [button(h, vm.jobDetailLoading[id] ? '正在读取完整内容…' : '查看完整校验内容', function () { vm.showFullJob(job); }, vm.jobDetailLoading[id] || !!vm.preparingJob), h('span', {class: 'storage-muted storage-small'}, '当前为摘要预览；执行更新前会读取并核对完整内容。')]),
          vm.jobDetailErrors[id] && h('p', {class: 'storage-notice storage-notice-error', attrs: {role: 'alert'}}, vm.jobDetailErrors[id]),
          h('ol', {class: 'ops-steps', attrs: {'aria-label': '升级阶段'}}, (reverting?['核查版本与备份','记录当前镜像','恢复上一版本','运行验证']:['校验升级包','备份','更新','运行验证']).map(function (label, index) {
            var done = completed || index === 0 && job.status !== 'validating' || current >= 0 && index <= current;
            return h('li', {class: {'is-current': index === current + 1 && current >= 0 || index === 0 && job.status === 'validating', 'is-done': done}}, label);
          })),
          h('div', {class: 'ops-preview'}, [h('h4', reverting?'恢复范围':'更新范围'), vm.componentsView(h, job), !(job.components || []).length && h('p', {class: 'storage-muted'}, job.status === 'validating' ? '正在读取升级清单…' : '旧版任务未记录组件明细，请核对原升级包。'),
            preview.restart_services && h('p', '涉及服务：' + (preview.restart_services.join('、') || '无需重启')),
            preview.protected_paths && preview.protected_paths.length && h('details', [h('summary', '保留的现场数据与目录'), textList(h, preview.protected_paths)]),
            preview.verification_steps && preview.verification_steps.length && h('details', {attrs: {open: job.status === 'ready'}}, [h('summary', '更新后的验证步骤'), textList(h, preview.verification_steps)]),
            preview.removed_files && preview.removed_files.length > 0 && h('details', {attrs: {open: job.status === 'ready' && preview.removed_files.length <= 100}, class: 'ops-warning'}, [h('summary', '将移除的旧文件（' + (preview.removed_files_total == null ? preview.removed_files.length : preview.removed_files_total) + (preview.removed_files_truncated ? '，当前预览 ' + preview.removed_files.length + ' 个' : '') + '）'), textList(h, preview.removed_files)]),
            preview.changes && preview.changes.length && h('details', [h('summary', '查看变更说明'), textList(h, preview.changes.map(function (change) { return typeof change === 'string' ? change : componentLabel(change) + '：' + (change.description || String(change.files || 0) + ' 个文件'); }))])]),
          job.backup_path && h('p', {class: 'storage-muted storage-small'}, '备份位置：' + job.backup_path),
          Object.keys(evidence).length > 0 && h('details', [h('summary', '查看备份、验证与数据保留结果'), h('pre', {class: 'ops-code', attrs: {tabindex: '0'}}, json(evidence))]),
          job.rollback_evidence && h('details', [h('summary', '查看回退验证与当前数据保留结果'), h('pre', {class: 'ops-code', attrs: {tabindex: '0'}}, json(job.rollback_evidence))]),
          job.steps && job.steps.length > 0 && h('details', [h('summary', '详细执行记录（共 ' + (job.steps_total == null ? job.steps.length : job.steps_total) + ' 条' + (job.steps_truncated ? '，当前显示最近 ' + job.steps.length + ' 条' : '') + '）'), h('pre', {class: 'ops-code', attrs: {tabindex: '0'}}, json(job.steps))]),
          job.status === 'ready' && button(h, vm.preparingJob === id ? '正在核对完整内容…' : '备份并更新', function () { vm.apply(job); }, blocked || vm.jobDetailLoading[id] || vm.state.backup_ready === false, true),
          job.rollback_eligible && h('div', {class: 'ops-actions'}, [button(h, '一键回退', function () { vm.rollback(job); }, blocked), h('span', {class: 'storage-muted storage-small'}, '恢复上一版本镜像，保留当前业务数据。')]),
          !job.rollback_eligible && job.status === 'completed' && h('p', {class: 'storage-muted storage-small'}, '当前不可回退：' + (job.rollback_block_reason || '仅当前生效且旧镜像仍在本机的版本可回退。'))]);
      }
    },
    render: function (h) {
      var vm=this, state=this.state, jobs=state.jobs||[], capabilities=state.capabilities||[];
      var choices=Object.keys(this.examples), blocked=vm.uploading||vm.active||vm.mutating||!!vm.preparingJob;
      var current=state.current_version||state.release||{}, previous=state.previous_version;
      var history=state.version_history||[], rollbackJob=jobs.find(function(job){return job.rollback_eligible;});
      var currentJob=jobs.find(function(job){return String(job.id)===String(current.job_id);});
      var rollbackReason=state.rollback_block_reason||currentJob&&currentJob.rollback_block_reason||
        (previous?'当前版本没有通过校验的回退备份，请查看下方执行记录。':'暂无可回退的上一版本。');
      function releaseName(value){return typeof value==='string'?value:value&&value.release||'—';}
      var maximum=Number(state.max_upload_bytes), limit=maximum>0?'，最大 '+(maximum/1073741824).toFixed(1)+' GiB':'';
      return h('div',{class:'storage-management ops-page'},[
        h('div',{class:'storage-heading'},[h('div',[h('h2','平台升级'),
          h('p',{class:'storage-muted'},'管理离线镜像版本，上传升级包，或一键回退到上一版本。')]),
          button(h,vm.loading?'刷新中…':'刷新',function(){vm.load();},vm.loading)]),
        vm.error&&h('div',{class:'storage-notice storage-notice-error',attrs:{role:'alert'}},vm.error),
        vm.success&&h('div',{class:'storage-notice storage-notice-success',attrs:{role:'status'}},vm.success),
        h('section',{class:'storage-card'},[h('h3','当前版本与服务'),
          h('p',[h('strong','当前版本：'),current.release||'读取中…',' · '+(state.architecture||'—')]),
          current.updated_at&&h('p',{class:'storage-muted storage-small'},'最近变更：'+current.updated_at),
          h('p','上一版本：'+(previous?releaseName(previous):'暂无可回退版本')),
          h('div',{class:'ops-actions'},[button(h,'一键回退到上一版本',function(){return vm.rollback(rollbackJob);},
            blocked||!rollbackJob||state.manual_rollback_supported===false)]),
          !rollbackJob&&h('p',{class:'storage-muted storage-small'},rollbackReason),
          h('div',{class:'ops-table-wrap'},[h('table',{class:'ops-table'},[
            h('thead',[h('tr',['服务','版本','状态'].map(function(label){return h('th',label);} ))]),
            h('tbody',(state.services||[]).map(function(item){return h('tr',{key:item.name},[
              h('td',item.name),h('td',item.version||'—'),
              h('td',item.running?'运行中':'未运行')]);}))])]),
          capabilities.length>0&&h('div',{class:'ops-capabilities',attrs:{'aria-label':'支持的更新方式'}},
            capabilities.map(function(item){return h('span',{class:'ops-capability',attrs:{title:item.description||''}},item.label||componentLabel(item));})),
          h('p',{class:'storage-muted storage-small'},'升级和回退切换涉及服务的镜像。现场配置、数据库、账号、授权、证书和历史媒体保留。')]),
        h('section',{class:'storage-card'},[h('h3','版本历史'),
          h('p',{class:'storage-muted storage-small'},'记录成功升级和回退。每次回退恢复上一个版本，需要更早版本时可继续逐次回退。'),
          !history.length?h('p',{class:'ops-empty'},'暂无版本变更记录。'):h('div',{class:'ops-table-wrap'},[h('table',{class:'ops-table'},[
            h('thead',[h('tr',['操作','版本','涉及组件','完成时间','结果'].map(function(label){return h('th',label);}))]),
            h('tbody',history.map(function(item){return h('tr',{key:item.id},[
              h('td',item.operation==='rollback'?'回退':item.operation==='deployment'?'部署':'升级'),
              h('td',[releaseName(item.release),(item.current===true||item.current==null&&String(item.id)===String(current.last_operation_id||current.job_id||current.deployment_id))&&' · 当前生效',
                h('div',{class:'storage-muted storage-small'},'原版本：'+releaseName(item.previous_release))]),
              h('td',(item.components||[]).map(function(part){var role=typeof part==='string'?part:part.role;return roles[role]||role;}).join('、')||'—'),
              h('td',item.updated_at||item.created_at||'—'),h('td',labels[item.status]||item.status||'已完成')]);}))])])]),
        h('section',{class:'storage-card'},[h('h3','上传并预检升级包'),
          h('p',{class:'storage-muted'},'选择与当前 '+(state.architecture||'服务器')+' 架构匹配的升级包（tar、tar.gz 或 zip'+limit+'）。上传完成后先预检，确认后才执行更新。'),
          state.backup_ready===false&&h('p',{class:'storage-notice storage-notice-error'},'备份目录未就绪，暂不能执行更新。'),
          h('input',{attrs:{type:'file',accept:'.tar,.gz,.tgz,.zip',disabled:blocked,'aria-label':'选择平台升级包'},
            on:{change:function(event){vm.file=event.target.files[0]||null;vm.progress=0;vm.phase='';vm.error='';vm.success='';}}}),
          vm.file&&h('p',{class:'ops-package-size'},vm.file.name+' · '+(vm.file.size/1048576).toFixed(2)+' MiB'),
          h('div',{class:'ops-actions'},[button(h,vm.uploading?vm.phase+' '+vm.progress+'%':'上传并预检',function(){vm.upload();},!vm.file||blocked,true)]),
          vm.uploading&&h('progress',{attrs:{max:100,value:vm.progress,'aria-label':'升级包上传进度'},style:{width:'100%',marginTop:'14px'}}),
          h('details',{class:'ops-upgrade-help'},[h('summary','查看升级包格式与示例'),
            h('p','升级包根目录包含 manifest.json，清单使用 platform-container 格式，声明版本、架构和application、middleware、algorithm镜像。每个镜像归档由docker save导出，放入清单指定的images目录。'),
            h('p','每个镜像声明含版本的aiplatform标签、归档相对路径archive和SHA256。使用新版本标签更新，已部署的旧版本镜像保留供回退。'),
            h('p','现场配置、数据库、授权、证书、算法运行目录及历史媒体不在本入口更新范围。预检只读取升级包和当前镜像，执行前会展示变更文件与需要重启的服务。'),
            choices.length?h('div',[
              h('label',{class:'ops-field'},[h('span','升级包清单示例'),h('select',{attrs:{'aria-label':'升级包清单示例'},domProps:{value:vm.exampleId},
                on:{change:function(event){vm.exampleId=event.target.value;}}},choices.map(function(key){return h('option',{attrs:{value:key}},exampleLabels[key]||key);} ))]),
              button(h,'下载清单示例',vm.format,vm.uploading),
              h('pre',{class:'ops-code',attrs:{tabindex:'0','aria-label':'升级包清单 JSON 示例'}},json(this.examples[this.exampleId]))
            ]):h('p',{class:'storage-muted'},'清单示例尚未载入，请刷新后查看。'),
            h('p',{class:'storage-muted storage-small'},'请使用实际文件和哈希制作升级包；清单示例不能直接用于更新。')])]),
        h('section',{class:'storage-card'},[h('h3','预检与执行记录'),
          h('p',{class:'storage-muted storage-small'},'升级和回退均先备份受影响的镜像，再执行并检查服务；失败时恢复操作前的镜像。页面每 5 秒刷新进度，可随时查看详细执行记录。'),
          !jobs.length&&h('p',{class:'ops-empty'},'暂无升级任务'),
          jobs.map(function(job){return vm.jobView(h,job);})])
      ]);
    }
  };
})(window);
