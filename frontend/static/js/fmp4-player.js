/* Independent WebSocket-fMP4 / MSE player for ZLMediaKit live streams. */
(function (root) {
  'use strict';
  root.AiMonitorFmp4Player = {
    create: function (video, httpUrl, onError) {
      var MediaSource = root.MediaSource || root.WebKitMediaSource;
      var diagnosticOwner = {};
      video._aiMonitorFmp4DiagnosticOwner = diagnosticOwner;
      var capabilities = null;
      var sourceApi = root.MediaSource ? 'MediaSource' : root.WebKitMediaSource ? 'WebKitMediaSource' : null;
      var mode = 'initializing';
      var failureStage = '';
      var exceptionName = '';
      var selectedMime = '';
      function diagnostics() {
        var code = video.error && Number(video.error.code) || null;
        var stage = failureStage || (code ? 'media-error' : mode);
        var hevc = capabilities && capabilities.tracks.some(function (track) { return /^(hvc1|hev1)/i.test(track.codec); });
        var codecFailure = stage === 'capability' && !capabilities.videoOnly.mseSupported
          || ['mse-initialize', 'mse-buffer', 'mse-append', 'native-play'].indexOf(stage) >= 0
          || stage === 'media-error' && (code === 3 || code === 4);
        return { transport: mode, stage: stage,
          exceptionName: exceptionName, mediaErrorCode: code, selectedMime: selectedMime,
          compatibilityFallback: { eligible: !!(hevc && codecFailure && exceptionName !== 'QuotaExceededError' && exceptionName !== 'NotAllowedError'),
            codec: hevc ? 'H265' : null },
          browser: { userAgent: String(root.navigator && root.navigator.userAgent || '').slice(0, 256),
            mediaSource: sourceApi,
            managedMediaSourcePresent: !!root.ManagedMediaSource },
          capabilities: capabilities ? JSON.parse(JSON.stringify(capabilities)) : null };
      }
      function publishDiagnostics() {
        var data = diagnostics();
        // Root can inspect this safe DOM attribute without privileged browser
        // APIs. Never store the playback URL, token, raw descriptions or errors.
        if (video._aiMonitorFmp4DiagnosticOwner === diagnosticOwner && video.setAttribute) {
          video.setAttribute('data-fmp4-diagnostics', JSON.stringify(data));
        }
        return data;
      }
      publishDiagnostics();
      if (!MediaSource || !root.WebSocket || !root.MP4Box) {
        failureStage = !MediaSource ? 'media-source-unavailable' : 'dependencies';
        mode = 'unavailable';
        publishDiagnostics();
        throw new Error(!MediaSource ? '当前页面没有可用的 MSE 播放通道，请检查媒体播放支持'
          : '流媒体播放器未完整加载，请刷新页面后重试');
      }
      var disposed = false;
      var socket = null;
      var source = new MediaSource();
      var buffer = null;
      var parser = root.MP4Box.createFile();
      var offset = 0;
      var queue = [];
      var queuedBytes = 0;
      var videoFilter = null;
      var objectUrl = root.URL.createObjectURL(source);
      var nativePlayback = false;
      var started = false;
      var lastSeek = 0;
      var lastCleanup = 0;
      var targetBuffer = 1.5;
      var stats = { gapSkips: 0, liveSeeks: 0, receivedBytes: 0 };
      var timing = root.AiMonitorFmp4Timing
        ? root.AiMonitorFmp4Timing.create(receive, fail) : null;

      function ranges() {
        // HTMLMediaElement.buffered is the intersection of the audio/video tracks.
        return video.buffered && video.buffered.length ? video.buffered : buffer && buffer.buffered;
      }
      function seek(time, reason) {
        var now = Date.now();
        if (video.seeking || (lastSeek && now - lastSeek < 200)) return;
        lastSeek = now;
        video.currentTime = time;
        stats[reason]++;
      }
      function livePoint(ranges, end) {
        var desired = Math.max(ranges.start(0), end - targetBuffer);
        for (var i = 0; i < ranges.length; i++) {
          if (desired <= ranges.end(i) - 0.02) {
            return Math.max(ranges.start(i) + 0.01, desired);
          }
        }
        return Math.max(ranges.start(ranges.length - 1), end - 0.05);
      }
      function maintain() {
        if (disposed || video._aiMonitorFmp4DiagnosticOwner !== diagnosticOwner ||
            (!nativePlayback && (!buffer || !source || source.readyState !== 'open'))) return;
        var r = ranges();
        if (!r || !r.length) return;
        var start = r.start(0), end = r.end(r.length - 1), current = video.currentTime;
        if (!started) {
          // Build a useful safety margin before starting, including streams with
          // an absolute live timestamp. Do not repeatedly jump to the newest frame.
          if (end - start < targetBuffer) return;
          started = true;
          seek(livePoint(r, end), 'liveSeeks');
        } else if (current < start - 0.05 || end - current > 6) {
          seek(livePoint(r, end), 'liveSeeks');
        } else {
          // Receiving data does not guarantee a continuous decoded timeline.
          // Cross a short hole as soon as its next playable range is available.
          for (var i = 1; i < r.length; i++) {
            var next = r.start(i), previous = r.end(i - 1);
            if (current >= previous - 0.06 && current < next && next - current <= 0.75) {
              seek(next + Math.min(0.02, (r.end(i) - next) / 2), 'gapSkips');
              break;
            }
          }
        }
        if (source && source.setLiveSeekableRange) {
          try { source.setLiveSeekableRange(start, end); } catch (error) { /* optional */ }
        }
      }
      function waitForData() { maintain(); }

      function fail(message, stage, error) {
        if (disposed) return;
        failureStage = stage || 'stream-data';
        exceptionName = error && /^[A-Za-z]+Error$/.test(error.name || '') ? error.name : '';
        var data = publishDiagnostics();
        try { onError(message, data); } finally { destroy(); }
      }
      function drain() {
        if (disposed || !buffer || !source || buffer.updating || source.readyState !== 'open') return;
        maintain();
        if (buffer.buffered.length) {
          var start = buffer.buffered.start(0);
          if (video.currentTime - start > 8 && Date.now() - lastCleanup > 1000) {
            lastCleanup = Date.now();
            try { buffer.remove(start, video.currentTime - 4); return; }
            catch (error) { fail('视频缓冲清理失败，点击重试'); return; }
          }
        }
        if (!queue.length) return;
        var data = queue.shift();
        queuedBytes -= data.byteLength;
        try { buffer.appendBuffer(data); }
        catch (error) { fail(error.name === 'QuotaExceededError'
          ? '视频解码缓冲已满，请减少同时预览路数后重试'
          : '视频数据写入失败，请检查码流封装后重试', 'mse-append', error); }
      }
      function bufferError() { fail('视频数据解析或解码失败，请检查码流与播放环境', 'mse-buffer'); }
      function enqueue(data) {
        if (disposed || nativePlayback) return;
        queue.push(data);
        queuedBytes += data.byteLength;
        if (queuedBytes > 8 * 1024 * 1024) {
          fail('视频接收缓冲过大，请减少预览路数或检查网络');
          return;
        }
        drain();
      }
      function receive(data) {
        if (disposed || nativePlayback) return;
        if (videoFilter) { videoFilter.push(data); return; }
        enqueue(data);
        if (disposed) return;
        if (parser) {
          data.fileStart = offset;
          offset += data.byteLength;
          try { parser.appendBuffer(data); }
          catch (error) { fail('无法读取转发流的 MP4 数据', 'mp4-parser', error); return; }
        }
        drain();
      }
      function mseSupport(mime) {
        if (!mime || typeof MediaSource.isTypeSupported !== 'function') return false;
        try { return !!MediaSource.isTypeSupported(mime); } catch (error) { return false; }
      }
      function nativeSupport(mime) {
        if (!mime || typeof video.canPlayType !== 'function') return '';
        try {
          var answer = video.canPlayType(mime);
          return answer === 'maybe' || answer === 'probably' ? answer : '';
        } catch (error) { return ''; }
      }
      function closeSocket() {
        if (!socket) return;
        socket.onmessage = socket.onerror = socket.onclose = null;
        socket.close();
        socket = null;
      }
      function releaseMse() {
        if (source) source.removeEventListener('sourceopen', openSource);
        if (buffer) {
          buffer.removeEventListener('updateend', drain);
          buffer.removeEventListener('error', bufferError);
          if (source && source.readyState === 'open') {
            try { buffer.abort(); source.removeSourceBuffer(buffer); } catch (error) { /* already closed */ }
          }
          buffer = null;
        }
        source = null;
        if (objectUrl) { root.URL.revokeObjectURL(objectUrl); objectUrl = null; }
      }
      function startNative() {
        // Only the exact complete MIME can authorize this attempt. Never use
        // generic HEVC, substitute hvc1/hev1, or change profile/tier/level bytes.
        if (disposed || video._aiMonitorFmp4DiagnosticOwner !== diagnosticOwner ||
            !capabilities || !capabilities.combined.nativeSupport) return false;
        nativePlayback = true;
        mode = 'native';
        selectedMime = capabilities.combined.mime;
        closeSocket();
        releaseMse();
        parser = null;
        if (timing) { timing.destroy(); timing = null; }
        queue = []; queuedBytes = 0;
        publishDiagnostics();
        video.src = httpUrl;
        if (video.load) video.load();
        try {
          var pending = video.play && video.play();
          if (pending) pending.catch(function (error) {
            if (disposed || error.name === 'AbortError') return;
            fail(error.name === 'NotAllowedError' ? '浏览器阻止自动播放，点击重试'
              : '原生视频播放失败，请检查码流与播放环境', 'native-play', error);
          });
        } catch (error) { fail('原生视频播放启动失败，点击重试', 'native-play', error); }
        return true;
      }
      parser.onError = function () { fail('转发流的 MP4 数据无效，点击重试', 'mp4-parser'); };
      parser.onReady = function (info) {
        if (disposed || video._aiMonitorFmp4DiagnosticOwner !== diagnosticOwner) return;
        var tracks = info && Array.isArray(info.tracks) ? info.tracks : [];
        var codecs = tracks.map(function (track) { return track.codec; });
        if (!codecs.length || codecs.length > 16 || codecs.some(function (codec) {
          return typeof codec !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$/.test(codec);
        })) { fail('转发流未返回有效编码信息，点击重试', 'mp4-metadata'); return; }
        var mime = 'video/mp4; codecs="' + codecs.join(', ') + '"';
        var videos = tracks.filter(function (track) { return track.video || /^(avc[13]|hvc1|hev1|vp09|av01)(\.|$)/i.test(track.codec); });
        if (!videos.length) {
          fail('转发流尚未提供视频轨，请等待关键帧后重试', 'video-track-pending');
          return;
        }
        var videoMime = videos.length === 1 ? 'video/mp4; codecs="' + videos[0].codec + '"' : '';
        capabilities = { combined: { mime: mime, mseSupported: mseSupport(mime), nativeSupport: nativeSupport(mime) },
          videoOnly: { mime: videoMime, mseSupported: mseSupport(videoMime), nativeSupport: nativeSupport(videoMime) },
          tracks: tracks.map(function (track) { return { id: Number(track.id) || null, codec: track.codec,
            kind: track.video ? 'video' : track.audio ? 'audio' : 'other',
            width: track.video && Number(track.video.width) || null,
            height: track.video && Number(track.video.height) || null }; }) };
        publishDiagnostics();
        if (!capabilities.combined.mseSupported) {
          if (root.AiMonitorFmp4VideoFilter && videoMime && capabilities.videoOnly.mseSupported) {
            // Preview is muted. Keep an unsupported audio track from blocking
            // otherwise supported video; leave normal audio/video streams intact.
            videoFilter = root.AiMonitorFmp4VideoFilter.create(videos[0].id, enqueue, fail);
            var pending = queue; queue = []; queuedBytes = 0;
            pending.forEach(function (data) { videoFilter.push(data); });
            if (disposed) return;
            mime = videoMime;
          } else if (startNative()) {
            return;
          } else {
          mode = 'unsupported';
          fail(capabilities.videoOnly.mseSupported
            ? '视频编码可播放，当前音频组合无法初始化；请刷新页面并检查播放器是否完整加载'
            : codecs.some(function (codec) { return /^(hvc1|hev1)/i.test(codec); })
              ? '当前浏览器无法播放此 H.265 码流'
              : '当前浏览器未支持此视频或音频编码组合，请检查转发流', 'capability');
          return;
          }
        }
        try {
          buffer = source.addSourceBuffer(mime);
          buffer.addEventListener('updateend', drain);
          buffer.addEventListener('error', bufferError);
          source.duration = Infinity;
          mode = 'mse';
          selectedMime = mime;
          publishDiagnostics();
          parser = null; // Parse only the initialization segment, never retain live samples.
          drain();
        } catch (error) {
          if (error.name === 'NotSupportedError' && !videoFilter && startNative()) return;
          fail('无法初始化视频播放通道，点击重试', 'mse-initialize', error);
        }
      };
      function openSource() {
        if (disposed) return;
        socket = new root.WebSocket(httpUrl.replace(/^http/i, 'ws'));
        socket.binaryType = 'arraybuffer';
        socket.onmessage = function (event) {
          if (disposed || nativePlayback || !(event.data instanceof ArrayBuffer)) return;
          var data = event.data;
          stats.receivedBytes += data.byteLength;
          if (timing) timing.push(data);
          else receive(data);
        };
        socket.onerror = function () { if (!nativePlayback) fail('无法连接流媒体，请检查 WebSocket 服务和网络', 'websocket'); };
        socket.onclose = function () { if (!disposed && !nativePlayback) fail('视频连接已中断，点击重试', 'websocket'); };
      }
      function destroy() {
        if (disposed) return;
        publishDiagnostics();
        disposed = true;
        if (video.removeEventListener) {
          video.removeEventListener('waiting', waitForData);
          video.removeEventListener('timeupdate', maintain);
          video.removeEventListener('progress', maintain);
        }
        closeSocket();
        releaseMse();
        parser = null;
        if (timing) timing.destroy();
        if (videoFilter) videoFilter.destroy();
        queue = [];
        queuedBytes = 0;
        if (nativePlayback && video._aiMonitorFmp4DiagnosticOwner === diagnosticOwner &&
            (video.getAttribute ? video.getAttribute('src') : video.src) === httpUrl) {
          if (video.pause) video.pause();
          if (video.removeAttribute) video.removeAttribute('src');
          if (video.load) video.load();
        }
      }
      source.addEventListener('sourceopen', openSource, { once: true });
      if (video.addEventListener) {
        video.addEventListener('waiting', waitForData);
        video.addEventListener('timeupdate', maintain);
        video.addEventListener('progress', maintain);
      }
      video.src = objectUrl;
      return { destroy: destroy, getStats: function () {
        return { gapSkips: stats.gapSkips, liveSeeks: stats.liveSeeks,
          receivedBytes: stats.receivedBytes, queuedBytes: queuedBytes, targetBuffer: targetBuffer,
          timing: timing ? timing.getStats() : null,
          videoOnly: !!videoFilter, audioFilter: videoFilter ? videoFilter.getStats() : null,
          diagnostics: publishDiagnostics() };
      } };
    },
  };
})(window);
