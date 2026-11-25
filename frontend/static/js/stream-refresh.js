/* 流媒体管理 (lmtgl) 刷新增强 v3
 *
 * 与 v2 的差别（v2 自作主张重发请求，可能与页面自身行为不一致）：
 *   1. 直接调用页面组件自己的 axioss() —— 与「查询」按钮 100% 同一条代码路径
 *   2. 通过监听 tableData 引用是否变化来判断结果，并区分三种状态：
 *        已刷新 · N 条 · 时间        数据变了
 *        已请求（数据未变）· N 条 · 时间   请求成功但内容与之前完全相同
 *        刷新失败 · 原因 · 时间        组件没找到或请求异常
 *      这样可以明确区分「按钮没生效」和「ZLK 本来就没有新数据」。
 *   3. 找不到组件时，兜底直接点击「查询」按钮。
 */
(function (root) {
  'use strict';

  var BUTTON_ID = 'stream-refresh-button';
  var SELECT_ID = 'stream-refresh-interval';
  var STATUS_ID = 'stream-refresh-status';
  var PLACEHOLDER_HINT = '监控点名称';
  var STORE_KEY = 'streamRefreshIntervalSec';
  var WAIT_TICKS = 30;      // 200ms × 30 = 6 秒
  var TICK_MS = 200;

  var timer = null;
  var running = false;

  function flatText(el) {
    return (el && el.textContent ? el.textContent : '').replace(/\s+/g, '');
  }

  function store(key, value) {
    try {
      if (value === null) root.localStorage.removeItem(key);
      else root.localStorage.setItem(key, value);
    } catch (error) { /* 忽略 */ }
  }

  function recall(key, fallback) {
    try {
      var value = root.localStorage.getItem(key);
      return value === null ? fallback : value;
    } catch (error) { return fallback; }
  }

  function stamp() {
    var now = new Date();
    function pad(n) { return (n < 10 ? '0' : '') + n; }
    return pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds());
  }

  function findFilterInput() {
    var inputs = document.querySelectorAll('input[placeholder]');
    var i;
    for (i = 0; i < inputs.length; i += 1) {
      if ((inputs[i].getAttribute('placeholder') || '').indexOf(PLACEHOLDER_HINT) !== -1) {
        return inputs[i];
      }
    }
    return null;
  }

  function buttonByText(scope, wanted) {
    if (!scope || !scope.querySelectorAll) return null;
    var buttons = scope.querySelectorAll('button');
    var i;
    for (i = 0; i < buttons.length; i += 1) {
      if (flatText(buttons[i]) === wanted) return buttons[i];
    }
    return null;
  }

  function findToolbar(anchor) {
    var node = anchor;
    var depth = 0;
    while (node && depth < 8) {
      if (buttonByText(node, '查询')) return node;
      node = node.parentElement;
      depth += 1;
    }
    return null;
  }

  /* 精确匹配 lmtgl 组件：只有它同时具备 axioss 方法与 tableData 数据 */
  function componentOf(el) {
    var node = el;
    while (node) {
      var vm = node.__vue__;
      if (vm && typeof vm.axioss === 'function' && vm.tableData !== undefined) return vm;
      node = node.parentElement;
    }
    return null;
  }

  function setStatus(text, color) {
    var node = document.getElementById(STATUS_ID);
    if (!node) return;
    node.textContent = text;
    node.style.color = color;
  }

  function stopTimer() {
    if (timer !== null) {
      root.clearInterval(timer);
      timer = null;
    }
  }

  function startTimer() {
    stopTimer();
    var select = document.getElementById(SELECT_ID);
    var seconds = select ? Number(select.value) || 0 : 0;
    if (!seconds) return;
    timer = root.setInterval(function () {
      if (!document.getElementById(BUTTON_ID)) { stopTimer(); return; }
      load(false);
    }, seconds * 1000);
  }

  function load(manual) {
    if (running) return;
    var anchor = findFilterInput();
    var button = document.getElementById(BUTTON_ID);
    var caption = button ? (button.querySelector('span') || button) : null;
    var release = function () {
      running = false;
      if (manual && button) {
        button.disabled = false;
        if (caption) caption.textContent = '刷新';
      }
    };

    if (manual && button) {
      button.disabled = true;
      if (caption) caption.textContent = '刷新中…';
    }

    var component = anchor ? componentOf(anchor) : null;
    if (!component) {
      var query = buttonByText(findToolbar(anchor), '查询');
      if (query) {
        query.click();
        setStatus('已转交「查询」· ' + stamp(), '#e6a23c');
      } else {
        setStatus('未找到页面组件 · ' + stamp(), '#f56c6c');
      }
      release();
      return;
    }

    running = true;
    var before = component.tableData;
    var settled = false;
    try {
      component.axioss();
    } catch (error) {
      setStatus('刷新失败 · 调用异常 · ' + stamp(), '#f56c6c');
      release();
      return;
    }

    var ticks = 0;
    var waiter = root.setInterval(function () {
      if (settled) return;
      ticks += 1;
      var current = component.tableData;
      var rows = current || [];
      if (current !== before) {
        settled = true;
        root.clearInterval(waiter);
        setStatus('已刷新 · ' + rows.length + ' 条 · ' + stamp(), '#67c23a');
        release();
      } else if (ticks >= WAIT_TICKS) {
        settled = true;
        root.clearInterval(waiter);
        setStatus('已请求（数据未变）· ' + rows.length + ' 条 · ' + stamp(), '#e6a23c');
        release();
      }
    }, TICK_MS);
  }

  function decorate() {
    if (document.getElementById(BUTTON_ID)) return;
    var anchor = findFilterInput();
    if (!anchor) return;
    var toolbar = findToolbar(anchor);
    if (!toolbar) return;
    var query = buttonByText(toolbar, '查询');
    if (!query || !query.parentNode) return;

    var button = document.createElement('button');
    button.id = BUTTON_ID;
    button.type = 'button';
    button.className = (query.className || '').replace('el-button--primary', 'el-button--info');
    button.setAttribute('title', '重新拉取 ZLMediaKit 当前流列表');
    var icon = document.createElement('i');
    icon.className = 'el-icon-refresh';
    var caption = document.createElement('span');
    caption.textContent = '刷新';
    button.appendChild(icon);
    button.appendChild(caption);
    button.addEventListener('click', function () { load(true); });

    var select = document.createElement('select');
    select.id = SELECT_ID;
    select.setAttribute('title', '自动刷新间隔');
    select.style.cssText = 'height:28px;line-height:28px;margin-left:8px;padding:0 6px;' +
      'border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#606266;' +
      'font-size:12px;vertical-align:middle;cursor:pointer;';
    [['0', '不自动刷新'], ['5', '每 5 秒'], ['10', '每 10 秒'], ['30', '每 30 秒']]
      .forEach(function (item) {
        var option = document.createElement('option');
        option.value = item[0];
        option.textContent = item[1];
        select.appendChild(option);
      });
    select.value = recall(STORE_KEY, '0');
    select.addEventListener('change', function () {
      store(STORE_KEY, select.value);
      startTimer();
      if (Number(select.value) > 0) load(false);
    });

    var status = document.createElement('span');
    status.id = STATUS_ID;
    status.style.cssText = 'margin-left:10px;font-size:12px;color:#909399;vertical-align:middle;';
    status.textContent = '';

    var anchorButton = buttonByText(toolbar, '新增') || query;
    var parent = anchorButton.parentNode;
    if (anchorButton.nextSibling) parent.insertBefore(button, anchorButton.nextSibling);
    else parent.appendChild(button);
    parent.insertBefore(select, button.nextSibling);
    parent.insertBefore(status, select.nextSibling);

    startTimer();
  }

  var pending = false;
  function schedule() {
    if (pending) return;
    pending = true;
    root.setTimeout(function () { pending = false; decorate(); }, 120);
  }

  function start() {
    decorate();
    var observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
}(window));
