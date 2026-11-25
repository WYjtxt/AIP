<template>
  <div class="sfgl_child algorithm-config-page">
    <el-button @click="goback" size="mini" style="margin: 12px;">返回</el-button>
    <div class="sfpzs">
      <el-form ref="form" :model="form" :rules="rules" size="mini" label-width="110px">
        <el-form-item label="任务名称" style="padding-top: 16px;" prop="conf_name">
          <el-input v-model="form.conf_name" style="width: 50%;float: left;"></el-input>
          <div class="w-1\2 algorithm-field-hint" style="color: red;">*例:报警设备_解析类型名称</div>
        </el-form-item>
        <el-form-item label="单位名称" prop="Mine_id">
          <el-select v-model="form.Mine_id" placeholder="请选择单位名称" size="small" clearable filterable
            style="width: 50%;float: left;">
            <el-option v-for="item in options1" :key="item.id" :label="item.mine_name" :value="item.id"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="报警设备" prop="equipment_name">
          <!-- <el-cascader v-model="form.equipment_name" :options="dict.equipment_list" :props="props" clearable filterable style="width: 50%;float: left;" @change="handleChangeCanvas2();updateConfName();type_qy=true;"></el-cascader> -->
          <el-cascader v-model="form.equipment_name" :options="dict.equipment_list" :props="props" clearable filterable
            @change="onAdvancedDeviceChange" style="width: 50%;float: left;"></el-cascader>
        </el-form-item>
        <el-form-item label="视频码流" class="algorithm-stream-row">
          <el-select v-model="streamSelection" :disabled="streamSelectionDisabled" style="width: 50%">
            <el-option v-for="option in streamOptions" :key="option.value" :value="option.value" :label="option.label" :disabled="option.disabled" />
          </el-select>
          <div class="algorithm-stream-help">{{ streamCapabilityHint }}；所有解析类型使用同一码流</div>
        </el-form-item>
        <el-form-item label="解析类型" class="algorithm-model-selector" v-if="form.equipment_name" v-for="(item, index) in jxlxlist" :key="index">
          <el-select v-model="item.Algorithm_library_id" placeholder="请选择解析类型" @change="countfns(index)"
            filterable style="width: 50%;float: left;margin-right: 12px;">
            <el-option v-for="item in dict.algorithm_list" :key="item.id" :label="item.algorithm_name" :value="item.id">
            </el-option>
          </el-select>
          <div class="w-1\2 algorithm-model-actions">
            <el-button v-if="index == 0" icon="el-icon-plus" circle size="mini" @click="addfn"></el-button>
            <el-button icon="el-icon-minus" v-if="jxlxlist.length > 1" circle size="mini"
              @click="deletefn(index)"></el-button>
          </div>
        </el-form-item>
        <el-divider></el-divider>
        <div class="btnlist" v-if="jxlxlist.length > 0 && jxlxlist[0].algorithm_name">
          <div v-for="(item, index) in jxlxlist" v-show="item.algorithm_name" :key="index+'i'"
            :class="[{ is_active: btnCli+'i' == index+'i' }]" @click="btnClick(index)">{{ item.algorithm_name }}</div>
        </div>
        <div v-if="aaas">

          <div class="algorithm-model-panel" v-for="(item,index) in jxlxlist" :key="modelKey(item)" v-show="index == btnCli">
            <cavdiv ref="canvasRef" :item="item" :config-stream-type="form.stream_type" :conf_id="conf_ids" :indexnum="index" :types="ddds" v-if="jxlxlist[index].algorithm_name" @update:item="item[index] = $event"></cavdiv>
          </div>
        </div>
        <el-form-item class="algorithm-form-actions">
          <div class="algorithm-action-buttons" style="text-align: -end;margin-bottom: 24px;">
            <el-button type="primary" @click="sub_fn">保存</el-button>
            <el-button @click="goback">取消</el-button>
          </div>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script>
