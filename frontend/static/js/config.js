let ip = '172.16.129.236';  //浏览器地址

window.wgParameter = {
    url_5000 : window.location.origin + '/api',
    url_7000 : `http://${ip}:7000`,
    url_8080 : `http://${ip}:8080`,
    ip,
    system:`JY`,//这里用于区分极云（JY）、探放水（TFS）、海康安防（HKAF）、uwb（UWB）
    hkaf:{//海康安防平台四个参数（能访问到海康安防平台视频的地址ip、port
        ip: '10.100.11.9',
        port: 4443,
        appKey: '',//这两参数需要再平台中获取
        secret:'',
    }
}

/* native-model-upload-layout-v1 */
;(function(){var id="native-model-upload-layout",style=document.getElementById(id);if(!style){style=document.createElement("style");style.id=id;(document.head||document.documentElement).appendChild(style);}style.textContent="\n.jia_algoBox[data-v-60109a28] .el-form-item.jia_formItem2 + .el-form-item{margin-left:50%;width:50%;box-sizing:border-box}\n.jia_algoBox[data-v-60109a28] .el-form-item.jia_formItem2 + .el-form-item .el-textarea{width:100%!important}\n";})();

/* native-recorder-form-v2 */
;(function(root){
  if(root.__platformRecorderFormV2)return;
  root.__platformRecorderFormV2=true;
  function addRecorder(){
    var view=this;
    this.addUpdateTitle="新增硬盘录像机";
    this.addUpdateForm={vcr_name:"",vcr_type:"",vcr_way:"",Mine_id:"",port:"",ip:"",username:"",password:""};
    this.addUpdateOpen=true;
    this.$nextTick(function(){var form=view.$refs.addUpdateForm;if(form)form.clearValidate();});
  }
  function loadRecorderDictionary(){
    var view=this;
    return this.$http.get(this.$url.url_5000+"/model_view/type_select",{params:{mine_id:"1"}}).then(function(response){
      if(response.data.code===200){
        view.access_type=response.data.vcr_way;
        view.sub_type=response.data.equipment_type;
        view.producer_type=response.data.manufacturer_type;
        view.Mine_id_type=response.data.mine_list;
      }
    }).catch(function(error){console.log(error);});
  }
  function repair(view,existing){
    var options=view.$options,methods=options.methods;
    if(options._scopeId!=="data-v-e147e160"||!methods)return;
    var add=String(methods.handleClickAdd||""),reset=String(methods.resetForm||"");
    if(!/this\.addUpdateForm\s*=\s*\{\}/.test(add)||!/resetForm/.test(add)||!/resetFields/.test(reset))return;
    var patched=Object.assign({},methods,{handleClickAdd:addRecorder});
    if(/this\.addUpdateForm\.Mine_id\s*=\s*this\.Mine_id_type\[0\]\.id/.test(String(methods.getDictData||"")))
      patched.getDictData=loadRecorderDictionary;
    options.methods=patched;
    if(existing){
      view.handleClickAdd=patched.handleClickAdd.bind(view);
      if(patched.getDictData!==methods.getDictData)view.getDictData=patched.getDictData.bind(view);
    }
  }
  function install(){
    var element=root.document.getElementById("app"),application=element&&element.__vue__;
    if(!application)return;
    var Base=application.constructor;
    while(Base.super)Base=Base.super;
    Base.mixin({beforeCreate:function(){repair(this,false);}});
    function visit(view){repair(view,true);(view.$children||[]).forEach(visit);}
    visit(application);
  }
  if(root.document.readyState==="loading")root.document.addEventListener("DOMContentLoaded",install,{once:true});
  else install();
})(window);

