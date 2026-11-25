/* Drop unsupported audio only when falling back to a single video-only MSE track. */
(function (root) {
  'use strict';
  var LIMIT = 8 * 1024 * 1024;
  function u32(bytes, offset) { return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(offset); }
  function kind(bytes, offset) { return String.fromCharCode.apply(null, bytes.subarray(offset + 4, offset + 8)); }
  function join(parts) {
    var out = new Uint8Array(parts.reduce(function (n, p) { return n + p.length; }, 0)), offset = 0;
    parts.forEach(function (p) { out.set(p, offset); offset += p.length; }); return out;
  }
  function boxes(bytes, start, end) {
    var result = [];
    while (start < end) {
      if (start + 8 > end) throw new Error('Truncated MP4 header');
      var size = u32(bytes, start);
      if (size < 8 || start + size > end) throw new Error('Invalid MP4 size');
      result.push({ start: start, end: start + size, kind: kind(bytes, start) }); start += size;
    }
    return result;
  }
  function repack(original, parts) {
    var out = join([original.subarray(0, 8)].concat(parts));
    new DataView(out.buffer).setUint32(0, out.length); return out;
  }
  function videoInitialization(moov, id) {
    var found = false;
    var parts = boxes(moov, 8, moov.length).map(function (child) {
      var data = moov.subarray(child.start, child.end);
      if (child.kind === 'trak') {
        var tkhd = boxes(data, 8, data.length).find(function (b) { return b.kind === 'tkhd'; });
        if (!tkhd) throw new Error('Missing track ID');
        if (u32(data, tkhd.start + (data[tkhd.start + 8] === 1 ? 28 : 20)) !== id) return null;
        found = true; return data;
      }
      if (child.kind === 'mvex') {
        return repack(data, boxes(data, 8, data.length).filter(function (b) {
          return b.kind !== 'trex' || u32(data, b.start + 12) === id;
        }).map(function (b) { return data.subarray(b.start, b.end); }));
      }
      return data;
    }).filter(Boolean);
    if (!found) throw new Error('Video track missing');
    return repack(moov, parts);
  }
  function fragmentTrack(moof) {
    var trafs = boxes(moof, 8, moof.length).filter(function (b) { return b.kind === 'traf'; });
    if (trafs.length !== 1) throw new Error('Mixed-track fragment requires remuxing');
    var tfhd = boxes(moof, trafs[0].start + 8, trafs[0].end).find(function (b) { return b.kind === 'tfhd'; });
    if (!tfhd || (u32(moof, tfhd.start + 8) & 1)) throw new Error('Absolute fragment offset requires remuxing');
    return u32(moof, tfhd.start + 12);
  }
  root.AiMonitorFmp4VideoFilter = {
    create: function (videoId, onData, onError) {
      var pending = new Uint8Array(0), stopped = false, expectingMedia = false, keepMedia = false, dropped = 0;
      function destroy() { stopped = true; pending = new Uint8Array(0); }
      function emit(data) { onData(data.buffer.slice(data.byteOffset, data.byteOffset + data.byteLength)); }
      return {
        push: function (data) {
          if (stopped || !data.byteLength) return;
          try {
            if (pending.length + data.byteLength > LIMIT) throw new Error('Input exceeds limit');
            pending = join([pending, new Uint8Array(data)]);
            var pos = 0;
            while (!stopped && pending.length - pos >= 8) {
              var size = u32(pending, pos);
              if (size < 8 || size > LIMIT) throw new Error('Invalid box size');
              if (size > pending.length - pos) break;
              var packet = pending.subarray(pos, pos + size), type = kind(packet, 0); pos += size;
              if (expectingMedia && type !== 'mdat') throw new Error('Missing media box');
              if (type === 'moov') emit(videoInitialization(packet, videoId));
              else if (type === 'moof') {
                keepMedia = fragmentTrack(packet) === videoId; expectingMedia = true;
                if (keepMedia) emit(packet); else dropped++;
              } else if (type === 'mdat') {
                if (!expectingMedia) throw new Error('Media without fragment');
                if (keepMedia) emit(packet); expectingMedia = false;
              } else emit(packet);
            }
            if (!stopped) pending = pending.slice(pos);
          } catch (error) { destroy(); onError('此音频不兼容浏览器，且转发流分段不支持静音回退；请使用 H.264 / AAC 转发流'); }
        },
        destroy: destroy,
        getStats: function () { return { droppedAudioFragments: dropped, pendingBytes: pending.length }; },
      };
    },
  };
})(window);
