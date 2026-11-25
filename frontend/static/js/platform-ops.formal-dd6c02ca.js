(function (root) {
  'use strict';
  function boot(attempt) {
    var element = root.document.getElementById('app'), app = element && element.__vue__;
    if (!app || !app.$router || !root.AiMonitorDataPush || !root.AiMonitorPlatformUpgrade) { if (attempt < 300) root.setTimeout(function () { boot(attempt + 1); }, 100); return; }
    var router = app.$router;
    if (!router.__platformOpsInstalled) {
      var routes = router.options.routes, main = routes.filter(function (route) { return route.name === 'Home'; })[0];
      if (!main) return;
      var children = (main.children || []).slice();
      [{path: 'data-push', name: 'platform_data_push', component: root.AiMonitorDataPush, title: '数据推送'}, {path: 'platform-upgrade', name: 'platform_upgrade', component: root.AiMonitorPlatformUpgrade, title: '平台升级'}].forEach(function (item) {
        if (!children.some(function (route) { return route.name === item.name; })) children.push({path: item.path, name: item.name, component: item.component, meta: {title: item.title, requireAuth: true, keepAlive: false}});
      });
      var next = routes.map(function (route) { return route === main ? Object.assign({}, route, {children: children}) : route; });
      router.matcher = new router.constructor({routes: next, mode: router.mode, base: router.options.base}).matcher;
      router.options.routes = next; router.__platformOpsInstalled = true;
      if (['/data-push','/platform-upgrade'].indexOf(router.currentRoute.path) >= 0) router.replace(router.currentRoute.fullPath).catch(function () {});
    }
    if (root.AiMonitorStorageManagement && root.AiMonitorAlarmDirectory && !root.AiMonitorStorageManagement.__directoryInstalled) {
      var original = root.AiMonitorStorageManagement.render;
      var withDirectory = function (h) { var node = original.call(this, h); if (node && Array.isArray(node.children)) node.children.splice(1, 0, h(root.AiMonitorAlarmDirectory, {key: 'alarm-directory-control', props: {canEdit: this.canEdit}})); return node; };
      root.AiMonitorStorageManagement.render = withDirectory;
      // Vue may cache a constructor or mount this page before the extension runs.
      Object.keys(root.AiMonitorStorageManagement._Ctor || {}).forEach(function (key) { var cached = root.AiMonitorStorageManagement._Ctor[key]; if (cached && cached.options) cached.options.render = withDirectory; });
      (function refresh(vm) { if (!vm) return; if (vm.$options && vm.$options.name === 'StorageManagement') { vm.$options.render = withDirectory; vm.$forceUpdate(); } (vm.$children || []).forEach(refresh); })(app);
      root.AiMonitorStorageManagement.__directoryInstalled = true;
    }
    // Navigation is supplied by the platform menu and role APIs.
  }
  boot(0);
})(window);
