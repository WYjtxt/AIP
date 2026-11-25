"""Restore the existing upload and upgrade workflow for native code packages."""
from pathlib import Path


NATIVE_RENDER = r'''    render: function (h) {
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
          h('p',{class:'storage-muted'},'管理原生前后端版本，上传升级包，或一键回退到上一版本。')]),
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
          h('p',{class:'storage-muted storage-small'},'升级和回退只变更前后端代码。现场配置、数据库、账号、授权、证书、算法服务和历史媒体保留。')]),
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
            h('p','升级包根目录包含 manifest.json，清单使用 platform-native 格式，声明版本、架构和前端或后端组件。代码文件按清单放入包内，可单独更新一个组件或组合更新。'),
            h('p','每个文件声明相对组件根目录的目标路径、包内路径和 SHA256。需要核对当前文件时提供 base_sha256；新增文件使用 null 表示目标必须不存在。'),
            h('p','现场配置、数据库、授权、证书、算法运行目录及历史媒体不在本入口更新范围。预检只读取升级包和当前代码，执行前会展示变更文件与需要重启的服务。'),
            choices.length?h('div',[
              h('label',{class:'ops-field'},[h('span','升级包清单示例'),h('select',{attrs:{'aria-label':'升级包清单示例'},domProps:{value:vm.exampleId},
                on:{change:function(event){vm.exampleId=event.target.value;}}},choices.map(function(key){return h('option',{attrs:{value:key}},exampleLabels[key]||key);} ))]),
              button(h,'下载清单示例',vm.format,vm.uploading),
              h('pre',{class:'ops-code',attrs:{tabindex:'0','aria-label':'升级包清单 JSON 示例'}},json(this.examples[this.exampleId]))
            ]):h('p',{class:'storage-muted'},'清单示例尚未载入，请刷新后查看。'),
            h('p',{class:'storage-muted storage-small'},'请使用实际文件和哈希制作升级包；清单示例不能直接用于更新。')])]),
        h('section',{class:'storage-card'},[h('h3','预检与执行记录'),
          h('p',{class:'storage-muted storage-small'},'升级和回退均先备份受影响的代码，再执行并检查服务；失败时恢复操作前的代码。页面每 5 秒刷新进度，可随时查看详细执行记录。'),
          !jobs.length&&h('p',{class:'ops-empty'},'暂无升级任务'),
          jobs.map(function(job){return vm.jobView(h,job);})])
      ]);
    }
'''


NATIVE_ROLLBACK = r'''      rollback: function (job) {
        if (!job || !job.rollback_eligible || this.active || this.uploading || this.mutating || this.preparingJob) return;
        var vm=this, services=job.preview&&job.preview.restart_services||[], previous=job.previous_release||vm.state.previous_version;
        var target=typeof previous==='string'?previous:previous&&previous.release||'上一版本';
        vm.preparingJob='rollback:'+String(job.id);vm.error='';
        var summary='当前版本：'+job.release+'\n回退到：'+target+'\n需要重启：'+(services.join('、')||'本次变更涉及的服务')+
          '\n系统先备份当前代码，再恢复上一版本并检查服务。回退失败时恢复操作前的代码。'+
          '\n现有配置、账号、授权、数据库、累计人数和历史媒体保留；算法服务保持运行。\n是否回退？';
        return vm.$confirm(summary,'确认回退到上一版本',{confirmButtonText:'备份并回退',cancelButtonText:'取消',type:'warning',customClass:'ops-confirm-summary'})
          .then(function(){
            if(vm.disposed||vm.active||vm.mutating)return;vm.mutating=true;vm.error='';vm.success='';
            return vm.post('rollback',{job_id:job.id}).then(function(){if(!vm.disposed){vm.success='回退任务已开始，请查看备份、恢复和服务验证结果。';return vm.load(true);}});
          }).catch(function(error){if(error!=='cancel'&&error!=='close'&&!vm.disposed)vm.error=message(error);})
          .finally(function(){vm.mutating=false;vm.preparingJob='';});
      },
'''


