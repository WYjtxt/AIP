/* Correct one-frame fMP4 video durations using the next DTS; preserve both tracks. */
(function (root) {
  'use strict';
  var LIMIT = 8 * 1024 * 1024;
  function u32(bytes, offset) { return new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength).getUint32(offset); }
  function type(bytes, offset) { return String.fromCharCode.apply(null, bytes.subarray(offset + 4, offset + 8)); }
  function join(parts) {
    var out = new Uint8Array(parts.reduce(function (n, p) { return n + p.byteLength; }, 0)), offset = 0;
    parts.forEach(function (p) { out.set(p, offset); offset += p.byteLength; }); return out;
  }
  function children(bytes, start) {
    var out = [], end = start + u32(bytes, start), pos = start + 8;
    if (end > bytes.length) throw new Error('MP4 box length');
    while (pos < end) {
      if (pos + 8 > end) throw new Error('MP4 box header');
      var size = u32(bytes, pos);
      if (size < 8 || pos + size > end) throw new Error('MP4 box length');
      out.push({ kind: type(bytes, pos), start: pos, end: pos + size }); pos += size;
    }
    return out;
  }
  function videoTracks(moov) {
    var tracks = {};
    children(moov, 0).filter(function (b) { return b.kind === 'trak'; }).forEach(function (trak) {
      var boxes = children(moov, trak.start), tkhd = boxes.find(function (b) { return b.kind === 'tkhd'; });
      var mdia = boxes.find(function (b) { return b.kind === 'mdia'; });
      if (!tkhd || !mdia) return;
      var media = children(moov, mdia.start), hdlr = media.find(function (b) { return b.kind === 'hdlr'; });
      var mdhd = media.find(function (b) { return b.kind === 'mdhd'; });
      if (!hdlr || !mdhd || String.fromCharCode.apply(null, moov.subarray(hdlr.start + 16, hdlr.start + 20)) !== 'vide') return;
      var id = u32(moov, tkhd.start + (moov[tkhd.start + 8] === 1 ? 28 : 20));
      tracks[id] = u32(moov, mdhd.start + (moov[mdhd.start + 8] === 1 ? 28 : 20));
    });
    return tracks;
  }
  function timing(packet, tracks) {
    var trafs = children(packet, 0).filter(function (b) { return b.kind === 'traf'; });
    // General multi-sample/multi-track fragments pass through unchanged.
    if (trafs.length !== 1) return { passthrough: true };
    var boxes = children(packet, trafs[0].start), tfhd = boxes.find(function (b) { return b.kind === 'tfhd'; });
    var tfdt = boxes.find(function (b) { return b.kind === 'tfdt'; });
    var truns = boxes.filter(function (b) { return b.kind === 'trun'; });
    if (!tfhd) return { passthrough: true };
    var id = u32(packet, tfhd.start + 12), scale = tracks[id], trun = truns[0];
    if (!scale) return null;
    if (!tfdt || truns.length !== 1 || u32(packet, trun.start + 12) !== 1) return { passthrough: true };
    var flags = u32(packet, trun.start + 8) & 0xffffff, pos = trun.start + 16;
    if (flags & 1) pos += 4;
    if (flags & 4) pos += 4;
    if (!(flags & 0x100)) {
      var defaults = u32(packet, tfhd.start + 8) & 0xffffff;
      if (!(defaults & 8)) return { passthrough: true };
      pos = tfhd.start + 16;
      if (defaults & 1) pos += 8;
      if (defaults & 2) pos += 4;
    }
    if (pos + 4 > (flags & 0x100 ? trun.end : tfhd.end)) return { passthrough: true };
    var dts = packet[tfdt.start + 8] === 1
      ? u32(packet, tfdt.start + 12) * 4294967296 + u32(packet, tfdt.start + 16)
      : u32(packet, tfdt.start + 12);
    return { id: id, scale: scale, dts: dts, duration: u32(packet, pos), position: pos, packet: packet };
  }
  root.AiMonitorFmp4Timing = {
    create: function (onData, onError) {
      var parts = [], available = 0, headOffset = 0, stopped = false;
      var tracks = {}, moof = null, held = [], heldBytes = 0, previous = null, corrected = 0;
      function peekSize() {
        var header = new Uint8Array(4), offset = 0;
        for (var i = 0; i < parts.length && offset < 4; i++) {
          var p = parts[i].subarray(i ? 0 : headOffset), count = Math.min(4 - offset, p.length);
          header.set(p.subarray(0, count), offset); offset += count;
        }
        return u32(header, 0);
      }
      function take(size) {
        var out;
        if (parts[0].length - headOffset >= size) out = parts[0].subarray(headOffset, headOffset + size);
        else {
          out = new Uint8Array(size); var copied = 0;
          for (var i = 0; copied < size; i++) {
            var p = parts[i].subarray(i ? 0 : headOffset), count = Math.min(size - copied, p.length);
            out.set(p.subarray(0, count), copied); copied += count;
          }
        }
        available -= size;
        while (size) {
          var count = Math.min(size, parts[0].length - headOffset); headOffset += count; size -= count;
          if (headOffset === parts[0].length) { parts.shift(); headOffset = 0; }
        }
        return out;
      }
      function flush() {
        if (held.length) onData(join(held).buffer);
        held = []; heldBytes = 0; previous = null;
      }
      function fragment(packet) {
        var next = timing(packet, tracks);
        if (next && next.passthrough) {
          flush(); onData(packet.buffer.slice(packet.byteOffset, packet.byteOffset + packet.byteLength)); return;
        }
        if (next) {
          if (previous && previous.id === next.id) {
            var delta = next.dts - previous.dts;
            // Repair ordinary frame cadence only; preserve outages/reordered timestamps.
            if (delta > 0 && delta / previous.scale <= 0.25 && delta !== previous.duration) {
              new DataView(previous.packet.buffer, previous.packet.byteOffset, previous.packet.byteLength)
                .setUint32(previous.position, delta);
              corrected++;
            }
          }
          flush(); previous = next;
        }
        if (previous) { held.push(packet); heldBytes += packet.length; }
        else onData(packet.buffer.slice(packet.byteOffset, packet.byteOffset + packet.byteLength));
      }
      function process(box) {
        var kind = type(box, 0);
        if (kind === 'moof') { if (moof) throw new Error('MP4 fragment without media'); moof = box; return; }
        if (kind === 'mdat' && moof) { var packet = join([moof, box]); moof = null; fragment(packet); return; }
        if (kind === 'moov') { flush(); tracks = videoTracks(box); }
        if (previous) { held.push(box); heldBytes += box.length; }
        else onData(box.buffer.slice(box.byteOffset, box.byteOffset + box.byteLength));
      }
      function destroy() { stopped = true; parts = []; moof = null; held = []; previous = null; available = heldBytes = 0; }
      return {
        push: function (data) {
          if (stopped || !data.byteLength) return;
          parts.push(new Uint8Array(data)); available += data.byteLength;
          try {
            if (available + heldBytes + (moof ? moof.length : 0) > LIMIT) throw new Error('MP4 input exceeds limit');
            while (!stopped && available >= 8) {
              var size = peekSize();
              if (size < 8 || size > LIMIT) throw new Error('MP4 box size');
              if (available < size) break;
              process(take(size));
            }
          } catch (error) { destroy(); onError('转发流的 MP4 分段数据无效，请检查流媒体输出'); }
        },
        destroy: destroy,
        getStats: function () { return { correctedDurations: corrected, pendingBytes: available + heldBytes + (moof ? moof.length : 0) }; },
      };
    },
  };
})(window);
