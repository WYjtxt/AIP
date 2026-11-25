<template>
  <div class="sfgl" style="overflow-y: auto;">
    <div class="serch">
      <el-form class="demo-ruleForm">
        <el-form-item label="监控点名称" label-width="130px">
          <el-input autocomplete="off" style="width: 100%" v-model="camera_name" placeholder="请输入监控点名称" clearable></el-input>
        </el-form-item>
        <el-form-item>
          <el-button icon="el-icon-search" type="primary" size="small" @click="axioss()">查询</el-button>
          <el-button icon="el-icon-plus" type="success" size="small" @click="handleAdd">新增</el-button>
        </el-form-item>
      </el-form>
    </div>
    <section class="stream-recovery-panel" aria-label="后台自动恢复状态" style="margin: 0 16px 10px;padding: 12px 14px;border: 1px solid #dce5f2;border-radius: 6px;background: #f8faff;font-size: 13px;line-height: 22px;">
  <div style="display: flex;flex-wrap: wrap;gap: 8px 18px;align-items: center;">
    <strong>后台自动恢复</strong>
    <span v-if="streamRecoverySnapshot">{{ streamRecoverySnapshot.enabled ? '已启用' : '未启用' }}</span>
    <span v-else>{{ streamRecoveryLoading ? '正在读取状态…' : '尚未取得状态' }}</span>
    <span style="margin-left: auto;color: #78869a;">最近检查：{{ streamRecoveryCheckedAt }}</span>
  </div>
  <div v-if="streamRecoveryError" role="alert" style="color: #b26a00;">{{ streamRecoveryError }}</div>
  <div v-if="streamRecoverySnapshot" style="display: flex;flex-wrap: wrap;gap: 8px 18px;">
    <span>异常 {{ streamRecoverySummary.abnormal }}</span><span>恢复中 {{ streamRecoverySummary.recovering }}</span>
    <span>认证待维护 {{ streamRecoverySummary.auth }}</span><span>需要关注 {{ streamRecoverySummary.attention }}</span>
  </div>
  <details v-if="streamRecoverySnapshot" style="max-height: 240px;overflow-y: auto;">
    <summary style="cursor: pointer;">查看异常与恢复明细（{{ streamRecoveryDetails.length }}）</summary>
    <div v-if="!streamRecoveryDetails.length" style="color: #78869a;">{{ Number(streamRecoverySnapshot.checked_at) > 0 ? '最近检查未记录异常条目' : '尚未形成检查结果' }}</div>
    <div v-for="device in streamRecoveryDetails" :key="device.id" style="padding: 8px 0;border-top: 1px solid #e5ebf3;">
      <strong>{{ device.name || ('监控点 ' + device.id) }}</strong> · {{ streamRecoveryStateLabel(device.state) }}
      <div>{{ streamRecoveryReasonLabel(device) }}</div>
      <div style="color: #78869a;">下次尝试：{{ streamRecoveryNextAttempt(device) }}<span v-if="device.last_attempt"> · 上次尝试：{{ formatStreamRecoveryTime(device.last_attempt) }}</span></div>
    </div>
  </details>
