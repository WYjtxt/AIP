(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["chunk-0feaf7a3"],{"04aa":function(e,t,a){"use strict";
// The panel reads recovery status and never changes camera or task settings.
var streamRecoveryStatusMixin={
  data() {
    return { streamRecoverySnapshot: null, streamRecoveryError: '', streamRecoveryLoading: false };
  },
  computed: {
    streamRecoveryCheckedAt() {
      return this.streamRecoverySnapshot ? this.formatStreamRecoveryTime(this.streamRecoverySnapshot.checked_at) : '尚未读取';
    },
    streamRecoveryDetails() {
      const devices = this.streamRecoverySnapshot && this.streamRecoverySnapshot.devices;
      return Array.isArray(devices) ? devices.filter(device => device && device.state !== 'healthy') : [];
    },
    streamRecoverySummary() {
      const summary = this.streamRecoverySnapshot && this.streamRecoverySnapshot.summary || {};
      const devices = this.streamRecoverySnapshot && this.streamRecoverySnapshot.devices || [];
      const count = states => states.reduce((sum, state) => {
        const value = Object.prototype.hasOwnProperty.call(summary, state) ? Number(summary[state]) : devices.filter(device => device.state === state).length;
        return sum + (Number.isFinite(value) && value > 0 ? value : 0);
      }, 0);
      const known = ['healthy', 'observing_video', 'waiting_video', 'proxy_connecting', 'recovering', 'backoff', 'source_auth_paused', 'needs_attention'];
      const unknown = Array.from(new Set([...Object.keys(summary), ...devices.map(device => device.state)])).filter(state => !known.includes(state));
      return { abnormal: count(['waiting_video', 'backoff']), recovering: count(['observing_video', 'proxy_connecting', 'recovering']),
        auth: count(['source_auth_paused']), attention: count(['needs_attention', ...unknown]) };
    },
  },
  created() {
    this._streamRecoveryMounted = false;
    this._streamRecoveryDenied = false;
    this._streamRecoveryGeneration = 0;
    this._streamRecoveryTimer = null;
    this._streamRecoveryController = null;
  },
  mounted() {
    this._streamRecoveryMounted = true;
    this._streamRecoveryVisibility = () => {
      if (typeof document !== 'undefined' && document.hidden) this.stopStreamRecoveryPolling();
      else this.refreshStreamRecoveryStatus();
    };
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', this._streamRecoveryVisibility);
    this.refreshStreamRecoveryStatus();
  },
  beforeDestroy() {
    this._streamRecoveryMounted = false;
    this.stopStreamRecoveryPolling();
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', this._streamRecoveryVisibility);
  },
  watch: {
    '$route.path'() {
      if (this.streamRecoveryPageActive()) this.refreshStreamRecoveryStatus();
      else this.stopStreamRecoveryPolling();
    },
  },
  methods: {
    streamRecoveryPageActive() {
      if (!this._streamRecoveryMounted || this._isDestroyed || this._isBeingDestroyed) return false;
      if (typeof document !== 'undefined' && document.hidden) return false;
      const route = this.$route;
      return !route || !route.path || /\/lmtgl\/?$/.test(route.path);
    },
    formatStreamRecoveryTime(value) {
      const epoch = Number(value);
      if (!Number.isFinite(epoch) || epoch <= 0) return '暂无';
      const date = new Date(epoch < 1000000000000 ? epoch * 1000 : epoch);
      return Number.isNaN(date.getTime()) ? '暂无' : date.toLocaleString('zh-CN', { hour12: false });
    },
    streamRecoveryStateLabel(state) {
      return { healthy: '正常', observing_video: '画面观察中', waiting_video: '等待画面', proxy_connecting: '连接中',
        recovering: '恢复中', backoff: '等待重试', source_auth_paused: '认证待维护', needs_attention: '需要关注' }[state] || '待确认';
    },
    streamRecoveryReasonLabel(device) {
      const known = { account_maintenance: '账号认证需要维护，已暂停自动尝试', authentication_failed: '账号认证未通过，请维护账号',
        source_authentication_failed: '源设备账号认证未通过，请维护账号', source_unavailable: '源设备暂时不可用',
        waiting_video: '等待源设备恢复画面', no_video: '暂未检测到有效画面', no_frames: '暂未检测到有效画面',
        retry_backoff: '等待下次自动尝试', recovering: '正在恢复画面', proxy_connecting: '正在连接源设备',
        needs_attention: '多次尝试后仍未恢复，需要人工查看' };
      if (known[device.reason]) return known[device.reason];
      return { healthy: '画面正常', observing_video: '正在确认画面稳定性', waiting_video: '等待源设备恢复画面',
        proxy_connecting: '正在连接源设备', recovering: '正在恢复画面', backoff: '等待下次自动尝试',
        source_auth_paused: '账号认证需要维护，已暂停自动尝试', needs_attention: '请查看源设备和网络状态' }[device.state] || '状态待进一步确认';
    },
    streamRecoveryNextAttempt(device) {
      if (device.state === 'source_auth_paused') return '账号维护后再尝试';
      return this.formatStreamRecoveryTime(device.next_retry);
    },
    stopStreamRecoveryPolling() {
      this._streamRecoveryGeneration++;
      clearTimeout(this._streamRecoveryTimer); this._streamRecoveryTimer = null;
      if (this._streamRecoveryController) this._streamRecoveryController.abort();
      this._streamRecoveryController = null;
      this.streamRecoveryLoading = false;
    },
    pauseStreamRecoveryPolling(code) {
      this._streamRecoveryDenied = true;
      this.streamRecoveryError = Number(code) === 401 ? '登录状态已失效，已暂停读取后台恢复状态' : '没有读取后台恢复状态的权限，已暂停自动刷新';
      this.stopStreamRecoveryPolling();
    },
    refreshStreamRecoveryStatus() {
      if (!this.streamRecoveryPageActive() || this._streamRecoveryDenied || this._streamRecoveryController) return Promise.resolve(false);
      clearTimeout(this._streamRecoveryTimer); this._streamRecoveryTimer = null;
      const generation = this._streamRecoveryGeneration;
      const current = () => generation === this._streamRecoveryGeneration && this.streamRecoveryPageActive();
      const controller = new AbortController(); this._streamRecoveryController = controller;
      this.streamRecoveryLoading = true;
      return this.$http.get(this.$url.url_5000 + '/zlmediakit_view/recovery/status', { signal: controller.signal, timeout: 8000 }).then(response => {
        if (!current()) return false;
        const body = response && response.data;
        if (body && [401, 403].includes(Number(body.code))) { this.pauseStreamRecoveryPolling(body.code); return false; }
        const data = body && body.data;
        if (!body || Number(body.code) !== 200 || !data || typeof data.enabled !== 'boolean' || !Array.isArray(data.devices)
          || !data.summary || typeof data.summary !== 'object' || Array.isArray(data.summary)) throw new Error('Unavailable recovery status');
        this.streamRecoverySnapshot = data;
        this.streamRecoveryError = '';
        return true;
      }).catch(error => {
        if (!current()) return false;
        const code = error && error.response && error.response.status;
        if ([401, 403].includes(Number(code))) this.pauseStreamRecoveryPolling(code);
        else this.streamRecoveryError = '后台恢复状态暂时不可用，保留最近结果；数据可能已过期';
        return false;
      }).finally(() => {
        if (this._streamRecoveryController === controller) this._streamRecoveryController = null;
        if (generation === this._streamRecoveryGeneration) this.streamRecoveryLoading = false;
        if (current() && !this._streamRecoveryDenied) this._streamRecoveryTimer = setTimeout(() => this.refreshStreamRecoveryStatus(), 10000);
      });
    },
  },
};

var renderStreamRecoveryPanel=function(){var _vm=this;var _h=_vm.$createElement;var _c=_vm._self._c||_h;return _c('section',{staticClass:"stream-recovery-panel",staticStyle:{"margin":"0 16px 10px","padding":"12px 14px","border":"1px solid #dce5f2","border-radius":"6px","background":"#f8faff","font-size":"13px","line-height":"22px"},attrs:{"aria-label":"后台自动恢复状态"}},[_c('div',{staticStyle:{"display":"flex","flex-wrap":"wrap","gap":"8px 18px","align-items":"center"}},[_c('strong',[_vm._v("后台自动恢复")]),(_vm.streamRecoverySnapshot)?_c('span',[_vm._v(_vm._s(_vm.streamRecoverySnapshot.enabled ? '已启用' : '未启用'))]):_c('span',[_vm._v(_vm._s(_vm.streamRecoveryLoading ? '正在读取状态…' : '尚未取得状态'))]),_c('span',{staticStyle:{"margin-left":"auto","color":"#78869a"}},[_vm._v("最近检查："+_vm._s(_vm.streamRecoveryCheckedAt))])]),(_vm.streamRecoveryError)?_c('div',{staticStyle:{"color":"#b26a00"},attrs:{"role":"alert"}},[_vm._v(_vm._s(_vm.streamRecoveryError))]):_vm._e(),(_vm.streamRecoverySnapshot)?_c('div',{staticStyle:{"display":"flex","flex-wrap":"wrap","gap":"8px 18px"}},[_c('span',[_vm._v("异常 "+_vm._s(_vm.streamRecoverySummary.abnormal))]),_c('span',[_vm._v("恢复中 "+_vm._s(_vm.streamRecoverySummary.recovering))]),_c('span',[_vm._v("认证待维护 "+_vm._s(_vm.streamRecoverySummary.auth))]),_c('span',[_vm._v("需要关注 "+_vm._s(_vm.streamRecoverySummary.attention))])]):_vm._e(),(_vm.streamRecoverySnapshot)?_c('details',{staticStyle:{"max-height":"240px","overflow-y":"auto"}},[_c('summary',{staticStyle:{"cursor":"pointer"}},[_vm._v("查看异常与恢复明细（"+_vm._s(_vm.streamRecoveryDetails.length)+"）")]),(!_vm.streamRecoveryDetails.length)?_c('div',{staticStyle:{"color":"#78869a"}},[_vm._v(_vm._s(Number(_vm.streamRecoverySnapshot.checked_at) > 0 ? '最近检查未记录异常条目' : '尚未形成检查结果'))]):_vm._e(),_vm._l((_vm.streamRecoveryDetails),function(device){return _c('div',{key:device.id,staticStyle:{"padding":"8px 0","border-top":"1px solid #e5ebf3"}},[_c('strong',[_vm._v(_vm._s(device.name || ('监控点 ' + device.id)))]),_vm._v(" · "+_vm._s(_vm.streamRecoveryStateLabel(device.state))+"\n      "),_c('div',[_vm._v(_vm._s(_vm.streamRecoveryReasonLabel(device)))]),_c('div',{staticStyle:{"color":"#78869a"}},[_vm._v("下次尝试："+_vm._s(_vm.streamRecoveryNextAttempt(device))),(device.last_attempt)?_c('span',[_vm._v(" · 上次尝试："+_vm._s(_vm.formatStreamRecoveryTime(device.last_attempt)))]):_vm._e()])])})],2):_vm._e()])};
a.r(t);var l=function(){var e=this,t=e._self._c;return t("div",{staticClass:"sfgl",staticStyle:{"overflow-y":"auto"}},[t("div",{staticClass:"serch"},[t("el-form",{staticClass:"demo-ruleForm"},[t("el-form-item",{attrs:{label:"监控点名称","label-width":"130px"}},[t("el-input",{staticStyle:{width:"100%"},attrs:{autocomplete:"off",placeholder:"请输入监控点名称",clearable:""},model:{value:e.camera_name,callback:function(t){e.camera_name=t},expression:"camera_name"}})],1),t("el-form-item",[t("el-button",{attrs:{icon:"el-icon-search",type:"primary",size:"small"},on:{click:function(t){return e.axioss()}}},[e._v("查询")]),t("el-button",{attrs:{icon:"el-icon-plus",type:"success",size:"small"},on:{click:e.handleAdd}},[e._v("新增")])],1)],1)],1),renderStreamRecoveryPanel.call(e),t("div",{staticClass:"table",staticStyle:{height:"calc(100% - 170px)","min-height":"240px"}},[t("div",{staticClass:"jia_table"},[t("el-table",{ref:"singleTable",staticStyle:{width:"100%"},attrs:{data:e.tableData,height:"95%"}},[t("el-table-column",{attrs:{prop:"index",label:"序号",width:"50"},scopedSlots:e._u([{key:"default",fn:function(t){return[e._v(" "+e._s((Number(e.currentPage)-1)*Number(e.pagesize)+t.$index+1)+" ")]}}])}),t("el-table-column",{attrs:{prop:"cameras_name",sortable:"",label:"监控点名称","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"app",label:"应用名","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"stream",label:"流id","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"schema",label:"协议",sortable:"","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"create_date",label:"创建时间","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"originUrl",label:"源地址","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"stream_url",label:"转出地址"}}),t("el-table-column",{attrs:{prop:"hhh",label:"观看人数","show-overflow-tooltip":!0},scopedSlots:e._u([{key:"default",fn:function(a){return[t("el-button",{on:{click:function(t){return e.gkrs(a.row)}}},[e._v(e._s(a.row.readerCount)+"/"+e._s(a.row.totalReaderCount))])]}}])}),t("el-table-column",{attrs:{label:"操作"},scopedSlots:e._u([{key:"default",fn:function(a){return[t("el-button",{attrs:{type:"text",icon:"el-icon-delete",size:"mini"},on:{click:function(t){return e.handleDelete(a.row)}}},[e._v("关闭")])]}}])})],1),0===e.tableData.length?t("el-empty",{attrs:{image:"/static/img/home/placeholder_kong.png","image-size":307,description:"暂时没有数据~"}}):e._e()],1)]),t("el-dialog",{attrs:{title:e.title,visible:e.dialogFormVisible,width:"80%"},on:{"update:visible":function(t){e.dialogFormVisible=t}}},[e.dialogFormVisible?t("el-form",{attrs:{model:e.form}},[t("el-form-item",{attrs:{label:"全部监控点","label-width":e.formLabelWidth}},[t("div",{staticStyle:{"text-align":"center"}},[t("div",{staticClass:"transferTreeBox"},[t("div",{staticClass:"SelectBox"},[t("div",{staticClass:"boxTitle",on:{click:e.clickAllSelect}},[e._v("未配置监控点 >")]),t("div",{staticClass:"boxCenter"},[t("el-tree",{ref:"leftTree",attrs:{data:e.leftData,props:e.defaultProps,"show-checkbox":"","node-key":"id"}})],1)]),t("div",{staticClass:"transferBtn"},[t("el-button",{attrs:{type:"primary",size:"small"},on:{click:e.towardsLeft}},[t("i",{staticClass:"el-icon-arrow-left"}),e._v(" 移除")]),t("el-button",{attrs:{type:"primary",size:"small"},on:{click:e.towardsRight}},[e._v("添加"),t("i",{staticClass:"el-icon-arrow-right"})])],1),t("div",{staticClass:"SelectBox"},[t("div",{staticClass:"boxTitle",on:{click:e.clickCancelAllSelect}},[e._v("已配置选中监控点")]),t("div",{staticClass:"boxCenter"},[t("el-tree",{ref:"rightTree",attrs:{data:e.rightData,props:e.defaultProps,"show-checkbox":"","node-key":"id"}})],1)])])])]),t("el-form-item",{attrs:{label:"","label-width":e.formLabelWidth}},[t("el-checkbox",{model:{value:e.enable_hls,callback:function(t){e.enable_hls=t},expression:"enable_hls"}},[e._v("转hls-mpeg")]),t("el-checkbox",{model:{value:e.enable_hls_fmp4,callback:function(t){e.enable_hls_fmp4=t},expression:"enable_hls_fmp4"}},[e._v("转hls-fmp4")]),t("el-checkbox",{model:{value:e.enable_rtsp,callback:function(t){e.enable_rtsp=t},expression:"enable_rtsp"}},[e._v("转rtsp")]),t("el-checkbox",{model:{value:e.enable_rtmp,callback:function(t){e.enable_rtmp=t},expression:"enable_rtmp"}},[e._v("转rtmp/flv")]),t("el-checkbox",{model:{value:e.enable_ts,callback:function(t){e.enable_ts=t},expression:"enable_ts"}},[e._v("转http-ts/ws-ts")]),t("el-checkbox",{model:{value:e.enable_fmp4,callback:function(t){e.enable_fmp4=t},expression:"enable_fmp4"}},[e._v("转http-fmp4/ws-fmp4")])],1)],1):e._e(),t("div",{staticClass:"dialog-footer",attrs:{slot:"footer"},slot:"footer"},[t("el-button",{on:{click:function(t){e.dialogFormVisible=!1}}},[e._v("取 消")]),t("el-button",{attrs:{type:"primary"},on:{click:e.submits}},[e._v("确 定")])],1)],1),t("el-dialog",{attrs:{title:"观看者列表",visible:e.dialogFormVisible2,width:"80%"},on:{"update:visible":function(t){e.dialogFormVisible2=t}}},[t("el-table",{attrs:{data:e.gridData}},[t("el-table-column",{attrs:{property:"identifier",label:"id"}}),t("el-table-column",{attrs:{property:"local_ip",label:"本机ip"}}),t("el-table-column",{attrs:{property:"local_port",label:"本机端口"}}),t("el-table-column",{attrs:{property:"peer_ip",label:"对端ip"}}),t("el-table-column",{attrs:{property:"peer_port",label:"对端端口"}}),t("el-table-column",{attrs:{property:"typeid",label:"类型"}}),t("el-table-column",{attrs:{property:"address",label:"操作"},scopedSlots:e._u([{key:"default",fn:function(a){return[t("el-button",{attrs:{type:"danger",size:"mini"},on:{click:function(t){return e.handleDelete1(a.row)}}},[e._v("断开")])]}}])})],1)],1)],1)},s=[],i=(a("14d9"),a("ed5a")),r={components:{History:History},name:"sfgl",data(){return{enable_hls:!1,enable_hls_fmp4:!1,enable_rtsp:!1,enable_rtmp:!1,enable_ts:!1,enable_fmp4:!1,dialogFormVisible2:!1,gridData:[],checked:!1,camera_name:"",title:"",formLabelWidth:"100px",dialogFormVisible:!1,form:{mine_name:"",mine_code:""},type:0,levelType:"",tableData:[],currentPage:1,pagenumber:1,pagesize:15,pagelength:0,pagesizes:[15,35,50,100,150,200,300],checkedList:[],monitorData:[],monitorValue:[],monitorF:[],selectedMonitor:"",config:{headers:{"Content-Type":"multipart/form-data"}},defaultProps:{children:"children",label:"equipment_name"},leftData:[],rightData:[],mockTreeData:[],checkAll:!1,isIndeterminate:!1,checkedList:[],monitorData:[],monitorValue:[]}},computed:{},created(){},methods:{gkrs(e){e.readerCount>0&&(console.log(e),this.$http.post(i["a"].getMediaPlayerList,{id:e.id,schema:e.schema,vhost:e.vhost,app:e.app,stream:e.stream},this.config).then(e=>{200==e.data.code&&(this.gridData=e.data.data)}).catch(e=>{console.log(e)}),this.dialogFormVisible2=!0)},towardsRight(){const e=this.$refs.leftTree.getCheckedNodes(!1,!0),t=this.$refs.leftTree.getCheckedKeys(!1),a=JSON.parse(JSON.stringify(e));a.forEach(e=>{e.children=[],this.$refs.rightTree.getNode(e.id)||this.$refs.rightTree.append(e,e.parent_id)}),t.forEach(e=>{this.$refs.leftTree.remove(e)}),this.afterToward()},towardsLeft(){const e=this.$refs.rightTree.getCheckedNodes(!1,!0),t=this.$refs.rightTree.getCheckedKeys(!1),a=JSON.parse(JSON.stringify(e));a.forEach(e=>{e.children=[],this.$refs.leftTree.getNode(e.id)||this.$refs.leftTree.append(e,e.parent_id)}),t.forEach(e=>{this.$refs.rightTree.remove(e)}),this.afterToward()},clickAllSelect(){this.$refs.leftTree.setCheckedNodes(this.leftData),this.towardsRight()},clickCancelAllSelect(){this.$refs.rightTree.setCheckedNodes(this.rightData),this.towardsLeft()},afterToward(){this.$refs.leftTree.setCheckedKeys([]),this.$refs.rightTree.setCheckedKeys([]),console.log(this.leftData,this.rightData),this.$emit("getData",{leftData:this.leftData,rightData:this.rightData})},renderTree(){this.leftData=[mockTreeData[1]],this.rightData=[mockTreeData[0],mockTreeData[2]]},findEngishName(e){let t=this.timeOptions.find(t=>t.value==e);return t?t.label:e},toggleShowPassword(e){e.hasOwnProperty("showPassword")||this.$set(e,"showPassword",!1),e.showPassword=!e.showPassword},getRowKey(e){return e.id},handleCurrentChange(e){this.pagenumber=e,this.axioss()},handleSizeChange(e){this.pagesize=e,this.axioss()},handleRow(e){this.multipleSelection=e},handleRows(e){this.multipleSelection=e},handleCurrentChange(e){this.pagenumber=e,this.axioss()},handleSizeChange(e){this.pagesize=e,this.axioss()},handleAdd(){this.enable_hls=!1,this.enable_hls_fmp4=!1,this.enable_rtsp=!1,this.enable_rtmp=!1,this.enable_ts=!1,this.enable_fmp4=!1,this.checkAll=!1,this.isIndeterminate=!1,this.$set(this.checkedList,[]),this.getMonitorList(),this.rightData=[],this.title="新增",this.dialogFormVisible=!0},getMonitorList(){this.$http.get(this.$url.url_5000+"/model_view/equipment_show",{params:{equipment_name:"",equipment_type:"",page:1,per_page:99999999}}).then(e=>{this.mockTreeData=e.data.data_list.data,this.leftData=this.mockTreeData;let t=e.data.data_list.data;t.forEach(e=>{this.monitorF.push(e.equipment_name),e.children&&e.children.forEach(e=>{let t={key:e.id,label:e.equipment_name,ip:e.equipment_ip,parent_ip:e.parent_ip,rtsp:e.rtsp,id:e.id,name:e.equipment_name};this.monitorData.push(t)})})}).catch((function(e){console.log(e)}))},handleDelete(e){return this.$http.post(i["a"].delStreamProxy,{ids:e.id},this.config).then(e=>{const t=e&&e.data||{};200==t.code?this.$message({message:t.msg||"关闭成功",type:"success"}):this.$message.error(t.msg||"关闭流媒体失败")}).catch(e=>{this.$message.error(e&&e.response&&e.response.data&&e.response.data.msg||"关闭流媒体失败，请稍后重试")}).then(()=>this.axioss())},handleDelete1(e){this.$http.post(i["a"].kick_session,{id:e.identifier},this.config).then(e=>{200==e.data.code?this.$message({message:e.data.msg,type:"success"}):this.$message.error(e.data.msg)}).catch(e=>{console.log(e)})},submits(){this.$http.post(i["a"].addStreamProxy,{rtsp_list:JSON.stringify(this.rightData),enable_hls:this.enable_hls,enable_hls_fmp4:this.enable_hls_fmp4,enable_rtsp:this.enable_rtsp,enable_rtmp:this.enable_rtmp,enable_ts:this.enable_ts,enable_fmp4:this.enable_fmp4},this.config).then(e=>{200==e.data.code?(this.$message({message:e.data.msg,type:"success"}),this.dialogFormVisible=!1,this.axioss()):this.$message({message:e.data.msg,type:"error"})}).catch(e=>{alert(2),console.log(e)})},submitss(){this.$http.post(this.$url.url_5000+"/model_view/mine_update",this.form).then(e=>{200===e.data.code?(this.$message({message:e.data.msg,type:"success"}),this.dialogFormVisible=!1,this.axioss()):this.$message.error(e.data.msg)}).catch((function(e){this.$message.error(e.data.msg),console.log(e)}))},axioss(){this.$http.post(i["a"].getMediaList,{camera_name:this.camera_name},this.config).then(e=>{200==e.data.code&&(this.tableData=e.data.data)}).catch(e=>{console.log(e)})}},mounted(){this.axioss()},beforeDestroy(){},destroyed(){}},o=r,n=(a("e7d3"),a("2877")),d=Object(n["a"])(o,l,s,!1,null,"f52cacac",null);d.exports.mixins=(d.exports.mixins||[]).concat([streamRecoveryStatusMixin]);t["default"]=d.exports},"064c":function(e,t,a){},e7d3:function(e,t,a){"use strict";a("064c")},ed5a:function(e,t,a){"use strict";a.d(t,"a",(function(){return l}));const l={getModelList:window.wgParameter.url_5000+"/model_template/model_template_show",getModelDetail:window.wgParameter.url_5000+"/model_template/model_template_detail",updateModel:window.wgParameter.url_5000+"/model_template/model_template_update",addModel:window.wgParameter.url_5000+"/model_template/model_template_add",deleteModel:window.wgParameter.url_5000+"/model_template/model_template_delete",getModelType:window.wgParameter.url_5000+"/model_template/model_type_template_show",addModelType:window.wgParameter.url_5000+"/model_template/model_type_template_add",updateModelType:window.wgParameter.url_5000+"/model_template/model_type_template_update",deleteModelType:window.wgParameter.url_5000+"/model_template/model_type_template_delete",gteModelTypeOne:window.wgParameter.url_5000+"/model_template/model_type_template_detail",getModelSmallList:window.wgParameter.url_5000+"/model_template/model_template_small_show",updateModelSmallList:window.wgParameter.url_5000+"/model_template/model_template_small_update",getModelSmallDetail:window.wgParameter.url_5000+"/model_template/model_small_detail",deleteModelSmall:window.wgParameter.url_5000+"/model_template/model_template_small_delete",addModelSmall:window.wgParameter.url_5000+"/model_template/model_template_small_add",addStreamProxy:window.wgParameter.url_5000+"/zlmediakit_view/addStreamProxy",delStreamProxy:window.wgParameter.url_5000+"/zlmediakit_view/delStreamProxy",getMediaList:window.wgParameter.url_5000+"/zlmediakit_view/getMediaList",getMediaPlayerList:window.wgParameter.url_5000+"/zlmediakit_view/getMediaPlayerList",getServerConfig:window.wgParameter.url_5000+"/zlmediakit_view/getServerConfig",restartServer:window.wgParameter.url_5000+"/zlmediakit_view/restartServer",getAllSession:window.wgParameter.url_5000+"/zlmediakit_view/getAllSession",kick_session:window.wgParameter.url_5000+"/zlmediakit_view/kick_session",model_warnmessage_show:window.wgParameter.url_5000+"/model_template/model_warnmessage_show",model_warn_maessage_add:window.wgParameter.url_5000+"/model_template/model_warn_maessage_add",model_warn_maessage_update:window.wgParameter.url_5000+"/model_template/model_warn_maessage_update",model_warning_message_delete:window.wgParameter.url_5000+"/model_template/model_warning_message_delete"}}}]);
//# sourceMappingURL=chunk-0feaf7a3.af756f59.js.map
