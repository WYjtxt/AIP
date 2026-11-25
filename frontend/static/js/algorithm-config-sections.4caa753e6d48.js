/* AiMonitor configuration folds: keep Vue fields mounted and preserve drafts. */
(function(root){
  'use strict';
  var groups=[],nextId=0,pending=false,observer;
  var STYLE=`
  #app .home .ai-config-section-toggle{display:flex!important;align-items:center;justify-content:space-between;gap:16px;width:100%;padding:7px 0!important;margin:0!important;border:0!important;border-radius:4px;background:transparent!important;color:#30445f!important;font:inherit;font-size:15px!important;font-weight:600;line-height:24px;text-align:left;cursor:pointer;box-shadow:none!important}
  #app .home .ai-config-section-toggle:focus-visible{outline:2px solid #2864ee;outline-offset:4px}
  #app .home .ai-config-section-toggle span:last-child{font-size:13px;font-weight:400;color:#2864ee;white-space:nowrap}
  #app .home [data-ai-fold-section][data-ai-fold-collapsed="true"] > :not([data-ai-fold-heading]):not([data-ai-fold-bridge]):not([data-ai-fold-section]){display:none!important}
  #app .home [data-ai-fold-section][data-ai-fold-collapsed="true"] [data-ai-fold-bridge]{display:block!important;height:auto!important;min-height:0!important;margin:0!important;padding:0!important;border:0!important;background:transparent!important}
  #app .home [data-ai-fold-section][data-ai-fold-collapsed="true"] [data-ai-fold-bridge] > :not([data-ai-fold-heading]):not([data-ai-fold-bridge]):not([data-ai-fold-section]){display:none!important}
  #app .home [data-ai-fold-section] [data-ai-fold-section]{margin-top:8px!important}
  #app .home [data-ai-fold-section][data-ai-fold-collapsed="true"]{gap:0!important;row-gap:0!important;min-height:0!important}
  #app .home .algorithm-drawing-scroll > [data-ai-fold-section]{width:100%!important;max-width:none!important;grid-template-columns:minmax(0,1fr)!important;justify-self:stretch}
  #app .home .algorithm-drawing-scroll > [data-ai-fold-section] > [data-ai-fold-heading]{display:block!important;grid-column:1 / -1;width:100%!important}
  #app .home .uniqueness-config-page .algorithm-drawing-scroll:before{display:none!important}
  #app .home .uniqueness-fields[data-ai-fold-collapsed="true"]{margin-top:0!important;margin-bottom:0!important}
  #app .home .uniqueness-confirmation{max-width:640px;margin:12px auto}
  #app .home .uniqueness-confirmation label{display:flex;align-items:center;gap:10px;font-size:13px;line-height:1.7}
  #app .home .uniqueness-confirmation input[type=checkbox]{order:-1;accent-color:#2864ee;width:16px;height:16px;margin:0}
  #app .home [data-ai-fold-section] .algorithm-panel-title[data-ai-fold-heading]{margin-bottom:0!important}
  `;
  function setOpen(group,open){
    if(!group || !group.scope.isConnected)return;
    var collapsed=open?'false':'true';
    if(group.scope.getAttribute('data-ai-fold-collapsed')!==collapsed)group.scope.setAttribute('data-ai-fold-collapsed',collapsed);
    group.button.setAttribute('aria-expanded',String(!!open));
    var action=open?'收起':'展开';if(group.action.textContent!==action)group.action.textContent=action;
  }
  function reveal(target,scroll){
    if(!target)return;
    groups.forEach(function(g){if(g.scope.contains(target)||g.header===target||g.header.contains(target))setOpen(g,true);});
    // An inner section's heading may live outside its body but inside a folded parent.
    groups.forEach(function(g){if(g.scope.contains(target))setOpen(g,true);});
    if(scroll && target.scrollIntoView)target.scrollIntoView({behavior:'smooth',block:'center'});
  }
  function fold(scope,label,existingHeading){
    if(!scope||scope.dataset.aiFoldSection)return;
    var header=existingHeading||Array.prototype.find.call(scope.children,function(el){return el.classList.contains('algorithm-panel-title');});
    var createdHeader=!header,originalHeaderNodes=header?Array.from(header.childNodes):[],originalId=scope.id;
    if(!header){header=document.createElement('div');scope.insertBefore(header,scope.firstChild);}
    header.setAttribute('data-ai-fold-heading','');
    var button=document.createElement('button');button.type='button';button.className='ai-config-section-toggle';
    button.setAttribute('aria-label',label+'展开或收起');
    var title=document.createElement('span'),action=document.createElement('span');title.textContent=label;button.appendChild(title);button.appendChild(action);
    header.textContent='';header.appendChild(button);
    var id='ai-config-section-'+(++nextId);scope.dataset.aiFoldSection=label;scope.setAttribute('data-ai-fold-id',id);
    if(!scope.id)scope.id=id;button.setAttribute('aria-controls',scope.id);
    var group={scope:scope,header:header,button:button,action:action,createdHeader:createdHeader,originalHeaderNodes:originalHeaderNodes,originalId:originalId};groups.push(group);
    button.addEventListener('click',function(){setOpen(group,button.getAttribute('aria-expanded')!=='true');});setOpen(group,false);
  }
  function scan(){
    pending=false;groups=groups.filter(function(g){return g.scope.isConnected;});
    document.querySelectorAll('.algorithm-config-page,.algorithm-config-model').forEach(function(page){
      // The specialized panel is loaded asynchronously. Remove a generic fold
      // created before that panel arrived, so there is only one parameter group.
      if(page.classList.contains('uniqueness-config-page'))groups=groups.filter(function(g){
        if(!page.contains(g.scope)||!g.scope.classList.contains('algorithm-template-parameters'))return true;
        if(g.createdHeader)g.header.remove();
        else{g.header.textContent='';g.originalHeaderNodes.forEach(function(node){g.header.appendChild(node);});g.header.removeAttribute('data-ai-fold-heading');}
        ['data-ai-fold-section','data-ai-fold-collapsed','data-ai-fold-id'].forEach(function(name){g.scope.removeAttribute(name);});
        if(!g.originalId)g.scope.removeAttribute('id');
        return false;
      });
      page.querySelectorAll('.algorithm-basic-panel').forEach(function(el){fold(el,'基础信息');});
      page.querySelectorAll('.algorithm-model-settings').forEach(function(el){fold(el,'模型配置');});
      if(!page.classList.contains('uniqueness-config-page'))page.querySelectorAll('.algorithm-template-parameters').forEach(function(el){fold(el,'检测参数');});
      page.querySelectorAll('.algorithm-drawing-scroll').forEach(function(el){
        var body=el.children[1];if(body)fold(body,'通用运行参数');
      });
      page.querySelectorAll('.uniqueness-panel').forEach(function(el){
        var body=el.querySelector('.uniqueness-fields'),heading=el.querySelector('h4');
        if(body&&heading)fold(body,'检测参数',heading);
      });
      page.querySelectorAll('.el-form-item.is-error').forEach(function(el){reveal(el,false);});
    });
    // Preserve the original Vue hierarchy. A nested parameter group keeps its
    // own heading and can open independently while its parent remains folded.
    document.querySelectorAll('[data-ai-fold-bridge]').forEach(function(el){el.removeAttribute('data-ai-fold-bridge');});
    groups.forEach(function(inner){groups.forEach(function(outer){
      if(inner===outer||!outer.scope.contains(inner.scope))return;
      var branch=inner.scope.parentElement;
      while(branch&&branch!==outer.scope){if(!branch.hasAttribute('data-ai-fold-section'))branch.setAttribute('data-ai-fold-bridge','');branch=branch.parentElement;}
    });});
  }
  function schedule(){if(!pending){pending=true;root.setTimeout(scan,0);}}
  function boot(){
    var app=document.getElementById('app');if(!app){root.setTimeout(boot,100);return;}
    var style=document.createElement('style');style.textContent=STYLE;document.head.appendChild(style);
    app.addEventListener('invalid',function(e){reveal(e.target,true);},true);
    app.addEventListener('focusin',function(e){if(!e.target.closest('.ai-config-section-toggle'))reveal(e.target,false);},true);
    observer=new MutationObserver(function(records){
      if(records.some(function(r){return r.type==='childList'||r.attributeName==='class';}))schedule();
    });observer.observe(app,{subtree:true,childList:true,attributes:true,attributeFilter:['class']});scan();
  }
  root.AiMonitorConfigSections={reveal:reveal,refresh:schedule};boot();
})(window);
