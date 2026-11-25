/* hik-platform-preview-v1 */
/* Vue 2 component loaded alongside the existing distribution. No camera plugin required. */
(function (root) {
  'use strict';
  function emptySlot(index) {
    return { index: index, device: null, state: 'empty', message: '', diagnostics: null, compatibility: '', compatibilityAttempted: false, sourceCodec: '', connectionRetries: 0 };
  }
  function apiBase() {
    return (root.wgParameter.url_5000 || '').replace(/\/$/, '');
  }
  function token(vm) {
    return (vm.$store && vm.$store.getters.getToken) || root.localStorage.getItem('token') || '';
  }
  function visibleSlots(vm) {
    return vm.slots.slice(0, vm.layout);
  }
  function diagnosticText(data) {
    if (!data) return '';
    var capabilities = data.capabilities || {}, combined = capabilities.combined || {}, videoOnly = capabilities.videoOnly || {};
    var tracks = (capabilities.tracks || []).map(function (track) {
      return track.kind + ': ' + track.codec + (track.width && track.height ? ' (' + track.width + '×' + track.height + ')' : '');
    });
    function support(value) { return value === true ? '已声明支持' : value === false ? '未声明支持' : '尚未检测'; }
    return tracks.concat([
      'MSE 完整轨: ' + support(combined.mseSupported),
      'MSE 单视频: ' + support(videoOnly.mseSupported),
      '原生完整轨: ' + (combined.nativeSupport || '未声明支持'),
      '播放通道: ' + data.transport + ' / ' + data.stage,
      '媒体错误码: ' + (data.mediaErrorCode || '无'),
      '浏览器: ' + (data.browser && data.browser.userAgent || '未知'),
    ]).join('\n');
  }

  // Share playback cleanup while each page keeps its own sources and layouts.
  // Only live preview may request a transient compatible-playback lease.
  function createPreview(profile) {
    profile = profile || {};
    var layouts = profile.layouts || [1, 4, 9, 16, 25];
    var heading = profile.heading || '监控点';
    var apiPrefix = profile.apiPrefix || '/video_view/preview/';
    var compatibilityAllowed = apiPrefix === '/video_view/preview/' && !profile.showTasks;
    var analysisPreview = apiPrefix === '/video_view/analysis_preview/';
    function taskText(device, includeTaskNames) {
      if (!profile.showTasks) return '';
      var tasks = device.tasks || [];
      // Put enabled configurations first and keep the saved task name searchable.
      var ordered = tasks.filter(function (task) { return String(task.status) === '1'; })
        .concat(tasks.filter(function (task) { return String(task.status) !== '1'; }));
      return ordered.map(function (task) {
        var status = String(task.status);
        var statusLabel = status === '1' ? '已启用' : status === '2' ? '已停用' : '状态未知';
        var algorithm = task.algorithm ? [task.algorithm, task.algorithm_version].filter(Boolean).join(' ') : '';
        var name = includeTaskNames && algorithm && task.name && task.name !== task.algorithm ? '任务：' + task.name : '';
        return [algorithm || task.name, statusLabel, name].filter(Boolean).join(' · ');
      }).join('；');
    }
    return {
    name: profile.name || 'StreamPreview',
    data: function () {
      return {
        layout: 4, activeSlot: 0, maximizedSlot: null,
        slots: Array.from({ length: 25 }, function (_, i) { return emptySlot(i); }),
        devices: [], checkedIds: [], search: '', loading: false, listError: '',
        bulkPlaying: false, statusMessage: '',
        compatSettings: null, compatLimit: 8, compatSaving: false, compatSettingsError: '',
      };
    },
    computed: {
      groups: function () {
        var groups = new Map();
        var query = this.search.trim().toLowerCase();
        this.devices.forEach(function (device) {
          if (query && (device.name + ' ' + device.group + ' ' + taskText(device, true)).toLowerCase().indexOf(query) < 0) return;
          var key = device.parent_id || 'independent';
          if (!groups.has(key)) groups.set(key, { key: key, name: device.group, devices: [] });
          groups.get(key).devices.push(device);
        });
        return Array.from(groups.values());
      },
      playingCount: function () {
        return visibleSlots(this).filter(function (slot) { return slot.state === 'playing'; }).length;
      },
      occupiedCount: function () {
        return visibleSlots(this).filter(function (slot) { return slot.device; }).length;
      },
      errorCount: function () {
        return visibleSlots(this).filter(function (slot) { return slot.state === 'error'; }).length;
      },
      connectingCount: function () {
        return visibleSlots(this).filter(function (slot) { return slot.state === 'loading'; }).length;
      },
    },
    created: function () {
      this._previewPlayers = new Map();
      this._previewRequests = new Map();
      this._previewCompatibilityLeases = new Map();
      this._previewReconnectTimers = new Map();
      this._previewGenerations = Array(25).fill(0);
      this._previewClosed = false;
      this._previewBulkGeneration = 0;
      this._previewListController = null;
      this._previewSettingsController = null;
      this._previewHiddenTimer = null;
      this._previewCatalogTimer = null;
      this._previewCatalogStarted = false;
      this._previewSuspendedSlots = new Map();
    },
    mounted: function () {
      var vm = this;
      this._previewPageHide = function () {
        root.clearTimeout(vm._previewCatalogTimer);
        vm.stopAll();
      };
      this._previewSessionExpired = function () {
        vm._previewClosed = true;
        root.clearTimeout(vm._previewCatalogTimer);
        if (vm._previewListController) vm._previewListController.abort();
        if (vm._previewSettingsController) vm._previewSettingsController.abort();
        vm.stopAll();
      };
      root.addEventListener('pagehide', this._previewPageHide);
      root.addEventListener('platform:session-expired', this._previewSessionExpired);
      this._previewVisibility = function () {
        root.clearTimeout(vm._previewHiddenTimer);
        vm._previewHiddenTimer = null;
        if (root.document && root.document.hidden) {
          root.clearTimeout(vm._previewCatalogTimer);
          vm._previewHiddenTimer = root.setTimeout(function () {
            vm._previewHiddenTimer = null;
            if (!vm._previewClosed && root.document.hidden) vm.suspendHiddenPlayback();
          }, 30000);
        } else {
          vm.resumeVisiblePlayback();
          if ((analysisPreview || compatibilityAllowed) && vm._previewCatalogStarted) vm.loadDevices(true);
        }
      };
      if (root.document && root.document.addEventListener) root.document.addEventListener('visibilitychange', this._previewVisibility);
      this._previewVisibility();
      this.loadDevices();
      this._previewCatalogStarted = true;
      if (compatibilityAllowed) this.loadCompatibilitySettings();
    },
    beforeDestroy: function () {
      this._previewClosed = true;
      if (this._previewListController) this._previewListController.abort();
      if (this._previewSettingsController) this._previewSettingsController.abort();
      root.removeEventListener('pagehide', this._previewPageHide);
      root.removeEventListener('platform:session-expired', this._previewSessionExpired);
      if (root.document && root.document.removeEventListener) root.document.removeEventListener('visibilitychange', this._previewVisibility);
      root.clearTimeout(this._previewHiddenTimer);
      root.clearTimeout(this._previewCatalogTimer);
      this.stopAll();
    },
    methods: {
      suspendHiddenPlayback: function () {
        this._previewBulkGeneration++;
        this.bulkPlaying = false;
        for (var index = 0; index < this.layout; index++) {
          var slot = this.slots[index];
          if (!slot.device || slot.state === 'error' || slot.state === 'suspended') continue;
          var saved = { device: slot.device, compatibility: slot.compatibilityAttempted, generation: null };
          this.stopSlot(index);
          saved.generation = this._previewGenerations[index];
          this._previewSuspendedSlots.set(index, saved);
          this.$set(this.slots, index, Object.assign(emptySlot(index), { device: saved.device, state: 'suspended', message: '页面在后台，已暂停播放；返回页面后自动恢复' }));
        }
      },
      resumeVisiblePlayback: async function () {
        if (this._previewClosed || root.document && root.document.hidden) return;
        var vm = this, pending = Array.from(this._previewSuspendedSlots.entries()), next = 0;
        async function worker() {
          while (next < pending.length && !vm._previewClosed && !(root.document && root.document.hidden)) {
            var entry = pending[next++], index = entry[0], saved = entry[1];
            if (index >= vm.layout || vm._previewSuspendedSlots.get(index) !== saved || vm._previewGenerations[index] !== saved.generation) continue;
            vm._previewSuspendedSlots.delete(index);
            await vm.startSlot(index, saved.device, saved.compatibility);
          }
        }
        await Promise.all(Array.from({ length: Math.min(4, pending.length) }, worker));
      },
      loadCompatibilitySettings: async function (save) {
        if (!compatibilityAllowed || this._previewClosed || this.compatSaving) return;
        if (this._previewSettingsController) this._previewSettingsController.abort();
        var controller = new AbortController(), vm = this;
        this._previewSettingsController = controller;
        this.compatSaving = !!save; this.compatSettingsError = '';
        var timeout = root.setTimeout(function () { controller.abort(); }, 10000);
        try {
          var options = save ? { body: { max_streams: Number(this.compatLimit) } } : {};
          var result = await this.api('compat/settings', controller, options);
          if (this._previewClosed || this._previewSettingsController !== controller) return;
          if (!result.data || !Number.isInteger(result.data.max_streams)) throw new Error('转码设置返回异常');
          this.compatSettings = result.data;
          this.compatLimit = result.data.max_streams;
          if (save) this.statusMessage = '兼容转码上限已保存为 ' + this.compatLimit + ' 路；正在播放的画面继续播放';
        } catch (error) {
          if (!vm._previewClosed && vm._previewSettingsController === controller) vm.compatSettingsError = error.name === 'AbortError' ? '转码设置请求超时，请重试' : error.message;
        } finally {
          root.clearTimeout(timeout);
          if (this._previewSettingsController === controller) { this._previewSettingsController = null; this.compatSaving = false; }
        }
      },
      saveCompatibilitySettings: function () { return this.loadCompatibilitySettings(true); },
      api: async function (path, controller, options) {
        options = options || {};
        var url = apiBase() + apiPrefix + path;
        var authTicket = root.AiMonitorSession ? root.AiMonitorSession.begin(url) : null;
        var request = {
          headers: { Authorization: 'Bearer ' + token(this) },
          signal: controller.signal, cache: 'no-store',
        };
        if (options.body) { request.method = 'POST'; request.headers['Content-Type'] = 'application/json'; request.body = JSON.stringify(options.body); }
        if (options.keepalive) request.keepalive = true;
        var response = await root.fetch(url, request);
        if (response.status === 401 || response.status === 422) {
          var failure = null;
          try { failure = await response.json(); } catch (_) {}
          if (root.AiMonitorSession) root.AiMonitorSession.check(response, failure, authTicket, url);
          throw new Error('登录已失效，请重新登录');
        }
        if (!response.ok) { var httpError = new Error('请求失败（' + response.status + '）'); httpError.apiStatus = response.status; throw httpError; }
        var result = await response.json();
        if (root.AiMonitorSession) root.AiMonitorSession.check(response, result, authTicket, url);
        if (options.allowPrepare && result.code === 409 && result.data && result.data.needs_prepare) return result;
        if (result.code !== 200 && !(options.allowPending && result.code === 202)) { var apiError = new Error(result.msg || '获取播放地址失败'); apiError.apiCode = result.code; throw apiError; }
        return result;
      },
      releaseCompatibilityLease: function (lease) {
        if (!lease || lease.released) return;
        lease.released = true;
        root.clearTimeout(lease.timer);
        root.clearTimeout(lease.requestTimeout);
        if (lease.controller) lease.controller.abort();
        this.api('compat/release', new AbortController(), { body: { em_id: lease.deviceId, lease_id: lease.leaseId }, keepalive: true }).catch(function () { /* Server TTL bounds abandoned leases. */ });
      },
      releaseCompatibility: function (index) {
        var lease = this._previewCompatibilityLeases.get(index);
        this._previewCompatibilityLeases.delete(index);
        this.releaseCompatibilityLease(lease);
      },
      keepCompatibilityAlive: function (index, generation, lease) {
        var vm = this;
        lease.timer = root.setTimeout(async function () {
          lease.timer = null;
          if (vm._previewClosed || generation !== vm._previewGenerations[index] || vm._previewCompatibilityLeases.get(index) !== lease) return;
          var controller = new AbortController(); lease.controller = controller;
          var timeout = root.setTimeout(function () { controller.abort(); }, 10000);
          lease.requestTimeout = timeout;
          try {
            await vm.api('compat/keepalive', controller, { body: { em_id: lease.deviceId, lease_id: lease.leaseId } });
            if (!vm._previewClosed && generation === vm._previewGenerations[index] && vm._previewCompatibilityLeases.get(index) === lease) vm.keepCompatibilityAlive(index, generation, lease);
          } catch (error) {
            if (!lease.released && !vm._previewClosed && generation === vm._previewGenerations[index]) vm.failSlot(index, generation, '兼容预览已失效，点击重试');
          } finally {
            root.clearTimeout(timeout);
            if (lease.requestTimeout === timeout) lease.requestTimeout = null;
            if (lease.controller === controller) lease.controller = null;
          }
        }, 30000);
      },
      compatibilityDelay: function (controller, delay) {
        return new Promise(function (resolve, reject) {
          var timer;
          function aborted() { root.clearTimeout(timer); controller.signal.removeEventListener('abort', aborted); var error = new Error('Compatibility request aborted'); error.name = 'AbortError'; reject(error); }
          if (controller.signal.aborted) { aborted(); return; }
          controller.signal.addEventListener('abort', aborted, { once: true });
          timer = root.setTimeout(function () { controller.signal.removeEventListener('abort', aborted); resolve(); }, delay);
        });
      },
      compatibilityPlay: async function (device, controller) {
        if (device.source_mode === 'hik-platform' || device.needs_prepare) {
          await this.preparePreviewSource(device, controller);
        }
        var waited = 0;
        while (!controller.signal.aborted) {
          var result = await this.api('compat/play', controller, { body: { em_id: device.id }, allowPending: true });
          if (result.code === 200) return result;
          if (waited >= 25000) throw new Error('兼容预览准备超时，点击重试');
          var delay = Math.min(5000, Math.max(1000, Number(result.retry_after_ms) || 1000), 25000 - waited);
          await this.compatibilityDelay(controller, delay); waited += delay;
        }
        var error = new Error('Compatibility request aborted'); error.name = 'AbortError'; throw error;
      },
      preparePreviewSource: async function (device, controller) {
        var prepared;
        do {
          prepared = await this.api('prepare', controller, { body: { em_id: device.id }, allowPending: true });
          if (prepared.code === 202) await this.compatibilityDelay(controller, 1000);
        } while (prepared.code === 202 && !controller.signal.aborted);
        if (prepared.code === 200) { device.needs_prepare = false; device.source_mode = prepared.data && prepared.data.source_mode || device.source_mode || ''; }
      },
      previewPlay: async function (device, controller) {
        var prepared = compatibilityAllowed && (device.needs_prepare || device.source_mode === 'hik-platform');
        if (prepared) {
          await this.preparePreviewSource(device, controller);
        }
        var waited = 0;
        while (!controller.signal.aborted) {
          var result = await this.api('play?em_id=' + encodeURIComponent(device.id), controller, { allowPending: true, allowPrepare: compatibilityAllowed });
          if (result.code === 200) return result;
          if (result.code === 409 && !prepared) {
            await this.preparePreviewSource(device, controller);
            prepared = true;
            continue;
          }
          if (waited >= 25000) throw new Error('转发流视频轨仍未就绪，请检查摄像头或录像机的视频输出后重试');
          var delay = Math.min(5000, Math.max(1000, Number(result.retry_after_ms) || 2000), 25000 - waited);
          await this.compatibilityDelay(controller, delay); waited += delay;
        }
        var error = new Error('Preview request aborted'); error.name = 'AbortError'; throw error;
      },
      retryConnection: function (index, generation, message, diagnostics) {
        if (this._previewClosed || generation !== this._previewGenerations[index]) return false;
        var slot = this.slots[index];
        if (!slot.device || slot.connectionRetries >= 2) return false;
        slot.connectionRetries++;
        var pending = this._previewRequests.get(index);
        if (pending) { root.clearTimeout(pending._previewTimeout); pending.abort(); this._previewRequests.delete(index); }
        this.releasePlayer(index);
        this.releaseCompatibility(index);
        var nextGeneration = ++this._previewGenerations[index], vm = this;
        slot.state = 'loading'; slot.message = message.replace(/，点击重试$/, '') + '，正在重连（' + slot.connectionRetries + '/2）'; slot.diagnostics = diagnostics || null;
        var timer = root.setTimeout(function () {
          vm._previewReconnectTimers.delete(index);
          if (!vm._previewClosed && nextGeneration === vm._previewGenerations[index] && index < vm.layout) {
            vm.connectSlot(index, slot.device, nextGeneration, slot.compatibilityAttempted);
          }
        }, slot.connectionRetries === 1 ? 2000 : 6000);
        this._previewReconnectTimers.set(index, timer);
        return true;
      },
      handlePlaybackFailure: function (index, generation, message, diagnostics, codec) {
        if (this._previewClosed || generation !== this._previewGenerations[index]) return;
        var slot = this.slots[index], hint = diagnostics && diagnostics.compatibilityFallback;
        if (diagnostics && (['websocket', 'video-track-pending', 'connection-timeout'].indexOf(diagnostics.stage) >= 0
            || (analysisPreview || compatibilityAllowed) && diagnostics.mediaErrorCode === 2)
            && this.retryConnection(index, generation, message, diagnostics)) return;
        var hevc = /^(H\.?265|HEVC)$/i.test(String(codec || '')) || hint && hint.codec === 'H265';
        var decode = diagnostics && (diagnostics.mediaErrorCode === 3 || diagnostics.mediaErrorCode === 4);
        var compatibleFailure = hint ? hint.eligible : decode;
        if (compatibilityAllowed && hevc && compatibleFailure && !slot.compatibilityAttempted) {
          slot.sourceCodec = 'H265';
          slot.compatibilityAttempted = true; slot.compatibility = 'preparing';
          slot.state = 'loading'; slot.message = '正在准备兼容预览…'; slot.diagnostics = diagnostics || null;
          this.releasePlayer(index);
          this.connectSlot(index, slot.device, generation, true);
          return;
        }
        this.failSlot(index, generation, slot.compatibilityAttempted ? '兼容预览失败，点击重试' : message, diagnostics);
      },
      canPlayCompatibility: function (slot) {
        return compatibilityAllowed && slot.device && /^(H\.?265|HEVC)$/i.test(String(slot.sourceCodec || slot.device.codec || ''))
          && slot.compatibility !== 'preparing' && slot.compatibility !== 'active';
      },
      playCompatibility: function (index) {
        var slot = this.slots[index];
        if (this.canPlayCompatibility(slot)) return this.startSlot(index, slot.device, true);
      },
      scheduleCatalogRefresh: function () {
        root.clearTimeout(this._previewCatalogTimer);
        if ((!analysisPreview && !compatibilityAllowed) || this._previewClosed || root.document && root.document.hidden) return;
        var vm = this;
        this._previewCatalogTimer = root.setTimeout(function () { vm.loadDevices(true); }, 15000);
      },
      loadDevices: async function (quiet) {
        quiet = quiet === true;
        if (this._previewClosed || quiet && (this._previewListController || root.document && root.document.hidden)) return;
        root.clearTimeout(this._previewCatalogTimer);
        if (this._previewListController) this._previewListController.abort();
        var controller = new AbortController();
        this._previewListController = controller;
        if (!quiet) {
          this.loading = true;
          this.listError = '';
        }
        if (!quiet && compatibilityAllowed && this.compatSettings) this.loadCompatibilitySettings();
        var timeout = root.setTimeout(function () { controller.abort(); }, 12000);
        try {
          var result = await this.api('devices', controller);
          if (this._previewClosed || this._previewListController !== controller) return;
          this.devices = result.data || [];
          var present = new Map(this.devices.map(function (d) { return [d.id, d]; })), removed = 0;
          for (var i = 0; i < this.layout; i++) {
            var slot = this.slots[i];
            if (!slot.device) continue;
            var device = present.get(slot.device.id);
            if (!device) { this.stopSlot(i); removed++; }
            else if (analysisPreview || compatibilityAllowed) {
              // Refresh captions and retry metadata without replacing the video element or player.
              var previous = slot.device;
              slot.device = device;
              var suspended = this._previewSuspendedSlots.get(i);
              if (suspended) suspended.device = device;
              if (compatibilityAllowed && device.available && slot.state === 'error'
                  && (device.source_mode === 'recorder' || device.source_mode === 'camera-direct')
                  && ((previous.source_online === false && device.source_online === true)
                      || (previous.media_live === false && device.media_live === true))) {
                this.startSlot(i, device, slot.compatibilityAttempted);
              }
            }
          }
          if (removed) this.statusMessage = '设备列表已更新，已停止 ' + removed + ' 个已删除或变更的监控点';
          var available = new Set(this.devices.filter(function (d) { return d.available; }).map(function (d) { return d.id; }));
          this.checkedIds = this.checkedIds.filter(function (id) { return available.has(id); });
          this.listError = result.media_status_known ? '' : (profile.mediaStatusUnknownHint || '流媒体状态暂时不可获取，可选择监控点尝试播放');
        } catch (error) {
          if (!quiet && !this._previewClosed && this._previewListController === controller) {
            this.listError = error.name === 'AbortError' ? heading + '加载超时，请刷新重试' : error.message;
          }
        } finally {
          root.clearTimeout(timeout);
          if (this._previewListController === controller) {
            this._previewListController = null;
            this.loading = false;
            this.scheduleCatalogRefresh();
          }
        }
      },
      changeLayout: function (count) {
        count = Number(count);
        if (layouts.indexOf(count) < 0) return;
        if (count !== this.layout) { this._previewBulkGeneration++; this.bulkPlaying = false; }
        for (var i = count; i < this.layout; i++) this.stopSlot(i);
        this.layout = count;
        this.maximizedSlot = null;
        if (this.activeSlot >= count) this.activeSlot = 0;
        this.statusMessage = '';
      },
      toggleChecked: function (device, checked) {
        if (!device.available) return;
        this.checkedIds = this.checkedIds.filter(function (id) { return id !== device.id; });
        if (checked) this.checkedIds.push(device.id);
      },
      selectVisible: function () {
        this.checkedIds = this.groups.reduce(function (ids, group) {
          return ids.concat(group.devices.filter(function (d) { return d.available && (!compatibilityAllowed || d.source_online !== false); }).map(function (d) { return d.id; }));
        }, []);
      },
      playChecked: async function () {
        if (this.bulkPlaying) return;
        var vm = this;
        var chosen = this.checkedIds.map(function (id) { return vm.devices.find(function (d) { return d.id === id; }); })
          .filter(function (d) { return d && d.available; });
        if (!chosen.length) { this.statusMessage = '请先勾选' + heading; return; }
        if (chosen.length > this.layout) {
          this.statusMessage = '已选择 ' + chosen.length + ' 路，请切换到足够的分屏或减少选择';
          return;
        }
        this.bulkPlaying = true;
        var run = ++this._previewBulkGeneration;
        this.statusMessage = '';
        // A new batch replaces the visible selection; surplus old windows
        // must not retain readers or consume compatibility jobs silently.
        for (var extra = chosen.length; extra < this.layout; extra++) this.stopSlot(extra);
        var next = 0;
        var count = this.layout;
        // Limit address lookups to four concurrent requests; streams themselves remain independent.
        async function worker() {
          while (next < chosen.length && !vm._previewClosed && vm.layout === count && vm._previewBulkGeneration === run) {
            var index = next++;
            await vm.startSlot(index, chosen[index]);
          }
        }
        try {
          await Promise.all(Array.from({ length: Math.min(4, chosen.length) }, worker));
        } finally {
          if (this._previewBulkGeneration === run) this.bulkPlaying = false;
        }
      },
      playDevice: function (device) {
        if (!device.available) { this.statusMessage = device.reason; return; }
        this._previewBulkGeneration++;
        this.bulkPlaying = false;
        var index = this.activeSlot;
        this.startSlot(index, device);
        var empty = visibleSlots(this).find(function (slot) { return !slot.device; });
        if (empty) this.activeSlot = empty.index;
      },
      releasePlayer: function (index) {
        var player = this._previewPlayers.get(index);
        if (!player) return;
        this._previewPlayers.delete(index);
        root.clearTimeout(player.timeout);
        root.clearTimeout(player.bufferingNotice);
        root.clearTimeout(player.recoveryReset);
        player.events.forEach(function (event) { player.video.removeEventListener(event[0], event[1]); });
        if (player.transport) player.transport.destroy();
        player.video.pause();
        player.video.removeAttribute('src');
        player.video.load();
      },
      stopSlot: function (index) {
        this._previewSuspendedSlots.delete(index);
        this._previewGenerations[index]++;
        root.clearTimeout(this._previewReconnectTimers.get(index));
        this._previewReconnectTimers.delete(index);
        var pending = this._previewRequests.get(index);
        if (pending) { root.clearTimeout(pending._previewTimeout); pending.abort(); this._previewRequests.delete(index); }
        this.releasePlayer(index);
        this.releaseCompatibility(index);
        this.$set(this.slots, index, emptySlot(index));
      },
      stopAll: function () {
        this._previewBulkGeneration++;
        this.bulkPlaying = false;
        for (var i = 0; i < 25; i++) this.stopSlot(i);
        this.maximizedSlot = null;
        this.statusMessage = '';
      },
      failSlot: function (index, generation, message, diagnostics) {
        if (this._previewClosed || generation !== this._previewGenerations[index]) return;
        var video = this.$refs['video-' + index];
        if (!diagnostics && video && video.getAttribute && this._previewPlayers.has(index)) {
          try {
            var value = video.getAttribute('data-fmp4-diagnostics') || '';
            if (value && value.length < 8192) diagnostics = JSON.parse(value);
          } catch (error) { /* Diagnostic absence must not change playback cleanup. */ }
        }
        this.releasePlayer(index);
        this.releaseCompatibility(index);
        this.slots[index].state = 'error';
        this.slots[index].message = message;
        this.slots[index].diagnostics = diagnostics || null;
        if (this.slots[index].compatibilityAttempted) this.slots[index].compatibility = 'failed';
      },
      startSlot: async function (index, device, compatibility) {
        if (this._previewClosed || index >= this.layout) return;
        compatibility = !!compatibility && compatibilityAllowed;
        var sourceCodec = compatibility ? this.slots[index].sourceCodec || device.codec || '' : device.codec || '';
        this.stopSlot(index);
        this.$set(this.slots, index, { index: index, device: device, state: 'loading', message: compatibility ? '正在准备兼容预览…' : '正在连接视频…', diagnostics: null,
          compatibility: compatibility ? 'preparing' : '', compatibilityAttempted: compatibility, sourceCodec: sourceCodec, connectionRetries: 0 });
        return this.connectSlot(index, device, this._previewGenerations[index], compatibility);
      },
      connectSlot: async function (index, device, generation, compatibility) {
        if (this._previewClosed || generation !== this._previewGenerations[index] || index >= this.layout) return;
        var vm = this;
        var controller = new AbortController();
        this._previewRequests.set(index, controller);
        var requestTimeout = root.setTimeout(function () { controller.abort(); }, 25000);
        controller._previewTimeout = requestTimeout;
        try {
          var result = compatibility ? await this.compatibilityPlay(device, controller) : await this.previewPlay(device, controller);
          var data = result.data || {};
          if (!compatibility && data.source_mode) device.source_mode = data.source_mode;
          if (!compatibility && generation === this._previewGenerations[index]) this.slots[index].sourceCodec = data.codec || device.codec || '';
          var leaseId = result.lease_id || data.lease_id;
          var lease = compatibility && typeof leaseId === 'string' && leaseId ? { deviceId: device.id, leaseId: leaseId, timer: null, controller: null, released: false } : null;
          if (this._previewClosed || generation !== this._previewGenerations[index] || index >= this.layout) { this.releaseCompatibilityLease(lease); return; }
          if (compatibility) {
            if (lease) this._previewCompatibilityLeases.set(index, lease);
            if (!lease || !/^(H\.?264|AVC)$/i.test(String(data.codec || '')) || (data.id != null && String(data.id) !== String(device.id))) throw new Error('未取得当前设备的兼容视频');
            this.slots[index].compatibility = 'active';
            this.slots[index].message = '正在连接兼容预览…';
            this.keepCompatibilityAlive(index, generation, lease);
          }
          var keyframeSeconds = Number(result.data && result.data.keyframe_interval_ms) / 1000;
          var startupError = keyframeSeconds > 15 && Number.isFinite(keyframeSeconds)
            ? '视频加载超时，关键帧间隔约 ' + Math.round(keyframeSeconds) + ' 秒；请将摄像头 I 帧间隔调整为 1–2 秒后重试'
            : '视频加载超时，点击重试';
          var url = result.play_url || data.play_url || result.flv_url;
          if (root.AiMonitorTransport) url = root.AiMonitorTransport.normalize(url);
          if (!/^https?:\/\//i.test(url || '')) throw new Error('流媒体未返回有效播放地址');
          if (root.location.protocol === 'https:' && url.indexOf('http:') === 0) {
            throw new Error('当前页面为 HTTPS，请配置 HTTPS 流媒体播放地址');
          }
          if (root.AiMonitorTransport && !await root.AiMonitorTransport.ensureMediaSession()) {
            throw new Error('媒体访问需要有效登录，请刷新或重新登录');
          }
          await this.$nextTick();
          if (this._previewClosed || generation !== this._previewGenerations[index]) return;
          var video = this.$refs['video-' + index];
          if (!video) { this.failSlot(index, generation, '播放窗口尚未就绪，点击重试'); return; }
          var player = { video: video, timeout: null, bufferingNotice: null, recoveryReset: null, events: [] };
          function listen(name, callback) {
            video.addEventListener(name, callback);
            player.events.push([name, callback]);
          }
          function current() { return !vm._previewClosed && generation === vm._previewGenerations[index] && vm._previewPlayers.get(index) === player; }
          listen('playing', function () {
            if (!current()) return;
            root.clearTimeout(player.timeout);
            player.timeout = null;
            root.clearTimeout(player.bufferingNotice);
            player.bufferingNotice = null;
            vm.slots[index].state = 'playing'; vm.slots[index].message = '';
            if (analysisPreview && vm.slots[index].connectionRetries && !player.recoveryReset) {
              player.recoveryReset = root.setTimeout(function () {
                player.recoveryReset = null;
                if (current()) vm.slots[index].connectionRetries = 0;
              }, 30000);
            }
          });
          listen('waiting', function () {
            if (!current()) return;
            root.clearTimeout(player.recoveryReset);
            player.recoveryReset = null;
            // Short decode/seek waits should not cover a healthy video with an overlay.
            // Keep the first interruption deadline: repeated waiting is not recovery.
            if (!player.bufferingNotice) player.bufferingNotice = root.setTimeout(function () {
              player.bufferingNotice = null;
              if (!current()) return;
              vm.slots[index].state = 'loading'; vm.slots[index].message = '视频缓冲中…';
            }, 650);
            if (!player.timeout) player.timeout = root.setTimeout(function () {
              vm.handlePlaybackFailure(index, generation, '视频连接中断', { stage: 'connection-timeout' });
            }, 15000);
          });
          listen('error', function () {
            if (!current()) return;
            var code = video.error && video.error.code;
            var codec = (result.data && result.data.codec) || device.codec;
            var message = code === 3 || code === 4
              ? (codec === 'H265' ? 'H.265 视频播放失败，请检查码流封装与当前播放环境' : '视频播放失败，请检查转发流与当前播放环境')
              : '视频连接失败，请检查流媒体服务后重试';
            var stats = player.transport && player.transport.getStats ? player.transport.getStats() : null;
            var diagnostics = stats && stats.diagnostics || { mediaErrorCode: code };
            if (diagnostics.mediaErrorCode == null) diagnostics.mediaErrorCode = code;
            vm.handlePlaybackFailure(index, generation, message, diagnostics, codec);
          });
          listen('ended', function () {
            if (!current()) return;
            var message = analysisPreview ? '分析视频连接中断' : '实时视频连接中断';
            if ((analysisPreview || compatibilityAllowed)
                && vm.retryConnection(index, generation, message, { stage: 'stream-ended' })) return;
            vm.failSlot(index, generation, '转发流已结束，点击重试');
          });
          this._previewPlayers.set(index, player);
          player.timeout = root.setTimeout(function () { vm.handlePlaybackFailure(index, generation, startupError, { stage: 'connection-timeout' }); }, 15000);
          video.muted = true;
          player.transport = root.AiMonitorFmp4Player.create(video, url, function (message, diagnostics) {
            if (current()) vm.handlePlaybackFailure(index, generation, message, diagnostics, (result.data && result.data.codec) || device.codec);
          });
          if (!current()) { if (player.transport) player.transport.destroy(); return; }
          var playPromise = video.play();
          if (playPromise) playPromise.catch(function (error) {
            if (error.name === 'AbortError' || !current()) return;
            vm.failSlot(index, generation, error.name === 'NotAllowedError' ? '浏览器阻止自动播放，点击重试' : '视频播放失败，请检查编码和流媒体服务');
          });
        } catch (error) {
          if ((error.apiCode === 503 || error.apiStatus >= 500 || analysisPreview && error.apiCode === 409)
              && this.retryConnection(index, generation, error.message, { stage: 'api-unavailable' })) return;
          if (this._previewRequests.get(index) === controller) this.failSlot(index, generation, error.name === 'AbortError'
            ? compatibility ? '兼容预览准备超时，点击重试' : '视频轨或播放地址准备超时，请检查视频输出后重试' : error.message);
        } finally {
          root.clearTimeout(requestTimeout);
          if (this._previewRequests.get(index) === controller) this._previewRequests.delete(index);
        }
      },
      toggleMaximized: function (index) {
        this.activeSlot = index;
        this.maximizedSlot = this.maximizedSlot === index ? null : index;
      },
      fullscreen: function () {
        var grid = this.$refs.grid;
        if (document.fullscreenElement) document.exitFullscreen();
        else if (grid && grid.requestFullscreen) {
          var vm = this;
          grid.requestFullscreen().catch(function () { vm.statusMessage = '浏览器未允许全屏显示'; });
        }
      },
    },
    render: function (h) {
      var vm = this;
      function button(text, handler, disabled, extra) {
        return h('button', {
          class: ['preview-button', extra || ''], attrs: { type: 'button', disabled: !!disabled },
          on: { click: handler },
        }, text);
      }
      var deviceGroups = this.groups.map(function (group) {
        return h('details', { key: group.key, class: 'preview-device-group', attrs: { open: '' } }, [
          h('summary', [group.name, h('span', { class: 'preview-group-count' }, String(group.devices.length))]),
          h('ul', group.devices.map(function (device) {
            return h('li', { key: device.id, class: { 'is-unavailable': !device.available || device.source_online === false } }, [
              h('label', { class: 'preview-check', attrs: { title: '选择 ' + device.name } }, [
                h('input', { attrs: { type: 'checkbox', disabled: !device.available, 'aria-label': '选择 ' + device.name },
                  domProps: { checked: vm.checkedIds.indexOf(device.id) >= 0 },
                  on: { change: function (event) { vm.toggleChecked(device, event.target.checked); } } }),
              ]),
              h('button', { class: 'preview-device', attrs: {
                type: 'button', disabled: !device.available, title: device.reason || ('在所选窗口播放 ' + device.name + (taskText(device) ? '\n' + taskText(device, true) : '')),
                'data-device-id': device.id,
              }, on: { click: function () { vm.playDevice(device); } } }, [
                h('span', { class: 'preview-device-dot' }),
                profile.showTasks ? h('span', { class: 'preview-device-description' }, [
                  h('span', { class: 'preview-device-name' }, device.name),
                  h('span', { class: 'preview-task-summary', attrs: { title: taskText(device, true) } }, taskText(device) || '暂无算法任务'),
                ]) : h('span', { class: 'preview-device-name' }, (device.channel ? String(device.channel).padStart(2, '0') + ' · ' : '') + device.name),
                h('small', (device.source_mode === 'camera-direct' ? '直连 ' : '') + (device.source_online === false ? '离线' : device.codec || (device.online === false ? '离线' : ''))),
              ]),
            ]);
          })),
        ]);
      });
      var tiles = visibleSlots(this).map(function (slot) {
        var index = slot.index;
        var controls = slot.device ? [
          vm.canPlayCompatibility(slot) ? button('兼容播放', function (event) { event.stopPropagation(); vm.playCompatibility(index); }, false, 'preview-small') : null,
          slot.state === 'error' ? button('重试', function (event) { event.stopPropagation(); vm.startSlot(index, slot.device); }, false, 'preview-small') : null,
          button('停止', function (event) { event.stopPropagation(); vm.stopSlot(index); }, false, 'preview-small'),
        ] : [];
        return h('section', {
          key: index, class: ['preview-tile', { 'is-selected': vm.activeSlot === index, 'is-maximized': vm.maximizedSlot === index }],
          style: vm.maximizedSlot !== null && vm.maximizedSlot !== index ? { display: 'none' } : {},
          attrs: { 'data-slot': index, tabindex: 0, 'aria-label': (profile.windowLabel || '预览窗口') + ' ' + (index + 1) },
          on: { click: function () { vm.activeSlot = index; }, dblclick: function () { vm.toggleMaximized(index); },
            keydown: function (event) { if (event.key === 'Enter') vm.toggleMaximized(index); } },
        }, [
          h('div', { class: 'preview-tile-header' }, [
            h('span', { class: 'preview-window-number' }, String(index + 1)),
            h('span', { class: 'preview-tile-name', attrs: { title: slot.device ? slot.device.name + (taskText(slot.device) ? '\n' + taskText(slot.device, true) : '') : '' } }, slot.device ? slot.device.name : '未选择' + heading),
            h('span', { class: 'preview-tile-controls' }, controls),
          ]),
          h('video', { ref: 'video-' + index, key: 'video-' + index, class: 'preview-video',
            attrs: { autoplay: '', muted: '', playsinline: '', preload: 'none', 'data-preview-device-id': slot.device ? slot.device.id : null }, domProps: { muted: true } }),
          slot.state === 'playing' ? h('span', { class: 'preview-live' }, (slot.compatibility === 'active' ? '兼容预览' : profile.liveLabel || '直播') + (slot.device && slot.device.source_mode === 'camera-direct' ? ' · 直连' : ''))
            : h('div', { class: ['preview-overlay', 'preview-state-' + slot.state], attrs: { role: 'status' } }, [
              h('span', { class: 'preview-status-icon' }, slot.state === 'empty' ? '▷' : slot.state === 'error' ? '!' : '◌'),
              h('span', slot.state === 'empty' ? '点击' + heading + '在此窗口播放' : slot.message),
              slot.state === 'error' && slot.diagnostics ? h('details', { class: 'preview-diagnostics',
                style: { maxWidth: 'calc(100% - 24px)', fontSize: '11px', textAlign: 'left' } }, [
                h('summary', { style: { cursor: 'pointer', textAlign: 'center' } }, '播放诊断'),
                h('pre', { style: { maxHeight: '140px', overflow: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: '6px 0 0' } }, diagnosticText(slot.diagnostics)),
              ]) : null,
            ]),
        ]);
      });
      var side = h('aside', { class: 'preview-sidebar' }, [
        h('div', { class: 'preview-sidebar-heading' }, [h('strong', heading), button('刷新', this.loadDevices, this.loading)]),
        h('input', { class: 'preview-search', attrs: { placeholder: profile.searchPlaceholder || '搜索监控点或录像机', 'aria-label': '搜索' + heading },
          domProps: { value: this.search }, on: { input: function (event) { vm.search = event.target.value; } } }),
        h('div', { class: 'preview-selection-tools' }, [button('选择筛选结果', this.selectVisible),
          button('清空选择', function () { vm.checkedIds = []; }), h('span', '已选 ' + this.checkedIds.length + ' 路')]),
        this.listError ? h('div', { class: 'preview-list-error', attrs: { role: 'status' } }, this.listError) : null,
        h('div', { class: 'preview-devices' }, this.loading ? [h('p', '正在加载监控点…')] : deviceGroups.length ? deviceGroups
          : [h('p', this.search ? '未找到匹配的' + heading : (profile.emptySources || '暂无监控点'))]),
        h('div', { class: 'preview-sidebar-footer' }, [
          button(this.bulkPlaying ? '正在连接…' : '播放所选', this.playChecked, this.bulkPlaying || !this.checkedIds.length, 'preview-primary'),
          h('p', profile.selectionHint || '单击窗口后选择监控点；勾选多路后点击播放所选。'),
        ]),
      ]);
      var toolbar = h('div', { key: 'preview-toolbar', class: 'preview-toolbar' }, [
        h('div', { class: 'preview-layout-controls', attrs: { 'aria-label': profile.layoutLabel || '预览分屏' } }, layouts.map(function (count) {
          return h('button', { key: count, class: ['preview-button', { 'preview-active': count === vm.layout }],
            attrs: { type: 'button', 'aria-pressed': count === vm.layout, 'data-layout': count },
            on: { click: function () { vm.changeLayout(count); } } }, count + ' 路');
        })),
        h('span', { class: 'preview-summary' }, '正在播放 ' + this.playingCount + ' / ' + this.layout + ' 路'
          + (this.connectingCount ? ' · 连接中 ' + this.connectingCount : '') + (this.errorCount ? ' · 异常 ' + this.errorCount : '') + ' · 当前窗口 ' + (this.activeSlot + 1)),
        compatibilityAllowed ? h('details', { class: 'preview-compat-settings', on: {
          toggle: function (event) { if (event.target.open) vm.loadCompatibilitySettings(); },
        } }, [
          h('summary', '兼容转码' + (this.compatSettings ? ' · 上限 ' + this.compatSettings.max_streams + ' 路' : '设置')),
          h('div', { class: 'preview-compat-settings-panel' }, [
            h('strong', 'H.264 兼容转码'),
            h('p', '限制同时转码的监控点数量；多个窗口播放同一监控点共用一路。'),
            this.compatSettings ? h('label', [
              h('span', '最大路数'), h('select', { attrs: { 'aria-label': '兼容转码最大路数', disabled: !this.compatSettings.can_edit || this.compatSaving },
                domProps: { value: this.compatLimit }, on: { change: function (event) { vm.compatLimit = Number(event.target.value); } } },
              Array.from({ length: 8 }, function (_, i) { return h('option', { attrs: { value: i + 1 } }, (i + 1) + ' 路'); })),
            ]) : null,
            this.compatSettings && this.compatSettings.active_streams != null ? h('p', '当前占用 ' + this.compatSettings.active_streams + ' 路 · 调低上限保留已有播放') : null,
            this.compatSettingsError ? h('p', { class: 'preview-list-error', attrs: { role: 'status' } }, this.compatSettingsError) : null,
            h('div', { class: 'preview-compat-settings-actions' }, [
              button('刷新', function () { vm.loadCompatibilitySettings(); }, this.compatSaving),
              this.compatSettings && this.compatSettings.can_edit ? button(this.compatSaving ? '保存中…' : '保存', this.saveCompatibilitySettings, this.compatSaving, 'preview-primary') : null,
            ]),
          ]),
        ]) : null,
        this.maximizedSlot !== null ? button('返回分屏', function () { vm.maximizedSlot = null; }) : null,
        profile.temporaryAnalysisRoute ? button('临时分析', function () { vm.$router.push(profile.temporaryAnalysisRoute); }) : null,
        button('全屏', this.fullscreen), button('全部停止', this.stopAll, !this.occupiedCount),
      ]);
      return h('div', { class: ['stream-preview', profile.className || ''] }, [side, h('main', { class: 'preview-main' }, [
        toolbar,
        this.statusMessage ? h('div', { key: 'preview-notice', class: 'preview-notice', attrs: { role: 'status' } }, this.statusMessage) : null,
        // Sibling divs need stable keys: adding a notice must never replace the
        // grid and detach videos while their independent players keep running.
        h('div', { key: 'preview-grid', ref: 'grid', class: ['preview-grid', { 'preview-grid-maximized': this.maximizedSlot !== null }],
          style: { gridTemplateColumns: 'repeat(' + Math.sqrt(this.layout) + ', minmax(0, 1fr))',
            gridTemplateRows: 'repeat(' + Math.sqrt(this.layout) + ', minmax(0, 1fr))' },
          attrs: { 'data-layout': this.layout } }, tiles),
        h('div', { key: 'preview-bottom-hint', class: 'preview-bottom-hint' }, profile.bottomHint || '双击窗口放大 / 还原 · 视频默认静音 · 切换到更少分屏将停止移出的窗口'),
      ])]);
    },
    };
  }
  root.AiMonitorPreviewFactory = createPreview;
  root.AiMonitorStreamPreview = createPreview();
})(window);
