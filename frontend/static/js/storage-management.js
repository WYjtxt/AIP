/* Storage settings page for the existing Vue 2 platform distribution. */
(function (root) {
  'use strict';

  function apiBase() {
    return ((root.wgParameter && root.wgParameter.url_5000) || '').replace(/\/$/, '');
  }
  function payload(response) {
    var body = response && response.data;
    if (!body || Number(body.code) !== 200) {
      throw new Error(body && body.msg || '请求失败，请稍后重试');
    }
    return body.data || {};
  }
  function errorText(error) {
    var body = error && error.response && error.response.data;
    return body && body.msg || error && error.message || '请求失败，请稍后重试';
  }
  function bytes(value) {
    var amount = Number(value);
    if (!isFinite(amount) || amount < 0) return '—';
    if (amount < 1024) return Math.round(amount) + ' B';
    var units = ['KiB', 'MiB', 'GiB', 'TiB'], index = -1;
    do { amount /= 1024; index += 1; } while (amount >= 1024 && index < units.length - 1);
    return amount.toFixed(amount >= 100 ? 0 : 1) + ' ' + units[index];
  }
  function dateText(value) {
    return value ? String(value).replace('T', ' ').replace(/\.\d+(?=[Z+-]|$)/, '') : '—';
  }
  function button(h, label, click, disabled, primary) {
    return h('button', {
      class: ['storage-button', primary && 'storage-button-primary'],
      attrs: { type: 'button', disabled: !!disabled },
      on: { click: click },
    }, label);
  }
  function metric(h, title, value, detail) {
    return h('div', { class: 'storage-metric' }, [
      h('span', { class: 'storage-muted' }, title),
      h('strong', value),
      detail && h('span', { class: 'storage-muted' }, detail),
    ]);
  }

  var component = {
    name: 'StorageManagement',
    data: function () {
      return { settings: null, draftDays: '180', loading: false, saving: false, estimating: false,
        error: '', success: '', estimate: null, refreshTimer: null, disposed: false };
    },
    computed: {
      canEdit: function () { return !!(this.settings && this.settings.can_edit); },
      validDays: function () {
        var raw = String(this.draftDays);
        return /^\d+$/.test(raw) && Number(raw) >= 1 && Number(raw) <= 3650;
      },
      changed: function () {
        return !!(this.settings && Number(this.draftDays) !== Number(this.settings.alarm_retention_days));
      },
    },
    created: function () {
      this.load(false);
      var vm = this;
      this.refreshTimer = root.setInterval(function () {
        if (!root.document.hidden && !vm.saving && !vm.estimating) vm.load(true);
      }, 60000);
    },
    beforeDestroy: function () {
      this.disposed = true;
      root.clearInterval(this.refreshTimer);
    },
    methods: {
      load: function (preserveDraft) {
        if (this.loading || this.disposed) return Promise.resolve();
        var keepDraft = !!preserveDraft && this.changed;
        this.loading = true;
        var vm = this;
        return this.$http.get(apiBase() + '/storage_view/settings').then(payload).then(function (data) {
          if (vm.disposed) return;
          vm.settings = data;
          if (!keepDraft) vm.draftDays = String(data.alarm_retention_days);
          vm.error = '';
        }).catch(function (error) {
          if (!vm.disposed) vm.error = errorText(error);
        }).then(function () { if (!vm.disposed) vm.loading = false; });
      },
      setDays: function (value) {
        this.draftDays = String(value);
        this.estimate = null;
        this.success = '';
      },
      save: function () {
        if (!this.canEdit || !this.validDays || !this.changed || this.saving) return;
        var vm = this, days = Number(this.draftDays);
        this.$confirm('保存后仅保留最近 ' + days + ' 天的报警。超过期限的报警记录、对应图片和录像会自动删除，删除后无法恢复。', '调整报警保留期限', {
          confirmButtonText: '保存期限', cancelButtonText: '取消', type: 'warning',
        }).then(function () {
          vm.saving = true;
          vm.error = '';
          vm.success = '';
          return vm.$http.post(apiBase() + '/storage_view/settings', { alarm_retention_days: days }).then(payload).then(function (data) {
            if (vm.disposed) return;
            vm.settings = data;
            vm.draftDays = String(data.alarm_retention_days);
            vm.estimate = null;
            vm.success = '已保存，自动清理将按新的保留期限执行。';
          }).catch(function (error) {
            if (!vm.disposed) vm.error = errorText(error);
          }).then(function () { if (!vm.disposed) vm.saving = false; });
        }).catch(function () {});
      },
      estimateCleanup: function () {
        if (!this.canEdit || this.changed || this.estimating || this.saving) return;
        var vm = this;
        this.estimating = true;
        this.error = '';
        this.$http.post(apiBase() + '/storage_view/cleanup', { dry_run: true }).then(payload).then(function (data) {
          if (!vm.disposed) vm.estimate = data;
        }).catch(function (error) {
          if (!vm.disposed) vm.error = errorText(error);
        }).then(function () { if (!vm.disposed) vm.estimating = false; });
      },
    },
    render: function (h) {
      var vm = this, settings = this.settings || {}, disk = settings.disk || {}, last = settings.last_cleanup || {};
      var capacity = settings.retention_capacity || {};
      var pendingMedia = Number(settings.pending_media_files !== undefined ? settings.pending_media_files : last.pending_media_files || 0);
      var used = Number(disk.used_percent), hasDisk = isFinite(used) && disk.total_bytes > 0;
      var busy = this.loading || this.saving || this.estimating;
      var sections = [
        h('div', { class: 'storage-heading', key: 'heading' }, [
          h('div', [h('h2', '存储管理'), h('p', { class: 'storage-muted' }, '查看服务器空间，设置报警数据的自动保留期限。')]),
          button(h, this.loading ? '刷新中…' : '刷新', function () { vm.load(true); }, busy),
        ]),
      ];
      if (this.error) sections.push(h('div', { class: 'storage-notice storage-notice-error', attrs: { role: 'alert' }, key: 'error' }, this.error));
      if (this.success) sections.push(h('div', { class: 'storage-notice storage-notice-success', attrs: { role: 'status' }, key: 'success' }, this.success));
      sections.push(h('section', { class: 'storage-card', key: 'disk' }, [
        h('div', { class: 'storage-card-heading' }, [h('h3', '服务器根盘'), h('span', { class: ['storage-status', hasDisk && used >= 80 && 'storage-status-warning', hasDisk && used >= 90 && 'storage-status-critical'] }, hasDisk ? (used >= 90 ? '空间紧张' : used >= 80 ? '空间偏紧' : '空间正常') : '等待空间数据')]),
        h('div', { class: 'storage-metrics' }, [
          metric(h, '已使用', hasDisk ? bytes(disk.used_bytes) : '—'),
          metric(h, '可用空间', hasDisk ? bytes(disk.free_bytes) : '—'),
          metric(h, '总容量', hasDisk ? bytes(disk.total_bytes) : '—'),
          metric(h, '占用比例', hasDisk ? used.toFixed(1) + '%' : '—'),
        ]),
        h('div', { class: ['storage-progress', hasDisk && used >= 80 && 'storage-progress-warning', hasDisk && used >= 90 && 'storage-progress-critical'], attrs: { role: 'progressbar', 'aria-label': '根盘占用比例', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': hasDisk ? used : undefined } }, [h('div', { style: { width: (hasDisk ? Math.max(0, Math.min(100, used)) : 0) + '%' } })]),
        hasDisk && used >= 80 && h('div', { class: ['storage-space-alert', used >= 90 && 'storage-space-alert-critical'], attrs: { role: used >= 90 ? 'alert' : 'status' } }, [
          h('strong', used >= 90 ? '剩余空间较少，请及时调整保留期限或扩容。' : '根盘占用已达到 80%，请关注剩余空间。'),
          h('span', '当前可用 ' + bytes(disk.free_bytes) + '。平台只按保留天数删除过期报警，不会因空间不足提前删除报警。'),
        ]),
        capacity.insufficient && h('div', { class: 'storage-space-alert storage-space-alert-critical', attrs: { role: 'alert' } }, [
          h('strong', '当前保留期限预计超过可用容量，请缩短期限或扩容。'),
          h('span', '预计报警存储需要 ' + bytes(capacity.estimated_retention_bytes) + '，可用于报警的空间约 ' + bytes(capacity.available_for_alarm_bytes) + '。'),
        ]),
        h('p', { class: 'storage-muted storage-small' }, '空间状态每分钟更新。报警保留期限只影响过期报警，不影响算法任务运行。'),
      ]));
      var retention = [
        h('div', { class: 'storage-card-heading' }, [h('h3', '报警数据保留期限'), h('span', { class: 'storage-muted storage-small' }, '自动清理每 ' + (settings.cleanup_interval_minutes || 60) + ' 分钟检查一次')]),
        h('p', { class: 'storage-muted' }, '超过保留期限的报警记录及对应图片、录像将自动删除。'),
        h('div', { class: 'storage-retention-control' }, [
          h('label', { attrs: { for: 'alarm-retention-days' } }, '保留天数'),
          h('input', { class: 'storage-days', attrs: { id: 'alarm-retention-days', type: 'number', min: 1, max: 3650, step: 1, disabled: !this.canEdit || busy, 'aria-describedby': 'alarm-retention-help' }, domProps: { value: this.draftDays }, on: { input: function (event) { vm.setDays(event.target.value); } } }),
          h('span', { class: 'storage-muted' }, '天'),
          button(h, '10 天', function () { vm.setDays(10); }, !this.canEdit || busy),
          button(h, '30 天', function () { vm.setDays(30); }, !this.canEdit || busy),
          button(h, '60 天', function () { vm.setDays(60); }, !this.canEdit || busy),
          button(h, '90 天', function () { vm.setDays(90); }, !this.canEdit || busy),
          button(h, '180 天', function () { vm.setDays(180); }, !this.canEdit || busy),
          button(h, '365 天', function () { vm.setDays(365); }, !this.canEdit || busy),
          button(h, this.saving ? '保存中…' : '保存期限', this.save, !this.canEdit || !this.validDays || !this.changed || busy, true),
        ]),
        h('p', { class: 'storage-muted storage-small', attrs: { id: 'alarm-retention-help' } }, '支持 1–3650 天，默认 180 天。保留期限须与实际磁盘容量匹配；磁盘空间不足时不会提前删除期限内的报警。' + (this.canEdit ? '' : '只有超级管理员可以修改。')),
      ];
      if (!this.validDays) retention.push(h('p', { class: 'storage-validation', attrs: { role: 'alert' } }, '请输入 1–3650 之间的整数天数。'));
      retention.push(h('div', { class: 'storage-cleanup-actions' }, [
        button(h, this.estimating ? '估算中…' : '估算过期数据', this.estimateCleanup, !this.canEdit || this.changed || busy),
        h('span', { class: 'storage-muted storage-small' }, this.changed ? '先保存期限，再估算过期数据。' : '仅统计过期数据，不执行删除。'),
      ]));
      if (this.estimate) {
        var estimate = this.estimate;
        retention.push(h('div', { class: 'storage-estimate', attrs: { role: 'status' } }, [
          h('strong', '本次估算'),
          h('span', '过期报警总计 ' + Number(estimate.expired_records || 0) + ' 条 · 已估算媒体 ' + Number(estimate.media_files || 0) + ' 个 · ' + bytes(estimate.media_bytes || 0)),
          h('span', { class: 'storage-muted storage-small' }, '截止时间：' + dateText(estimate.cutoff) + (estimate.sample_limited ? ' · 本次扫描 ' + Number(estimate.scanned_records || 0) + ' 条报警，媒体数量和大小仅为本批统计。' : '')),
        ]));
      }
      sections.push(h('section', { class: 'storage-card', key: 'retention' }, retention));
      sections.push(h('section', { class: 'storage-card', key: 'cleanup' }, [
        h('div', { class: 'storage-card-heading' }, [h('h3', '最近自动清理'), h('span', { class: 'storage-muted storage-small' }, dateText(last.finished_at || last.completed_at || last.run_at || last.started_at))]),
        last.finished_at || last.completed_at || last.run_at || last.started_at ? h('div', { class: 'storage-metrics' }, [
          metric(h, '已清理报警', String(last.deleted_records || 0) + ' 条'),
          metric(h, '已清理媒体', String(last.deleted_media_files || last.deleted_files || 0) + ' 个'),
          metric(h, '已释放空间', bytes(last.freed_media_bytes || last.deleted_bytes || 0)),
        ]) : h('p', { class: 'storage-muted' }, '尚无自动清理记录。保存的保留期限会在后续自动检查中生效。'),
        Number(last.errors || 0) > 0 && h('p', { class: 'storage-validation', attrs: { role: 'alert' } }, '有 ' + Number(last.errors) + ' 项媒体清理失败，后续自动检查会继续尝试。'),
        pendingMedia > 0 && h('p', { class: 'storage-muted storage-small' }, '尚有 ' + pendingMedia + ' 个媒体文件等待后续安全检查。'),
        last.sample_limited && h('p', { class: 'storage-muted storage-small' }, '本轮清理已按批次结束，剩余过期数据将在后续自动检查中继续处理。'),
      ]));
      return h('div', { class: 'storage-management' }, sections);
    },
  };
  root.AiMonitorStorageManagement = component;

  // Keep all original routes and navigation guards. Only add this page's route.
  function installRoute(router) {
    if (router.__aiStorageInstalled) return;
    var routes = router.options.routes, homeRoute = routes.filter(function (route) { return route.name === 'Home'; })[0];
    if (!homeRoute) return;
    var children = (homeRoute.children || []).slice();
    if (!children.some(function (route) { return route.name === 'storage_management'; })) children.push({
      path: 'storage', name: 'storage_management', component: component,
      meta: { title: '存储管理', requireAuth: true, keepAlive: false },
    });
    var nextRoutes = routes.map(function (route) { return route === homeRoute ? Object.assign({}, route, { children: children }) : route; });
    var nextRouter = new router.constructor({ routes: nextRoutes, mode: router.mode, base: router.options.base });
    router.matcher = nextRouter.matcher;
    router.options.routes = nextRoutes;
    router.__aiStorageInstalled = true;
    if (router.currentRoute.path === '/storage') router.replace(router.currentRoute.fullPath).catch(function () {});
  }
  function findHome(vm) {
    if (!vm) return null;
    if (vm.$options && vm.$options.name === 'Home') return vm;
    var children = vm.$children || [];
    for (var index = 0; index < children.length; index += 1) {
      var home = findHome(children[index]);
      if (home) return home;
    }
    return null;
  }
  function attachMenu(app) {
    var home = findHome(app);
    if (!home || home.__aiStorageMenuRequested) return;
    home.__aiStorageMenuRequested = true;
    app.$http.get(apiBase() + '/storage_view/settings').then(payload).then(function (data) {
      if (!data.can_edit || home._isDestroyed) return;
      function addMenu() {
        var menus = home.menuData || [];
        if (!menus.length || menus.some(function (menu) {
          return menu.menu_link === 'storage' || (menu.children || []).some(function (child) { return child.menu_link === 'storage'; });
        })) return;
        var parent = menus.filter(function (menu) {
          return /运管中心|云管中心/.test(menu.menu_name || '') || (menu.children || []).some(function (child) { return child.menu_link === 'ygzx'; });
        })[0];
        var item = { menu_name: '存储管理', menu_link: 'storage', menu_icon: 'el-icon-folder', menu_id: 'storage_management' };
        if (parent) {
          if (!parent.children) home.$set(parent, 'children', []);
          parent.children.push(item);
        } else home.menuData = menus.concat([item]);
        if (home.$route.path === '/storage') home.handleMenuName();
      }
      var unwatch = home.$watch('menuData', addMenu);
      home.$once('hook:beforeDestroy', unwatch);
      addMenu();
    }).catch(function () {});
  }
  function boot(attempt) {
    var element = root.document.getElementById('app'), app = element && element.__vue__;
    if (!app || !app.$router || !app.$http) {
      if (attempt < 100) root.setTimeout(function () { boot(attempt + 1); }, 100);
      return;
    }
    installRoute(app.$router);
    app.$nextTick(function () { attachMenu(app); });
    app.$router.afterEach(function () { app.$nextTick(function () { attachMenu(app); }); });
  }
  boot(0);
})(window);
