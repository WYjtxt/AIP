/* hik-security-platform-connection-v1 */
/* hik-security-platform-delete-v1 */
(window["webpackJsonp"]=window["webpackJsonp"]||[]).push([["chunk-4ad89578"],{"0109":function(e,t,a){"use strict";a.r(t);var i=function(){var e=this,t=e._self._c;return t("div",{staticClass:"hkaf"},[t("div",{staticClass:"serch"},[t("el-button",{attrs:{type:"primary",size:"small"},on:{click:e.handleClickAdd}},[t("i",{staticClass:"el-icon-plus"}),e._v("  新增")])],1),t("div",{staticClass:"table"},[t("div",{staticClass:"jia_table"},[t("el-table",{staticStyle:{width:"100%"},attrs:{data:e.tableData,height:"95%","header-cell-style":{background:"#f9fbff",height:"48.5px",fontSize:"14px"},"row-key":"treeKey","tree-props":{children:"children_qdsj",hasChildren:"hasChildren"},"span-method":e.arraySpanMethod}},[t("el-table-column",{attrs:{label:"序号",type:"index",index:e.indexMethod}}),t("el-table-column",{attrs:{prop:"hik_name",label:"安防平台区域名称"}}),t("el-table-column",{attrs:{prop:"hik_host",label:"安防平台地址"}}),t("el-table-column",{attrs:{prop:"hik_port",label:"端口"}}),t("el-table-column",{attrs:{label:"安防平台识别码",width:"150"},scopedSlots:e._u([{key:"default",fn:function(a){return[a.row.showIce?t("span",[e._v(e._s(a.row.hik_appKey))]):t("span",[e._v(e._s(e.maskedValue(a.row.hik_appKey)))]),e._v("    "),t("i",{staticClass:"el-icon-view",staticStyle:{"font-size":"16px",cursor:"pointer"},on:{click:function(t){return t.preventDefault(),e.handleUpdateAppKey(a.row)}}})]}}])}),t("el-table-column",{attrs:{label:"安防平台密钥",width:"260"},scopedSlots:e._u([{key:"default",fn:function(a){return[a.row.showSecret?t("span",[e._v(e._s(a.row.hik_appSecret))]):t("span",[e._v(e._s(e.maskedValue(a.row.hik_appSecret)))]),e._v("    "),a.row.showSecret?e._e():t("i",{staticClass:"el-icon-view",staticStyle:{"font-size":"16px",cursor:"pointer"},on:{click:function(t){return t.preventDefault(),e.handleUpdateSecret(a.row)}}})]}}])}),t("el-table-column",{attrs:{prop:"hik_artemis",label:"安防平台节点"}}),t("el-table-column",{attrs:{prop:"created_at",label:"创建时间"},scopedSlots:e._u([{key:"default",fn:function(t){return[e._v(" "+e._s(e.formatDate(t.row.created_at))+" ")]}}])}),t("el-table-column",{attrs:{prop:"updated_at",label:"更新时间"},scopedSlots:e._u([{key:"default",fn:function(t){return[e._v(" "+e._s(e.formatDate(t.row.updated_at))+" ")]}}])}),t("el-table-column",{attrs:{label:"操作","min-width":132},scopedSlots:e._u([{key:"default",fn:function(a){return[t("el-button",{attrs:{type:"text",icon:"el-icon-edit",size:"small"},on:{click:function(t){return e.openEditDialog(a.row)}}},[e._v("详情")]),e.canDeletePlatform&&e.isHikPlatformRow(a.row)?t("el-button",{
      attrs:{type:"text",icon:"el-icon-delete",size:"small",disabled:e.deletingPlatform},
      on:{click:function(){return e.handleDeletePlatform(a.row)}}
    },[e._v("删除")]):e._e()]}}])})],1),0===e.tableData.length?t("el-empty",{attrs:{image:"/static/img/home/placeholder_kong.png","image-size":307,description:"暂时没有数据~"}}):e._e()],1),t("div",{staticClass:"jia_page"},[t("el-pagination",{directives:[{name:"show",rawName:"v-show",value:e.total>0,expression:"total > 0"}],attrs:{total:e.total,"current-page":e.pageNum,"page-size":e.pageSize,layout:"total, prev, pager, next, jumper, sizes"},
    on:{"current-change":e.changePlatformPage,"size-change":e.changePlatformPageSize}})],1)]),t("el-dialog",{attrs:{title:"详情信息",visible:e.detailOpen,width:"80%"},on:{"update:visible":function(t){e.detailOpen=t}}},[t("el-descriptions",{attrs:{title:"设备类型"}},[t("el-descriptions-item",{attrs:{label:"设备名称"}},[e._v(" "+e._s(e.detailForm.name)+" ")]),t("el-descriptions-item",{attrs:{label:"设备编码"}},[e._v(" "+e._s(e.detailForm.indexCode)+" ")]),t("el-descriptions-item",{attrs:{label:"创建时间"}},[e._v(" "+e._s(e.detailForm.created_at)+" ")]),t("el-descriptions-item",{attrs:{label:"更新时间"}},[e._v(" "+e._s(e.detailForm.updated_at)+" ")])],1),t("el-descriptions",{staticClass:"jia_description",attrs:{title:"通道信息"}},[t("el-descriptions-item",[t("div",{staticStyle:{width:"100%"}},[t("el-table",{staticStyle:{width:"100%"},attrs:{data:e.detailTable,height:"390px"}},[t("el-table-column",{attrs:{label:"序号",type:"index",width:"80"}}),t("el-table-column",{attrs:{prop:"manufacturer_type",label:"厂商类型"}}),t("el-table-column",{attrs:{prop:"equipment_ip",label:"IP地址"}}),t("el-table-column",{attrs:{prop:"equipment_type",label:"设备类型"}}),t("el-table-column",{attrs:{prop:"equipment_name",label:"设备名称"}}),t("el-table-column",{attrs:{prop:"Hik_indexCode",label:"监控点编码"}}),t("el-table-column",{attrs:{prop:"Hik_rtsp_url",label:"视频流","show-overflow-tooltip":!0}})],1)],1),t("br")])],1),t("div",{staticClass:"jia_page"},[t("el-pagination",{directives:[{name:"show",rawName:"v-show",value:e.detailTotal>0,expression:"detailTotal > 0"}],attrs:{"current-page":e.detailpage,"page-size":e.detailper_page,layout:"total, sizes, prev, pager, next, jumper",total:e.detailTotal},on:{"current-change":e.handleChangeDetail,"size-change":e.handleChangeDetail,"update:currentPage":function(t){e.detailpage=t},"update:current-page":function(t){e.detailpage=t},"update:pageSize":function(t){e.detailper_page=t},"update:page-size":function(t){e.detailper_page=t}}})],1)],1),t("el-dialog",{
  attrs:{title:"新增配置",visible:e.dialogVisible,width:"500px",
    "close-on-click-modal":!e.hikRequest,"close-on-press-escape":!e.hikRequest,"show-close":!e.hikRequest},
  on:{"update:visible":function(visible){if(!e.hikRequest)e.dialogVisible=visible;},close:e.resetForm}
},[
  t("el-form",{ref:"form",staticClass:"demo-addUpdateForm",
    attrs:{model:e.formData,"label-position":"top",disabled:!!e.hikRequest}},[
    t("el-form-item",{attrs:{label:"接入协议",prop:"hik_scheme"}},[
      t("el-radio-group",{props:{value:e.formData.hik_scheme},on:{input:function(value){e.setGatewayField("hik_scheme",value);}}},[
        t("el-radio-button",{attrs:{label:"https"}},[e._v("HTTPS")]),
        t("el-radio-button",{attrs:{label:"http"}},[e._v("HTTP")])
      ],1)
    ],1),
    t("el-form-item",{attrs:{label:"平台地址",prop:"hik_host"}},[
      t("el-input",{attrs:{placeholder:"输入 IP 地址或域名，也可粘贴完整地址"},
        props:{value:e.formData.hik_host},on:{input:function(value){e.setGatewayField("hik_host",value);}}})
    ],1),
    t("el-form-item",{attrs:{label:"平台端口",prop:"hik_port"}},[
      t("el-input",{attrs:{inputmode:"numeric",placeholder:e.formData.hik_scheme==="https"?"默认 443":"默认 80"},
        props:{value:e.formData.hik_port},on:{input:function(value){e.setGatewayField("hik_port",value);}}})
    ],1),
    t("el-form-item",{attrs:{label:"AppKey",prop:"hik_appKey"}},[
      t("el-input",{attrs:{placeholder:"请输入安防平台 AppKey",autocomplete:"off"},
        props:{value:e.formData.hik_appKey},on:{input:function(value){e.setGatewayField("hik_appKey",value);}}})
    ],1),
    t("el-form-item",{attrs:{label:"AppSecret",prop:"hik_appSecret"}},[
      t("el-input",{attrs:{placeholder:"请输入安防平台 AppSecret",type:"password",autocomplete:"new-password"},
        props:{value:e.formData.hik_appSecret},on:{input:function(value){e.setGatewayField("hik_appSecret",value);}}})
    ],1),
    t("el-form-item",{attrs:{label:"单位",prop:"Mine_id"}},[
      t("el-select",{attrs:{placeholder:"请选择单位"},props:{value:e.formData.Mine_id},
        on:{input:function(value){e.setGatewayField("Mine_id",value);}}},
        e._l(e.Mine_id_type,function(unit){return t("el-option",{key:unit.id,attrs:{label:unit.mine_name,value:unit.id}});}),1)
    ],1)
  ],1),
  e.hikResult?t("el-alert",{attrs:{title:e.hikResult.message,type:e.hikResult.type,"show-icon":true,closable:false}}):e._e(),
  t("div",{staticClass:"dialog-footer",attrs:{slot:"footer"},slot:"footer"},[
    t("el-button",{attrs:{disabled:!!e.hikRequest},on:{click:function(){e.dialogVisible=false;}}},[e._v("取消")]),
    t("el-button",{attrs:{disabled:!!e.hikRequest,loading:e.hikRequest==="test"},on:{click:e.testConnection}},[e._v("测试连接")]),
    t("el-button",{attrs:{type:"primary",disabled:!!e.hikRequest,loading:e.hikRequest==="save"},on:{click:e.submitForm}},[e._v("确认接入")])
  ],1)
],1)],1)},l=[];a("14d9");const verifiedConnections=new WeakMap();
function connectionKey(payload){
  return JSON.stringify(["hik_host","hik_port","hik_appKey","hik_appSecret"].map(field=>payload.get(field)));
}
function connectionPort(value){
  if(!/^[0-9]{1,5}$/.test(value)||Number(value)<1||Number(value)>65535){
    throw new Error("请输入 1–65535 之间的端口号");
  }
  return String(Number(value));
}
function connectionPayload(form, saving){
  const scheme=form.hik_scheme;
  if(scheme!=="https"&&scheme!=="http")throw new Error("请选择接入协议");
  const input=String(form.hik_host||"").trim();
  const explicit=input.match(/^(https?):\/\//i);
  if(explicit&&explicit[1].toLowerCase()!==scheme){
    throw new Error("平台地址中的协议与所选协议不一致");
  }
  let authority=(explicit?input.slice(explicit[0].length):input).replace(/\/$/,"");
  if(!authority||/[\s\/\\@?#%]/.test(authority)){
    throw new Error("请输入平台 IP 地址或域名，地址中不能包含路径或账号");
  }
  if(!authority.startsWith("[")&&(authority.match(/:/g)||[]).length>1)authority="["+authority+"]";
  const parts=authority.match(/^(\[[0-9a-f:.]+\]|[A-Za-z0-9.-]+)(?::([0-9]+))?$/i);
  if(!parts)throw new Error("请输入有效的平台 IP 地址或域名");
  let hostname;
  try{
    hostname=new URL(scheme+"://"+parts[1]).hostname;
    if(!parts[1].startsWith("[")&&(hostname!==parts[1].toLowerCase()||
      hostname.length>253||!hostname.replace(/\.$/,"").split(".").every(
        label=>/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)
      )))throw new Error();
  }catch(error){
    throw new Error("请输入有效的平台 IP 地址或域名");
  }
  const host=scheme+"://"+hostname;
  if(host.length>50)throw new Error("平台地址含协议最多 50 个字符，请使用较短域名或 IP 地址");
  const portField=String(form.hik_port||"").trim();
  const separatePort=portField?connectionPort(portField):"";
  const addressPort=parts[2]?connectionPort(parts[2]):"";
  if(separatePort&&addressPort&&separatePort!==addressPort){
    throw new Error("平台地址中的端口与端口栏不一致");
  }
  const appKey=String(form.hik_appKey||"").trim();
  const appSecret=String(form.hik_appSecret||"").trim();
  if(!appKey||!appSecret)throw new Error("请填写 AppKey 和 AppSecret");
  if(saving&&!form.Mine_id)throw new Error("请选择单位");
  const payload=new FormData();
  payload.append("hik_host",host);
  payload.append("hik_port",separatePort||addressPort||(scheme==="https"?"443":"80"));
  payload.append("hik_appKey",appKey);
  payload.append("hik_appSecret",appSecret);
  if(form.Mine_id)payload.append("Mine_id",String(form.Mine_id));
  return payload;
}
function blankGatewayForm(){
  return {hik_scheme:"https",hik_host:"",hik_port:"",hik_appKey:"",hik_appSecret:"",Mine_id:""};
}
const r={
      testHkafConnection:window.wgParameter.url_5000+"/hik_security_platform_info_view/hik_security_platform_test",
      deleteHkafPlatform:window.wgParameter.url_5000+"/hik_security_platform_info_view/hik_security_platform_delete",
      getHkafList:window.wgParameter.url_5000+"/hik_security_platform_info_view/hik_security_platform_data",getHkafJkdList:window.wgParameter.url_5000+"/hik_security_platform_info_view/hik_security_platform_resource_data",addHkafList:window.wgParameter.url_5000+"/hik_security_platform_info_view/hik_security_platform_add"};var o={data(){return{tableData:[],total:0,pageNum:1,pageSize:10,canDeletePlatform:!1,deletingPlatform:!1,detailOpen:!1,detailForm:{},detailTable:[],detailpage:1,detailper_page:10,detailTotal:0,detailId:null,dialogVisible:!1,formData:blankGatewayForm(),hikRequest:"",hikRevision:0,hikResult:null,Mine_id_type:[]}},created(){this.getData(),this.getDictData()},mounted(){},methods:{arraySpanMethod({row:e,column:t,rowIndex:a,columnIndex:i}){this.tableData;let l=this.tableData.length,r=[],o=0;for(let s=0;s<l;s++)o=s,r.push(o);if(!this.isHikPlatformRow(e)){if(1===i)return[1,2];if(2===i)return[0,0];if(4===i)return[1,3];if(5===i||6===i)return[0,0]}return[1,1]},getDictData(){this.$http.get(this.$url.url_5000+"/model_view/type_select",{params:{mine_id:"1"}}).then(e=>{200===e.data.code&&(this.Mine_id_type=e.data.mine_list,this.formData.Mine_id=this.Mine_id_type[0].id)}).catch((function(e){console.log(e)}))},maskedValue(e){if(e)return e.replace(/./g,"*")},indexMethod(e){return(this.pageNum-1)*this.pageSize+1+e},formatDate(e){const t=new Date(e),a=t.getFullYear(),i=String(t.getMonth()+1).padStart(2,"0"),l=String(t.getDate()).padStart(2,"0"),r=String(t.getHours()).padStart(2,"0"),o=String(t.getMinutes()).padStart(2,"0"),s=String(t.getSeconds()).padStart(2,"0"),n=`${a}-${i}-${l} ${r}:${o}:${s}`;return n},getData(){
      return this.$http.get(r.getHkafList,{params:{page:this.pageNum,per_page:this.pageSize}}).then(response=>{
        const body=response.data;
        if(Number(body.code)!==200){this.canDeletePlatform=false;return;}
        const page=body.data;
        this.canDeletePlatform=page.can_delete===true;
        this.total=page.pagination.total_items;
        this.tableData=page.data.map(platform=>({
          ...platform,treeKey:"platform-"+platform.id,showIce:false,showSecret:false,
          children_qdsj:platform.children_list.map(area=>({
            id:area.id,treeKey:"area-"+area.id,hik_appKey:area.indexCode,hik_name:area.name,
            created_at:area.created_at,updated_at:area.updated_at,hik_appSecret:null,hik_artemis:null,
            hik_host:null,hik_methon:null,Mine_id:null,showIce:false,showSecret:true
          }))
        }));
      }).catch(()=>{this.canDeletePlatform=false;});
    },changePlatformPage(page){
      if(this.pageNum===page)return;
      this.pageNum=page;
      this.getData();
    },changePlatformPageSize(size){
      if(this.pageSize===size)return;
      this.pageSize=size;
      this.pageNum=1;
      this.getData();
    },isHikPlatformRow(row){
      return !!row&&Array.isArray(row.children_list)&&Number.isSafeInteger(Number(row.id))&&Number(row.id)>0;
    },async handleDeletePlatform(row){
      if(!this.canDeletePlatform||this.deletingPlatform||!this.isHikPlatformRow(row))return;
      this.deletingPlatform=true;
      try{
        try{
          await this.$confirm("删除「"+(row.hik_name||row.hik_host||row.id)+"」的接入配置及其同步区域、未绑定任务的监控点？存在关联算法任务时将阻止删除。","删除安防平台",{
            confirmButtonText:"删除",cancelButtonText:"取消",type:"warning"
          });
        }catch(cancelled){return;}
        const data=new FormData;
        data.append("id",String(row.id));
        const response=await this.$http.post(r.deleteHkafPlatform,data,{headers:{"Content-Type":"multipart/form-data"}});
        const body=response.data;
        if(Number(body.code)===200){
          this.$message({type:"success",message:body.msg||"安防平台已删除"});
          if(this.tableData.length===1&&this.pageNum>1)this.pageNum--;
          await this.getData();
        }else this.$message({type:"warning",message:body.msg||"删除安防平台失败"});
      }catch(error){
        const body=error.response&&error.response.data;
        this.$message({type:"error",message:body&&body.msg||"删除安防平台失败，请稍后重试"});
      }finally{this.deletingPlatform=false;}
    },handleUpdateAppKey(e){e.showIce=!e.showIce},handleUpdateSecret(e){e.showSecret=!e.showSecret},openEditDialog(e){this.detailId=e.id,this.$http.get(r.getHkafJkdList,{params:{page:this.detailpage,per_page:this.detailper_page,id:e.id}}).then(e=>{this.detailForm=e.data.data,this.detailTable=e.data.data.children,this.detailTotal=e.data.data.total,this.detailOpen=!0}).catch(e=>{console.log(e)})},handleChangeDetail(){this.$http.get(r.getHkafJkdList,{params:{page:this.detailpage,per_page:this.detailper_page,id:this.detailId}}).then(e=>{this.detailForm=e.data.data,this.detailTable=e.data.data.children,this.detailTotal=e.data.data.total}).catch(e=>{console.log(e)})},handleClickAdd(){this.dialogVisible=!0},setGatewayField(name,value){
  this.formData[name]=value;
  if(name==="hik_host"){
    const scheme=String(value).trim().match(/^(https?):\/\//i);
    if(scheme)this.formData.hik_scheme=scheme[1].toLowerCase();
  }
  if(name!=="Mine_id"){
    verifiedConnections.delete(this);
    this.hikRevision++;
    this.hikResult=null;
  }
},testConnection(){
  return this.requestGateway("test");
},submitForm(){
  return this.requestGateway("save");
},async requestGateway(operation){
  if(this.hikRequest)return;
  const saving=operation==="save";
  let form;
  try{
    form=connectionPayload(this.formData,saving);
  }catch(error){
    this.hikResult={type:"warning",message:error.message};
    return;
  }
  const key=connectionKey(form);
  if(saving&&verifiedConnections.get(this)!==key){
    this.hikResult={type:"warning",message:"请先测试当前连接配置，测试通过后再确认接入"};
    return;
  }
  if(!saving)verifiedConnections.delete(this);
  const revision=this.hikRevision;
  this.hikResult=null;
  this.hikRequest=operation;
  const fallback=saving?"接入失败，请稍后重试":"测试连接失败，请稍后重试";
  try{
    const response=await this.$http.post(saving?r.addHkafList:r.testHkafConnection,form,{
      headers:{"Content-Type":"multipart/form-data"}
    });
    if(revision!==this.hikRevision)return;
    const body=response.data||{};
    if(Number(body.code)!==200){
      this.hikResult={type:"warning",message:body.msg||fallback};
      return;
    }
    if(saving){
      this.$message({type:"success",message:body.msg||"安防平台已接入"});
      this.dialogVisible=false;
      await this.getData();
    }else{
      const data=body.data||{};
      if(data.region_count===0){
        this.hikResult={type:"warning",message:"连接成功，当前应用没有可访问区域，请核对资源授权"};
        return;
      }
      verifiedConnections.set(this,key);
      let message=body.msg||"连接成功";
      if(Number.isInteger(data.region_count)&&data.region_count>0)message+="，可访问区域 "+data.region_count+" 个";
      if(Number.isInteger(data.camera_count)&&data.camera_count>=0)message+="，抽查区域监控点 "+data.camera_count+" 个";
      this.hikResult={type:"success",message};
    }
  }catch(error){
    if(revision!==this.hikRevision)return;
    const body=error.response&&error.response.data;
    this.hikResult={type:"error",message:body&&body.msg||fallback};
  }finally{
    this.hikRequest="";
  }
},resetForm(){
  verifiedConnections.delete(this);
  this.hikRevision++;
  this.formData=blankGatewayForm();
  this.hikResult=null;
}}},s=o,n=(a("f88f"),a("2877")),p=Object(n["a"])(s,i,l,!1,null,"c418c54c",null);t["default"]=p.exports},"0c3e":function(e,t,a){},f88f:function(e,t,a){"use strict";a("0c3e")}}]);
//# sourceMappingURL=chunk-4ad89578.44b8599c.js.map