<template>
  <div class="sfgl_child algorithm-config-model">
    <div class="sfpzs">
      <el-form ref="form" :model="form" :rules="rules" size="mini" label-width="110px">
        <div style="width: 100%;border: 1px dashed #e5e5e5;background: #f9fafb;border-radius: 10px;" v-if="type_jx">
          <el-form-item label="检测类型" style="margin-top: 16px;" v-show="model_template_config_id_num != 4">
            <el-select v-model="jclxslist" placeholder="请选择检测类型" size="mini" clearable filterable multiple style="width: 50%" @change="handleChangeLabelList">
              <el-option v-for="item in options4" :key="item.id" :label="item.test_type_cname" :value="item.test_type_ename"></el-option>
            </el-select>
          </el-form-item>
          <div v-if="algorithmPeopleCountVisible" class="algorithm-people-counts" style="font-size: 12px;line-height: 20px;">
            <el-form-item label="人数统计版本">
                  <el-select v-model="algorithmCountingScene" @change="changeAlgorithmCountingScene" aria-label="人数统计版本">
                    <el-option label="唯一性检测装置" value="uniqueness"></el-option>
                    <el-option label="乘车点" value="boarding"></el-option>
                  </el-select>
                </el-form-item>
                <el-form-item v-if="algorithmCountingBoarding" label="驻留确认帧数">
                  <el-input-number v-model="algorithmCountingResidenceFrames" :min="1" :max="120" :step="1" :precision="0" @change="_algorithmOperationalEdited = true" aria-label="驻留确认帧数"></el-input-number>
                  <div style="color: #78869a;font-size: 12px;">连续处于区域另一侧达到此帧数后确认，避免边界抖动。</div>
                </el-form-item>
                <el-form-item :label="algorithmCountingEnteringLabel">
              <el-input :value="algorithmPeopleEnteringDisplay" readonly :aria-label="algorithmCountingEnteringLabel" style="width: 50%;"></el-input>
            </el-form-item>
            <el-form-item :label="algorithmCountingExitingLabel">
              <el-input :value="algorithmPeopleExitingDisplay" readonly :aria-label="algorithmCountingExitingLabel" style="width: 50%;"></el-input>
            </el-form-item>
            <div role="status" style="color: #78869a;">{{ algorithmPeopleCountHint }}</div>
          </div>
          <el-form-item label="模型类型" style="margin-top: 16px;" v-if="algorithmTemplateAdministrator">
            <el-cascader style="width: 50%" v-model="form.model_template_config_id" :options="modelOptions" :props="modelProps" clearable ></el-cascader>
          </el-form-item>
          <el-form-item label="模型小类" style="margin-top: 16px;" v-if="algorithmTemplateAdministrator">
            <el-select v-model="form.template_small_id" placeholder="请选择模型小类" clearable filterable style="width: 50%" @change="onAlgorithmTemplateSmallChange">
              <el-option v-for="item in modelSmallOption" :key="item.id" :label="item.template_small_name" :value="item.id"> </el-option>
            </el-select>
          </el-form-item>
          <div class="algorithm-template-parameters" style="width: 90%;height: auto;margin-left: 32px;padding-bottom: 12px;">
            <div v-if="algorithmTemplateAdministrator" style="display: flex;flex-wrap: wrap;gap: 8px;margin: 8px 0;">
              <el-button type="success" icon="el-icon-plus" @click="addItem" size="mini">新增参数</el-button>
              <el-button icon="el-icon-refresh" @click="completeAlgorithmTemplateParameters" :loading="algorithmTemplateLoading" :disabled="!form.template_small_id" size="mini" style="margin-left: 0;">补齐模板参数</el-button>
            </div>
            <div v-if="algorithmTemplateError" role="alert" style="color: #c45656;font-size: 12px;line-height: 20px;">{{ algorithmTemplateError }}</div>
            <div v-for="(item, index) in form.template_data" :key="index" class="form-group" v-show="!isAlgorithmPeopleCountParameter(item.key)">
              <span slot="label" style="display:inline-block;width: 20px;">
                <el-tooltip effect="dark" :content="item.msg" placement="bottom" v-if="item.msg">
                  <i class='el-icon-question' />
                </el-tooltip>
              </span>
              <el-input v-model="item.key" placeholder="请输入键名" v-if="algorithmTemplateAdministrator" size="mini" :disabled="!algorithmTemplateAdministrator" style="width: 15%;margin-right: 10px;margin-top: 10px;"></el-input>
              <el-input v-model="item.key" placeholder="请输入键名" v-else size="mini" :disabled="model_template_config_id_num != 2" style="width: 15%;margin-right: 10px;margin-top: 10px;"></el-input>
              <el-input v-model="item.value" placeholder="请输入值" v-if="algorithmTemplateAdministrator" size="mini" :disabled="!algorithmTemplateAdministrator" style="width: 39%;margin-right: 10px;margin-top: 10px;"></el-input>
              <el-input v-model="item.value" placeholder="请输入值" v-else size="mini" :disabled="model_template_config_id_num != 2" style="width: 39%;margin-right: 10px;margin-top: 10px;"></el-input>
              <el-button type="danger" icon="el-icon-delete" @click="removeItem(index)" size="mini" style="margin-right: 10px;margin-top: 10px;"  v-if="algorithmTemplateAdministrator">删除</el-button>
            </div>
          </div>
        </div>
        <el-form-item label="扩增比例参数" style="margin-top: 16px;" prop="amp" v-show="model_template_config_id_num == 5">
          <el-input-number v-model="form.amp" controls-position="right" :min="1" :max="100" style="width: 50%;float: left;"></el-input-number>
        </el-form-item>
        <el-form-item label="图像类型" style="margin-top: 16px;" prop="alg_select_type" v-show="model_template_config_id_num == 5">
          <el-radio-group v-model="form.alg_select_type">
            <el-radio :label="'1'">裁剪</el-radio>
            <el-radio :label="'2'">屏蔽</el-radio>
            <el-radio :label="'3'">原图</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="级联解析类型" style="margin-top: 16px;" prop="model_two_type" v-if="model_template_config_id_num == 5">
          <el-select v-model="form.model_two_type" placeholder="请选择级联解析类型" size="mini" clearable filterable style="width: 50%">
            <el-option v-for="item in dict.algorithm_list_five" :key="'级联解析类型'+item.id" :label="item.algorithm_name" :value="item.id"></el-option>
          </el-select>
        </el-form-item>
        <!-- <div style="width: 100%;border: 1px dashed #e5e5e5;background: #f9fafb;border-radius: 10px;" v-if="form.model_two_type != ''">
          <el-form-item label="检测类型" style="margin-top: 16px;">
            <el-select v-model="label_list" placeholder="请选择检测类型" size="mini" clearable filterable multiple style="width: 50%">
              <el-option v-for="item in options4" :key="item.id" :label="item.test_type_cname" :value="item.test_type_ename"></el-option>
            </el-select>
          </el-form-item>
          <el-form-item prop="confidence">
            <span slot="label" style="display:inline-block;">
              置信度
              <el-tooltip effect="dark" content="触发报警阈值，值越小越容易触发报警。取值范围：（1-100）" placement="bottom">
                <i class='el-icon-question' />
              </el-tooltip>
            </span>
            <el-input style="width: 50%" v-model.number="confidence" placeholder="请输入置信度" maxlength="4"></el-input>
          </el-form-item>
        </div> -->
        <el-form-item label="报警等级" style="margin-top: 16px;" prop="res_type">
          <el-select v-model="form.res_type" placeholder="请选择报警等级" size="mini" clearable filterable style="width: 50%" @change="markAlgorithmAlarmEdited">
            <el-option v-for="item in alarmTypeDictOptions" :key="'报警等级'+item.value" :label="item.label" :value="item.value"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="算力资源" prop="resource_id">
          <el-cascader style="width: 50%" v-model="form.resource_id" :options="computeOptions" :props="computeProps" :show-all-levels="false" clearable @change="markAlgorithmResourceEdited"></el-cascader>
              <div class="algorithm-resource-status" role="status" aria-live="polite">{{ algorithmAdmissionHint }}</div>
        </el-form-item>
        <div class="algorithm-drawing-scroll" style="width: 100%;height: 590px;border: 1px dashed #e5e5e5;background: #f9fafb;border-radius: 10px;" v-if="type_qy">
          <div style="width: 100%;height: 400px;">
            <div style="width: 120px;height: 30px;border: 2px solid #5b65eb; text-align: center;color: #5b65eb;background: #ddefff;display:flex;align-items:center;justify-content:center;font-size: 0.8vw;margin: 12px 0 0 12px;float: left;">
              绘制检测区域
            </div>
            <div style="width: 640px;height: 419px; float: left;margin: 12px 0 0 12px">
              <div class="Bcanvas" v-loading="loading">
                <div class="jia_div" v-if="!imgOpen">{{ algorithmSnapshotHint }}</div>
                <img :src="imgurl" alt="" style="width: 640px; height: 360px" v-if="imgOpen" @load="loading = false" />
                <canvas id="mycanvas" ref="mycanvas" tabindex="0" v-if="isTypeTFS"></canvas>
                <div class="jia_div" v-if="shield_status == 1||image_draw_type == 2"></div>
              </div>
              <div v-if="algorithmPeopleCountVisible" class="algorithm-counting-tools" style="display: flex;flex-wrap: wrap;gap: 8px;align-items: center;padding: 6px 0;">
                  <el-button type="text" @click="handleimg(1)" icon="el-icon-refresh">刷新图片</el-button>
                  <el-button type="text" @click="startAlgorithmCountingDrawing" icon="el-icon-edit">{{ algorithmCountingPoints.length ? '重新绘制' : '开始绘制' }}{{ algorithmCountingBoarding ? '区域' : '计数线' }}</el-button>
                  <el-button type="text" @click="undoAlgorithmCountingPoint" :disabled="!algorithmCountingPoints.length">撤销顶点</el-button>
                  <el-button type="text" @click="finishAlgorithmCountingDrawing" :disabled="!algorithmCountingDrawing">完成绘制</el-button>
                  <el-button v-if="!algorithmCountingBoarding" type="text" @click="reverseAlgorithmCountingDirection" :disabled="algorithmCountingPoints.length < 2">切换进出方向</el-button>
                  <div role="status" style="width: 100%;font-size: 12px;line-height: 1.6;color: #78869a;">{{ algorithmCountingGeometryHint }}</div>
                  <div v-if="algorithmCountingGeometryError" role="alert" style="color: #c45656;font-size: 12px;">{{ algorithmCountingGeometryError }}</div>
                </div>
                <div class="canvasBtn" v-if="isTypeTFS && !algorithmPeopleCountVisible">
                <el-button type="text" @click="handleimg(1)" icon="el-icon-refresh">刷新</el-button>
                <el-button type="text" @click="handleDrewAgain" icon="el-icon-edit">重新绘制</el-button>
                <el-button type="text" @click="resole" icon="el-icon-refresh-left">撤销</el-button>
              </div>
            </div>
          </div>
          <div style="width: 100%;height: 180px;">
            <div style="width: 38%;height: 100%;float: left;margin-left: 15%;">
              <el-form-item style="padding-top: 16px;" prop="confidence">
                <span slot="label" style="display:inline-block;">
                  置信度
                  <el-tooltip effect="dark" content="触发报警阈值，值越小越容易触发报警。取值范围：（1-100）" placement="bottom">
                    <i class='el-icon-question' />
                  </el-tooltip>
                </span>
                <el-input style="width: 100%" v-model.number="form.confidence" placeholder="请输入置信度" maxlength="4"></el-input>
              </el-form-item>
              <el-form-item prop="sensitivity" v-if="isTypeTFS">
                <span slot="label" style="display:inline-block;">
                  间隔帧
                  <el-tooltip effect="dark" content="视频流检测频率，如设置为25，1s检测一次。取值范围：（1-100）" placement="bottom">
                    <i class='el-icon-question' />
                  </el-tooltip>
                </span>
                <el-input style="width: 100%" :disabled="indexnum != 0" v-model.number="form.sensitivity" placeholder="请输入间隔帧" maxlength="4"></el-input>
              </el-form-item>
            </div>
            <div style="width: 38%;height: 100%;float: left;" v-if="isTypeTFS">
              <el-form-item style="padding-top: 16px;" prop="duration_time">
                <span slot="label" style="display:inline-block;">
                  持续时长
                  <el-tooltip effect="dark" content="需求行为的持续时长。取值范围：（1-100）" placement="bottom">
                    <i class='el-icon-question' />
                  </el-tooltip>
                </span>
                <el-input style="width: 100%" v-model.number="form.duration_time" placeholder="请输入持续时长" maxlength="4">
                  <template slot="append">秒</template>
                </el-input>
              </el-form-item>
              <el-form-item prop="interval_time"  v-if="isTypeTFS">
                <span slot="label" style="display:inline-block;">
                  告警间隔
                  <el-tooltip effect="dark" content="当满足触发报警条件达到一定间隔时长以后才会上报。取值范围：（1-3600秒）" placement="bottom">
                    <i class='el-icon-question' />
                  </el-tooltip>
                </span>
                <el-input style="width: 100%" v-model.number="form.interval_time" placeholder="请输入告警间隔" maxlength="4">
                  <template slot="append">秒</template>
                </el-input>
              </el-form-item>
              <el-form-item label="开始时间" prop="defense_time_start" v-if="isTypeTFS">
                <el-time-picker :disabled="indexnum != 0" v-model="form.defense_time_start" style="width: 100%" value-format="HH:mm:ss" :picker-options="{selectableRange: '00:00:00 - 23:59:59'}" placeholder="任意时间点" :default-value="new Date().setHours(0, 0, 0, 0)">
                </el-time-picker>
              </el-form-item>
              <el-form-item label="结束时间" prop="defense_time_end">
                <el-time-picker :disabled="indexnum != 0" v-model="form.defense_time_end" value-format="HH:mm:ss" style="width: 100%" :picker-options="{selectableRange: '00:00:00 - 23:59:59'}" placeholder="任意时间点" :default-value="new Date().setHours(0, 0, 0, 0)">
                </el-time-picker>
              </el-form-item>
            </div>
          </div>
        </div>
        <el-form-item label="任务说明" style="margin-top: 16px;">
          <el-input v-model="form.Algorithm_config_ps" placeholder="请输入备注" type="textarea" style="width: 50%;float: left;"></el-input>
        </el-form-item>
        <!-- <el-button type="primary" @click="sub_fn">保存</el-button> -->
      </el-form>
    </div>

    <!-- 区域 -->
    <el-dialog :title="title2" id="alarmTypeBox" :visible.sync="dialogVisible2" width="500px" @close="handleClose2" :close-on-click-modal="false">
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
        <el-radio :label="selectedOption_type" class="grid-item">{{selectedOption_type}}</el-radio>
      </el-radio-group>
      <span slot="footer" class="dialog-footer">
        <el-button @click="dialogVisible2 = false;handleDeleteList()">取 消</el-button>
        <el-button type="primary" @click="handleUpdateList()">确 定</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import store from "../store";