/* native-playback-recovery-v2 */
;(function(root){
  if(root.__platformPlaybackRecoveryV2)return;
  root.__platformPlaybackRecoveryV2=true;
  function frames(video){
    if(video.getVideoPlaybackQuality)return video.getVideoPlaybackQuality().totalVideoFrames;
    return typeof video.webkitDecodedFrameCount==="number"?video.webkitDecodedFrameCount:null;
  }
  function now(){return root.performance&&root.performance.now?root.performance.now():Date.now();}
  function attach(view,index,generation){
    var player=view._previewPlayers&&view._previewPlayers.get(index);
    if(!player||!player.video||!Array.isArray(player.events)||player._platformPlaybackRecoveryV2)return;
    var video=player.video,state={timer:null,lastTime:Number(video.currentTime)||0,lastFrames:frames(video),lastProgress:now(),stableSince:null};
    player._platformPlaybackRecoveryV2=state;
    function current(){return !view._previewClosed&&index<view.layout&&view._previewGenerations[index]===generation&&view._previewPlayers.get(index)===player;}
    state.clear=function(){if(state.timer!==null)root.clearTimeout(state.timer);state.timer=null;};
    // The original playing handler clears the interruption deadline. Run it
    // only after measured frame/time progress, never from a transient event.
    var playing=player.events.filter(function(event){return event[0]==="playing";});
    playing.forEach(function(event){video.removeEventListener(event[0],event[1]);});
    player.events=player.events.filter(function(event){return event[0]!=="playing";});
    function waiting(){state.stableSince=null;}
    video.addEventListener("waiting",waiting);player.events.push(["waiting",waiting]);
    function sample(){
      state.timer=null;
      if(!current())return;
      var stamp=now(),count=frames(video),time=Number(video.currentTime)||0;
      if(root.document.hidden||video.paused||video.ended){
        state.lastProgress=stamp;state.stableSince=null;
        if(root.document.hidden){root.clearTimeout(player.timeout);player.timeout=null;}
      }else{
        var progressed=!video.seeking&&time>state.lastTime&&
          (typeof count!=="number"||typeof state.lastFrames!=="number"||count>state.lastFrames);
        if(progressed){
          state.lastProgress=stamp;
          if(state.stableSince===null)state.stableSince=stamp;
          playing.forEach(function(event){event[1]();});
          if(stamp-state.stableSince>=10000)view.slots[index].connectionRetries=0;
        }else if(stamp-state.lastProgress>=3000)state.stableSince=null;
        if(stamp-state.lastProgress>=15000){
          var stats=player.transport&&player.transport.getStats?player.transport.getStats():{};
          view.handlePlaybackFailure(index,generation,"视频画面停止更新，点击重试",{
            stage:"connection-timeout",reason:"video-not-advancing",videoFrames:count,
            currentTime:time,receivedBytes:Number(stats.receivedBytes)||0
          });
          return;
        }
      }
      state.lastTime=time;state.lastFrames=count;
      state.timer=root.setTimeout(sample,1000);
    }
    state.timer=root.setTimeout(sample,1000);
  }
  function repair(view,existing){
    var options=view.$options,methods=options.methods;
    if(!methods||options._platformPlaybackRecoveryV2)return;
    if(!["connectSlot","retryConnection","releasePlayer","handlePlaybackFailure"].every(function(name){return typeof methods[name]==="function";})||
       String(methods.connectSlot).indexOf("AiMonitorFmp4Player")===-1)return;
    options._platformPlaybackRecoveryV2=true;
    var connect=methods.connectSlot,release=methods.releasePlayer,failure=methods.handlePlaybackFailure;
    var patched=Object.assign({},methods);
    patched.connectSlot=function(index,device,generation){
      var instance=this;
      return Promise.resolve(connect.apply(this,arguments)).then(function(result){
        if(instance._previewGenerations[index]===generation)attach(instance,index,generation);
        return result;
      });
    };
    patched.releasePlayer=function(index){
      var player=this._previewPlayers&&this._previewPlayers.get(index);
      if(player&&player._platformPlaybackRecoveryV2)player._platformPlaybackRecoveryV2.clear();
      return release.apply(this,arguments);
    };
    patched.handlePlaybackFailure=function(index,generation,message,diagnostics,codec){
      if(diagnostics&&diagnostics.stage==="websocket"&&this._previewGenerations[index]===generation){
        var player=this._previewPlayers&&this._previewPlayers.get(index),video=player&&player.video;
        var stats=player&&player.transport&&player.transport.getStats?player.transport.getStats():{};
        var received=Number(stats.receivedBytes)||0,count=video?frames(video):null;
        diagnostics=Object.assign({},diagnostics,{receivedBytes:received,state:this.slots[index].state,
          videoFrames:count,hadFrames:typeof count==="number"?count>0:!!(video&&video.readyState>=2&&video.currentTime>0)});
        if(received>0)message="视频传输中断，点击重试";
      }
      return failure.call(this,index,generation,message,diagnostics,codec);
    };
    options.methods=patched;
    if(existing){
      ["connectSlot","releasePlayer","handlePlaybackFailure"].forEach(function(name){view[name]=patched[name].bind(view);});
      if(view._previewPlayers)view._previewPlayers.forEach(function(_player,index){attach(view,index,view._previewGenerations[index]);});
    }
  }
  function install(){
    var element=root.document.getElementById("app"),application=element&&element.__vue__;
    if(!application)return;
    var Base=application.constructor;
    while(Base.super)Base=Base.super;
    Base.mixin({beforeCreate:function(){repair(this,false);}});
    function visit(view){repair(view,true);(view.$children||[]).forEach(visit);}
    visit(application);
  }
  if(root.document.readyState==="loading")root.document.addEventListener("DOMContentLoaded",install,{once:true});
  else install();
})(window);
