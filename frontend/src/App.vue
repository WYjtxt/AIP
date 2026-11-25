<!-- Restored from the server app source map. Platform layout builds CSS only; the current runtime JavaScript, routes and navigation guards are preserved. -->
<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script>
export default {
  data() {
    return {
     
    };
  },
  created() {
    // this.$store.state.version = window.wgParameter.version
  },
  methods: {
    
  }
};
</script>

<style lang="scss">
html,
body,
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 0;
  overflow: hidden;
}
.serch {
  width: 100%;
  height: 50px;
  form {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    .el-form-item {
      margin-bottom: 0px !important;
      margin-left: 10px;
    }
  }
}
.table {
  width: calc(100% - 40px);
  height: calc(100% - 50px);
  margin: 0 20px;
  .el-button {
    padding: 5px 10px !important;
  }
}
.el-table td,
.el-table th {
  padding: 0 !important;
}
.el-table__body {
  tr,
  .el-table__row--level-2 {
    height: 48.5px !important;
    font-size: 12px;
  }
}
.el-dialog{
  border-radius: 21px;
}
.el-dialog__header {
  background-image: url(./img/home/bjlb/title.png);
  background-repeat: no-repeat;
  background-size: 101.6% 140%;
  // background-position: center 100%;
  background-attachment: fixed;
    background-position: center -10px!important;
  // border-radius: 20px;
  // border-top-left-radius: 10px !important; /* 设置左上角圆角半径为10px */
  // border-top-right-radius: 10px !important; /* 设置右上角圆角半径为10px */
  border-bottom: 1px solid #d4d4d4;
  // box-sizing: content-box;
  .el-dialog__title {
    border-left: 4px solid #006eff;
    padding-left: 5px;
  }
}
</style>

<!-- Maintained platform theme. Only this plain CSS block is rebuilt by build_platform_layout.cjs. -->
<style data-platform-layout>
:root {
  --platform-primary: #2563eb;
  --platform-primary-hover: #1d4ed8;
  --platform-primary-soft: #eff6ff;
  --platform-text: #334155;
  --platform-label: #475569;
  --platform-muted: #64748b;
  --platform-placeholder: #94a3b8;
  --platform-border: #e2e8f0;
  --platform-border-hover: #b8c8de;
  --platform-divider: #edf1f6;
  --platform-background: #f4f7fb;
  --platform-surface: #fff;
  --platform-subtle: #f8fafc;
  --platform-row-hover: #f5f9ff;
  --platform-danger: #b42318;
  --platform-danger-soft: #fff4f2;
  --platform-danger-border: #f1c5c0;
  --platform-danger-hover: #fee9e6;
  --platform-radius: 6px;
  --platform-overlay-radius: 8px;
  --platform-shadow: 0 1px 3px rgba(15, 23, 42, .04);
  --platform-overlay-shadow: 0 12px 32px rgba(30, 48, 76, .14);
  --platform-focus-ring: 0 0 0 3px rgba(37, 99, 235, .12);
  --platform-font-family: "Segoe UI", "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
  --platform-font-size: 13px;
  --platform-list-inset: 16px;
}

/* Decoration also reaches diagnostic/tree/template pages without replacing
   their layout calculations, player containers or chart sizing. */
