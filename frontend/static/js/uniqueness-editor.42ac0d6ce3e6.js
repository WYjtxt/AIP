/* Per-task calibration panel for the existing authenticated Vue editor. */
(function (root) {
  'use strict';
  var STYLE = `
  #app .home .algorithm-config-page.uniqueness-config-page > .sfpzs{max-width:900px!important;width:100%!important;padding:4px 24px 32px!important;box-sizing:border-box}
  #app .home .uniqueness-config-page .algorithm-config-top{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:18px;max-width:none!important;margin:0!important}
  #app .home .uniqueness-config-page :is(.algorithm-basic-panel,.algorithm-model-settings){width:100%;padding:20px 24px!important;background:#fff!important;gap:16px!important;scroll-margin-top:16px}
  #app .home .uniqueness-config-page .algorithm-panel-title{font-size:16px;line-height:26px;margin:0 0 8px}
  #app .home .uniqueness-config-page :is(.algorithm-basic-panel,.algorithm-model-settings,.algorithm-drawing-scroll) .el-form-item{display:flex!important;flex-wrap:wrap;align-items:flex-start;width:100%!important;max-width:680px!important;margin:0 auto 14px!important;padding:0!important;box-sizing:border-box}
  #app .home .uniqueness-config-page :is(.algorithm-basic-panel,.algorithm-model-settings,.algorithm-drawing-scroll) .el-form-item__label{width:140px!important;float:none!important;text-align:right!important;padding:0 18px 0 0!important;line-height:34px!important;flex:none}
  #app .home .uniqueness-config-page :is(.algorithm-basic-panel,.algorithm-model-settings,.algorithm-drawing-scroll) .el-form-item__content{margin-left:0!important;flex:1;min-width:0;line-height:34px}
  #app .home .uniqueness-config-page :is(.algorithm-basic-panel,.algorithm-model-settings,.algorithm-drawing-scroll) .el-form-item__content > :is(.el-input,.el-select,.el-cascader,.el-input-number,.el-textarea){width:100%!important;max-width:520px!important;float:none!important}
  #app .home .uniqueness-config-page .algorithm-template-parameters{margin:0!important;width:100%!important;padding:0!important}
  #app .home .uniqueness-config-page .algorithm-drawing-scroll{height:auto!important;min-width:0!important;width:100%!important;overflow:visible!important;margin:18px 0;padding:20px 24px!important;box-sizing:border-box;border:1px solid #e1e8f2!important;background:#fff!important;scroll-margin-top:16px}
  #app .home .uniqueness-config-page .algorithm-drawing-scroll:before{content:'通用运行参数';display:block;font-size:16px;font-weight:600;margin-bottom:18px;color:#30445f}
  #app .home .uniqueness-config-page .algorithm-drawing-scroll > div:first-child{display:none!important}
  #app .home .uniqueness-config-page .algorithm-drawing-scroll > div:nth-child(2){height:auto!important;min-width:0!important;width:100%!important;display:grid;grid-template-columns:minmax(0,1fr);gap:0}
  #app .home .uniqueness-config-page .algorithm-drawing-scroll > div:nth-child(2) > div{float:none!important;width:100%!important;height:auto!important;margin:0!important;min-width:0}
  #app .home .uniqueness-config-page .algorithm-form-actions{position:sticky;bottom:0;z-index:4;background:#fff;border-top:1px solid #e1e8f2;max-width:none!important;margin:0!important;padding:12px 0!important}
  #app .home .uniqueness-config-page .algorithm-form-actions .el-form-item__content{margin-left:0!important}
  #app .home .uniqueness-config-page .algorithm-action-buttons{justify-content:center;max-width:none!important;padding:0!important;border:0!important;flex-wrap:wrap}
  #app .home .uniqueness-config-page .algorithm-action-buttons:before{content:'基础与运行配置';color:#60718a;font-size:13px;margin-right:10px}
  .uniqueness-navigation{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin:0 0 18px;padding:12px;background:#f5f8fc;border-radius:8px}
  .uniqueness-navigation button,.uniqueness-panel button{font:inherit;font-size:13px;cursor:pointer;border:1px solid #d4dfef;border-radius:5px;padding:8px 12px;color:#245fd2;background:#fff}
  .uniqueness-panel{box-sizing:border-box;width:100%;min-width:0;max-width:none;margin:18px 0;padding:20px 24px;border:1px solid #e1e8f2;border-radius:8px;background:#fff;color:#30445f;font-size:14px}
  .uniqueness-panel h3,.uniqueness-panel h4{font-size:16px;font-weight:600;line-height:26px;margin:0 0 14px;scroll-margin-top:16px}
  .uniqueness-panel h4{padding-top:20px;margin-top:20px;border-top:1px solid #e8edf4}
  .uniqueness-panel p{line-height:1.7;font-size:13px;margin:10px 0 14px}
  .uniqueness-panel .uniqueness-status{padding:10px 14px;background:#f0f6ff;color:#386191;border-radius:5px}
  .uniqueness-panel .uniqueness-hint{color:#748299}
  .uniqueness-panel canvas{display:block;width:100%;max-width:640px;height:auto;aspect-ratio:16/9;margin:16px auto 0;cursor:crosshair;border-radius:4px;touch-action:none}
  .uniqueness-panel canvas:focus-visible{outline:2px solid #2864ee;outline-offset:3px}
  .uniqueness-actions{display:flex;justify-content:center;align-items:center;gap:8px;flex-wrap:wrap;margin:14px 0}
  .uniqueness-panel select,.uniqueness-panel input{font:inherit;font-size:13px;padding:8px 10px;border:1px solid #cdd8e8;border-radius:5px;background:#fff;color:#30445f;min-width:0;box-sizing:border-box}
  .uniqueness-panel button:disabled{opacity:.45;cursor:default}
  .uniqueness-fields{max-width:640px;margin:0 auto}
  .uniqueness-fields label{display:grid;grid-template-columns:160px minmax(0,1fr);align-items:center;gap:16px;margin:14px 0}
  .uniqueness-fields label[hidden]{display:none!important}
  .uniqueness-fields label span{text-align:right;line-height:1.6}
  .uniqueness-fields input:not([type=checkbox]),.uniqueness-fields select{width:100%;height:36px}
  .uniqueness-fields .uniqueness-check{display:flex;justify-content:flex-start;padding-left:176px;gap:10px}
  .uniqueness-fields .uniqueness-check span{text-align:left;font-size:13px}
  .uniqueness-fields input[type=checkbox]{order:-1;flex:none;width:16px;height:16px;margin:0;accent-color:#2864ee}
  .uniqueness-panel .uniqueness-save{padding:16px 0 0;margin:16px 0 0;border-top:1px solid #e8edf4}
  .uniqueness-panel .uniqueness-primary{background:#2864ee;border-color:#2864ee;color:#fff}
  .uniqueness-panel button:focus-visible,.uniqueness-navigation button:focus-visible{outline:2px solid #2864ee;outline-offset:2px}
  @media(max-width:700px){
    #app .home .algorithm-config-page.uniqueness-config-page > .sfpzs{padding:4px 12px 24px!important}
    #app .home .uniqueness-config-page :is(.algorithm-basic-panel,.algorithm-model-settings,.algorithm-drawing-scroll){padding:16px!important}
    #app .home .uniqueness-config-page :is(.algorithm-basic-panel,.algorithm-model-settings,.algorithm-drawing-scroll) .el-form-item{display:block!important}
    #app .home .uniqueness-config-page :is(.algorithm-basic-panel,.algorithm-model-settings,.algorithm-drawing-scroll) .el-form-item__label{display:block;width:100%!important;text-align:left!important;padding:0!important}
    .uniqueness-panel{padding:16px}
    .uniqueness-fields label{grid-template-columns:minmax(0,1fr);gap:6px}
    .uniqueness-fields label span{text-align:left}
    .uniqueness-fields .uniqueness-check{padding-left:0}
  }
  #app .home .uniqueness-config-page .el-form-item[style*="display: none"],#app .home .uniqueness-config-page .el-form-item[style*="display:none"]{display:none!important}`;
  var app, kinds = {}, catalogReady = false, keys = {entry:'入口区', gate:'闸内区', exit:'出口区', obstacle:'阻挡区'}, colors = {entry:'#38ae54', gate:'#edac26', exit:'#267cf0', obstacle:'#ef5350'};
  function node(tag, text) { var e = document.createElement(tag); if (text != null) e.textContent = text; return e; }
  function button(text, fn) { var b = node('button',text); b.type='button'; b.onclick=fn; return b; }
  function endpoint(id) { return ((root.wgParameter && root.wgParameter.url_5000)||'').replace(/\/$/,'')+'/model_view/uniqueness/tasks/'+id; }
  function body(r) { if (!r || !r.data || r.data.code!==200) throw new Error(r && r.data && r.data.msg || '请求失败'); return r.data.data; }
  function error(e) { return e && e.response && e.response.data && e.response.data.msg || e.message || '请求失败'; }
  function taskId(vm) { var q=vm.$route && vm.$route.query||{}; return String(q.conf_id||q.id||''); }
  function supported(vm) { var f=vm.form; return !!(f && vm.$route && /^\/sfgl_childs?$/.test(vm.$route.path) && kinds[String(f.Algorithm_library_id)] && /^\d+$/.test(taskId(vm)) && String(f.id)===taskId(vm)); }
  function loadKinds(attempt) {
    var url=((root.wgParameter && root.wgParameter.url_5000)||'').replace(/\/$/,'')+'/model_view/algorithm_first/catalog';
    app.$http.get(url).then(function(r){
      var names={'人员尾随':'tailgating','唯一性尾随':'tailgating','违规跨越':'crossing','唯一性违规跨越':'crossing'};
      kinds={};body(r).algorithms.forEach(function(a){if(names[a.model_name])kinds[String(a.id)]=names[a.model_name];});
      catalogReady=true;visit(app);
    }).catch(function(){if(attempt<5)root.setTimeout(function(){loadKinds(attempt+1);},2000);});
  }
  function cleanup(vm) { var s=vm._uniquenessPanel; if(s){s.dead=true;root.clearTimeout(s.statusTimer);s.panel.remove();if(s.nav)s.nav.remove();vm.$el.classList.remove('uniqueness-config-page');delete vm._uniquenessPanel;} }
  function message(s,text) { s.message.textContent=text; }
  function updateDrawing(s) {
    s.begin.textContent=s.cfg && s.cfg[s.zone] && s.cfg[s.zone].length?'重绘所选区域':'开始绘制';
    s.zoneSelect.disabled=!!s.drawing;s.finish.disabled=!s.editable || !s.drawing;s.undo.disabled=!s.editable || (!s.drawing && !s.history.length);s.cancel.disabled=!s.drawing;
    s.progress.textContent=s.zones.map(function(k){return keys[k]+'：'+(s.cfg && s.cfg[k] && s.cfg[k].length>=3?'已绘制':'待绘制');}).join('　');
  }
  function updateStatus(s,data,initial){
    var cameraChanged=!!data.camera_changed || Number(data.equipment_id)!==Number(s.data.equipment_id);
    var stopped=String(data.status)==='2' && Number(data.model_status)===4;
    var key=String(data.status)+':'+String(data.model_status)+':'+cameraChanged;
    s.editable=stopped && !cameraChanged;s.save.disabled=!s.editable || !!s.saving;s.begin.disabled=!s.editable;
    if(initial || key!==s.statusKey){
      var hint=cameraChanged?'摄像机已变化，请重新载入配置后标定。':stopped?'任务已停止，现在可以绘制和保存区域。':String(data.status)==='1'?'任务正在运行，请先在任务列表停止；停止后本页会自动解锁。':'正在等待停止确认，页面会自动检查并解锁，无需反复刷新。';
      message(s,hint+(initial && !s.cfg.calibrated?' 尚未完成现场标定，请按实际画面绘制区域。':''));
    }
    s.statusKey=key;updateDrawing(s);
  }
  function scheduleStatus(s){
    root.clearTimeout(s.statusTimer);if(s.dead)return;
    s.statusTimer=root.setTimeout(function(){
      if(s.dead)return;if(s.saving){scheduleStatus(s);return;}
      var original=s.data;
      app.$http.get(endpoint(s.id)).then(function(r){
        if(s.dead || s.data!==original || s.saving)return;
        // Refresh only task state. Never replace polygons, history, revision or form drafts.
        updateStatus(s,body(r),false);
      }).catch(function(){
        if(s.dead || s.data!==original || s.saving)return;
        s.statusKey='unavailable';s.editable=false;s.save.disabled=true;s.begin.disabled=true;updateDrawing(s);
        message(s,'暂时无法确认任务状态，正在重试；已绘制内容仍保留。');
      }).then(function(){scheduleStatus(s);});
    },s.editable?5000:2000);
  }
  function copyPoints(points){return (points||[]).map(function(p){return p.slice();});}
  function cursorPoint(s,e){var r=s.canvas.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];}
  function distance(s,a,b){var r=s.canvas.getBoundingClientRect();return Math.hypot((a[0]-b[0])*r.width,(a[1]-b[1])*r.height);}
  function validArea(points){return points.length>=3 && Math.abs(points.reduce(function(sum,p,i){var q=points[(i+1)%points.length];return sum+p[0]*q[1]-q[0]*p[1];},0))/2>=.0001;}
  function startDrawing(s){if(!s.editable)return;s.drawing=true;s.points=[];s.hover=null;message(s,'正在绘制'+keys[s.zone]+'：依次点击顶点，点击首点或双击闭合；Esc 取消。');updateDrawing(s);draw(s);s.canvas.focus({preventScroll:true});}
  function finishDrawing(s){
    if(!s.editable || !s.drawing)return;
    if(!validArea(s.points)){message(s,'请至少绘制三个不在同一直线上的顶点。');return;}
    var finished=s.zone;s.history.push({zone:finished,points:copyPoints(s.cfg[finished])});s.cfg[finished]=copyPoints(s.points);s.drawing=false;s.hover=null;s.dirty=true;
    var next=s.zones.filter(function(k){return !s.cfg[k] || s.cfg[k].length<3;})[0];
    if(next){s.zone=next;s.zoneSelect.value=next;}
    updateDrawing(s);draw(s);message(s,keys[finished]+'已绘制。'+(next?'已选中'+keys[next]+'，直接点击画面继续绘制。':'区域已画齐，可拖动所选区域的顶点微调，确认后保存。'));
  }
  function cancelDrawing(s){s.drawing=false;s.points=[];s.hover=null;updateDrawing(s);draw(s);message(s,'已取消本次绘制，保留原区域。');}
  function undoDrawing(s){if(!s.editable)return;if(s.drawing)s.points.pop();else if(s.history.length){var old=s.history.pop();s.zone=old.zone;s.zoneSelect.value=old.zone;s.cfg[old.zone]=old.points;s.dirty=true;}updateDrawing(s);draw(s);}
  function draw(s) {
    var c=s.canvas.getContext('2d'); c.clearRect(0,0,640,360);c.fillStyle='#e9eef5';c.fillRect(0,0,640,360);
    if(s.image && s.image.complete && s.image.naturalWidth)c.drawImage(s.image,0,0,640,360);
    if(!s.cfg)return;
    s.zones.forEach(function(k){var points=k===s.zone && s.drawing ? s.points : s.cfg[k];if(!points || !points.length)return;
      c.strokeStyle=colors[k];c.fillStyle=colors[k];c.lineWidth=2;c.beginPath();points.forEach(function(p,i){if(i)c.lineTo(p[0]*640,p[1]*360);else c.moveTo(p[0]*640,p[1]*360);});
      if(!(k===s.zone && s.drawing)){c.closePath();c.globalAlpha=k===s.zone ? .12 : .04;c.fill();c.globalAlpha=1;}c.stroke();c.font='14px sans-serif';c.fillText(keys[k],points[0][0]*640,Math.max(16,points[0][1]*360-5));
      points.forEach(function(p){c.beginPath();c.arc(p[0]*640,p[1]*360,k===s.zone?5:3,0,Math.PI*2);c.fill();});
    });
    if(s.drawing && s.hover && s.points.length){var last=s.points[s.points.length-1];c.strokeStyle=colors[s.zone];c.setLineDash([5,4]);c.beginPath();c.moveTo(last[0]*640,last[1]*360);c.lineTo(s.hover[0]*640,s.hover[1]*360);c.stroke();c.setLineDash([]);}
  }
  function refreshImage(s) {
    var url=s.vm.imgurl;if(!url || url===s.imageUrl)return;s.imageUrl=url;s.image=new Image();s.image.onload=function(){if(!s.dead)draw(s);};s.image.src=url;
  }
  function control(s,label,key,type,options) {
    var row=node('label'), caption=node('span',label), input=node(type==='select'?'select':'input');row.appendChild(caption);
    if(type==='select') options.forEach(function(o){var n=node('option',o[1]);n.value=o[0];input.appendChild(n);});
    else input.type=type;
    if(type==='number'){input.step='any';input.min='0';}
    input.onchange=function(){if(s.cfg){s.cfg[key]=type==='checkbox'?input.checked:type==='number'?Number(input.value):input.value;s.dirty=true;
      if(key==='passage_confirmation'||key==='crossing_confirmation'){s.cfg.calibrated=false;s.controls.calibrated.checked=false;s.drawing=false;s.points=[];s.history=[];message(s,'确认方式已改变，请核对所需区域并重新勾选现场标定确认。');}
      updateFields(s);}};
    input.setAttribute('aria-label',label);row.dataset.field=key;row.className=type==='checkbox'?'uniqueness-check':'uniqueness-field';row.appendChild(input);s.fields.appendChild(row);s.controls[key]=input;
  }
  function updateFields(s) {
    if(!s.cfg || !s.data)return;
    ['passage_confirmation','crossing_confirmation','direction','authorization_mode','message_delay','session_gap','pose_confidence','action_frames','action_duration','support_posture_enabled'].forEach(function(k){
      s.controls[k].parentNode.hidden=['crossing_confirmation','pose_confidence','action_frames','action_duration','support_posture_enabled'].indexOf(k)>=0?s.data.kind!=='crossing':s.data.kind!=='tailgating' || (k==='direction' && s.cfg.authorization_mode!=='controller');
    });
    var zones=s.data.kind==='tailgating'?(s.cfg.passage_confirmation==='gate'?['entry','gate']:['entry','gate','exit']):(s.cfg.crossing_confirmation==='obstacle'?['obstacle']:['entry','exit','obstacle']);
    if(JSON.stringify(zones)!==JSON.stringify(s.zones)){
      s.zones=zones;if(zones.indexOf(s.zone)<0)s.zone=zones[0];s.zoneSelect.textContent='';
      zones.forEach(function(k){var o=node('option',keys[k]);o.value=k;s.zoneSelect.appendChild(o);});s.zoneSelect.value=s.zone;updateDrawing(s);draw(s);
    }
    s.guide.textContent=s.data.kind==='tailgating'?(s.cfg.passage_confirmation==='gate'?'依次绘制入口区和闸内区，以人头中心从入口稳定进入闸内确认通行，无需拍到出口。入口应在闸机外，闸内应位于闸机内侧，避免重叠。':'依次绘制入口区、闸内区、出口区，以人头中心完整通过三区确认通行。'):(s.cfg.crossing_confirmation==='obstacle'?'紧贴实际闸机或栏杆绘制阻挡区，勿将正常通道一起圈入。抬高的膝部进入阻挡区，并有髋部或手腕位置佐证的动作连续出现即可报警，无需入口轨迹或落地；报警会注明未确认落地。':'在阻挡物两侧绘制入口区、出口区，并绘制实际阻挡区；连续越障动作且异侧稳定落地后报警，适合完整视野。');
  }
  function apply(s,data) {
    if(s.dead)return;s.data=data;s.cfg=JSON.parse(JSON.stringify(data.configuration));s.dirty=false;s.drawing=false;s.points=[];s.history=[];s.hover=null;
    var temporalDefaults={max_fps:20,zone_hits:2,session_gap:3,action_frames:2,action_duration:.1};Object.keys(temporalDefaults).forEach(function(k){if(s.cfg[k]==null)s.cfg[k]=temporalDefaults[k];});
    if(!s.cfg.passage_confirmation)s.cfg.passage_confirmation=s.cfg.calibrated?'exit':'gate';
    if(!s.cfg.crossing_confirmation)s.cfg.crossing_confirmation=s.cfg.calibrated?'landing':'obstacle';
    s.zones=data.kind==='tailgating'?['entry','gate','exit']:['entry','exit','obstacle'];s.zone=s.zones[0];s.zoneSelect.textContent='';
    // Discard only the complete legacy example in the local draft. Saved custom polygons stay intact.
    var example={entry:[[0,0],[.3,0],[.3,1],[0,1]],gate:[[.3,0],[.7,0],[.7,1],[.3,1]],exit:[[.7,0],[1,0],[1,1],[.7,1]],obstacle:[[.3,0],[.7,0],[.7,1],[.3,1]]};
    if(!s.cfg.calibrated && s.zones.every(function(k){return JSON.stringify(s.cfg[k])===JSON.stringify(example[k]);}))s.zones.forEach(function(k){s.cfg[k]=[];});
    s.heading.textContent=data.kind==='tailgating'?'尾随区域标定':'跨越区域标定';
    s.zones=[];updateFields(s);
    Object.keys(s.controls).forEach(function(k){var i=s.controls[k];if(i.type==='checkbox')i.checked=!!s.cfg[k];else i.value=s.cfg[k]==null?'':s.cfg[k];});
    updateStatus(s,data,true);refreshImage(s);draw(s);scheduleStatus(s);
  }
  function reload(s) { if((s.dirty || s.drawing) && !root.confirm('重新载入会放弃本区域面板尚未保存的修改，是否继续？'))return;
    message(s,'正在读取配置…');app.$http.get(endpoint(s.id)).then(function(r){apply(s,body(r));}).catch(function(e){message(s,error(e));}); }
  function save(s) {
    if(!s.editable || s.saving){message(s,'任务尚未停止或正在保存，请等待状态确认。');return Promise.resolve(false);}
    if(s.drawing || s.drag){message(s,'请先完成当前区域。');return Promise.resolve(false);}
    var missing=s.zones.filter(function(k){return !s.cfg[k] || s.cfg[k].length<3;});
    if(missing.length){message(s,'请先绘制：'+missing.map(function(k){return keys[k];}).join('、')+'。');return Promise.resolve(false);}
    var camera=Number(s.vm.form.Equipment_id||s.vm.form.equipment_name);
    if(camera && camera!==s.data.equipment_id){message(s,'摄像机已变化，请先保存普通配置并重新打开本页。');return Promise.resolve(false);}
    s.saving=true;s.save.disabled=true;message(s,'正在保存…');
    return app.$http.post(endpoint(s.id),{configuration:s.cfg,revision:s.data.revision,equipment_id:s.data.equipment_id}).then(function(r){apply(s,body(r));message(s,'区域与参数已保存，可继续完成任务配置并启动。');return true;}).catch(function(e){message(s,error(e));return false;}).then(function(ok){s.saving=false;if(!s.dead)s.save.disabled=!s.editable;return ok;});
  }
  function saveBeforeBatch(vm){
    var s=vm._uniquenessPanel;
    if(!s || !s.data)return Promise.reject(new Error('区域配置尚未加载完成，请稍后重试。'));
    if(s.drawing)return Promise.reject(new Error('请先完成当前区域绘制。'));
    var missing=s.zones.filter(function(k){return !validArea(s.cfg[k]||[]);});
    if(missing.length){s.heading.scrollIntoView({behavior:'smooth',block:'start'});return Promise.reject(new Error('请先绘制：'+missing.map(function(k){return keys[k];}).join('、')+'。'));}
    if(!s.cfg.calibrated)return Promise.reject(new Error('请确认现场区域，并勾选“已按现场画面完成区域标定”。'));
    if(!s.editable){if(String(s.data.status)==='1' && !s.dirty)return Promise.resolve(true);return Promise.reject(new Error('请先停止任务，再保存区域配置。'));}
    return save(s).then(function(ok){if(!ok)throw new Error(s.message.textContent);return true;});
  }
  function attach(vm) {
    if(!vm.$route || !vm.form || !vm.$el || !vm.$el.querySelector)return;
    var old=vm._uniquenessPanel;if(!supported(vm)){if(old)cleanup(vm);return;}
    if(old && old.id===taskId(vm)){refreshImage(old);return;}if(old)cleanup(vm);
    var anchor=vm.$el.querySelector('.algorithm-template-parameters');if(!anchor)return;
    var s={vm:vm,id:taskId(vm),panel:node('section'),message:node('p'),fields:node('div'),controls:{},zones:[],points:[],history:[]};vm._uniquenessPanel=s;s.panel.className='uniqueness-panel';
    s.heading=node('h3','区域标定');s.panel.appendChild(s.heading);s.message.setAttribute('role','status');s.message.className='uniqueness-status';s.panel.appendChild(s.message);
    s.guide=node('p');s.guide.className='uniqueness-hint';s.panel.appendChild(s.guide);
    s.canvas=node('canvas');s.canvas.width=640;s.canvas.height=360;s.canvas.tabIndex=0;s.canvas.setAttribute('aria-label','唯一性区域绘制画布');s.panel.appendChild(s.canvas);
    var bar=node('div');bar.className='uniqueness-actions';s.zoneSelect=node('select');s.zoneSelect.setAttribute('aria-label','选择标定区域');s.zoneSelect.onchange=function(){s.zone=this.value;s.drawing=false;s.points=[];updateDrawing(s);draw(s);};bar.appendChild(s.zoneSelect);
    s.begin=button('开始绘制',function(){startDrawing(s);});s.begin.disabled=true;bar.appendChild(s.begin);
    s.undo=button('撤销',function(){undoDrawing(s);});bar.appendChild(s.undo);
    s.finish=button('完成区域',function(){finishDrawing(s);});bar.appendChild(s.finish);
    s.cancel=button('取消绘制',function(){cancelDrawing(s);});bar.appendChild(s.cancel);
    bar.appendChild(button('刷新画面',function(){if(typeof vm.handleimg==='function')vm.handleimg(1);}));s.panel.appendChild(bar);
    s.progress=node('p');s.progress.className='uniqueness-hint';s.progress.setAttribute('aria-label','区域绘制进度');s.panel.appendChild(s.progress);updateDrawing(s);
    var help=node('p','直接点击空白区域开始画点；点击首点或双击闭合。已画区域可拖动顶点，Backspace 撤销，Esc 取消。');help.className='uniqueness-hint';s.panel.appendChild(help);
    s.canvas.onclick=function(e){
      if(s.suppressClick){s.suppressClick=false;return;}if(!s.editable || e.detail>1)return;
      if(!s.drawing){if(!s.cfg[s.zone] || !s.cfg[s.zone].length)startDrawing(s);else {message(s,'拖动所选区域的顶点进行调整，或点击“重绘所选区域”。');return;}}
      var p=cursorPoint(s,e);
      if(s.points.length>=3 && distance(s,p,s.points[0])<=10){finishDrawing(s);return;}
      if(s.points.some(function(q){return distance(s,p,q)<4;}))return;
      if(s.points.length>=32){message(s,'每个区域最多32个顶点，请闭合或撤销后调整。');return;}
      s.points.push(p);draw(s);
    };
    s.canvas.ondblclick=function(e){e.preventDefault();if(s.editable && s.drawing)finishDrawing(s);};
    s.canvas.onpointerdown=function(e){
      if(!s.editable || s.drawing || e.button!==0)return;
      var p=cursorPoint(s,e),points=s.cfg[s.zone]||[],index=points.findIndex(function(q){return distance(s,p,q)<=10;});
      if(index<0)return;
      s.drag={index:index,zone:s.zone,points:copyPoints(points),origin:p,moved:false};
      s.canvas.setPointerCapture(e.pointerId);s.canvas.focus({preventScroll:true});
    };
    s.canvas.onpointermove=function(e){
      var p=cursorPoint(s,e);
      if(s.drag){if(distance(s,p,s.drag.origin)>2)s.drag.moved=true;if(s.drag.moved){s.cfg[s.drag.zone][s.drag.index]=p;draw(s);}return;}
      if(s.drawing){s.hover=p;draw(s);}
    };
    function endDrag(e,cancel){
      if(!s.drag)return;var d=s.drag;s.drag=null;s.suppressClick=true;
      if(cancel || !validArea(s.cfg[d.zone])){s.cfg[d.zone]=d.points;message(s,'已恢复原顶点，区域不能退化为直线。');}
      else if(d.moved){s.history.push({zone:d.zone,points:d.points});s.dirty=true;message(s,keys[d.zone]+'已调整，保存后生效。');}
      if(s.canvas.hasPointerCapture(e.pointerId))s.canvas.releasePointerCapture(e.pointerId);updateDrawing(s);draw(s);
    }
    s.canvas.onpointerup=function(e){endDrag(e,false);};s.canvas.onpointercancel=function(e){endDrag(e,true);};
    s.canvas.onpointerleave=function(){s.hover=null;if(!s.drag)draw(s);};
    s.canvas.onkeydown=function(e){if(!s.editable)return;if(e.key==='Escape' && s.drawing){e.preventDefault();cancelDrawing(s);}else if(e.key==='Backspace' || ((e.ctrlKey||e.metaKey) && e.key.toLowerCase()==='z')){e.preventDefault();undoDrawing(s);}else if(e.key==='Enter' && s.drawing){e.preventDefault();finishDrawing(s);}};
    s.parametersHeading=node('h4','检测参数');s.panel.appendChild(s.parametersHeading);s.fields.className='uniqueness-fields';s.panel.appendChild(s.fields);
    control(s,'通道标识','lane_id','text');control(s,'授权消息方向','direction','select',[['forward','正向'],['reverse','反向']]);
    control(s,'授权判定','authorization_mode','select',[['video_only','纯视频：疑似尾随'],['controller','控制器有效授权关联']]);
    control(s,'尾随通行确认','passage_confirmation','select',[['gate','进入闸内确认（无需出口）'],['exit','完整通过出口确认']]);
    control(s,'跨越报警时机','crossing_confirmation','select',[['obstacle','越障动作确认（无需落地）'],['landing','异侧落地确认（完整视野）']]);
    control(s,'处理帧率上限','max_fps','number');control(s,'事件确认等待秒数','message_delay','number');
    control(s,'区域确认连续帧数','zone_hits','number');control(s,'尾随通行间隔（秒）','session_gap','number');
    control(s,'连续动作确认帧数','action_frames','number');control(s,'动作确认时长（秒）','action_duration','number');
    control(s,'支撑翻越辅助判定','support_posture_enabled','checkbox');
    control(s,'跟踪建轨置信度','detection_confidence','number');control(s,'姿态置信度','pose_confidence','number');
    [['max_fps',1,25],['message_delay',0,10],['detection_confidence',.1,1],['pose_confidence',.1,1],['zone_hits',1,30],['session_gap',0,120],['action_frames',1,30],['action_duration',0,30]].forEach(function(r){s.controls[r[0]].min=r[1];s.controls[r[0]].max=r[2];});
    ['zone_hits','action_frames'].forEach(function(k){s.controls[k].step='1';});
    control(s,'仅测试记录，不向外部平台推送','test_mode','checkbox');control(s,'已按现场画面完成区域标定','calibrated','checkbox');
    var confirmation=node('div');confirmation.className='uniqueness-confirmation';confirmation.appendChild(s.controls.calibrated.parentNode);s.panel.insertBefore(confirmation,s.parametersHeading);
    var note=node('p','更换摄像机后，先保存基础配置并重新打开页面，再重新标定。下方按钮仅保存区域与检测参数。');note.className='uniqueness-hint';s.panel.appendChild(note);
    var actions=node('div');actions.className='uniqueness-actions uniqueness-save';s.save=button('保存区域与检测参数',function(){save(s);});s.save.className='uniqueness-primary';s.save.disabled=true;actions.appendChild(s.save);actions.appendChild(button('重新载入',function(){reload(s);}));s.panel.appendChild(actions);
    var top=anchor.closest('.algorithm-config-top')||anchor;
    top.parentNode.insertBefore(s.panel,top.nextSibling);vm.$el.classList.add('uniqueness-config-page');
    s.nav=node('nav');s.nav.className='uniqueness-navigation';s.nav.setAttribute('aria-label','配置分区导航');
    [['基础信息','.algorithm-basic-panel'],['模型配置','.algorithm-model-settings'],['区域标定',s.heading],['检测参数',s.parametersHeading],['通用参数','.algorithm-drawing-scroll']].forEach(function(item){
      var target=typeof item[1]==='string'?vm.$el.querySelector(item[1]):item[1];if(target)s.nav.appendChild(button(item[0],function(){if(root.AiMonitorConfigSections)root.AiMonitorConfigSections.reveal(target);target.scrollIntoView({behavior:'smooth',block:'start'});}));
    });
    top.parentNode.insertBefore(s.nav,top);reload(s);
  }
  function visit(vm){attach(vm);(vm.$children||[]).forEach(visit);}
  function boot(n){var el=document.getElementById('app');app=el&&el.__vue__;if(!app||!app.$router||!app.$http||!app.$options._base){if(n<300)root.setTimeout(function(){boot(n+1);},100);return;}
    var style=node('style',STYLE);document.head.appendChild(style);
    app.$options._base.mixin({mounted:function(){attach(this);},updated:function(){attach(this);},beforeDestroy:function(){cleanup(this);}});app.$router.afterEach(function(){app.$nextTick(function(){visit(app);if(!catalogReady)loadKinds(0);});});loadKinds(0);app.$nextTick(function(){visit(app);});
  }
  root.AiMonitorUniquenessEditor={supported:supported,taskId:taskId,endpoint:endpoint,saveBeforeBatch:saveBeforeBatch};boot(0);
})(window);
