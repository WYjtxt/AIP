/* 人员尾随配置页路由（挂到平台 Home 子路由，页面本体为 /tailgate/ 独立页） */
(function (root) {
  'use strict';
  var PATH = '/tailgate-config', NAME = 'tailgate_config';

  var component = {
    name: 'TailgateConfig',
    render: function (h) {
      return h('iframe', {
        attrs: {
          src: '/tailgate/',
          title: '人员尾随配置',
          style: 'width:100%;height:calc(100vh - 110px);border:0;display:block;background:#f4f7fb'
        }
      });
    }
  };

  function installRoute(router) {
    if (router.__tailgateInstalled) return;
    var routes = router.options.routes;
    var home = routes.filter(function (r) { return r.name === 'Home'; })[0];
    if (!home) return;
    var children = (home.children || []).slice();
    if (!children.some(function (r) { return r.name === NAME || r.path === PATH.slice(1); })) {
      children.push({
        path: PATH.slice(1), name: NAME, component: component,
        meta: { title: '尾随配置', requireAuth: true, keepAlive: false }
      });
    }
    var next = routes.map(function (r) {
      return r === home ? Object.assign({}, r, { children: children }) : r;
    });
    router.matcher = new router.constructor({ routes: next, mode: router.mode, base: router.options.base }).matcher;
    router.options.routes = next;
    router.__tailgateInstalled = true;
  }

  function boot(attempt) {
    var el = root.document.getElementById('app');
    var app = el && el.__vue__;
    if (!app || !app.$router) {
      if (attempt < 300) root.setTimeout(function () { boot(attempt + 1); }, 100);
      return;
    }
    app.$router.onReady(function () { installRoute(app.$router); });
  }

  root.AiMonitorTailgateConfig = { component: component, installRoute: installRoute, path: PATH };
  boot(0);
})(window);