.home { color: var(--platform-text); font-family: var(--platform-font-family); }
.home .contents .el-form-item__label { color: var(--platform-label); }
.home .contents .el-input__inner {
  color: var(--platform-text);
  border-color: var(--platform-border);
  border-radius: var(--platform-radius);
  font-family: inherit;
  font-size: var(--platform-font-size);
  transition: border-color .15s ease, box-shadow .15s ease;
}
.home .contents .el-input__inner::placeholder { color: var(--platform-placeholder); }
.home .contents .el-input:not(.is-disabled) .el-input__inner:hover,
.home .contents .el-range-editor:not(.is-disabled):hover { border-color: var(--platform-border-hover); }
.home .contents .el-input:not(.is-disabled) .el-input__inner:focus,
.home .contents .el-select .el-input.is-focus:not(.is-disabled) .el-input__inner,
.home .contents .el-cascader .el-input.is-focus:not(.is-disabled) .el-input__inner,
.home .contents .el-range-editor.is-active:not(.is-disabled) {
  border-color: var(--platform-primary);
  box-shadow: var(--platform-focus-ring);
}
.home .contents .el-input.is-disabled .el-input__inner {
  color: var(--platform-muted);
  background-color: var(--platform-subtle);
  border-color: var(--platform-border);
}
.home .contents .el-button {
  font-family: inherit;
  transition: color .15s ease, border-color .15s ease, background-color .15s ease, box-shadow .15s ease;
}
.home .contents .el-button--default:not(.is-disabled) {
  color: var(--platform-label);
  background-color: var(--platform-surface);
  border-color: var(--platform-border);
}
.home .contents .el-button--default:not(.is-disabled):is(:hover, :focus) {
  color: var(--platform-primary);
  background-color: var(--platform-primary-soft);
  border-color: var(--platform-border-hover);
}
.home .contents .el-button--primary:not(.is-disabled):not(.is-plain) {
  color: #fff;
  background-color: var(--platform-primary);
  border-color: var(--platform-primary);
}
.home .contents .el-button--primary:not(.is-disabled):not(.is-plain):is(:hover, :focus) {
  background-color: var(--platform-primary-hover);
  border-color: var(--platform-primary-hover);
}
.home .contents .el-button--primary.is-plain:not(.is-disabled),
.home .contents .el-button--success:not(.is-disabled) {
  color: var(--platform-primary);
  background-color: var(--platform-surface);
  border-color: #b9cdfa;
}
.home .contents .el-button--primary.is-plain:not(.is-disabled):is(:hover, :focus),
.home .contents .el-button--success:not(.is-disabled):is(:hover, :focus) {
  background-color: var(--platform-primary-soft);
  border-color: var(--platform-primary);
}
.home .contents .el-button--danger:not(.is-disabled) {
  color: var(--platform-danger);
  background-color: var(--platform-danger-soft);
  border-color: var(--platform-danger-border);
}
.home .contents .el-button--danger:not(.is-disabled):is(:hover, :focus) {
  background-color: var(--platform-danger-hover);
  border-color: #e6afa8;
}
.home .contents .el-button--text:not(.is-disabled) { color: var(--platform-primary); }
.home .contents .el-button--text:not(.is-disabled):is(:hover, :focus) { color: var(--platform-primary-hover); }
.home .contents .el-button.is-disabled {
  color: var(--platform-placeholder);
  background-color: var(--platform-subtle);
  border-color: var(--platform-border);
}
.home .contents .el-button--text.is-disabled { background-color: transparent; border-color: transparent; }
.home .contents .el-pagination { color: var(--platform-muted); font-size: var(--platform-font-size); }
.home .contents .el-tabs__item { font-size: var(--platform-font-size); }
.home .contents .el-tabs__item.is-active { color: var(--platform-primary); }
.home .contents .el-tabs__active-bar { background-color: var(--platform-primary); }
.home .contents > :is(.containner10, .app-container, .dictPage, .modelbig, .model, .menu_box) .el-table {
  color: var(--platform-text);
  border-color: var(--platform-border);
  font-size: var(--platform-font-size);
}
.home .contents > :is(.containner10, .app-container, .dictPage, .modelbig, .model, .menu_box) .el-table th {
  background: var(--platform-subtle) !important;
  color: var(--platform-label);
  font-weight: 600;
}
.home .contents > :is(.containner10, .app-container, .dictPage, .modelbig, .model, .menu_box) .el-table__empty-text {
  color: var(--platform-muted) !important;
}

