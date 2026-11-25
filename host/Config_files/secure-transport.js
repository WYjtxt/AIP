/* Same-origin transport for the existing compiled platform distribution. */
(function (root, factory) {
  'use strict';
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.AiMonitorTransport = api;
  if (root && root.document) api.install();
})(typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';
  var installed = false;
  var mediaToken = '', mediaUntil = 0, rejectedToken = '', sessionRequest = null;
  var originalFetch = root.fetch;
  var pendingAttributes = typeof WeakMap === 'function' ? new WeakMap() : null;
  var HOSTS = ['172.16.129.236', '172.16.129.236', '127.0.0.1', 'localhost'];
  var MEDIA_PORTS = ['8085', '8443'];
  var ALARM_PREFIX = '/data/AIGO/outputs/';

  function decodedPath(path) {
    try { return decodeURIComponent(path); } catch (_) { return ''; }
  }
  function mediaPath(path) {
    var decoded = decodedPath(path);
    if (!decoded || decoded.indexOf('\\') !== -1 || /%[0-9a-f]{2}/i.test(decoded)) return false;
    // Only playback signalling is exposed; ZLK administration stays server-side.
    if (/^\/index\/api(?:\/|$)/i.test(decoded)) return decoded === '/index/api/webrtc';
    if (/(?:^|\/)\.\.(?:\/|$)/.test(decoded)) return false;
    return decoded === '/' || /\.(?:mp4|flv|ts|m3u8|m4s|aac|mpd|jpe?g|png|webp|gif)$/i.test(decoded);
  }
  function normalize(value) {
    if (!root.location || root.location.protocol !== 'https:' || typeof value !== 'string') return value;
    var input;
    try { input = new URL(value, root.location.href || root.location.origin + '/'); }
    catch (_) { return value; }
    if (!/^(?:https?|wss?):$/.test(input.protocol) || input.username || input.password ||
        HOSTS.indexOf(input.hostname.toLowerCase()) === -1) return value;
    var prefix, mappedPath = input.pathname;
    if (input.port === '5000' && /^https?:$/.test(input.protocol)) prefix = '/api';
    else if (MEDIA_PORTS.indexOf(input.port) !== -1 && mediaPath(input.pathname)) prefix = '/media';
    else if (input.port === '9002' && /^https?:$/.test(input.protocol) &&
        input.pathname.indexOf(ALARM_PREFIX) === 0 && mediaPath(input.pathname)) {
      prefix = '/media/alarms';
      mappedPath = '/' + input.pathname.slice(ALARM_PREFIX.length);
    }
    else return value;
    // Historical playback URLs must never carry the ZLK management secret.
    if (prefix.indexOf('/media') === 0) {
      Array.from(input.searchParams.keys()).forEach(function (key) {
        if (/^(?:secret|api_secret|zlk_secret)$/i.test(key)) input.searchParams.delete(key);
      });
    }
    var scheme = /^wss?:$/.test(input.protocol) ? 'wss:' : 'https:';
    return scheme + '//' + root.location.host + prefix + mappedPath + input.search + input.hash;
  }
  function token() {
    try { return root.localStorage && root.localStorage.getItem('token') || ''; } catch (_) { return ''; }
  }
  function mediaRequest(value) {
    try {
      var url = new URL(value, root.location.href || root.location.origin + '/');
      return url.origin === root.location.origin && /^\/media\//.test(url.pathname);
    } catch (_) { return false; }
  }
  function ensureMediaSession() {
    if (!root.location || root.location.protocol !== 'https:') return Promise.resolve(true);
    var current = token();
    if (!originalFetch || !current || current === rejectedToken) return Promise.resolve(false);
    if (current === mediaToken && Date.now() < mediaUntil) return Promise.resolve(true);
    if (sessionRequest && sessionRequest.token === current) return sessionRequest.promise;
    var active = { token: current, promise: null, controller: root.AbortController ? new root.AbortController() : null };
    if (sessionRequest && sessionRequest.controller) sessionRequest.controller.abort();
    var timeout = active.controller && root.setTimeout ? root.setTimeout(function () { active.controller.abort(); }, 10000) : null;
    active.promise = originalFetch.call(root, '/api/security/media-session', {
      method: 'POST', credentials: 'same-origin', cache: 'no-store',
      headers: { Authorization: 'Bearer ' + current },
      signal: active.controller ? active.controller.signal : undefined,
    }).then(function (response) {
      if (token() !== current || sessionRequest !== active) return false;
      if (!response.ok) {
        if (response.status === 401 || response.status === 403 || response.status === 422) rejectedToken = current;
        mediaToken = ''; mediaUntil = 0;
        return false;
      }
      mediaToken = current; mediaUntil = Date.now() + 110000; rejectedToken = '';
      return true;
    }).catch(function () { return false; }).then(function (result) {
      if (timeout !== null && root.clearTimeout) root.clearTimeout(timeout);
      if (sessionRequest === active) sessionRequest = null;
      return result;
    });
    sessionRequest = active;
    return active.promise;
  }
  function clearMediaSession() {
    if (sessionRequest && sessionRequest.controller) sessionRequest.controller.abort();
    mediaToken = ''; mediaUntil = 0; sessionRequest = null;
    if (!originalFetch || !root.location || root.location.protocol !== 'https:') return;
    originalFetch.call(root, '/api/security/media-session', {
      method: 'DELETE', credentials: 'same-origin', cache: 'no-store',
    }).catch(function () { /* The short-lived server cookie also expires automatically. */ });
  }
  function assignAttribute(element, name, value, setter) {
    var generations;
    if (pendingAttributes) {
      generations = pendingAttributes.get(element) || {};
      generations[name] = (generations[name] || 0) + 1;
      pendingAttributes.set(element, generations);
    }
    var generation = generations && generations[name];
    if (mediaRequest(value) && token() && !(token() === mediaToken && Date.now() < mediaUntil)) {
      ensureMediaSession().then(function (ok) {
        if (ok && (!generations || generations[name] === generation)) setter(value);
      });
      return;
    }
    setter(value);
  }
  function install() {
    if (installed || !root.location || root.location.protocol !== 'https:') return;
    installed = true;
    var parameters = root.wgParameter;
    if (parameters && parameters.url_5000) parameters.url_5000 = normalize(parameters.url_5000).replace(/\/$/, '');
    if (parameters && parameters.url_8080) parameters.url_8080 = normalize(parameters.url_8080).replace(/\/$/, '');
    if (root.XMLHttpRequest && root.XMLHttpRequest.prototype.open) {
      var open = root.XMLHttpRequest.prototype.open;
      root.XMLHttpRequest.prototype.open = function () {
        var args = Array.prototype.slice.call(arguments);
        args[1] = normalize(args[1]);
        return open.apply(this, args);
      };
    }
    if (root.fetch) {
      var fetch = root.fetch;
      root.fetch = function (input, options) {
        if (typeof input === 'string') input = normalize(input);
        else if (root.URL && input instanceof root.URL) input = normalize(input.href);
        else if (root.Request && input instanceof root.Request) {
          var mapped = normalize(input.url);
          if (mapped !== input.url) input = new root.Request(mapped, input);
        }
        var context = this, url = typeof input === 'string' ? input : input && input.url;
        if (mediaRequest(url)) return ensureMediaSession().then(function (ok) {
          if (!ok) throw new Error('媒体访问需要有效登录，请刷新或重新登录');
          return fetch.call(context, input, options);
        });
        return fetch.call(context, input, options);
      };
    }
    if (root.WebSocket) {
      var NativeWebSocket = root.WebSocket;
      var SecureWebSocket = function (url, protocols) {
        return arguments.length > 1 ? new NativeWebSocket(normalize(url), protocols) : new NativeWebSocket(normalize(url));
      };
      SecureWebSocket.prototype = NativeWebSocket.prototype;
      ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED'].forEach(function (name) {
        Object.defineProperty(SecureWebSocket, name, { value: NativeWebSocket[name], enumerable: true });
      });
      root.WebSocket = SecureWebSocket;
    }
    if (root.Element && root.Element.prototype.setAttribute) {
      var setAttribute = root.Element.prototype.setAttribute;
      root.Element.prototype.setAttribute = function (name, value) {
        if (/^(?:src|poster)$/i.test(name)) {
          var element = this;
          assignAttribute(element, name.toLowerCase(), normalize(value), function (mapped) { setAttribute.call(element, name, mapped); });
          return;
        }
        return setAttribute.call(this, name, value);
      };
    }
    [['HTMLImageElement', 'src'], ['HTMLMediaElement', 'src'], ['HTMLVideoElement', 'poster'],
      ['HTMLSourceElement', 'src']].forEach(function (entry) {
      var constructor = root[entry[0]];
      if (!constructor) return;
      var descriptor = Object.getOwnPropertyDescriptor(constructor.prototype, entry[1]);
      if (!descriptor || !descriptor.set || !descriptor.configurable) return;
      var setter = descriptor.set;
      Object.defineProperty(constructor.prototype, entry[1], Object.assign({}, descriptor, {
        set: function (value) {
          var element = this;
          assignAttribute(element, entry[1], normalize(value), function (mapped) { setter.call(element, mapped); });
        },
      }));
    });
    if (root.addEventListener) root.addEventListener('platform:session-expired', function () {
      rejectedToken = token() || mediaToken || rejectedToken;
      clearMediaSession();
    });
    if (root.setInterval) root.setInterval(function () {
      if (!token()) { if (mediaToken || sessionRequest) clearMediaSession(); return; }
      ensureMediaSession();
    }, 120000);
    if (token()) ensureMediaSession(); else clearMediaSession();
  }
  return { normalize: normalize, install: install, ensureMediaSession: ensureMediaSession,
    clearMediaSession: clearMediaSession };
});