</section>
    <div class="table" style="height: calc(100% - 170px);min-height: 240px;">
      <div class="jia_table">
        <el-table ref="singleTable" :data="tableData" height="95%" style="width: 100%">
          <el-table-column prop="index" label="序号" width="50">
            <template slot-scope="scope">
              {{ ((Number(currentPage)-1)*Number(pagesize))+scope.$index + 1 }}
            </template>
          </el-table-column>
          <el-table-column prop="cameras_name" sortable label="监控点名称" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column prop="app" label="应用名" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column prop="stream" label="流id" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column prop="schema" label="协议" sortable :show-overflow-tooltip="true"></el-table-column>
          <el-table-column prop="create_date" label="创建时间" :show-overflow-tooltip="true"></el-table-column>
          <!-- <el-table-column prop="mine_code" label="码率" :show-overflow-tooltip="true"></el-table-column> -->
          <!-- <el-table-column prop="mine_code" label="录制" :show-overflow-tooltip="true"></el-table-column> -->
          <!-- <el-table-column prop="mine_code" label="类型" :show-overflow-tooltip="true"></el-table-column> -->
          <el-table-column prop="originUrl" label="源地址" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column prop="stream_url" label="转出地址" ></el-table-column>
          <el-table-column prop="hhh" label="观看人数" :show-overflow-tooltip="true">
            <template slot-scope="scope">
              <el-button @click="gkrs(scope.row)">{{scope.row.readerCount}}/{{scope.row.totalReaderCount}}</el-button>
            </template>
          </el-table-column>
          <!-- <el-table-column prop="mine_code" label="网络信息" :show-overflow-tooltip="true">
            <el-table-column prop="mine_code" label="identifier" :show-overflow-tooltip="true"></el-table-column>
            <el-table-column prop="mine_code" label="local_ip" :show-overflow-tooltip="true"></el-table-column>
            <el-table-column prop="mine_code" label="peer_ip" :show-overflow-tooltip="true"></el-table-column>
          </el-table-column> -->
          <!-- <el-table-column prop="mine_code" label="媒体轨道" :show-overflow-tooltip="true"></el-table-column> -->
          <el-table-column label="操作">
            <template slot-scope="scope">
              <el-button type="text" icon="el-icon-delete" size="mini" @click="handleDelete(scope.row)">关闭</el-button>
            </template>
          </el-table-column>
        </el-table>
        <!-- 如果没有数据，显示空状态 -->
        <el-empty v-if="tableData.length === 0" image="/static/img/home/placeholder_kong.png" :image-size="307" description="暂时没有数据~"></el-empty>
      </div>
      <!-- <div class="page">
        <el-pagination @current-change="handleCurrentChange" @size-change="handleSizeChange" :current-page.sync="currentPage" :page-size="pagesize" :page-sizes="pagesizes" background layout="total, prev, pager, next, jumper,sizes" :total="pagelength">
        </el-pagination>
      </div> -->
    </div>

    <el-dialog :title="title" :visible.sync="dialogFormVisible" width="80%">
      <el-form :model="form" v-if='dialogFormVisible'>
        <el-form-item label="全部监控点" :label-width="formLabelWidth">
          <div style="text-align: center">
            <div class="transferTreeBox">
              <div class="SelectBox">
                <div class="boxTitle" @click="clickAllSelect">未配置监控点 &gt;</div>
                <div class="boxCenter">
                  <el-tree
                    ref="leftTree"
                    :data="leftData"
                    :props="defaultProps"
                    show-checkbox
                    node-key="id"
                  />
                </div>
              </div>
              <div class="transferBtn">
                <el-button type="primary" size="small" @click="towardsLeft"> <i class="el-icon-arrow-left"></i> 移除</el-button>
                <el-button type="primary" size="small" @click="towardsRight">添加<i class="el-icon-arrow-right"></i></el-button>
              </div>
              <div class="SelectBox">
                <div class="boxTitle" @click="clickCancelAllSelect">已配置选中监控点</div>

                <div class="boxCenter">
                  <el-tree
                    ref="rightTree"
                    :data="rightData"
                    :props="defaultProps"
                    show-checkbox
                    node-key="id"
                  />
                </div>
              </div>
            </div>
            <!-- <el-transfer style="text-align: left; display: inline-block" v-model="monitorValue" filterable :left-default-checked="[2, 3]" :right-default-checked="[1]" :titles="['未配置监控点', '已配置选中监控点']" :button-texts="['移除', '添加']" :format="{
                  noChecked: '${total}',
                  hasChecked: '${checked}/${total}'
                }" :data="monitorData" @change="handleChange">
            </el-transfer> -->
          </div>
        </el-form-item>
        <el-form-item label="" :label-width="formLabelWidth">
          <el-checkbox v-model="enable_hls">转hls-mpeg</el-checkbox>
          <el-checkbox v-model="enable_hls_fmp4">转hls-fmp4</el-checkbox>
          <el-checkbox v-model="enable_rtsp">转rtsp</el-checkbox>
          <el-checkbox v-model="enable_rtmp">转rtmp/flv</el-checkbox>
          <el-checkbox v-model="enable_ts">转http-ts/ws-ts</el-checkbox>
          <el-checkbox v-model="enable_fmp4">转http-fmp4/ws-fmp4</el-checkbox>
        </el-form-item>
      </el-form>
      <div slot="footer" class="dialog-footer">
        <el-button @click="dialogFormVisible = false">取 消</el-button>
        <el-button type="primary" @click="submits">确 定</el-button>
      </div>
    </el-dialog>

    <el-dialog title="观看者列表" :visible.sync="dialogFormVisible2" width="80%">
      <el-table :data="gridData">
        <el-table-column property="identifier" label="id"></el-table-column>
        <el-table-column property="local_ip" label="本机ip"></el-table-column>
        <el-table-column property="local_port" label="本机端口"></el-table-column>
        <el-table-column property="peer_ip" label="对端ip"></el-table-column>
        <el-table-column property="peer_port" label="对端端口"></el-table-column>
        <el-table-column property="typeid" label="类型"></el-table-column>
        <el-table-column property="address" label="操作">
            <template slot-scope="scope">
              <el-button type="danger" size="mini" @click="handleDelete1(scope.row)">断开</el-button>
            </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script>
