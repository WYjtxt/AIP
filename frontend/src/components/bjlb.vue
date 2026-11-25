<!-- 报警列表，+轮播图 -->
<template>
  <div class="bjlb">
    <div class="serch">
      <el-form class="demo-ruleForm">
        <el-form-item label="单位名称" label-width="110px">
          <el-select v-model="mkname" placeholder="请选择单位名称" size="small" @change="handleSelect1(),queryfn()" clearable filterable>
            <span slot="prefix" class="select-icon">
              <img class="selectImg" src="../img/home/alarmlist/mk.png" alt="">
            </span>
            <el-option v-for="item in options1" :key="item.id" :label="item.mine_name" :value="item.id"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="报警设备" label-width="110px">
          <img src="../img/home/alarmlist/video.png" alt="" class="cascaderImg">
          <el-cascader style="width: 100%" v-model="jkdname" :options="options2" :props="props" clearable @change="queryfn()" size="small">
          </el-cascader>
        </el-form-item>
        <!-- <el-form-item label="算法" label-width="60px">
          <el-select v-model="algorithm_id" placeholder="请选算法" size="small" clearable filterable @change="axioss()">
            <el-option v-for="item in options4" :key="item.id" :label="item.algorithm_name" :value="item.id"> </el-option>
          </el-select>
        </el-form-item> -->
        <el-form-item label="解析类型" label-width="110px">
          <el-select v-model="queryParams.algorithm_id" placeholder="请选解析类型" size="small" clearable filterable @change="jxlxfn()">
            <span slot="prefix" class="select-icon">
              <img class="selectImg" src="../img/home/alarmlist/algorithm.png" alt="">
            </span>
            <!-- <el-option v-for="item in options5" :key="item.id" :label="item.conf_name" :value="item.id"></el-option> -->
            <el-option v-for="item in options5" :key="'解析类型'+item.id" :label="item.algorithm_name" :value="item.id"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="报警类别" label-width="110px">
          <el-select v-model="queryParams.template_type_id" placeholder="请选择报警类别" size="small" clearable filterable @change="queryfn()">
            <span slot="prefix" class="select-icon">
              <img class="selectImg" src="../img/home/alarmlist/algorithm.png" alt="">
            </span>
            <el-option v-for="item in modelTypeOptions" :key="item.id+item.model_type_name" :label="item.model_type_name" :value="item.id"> </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="处置状态" label-width="110px">
          <el-select v-model="queryParams.disposal_status" placeholder="请选择处置状态" size="small" clearable filterable @change="queryfn()">
            <span slot="prefix" class="select-icon">
              <img class="selectImg" src="../img/home/alarmlist/algorithm.png" alt="">
            </span>
            <el-option v-for="item in czzt" :key="item.id" :label="item.value" :value="item.id"> </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="审批状态" label-width="110px">
          <el-select v-model="queryParams.approval_status" placeholder="请选择审批状态" size="small" clearable filterable @change="queryfn()">
            <span slot="prefix" class="select-icon">
              <img class="selectImg" src="../img/home/alarmlist/algorithm.png" alt="">
            </span>
            <el-option v-for="item in spzt" :key="item.id" :label="item.value" :value="item.id"> </el-option>
          </el-select>
        </el-form-item>
        <el-form-item v-if="queryParams.template_type_id != 3" label="报警等级" label-width="110px">
          <el-select v-model="bjtype" placeholder="请选择报警等级" size="small" clearable filterable @change="queryfn()">
            <span slot="prefix" class="select-icon">
              <img class="selectImg" src="../img/home/alarmlist/alarm.png" alt="">
            </span>
            <el-option v-for="item in options3" :key="item.id" :label="item.value" :value="item.id"> </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="报警时间" label-width="110px" prop="StartTime">
          <el-date-picker value-format="yyyy-MM-dd HH:mm:ss" type="datetime" v-model="StartTime" placeholder="报警开始时间" :picker-options="pickerOptions" size="small" clearable style="width: 190px" @change="queryfn()"></el-date-picker>
        </el-form-item>
        <el-form-item label="至" label-width="30px" prop="EndTime">
          <el-date-picker value-format="yyyy-MM-dd HH:mm:ss" type="datetime" v-model="EndTime" placeholder="报警结束时间" :picker-options="pickerOptions" size="small" clearable style="width: 190px" @change="queryfn()"></el-date-picker>
        </el-form-item>
        <div class="searchBtn">
          <el-button type="primary" size="small" icon="el-icon-search" @click="queryfn()">查询</el-button>
          <el-button type="success" size="small" icon="el-icon-upload2" @click="downLoad()">导出</el-button>
        </div>
      </el-form>
    </div>
    <div class="table">
      <div class="jia_table">
        <el-table v-loading="loading" ref="singleTable" :data="tableData" height="95%" style="width: 100%" :header-cell-style="{ background: '#f9fbff',height:'48.5px',fontSize:'14px' }">
          <el-table-column prop="index" label="序号" width="100">
            <template slot-scope="scope">
              {{ (Number(Number(pagenumber)-1)*Number(pagesize))+scope.$index + 1 }}
            </template>
          </el-table-column>
          <el-table-column prop="mine_name" label="单位名称" key="单位名称" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column prop="equipment_name" label="报警设备" key="报警设备" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column v-if="queryParams.template_type_id == 3" key="开始时间" prop="result_count_time" label="开始时间" :show-overflow-tooltip="true">
            <template slot-scope="scope">
              {{ formatGmtToDate(scope.row.result_count_time) }}
            </template>
          </el-table-column>
          <el-table-column v-if="queryParams.template_type_id == 3" key="结束时间" prop="res_time" label="结束时间" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column v-if="queryParams.template_type_id != 3" key="报警时间" prop="res_time" label="报警时间" :show-overflow-tooltip="true"></el-table-column>
          <!-- <el-table-column prop="algorithm_name" label="算法" :show-overflow-tooltip="true"></el-table-column> -->
          <el-table-column prop="conf_name" label="解析类型" key="解析类型" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column v-if="queryParams.template_type_id != 3" key="报警等级" prop="res_type" label="报警等级" :show-overflow-tooltip="true"></el-table-column>
          <!-- <el-table-column prop="model_name" label="报警类别" :show-overflow-tooltip="true"></el-table-column> -->
          <!-- <el-table-column prop="model_type" label="解析类型" :show-overflow-tooltip="true">
            <template slot-scope="scope">
              {{ (modelTypeDict.find(v=>v.data_value == scope.row.model_type)).data_label }}
            </template>
          </el-table-column> -->
          <el-table-column prop="approval_status" label="审批状态" :show-overflow-tooltip="true">
            <template slot-scope="scope">
              <span v-if="scope.row.approval_status == 0">正常</span>
              <span v-if="scope.row.approval_status == 1">误报</span>
            </template>
          </el-table-column>
          <el-table-column prop="disposal_time" label="审核时间" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column prop="disposal_status" label="处置状态" :show-overflow-tooltip="true">
            <template slot-scope="scope">
              <span v-if="scope.row.disposal_status == 0" style="color:red;">待处理</span>
              <span v-if="scope.row.disposal_status == 1">处理中</span>
              <span v-if="scope.row.disposal_status == 2" style="color:green;">已处理</span>
            </template>
          </el-table-column>
          <el-table-column prop="model_type_name" label="报警类别" :show-overflow-tooltip="true">
            <!-- <template slot-scope="scope">
              {{ (modelTypeDict.find(v=>v.data_value == scope.row.model_type)).data_label }}
            </template> -->
          </el-table-column>
          <el-table-column v-if="system == 'UWB'" key="标识卡" prop="uwb_id" label="标识卡" :show-overflow-tooltip="true"></el-table-column>
          <!-- <el-table-column v-if="queryParams.template_type_id == 3" key="统计监测数量" prop="result_count" label="统计检测数量" :show-overflow-tooltip="true"></el-table-column> -->
          <el-table-column v-if="queryParams.template_type_id == 3" key="进入数量" prop="Entering_num" label="统计数量" :show-overflow-tooltip="true"></el-table-column>
          <!-- <el-table-column v-if="queryParams.template_type_id == 3" key="离开数量" prop="Exiting_num" label="离开数量" :show-overflow-tooltip="true"></el-table-column> -->
          <!-- <el-table-column label="报警图片" width="110px" v-if="queryParams.template_type_id == 1">
            <template slot-scope="scope">
              <div style="width: 100px;height: 50px;" @click="handleOpenPictureOpen(scope.row)">
                <img :src="scope.row.carousel_images_list[0]" alt="暂无图片！" style="width: 100px; height: 50px; cursor: pointer" @click="handleLookImg(scope.row)" />
              </div>
            </template>
          </el-table-column> -->
          <el-table-column v-if="queryParams.template_type_id != 3" key="报警图片" label="报警图片" width="150px">
            <template slot-scope="scope">
              <!-- <el-button type="success" size="mini" @click="compileclick(scope.row)">查看</el-button> -->
              <div style="width: 120px;height: 60px;" @click="handleOpenPictureOpen(scope.row)">
                <!-- <img v-if="scope.row.id == 5" :src="scope.row.res_image" alt="暂无图片！" style="width: 100px; height: 50px; cursor: pointer" @click="handleLookImg(scope.row)" /> -->
                <!-- <images_loop :images="scope.row.carousel_images_list" style="cursor: pointer;"></images_loop> -->
                <carousel :imgList="scope.row.carousel_images_list" :key="'报警表格图片_'+scope.row.id+ '_' + Date.now()"></carousel>
              </div>
            </template>
          </el-table-column>
          <el-table-column v-if="queryParams.template_type_id != 3 && $store.state.user_role_id == 1" key="无标注框报警图片" label="无标注框报警图片" width="150px">
            <template slot-scope="scope">
              <!-- <el-button type="success" size="mini" @click="compileclick(scope.row)">查看</el-button> -->
              <div style="width: 120px;height: 60px;" @click="handleOpenPictureOpens(scope.row)">
                <!-- <img v-if="scope.row.id == 5" :src="scope.row.res_image" alt="暂无图片！" style="width: 100px; height: 50px; cursor: pointer" @click="handleLookImg(scope.row)" /> -->
                <!-- <images_loop :images="scope.row.carousel_images_list" style="cursor: pointer;"></images_loop> -->
                <carousel :imgList="scope.row.ori_images_list" :key="'报警表格图片_'+scope.row.id+ '_' + Date.now()"></carousel>
              </div>
            </template>
          </el-table-column>
          <!-- <el-table-column prop="res_frame_skip" label="花帧阈值测试" align='center' :show-overflow-tooltip="true"></el-table-column> -->
          <!-- <el-table-column label="报警视频" align='center'>
          <template slot-scope="scope">
            <el-button type="primary" size="mini" @click="compileclick(scope.row)">查看</el-button>
          </template>
        </el-table-column> -->
          <el-table-column label="报警详情" class-name="jia_btn_class">
            <template slot-scope="scope">
              <el-button v-if="scope.row.model_type_id == 3" type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenSpfx(scope.row,4)">视频分析回放</el-button>
              <el-button v-else type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenSpfx(scope.row,1)">视频分析回放</el-button>
              <el-button  type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenSpfx(scope.row,0)">报警回放</el-button>
              <!-- <el-button  type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenHKVS(scope.row)">报警回放</el-button> -->
            </template>
          </el-table-column>
          <el-table-column label="操作" class-name="jia_btn_class">
            <template slot-scope="scope">
              <el-button type="text" size="mini" @click="czfn(scope.row)">处置</el-button>
            </template>
          </el-table-column>
        </el-table>
        <!-- 如果没有数据，显示空状态 -->
        <el-empty v-if="tableData.length === 0" image="/static/img/home/placeholder_kong.png" :image-size="307" description="暂时没有数据~"></el-empty>
      </div>
      <div class="page">
        <el-pagination @current-change="handleCurrentChange" @size-change="handleSizeChange" :current-page="pagenumber" :page-size="pagesize" :page-sizes="pagesizes" background layout="total, prev, pager, next, jumper,sizes" :total="pagelength">
        </el-pagination>
      </div>
    </div>
    <el-dialog :title="imgTitle" :visible.sync="imgOpen" width="50%" :before-close="handleClose">
      <div style="width: 100%;height: auto;position: relative;">
        <img :src="imgData.res_image" alt="" style="width: 100%" />
        <el-button class="nav-button" type="text" style="scale: 3.0;position: absolute;top: 50%;left: 10px;margin-top: -30px;color: #fff;" @click="handleLookUpImg" icon="el-icon-arrow-left"></el-button>
        <el-button class="nav-button" type="text" style="scale: 3.0;position: absolute;top: 50%;right: 10px;margin-top: -30px;color: #fff;" @click="handleLookNextImg" icon="el-icon-arrow-right"></el-button>
      </div>
      <!-- <span slot="footer" class="dialog-footer">
        <el-button @click="dialogVisible = false">取 消</el-button>
        <el-button type="primary" @click="dialogVisible = false">确 定</el-button>
      </span> -->
    </el-dialog>
    <!-- 导出选项 -->
    <el-dialog title="导出提示" :visible.sync="dialogVisibleBox" append-to-body width="32%" center style="margin-top: 28vh !important">
      <div slot="title" class="dialog-header-title">
        <i class="el-icon-warning" style="color: orange"></i>
        <span>导出提示</span>
      </div>
      <p style="width: 100%; text-align: center">请选择导出方式</p>
      <div slot="footer" class="dialog-footer">
        <el-button @click="exportCurrentPage">导出当前页</el-button>
        <el-button @click="exportAll" type="primary">导出全部</el-button>
      </div>
    </el-dialog>
    <el-dialog :title="alarmVideoTitle" :visible.sync="alarmVideoOpen" width="1200px" :before-close="handleCloseAlarmVideo" class="jia_videoDia">
      <el-button size="mini" :disabled="alarmImageOffset === null" @click="seekAlarmImage" style="margin-bottom: 10px">{{ alarmImageLabel }}</el-button>
      <video ref="videoPlayer" id="videoPlayer" width="100%" height="100%" autoplay muted loop controls :src="ssfxVideoFlv">
      </video>
    </el-dialog>
    <el-dialog :title="pictureTitle" :visible.sync="pictureOpen" width="1200px" :before-close="handleClosePictureOpen" class="jia_videoDia">
      <!-- <images_loop :images="pictureArr" style="cursor: pointer;width: 1150px;height: 600px"></images_loop> -->
      <carousel2 :imgList="pictureArr" style="cursor: pointer;width: 1150px;height: 600px"></carousel2>
      <div class="btn_group">
        <el-button-group>
          <el-button type="primary" icon="el-icon-arrow-left" @click="handleUpImg">上一条</el-button>
          <el-button type="primary" @click="handleNextImg">下一条<i class="el-icon-arrow-right el-icon--right"></i></el-button>
        </el-button-group>
        <el-button-group>
          <el-button type="primary" icon="el-icon-download" @click="handleDownLoadImage"></el-button>
        </el-button-group>
      </div>
    </el-dialog>
    <el-dialog :title="HKVSTitle" :visible.sync="HKVSOpen" width="1050px" :before-close="handleCloseHKVSOpen" class="jia_videoDia">
      <div style="width: 1000px; height: 600px;">
        <HKVS ref="hkvs" :width="1000" :height="600" :scale="1"></HKVS>
      </div>
    </el-dialog>
    <el-dialog title="报警列表" :visible.sync="bjlbOpen" width="1200px" :before-close="handleCloseBjlbOpen" class="jia_videoDia">
      <div style="width: 100%;height: 700px;">
        <div class="serch">
          <el-form class="demo-ruleForm">
            <el-form-item label="单位名称" label-width="80px">
              <el-select v-model="mkname" placeholder="请选择单位名称" size="small" @change="handleSelect1()" clearable filterable>
                <span slot="prefix" class="select-icon">
                  <img class="selectImg" src="../img/home/alarmlist/mk.png" alt="">
                </span>
                <el-option v-for="item in options1" :key="item.id" :label="item.mine_name" :value="item.id"></el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="报警设备" label-width="90px">
              <img src="../img/home/alarmlist/video.png" alt="" class="cascaderImg">
              <el-cascader style="width: 100%" v-model="jkdname" :options="options2" :props="props" clearable @change="axioss()" size="small">
              </el-cascader>
            </el-form-item>
            <!-- <el-form-item label="算法" label-width="60px">
          <el-select v-model="algorithm_id" placeholder="请选算法" size="small" clearable filterable @change="axioss()">
            <el-option v-for="item in options4" :key="item.id" :label="item.algorithm_name" :value="item.id"> </el-option>
          </el-select>
        </el-form-item> -->
            <el-form-item label="解析类型" label-width="80px">
              <el-select v-model="queryParams.algorithm_id" placeholder="请选解析类型" size="small" clearable filterable @change="axioss()">
                <span slot="prefix" class="select-icon">
                  <img class="selectImg" src="../img/home/alarmlist/algorithm.png" alt="">
                </span>
                <el-option v-for="item in options5" :key="item.id" :label="item.conf_name" :value="item.id"></el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="报警类别" label-width="110px">
              <el-select v-model="queryParams.template_type_id" placeholder="请选择报警类别" size="small" clearable filterable @change="axioss()">
                <span slot="prefix" class="select-icon">
                  <img class="selectImg" src="../img/home/alarmlist/algorithm.png" alt="">
                </span>
                <el-option v-for="item in modelTypeOptions" :key="item.id+item.model_type_name" :label="item.model_type_name" :value="item.id"> </el-option>
              </el-select>
            </el-form-item>
            <el-form-item v-if="queryParams.template_type_id != 3" label="报警等级" label-width="80px">
              <el-select v-model="bjtype" placeholder="请选择报警等级" size="small" clearable filterable @change="axioss()">
                <span slot="prefix" class="select-icon">
                  <img class="selectImg" src="../img/home/alarmlist/alarm.png" alt="">
                </span>
                <el-option v-for="item in options3" :key="item.id" :label="item.value" :value="item.id"> </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="报警时间" label-width="80px" prop="StartTime">
              <el-date-picker value-format="yyyy-MM-dd HH:mm:ss" type="datetime" v-model="StartTime" placeholder="报警开始时间" :picker-options="pickerOptions" size="small" clearable style="width: 190px" @change="axioss()"></el-date-picker>
            </el-form-item>
            <el-form-item label="至" label-width="30px" prop="EndTime">
              <el-date-picker value-format="yyyy-MM-dd HH:mm:ss" type="datetime" v-model="EndTime" placeholder="报警结束时间" :picker-options="pickerOptions" size="small" clearable style="width: 190px" @change="axioss()"></el-date-picker>
            </el-form-item>
            <div class="searchBtn">
              <el-button type="primary" size="small" icon="el-icon-search" @click="axioss()">查询</el-button>
              <!-- <el-button type="success" size="small" icon="el-icon-upload2" @click="downLoad()">导出</el-button> -->
              <el-button type="danger" size="small" icon="el-icon-delete" @click="handleCloseBjlbList()">删除</el-button>
            </div>
          </el-form>
        </div>
        <el-table v-loading="loading" ref="singleTable" :data="tableData" height="75%" style="width: 100%;height: 530px;" :header-cell-style="{ background: '#f9fbff',height:'48.5px',fontSize:'14px' }" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="55">
          </el-table-column>
          <el-table-column prop="index" label="序号" width="100">
            <template slot-scope="scope">
              {{ (Number(Number(pagenumber)-1)*Number(pagesize))+scope.$index + 1 }}
            </template>
          </el-table-column>
          <el-table-column prop="mine_name" label="单位名称" key="单位名称" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column prop="equipment_name" label="报警设备" key="报警设备" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column v-if="queryParams.template_type_id == 3" key="开始时间" prop="result_count_time" label="开始时间" :show-overflow-tooltip="true">
            <template slot-scope="scope">
              {{ formatGmtToDate(scope.row.result_count_time) }}
            </template>
          </el-table-column>
          <el-table-column v-if="queryParams.template_type_id == 3" key="结束时间" prop="res_time" label="结束时间" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column v-if="queryParams.template_type_id != 3" key="报警时间" prop="res_time" label="报警时间" :show-overflow-tooltip="true"></el-table-column>
          <!-- <el-table-column prop="algorithm_name" label="算法" :show-overflow-tooltip="true"></el-table-column> -->
          <el-table-column prop="conf_name" label="解析类型" key="解析类型" :show-overflow-tooltip="true"></el-table-column>
          <el-table-column v-if="queryParams.template_type_id != 3" key="报警等级" prop="res_type" label="报警等级" :show-overflow-tooltip="true"></el-table-column>
          
          <!-- <el-table-column prop="model_name" label="报警类别" :show-overflow-tooltip="true"></el-table-column> -->
          <!-- <el-table-column prop="model_type" label="解析类型" :show-overflow-tooltip="true">
            <template slot-scope="scope">
              {{ (modelTypeDict.find(v=>v.data_value == scope.row.model_type)).data_label }}
            </template>
          </el-table-column> -->
          <el-table-column prop="model_type_name" label="报警类别" :show-overflow-tooltip="true">
            <!-- <template slot-scope="scope">
              {{ (modelTypeDict.find(v=>v.data_value == scope.row.model_type)).data_label }}
            </template> -->
          </el-table-column>
          <el-table-column v-if="queryParams.template_type_id == 3" key="统计监测数量" prop="result_count" label="统计检测数量" :show-overflow-tooltip="true"></el-table-column>
          <!-- <el-table-column label="报警图片" width="110px" v-if="queryParams.template_type_id == 1">
            <template slot-scope="scope">
              <div style="width: 100px;height: 50px;" @click="handleOpenPictureOpen(scope.row)">
                <img :src="scope.row.carousel_images_list[0]" alt="暂无图片！" style="width: 100px; height: 50px; cursor: pointer" @click="handleLookImg(scope.row)" />
              </div>
            </template>
          </el-table-column> -->
          <el-table-column v-if="queryParams.template_type_id != 3" key="报警图片" label="报警图片" width="150px">
            <template slot-scope="scope">
              <!-- <el-button type="success" size="mini" @click="compileclick(scope.row)">查看</el-button> -->
              <div style="width: 120px;height: 60px;" @click="handleOpenPictureOpen(scope.row)">
                <!-- <img v-if="scope.row.id == 5" :src="scope.row.res_image" alt="暂无图片！" style="width: 100px; height: 50px; cursor: pointer" @click="handleLookImg(scope.row)" /> -->
                <!-- <images_loop :images="scope.row.carousel_images_list" style="cursor: pointer;"></images_loop> -->
                <carousel :imgList="scope.row.carousel_images_list"></carousel>
              </div>
            </template>
          </el-table-column>
          <!-- <el-table-column prop="res_frame_skip" label="花帧阈值测试" align='center' :show-overflow-tooltip="true"></el-table-column> -->
          <!-- <el-table-column label="报警视频" align='center'>
          <template slot-scope="scope">
            <el-button type="primary" size="mini" @click="compileclick(scope.row)">查看</el-button>
          </template>
        </el-table-column> -->
          <el-table-column label="报警详情" class-name="jia_btn_class" >
            <template slot-scope="scope">
              <el-button v-if="scope.row.model_type_id == 3" type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenSpfx(scope.row,4)">视频分析回放</el-button>
              <el-button v-else type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenSpfx(scope.row,1)">视频分析回放</el-button>
              <el-button  type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenSpfx(scope.row,0)">报警回放</el-button>
              <!-- <el-button type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenSpfx(scope.row)">视频分析回放</el-button>
              <el-button type="text" icon="el-icon-video-camera" size="mini" @click="handleOpenHKVS(scope.row)">报警回放</el-button> -->
            </template>
          </el-table-column>
        </el-table>
        <br />
        <el-pagination @current-change="handleCurrentChange" @size-change="handleSizeChange" :current-page="pagenumber" :page-size="pagesize" :page-sizes="pagesizes" background layout="total, prev, pager, next, jumper,sizes" :total="pagelength" style="float: right;">
        </el-pagination>
        <br />
      </div>
    </el-dialog>

    <el-dialog title="处置" :visible.sync="dialogFormVisible_cz">
      <div class="box">
        <div class="left">
          <carousel :imgList="formcz.carousel_images_list" :key="'报警表格图片_'+formcz.id+ '_' + Date.now()"></carousel>
        </div>
        <div class="right">
          <el-form :model="formcz">
            <el-form-item label="审批状态" :label-width="formLabelWidth">
              <el-select v-model="formcz.approval_status" style="width: 100%;" placeholder="审批状态">
                <el-option label="正常" value="0"></el-option>
                <el-option label="误报" value="1"></el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="处置状态" :label-width="formLabelWidth">
              <el-select v-model="formcz.disposal_status" style="width: 100%;" placeholder="处置状态">
                <el-option label="待处理" value="0"></el-option>
                <el-option label="处理中" value="1"></el-option>
                <el-option label="已处理" value="2"></el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="审批意见" :label-width="formLabelWidth">
              <el-input v-model="formcz.approval_opinion" style="width: 100%;" type="textarea" :rows="2" placeholder="请输入审批意见"></el-input>
            </el-form-item>
            <el-form-item label="处置措施" :label-width="formLabelWidth">
              <el-input v-model="formcz.disposal_opinion" style="width: 100%;"  type="textarea" :rows="2" placeholder="请输入处置措施"></el-input>
            </el-form-item>
            <el-form-item label="处置时间" :label-width="formLabelWidth">
              <!-- <el-input v-model="formcz.disposal_time" style="width: 100%;" placeholder="请选择处置时间"></el-input> -->
              <el-date-picker
                v-model="formcz.disposal_time"
                type="datetime"
                :picker-options="pickerOptions"
                value-format="yyyy-MM-dd HH:mm:ss"
                style="width: 100%;"
                placeholder="选择日期时间">
              </el-date-picker>
            </el-form-item>
          </el-form>
        </div>
      </div>
      <div slot="footer" class="dialog-footer">
        <el-button @click="dialogFormVisible_cz = false">取 消</el-button>
        <el-button type="primary" @click="sure()">确 定</el-button>
      </div>
    </el-dialog>
    <div class="bj_list" v-if="loading_bj">
      <el-card class="box-card" style="height: 100%;">
        <div slot="header" class="clearfix">
          <span>报警信息</span>
          <el-button icon="el-icon-close" style="float: right; padding: 3px 0" type="text" @click="closefn"></el-button>
        </div>
        <div style="width:300px;height: 150px;background: #ccc;margin: 0 auto;margin-top: 12px;">
          <img style="width: 100%;height: 100%;background-size: 100% 100%;" :src="bj_forms.carousel_images" alt="">
        </div>
        <!-- <div class="bjitems">
          报警总数: <span>990</span>
        </div> -->
        <div class="bjitems">
          处置状态: 
          <!-- <span v-if="bj_forms.approval_status*1 == 0">正常</span>
          <span v-if="bj_forms.approval_status*1 == 1">误报</span> -->
          
          <span v-if="bj_forms.disposal_status*1 == 0" style="color:red;">待处理</span>
          <span v-if="bj_forms.disposal_status*1 == 1">处理中</span>
          <span v-if="bj_forms.disposal_status*1 == 2" style="color:green;">已处理</span>
        </div>
        <div class="bjitems">
          报警类型: <span>{{ bj_forms.algorithm_name }}</span>
        </div>
        <div class="bjitems">
          报警等级: <span>{{ bj_forms.res_type }}</span>
        </div>
        <div class="bjitems">
          报警地点: <span>{{ bj_forms.equipment_name }}</span>
        </div>
        <div class="bjitems">
          报警时间: <span>{{ bj_forms.res_time }}</span>
        </div>
        <div class="bjitems">
          处理时间: <span>{{ bj_forms.disposal_time }}</span>
        </div>
        
        <div class="bjitems_b">
          <el-button size="small" @click="lastfn">上一条</el-button>
          <el-button size="small" type="primary" @click="czfn(bj_forms)">处置报警</el-button>
          <el-button size="small" @click="nextfn">下一条</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script>
