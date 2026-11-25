<template>
  <div class="sfgl">
    <div class="serch">
      <el-form class="demo-ruleForm">
        <el-form-item label="任务名称" label-width="130px">
          <el-input autocomplete="off" style="width: 100%" v-model="conf_name" placeholder="请输入任务名称" clearable @input="queryAlgorithms()"></el-input>
        </el-form-item>
        <el-form-item label="解析类型" label-width="80px">
          <el-select v-model="algorithm_library_id" placeholder="请选择解析类型" size="small" clearable filterable style="width: 90%" @change="queryAlgorithms()">
            <span slot="prefix" class="select-icon">
              <img class="selectImg" src="../img/home/alarmlist/algorithm.png" alt="">
            </span>
            <el-option v-for="item in options3" :key="item.id" :label="item.algorithm_name" :value="item.id"> </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="单位名称" label-width="80px">
          <el-select v-model="mkname" placeholder="请选择单位名称" size="small" @change="queryAlgorithms()" clearable filterable>
            <span slot="prefix" class="select-icon">
              <img class="selectImg" src="../img/home/alarmlist/mk.png" alt="">
            </span>
            <el-option v-for="item in options1" :key="item.id" :label="item.mine_name" :value="item.id"></el-option>
          </el-select>
        </el-form-item>
        <!-- <el-form-item label="模板大类" label-width="80px">
          <el-select v-model="template_type_id" placeholder="请选择模板大类" size="small" clearable filterable style="width: 90%" @change="axioss()">
            <span slot="prefix" class="select-icon">
              <img class="selectImg" src="../img/home/alarmlist/algorithm.png" alt="">
            </span>
            <el-option v-for="item in modelTypeOptions" :key="item.id+item.model_type_name" :label="item.model_type_name" :value="item.id"> </el-option>
          </el-select>
        </el-form-item> -->
        <!-- <el-form-item label="选择时间" label-width="80px" prop="StartTime">
          <el-date-picker value-format="yyyy-MM-dd HH:mm:ss" type="datetime" v-model="StartTime" placeholder="选择时间" size="small" clearable @change="axioss()" :picker-options="startTimePickerOptions"> </el-date-picker>
        </el-form-item>
        <el-form-item label="至" label-width="30px" prop="EndTime">
          <el-date-picker value-format="yyyy-MM-dd HH:mm:ss" type="datetime" v-model="EndTime" placeholder="选择时间" size="small" clearable @change="axioss()" :picker-options="endTimePickerOptions"> </el-date-picker>
        </el-form-item> -->
        <el-form-item>
          <el-button icon="el-icon-search" type="primary" size="small" @click="queryAlgorithms()">查询</el-button>
        </el-form-item>
        <el-form-item>
          <el-button icon="el-icon-setting" type="success" size="small" @click="handleadds()">配置</el-button>
          <!-- <el-button icon="el-icon-setting" type="success" size="small" @click="handleadd()">配置(窗)</el-button> -->
        </el-form-item>
        <el-form-item>
          <el-button icon="el-icon-setting" type="success" size="small" @click="handleaddss()">高级配置</el-button>
        </el-form-item>
        <el-form-item>
          <el-button icon="el-icon-delete" type="danger" size="small" :disabled="batchStatusBusy" @click="handledel()">删除</el-button>
        </el-form-item>
        <el-form-item>
          <el-button icon="el-icon-refresh" size="small" @click="axioss()">刷新</el-button>
        </el-form-item>
        <!-- <el-form-item>
          <el-button icon="el-icon-s-data" type="" size="small" @click="handleOpenHistory()">历史记录</el-button>
        </el-form-item> -->
      </el-form>
    </div>
    <div class="table">
      <div class="batch-toolbar" style="display: flex; align-items: center; gap: 10px; height: 48px; padding: 0 16px; box-sizing: border-box;">
        <span style="margin-right: auto; color: #66758c;">当前页已选 {{ multipleSelection.length }} 项<span v-if="multipleSelection.length > 100" style="color: #c45656;">，单次最多 100 项</span><span role="status" style="display: block;font-size: 12px;line-height: 18px;color: #78869a;">{{ algorithmRuntimeHealthError || (algorithmRuntimeHealthUpdatedAt ? '运行状态更新于 ' + algorithmRuntimeHealthUpdatedAt : '运行状态自动刷新') }}</span></span>
        <el-button size="small" type="success" icon="el-icon-video-play" :disabled="batchStatusUnavailable()" :loading="batchStatusBusy && batchRequestedStatus === '运行'" @click="handleBatchStatus('运行')">批量启动</el-button>
        <el-button size="small" type="danger" icon="el-icon-video-pause" :disabled="batchStatusUnavailable()" :loading="batchStatusBusy && batchRequestedStatus === '停止'" @click="handleBatchStatus('停止')">批量停止</el-button>
      </div>
      <div class="jia_table" style="height: calc(100% - 48px);">
        <el-table ref="singleTable" :data="tableData" :row-key="getRowKey" height="95%" style="width: 100%" :header-cell-style="{ background: '#f9fbff',height:'48.5px',fontSize:'14px', }" @select="handleRow" @select-all="handleRows">
          <el-table-column type="selection" width="55" :selectable="canSelectBatchRow"></el-table-column>
          <el-table-column prop="index" label="序号" width="50">
            <template slot-scope="scope">
              {{ ((Number(currentPage)-1)*Number(pagesize))+scope.$index + 1 }}
            </template>
          </el-table-column>
          <el-table-column prop="mine_name" label="单位名称" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column prop="conf_name" label="任务名称" :show-overflow-tooltip="true" width="230px"></el-table-column>
          <el-table-column prop="algorithm_name" label="解析类型" :show-overflow-tooltip="true" width="230px">
            <template slot-scope="scope">
              <div v-if="scope.row.merged_model_data == '[]'">
                {{ scope.row.algorithm_name  }}
              </div>
              <div v-else>
                <span v-for="(item,index) in scope.row.merged_model_data.model_data" :key="index">{{ item.algorithm_name }};</span>
              </div>
            </template>
          </el-table-column>
          <!-- <el-table-column prop="model_type_name" label="模板大类" :show-overflow-tooltip="true"></el-table-column> -->
          <el-table-column prop="equipment_name" label="报警设备" width="180px" :show-overflow-tooltip="true"></el-table-column>
          <!-- <el-table-column prop="conf_object" label="分析对象" align='center' :show-overflow-tooltip="true"></el-table-column> -->
          <el-table-column prop="conf_time" label="创建时间" width="160px"></el-table-column>
          <el-table-column prop="conf_area" label="分析区域" width="180px">
            <template slot-scope="scope">
            <div style="width: 96px; height: 54px; position: relative" @click="handleOpenTableImg(scope.row.id)"> 
                <!-- <span>{{process.env.VUE_APP_BASE_API + scope.row.image}}</span> -->
              <!-- <img :src="process.env.VUE_APP_BASE_API + scope.row.image" style="width: 96px; height: 54px; position: absolute; top: 0; left: 0; z-index: 9" /> -->
              <img v-roi-image="{ path: scope.row.image, epoch: roiThumbnailEpoch }" style="width: 96px; height: 54px; position: absolute; top: 0; left: 30px; z-index: 9" />
              <canvas
                :id="'tableCanvas_' + scope.row.id"
                :ref="'tableCanvas_' + scope.row.id"
                tabindex="0"
                style="
                  position: absolute;
                  top: 0;
                  left: 30px;
                  z-index: 10;
                  cursor: none;
                "
              ></canvas>
            </div>
          </template>
          </el-table-column>
          <!-- <el-table-column prop="duration_time" label="持续时间（s）"  :show-overflow-tooltip="true"></el-table-column> -->
          <!-- <el-table-column prop="status" label="状态">
            <template slot-scope="scope">
              {{ scope.row.status }}
              <el-switch v-model="scope.row.status" active-color="#13ce66" inactive-color="#ff4949" active-value="运行" inactive-value="停止" @change="handleChangeStatus(scope.row)"></el-switch>
            </template>
          </el-table-column> -->
          <el-table-column prop="model_status" label="算法运行状态" width="120" align="center">
            <template slot-scope="scope">
              <!-- 此处也可自行配置字典使用 -->
              <span v-if="scope.row.status=='停止' && scope.row.model_status!='4'" style="color: #b26a00;cursor: pointer;" title="停止请求已提交，等待运行进程确认退出">停止中 <i class="el-icon-loading"></i></span>
              <span v-else-if="scope.row.model_status==1" title="画面帧、推理与分析输出均正常" style="cursor: pointer;">正常</span>
              <span v-else-if="scope.row.model_status=='2'" style="color: green;cursor: pointer;" title="算法配置参数修改">等待 <i class="el-icon-warning-outline"></i></span>
              <span v-else-if="scope.row.model_status=='3'" style="color:red;cursor: pointer;" title="算法运行异常或正在恢复，请检查画面、推理与分析输出">异常 <i class="el-icon-warning-outline"></i></span>
              <span v-else-if="scope.row.model_status=='4'" style="color:red;cursor: pointer;" title="算法停止运行">
                停止
                <i class="el-icon-warning-outline" ></i>
                <!-- <el-popover placement="top-start" trigger="hover" content="监控点掉线！" style="margin-left: -10px;">
                  <el-button slot="reference" icon="el-icon-warning" circle style="background-color: transparent;border: none;color: red;"></el-button>
                </el-popover> -->
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="update_time" label="更新时间" width="160"></el-table-column>
          <el-table-column prop="Algorithm_config_ps" label="备注">
            <template slot-scope="scope">
              {{ scope.row.Algorithm_config_ps || '暂无备注' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="320px" class-name="jia_btn_class" position="right">
            <template slot-scope="scope">
              {{ scope.row.status }}
              <el-switch v-model="scope.row.status" :disabled="batchStatusBusy || !!statusPending[scope.row.id]" active-color="#13ce66" inactive-color="#ff4949" active-value="运行" inactive-value="停止" @change="handleChangeStatus(scope.row)"></el-switch>
              <el-button type="text" icon="el-icon-edit" size="mini" @click="handlechanges(scope.row)">修改</el-button>
              <!-- <el-button type="text" icon="el-icon-tickets" size="mini" @click="handleOpenHistory(scope.row.id)">历史记录</el-button> -->
              <el-button type="text" icon="el-icon-warning-outline" size="mini" @click="handleToBjlb(scope.row)">报警列表</el-button>
              <!-- <el-button type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenSpfx(scope.row)">分析视频回放</el-button> -->
            </template>
          </el-table-column>
        </el-table>
        <!-- 如果没有数据，显示空状态 -->
        <el-empty v-if="tableData.length === 0" image="/static/img/home/placeholder_kong.png" :image-size="307" description="暂时没有数据~"></el-empty>
      </div>
      <div class="page">
        <el-pagination @current-change="handleCurrentChange" @size-change="handleSizeChange" :current-page.sync="currentPage" :page-size="pagesize" :page-sizes="pagesizes" background layout="total, prev, pager, next, jumper,sizes" :total="pagelength">
        </el-pagination>
      </div>
    </div>
    <el-dialog title="批量启停结果" :visible.sync="batchResultVisible" width="min(760px, 92vw)" :close-on-click-modal="false" append-to-body>
      <p>本次{{ batchRequestedStatus === '运行' ? '启动' : '停止' }} {{ batchSummary.total }} 项：已提交 {{ batchSummary.succeeded }} 项，失败 {{ batchSummary.failed }} 项<span v-if="batchSummary.unconfirmed">，未确认 {{ batchSummary.unconfirmed }} 项</span>。</p>
      <p style="color: #66758c; font-size: 12px; line-height: 1.6;">已提交表示服务端已接受请求，实际运行状态以列表为准；停止任务需等待运行进程确认退出。</p>
      <el-table :data="batchResults" max-height="360" style="width: 100%;">
        <el-table-column prop="id" label="任务 ID" width="85"></el-table-column>
        <el-table-column prop="name" label="任务名称" min-width="130" show-overflow-tooltip></el-table-column>
        <el-table-column label="结果" width="90">
          <template slot-scope="scope"><span :style="{ color: scope.row.success === true ? '#2c8a3e' : scope.row.success === false ? '#c45656' : '#b26a00' }">{{ scope.row.success === true ? '已提交' : scope.row.success === false ? '失败' : '未确认' }}</span></template>
        </el-table-column>
        <el-table-column prop="msg" label="说明" min-width="240"></el-table-column>
      </el-table>
      <span slot="footer"><el-button @click="batchResultVisible = false">关闭</el-button></span>
    </el-dialog>
    <el-dialog :title="title" :visible.sync="dialogVisible" width="900px" @close="handleClose" :close-on-click-modal="false" class="jia_algoBox" id="stepDialog">
      <el-steps :active="stepActive" finish-status="success" simple style="margin-top: 0px">
        <el-step title="步骤 1"></el-step>
        <el-step title="步骤 2"></el-step>
        <el-step title="步骤 3"></el-step>
      </el-steps>
      <el-form :model="ruleForm" :rules="rules" ref="ruleForms" class="sfgl_diaForm" label-position="top">
        <!-- 1 -->
        <el-form-item label="报警设备" :label-width="formLabelWidth" prop="equipment_name" v-show="stepActive == 0">
          <el-cascader style="width: 90%" v-model="ruleForm.equipment_name" :options="options2" :props="props" clearable filterable size="small" @change="
            handleChangeCanvas2();updateConfName();
            "></el-cascader>
        </el-form-item>
        <el-form-item label="解析类型" :label-width="formLabelWidth" prop="Algorithm_library_id" v-show="stepActive == 0">
          <el-select v-model="ruleForm.Algorithm_library_id" placeholder="请选择解析类型" size="small" clearable filterable style="width: 90%" @change="handleChangeSf(ruleForm.Algorithm_library_id);updateConfName()">
            <el-option v-for="item in options3" :key="item.id" :label="item.algorithm_name" :value="item.id"> </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="任务名称" :label-width="formLabelWidth" prop="conf_name" v-show="stepActive == 0">
          <el-input style="width: 90%" v-model="ruleForm.conf_name" placeholder="请输入任务名称" size="small" @input="checkShieldStatus();handlesearchModelName()"></el-input>
          <br>
          <div v-show="conf_name_type">例:{{conf_name_note}}</div>
          <span v-if="modelNameOpen" style="font-size: 12px;color: red;">{{ modelNamemsg }}</span>
        </el-form-item>
        <el-form-item label="报警等级" :label-width="formLabelWidth" prop="res_type" v-show="stepActive == 0">
          <el-select v-model="ruleForm.res_type" placeholder="请选择报警等级" size="small" clearable filterable style="width: 90%">
            <el-option v-for="item in alarmTypeDictOptions" :key="'报警等级'+item.value" :label="item.label" :value="item.value"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="场景类型" :label-width="formLabelWidth" prop="scene_typename" v-show="drawLineOpen && stepActive == 0">
          <el-select v-model="ruleForm.scene_typename" placeholder="请选择场景类型" size="small" clearable filterable style="width: 90%">
            <el-option v-for="item in areaOption" :key="item" :label="item" :value="item"> </el-option>
          </el-select>
        </el-form-item>
        <!-- <el-form-item label="单位名称" :label-width="formLabelWidth" prop="mine_name" v-show="stepActive == 0">
          <el-select v-model="ruleForm.mine_name" placeholder="请选择单位名称" size="small" clearable filterable style="width: 90%" @change="handleSelect(1)">
            <el-option v-for="item in options1" :key="item.id" :label="item.mine_name" :value="item.id"> </el-option>
          </el-select>
        </el-form-item> -->
        <!-- 2 -->
        <el-form-item label="模型类型选择" :label-width="formLabelWidth" prop="model_template_config_id" v-show="stepActive == 1" v-if="algorithmTemplateAdministrator">
          <el-cascader style="width: 90%" v-model="ruleForm.model_template_config_id" :options="modelOptions" :props="modelProps" clearable size="small" @expand-change="getModelSmallDict"></el-cascader>
        </el-form-item>
        <el-form-item label="模型小类" :label-width="formLabelWidth" prop="template_small_id" v-show="stepActive == 1"  v-if="algorithmTemplateAdministrator">
          <el-select v-model="ruleForm.template_small_id" placeholder="请选择模型小类" size="small" clearable filterable style="width: 90%" @change="handleChangeTemplateSmall()">
            <el-option v-for="item in modelSmallOption" :key="item.id" :label="item.template_small_name" :value="item.id"> </el-option>
          </el-select>
        </el-form-item>
        <div style="width: 100%;height: auto;" v-show="stepActive == 1 && ruleForm.template_data.length!=0">
          <div v-for="(item, index) in ruleForm.template_data" :key="index" class="form-group">
            <el-input v-model="item.key" placeholder="请输入键名" size="small" :disabled="!algorithmTemplateAdministrator" style="width: 150px;margin-right: 10px;margin-top: 10px;"></el-input>
            <el-input v-model="item.value" placeholder="请输入值" size="small" :disabled="!algorithmTemplateAdministrator" style="width: 230px;margin-right: 10px;margin-top: 10px;"></el-input>
            <el-button type="danger" icon="el-icon-delete" @click="removeItem(index)" size="small" style="margin-right: 10px;margin-top: 10px;"  v-if="algorithmTemplateAdministrator">删除</el-button>
            <el-button type="success" icon="el-icon-plus" @click="addItem(index)" size="small" style="margin-right: 10px;margin-top: 10px;" v-if="(index == ruleForm.template_data.length-1 ||ruleForm.template_data.length == 0) &&  algorithmTemplateAdministrator">新增</el-button>
          </div>
          <el-button type="success" icon="el-icon-plus" @click="addItem(index)" size="small" style="margin-right: 10px;margin-top: 10px;" v-if="ruleForm.template_data.length == 0 &&  algorithmTemplateAdministrator">新增</el-button>
        </div>
        <el-form-item label="检测类型" :label-width="formLabelWidth" prop="label_list" v-show="stepActive == 1 && model_template_config_id_num != 4">
          <!-- <el-select v-model="ruleForm.test_type_id" placeholder="请选择检测类型" size="small" clearable filterable style="width: 90%">
            <el-option v-for="item in options4" :key="item.id" :label="item.test_type_ename" :value="item.id"> </el-option>
          </el-select> -->
          <el-select v-model="ruleForm.label_list" placeholder="请选择检测类型" size="small" clearable filterable multiple style="width: 90%" @change="handleChangeLabelList">
            <el-option v-for="item in options4" :key="item.id" :label="item.test_type_cname" :value="item.test_type_ename"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item :label="'遮挡配置'" :label-width="formLabelWidth" prop="shield_status" v-show="showShieldConfig && stepActive == 0">
          <el-radio v-model="shield_status" :label="1" @input="handleChangeShield_status">遮挡</el-radio>
          <el-radio v-model="shield_status" :label="2">未遮挡</el-radio>
        </el-form-item>
        <el-form-item label="置信度" :label-width="formLabelWidth" prop="confidence" v-show="stepActive == 2 ">
          <el-input autocomplete="off" style="width: 90%" v-model="ruleForm.confidence" placeholder="请输入置信度" size="small"></el-input>
        </el-form-item>
        <!-- <el-form-item label="温度阈值" :label-width="formLabelWidth" prop="tem_frames" v-if="area2 && stepActive == 2 ">
          <el-input autocomplete="off" style="width: 90%" v-model="ruleForm.tem_frames" placeholder="请输入温度阈值" size="small"></el-input>
        </el-form-item> -->
        <!-- <el-form-item label="持续时间" :label-width="formLabelWidth" prop="duration_time" v-if="version=='极云'">
          <el-input autocomplete="off" style="width: 90%" v-model="ruleForm.duration_time" placeholder="请输入持续时间" size="small">
            <template slot="append">秒</template>
          </el-input>
        </el-form-item>
        <el-form-item label="报警间隔时间" :label-width="formLabelWidth" prop="interval_time" v-if="version=='极云'">
          <el-input autocomplete="off" style="width: 90%" v-model="ruleForm.interval_time" placeholder="请输入报警间隔时间" size="small">
            <template slot="append">秒</template>
          </el-input>
        </el-form-item> -->
        <el-form-item label="持续时长" :label-width="formLabelWidth" prop="duration_time" v-show="stepActive == 2 ">
          <el-input autocomplete="off" style="width: 90%" v-model="ruleForm.duration_time" placeholder="请输入持续时长" size="small">
            <template slot="append">秒</template>
          </el-input>
        </el-form-item>
        <el-form-item label="告警间隔" :label-width="formLabelWidth" prop="interval_time" v-show="stepActive == 2 ">
          <el-input autocomplete="off" style="width: 90%" v-model="ruleForm.interval_time" placeholder="请输入告警间隔" size="small">
            <template slot="append">秒</template>
          </el-input>
        </el-form-item>
        <el-form-item label="间隔帧" :label-width="formLabelWidth" prop="sensitivity" v-show="stepActive == 2 ">
          <el-input style="width: 90%" v-model.number="ruleForm.sensitivity" placeholder="请输入间隔帧" size="small"></el-input>
        </el-form-item>
        <el-form-item label="算力资源信息" :label-width="formLabelWidth" prop="resource_id" v-show="system == 'JY' && stepActive == 2 ">
          <el-cascader style="width: 90%" v-model="ruleForm.resource_id" :options="computeOptions" :props="computeProps" clearable size="small"></el-cascader>
        </el-form-item>
        <el-form-item label="报警图片目标框是否显示" :label-width="formLabelWidth" prop="image_draw_type" v-show="stepActive == 2 ">
          <!-- <el-radio v-model="image_draw_type" :label="1">绘制</el-radio>
          <el-radio v-model="image_draw_type" :label="2">不绘制</el-radio> -->
          <el-select v-model="image_draw_type" placeholder="请选择" size="small" clearable filterable style="width: 90%">
            <el-option label="是" :value="1"></el-option>
            <el-option label="否" :value="2"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="布防开始时间" :label-width="formLabelWidth" prop="defense_time_start" v-show="stepActive == 2 ">
          <!-- <el-date-picker popper-class="elDatePicker" v-model="ruleForm.defense_time_start" type="datetime" placeholder="选择开始时间" format='yyyy-MM-dd HH:mm:ss' value-format="yyyy-MM-dd HH:mm:ss">
          </el-date-picker> -->
          <el-time-picker v-model="ruleForm.defense_time_start" value-format="HH:MM:ss" :picker-options="{selectableRange: '00:00:00 - 23:59:59'}" placeholder="任意时间点" :default-value="new Date().setHours(0, 0, 0, 0)">
          </el-time-picker>
        </el-form-item>
        <el-form-item label="布防结束时间" :label-width="formLabelWidth" prop="defense_time_end" v-show="stepActive == 2 ">
          <!-- <el-date-picker popper-class="elDatePicker" v-model="ruleForm.defense_time_end" type="datetime" placeholder="选择结束时间" format='yyyy-MM-dd HH:mm:ss' value-format="yyyy-MM-dd HH:mm:ss">
          </el-date-picker> -->
          <el-time-picker v-model="ruleForm.defense_time_end" value-format="HH:MM:ss" :picker-options="{selectableRange: '00:00:00 - 23:59:59'}" placeholder="任意时间点" :default-value="new Date().setHours(0, 0, 0, 0)">
          </el-time-picker>
        </el-form-item>
        <el-form-item label="备注" :label-width="formLabelWidth" prop="Algorithm_config_ps" class="jia_formItm" v-show="stepActive == 2 ">
          <el-input autocomplete="off" v-model="ruleForm.Algorithm_config_ps" placeholder="请输入备注" type="textarea"></el-input>
        </el-form-item>
        <!-- <el-form-item label="图片数量" :label-width="formLabelWidth" prop="image_count" class="jia_formItm" v-show="stepActive == 2 ">
          <el-input style="width: 90%;" autocomplete="off" v-model="ruleForm.image_count" placeholder="请输入图片数量"></el-input>
        </el-form-item> -->

        <!-- <el-form-item label="" :label-width="formLabelWidth"> -->
        <!-- <el-radio-group v-model="ruleForm.type" @change="handleimg()">
            <el-radio :label=1>是</el-radio>
            <el-radio :label=0>否</el-radio>
          </el-radio-group> -->
        <!-- <el-button type="primary" @click="handleimg(1)">刷新</el-button>
        </el-form-item> -->
        <el-form-item label="绘制监测区域" :label-width="formLabelWidth" style="width: 100%" class="jia_formItem2" v-show="stepActive == 0">
          <div class="jia_btn">
            <!-- <el-button type="info" plain vautofocus="true" style="pointer-events: none">绘制监测区域</el-button> -->
            <!-- <div class="jia_btnTop">
              <span>画线开关&nbsp;&nbsp;</span>
              <el-switch v-model="drawLineOpen" @change="handleChangeDrawLine"></el-switch>
              &nbsp;&nbsp;&nbsp;&nbsp;
              <span>画区域开关&nbsp;&nbsp;</span>
              <el-switch v-model="drawAreaOpen" @change="handleChangeDrawArea"></el-switch>
              &nbsp;&nbsp;&nbsp;&nbsp; -->
              <!-- <el-form-item label="分辨率" :label-width="formLabelWidth" prop="resolution" style="float: right; margin-right: 10px;width: 250px;"> -->
              <!-- <span>分辨率&nbsp;&nbsp;</span>
              <el-select v-model="resolution" placeholder="分辨率" size="small" clearable filterable style="width: 120px" @change="handleTimesData(resolution)">
                <el-option v-for="item in resolutionOption" :key="item.name" :label="item.value" :value="item.value"> </el-option>
              </el-select> -->
              <!-- </el-form-item> -->
            <!-- </div> -->
            <!-- <div class="jia_color">
              <div class="color_box">
                <div class="color color1"></div>
                &nbsp;&nbsp;
                <div class="text">危险等级：1</div>
              </div>
              <div class="color_box">
                <div class="color color2"></div>
                &nbsp;&nbsp;
                <div class="text">危险等级：2</div>
              </div>
              <div class="color_box">
                <div class="color color3"></div>
                &nbsp;&nbsp;
                <div class="text">危险等级：3</div>
              </div>
              <div class="color_box">
                <div class="color color4"></div>
                &nbsp;&nbsp;
                <div class="text">消除</div>
              </div>
            </div> -->
          </div>
          <div class="Bcanvas" v-loading="loading">
            <div class="jia_div" v-if="!imgOpen">暂未选择监控点，无图片展示</div>
            <img :src="imgurl" alt="" style="width: 640px; height: 360px" v-if="imgOpen" @load="loading = false" />
            <canvas id="mycanvas" ref="mycanvas" tabindex="0"></canvas>
            <div class="jia_div" v-if="shield_status == 1||image_draw_type == 2"></div>
          </div>
          <div class="canvasBtn">
            <el-button type="text" @click="handleimg(1)" icon="el-icon-refresh">刷新</el-button>
            <el-button type="text" @click="handleDrewAgain" icon="el-icon-edit">重新绘制</el-button>
            <el-button type="text" @click="resole" icon="el-icon-refresh-left">撤销</el-button>
          </div>
        </el-form-item>
        <!-- <el-form-item label="模板配置区域" :label-width="formLabelWidth" style="width: 100%" class="jia_formItem3" v-show="stepActive == 1 && ruleForm.model_template_config_id != 1">
          <div class="jia_btn">
            <div class="jia_color3">
              <div class="color_box">
                <div class="color color1"></div>
                &nbsp;&nbsp;
                <div class="text">类型一</div>
              </div>
              <div class="color_box">
                <div class="color color2"></div>
                &nbsp;&nbsp;
                <div class="text">类型二</div>
              </div>
              <div class="color_box">
                <div class="color color3"></div>
                &nbsp;&nbsp;
                <div class="text">类型三</div>
              </div>
            </div>
          </div>
          <div class="Bcanvas" v-loading="loading">
            <div class="jia_div" v-if="!imgOpen">暂未选择监控点，无图片展示</div>
            <img :src="imgurl" alt="" style="width: 640px; height: 360px" v-if="imgOpen" @load="loading = false" />
            <canvas id="mycanvas_model" ref="mycanvas_model" tabindex="0"></canvas>
          </div>
          <div class="canvasBtn">
            <el-button type="text" @click="handleimg(1)" icon="el-icon-refresh">刷新</el-button>
            <el-button type="text" @click="handleDrewAgain_model" icon="el-icon-edit">重新绘制</el-button>
            <el-button type="text" @click="resole_model" icon="el-icon-refresh-left">撤销</el-button>
          </div>
        </el-form-item> -->
        <!-- <el-form-item label="热成像检测消除区域" :label-width="formLabelWidth" style="width: 100%" v-if="area2">
          <div class="jia_btn">
            <el-button type="info" plain vautofocus="true" style="pointer-events: none">绘制热成像检测消除区域</el-button>
            <div>
              <el-button type="primary" size="mini" @click="handleimg(1)" style="float: right; margin-right: 10px">刷新</el-button>
              <el-button type="primary" size="mini" @click="handleDrewAgain2" style="float: right; margin-right: 10px">重新绘制</el-button>
              <el-button type="primary" size="mini" @click="resole2" style="float: right; margin-right: 10px">撤销</el-button>
            </div>
          </div>
          <div class="Bcanvas" v-loading="loading">
            <div class="jia_div" v-if="!imgOpen">暂未选择监控点，无图片展示</div>
            <img :src="imgurl" alt="" style="width: 640px; height: 360px" v-if="imgOpen" @load="loading2 = false" />
            <canvas id="mycanvas2" ref="mycanvas2" tabindex="0"></canvas>
          </div>
        </el-form-item> -->
      </el-form>

      <span slot="footer" class="dialog-footer">
        <el-button @click="stepUp">上一步</el-button>
        <el-button @click="stepNext">下一步</el-button>
        <el-button @click="handleCloseDialog()">取 消</el-button>
        <el-button v-if="stepActive == 3" type="primary" @click="handleSure()">确 定</el-button>
      </span>
    </el-dialog>
    <!-- 类型 -->
    <el-dialog :title="title2_model" :visible.sync="dialogVisible2_model" width="500px" @close="handleClose2_model">
      <el-radio-group v-model="selectedOption_model">
        <el-radio :label="'类型一'">类型一</el-radio>
        <!-- <el-radio :label="'类型二'">类型二</el-radio>
        <el-radio :label="'类型三'">类型三</el-radio> -->
      </el-radio-group>
      <span slot="footer" class="dialog-footer">
        <el-button @click="dialogVisible2_model = false;handleDeleteList_model()">取 消</el-button>
        <el-button type="primary" @click="handleUpdateList_model()">确 定</el-button>
      </span>
    </el-dialog>
    <!-- 区域 -->
    <el-dialog :title="title2" id="alarmTypeBox" :visible.sync="dialogVisible2" width="500px" @close="handleClose2" :close-on-click-modal="false">
      <!-- <el-radio-group v-model="selectedOption">
        <el-radio :label="'告警区域'">告警区域</el-radio>
        <el-radio :label="'类型一'">类型一</el-radio>
        <el-radio :label="'类型二'">类型二</el-radio>
        <el-radio :label="'类型三'">类型三</el-radio>
      </el-radio-group> -->
      <div class="radio-group-title">告警区域</div>
      <br>
      <el-radio-group v-model="selectedOption" class="radio-grid">
        <el-radio :label="'告警区域'" class="grid-item">告警区域</el-radio>
      </el-radio-group>
      <br>
      <br>
      <div class="radio-group-title">后处理区域</div>
      <br>
      <el-radio-group v-model="selectedOption" class="radio-grid">
        <el-radio :label="'类型一'" class="grid-item">类型一</el-radio>
        <!-- <el-radio :label="'类型二'" class="grid-item">类型二</el-radio>
        <el-radio :label="'类型三'" class="grid-item">类型三</el-radio> -->
      </el-radio-group>
      <span slot="footer" class="dialog-footer">
        <el-button @click="dialogVisible2 = false;handleDeleteList()">取 消</el-button>
        <el-button type="primary" @click="handleUpdateList()">确 定</el-button>
      </span>
    </el-dialog>
    <el-dialog :title="title3" :visible.sync="dialogVisible3" width="80%" @close="handleClose3">
      <History :key="historyKey" ref="historyTable"></History>
    </el-dialog>
    <el-dialog title="视频分析" :visible.sync="dialogVisible4" width="80%" @close="handleClose4">
      <video ref="videoPlayer" width="100%" height="100%" controls></video>
    </el-dialog>
    <el-dialog title="分析区域" :visible.sync="dialogVisible5" width="850px" @close="handleClose5">
      <div style="width: 800px; height: 400px; position: relative">
        <img v-roi-image.eager="{ path: dialogVisible5 ? analysisSrc : '', epoch: roiThumbnailEpoch }" style="width: 800px; height: 400px; position: absolute; top: 0; left: 0; z-index: 9" />
        <canvas :id="'tableCanvas_' + 'tableMax'" :ref="'tableCanvas_' + 'tableMax'" tabindex="0" style="position: absolute; top: 0; left: 0; z-index: 10; cursor: none"></canvas>
      </div>
      <div class="btn_group" style="margin-top: 10px;width: 100%;height: 50px;display: flex;justify-content: center;">
        <el-button-group>
          <el-button type="primary" icon="el-icon-arrow-left" @click="handleUpImg">上一条</el-button>
          <el-button type="primary" @click="handleNextImg">下一条<i class="el-icon-arrow-right el-icon--right"></i></el-button>
        </el-button-group>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { compute, findModelName } from "../api/sfgl";
import { draw_test } from "../relevantjs/draw_shape";
import { draw_test2 } from "../relevantjs/draw_shape2";
import { draw_test3 } from "../relevantjs/draw_shape3";
import { draw_test4 } from "../relevantjs/draw_shape4";//用于标线

import store from "../store";

import History from './sfgl_history.vue';

import flvjs from 'flv.js';
import { spfxApi } from '@/api/spfx';
import { modelApi } from '@/api/model/index';
import { roiThumbnailMixin, roiImageDirective } from './roiThumbnailImages';
import { algorithmListReturnStateMixin } from './algorithmListReturnState';
import algorithmRuntimeHealthMixin from './algorithmRuntimeHealth';

export default {
  mixins: [window.PlatformAlgorithmTemplateAdministrator, roiThumbnailMixin, algorithmListReturnStateMixin, algorithmRuntimeHealthMixin],
  directives: { roiImage: roiImageDirective },
  components: {
    History,
  },
  name: "sfgl",
  data() {
    return {
      mkname: "",
      system: window.wgParameter.system,
      version: store.state.version,
      url_5000: this.$url.url_5000,
      StartTime: "",
      EndTime: "",
      startTimePickerOptions: {
        disabledDate: (time) => {

          return time.getTime() > Date.now(); // 禁止选择今天之后的日期
        }
      },
      endTimePickerOptions: {
        disabledDate: (time) => {
          if (this.StartTime) {
            const startTime = new Date(this.StartTime);
            startTime.setHours(0, 0, 0, 0);
            return time.getTime() > Date.now() || time.getTime() < startTime.getTime();
          } else {
            return time.getTime() > Date.now();
          }
        }
      },
      conf_name: "",//任务名称
      algorithm_name: "",//算法
      algorithm_library_id: '',
      tableData: [],
      listRequestSequence: 0,
      statusPending: {},
      statusRefreshTimer: null,
      batchStatusBusy: false,
      batchRequestedStatus: '',
      batchResultVisible: false,
      batchResults: [],
      batchSummary: { total: 0, succeeded: 0, failed: 0, unconfirmed: 0 },
      currentPage: 1, //默认开始页面 this.$store.state.pages  $store.state.loginuser
      pagenumber: 1, //第几页
      pagesize: 15, //每页的数据条数
      pagelength: 0, //默认数据总数
      pagesizes: [15, 35, 50, 100, 150, 200, 300],
      multipleSelection: [],
      dialogVisible: false,
      dialogVisible2: false,
      dialogVisible3: false,
      dialogVisible4: false,
      dialogVisible5: false,
      historyKey: 0, // 初始化 key，用于触发 History 组件的重新渲染
      formLabelWidth: "140px",
      conf_name_note:'',
      conf_name_type:false,
      resolution: '',
      resolutionOption: [
        { value: '1920x1080', name: '普通' },
        { value: '2688x1520', name: '热成像' },
        { value: '2560x1440', name: '热成像' },
        { value: '1280x720', name: '热成像' },
        { value: '720x576', name: '热成像2' }
      ],
      areaOption: [
        '掘进机',
        '转载点-运输皮带仓内',
        '转载点-运输皮带仓外'
      ],
      alarmTypeDictOptions: [
        {
          label: 'I级报警',
          value: '1',
        },
        {
          label: 'II级报警',
          value: '2',
        },
        {
          label: 'III级报警',
          value: '3',
        }
      ],
      timesX: 3,
      timesY: 3,
      options1: [],
      options2: [],
      options3: [],
      options4: [],
      // 该表单参数，想要默认值去函数中添加初始值
      ruleForm: {
        mine_name: "",
        algorithm_name: "",
        equipment_name: "",
        Algorithm_library_id: "",
        type: 0,
        confidence: "80",
        tem_frames: "[27,37]",
        duration_time: 10,
        interval_time: 300,
        image_draw_type: 1,
        Algorithm_config_ps: '',
        scene_typename: '',
        sensitivity: 25,
        resource_id: "",
        resource_id_old: "",
        defense_time_start: "",
        defense_time_end: "",
        image_count: 5,
        template_small_id: '',
        res_type: '',
        template_data: [],
        test_type_id: "",
        label_list: [],
      },
      rules: {
        sensitivity: [
          {
            type: 'number',
            min: 1,
            // max: 100,
            message: '间隔帧必须是正整数',
            trigger: 'blur'
          },
          {
            validator: this.validateInteger,
            trigger: ['blur', 'change']
          }
        ],
        confidence: [
          // { required: true, message: '请输入置信度', trigger: 'blur' },
          {
            validator: this.validateConfidence,
            trigger: ['blur', 'change']
          }
        ],
        duration_time: [
          // { required: true, message: '请输入持续时间', trigger: 'blur' },
          {
            validator: this.validateDurationTime,
            trigger: ['blur', 'change']
          }
        ],
        interval_time: [
          // { required: true, message: '请输入报警间隔时间', trigger: 'blur' },
          { validator: this.validateDurationTime, trigger: ['blur', 'change'] }
        ],
        // sensitivity: [
        //   // { required: false, message: '请输入灵敏度', trigger: 'blur' },
        //   { validator: this.validateNumber, trigger: 'blur' }
        // ],
        image_count: [
          // { required: true, message: '请输入图片数量', trigger: 'blur' },
          { pattern: /^[1-9]\d*$/, message: '图片数量必须为正整数', trigger: ['blur', 'change'] }
        ]
      },
      props: {
        checkStrictly: false,
        emitPath: false,
        value: "id",
        label: "equipment_name",
      },
      modelProps: {
        checkStrictly: false,
        emitPath: false,
        value: 'model_id', // 动态选择值字段
        label: 'model_type_name', // 动态选择标签字段
        // children: "children" // 如果子级还有下一级，确保正确指向子选项数组
      },
      imgurl: "",
      // 图形绘制相关参数（开始）
      isdraw: false, //是否在画图形
      coordinates: [], //一个多边形的坐标信息
      cor_index: 0, //当前多边形的索引
      endtip: false, //是否结束一个多边形的绘制
      //    mark_list: [], //所有多边形的信息
      mark_list: [
        // [
        //   {
        //     x: 135,
        //     y: 49,
        //   },
        //   {
        //     x: 509,
        //     y: 50,
        //   },
        //   {
        //     x: 230,
        //     y: 198,
        //   },
        // ],
      ], //所有多边形的信息
      mark_lists: [], //多边形的信息,最终提交的数据
      PointInArea: false,
      index: null,
      loading: false,
      // 图形绘制相关参数（结束）
      // 图形绘制相关参数（开始）特殊热成像区域
      area2: false,
      isdraw2: false, //是否在画图形
      coordinates2: [], //一个多边形的坐标信息
      cor_index2: 0, //当前多边形的索引
      endtip2: false, //是否结束一个多边形的绘制
      //    mark_list: [], //所有多边形的信息
      mark_list2: [
        // [
        //   {
        //     x: 135,
        //     y: 49,
        //   },
        //   {
        //     x: 509,
        //     y: 50,
        //   },
        //   {
        //     x: 230,
        //     y: 198,
        //   },
        // ],
      ], //所有多边形的信息
      mark_lists2: [], //多边形的信息,最终提交的数据
      PointInArea2: false,
      index2: null,
      loading2: false,
      // 图形绘制相关参数（结束）

      // 图形绘制相关参数（开始）划线相关参数
      area3: false,
      isdraw3: false, //是否在画图形
      coordinates3: [], //一个多边形的坐标信息
      cor_index3: 0, //当前多边形的索引
      endtip3: false, //是否结束一个多边形的绘制
      //    mark_list: [], //所有多边形的信息
      mark_list3: [
        // [
        //   {
        //     x: 135,
        //     y: 49,
        //   },
        //   {
        //     x: 509,
        //     y: 50,
        //   },
        //   {
        //     x: 230,
        //     y: 198,
        //   },
        // ],
      ], //所有多边形的信息
      mark_lists3: [], //多边形的信息,最终提交的数据
      PointInArea3: false,
      index3: null,
      loading3: false,
      // 图形绘制相关参数（结束）

      imgOpen: false, //控制图片的开关
      title: "",
      title2: "",
      title3: "",
      shield_status: 2,
      image_draw_type: 1,
      // 画线相关操作
      drawLineOpen: false,
      selectedOption: '报警',
      pickerOptions: {
        disabledDate(time) {
          // 获取当前日期的零时零分零秒
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          // 禁用今天之后的所有日期和时间
          return time.getTime() > today.getTime();
        },
      },
      coordinates: [],
      coordinates2: [],
      coordinates3: [],
      computeOptions: [],//算力资源信息字典
      computeProps: {
        checkStrictly: false,
        emitPath: false,
        value: "id",
        label: "label",
      },
      checkStatusTime: null,
      flvPlayer: null,
      coordinates_model: [],//类型
      mark_list_model: [],
      mark_lists_model: [],
      selectedOption_model: '类型一',
      title2_model: '',
      dialogVisible2_model: false,
      modelOptions: [],//类型字典
      modelTypeOptions: [],//模板大类
      template_type_id: '',
      stepActive: 0,//步骤条初始为0
      modelSmallOption: [],//小类字典
      modelNameOpen: false,
      modelNamemsg: '',
      // template_data: [],//小类详情信息
      model_template_config_id_num: 1,
      analysisSrc: '',
      // analysisCanvas: '',
      analysisId: '',
    };
  },
  computed: {
    showShieldConfig() {
      // 检查输入或选择的值是否包含“遮挡”两个字，处理可能的空值情况
      const confName = this.ruleForm.conf_name || '';
      const selectedOption = this.options3.find(option => option.id === this.ruleForm.Algorithm_library_id);
      const algorithmName = selectedOption ? selectedOption.algorithm_name : '';

      const confNameContainsShield = confName.includes('遮挡');
      const selectedOptionContainsShield = algorithmName.includes('遮挡');

      return confNameContainsShield || selectedOptionContainsShield;
    },
    drawAreaOpen: {
      get() {
        return !this.drawLineOpen;
      },
      set(newValue) {
        this.drawLineOpen = !newValue;
      }
    }
  },
  created() {
    this.getCompute();//获取苏哪里资源信息
    // 大类
    this.$http.get(modelApi.getModelType, {
      params: {
        page: 1,
        per_page: 999
      }
    }).then(response => {
      this.modelTypeOptions = response.data.data.data
    }).catch(rek => {
      console.log(rek)
    })
  },
  methods: {
    getModelSmallDict(value) {
      let id = this.extractNumberFromF(value[0])
      this.model_template_config_id_num = id
      this.$http.get(modelApi.getModelSmallList, {
        params: {
          page: 1,
          per_page: 15,
          model_template_type_id: id,
        }
      }).then(response => {
        this.modelSmallOption = response.data.data.data;
      }).catch(rek => {
        console.log(rek)
      })
    },
    getModelSmallDict2(id) {
      this.model_template_config_id_num = id
      this.$http.get(modelApi.getModelSmallList, {
        params: {
          page: 1,
          per_page: 15,
          model_template_type_id: id,
        }
      }).then(response => {
        this.modelSmallOption = response.data.data.data;
        // console.log("===================",this.modelSmallOption)
      }).catch(rek => {
        console.log(rek)
      })
    },
    extractNumberFromF(str) {
      const match = str.match(/^F(\d+)$/);
      return match ? parseInt(match[1], 10) : NaN;
    },
    handleToBjlb(data) {
      if(data.algorithm_name == '人数统计' || data.algorithm_name == '车辆统计'){
        this.$router.push({
          path: '/bjlb',
          query: {
            Algorithm_config_id: data.id,
            type:'tj',
          }
        })
      }else{
        this.$router.push({
          path: '/bjlb',
          query: {
            Algorithm_config_id: data.id
          }
        })
      }
    },
    // 获取算力资源信息
    getCompute() {
      this.$http.get(compute)
        .then(response => {
          this.computeOptions = this.transformData(response.data.data)
          console.log("算力资源信息", this.computeOptions);
        })
        .catch(rek => {
          console.log(rek)
        })
    },
    transformData(rawData) {
      let res = []
      rawData.forEach(item => {
        let res2 = item.grouped_resources
        let tableData = Object.entries(res2).flatMap(([key, devices]) => {
          let adc = {
            id: this.generateRandomId(),
            label: `${key}`,
          }
          let arr3 = devices.map(device => {
            return {
              id: device.id,
              label: `TPU${device.dev_id}`
            }
          })
          return {
            ...adc,
            children: arr3
          }
        });
        let msg = {
          id: '设备' + item.computing_id,
          deviceId: item.computing_id,
          computing_ip: item.computing_ip,
          label: item.computing_name,
          children: tableData
        }
        res.push(msg)
      })
      return res
    },
    generateRandomId() {
      return Math.random().toString(36).substr(2, 9); // 生成随机 ID
    },
    validateInteger(rule, value, callback) {
      if (value === '' || Number.isInteger(Number(value))) {
        callback();
      } else {
        callback(new Error('请输入一个整数'));
      }
    },
    validateConfidence(rule, value, callback) {
      // 定义正则表达式，确保值是大于0且小于等于100的整数
      const pattern = /^(?:[1-9][0-9]?|100)$/;

      if (!pattern.test(value)) {
        callback(new Error('置信度必须为大于0且小于等于100的整数'));
      } else {
        callback(); // 验证成功
      }
    },
    validateNumber(rule, value, callback) {
      const numValue = parseFloat(value);
      if (value === '') {
        callback(new Error('请输入数字'));
      } else if (isNaN(numValue)) {
        callback(new Error('必须是数字'));
      } else {
        callback(); // 验证成功
      }
    },
    // 定义验证器方法
    validateDurationTime(rule, value, callback) {
      if (!/^\d+$/.test(value)) {
        callback(new Error('时间必须是正整数'));
      } else {
        callback();
      }
    },
    checkShieldStatus() {
      // 用于触发计算属性更新
      this.$forceUpdate();
    },
    // 撤销
    resole() {
      if (!this.drawLineOpen) {
        // console.log("当前标注区域", this.coordinates);
        this.coordinates.pop()
      } else {
        this.coordinates3.pop()
      }
    },
    resole_model() {
      this.coordinates_model.pop()
    },
    resole2() {
      this.coordinates2.pop()
    },
    getRowKey(row) {
      return row.id;
    },
    handleRow(val) {
      // console.log(val)
      if (!this.batchStatusBusy) this.multipleSelection = val;
    },
    handleRows(val) {
      // console.log(val)
      if (!this.batchStatusBusy) this.multipleSelection = val;
    },
    canSelectBatchRow(row) {
      return !this.batchStatusBusy && !this.statusPending[row.id];
    },
    clearBatchSelection() {
      this.multipleSelection = [];
      const table = this.$refs.singleTable;
      if (table && table.clearSelection) table.clearSelection();
    },
    restoreBatchSelection() {
      const ids = new Set(this.multipleSelection.map(row => String(row.id)));
      this.multipleSelection = this.tableData.filter(row => ids.has(String(row.id)));
      this.$nextTick(() => {
        if (this._isDestroyed || this._isBeingDestroyed) return;
        const table = this.$refs.singleTable;
        if (!table || !table.clearSelection || !table.toggleRowSelection) return;
        table.clearSelection();
        this.multipleSelection.forEach(row => table.toggleRowSelection(row, true));
      });
    },
    batchStatusUnavailable() {
      return this.batchStatusBusy || !this.multipleSelection.length || this.multipleSelection.length > 100 || Object.keys(this.statusPending).length > 0;
    },
    showBatchResults(body, selected) {
      const payload = body && body.data && typeof body.data === 'object' ? body.data : {};
      const results = Array.isArray(payload.results) ? payload.results : [];
      this.batchResults = selected.map(row => {
        const result = results.find(item => item && Number(item.id) === row.id);
        const rejected = !result && body && Number(body.code) === 400;
        const success = result && typeof result.success === 'boolean' ? result.success : rejected ? false : null;
        const fallback = success === true ? '请求已提交' : success === false ? body.msg || '操作失败' : '未收到该任务的明确回执，请刷新列表确认';
        return { id: row.id, name: row.name, success,
          code: result ? result.code : body && body.code,
          msg: String(result && result.msg || fallback) };
      });
      this.batchSummary = { total: this.batchResults.length,
        succeeded: this.batchResults.filter(item => item.success === true).length,
        failed: this.batchResults.filter(item => item.success === false).length,
        unconfirmed: this.batchResults.filter(item => item.success === null).length };
      this.batchResultVisible = true;
    },
    handleBatchStatus(status) {
      if (this.batchStatusUnavailable() || (status !== '运行' && status !== '停止')) return;
      const selected = [];
      for (const row of this.multipleSelection) {
        const validSource = typeof row.id === 'number' || (typeof row.id === 'string' && /^\d+$/.test(row.id));
        const id = Number(row.id);
        if (!validSource || !Number.isSafeInteger(id) || id <= 0) {
          this.$message({ type: 'warning', message: '所选任务 ID 无效，请刷新后重新选择' });
          return;
        }
        if (!selected.some(item => item.id === id)) selected.push({ id, name: String(row.conf_name || '任务 ' + id) });
      }
      this.batchStatusBusy = true;
      this.batchRequestedStatus = status;
      selected.forEach(row => this.$set(this.statusPending, row.id, true));
      ++this.listRequestSequence;
      clearTimeout(this.statusRefreshTimer);
      this.statusRefreshTimer = null;
      const release = () => {
        selected.forEach(row => this.$delete(this.statusPending, row.id));
        this.batchStatusBusy = false;
      };
      return this.$http.post(this.$url.url_5000 + '/model_view/algorithm_conf_batch_update',
        { ids: selected.map(row => row.id), status }, { headers: { 'Content-Type': 'application/json' } })
        .then(response => {
          this.showBatchResults(response.data, selected);
          return this.axioss();
        })
        .catch(error => {
          const body = error.response && error.response.data;
          if (body && (Number(body.code) === 400 || body.data && Array.isArray(body.data.results))) {
            this.showBatchResults(body, selected);
          } else {
            this.showBatchResults(null, selected);
          }
          return this.axioss();
        })
        .then(release, release);
    },
    handleCurrentChange(val) {
      this.clearBatchSelection();
      this.currentPage = val;
      this.pagenumber = val;
      return this.axioss();
    },
    handleSizeChange(val) {
      this.pagesize = val;
      return this.queryAlgorithms();
    },
    queryAlgorithms() {
      this.clearBatchSelection();
      this.currentPage = 1;
      this.pagenumber = 1;
      return this.axioss();
    },
    scheduleStatusRefresh() {
      return this.scheduleAlgorithmRuntimeRefresh();
    },
    axioss() {
      const requestSequence = ++this.listRequestSequence;
      this.captureAlgorithmRuntimeQuery();
      clearTimeout(this.statusRefreshTimer);
      this.statusRefreshTimer = null;
      return this.$http
        .get(this.$url.url_5000 + "/model_view/algorithm_data_show", {
          params: {
            conf_name: this.conf_name,
            // algorithm_name: this.algorithm_name,
            Mine_id: this.mkname,
            algorithm_library_id: this.algorithm_library_id,
            start_time: this.StartTime,
            end_time: this.EndTime,
            page: this.pagenumber,
            per_page: this.pagesize,
            // template_type_id:this.template_type_id,
          },
        })
        .then((response) => {
          if (requestSequence !== this.listRequestSequence || this._isDestroyed || this._isBeingDestroyed) return;
          if ([401, 403].includes(Number(response.data.code))) this.pauseAlgorithmRuntimeRefresh(response.data.code);
          if (response.data.code === 200) {
            this.algorithmRuntimeHealthUpdatedAt = new Date().toLocaleTimeString('zh-CN', { hour12: false });
            this.algorithmRuntimeHealthError = '';
            this.tableData = response.data.data_list.data;
            this.pagelength = response.data.data_list.total_items;
            this.restoreBatchSelection();
            // 对获取的图片进行处理，得到绘制过后的图片
            this.tableData.forEach((v) => {
              let confArea = []
              if (v.conf_area && v.conf_area != '[]') {
                confArea = JSON.parse(v.conf_area.replace(/'/g, '"'))
              }
              
              // 解析线数据
              let crossLineData = null
              if (v.cross_line_area && v.cross_line_area !== '' && v.cross_line_area !== '{}') {
                try {
                  crossLineData = typeof v.cross_line_area === 'string' 
                    ? JSON.parse(v.cross_line_area.replace(/'/g, '"')) 
                    : v.cross_line_area
                } catch(e) {
                  console.error('解析线数据失败:', e)
                }
              }
              
              // 使用表格专用方法
              this.tableCanvasForTable(v.id, confArea, crossLineData, v.draw_type, v.img_resolution)
            });
          } else {
            this.$message({ type: 'warning', message: response.data.msg || '查询算法配置失败' });
          }
          this.scheduleStatusRefresh();
        })
        .catch((error) => {
          if (requestSequence !== this.listRequestSequence || this._isDestroyed || this._isBeingDestroyed) return;
          if ([401, 403].includes(Number(error.response && error.response.status))) this.pauseAlgorithmRuntimeRefresh(error.response.status);
          this.$message({ type: 'error', message: error.response && error.response.data && error.response.data.msg || '查询算法配置失败，请重试' });
          this.scheduleStatusRefresh();
        });
    },
    tableCanvasForTable(id, list, crossLineData, type, resolution) {
  var parts = resolution.split('x');
  var WW = parseInt(parts[0], 10);
  var HH = parseInt(parts[1], 10);
  
  this.$nextTick(() => {
    let cav = this.$refs[`tableCanvas_${id}`];
    if (!cav) return;
    
    cav.width = "96";
    cav.height = "54";
    let ctx = cav.getContext("2d");
    
    let XX = WW / 96;
    let YY = HH / 54;
    
    ctx.clearRect(0, 0, 96, 54);
    
    // 绘制框
    if (list && list.length > 0) {
      for (let w = 0; w < list.length; w++) {
        if (list[w].length < 3) continue;
        ctx.beginPath();
        ctx.strokeStyle = list[w][0].color || '#f00';
        ctx.lineWidth = 1;
        ctx.moveTo(list[w][0].x / XX, list[w][0].y / YY);
        for (let i = 1; i < list[w].length; i++) {
          ctx.lineTo(list[w][i].x / XX, list[w][i].y / YY);
        }
        ctx.closePath();
        ctx.stroke();
      }
    }
    
    // 绘制线
    if (crossLineData && crossLineData.p1 && crossLineData.p2) {
      try {
        // 转换线端点坐标到缩略图
        const p1 = {
          x: Number(crossLineData.p1.x) / XX,
          y: Number(crossLineData.p1.y) / YY
        };
        const p2 = {
          x: Number(crossLineData.p2.x) / XX,
          y: Number(crossLineData.p2.y) / YY
        };
        
        p1.x = Math.min(96, Math.max(0, p1.x));
        p1.y = Math.min(54, Math.max(0, p1.y));
        p2.x = Math.min(96, Math.max(0, p2.x));
        p2.y = Math.min(54, Math.max(0, p2.y));
        
        // 绘制线
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = "#ffd700";
        ctx.lineWidth = 1.5;
        ctx.stroke();
        
        // 计算箭头位置
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        
        if (len > 0) {
          const ux = dx / len;
          const uy = dy / len;
          const perpLen = 15;
          const mx = (p1.x + p2.x) / 2;
          const my = (p1.y + p2.y) / 2;
          
          let leftX = mx - uy * perpLen;
          let leftY = my + ux * perpLen;
          let rightX = mx + uy * perpLen;
          let rightY = my - ux * perpLen;
          
          leftX = Math.min(94, Math.max(2, leftX));
          leftY = Math.min(52, Math.max(2, leftY));
          rightX = Math.min(94, Math.max(2, rightX));
          rightY = Math.min(52, Math.max(2, rightY));
          
          // 【关键】根据 direction 字段决定绿点（IN）的位置
          if (crossLineData.direction === 'left') {
            // direction: 'left' 表示 IN 在左边 - 左边绿点，右边红点
            ctx.beginPath();
            ctx.fillStyle = '#44ff44';  // 绿色 = IN
            ctx.arc(leftX, leftY, 3, 0, 2 * Math.PI);
            ctx.fill();
            ctx.beginPath();
            ctx.fillStyle = '#ff4444';  // 红色 = OUT
            ctx.arc(rightX, rightY, 3, 0, 2 * Math.PI);
            ctx.fill();
          } else if (crossLineData.direction === 'right') {
            // direction: 'right' 表示 IN 在右边 - 左边红点，右边绿点
            ctx.beginPath();
            ctx.fillStyle = '#ff4444';  // 红色 = OUT
            ctx.arc(leftX, leftY, 3, 0, 2 * Math.PI);
            ctx.fill();
            ctx.beginPath();
            ctx.fillStyle = '#44ff44';  // 绿色 = IN
            ctx.arc(rightX, rightY, 3, 0, 2 * Math.PI);
            ctx.fill();
          } else {
            // 默认：右边绿点（IN），左边红点（OUT）
            ctx.beginPath();
            ctx.fillStyle = '#ff4444';
            ctx.arc(leftX, leftY, 3, 0, 2 * Math.PI);
            ctx.fill();
            ctx.beginPath();
            ctx.fillStyle = '#44ff44';
            ctx.arc(rightX, rightY, 3, 0, 2 * Math.PI);
            ctx.fill();
          }
        }
      } catch(e) {
        console.error('绘制线失败:', e);
      }
    }
  });
},
    getDefaultEndTime() {
      const today = new Date();
      return new Date(today.setHours(23, 59, 59, 999));
    },
    handleadds(){
      this.$router.push("/sfgl_child");
    },
    handleaddss(){
      this.$router.push("/sfgl_childs");
    },
    handleadd() {
      this.resolution = '';
      this.modelNameOpen = false
      this.stepActive = 0
      this.area2 = false;
      this.title = "算法配置";
      this.ruleForm = {
        mine_name: "",
        algorithm_name: "",
        equipment_name: "",
        Algorithm_library_id: "",
        type: 0,
        confidence: "80",
        tem_frames: "[27,37]",
        duration_time: 10,
        interval_time: 300,
        sensitivity: 25,
        defense_time_start: '00:00:00',
        defense_time_end: '23:59:59',
        image_count: 5,
        template_data: [],
        test_type_id: "",
        label_list: [],
      };
      this.shield_status = 2;
      this.dialogVisible = true;
      this.mark_list = []; //对canvas标点用到的数组进行重新赋值
      this.mark_list_model = []; //对canvas标点用到的数组进行重新赋值
      this.mark_list2 = []; //对canvas标点用到的数组进行重新赋值
      this.mark_list3 = []; //对canvas标点用到的数组进行重新赋值
      this.coordinates = [];
      this.coordinates_model = [];
      this.coordinates2 = [];
      this.coordinates3 = [];
      this.initCanvas();
      this.initCanvas_model();
      // this.initCanvas2();
      this.handleSelect();
    },
    findDeviceIdById(options, targetId) {
      for (const option of options) {
        console.log("current option", option);
        if (option.children) {
          const result = option.children.find(child => child.id === targetId);
          if (result) {
            return option.deviceId;
          }

          // 如果children还有子级children，递归查找
          const recursiveResult = this.findDeviceIdById(option.children, targetId);
          if (recursiveResult !== undefined) {
            return recursiveResult;
          }
        }
      }
      return undefined;
    },
    handleSure() {
      if (this.modelNameOpen == true) {
        this.$message({
          type: 'warning',
          message: '任务名称名字重复，请检查数据后重新提交'
        })
        return
      }
      // 1、无需绘制点，2、正常操作
      if (this.shield_status == "1") {
        //拿到分辨率，并赋值
        // 使用 split() 方法将字符串分割成数组
        let parts = this.resolution.split("x");

        // 获取 x 前后的两个数字
        let beforeX = parseInt(parts[0]);
        let afterX = parseInt(parts[1]);
        this.mark_lists = [
          [
            {
              x: 0,
              y: 0,
              type: 'I级报警',
              color: '#FF0000',
            },
            {
              x: beforeX,
              y: 0,
              type: 'I级报警',
              color: '#FF0000',
            },
            {
              x: beforeX,
              y: afterX,
              type: 'I级报警',
              color: '#FF0000',
            },
            {
              x: 0,
              y: afterX,
              type: 'I级报警',
              color: '#FF0000',
            },
          ],
        ];
        this.mark_lists2 = [
          [
            {
              x: 0,
              y: 0,
            },
            {
              x: beforeX,
              y: 0,
            },
            {
              x: beforeX,
              y: afterX,
            },
            {
              x: 0,
              y: afterX,
            },
          ],
        ];
      } else {
        this.handleData();
      }
      // 模型类型区域标注点处理
      this.handleData_model()
      // this.handleData();
      // 只有模型类型选择为4，深度适配类的时候才需要主动去赋值的情况，其他情况自己选值
      if (this.model_template_config_id_num == 4) {
        this.ruleForm.test_type_id = this.options4[0].id
        this.ruleForm.label_list = [this.options4[0].test_type_ename]
      }
      // 逆向寻找设备ID
      let computing_id;
      this.computeOptions.some(v1 => {
        // console.log("v1", v1);
        if (v1.children) {
          return v1.children.some(v2 => {
            // console.log("v2", v2);
            if (v2.children) {
              return v2.children.some(v3 => {
                // console.log("v3", v3);
                if (v3.id === this.ruleForm.resource_id) {
                  computing_id = v1.deviceId;
                  return true; // 终止所有循环
                }
                return false;
              });
            }
            return false;
          });
        }
        return false;
      });
      // 取出小类详情信息template_data
      let template_data = JSON.stringify(this.getModelSmallDetail())
      // let template_data = []
      // if (template_data_res == false) {
      //   this.$message({
      //     type: 'warning',
      //     message: '模板数据中存在未填写项！请检查修正后重新提交!'
      //   })
      //   return
      // } else {
      //   template_data = JSON.stringify(this.getModelSmallDetail())
      // }
      let model_template_type_id
      this.modelOptions.forEach(item => {
        item.children.forEach(v => {
          if (v.id == this.ruleForm.model_template_config_id) {
            model_template_type_id = item.id
          }
        })
      })
      // 新增
      let forms = {
        conf_name: this.ruleForm.conf_name,
        Algorithm_library_id: this.ruleForm.Algorithm_library_id,
        Mine_id: this.ruleForm.mine_name,
        Equipment_id: this.ruleForm.equipment_name,
        // conf_object: "",
        conf_area: this.drawLineOpen ? this.mark_lists3 : this.mark_lists,
        test_type_id: this.ruleForm.test_type_id,
        label_list: JSON.stringify(this.ruleForm.label_list),
        shield_status: this.shield_status,
        tem_frames: this.ruleForm.tem_frames,
        confidence: this.ruleForm.confidence,
        tem_conf_area: this.mark_lists2,
        draw_type: this.drawLineOpen ? '2' : '1',
        img_resolution: this.resolution,
        duration_time: this.ruleForm.duration_time,
        interval_time: this.ruleForm.interval_time,
        image_draw_type: this.image_draw_type,
        Algorithm_config_ps: this.ruleForm.Algorithm_config_ps,
        scene_typename: this.ruleForm.scene_typename,
        sensitivity: this.ruleForm.sensitivity,
        resource_id: this.ruleForm.resource_id,
        computing_id: computing_id,
        resource_id_old: this.ruleForm.resource_id_old,
        defense_time_start: this.ruleForm.defense_time_start,
        defense_time_end: this.ruleForm.defense_time_end,
        model_template_config_id: this.ruleForm.model_template_config_id,
        model_template_type_id: model_template_type_id,
        template_list_area: this.mark_lists_model,
        template_small_id: this.ruleForm.template_small_id,
        res_type: this.ruleForm.res_type,
        template_data: template_data
      };
      // 修改(修改的时候list标注数据记得处理)
      let forms2 = {
        id: this.ruleForm.id,
        conf_name: this.ruleForm.conf_name,
        Algorithm_library_id: this.ruleForm.Algorithm_library_id,
        Mine_id: this.ruleForm.mine_name,
        Equipment_id: this.ruleForm.equipment_name,
        // conf_object: "",
        conf_area: this.drawLineOpen ? JSON.stringify(this.mark_lists3) : JSON.stringify(this.mark_lists),
        test_type_id: this.ruleForm.test_type_id,
        label_list: JSON.stringify(this.ruleForm.label_list),
        shield_status: this.shield_status,
        tem_frames: this.ruleForm.tem_frames,
        confidence: this.ruleForm.confidence,
        tem_conf_area: JSON.stringify(this.mark_lists2),
        draw_type: this.drawLineOpen ? '2' : '1',
        img_resolution: this.resolution,
        duration_time: this.ruleForm.duration_time,
        interval_time: this.ruleForm.interval_time,
        image_draw_type: this.image_draw_type,
        Algorithm_config_ps: this.ruleForm.Algorithm_config_ps,
        scene_typename: this.ruleForm.scene_typename,
        sensitivity: this.ruleForm.sensitivity,
        resource_id: this.ruleForm.resource_id,
        computing_id: computing_id,
        resource_id_old: this.ruleForm.resource_id_old,
        defense_time_start: this.ruleForm.defense_time_start,
        defense_time_end: this.ruleForm.defense_time_end,
        model_template_config_id: this.ruleForm.model_template_config_id,
        model_template_type_id: model_template_type_id,
        template_list_area: JSON.stringify(this.mark_lists_model),
        template_small_id: this.ruleForm.template_small_id,
        res_type: this.ruleForm.res_type,
        template_data: template_data
      };
      if (this.title == "算法配置") {
        this.$http
          .post(this.$url.url_5000 + "/model_view/algorithm_add", forms)
          .then((response) => {
            // console.log(response);
            if (response.data.code === 200) {
              this.$message({
                message: response.data.msg,
                type: "success",
              });
              this.axioss();
              this.handleClose();
            } else {
              this.$message({
                message: response.data.msg,
                type: "warning",
              });
            }
          })
          .catch(function (response) {
            console.log(response);
          });
      } else if (this.title == "算法修改") {
        // console.log(forms2);
        const params = new URLSearchParams();
        // 处理模型绘制区域数据
        // forms2.template_list_area = JOSN.parse(forms2.template_list_area)
        for (const key in forms2) {
          params.append(key, forms2[key]);
        }
        this.$http
          .post(this.$url.url_5000 + "/model_view/algorithm_update", params, {
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
            },
          })
          .then((response) => {
            if (response.data.code === 200) {
              this.$message({
                message: response.data.msg,
                type: "success",
              });
              this.axioss();
              this.handleClose();
            } else {
              this.$message({
                message: response.data.msg,
                type: "warning",
              });
            }
          })
          .catch(function (response) {
            console.log(response);
          });
      }
    },
    handleSelect(a) {
      // let param = new URLSearchParams();
      // param.append("mine_id", this.mkname);
      if (a === 1) {
        this.ruleForm.equipment_name = "";
      }
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: this.ruleForm.mine_name, 
              // List filters use the server algorithm library across categories.
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          // console.log(response);
          if (response.data.code === 200) {
            this.options1 = response.data.mine_list;
            this.ruleForm.mine_name = response.data.mine_list[0].id
            this.options2 = response.data.equipment_list;
            this.options3 = response.data.algorithm_list;
            // this.options4=response.data.test_type_list
            this.modelOptions = response.data.model_type_template.map(v => {
              return {
                ...v,
                model_id: 'F' + v.id,
                children: v.template_model_data_list.map(child => {
                  return {
                    ...child,
                    model_id: child.id,
                    model_type_name: child.model_name
                  }
                })
              }
            })
            // console.log(9527,this.modelOptions)
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    handleimg(num) {
      // this.openFullScreen();
      this.loading = true;
      this.loading2 = true;
      this.imgOpen = false;
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/image_show",
          {
            params: {
              equipment_id: this.ruleForm.equipment_name,
              type: num == 1 ? num : this.ruleForm.type,
              img_resolution: this.resolution,
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          this.loading = true;
          if (response.data.code === 200) {
            this.resolution = response.data.img_resolution; //安防、录像机分辨率传或不传问题
            this.handleTimesData(this.resolution)
            let imgUrl = this.$url.url_5000 + "" + response.data.msg;
            this.imgurl = `${imgUrl}?timestamp=${new Date().getTime()}`;
            this.loading = false;
            this.loading2 = true;
            if (!this.drawLineOpen) {
              this.initCanvas();
            } else {
              this.initCanvas4();
            }
            this.initCanvas_model();
            this.imgOpen = true;
          } else {
            this.$message({
              message: response.data.msg,
              type: "warning",
            });
            this.imgurl = "";
            this.loading = false;
            this.loading2 = true;
            this.imgOpen = false;
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    handledel() {
      // console.log(this.multipleSelection);
      if (this.multipleSelection.length > 0) {
        this.$confirm("此操作将永久删除选中信息, 是否继续?", "提示", {
          confirmButtonText: "确定",
          cancelButtonText: "取消",
          type: "warning",
        })
          .then(() => {
            this.$http
              .post(this.$url.url_5000 + "/model_view/algorithm_data_delete", {
                id: this.multipleSelection,
              })
              .then((response) => {
                // console.log(response);
                if (response.data.code === 200) {
                  this.$message({
                    message: response.data.msg,
                    type: "success",
                  });
                  this.axioss();
                } else {
                  this.$message({
                    message: response.data.msg,
                    type: "warning",
                  });
                }
              })
              .catch(function (response) {
                console.log(response);
              });
            // this.$message({
            //   type: 'success',
            //   message: '删除成功!'
            // });
          })
          .catch(() => {
            this.$message({
              type: "info",
              message: "已取消删除",
            });
          });
      } else {
        this.$message(
          {
            type: 'warning',
            message: '没有选中删除的信息'
          }
        )
      }
    },
    // stringToArray(str) {
    //   // 去除首尾的方括号和空格
    //   let cleanedStr = str.replace(/^$|\'|$$/g, '').trim();

    //   // 按照逗号分隔并去除每个元素两端的空白字符和引号
    //   return cleanedStr.split(',').map(item => item.trim().replace(/^'|'$/g, ''));
    // },
    // 表格修改按钮
    handlechanges(data){
      if(data.multimodels_type == 0){
        this.$router.push({
          path: '/sfgl_child',
          query: {
            conf_id: data.id,
          }
        })
      }else{
        this.$router.push({
          path: '/sfgl_childs',
          query: {
            id: data.id,
            map: JSON.stringify(data.merged_model_data),
          }
        })
      }
    },
    handlechange(data) {
      this.modelNameOpen = false
      this.stepActive = 0
      this.coordinates = [];
      this.coordinates_model = [];
      this.coordinates2 = [];
      this.coordinates3 = [];
      this.$http
        .get(this.$url.url_5000 + "/model_view/algorithm_data_show", {
          params: {
            // algorithm_name: this.conf_name,
            // start_time: this.StartTime,
            // end_time: this.EndTime,
            // page: this.pagenumber,
            // per_page: this.pagesize
            conf_id: data.id,
          },
        })
        .then((response) => {
          if (response.data.code === 200) {
            this.title = "算法修改";
            this.ruleForm = response.data.datalist;
            console.log(this.ruleForm)
            // this.ruleForm.label_list = this.stringToArray(this.ruleForm.label_list)
            // console.log(12121212121212121, this.ruleForm.label_list)
            this.findModelBigDict(this.ruleForm.model_template_config_id)
            // this.handleChangeTemplateSmall()
            this.ruleForm.template_data = this.ruleForm.template_data.reduce((acc, obj) => {
              if (Object.keys(obj).length > 0) {
                const key = Object.keys(obj)[0];
                acc.push({
                  key: key,
                  value: obj[key]
                });
              }
              return acc;
            }, []);
            if (this.ruleForm.tem_frames == '') {
              this.ruleForm.tem_frames = '[27,37]'
            }
            if (this.ruleForm.confidence == null || this.ruleForm.confidence == '') {
              this.ruleForm.confidence = "80"
            }
            this.drawLineOpen = this.ruleForm.draw_type == '2' ? true : false
            this.image_draw_type = this.ruleForm.image_draw_type
            this.resolution = this.ruleForm.img_resolution
            this.ruleForm.resource_id_old = this.ruleForm.resource_id
            this.handleTimesData(this.resolution)
            // console.log(this.ruleForm);
            // console.log("147369", this.drawLineOpen, this.area2);
            this.ruleForm.mine_name = this.ruleForm.Mine_id;
            this.shield_status = Number(response.data.datalist.shield_status);
            this.dialogVisible = true;
            this.handleSelect();
            this.handleChangeSf(this.ruleForm.Algorithm_library_id);
            this.ruleForm.equipment_name = response.data.datalist.Equipment_id;

            this.handleimg();

            // 将list字符串转为可用数组
            if (this.ruleForm.draw_type == '2') {
              let arr = JSON.parse(response.data.datalist.conf_area.replace(/'/g, '"')); //这里拿到的数据是字符串，需要转换为数组
              let jia = [];
              let jia_w = [];
              for (let w = 0; w < arr.length; w++) {
                for (let i = 0; i < arr[w].length; i++) {
                  // let x = arr[w][i].x / 3;
                  // let y = arr[w][i].y / 3;
                  let x = arr[w][i].x / this.timesX;
                  let y = arr[w][i].y / this.timesY;
                  jia.push({
                    x,
                    y,
                  });
                }
                jia_w.push(jia)
                jia = []
              }
              this.mark_list3 = [...jia_w]; //给数组赋值，方便再次修改的时候提交数据
            } else {
              let arr = JSON.parse(response.data.datalist.conf_area.replace(/'/g, '"')); //这里拿到的数据是字符串，需要转换为数组
              let jia = [];
              let jia_w = [];
              for (let w = 0; w < arr.length; w++) {
                for (let i = 0; i < arr[w].length; i++) {
                  let x = arr[w][i].x / this.timesX;
                  let y = arr[w][i].y / this.timesY;
                  jia.push({
                    x,
                    y,
                    type: arr[w][i].type,
                    color: arr[w][i].color,
                  });
                }
                jia_w.push(jia)
                jia = []
              }
              this.mark_list = [...jia_w]; //给数组赋值，方便再次修改的时候提交数据
            }
            (() => {
              let arr = JSON.parse(response.data.datalist.template_list_area.replace(/'/g, '"')); //这里拿到的数据是字符串，需要转换为数组
              let jia = [];
              let jia_w = [];
              for (let w = 0; w < arr.length; w++) {
                for (let i = 0; i < arr[w].length; i++) {
                  let x = arr[w][i].x / this.timesX;
                  let y = arr[w][i].y / this.timesY;
                  jia.push({
                    x,
                    y,
                    type: arr[w][i].type,
                    color: arr[w][i].color,
                  });
                }
                jia_w.push(jia)
                jia = []
              }
              this.mark_list_model = [...jia_w]; //给数组赋值，方便再次修改的时候提交数据
            })();

            // this.handleimg();

            let tem_conf_area = response.data.datalist.tem_conf_area;
            this.$http
              .get(this.$url.url_5000 + "/model_view/equipment_one_info", {
                params: { equipment_id: this.ruleForm.equipment_name },
              })
              .then((response) => {
                console.log(response);
                if (response.data.data.equipment_code == "201") {
                  this.area2 = true;
                  let arr2 = JSON.parse(tem_conf_area.replace(/'/g, '"')); //这里拿到的数据是字符串，需要转换为数组
                  let jia2 = [];
                  for (let i = 0; i < arr2[0].length; i++) {
                    // let x = arr2[0][i].x / 3;
                    // let y = arr2[0][i].y / 3;
                    let x = arr2[0][i].x / this.timesX;
                    let y = arr2[0][i].y / this.timesY;
                    jia2.push({
                      x,
                      y,
                    });
                  }
                  this.mark_list2 = [jia2]; //给数组赋值，方便再次修改的时候提交数据
                  // 进行热成像区域的canvas加载
                  this.initCanvas2();
                } else {
                  this.area2 = false;
                }
              });

            // this.handleChangeCanvas2(this.ruleForm.equipment_name);
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    findModelBigDict(id) {
      this.modelOptions.forEach(item => {
        let res = item.children.find(v => v.id == id)
        if (res) {
          this.getModelSmallDict([item.model_id])
          return
        }
      })
    },
    handleClose() {
      this.$refs.ruleForms.resetFields();
      this.imgurl = "";
      this.$nextTick(() => {
        this.dialogVisible = false;
      });
    },
    handleClose2() {
      this.dialogVisible2 = false;
      this.handleUpdateList();
    },
    handleClose2_model() {
      this.dialogVisible2_model = false;
      this.handleUpdateList_model();
    },
    handleClose3() {
      this.dialogVisible3 = false;
    },
    handleClose4() {
      this.stopVideo();
      this.dialogVisible4 = false;
      clearInterval(this.checkStatusTime)
      // 如果已经存在 FLV 播放器实例，先销毁当前的播放器
      if (this.flvPlayer && this.flvPlayer.destroy) {
        this.flvPlayer.destroy();
      }
    },
    handleClose5() {
      this.dialogVisible5 = false;
    },
    /* 画布初始化 */
    initCanvas() {
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs.mycanvas;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        // 计算使用变量
        // this.mark_list = []
        let list = this.mark_list; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        let coordinates = this.coordinates
        // 若list长度不为0, 则显示已标记框
        let this_ = this
        draw_test(cav, list, this.handleChooseType, coordinates);
      });
    },
    initCanvas_model() {
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs.mycanvas_model;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        // 计算使用变量
        // this.mark_list = []
        let list = this.mark_list_model; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        let coordinates = this.coordinates_model
        // 若list长度不为0, 则显示已标记框
        let this_ = this
        draw_test(cav, list, this.handleChooseType_model, coordinates);
      });
    },
    initCanvas2() {
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs.mycanvas2;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        // 计算使用变量
        // this.mark_list = []
        let list = this.mark_list2; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        let coordinates = this.coordinates2
        // 若list长度不为0, 则显示已标记框
        draw_test3(cav, list, coordinates);
      });
    },
    initCanvas4() {
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs.mycanvas;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        // 计算使用变量
        // this.mark_list = []
        let list = this.mark_list3; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        let coordinates = this.coordinates3
        // 若list长度不为0, 则显示已标记框
        draw_test4(cav, list, coordinates);
      });
    },
    /* 画布初始化 */
    tableCanvas(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10); // 将宽度转换为整数
      var HH = parseInt(parts[1], 10); // 将高度转换为整数
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs[`tableCanvas_${id}`];
        cav.width = "96";
        cav.height = "54";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        // cav.style.cursor = "crosshair";
        let XX = parseInt(WW / 96, 10)
        let YY = parseInt(HH / 54, 10)
        // if (type == '2') {
        // 计算使用变量
        let res = list;
        let arr = [], arr_w = [];
        for (let w = 0; w < res.length; w++) {
          for (let i = 0; i < res[w].length; i++) {
            let x = Number(res[w][i].x) / XX;
            let y = Number(res[w][i].y) / YY;
            arr.push({
              x,
              y,
              color: res[w][i].color,
            });
          }
          arr_w.push(arr)
          arr = []
        }

        // this.mark_list = []
        // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        // 若list长度不为0, 则显示已标记框
        draw_test2(cav, [...arr_w]);
        // } else {
        //   // 计算使用变量
        //   let res = list[0];
        //   let arr = [];
        //   for (let i = 0; i < res.length; i++) {
        //     let x = Number(res[i].x) / XX;
        //     let y = Number(res[i].y) / YY;
        //     arr.push({
        //       x,
        //       y,
        //     });
        //   }
        //   // this.mark_list = []
        //   // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        //   // 若list长度不为0, 则显示已标记框
        //   draw_test2(cav, [arr]);
        // }
      });
    },
    tableCanvas(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10); // 将宽度转换为整数
      var HH = parseInt(parts[1], 10); // 将高度转换为整数
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs[`tableCanvas_${id}`];
        cav.width = "96";
        cav.height = "54";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        // cav.style.cursor = "crosshair";
        let XX = WW / 96
        let YY = HH / 54
        // if (type == '2') {
        // 计算使用变量
        let res = list;
        let arr = [], arr_w = [];
        for (let w = 0; w < res.length; w++) {
          for (let i = 0; i < res[w].length; i++) {
            let x = Number(res[w][i].x) / XX;
            let y = Number(res[w][i].y) / YY;
            arr.push({
              x,
              y,
              color: res[w][i].color,
            });
          }
          arr_w.push(arr)
          arr = []
        }

        // this.mark_list = []
        // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        // 若list长度不为0, 则显示已标记框
        draw_test2(cav, [...arr_w]);
        // } else {
        //   // 计算使用变量
        //   let res = list[0];
        //   let arr = [];
        //   for (let i = 0; i < res.length; i++) {
        //     let x = Number(res[i].x) / XX;
        //     let y = Number(res[i].y) / YY;
        //     arr.push({
        //       x,
        //       y,
        //     });
        //   }
        //   // this.mark_list = []
        //   // let list = this.mark_list // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        //   // 若list长度不为0, 则显示已标记框
        //   draw_test2(cav, [arr]);
        // }
      });
    },
    tableCanvasMax(id, list, crossLineData, type, resolution) {
  var parts = resolution.split('x');
  var WW = parseInt(parts[0], 10); // 原始宽度
  var HH = parseInt(parts[1], 10); // 原始高度
  
  this.$nextTick(() => {
    let cav = this.$refs[`tableCanvas_tableMax`];
    if (!cav) return;
    
    cav.width = "800";
    cav.height = "400";
    let ctx = cav.getContext("2d");
    
    let XX = WW / 800;
    let YY = HH / 400;
    
    ctx.clearRect(0, 0, 800, 400);
    
    // 绘制框
    if (list && list.length > 0) {
      for (let w = 0; w < list.length; w++) {
        if (list[w].length < 3) continue;
        ctx.beginPath();
        ctx.strokeStyle = list[w][0].color || '#f00';
        ctx.lineWidth = 2;
        ctx.moveTo(list[w][0].x / XX, list[w][0].y / YY);
        for (let i = 1; i < list[w].length; i++) {
          ctx.lineTo(list[w][i].x / XX, list[w][i].y / YY);
        }
        ctx.closePath();
        ctx.stroke();
      }
    }
    
    // 绘制线
    if (crossLineData && crossLineData.p1 && crossLineData.p2) {
      try {
        const p1 = {
          x: Number(crossLineData.p1.x) / XX,
          y: Number(crossLineData.p1.y) / YY
        };
        const p2 = {
          x: Number(crossLineData.p2.x) / XX,
          y: Number(crossLineData.p2.y) / YY
        };
        
        p1.x = Math.min(800, Math.max(0, p1.x));
        p1.y = Math.min(400, Math.max(0, p1.y));
        p2.x = Math.min(800, Math.max(0, p2.x));
        p2.y = Math.min(400, Math.max(0, p2.y));
        
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.strokeStyle = "#ffd700";
        ctx.lineWidth = 2;
        ctx.stroke();
        
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        
        if (len > 0) {
          const ux = dx / len;
          const uy = dy / len;
          const perpLen = 70;
          const mx = (p1.x + p2.x) / 2;
          const my = (p1.y + p2.y) / 2;
          
          let leftX = mx - uy * perpLen;
          let leftY = my + ux * perpLen;
          let rightX = mx + uy * perpLen;
          let rightY = my - ux * perpLen;
          
          leftX = Math.min(780, Math.max(20, leftX));
          leftY = Math.min(380, Math.max(20, leftY));
          rightX = Math.min(780, Math.max(20, rightX));
          rightY = Math.min(380, Math.max(20, rightY));
          
          // ========== 根据 direction 动态显示（与表格一致） ==========
          let leftText, rightText, leftColor, rightColor;
          
          if (crossLineData.direction === 'left') {
            // direction='left' 表示 IN 在左边
            leftText = 'IN';
            rightText = 'OUT';
            leftColor = '#44ff44';  // 绿色 = IN
            rightColor = '#ff4444'; // 红色 = OUT
          } else if (crossLineData.direction === 'right') {
            // direction='right' 表示 IN 在右边
            leftText = 'OUT';
            rightText = 'IN';
            leftColor = '#ff4444';
            rightColor = '#44ff44';
          } else {
            // 默认：右边为 IN
            leftText = 'OUT';
            rightText = 'IN';
            leftColor = '#ff4444';
            rightColor = '#44ff44';
          }
          // =======================================================
          
          const drawArrow = (fromX, fromY, toX, toY, color) => {
            ctx.strokeStyle = color;
            ctx.fillStyle = color;
            ctx.lineWidth = 2;
            const headLen = 10;
            const angle = Math.atan2(toY - fromY, toX - fromX);
            
            ctx.beginPath();
            ctx.moveTo(fromX, fromY);
            ctx.lineTo(toX, toY);
            ctx.stroke();
            
            ctx.beginPath();
            ctx.moveTo(toX, toY);
            let x1 = toX - headLen * Math.cos(angle - Math.PI / 6);
            let y1 = toY - headLen * Math.sin(angle - Math.PI / 6);
            ctx.lineTo(x1, y1);
            ctx.moveTo(toX, toY);
            let x2 = toX - headLen * Math.cos(angle + Math.PI / 6);
            let y2 = toY - headLen * Math.sin(angle + Math.PI / 6);
            ctx.lineTo(x2, y2);
            ctx.stroke();
          };
          
          const drawText = (x, y, text, color) => {
            ctx.font = "bold 18px Arial";
            ctx.textAlign = "center";
            ctx.fillStyle = color;
            ctx.fillText(text, x, y - 12);
          };
          
          drawArrow(mx, my, leftX, leftY, leftColor);
          drawArrow(mx, my, rightX, rightY, rightColor);
          drawText(leftX, leftY, leftText, leftColor);
          drawText(rightX, rightY, rightText, rightColor);
        }
      } catch(e) {
        console.error('绘制线失败:', e);
      }
    }
  });
},
    // 提交数据处理
    handleData() {
      if (this.mark_list.length != 0 && !this.drawLineOpen) {
        let data = this.mark_list
        let arr = []
        for (let i = 0; i < data.length; i++) {
          arr.push(
            this.mark_list[i].map(v => ({
              x: (v.x * this.timesX).toFixed(0),
              y: (v.y * this.timesY).toFixed(0),
              type: v.type,
              color: v.color,
            }))
          )
        }
        this.mark_lists = arr
      } else {
        this.mark_lists = [];
      }
      // 热成像
      if (this.mark_list2.length != 0) {
        let data2 = this.mark_list2[0];
        let arr2 = [];
        for (let i = 0; i < data2.length; i++) {
          let x = (data2[i].x * this.timesX).toFixed(0);
          let y = (data2[i].y * this.timesY).toFixed(0);
          arr2.push({
            x,
            y,
          });
        }
        this.mark_lists2 = [arr2];
      } else {
        this.mark_lists2 = [];
      }

      // 画线
      if (this.mark_list3.length != 0 && this.drawLineOpen) {
        let data = this.mark_list3;
        let arr3 = [];
        let arr_w = [];
        for (let w = 0; w < data.length; w++) {
          for (let i = 0; i < data[w].length; i++) {
            // let x = data[w][i].x * 3;
            // let y = data[w][i].y * 3;
            let x = (data[w][i].x * this.timesX).toFixed(0);
            let y = (data[w][i].y * this.timesY).toFixed(0);
            arr3.push({
              x,
              y,
              type: '报警',
            });
          }
          arr_w.push(arr3)
          arr3 = []
        }
        this.mark_lists3 = [...arr_w];
        this.mark_lists3.sort((a, b) => {
          // 按照第一个对象的x值进行比较
          return b[0].y - a[0].y;
        });
      } else {
        this.mark_lists3 = [];
      }
    },
    // 处理模型区域数据
    handleData_model() {
      if (this.mark_list_model.length != 0) {
        let data = this.mark_list_model
        let brr = []
        for (let i = 0; i < data.length; i++) {
          brr.push(
            this.mark_list_model[i].map(v => ({
              x: (v.x * this.timesX).toFixed(0),
              y: (v.y * this.timesY).toFixed(0),
              type: v.type,
              color: v.color,
            }))
          )
        }
        this.mark_lists_model = brr
      } else {
        this.mark_lists_model = [];
      }
    },
    openFullScreen() {
      this.loading = true;
      setTimeout(() => {
        this.loading = false;
      }, 2000);
    },
    handleChangeSf(id) {
      this.$http
        .get(this.$url.url_5000 + "/model_view/Algorithm_type_select", {
          params: {
            id,
          },
        })
        .then((response) => {
          this.options4 = response.data.data.algorithm_data;
          // 模型类型、模型小类赋值
          if (this.title == '算法配置') {
            this.ruleForm.model_template_config_id = response.data.data.model_data[0].id
            this.getModelSmallDict2(response.data.data.model_type_data[0].id)
            this.ruleForm.template_small_id = response.data.data.template_small_data[0].id
            this.handleChangeTemplateSmall()
          } else if (this.title == '算法修改') {
            // console.log("代码跑到这里了嘛？？？？？")
            this.ruleForm.model_template_config_id = response.data.data.model_data[0].id
            this.getModelSmallDict2(response.data.data.model_type_data[0].id)
            this.ruleForm.template_small_id = response.data.data.template_small_data[0].id
          }
        })
        .catch((rek) => {
          console.log(rek);
        });
    },
    // 重绘
    handleDrewAgain() {
      this.mark_list3 = [];
      this.mark_list = [];
      this.coordinates = [];
      this.coordinates3 = [];
      if (this.drawLineOpen) {
        this.initCanvas4();
      } else {
        this.initCanvas();
      }
    },
    // 类型重绘
    handleDrewAgain_model() {
      this.mark_list_model = [];
      this.coordinates_model = [];
      this.initCanvas_model();
    },
    handleDrewAgain2() {
      this.mark_list2 = [];
      this.coordinates2 = [];
      this.initCanvas2();
    },
    handleChangeDrawLine() {
      this.mark_list3 = [];
      this.mark_list = [];
      if (this.drawLineOpen) {
        this.initCanvas4();
      } else {
        this.initCanvas();
      }
    },
    handleChangeDrawArea() {
      this.handleChangeDrawLine()
    },
    //状态修改函数
    handleChangeStatus(data) {
      if (this.batchStatusBusy || this.statusPending[data.id]) return;
      const requestedStatus = data.status;
      const previousStatus = requestedStatus === '运行' ? '停止' : '运行';
      this.$set(this.statusPending, data.id, true);
      // Any read started before this change must not restore the previous state.
      ++this.listRequestSequence;
      clearTimeout(this.statusRefreshTimer);
      this.statusRefreshTimer = null;
      return this.$http
        .post(
          this.$url.url_5000 + "/model_view/algorithm_conf_update",
          {
            id: data.id,
            status: requestedStatus,
          },
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
          }
        )
        .then((response) => {
          if (response.data.code == 200) {
            this.$message({ type: "success", message: response.data.msg });
          } else {
            data.status = previousStatus;
            this.$message({ type: "warning", message: response.data.msg });
          }
          return this.axioss();
        })
        .catch((rek) => {
          data.status = previousStatus;
          this.$message({ type: "error", message: rek.response && rek.response.data && rek.response.data.msg || "更新运行状态失败，请刷新后重试" });
          return this.axioss();
        })
        .then(() => {
          this.$delete(this.statusPending, data.id);
        }, () => {
          this.$delete(this.statusPending, data.id);
        });
    },
    // 当遮挡配置选择为遮挡的时候，清空标注区域。
    handleChangeShield_status() {
      this.handleDrewAgain();
    },
    // 热成像区域相关
    handleChangeCanvas2(data) {
      // console.log("特殊热成像摄像头",this.ruleForm.equipment_name);
      // console.log(this.options2);
      // /model_view/equipment one_info
      this.$http
        .get(this.$url.url_5000 + "/model_view/equipment_one_info", {
          params: { equipment_id: data ? data : this.ruleForm.equipment_name },
        })
        .then((response) => {
          // console.log(response);
          if (response.data.data.equipment_code == "201") {
            this.area2 = true;
            // this.resolution = '1280x720';
            this.handleTimesData(this.resolution);
            // 进行热成像区域的canvas加载
            this.initCanvas2();
          } else {
            this.area2 = false;
            // this.resolution = '1920x1080';
            this.handleTimesData(this.resolution);

            // 这里需要强行转换划线状态，当他从热成像（201）变成其他状态的时候，需要从划线变为画框。
            this.mark_list3 = [];
            this.mark_list = [];
            this.drawLineOpen = false;
            this.initCanvas();
          }
          this.handleimg();
        });
    },
    // 通过选中的分辨率，来计算渲染比值timesX和timesY
    handleTimesData(resolution) {
      let w = 640, h = 360;
      var parts = resolution.split('x');
      // var width = parseInt(parts[0], 10); // 将宽度转换为整数
      // var height = parseInt(parts[1], 10); // 将高度转换为整数
      var width = parts[0]; // 宽度
      var height = parts[1]; // 高度
      this.timesX = (width / w).toFixed(2);
      this.timesY = (height / h).toFixed(2);
      // this.handleimg(1)//刷新
      // this.handleDrewAgain();//重新绘制

    },
    // 区域标注类型选择
    handleChooseType() {
      this.selectedOption = '告警区域'
      this.title2 = '区域标注类型选择'
      this.dialogVisible2 = true
    },
    // 类型标注类型选择
    handleChooseType_model() {
      this.selectedOption_model = '类型一'
      this.title2_model = '模型类型选择'
      this.dialogVisible2_model = true
    },
    handleUpdateList() {
      // console.log(this.mark_list);
      // console.log(this.selectedOption);
      let color = {
        'I级报警': '#FF0000',
        // 'II级报警': '#FFA500',
        // 'III级报警': '#FCFF00',
        // '消除': '#8a8383',
        '类型一': '#67C23A',
        '类型二': '#FFA500',
        '类型三': '#FCFF00',
      }
      this.mark_list[this.mark_list.length - 1] = this.mark_list[this.mark_list.length - 1].map(v => ({
        ...v,
        type: this.selectedOption,
        color: color[this.selectedOption]
      }));
      this.coordinates = []
      this.initCanvas()
      // console.log("数据一致性检查-------------------------");
      // console.log(this.mark_list);
      this.dialogVisible2 = false
    },
    handleUpdateList_model() {
      let color = {
        '类型一': '#FF0000',
        '类型二': '#FFA500',
        '类型三': '#FCFF00',
      }
      this.mark_list_model[this.mark_list_model.length - 1] = this.mark_list_model[this.mark_list_model.length - 1].map(v => ({
        ...v,
        type: this.selectedOption_model,
        color: color[this.selectedOption_model]
      }));
      this.coordinates_model = []
      this.initCanvas_model()
      // console.log("数据一致性检查-------------------------");
      // console.log(this.mark_list);
      this.dialogVisible2_model = false
    },
    handleDeleteList() {
      this.coordinates = [];
      this.coordinates2 = [];
      this.coordinates3 = [];//清除当前标注数据
      // 由于鼠标双击的时候，数据已经被提交，所以要从根源上删除该数据
      this.mark_list.pop()
    },
    handleDeleteList_model() {
      this.coordinates_model = [];
      // this.coordinates2 = [];
      // this.coordinates3 = [];//清除当前标注数据
      // 由于鼠标双击的时候，数据已经被提交，所以要从根源上删除该数据
      this.mark_list_model.pop()
    },
    // 打开历史弹窗
    handleOpenHistory(id) {
      this.title3 = '历史信息记录'
      this.dialogVisible3 = true
      this.historyKey++;  // 每次打开对话框时增加 key 的值，触发重新渲染
      if (id) {

        this.$nextTick(() => {
          this.$refs.historyTable.historyValue = '2'
          this.$refs.historyTable.queryParams = {
            id
          }
          this.$refs.historyTable.axioss2()
        })
        // this.$nextTick(() => {
        //   this.$refs.historyTable.axioss2()
        // })
        return
      }
      this.$nextTick(() => {
        this.$refs.historyTable.historyValue = '2'
        this.$refs.historyTable.axioss()
      })
    },
    handleCloseDialog() {
      this.dialogVisible = false;
    },
    handleOpenSpfx(row) {
      this.$http.get(spfxApi.getAlgConfVideo, {
        params: {
          config_id: row.id,
          width: 360,
          height: 200,
          frame_r: 5,
          baud_b: 1200,
          stream_data_flag: 1
        }
      }).then(response => {
        if (response.data.code == 200) {
          this.$message.success(response.data.message);
          this.dialogVisible4 = true;
          this.checkStatusTime = setInterval(() => {
            this.startCheckStatus();
          }, 1000)
        }
      }).catch(rek => {
        console.log(rek)
      })
    },
    // 状态检测函数
    startCheckStatus() {
      /* 
        200 成功
        201 暂无图片(201不用处理，继续执行)
        203 不能播放，直接终止
      */
      this.$http.get(spfxApi.getAlgStatusVideo)
        .then(response => {
          if (response.data.code == 203) {
            clearInterval(this.checkStatusTime)
            this.$message.warning('无法查看')
          } else if (response.data.code == 200) {
            clearInterval(this.checkStatusTime)
            this.playVideo(response.data.video_type)
          }
        })
        .catch(rek => {
          console.log(rek)
        })
    },
    // 播放视频函数
    playVideo(url) {
      // 检查浏览器是否支持 FLV.js
      if (flvjs.isSupported()) {
        // 获取视频元素
        const videoElement = this.$refs.videoPlayer;

        // 如果已经存在 FLV 播放器实例，先销毁当前的播放器
        // if (this.flvPlayer && this.flvPlayer.destroy) {
        //   this.flvPlayer.destroy();
        //   this.flvPlayer = null; // 销毁后将播放器实例置为 null，确保重新创建
        // }

        // 创建新的 FLV 播放器实例
        this.flvPlayer = flvjs.createPlayer({
          type: 'flv',
          url: url, // 你的 FLV 流地址
        });

        // 将新的播放器绑定到视频元素
        this.flvPlayer.attachMediaElement(videoElement);

        // 开始加载和播放新的视频
        this.flvPlayer.load();
        this.flvPlayer.play();
      } else {
        this.$message.warning('浏览器不支持 FLV.js');
      }
    },
    stopVideo() {
      this.$http.get(spfxApi.stopVideoSfgl, {
        params: {
          stream_data_flag: 3
        }
      }).then(response => {
        // if (response.data.code === 200) {
        //   this.$message.success('停止成功');
        // }
        // 如果已经存在 FLV 播放器实例，先销毁当前的播放器
        if (this.flvPlayer && this.flvPlayer.destroy) {
          this.flvPlayer.destroy();
        }
      }).catch(rek => {
        console.log(rek)
      })
    },
    // 步骤条，上下一条切换
    stepUp() {
      document.getElementById('stepDialog').click();
      if (this.stepActive > 0) {
        const loading = this.$loading({
          lock: true,
          text: "Loading",
          spinner: "el-icon-loading",
          background: "rgba(0, 0, 0, 0.7)",
        });
        this.stepActive--
        loading.close()
      }
    },
    stepNext() {
      document.getElementById('stepDialog').click();
      if (this.stepActive <= 2) {
        const loading = this.$loading({
          lock: true,
          text: "Loading",
          spinner: "el-icon-loading",
          background: "rgba(0, 0, 0, 0.7)",
        });
        this.stepActive++
        loading.close()
      }
    },
    // 任务名称名字自动化获取
    updateConfName() {
      const { equipment_name, Algorithm_library_id } = this.ruleForm;
      console.log(equipment_name, Algorithm_library_id)
      let algorithmName = '';
      let monitorPointName = '';
      // 查找解析类型名称
      if (Algorithm_library_id) {
        const selectedAlgorithm = this.options3.find(option => option.id === Algorithm_library_id);
        algorithmName = selectedAlgorithm ? selectedAlgorithm.algorithm_name : '';
        // algorithmName = (algorithmName.split('_'))[1]
      }

      // 组合监控点名称和解析类型名称
      if (equipment_name) {
        // 假设 cascader 的最后一级是监控点名称
        for (let item of this.options2) {
          // 检查 children 属性是否存在并且是数组
          if (Array.isArray(item.children)) {
            // 使用 find 方法查找具有指定 id 的子项
            const foundChild = item.children.find(child => child.id === equipment_name);
            // 如果找到了匹配项，则返回它的 equipment_name
            if (foundChild) {
              monitorPointName = foundChild.equipment_name;
            }
          }
        }
      }
      if (equipment_name && Algorithm_library_id) {
        this.ruleForm.conf_name = `${monitorPointName}-${algorithmName}`;
        // this.ruleForm.conf_name = `${monitorPointName}-${algorithmName}`;
        this.$http.post(findModelName, {
          conf_name: this.ruleForm.conf_name
        }).then(response => {
          if (response.data.code == 400) {
            this.modelNameOpen = true
            this.modelNamemsg = response.data.msg
          } else {
            this.modelNamemsg = response.data.msg
            this.modelNameOpen = false
          }
        }).catch(rek => {
          console.log(rek)
        })
      } else {
        this.ruleForm.conf_name = '';
      }
      if(this.ruleForm.conf_name == '' || this.ruleForm.conf_name == null || this.ruleForm.conf_name == undefined){
        this.conf_name_note = '';
        this.conf_name_type = false;
        this.ruleForm.conf_name = '';
      }else{
        this.conf_name_note = this.ruleForm.conf_name;
        this.conf_name_type = true;
        this.ruleForm.conf_name = '';
      }
    },
    handlesearchModelName() {
      this.$http.post(findModelName, {
        conf_name: this.ruleForm.conf_name
      }).then(response => {
        if (response.data.code == 400) {
          this.modelNameOpen = true
          this.modelNamemsg = response.data.msg
        } else {
          this.modelNamemsg = response.data.msg
          this.modelNameOpen = false
        }
      }).catch(rek => {
        console.log(rek)
      })
    },
    //选择小类，查询相关配置详情
    handleChangeTemplateSmall() {
      this.$http.get(modelApi.getModelSmallDetail, {
        params: {
          id: this.ruleForm.template_small_id
        }
      }).then(response => {
        if (response.data.code == 200) {
          this.ruleForm.template_data = response.data.data.list_data.reduce((acc, obj) => {
            if (Object.keys(obj).length > 0) {
              const key = Object.keys(obj)[0];
              acc.push({
                key: key,
                value: obj[key]
              });
            }
            return acc;
          }, []);
        } else {
          this.ruleForm.template_data = []
        }
      }).catch(rek => {
        this.ruleForm.template_data = []
        console.log(rek)
      })
    },
    // 删除一个小类详情
    removeItem(index) {
      this.ruleForm.template_data.splice(index, 1)
    },
    // 新增一个小类详情
    addItem() {
      this.ruleForm.template_data.push({ key: '', value: '' })
    },
    // 获取小类详情的数据
    getModelSmallDetail() {
      // 检查是否有任何一个 key 或 value 为空
      // if (this.ruleForm.template_data.length != 0) {
      //   for (const item of this.ruleForm.template_data) {
      //     if (!item.key || item.key.trim() === '' || !item.value || item.value.trim() === '') {
      //       return false;
      //     }
      //   }
      // }
      return this.ruleForm.template_data.map(item => {
        const obj = {};
        obj[item.key] = item.value;
        return obj;
      });
    },
    handleChangeLabelList() {
      console.log("slect选中值输出====", this.ruleForm.label_list)
      if (this.ruleForm.label_list.length != 0) {
        this.ruleForm.test_type_id = (this.options4.find(v => v.test_type_ename == this.ruleForm.label_list[0])).id
      }
    },
    // 表格点击图片
    handleOpenTableImg(id) {
  this.dialogVisible5 = true
  this.analysisId = id
  let res = this.tableData.find(v => v.id == id)
  this.analysisSrc = this.url_5000 + res.image
  
  // 解析框数据
  let confArea = []
  if (res.conf_area && res.conf_area != '[]') {
    confArea = JSON.parse(res.conf_area.replace(/'/g, '"'))
  }
  
  // 解析线数据
  let crossLineData = null
  if (res.cross_line_area && res.cross_line_area !== '' && res.cross_line_area !== '{}') {
    try {
      crossLineData = typeof res.cross_line_area === 'string' 
        ? JSON.parse(res.cross_line_area.replace(/'/g, '"')) 
        : res.cross_line_area
    } catch(e) {
      console.error('解析线数据失败:', e)
    }
  }
  
  this.tableCanvasMax(res.id, confArea, crossLineData, res.draw_type, res.img_resolution)
},
   handleUpImg(){
  let index = this.tableData.findIndex(v=>v.id == this.analysisId)
  if (index == 0) {
    this.$message({
      type: 'success',
      message: '当前是第一条信息！！！'
    })
  } else {
    index -= 1
    this.analysisId = this.tableData[index].id
    this.analysisSrc = this.url_5000 + this.tableData[index].image
    
    // 解析框数据
    let confArea = []
    if (this.tableData[index].conf_area && this.tableData[index].conf_area != '[]') {
      confArea = JSON.parse(this.tableData[index].conf_area.replace(/'/g, '"'))
    }
    
    // 解析线数据
    let crossLineData = null
    if (this.tableData[index].cross_line_area && this.tableData[index].cross_line_area !== '' && this.tableData[index].cross_line_area !== '{}') {
      try {
        crossLineData = typeof this.tableData[index].cross_line_area === 'string' 
          ? JSON.parse(this.tableData[index].cross_line_area.replace(/'/g, '"')) 
          : this.tableData[index].cross_line_area
      } catch(e) {
        console.error('解析线数据失败:', e)
      }
    }
    
    this.tableCanvasMax(this.tableData[index].id, confArea, crossLineData, this.tableData[index].draw_type, this.tableData[index].img_resolution)
  }
},
handleNextImg(){
  let index = this.tableData.findIndex(v=>v.id == this.analysisId)
  if (index == this.tableData.length - 1) {
    this.$message({
      type: 'success',
      message: '当前是最后一条信息！！！'
    })
  } else {
    index += 1
    this.analysisId = this.tableData[index].id
    this.analysisSrc = this.url_5000 + this.tableData[index].image
    
    // 解析框数据
    let confArea = []
    if (this.tableData[index].conf_area && this.tableData[index].conf_area != '[]') {
      confArea = JSON.parse(this.tableData[index].conf_area.replace(/'/g, '"'))
    }
    
    // 解析线数据
    let crossLineData = null
    if (this.tableData[index].cross_line_area && this.tableData[index].cross_line_area !== '' && this.tableData[index].cross_line_area !== '{}') {
      try {
        crossLineData = typeof this.tableData[index].cross_line_area === 'string' 
          ? JSON.parse(this.tableData[index].cross_line_area.replace(/'/g, '"')) 
          : this.tableData[index].cross_line_area
      } catch(e) {
        console.error('解析线数据失败:', e)
      }
    }
    
    this.tableCanvasMax(this.tableData[index].id, confArea, crossLineData, this.tableData[index].draw_type, this.tableData[index].img_resolution)
  }
},
  },
  mounted() {
    this.axioss();
    this.handleSelect();
  },
  beforeDestroy() {
    ++this.listRequestSequence;
    clearTimeout(this.statusRefreshTimer);
    this.statusRefreshTimer = null;
    this.stopVideo()
  },
  destroyed() {
    this.stopVideo()
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
        line-height: none;
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
        /* top: -35px; */
        top:-26px;
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
</style>
