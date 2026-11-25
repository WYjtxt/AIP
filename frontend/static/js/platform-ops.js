(function (root) {
  'use strict';
  function home(vm) { if (!vm) return null; if (vm.$options && vm.$options.name === 'Home') return vm; var children = vm.$children || []; for (var i = 0; i < children.length; i++) { var found = home(children[i]); if (found) return found; } return null; }
  function boot(attempt) {
    var element = root.document.getElementById('app'), app = element && element.__vue__;
    if (!app || !app.$router || !app.$http || !root.AiMonitorDataPush || !root.AiMonitorPlatformUpgrade) { if (attempt < 300) root.setTimeout(function () { boot(attempt + 1); }, 100); return; }
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
      root.AiMonitorStorageManagement.render = function (h) { var node = original.call(this, h); if (node && Array.isArray(node.children)) node.children.splice(1, 0, h(root.AiMonitorAlarmDirectory, {key: 'alarm-directory-control', props: {canEdit: this.canEdit}})); return node; };
      root.AiMonitorStorageManagement.__directoryInstalled = true;
    }
    function attach() {
      var page = home(app); if (!page || page.__platformOpsMenuPending || page.__platformOpsMenuInstalled) return;
      page.__platformOpsMenuPending = true;
      var base = ((root.wgParameter && root.wgParameter.url_5000) || '').replace(/\/$/, '');
      app.$http.get(base + '/platform_ops/health').then(function (response) {
        if (!response.data || Number(response.data.code) !== 200 || page._isDestroyed) return;
        function add() { var parent = (page.menuData || []).filter(function (menu) { return menu.menu_name === '系统管理'; })[0]; if (!parent) return;
          var items = (parent.children || []).slice(), changed = false;
          [{menu_name: '数据推送', menu_link: 'data-push', menu_icon: 'el-icon-upload', menu_id: 'platform_data_push'}, {menu_name: '平台升级', menu_link: 'platform-upgrade', menu_icon: 'el-icon-top', menu_id: 'platform_upgrade'}].forEach(function (item) { if (!items.some(function (existing) { return String(existing.menu_link || '').replace(/^\/+|\/+$/g, '') === item.menu_link; })) { items.push(item); changed = true; } });
          if (changed) { page.$set(parent, 'children', items); if (page.handleMenuName) page.handleMenuName(); }
        }
        var unwatch = page.$watch('menuData', add, {deep: true}); page.$once('hook:beforeDestroy', unwatch); page.__platformOpsMenuInstalled = true; add();
      }).catch(function () {}).finally(function () { page.__platformOpsMenuPending = false; });
    }
    attach(); router.afterEach(function () { app.$nextTick(attach); });
  }
  boot(0);
})(window);
