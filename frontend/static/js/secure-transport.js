/* media-session-recovery-v1 */
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
  /* media-recovery-state */
  var mediaRevision = 0, lastRecoveryAt = -Infinity;
  var imageRecovery = typeof WeakMap === 'function' ? new WeakMap() : null;
  var nativeSetAttribute = root.Element && root.Element.prototype.setAttribute;
  /* /media-recovery-state */
  var pendingAttributes = typeof WeakMap === 'function' ? new WeakMap() : null;
  var HOSTS = (root.location && root.location.hostname) ? [root.location.hostname.toLowerCase()] : [];
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
  /* alarm-url-routing-v1 */
  function alarmMediaRoute(path, gateway, configured) {
    var decoded = decodedPath(path);
    if (!decoded || /[\\\x00-\x1f\x7f]/.test(decoded) || /%[0-9a-f]{2}/i.test(decoded) ||
        /%(?:2f|5c)/i.test(path) || /(?:^|\/)\.\.(?:\/|$)/.test(decoded)) return null;
    var storage = gateway ? '/media/alarm-storage/' : '/alarm-storage/';
    if (path.indexOf(storage) === 0 &&
        /^[a-f0-9]{20}\/.+\.(?:mp4|avi|mov|mkv|jpe?g|png|webp|gif)$/i.test(decoded.slice(storage.length))) {
      return '/alarm-storage/' + path.slice(storage.length);
    }
    var roots = gateway ? ['/media/alarms/'] : ['/data/AIGO/outputs/', '/data/AIGO/python/bingxing_model/results/'];
    if (!gateway && configured) roots.unshift(ALARM_PREFIX);
    if (mediaPath(path)) {
      for (var i = 0; i < roots.length; i++) {
        if (roots[i] && path.indexOf(roots[i]) === 0) {
          return '/alarms/' + path.slice(roots[i].length);
        }
      }
    }
    return null;
  }
  /* /alarm-url-routing-v1 */
  function normalize(value) {
    if (!root.location || root.location.protocol !== 'https:' || typeof value !== 'string') return value;
    var input;
    try { input = new URL(value, root.location.href || root.location.origin + '/'); }
    catch (_) { return value; }
    if (!/^(?:https?|wss?):$/.test(input.protocol) || input.username || input.password) return value;
    var host = input.hostname.toLowerCase(), http = /^https?:$/.test(input.protocol);
    var sameHost = host === root.location.hostname.toLowerCase();
    var knownHost = HOSTS.indexOf(host) !== -1;
    var loopback = host === '127.0.0.1' || host === 'localhost' || host === '[::1]';
    var gatewayAlarm = http && sameHost && /^\/media\/(?:alarms|alarm-storage)\//.test(input.pathname);
    var legacyAlarm = http && input.port === '9002' && (sameHost || knownHost || loopback);
    // Existing count alarms may use the web port with the physical output prefix.
    var siteAlarm = http && sameHost &&
      (input.port === (root.location.port || '') || input.port === '8888') &&
      alarmMediaRoute(input.pathname, false, true) !== null;
    var prefix, mappedPath = input.pathname;
    if (gatewayAlarm || legacyAlarm || siteAlarm) {
      mappedPath = alarmMediaRoute(input.pathname, gatewayAlarm, !loopback || sameHost);
      if (!mappedPath) return value;
      prefix = '/media';
    }
    else if (input.origin === root.location.origin || !knownHost) return value;
    else if (input.port === '5000' && http) prefix = '/api';
    else if (MEDIA_PORTS.indexOf(input.port) !== -1 && mediaPath(input.pathname)) prefix = '/media';
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
  function ensureMediaSession(force) {
    if (!root.location || root.location.protocol !== 'https:') return Promise.resolve(true);
    var current = token();
    if (!originalFetch || !current || current === rejectedToken) return Promise.resolve(false);
    if (sessionRequest && sessionRequest.token === current) return sessionRequest.promise;
    if (!force && current === mediaToken && Date.now() < mediaUntil) return Promise.resolve(true);
    var auth = root.AiMonitorSession, ticket = null;
    try { if (auth && auth.begin) ticket = auth.begin('/api/security/media-session'); }
    catch (_) { return Promise.resolve(false); }
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
        // Only a failed JWT-protected session request may expire the API login.
        // A media GET returning 401 never invalidates the business credentials.
        if (auth && auth.check && (response.status === 401 || response.status === 422)) {
          return response.clone().json().catch(function () { return {}; }).then(function (body) {
            if (token() !== current || sessionRequest !== active) return false;
            try { auth.check(response, body, ticket, '/api/security/media-session'); } catch (_) {}
            return false;
          });
        }
        return false;
      }
      mediaToken = current; mediaUntil = Date.now() + 110000; rejectedToken = ''; mediaRevision += 1;
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
    mediaToken = ''; mediaUntil = 0; sessionRequest = null; mediaRevision += 1;
    if (!originalFetch || !root.location || root.location.protocol !== 'https:') return;
    originalFetch.call(root, '/api/security/media-session', {
      method: 'DELETE', credentials: 'same-origin', cache: 'no-store',
    }).catch(function () { /* The short-lived server cookie also expires automatically. */ });
  }
  function recoverMediaSession(expectedToken, revision) {
    if (!expectedToken || token() !== expectedToken || expectedToken === rejectedToken) return Promise.resolve(false);
    if (sessionRequest && sessionRequest.token === expectedToken) return sessionRequest.promise;
    // Concurrent failures from the same old cookie share one renewal, even
    // when their HEAD responses arrive after that renewal has already finished.
    if (revision !== mediaRevision && mediaToken === expectedToken && Date.now() < mediaUntil) return Promise.resolve(true);
    if (Date.now() - lastRecoveryAt < 5000) return Promise.resolve(false);
    lastRecoveryAt = Date.now();
    return ensureMediaSession(true);
  }
  function imageUrl(element) {
    try { return new URL(element.getAttribute('src') || '', root.location.href).href; }
    catch (_) { return ''; }
  }
  function recoverImage(element, renewedOnResume) {
    if (!imageRecovery || !originalFetch || !nativeSetAttribute || !element || element.tagName !== 'IMG') return;
    var url = imageUrl(element), current = token(), state = imageRecovery.get(element);
    if (!current || !mediaRequest(url)) return;
    if (!state || state.url !== url || state.token !== current) {
      state = { url: url, token: current, attempted: false };
      imageRecovery.set(element, state);
    }
    if (state.attempted) return;
    state.attempted = true;
    var revision = mediaRevision;
    var controller = root.AbortController ? new root.AbortController() : null;
    var timeout = controller && root.setTimeout ? root.setTimeout(function () { controller.abort(); }, 10000) : null;
    function sameImage() {
      return token() === current && imageRecovery.get(element) === state && imageUrl(element) === url;
    }
    // An image error alone does not distinguish an expired cookie from a 404,
    // corrupt file or network failure. Probe status before renewing credentials.
    originalFetch.call(root, url, { method: 'HEAD', credentials: 'same-origin', cache: 'no-store',
      signal: controller ? controller.signal : undefined }).then(function (response) {
      if (!sameImage()) return false;
      if (response.status === 401) return recoverMediaSession(current, revision);
      return Boolean(response.ok && (renewedOnResume ||
        revision !== mediaRevision && mediaToken === current && Date.now() < mediaUntil));
    }).then(function (ok) {
      if (ok && sameImage()) nativeSetAttribute.call(element, 'src', url);
    }).catch(function () {}).then(function () {
      if (timeout !== null && root.clearTimeout) root.clearTimeout(timeout);
    });
  }
  function refreshMediaOnResume() {
    if (root.document && root.document.hidden || !token()) return;
    ensureMediaSession(true).then(function (ok) {
      if (!ok || !root.document || !root.document.querySelectorAll) return;
      Array.prototype.forEach.call(root.document.querySelectorAll('img'), function (image) {
        if (image.complete && image.naturalWidth === 0) recoverImage(image, true);
      });
    });
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
          var current = token(), revision = mediaRevision;
          var method = String(options && options.method || input && input.method || 'GET').toUpperCase();
          return fetch.call(context, input, options).then(function (response) {
            if (response.status !== 401 || (method !== 'GET' && method !== 'HEAD') ||
                options && options.signal && options.signal.aborted || token() !== current) return response;
            return recoverMediaSession(current, revision).then(function (renewed) {
              if (!renewed || token() !== current) return response;
              // GET/HEAD only: never replay a body, POST, or a business mutation.
              return fetch.call(context, input, options);
            });
          });
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
    /* media-recovery-events */
    if (root.document && root.document.addEventListener) {
      root.document.addEventListener('error', function (event) { recoverImage(event.target); }, true);
      root.document.addEventListener('load', function (event) {
        var element = event.target;
        if (imageRecovery && element && element.tagName === 'IMG' && element.naturalWidth > 0) imageRecovery.delete(element);
      }, true);
      root.document.addEventListener('visibilitychange', refreshMediaOnResume);
    }
    if (root.addEventListener) {
      root.addEventListener('focus', refreshMediaOnResume);
      root.addEventListener('storage', function (event) {
        if (event.key !== 'token' && event.key !== null) return;
        mediaToken = ''; mediaUntil = 0; mediaRevision += 1;
        if (token()) ensureMediaSession();
        else clearMediaSession();
      });
    }
    /* /media-recovery-events */
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
