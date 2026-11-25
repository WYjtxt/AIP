(function (root) {
  'use strict';

  var NAME = 'platform_ntp';
  var PAGE = 'platform-ntp';
  var TITLE = 'NTP 校时';
  var states = {synchronized: '已同步', pending: '等待同步', disabled: '已停用', unavailable: '校时服务不可用'};
  var navigation = {token: null, authorized: false, home: null};

  function api(suffix) {
    return String(root.wgParameter && root.wgParameter.url_5000 || '/api').replace(/\/$/, '') +
      '/platform_ops/ntp' + (suffix || '');
  }

  function status(response) {
    var body = response && response.data;
    if (!body || Number(body.code) !== 200 || !body.data || typeof body.data.supported !== 'boolean') {
      var error = new Error(body && body.msg || '无法读取主机校时状态');
      error.platformStatus = body && Number(body.code);
      throw error;
    }
    return body.data;
  }

  function errorCode(error) { return error && error.response && error.response.status || error && error.platformStatus; }

  function requestError(error) {
    var body = error && error.response && error.response.data;
    var code = errorCode(error);
    if (code === 401 || code === 403) return body && body.msg || '当前账号没有校时操作权限';
    if (error && error.code === 'ECONNABORTED') return '请求超时，请刷新后查看主机状态';
    var message = error && !error.response && error.message;
    return body && body.msg || (message !== 'Network Error' && message) || '校时服务连接失败，请稍后重试';
  }

  function button(h, title, handler, disabled, primary) {
    return h('button', {
      class: ['storage-button', primary && 'storage-button-primary'],
      attrs: {type: 'button', disabled: !!disabled},
      on: {click: handler}
    }, title);
  }

  function displayTime(value) {
    return typeof value === 'string' && value ? value.replace('T', ' ').replace(/\.\d+(?=Z|[+-]\d\d:\d\d$|$)/, '') : '—';
  }

  function intervalText(state) {
    var seconds = state && state.interval;
    if (!seconds) return '系统默认（最长约 34 分钟）';
    if (seconds % 3600 === 0) return '每 ' + (seconds / 3600) + ' 小时';
    if (seconds % 60 === 0) return '每 ' + (seconds / 60) + ' 分钟';
    return '每 ' + seconds + ' 秒';
  }

  var page = {
    name: 'AiMonitorPlatformNtp',
    data: function () {
      return {
        reading: false, action: '', state: null, server: '', enabled: false, interval: '', customInterval: '',
        error: '', notice: '', waiting: false, timer: null, deadline: 0, disposed: false
      };
    },
    computed: {
      canEdit: function () { return !!(this.state && this.state.supported && this.state.can_edit === true); },
      intervalSeconds: function () {
        if (this.interval === 'existing') return this.state.interval;
        if (this.interval === 'custom') {
          var hours = Number(this.customInterval);
          if (!Number.isInteger(hours) || hours < 1 || hours > 168) return undefined;
          return hours * 3600;
        }
        return this.interval === '' ? null : Number(this.interval);
      },
      dirty: function () {
        return !!(this.state && (this.server.trim() !== (this.state.server || '') ||
          this.enabled !== this.state.enabled || this.intervalSeconds !== (this.state.interval || null)));
      },
      canSave: function () { return this.canEdit && !this.busy && this.dirty && this.intervalSeconds !== undefined; },
      busy: function () { return this.reading || !!this.action; }
    },
    created: function () { this.load(false); },
    beforeDestroy: function () {
      this.disposed = true;
      root.clearTimeout(this.timer);
    },
    methods: {
      applyStatus: function (value, replaceDraft) {
        var adopt = !this.state || !this.dirty || replaceDraft;
        this.state = value;
        if (adopt) {
          this.server = value.server || '';
          this.enabled = value.enabled === true;
          var seconds = value.interval;
          this.interval = ['3600', '21600', '43200', '86400'].indexOf(String(seconds)) >= 0 ? String(seconds)
            : (!seconds ? '' : seconds % 3600 === 0 ? 'custom' : 'existing');
          this.customInterval = this.interval === 'custom' ? String(seconds / 3600) : '';
        }
      },
      load: function (polling) {
        if (this.disposed || this.action || this.reading) return Promise.resolve();
        var vm = this;
        this.reading = true;
        if (!polling) this.error = '';
        return this.$http.get(api(), {timeout: 10000}).then(status).then(function (value) {
          if (vm.disposed) return;
          vm.applyStatus(value, false);
          vm.error = '';
          if (vm.waiting && value.synchronized === true) {
            vm.notice = '主机时间已同步';
            vm.waiting = false;
          } else if (vm.waiting && (value.enabled === false || !value.supported)) {
            vm.waiting = false;
          }
        }).catch(function (error) {
          if (!vm.disposed) {
            vm.error = requestError(error);
            if ([401, 403].indexOf(errorCode(error)) >= 0) {
              vm.state = null;
              vm.waiting = false;
            }
          }
        }).finally(function () {
          if (!vm.disposed) {
            vm.reading = false;
            if (vm.waiting) vm.poll();
          }
        });
      },
      poll: function () {
        var vm = this;
        root.clearTimeout(this.timer);
        if (Date.now() >= this.deadline) {
          this.waiting = false;
          this.notice = '已发起校时，暂未确认同步';
          return;
        }
        this.timer = root.setTimeout(function () { vm.load(true); }, 2500);
      },
      submit: function (mode) {
        if (this.disposed || this.busy || !this.canEdit) return Promise.resolve();
        var save = mode === 'save', vm = this;
        if (save ? !this.canSave : this.dirty || !this.state.enabled || this.waiting) return Promise.resolve();
        this.action = mode;
        this.error = '';
        this.notice = '';
        this.waiting = false;
        root.clearTimeout(this.timer);
        var request = save
          ? this.$http.put(api(), {server: this.server.trim(), enabled: this.enabled, interval: this.intervalSeconds}, {timeout: 20000})
          : this.$http.post(api('/sync'), {}, {timeout: 20000});
        return request.then(status).then(function (value) {
          if (vm.disposed) return;
          vm.applyStatus(value, true);
          vm.notice = save ? '校时配置已保存' : '已发起校时，正在等待同步';
          vm.waiting = !save || (value.enabled && value.state === 'pending');
          if (vm.waiting) vm.deadline = Date.now() + 45000;
        }).catch(function (error) {
          if (!vm.disposed) {
            vm.error = requestError(error);
            if (errorCode(error) === 401) vm.state = null;
            else if (errorCode(error) === 403 && vm.state) vm.state.can_edit = false;
          }
        }).finally(function () {
          if (!vm.disposed) {
            vm.action = '';
            if (vm.waiting) vm.poll();
          }
        });
      }
    },
    render: function (h) {
      var vm = this, current = this.state;
      var summary = [
        ['平台主机时间', displayTime(current && current.host_time)],
        ['时区', current && current.timezone || '—'],
        ['同步状态', this.waiting ? states.pending : (current && states[current.state] || '—')],
        ['当前时间源', current && current.active_server || '—'],
        ['自动校时间隔', intervalText(current)],
        ['最近同步', displayTime(current && current.last_sync)],
        ['校时服务', current && current.provider || '—']
      ];
      return h('div', {class: 'storage-management ops-page', attrs: {'aria-label': TITLE}}, [
        h('div', {class: 'storage-heading'}, [
          h('div', [h('h2', TITLE), h('p', {class: 'storage-muted'}, '校时作用于平台主机。立即校时可能调整主机时间。')]),
          button(h, this.reading ? '刷新中…' : '刷新状态', function () { vm.load(false); }, this.busy)
        ]),
        this.error && h('div', {class: 'storage-notice storage-notice-error', attrs: {role: 'alert'}}, this.error),
        this.notice && h('div', {class: ['storage-notice', !this.waiting && !this.error && this.state && this.state.synchronized && 'storage-notice-success'],
          attrs: {role: 'status'}}, this.notice),
        h('section', {class: 'storage-card'}, [
          h('h3', '主机时钟'),
          h('div', {class: 'ops-table-wrap'}, [
            h('table', {class: 'ops-table'}, [
              h('tbody', summary.map(function (row) {
                return h('tr', {key: row[0]}, [h('th', {attrs: {scope: 'row'}}, row[0]), h('td', row[1])]);
              }))
            ])
          ])
        ]),
        current && h('section', {class: 'storage-card'}, [
          h('div', {class: 'storage-card-heading'}, [h('h3', '校时配置')]),
          h('form', {on: {submit: function (event) { event.preventDefault(); vm.submit('save'); }}}, [
            h('label', {class: 'ops-field'}, [
              h('span', 'NTP 服务器'),
              h('input', {attrs: {type: 'text', maxlength: 254, spellcheck: 'false', autocomplete: 'off',
                disabled: this.busy || !this.canEdit, placeholder: '留空使用系统默认时间源'},
                domProps: {value: this.server}, on: {input: function (event) { vm.server = event.target.value; }}})
            ]),
            h('label', {class: 'ops-field'}, [
              h('span', '自动校时'),
              h('select', {attrs: {disabled: this.busy || !this.canEdit}, domProps: {value: this.enabled ? 'enabled' : 'disabled'},
                on: {change: function (event) { vm.enabled = event.target.value === 'enabled'; }}}, [
                h('option', {attrs: {value: 'enabled'}}, '启用'),
                h('option', {attrs: {value: 'disabled'}}, '停用')
              ])
            ]),
            h('label', {class: 'ops-field'}, [
              h('span', '自动校时间隔'),
              h('select', {attrs: {disabled: this.busy || !this.canEdit || !this.enabled}, domProps: {value: this.interval},
                on: {change: function (event) { vm.interval = event.target.value; }}}, [
                h('option', {attrs: {value: ''}}, '系统默认（最长约 34 分钟）'),
                h('option', {attrs: {value: '3600'}}, '每 1 小时'),
                h('option', {attrs: {value: '21600'}}, '每 6 小时'),
                h('option', {attrs: {value: '43200'}}, '每 12 小时'),
                h('option', {attrs: {value: '86400'}}, '每 24 小时'),
                current.interval && current.interval % 3600 !== 0
                  ? h('option', {attrs: {value: 'existing'}}, intervalText(current)) : null,
                h('option', {attrs: {value: 'custom'}}, '自定义')
              ]),
              this.interval === 'custom' && h('input', {attrs: {type: 'number', min: 1, max: 168, step: 1,
                disabled: this.busy || !this.canEdit || !this.enabled, placeholder: '自定义间隔（小时，1-168）'},
                domProps: {value: this.customInterval}, on: {input: function (event) { vm.customInterval = event.target.value; }}})
            ]),
            h('div', {class: 'ops-actions'}, [
              button(h, this.action === 'save' ? '保存中…' : '保存配置', function () { vm.submit('save'); },
                !this.canSave, true),
              button(h, this.action === 'sync' ? '正在请求…' : '立即校时', function () { vm.submit('sync'); },
                this.busy || !this.canEdit || this.dirty || !current.enabled || this.waiting)
            ])
          ])
        ])
      ]);
    }
  };

  function normalizedPath(path) { return String(path || '').replace(/^\/+|\/+$/g, ''); }

  function findHome(vm) {
    if (!vm) return null;
    if (vm.$options && vm.$options.name === 'Home') return vm;
    for (var i = 0; i < (vm.$children || []).length; i += 1) {
      var result = findHome(vm.$children[i]);
      if (result) return result;
    }
    return null;
  }

  function menuItem(item) { return item && normalizedPath(item.menu_link) === PAGE; }

  function updateMenu(home) {
    var menu = home && home.menuData;
    if (!Array.isArray(menu) || home._isDestroyed) return;
    var upgrade = menu.findIndex(function (item) { return normalizedPath(item.menu_link) === 'platform-upgrade'; });
    var present = menu.filter(menuItem);
    if (navigation.authorized && upgrade >= 0 && present.length === 1 && menu[upgrade + 1] === present[0]) return;
    for (var i = menu.length - 1; i >= 0; i -= 1) {
      if (menuItem(menu[i])) {
        menu.splice(i, 1);
        if (i < upgrade) upgrade -= 1;
      }
    }
    if (navigation.authorized && upgrade >= 0) {
      menu.splice(upgrade + 1, 0, {id: '__platform_ntp', menu_name: TITLE, menu_link: PAGE, permissions_list: ['r']});
    }
  }

  function watchHome(app) {
    var home = findHome(app);
    if (home && home !== navigation.home) {
      navigation.home = home;
      ['findActive', 'findNoActive'].forEach(function (name) {
        var original = home[name];
        if (typeof original === 'function') home[name] = function (label) { return original.call(this, label === TITLE ? '系统管理' : label); };
      });
      var unwatch = home.$watch('menuData', function () { updateMenu(home); }, {deep: true});
      home.$once('hook:beforeDestroy', function () {
        unwatch();
        if (navigation.home === home) navigation.home = null;
      });
    }
    updateMenu(home);
  }

  function capability(app) {
    var token = root.localStorage && root.localStorage.getItem('token');
    if (token === navigation.token) return;
    navigation.token = token;
    navigation.authorized = false;
    updateMenu(navigation.home);
    if (!token) return;
    app.$http.get(api(), {timeout: 10000}).then(status).then(function () {
      if (token !== navigation.token) return;
      navigation.authorized = true;
      updateMenu(navigation.home);
    }).catch(function (error) {
      if (token !== navigation.token) return;
      var code = errorCode(error);
      if (code !== 401 && code !== 403) navigation.token = null;
    });
  }

  function installRoute(router) {
    if (router.__platformNtpInstalled) return;
    var routes = router.options.routes;
    var home = routes.find(function (route) { return route.name === 'Home'; });
    if (!home) return;
    var children = (home.children || []).slice();
    if (!children.some(function (route) { return route.name === NAME || route.path === PAGE; })) {
      children.push({path: PAGE, name: NAME, component: page, meta: {title: TITLE, requireAuth: true, keepAlive: false}});
    }
    var next = routes.map(function (route) { return route === home ? Object.assign({}, route, {children: children}) : route; });
    router.matcher = new router.constructor({routes: next, mode: router.mode, base: router.options.base}).matcher;
    router.options.routes = next;
    router.__platformNtpInstalled = true;
    if (router.currentRoute.path === '/' + PAGE) router.replace(router.currentRoute.fullPath).catch(function () {});
  }

  function boot(attempt) {
    var element = root.document.getElementById('app'), app = element && element.__vue__;
    if (!app || !app.$router || !app.$http) {
      if (attempt < 300) root.setTimeout(function () { boot(attempt + 1); }, 100);
      return;
    }
    function update() { app.$nextTick(function () { watchHome(app); capability(app); }); }
    app.$router.onReady(function () { installRoute(app.$router); update(); });
    app.$router.afterEach(update);
  }

  boot(0);
})(window);
