/* Load this script BEFORE the existing business script. No secrets are persisted locally. */
(function () {
  'use strict';
  const nativeFetch = window.fetch.bind(window);
  const roles = {admin: '管理员', operator: '操作员', viewer: '只读'};
  const sensitiveKey = /password|secret|token|credential|passwd|pwd/i;
  const configLabels = {primary_ip:'主 IP（linux_ip）',box_ip:'算力设备 IP（box_ip）',db_host:'数据库 IP',db_port:'数据库端口',db_user:'数据库用户',db_password:'数据库密码',db_name:'数据库名',redis_ip:'Redis IP',redis_port:'Redis 端口',redis_password:'Redis 密码',kafka_ip:'Kafka IP',kafka_port:'Kafka 端口',zlk_ip:'ZLK IP',zlk_port:'ZLK 端口',zlk_secret:'ZLK 密钥',box_user:'算力设备用户',box_password:'算力设备密码',upload_ip:'上传服务 IP',upload_port:'上传服务端口',stream_push_ip:'推流目标 IP',aifz_ip:'AIFZ IP',platform_port:'平台端口',aifz_port:'AIFZ 端口'};
  let me = null, configured = {}, savedSecretSources = {}, plan = null, planFingerprint = '', busy = false, installed = false;
  let csrf = '', accountButton = null, menu = null;

  function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined) item.textContent = String(text);
    return item;
  }
  function report(text, kind) {
    const host = document.getElementById('topmsg');
    if (!host) return;
    host.replaceChildren(node('div', 'msg ' + (kind || 'err'), text));
  }
  function redirectLogin() { window.location.replace('/login'); }
  function apiPath(input) {
    try { const url=new URL(input instanceof Request ? input.url : input, window.location.href);return url.origin===window.location.origin?url.pathname:''; }
    catch (_) { return ''; }
  }
  async function readJSON(response) {
    try { return await response.json(); }
    catch (_) { throw new Error('服务响应异常，请稍后重试。'); }
  }
  async function authReady() {
    const response = await nativeFetch('/api/auth/me', {credentials:'same-origin', cache:'no-store', headers:{Accept:'application/json'}});
    if (response.status === 401) { redirectLogin(); throw new Error('请先登录。'); }
    const data = await readJSON(response);
    if (!response.ok || !data.username || !data.csrf) throw new Error(data.error || '无法读取当前账号。');
    if (!Object.prototype.hasOwnProperty.call(roles, data.role)) throw new Error('账号权限无效，请联系管理员。');
    me = {username:data.username, role:data.role}; csrf = data.csrf;
    if (installed) { renderAccount(); applyFieldProtection(); }
    return me;
  }
  const ready = authReady();
  // Attach a rejection handler immediately; pending business requests still receive the same failure.
  ready.catch(function (error) { report(error.message); });
  window.DispatchSecurityReady = ready;
  window.fetch = async function (input, init) {
    const path = apiPath(input);
    if (!path.startsWith('/api/')) return nativeFetch(input, init);
    await ready;
    const options = Object.assign({}, init || {});
    const method = String(options.method || (input instanceof Request ? input.method : 'GET')).toUpperCase();
    const headers = new Headers(input instanceof Request ? input.headers : undefined);
    new Headers(options.headers || {}).forEach(function (value, key) { headers.set(key, value); });
    if (!['GET','HEAD','OPTIONS'].includes(method)) headers.set('X-CSRF-Token', csrf);
    headers.set('Accept', 'application/json');
    options.headers = headers; options.credentials = 'same-origin'; options.cache = 'no-store';
    const response = await nativeFetch(input, options);
    if (response.status === 401) { redirectLogin(); throw new Error('登录已过期，请重新登录。'); }
    if (response.status === 403) {
      const denied = await response.clone().json().catch(function () { return {}; });
      report(denied.error || '当前账号没有执行此操作的权限。');
    }
    if (path === '/api/state' && response.ok) {
      const state = await response.clone().json();
      const secretConfigured = state.secret_configured || {};
      configured = Array.isArray(secretConfigured) ? Object.fromEntries(secretConfigured.map(function(key){return [key,true];})) : secretConfigured;
      savedSecretSources = state.saved_secret_sources || {};
      // The original load() consumes the response next; the observer handles its new inputs.
      window.setTimeout(applyFieldProtection, 0);
    }
    return response;
  };
  async function request(path, payload) {
    const response = await window.fetch(path, payload === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
    const data = await readJSON(response);
    if (!response.ok || data.ok === false) throw new Error(data.error || '操作失败，请稍后重试。');
    return data;
  }
  function isConfigured(key) {
    return Array.isArray(configured) ? configured.includes(key) : Boolean(configured && configured[key]);
  }
  function canWrite() { return me && ['admin','operator'].includes(me.role); }
  function capture() {
    const values={};
    document.querySelectorAll('#fields input[data-key]').forEach(function(input){values[input.dataset.key]=input.value;});
    const primary=document.getElementById('primary_ip');values.primary_ip=primary?primary.value.trim():'';
    const files=Array.from(document.querySelectorAll('.fchk:checked')).map(function(input){return input.value;});
    const reuse = document.getElementById('security-reuse-db-password');
    return JSON.stringify({values:values,files:files,reuse_db_password:Boolean(reuse && reuse.checked)});
  }
  function updateButtons() {
    const preview = document.getElementById('btnPreview'), apply = document.getElementById('btnApply');
    if (preview) preview.disabled = busy || !canWrite();
    if (apply) {
      apply.disabled = busy || !canWrite() || !plan || planFingerprint !== capture();
      apply.title = !canWrite() ? '只读账号不能应用配置' : (!plan ? '请先预览并核对变更' : '应用已预览的变更');
    }
  }
  function invalidate() {
    if (plan) {
      plan = null; planFingerprint = '';
      const hint = document.getElementById('security-plan-state');
      if (hint) hint.textContent = '配置或目标文件已改变，请重新预览。';
    }
    updateButtons();
  }
  function updateDbPasswordSync() {
    const input = document.getElementById('f_db_password');
    if (!input || !me) return;
    const wrapper = input.closest('.field-control') || input.parentNode;
    let control = document.getElementById('security-db-password-sync');
    if (!control) {
      control = node('div');control.id = 'security-db-password-sync';
      const label = node('label', 'security-form-check'), checkbox = node('input');
      checkbox.type = 'checkbox';checkbox.id = 'security-reuse-db-password';checkbox.checked = false;
      label.append(checkbox,node('span','','沿用主配置密码同步'));
      const description = node('p','security-secret-note');description.id = 'security-db-password-sync-note';
      checkbox.setAttribute('aria-describedby',description.id);
      control.append(label,description);wrapper.appendChild(control);
      checkbox.addEventListener('change',function () {
        if (checkbox.checked && input.value !== '') {
          checkbox.checked = false;
          report('已填写新密码。若要沿用主配置密码，请先清空新密码；当前输入已保留。','warn');
        }
        updateDbPasswordSync();invalidate();
      });
      input.addEventListener('input',function () { updateDbPasswordSync();invalidate(); });
    }
    const checkbox = document.getElementById('security-reuse-db-password');
    const description = document.getElementById('security-db-password-sync-note');
    const source = savedSecretSources && savedSecretSources.db_password;
    const available = Boolean(source && source.available === true);
    const path = source && typeof source.path === 'string' ? source.path : '/data/AIGO/platform_start/Config_files/config.ini';
    if ((!available || input.value !== '') && checkbox.checked) {
      checkbox.checked = false;invalidate();
    }
    checkbox.disabled = busy || !canWrite() || !available || input.value !== '';
    input.disabled = busy || !canWrite() || checkbox.checked;
    let message = '来源：' + path + '。服务器直接同步，现有密码不会返回浏览器。';
    if (!available) message += ' 主配置密码不可用；可填写新密码，或先完善主配置。';
    else if (input.value !== '') message += ' 已填写新密码；清空后才可选择沿用主配置密码。';
    else if (checkbox.checked) message += ' 本次将沿用主配置密码，预览后再应用。';
    else message += ' 默认不勾选；留空且不勾选时，保留各目标文件原值。';
    if (!canWrite()) message += ' 只读账号不能同步密码。';
    if (description.textContent !== message) description.textContent = message;
  }
  function applyFieldProtection() {
    if (!me) return;
    document.body.classList.toggle('security-viewer', !canWrite());
    document.querySelectorAll('#fields input[data-key]').forEach(function (input) {
      const key = input.dataset.key || '';
      if (sensitiveKey.test(key)) {
        input.autocomplete = 'new-password';
        input.placeholder = input.value === '__RANDOM__' ? '将在应用时更新' : (isConfigured(key) ? '已配置，留空保持' : '未配置，按需填写');
        let note = input.closest('.field-control') && input.closest('.field-control').querySelector('.security-secret-note');
        if (!note) {
          note = node('p', 'security-secret-note');
          const wrapper = input.closest('.field-control') || input.parentNode;
          wrapper.appendChild(note);
        }
        const text = input.value === '__RANDOM__' ? '已请求生成新密钥，将在应用时更新。' : ((isConfigured(key) ? '现有值已隐藏，留空时保留。' : '留空时不会覆盖已有配置。') + (key==='db_password' ? ' 如需同步数据库密码，请填写新密码，或勾选“沿用主配置密码同步”。' : ''));
        if (note.textContent !== text) note.textContent = text;
      }
    });
    if (!canWrite()) {
      document.querySelectorAll('#network-section input,#network-section button,#config-section input,#config-section .operation-tools button,#file-section input,#file-section button').forEach(function (input) { input.disabled = true; });
    }
    updateDbPasswordSync();
    updateButtons();
  }
  function safeValue(key, value) {
    if (sensitiveKey.test(String(key || ''))) return '••••••（已隐藏）';
    if (value === null || value === undefined) return '—';
    return String(value);
  }
  function makeTable(columns) {
    const wrap = node('div', 'security-table-wrap'), table = node('table', 'security-table');
    const head = node('thead'), row = node('tr'), body = node('tbody');
    columns.forEach(function (column) { row.appendChild(node('th', '', column)); });
    head.appendChild(row); table.append(head, body); wrap.appendChild(table);
    return {wrap:wrap, body:body};
  }
  function resultRow(body, values) {
    const row = node('tr');
    values.forEach(function (value) { const cell=node('td'); cell.appendChild(value instanceof Node ? value : node('span','',value)); row.appendChild(cell); });
    body.appendChild(row);
  }
  function renderResults(data, applying) {
    const out = document.getElementById('out');
    out.replaceChildren();
    const results = Array.isArray(data.results) ? data.results : [];
    const total = results.reduce(function (sum, item) { return sum + Number(item.changed || 0); }, 0);
    const message = applying ? '已写入 ' + Number(data.applied || 0) + ' 个文件' : '预览完成，共 ' + total + ' 处变更';
    out.appendChild(node('div', 'msg ' + (applying || total ? 'ok' : 'warn'), message + (data.note ? ' · ' + data.note : '')));
    if (data.reuse_db_password === true) {
      const source = typeof data.secret_sync_source === 'string' ? data.secret_sync_source : '/data/AIGO/platform_start/Config_files/config.ini';
      out.appendChild(node('div','msg warn',(applying ? '已沿用主配置密码同步。' : '本次将沿用主配置密码同步。') + ' 来源：' + source + '；密码仅在服务器内处理，预览不会显示密码。'));
    }
    if (applying && data.backup) out.appendChild(node('p', 'security-plan-hint', '备份目录：' + data.backup));
    results.forEach(function (item) {
      const changes = Array.isArray(item.changes) ? item.changes : [];
      const skipped = Array.isArray(item.skipped) ? item.skipped : [];
      if (!changes.length && !skipped.length && !item.changed) return;
      const card = node('section', 'security-result-card');
      const heading = node('h3', 'security-result-heading', item.path || '配置文件');
      heading.appendChild(node('span', 'chip', Number(item.changed || 0) + ' 处变更')); card.appendChild(heading);
      if (changes.length) {
        const table = makeTable(['位置','字段','原值','新值']);
        changes.forEach(function (change) {
          const key = change.key || '';
          resultRow(table.body, [change.section || '—', key, node('code',sensitiveKey.test(key)?'security-redacted':'',safeValue(key,change.old)), node('code',sensitiveKey.test(key)?'security-redacted':'',safeValue(key,change.new))]);
        });
        card.appendChild(table.wrap);
      }
      skipped.forEach(function (item) {
        const key = String(item.key || '');
        const configuredField = window.STATE && Array.isArray(window.STATE.fields) && window.STATE.fields.find(function (field) { return field.key === key; });
        const label = configLabels[key] || (configuredField && configuredField.label) || key || '配置字段';
        const updateHint = key === 'db_password' ? '可填写新密码，或勾选“沿用主配置密码同步”。' : (sensitiveKey.test(key) ? '需重新输入才会更新。' : '');
        card.appendChild(node('p', 'security-form-note', label + '：未填写，保留原值。' + updateHint));
      });
      // Full text diffs are intentionally omitted: the structured changes above are redacted.
      out.appendChild(card);
    });
    const hint = node('p', 'security-plan-hint', applying ? '本次计划已使用。继续修改时，请重新预览。' : (plan ? '预览已就绪。核对后可应用；修改任一字段或目标文件后，需要重新预览。' : '未生成可应用的计划，请重新预览。'));
    hint.id = 'security-plan-state'; out.appendChild(hint);
  }
  async function secureGo(action) {
    if (busy) return;
    if (!canWrite()) { report('只读账号可查看配置，不能预览或应用变更。', 'warn'); return; }
    if (!['preview','apply'].includes(action)) return;
    if (action === 'apply' && (!plan || planFingerprint !== capture())) {
      invalidate(); report('请先预览并核对当前变更，再应用配置。', 'warn'); return;
    }
    const snapshot = capture(), payload = JSON.parse(snapshot);
    if (!payload.files.length) { report('请先勾选要修改的文件。', 'warn'); return; }
    busy = true; updateButtons();
    const controls = Array.from(document.querySelectorAll('#network-section input,#network-section button,#config-section input,#config-section button,#file-section input,#file-section button')).map(function(input){return {input:input,disabled:input.disabled};});
    controls.forEach(function(item){item.input.disabled=true;});
    document.getElementById('out').replaceChildren(node('div','msg warn',action==='preview'?'正在核对变更…':'正在应用已预览的变更…'));
    document.getElementById('topmsg').replaceChildren();
    try {
      if (action === 'preview') {
        plan = null; planFingerprint = '';
        const data = await request('/api/preview', payload);
        if (snapshot === capture() && data.plan_id) { plan = String(data.plan_id); planFingerprint = snapshot; }
        renderResults(data, false);
        if (snapshot !== capture()) report('预览期间配置已发生变化，请重新预览。', 'warn');
      } else {
        const id = plan; plan = null; planFingerprint = '';
        const data = await request('/api/apply', {plan_id:id});
        // Submitted password values are no longer needed in the browser after the write.
        document.querySelectorAll('#fields input[data-key]').forEach(function(input){if(sensitiveKey.test(input.dataset.key||'')){if(input.value)configured[input.dataset.key]=true;input.value='';}});
        const reuse = document.getElementById('security-reuse-db-password');if(reuse)reuse.checked=false;
        renderResults(data, true); applyFieldProtection();
      }
    } catch (error) {
      plan = null; planFingerprint = '';
      document.getElementById('out').replaceChildren(node('div','msg err',error.message || '请求失败，请稍后重试。'));
    } finally {
      controls.forEach(function(item){item.input.disabled=item.disabled;});
      busy = false; updateDbPasswordSync();updateButtons();
    }
  }
  function secureGenSecret() {
    if (!canWrite()) return;
    const input = document.getElementById('f_zlk_secret');
    if (!input) return;
    input.value = '__RANDOM__'; input.placeholder = '将在应用时更新';
    invalidate(); applyFieldProtection();
    report('已请求更新 ZLK 密钥；请先预览，再应用。', 'ok');
  }
  function dialog(title, description, wide) {
    const modal = node('dialog', 'security-dialog' + (wide ? ' security-dialog-wide' : ''));
    const heading = node('div','security-dialog-heading'), copy=node('div'), titleNode=node('h2','',title);
    titleNode.id = 'security-dialog-title-' + Date.now(); modal.setAttribute('aria-labelledby',titleNode.id);
    copy.appendChild(titleNode); if(description)copy.appendChild(node('p','',description));
    const close=node('button','security-dialog-close','×');close.type='button';close.setAttribute('aria-label','关闭窗口');
    close.addEventListener('click',function(){modal.close();});heading.append(copy,close);
    const body=node('div','security-dialog-body');modal.append(heading,body);document.body.appendChild(modal);
    modal.addEventListener('close',function(){modal.remove();if(accountButton)accountButton.focus();});
    modal.showModal();return {modal:modal,body:body};
  }
  function feedback(body) {
    const box=node('div','security-feedback');box.hidden=true;box.setAttribute('role','alert');body.appendChild(box);
    return function(text,ok){box.textContent=text;box.className='security-feedback'+(ok?' ok':'');box.hidden=!text;};
  }
  function field(label, type, hint) {
    const wrap=node('label','security-form-field');wrap.appendChild(node('span','',label));
    const input=node(type==='select'?'select':'input');if(type!=='select')input.type=type||'text';wrap.appendChild(input);
    if(hint)wrap.appendChild(node('small','',hint));return {wrap:wrap,input:input};
  }
  function button(text, primary, handler) {
    const item=node('button','security-button'+(primary?' security-button-primary':''),text);item.type='button';
    if(handler)item.addEventListener('click',handler);return item;
  }
  async function changePassword() {
    const view=dialog('修改密码','修改成功后，当前账号的所有会话都会退出，需要重新登录。');
    const notify=feedback(view.body),form=node('form','security-form');
    const old=field('当前密码','password'),fresh=field('新密码','password','15–128 个字符，建议使用易记的长口令。'),confirmation=field('确认新密码','password');
    old.input.autocomplete='current-password';fresh.input.autocomplete='new-password';confirmation.input.autocomplete='new-password';
    [old,fresh,confirmation].forEach(function(item){item.input.required=true;item.input.maxLength=128;form.appendChild(item.wrap);});fresh.input.minLength=15;
    const footer=node('div','security-form-footer'),cancel=button('取消',false,function(){view.modal.close();}),save=button('保存新密码',true);save.type='submit';footer.append(cancel,save);form.appendChild(footer);view.body.appendChild(form);
    form.addEventListener('submit',async function(event){
      event.preventDefault();if(!form.reportValidity())return;
      if(fresh.input.value!==confirmation.input.value){notify('两次输入的新密码不一致。');confirmation.input.focus();return;}
      save.disabled=true;notify('');
      try{await request('/api/auth/password',{old_password:old.input.value,new_password:fresh.input.value});old.input.value='';fresh.input.value='';confirmation.input.value='';redirectLogin();}
      catch(error){notify(error.message);save.disabled=false;}
    });
    old.input.focus();
  }
  function userEditor(user, reload) {
    const editing=Boolean(user),view=dialog(editing?'编辑账号':'新建账号',editing?'调整角色、启用状态，或为该账号重设密码。':'为每位使用者分配独立账号，便于权限控制与审计。');
    const notify=feedback(view.body),form=node('form','security-form'),grid=node('div','security-form-grid');
    const username=field('用户名','text','3–32 位字母、数字、下划线、点或连字符。'),role=field('角色','select');
    username.input.required=true;username.input.maxLength=32;username.input.pattern='[A-Za-z0-9_.-]{3,32}';username.input.autocomplete='off';username.input.spellcheck=false;
    Object.keys(roles).forEach(function(key){const option=node('option','',roles[key]);option.value=key;role.input.appendChild(option);});
    const password=field(editing?'重设密码（可选）':'初始密码','password',editing?'留空时保持原密码；重设后，该账号需要重新登录。':'15–128 个字符。通过安全渠道将初始密码交给本人。');
    password.input.autocomplete='new-password';password.input.minLength=15;password.input.maxLength=128;password.input.required=!editing;
    const check=node('label','security-form-check'),disabled=node('input');disabled.type='checkbox';check.append(disabled,node('span','','停用此账号'));
    if(editing){username.input.value=user.username;username.input.readOnly=true;role.input.value=user.role;disabled.checked=Boolean(user.disabled);}
    else role.input.value='viewer';
    if(editing&&me&&user.username===me.username){disabled.disabled=true;check.appendChild(node('span','security-current-user','当前账号请保持启用'));}
    grid.append(username.wrap,role.wrap);form.append(grid,password.wrap,check);
    const footer=node('div','security-form-footer'),cancel=button('取消',false,function(){view.modal.close();}),save=button('保存账号',true);save.type='submit';footer.append(cancel,save);form.appendChild(footer);view.body.appendChild(form);
    form.addEventListener('submit',async function(event){
      event.preventDefault();if(!form.reportValidity())return;
      const payload={username:username.input.value.trim(),role:role.input.value,disabled:disabled.checked};if(password.input.value)payload.password=password.input.value;
      save.disabled=true;notify('');
      try{await request('/api/users',payload);password.input.value='';view.modal.close();await reload();}
      catch(error){notify(error.message);save.disabled=false;}
    });username.input.focus();
  }
  async function manageUsers() {
    const view=dialog('账号管理','管理员维护账号；操作员派发配置；只读账号仅查看。',true),notify=feedback(view.body);
    const toolbar=node('div','security-toolbar'),copy=node('span','security-toolbar-copy','账号应按人分配，请勿多人共用。'),add=button('新建账号',true,function(){userEditor(null,reload);});toolbar.append(copy,add);view.body.appendChild(toolbar);
    const host=node('div');view.body.appendChild(host);
    async function reload(){
      host.replaceChildren(node('p','security-empty','正在读取账号…'));notify('');
      try{
        const data=await request('/api/users'),users=Array.isArray(data.users)?data.users:[];
        host.replaceChildren();const table=makeTable(['用户名','角色','状态','操作']);
        users.forEach(function(user){
          const name=node('span','',user.username);if(me&&user.username===me.username)name.appendChild(node('span','security-current-user','当前账号'));
          const status=node('span','security-user-status'+(user.disabled?' disabled':''),user.disabled?'已停用':'已启用');
          const edit=button('编辑',false,function(){userEditor(user,reload);});edit.classList.add('security-button-small');
          resultRow(table.body,[name,roles[user.role]||user.role,status,edit]);
        });host.appendChild(users.length?table.wrap:node('div','security-empty','暂无账号。'));
      }catch(error){host.replaceChildren();notify(error.message);}
    }
    await reload();
  }
  function auditDetail(event) {
    const detail=event.details===undefined?event.detail:event.details;
    if(detail===undefined||detail===null)return '—';
    function scrub(value,key){
      if(sensitiveKey.test(key||''))return '（已隐藏）';
      if(Array.isArray(value))return value.map(function(item){return scrub(item,'');});
      if(value&&typeof value==='object'){const output={};Object.keys(value).forEach(function(name){output[name]=scrub(value[name],name);});return output;}
      return value;
    }
    if(typeof detail==='string')return detail;
    return JSON.stringify(scrub(detail,''));
  }
  async function showAudit() {
    const view=dialog('操作审计','查看近期登录、账号维护与配置派发记录。',true),notify=feedback(view.body);
    const toolbar=node('div','security-toolbar'),copy=node('span','security-toolbar-copy','记录由服务器生成，展示最近的操作。'),refresh=button('刷新记录',false,reload);toolbar.append(copy,refresh);view.body.appendChild(toolbar);
    const host=node('div');view.body.appendChild(host);
    async function reload(){
      refresh.disabled=true;notify('');host.replaceChildren(node('div','security-empty','正在读取审计记录…'));
      try{
        const data=await request('/api/audit'),events=Array.isArray(data.events)?data.events:[];host.replaceChildren();
        const table=makeTable(['时间','账号','操作','结果','来源','详情']);
        events.forEach(function(event){
          const success=event.success===undefined?(event.ok===undefined?(event.result||event.status||'—'):(event.ok?'成功':'失败')):(event.success?'成功':'失败');
          resultRow(table.body,[event.time||event.timestamp||event.ts||'—',event.username||event.user||event.actor||'—',event.action||event.event||'—',success,event.ip||event.remote_ip||event.remote||'—',node('span','security-audit-detail',auditDetail(event))]);
        });host.appendChild(events.length?table.wrap:node('div','security-empty','暂无审计记录。'));
      }catch(error){host.replaceChildren();notify(error.message);}finally{refresh.disabled=false;}
    }
    await reload();
  }
  function renderAccount() {
    if(!me||document.getElementById('security-account'))return;
    const header=document.querySelector('.app-header');if(!header)return;
    const account=node('div','security-account');account.id='security-account';
    accountButton=node('button','security-account-button');accountButton.type='button';accountButton.setAttribute('aria-expanded','false');accountButton.setAttribute('aria-haspopup','menu');accountButton.setAttribute('aria-controls','security-account-menu');
    accountButton.append(node('span','security-avatar',me.username.slice(0,1).toUpperCase()),node('span','',me.username),node('span','security-role',roles[me.role]),node('span','security-chevron','⌄'));
    menu=node('div','security-menu');menu.id='security-account-menu';menu.hidden=true;menu.setAttribute('role','menu');
    function menuItem(text,handler,className){const item=node('button',className||'',text);item.type='button';item.setAttribute('role','menuitem');item.addEventListener('click',function(){closeMenu();handler();});menu.appendChild(item);}
    menuItem('修改本人密码',changePassword);
    if(me.role==='admin'){menuItem('账号管理',manageUsers);menuItem('操作审计',showAudit);}
    menuItem('退出登录',async function(){try{await request('/api/auth/logout',{});redirectLogin();}catch(error){report(error.message);}},'security-logout');
    accountButton.addEventListener('click',function(){menu.hidden=!menu.hidden;accountButton.setAttribute('aria-expanded',String(!menu.hidden));if(!menu.hidden)menu.querySelector('button').focus();});
    account.append(accountButton,menu);header.appendChild(account);
    if(!canWrite()){
      const hero=document.querySelector('.workspace-hero');if(hero){const note=node('div','security-access-note','你正在使用只读账号。可查看已脱敏的配置与文件列表；修改和派发请联系管理员或操作员。');hero.insertAdjacentElement('afterend',note);}
    }
    const description=document.querySelector('#config-section .section-description');if(description)description.textContent='按服务分组调整连接参数；密码和密钥不回传，留空时保留原值。';
    const note=document.querySelector('#config-section > .hint');if(note){note.appendChild(node('span','security-form-note',' 敏感值在预览中隐藏，随机密钥仅在服务器应用时生成。'));}
  }
  function closeMenu(){if(menu){menu.hidden=true;accountButton.setAttribute('aria-expanded','false');}}
  function install() {
    if(installed)return;installed=true;
    // Existing global declarations run after this file, so install the replacements after parsing.
    window.go=secureGo;window.genSecret=secureGenSecret;
    ['syncPrimary','onPrimaryInput','selAll'].forEach(function(name){
      const original=window[name];if(typeof original==='function')window[name]=function(){if(!canWrite())return;const result=original.apply(this,arguments);invalidate();return result;};
    });
    function dispatchAction(event){
      const target=event.target.closest&&event.target.closest('[data-dispatch-action]');if(!target)return;
      const action=String(target.dataset.dispatchAction||'').replace(/\s/g,'').replace(/;$/,'');
      if(action==='onPrimaryInput()'){
        if(event.type==='input'||event.type==='change'){if(typeof window.onPrimaryInput==='function')window.onPrimaryInput();}
        return;
      }
      if(event.type!=='click')return;
      if(action==="go('preview')"||action==='go("preview")')secureGo('preview');
      else if(action==="go('apply')"||action==='go("apply")')secureGo('apply');
      else if(action==='genSecret()')secureGenSecret();
      else if(action==='syncPrimary()'&&typeof window.syncPrimary==='function')window.syncPrimary();
      else if(action==='selAll(true)'&&typeof window.selAll==='function')window.selAll(true);
      else if(action==='selAll(false)'&&typeof window.selAll==='function')window.selAll(false);
    }
    document.addEventListener('input',function(event){dispatchAction(event);if(event.target.closest&&event.target.closest('#network-section,#config-section,#file-section'))invalidate();});
    document.addEventListener('change',function(event){dispatchAction(event);if(event.target.closest&&event.target.closest('#network-section,#config-section,#file-section'))invalidate();});
    document.addEventListener('click',function(event){
      dispatchAction(event);
      // Network address chips use native JS handlers which may change values without input events.
      if(event.target.closest&&event.target.closest('#network-section .ipbtn'))invalidate();
      if(menu&&!event.target.closest('#security-account'))closeMenu();
    });
    document.addEventListener('keydown',function(event){if(event.key==='Escape')closeMenu();});
    // Changes from load() and the presentation grouping script arrive asynchronously.
    const observer=new MutationObserver(function(){applyFieldProtection();});
    const fields=document.getElementById('fields'),files=document.getElementById('files');
    if(fields)observer.observe(fields,{childList:true,subtree:true});if(files)observer.observe(files,{childList:true,subtree:true});
    ready.then(function(){renderAccount();applyFieldProtection();}).catch(function(){});updateButtons();
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
})();
