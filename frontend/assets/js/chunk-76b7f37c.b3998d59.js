(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["chunk-76b7f37c"],{"0486":function(e,t,a){"use strict";a("14d9");var i=a("cee4"),s=a("4360"),l=a("a18c");const o=i["a"].create({timeout:1e6,withCredentials:!1,headers:{"Content-Type":"application/json"}});o.interceptors.request.use(e=>{const t=s["a"].state.token||localStorage.getItem("token");return t&&(e.headers["Authorization"]="Bearer "+t),e},e=>Promise.reject(e)),o.interceptors.response.use(e=>(console.log(e),401===e.data.code&&(alert("登录状态已过期，请重新登录"),s["a"].commit("delToken"),l["a"].push("/login")),e),e=>(401===e.data.code&&(alert("登录状态已过期，请重新登录"),s["a"].commit("delToken"),l["a"].push("/login")),console.log("error",e),Promise.reject(e))),t["a"]=o},4029:function(e,t,a){"use strict";a.r(t);var i=function(){var e=this,t=e._self._c;return t("div",{staticClass:"sfc"},[t("div",{staticClass:"serch"},[t("el-form",{staticClass:"demo-ruleForm"},[t("el-form-item",{attrs:{label:"解析类型","label-width":"80px"}},[t("el-input",{staticStyle:{width:"100%"},attrs:{autocomplete:"off",clearable:"",placeholder:"请输入解析类型"},on:{input:function(t){return e.axioss()}},model:{value:e.sfname,callback:function(t){e.sfname=t},expression:"sfname"}})],1),t("el-form-item",{attrs:{label:"算法启用","label-width":"80px"}},[t("el-select",{attrs:{placeholder:"请选择",size:"small",clearable:"",filterable:""},on:{change:function(t){return e.axioss()}},model:{value:e.queryParams.algorithm_status,callback:function(t){e.$set(e.queryParams,"algorithm_status",t)},expression:"queryParams.algorithm_status"}},[t("el-option",{attrs:{label:"运行",value:"1"}}),t("el-option",{attrs:{label:"停止",value:"2"}})],1)],1),1==e.$store.state.user_role_id?t("el-form-item",{attrs:{label:"算法厂商类型","label-width":"130px"}},[t("el-select",{attrs:{placeholder:"请选择算法厂商类型",size:"small",clearable:"",filterable:""},on:{change:function(t){return e.axioss()}},model:{value:e.queryParams.algorithm_trade_type,callback:function(t){e.$set(e.queryParams,"algorithm_trade_type",t)},expression:"queryParams.algorithm_trade_type"}},e._l(e.options1,(function(e){return t("el-option",{key:e.value,attrs:{label:e.label,value:e.value}})})),1)],1):e._e(),t("el-form-item",[t("el-button",{attrs:{icon:"el-icon-search",type:"primary",size:"small"},on:{click:function(t){return e.axioss()}}},[e._v("查询")])],1),t("el-form-item",[t("el-button",{attrs:{icon:"el-icon-setting",type:"success",size:"small"},on:{click:function(t){return e.handleUp()}}},[e._v("上传")])],1),t("el-form-item",[t("el-button",{attrs:{icon:"el-icon-delete",type:"danger",size:"small"},on:{click:function(t){return e.handleDeleteOne()}}},[e._v("删除")])],1)],1)],1),t("div",{staticClass:"table"},[t("div",{staticClass:"jia_table"},[t("el-table",{ref:"singleTable",staticStyle:{width:"100%"},attrs:{data:e.tableData,height:"95%","header-cell-style":{background:"#f9fbff",height:"48.5px",fontSize:"14px"}},on:{select:e.handleRow,"select-all":e.handleRows}},[t("el-table-column",{attrs:{type:"expand"},scopedSlots:e._u([{key:"default",fn:function(a){return[t("div",{staticClass:"expand-box"},e._l(a.row.deployed_devices,(function(i,s){return t("div",{key:s,staticClass:"device-item"},[t("div",{staticClass:"device-info"},[t("p",{staticClass:"info-line"},[e._v("设备名称："+e._s(i.computing_name))]),t("p",{staticClass:"info-line"},[e._v("设备IP："+e._s(i.computing_ip))]),t("el-button",{staticClass:"delete-btn",attrs:{type:"text",size:"small"},on:{click:function(t){return e.handleDeleteDevice(a.row,i,s)}}},[e._v(" 删除 ")])],1)])})),0)]}}])}),t("el-table-column",{attrs:{type:"selection",width:"55"}}),t("el-table-column",{attrs:{prop:"index",label:"序号",width:"80"},scopedSlots:e._u([{key:"default",fn:function(t){return[e._v(" "+e._s((Number(e.currentPage)-1)*Number(e.pagesize)+t.$index+1)+" ")]}}])}),t("el-table-column",{attrs:{prop:"algorithm_name",label:"解析类型","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"algorithm_version",label:"算法版本","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"algorithm_trade_type",label:"算法厂商类型"},scopedSlots:e._u([{key:"default",fn:function(a){return[1==e.user_id?t("span",[e._v(e._s(e.handleFindType(a.row.algorithm_trade_type)))]):t("span",[e._v("阳光三极")])]}}])}),t("el-table-column",{attrs:{prop:"create_time",label:"安装时间","show-overflow-tooltip":!0}}),t("el-table-column",{attrs:{prop:"algorithm_ps",label:"算法备注"}}),t("el-table-column",{attrs:{label:"操作"},scopedSlots:e._u([{key:"default",fn:function(a){return[t("el-button",{attrs:{type:"text",size:"small"},on:{click:function(t){return e.handleSend(a.row)}}},[e._v("下发")])]}}])})],1),0===e.tableData.length?t("el-empty",{attrs:{image:"/static/img/home/placeholder_kong.png","image-size":307,description:"暂时没有数据~"}}):e._e()],1),t("div",{staticClass:"page"},[t("el-pagination",{attrs:{"current-page":e.currentPage,"page-size":e.pagesize,"page-sizes":e.pagesizes,background:"",layout:"total, prev, pager, next, jumper,sizes",total:e.pagelength},on:{"current-change":e.handleCurrentChange,"size-change":e.handleSizeChange,"update:currentPage":function(t){e.currentPage=t},"update:current-page":function(t){e.currentPage=t}}})],1)]),t("el-dialog",{staticClass:"jia_algoBox",attrs:{title:"算法上传",visible:e.dialogVisible,"close-on-click-modal":!1,width:"900px"},on:{"update:visible":function(t){e.dialogVisible=t},click:function(t){e.dialogVisible=!1}}},[t("el-form",{ref:"jiaRules",staticClass:"sfgl_diaForm",attrs:{model:e.jiaForm,rules:e.rules,"label-position":"top"}},[t("el-form-item",{attrs:{label:"算法上传(请上传单个zip格式压缩包且大小不超过60MB)"}},[t("el-upload",{ref:"upload",attrs:{action:"#","auto-upload":!0,multiple:!1,"file-list":e.fileList,"before-upload":e.beforeUpload,"http-request":e.uploadHttpRequest,"on-remove":e.fileRemove,"on-change":e.fileChange,accept:".zip"}},[t("el-button",{staticStyle:{width:"100%",height:"32px","border-radius":"6px"},attrs:{size:"small",type:"primary",icon:"el-icon-folder-opened"}},[e._v("点击此处上传算法组包")])],1),t("el-upload",{ref:"uploads",attrs:{action:"#","auto-upload":!0,multiple:!1,"file-list":e.fileLists,"before-upload":e.beforeUploads,"http-request":e.uploadHttpRequests,"on-remove":e.fileRemoves,"on-change":e.fileChanges,accept:".zip"}},[t("el-button",{staticStyle:{width:"100%",height:"32px","border-radius":"6px"},attrs:{size:"small",type:"primary",icon:"el-icon-folder-opened"}},[e._v("点击此处上传算法包")])],1),t("p",{staticStyle:{"font-size":"12px","line-height":"1.6",margin:"8px 0 0",color:"#66758c"}},[e._v("RKNN 算法 ZIP 上传后仅收录到平台算法库，尚未下发摄像仪。请核对目标硬件，再使用列表“下发”选择设备。")])],1),t("el-form-item",{staticClass:"jia_formItem2",attrs:{label:"算法启用","label-width":e.formLabelWidth,prop:"algorithm_status"}},[t("el-radio",{attrs:{label:"1"},model:{value:e.jiaForm.algorithm_status,callback:function(t){e.$set(e.jiaForm,"algorithm_status",t)},expression:"jiaForm.algorithm_status"}},[e._v("运行")]),t("el-radio",{attrs:{label:"2"},model:{value:e.jiaForm.algorithm_status,callback:function(t){e.$set(e.jiaForm,"algorithm_status",t)},expression:"jiaForm.algorithm_status"}},[e._v("停止")])],1),t("el-form-item",{attrs:{label:"算法备注","label-width":e.formLabelWidth,prop:"algorithm_ps"}},[t("el-input",{staticStyle:{width:"50%",resize:"none !important"},attrs:{placeholder:"请输入算法备注",type:"textarea",size:"small"},model:{value:e.jiaForm.algorithm_ps,callback:function(t){e.$set(e.jiaForm,"algorithm_ps",t)},expression:"jiaForm.algorithm_ps"}})],1)],1)],1),t("el-dialog",{attrs:{title:"算法下发",visible:e.dialogVisibles,"close-on-click-modal":!1,width:"600px"},on:{"update:visible":function(t){e.dialogVisibles=t},click:function(t){e.dialogVisibles=!1}}},[t("el-form",{ref:"xfForm",attrs:{model:e.xfForm,rules:e.ruless,"label-position":"top"}},[t("el-form-item",{staticClass:"inline-form-item",attrs:{label:"","label-width":e.formLabelWidth,prop:"equipment_ids"}},[t("el-select",{attrs:{placeholder:"请选择设备",multiple:"","collapse-tags":"",size:"small",clearable:"",filterable:""},model:{value:e.xfForm.equipment_ids,callback:function(t){e.$set(e.xfForm,"equipment_ids",t)},expression:"xfForm.equipment_ids"}},e._l(e.videolist,(function(e){return t("el-option",{key:e.id,attrs:{label:e.equipment_name,value:e.id}})})),1)],1)],1),t("span",{staticClass:"dialog-footer",attrs:{slot:"footer"},slot:"footer"},[t("el-button",{on:{click:function(t){e.dialogVisibles=!1}}},[e._v("取 消")]),t("el-button",{attrs:{type:"primary"},on:{click:function(t){return e.handleSure()}}},[e._v("确 定")])],1)],1)],1)},s=[],l=(a("d9e2"),a("0486")),o={name:"sfc",data(){return{dialogVisibles:!1,wjname:"",sfname:"",videolist:[],tableData:[],statusPending:{},listRequestSequence:0,currentPage:1,pagenumber:1,pagesize:15,pagelength:0,pagesizes:[15,35,50,100,150,200,300],dialogVisible:!1,fileList:[],fileLists:[],uploadDisabled:!0,jiaForm:{algorithm_name:"",algorithm_type_list:"['person']",algorithm_version:"v1.0",algorithm_type:"2",algorithm_status:"1",algorithm_ps:"",algorithm_trade_type:""},xfForm:{algorithm_libary_id:"",equipment_ids:[]},jiaRules:{},algorithm_statusValue:!1,formLabelWidth:"120px",ruless:{equipment_ids:[{required:!0,message:"请选择设备",trigger:"blur"}]},rules:{},options1:[{label:"寒武纪",value:1},{label:"算能",value:2},{label:"华为",value:3},{label:"瑞芯微",value:4},{label:"阳光三极",value:5}],options2:[{label:"人员检测模型",value:"['person']"}],multipleSelection:[],queryParams:{algorithm_status:null,algorithm_trade_type:null},user_id:0}},methods:{validateAlgorithmNameFormat(e,t,a){if(t){const e=t.split("-");7!==e.length?a(new Error("算法名称必须由七个部分组成")):a()}else a()},handleFindType(num) {
      const item = this.options1.find(value => String(value.value) === String(num));
      return item ? item.label : (num === null || num === undefined || num === '' ? '未标注厂商' : '其他厂商（' + String(num) + '）');
    },handleCurrentChange(e){this.pagenumber=e,this.axioss()},handleSizeChange(e){this.pagesize=e,this.axioss()},handleDeleteDevice(e,t,a){this.$confirm("此操作将永久删除该条数据, 是否继续?","提示",{confirmButtonText:"确定",cancelButtonText:"取消",type:"warning"}).then(()=>{this.$http.post(this.$url.url_5000+"/ai_camera_view/algorithm_library_delete_aicam",{equipment_id:t.equipment_id,id:[e.id]}).then(e=>{200==e.data.code?(this.$message({type:"success",message:e.data.msg}),this.axioss()):(this.$message({type:"warning",message:e.data.msg}),this.axioss())}).catch(e=>{this.$message({type:"error",message:response.data.msg})})}).catch(e=>{console.log(e),this.$message({type:"info",message:"已取消删除"})})},axioss() {
      const requestSequence = ++this.listRequestSequence;
      return this.$http
        .get(this.$url.url_5000 + "/ai_camera_view/algorithm_data_aicam", {
          params: {
            algorithm_file_name: this.wjname,
            algorithm_name: this.sfname,
            page: this.pagenumber,
            per_page: this.pagesize,
            ...this.queryParams
          },
        })
        .then((response) => {
          if (requestSequence !== this.listRequestSequence || this._isDestroyed || this._isBeingDestroyed) return;
          if (response.data.code === 200) {
            this.tableData = response.data.data_list.data.map(row => ({ ...row, algorithm_status: this.normalizeAlgorithmStatus(row.algorithm_status) }));
            this.pagelength = response.data.data_list.total_items;
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },handleUp(){this.$set(this.jiaForm,"algorithm_name",""),this.$set(this.jiaForm,"algorithm_type_list","['person']"),this.$set(this.jiaForm,"algorithm_version","v1.0"),this.$set(this.jiaForm,"algorithm_type","2"),this.$set(this.jiaForm,"algorithm_status","1"),this.dialogVisible=!0,this.$refs.upload.clearFiles(),this.fileList=[],this.$refs.uploads.clearFiles(),this.fileLists=[]},beforeUpload(e){const t="application/zip"===e.type||"application/x-zip-compressed"===e.type;t||this.$message.error("只能上传 ZIP 格式的文件!")},beforeUploads(e){const t="application/zip"===e.type||"application/x-zip-compressed"===e.type;t||this.$message.error("只能上传 ZIP 格式的文件!")},uploadHttpRequest(param) {
      this.$refs['jiaRules'].validate((valid) => {
        if (valid) {
          const loading = this.$loading({
            lock: true,
            text: "Loading",
            spinner: "el-icon-loading",
            background: "rgba(0, 0, 0, 0.7)",
          });
          const formData = new FormData(); //FormData对象，添加参数只能通过append('key', value)的形式添加
          formData.append("files", param.file); //添加文件对象
          formData.append("algorithm_name", this.jiaForm.algorithm_name);
          formData.append("algorithm_type", this.jiaForm.algorithm_type);
          formData.append("algorithm_type_list", this.jiaForm.algorithm_type_list);
          formData.append("algorithm_status", this.jiaForm.algorithm_status);
          formData.append("algorithm_version", this.jiaForm.algorithm_version);
          formData.append("algorithm_trade_type", this.jiaForm.algorithm_trade_type || '');
          formData.append("algorithm_ps", this.jiaForm.algorithm_ps || '');
          // formData.append('workSpaceName',this.workSpaceName)
          // formData.append('styleName',this.ruleForm.styleName)
          // console.log(formData.get('files'))
          let config = {
            headers: {
              "Content-Type": "multipart/form-data",
            },
          };
          l["a"]
            .post(
              this.$url.url_5000 + "/ai_camera_view/algorithm_upload_aicam",
              formData,
              config
            )
            .then((response) => {
              if (response.data.code == 200) {
                this.jiaForm.algorithm_version = response.data.data.algorithm_version;
                this.jiaForm.algorithm_type = response.data.data.algorithm_type;
                this.jiaForm.algorithm_type_list = response.data.data.algorithm_type_list;
                this.jiaForm.algorithm_trade_type = response.data.data.algorithm_trade_type;
                this.jiaForm.algorithm_name = response.data.data.filename;
                this.notifyUploadResult(response.data);
                this.axioss();
                setTimeout(() => {
                  this.handleClose();
                }, 3000);
                loading.close();
              } else {
                this.$message({
                  message: response.data.msg,
                  type: "warning",
                });
                loading.close();
              }
            })
            .catch((response) => {
              console.log(response);
              loading.close();
            });
        } else {
          this.$message({
            type: 'error',
            message: '校验未通过，请检查数据后重新提交'
          })
          return false;
        }
      });
    },uploadHttpRequests(param) {
      this.$refs['jiaRules'].validate((valid) => {
        if (valid) {
          const loading = this.$loading({
            lock: true,
            text: "Loading",
            spinner: "el-icon-loading",
            background: "rgba(0, 0, 0, 0.7)",
          });
          const formData = new FormData(); //FormData对象，添加参数只能通过append('key', value)的形式添加
          formData.append("files", param.file); //添加文件对象
          formData.append("algorithm_name", this.jiaForm.algorithm_name);
          formData.append("algorithm_type", this.jiaForm.algorithm_type);
          formData.append("algorithm_type_list", this.jiaForm.algorithm_type_list);
          formData.append("algorithm_status", this.jiaForm.algorithm_status);
          formData.append("algorithm_version", this.jiaForm.algorithm_version);
          formData.append("algorithm_trade_type", this.jiaForm.algorithm_trade_type || '');
          formData.append("algorithm_ps", this.jiaForm.algorithm_ps || '');
          // formData.append('workSpaceName',this.workSpaceName)
          // formData.append('styleName',this.ruleForm.styleName)
          // console.log(formData.get('files'))
          let config = {
            headers: {
              "Content-Type": "multipart/form-data",
            },
          };
          l["a"]
            .post(
              this.$url.url_5000 + "/ai_camera_view/algorithm_upload_sub_aicam",
              formData,
              config
            )
            .then((response) => {
              if (response.data.code == 200) {
                this.jiaForm.algorithm_version = response.data.data.algorithm_version;
                this.jiaForm.algorithm_type = response.data.data.algorithm_type;
                this.jiaForm.algorithm_type_list = response.data.data.algorithm_type_list;
                this.jiaForm.algorithm_trade_type = response.data.data.algorithm_trade_type;
                this.jiaForm.algorithm_name = response.data.data.filename;
                this.notifyUploadResult(response.data);
                this.axioss();
                setTimeout(() => {
                  this.handleClose();
                }, 3000);
                loading.close();
              } else {
                this.$message({
                  message: response.data.msg,
                  type: "warning",
                });
                loading.close();
              }
            })
            .catch((response) => {
              console.log(response);
              loading.close();
            });
        } else {
          this.$message({
            type: 'error',
            message: '校验未通过，请检查数据后重新提交'
          })
          return false;
        }
      });
    },submitUpload(){this.$refs.upload.submit()},fileRemove(e,t){t.length<1&&(this.uploadDisabled=!0)},fileChange(e,t){t.length>0&&(this.uploadDisabled=!1,this.fileList=[t[t.length-1]])},fileRemoves(e,t){t.length<1&&(this.uploadDisabled=!0)},fileChanges(e,t){t.length>0&&(this.uploadDisabled=!1,this.fileLists=[t[t.length-1]])},handleClose(){this.fileList=[],this.$nextTick(()=>{this.jiaForm={algorithm_name:"",algorithm_type_list:"['person']",algorithm_version:"v1.0",algorithm_type:"2",algorithm_status:"1",algorithm_ps:"",algorithm_trade_type:""}})},notifyUploadResult(result) {
      const items = Array.isArray(result.data) ? result.data : null;
      if (items && items.length) {
        const h = this.$createElement;
        const hasFailure = items.some(value => !value || Number(value.code) !== 200);
        this.$notify({
          title: '算法收录结果（未下发）', type: hasFailure ? 'warning' : 'success', duration: 0,
          message: h('div', { style: { maxHeight: '280px', overflowY: 'auto' } }, items.map((value, index) => {
            const item = value && typeof value === 'object' ? value : {};
            const name = String(item.sub_zip_name || item.filename || '算法包');
            const message = String(item.msg || (Number(item.code) === 200 ? '上传成功' : '上传失败'));
            // String children are rendered as text, including angle brackets and quotes.
            return h('p', { style: { margin: '4px 0', whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' } },
              (index + 1) + '. ' + name + '：' + message);
          }))
        });
      } else {
        this.$notify({ title: '已收录，尚未下发', message: String(result.msg || '算法已收录') + '；请使用列表“下发”按钮选择目标摄像仪。', type: 'success' });
      }
    },
    normalizeAlgorithmStatus(value) {
      if (String(value) === '1' || value === '运行') return '运行';
      if (String(value) === '2' || value === '停止') return '停止';
      return value;
    },
    handleChangeStatus(data) {
      if (this.statusPending[data.id]) return;
      const requestedStatus = this.normalizeAlgorithmStatus(data.algorithm_status);
      if (requestedStatus !== '运行' && requestedStatus !== '停止') {
        this.$message({ type: 'warning', message: '算法状态无效，请刷新后重试' });
        return this.axioss();
      }
      const previousStatus = requestedStatus === '运行' ? '停止' : '运行';
      this.$set(this.statusPending, data.id, true);
      ++this.listRequestSequence;
      return this.$http.post(
        this.$url.url_5000 + "/ai_camera_view/algorithm_data_update",
        { id: data.id, status: requestedStatus },
        { headers: { "Content-Type": "multipart/form-data" } }
      ).then(response => {
        if (response.data.code == 200) {
          this.$message({ type: 'success', message: response.data.msg });
        } else {
          data.algorithm_status = previousStatus;
          this.$message({ type: 'warning', message: response.data.msg });
        }
        return this.axioss();
      }).catch(error => {
        data.algorithm_status = previousStatus;
        this.$message({ type: 'error', message: error.response && error.response.data && error.response.data.msg || '更新算法启用状态失败，请刷新后重试' });
        return this.axioss();
      }).then(() => {
        this.$delete(this.statusPending, data.id);
      }, () => {
        this.$delete(this.statusPending, data.id);
      });
    },init(){this.$http.get(this.$url.url_5000+"/model_view/type_select",{params:{mine_id:"",type:2}},{withCredentials:!0}).then(e=>{200===e.data.code&&(this.videolist=e.data.equipment_list,this.dialogVisibles=!0)}).catch((function(e){console.log(e)}))},handleSend(e){this.xfForm.algorithm_libary_id=e.id,this.xfForm.equipment_ids=[],this.init()},handleSure(){this.$refs["xfForm"].validate(e=>{e&&this.$http.post(this.$url.url_5000+"/ai_camera_view/algorithm_deploy_aicam",this.xfForm).then(e=>{200==e.data.code?(this.$message({type:"success",message:e.data.msg}),this.axioss()):(this.$message({type:"warning",message:e.data.msg}),this.axioss())}).catch(e=>{this.$message({type:"error",message:response.data.msg})})})},handleDeleteOne(){this.multipleSelection.length>0?this.$confirm("此操作将永久删除该条数据, 是否继续?","提示",{confirmButtonText:"确定",cancelButtonText:"取消",type:"warning"}).then(()=>{this.$http.post(this.$url.url_5000+"/ai_camera_view/algorithm_library_delete_aicam",{id:this.multipleSelection}).then(e=>{200==e.data.code?(this.$message({type:"success",message:e.data.msg}),this.axioss()):(this.$message({type:"warning",message:e.data.msg}),this.axioss())}).catch(e=>{this.$message({type:"error",message:response.data.msg})})}).catch(e=>{console.log(e),this.$message({type:"info",message:"已取消删除"})}):this.$message({type:"warning",message:"没有选中删除的信息"})},handleRow(e){this.multipleSelection=e.map(e=>e.id)},handleRows(e){this.multipleSelection=e.map(e=>e.id)}},mounted(){this.user_id=this.$store.state.user_role_id||localStorage.getItem("userId"),this.axioss()}},r=o,n=(a("cfe7"),a("2877")),m=Object(n["a"])(r,i,s,!1,null,"0c39d77a",null);t["default"]=m.exports},"7f0a":function(e,t,a){},cfe7:function(e,t,a){"use strict";a("7f0a")}}]);
//# sourceMappingURL=chunk-76b7f37c.b3998d59.js.map