import cavdiv from './sfgl_childsCom.vue'
import algorithmStreamMixin from './algorithmStreamMixin';
export default {
  mixins: [algorithmStreamMixin],
  components: {
    cavdiv
  },
  name: "sfgl_child",
  data() {
    return {
      ddds: 0,
      aaas: true,
      conf_ids:'',
      btnCli: 0,
      listMap: [],
      jxlxlist: [],
      dict: [],
      options1: [],
      options2: [],
      options3: [],
      modelOptions: [],
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
      form: {
        conf_name: '',
        Mine_id: '',
        equipment_name: '',
      },
      rules:{
        conf_name: [
          { required: true, message: '请输入任务名称', trigger: 'blur' },
        ],
        Mine_id: [
          { required: true, message: '请选择单位名称', trigger: 'change' },
        ],
        equipment_name: [
          { required: true, message: '请选择报警设备', trigger: 'change' },
        ],
      }
    };
  },
  computed: {

  },
  created() {

  },
  methods: {
    modelKey(item) {
      if (!this._algorithmModelKeys) { this._algorithmModelKeys = new WeakMap(); this._algorithmModelSequence = 0; }
      if (!this._algorithmModelKeys.has(item)) this._algorithmModelKeys.set(item, 'model-' + (++this._algorithmModelSequence));
      return this._algorithmModelKeys.get(item);
    },
    onAdvancedDeviceChange() {
      this.onAlarmDeviceChange();
      this.addfn(1);
      this.syncModelStreams();
    },
    syncModelStreams() {
      var streamType = this.form.stream_type === 'main' || this.form.stream_type === 'sub' ? this.form.stream_type : null;
      this.jxlxlist.forEach((item) => this.$set(item, 'stream_type', streamType));
    },
    btnClick(index) {
      this.btnCli = index
    },
    addfn(e) {
      if(e == 1){
        this.jxlxlist = []
        this.jxlxlist.push({
          equipment_name: this.form.equipment_name,
          stream_type: this.form.stream_type,
          "Mine_id": "",
          "Equipment_id": "",
          "conf_area": '[]',
          "shield_status": "",
          "tem_conf_area": '[]',
          "draw_type": "1",
          "img_resolution": "",
          "image_draw_type": 1,
          "template_list_area": '[]',
          priority: "",
          run_time: "",
          mine_name: "",
          algorithm_name: "",
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
          template_data: '[]',
          test_type_id: "",
          label_list: '[]',
          amp: 10,
          alg_select_type: '3',
          model_two_data: '[]',
          model_two_type: '',
        })
      }else if (this.jxlxlist.length < 3) {
        this.jxlxlist.push({
          equipment_name: this.form.equipment_name,
          stream_type: this.form.stream_type,
          "Mine_id": "",
          "Equipment_id": "",
          "conf_area": '[]',
          "shield_status": "",
          "tem_conf_area": '[]',
          "draw_type": "1",
          "img_resolution": "",
          "image_draw_type": 1,
          "template_list_area": '[]',
          priority: "",
          run_time: "",
          mine_name: "",
          algorithm_name: "",
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
          template_data: '[]',
          test_type_id: "",
          label_list: '[]',
          amp: 10,
          alg_select_type: '3',
          model_two_data: '[]',
          model_two_type: '',
        })
      }
    },
    deletefn(e) {
      this.btnCli = 0
      this.jxlxlist.splice(e, 1);
    },
    countfns(index) {
      this.btnCli = index
      this.jxlxlist[index].algorithm_name = null;
      this.jxlxlist[index].label_list = [];
      for (var i = 0; i < this.dict.algorithm_list.length; i++) {
        if (this.dict.algorithm_list[i].id == this.jxlxlist[index].Algorithm_library_id) {
          this.jxlxlist[index].Algorithm_library_id = this.dict.algorithm_list[i].id;
          this.jxlxlist[index].algorithm_name = this.dict.algorithm_list[i].algorithm_name;
          const selectedId = this.dict.algorithm_list[i].id;
          const selectedModel = this.jxlxlist[index];
          this.$nextTick(() => {
            if (this._algorithmFormClosed || this.jxlxlist[index] !== selectedModel || selectedModel.Algorithm_library_id !== selectedId) return;
            const refs = this.$refs.canvasRef || [];
            const child = refs.find((item) => Number(item.indexnum) === index);
            if (child && typeof child.clearss === 'function') child.clearss(selectedId);
          });
          // this.ssa(index)
          // this.jxlxlist[index] = {
          //   equipment_name: this.dict.algorithm_list[i].algorithm_name,
          //   "Mine_id": "",
          //   "Equipment_id": "",
          //   "conf_area": '[]',
          //   "shield_status": "",
          //   "tem_conf_area": '[]',
          //   "draw_type": "1",
          //   "img_resolution": "",
          //   "image_draw_type": 1,
          //   "template_list_area": '[]',
          //   priority: "",
          //   run_time: "",
          //   mine_name: "",
          //   algorithm_name: "",
          //   Algorithm_library_id: this.dict.algorithm_list[i].Algorithm_library_id,
          //   type: 0,
          //   confidence: "60",
          //   tem_frames: "[27,37]",
          //   duration_time: 10,
          //   interval_time: 300,
          //   sensitivity: 25,
          //   defense_time_start: '00:00:00',
          //   defense_time_end: '23:59:59',
          //   image_count: 5,
          //   template_data: '[]',
          //   test_type_id: "",
          //   label_list: '[]',
          //   amp: 10,
          //   alg_select_type: '3',
          //   model_two_data: '[]',
          //   model_two_type: '',
          // }
        }
      }
    },
    goback() {
      this.$router.push({
        path: '/sfgl',
      })
    },
    sub_fn() {
      
      this.$refs['form'].validate(async (valid) => {
          if (valid) {
      // console.log(this.$refs.canvasRef);
      // this.$refs.canvasRef.setF()
      const refs = this.$refs.canvasRef || [];
      const children = this.jxlxlist.map((item, index) => refs.find((child) => Number(child.indexnum) === index));
      if (children.filter(child => child && child.algorithmPeopleCountVisible).length > 1) {
        this.$message({ message: '一个任务最多配置一个人数统计算法，请为另一计数版本创建独立任务', type: 'warning' }); return;
      }
      if (!children.length || children.some((child, index) => !child || !this.jxlxlist[index].algorithm_name)) {
        this.$message({ message: '请选择每一项解析类型并等待配置加载完成', type: 'warning' }); return;
      }
      if (this._algorithmSourceEdited && children.some((child) => child.loading || child.algorithmSnapshotReadyKey !== child.streamSourceKey)) {
        this.$message({ message: '请等待所有解析类型的码流图片加载完成后保存', type: 'warning' }); return;
      }
      try {
        const validatedModels = this.jxlxlist.slice();
        const validatedAlgorithmIds = validatedModels.map((item) => String(item.Algorithm_library_id));
        const validationSourceKey = this.streamSourceKey;
        const validModels = await Promise.all(children.map((child) => child.sub_fn()));
        if (validModels.some((result) => result === false) || this._algorithmFormClosed) return;
        if (validationSourceKey !== this.streamSourceKey || validatedModels.length !== this.jxlxlist.length || validatedModels.some((item, index) => item !== this.jxlxlist[index] || String(item.Algorithm_library_id) !== validatedAlgorithmIds[index])) {
          this.$message({ message: '配置内容已变化，请重新点击保存', type: 'warning' }); return;
        }
      } catch (error) {
        this.$message({ message: '配置数据尚未准备好，请刷新后重试', type: 'warning' }); return;
      }
      var objmap = {
        conf_name: this.form.conf_name,
        Mine_id: this.form.Mine_id,
        id: this.$route.query.id,
        equipment_name: this.form.equipment_name,
        stream_type: this.streamTypeRequest(),
        model_data: this.jxlxlist,
      }
      console.log(objmap);
        console.log(this.jxlxlist)
        if(this.$route.query.map){
          this.$http
            .post(this.$url.url_5000 + "/model_view/algorithm_update_models", objmap)
            .then((response) => {
              // console.log(response);
              if (response.data.code === 200) {
                this.$message({
                  message: response.data.msg,
                  type: "success",
                });
                this.goback()
                // this.axioss();
                // this.handleClose();
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
            .post(this.$url.url_5000 + "/model_view/algorithm_add_models", objmap)
            .then((response) => {
              // console.log(response);
              if (response.data.code === 200) {
                this.$message({
                  message: response.data.msg,
                  type: "success",
                });
                this.goback()
                // this.axioss();
                // this.handleClose();
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
                this.$message({
                  message: '算法配置数据有未填写项',
                  type: "warning",
                });
          }
        });
    },
    init() {//字典
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
            // console.log(9527,this.modelOptions)
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
  },
  mounted() {
    this.init()
    if(this.$route.query.map){
      var obj = JSON.parse(this.$route.query.map)
      this.conf_ids = this.$route.query.id
      this.form = obj
      this.restoreAlgorithmSource();
      this.jxlxlist = obj.model_data
      this.syncModelStreams();
      this.jxlxlist.forEach(item =>{
        if(!Array.isArray(item.label_list)){
          item.label_list = JSON.parse(item.label_list)
        }
      })
    }
  },
  beforeDestroy() {

  },
  destroyed() {

  },
};
</script>

<style lang="scss" scoped>
.is_active {
  background-color: #ecf5ff !important;
  border-color: #d9ecff !important;
  color: #409EFF !important;
}

.btnlist {
  width: 100%;
  height: 40px;

  div {
    width: 100px;
    height: 80%;
    float: left;
    margin-right: 12px;
    display: flex;
    align-items: center;
    font-size: 12px;
    justify-content: center;
    color: #858585;
    cursor: pointer;
    border: 1px solid #ebebeb;
    border-radius: 5px;
  }
}

.sfgl_child {
  width: 100%;
  height: 100%;
  background: #fff;
  overflow: hidden;
  overflow-y: scroll;
}

.sfpzs {
  width: 900px;
  height: calc(100% - 100px);
  margin: 0 auto;
}

.w-1\2 {
  width: calc(50% - 12px) !important;
  margin-left: 12px !important;
  float: left;
}

.jia_div {
  width: 640px;
  height: 360px;
  text-align: center;
  color: red;
  display: flex;
  align-items: center;
  justify-content: center;
}

.Bcanvas {
  width: 100%;
  height: calc(100% - 50px);
  border: 1px solid #e5e5e5;
  box-sizing: border-box;
  -moz-box-sizing: border-box;
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

#mycanvas,
#mycanvas1,
#mycanvas2,
#mycanvas3 {
  width: 640px;
  height: 360px;
  position: relative;
  top: -100%;
  left: 0;
  z-index: 10;
}
  /* Parent fields are scoped to this form; child drawing layouts stay independent. */
  .algorithm-config-page { min-height: 0; overflow: auto; overscroll-behavior: contain; }
  .algorithm-config-page .sfpzs { width: 100%; max-width: 1120px; height: auto; margin: 0 auto; padding: 4px 24px 32px; box-sizing: border-box; }
  .algorithm-config-page .sfpzs ::v-deep > .el-form > .el-form-item {
    max-width: 680px; margin: 0 auto 20px !important; padding-top: 0 !important;
    > .el-form-item__label { color: #42516a; font-size: 13px; line-height: 32px; padding-right: 16px; }
    > .el-form-item__content {
      line-height: 32px; min-width: 0;
      > .el-select, > .el-cascader, > .el-input { width: 100% !important; max-width: 520px; float: none !important; vertical-align: top; }
      > .el-select .el-input__inner, > .el-cascader .el-input__inner, > .el-input .el-input__inner { height: 32px; line-height: 32px; }
      .el-cascader__label { padding-right: 30px; }
    }
    &.algorithm-model-selector > .el-form-item__content > .el-select { width: calc(100% - 84px) !important; display: inline-block; vertical-align: middle; }
  }
  .algorithm-config-page .algorithm-field-hint,
  .algorithm-config-page .algorithm-stream-help { display: block; width: 100% !important; max-width: 520px; clear: both; float: none !important; margin: 6px 0 0 !important; padding: 0; color: #78869a !important; font-size: 12px; line-height: 1.65; overflow-wrap: break-word; }
  .algorithm-config-page .algorithm-model-actions { display: inline-flex; align-items: center; gap: 8px; width: auto !important; margin: 0 !important; float: none; vertical-align: middle; }
  .algorithm-config-page .algorithm-model-actions ::v-deep > .el-button { margin-left: 0; }
  .algorithm-config-page .algorithm-model-panel { height: auto; overflow: visible; margin-top: 14px; }
  .algorithm-config-page .btnlist > div { border: 1px solid #dce4ef; border-radius: 6px; box-sizing: border-box; color: #52637c; font-size: 13px; }
  .algorithm-config-page .algorithm-action-buttons { display: flex; align-items: center; gap: 10px; max-width: 520px; margin: 0 !important; padding: 18px 0 4px; border-top: 1px solid #e8edf4; }
  .algorithm-config-page .algorithm-action-buttons ::v-deep > .el-button { min-width: 88px; margin-left: 0; padding: 9px 18px; }
  @media (max-width: 1100px) { .algorithm-config-page .sfpzs { padding: 4px 16px 28px; } }
  @media (max-width: 760px) {
    .algorithm-config-page .sfpzs { padding: 4px 12px 24px; }
    .algorithm-config-page .sfpzs ::v-deep > .el-form > .el-form-item {
      > .el-form-item__label { display: block; width: auto !important; float: none; text-align: left; line-height: 22px; padding: 0 0 6px; }
      > .el-form-item__content { margin-left: 0 !important; }
    }
  }
  @media (max-height: 720px) { .algorithm-config-page .sfpzs { padding-top: 0; padding-bottom: 24px; } .algorithm-config-page .sfpzs ::v-deep > .el-form > .el-form-item { margin-bottom: 16px !important; } }
</style>
