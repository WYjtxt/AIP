(function (root) {
  'use strict';
  function base() { return ((root.wgParameter || {}).url_5000 || '').replace(/\/$/, '') + '/platform_ops/storage'; }
  function value(response) { var body = response.data; if (!body || Number(body.code) !== 200) throw new Error(body && body.msg || '存储操作失败'); return body.data; }
  function message(error) { return error && error.response && error.response.data && error.response.data.msg || error && error.message || '存储操作失败'; }
  var component = {
    name: 'AlarmDirectorySettings',
    props: { canEdit: { type: Boolean, default: false } },
    data: function () { return { status: null, draft: '', preview: null, busy: false, error: '', notice: '' }; },
    created: function () { this.load(); },
    methods: {
      load: function () {
        var vm = this;
        return this.$http.get(base()).then(value).then(function (data) {
          vm.status = data;
          if (!vm.draft) vm.draft = data.draft || (data.active || {}).target || '';
        }).catch(function (error) { vm.error = message(error); });
      },
      edit: function (event) { this.draft = event.target.value; this.preview = null; this.notice = ''; this.error = ''; },
      operate: function (action) {
        if (!this.canEdit || this.busy) return;
        var vm = this, path = this.draft.trim();
        if (!path) { this.error = '请输入报警目录'; return; }
        if (action === 'apply' && (!this.preview || this.preview.path !== path)) { this.error = '请先预检当前目录'; return; }
        this.busy = true; this.error = ''; this.notice = '';
        var body = { path: path };
        if (action === 'apply') body.revision = this.preview.revision;
        return this.$http.post(base() + '/' + action, body).then(value).then(function (data) {
          if (action === 'preview') { vm.preview = data; vm.draft = data.path; vm.notice = data.will_create ? '目录预检通过，点击“应用目录”后将自动创建缺失目录，并切换新报警保存位置。' : '目录预检通过，应用后新报警将写入该目录。'; }
          else if (action === 'draft') { vm.status = data; vm.notice = '草稿已保存，当前报警目录未切换。'; }
          else { vm.status = data; vm.preview = null; vm.notice = data.changed ? ((data.created_directories || []).length ? '目标目录已自动创建并应用，历史文件保留在原目录。' : '目录已应用，历史文件保留在原目录。') : '当前已使用该目录。'; }
        }).catch(function (error) { vm.error = message(error); if (action === 'apply') vm.preview = null; }).then(function () { vm.busy = false; });
      },
    },
    render: function (h) {
      var vm = this, status = this.status || {}, active = status.active || {};
      function button(label, action, disabled) { return h('button', { class: 'storage-button', attrs: { type: 'button', disabled: !!disabled }, on: { click: function () { vm.operate(action); } } }, label); }
      var disabled = this.busy || !this.canEdit;
      return h('section', { class: 'storage-card', attrs: { 'aria-label': '报警目录设置' } }, [
        h('div', { class: 'storage-card-heading' }, [h('h3', '报警图片与录像目录')]),
        h('p', ['当前目录：', h('strong', active.target || '读取中…')]),
        h('p', { class: 'storage-muted storage-small' }, '更改只影响新报警。历史图片和录像保留原位，原地址继续可读；按现有保留期限清理，不自动迁移。'),
        !status.ready && status.readiness_reason && h('p', { class: 'storage-validation', attrs: { role: 'status' } }, status.readiness_reason),
        h('label', { attrs: { for: 'alarm-directory-path' } }, '目标目录'),
        h('input', { class: 'storage-directory-input', style: { width: '100%', maxWidth: '760px', margin: '12px 0', padding: '10px', boxSizing: 'border-box' }, attrs: { id: 'alarm-directory-path', type: 'text', autocomplete: 'off', placeholder: '/data/AIGO/platform_start/alarm-storage', disabled: disabled }, domProps: { value: this.draft }, on: { input: this.edit } }),
        h('p', { class: 'storage-muted storage-small' }, '目录不存在时，点击“应用目录”后会自动创建；预检和保存草稿不会创建目录。'),
        h('div', { class: 'storage-cleanup-actions' }, [button('保存草稿', 'draft', disabled), button(this.busy ? '处理中…' : '预检目录', 'preview', disabled), button('应用目录', 'apply', disabled || !this.preview || !status.ready)]),
        this.preview && h('p', { class: 'storage-muted storage-small' }, '预检可用空间：' + (Number(this.preview.available_bytes) / 1073741824).toFixed(2) + ' GiB。' + (this.preview.will_create ? '应用时自动创建 ' + (this.preview.missing_directories || []).length + ' 级目录。' : '目标目录已存在，可直接应用。')),
        this.error && h('p', { class: 'storage-validation', attrs: { role: 'alert' } }, this.error),
        this.notice && h('p', { class: 'storage-notice storage-notice-success', attrs: { role: 'status' } }, this.notice),
      ]);
    },
  };
  root.AiMonitorAlarmDirectory = component;
})(window);
