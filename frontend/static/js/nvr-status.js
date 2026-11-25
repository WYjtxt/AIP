/* Periodically refresh only the online cells currently displayed on device pages. */
(function (root) {
  'use strict';
  var timer, generation = 0, interval = 15000;

  function route() {
    return (root.location.hash || '').split('?')[0].replace(/^#\/?|\/$/g, '');
  }
  function viewFor(page) {
    var app = root.document.getElementById('app');
    var router = app && app.__vue__ && app.__vue__.$router;
    var current = router && router.currentRoute;
    if (!current || current.path !== '/' + page) return null;
    var matched = current.matched || [];
    var leaf = matched.length && matched[matched.length - 1].instances;
    var pending = leaf && leaf.default ? [leaf.default] : [];
    while (pending.length) {
      var view = pending.pop();
      if (view._isDestroyed || view._inactive) continue;
      if (Array.isArray(view.tableData)
          && (page === 'sbtj' ? typeof view.synchros === 'function' : typeof view.handleLookDetail === 'function')) return view;
      (view.$children || []).forEach(function (child) { pending.push(child); });
    }
    return null;
  }
  function equipmentRows(view) {
    var table = view.$refs.singleTable;
    var tree = table && table.store && table.store.states.treeData || {};
    var visible = [];
    function visit(row) {
      visible.push(row);
      if (tree[row.id] && tree[row.id].expanded && Array.isArray(row.children)) row.children.forEach(visit);
    }
    view.tableData.forEach(visit);
    return visible;
  }
  function stillHere(page, view, epoch) {
    return epoch === generation && !root.document.hidden && page === route() && view === viewFor(page);
  }
  async function refreshRows(page, view, epoch, endpoint, rows, params) {
    var ids = Array.from(new Set(rows.map(function (row) { return row.id; })));
    for (var offset = 0; offset < ids.length && stillHere(page, view, epoch); offset += 200) {
      var batch = ids.slice(offset, offset + 200);
      var response = await view.$http.get(view.$url.url_5000 + '/model_view/' + endpoint, {
        params: Object.assign({scope:'status', ids:batch.join(',')}, params), timeout:8000
      });
      if (!stillHere(page, view, epoch)) return;
      var data = response.data;
      if (!data || data.code !== 200 || !data.data || Array.isArray(data.data)) return;
      rows.forEach(function (row) {
        if (Object.prototype.hasOwnProperty.call(data.data, row.id) && row.online !== data.data[row.id]) {
          view.$set(row, 'online', data.data[row.id]);
        }
      });
    }
  }
  async function poll(epoch) {
    var page = route();
    if (epoch !== generation || root.document.hidden || (page !== 'sbtj' && page !== 'sbtb')) return;
    var view = viewFor(page), delay = interval;
    try {
      if (!view || !view.tableData.length) {
        delay = view ? interval : 1500;
      } else if (page === 'sbtj') {
        await refreshRows(page, view, epoch, 'equipment_show', equipmentRows(view), {});
      } else {
        await refreshRows(page, view, epoch, 'VCR_data_show', view.tableData.slice(), {type_st:'1'});
        if (stillHere(page, view, epoch) && view.detailsOpen && view.detailsForm.id && Array.isArray(view.detailsTableData2)) {
          await refreshRows(page, view, epoch, 'VCR_data_show', view.detailsTableData2.slice(), {
            type_st:'2', id:view.detailsForm.id
          });
        }
      }
    } catch (_) {
      // Keep the last known status during a temporary network interruption.
    } finally {
      if (epoch === generation && !root.document.hidden) timer = root.setTimeout(function () { poll(epoch); }, delay);
    }
  }
  function reset() {
    root.clearTimeout(timer);
    var epoch = ++generation, page = route();
    if (!root.document.hidden && (page === 'sbtj' || page === 'sbtb')) {
      timer = root.setTimeout(function () { poll(epoch); }, 1200);
    }
  }
  root.addEventListener('hashchange', reset);
  root.addEventListener('pageshow', reset);
  root.addEventListener('pagehide', function () { generation++; root.clearTimeout(timer); });
  root.document.addEventListener('visibilitychange', reset);
  reset();
})(window);