import { MessageBox } from "element-ui"
import images_loop from "./component/images_loop.vue";
import carousel from "./component/carousel.vue";
import carousel2 from "./component/carousel.vue";
import axios from "axios";
import flvjs from 'flv.js';
import { spfxApi } from '@/api/spfx.js';
import { dictApi } from '@/api/system/dict.js';
import { modelApi } from '@/api/model/index';
import { hkvsApi } from "@/api/hkvs/index";
import { bjlbApi } from "@/api/bjlb";
import HKVS from "./HK/hkvideo/new/oldVideo.vue"
import JSZip from 'jszip';

export default {
  name: "bjlb",
  components: {
    images_loop,
    carousel,
    carousel2,
    HKVS,
  },
  data() {
    return {
      timer:null,
      loading_bj: false,
      bjobj:[],
      bj_index: 0,
      bj_forms:{},
      czzt: [
        { "id": "0", "value": "待处理"},
        { "id": "1", "value": "处理中"},
        { "id": "2", "value": "已处理"},
      ],
      spzt: [
        { "id": "0", "value": "正常"},
        { "id": "1", "value": "误报"},
      ],
      formLabelWidth: '100px',
      dialogFormVisible_cz: false,
      formcz:{
        approval_status: '',
        disposal_status: '',
        approval_opinion: '',
        disposal_opinion: '',
        disposal_time: '',
      },
      system: window.wgParameter.system,
      clickType:'',
      StartTime: "",
      EndTime: "",
      mkname: "",
      jkdname: "",
      bjtype: "",
      algorithm_id: "",
      Algorithm_config_id: "",
      queryParams: {
        template_type_id: '',
        algorithm_id: '',
      },
      options1: [],
      options2: [],
      options3: [],
      options4: [],
      options5: [],//解析类型字典
      props: {
        checkStrictly: false,
        emitPath: false,
        value: "id",
        label: "equipment_name",
      },
      loading: false,
      tableData: [],
      tableDataAll: [],
      currentPage: 1, //默认开始页面 this.$store.state.pages  $store.state.loginuser
      pagenumber: 1, //第几页
      pagesize: 15, //每页的数据条数
      pagelength: 0, //默认数据总数
      pagesizes: [15, 35, 50, 100, 150, 200, 300],
      //点击查看图片相关参数
      imgTitle: "",
      imgOpen: false,
      imgData: {},
      video_page_id: null,
      //导出弹窗
      dialogVisibleBox: false,
      excelName: "报警列表",
      column: [
        {
          title: "序号",
          key: "index",
          type: "text",
        },
        {
          title: "单位名称",
          key: "mine_name",
          type: "text",
        },
        {
          title: "报警设备",
          key: "equipment_name",
          type: "text",
        },
        {
          title: "时间",
          key: "res_time",
          type: "text",
        },
        {
          title: "算法",
          key: "algorithm_name",
          type: "text",
        },
        {
          title: "算法名称",
          key: "conf_name",
          type: "text",
        },


        {
          title: "报警等级",
          key: "res_type",
          type: "text",
        },
        {
          title: "报警图片",
          key: "res_image",
          type: "image",
          width: 100,
          height: 50,
        },
      ],
      pickerOptions: {
        disabledDate(time) {
          // 获取当前日期的零时零分零秒
          const today = new Date();
          today.setHours(0, 0, 0, 0);

          // 计算一个月前的日期，并将其设置为当天的零时零分零秒
          const oneMonthAgo = new Date(today);
          oneMonthAgo.setMonth(oneMonthAgo.getMonth() - 1);
          oneMonthAgo.setHours(0, 0, 0, 0);

          // 禁用今天之后的所有日期和一个月前的所有日期
          return time.getTime() > today.getTime() || time.getTime() < oneMonthAgo.getTime();
        },
        disabledTime(time) {
          // 当 StartTime 为空时，不作任何限制
          if (!this.StartTime) return false;

          try {
            // 尝试将 StartTime 字符串转换为 Date 对象
            const startTime = new Date(this.StartTime);
            if (isNaN(startTime.getTime())) throw new Error('Invalid date format');

            // 禁止选择早于 StartTime 的时间
            return time.getTime() < startTime.getTime();
          } catch (e) {
            console.error('Error parsing StartTime:', e);
            return false; // 或者 true，取决于你希望如何处理无效的 StartTime
          }
        },
      },
      alarmVideoOpen: false,
      alarmVideoTitle: '',
      interTime: null,
      pictureTitle: '',
      pictureOpen: false,
      pictureArr: [],
      pictureArrId: 0,
      modelTypeDict: [],//解析类型字典
      modelTypeOptions: [],//模板大类
      HKVSTitle: '',
      HKVSOpen: false,
      ssfxVideo: '/static/img/video/AIspfx.mp4',
      ssfxVideoFlv: '',
      alarmImageOffset: null,
      alarmImageLabel: '定位报警画面',
      flvPlayer: null,
      bjlbOpen: false,//报警列表弹窗开关
      multipleSelection: [],
    };
  },
  watch: {
    // 监听StartTime变化
    StartTime(newVal, oldVal) {
      this.validateTimeRange();
    },
    // 监听EndTime变化
    EndTime(newVal, oldVal) {
      this.validateTimeRange();
    },

  },
  methods: {
    lastfn(){
      if(this.bj_index == 0){
        this.bj_index=0
        this.$message({
          message: '当前报警已经是第一条!',
          type: "warning",
        });
      }else{
        this.bj_index--
        this.bj_forms = this.bjobj[this.bj_index]
      }
    },
    nextfn(){
      this.bj_index++
      if(this.bjobj.length == this.bj_index){
        this.bj_index=this.bjobj.length-1
        this.$message({
          message: '当前报警已经是最后一条!',
          type: "warning",
        });
      }else{
        this.bj_forms = this.bjobj[this.bj_index]
      }
    },
    closefn(){
      this.loading_bj=false
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/algo_result_pop",
          {
            params: {
              close_signal: true,
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((res) => {
          
        })
        .catch(function (res) {
          console.log("rek=====", res);
        });
    },
    bjfns() {
      this.bj_forms = {}
      this.bj_index = 0;
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/algo_result_pop",
          {
            params: {
              close_signal:'',
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((res) => {
          if(res.data.data.length>0){
            // res.data.data[0].carousel_images_list = 'http://192.168.113.35:9001/data2/sophon/ModelZoo/YOLOv5/python/bingxing_model/normal_model/result/test/images/alarm_2026-01-23_15-11-42.jpg'
            // res.data.data[1].carousel_images_list = 'http://192.168.113.35:9001/data2/sophon/ModelZoo/YOLOv5/python/bingxing_model/normal_model/result/test/images/alarm_2026-01-23_15-11-54.jpg'
            this.bjobj = res.data.data.map(v => {
              return {
                ...v,
                carousel_images_list: JSON.parse(v.carousel_images_list.replace(/'/g, '"')),
              }
            });
            this.bj_forms = this.bjobj[this.bj_index]

            this.$nextTick(()=>{
              var str = this.bj_forms.equipment_name +'触发'+ this.bj_forms.algorithm_name+'报警'
              var ssu = new SpeechSynthesisUtterance(str);
              window.speechSynthesis.speak(ssu);
              this.loading_bj = true
            })
          }
        })
        .catch(function (res) {
          console.log("rek=====", res);
        });
    },
    czfn(row){
      console.log(row)
      this.formcz = {
        Algorithm_result_id: row.Algorithm_result_id,
        carousel_images_list: row.carousel_images_list,
        approval_status: row.approval_status,
        disposal_status: row.disposal_status,
        approval_opinion: row.approval_opinion,
        disposal_opinion: row.disposal_opinion,
        disposal_time: row.disposal_time,
      }
      if(row.approval_status == null){
        this.formcz.approval_status = '0'
      }
      if(row.disposal_status == null){
        this.formcz.disposal_status = '0'
      }
      if(row.approval_opinion == null){
        this.formcz.approval_opinion = ''
      }
      if(row.disposal_opinion == null){
        this.formcz.disposal_opinion = ''
      }
        const now = new Date();
      this.formcz.disposal_time = this.formatDate(now);
      this.$nextTick(()=>{
        this.dialogFormVisible_cz = true;
      })
    },
    sure(){
      // this.formcz.approval_opinion = 333333333333
      var obg ={
        id: this.formcz.Algorithm_result_id,
        approval_status: this.formcz.approval_status,
        disposal_status: this.formcz.disposal_status,
        approval_opinion: this.formcz.approval_opinion,
        disposal_opinion: this.formcz.disposal_opinion,
        disposal_time: this.formcz.disposal_time,
      }
      
        this.$http
          .post(this.$url.url_5000 + "/model_view/algorithm_result_manage", obg)
          .then((response) => {
            // console.log(response);
            if (response.data.code === 200) {
              this.$message({
                message: response.data.msg,
                type: "success",
              });
              this.dialogFormVisible_cz = false
              this.axioss();
              this.bjfns()
              // this.handleClose();
            } else {
              this.$message({
                message: response.data.msg,
                type: "warning",
              });
            }
          })
        .catch(function (response) {
          console.log("rek=====", response);
        });
    },
    validateTimeRange() {
      // 验证开始时间和结束时间
      const startTime = this.StartTime ? new Date(this.StartTime) : null;
      const endTime = this.EndTime ? new Date(this.EndTime) : null;

      if (startTime && endTime) {
        if (endTime < startTime) {
          this.EndTime = ''; // 清空EndTime
          this.$message.error('结束时间必须晚于开始时间');
        }
      }
    },
    handleCurrentChange(val) {
      console.log(val);
      this.pagenumber = val;
      this.axioss();
    },
    handleSizeChange(val) {
      console.log(val);
      this.pagesize = val;
      this.axioss();
    },
    handleSelect1() {
      // let param = new URLSearchParams();
      // param.append("mine_id", this.mkname);
      this.jkdname = "";
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/type_select",
          {
            params: {
              mine_id: this.mkname,
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          console.log(response);
          if (response.data.code === 200) {
            this.options1 = response.data.mine_list;
            this.options2 = response.data.equipment_list;
            this.options3 = response.data.type_list;
            this.options4 = response.data.algorithm_list;
            // this.options5 = response.data.algorithm_conf_list;
            this.options5 = response.data.algorithm_list;
            
    if (this.$route.query.Algorithm_config_id) {
      this.Algorithm_config_id = this.$route.query.Algorithm_config_id;
      if(this.$route.query.type){
        this.options5.forEach((item)=>{
          if(item.algorithm_name == '人数统计' || item.algorithm_name == '车辆统计'){
            this.queryParams.algorithm_id = item.id
          }
        })
        this.queryParams.template_type_id = 3
      }
    }
          }
        })
        .catch(function (response) {
          console.log(response);
        });
    },
    handleSelect2() { },
    handleSelect3() { },
    jxlxfn(){
      this.options5.forEach((item)=>{
        if(item.id == this.queryParams.algorithm_id){
          if(item.algorithm_name == '人数统计' || item.algorithm_name == '车辆统计'){
            this.queryParams.template_type_id = 3
          }
          // if(item.algorithm_name == '人数统计' || item.algorithm_name == '车辆统计'){
          //   this.queryParams.template_type_id = 3
          //   this.queryfn()
          // }else{
          //   this.queryfn()
          // }
        }
      })
      this.$nextTick(()=>{
        this.queryfn()
      })
    },
    queryfn(){
      this.pagenumber = 1;
      this.axioss()
    },
    axioss() {
      this.loading = true
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/algorithm_result",
          {
            params: {
              mine_id: this.mkname,
              equipment_id: this.jkdname,
              type: this.bjtype,
              start_time: this.StartTime,
              end_time: this.EndTime,
              page: this.pagenumber,
              per_page: this.pagesize,
              Algorithm_config_id:this.Algorithm_config_id,
              ...this.queryParams
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          console.log(response);
          if (response.data.code === 200) {
            this.tableData = response.data.data_list.data.map(v => {
              return {
                ...v,
                carousel_images_list: JSON.parse(v.carousel_images_list.replace(/'/g, '"')),
                ori_images_list: JSON.parse(v.ori_images_list.replace(/'/g, '"')),
              }
            });
            console.log(this.tableData)
            this.pagelength = response.data.data_list.total_items;
            this.loading = false
          }
        })
        .catch(function (response) {
          console.log("rek=====", response);
        });
    },
    formatDate(date) {
      const y = date.getFullYear();
      const m = String(date.getMonth() + 1).padStart(2, '0');
      const d = String(date.getDate()).padStart(2, '0');
      const h = String(date.getHours()).padStart(2, '0');
      const min = String(date.getMinutes()).padStart(2, '0');
      const s = String(date.getSeconds()).padStart(2, '0');
      return `${y}-${m}-${d} ${h}:${min}:${s}`;
    },
    formatGmtToDate(gmtString) {
      const date = new Date(gmtString);

      // 获取年份、月份（需要加1）、日期
      const year = date.getUTCFullYear();
      let month = date.getUTCMonth() + 1;
      let day = date.getUTCDate();

      // 获取小时、分钟和秒（使用 UTC 方法获取 GMT 时间）
      let hours = date.getUTCHours();
      let minutes = date.getUTCMinutes();
      let seconds = date.getUTCSeconds();

      // 使用 padStart 确保月份、日期、小时、分钟和秒都是两位数
      month = String(month).padStart(2, '0');
      day = String(day).padStart(2, '0');
      hours = String(hours).padStart(2, '0');
      minutes = String(minutes).padStart(2, '0');
      seconds = String(seconds).padStart(2, '0');

      // 返回格式化后的 GMT 时间字符串
      const gmtTime = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;

      // 同样方法获取本地时间
      // let localHours = String(date.getHours()).padStart(2, '0');
      // let localMinutes = String(date.getMinutes()).padStart(2, '0');
      // let localSeconds = String(date.getSeconds()).padStart(2, '0');
      // const localTime = `${year}-${month}-${day} ${localHours}:${localMinutes}:${localSeconds}`;

      return gmtTime;
    },
    convertGmtToFormattedLocalTime(gmtTimeString) {
      // 创建一个新的 Date 对象，传入 GMT 时间字符串
      const gmtDate = new Date(gmtTimeString);

      // 检查是否成功创建了有效的 Date 对象
      if (isNaN(gmtDate.getTime())) {
        throw new Error('Invalid date string');
      }

      // 获取各个时间组件
      const year = gmtDate.getFullYear();
      const month = String(gmtDate.getMonth() + 1).padStart(2, '0'); // 月份从0开始，需要加1，并确保两位数
      const day = String(gmtDate.getDate()).padStart(2, '0'); // 确保两位数
      const hours = String(gmtDate.getHours()).padStart(2, '0'); // 确保两位数
      const minutes = String(gmtDate.getMinutes()).padStart(2, '0'); // 确保两位数
      const seconds = String(gmtDate.getSeconds()).padStart(2, '0'); // 确保两位数

      // 组合成所需的格式
      const formattedLocalTime = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
      console.log("==============================", formattedLocalTime)

      return formattedLocalTime;
    },
    //查看图片
    handleLookImg(data) {
      console.log(data)
      this.imgData = data;
      this.imgTitle = data.conf_name + "_" + data.mine_name + "_" + data.equipment_name + "_" + data.res_type;
      this.imgOpen = true;
    },
    // 查看下一张图片
    handleLookNextImg() {
      const currentIndex = this.tableData.findIndex(item => item === this.imgData);
      const nextIndex = (currentIndex + 1) % this.tableData.length; // 确保在数据末尾循环到开头
      this.imgData = this.tableData[nextIndex];
      this.imgTitle = this.imgData.conf_name + "_" + this.imgData.mine_name + "_" + this.imgData.equipment_name + "_" + this.imgData.res_type;
    },

    // 查看上一张图片
    handleLookUpImg() {
      const currentIndex = this.tableData.findIndex(item => item === this.imgData);
      const prevIndex = (currentIndex - 1 + this.tableData.length) % this.tableData.length; // 确保在数据开头循环到末尾
      this.imgData = this.tableData[prevIndex];
      this.imgTitle = this.imgData.conf_name + "_" + this.imgData.mine_name + "_" + this.imgData.equipment_name + "_" + this.imgData.res_type;
    },
    handleClose() {
      this.imgOpen = false;
    },
    downLoad() {
      this.dialogVisibleBox = true;
    },
    // 导出当前页
    exportCurrentPage() {
      // const excelName = "视频质量诊断"; //文件名称
      const newData = JSON.parse(JSON.stringify(this.tableData));
      let index = 0;
      newData.forEach((item) => {
        item.index = index += 1;
      });
      const newData2 = newData.map(v => {
        return {
          ...v,
          res_image: v.carousel_images_list.length > 0 ? v.carousel_images_list[0] : ''
        }
      })
      this.$table2excel(this.column, newData2, this.excelName); //生成Excel表格，自动下载
      this.$message({
        type: "success",
        message: "导出成功!",
      });
      this.dialogVisibleBox = false;
    },
    // 导出全部
    exportAll() {
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/algorithm_result",
          {
            params: {
              mine_id: this.mkname,
              equipment_id: this.jkdname,
              type: this.bjtype,
              start_time: this.StartTime,
              end_time: this.EndTime,
              page: 1,
              per_page: this.pagelength,
              algorithm_id: this.algorithm_id,
              Algorithm_config_id:this.Algorithm_config_id,
            },
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          if (response.data.code === 200) {
            this.tableDataAll = response.data.data_list.data;
            const newData1 = JSON.parse(JSON.stringify(this.tableDataAll));
            let index = 0;
            newData1.forEach((item) => {
              item.index = index += 1;
            });
            console.log("newData1", newData1)
            const newData2 = newData1.map(v => {
              v.carousel_images_list = JSON.parse(v.carousel_images_list.replace(/'/g, '"'))
              return {
                ...v,
                res_image: v.carousel_images_list.length > 0 ? v.carousel_images_list[0] : ''
              }
            })
            console.log("newData2", newData2)
            this.$table2excel(this.column, newData2, this.excelName); //生成Excel表格，自动下载
            this.$message({
              type: "success",
              message: "导出成功!",
            });
            this.dialogVisibleBox = false;
          }
        })
        .catch(function (response) {
          console.log("rek=====", response);
        });
    },
    removeFileExtension(filename) {
      // 使用正则表达式匹配最后一个点号及其后面的内容（假设为文件扩展名）
      return filename.replace(/\.[^/.]+$/, '');
    },
    // 按报警时间回放；人数统计 det_type=4 使用对应记录的存档视频。
    async handleOpenSpfx(row, requestedType) {
  // Freeze the visible image before any await or carousel timer can advance.
  const selectedImage = this.snapshotAlarmPlaybackImage(row);
  const stopped = this.stopVideo();
  const generation = this._alarmPlaybackGeneration;
  const current = () => !this._alarmPlaybackDisposed && generation === this._alarmPlaybackGeneration;
  await stopped;
  if (!current()) return;
  const monitorId = Number(row && row.Equipment_id);
  const alarmId = Number(row && row.Algorithm_result_id);
  if (!Number.isSafeInteger(monitorId) || monitorId <= 0 || !Number.isSafeInteger(alarmId) || alarmId <= 0) {
    this.$message.error('报警记录编号或监控点编号无效，请刷新列表后重试');
    return;
  }
  const archived = Boolean(row.warning_video || row.res_video);
  const detType = archived ? 4 : requestedType;
  const params = {
    Algorithm_result_id: alarmId, algorithm_name: row.algorithm_name,
    width: 1920, height: 1080, baud_b: 1000, frame_r: 25,
    det_type: detType, stream_data_flag: 1,
    em_id: JSON.stringify([monitorId]), video_status: 2,
    ...this.calculateTimeAroundssfx(row.res_time),
  };
  if (Number(row.model_type_id) === 3) {
    params.start_time = this.calculateTimeAroundssfxs(row.result_count_time || row.res_time);
    params.end_time = this.calculateTimeAroundssfxs(row.res_time);
  }
  let session = null;
  if (!archived && Number(detType) !== 3 && Number(detType) !== 4) {
    const bytes = new Uint8Array(32);
    window.crypto.getRandomValues(bytes);
    session = Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('');
    params.session_token = session;
    this._alarmPlaybackSession = session;
  }
  const controller = new AbortController();
  this._alarmPlaybackController = controller;
  try {
    let response;
    for (let attempt = 0; attempt < 21 && current(); attempt++) {
      response = await this.$http.get(this.$url.url_5000 + '/video_view/real_time_video', {
        params, signal: controller.signal, timeout: 20000,
      });
      if (!current()) return;
      if (Number(response.data.code) !== 202) break;
      if (attempt === 20) throw new Error('回放准备超时，请稍后重试');
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    if (!current()) return;
    const body = response.data || {};
    if (Number(body.code) !== 200) throw new Error(body.msg || '回放准备失败，请稍后重试');
    const item = body.flv_data && body.flv_data[0];
    if (!item || typeof item.flv_url !== 'string' || !item.flv_url) throw new Error('该报警没有可用的视频地址');
    if (body.playback_source === 'archive' &&
        (Number(body.alarm_record_id) !== alarmId || Number(body.equipment_id) !== monitorId)) {
      throw new Error('回放视频与所选报警记录不一致，请刷新列表后重试');
    }
    const temporary = body.playback_source !== 'archive' && Boolean(session);
    if (temporary && body.session_token !== session) throw new Error('回放会话校验失败，请刷新后重试');
    if (!temporary) this._alarmPlaybackSession = null;
    this.alarmVideoTitle = (Number(requestedType) === 0 ? '报警回放' : '视频分析回放') +
      (body.playback_source === 'archive' ? (body.media_integrity === 'verified' ? ' · 完整事件录像 · 报警 #' : ' · 历史存档 · 报警 #') + alarmId : '');
    let imageOffset = body.alarm_image_offset_seconds;
    let imageLabel = '定位首张报警图片';
    const anchors = body.evidence_frames;
    if (selectedImage.reliable && selectedImage.url && Array.isArray(anchors) &&
        anchors.length === selectedImage.count && selectedImage.index < anchors.length) {
      const candidate = anchors[selectedImage.index] && anchors[selectedImage.index].offset_seconds;
      if (typeof candidate === 'number' && Number.isFinite(candidate) && candidate >= 0) {
        imageOffset = candidate;
        imageLabel = '定位第' + (selectedImage.index + 1) + '张报警图片';
        this.alarmVideoTitle += ' · 图片 ' + (selectedImage.index + 1) + '/' + selectedImage.count;
      }
    }
    this.alarmImageOffset = typeof imageOffset === 'number' && Number.isFinite(imageOffset) && imageOffset >= 0 ? imageOffset : null;
    this.alarmImageLabel = this.alarmImageOffset === null ? '定位报警画面' : imageLabel;
    this.alarmVideoOpen = true;
    this.ssfxVideoFlv = item.flv_url;
    if (temporary) this.startAlarmPlaybackHeartbeat(session, generation);
    this.$nextTick(() => {
      if (!current()) return;
      const video = this.$refs.videoPlayer;
      if (video) {
        video.onerror = () => {
          if (current()) this.$message.error('该报警存档无法播放，请检查文件是否存在及视频编码');
        };
        const mapped = window.AiMonitorTransport && window.AiMonitorTransport.normalize ? window.AiMonitorTransport.normalize(item.flv_url) : item.flv_url;
        const expected = new URL(mapped, window.location.href).href;
        let positioned = false;
        const seek = force => {
          if (!current() || this.alarmImageOffset === null || video.readyState < 1 ||
              !video.currentSrc || new URL(video.currentSrc, window.location.href).href !== expected ||
              (!force && positioned)) return false;
          const offset = this.alarmImageOffset;
          if (Number.isFinite(video.duration) && offset >= video.duration) return false;
          try { video.currentTime = offset; positioned = true; return true; } catch (_) { return false; }
        };
        video.onloadedmetadata = () => seek(false);
        video.oncanplay = () => seek(false);
        this._alarmPlaybackSeek = () => seek(true);
        video.load();
      }
    });
  } catch (error) {
    if (current()) {
      this.$message.error(error.response && error.response.data && error.response.data.msg || error.message || '回放请求失败');
      this.stopVideo();
    }
  } finally {
    if (this._alarmPlaybackController === controller) this._alarmPlaybackController = null;
  }
},
    startAlarmPlaybackHeartbeat(session, generation) {
      clearInterval(this._alarmPlaybackHeartbeat);
      this._alarmPlaybackHeartbeat = setInterval(() => {
        if (this._alarmPlaybackDisposed || generation !== this._alarmPlaybackGeneration || this._alarmPlaybackHeartbeatBusy) return;
        this._alarmPlaybackHeartbeatBusy = true;
        this.$http.post(this.$url.url_5000 + '/video_view/real_time_video_keepalive', { session_token: session }, { timeout: 8000 })
          .then(response => {
            if (generation === this._alarmPlaybackGeneration && Number(response.data.code) === 410) {
              this.$message.warning('临时回放会话已结束，请重新打开');
              this.stopVideo();
            }
          }).catch(() => { /* A brief network interruption can recover before the lease expires. */ })
          .finally(() => { this._alarmPlaybackHeartbeatBusy = false; });
      }, 20000);
    },
    seekAlarmImage() { if (this._alarmPlaybackSeek) return this._alarmPlaybackSeek(); return false; },
    snapshotAlarmPlaybackImage(row) {
      let images = row && row.carousel_images_list;
      if (typeof images === 'string') {
        try { images = JSON.parse(images.replace(/'/g, '"')); } catch (_) { images = []; }
      }
      images = Array.isArray(images) ? images.filter(value => typeof value === 'string' && value.trim()) : [];
      const key = row && (row._carousel_key || row.Algorithm_result_id || row.id);
      let raw = this.rowCarouselIndex && this.rowCarouselIndex[key];
      if (typeof this.getCurrentIndex === 'function') raw = this.getCurrentIndex(row);
      let reliable = images.length === 1 || Number.isInteger(raw) && raw >= 0;
      let selected = Number.isInteger(raw) && raw >= 0 && images.length ? raw % images.length : 0;
      if (typeof this.getCurrentImage === 'function' && images.length) {
        const displayed = this.getCurrentImage(row);
        if (images[selected] !== displayed) {
          const first = images.indexOf(displayed);
          reliable = first >= 0 && images.lastIndexOf(displayed) === first;
          if (reliable) selected = first;
        }
      }
      return Object.freeze({index: selected, url: images[selected] || '', count: images.length, reliable});
    },
    // 格式化函数，将时间转换为目标格式
    formatDate2(input) {
      console.log(input)
      // 使用正则表达式将日期格式从 "YYYY-MM-DD HH:MM:SS" 转换为 "YYYYMMDDtHHMMSS"
      return input.replace(/(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})/, '\$1\$2\$3t\$4\$5\$6');
    },
    formatDate3(date) {
      // 获取日期的各个部分
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');  // 月份是从0开始的，所以需要加1
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');

      // 返回格式化后的字符串
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    },

    // 计算前后30秒的时间
    calculateTimeAroundssfx(input) {
      // 将输入时间字符串转换为 Date 对象
      const inputDate = new Date(input);

      // 计算前30秒和后30秒的时间
      const timeBefore30Sec = new Date(inputDate.getTime() - 5 * 1000);
      const timeAfter30Sec = new Date(inputDate.getTime() + 10 * 1000);
      // const timeBefore30Sec = new Date(inputDate.getTime() - 30 * 1000); // 前30秒
      // const timeAfter30Sec = new Date(inputDate.getTime() + 30 * 1000);  // 后30秒

      // 格式化前后30秒的时间
      const formattedBefore = this.formatDate2(this.formatDate3(timeBefore30Sec));
      const formattedAfter = this.formatDate2(this.formatDate3(timeAfter30Sec));

      // 返回结果
      return {
        start_time: formattedBefore,
        end_time: formattedAfter
      };
    },
    calculateTimeAroundssfxs(input) {
      return this.formatDate2(this.formatDate3(new Date(input)));
    },
    calculateTimeAround(input) {
      // 将输入时间字符串转换为 Date 对象
      const inputDate = new Date(input);

      // 检查输入是否有效
      if (isNaN(inputDate.getTime())) {
        throw new Error('Invalid date input');
      }

      // 计算前30秒和后30秒的时间
      const timeBefore30Sec = new Date(inputDate.getTime() - 30 * 1000); // 前30秒
      const timeAfter30Sec = new Date(inputDate.getTime() + 30 * 1000);  // 后30秒

      // 格式化时间的方法
      function formatDate(date) {
        return [
          date.getFullYear(),
          String(date.getMonth() + 1).padStart(2, '0'),
          String(date.getDate()).padStart(2, '0')
        ].join('-') + ' ' +
          [
            String(date.getHours()).padStart(2, '0'),
            String(date.getMinutes()).padStart(2, '0'),
            String(date.getSeconds()).padStart(2, '0')
          ].join(':');
      }

      // 返回结果
      return {
        before: formatDate(timeBefore30Sec),
        after: formatDate(timeAfter30Sec)
      };
    },
    // 关闭视频回放弹窗
    handleCloseAlarmVideo() {
      // 关闭弹窗、清除video、关闭视频流
      this.stopVideo()
      this.alarmVideoOpen = false;
    },
    // 播放视频函数
    playVideo(url) {
      // 检查浏览器是否支持 FLV.js
      if (flvjs.isSupported()) {
        // 获取视频元素
        const videoElement = this.$refs.videoPlayer;
        if (videoElement) {
          videoElement.src = ''; // 清空 src
          videoElement.load();   // 重新加载以清除之前的流数据
          videoElement.pause();  // 确保视频已暂停
        }

        // 如果已经存在 FLV 播放器实例，先销毁当前的播放器
        if (this.flvPlayer && this.flvPlayer.destroy) {
          this.flvPlayer.destroy();
        }

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
    // 获取flv状态
    getFlvStatus() {
      this.$http.get(spfxApi.getFlvStatus)
        .then(response => {
          if (response.data.code == 200) {
            clearInterval(this.interTime)
            setTimeout(() => {
              this.playVideo(this.ssfxVideoFlv)
            }, 3000)
          }
        })
        .catch(rek => {
          console.log(rek)
        })
    },
    stopVideo() {
      this._alarmPlaybackGeneration = (this._alarmPlaybackGeneration || 0) + 1;
      if (this._alarmPlaybackController) this._alarmPlaybackController.abort();
      this._alarmPlaybackController = null;
      clearInterval(this.interTime);
      clearInterval(this._alarmPlaybackHeartbeat);
      if (this.flvPlayer && this.flvPlayer.destroy) this.flvPlayer.destroy();
      this.flvPlayer = null;
      const session = this._alarmPlaybackSession;
      this._alarmPlaybackSession = null;
      this.alarmImageOffset = null;
      this._alarmPlaybackSeek = null;
      this.ssfxVideoFlv = '';
      this.alarmVideoOpen = false;
      const video = this.$refs.videoPlayer;
      if (video) { video.onloadedmetadata = null; video.oncanplay = null; video.onerror = null; video.pause(); video.removeAttribute('src'); video.load(); }
      // Static archives and existing analysis streams never own the temporary worker.
      if (!session) return Promise.resolve();
      return this.$http.post(this.$url.url_5000 + '/video_view/real_time_video_stop', { session_token: session }, { timeout: 8000 })
        .catch(() => { /* Expired owned sessions are reclaimed before another playback can start. */ });
    },
    // 轮播图片
    handleOpenPictureOpen(data) {
      // 记录上下一页所需参数
      this.clickType = '0',
      this.pictureArrId = data.Algorithm_result_id
      this.pictureOpen = true
      this.pictureArr = data.carousel_images_list //报警图片-有框
      // this.pictureArr = data.ori_images_list //报警图片-无框
      this.pictureTitle = data.conf_name + "_" + data.mine_name + "_" + data.equipment_name + "_" + data.res_type
    },
    // 轮播图片
    handleOpenPictureOpens(data) {
      this.clickType = '1',
      // 记录上下一页所需参数
      this.pictureArrId = data.Algorithm_result_id
      this.pictureOpen = true
      this.pictureArr = data.ori_images_list //报警图片-无框
      this.pictureTitle = data.conf_name + "_" + data.mine_name + "_" + data.equipment_name + "_" + data.res_type
    },
    handleClosePictureOpen() {
      this.pictureOpen = false
    },
    handleSearchDict() {
      this.$http.get(dictApi.getDictDataList, {
        params: {
          type_code: 4,
          page: 1,
          per_page: 999,
        }
      }).then(res => {
        if (res.data.code == 200) {
          this.modelTypeDict = res.data.data_list.data
        }
      }).catch(rek => {
        console.log(rek)
      })
    },
    // 点击查看，海康录像机回放视频
    handleOpenHKVS(row) {
      this.$http.get(hkvsApi.getHKVSMsg, {
        params: {
          id: row.Equipment_id
        }
      }).then(response => {
        let res = response.data.data
        this.HKVSTitle = row.equipment_name
        this.HKVSOpen = true
        // this.$refs.hkvs.delInitPlugin()
        setTimeout(() => {
          this.$refs.hkvs.initPlugin();
        }, 10)

        setTimeout(() => {
          let { before, after } = this.calculateTimeAround(row.res_time)
          let oLiveView = {
            iProtocol: 1, // http 协议，1 表示 http 协议 2 表示 https 协议
            szIP: res.equipment_ip, // 设备的 IP 地址或者普通域名(比如花生壳域名)
            szPort: '80', // 登录设备的 http/https 端口号，根据 iPrototocol 选择传入不同的端口
            szUsername: res.equipment_uname, // 登录用户名称
            szPassword: res.equipment_password, // 登录用户密码
            iStreamType: 1, // 码流类型 1-主码流，2-子码流，默认使用主码流预览
            iChannelID: res.equipment_aisles, // 播放通道号，默认通道 1
            bZeroChannel: false, // 是否播放零通道，默认为 false
            szStartTime: before,
            szEndTime: after,
          }
          
          // this.$refs.hkvs.clickLoginBack(oLiveView)
          this.$nextTick(()=>{
            this.$refs.hkvs.getMessage(oLiveView, 'back')
          })
        }, 2000);
      }).catch(rek => {
        console.log(rek)
      })
    },
    // 关闭HKVS插件
    handleCloseHKVSOpen() {
      //  清除插件
      this.$refs.hkvs.delInitPlugin()
      this.HKVSOpen = false;
    },
    // 图片查看，上一页
    handleUpImg() {
      // pictureArrId是当前弹窗中所展示图片的ID，可以通过当前ID来查询当前图片的位置，并找到相关联的上下一组图片
      let index = this.tableData.findIndex(v => v.Algorithm_result_id == this.pictureArrId)
      if (index == 0) {
        this.$message({
          type: 'success',
          message: '当前是第一条信息！！！'
        })
      } else {
        index -= 1
        if(this.clickType == '0'){
          this.handleOpenPictureOpen(this.tableData[index])
        }else{
          this.handleOpenPictureOpens(this.tableData[index])
        }
      }
    },
    // 图片查看，下一页
    handleNextImg() {
      let index = this.tableData.findIndex(v => v.Algorithm_result_id == this.pictureArrId)
      if (index == this.tableData.length - 1) {
        this.$message({
          type: 'success',
          message: '当前是最后一条信息！！！'
        })
      } else {
        index += 1
        if(this.clickType == '0'){
          this.handleOpenPictureOpen(this.tableData[index])
        }else{
          this.handleOpenPictureOpens(this.tableData[index])
        }
      }
    },
    // 图片下载
    async handleDownLoadImage() {
      const zip = new JSZip();

      // 循环处理每个图像并添加到zip文件中
      for (let i = 0; i < this.pictureArr.length; i++) {
        // let res = this.pictureArr[i].replace('http://192.168.7.51:9001',`${window.wgParameter.url_5000}/image`)
        // let res = this.pictureArr[i].replace('http://192.168.7.51:9001',`http://192.168.14.92:8888/image`)
        let res = this.pictureArr[i]
        const response = await fetch(res);
        const arrayBuffer = await response.arrayBuffer();
        zip.file(`${this.pictureTitle}-${i}.jpg`, arrayBuffer);
      }

      // 生成zip文件并下载
      const content = await zip.generateAsync({ type: 'blob' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(content);
      link.download = 'images.zip';
      link.click();
    },
    // 关闭报警列表删除界面
    handleCloseBjlbOpen() {
      this.bjlbOpen = false
      this.axioss()
    },
    // 快捷键按钮触发函数，打开报警列表删除界面
    handleOpenBjlbOpen(event) {
      //event.preventDefault();  // 阻止默认行为
      // 检查是否按下了组合键，例如 Ctrl + Shift + M
      if (event.ctrlKey && event.shiftKey && event.key.toLowerCase() == 'x') {
        this.bjlbOpen = true
      }
      // 检查是否按下了 Alt + Shift + T 组合键
      if (event.altKey && event.shiftKey && event.key.toLowerCase() == 't') {
        this.bjlbOpen = true
      }
    },
    handleCloseBjlbList() {
      if(this.multipleSelection.length == 0){
        this.$message({type:'success',message:'请先选择要删除的数据！'})
        return false
      }
      MessageBox.confirm('确定删除该数据吗？', '提示', {
        type: 'warning'
      }).then(() => {
        this.$http.get(bjlbApi.delete,{
          params:{
            id_list:JSON.stringify(this.multipleSelection)
          }
        })
          .then(response => {
            if (response.data.code == 200) {
              this.$message({
                type: 'success',
                message: response.data.msg
              })
            } else {
              this.$message({
                type: 'warning',
                message: response.data.msg
              })
            }
            this.axioss()
          })
          .catch(rek => {
            console.log(rek)
          })
      }).catch(() => {
        Message.info('已取消删除');
      });
    },
    handleSelectionChange(val) {
      this.multipleSelection = val.map(v=>{
        return v.Algorithm_result_id
      });
      console.log(this.multipleSelection)
    }
  },
  created() {
    if(localStorage.getItem('user_role_id')){
      this.$store.state.user_role_id = localStorage.getItem('user_role_id')
    }
    this.handleSelect1();
    
    this.handleSearchDict();
    // 大类
    this.$http.get(modelApi.getModelType, {
      params: {
        page: 1,
        per_page: 999
      }
    }).then(response => {
      this.modelTypeOptions = response.data.data.data
      // this.queryParams.template_type_id = response.data.data.data[0].id
      // 表格数据查询
      if (JSON.stringify(this.$router.history.current.query) != "{}") {
        this.loading = true
        if (this.$route.query.id) {
          this.video_page_id = this.$route.query.id;
        }
        if (this.$route.query.Algorithm_config_id) {
          this.Algorithm_config_id = this.$route.query.Algorithm_config_id;
          if(this.$route.query.type){
            this.options5.forEach((item)=>{
              if(item.algorithm_name == '人数统计' || item.algorithm_name == '车辆统计'){
                this.queryParams.algorithm_id = item.id
              }
            })
            this.queryParams.template_type_id = 3
          }
        }
        this.queryfn()
        // this.$http
        //   .get(
        //     this.$url.url_5000 + "/model_view/algorithm_result",
        //     {
        //       params: {
        //         mine_id: this.mkname,
        //         equipment_id: this.jkdname,
        //         type: this.bjtype,
        //         start_time: this.StartTime,
        //         end_time: this.EndTime,
        //         page: this.pagenumber,
        //         per_page: this.pagesize,
        //         algorithm_id: this.algorithm_id,
        //         id: this.video_page_id,
        //         Algorithm_config_id:this.Algorithm_config_id,
        //       },
        //     },
        //     {
        //       withCredentials: true,
        //     }
        //   )
        //   .then((response) => {
        //     console.log(response);
        //     if (response.data.code === 200) {
        //       this.tableData = response.data.data_list.data.map(v => {
        //         return {
        //           ...v,
        //           carousel_images_list: JSON.parse(v.carousel_images_list.replace(/'/g, '"')),
        //           ori_images_list: JSON.parse(v.ori_images_list.replace(/'/g, '"')),
        //         }
        //       });
        //       this.pagelength = response.data.data_list.total_items;
        //       this.loading = false
        //     }
        //   })
        //   .catch(function (response) {
        //     console.log("rek=====", response);
        //   });
      } else {
        const now = new Date();
        const currentTime = this.formatDate(now);

        // 当天零点时间
        const midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const midnightTime = this.formatDate(midnight);

        this.StartTime = midnightTime;
        this.EndTime = currentTime;
        this.axioss();
      }
    }).catch(rek => {
      console.log(rek)
    })
  },
  mounted() {
    clearInterval(this.timer)
    document.addEventListener('keydown', this.handleOpenBjlbOpen);
    this.timer = setInterval(()=>{
      this.bjfns()
      this.axioss()
    },15000)
  },
  beforeDestroy() {
    this._alarmPlaybackDisposed = true;
    this.stopVideo();
    clearInterval(this.timer)
    document.removeEventListener('keydown', this.handleOpenBjlbOpen);
  },
  // beforeRouteLeave(to, from, next) {
  //   clearInterval(this.timer)
  // },
  // destroyed() {
  //   clearInterval(this.timer)
  // },
};
</script>

<style lang="scss" scoped>
.box{
  width: 100%;
  height: 300px;
  .left{
    width: 60%;
    height: 100%;
    float: left;
  }
  .right{
    width: 40%;
    height: 100%;
    float: left;
  }
}
::v-deep.demo-ruleForm {
  .selectImg {
    width: 14px;
    height: 14px;
    margin-top: 13px;
    margin-left: 7px;
  }
  .cascaderImg {
    width: 14px;
    height: 14px;
    position: absolute;
    top: 13px;
    left: 13px;
    z-index: 30;
  }
  .el-cascader {
    .el-input__inner {
      padding-left: 30px;
    }
  }
  .el-cascader {
    .el-input__inner {
      width: 177px;
      height: 33px;
      background: #ffffff;
      border-radius: 4px;
      border: 1px solid #b4b2b3;
    }
    .el-input__suffix-inner {
      border-left: 1px solid #b4b2b3;
    }
  }
  .el-select {
    .el-input__inner {
      width: 177px;
      height: 33px;
      background: #ffffff;
      border-radius: 4px;
      border: 1px solid #b4b2b3;
    }
    .el-input__suffix-inner {
      border-left: 1px solid #b4b2b3;
      .el-icon-arrow-up:before {
        position: relative;
        top: 2px;
      }
    }
  }
  // .el-date-editor {
  // .el-input__inner {
  //   width: 200px;
  //   height: 33px;
  //   background: #ffffff;
  //   border-radius: 4px;
  //   border: 1px solid #b4b2b3;
  // }
  // .el-icon-time::before {
  //   content: none;
  // }
  // .el-icon-time {
  //   // display: none !important;
  //   background-image: url("../img/home/alarmlist/time.png"); /* 替换为你自己的图标路径 */
  //   background-repeat: no-repeat;
  //   background-position: center;
  //   width: 16px; /* 图标大小 */
  //   height: 16px;
  //   display: inline-block;
  //   margin-top: 10px;
  //   margin-left: 4px;
  // }
  //   .el-input__suffix-inner {
  //     display: inline-block;
  //     width: 15px;
  //     height: 15px;
  //     border-left: 1px solid #b4b2b3;
  //     margin-top: 11px;

  //     .el-input__icon::before {
  //       content: "";
  //       position: absolute;
  //       top: 3px;
  //       left: 7px;
  //       width: 14px;
  //       height: 14px;
  //       border: 1px solid #b4b2b3;
  //       transform: rotate(45deg);
  //       clip-path: polygon(50% 50%, 100% 50%, 100% 100%, 50% 100%);
  //     }
  //   }
  // }
}
::v-deep .el-dialog {
  border-radius: 21px;
}
::v-deep .el-dialog__header {
  background-image: url(../img/home/bjlb/title.png);
  background-repeat: no-repeat;
  background-size: 101.6% 150%;
  // background-position: center 100%;
  background-attachment: fixed;
  background-position: center -10px !important;
  // border-radius: 20px;
  // border-top-left-radius: 10px !important; /* 设置左上角圆角半径为10px */
  // border-top-right-radius: 10px !important; /* 设置右上角圆角半径为10px */
  // border-bottom: 1px solid #d4d4d4;
  // box-sizing: content-box;
  .el-dialog__title {
    border-left: 4px solid #006eff;
    padding-left: 5px;
  }
}
::v-deep .jia_videoDia {
  .el-dialog__body {
    background-image: url(../img/home/bjlb/back02.png) !important;
    background-repeat: no-repeat !important;
    background-size: 100% 100% !important;
    // background-position: center !important;
    // background-attachment: fixed;
    // background-position: center -10px!important;
  }
  .btn_group {
    margin-top: 10px;
    width: 100%;
    height: 50px;
    display: flex;
    justify-content: center;
  }
}
.bjlb {
  width: 100%;
  height: 100%;
  background-color: #ffffff;
  border-radius: 6px;

  .serch {
    height: 120px;
    padding-top: 16px;
    padding-bottom: 16px;
    box-sizing: border-box;
    position: relative;
    .searchBtn {
      width: 177px;
      height: 33px;
      // background-color: pink;
      position: absolute;
      right: 0px;
      bottom: 16px;
    }
    .demo-ruleForm {
      height: 100%;
      display: flex;
      justify-content: flex-start;
      align-items: flex-start;
      flex-wrap: wrap;
    }
  }

  .table {
    height: 80%;
    position: relative;
    // font-size: 12px;
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
      bottom: -24px;
    }
  }
  .nav-button:hover {
    color: #409eff !important;
  }
}
.bj_list{
  width: 350px;
  height: 450px;
  position: fixed;
  left: 226px;
  bottom: 32px;
  z-index: 999;
  ::v-deep .el-card__header{
    padding: 12px 12px !important;
  }
  ::v-deep .el-card__body{
    width: calc(100% - 40px);
    height: calc(100% - 50px);
    padding: 0 !important;
    margin: 0 auto;
  }
  .bjitems{
    font-size: 14px;
    padding-top: 5px;
  }
  .bjitems_b{
    margin-top: 15px;
    text-align: center;
  }
}
</style>
