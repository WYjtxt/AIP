/* Administrator scheduling settings for the existing Vue 2 application. */
(function (root) {
  'use strict';
  var fields = [
    ['cpu_warning', 'CPU 提醒阈值', '%', 0, 100],
    ['cpu_warning_recovery', 'CPU 提醒恢复阈值', '%', 1, 100],
    ['cpu_limit', 'CPU 暂停部署阈值', '%', 0, 100],
    ['cpu_recovery', 'CPU 恢复部署阈值', '%', 1, 100],
    ['card_limit', '芯片利用率暂停阈值', '%', 0, 100],
    ['card_recovery', '芯片利用率恢复阈值', '%', 1, 100],
    ['memory_limit', '芯片内存暂停阈值', '%', 1, 100],
    ['memory_recovery', '芯片内存恢复阈值', '%', 1, 100],
    ['cpu_budget_limit', '新增部署 CPU 预算上限', '%', 1, 100],
    ['cpu_task_reserve', '每个任务的 CPU 预留', '百分点', 1, 100],
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
     ['card_recovery', 'card_limit', '计算芯片保护'], ['memory_recovery', 'memory_limit', '芯片内存保护']].forEach(function (pair) {
      if (Number(values[pair[0]]) >= Number(values[pair[1]])) found.push(pair[2] + '的恢复阈值须低于触发阈值');
    });
    if (Number(values.cpu_warning) >= Number(values.cpu_limit)) found.push('CPU 提醒阈值须低于暂停部署阈值');
    if (Number(values.cpu_task_reserve) > Number(values.cpu_budget_limit) || Number(values.cpu_budget_limit) > Number(values.cpu_limit)) found.push('单任务 CPU 预留不得高于预算上限，预算上限不得高于 CPU 暂停阈值');
    return found;
  }
  function button(h, label, click, disabled, primary) {
    return h('button', {class: ['resource-settings-button', primary && 'is-primary'], attrs: {type: 'button', disabled: !!disabled}, on: {click: click}}, label);
  }
  var component = {
    name: 'ResourceAdmissionSettings',
    data: function () { return {openGroups: {"01": true, "02": false, "03": false, "04": false}, settings: null, draft: {}, loading: false, saving: false, error: '', success: '', disposed: false}; },
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
      function note(summary, text) {
        return h('details', {class: 'resource-settings-details'}, [h('summary', summary), h('p', text)]);
      }
      function group(number, title, description, definitions, extra, className) {
        var open = vm.openGroups[number], id = 'scheduling-group-' + number;
        var v = vm.draft;
        var summaries = {
          '01': '提醒 ' + v.cpu_warning + '% · 暂停 ' + v.cpu_limit + '% · 恢复 ' + v.cpu_recovery + '%',
          '02': '利用率上限 ' + v.card_limit + '% · 内存上限 ' + v.memory_limit + '%',
          '03': '预算上限 ' + v.cpu_budget_limit + '% · 每任务预留 ' + v.cpu_task_reserve + ' 个百分点',
          '04': '超限 ' + v.trigger_seconds + ' 秒 · 恢复 ' + v.recovery_seconds + ' 秒 · 配置观察 ' + v.reservation_seconds + ' 秒'
        };
        var changed = definitions.some(function (field) { return String(vm.draft[field[0]]) !== String(vm.settings.policy[field[0]]); });
        return h('section', {key: number, class: ['resource-settings-card', 'config-fold-card', className || '']}, [
          h('button', {class: 'config-fold-heading', attrs: {type: 'button', 'aria-expanded': String(open), 'aria-controls': id},
            on: {click: function () { vm.$set(vm.openGroups, number, !vm.openGroups[number]); }}}, [
            h('span', {class: 'resource-settings-number', attrs: {'aria-hidden': 'true'}}, number),
            h('span', {class: 'config-fold-caption'}, [h('span', {class: 'config-fold-title'}, title),
              h('span', {class: 'config-fold-summary'}, summaries[number]), changed ? h('span', {class: 'config-fold-dirty'}, '未保存修改') : null]),
            h('span', {class: 'config-fold-action'}, [open ? '收起' : '展开', h('span', {attrs: {'aria-hidden': 'true'}}, open ? ' ▴' : ' ▾')])
          ]),
          h('div', {class: 'config-fold-body', attrs: {id: id, hidden: !open}}, [h('p', description),
            h('div', {class: 'resource-settings-grid'}, definitions.map(function (field) { return vm.field(h, field); })), extra || null])
        ]);
      }
      var sections = [h('header', {class: 'resource-settings-header'}, [
        h('div', [h('h2', '调度策略'), h('p', '设置新增任务的资源上限，已有任务继续运行。')]),
        button(h, this.loading ? '读取中…' : '重新读取', function () { vm.load(); }, busy)
      ])];
      if (this.error) sections.push(h('div', {class: 'resource-settings-message is-error', attrs: {role: 'alert'}}, this.error));
      if (this.success) sections.push(h('div', {class: 'resource-settings-message is-success', attrs: {role: 'status'}}, this.success));
      if (this.loading && !this.settings) sections.push(h('p', {attrs: {role: 'status'}}, '正在读取当前生效配置…'));
      if (this.settings) {
        sections.push(h('div', {class: 'config-fold-toolbar'}, [
          button(h, '全部展开', function () { Object.keys(vm.openGroups).forEach(function (key) { vm.$set(vm.openGroups, key, true); }); }, false),
          button(h, '全部收起', function () { Object.keys(vm.openGroups).forEach(function (key) { vm.$set(vm.openGroups, key, false); }); }, false)
        ]));
        sections.push(h('div', {class: 'resource-settings-cards'}, [
          group('01', '主机 CPU 保护', '整台主机统一保护，不按卡数或芯片数分摊。', fields.slice(0, 4)),
          group('02', '计算芯片保护', '每个芯片独立判断利用率和内存占用。', fields.slice(4, 8),
            note('查看选卡与恢复规则', '华为 NPU、算能 TPU 均按采集到的独立计算设备调度。主机有 CPU 预算且至少一个兼容芯片可用时，允许新增部署。持续超限后，芯片须低于恢复阈值并满足恢复时间。')),
          group('03', '新增任务 CPU 预算', '预计占用 = 当前主机 CPU + 本次新增任务预留。', fields.slice(8, 10),
            note('查看预算计算说明', '每任务预留是估算值，需按现场压测校准。批量任务逐个累计，多模型按执行单元分别预留；启动完成后进入观察期，再接收下一次部署。')),
          group('04', '时间策略', '设置保护锁定、恢复及启动后的观察时间。', fields.slice(10),
            h('p', {class: 'resource-settings-inline-note'}, '当前每 ' + this.settings.policy.sample_seconds + ' 秒采样。任务已运行并取得新的 CPU 和芯片负载数据后，可在配置观察时间到达后提前放行。未满足提前放行条件时，按 ' + this.settings.effective_observation_seconds + ' 秒复核。'), 'resource-settings-timing')
        ]));
        sections.push(h('details', {class: 'resource-settings-resources'}, [
          h('summary', '已发现的计算资源'),
          !this.settings.telemetry_available ? h('p', '资源状态暂不可用，新增部署将暂停。') :
          h('div', (this.settings.hosts || []).map(function (host) {
            return h('p', '主机 ' + host.computing_id + '：' + host.chip_count + ' 个计算芯片，当前可新增部署 ' + host.available_chip_count + ' 个；CPU ' + (host.cpu == null ? '未知' : host.cpu + '%') + '。');
          })),
          h('p', '物理卡归属、板卡健康及编解码占用尚未采集，不推算物理卡数。芯片内 ARM CPU 与服务器 CPU 分别统计，完整容量需现场验证。')
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
  function createCenter(monitor) {
    return {
      name: 'DeviceMonitoringCenter',
      data: function () { return {activeTab: 'resources', canConfigure: false, settingsVisited: false, disposed: false}; },
      created: function () {
        var vm = this;
        return this.$http.get(apiBase() + '/resource_view/admission/settings').then(body).then(function (data) {
          if (!vm.disposed) { vm.canConfigure = data.can_edit === true; vm.syncTab(); }
        }).catch(function () { if (!vm.disposed) { vm.canConfigure = false; vm.syncTab(); } });
      },
      beforeDestroy: function () { this.disposed = true; },
      watch: {'$route.query.tab': function () { this.syncTab(); }},
      methods: {
        syncTab: function () {
          this.activeTab = this.canConfigure && this.$route.query.tab === 'scheduling' ? 'scheduling' : 'resources';
          if (this.activeTab === 'scheduling') this.settingsVisited = true;
        },
        selectTab: function (name) {
          if (name === 'scheduling' && !this.canConfigure) return;
          this.activeTab = name;
          if (name === 'scheduling') this.settingsVisited = true;
          var query = Object.assign({}, this.$route.query);
          if (name === 'scheduling') query.tab = 'scheduling'; else delete query.tab;
          if (query.tab !== this.$route.query.tab) this.$router.replace({path: this.$route.path, query: query, hash: this.$route.hash}).catch(function () {});
        },
        moveTab: function (event) {
          if (event.altKey || event.ctrlKey || event.metaKey || ['ArrowLeft', 'ArrowRight', 'Home', 'End'].indexOf(event.key) < 0) return;
          event.preventDefault();
          var name = event.key === 'Home' || !this.canConfigure ? 'resources' : event.key === 'End' ? 'scheduling'
            : this.activeTab === 'resources' ? 'scheduling' : 'resources';
          this.selectTab(name);
          var vm = this; this.$nextTick(function () { if (vm.$refs[name + 'Tab']) vm.$refs[name + 'Tab'].focus(); });
        }
      },
      render: function (h) {
        var vm = this;
        function tab(name, label) {
          return h('button', {key: name, ref: name + 'Tab', class: ['device-center-tab', vm.activeTab === name && 'is-active'],
            attrs: {type: 'button', role: 'tab', id: 'device-center-' + name + '-tab', 'aria-selected': String(vm.activeTab === name),
              'aria-controls': 'device-center-' + name + '-panel', tabindex: vm.activeTab === name ? 0 : -1},
            on: {click: function () { vm.selectTab(name); }, keydown: this.moveTab}}, label);
        }
        var tabs = [tab.call(this, 'resources', '资源监控')];
        if (this.canConfigure) tabs.push(tab.call(this, 'scheduling', '算力调度配置'));
        var panels = [h('section', {key: 'resources', class: 'device-center-panel', attrs: {role: 'tabpanel', id: 'device-center-resources-panel',
          'aria-labelledby': 'device-center-resources-tab', hidden: this.activeTab !== 'resources'}}, [h(monitor, {key: 'monitor'})])];
        if (this.canConfigure) panels.push(h('section', {key: 'scheduling', class: 'device-center-panel', attrs: {role: 'tabpanel',
          id: 'device-center-scheduling-panel', 'aria-labelledby': 'device-center-scheduling-tab', hidden: this.activeTab !== 'scheduling'}},
          this.settingsVisited ? [h(component, {key: 'settings'})] : []));
        return h('div', {class: 'device-monitor-center'}, [h('div', {class: 'device-center-tabs', attrs: {role: 'tablist', 'aria-label': '设备监测中心'}}, tabs)].concat(panels));
      }
    };
  }
  root.AiMonitorResourceSettings = {component: component, fields: fields, validate: errors, createCenter: createCenter};
  function installRoute(router) {
    if (router.__resourceSettingsInstalled) return;
    var routes = router.options.routes, home = routes.filter(function (route) { return route.name === 'Home'; })[0];
    if (!home) return;
    var monitor = (home.children || []).filter(function (route) { return route.path === 'ygzx' || route.name === 'ygzx'; })[0];
    if (!monitor || !monitor.component) return;
    var children = (home.children || []).filter(function (route) { return route.path !== 'resource-settings'; }).map(function (route) {
      return route === monitor ? Object.assign({}, route, {component: createCenter(monitor.component)}) : route;
    });
    children.push({path: 'resource-settings', name: 'resource-settings', redirect: function (to) {
      return {path: '/ygzx', query: Object.assign({}, to.query, {tab: 'scheduling'}), hash: to.hash};
    }, meta: {title: '设备监测中心', requireAuth: true, keepAlive: false}});
    var nextRoutes = routes.map(function (route) { return route === home ? Object.assign({}, route, {children: children}) : route; });
    var replacement = new router.constructor({routes: nextRoutes, mode: router.mode, base: router.options.base});
    router.matcher = replacement.matcher; router.options.routes = nextRoutes; router.__resourceSettingsInstalled = true;
    if (router.currentRoute.path === '/ygzx' || router.currentRoute.path === '/resource-settings') router.replace(router.currentRoute.fullPath).catch(function () {});
  }
  function findHome(vm) {
    if (!vm) return null;
    if (vm.$options && vm.$options.name === 'Home') return vm;
    var children = vm.$children || [];
    for (var i = 0; i < children.length; i += 1) { var home = findHome(children[i]); if (home) return home; }
    return null;
  }
  function cleanMenu(app) {
    var home = findHome(app);
    if (!home || home.__resourceSettingsMenuCleaned) return;
    home.__resourceSettingsMenuCleaned = true;
    function removeMenu() {
      if (home._isDestroyed) return;
      var menus = home.menuData || [];
        function isSettings(item) { return String(item.menu_link || '').replace(/^\/+|\/+$/g, '') === 'resource-settings'; }
      menus.forEach(function (menu) {
          if ((menu.children || []).some(isSettings)) {
            home.$set(menu, 'children', menu.children.filter(function (item) { return !isSettings(item); }));
          }
        });
    }
    removeMenu(); var unwatch = home.$watch('menuData', removeMenu, {deep: true});
    home.$once('hook:beforeDestroy', unwatch);
  }
  function boot(attempt) {
    var element = root.document.getElementById('app'), app = element && element.__vue__;
    if (!app || !app.$router || !app.$http) { if (attempt < 100) root.setTimeout(function () { boot(attempt + 1); }, 100); return; }
    app.$router.onReady(function () {
      installRoute(app.$router); app.$nextTick(function () { cleanMenu(app); });
    });
    app.$router.afterEach(function () { app.$nextTick(function () { cleanMenu(app); }); });
  }
  boot(0);
})(window);