/* Ordinary list pages share the existing search/table/page structure.
   Video, ROI forms, dashboards, tree editors and the device monitor are not list roots. */
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) {
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  min-width: 0;
  max-width: 100%;
  min-height: 0;
  height: 100%;
  overflow: hidden;
  background: var(--platform-surface);
  border: 1px solid var(--platform-border);
  border-radius: var(--platform-radius);
  box-shadow: var(--platform-shadow);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) {
  flex: 0 0 auto;
  width: 100%;
  height: auto !important;
  min-height: 52px;
  padding: 12px var(--platform-list-inset) !important;
  background: var(--platform-surface);
  border-bottom: 1px solid var(--platform-divider);
  box-sizing: border-box;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) form {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-start;
  gap: 10px 14px;
  height: auto !important;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-form-item {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  margin: 0 !important;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-form-item__label {
  width: auto !important;
  padding-right: 8px;
  line-height: 32px;
  color: var(--platform-label);
  font-size: var(--platform-font-size);
  white-space: nowrap;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-form-item__content {
  margin-left: 0 !important;
  line-height: 32px;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) :is(.el-input, .el-select, .el-cascader) {
  width: 184px;
  max-width: 100%;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-date-editor {
  width: 200px !important;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-date-editor--daterange {
  width: 280px !important;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-input__inner {
  width: 100% !important;
  height: 32px !important;
  line-height: 32px;
  border-color: var(--platform-border);
  border-radius: var(--platform-radius);
  font-size: var(--platform-font-size);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > .table {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  min-width: 0;
  min-height: 0;
  width: auto !important;
  height: auto !important;
  margin: 0 !important;
  padding: 12px var(--platform-list-inset) 10px;
  position: relative;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > .table > .jia_table {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  min-width: 0;
  min-height: 0;
  height: auto !important;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > .table > .jia_table > .el-table {
  flex: 1 1 0;
  min-height: 0;
  height: 100% !important;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > .table > :is(.page, .jia_page, .el-pagination),
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.page, .jia_page, .el-pagination) {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  position: static !important;
  float: none !important;
  width: 100%;
  height: auto !important;
  min-height: 42px;
  padding-top: 10px;
  margin: 0 !important;
  box-sizing: border-box;
  border-top: 1px solid var(--platform-divider);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > .table > .jia_table > .el-empty {
  display: none;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) :is(.page, .jia_page) > .el-pagination {
  float: none !important;
  max-width: 100%;
  overflow-x: auto;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table {
  color: var(--platform-text);
  font-size: var(--platform-font-size);
  border-color: var(--platform-border);
  background-image: none !important;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table :is(td, th) {
  padding: 8px 0 !important;
  border-color: var(--platform-divider);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table th {
  height: 40px !important;
  background: var(--platform-subtle) !important;
  color: var(--platform-label);
  font-size: var(--platform-font-size) !important;
  font-weight: 600;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table__body tr {
  height: auto !important;
  font-size: var(--platform-font-size);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table .cell {
  line-height: 20px;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table__empty-text {
  color: var(--platform-muted) !important;
  font-size: var(--platform-font-size);
  line-height: 24px;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-button {
  min-height: 32px;
  padding: 7px 12px !important;
  font-size: var(--platform-font-size);
  border-radius: var(--platform-radius);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-button--text {
  min-height: 26px;
  padding: 4px 6px !important;
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-button + .el-button {
  margin-left: 8px;
}

.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table::before,
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table--border::after {
  background-color: var(--platform-border);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table--striped .el-table__body tr.el-table__row--striped td {
  background-color: var(--platform-subtle);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table--enable-row-hover .el-table__body tr:hover > td,
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table__body tr.hover-row > td {
  background-color: var(--platform-row-hover);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-table__body tr.current-row > td {
  background-color: var(--platform-primary-soft);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-checkbox__input:is(.is-checked, .is-indeterminate) .el-checkbox__inner {
  background-color: var(--platform-primary);
  border-color: var(--platform-primary);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination :is(.btn-prev, .btn-next, .el-pager li) {
  border-radius: var(--platform-radius);
  background-color: var(--platform-subtle);
  color: var(--platform-label);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination :is(.btn-prev, .btn-next):not(:disabled):hover,
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination .el-pager li:not(.disabled):not(.active):hover {
  color: var(--platform-primary);
  background-color: var(--platform-primary-soft);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination .el-pager li.active {
  color: #fff;
  background-color: var(--platform-primary);
}
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination :is(.btn-prev, .btn-next):disabled,
.home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination .el-pager li.disabled {
  color: var(--platform-placeholder);
  background-color: var(--platform-subtle);
}

/* Shared dialog decoration does not alter any media element's dimensions. */
.el-dialog {
  border-radius: var(--platform-overlay-radius);
  box-shadow: var(--platform-overlay-shadow);
}
.el-dialog__header {
  background: var(--platform-subtle) !important;
  border-bottom: 1px solid var(--platform-border);
  border-radius: var(--platform-overlay-radius) var(--platform-overlay-radius) 0 0;
}
.el-dialog__title {
  color: var(--platform-text);
  border-left-color: var(--platform-primary);
  font-size: 15px;
  font-weight: 600;
}
/* Drawing/video/image dialogs retain their original body sizes and geometry. */
.el-dialog__wrapper:not(.jia_algoBox):not(.jia_videoDia):not(#stepDialog):not(:has(canvas, video, img, .Bcanvas, .stream-preview)) > .el-dialog {
  max-width: calc(100vw - 40px);
}
.el-dialog__wrapper:not(.jia_algoBox):not(.jia_videoDia):not(#stepDialog):not(:has(canvas, video, img, .Bcanvas, .stream-preview)) > .el-dialog > .el-dialog__body {
  padding: 16px 20px;
  max-height: calc(100vh - 220px);
  overflow-y: auto;
  color: var(--platform-text);
}
.el-dialog__wrapper:not(.jia_algoBox):not(.jia_videoDia):not(#stepDialog):not(:has(canvas, video, img, .Bcanvas, .stream-preview)) .el-form-item {
  margin-bottom: 16px;
}
.el-dialog__wrapper:not(.jia_algoBox):not(.jia_videoDia):not(#stepDialog):not(:has(canvas, video, img, .Bcanvas, .stream-preview)) .el-input__inner {
  min-height: 32px;
  border-color: var(--platform-border);
  border-radius: var(--platform-radius);
}
.el-dialog__wrapper:not(.jia_algoBox):not(.jia_videoDia):not(#stepDialog):not(:has(canvas, video, img, .Bcanvas, .stream-preview)) .el-dialog__footer {
  padding: 12px 20px;
  border-top: 1px solid var(--platform-divider);
}
.el-message-box {
  max-width: calc(100vw - 32px);
  border-radius: var(--platform-overlay-radius);
}
.el-select-dropdown, .el-picker-panel {
  border-color: var(--platform-border);
  border-radius: var(--platform-radius);
  box-shadow: var(--platform-overlay-shadow);
}
@media (max-width: 1100px) {
  :root { --platform-list-inset: 12px; }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) {
    padding: 10px var(--platform-list-inset) !important;
  }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) form {
    gap: 8px 10px;
  }
}
/* A narrow side pane stacks filters; the table keeps its own scroll area.
   Long filter sets scroll inside the toolbar, leaving room for rows and paging. */
@media (max-width: 760px) {
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) {
    max-height: 45%;
    overflow-y: auto;
  }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-form-item {
    flex-direction: column;
    align-items: stretch;
    box-sizing: border-box;
    width: 100%;
    max-width: 100%;
    min-width: 0;
  }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-form-item__label {
    width: 100% !important;
    text-align: left;
    padding: 0 0 4px;
    line-height: 22px;
  }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-form-item__label:empty { display: none; }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-form-item__content {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    width: 100%;
    max-width: 100%;
    min-width: 0;
  }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) :is(.el-input, .el-select, .el-cascader, .el-date-editor) {
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0;
  }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) > :is(.serch, .search) .el-button + .el-button { margin-left: 0; }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    align-items: center;
    gap: 6px 4px;
    box-sizing: border-box;
    width: 100%;
    white-space: normal;
    overflow-x: visible;
  }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) :is(.page, .jia_page) > .el-pagination { overflow-x: visible; }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination .el-pager {
    display: flex;
    flex: 1 1 120px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 100%;
    min-width: 0;
  }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination :is(.el-pagination__total, .el-pagination__sizes) { margin-right: 0; }
  .home .contents > :is(.bjlb, .sfgl, .sfc, .sbtj, .yplxj, .user-management, .role-management, .device_computing, .model, .modelbig, .menu_box, .hkaf) .el-pagination .el-pagination__jump { margin-left: 0 !important; }
}
</style>
