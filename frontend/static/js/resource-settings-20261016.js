/* Administrator scheduling settings for the existing Vue 2 application. */
(function (root) {
  'use strict';
  var fields = [
    ['cpu_warning', 'CPU 提醒阈值', '%', 0, 100],
    ['cpu_warning_recovery', 'CPU 提醒恢复阈值', '%', 1, 100],
    ['cpu_limit', 'CPU 暂停部署阈值', '%', 0, 100],
    ['cpu_recovery', 'CPU 暂停部署恢复阈值', '%', 1, 100],
    ['card_limit', '单卡暂停部署阈值', '%', 0, 100],
    ['card_recovery', '单卡恢复阈值', '%', 1, 100],
    ['pair_limit', '整机各卡暂停部署阈值', '%', 0, 100],
    ['pair_recovery', '整机各卡恢复阈值', '%', 1, 100],
    ['trigger_seconds', '超限持续时间', '秒', 10, 300],
    ['recovery_seconds', '恢复持续时间', '秒', 10, 600],
    ['reservation_seconds', '部署观察时间', '秒', 5, 120]
  ];
  function apiBase() { return ((root.wgParameter && root.wgParameter.url_5000) || '').replace(/\/$/, ''); }
  function body(response) {
    var data = response && response.data;
    if (!data || Number(data.code) !== 200) throw new Error(data && data.msg || '请求失败，请稍后重试');
    return data.data;
  }
  function errorText(error) { return error && error.response && error.response.data && error.response.data.msg || error && error.message || '请求失败，请稍后重试'; }
  function draft(policy) { var next = {}; fields.forEach(function (field) { next[field[0]] = String(policy[field[0]]); }); return next; }
  function errors(values) {
    var found = [];
    fields.forEach(function (field) {
      var raw = String(values[field[0]] == null ? '' : values[field[0]]);
      if (!/^\d+$/.test(raw) || Number(raw) < field[3] || Number(raw) > field[4]) found.push(field[1] + '须为 ' + field[3] + '–' + field[4] + ' 之间的整数');
    });
    if (found.length) return found;
    [['cpu_warning_recovery', 'cpu_warning', 'CPU 提醒'], ['cpu_recovery', 'cpu_limit', 'CPU 暂停部署'],
     ['card_recovery', 'card_limit', '单卡保护'], ['pair_recovery', 'pair_limit', '整机各卡保护']].forEach(function (pair) {
      if (Number(values[pair[0]]) >= Number(values[pair[1]])) found.push(pair[2] + '的恢复阈值须低于触发阈值');
    });
    if (Number(values.cpu_warning) >= Number(values.cpu_limit)) found.push('CPU 提醒阈值须低于暂停部署阈值');
    return found;
  }
  function button(h, label, click, disabled, primary) {
    return h('button', {class: ['resource-settings-button', primary && 'is-primary'], attrs: {type: 'button', disabled: !!disabled}, on: {click: click}}, label);
  }
  var component = {
    name: 'ResourceAdmissionSettings',
    data: function () { return {settings: null, draft: {}, loading: false, saving: false, error: '', success: '', disposed: false}; },
    computed: {
      validationErrors: function () { return this.settings ? errors(this.draft) : []; },
      canEdit: function () { return !!(this.settings && this.settings.can_edit); }
    },
    created: function () { this.load(); },
    beforeDestroy: function () { this.disposed = true; },
    methods: {
      load: function () {
        if (this.loading || this.saving || this.disposed) return;
        var vm = this; this.loading = true; this.error = ''; this.success = '';
        return this.$http.get(apiBase() + '/resource_view/admission/settings').then(body).then(function (data) {
          if (!vm.disposed) { vm.settings = data; vm.draft = draft(data.policy); }
        }).catch(function (error) { if (!vm.disposed) vm.error = errorText(error); })
          .then(function () { if (!vm.disposed) vm.loading = false; });
      },
      restore: function () { if (this.settings) { this.draft = draft(this.settings.policy); this.error = ''; this.success = ''; } },
      defaults: function () { if (this.settings) { this.draft = draft(this.settings.defaults); this.success = '初始值已填入，保存后生效。'; this.error = ''; } },
      save: function () {
        if (!this.canEdit || this.validationErrors.length || this.saving || this.loading) return;
        var vm = this, values = {}; fields.forEach(function (field) { values[field[0]] = Number(vm.draft[field[0]]); });
        this.saving = true; this.error = ''; this.success = '';
        return this.$http.post(apiBase() + '/resource_view/admission/settings', {policy: values, revision: this.settings.revision})
          .then(body).then(function (data) {
            if (!vm.disposed) { vm.settings = data; vm.draft = draft(data.policy); vm.success = '配置已保存，后续采样与部署校验将自动使用新设置。'; }
          }).catch(function (error) { if (!vm.disposed) vm.error = errorText(error); })
          .then(function () { if (!vm.disposed) vm.saving = false; });
      },
      field: function (h, definition) {
        var vm = this, key = definition[0], id = 'resource-setting-' + key;
        return h('div', {class: 'resource-settings-field', key: key}, [
          h('label', {attrs: {for: id}}, definition[1]),
          h('div', {class: 'resource-settings-input'}, [
            h('input', {attrs: {id: id, type: 'number', min: definition[3], max: definition[4], step: 1, disabled: !this.canEdit || this.saving || this.loading,
              'aria-describedby': 'resource-settings-validation'}, domProps: {value: this.draft[key]},
              on: {input: function (event) { vm.$set(vm.draft, key, event.target.value); vm.success = ''; }}}),
            h('span', definition[2])
          ])
        ]);
      }
    },
    render: function (h) {
      var vm = this, busy = this.loading || this.saving;
      var sections = [h('header', {class: 'resource-settings-header'}, [
        h('div', [h('h2', '算力调度设置'), h('p', '控制新增部署的负载上限，已有任务继续运行。')]),
        button(h, this.loading ? '读取中…' : '重新读取', function () { vm.load(); }, busy)
      ])];
      if (this.error) sections.push(h('div', {class: 'resource-settings-message is-error', attrs: {role: 'alert'}}, this.error));
      if (this.success) sections.push(h('div', {class: 'resource-settings-message is-success', attrs: {role: 'status'}}, this.success));
      if (this.loading && !this.settings) sections.push(h('p', {attrs: {role: 'status'}}, '正在读取当前生效配置…'));
      if (this.settings) {
        sections.push(h('div', {class: 'resource-settings-cards'}, [
          h('section', {class: 'resource-settings-card'}, [h('h3', 'CPU 保护'), h('p', '提醒只影响选卡建议；暂停部署作用于同一主机的所有卡。'),
            h('div', {class: 'resource-settings-grid'}, fields.slice(0, 4).map(function (field) { return vm.field(h, field); }))]),
          h('section', {class: 'resource-settings-card'}, [h('h3', '加速卡保护'), h('p', '单卡超限时改选可用卡；同一主机各卡均超限时暂停新增部署。'),
            h('div', {class: 'resource-settings-grid'}, fields.slice(4, 8).map(function (field) { return vm.field(h, field); })),
            h('small', '整机保护解除：至少一张卡低于对应恢复阈值，并持续满足恢复时间。')]),
          h('section', {class: 'resource-settings-card resource-settings-timing'}, [h('h3', '时间策略'),
            h('div', {class: 'resource-settings-grid'}, fields.slice(8).map(function (field) { return vm.field(h, field); })),
            h('p', '每 ' + this.settings.policy.sample_seconds + ' 秒采样。部署观察期间暂停接收该主机的下一次新增部署，防止并发超放。')])
        ]));
        sections.push(h('div', {class: 'resource-settings-validation', attrs: {id: 'resource-settings-validation', role: this.validationErrors.length ? 'alert' : 'note'}},
          this.validationErrors.length ? this.validationErrors.map(function (error) { return h('p', error); }) : '保存后自动使用新规则。已触发保护的资源，仍需满足新的恢复条件后解除。'));
        var stamp = this.settings.updated_at ? new Date(this.settings.updated_at).toLocaleString() : '沿用初始配置';
        sections.push(h('footer', {class: 'resource-settings-footer'}, [
          h('span', {class: 'resource-settings-stamp'}, '最近保存：' + stamp + (this.settings.updated_by ? ' · ' + this.settings.updated_by : '')),
          h('div', [button(h, '填入初始值', this.defaults, !this.canEdit || busy), button(h, '撤销修改', this.restore, busy),
            button(h, this.saving ? '保存中…' : '保存配置', this.save, !this.canEdit || busy || !!this.validationErrors.length, true)])
        ]));
      }
      return h('div', {class: 'resource-settings'}, sections);
    }
  };
  root.AiMonitorResourceSettings = {component: component, fields: fields, validate: errors};
  function installRoute(router) {
    if (router.__resourceSettingsInstalled) return;
    var routes = router.options.routes, home = routes.filter(function (route) { return route.name === 'Home'; })[0];
    if (!home) return;
    var children = (home.children || []).slice();
    if (!children.some(function (route) { return route.name === 'resource_admission_settings'; })) children.push({
      path: 'resource-settings', name: 'resource_admission_settings', component: component,
      meta: {title: '算力调度设置', requireAuth: true, keepAlive: false}
    });
    var nextRoutes = routes.map(function (route) { return route === home ? Object.assign({}, route, {children: children}) : route; });
    var replacement = new router.constructor({routes: nextRoutes, mode: router.mode, base: router.options.base});
    router.matcher = replacement.matcher; router.options.routes = nextRoutes; router.__resourceSettingsInstalled = true;
    if (router.currentRoute.path === '/resource-settings') router.replace(router.currentRoute.fullPath).catch(function () {});
  }
  function findHome(vm) {
    if (!vm) return null;
    if (vm.$options && vm.$options.name === 'Home') return vm;
    var children = vm.$children || [];
    for (var i = 0; i < children.length; i += 1) { var home = findHome(children[i]); if (home) return home; }
    return null;
  }
  function attachMenu(app) {
    var home = findHome(app);
    if (!home || home.__resourceSettingsMenuRequested) return;
    home.__resourceSettingsMenuRequested = true;
    app.$http.get(apiBase() + '/resource_view/admission/settings').then(body).then(function (data) {
      if (!data.can_edit || home._isDestroyed) return;
      function addMenu() {
        var menus = home.menuData || [], parent = menus.filter(function (menu) { return menu.menu_name === '系统管理'; })[0];
        if (!parent || (parent.children || []).some(function (item) { return item.menu_link === 'resource-settings'; })) return;
        home.$set(parent, 'children', (parent.children || []).concat([{menu_name: '算力调度设置', menu_link: 'resource-settings', menu_icon: 'el-icon-cpu', menu_id: 'resource_admission_settings'}]));
        if (home.$route.path === '/resource-settings' && typeof home.handleMenuName === 'function') home.handleMenuName();
      }
      addMenu(); var unwatch = home.$watch('menuData', addMenu, {deep: true});
      home.$once('hook:beforeDestroy', unwatch);
    }).catch(function () {});
  }
  function boot(attempt) {
    var element = root.document.getElementById('app'), app = element && element.__vue__;
    if (!app || !app.$router || !app.$http) { if (attempt < 100) root.setTimeout(function () { boot(attempt + 1); }, 100); return; }
    installRoute(app.$router); app.$nextTick(function () { attachMenu(app); });
    app.$router.afterEach(function () { app.$nextTick(function () { attachMenu(app); }); });
  }
  boot(0);
})(window);
