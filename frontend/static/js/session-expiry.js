/* One authentication boundary for concurrent Axios and preview-fetch requests. */
(function (root, factory) {
  'use strict';
  var api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.AiMonitorSession = api;
})(typeof window !== 'undefined' ? window : globalThis, function (root) {
  'use strict';
  var installed = null;
  var PUBLIC = /\/(?:user_view\/(?:login|loginfree)|captcha|uuid_qr|activate\/(?:activate_verify|activate_show))\/?$/;
  function cancelled() {
    var error = new Error('登录已失效，请重新登录');
    error.name = 'SessionExpiredError'; error.code = 'ERR_CANCELED';
    error.__CANCEL__ = true; error.authExpired = true;
    return error;
  }
  function publicUrl(url) { return PUBLIC.test(String(url || '').split(/[?#]/)[0]); }
  function failedAuth(response, body) {
    return response && (response.status === 401 || body && Number(body.code) === 401 ||
      response.status === 422 && body && /token|jwt|signature|segments|令牌|登录/i.test(String(body.msg || body.message || '')));
  }
  function install(client, options) {
    if (installed) return installed;
    options = options || {};
    var store = options.store, router = options.router, axios = options.axios;
    var expired = false, rejectedToken = '', generation = 0, pending = new Set();
    function token() {
      return store && store.state.token || root.localStorage && root.localStorage.getItem('token') || '';
    }
    function clearIdentity() {
      try { if (store) store.commit('delToken'); } catch (_) {}
      ['token', 'userId', 'user_role_id', 'userRoleName'].forEach(function (key) {
        try { root.localStorage.removeItem(key); } catch (_) {}
      });
      if (store && store.state) {
        // A fresh page starts with state.token === ''. Its cached getToken getter
        // may contain the localStorage token, so assigning '' again cannot dirty
        // that getter. Replacing the state invalidates it and preserves other state.
        var state = Object.assign({}, store.state, {
          token: '', userId: '', user_role_id: '', userRoleName: '', menuData: [],
        });
        if (store.replaceState) store.replaceState(state);
        else Object.assign(store.state, state);
      }
      var headers = client.defaults && client.defaults.headers;
      if (headers) { delete headers.Authorization; if (headers.common) delete headers.common.Authorization; }
    }
    function synchronize() {
      if (expired && token() && token() !== rejectedToken) { expired = false; generation += 1; }
    }
    function begin(url) {
      synchronize();
      var isPublic = publicUrl(url);
      if (expired && !isPublic) throw cancelled();
      return { generation: generation, token: token(), public: isPublic };
    }
    function stale(ticket) {
      return ticket && !ticket.public &&
        (ticket.generation !== generation || ticket.token !== token() || expired);
    }
    function fallback() {
      if (!root.location || /#\/login(?:[/?]|$)/.test(root.location.hash || '')) return;
      root.location.replace(root.location.pathname + root.location.search + '#/login');
    }
    function expire(ticket) {
      if (expired || stale(ticket)) return;
      rejectedToken = token(); expired = true; generation += 1;
      clearIdentity();
      pending.forEach(function (source) { source.cancel('AUTH_SESSION_EXPIRED'); });
      pending.clear();
      if (root.dispatchEvent && root.CustomEvent) root.dispatchEvent(new root.CustomEvent('platform:session-expired'));
      var moving;
      try { moving = router.replace('/login'); }
      catch (_) { fallback(); }
      if (moving && moving.catch) moving.catch(function (error) {
        if (!error || error.name !== 'NavigationDuplicated') fallback();
      });
      try { if (options.notify) options.notify('登录已过期，请重新登录'); } catch (_) {}
    }
    function check(response, body, ticket, url) {
      if (ticket && ticket.public || publicUrl(url)) return;
      if (stale(ticket)) throw cancelled();
      if (failedAuth(response, body)) { expire(ticket); throw cancelled(); }
    }
    function release(config) {
      if (config && config._platformCancel) pending.delete(config._platformCancel);
    }
    client.interceptors.request.use(function (config) {
      var ticket = begin(config.url);
      config._platformAuth = ticket;
      config.headers = config.headers || {};
      if (!ticket.public && ticket.token) config.headers.Authorization = 'Bearer ' + ticket.token;
      else delete config.headers.Authorization;
      if (!ticket.public && !config.cancelToken && axios && axios.CancelToken) {
        var source = axios.CancelToken.source();
        config.cancelToken = source.token; config._platformCancel = source;
        pending.add(source);
      }
      return config;
    }, function (error) { return Promise.reject(error); });
    client.interceptors.response.use(function (response) {
      release(response.config);
      check(response, response.data, response.config && response.config._platformAuth, response.config && response.config.url);
      return response;
    }, function (error) {
      var config = error && (error.config || error.response && error.response.config);
      release(config);
      check(error && error.response, error && error.response && error.response.data,
        config && config._platformAuth, config && config.url);
      return Promise.reject(error);
    });
    installed = { begin: begin, check: check };
    return installed;
  }
  return {
    install: install,
    begin: function (url) { return installed ? installed.begin(url) : null; },
    check: function (response, body, ticket, url) { if (installed) return installed.check(response, body, ticket, url); },
  };
});
