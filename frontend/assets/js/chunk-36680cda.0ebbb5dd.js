/* native-template-administrator-v1 */
(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["chunk-36680cda"],{"00da":function(t,e,a){"use strict";a("4277")},"0486":function(t,e,a){"use strict";a("14d9");var i=a("cee4"),s=a("4360"),l=a("a18c");const o=i["a"].create({timeout:1e6,withCredentials:!1,headers:{"Content-Type":"application/json"}});o.interceptors.request.use(t=>{const e=s["a"].state.token||localStorage.getItem("token");return e&&(t.headers["Authorization"]="Bearer "+e),t},t=>Promise.reject(t)),o.interceptors.response.use(t=>(console.log(t),401===t.data.code&&(alert("登录状态已过期，请重新登录"),s["a"].commit("delToken"),l["a"].push("/login")),t),t=>(401===t.data.code&&(alert("登录状态已过期，请重新登录"),s["a"].commit("delToken"),l["a"].push("/login")),console.log("error",t),Promise.reject(t))),e["a"]=o},4277:function(t,e,a){},4955:function(t,e,a){"use strict";a.r(e);var i=function(){var t=this,e=t._self._c;return e("div",{staticClass:"sfc"},[e("div",{staticClass:"serch"},[e("el-form",{staticClass:"demo-ruleForm"},[e("el-form-item",{attrs:{label:"解析类型","label-width":"80px"}},[e("el-input",{staticStyle:{width:"100%"},attrs:{autocomplete:"off",clearable:"",placeholder:"请输入解析类型"},on:{input:function(e){return t.axioss()}},model:{value:t.sfname,callback:function(e){t.sfname=e},expression:"sfname"}})],1),e("el-form-item",{attrs:{label:"算法启用","label-width":"80px"}},[e("el-select",{attrs:{placeholder:"请选择",size:"small",clearable:"",filterable:""},on:{change:function(e){return t.axioss()}},model:{value:t.queryParams.algorithm_status,callback:function(e){t.$set(t.queryParams,"algorithm_status",e)},expression:"queryParams.algorithm_status"}},[e("el-option",{attrs:{label:"运行",value:"1"}}),e("el-option",{attrs:{label:"停止",value:"2"}})],1)],1),t.algorithmTemplateAdministrator?e("el-form-item",{attrs:{label:"算法厂商类型","label-width":"130px"}},[e("el-select",{attrs:{placeholder:"请选择算法厂商类型",size:"small",clearable:"",filterable:""},on:{change:function(e){return t.axioss()}},model:{value:t.queryParams.algorithm_trade_type,callback:function(e){t.$set(t.queryParams,"algorithm_trade_type",e)},expression:"queryParams.algorithm_trade_type"}},t._l(t.options1,(function(t){return e("el-option",{key:t.value,attrs:{label:t.label,value:t.value}})})),1)],1):t._e(),e("el-form-item",[e("el-button",{attrs:{icon:"el-icon-search",type:"primary",size:"small"},on:{click:function(e){return t.axioss()}}},[t._v("查询")])],1),e("el-form-item",[e("el-button",{attrs:{icon:"el-icon-setting",type:"success",size:"small"},on:{click:function(e){return t.handleUp()}}},[t._v("上传")])],1),e("el-form-item",[e("el-button",{attrs:{icon:"el-icon-delete",type:"danger",size:"small"},on:{click:function(e){return t.handleDeleteOne()}}},[t._v("删除")])],1)],1)],1),e("div",{staticClass:"table"},[e("div",{staticClass:"jia_table"},[e("el-table",{ref:"singleTable",staticStyle:{width:"100%"},attrs:{data:t.tableData,height:"95%","header-cell-style":{background:"#f9fbff",height:"48.5px",fontSize:"14px"}},on:{select:t.handleRow,"select-all":t.handleRows}},[e("el-table-column",{attrs:{type:"selection",width:"55"}}),e("el-table-column",{attrs:{prop:"index",label:"序号",width:"80"},scopedSlots:t._u([{key:"default",fn:function(e){return[t._v(" "+t._s((Number(t.currentPage)-1)*Number(t.pagesize)+e.$index+1)+" ")]}}])}),e("el-table-column",{attrs:{prop:"algorithm_name",label:"解析类型","show-overflow-tooltip":!0}}),e("el-table-column",{attrs:{prop:"algorithm_version",label:"算法版本","show-overflow-tooltip":!0}}),e("el-table-column",{attrs:{prop:"algorithm_status",label:"算法启用","show-overflow-tooltip":!0},scopedSlots:t._u([{key:"default",fn:function(a){return[t._v(" "+t._s(a.row.algorithm_status)+" "),e("el-switch",{attrs:{disabled:!!t.statusPending[a.row.id],"active-color":"#13ce66","inactive-color":"#ff4949","active-value":"运行","inactive-value":"停止"},on:{change:function(e){return t.handleChangeStatus(a.row)}},model:{value:a.row.algorithm_status,callback:function(e){t.$set(a.row,"algorithm_status",e)},expression:"scope.row.algorithm_status"}})]}}])}),e("el-table-column",{attrs:{prop:"algorithm_trade_type",label:"算法厂商类型"},scopedSlots:t._u([{key:"default",fn:function(a){return[1==t.user_id?e("span",[t._v(t._s(t.handleFindType(a.row.algorithm_trade_type)))]):e("span",[t._v("阳光三极")])]}}])}),e("el-table-column",{attrs:{prop:"create_time",label:"安装时间","show-overflow-tooltip":!0}}),e("el-table-column",{attrs:{prop:"algorithm_ps",label:"算法备注"}})],1),0===t.tableData.length?e("el-empty",{attrs:{image:"/static/img/home/placeholder_kong.png","image-size":307,description:"暂时没有数据~"}}):t._e()],1),e("div",{staticClass:"page"},[e("el-pagination",{attrs:{"current-page":t.currentPage,"page-size":t.pagesize,"page-sizes":t.pagesizes,background:"",layout:"total, prev, pager, next, jumper,sizes",total:t.pagelength},on:{"current-change":t.handleCurrentChange,"size-change":t.handleSizeChange,"update:currentPage":function(e){t.currentPage=e},"update:current-page":function(e){t.currentPage=e}}})],1)]),e("el-dialog",{staticClass:"jia_algoBox",attrs:{title:"算法上传",visible:t.dialogVisible,"close-on-click-modal":!1,width:"900px"},on:{"update:visible":function(e){t.dialogVisible=e},click:function(e){t.dialogVisible=!1}}},[e("el-form",{ref:"jiaRules",staticClass:"sfgl_diaForm",attrs:{model:t.jiaForm,rules:t.rules,"label-position":"top"}},[e("el-form-item",{attrs:{label:"算法上传(请上传单个zip格式压缩包且大小不超过60MB)"}},[e("el-upload",{ref:"upload",attrs:{action:"#","auto-upload":!0,multiple:!1,"file-list":t.fileList,"before-upload":t.beforeUpload,"http-request":t.uploadHttpRequest,"on-remove":t.fileRemove,"on-change":t.fileChange,accept:".zip"}},[e("el-button",{staticStyle:{width:"100%",height:"32px","border-radius":"6px"},attrs:{size:"small",type:"primary",icon:"el-icon-folder-opened"}},[t._v("点击此处上传算法组包")])],1),e("el-upload",{ref:"uploads",attrs:{action:"#","auto-upload":!0,multiple:!1,"file-list":t.fileLists,"before-upload":t.beforeUploads,"http-request":t.uploadHttpRequests,"on-remove":t.fileRemoves,"on-change":t.fileChanges,accept:".zip"}},[e("el-button",{staticStyle:{width:"100%",height:"32px","border-radius":"6px"},attrs:{size:"small",type:"primary",icon:"el-icon-folder-opened"}},[t._v("点击此处上传算法包")])],1),e("p",{staticStyle:{"font-size":"12px","line-height":"1.6",margin:"8px 0 0",color:"#66758c"}},[t._v("普通算法包支持 .om（昇腾）和 .bmodel（算能），模型须与运行设备匹配；.rknn 请前往「AI摄像仪算法安装」。请上传平台格式 ZIP 包。")])],1),e("el-form-item",{staticClass:"jia_formItem2",attrs:{label:"算法启用","label-width":t.formLabelWidth,prop:"algorithm_status"}},[e("el-radio",{attrs:{label:"1"},model:{value:t.jiaForm.algorithm_status,callback:function(e){t.$set(t.jiaForm,"algorithm_status",e)},expression:"jiaForm.algorithm_status"}},[t._v("运行")]),e("el-radio",{attrs:{label:"2"},model:{value:t.jiaForm.algorithm_status,callback:function(e){t.$set(t.jiaForm,"algorithm_status",e)},expression:"jiaForm.algorithm_status"}},[t._v("停止")])],1),e("el-form-item",{attrs:{label:"算法备注","label-width":t.formLabelWidth,prop:"algorithm_ps"}},[e("el-input",{staticStyle:{width:"50%",resize:"none !important"},attrs:{placeholder:"请输入算法备注",type:"textarea",size:"small"},model:{value:t.jiaForm.algorithm_ps,callback:function(e){t.$set(t.jiaForm,"algorithm_ps",e)},expression:"jiaForm.algorithm_ps"}})],1)],1)],1)],1)},s=[],l=(a("d9e2"),a("0486")),o={mixins:[window.PlatformAlgorithmTemplateAdministrator],name:"sfc",data(){return{wjname:"",sfname:"",tableData:[],statusPending:{},listRequestSequence:0,currentPage:1,pagenumber:1,pagesize:15,pagelength:0,pagesizes:[15,35,50,100,150,200,300],dialogVisible:!1,fileList:[],fileLists:[],uploadDisabled:!0,jiaForm:{algorithm_name:"",algorithm_type_list:"['person']",algorithm_version:"v1.0",algorithm_type:"2",algorithm_status:"1",algorithm_ps:"",algorithm_trade_type:""},jiaRules:{},algorithm_statusValue:!1,formLabelWidth:"120px",rules:{},options1:[{label:"寒武纪",value:1},{label:"算能",value:2},{label:"华为",value:3}],options2:[{label:"人员检测模型",value:"['person']"}],multipleSelection:[],queryParams:{algorithm_status:null,algorithm_trade_type:null},user_id:0}},methods:{validateAlgorithmNameFormat(t,e,a){if(e){const t=e.split("-");7!==t.length?a(new Error("算法名称必须由七个部分组成")):a()}else a()},handleFindType(t){let e=this.options1.find(e=>e.value==t);return e.label},handleCurrentChange(t){this.pagenumber=t,this.axioss()},handleSizeChange(t){this.pagesize=t,this.axioss()},axioss() {
      const requestSequence = ++this.listRequestSequence;
      return this.$http
        .get(this.$url.url_5000 + "/model_view/algorithm_data", {
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
    },handleUp(){this.$set(this.jiaForm,"algorithm_name",""),this.$set(this.jiaForm,"algorithm_type_list","['person']"),this.$set(this.jiaForm,"algorithm_version","v1.0"),this.$set(this.jiaForm,"algorithm_type","2"),this.$set(this.jiaForm,"algorithm_status","1"),this.dialogVisible=!0,this.$refs.upload.clearFiles(),this.fileList=[],this.$refs.uploads.clearFiles(),this.fileLists=[]},beforeUpload(t){const e="application/zip"===t.type||"application/x-zip-compressed"===t.type;e||this.$message.error("只能上传 ZIP 格式的文件!")},beforeUploads(t){const e="application/zip"===t.type||"application/x-zip-compressed"===t.type;e||this.$message.error("只能上传 ZIP 格式的文件!")},uploadHttpRequest(param) {
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
              this.$url.url_5000 + "/model_view/algorithm_upload",
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
              this.$url.url_5000 + "/model_view/algorithm_upload_sub",
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
    },submitUpload(){this.$refs.upload.submit()},fileRemove(t,e){e.length<1&&(this.uploadDisabled=!0)},fileChange(t,e){e.length>0&&(this.uploadDisabled=!1,this.fileList=[e[e.length-1]])},fileRemoves(t,e){e.length<1&&(this.uploadDisabled=!0)},fileChanges(t,e){e.length>0&&(this.uploadDisabled=!1,this.fileLists=[e[e.length-1]])},handleClose(){this.fileList=[],this.$nextTick(()=>{this.jiaForm={algorithm_name:"",algorithm_type_list:"['person']",algorithm_version:"v1.0",algorithm_type:"2",algorithm_status:"1",algorithm_ps:"",algorithm_trade_type:""}})},notifyUploadResult(result) {
      const items = Array.isArray(result.data) ? result.data : null;
      if (items && items.length) {
        const h = this.$createElement;
        const hasFailure = items.some(value => !value || Number(value.code) !== 200);
        this.$notify({
          title: '算法上传结果', type: hasFailure ? 'warning' : 'success', duration: 0,
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
        this.$notify({ title: '成功', message: String(result.msg || '上传成功'), type: 'success' });
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
        this.$url.url_5000 + "/model_view/algorithm_data_update",
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
    },handleDeleteOne(){this.multipleSelection.length>0?this.$confirm("此操作将永久删除该条数据, 是否继续?","提示",{confirmButtonText:"确定",cancelButtonText:"取消",type:"warning"}).then(()=>{this.$http.post(this.$url.url_5000+"/model_view/algorithm_library_delete",{id:this.multipleSelection}).then(t=>{200==t.data.code?(this.$message({type:"success",message:t.data.msg}),this.axioss()):(this.$message({type:"warning",message:t.data.msg}),this.axioss())}).catch(t=>{this.$message({type:"error",message:response.data.msg})})}).catch(t=>{console.log(t),this.$message({type:"info",message:"已取消删除"})}):this.$message({type:"warning",message:"没有选中删除的信息"})},handleRow(t){this.multipleSelection=t.map(t=>t.id)},handleRows(t){this.multipleSelection=t.map(t=>t.id)}},mounted(){this.user_id=this.$store.state.user_role_id||localStorage.getItem("userId"),this.axioss()}},r=o,n=(a("00da"),a("2877")),m=Object(n["a"])(r,i,s,!1,null,"60109a28",null);e["default"]=m.exports}}]);
//# sourceMappingURL=chunk-36680cda.5b1653e8.js.map
