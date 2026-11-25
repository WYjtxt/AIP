/* AiMonitor resource defaults: camera affinity, then available chip 0. */
(function(root){
  'use strict';
  function id(value){return Array.isArray(value)?value[value.length-1]:value;}
  function number(value){return value==null||value===''||!Number.isFinite(Number(value))?Infinity:Number(value);}
  function editing(vm){
    var q=vm.$route&&vm.$route.query||{};
    return !!(q.conf_id!=null||q.id!=null||q.map!=null||vm.conf_id||vm.form&&vm.form.id||vm.algorithmIsEditing&&vm.algorithmIsEditing());
  }
  function context(vm){
    var f=vm.form||{},camera=typeof vm.previewEquipmentId==='function'?vm.previewEquipmentId():f.equipment_name||f.Equipment_id;
    return {equipment_id:id(camera)||'',algorithm_id:id(f.Algorithm_library_id)||''};
  }
  function key(vm){var c=context(vm);return String(c.equipment_id)+':'+String(c.algorithm_id);}
  function stoppedDraft(vm){
    var status=String(vm.form&&vm.form.status);
    return editing(vm)&&(status==='2'||status==='停止');
  }
  function flattened(vm){
    var rows=[];(vm.computeOptions||[]).forEach(function(host){(host.children||[]).forEach(function(card){rows.push(card);});});return rows;
  }
  function choose(cards){
    return cards.filter(function(card){return card.disabled===false;}).slice().sort(function(a,b){
      var x=a.admission||{},y=b.admission||{};
      return Number(x.disabled!==false)-Number(y.disabled!==false)||Number(String(a.devId)!=='0')-Number(String(b.devId)!=='0')||number(x.selection_score)-number(y.selection_score)||number(a.id)-number(b.id);
    })[0]||null;
  }
  function note(vm,text){
    var page=vm.$el,box=page&&page.querySelector&&page.querySelector('.algorithm-model-settings');if(!box)return;
    var el=box.querySelector('.ai-resource-default-note');
    if(!text){if(el)el.remove();return;}
    if(!el){el=document.createElement('p');el.className='ai-resource-default-note';el.style.cssText='grid-column:1/-1;color:#65758a;font-size:13px;line-height:1.7;margin:8px 0';el.setAttribute('role','status');box.appendChild(el);}
    if(el.textContent!==text)el.textContent=text;
  }
  function apply(vm){
    var state=vm._aiResourceDefaults,data=state&&state.data;
    if(!data||state.key!==key(vm)||!vm.form)return;
    var lookup={};(data.resources||[]).forEach(function(r){lookup[String(r.id)]=r;});
    // Resource load can prevent a start, but must not prevent saving a stopped
    // configuration. Only server-verified missing/incompatible cards stay disabled.
    var draft=stoppedDraft(vm),changed=false;
    var nextHosts=(vm.computeOptions||[]).map(function(host){var hostChanged=false;var children=(host.children||[]).map(function(card){
      var meta=lookup[String(card.id)],status=(vm.algorithmAdmissionCards||{})[String(card.id)]||card.admission||{};
      var reason=meta&&meta.disabled?meta.reason:status.disabled?status.reason:'';
      var disabled=!meta||meta.disabled||!draft&&status.disabled!==false,devId=meta?meta.dev_id:card.devId;
      var label=(card.baseLabel||card.label)+(reason?' · '+reason+(draft&&meta&&!meta.disabled?'（配置可保存，启动时检查）':''):'');
      if(card.disabled===disabled&&card.devId===devId&&card.admission===status&&card.label===label)return card;
      hostChanged=true;return Object.assign({},card,{disabled:disabled,devId:devId,admission:status,label:label});
    });if(!hostChanged)return host;changed=true;return Object.assign({},host,{children:children});});
    if(changed)vm.computeOptions=nextHosts;
    if(editing(vm)||vm._algorithmResourceEdited){note(vm,'');return;}
    if(data.reason){vm.$set(vm.form,'resource_id',0);note(vm,data.reason);return;}
    var cards=flattened(vm),bound=/^camera_/.test(data.source||''),chosen=bound?cards.find(function(card){return String(card.id)===String(data.resource_id)&&!card.disabled;}):choose(cards);
    if(!chosen)return;
    if(String(id(vm.form.resource_id))!==String(chosen.id))vm.$set(vm.form,'resource_id',chosen.id);
    vm._algorithmResourceDefaultPending=false;
    note(vm,bound?'沿用此摄像机已有任务的芯片 '+chosen.devId+'。':'未绑定摄像机优先使用可用芯片 0；当前推荐芯片 '+chosen.devId+'。');
  }
  function refresh(vm,force){
    var state=vm._aiResourceDefaults;if(!state||!vm.$http)return;
    var current=key(vm);
    if(!force&&state.key===current&&(state.loading||state.data)){apply(vm);return;}
    state.key=current;state.data=null;state.loading=true;var seq=++state.seq;
    if(!editing(vm)&&!vm._algorithmResourceEdited)vm.$set(vm.form,'resource_id',0);
    var base=(vm.$url&&vm.$url.url_5000||root.wgParameter&&root.wgParameter.url_5000||'').replace(/\/$/,'');
    return vm.$http.get(base+'/model_view/algorithm_first/resource-default',{params:context(vm),timeout:8000}).then(function(response){
      if(vm._isDestroyed||seq!==state.seq||current!==key(vm))return;
      if(!response.data||Number(response.data.code)!==200)throw new Error('resource_defaults_unavailable');
      state.data=response.data.data;apply(vm);
    }).catch(function(){
      if(seq===state.seq&&!editing(vm)&&!vm._algorithmResourceEdited)note(vm,'默认算力读取失败，请刷新后重试；已有配置与手动选择保持不变。');
    }).finally(function(){if(seq===state.seq)state.loading=false;});
  }
  function install(vm){
    if(vm._aiResourceDefaults||typeof vm.applyAlgorithmResourceDefault!=='function'||!vm.form)return;
    vm._aiResourceDefaults={seq:0,key:null,data:null,loading:false};
    var admission=vm.applyAlgorithmAdmission;
    vm.applyAlgorithmResourceDefault=function(){refresh(vm,false);};
    if(typeof admission==='function')vm.applyAlgorithmAdmission=function(){
      // Retain the existing status refresh while suppressing its old load-score
      // based migration. Explicit selections and saved edits never auto-change.
      var selected=vm._algorithmResourceEdited;vm._algorithmResourceEdited=true;
      try{admission.apply(vm,arguments);}finally{vm._algorithmResourceEdited=selected;}
      refresh(vm,false);
    };
    if(vm.$watch){
      var stop=vm.$watch(function(){return key(vm);},function(){refresh(vm,true);});
      var stopCards=vm.$watch(function(){return String(vm.form&&vm.form.status)+':'+flattened(vm).map(function(c){return c.id;}).join(',');},function(){refresh(vm,false);});
      if(vm.$once)vm.$once('hook:beforeDestroy',function(){stop();stopCards();vm._aiResourceDefaults.seq++;});
    }
    refresh(vm,true);
  }
  function scan(){
    var el=document.getElementById('app'),app=el&&el.__vue__;if(!app)return;
    var seen=[];function visit(vm){if(!vm||seen.indexOf(vm)>=0)return;seen.push(vm);install(vm);(vm.$children||[]).forEach(visit);}visit(app);
  }
  root.AiMonitorResourceDefaults={install:install,refresh:refresh,choose:choose,editing:editing};
  scan();root.setInterval(scan,500);
})(window);
