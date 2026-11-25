"""Use real video progress for preview recovery and bounded reconnects."""
from pathlib import Path


PLAYBACK_RECOVERY_MARKER = '/* native-playback-recovery-v2 */'


def playback_recovery_script():
    return PLAYBACK_RECOVERY_MARKER + r'''
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
'''


def update_config_source(source, script):
    """Upgrade the former appended script while retaining surrounding site code."""
    marker = script.splitlines()[0]
    if marker in source:
        return source
    previous = '/* native-playback-recovery-v1 */'
    start = source.find(previous)
    if start >= 0:
        end = source.index('})(window);', start) + len('})(window);')
        return source[:start] + script + source[end:]
    return source + '\n' + script


def append_to_config(root):
    config = Path(root) / 'Config_files/config.js'
    source = config.read_text(encoding='utf-8')
    updated = update_config_source(source, playback_recovery_script())
    if updated == source:
        return False
    config.write_text(updated, encoding='utf-8')
    return True
