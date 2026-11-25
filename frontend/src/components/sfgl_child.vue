<template>
  <div class="sfgl_child algorithm-config-page algorithm-config-split">
    <el-button @click="goback" size="mini" style="margin: 12px;">返回</el-button>
    <div class="sfpzs">
      <el-form ref="form" :model="form" :rules="rules" size="mini" label-width="110px">
        <div class="algorithm-config-top" :class="{ 'algorithm-top-with-model': type_jx || model_template_config_id_num == 5 || form.model_two_type != '' }">
          <section class="algorithm-basic-panel" aria-label="基础信息">
            <h3 class="algorithm-panel-title">基础信息</h3>
            <el-form-item label="任务名称" style="padding-top: 16px;" prop="conf_name">
              <el-input v-model="form.conf_name" style="width: 50%;float: left;"></el-input>
              <div class="w-1\2 algorithm-field-hint" style="color: red;">*例:报警设备_解析类型名称</div>
            </el-form-item>
            <el-form-item label="单位名称" prop="Mine_id">
              <el-select v-model="form.Mine_id" placeholder="请选择单位名称" size="small" clearable filterable  style="width: 50%;float: left;">
                <el-option v-for="item in options1" :key="item.id" :label="item.mine_name" :value="item.id"></el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="报警设备" prop="equipment_name">
              <!-- <el-cascader v-model="form.equipment_name" :options="dict.equipment_list" :props="props" clearable filterable style="width: 50%;float: left;" @change="handleChangeCanvas2();updateConfName();type_qy=true;"></el-cascader> -->
                  <!-- <el-cascader v-model="form.equipment_name" :options="dict.equipment_list" :props="props" clearable filterable style="width: 50%;float: left;" @change="equipment_alogrithm_info(),handleChangeCanvas2();updateConfName();type_qy=true;"></el-cascader> -->
              <!-- <el-select v-model="form.equipment_name" placeholder="请选择设备" collapse-tags size="small" clearable filterable @change="equipment_alogrithm_info(),handleChangeCanvas2();updateConfName();type_qy=true;" style="width: 50%;float: left;">
                <el-option v-for="item in dict.equipment_list" :key="item.id" :label="item.equipment_name" :value="item.id"></el-option>
              </el-select> -->
              <el-cascader v-model="form.equipment_name" :options="dict.equipment_list" :props="props" clearable filterable style="width: 50%;float: left;" @change="onAlarmDeviceChange"></el-cascader>
            </el-form-item>
            <el-form-item label="视频码流" class="algorithm-stream-row">
              <el-select v-model="streamSelection" :disabled="streamSelectionDisabled" style="width: 50%">
                <el-option v-for="option in streamOptions" :key="option.value" :value="option.value" :label="option.label" :disabled="option.disabled" />
              </el-select>
              <div class="algorithm-stream-help">{{ streamCapabilityHint }}</div>
            </el-form-item>
            <el-form-item label="解析类型" prop="Algorithm_library_id">
              <el-select v-model="form.Algorithm_library_id" placeholder="请选择解析类型" @change="countfns()" clearable filterable style="width: 50%;float: left;">
                <el-option v-for="item in dict.algorithm_list" :key="item.id" :label="item.algorithm_name" :value="item.id"> </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="报警等级" style="margin-top: 16px;" prop="res_type">
              <el-select v-model="form.res_type" placeholder="请选择报警等级" size="mini" clearable filterable style="width: 50%" @change="markAlgorithmAlarmEdited">
                <!-- <el-option v-for="item in alarmTypeDictOptions" :key="'报警等级'+item.value" :label="item.label" :value="item.value"></el-option> -->
                <el-option v-for="item in dict.type_list" :key="'报警等级'+item.id" :label="item.value" :value="item.id"></el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="算力资源" prop="resource_id">
              <el-cascader style="width: 50%" v-model="form.resource_id" :options="computeOptions" :props="computeProps" :show-all-levels="false" clearable @change="markAlgorithmResourceEdited"></el-cascader>
              <div class="algorithm-resource-status" role="status" aria-live="polite">{{ algorithmAdmissionHint }}</div>
            </el-form-item>
          </section>
          <section class="algorithm-model-settings" aria-label="模型配置" v-if="type_jx || model_template_config_id_num == 5 || form.model_two_type != ''">
            <h3 class="algorithm-panel-title">模型配置</h3>
            <div style="width: 100%;border: 1px dashed #e5e5e5;background: #f9fafb;border-radius: 10px;" v-if="type_jx">
              <el-form-item label="检测类型" style="margin-top: 16px;" v-show="model_template_config_id_num != 4">
                <el-select v-model="form.label_list" placeholder="请选择检测类型" size="mini" clearable filterable multiple style="width: 50%" @change="handleChangeLabelList">
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
                  <el-input :value="algorithmPeopleEnteringDisplay" readonly :aria-label="algorithmCountingEnteringLabel"></el-input>
                </el-form-item>
                <el-form-item :label="algorithmCountingExitingLabel">
                  <el-input :value="algorithmPeopleExitingDisplay" readonly :aria-label="algorithmCountingExitingLabel"></el-input>
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
              <!-- <el-form-item label="偏移量">
                <el-input v-model="form.name" style="width: 50%;float: left;"></el-input>
                <div class="w-1\2">
                  <el-button type="danger" plain>删除</el-button>
                </div>
              </el-form-item>
              <el-form-item label="触发数量">
                <el-input v-model="form.name" style="width: 50%;float: left;"></el-input>
                <div class="w-1\2">
                  <el-button type="danger" plain>删除</el-button>
                </div>
              </el-form-item>
              <el-form-item label="IOU阈值">
                <el-input v-model="form.name" style="width: 50%;float: left;"></el-input>
                <div class="w-1\2">
                  <el-button type="danger" plain>删除</el-button>
                  <el-button type="success" plain>新增</el-button>
                </div>
              </el-form-item> -->
            </div>
            <el-form-item label="扩增比例参数" style="margin-top: 16px;" prop="amp" v-show="model_template_config_id_num == 5">
              <!-- <el-input v-model.number="form.amp" style="width: 50%;float: left;"></el-input> -->
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
                <el-option v-for="item in options8" :key="'级联解析类型'+item.id" :label="item.algorithm_name" :value="item.id"></el-option>
              </el-select>
            </el-form-item>
            <div style="width: 100%;border: 1px dashed #e5e5e5;background: #f9fafb;border-radius: 10px;" v-if="form.model_two_type != ''">
              <el-form-item label="检测类型" style="margin-top: 16px;">
                <el-select v-model="label_list" placeholder="请选择检测类型" size="mini" clearable filterable multiple style="width: 50%">
                  <el-option v-for="item in options7" :key="item.id" :label="item.test_type_cname" :value="item.test_type_ename"></el-option>
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
            </div>
          </section>
        </div>
        <div class="algorithm-drawing-scroll" style="width: 100%;height: 680px;border: 1px dashed #e5e5e5;background: #f9fafb;border-radius: 10px;" v-if="type_qy">
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
                <el-button type="text" :show="!drawLineOpen ? 'primary' : ''"
                  @click="switchDrawMode(false)">绘制区域</el-button>
                <el-button type="text" :show="drawLineOpen ? 'primary' : ''"
                  @click="switchDrawMode(true)">绘制警戒线</el-button>
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
                <el-input style="width: 100%" v-model.number="form.sensitivity" placeholder="请输入间隔帧" maxlength="4"></el-input>
              </el-form-item>
              <!-- <el-form-item label="算法优先级">
                <el-select v-model="form.priority" placeholder="请选择" clearable filterable style="width: 100%">
                  <el-option label="1" :value="1"></el-option>
                  <el-option label="2" :value="2"></el-option>
                  <el-option label="3" :value="3"></el-option>
                  <el-option label="4" :value="4"></el-option>
                  <el-option label="5" :value="5"></el-option>
                  <el-option label="6" :value="6"></el-option>
                  <el-option label="7" :value="7"></el-option>
                  <el-option label="8" :value="8"></el-option>
                  <el-option label="9" :value="9"></el-option>
                  <el-option label="10" :value="10"></el-option>
                </el-select>
              </el-form-item> -->
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
              <el-form-item label="目标框显示" v-if="isTypeTFS">
                <el-select v-model="form.image_draw_type" placeholder="请选择" clearable filterable style="width: 100%">
                  <el-option label="是" :value="1"></el-option>
                  <el-option label="否" :value="2"></el-option>
                </el-select>
              </el-form-item>
            </div>
            <div style="width: 38%;height: 100%;float: left;" v-if="isTypeTFS">
              <div style="width: 100%;height: 16px;"></div>
              <el-form-item prop="duration_time" v-if="show_cxsc">
                <span slot="label" style="display:inline-block;">
                  持续时长
                  <el-tooltip effect="dark" content="需求行为的持续时长。取值范围：（1-1800）" placement="bottom">
                    <i class='el-icon-question' />
                  </el-tooltip>
                </span>
                <el-input style="width: 100%" v-model.number="form.duration_time" placeholder="请输入持续时长" maxlength="4">
                  <template slot="append">秒</template>
                </el-input>
              </el-form-item>
              <el-form-item label="开始时间" prop="defense_time_start" v-if="isTypeTFS">
                <el-time-picker v-model="form.defense_time_start" style="width: 100%" value-format="HH:mm:ss" :picker-options="{selectableRange: '00:00:00 - 23:59:59'}" placeholder="任意时间点" :default-value="new Date().setHours(0, 0, 0, 0)">
                </el-time-picker>
              </el-form-item>
              <el-form-item label="结束时间" prop="defense_time_end">
                <el-time-picker v-model="form.defense_time_end" value-format="HH:mm:ss" style="width: 100%" :picker-options="{selectableRange: '00:00:00 - 23:59:59'}" placeholder="任意时间点" :default-value="new Date().setHours(0, 0, 0, 0)">
                </el-time-picker>
              </el-form-item>
              <!-- <el-form-item>
                <span slot="label" style="display:inline-block;">
                  运行时间
                </span>
                <el-input style="width: 100%" v-model.number="form.run_time" placeholder="请输入运行时间">
                  <template slot="append">秒</template>
                </el-input>
              </el-form-item> -->
            </div>
          </div>
        </div>
        <el-form-item label="任务说明" style="margin-top: 16px;">
          <el-input v-model="form.Algorithm_config_ps" placeholder="请输入备注" type="textarea" style="width: 50%;float: left;"></el-input>
        </el-form-item>
        <el-form-item class="algorithm-form-actions">
          <div class="algorithm-action-buttons" style="text-align: -end;margin-bottom: 24px;">
            <el-button type="primary" @click="sub_fn">保存</el-button>
            <el-button @click="goback">取消</el-button>
          </div>
        </el-form-item>
      </el-form>
    </div>

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
        <el-radio :label="selectedOption_type" class="grid-item">{{selectedOption_type}}</el-radio>
        <!-- <el-radio :label="'类型二'" class="grid-item">类型二</el-radio>
        <el-radio :label="'类型三'" class="grid-item">类型三</el-radio> -->
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
  data() {
    return {
      lineDirection: 'right',
      equipment_alogrithm_info_list: null,
      inOnArrow1: true,
      clickSide: null,
      isShow: false,
      show_cxsc: false,
      isTypeTFS: true,
      selectedOption_type: '',
      dict: {
        equipment_list: [],
      },
      type_jx: false,
      type_qy: false,
      StartTime: "",
      EndTime: "",
      nameif:'',
      form: {
        all_Entering_num: 0,
        all_Exiting_num: 0,
        resource_id: 0,
        conf_name: '',
        "Mine_id": "",
        "Equipment_id": "",
        "conf_area": [],
        "shield_status": "",
        "tem_conf_area": [],
        "draw_type": "1",
        "img_resolution": "",
        "image_draw_type": 1,
        uwb_distance: "10",
        "template_list_area": [],
        priority: "",
        run_time: "",
        mine_name: "",
        algorithm_name: "",
        equipment_name: "",
        Algorithm_library_id: "",
        type: 0,
        confidence: "60",
        tem_frames: "[27,37]",
        duration_time: 10,
        interval_time: 2,
        sensitivity: 2,
        defense_time_start: '00:00:00',
        defense_time_end: '23:59:59',
        image_count: 5,
        template_data: [],
        test_type_id: "",
        label_list: [],
        amp: 10,
        alg_select_type: '3',
        model_two_data: [],
        model_two_type: '',
      },
      model_two_type: '',
      label_list: [],
      confidence: '60',
      model_path: '',
      selectedOption_model: '类型一',
      title2_model: '',
      dialogVisible2_model: false,
      title2: "",
      selectedOption: '报警',
      dialogVisible2: false,
      type_list: [],
      alarmTypeDictOptions: [
        {
          label: '一级报警',
          value: '1',
        },
        {
          label: '二级报警',
          value: '2',
        },
        {
          label: '三级报警',
          value: '3',
        },
        {
          label: '四级报警',
          value: '4',
        },
        {
          label: '五级报警',
          value: '5',
        },
        {
          label: '六级报警',
          value: '6',
        },
        {
          label: '七级报警',
          value: '7',
        },
        {
          label: '八级报警',
          value: '8',
        },
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
        value: 'model_id',
        label: 'model_type_name',
      },
      modelOptions: [],
      modelSmallOption: [],
      computeOptions: [],
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
      options8: [],
      options7: [],
      resolution: '',
      resolutionOption: [
        { value: '1920x1080', name: '普通' },
        { value: '2688x1520', name: '热成像' },
        { value: '2560x1440', name: '热成像' },
        { value: '1280x720', name: '热成像' },
        { value: '720x576', name: '热成像2' }
      ],

      imgurl: "",
      isdraw: false,
      coordinates: [],
      cor_index: 0,
      endtip: false,
      mark_list: [],
      mark_lists: [],
      PointInArea: false,
      index: null,
      loading: false,
      area2: false,
      isdraw2: false,
      coordinates2: [],
      cor_index2: 0,
      endtip2: false,
      mark_list2: [],
      mark_lists2: [],
      PointInArea2: false,
      index2: null,
      loading2: false,
      area3: false,
      isdraw3: false,
      coordinates3: [],
      cor_index3: 0,
      endtip3: false,
      mark_list3: [],
      PointInArea3: false,
      index3: null,
      loading3: false,
      imgOpen: false,
      title: "",
      title3: "",
      shield_status: 2,
      image_draw_type: 1,
      drawLineOpen: false,
      selectedOption_type_s: '',
      pickerOptions: {
        disabledDate(time) {
          const today = new Date();
          today.setHours(0, 0, 0, 0);
          return time.getTime() > today.getTime();
        },
      },
      coordinates: [],
      coordinates2: [],
      coordinates3: [],
      checkStatusTime: null,
      flvPlayer: null,
      coordinates_model: [],
      mark_list_model: [],
      mark_lists_model: [],
      selectedOption_model: '类型一',
      title2_model: '',
      dialogVisible2_model: false,
      modelTypeOptions: [],
      template_type_id: '',
      stepActive: 0,
      modelSmallOption: [],
      modelNameOpen: false,
      modelNamemsg: '',
      model_template_config_id_num: 1,
      analysisSrc: '',
      analysisId: '',
      rules: {
        amp: [
          { required: true, message: '扩增比例参数(0-100)', trigger: 'blur' },
        ],
        model_two_type: [
          { required: true, message: '请选择级联解析类型', trigger: 'change' },
        ],
        uwb_distance: [
          { required: true, message: '请输入识别距离', trigger: 'blur' },
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
              if (value < 1 || value > 1800) {
                callback(new Error('数字必须在1到1800之间'));
              } else {
                callback();
              }
            },
            trigger: 'blur'
          }
        ],
        interval_time: [
          { required: true, message: '请输入告警间隔', trigger: 'blur' }, {
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
  computed: {
    
  },
  created() {
    if(localStorage.getItem('user_role_id')){
      this.usertype = localStorage.getItem('user_role_id')
    }
    this.getCompute();
  },
  methods: {
    switchDrawMode(isLine) {
      this.drawLineOpen = isLine
      if (isLine) {
        this.initCanvas4()
      } else {
        this.initCanvas()
      }
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
      if (!this.validateAlgorithmTemplateParameters()) return false;
      if (this.trySaveAlgorithmMetadata()) return;
      if (!this.validateAlgorithmCountingGeometry()) return false;
      if (!this.canSaveAlgorithmSource()) return false;
      const validationSourceKey = this.streamSourceKey;
      this.$refs['form'].validate((valid) => {
          if (this._algorithmFormClosed || validationSourceKey !== this.streamSourceKey || !this.canSaveAlgorithmSource()) return;
          if (valid) {
            const timestamp1 = this.timeToTimestamp(this.form.defense_time_start);
          const timestamp2 = this.timeToTimestamp(this.form.defense_time_end);
          if (timestamp1 > timestamp2) {
            this.$message({
              message: '结束时间不能小于开始时间，请重新选择结束时间!',
              type: "warning",
            });
            this.form.defense_time_end = '23:59:59';
            return;
          }
          if (this.shield_status == "1") {
            let parts = this.resolution.split("x");
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
            this.handleData_model()
            if (this.model_template_config_id_num == 4) {
              this.form.test_type_id = this.options4[0].id
              this.form.label_list = [this.options4[0].test_type_ename]
            }
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
            this.options7.forEach((item)=>{
              all_type_list.push(item.test_type_ename)
            })
            let strs = '';
            if(this.dict.algorithm_list_five.length != 0){
              var list_paths = this.dict.algorithm_list_five
              list_paths.forEach(item => {
                if(item.id == this.form.model_two_type){
                  strs = item.algorithm_path
                }
              })
            }
            // 逆向寻找设备ID
            const resource = this.resolveAlgorithmResource(this.form.resource_id);
            if (!resource) { this.$message({ type: 'warning', message: '请选择有效的计算资源卡' }); return; }
            const computing_id = resource.computingId;
            this.$set(this.form, 'resource_id', resource.resourceId);
          let obj = this.algorithmPeopleCountVisible ? this.algorithmCountingPayload() : {
            ...this.form.cross_line,
            in_point: this.form.in_point,
            out_point: this.form.out_point,
          }
            let forms = {
                uwb_distance: this.form.uwb_distance,
              conf_name: this.form.conf_name,
              Algorithm_library_id: this.form.Algorithm_library_id,
              Mine_id: this.form.Mine_id,
              Equipment_id: this.form.equipment_name,
              stream_type: this.streamTypeRequest(),
            conf_area: JSON.stringify(this.mark_lists),
            cross_line_area: JSON.stringify(obj),
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.form.label_list),
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
            let forms2 = {
                uwb_distance: this.form.uwb_distance,
              id: this.form.id,
              conf_name: this.form.conf_name,
              Algorithm_library_id: this.form.Algorithm_library_id,
              Mine_id: this.form.Mine_id,
              Equipment_id: this.form.equipment_name,
              stream_type: this.streamTypeRequest(),
            conf_area: JSON.stringify(this.mark_lists),
            cross_line_area: JSON.stringify(obj),
              test_type_id: this.form.test_type_id,
              label_list: JSON.stringify(this.form.label_list),
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
            if(this.$route.query.conf_id){
              const params = new URLSearchParams();
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
                    this.goback()
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
            }else{
              this.$http
                .post(this.$url.url_5000 + "/model_view/algorithm_add", forms)
                .then((response) => {
                  if (response.data.code === 200) {
                    this.$message({
                      message: response.data.msg,
                      type: "success",
                    });
                    this.goback()
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
          } else {
            return false;
          }
        });
    },
    getModelSmallDetail() {
      return this.algorithmTemplatePayload();
    },
    handleData() {
  // 框数据处理
  if (this.mark_list.length > 0) {
    let arr = []
    for (let i = 0; i < this.mark_list.length; i++) {
      arr.push(
        this.mark_list[i].map(v => ({
          x: Number((Math.min(Math.max(v.x, 0), 640) * this.timesX).toFixed(0)),
          y: Number((Math.min(Math.max(v.y, 0), 360) * this.timesY).toFixed(0)),
          type: v.type,
          color: v.color,
        }))
      )
    }
    this.mark_lists = arr
  } else {
    this.mark_lists = [];
  }

  // 线数据处理 - 只保存线的端点和方向
  if (this.mark_list3.length > 0 && this.mark_list3[0].length >= 2) {
    const line = this.mark_list3[0];
    const p1x = Math.min(Math.max(line[0].x, 0), 640);
    const p1y = Math.min(Math.max(line[0].y, 0), 360);
    const p2x = Math.min(Math.max(line[1].x, 0), 640);
    const p2y = Math.min(Math.max(line[1].y, 0), 360);
    
    const crossLineObj = {
      p1: {
        x: Number((p1x * this.timesX).toFixed(0)),
        y: Number((p1y * this.timesY).toFixed(0))
      },
      p2: {
        x: Number((p2x * this.timesX).toFixed(0)),
        y: Number((p2y * this.timesY).toFixed(0))
      },
      // 【关键修改】只保存方向，不保存具体坐标
      direction: this.lineDirection // 'left' 或 'right'
    };
    
    this.form.cross_line = crossLineObj;
    console.log('保存时的数据:', crossLineObj);
  } else {
    this.form.cross_line = {};
  }

  this.form.draw_type = this.drawLineOpen ? '2' : '1';
},
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
    countfns(e){
      if(this.form.equipment_name != '' && this.form.equipment_name != null && this.form.equipment_name != undefined){
        if(this.form.Algorithm_library_id != '' && this.form.Algorithm_library_id != null && this.form.Algorithm_library_id != undefined){
          this.options8 = []
          let list_b = this.dict.algorithm_list_five
          if(!e){
            this.form.label_list = []
            this.form.model_two_type = '';
            this.label_list = [];
          }
          this.dict.algorithm_list.forEach((item)=>{
            if(item.id == this.form.Algorithm_library_id){
              console.log(item.algorithm_name)
              list_b.forEach((items)=>{
                if(item.algorithm_name == items.algorithm_name){
                  this.options8.push(items)
                }
              })
              if(item.algorithm_name == '探放水'){
                this.isTypeTFS = false;
              }else{
                this.isTypeTFS = true;
              }
            }
          })
          this.handleChangeCanvas2();
          this.updateConfName();
          this.handleChangeSf(this.form.Algorithm_library_id, !e);
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
      this.coordinates3 = [];
      this.mark_list.pop()
    },
    handleUpdateList() {
      let color = {
        'I级报警': '#FF0000',
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
      this.dialogVisible2 = false
    },
    removeItem(index) {
      this.removeAlgorithmTemplateParameter(index);
    },
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
          },
        })
        .then(async (response) => {
          if (!current()) return;
          const data = response.data.data || {};
          const model = (data.model_data || [])[0];
          const type = (data.model_type_data || [])[0];
          const small = (data.template_small_data || [])[0];
          this.nameif = model ? model.model_name : '';
          this.options4 = data.algorithm_data || [];
          this.options7 = data.algorithm_child_data || [];
          this.selectedOption = data.show_status;
          this.selectedOption_type_s = data.show_status;
          const selectedByUser = userSelected || this._algorithmSelectedModelId === String(id);
          const useDefaults = selectedByUser || !this.algorithmIsEditing();
          if (useDefaults && model && this.form.model_template_config_id === modelBefore) this.$set(this.form, 'model_template_config_id', model.id);
          const typeId = type ? type.id : null;
          const smallOptions = type ? this.getModelSmallDict2(type.id, current) : Promise.resolve();
          if(typeId == 1 || typeId == 2){
            this.show_cxsc = true
          }else{
            this.show_cxsc = false
            if (useDefaults) this.form.duration_time = 1;
          }
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
      }).catch(rek => {
        console.log(rek)
      })
    },
    handleChangeShield_status() {
      this.handleDrewAgain();
    },
    equipment_alogrithm_info(){
      this.$http
        .get(this.$url.url_5000 + "/ai_camera_view/equipment_alogrithm_info", {
          params: { equipment_id: this.form.equipment_name },
        })
        .then((response) => {
          this.equipment_alogrithm_info_list = response.data.data;
        });
    },
    async handleChangeCanvas2(data) {
      var info = await this.loadStreamCapabilities(data || this.algorithmEquipmentId());
      if (!info || this._algorithmFormClosed) return false;
      this.area2 = String(info.data && info.data.equipment_code) === '201';
      return this.handleimg();
    },
    handleTimesData(resolution) {
      var parts = String(resolution || '').split('x');
      var width = Number(parts[0]), height = Number(parts[1]);
      if (parts.length !== 2 || !Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return false;
      this.timesX = width / 640;
      this.timesY = height / 360;
      return true;
    },
    
    handleimg(num) { return this.requestAlgorithmImage(num); },
    
    initCanvas() {
      if (this.algorithmPeopleCountVisible) return this.initAlgorithmCountingCanvas();
      this.$nextTick(() => {
        let cav = this.$refs.mycanvas;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        let list = this.mark_list;
        let coordinates = this.coordinates
        let this_ = this
        draw_test(cav, list, this.handleChooseType, coordinates);
      });
    },
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
    handleChooseType_model() {
      this.selectedOption_model = '类型一'
      this.title2_model = '模型类型选择'
      this.dialogVisible2_model = true
    },
    initCanvas_model() {
    },
    initCanvas2() {
      this.$nextTick(() => {
        let cav = this.$refs.mycanvas2;
        cav.width = "640";
        cav.height = "360";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        cav.style.cursor = "crosshair";
        let list = this.mark_list2;
        let coordinates = this.coordinates2
        draw_test3(cav, list, coordinates);
      });
    },
    // 统一的计算箭头位置函数
// 统一的计算箭头位置函数（输入和输出都是画布坐标 640x360）
// 统一的计算箭头位置函数（输入和输出都是画布坐标 640x360）
getArrowPositions(p1, p2) {
  const dx = p2.x - p1.x;
  const dy = p2.y - p1.y;
  const len = Math.sqrt(dx * dx + dy * dy);
  if (len === 0) return null;
  
  const ux = dx / len;
  const uy = dy / len;
  const perpLen = 40;
  const mx = (p1.x + p2.x) / 2;
  const my = (p1.y + p2.y) / 2;
  
  // 计算两个箭头端点（确保是数字类型）
  const arrow1X = mx + uy * perpLen;
  const arrow1Y = my - ux * perpLen;
  const arrow2X = mx - uy * perpLen;
  const arrow2Y = my + ux * perpLen;
  
  const arrow1 = {
    x: Number(arrow1X.toFixed(2)),
    y: Number(arrow1Y.toFixed(2))
  };
  const arrow2 = {
    x: Number(arrow2X.toFixed(2)),
    y: Number(arrow2Y.toFixed(2))
  };
  
  console.log('getArrowPositions 计算结果:', { arrow1, arrow2, mx, my, ux, uy });
  
  return { arrow1, arrow2 };
},
    initCanvas4() {
      if (this.algorithmPeopleCountVisible) return this.initAlgorithmCountingCanvas();
  this.$nextTick(() => {
    const cav = this.$refs.mycanvas;
    if (!cav) return;
    
    cav.width = 640;
    cav.height = 360;
    cav.style.cursor = "crosshair";
    
    if (!this.imgOpen) {
      console.log('图片未加载完成，等待...');
      return;
    }
    
    let isDrawing = false;
    let tempStart = null;
    
    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
    const clampX = (x) => clamp(Math.round(x), 0, 640);
    const clampY = (y) => clamp(Math.round(y), 0, 360);
    
    const drawAllBoxes = (ctx) => {
      this.mark_list.forEach(polygon => {
        if (polygon.length < 3) return;
        ctx.beginPath();
        ctx.strokeStyle = polygon[0].color || '#f00';
        ctx.lineWidth = 2;
        ctx.moveTo(clampX(polygon[0].x), clampY(polygon[0].y));
        polygon.forEach(point => ctx.lineTo(clampX(point.x), clampY(point.y)));
        ctx.closePath();
        ctx.stroke();
      });
    };
    
    const renderAll = () => {
      const ctx = cav.getContext("2d");
      ctx.clearRect(0, 0, cav.width, cav.height);
      drawAllBoxes(ctx);
      
      if (this.mark_list3.length > 0 && this.mark_list3[0].length >= 2) {
        const line = this.mark_list3[0];
        let p1 = { x: clampX(line[0].x), y: clampY(line[0].y) };
        let p2 = { x: clampX(line[1].x), y: clampY(line[1].y) };
        
        this.mark_list3[0] = [p1, p2];
        
        ctx.lineWidth = 2;
        ctx.strokeStyle = "#ffd700";
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
        
        // 计算箭头位置
        const dx = p2.x - p1.x;
        const dy = p2.y - p1.y;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (len === 0) return;
        
        const ux = dx / len;
        const uy = dy / len;
        const perpLen = 40;
        const mx = (p1.x + p2.x) / 2;
        const my = (p1.y + p2.y) / 2;
        
        // 计算两个箭头端点（右侧箭头和左侧箭头）
        let rightArrowX = mx + uy * perpLen;
        let rightArrowY = my - ux * perpLen;
        let leftArrowX = mx - uy * perpLen;
        let leftArrowY = my + ux * perpLen;
        
        // 四舍五入并限制范围
        rightArrowX = clamp(Math.round(rightArrowX), 15, 625);
        rightArrowY = clamp(Math.round(rightArrowY), 15, 345);
        leftArrowX = clamp(Math.round(leftArrowX), 15, 625);
        leftArrowY = clamp(Math.round(leftArrowY), 15, 345);
        
        const drawArrow = (fromX, fromY, toX, toY, color, text) => {
          ctx.strokeStyle = color;
          ctx.fillStyle = color;
          ctx.lineWidth = 2;
          const headLen = 6;
          const angle = Math.atan2(toY - fromY, toX - fromX);
          
          ctx.beginPath();
          ctx.moveTo(fromX, fromY);
          ctx.lineTo(toX, toY);
          ctx.stroke();
          
          ctx.beginPath();
          const arrowX1 = toX - headLen * Math.cos(angle - Math.PI / 6);
          const arrowY1 = toY - headLen * Math.sin(angle - Math.PI / 6);
          const arrowX2 = toX - headLen * Math.cos(angle + Math.PI / 6);
          const arrowY2 = toY - headLen * Math.sin(angle + Math.PI / 6);
          ctx.moveTo(toX, toY);
          ctx.lineTo(arrowX1, arrowY1);
          ctx.lineTo(arrowX2, arrowY2);
          ctx.fill();
          
          ctx.font = "bold 14px Arial";
          ctx.textAlign = "center";
          let textY = toY - 8;
          textY = clamp(textY, 12, 352);
          ctx.fillStyle = color;
          ctx.fillText(text, toX, textY);
        };
        
        const mxDraw = (p1.x + p2.x) / 2;
        const myDraw = (p1.y + p2.y) / 2;
        
        // 【关键修改】根据 lineDirection 决定哪个箭头显示 IN
        if (this.lineDirection === 'left') {
          // IN 在左侧箭头，OUT 在右侧箭头
          drawArrow(mxDraw, myDraw, leftArrowX, leftArrowY, '#44ff44', 'IN');
          drawArrow(mxDraw, myDraw, rightArrowX, rightArrowY, '#ff4444', 'OUT');
        } else {
          // IN 在右侧箭头，OUT 在左侧箭头（默认）
          drawArrow(mxDraw, myDraw, rightArrowX, rightArrowY, '#44ff44', 'IN');
          drawArrow(mxDraw, myDraw, leftArrowX, leftArrowY, '#ff4444', 'OUT');
        }
        
        console.log('渲染: lineDirection=', this.lineDirection);
      }
    };
    
    renderAll();
    
    // 鼠标按下开始绘制
    cav.onmousedown = (e) => {
      if (this.mark_list3.length >= 1) return;
      const rect = cav.getBoundingClientRect();
      const scaleX = cav.width / rect.width;
      const scaleY = cav.height / rect.height;
      let x = (e.clientX - rect.left) * scaleX;
      let y = (e.clientY - rect.top) * scaleY;
      x = clampX(x);
      y = clampY(y);
      if (!isDrawing) {
        isDrawing = true;
        tempStart = { x: x, y: y };
      } else {
        isDrawing = false;
        const endX = clampX(x);
        const endY = clampY(y);
        if (tempStart.x !== endX || tempStart.y !== endY) {
          this.mark_list3 = [[tempStart, { x: endX, y: endY }]];
          // 新绘制的线，默认 IN 在右侧
          this.lineDirection = 'right';
          renderAll();
        }
        tempStart = null;
        if (this.mark_list3.length > 0) {
          this.$message.success("警戒线绘制完成，点击线条左右切换进出方向");
        }
      }
    };
    
    // 鼠标移动绘制中
    cav.onmousemove = (e) => {
      if (!isDrawing || !tempStart) return;
      const rect = cav.getBoundingClientRect();
      const scaleX = cav.width / rect.width;
      const scaleY = cav.height / rect.height;
      let x = (e.clientX - rect.left) * scaleX;
      let y = (e.clientY - rect.top) * scaleY;
      x = clampX(x);
      y = clampY(y);
      const ctx = cav.getContext("2d");
      ctx.clearRect(0, 0, 640, 360);
      drawAllBoxes(ctx);
      ctx.strokeStyle = "#ffd700";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(tempStart.x, tempStart.y);
      ctx.lineTo(x, y);
      ctx.stroke();
    };
    
    // 点击线条切换方向
    cav.onclick = (e) => {
      if (this.mark_list3.length === 0) return;
      // 切换方向
      this.lineDirection = this.lineDirection === 'left' ? 'right' : 'left';
      console.log('切换方向: lineDirection=', this.lineDirection);
      renderAll();
    };
    
    // 双击结束绘制
    cav.ondblclick = () => {
      isDrawing = false;
      tempStart = null;
      renderAll();
    };
  });
},
    tableCanvas(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10);
      var HH = parseInt(parts[1], 10);
      this.$nextTick(() => {
        let cav = this.$refs[`tableCanvas_${id}`];
        cav.width = "96";
        cav.height = "54";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        let XX = parseInt(WW / 96, 10)
        let YY = parseInt(HH / 54, 10)
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
        draw_test2(cav, [...arr_w]);
      });
    },
    tableCanvasMax(id, list, type, resolution) {
      var parts = resolution.split('x');
      var WW = parseInt(parts[0], 10);
      var HH = parseInt(parts[1], 10);
      this.$nextTick(() => {
        let cav = this.$refs[`tableCanvas_tableMax`];
        cav.width = "800";
        cav.height = "400";
        let ctx = cav.getContext("2d");
        ctx.strokeStyle = "red";
        let XX = WW / 800
        let YY = HH / 400
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
        draw_test2(cav, [...arr_w]);
      });
    },
    handleChangeLabelList() {
      this.markAlgorithmDetectionEdited();
      if (this.form.label_list.length != 0) {
        const selected = this.options4.find(v => v.test_type_ename == this.form.label_list[0]);
        this.form.test_type_id = selected ? selected.id : '';
      } else {
        this.form.test_type_id = '';
      }
    },
    updateConfName() {
      const { equipment_name, Algorithm_library_id } = this.form;
      let algorithmName = '';
      let monitorPointName = '';
      if (Algorithm_library_id) {
        const selectedAlgorithm = this.options3.find(option => option.id === Algorithm_library_id);
        algorithmName = selectedAlgorithm ? selectedAlgorithm.algorithm_name : '';
      }
      if (equipment_name) {
        for (let item of this.options2) {
          if (Array.isArray(item.children)) {
            const foundChild = item.children.find(child => child.id === equipment_name);
            if (foundChild) {
              monitorPointName = foundChild.equipment_name;
            }
          }
        }
      }
    },
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
      return Math.random().toString(36).substr(2, 9);
    },
    transformData(rawData) {
      return this.sortAlgorithmResources(rawData);
    },
    handleDrewAgain() {
      if (this.algorithmPeopleCountVisible) return this.startAlgorithmCountingDrawing();
      this.mark_list = [];
      this.coordinates = [];
      this.mark_list3 = [];
      this.coordinates3 = [];
      this.clickSide = null;
      this.form.cross_line = {};
      this.form.in_point = {};
      this.form.out_point = {};
      this.drawLineOpen = false;
      this.initCanvas();
      this.$message.success("已清空所有绘制内容");
    },
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
    resole() {
      if (this.algorithmPeopleCountVisible) return this.undoAlgorithmCountingPoint();
      if (!this.drawLineOpen) {
        this.coordinates.pop()
        this.initCanvas()
      } else {
        this.mark_list3 = []
        this.initCanvas4()
      }
    },
    resole_model() {
      this.coordinates_model.pop()
    },
    resole2() {
      this.coordinates2.pop()
    },
    init(){
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: '',
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
            this.options2 = response.data.equipment_list;
            this.options3 = response.data.algorithm_list;
            this.type_list = response.data.type_list
            
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
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    
    handlechange(data) {
  this.stepActive = 0
  this.coordinates = [];
  this.coordinates_model = [];
  this.coordinates2 = [];
  this.coordinates3 = [];
  this.$http
    .get(this.$url.url_5000 + "/model_view/algorithm_data_show", {
      params: {
        conf_id: data,
      },
    })
    .then((response) => {
      if (this._algorithmFormClosed || this._algorithmModelWasSelected) return;
      if (response.data.code === 200) {
        this.title = "算法修改";
        this.form = response.data.datalist;
            this.restoreAlgorithmCountingGeometry(this.form.cross_line_area);
        this.restoreAlgorithmSource();
        this.form.equipment_name = this.form.Equipment_id
        // this.equipment_alogrithm_info()
        this.form.model_two_type = response.data.datalist.model_two_type * 1

        if (this.form.img_resolution) {
          this.resolution = this.form.img_resolution;
          this.handleTimesData(this.resolution);
        }
        
        if (this.form.model_two_data && this.form.model_two_data.length) {
          this.label_list = this.form.model_two_data[0].label_list;
          this.confidence = this.form.model_two_data[0].confidence;
          this.model_path = this.form.model_two_data[0].model_path;
        }
        
        // 框数据回显
        if (response.data.datalist.conf_area && response.data.datalist.conf_area != '[]') {
          let arr = JSON.parse(response.data.datalist.conf_area.replace(/'/g, '"'));
          let jia = [], jia_w = [];
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
            jia_w.push(jia);
            jia = [];
          }
          this.mark_list = [...jia_w];
        } else {
          this.mark_list = [];
        }
        
        // 线数据回显
this.mark_list3 = [];
this.form.cross_line = {};
this.lineDirection = 'right'; // 默认值

if (response.data.datalist.cross_line_area && 
    response.data.datalist.cross_line_area !== '' && 
    response.data.datalist.cross_line_area !== '{}') {
  
  try {
    let crossData = typeof response.data.datalist.cross_line_area === 'string' 
      ? JSON.parse(response.data.datalist.cross_line_area.replace(/'/g, '"')) 
      : response.data.datalist.cross_line_area;
    
    console.log('原始线数据:', crossData);
    
    if (crossData.p1 && crossData.p2) {
      // 线的端点：除以倍率，转换回画布坐标
      let p1 = {
        x: parseFloat(crossData.p1.x) / this.timesX,
        y: parseFloat(crossData.p1.y) / this.timesY
      };
      let p2 = {
        x: parseFloat(crossData.p2.x) / this.timesX,
        y: parseFloat(crossData.p2.y) / this.timesY
      };
      
      p1.x = Math.min(640, Math.max(0, p1.x));
      p1.y = Math.min(360, Math.max(0, p1.y));
      p2.x = Math.min(640, Math.max(0, p2.x));
      p2.y = Math.min(360, Math.max(0, p2.y));
      
      this.mark_list3 = [[p1, p2]];
      this.form.cross_line = { p1, p2 };
      
      // 【关键修改】读取保存的方向
      if (crossData.direction) {
        this.lineDirection = crossData.direction;
      } else if (crossData.in_point && crossData.out_point) {
        // 兼容旧数据：如果有 in_point/out_point，根据位置判断方向
        // 这里可以添加兼容逻辑，但最终还是要转换为 direction
        this.lineDirection = this.calcDirectionFromPoints(p1, p2, crossData.in_point);
      }
      
      console.log('回显方向:', this.lineDirection);
      
      this.drawLineOpen = true;
    }
  } catch(e) {
    console.error('解析cross_line_area失败:', e);
  }
}
        
        this.form.template_data = this.normalizeAlgorithmTemplateRows(this.form.template_data);
        
        if (this.form.tem_frames == '') {
          this.form.tem_frames = '[27,37]';
        }
        if (this.form.confidence == null || this.form.confidence == '') {
          this.form.confidence = "60";
        }
        
        this.image_draw_type = this.form.image_draw_type;
        this.form.resource_id_old = this.form.resource_id;
        this.shield_status = Number(response.data.datalist.shield_status);
        this.dialogVisible = true;
        this.handleSelect();
        this.handleChangeSf(this.form.Algorithm_library_id);
        this.form.equipment_name = response.data.datalist.Equipment_id;
        
        this.handleimg();
        
        // 模型区域数据回显
        (() => {
          if (response.data.datalist.template_list_area && response.data.datalist.template_list_area != '[]') {
            let arr = JSON.parse(response.data.datalist.template_list_area.replace(/'/g, '"'));
            let jia = [];
            let jia_w = [];
            for (let w = 0; w < arr.length; w++) {
              for (let i = 0; i < arr[w].length; i++) {
                let x = parseFloat(arr[w][i].x);
                let y = parseFloat(arr[w][i].y);
                jia.push({
                  x: x,
                  y: y,
                  type: arr[w][i].type,
                  color: arr[w][i].color,
                });
              }
              jia_w.push(jia);
              jia = [];
            }
            this.mark_list_model = [...jia_w];
          } else {
            this.mark_list_model = [];
          }
        })();

        let tem_conf_area = response.data.datalist.tem_conf_area;
        const editedSourceKey = this.streamSourceKey;
        this.loadStreamCapabilities(this.algorithmEquipmentId())
          .then((info) => {
            if (!info || this._algorithmFormClosed || editedSourceKey !== this.streamSourceKey) return;
            const response = { data: info };
            if (response.data.data.equipment_code == "201") {
              this.area2 = true;
              if (tem_conf_area && tem_conf_area != '[]') {
                let arr2 = JSON.parse(tem_conf_area.replace(/'/g, '"'));
                let jia2 = [];
                for (let i = 0; i < arr2[0].length; i++) {
                  let x = parseFloat(arr2[0][i].x);
                  let y = parseFloat(arr2[0][i].y);
                  jia2.push({
                    x: x,
                    y: y,
                  });
                }
                this.mark_list2 = [jia2];
              } else {
                this.mark_list2 = [];
              }
              if (this.$refs.mycanvas2) this.initCanvas2();
            } else {
              this.area2 = false;
            }
          });
      }
    })
    .catch(function (response) {
      console.log(response);
    });
},
    
    handleSelect(a) {
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
          if (response.data.code === 200) {
            this.options1 = response.data.mine_list;
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
  mounted() {
    this.init()
    if (this.$route.query.conf_id) {
      this.type_jx = true;
      this.type_qy = true;
      this.handlechange(this.$route.query.conf_id);
    }
  },
  beforeDestroy() {
    
  },
  destroyed() {
    
  },
};
</script>
<style lang="scss" scoped>
  .sfgl_child{
    width: 100%;
    height: 100%;
    background: #fff;
    overflow: hidden;
    overflow-y: scroll;
  }
  .sfpzs{
    width: 900px;
    height: calc(100% - 100px);
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
  /* Form presentation only. Keep the original drawing groups and media geometry. */
  .algorithm-config-page { min-height: 0; overflow: auto; overscroll-behavior: contain; }
  .algorithm-config-page .sfpzs { width: 100%; max-width: 1120px; height: auto; margin: 0 auto; padding: 4px 24px 32px; box-sizing: border-box; }
  .algorithm-config-page .sfpzs ::v-deep > .el-form > .el-form-item {
    max-width: 680px; margin: 0 auto 20px !important; padding-top: 0 !important;
    > .el-form-item__label { color: #42516a; font-size: 13px; line-height: 32px; padding-right: 16px; }
    > .el-form-item__content {
      line-height: 32px; min-width: 0;
      > .el-select, > .el-cascader, > .el-input, > .el-textarea, > .el-input-number {
        width: 100% !important; max-width: 520px; float: none !important; vertical-align: top;
      }
      > .el-select .el-input__inner, > .el-cascader .el-input__inner, > .el-input .el-input__inner, > .el-input-number .el-input__inner { height: 32px; line-height: 32px; }
      > .el-textarea .el-textarea__inner { min-height: 80px; }
      .el-cascader__label { padding-right: 30px; }
    }
  }
  .algorithm-config-page .algorithm-field-hint,
  .algorithm-config-page .algorithm-stream-help { display: block; width: 100% !important; max-width: 520px; clear: both; float: none !important; margin: 6px 0 0 !important; padding: 0; color: #78869a !important; font-size: 12px; line-height: 1.65; overflow-wrap: break-word; }
  .algorithm-config-page .algorithm-action-buttons { display: flex; align-items: center; gap: 10px; max-width: 520px; margin: 0 !important; padding: 18px 0 4px; border-top: 1px solid #e8edf4; }
  .algorithm-config-page .algorithm-action-buttons ::v-deep > .el-button { min-width: 88px; margin-left: 0; padding: 9px 18px; }
  .algorithm-config-page .algorithm-drawing-scroll { overflow: auto; }
  .algorithm-config-page .algorithm-drawing-scroll > div { min-width: 800px; }
  @media (max-width: 1100px) { .algorithm-config-page .sfpzs { padding: 4px 16px 28px; } }
  @media (max-width: 760px) {
    .algorithm-config-page .sfpzs { padding: 4px 12px 24px; }
    .algorithm-config-page .sfpzs ::v-deep > .el-form > .el-form-item {
      > .el-form-item__label { display: block; width: auto !important; float: none; text-align: left; line-height: 22px; padding: 0 0 6px; }
      > .el-form-item__content { margin-left: 0 !important; }
    }
    .algorithm-config-page .algorithm-drawing-scroll { overflow: auto; }
  }
  @media (max-height: 720px) { .algorithm-config-page .sfpzs { padding-top: 0; padding-bottom: 24px; } .algorithm-config-page .sfpzs ::v-deep > .el-form > .el-form-item { margin-bottom: 16px !important; } }
</style>