import { modelApi } from "@/api/model/index"
import streamRecoveryStatusMixin from './streamRecoveryStatus';
export default {
  mixins: [streamRecoveryStatusMixin],
  components: {
    History,
  },
  name: "sfgl",
  data() {
    return {
      enable_hls: false,
      enable_hls_fmp4: false,
      enable_rtsp: false,
      enable_rtmp: false,
      enable_ts: false,
      enable_fmp4: false,

      dialogFormVisible2:false,
       gridData: [],
      checked: false,
      camera_name: '',
      title:'',
      formLabelWidth:'100px',
      dialogFormVisible:false,
      form:{
        mine_name:'',
        mine_code:'',
      },
      type:0,
      levelType:'',
      tableData: [],
      currentPage: 1, //默认开始页面 this.$store.state.pages  $store.state.loginuser
      pagenumber: 1, //第几页
      pagesize: 15, //每页的数据条数
      pagelength: 0, //默认数据总数
      pagesizes: [15, 35, 50, 100, 150, 200, 300],

      
      checkedList: [],//已选中数据
      monitorData: [],//所有监控点
      monitorValue: [],//当前选中的监控点
      monitorF: [],//录像机
      selectedMonitor: '', // 用来绑定选中的值
      
      config: {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
      defaultProps: {
        children: 'children',
        label: 'equipment_name',
      },
      leftData: [],
      rightData: [],
      mockTreeData:[],
      checkAll: false,//选中所有
      isIndeterminate: false,
      checkedList: [],//已选中数据
      monitorData: [],//所有监控点
      monitorValue: [],//当前选中的监控点
    };
  },
  computed: {
    
  },
  created() {
    
  },
  methods: {
    gkrs(row){
      if(row.readerCount > 0){
        console.log(row)
      this.$http.post(modelApi.getMediaPlayerList, {
        id: row.id,
        schema: row.schema,
        vhost: row.vhost,
        app: row.app,
        stream: row.stream,
      }, this.config)
      .then(response => {
        if (response.data.code == 200) {
            this.gridData = response.data.data
          }
      }).catch(rek => {
        console.log(rek)
      })
        this.dialogFormVisible2 = true; 
      }
    },
    // 点击向右穿梭
    towardsRight() {
      // (leafOnly, includeHalfChecked) 接收两个 boolean 类型的参数，
      // 1. 是否只是叶子节点，默认值为 false 2. 是否包含半选节点，默认值为 false
      const checkedNodes = this.$refs.leftTree.getCheckedNodes(false, true) // 包含半选
      const checkedKeys = this.$refs.leftTree.getCheckedKeys(false)

      const copyNodes = JSON.parse(JSON.stringify(checkedNodes))
      copyNodes.forEach(x => {
        x.children = []
        if (!this.$refs.rightTree.getNode(x.id)) {
          this.$refs.rightTree.append(x, x.parent_id)
        }
      })

      checkedKeys.forEach(x => {
        this.$refs.leftTree.remove(x)
      })
      this.afterToward()
    },
    // 点击向左穿梭
    towardsLeft() {
      const checkedNodes = this.$refs.rightTree.getCheckedNodes(false, true) // 包含半选
      const checkedKeys = this.$refs.rightTree.getCheckedKeys(false)

      const copyNodes = JSON.parse(JSON.stringify(checkedNodes))
      copyNodes.forEach(x => {
        x.children = []
        if (!this.$refs.leftTree.getNode(x.id)) {
          this.$refs.leftTree.append(x, x.parent_id)
        }
      })

      checkedKeys.forEach(x => {
        this.$refs.rightTree.remove(x)
      })

      this.afterToward()
    },
    // 点击全选
    clickAllSelect() {
      this.$refs.leftTree.setCheckedNodes(this.leftData)

      this.towardsRight()
    },
    // 点击取消全选
    clickCancelAllSelect() {
      this.$refs.rightTree.setCheckedNodes(this.rightData)
      this.towardsLeft()
    },
    // 数据穿梭后
    afterToward() {
      this.$refs.leftTree.setCheckedKeys([])
      this.$refs.rightTree.setCheckedKeys([])
      console.log(this.leftData, this.rightData)
      this.$emit('getData', {
        leftData: this.leftData,
        rightData: this.rightData,
      })
    },
    // 数据回显
    renderTree() {
      this.leftData = [mockTreeData[1]]
      this.rightData = [mockTreeData[0], mockTreeData[2]]
    },
    findEngishName(en) {
      let res = this.timeOptions.find(v => v.value == en)
      return res ? res.label : en
    },
    toggleShowPassword(row) {
      // 确保 row.showPassword 是响应式的
      if (!row.hasOwnProperty('showPassword')) {
        this.$set(row, 'showPassword', false); // 初始化 showPassword
      }
      row.showPassword = !row.showPassword;
    },
    getRowKey(row) {
      return row.id;
    },
    handleCurrentChange(val) {
      this.pagenumber = val;
      this.axioss();
    },
    handleSizeChange(val) {
      this.pagesize = val;
      this.axioss();
    },
    handleRow(val) {
      // console.log(val)
      this.multipleSelection = val;
    },
    handleRows(val) {
      // console.log(val)
      this.multipleSelection = val;
    },
    handleCurrentChange(val) {
      this.pagenumber = val;
      this.axioss();
    },
    handleSizeChange(val) {
      this.pagesize = val;
      this.axioss();
    },
    handleAdd(){
      this.enable_hls = false;
      this.enable_hls_fmp4 = false;
      this.enable_rtsp = false;
      this.enable_rtmp = false;
      this.enable_ts = false;
      this.enable_fmp4 = false;
      this.checkAll = false
      this.isIndeterminate = false
      // this.checkedList = []
      this.$set(this.checkedList, [])
      this.getMonitorList()
      this.rightData=[]
      this.title='新增';
      this.dialogFormVisible=true
    },
    // 获取监控点列表
    getMonitorList() {
      this.$http
        .get(this.$url.url_5000 + "/model_view/equipment_show", {
          params: {
            equipment_name: '',
            equipment_type: '',
            page: 1,
            per_page: 99999999,
          },
        })
        .then((response) => {
          this.mockTreeData = response.data.data_list.data;
          this.leftData = this.mockTreeData
          let res = response.data.data_list.data
          res.forEach((v) => {
            this.monitorF.push(v.equipment_name)
            if (v.children) {
              v.children.forEach(k => {
                let msg = {
                  key: k.id,
                  label: k.equipment_name,
                  ip: k.equipment_ip,
                  parent_ip: k.parent_ip,
                  rtsp: k.rtsp,
                  id: k.id,
                  name: k.equipment_name,
                }
                this.monitorData.push(msg)
              })
            }
          })
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    handleDelete(e){return this.$http.post(modelApi.delStreamProxy,{ids:e.id},this.config).then(e=>{const t=e&&e.data||{};200==t.code?this.$message({message:t.msg||"关闭成功",type:"success"}):this.$message.error(t.msg||"关闭流媒体失败")}).catch(e=>{this.$message.error(e&&e.response&&e.response.data&&e.response.data.msg||"关闭流媒体失败，请稍后重试")}).then(()=>this.axioss())},
    handleDelete1(row){
      this.$http.post(modelApi.kick_session, {
        id: row.identifier
      }, this.config)
      .then(response => {
        if (response.data.code == 200) {
            this.$message({
              message: response.data.msg,
              type: 'success'
            });
            // this.axioss()
          }else{
            this.$message.error(response.data.msg);
          }
      }).catch(rek => {
        console.log(rek)
      })
    },
    submits(){
      this.$http.post(modelApi.addStreamProxy, {
        rtsp_list: JSON.stringify(this.rightData),
        // equipment_name: '',
        // rtsp: rtsps,
        // equipment_name: names,
        enable_hls: this.enable_hls,
        enable_hls_fmp4: this.enable_hls_fmp4,
        enable_rtsp: this.enable_rtsp,
        enable_rtmp: this.enable_rtmp,
        enable_ts: this.enable_ts,
        enable_fmp4: this.enable_fmp4,
      }, this.config)
      .then(response => {
        if (response.data.code == 200) {
            this.$message({
              message: response.data.msg,
              type: 'success'
            });
            this.dialogFormVisible = false
            this.axioss()
        }else{
        this.$message({
          message: response.data.msg,
          type: 'error'
        });
        }
      }).catch(rek => {
        alert(2)
        // this.$message({
        //   message: response.data.msg,
        //   type: 'warning'
        // });
        console.log(rek)
      })
    },
    submitss(){
      this.$http
        .post(this.$url.url_5000 + "/model_view/mine_update",this.form)
        .then((response) => {
          if (response.data.code === 200) {
            this.$message({
              message: response.data.msg,
              type: 'success'
            });
            this.dialogFormVisible = false;
            this.axioss()
          }else{
            this.$message.error(response.data.msg);
          }
        })
        .catch(function (response) {
            this.$message.error(response.data.msg);
          console.log(response);
        });
    },
    axioss() {
      this.$http.post(modelApi.getMediaList, {
        camera_name: this.camera_name
      }, this.config)
      .then(response => {
        if (response.data.code == 200) {
          this.tableData = response.data.data;
          // this.pagelength = response.data.data.pagination.total_items;
        }
      }).catch(rek => {
        console.log(rek)
      })
    },
  },
  mounted() {
    this.axioss();
  },
  beforeDestroy() {
  },
  destroyed() {

  },
};
</script>

<style lang="scss" scoped>
::v-deep.demo-ruleForm {
  .selectImg {
    width: 14px;
    height: 14px;
    margin-top: 13px;
    margin-left: 7px;
  }
  .el-select,
  .el-input {
    width: 177px;
    .el-input__inner {
      width: 177px;
      height: 33px;
      background: #ffffff;
      border-radius: 4px;
      border: 1px solid #b4b2b3;
      box-sizing: border-box;
    }
    .el-input__suffix-inner {
      border-left: 1px solid #b4b2b3;
      .el-icon-arrow-up:before {
        position: relative;
        top: 2px;
      }
    }
  }
}
::v-deep.el-date-editor {
  width: 200px !important;
  .el-input__inner {
    width: 200px !important;
    height: 33px;
    background: #ffffff;
    border-radius: 4px;
    border: 1px solid #b4b2b3;
  }
  .el-icon-time::before {
    content: none;
  }
  .el-icon-time {
    // display: none !important;
    background-image: url("../img/home/alarmlist/time.png"); /* 替换为你自己的图标路径 */
    background-repeat: no-repeat;
    background-position: center;
    width: 16px; /* 图标大小 */
    height: 16px;
    display: inline-block;
    margin-top: 10px;
    margin-left: 4px;
  }
  .el-input__suffix-inner {
    display: inline-block;
    width: 15px;
    height: 15px;
    border-left: 1px solid #b4b2b3;
    margin-top: 11px;
    margin-right: 8px;

    .el-input__icon::before {
      content: "";
      position: absolute;
      top: 3px;
      left: 5px;
      width: 14px;
      height: 14px;
      border: 1px solid #b4b2b3;
      transform: rotate(45deg);
      clip-path: polygon(50% 50%, 100% 50%, 100% 100%, 50% 100%);
    }
  }
}
::v-deep.jia_algoBox {
  .el-dialog {
    box-shadow: 0px 13px 9px 13px #878787;
    border-radius: 18px 18px 18px 18px;
  }
  .el-form {
    .el-form-item {
      margin-bottom: 3px;
      .el-input {
        margin-top: 10px;
        .el-input__inner {
          background-color: #f7f6fb;
          color: 12px;
        }
      }
      .el-textarea__inner {
        background-color: #f7f6fb;
        max-height: 48px !important;
        box-sizing: border-box;
        width: 90%;
      }
    }
    .el-form-item__label {
      padding: 0;
      height: 27px;
    }
    .jia_formItm {
      .el-form-item__content {
        margin-top: 10px;
      }
    }
    .el-cascader,
    .el-select {
      .el-input__suffix-inner {
        border-left: 1px solid #b4b2b3;
      }
    }
    .jia_formItem2 {
      margin-top: 10px;
      position: relative;
      .jia_btn {
        position: absolute;
        top: -35px;
        right: 72px;
        width: 80%;
        height: 32px;
      }
      .Bcanvas {
        margin-left: 100px;
        margin-top: 15px;
      }
      .canvasBtn {
        margin-left: 100px;
        width: 642px;
        height: 39px;
        text-align: center;
        background: rgba(203, 203, 203, 0.2);
        border-radius: 0px 0px 4px 4px;
        .el-button {
          color: rgba(0, 0, 0, 0.6);
          margin-left: 24px;
        }
        .el-button:hover {
          color: #409eff;
        }
      }
    }
    .jia_formItem3 {
      margin-top: 10px;
      position: relative;
      .jia_btn {
        position: absolute;
        top: -35px;
        right: 72px;
        width: 80%;
        height: 32px;
      }
      .Bcanvas {
        margin-left: 100px;
        margin-top: 15px;
      }
      .canvasBtn {
        margin-left: 100px;
        width: 642px;
        height: 39px;
        text-align: center;
        background: rgba(203, 203, 203, 0.2);
        border-radius: 0px 0px 4px 4px;
        .el-button {
          color: rgba(0, 0, 0, 0.6);
          margin-left: 24px;
        }
        .el-button:hover {
          color: #409eff;
        }
      }
    }
  }
}
.sfgl {
  width: 100%;
  height: 100%;
  background-color: #ffffff;
  border-radius: 6px;
  .serch {
    height: 70px;
    padding-top: 16px;
    padding-bottom: 16px;
    box-sizing: border-box;
    position: relative;
    .demo-ruleForm {
      height: 70px;
      display: flex;
      justify-content: flex-start;
      align-items: flex-start;
      flex-wrap: wrap;
    }
  }
  .table {
    height: 87%;
    position: relative;
    .jia_table {
      height: 100%;
      .el-table {
        height: 100%;
        background-image: url("../img/home/placeholder_bottom.png");
        background-position: bottom;
        background-size: 100% 60%;
        background-repeat: no-repeat;
      }
      ::v-deep .el-table--border .el-table__cell,
      .el-table__body-wrapper .el-table--border.is-scrolling-left ~ .el-table__fixed {
        border-right: none;
      }
      ::v-deep .el-table__empty-block {
        // display: none !important;
        .el-table__empty-text {
          color: transparent;
        }
      }
      ::v-deep .el-empty {
        width: 307px;
        height: 353px;
        position: absolute;
        top: 50%;
        left: 50%;
        margin-left: -153px;
        margin-top: -176px;
        .el-empty__image img {
          vertical-align: top;
          height: 147%;
          width: 100%;
        }
        .el-empty__description {
          margin-top: 20px;
          margin-right: 70px;
        }
      }
    }

    .page {
      width: 100%;
      height: 33px;
      // background-color: pink;
      text-align: right;
      position: absolute;
      right: 0;
      bottom: -21px;
    }
    ::v-deep .jia_btn_class {
      .cell {
        padding: 0;
        display: flex;
        justify-content: space-around;
        align-items: center;
        flex-wrap: nowrap;
        .el-button {
          margin: 0;
        }
      }
    }
  }

  .sfgl_diaForm {
    display: flex;
    flex-wrap: wrap;

    .el-form-item {
      width: 50%;
    }
  }

  .jia_btn {
    width: 640px;
    height: 40px;
    // background-color: pink;
    display: flex;
    align-items: center;
    justify-content: space-between;
    .jia_btnTop {
      width: 100%;
      height: 100%;
    }
    .jia_color {
      width: 384px;
      height: 100%;
      position: relative;
      bottom: -15px;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      flex-wrap: nowrap;
      .color_box {
        width: 100px;
        height: 100%;
        display: flex;
        align-items: center;
        .color {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .color1 {
          background-color: #ff0000;
        }
        .color2 {
          background-color: #ffa500;
        }
        .color3 {
          background-color: #fcff00;
        }
        .color4 {
          background-color: #8a8383;
        }
        .text {
          width: auto;
          height: 15px;
          font-family: "MicrosoftYaHei";
          font-size: 14px;
          color: #606266;
          line-height: 15px;
          text-align: center;
          font-style: normal;
          text-transform: none;
        }
      }
    }
    .jia_color3 {
      width: 384px;
      height: 100%;
      position: relative;
      bottom: -15px;
      right: -367px;
      display: flex;
      align-items: center;
      justify-content: flex-start;
      flex-wrap: nowrap;
      .color_box {
        width: 100px;
        height: 100%;
        display: flex;
        align-items: center;
        .color {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .color1 {
          background-color: #ff0000;
        }
        .color2 {
          background-color: #ffa500;
        }
        .color3 {
          background-color: #fcff00;
        }
        .color4 {
          background-color: #8a8383;
        }
        .text {
          width: auto;
          height: 15px;
          font-family: "MicrosoftYaHei";
          font-size: 14px;
          color: #606266;
          line-height: 15px;
          text-align: center;
          font-style: normal;
          text-transform: none;
        }
      }
    }
  }

  .Bcanvas {
    width: 640px;
    height: 360px;
    position: relative;

    .jia_div {
      width: 640px;
      height: 360px;
      position: absolute;
      top: 0;
      left: 0;
      z-index: 11;
      line-height: 360px;
      text-align: center;
      color: red;
      border: 1px solid rgb(102, 101, 101);
    }

    img {
      position: relative;
      z-index: 9;
    }

    #mycanvas {
      position: absolute;
      top: 0;
      left: 0;
      z-index: 10;
    }
    #mycanvas_model {
      position: absolute;
      top: 0;
      left: 0;
      z-index: 10;
    }
    #mycanvas2 {
      position: absolute;
      top: 0;
      left: 0;
      z-index: 10;
    }
  }
}

.transferTreeBox {
  display: flex;
  width: 590px;
  justify-content: space-around;

  .SelectBox {
    border: 1px solid #ccc;
    height: 270px;
    width: 200px;
    color: #fff;
    position: relative;

    .boxTitle {
      background: #a0cfff;
      height: 30px;
      line-height: 30px;
      text-align: center;
      border-bottom: 1px solid #ccc;
      cursor: pointer;
    }

    .boxCenter {
      height: 100%;
      width: 100%;
      max-height: 239px;
      overflow-y: scroll;
    }
  }

  .transferBtn {
    position: relative;
    display: flex;
    /* flex-direction: column; */
    align-items: center;
    justify-content: center;

    .pickBtn {
      height: 30px;
      width: 50px;
      float: left;
      padding: 0 10px;
      background: #a0cfff;
      color: #fff;
      font-weight: 700;
      font-size: 14px;
      border-radius: 5px;
      margin-top: 10px;
      text-align: center;
      line-height: 30px;
      cursor: pointer;
    }
  }
}
</style>
