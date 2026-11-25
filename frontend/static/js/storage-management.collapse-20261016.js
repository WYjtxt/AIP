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
  function firstDefined(value, fallback) {
    return value !== undefined && value !== null ? value : fallback;
  }
  function countValue(value) {
    if (value === undefined || value === null || value === '') return null;
    var number = Number(value);
    return isFinite(number) && number >= 0 ? Math.floor(number) : null;
  }
  function countText(value, suffix) {
    var number = countValue(value);
    return number === null ? '—' : String(number) + (suffix || '');
  }
  function diskNumber(value) {
    if (value === undefined || value === null || value === '' || typeof value === 'boolean') return null;
    var number = Number(value);
    return isFinite(number) && number >= 0 ? number : null;
  }
  function diskSnapshot(settings) {
    var summary = settings.disk_summary || {}, disks = Array.isArray(settings.disks) ? settings.disks : [];
    var status = String(summary.status || 'unavailable');
    if (status === 'ok' && summary.complete === false) status = 'partial';
    var valid = summary.available === true && (status === 'ok' || status === 'partial') && summary.scope === 'host_mounted_filesystems' && disks.length > 0;
    var seen = Object.create(null);
    if (valid) {
      valid = diskNumber(summary.total_bytes) > 0 && diskNumber(summary.used_bytes) !== null && diskNumber(summary.free_bytes) !== null && diskNumber(summary.used_percent) !== null && Number(summary.used_percent) <= 100 && Number(summary.volume_count) === disks.length && typeof summary.collected_at === 'string' && isFinite(new Date(summary.collected_at).getTime()) && diskNumber(summary.age_seconds) !== null;
      if (Number(summary.used_bytes) + Number(summary.free_bytes) > Number(summary.total_bytes)) valid = false;
      disks.forEach(function (disk) {
        if (!disk || typeof disk !== 'object' || typeof disk.device_id !== 'string' || !disk.device_id || seen[String(disk.device_id)] || typeof disk.mountpoint !== 'string' || disk.mountpoint.charAt(0) !== '/' || !(diskNumber(disk.total_bytes) > 0) || diskNumber(disk.used_bytes) === null || diskNumber(disk.free_bytes) === null || diskNumber(disk.used_percent) === null || Number(disk.used_percent) > 100) valid = false;
        if (disk && Number(disk.used_bytes) + Number(disk.free_bytes) > Number(disk.total_bytes)) valid = false;
        if (disk && disk.device_id) seen[String(disk.device_id)] = true;
      });
    }
    if ((status === 'ok' || status === 'partial') && !valid) status = 'invalid';
    return { available: valid, status: status, summary: summary, disks: valid ? disks : [] };
  }
  function diskTime(value) {
    var parsed = value ? new Date(value) : null;
    return parsed && isFinite(parsed.getTime()) ? parsed.toLocaleString('zh-CN', { hour12: false }) + '（浏览器本地时间）' : '—';
  }
  function diskTitle(disk) {
    var label = disk.mountpoint === '/boot/efi' ? 'EFI 系统分区' : disk.kind === 'root' ? '根文件系统' : disk.kind === 'system' ? '启动系统分区' : disk.kind === 'data' ? '数据 / 应用文件系统' : String(disk.label || '磁盘文件系统');
    return label + ' ' + disk.mountpoint;
  }
  function diskStatus(percent) {
    return percent >= 90 ? '空间紧张' : percent >= 80 ? '空间偏紧' : '空间正常';
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
        error: '', success: '', estimate: null, refreshTimer: null, disposed: false,
        diskExpansion: Object.create(null) };
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
      diskExpanded: function (disk) {
        var key = String(disk.device_id);
        return Object.prototype.hasOwnProperty.call(this.diskExpansion, key) ? this.diskExpansion[key] === true : Number(disk.used_percent) >= 80;
      },
      diskDetailsId: function (disk) {
        return 'storage-disk-details-' + String(disk.device_id).split('').map(function (character) { return character.charCodeAt(0).toString(16); }).join('-');
      },
      toggleDisk: function (disk) {
        this.$set(this.diskExpansion, String(disk.device_id), !this.diskExpanded(disk));
      },
      setAllDisksExpanded: function (expanded) {
        var vm = this;
        diskSnapshot(this.settings || {}).disks.forEach(function (disk) { vm.$set(vm.diskExpansion, String(disk.device_id), expanded === true); });
      },
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
      var vm = this, settings = this.settings || {}, last = settings.last_cleanup || {};
      var host = diskSnapshot(settings), summary = host.summary;
      var showingPreviousSnapshot = !!this.error && host.available;
      var diskWarnings = Array.isArray(summary.warnings) ? summary.warnings.filter(function (warning) { return typeof warning === 'string' && warning; }) : [];
      var capacity = settings.retention_capacity || {};
      var pendingMedia = countValue(firstDefined(settings.pending_media_files, last.pending_media_files));
      var uncheckedMedia = countValue(firstDefined(settings.unchecked_media_files, last.unchecked_media_files));
      var continuation = typeof settings.continuation_required === 'boolean' ? settings.continuation_required : (typeof last.continuation_required === 'boolean' ? last.continuation_required : null);
      var orphanComplete = typeof settings.orphan_scan_complete === 'boolean' ? settings.orphan_scan_complete : (typeof last.orphan_scan_complete === 'boolean' ? last.orphan_scan_complete : null);
      var discoverMinutes = countValue(settings.cleanup_interval_minutes) || 60;
      var backlogMinutes = countValue(settings.cleanup_backlog_interval_minutes) || 1;
      var nextMinutes = countValue(firstDefined(settings.next_check_minutes, last.next_check_minutes));
      var busy = this.loading || this.saving || this.estimating;
      var sections = [
        h('div', { class: 'storage-heading', key: 'heading' }, [
          h('div', [h('h2', '存储管理'), h('p', { class: 'storage-muted' }, '查看服务器空间，设置报警数据的自动保留期限。')]),
          button(h, this.loading ? '刷新中…' : '刷新', function () { vm.load(true); }, busy),
        ]),
      ];
      if (this.error) sections.push(h('div', { class: 'storage-notice storage-notice-error', attrs: { role: 'alert' }, key: 'error' }, this.error));
      if (this.success) sections.push(h('div', { class: 'storage-notice storage-notice-success', attrs: { role: 'status' }, key: 'success' }, this.success));
      sections.push(h('section', { class: 'storage-card', key: 'disk-summary' }, [
        h('div', { class: 'storage-card-heading' }, [h('h3', host.status === 'partial' ? '已采集分区合计（信息不完整）' : '宿主机存储总览'), h('span', { class: ['storage-status', (!host.available || host.status === 'partial' || showingPreviousSnapshot) && 'storage-status-warning', host.status === 'invalid' && 'storage-status-critical'] }, showingPreviousSnapshot ? '显示上次数据' : host.status === 'partial' ? '采集不完整' : host.available ? '采集正常' : host.status === 'stale' ? '数据已过期' : host.status === 'invalid' ? '采集数据异常' : '暂无可用数据')]),
        showingPreviousSnapshot && h('p', { class: 'storage-muted storage-small', attrs: { role: 'status' } }, '当前为上次成功读取的快照，请刷新核对采集时间。'),
        h('p', { class: 'storage-muted storage-small' }, '统计宿主机已挂载的真实磁盘文件系统，包含启动分区；同一文件系统只计一次，不将物理磁盘与其分区或逻辑卷重复相加。'),
        h('div', { class: 'storage-metrics' }, [
          metric(h, host.status === 'partial' ? '已采集容量' : '已挂载总容量', host.available ? bytes(summary.total_bytes) : '—'),
          metric(h, '已使用', host.available ? bytes(summary.used_bytes) : '—'),
          metric(h, '可用空间', host.available ? bytes(summary.free_bytes) : '—'),
          metric(h, host.status === 'partial' ? '已采集文件系统' : '独立文件系统', host.available ? String(summary.volume_count) + ' 个' : '—'),
        ]),
        h('p', { class: 'storage-muted storage-small' }, '采集时间：' + diskTime(summary.collected_at) + (diskNumber(summary.age_seconds) !== null ? ' · 数据年龄 ' + Math.floor(Number(summary.age_seconds)) + ' 秒' : '') + ' · 每 ' + (diskNumber(summary.refresh_interval_seconds) || 60) + ' 秒采集，页面每分钟更新。'),
        (!host.available || host.status === 'partial') && h('div', { class: 'storage-space-alert', attrs: { role: 'alert' } }, [
          h('strong', host.status === 'partial' ? '部分文件系统尚未采集，以下容量只包含已采集分区，不能代表宿主机总量。' : host.status === 'stale' ? '宿主机磁盘采集数据已过期，当前容量暂不展示。' : host.status === 'invalid' ? '宿主机磁盘数据异常，当前容量暂不展示。' : '尚未获取有效的宿主机磁盘数据。'),
          h('span', String(summary.message || '请检查宿主机采集服务。当前不会使用容器根盘数据代替宿主机容量。')),
        ]),
        host.available && host.status === 'ok' && summary.message && h('p', { class: 'storage-muted storage-small' }, String(summary.message)),
        diskWarnings.length > 0 && h('ul', { class: 'storage-muted storage-small', style: { paddingLeft: '20px', overflowWrap: 'anywhere' } }, diskWarnings.map(function (warning) { return h('li', warning); })),
        capacity.insufficient && h('div', { class: 'storage-space-alert storage-space-alert-critical', attrs: { role: 'alert' } }, [
          h('strong', '报警数据目录容量估算：当前保留期限预计超过可用容量，请缩短期限或扩容。'),
          h('span', '预计报警存储需要 ' + bytes(capacity.estimated_retention_bytes) + '，可用于报警的空间约 ' + bytes(capacity.available_for_alarm_bytes) + '。'),
        ]),
      ]));
      if (host.disks.length) sections.push(h('div', { class: 'storage-disk-controls', key: 'disk-controls' }, [
        h('span', { class: 'storage-muted storage-small' }, '挂载文件系统 · 空间偏紧的分区默认展开，手动选择会在本页面保留。'),
        button(h, '全部展开', function () { vm.setAllDisksExpanded(true); }, false),
        button(h, '全部收起', function () { vm.setAllDisksExpanded(false); }, false),
      ]));
      host.disks.forEach(function (disk) {
        var percent = Number(disk.used_percent);
        var expanded = vm.diskExpanded(disk), detailsId = vm.diskDetailsId(disk);
        var aliases = Array.isArray(disk.aliases) ? disk.aliases.filter(function (alias, index, all) { return typeof alias === 'string' && alias !== disk.mountpoint && all.indexOf(alias) === index; }) : [];
        sections.push(h('section', { class: ['storage-card', 'storage-disk-card'], key: 'host-disk-' + disk.device_id }, [
          h('div', { class: 'storage-card-heading storage-disk-heading' }, [
            h('h3', [h('button', { class: 'storage-disk-toggle', attrs: { type: 'button', 'aria-expanded': expanded ? 'true' : 'false', 'aria-controls': detailsId, 'aria-label': (expanded ? '收起' : '展开') + diskTitle(disk) + '详细信息' }, on: { click: function () { vm.toggleDisk(disk); } } }, [
              h('span', { class: 'storage-disk-chevron', attrs: { 'aria-hidden': 'true' } }, expanded ? '▾' : '▸'),
              h('span', { class: 'storage-disk-name' }, diskTitle(disk)),
              h('span', { class: 'storage-disk-action', attrs: { 'aria-hidden': 'true' } }, expanded ? '收起' : '展开'),
            ])]),
            h('span', { class: ['storage-status', percent >= 80 && 'storage-status-warning', percent >= 90 && 'storage-status-critical'], style: { flexShrink: 0 } }, diskStatus(percent)),
          ]),
          h('div', { class: 'storage-disk-summary' }, [
            h('span', ['占用 ', h('strong', percent.toFixed(1) + '%')]),
            h('span', ['可用 ', h('strong', bytes(disk.free_bytes))]),
            h('span', { class: 'storage-muted' }, '总容量 ' + bytes(disk.total_bytes)),
          ]),
          h('div', { class: ['storage-progress', percent >= 80 && 'storage-progress-warning', percent >= 90 && 'storage-progress-critical'], attrs: { role: 'progressbar', 'aria-label': disk.mountpoint + ' 占用比例', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': percent } }, [h('div', { style: { width: Math.max(0, Math.min(100, percent)) + '%' } })]),
          percent >= 80 && h('div', { class: ['storage-space-alert', percent >= 90 && 'storage-space-alert-critical'], attrs: { role: percent >= 90 ? 'alert' : 'status' } }, [
            h('strong', percent >= 90 ? '该文件系统剩余空间较少，请核查占用或扩容。' : '该文件系统占用已达到 80%，请关注剩余空间。'),
            h('span', '当前可用 ' + bytes(disk.free_bytes) + '。空间不足时不会提前删除保留期限内的报警。'),
          ]),
          h('div', { class: 'storage-disk-details', attrs: { id: detailsId, role: 'region', 'aria-label': diskTitle(disk) + '详细信息', hidden: !expanded } }, [
            h('p', { class: 'storage-muted storage-small', style: { overflowWrap: 'anywhere' } }, String(disk.source || '设备未标注') + ' · ' + String(disk.filesystem || '文件系统未标注') + ' · ' + (disk.read_only ? '只读挂载' : '读写挂载')),
            aliases.length > 0 && h('p', { class: 'storage-muted storage-small', style: { overflowWrap: 'anywhere' } }, '同一文件系统的其他挂载点：' + aliases.join('、') + '（已去重，不另计容量）'),
            h('div', { class: 'storage-metrics' }, [
              metric(h, '总容量', bytes(disk.total_bytes)), metric(h, '已使用', bytes(disk.used_bytes)),
              metric(h, '可用空间', bytes(disk.free_bytes)), metric(h, '占用比例', percent.toFixed(1) + '%'),
            ]),
          ]),
        ]));
      });
      var physicalDisks = host.available && Array.isArray(summary.physical_disks) ? summary.physical_disks : [];
      var swap = host.available && summary.swap && typeof summary.swap === 'object' ? summary.swap : null;
      var hasSwap = !!(swap && diskNumber(swap.total_bytes) !== null && diskNumber(swap.used_bytes) !== null && diskNumber(swap.free_bytes) !== null && Number(swap.used_bytes) + Number(swap.free_bytes) === Number(swap.total_bytes) && Array.isArray(swap.devices));
      sections.push(h('section', { class: 'storage-card', key: 'host-hardware' }, [
        h('div', { class: 'storage-card-heading' }, [h('h3', '物理磁盘与交换空间')]),
        h('p', { class: 'storage-muted storage-small' }, '以下物理盘与交换空间单列展示，不加入上方挂载文件系统汇总。'),
        !host.available && h('p', { class: 'storage-validation' }, '宿主机采集数据当前不可用，暂不显示硬件与交换空间数值。'),
        h('h4', { style: { margin: '18px 0 8px', fontSize: '14px' } }, '物理磁盘'),
        physicalDisks.length ? physicalDisks.map(function (value, index) {
          var physical = value && typeof value === 'object' ? value : {};
          return h('div', { key: 'physical-' + String(physical.device || index), style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '12px', padding: '12px 0', borderBottom: '1px solid #edf2f7' } }, [
            h('strong', { style: { minWidth: 0, overflowWrap: 'anywhere' } }, String(physical.device || physical.name || '设备未标注') + (physical.read_only ? '（只读）' : '')),
            h('span', '设备容量：' + (diskNumber(physical.size_bytes) !== null ? bytes(physical.size_bytes) : '—')),
          ]);
        }) : h('p', { class: 'storage-muted storage-small' }, '物理磁盘信息暂不可用。'),
        h('h4', { style: { margin: '20px 0 8px', fontSize: '14px' } }, '交换空间（Swap）'),
        hasSwap ? h('div', { class: 'storage-metrics' }, [
          metric(h, '交换空间总量', bytes(swap.total_bytes)),
          metric(h, '交换空间已用', bytes(swap.used_bytes)),
          metric(h, '交换空间可用', bytes(swap.free_bytes)),
        ]) : h('p', { class: 'storage-muted storage-small' }, '交换空间信息暂不可用。'),
        hasSwap && !swap.devices.length && h('p', { class: 'storage-muted storage-small' }, '当前未配置或启用交换空间。'),
        hasSwap && swap.devices.map(function (device, index) {
          return h('p', { key: 'swap-' + String(device.device || index), class: 'storage-muted storage-small', style: { overflowWrap: 'anywhere' } }, String(device.device || '设备未标注') + ' · 总量 ' + bytes(device.size_bytes) + ' · 已用 ' + bytes(device.used_bytes));
        }),
      ]));
      if (host.available && Array.isArray(summary.unmounted_devices) && summary.unmounted_devices.length) {
        sections.push(h('section', { class: 'storage-card', key: 'unmounted-volumes' }, [
          h('div', { class: 'storage-card-heading' }, [h('h3', '未挂载卷'), h('span', { class: 'storage-muted storage-small' }, String(summary.unmounted_devices.length) + ' 个')]),
          h('p', { class: 'storage-muted storage-small' }, '这些卷尚未挂载，仅显示卷容量；已用空间、可用空间和占用比例未知，不计入上方挂载文件系统汇总。'),
          summary.unmounted_devices.map(function (value, index) {
            var volume = value && typeof value === 'object' ? value : {};
            return h('div', { key: 'unmounted-' + String(volume.device || index), style: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '12px', padding: '14px 0', borderBottom: '1px solid #edf2f7' } }, [
              h('div', { style: { minWidth: 0, overflowWrap: 'anywhere' } }, [
                h('strong', String(volume.device || volume.name || '设备未标注')),
                h('div', { class: 'storage-muted storage-small' }, String(volume.filesystem || '文件系统未标注') + ' · ' + (volume.type === 'lvm' ? '逻辑卷' : '分区') + (volume.read_only ? ' · 只读设备' : '')),
              ]),
              h('span', '卷容量：' + (diskNumber(volume.size_bytes) !== null ? bytes(volume.size_bytes) : '—')),
            ]);
          }),
        ]));
      }
      var retention = [
        h('div', { class: 'storage-card-heading' }, [h('h3', '报警数据保留期限'), h('span', { class: 'storage-muted storage-small' }, '每 ' + discoverMinutes + ' 分钟发现新过期数据 · 待处理数据每 ' + backlogMinutes + ' 分钟续跑')]),
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
        h('div', { class: 'storage-card-heading' }, [h('h3', '自动清理进度'), h('span', { class: 'storage-muted storage-small' }, continuation === true ? '有待续跑批次' : continuation === false ? '当前无待续跑批次' : '等待进度数据')]),
        h('div', { class: 'storage-metrics' }, [
          metric(h, '媒体处理队列', countText(pendingMedia, ' 个'), settings.pending_media_files !== undefined ? '当前队列，包含暂时保留的文件' : '最近一批结束时的队列快照'),
          metric(h, '待安全检查媒体', countText(uncheckedMedia, ' 个'), settings.unchecked_media_files !== undefined ? '当前尚未完成安全检查' : '最近一批结束时的快照'),
          metric(h, '本批结束时剩余过期报警', countText(last.remaining_expired_records, ' 条')),
        ]),
        h('p', { class: 'storage-muted storage-small' }, continuation === true ? '待处理数据按每 ' + (nextMinutes || backlogMinutes) + ' 分钟的周期继续分批处理；该周期不是完成倒计时。' : continuation === false ? '后续按每 ' + (nextMinutes || discoverMinutes) + ' 分钟的周期检查新过期数据；暂时保留的媒体也会重新核查。' : '清理进度将在后续自动检查后更新。'),
        orphanComplete === false && h('p', { class: 'storage-muted storage-small' }, '媒体目录扫描尚未结束，后续批次会从保存的进度继续。'),
        h('p', { class: 'storage-muted storage-small' }, '队列数量不等于可删除数量。仍被报警记录引用、近期修改或安全检查尚未完成的文件会保留。'),
        h('div', { class: 'storage-card-heading', style: { marginTop: '24px' } }, [h('h3', '最近一批自动清理'), h('span', { class: 'storage-muted storage-small' }, dateText(last.finished_at || last.completed_at || last.run_at || last.started_at))]),
        h('p', { class: 'storage-muted storage-small' }, '以下数字仅为最近一个已完成批次的统计，不是累计清理总量。'),
        last.finished_at || last.completed_at || last.run_at || last.started_at ? h('div', { class: 'storage-metrics' }, [
          metric(h, '本批清理报警', countText(last.deleted_records, ' 条')),
          metric(h, '本批清理媒体', countText(firstDefined(last.deleted_media_files, last.deleted_files), ' 个')),
          metric(h, '本批释放空间', bytes(firstDefined(last.freed_media_bytes, last.deleted_bytes))),
          metric(h, '本批安全检查媒体', countText(last.queue_checked_files, ' 个')),
        ]) : h('p', { class: 'storage-muted' }, '尚无自动清理记录。保存的保留期限会在后续自动检查中生效。'),
        Number(last.errors || 0) > 0 && h('p', { class: 'storage-validation', attrs: { role: 'alert' } }, '最近一批有 ' + Number(last.errors) + ' 项清理错误，后续自动检查会重试。'),
        Number(last.shared_files || 0) > 0 && h('p', { class: 'storage-muted storage-small' }, '最近一批保留 ' + Number(last.shared_files) + ' 个仍被其他报警记录引用的媒体文件。'),
        Number(last.recent_files || 0) > 0 && h('p', { class: 'storage-muted storage-small' }, '最近一批有 ' + Number(last.recent_files) + ' 个文件因修改时间未超过保留期限而暂时保留。'),
        Number(last.incomplete_reference_batches || 0) > 0 && h('p', { class: 'storage-muted storage-small' }, '最近一批有 ' + Number(last.incomplete_reference_batches) + ' 个安全检查批次尚未完成完整引用扫描，整批文件保留，后续继续检查。'),
        Number(last.replaced_files || 0) > 0 && h('p', { class: 'storage-muted storage-small' }, '最近一批有 ' + Number(last.replaced_files) + ' 个文件在检查后发生变化，未删除替换后的文件。'),
        Number(last.unmanaged_references || 0) > 0 && h('p', { class: 'storage-muted storage-small' }, '最近一批有 ' + Number(last.unmanaged_references) + ' 条媒体引用不在受管目录内，未删除其文件。'),
        last.sample_limited && h('p', { class: 'storage-muted storage-small' }, '最近一批达到处理边界后结束；待检查数据会按续跑周期继续处理，已保留的文件不会被强制删除。'),
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