def install(root):
    """Reuse the packaged component's authenticated transfer and job methods."""
    path = Path(root) / 'frontend/static/js/platform-upgrade.js'
    source = path.read_text(encoding='utf-8')
    start = source.index('    render: function (h) {\n')
    end = source.rindex('  };\n})(window);')
    updated = source[:start] + NATIVE_RENDER + source[end:]
    rollback_start = updated.index('      rollback: function (job) {\n')
    rollback_end = updated.index('      format: function () {\n', rollback_start)
    updated = updated[:rollback_start] + NATIVE_ROLLBACK + updated[rollback_end:]
    replacements = (
        ("var types = {patch: '模块代码更新', image: '完整镜像更新', directory: '完整目录更新'};",
         "var types = {patch: '模块代码更新', deployment: '原生部署', directory: '完整目录更新'};"),
        ("h('dl', [component.image_id && proof(h, '新镜像 ID', component.image_id), component.base_image_id && proof(h, '要求当前镜像', component.base_image_id),\n              component.base_revision",
         "h('dl', [component.base_revision"),
        ("var exampleLabels = {frontend_patch: '前端模块代码', backend_patch: '后端模块代码', algorithm_patch: '算法代码', frontend_image: '仅前端镜像', backend_image: '仅后端镜像', paired_images: '前后端镜像一起更新', algorithm_directory: '整个算法目录'};",
         "var exampleLabels = {frontend_patch: '前端代码', backend_patch: '后端代码', paired_patches: '前后端代码一起更新'};"),
        ("components.map(componentLabel).join('；') || '前后端完整镜像'", "components.map(componentLabel).join('；') || '原生前后端代码'"),
        ('系统会先备份受影响的代码、服务及现场数据，再执行更新和验证。', '系统会先备份本次受影响的代码，再执行更新和服务验证。'),
        ("proof(h, '镜像归档', component.file)", "proof(h, '包内归档', component.file)"),
        ("vm.state.manual_rollback_supported===false?'执行失败时系统会自动恢复本次受影响代码。':('当前不可回滚：' + (job.rollback_block_reason || '仅最新且备份完整、当前版本一致的更新可回滚。'))",
         "'当前不可回退：' + (job.rollback_block_reason || '仅当前生效且备份完整、代码一致的版本可回退。')"),
        ("'当前不可回滚：' + (job.rollback_block_reason || '仅最新且备份完整、当前版本一致的更新可回滚。')",
         "'当前不可回退：' + (job.rollback_block_reason || '仅当前生效且备份完整、代码一致的版本可回退。')"),
        ("button(h, '回滚此更新'", "button(h, '一键回退'"),
        ('恢复代码或服务，保留当前业务数据。', '恢复上一版本代码，保留当前业务数据。'),
        ("var stage = ['backing_up', 'applying', 'health_check'], current = stage.indexOf(job.status), completed = job.status === 'completed';",
         "var reverting=job.operation==='rollback', stage=reverting?['backing_up','rolling_back','health_check']:['backing_up','applying','health_check'], current=stage.indexOf(job.status), completed=job.status==='completed'||job.status==='rolled_back';"),
        ("['校验升级包', '备份', '更新', '运行验证'].map(function (label, index)",
         "(reverting?['核查版本与备份','备份当前代码','恢复上一版本','运行验证']:['校验升级包','备份','更新','运行验证']).map(function (label, index)"),
        ("h('strong', (job.release || '升级包校验') + ' · '",
         "h('strong', (job.operation==='rollback'?'回退至 ':'') + (job.release || '升级包校验') + ' · '"),
        ("h('h4', '更新范围')", "h('h4', reverting?'恢复范围':'更新范围')"),
    )
    for old, new in replacements:
        if new not in updated:
            updated = updated.replace(old, new)
    updated = updated.replace('回滚', '回退')
    if updated == source:
        return False
    path.write_text(updated, encoding='utf-8')
    return True