import algorithmStreamMixin from './algorithmStreamMixin';
import { draw_test } from "../relevantjs/draw_shape";
import { draw_test2 } from "../relevantjs/draw_shape2";
import { draw_test3 } from "../relevantjs/draw_shape3";
import { draw_test4 } from "../relevantjs/draw_shape4";//用于标线
import { compute, findModelName } from "../api/sfgl";

import { modelApi } from '@/api/model/index';
import algorithmTemplateParameters from './algorithmTemplateParameters';
import algorithmPeopleCounts from './algorithmPeopleCounts';
import algorithmCountingScene from './algorithmCountingScene';
export default {
  mixins: [window.PlatformAlgorithmTemplateAdministrator, algorithmStreamMixin, algorithmTemplateParameters, algorithmPeopleCounts, algorithmCountingScene],
  components: {
    
  },
  name: "sfgl_child",
  props: ['item','conf_id','indexnum','types','configStreamType'],
  watch: {
    configStreamType: {
      immediate: true,
      handler(value) {
        if (!this.form) return;
        var streamType = value === 'main' || value === 'sub' ? value : null;
        if (this.form.stream_type !== streamType) this._algorithmSourceEdited = true;
        this._algorithmDefaultStreamPending = false;
        this.$set(this.form, 'stream_type', streamType);
      },
    },
    // item: {
    //   handler(newVal) {
    //   this.jclxslist = [];
    //   // this.handleChangeCanvas2();
    //   // this.updateConfName();
    //   this.handleChangeSf(newVal.Algorithm_library_id);
    //   // this.getCompute();//获取资源信息
    //   },
    //   deep: true
    // }
    // 'form.algorithm_name': function () {
    //   alert(3)
    //   this.handleChangeCanvas2();
    //   this.updateConfName();
    //   console.log(this.form.Algorithm_library_id)
    //   alert(2)
    //   this.handleChangeSf(this.form.Algorithm_library_id);
    //   this.getCompute();//获取资源信息
    // },
  },
  data() {
    return {
      form: this.item,
      // form.Algorithm_library_id:'',
      jclxslist:[],
      isTypeTFS:true,
      selectedOption_type:'',
      dict:{
        equipment_list:[],
      },
      type_jx:false,
      type_qy:false,
      system: window.wgParameter.system,
      version: store.state.version,
      url_5000: this.$url.url_5000,
      StartTime: "",
      EndTime: "",
      model_two_type:'',
      label_list:[],
      confidence:'60',
      model_path:'',
      selectedOption_model: '类型一',
      title2_model: '',
      dialogVisible2_model: false,
      title2: "",
      selectedOption: '报警',
      dialogVisible2: false,

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
      modelOptions:[],
      modelSmallOption:[],
      computeOptions: [],//算力资源信息字典
      computeProps: {
        checkStrictly: false,
        emitPath: false,
        value: "id",
        label: "label",
      },
      timesX: 3,
      timesY: 3,
      options1: [],
      options2: [],
      options3: [],
      options4: [],
      resolution: '',
      resolutionOption: [
        { value: '1920x1080', name: '普通' },
        { value: '2688x1520', name: '热成像' },
        { value: '2560x1440', name: '热成像' },
        { value: '1280x720', name: '热成像' },
        { value: '720x576', name: '热成像2' }
      ],
      
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
      usertype:'',
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
      selectedOption_type_s:'',
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
      rules:{
        amp: [
          { required: true, message: '扩增比例参数(0-100)', trigger: 'blur' },
        ],
        model_two_type: [
          { required: true, message: '请选择级联解析类型', trigger: 'change' },
        ],
        conf_name: [
          { required: true, message: '请输入任务名称', trigger: 'blur' },
        ],
        Mine_id: [
          { required: true, message: '请选择单位名称', trigger: 'change' },
        ],
        equipment_name: [
          { required: true, message: '请选择报警设备', trigger: 'change' },
        ],
        Algorithm_library_id: [
          { required: true, message: '请选择解析类型', trigger: 'change' },
        ],
        res_type: [
          { required: true, message: '请选择报警等级', trigger: 'change' },
        ],
        resource_id: [
          { required: true, message: '请选择算力资源', trigger: 'change' },
        ],
        confidence: [
          { required: true, message: '请输入置信度', trigger: 'blur' },
          {
          validator: (rule, value, callback) => {
            if (value < 1 || value > 100) {
              callback(new Error('数字必须在1到100之间'));
            } else {
              callback();
            }
          },
          trigger: 'blur'
        }
        ],
        sensitivity: [
          { required: true, message: '请输入间隔帧', trigger: 'blur' },
          {
          validator: (rule, value, callback) => {
            if (value < 1 || value > 100) {
              callback(new Error('数字必须在1到100之间'));
            } else {
              callback();
            }
          },
          trigger: 'blur'
        }
        ],
        defense_time_start: [
          { required: true, message: '请选择开始时间', trigger: 'change' },
        ],
        defense_time_end: [
          { required: true, message: '请选择结束时间', trigger: 'change' },
        ],
        duration_time: [
          { required: true, message: '请输入持续时长', trigger: 'blur' },
          {
          validator: (rule, value, callback) => {
            if (value < 1 || value > 100) {
              callback(new Error('数字必须在1到100之间'));
            } else {
              callback();
            }
          },
          trigger: 'blur'
        }
        ],
        interval_time: [
          { required: true, message: '请输入告警间隔', trigger: 'blur' },
          {
          validator: (rule, value, callback) => {
            if (!Number.isInteger(Number(value)) || value < 1 || value > 3600) {
              callback(new Error('告警间隔必须为1到3600秒的整数'));
            } else {
              callback();
            }
          },
          trigger: 'blur'
        }
        ],
      }
    };
  },
  // watch:{
  //     form(val){
  //       this.updateItem()
  //     },
  // },
  computed: {
    
  },
  created() {
    if(localStorage.getItem('user_role_id')){
      this.usertype = localStorage.getItem('user_role_id')
    }
    this.form.Algorithm_library_id = this.form.Algorithm_library_id
    this.jclxslist = this.form.label_list
    this.handleChangeCanvas2();
    this.updateConfName();
    this.handleChangeSf(this.form.Algorithm_library_id);
    this.getCompute();//获取资源信息
  },
  mounted() {
    this.init()
      // setTimeout(()=>{
      //   this.handleimg(1)
      // },1000)
  },
  beforeDestroy() {
    
  },
  destroyed() {
    
  },
  methods: {
    clearss(e){
      this.jclxslist = [];
      return this.handleChangeSf(e, true);
    },
    updateItem(event) {
      this.$emit('update:item', event.target.value); // 发送更新事件到父组件
    },
    goback(){
      this.$router.push({
        path: '/sfgl',
      })
    },
    timeToTimestamp(time) {
        const [hours, minutes, seconds] = time.split(':').map(Number);
        return hours * 3600 + minutes * 60 + seconds;
    },
    sub_fn() {
      if (!this.validateAlgorithmTemplateParameters()) return Promise.resolve(false);
      if (!this.validateAlgorithmCountingGeometry()) return Promise.resolve(false);
      const validationSourceKey = this.streamSourceKey;
      const validationAlgorithmId = this.form.Algorithm_library_id;
      return new Promise((resolve, reject) => {
      this.$refs['form'].validate((valid) => {
        try {
          if (this._algorithmFormClosed || validationSourceKey !== this.streamSourceKey || validationAlgorithmId !== this.form.Algorithm_library_id) { resolve(false); return; }
          if (valid) {
            // 判断开始结束时间时间
            const timestamp1 = this.timeToTimestamp(this.form.defense_time_start);
            const timestamp2 = this.timeToTimestamp(this.form.defense_time_end);
            if (timestamp1 > timestamp2) {
              this.$message({
                      message: '结束时间不能小于开始时间，请重新选择结束时间!',
                      type: "warning",
                    });
                this.form.defense_time_end = '23:59:59';
                resolve(false);
                return;
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
            // 只有模型类型选择为4，深度适配类的时候才需要主动去赋值的情况，其他情况自己选值
            if (this.model_template_config_id_num == 4) {
              this.form.test_type_id = this.options4[0].id
              this.jclxslist = [this.options4[0].test_type_ename]
            }
            // 逆向寻找设备ID
            const resource = this.resolveAlgorithmResource(this.form.resource_id);
            if (!resource) { this.$message({ type: 'warning', message: '请选择有效的计算资源卡' }); resolve(false); return; }
            const computing_id = resource.computingId;
            this.$set(this.form, 'resource_id', resource.resourceId);
            // 取出小类详情信息template_data
            let template_data = JSON.stringify(this.getModelSmallDetail())
          
            let model_template_type_id
            this.modelOptions.forEach(item => {
              item.children.forEach(v => {
                if (v.id == this.form.model_template_config_id) {
                  model_template_type_id = item.id
                }
              })
            })
            const all_type_list = [];
            this.options4.forEach((item)=>{
              all_type_list.push(item.test_type_ename)
            })
            let strs = '';
            if(this.dict.algorithm_list_five.length != 0){
              strs = this.dict.algorithm_list_five[0].algorithm_path
            }
            // 新增
            var forms = {
              conf_name: this.form.conf_name,
              Algorithm_library_id: this.form.Algorithm_library_id,
              Mine_id: this.form.Mine_id,
              Equipment_id: this.form.equipment_name,
              stream_type: this.streamTypeRequest(),
              // conf_object: "",
              conf_area: !this.algorithmPeopleCountVisible && this.drawLineOpen ? this.mark_lists3 : this.mark_lists,
              cross_line_area: this.algorithmPeopleCountVisible ? JSON.stringify(this.algorithmCountingPayload()) : this.form.cross_line_area,
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.jclxslist),
              shield_status: this.shield_status,
              tem_frames: this.form.tem_frames,
              confidence: this.form.confidence,
              tem_conf_area: this.mark_lists2,
              draw_type: this.algorithmPeopleCountVisible ? '1' : this.drawLineOpen ? '2' : '1',
              img_resolution: this.resolution,
              duration_time: this.form.duration_time,
              interval_time: this.form.interval_time,
              image_draw_type: this.image_draw_type,
              Algorithm_config_ps: this.form.Algorithm_config_ps,
              scene_typename: this.form.scene_typename,
              sensitivity: this.form.sensitivity,
              resource_id: this.form.resource_id,
              computing_id: computing_id,
              resource_id_old: this.form.resource_id_old,
              defense_time_start: this.form.defense_time_start,
              defense_time_end: this.form.defense_time_end,
              model_template_config_id: this.form.model_template_config_id,
              model_template_type_id: model_template_type_id,
              template_list_area: this.mark_lists_model,
              template_small_id: this.form.template_small_id,
              res_type: this.form.res_type,
              run_time: this.form.run_time,
              priority: this.form.priority,
              template_data: template_data,
              model_two_data: JSON.stringify([{
                label_list:this.label_list,
                confidence:this.confidence,
                model_path: strs,
                algorithm_type_list: all_type_list
              }]),
              amp: this.form.amp,
              alg_select_type: this.form.alg_select_type,
              model_two_type: this.form.model_two_type,
            };
            // 修改(修改的时候list标注数据记得处理)
            let forms2 = {
              id: this.form.id,
              conf_name: this.form.conf_name,
              Algorithm_library_id: this.form.Algorithm_library_id,
              Mine_id: this.form.Mine_id,
              Equipment_id: this.form.equipment_name,
              stream_type: this.streamTypeRequest(),
              // conf_object: "",
              conf_area: !this.algorithmPeopleCountVisible && this.drawLineOpen ? JSON.stringify(this.mark_lists3) : JSON.stringify(this.mark_lists),
              cross_line_area: this.algorithmPeopleCountVisible ? JSON.stringify(this.algorithmCountingPayload()) : this.form.cross_line_area,
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.jclxslist),
              shield_status: this.shield_status,
              tem_frames: this.form.tem_frames,
              confidence: this.form.confidence,
              tem_conf_area: JSON.stringify(this.mark_lists2),
              draw_type: this.algorithmPeopleCountVisible ? '1' : this.drawLineOpen ? '2' : '1',
              img_resolution: this.resolution,
              duration_time: this.form.duration_time,
              interval_time: this.form.interval_time,
              image_draw_type: this.image_draw_type,
              Algorithm_config_ps: this.form.Algorithm_config_ps,
              scene_typename: this.form.scene_typename,
              sensitivity: this.form.sensitivity,
              resource_id: this.form.resource_id,
              computing_id: computing_id,
              resource_id_old: this.form.resource_id_old,
              defense_time_start: this.form.defense_time_start,
              defense_time_end: this.form.defense_time_end,
              model_template_config_id: this.form.model_template_config_id,
              model_template_type_id: model_template_type_id,
              template_list_area: JSON.stringify(this.mark_lists_model),
              template_small_id: this.form.template_small_id,
              res_type: this.form.res_type,
              template_data: template_data,
              run_time: this.form.run_time,
              priority: this.form.priority,
              model_two_data: JSON.stringify([{
                label_list:this.label_list,
                confidence:this.confidence,
                model_path: strs,
                algorithm_type_list: all_type_list
              }]),
              amp: this.form.amp,
              alg_select_type: this.form.alg_select_type,
              model_two_type: this.form.model_two_type,
            };
            if(this.conf_id){
              this.item.model_template_type_id = this.form.model_template_config_id
              this.item.conf_area= forms2.conf_area
              this.item.cross_line_area = forms2.cross_line_area;
              if (this.algorithmPeopleCountVisible) this.item.draw_type = '1';
              this.item.img_resolution = forms2.img_resolution
              this.item.stream_type = this.form.stream_type;
              this.item.computing_id = forms2.computing_id
              this.item.shield_status = forms2.shield_status
              this.item.label_list = forms2.label_list
              
              this.item.confidence = forms2.confidence
              this.item.sensitivity = forms2.sensitivity
              this.item.defense_time_start = forms2.defense_time_start
              this.item.defense_time_end = forms2.defense_time_end
              this.item.duration_time = forms2.duration_time
              this.item.interval_time = forms2.interval_time
              this.item.Algorithm_config_ps = forms2.Algorithm_config_ps
              
              this.item.model_template_config_id = forms2.model_template_config_id
              this.item.template_small_id = forms2.template_small_id
              this.item.template_data = forms2.template_data
              this.item.amp = forms2.amp
              this.item.model_two_type = forms2.model_two_type
              this.item.res_type = forms2.res_type
              this.item.resource_id = forms2.resource_id
              
            }else{
              this.item.model_template_type_id = this.form.model_template_config_id
              this.item.conf_area= forms.conf_area
              this.item.cross_line_area = forms.cross_line_area;
              if (this.algorithmPeopleCountVisible) this.item.draw_type = '1';
              this.item.img_resolution = forms.img_resolution
              this.item.stream_type = this.form.stream_type;
              this.item.computing_id = forms.computing_id
              this.item.shield_status = forms.shield_status
              this.item.label_list = forms.label_list
              
              this.item.confidence = forms.confidence
              this.item.sensitivity = forms.sensitivity
              this.item.defense_time_start = forms.defense_time_start
              this.item.defense_time_end = forms.defense_time_end
              this.item.duration_time = forms.duration_time
              this.item.interval_time = forms.interval_time
              this.item.Algorithm_config_ps = forms.Algorithm_config_ps
              
              this.item.model_template_config_id = forms.model_template_config_id
              this.item.template_small_id = forms.template_small_id
              this.item.template_data = forms.template_data
              this.item.amp = forms.amp
              this.item.model_two_type = forms.model_two_type
              this.item.res_type = forms.res_type
              this.item.resource_id = forms.resource_id
            }
             this.removeAlgorithmPeopleCountFields(this.item);
             resolve(true);
          } else {
            resolve(false);
          }
        } catch (error) { reject(error); }
        });
      });
    },
    // 获取小类详情的数据
    getModelSmallDetail() {
      return this.algorithmTemplatePayload();
    },
    // 提交数据处理
    handleData() {
      if (this.mark_list.length != 0 && (!this.drawLineOpen || this.algorithmPeopleCountVisible)) {
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
    countfns(){
      if(this.form.equipment_name != '' && this.form.equipment_name != null && this.form.equipment_name != undefined){
        if(this.form.Algorithm_library_id != '' && this.form.Algorithm_library_id != null && this.form.Algorithm_library_id != undefined){
          this.dict.algorithm_list.forEach((item)=>{
            console.log(item)
            if(item.id == this.form.Algorithm_library_id){
              if(item.algorithm_name == '探放水'){
                this.isTypeTFS = false;
              }else{
                this.isTypeTFS = true;
              }
            }
          })
          this.handleChangeCanvas2();
          this.updateConfName();
          this.handleChangeSf(this.form.Algorithm_library_id);
          this.type_jx=true;
          this.type_qy=true;
        }else{
          this.type_jx = false;
          this.type_qy = false;
        }
      }else{
        this.form.Algorithm_library_id = '';
        this.$message({
          message: '请选择报警设备!',
          type: "warning",
        });
      }
    },
    handleClose2() {
      this.dialogVisible2 = false;
      this.handleUpdateList();
    },
    handleDeleteList() {
      this.coordinates = [];
      this.coordinates2 = [];
      this.coordinates3 = [];//清除当前标注数据
      // 由于鼠标双击的时候，数据已经被提交，所以要从根源上删除该数据
      this.mark_list.pop()
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
    // 删除一个小类详情
    removeItem(index) {
      this.removeAlgorithmTemplateParameter(index);
    },
    // 新增一个小类详情
    addItem() {
      this.addAlgorithmTemplateParameter();
    },
    handleChangeSf(id, userSelected = false) {
      const generation = ++this._algorithmModelGeneration;
      const form = this.form;
      const modelBefore = form.model_template_config_id, smallBefore = form.template_small_id;
      if (userSelected) { this._algorithmModelWasSelected = true; this._algorithmScrollPending = true; this._algorithmDetectionEdited = false; this._algorithmSelectedModelId = String(id); }
      const current = () => !this._algorithmFormClosed && generation === this._algorithmModelGeneration && form === this.form && String(id) === String(this.form.Algorithm_library_id);
      return this.$http
        .get(this.$url.url_5000 + "/model_view/Algorithm_type_select", {
          params: {
            id,
            // id: 1,
          },
        })
        .then(async (response) => {
          if (!current()) return;
          const data = response.data.data || {};
          const model = (data.model_data || [])[0];
          const type = (data.model_type_data || [])[0];
          const small = (data.template_small_data || [])[0];
          this.options4 = data.algorithm_data || [];
          this.selectedOption = data.show_status;
          this.selectedOption_type_s = data.show_status;
          const selectedByUser = userSelected || this._algorithmSelectedModelId === String(id);
          const useDefaults = selectedByUser || !this.algorithmIsEditing();
          if (useDefaults && model && this.form.model_template_config_id === modelBefore) this.$set(this.form, 'model_template_config_id', model.id);
          const smallOptions = type ? this.getModelSmallDict2(type.id, current) : Promise.resolve();
          let details = Promise.resolve();
          if (useDefaults && small && this.form.template_small_id === smallBefore) {
            this.$set(this.form, 'template_small_id', small.id);
            details = this.handleChangeTemplateSmall(current, true);
          } else if (!useDefaults && this.form.template_small_id) {
            details = this.handleChangeTemplateSmall(current);
          }
          this.applyAlgorithmDefaults(this.options4, selectedByUser);
          await Promise.all([smallOptions, details, this._algorithmComputePromise]);
          if (current()) { this._algorithmSelectedModelId = null; this.scrollToAlgorithmSave(); }
        })
        .catch((rek) => {
          console.log(rek);
        });
    },
    //选择小类，查询相关配置详情
    handleChangeTemplateSmall(isCurrent, replace = false) {
      return this.loadAlgorithmTemplateParameters(modelApi.getModelSmallDetail, isCurrent, replace);
    },
    getModelSmallDict2(id, isCurrent) {
      this.model_template_config_id_num = id
      return this.$http.get(modelApi.getModelSmallList, {
        params: {
          page: 1,
          per_page: 15,
          model_template_type_id: id,
        }
      }).then(response => {
        if (this._algorithmFormClosed || typeof isCurrent === 'function' && !isCurrent()) return;
        this.modelSmallOption = response.data.data.data;
        // console.log("===================",this.modelSmallOption)
      }).catch(rek => {
        console.log(rek)
      })
    },
    // 当遮挡配置选择为遮挡的时候，清空标注区域。
    handleChangeShield_status() {
      this.handleDrewAgain();
    },
    // 热成像区域相关
    async handleChangeCanvas2(data) {
      var info = await this.loadStreamCapabilities(data || this.algorithmEquipmentId());
      if (!info || this._algorithmFormClosed) return false;
      this.area2 = String(info.data && info.data.equipment_code) === '201';
      return this.handleimg();
    },
    // 通过选中的分辨率，来计算渲染比值timesX和timesY
    handleTimesData(resolution) {
      var parts = String(resolution || '').split('x');
      var width = Number(parts[0]), height = Number(parts[1]);
      if (parts.length !== 2 || !Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return false;
      this.timesX = width / 640;
      this.timesY = height / 360;
      return true;
    },
    
    handleimg(num) { return this.requestAlgorithmImage(num); },
    
    /* 画布初始化 */
    initCanvas() {
      if (this.algorithmPeopleCountVisible) return this.initAlgorithmCountingCanvas();
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
        var list = this.mark_list; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
        var coordinates = this.coordinates
        // 若list长度不为0, 则显示已标记框
        let this_ = this
        draw_test(cav, list, this.handleChooseType, coordinates);
      });
    },
    // 区域标注类型选择
    handleChooseType() {
      if(this.selectedOption_type_s == '空区域'){
        this.selectedOption = '告警区域'
        this.handleUpdateList()
      }else if(this.selectedOption_type_s == '屏蔽区域'){
        this.title2 = '区域标注类型选择'
        this.selectedOption_type = '屏蔽区域'
        this.dialogVisible2 = true
      }else if(this.selectedOption_type_s == '检测区域'){
        this.title2 = '区域标注类型选择'
        this.selectedOption_type = '检测区域'
        this.dialogVisible2 = true
      }else{
        this.selectedOption = '告警区域'
        this.title2 = '区域标注类型选择'
        this.dialogVisible2 = true
        this.handleUpdateList()
      }
    },
    // 类型标注类型选择
    handleChooseType_model() {
      this.selectedOption_model = '类型一'
      this.title2_model = '模型类型选择'
      this.dialogVisible2_model = true
    },
    initCanvas_model() {
      // this.$nextTick(() => {
      //   // 初始化canvas宽高
      //   let cav = this.$refs.mycanvas_model;
      //   cav.width = "640";
      //   cav.height = "360";
      //   let ctx = cav.getContext("2d");
      //   ctx.strokeStyle = "red";
      //   cav.style.cursor = "crosshair";
      //   // 计算使用变量
      //   // this.mark_list = []
      //   let list = this.mark_list_model; // 画框数据集合, 用于服务端返回的数据显示和绘制的矩形保存
      //   let coordinates = this.coordinates_model
      //   // 若list长度不为0, 则显示已标记框
      //   let this_ = this
      //   draw_test(cav, list, this.handleChooseType_model, coordinates);
      // });
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
      if (this.algorithmPeopleCountVisible) return this.initAlgorithmCountingCanvas();
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
    tableCanvasMax(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10); // 将宽度转换为整数
      var HH = parseInt(parts[1], 10); // 将高度转换为整数
      this.$nextTick(() => {
        // 初始化canvas宽高
        let cav = this.$refs[`tableCanvas_tableMax`];
        cav.width = "800";
        cav.height = "400";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        // cav.style.cursor = "crosshair";
        let XX = WW / 800
        let YY = HH / 400
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
    handleChangeLabelList() {
      this.markAlgorithmDetectionEdited();
      this.$set(this.form, 'label_list', this.jclxslist.slice());
      if (this.jclxslist.length != 0) {
        const selected = this.options4.find(v => v.test_type_ename == this.jclxslist[0]);
        this.form.test_type_id = selected ? selected.id : '';
      } else {
        this.form.test_type_id = '';
      }
    },
    // 任务名称名字自动化获取
    updateConfName() {
      const { equipment_name, Algorithm_library_id } = this.form;
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
      // if (equipment_name && Algorithm_library_id) {
      //   this.form.conf_name = `${monitorPointName}-${algorithmName}`;
      //   // this.form.conf_name = `${monitorPointName}-${algorithmName}`;
      //   this.$http.post(findModelName, {
      //     conf_name: this.form.conf_name
      //   }).then(response => {
      //     if (response.data.code == 400) {
      //       this.modelNameOpen = true
      //       this.modelNamemsg = response.data.msg
      //     } else {
      //       this.modelNamemsg = response.data.msg
      //       this.modelNameOpen = false
      //     }
      //   }).catch(rek => {
      //     console.log(rek)
      //   })
      // } else {
      //   this.form.conf_name = '';
      // }
      // if(this.form.conf_name == '' || this.form.conf_name == null || this.form.conf_name == undefined){
      //   this.conf_name_note = '';
      //   this.conf_name_type = false;
      //   this.form.conf_name = '';
      // }else{
      //   this.conf_name_note = this.form.conf_name;
      //   this.conf_name_type = true;
      //   this.form.conf_name = '';
      // }
    },
    // 获取算力资源信息
    getCompute() {
      this._algorithmComputePromise = this.$http.get(compute)
        .then(response => {
          if (this._algorithmFormClosed) return;
          this.computeOptions = this.transformData(response.data.data);
          this.applyAlgorithmAdmission();
          this.applyAlgorithmResourceDefault();
        }).catch(() => {});
      return this._algorithmComputePromise;
    },
    generateRandomId() {
      return Math.random().toString(36).substr(2, 9); // 生成随机 ID
    },
    transformData(rawData) {
      return this.sortAlgorithmResources(rawData);
    },
    // 重绘
    handleDrewAgain() {
      if (this.algorithmPeopleCountVisible) return this.startAlgorithmCountingDrawing();
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
    // 撤销
    resole() {
      if (this.algorithmPeopleCountVisible) return this.undoAlgorithmCountingPoint();
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
    init(){//字典
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: '',
              type: 1
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          if (response.data.code === 200) {
            this.dict = response.data;
            this.options1 = response.data.mine_list;
            // this.form.Mine_id = response.data.mine_list[0].id
            this.options2 = response.data.equipment_list;
            this.options3 = response.data.algorithm_list;
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
            if(this.conf_id){
              this.type_jx = true;
              this.type_qy = true;
              if(this.item.conf_area != '[]' && !this._algorithmModelWasSelected){
                this.handlechange(this.conf_id,this.indexnum)
              }
            }else{
            // setTimeout(() => {
              this.countfns()
            // }, 1000);
            }
            // console.log(9527,this.modelOptions)
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    
    handlechange(data,id) {
      const requestedForm = this.form, requestedAlgorithmId = this.form.Algorithm_library_id;
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
            conf_id: data,
            data_id: id,
          },
        })
        .then((response) => {
          if (this._algorithmFormClosed || this._algorithmModelWasSelected || this.form !== requestedForm || this.form.Algorithm_library_id !== requestedAlgorithmId) return;
          if (response.data.code === 200) {
            this.title = "算法修改";
            this.form = response.data.datalist;
            this.restoreAlgorithmCountingGeometry(this.form.cross_line_area);
            this.restoreAlgorithmSource();
            this.$set(this.form, 'stream_type', this.configStreamType === 'main' || this.configStreamType === 'sub' ? this.configStreamType : null);
            this.form.model_two_type = response.data.datalist.model_two_type*1
            if(this.form.model_two_data.length){
              this.label_list = this.form.model_two_data[0].label_list;
              this.confidence = this.form.model_two_data[0].confidence;
              this.model_path = this.form.model_two_data[0].model_path;
            }
            console.log(this.form)
            // this.jclxslist = this.stringToArray(this.jclxslist)
            // console.log(12121212121212121, this.jclxslist)
            this.findModelBigDict(this.form.model_template_config_id)
            // this.handleChangeTemplateSmall()
            // if(this.form.template_data){
            //   this.form.template_data = this.form.template_data.reduce((acc, obj) => {
            //     if (Object.keys(obj).length > 0) {
            //       const key = Object.keys(obj)[0];
            //       acc.push({
            //         key: key,
            //         value: obj[key]
            //       });
            //     }
            //     return acc;
            //   }, []);
            // }
            this.form.template_data = this.normalizeAlgorithmTemplateRows(this.form.template_data);
            if (this.form.tem_frames == '') {
              this.form.tem_frames = '[27,37]'
            }
            if (this.form.confidence == null || this.form.confidence == '') {
              this.form.confidence = "60"
            }
            this.drawLineOpen = this.form.draw_type == '2' ? true : false
            this.image_draw_type = this.form.image_draw_type
            this.resolution = this.form.img_resolution
            this.form.resource_id_old = this.form.resource_id
            this.handleTimesData(this.resolution)
            // console.log(this.form);
            // console.log("147369", this.drawLineOpen, this.area2);
            // this.form.Mine_id = response.data.datalist.Mine_id;
            this.shield_status = Number(response.data.datalist.shield_status);
            this.dialogVisible = true;
            this.handleSelect();
            this.handleChangeSf(this.form.Algorithm_library_id);
            this.form.equipment_name = response.data.datalist.Equipment_id;

            this.handleimg();

            // 将list字符串转为可用数组
            if (this.form.draw_type == '2') {
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
            const editedSourceKey = this.streamSourceKey;
            this.loadStreamCapabilities(this.algorithmEquipmentId())
              .then((info) => {
                if (!info || this._algorithmFormClosed || editedSourceKey !== this.streamSourceKey) return;
                const response = { data: info };
                if (response.data.data.equipment_code == "201") {
                  this.area2 = true;
                  let arr2 = Array.isArray(tem_conf_area) ? tem_conf_area : tem_conf_area ? JSON.parse(String(tem_conf_area).replace(/'/g, '"')) : [];
                  const thermalPoints = Array.isArray(arr2) && Array.isArray(arr2[0]) ? arr2[0] : [];
                  let jia2 = [];
                  for (let i = 0; i < thermalPoints.length; i++) {
                    // let x = arr2[0][i].x / 3;
                    // let y = arr2[0][i].y / 3;
                    let x = thermalPoints[i].x / this.timesX;
                    let y = thermalPoints[i].y / this.timesY;
                    jia2.push({
                      x,
                      y,
                    });
                  }
                  this.mark_list2 = jia2.length ? [jia2] : []; // Empty thermal regions stay empty.
                  // 进行热成像区域的canvas加载
                  if (this.$refs.mycanvas2) this.initCanvas2();
                } else {
                  this.area2 = false;
                }
              });
            // this.handleChangeCanvas2(this.form.equipment_name);
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    
    handleSelect(a) {
      // let param = new URLSearchParams();
      // param.append("mine_id", this.mkname);
      if (a === 1) {
        this.form.equipment_name = "";
      }
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: this.form.Mine_id,
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
            // this.form.Mine_id = response.data.mine_list[0].id
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
    findModelBigDict(id) {
      this.modelOptions.forEach(item => {
        let res = item.children.find(v => v.id == id)
        if (res) {
          this.getModelSmallDict([item.model_id])
          return
        }
      })
    },
    extractNumberFromF(str) {
      const match = str.match(/^F(\d+)$/);
      return match ? parseInt(match[1], 10) : NaN;
    },
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
  },
};
</script>

<style lang="scss" scoped>
  .sfgl_child{
    width: 100%;
    height: 100%;
    background: #fff;
    overflow: hidden;
  }
  .sfpzs{
    width: 900px;
    height: 100%;
    overflow: hidden;
    margin: 0 auto;
  }
  .w-1\2{
    width: calc(50% - 12px) !important;
    margin-left: 12px !important;
    float: left;
  }
  .jia_div {
      width: 640px;
      height: 360px;
      text-align: center;
      color: red;
      display:flex;align-items:center;justify-content:center;
    }
      .Bcanvas {
        width: 100%;
        height: calc(100% - 50px);
        border: 1px solid #e5e5e5;
        box-sizing: border-box; -moz-box-sizing: border-box;
        /* margin-left: 100px;
        margin-top: 15px; */
      }
      .canvasBtn {
        /* margin-left: 100px; */
        width: 100%;
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
    #mycanvas {
      position: relative;
      top: -100%;
      left: 0;
      z-index: 10;
    }
  /* Only standalone model fields; fixed media and grouped detection fields retain their geometry. */
  .algorithm-config-model { height: auto; overflow: visible; }
  .algorithm-config-model .sfpzs { width: 100%; height: auto; margin: 0; overflow: visible; }
  .algorithm-config-model .sfpzs ::v-deep > .el-form > .el-form-item {
    max-width: 680px; margin: 0 auto 20px !important; padding-top: 0 !important;
    > .el-form-item__label { color: #42516a; font-size: 13px; line-height: 32px; padding-right: 16px; }
    > .el-form-item__content {
      line-height: 32px; min-width: 0;
      > .el-select, > .el-cascader, > .el-input, > .el-textarea, > .el-input-number { width: 100% !important; max-width: 520px; float: none !important; vertical-align: top; }
      > .el-select .el-input__inner, > .el-cascader .el-input__inner, > .el-input .el-input__inner, > .el-input-number .el-input__inner { height: 32px; line-height: 32px; }
      .el-cascader__label { padding-right: 30px; }
      > .el-textarea .el-textarea__inner { min-height: 80px; }
    }
  }
  .algorithm-config-model .algorithm-drawing-scroll { overflow: auto; }
  .algorithm-config-model .algorithm-drawing-scroll > div { min-width: 800px; }
  @media (max-width: 760px) {
    .algorithm-config-model .sfpzs ::v-deep > .el-form > .el-form-item {
      > .el-form-item__label { display: block; width: auto !important; float: none; text-align: left; line-height: 22px; padding: 0 0 6px; }
      > .el-form-item__content { margin-left: 0 !important; }
    }
    .algorithm-config-model .algorithm-drawing-scroll { overflow: auto; }
  }
  @media (max-height: 720px) { .algorithm-config-model .sfpzs ::v-deep > .el-form > .el-form-item { margin-bottom: 16px !important; } }
</style>
