"""Small native frontend repairs applied to the packaged Vue distribution."""
from pathlib import Path
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


MENU_MARKER = '/* native-menu-loading-v1 */'
RECORDER_FORM_MARKER = '/* native-recorder-form-v2 */'
MODEL_UPLOAD_LAYOUT_MARKER = '/* native-model-upload-layout-v1 */'
MODEL_UPLOAD_LAYOUT_STYLE = '''
.jia_algoBox[data-v-60109a28] .el-form-item.jia_formItem2 + .el-form-item{margin-left:50%;width:50%;box-sizing:border-box}
.jia_algoBox[data-v-60109a28] .el-form-item.jia_formItem2 + .el-form-item .el-textarea{width:100%!important}
'''

ALARM_STATISTICS_MARKER = '/* native-alarm-statistics-v1 */'


def patch_native_alarm_statistics(root):
    """Render statistics after Vue updates the chart node, without a fixed delay."""
    frontend = Path(root) / 'frontend'
    index_path = frontend / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)', index)
    if not asset:
        raise ValueError('未找到当前前端入口')
    app_path = frontend / asset.group(1).lstrip('./')
    app = app_path.read_text(encoding='utf-8')
    reference = re.search(r'"chunk-7c317544":"([^"]+)"', app)
    if not reference:
        raise ValueError('未找到报警统计模块')
    old_name = 'chunk-7c317544.' + reference.group(1) + '.js'
    path = frontend / 'assets/js' / old_name
    source = path.read_text(encoding='utf-8')
    if ALARM_STATISTICS_MARKER in source:
        return False
    request = '''axioss(){
      const t=this.$loading({target:this.$el,text:"加载中...",spinner:"el-icon-loading"});
      const requestId=this._alarmStatisticsRequestId=(this._alarmStatisticsRequestId||0)+1;
      return this.$http.get(this.$url.url_5000+"/model_view/algorithm_ratio",{params:{mine_id:this.mkname,equipment_id:this.jkdname,start_time:this.StartTime,end_time:this.EndTime,template_type_id:this.template_type_id,type:this.bjtype}},{withCredentials:!0})
        .then(async e=>{
          if(this._isDestroyed||requestId!==this._alarmStatisticsRequestId)return;
          if(200===e.data.code){
            this.echartsTable=e.data.data_list;
            await this.$nextTick();
            if(this._isDestroyed||requestId!==this._alarmStatisticsRequestId)return;
            if(this.echartsTable.length)this.handleEchart();else this.disposeAlarmStatisticsChart();
          }
        }).catch(e=>{console.log(e)}).finally(()=>t.close())
    },disposeAlarmStatisticsChart(){
      if(this._alarmStatisticsChart){this._alarmStatisticsChart.dispose();this._alarmStatisticsChart=null}
    },handleEchart(){'''
    updated, count = re.subn(r'axioss\(\)\{const t=this\.\$loading\(.*?\},handleEchart\(\)\{',
                             lambda _: request, source, count=1, flags=re.S)
    if count != 1:
        raise ValueError('无法定位报警统计加载逻辑')
    old = 'let t=this.$echarts.init(document.getElementById("myChart1")),e='
    new = ('const chartNode=this.$el.querySelector("#myChart1");if(!chartNode)return;'
           'let t=this._alarmStatisticsChart||this.$echarts.getInstanceByDom(chartNode)||this.$echarts.init(chartNode),e=')
    if updated.count(old) != 1 or updated.count('t.setOption(e,!0),t.resize()') != 1:
        raise ValueError('无法定位报警统计图表初始化')
    updated = updated.replace(old, new, 1).replace('t.setOption(e,!0),t.resize()',
        'this._alarmStatisticsChart=t,t.setOption(e,!0),t.resize()', 1)
    if updated.count('},mounted(){const t=new Date') != 1:
        raise ValueError('无法定位报警统计页面生命周期')
    updated = updated.replace('},mounted(){const t=new Date',
        '},beforeDestroy(){this.disposeAlarmStatisticsChart()},mounted(){const t=new Date', 1)
    updated = ALARM_STATISTICS_MARKER + '\n' + updated
    digest = hashlib.sha256(updated.encode('utf-8')).hexdigest()[:8]
    new_name = 'chunk-7c317544.' + digest + '.js'
    (path.parent / new_name).write_text(updated, encoding='utf-8')
    app = app.replace('"chunk-7c317544":"' + reference.group(1) + '"',
                      '"chunk-7c317544":"' + digest + '"', 1)
    app_path.write_text(app, encoding='utf-8')
    index_path.write_text(index.replace(old_name, new_name), encoding='utf-8')
    return True


def model_upload_layout_script():
    """Use the shared, uncached config script so existing images receive the fix."""
    return (MODEL_UPLOAD_LAYOUT_MARKER + '\n;(function(){var id="native-model-upload-layout",'
            'style=document.getElementById(id);if(!style){style=document.createElement("style");'
            'style.id=id;(document.head||document.documentElement).appendChild(style);}'
            'style.textContent=' + json.dumps(MODEL_UPLOAD_LAYOUT_STYLE) + ';})();\n')


def patch_native_model_upload_layout(root):
    path = Path(root) / 'Config_files/config.js'
    source = path.read_text(encoding='utf-8')
    if MODEL_UPLOAD_LAYOUT_MARKER in source:
        return False
    path.write_text(source + '\n' + model_upload_layout_script(), encoding='utf-8')
    return True


TEMPLATE_ADMIN_SCRIPT = r'''/* native-template-administrator-v1 */
(function(root){
  'use strict';
  root.PlatformAlgorithmTemplateAdministrator={
    data:function(){return {algorithmTemplateAdministrator:false};},
    created:function(){
      var view=this;
      view._algorithmTemplateAdministratorAlive=true;
      view.algorithmTemplateAdministrator=false;
      if(!view.$http||!view.$http.get)return;
      var base=String(view.$url&&view.$url.url_5000||root.wgParameter&&root.wgParameter.url_5000||'/api').replace(/\/$/,'');
      view._algorithmTemplateAdministratorPromise=view.$http.get(base+'/user_view/protected',{timeout:10000})
        .then(function(response){
          var body=response&&response.data;
          if(view._algorithmTemplateAdministratorAlive)
            view.algorithmTemplateAdministrator=!!(body&&Number(body.code)===200&&body.is_superadmin===true);
        }).catch(function(){
          if(view._algorithmTemplateAdministratorAlive)view.algorithmTemplateAdministrator=false;
        });
    },
    beforeDestroy:function(){
      this._algorithmTemplateAdministratorAlive=false;
      this.algorithmTemplateAdministrator=false;
    }
  };
})(window);
'''
TEMPLATE_ADMIN_CHUNKS = ('chunk-e0401796', 'chunk-415cc626', 'chunk-32a3ec07',
                         'chunk-c55e7166', 'chunk-36680cda', 'chunk-76b7f37c')


def _template_admin_comparisons(source):
    target = r'(?:[A-Za-z_$][\w$]*\.)?usertype|(?:[A-Za-z_$][\w$]*\.)?\$store\.state\.user_role_id'
    operator = r'===|!==|==|!='

    def comparison(match):
        field = match.group('field')
        prefix = field.split('$store', 1)[0] if '$store' in field else field[:-len('usertype')]
        return ('!' if '!' in match.group('operator') else '') + prefix + 'algorithmTemplateAdministrator'

    source = re.sub(r'(?P<field>' + target + r')\s*(?P<operator>' + operator + r')\s*1(?!\d)', comparison, source)
    return re.sub(r'(?<![\w.])1\s*(?P<operator>' + operator + r')\s*(?P<field>' + target + r')', comparison, source)


def patch_native_template_administrator(root):
    """Use the authenticated superadmin capability without changing role IDs."""
    root = Path(root)
    frontend = root / 'frontend'
    index_path = frontend / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not asset:
        raise ValueError('未找到当前前端入口脚本')
    app_path = frontend / asset.group(1)
    app = app_path.read_text(encoding='utf-8')
    changed = []
    marker = '/* native-template-administrator-v1 */'
    for chunk_id in TEMPLATE_ADMIN_CHUNKS:
        mapping = re.search('"' + chunk_id + '":"([^"]+)"', app)
        if not mapping:
            raise ValueError('未找到模型权限页面：' + chunk_id)
        old_name = chunk_id + '.' + mapping.group(1) + '.js'
        source = (frontend / 'assets/js' / old_name).read_text(encoding='utf-8')
        if marker in source:
            continue
        updated = _template_admin_comparisons(source)
        if updated == source:
            raise ValueError('未找到模型页面角色判断：' + chunk_id)
        if chunk_id in ('chunk-e0401796', 'chunk-415cc626'):
            before = 'mixins: [algorithmStreamMixin, algorithmTemplateParameters'
            after = 'mixins: [window.PlatformAlgorithmTemplateAdministrator, algorithmStreamMixin, algorithmTemplateParameters'
        elif chunk_id == 'chunk-32a3ec07':
            before = 'mixins:[roiThumbnailMixin,algorithmListReturnStateMixin]'
            after = 'mixins:[window.PlatformAlgorithmTemplateAdministrator,roiThumbnailMixin,algorithmListReturnStateMixin]'
        else:
            name = 'sfgl' if chunk_id == 'chunk-c55e7166' else 'sfc'
            before = 'name:"' + name + '",data()'
            after = 'mixins:[window.PlatformAlgorithmTemplateAdministrator],name:"' + name + '",data()'
        if updated.count(before) != 1:
            raise ValueError('无法定位模型权限组件：' + chunk_id)
        updated = marker + '\n' + updated.replace(before, after, 1)
        digest = hashlib.sha256(updated.encode('utf-8')).hexdigest()[:8]
        new_name = chunk_id + '.' + digest + '.js'
        path = frontend / 'assets/js' / new_name
        path.write_bytes(updated.encode('utf-8'))
        changed.append(path.relative_to(root).as_posix())
        app = app.replace('"' + chunk_id + '":"' + mapping.group(1) + '"',
                          '"' + chunk_id + '":"' + digest + '"', 1)
        index = index.replace(old_name, new_name)
    script_name = 'algorithm-template-administrator.' + hashlib.sha256(TEMPLATE_ADMIN_SCRIPT.encode('utf-8')).hexdigest()[:8] + '.js'
    script = frontend / 'static/js' / script_name
    if not script.is_file() or script.read_text(encoding='utf-8') != TEMPLATE_ADMIN_SCRIPT:
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_bytes(TEMPLATE_ADMIN_SCRIPT.encode('utf-8'))
        changed.append(script.relative_to(root).as_posix())
    if script_name not in index:
        index = index[:asset.start()] + '<script src="./static/js/' + script_name + '"></script>' + index[asset.start():]
    if app != app_path.read_text(encoding='utf-8'):
        app_path.write_text(app, encoding='utf-8')
        changed.append(app_path.relative_to(root).as_posix())
    if index != index_path.read_text(encoding='utf-8'):
        index_path.write_text(index, encoding='utf-8')
        changed.append(index_path.relative_to(root).as_posix())
    for path in (frontend / 'src/components').glob('*.vue'):
        if path.name not in ('sfgl.vue', 'sfgl_child.vue', 'sfgl_childsCom.vue', 'sfc.vue', 'sxtsf.vue', 'sxtpz.vue'):
            continue
        source = path.read_text(encoding='utf-8')
        updated = _template_admin_comparisons(source)
        if updated == source:
            continue
        if 'mixins: [' in updated:
            updated = updated.replace('mixins: [', 'mixins: [window.PlatformAlgorithmTemplateAdministrator, ', 1)
        else:
            updated = updated.replace('export default {', 'export default {\n  mixins: [window.PlatformAlgorithmTemplateAdministrator],', 1)
        path.write_text(updated, encoding='utf-8')
        changed.append(path.relative_to(root).as_posix())
    if refresh_asset_versions(root) and index_path.relative_to(root).as_posix() not in changed:
        changed.append(index_path.relative_to(root).as_posix())
    return changed


def patch_menu_loading(root):
    """Keep failed menu requests recoverable without changing role permissions."""
    frontend = Path(root) / 'frontend'
    index = (frontend / 'index.html').read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not asset:
        raise ValueError('未找到当前前端入口脚本')
    path = frontend / asset.group(1)
    source = path.read_text(encoding='utf-8')
    if MENU_MARKER in source:
        return False

    replacements = (
        ('menuData:[],objinfo:', 'menuData:[],menuLoading:!0,menuError:"",objinfo:'),
        ('},created(){this.usernames=localStorage.getItem("userRoleName"),this.getJudgment()}',
         '},watch:{"$route"(){this.handleMenuName()}},created(){this.usernames=localStorage.getItem("userRoleName"),this.getJudgment()}'),
        ('[t("div",{staticClass:"menu"},[t("el-menu",',
         '[t("div",{staticClass:"menu"},['
         'e.menuLoading?t("div",{staticClass:"home-menu-state",attrs:{role:"status"},staticStyle:{padding:"16px",color:"#606266"}},[e._v("菜单加载中…")]):'
         'e.menuError?t("div",{staticClass:"home-menu-state",attrs:{role:"alert"},staticStyle:{padding:"16px",color:"#c45656"}},['
         't("p",[e._v(e.menuError)]),t("el-button",{attrs:{type:"text"},on:{click:e.getJudgment}},[e._v("重新加载")])]):e._e(),t("el-menu",'),
    )
    for old, new in replacements:
        if source.count(old) != 1:
            raise ValueError('无法定位菜单加载补丁入口')
        source = source.replace(old, new, 1)

    judgment = r'''getJudgment(retried){
      this.menuLoading=true;this.menuError="";
      const attempt=retried===true;
      const fail=error=>{
        const network=error&&(error.message==="Network Error"||error.code==="ECONNABORTED");
        if(!attempt&&network)return new Promise(resolve=>setTimeout(resolve,500)).then(()=>this.getJudgment(true));
        this.menuLoading=false;
        this.menuError=error&&error.response&&error.response.data&&error.response.data.msg||error&&error.message||"菜单加载失败";
      };
      if(this.system==="TFS")return this.getMenuData().catch(fail);
      return this.$http.get(o["a"].activateJudgment,{timeout:15000}).then(response=>{
        const body=response.data||{};
        if(Number(body.code)===400){this.activateOpen=false;this.menuLoading=false;return;}
        if(Number(body.code)!==200)throw new Error(body.msg||"激活状态读取失败");
        this.activateOpen=true;return this.getMenuData();
      }).catch(fail);
    },handleIndex(e)'''
    source, count = re.subn(r'getJudgment\(\)\{.*?\},handleIndex\(e\)', lambda _: judgment, source, count=1, flags=re.S)
    if count != 1:
        raise ValueError('无法定位菜单激活检查')

    menu = r'''getMenuData(){
      return this.$http.get(this.$url.url_5000+"/menu_view/menu_show",{
        params:{user_id:this.$store.state.userId||localStorage.getItem("userId")},timeout:15000
      }).then(response=>{
        const body=response.data||{};
        if(Number(body.code)!==200||!Array.isArray(body.menu_list))throw new Error(body.msg||"菜单数据读取失败");
        this.menuData=body.menu_list;u["a"].state.menuData=body.menu_list;
        this.menuLoading=false;this.menuError=body.menu_list.length?"":"当前账号未分配菜单，请联系管理员";
        this.handleMenuName();
      });
    },handleSelect()'''
    source, count = re.subn(r'getMenuData\(\)\{.*?\},handleSelect\(\)', lambda _: menu, source, count=1, flags=re.S)
    if count != 1:
        raise ValueError('无法定位菜单数据请求')
    path.write_text(MENU_MARKER + '\n' + source, encoding='utf-8')
    return True


def refresh_asset_versions(root):
    """Refresh local JavaScript URLs when their contents change."""
    frontend = Path(root) / 'frontend'
    index = frontend / 'index.html'
    source = index.read_text(encoding='utf-8')

    def version(match):
        url = urlsplit(match.group(2))
        if url.scheme or url.netloc or not url.path.endswith('.js'):
            return match.group(0)
        relative = url.path.removeprefix('./').lstrip('/')
        if relative in ('static/js/config.js', 'static/js/secure-transport.js'):
            return match.group(0)
        asset = frontend / relative
        if not asset.is_file():
            return match.group(0)
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
        parameters = [(key, value) for key, value in parse_qsl(url.query, keep_blank_values=True) if key != 'v']
        parameters.append(('v', 'native-asset-' + digest))
        updated = urlunsplit(('', '', url.path, urlencode(parameters), url.fragment))
        return match.group(1) + updated + match.group(3)

    updated = re.sub(r'(\b(?:src|href)=["\'])([^"\']+)(["\'])', version, source)
    if updated == source:
        return False
    index.write_text(updated, encoding='utf-8')
    return True


def patch_camera_sync_label(root):
    """Distinguish AI-camera IP synchronization from recorder synchronization."""
    frontend = Path(root) / 'frontend'
    index = (frontend / 'index.html').read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not asset:
        raise ValueError('未找到当前前端入口脚本')
    app_path = frontend / asset.group(1)
    app = app_path.read_text(encoding='utf-8')
    chunk = re.search(r'"chunk-3e4b0515":"([^"]+)"', app)
    if not chunk:
        raise ValueError('未找到当前摄像头页面脚本')
    old_name = 'chunk-3e4b0515.' + chunk.group(1) + '.js'
    path = frontend / 'assets/js' / old_name
    source = path.read_text(encoding='utf-8')
    old, new = '_v("ip同步")', '_v("AI摄像头IP同步")'
    if source.count(old) == 1 and '/model_view/sync_aicam_ip' in source:
        source = source.replace(old, new, 1)
    elif new not in source or old in source:
        raise ValueError('无法定位摄像头IP同步按钮')
    content = source.encode('utf-8')
    digest = hashlib.sha256(content).hexdigest()[:8]
    if chunk.group(1) == digest:
        return False
    new_name = 'chunk-3e4b0515.' + digest + '.js'
    (frontend / 'assets/js' / new_name).write_bytes(content)
    app = app.replace('"chunk-3e4b0515":"' + chunk.group(1) + '"',
                      '"chunk-3e4b0515":"' + digest + '"', 1)
    app_path.write_text(app, encoding='utf-8')
    (frontend / 'index.html').write_text(index.replace(old_name, new_name), encoding='utf-8')
    return True


def patch_native_recorder_dialog(root):
    """Keep recorder fields reactive and clear only validation when opening."""
    frontend = Path(root) / 'frontend'
    index_path = frontend / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not asset:
        raise ValueError('未找到当前前端入口脚本')
    app_path = frontend / asset.group(1)
    app = app_path.read_text(encoding='utf-8')
    chunk_id = 'chunk-4dcc7390'
    chunk = re.search('"' + chunk_id + '":"([^"]+)"', app)
    if not chunk:
        raise ValueError('未找到录像机同步页面脚本')
    old_name = chunk_id + '.' + chunk.group(1) + '.js'
    source = (frontend / 'assets/js' / old_name).read_text(encoding='utf-8')
    marker = '/* native-recorder-dialog-v2 */'
    if marker in source:
        return False
    original = ('this.addUpdateOpen=!0,this.resetForm("addUpdateForm")},'
                'resetForm(e){this.$refs[e].resetFields()}')
    previous = ('this.addUpdateOpen=!0,this.$nextTick(()=>{this.resetForm("addUpdateForm")})},'
                'resetForm(e){this.$refs[e]&&this.$refs[e].resetFields()}')
    after = ('this.addUpdateOpen=!0,this.$nextTick(()=>{this.resetForm("addUpdateForm")})},'
             'resetForm(e){this.$refs[e]&&this.$refs[e].clearValidate()}')
    before = original if original in source else previous
    fields = '{vcr_name:"",vcr_type:"",vcr_way:"",Mine_id:"",port:"",ip:"",username:"",password:""}'
    if (source.count(before) != 1 or source.count('addUpdateForm:{},rules:') != 1 or
            source.count('this.addUpdateForm={},this.addUpdateOpen') != 1):
        raise ValueError('无法定位录像机新增表单补丁入口')
    source = source.replace('/* native-recorder-dialog-v1 */\n', '', 1)
    source = source.replace('addUpdateForm:{},rules:', 'addUpdateForm:' + fields + ',rules:', 1)
    source = source.replace('this.addUpdateForm={},this.addUpdateOpen',
                            'this.addUpdateForm=' + fields + ',this.addUpdateOpen', 1)
    source = source.replace(',this.addUpdateForm.Mine_id=this.Mine_id_type[0].id', '', 1)
    source = marker + '\n' + source.replace(before, after, 1)
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()[:8]
    new_name = chunk_id + '.' + digest + '.js'
    (frontend / 'assets/js' / new_name).write_text(source, encoding='utf-8')
    app_path.write_text(app.replace('"' + chunk_id + '":"' + chunk.group(1) + '"',
                                  '"' + chunk_id + '":"' + digest + '"', 1), encoding='utf-8')
    index_path.write_text(index.replace(old_name, new_name), encoding='utf-8')
    return True


def recorder_form_script():
    """Repair the known recorder form in already-published container images."""
    return RECORDER_FORM_MARKER + r'''
;(function(root){
  if(root.__platformRecorderFormV2)return;
  root.__platformRecorderFormV2=true;
  function addRecorder(){
    var view=this;
    this.addUpdateTitle="新增硬盘录像机";
    this.addUpdateForm={vcr_name:"",vcr_type:"",vcr_way:"",Mine_id:"",port:"",ip:"",username:"",password:""};
    this.addUpdateOpen=true;
    this.$nextTick(function(){var form=view.$refs.addUpdateForm;if(form)form.clearValidate();});
  }
  function loadRecorderDictionary(){
    var view=this;
    return this.$http.get(this.$url.url_5000+"/model_view/type_select",{params:{mine_id:"1"}}).then(function(response){
      if(response.data.code===200){
        view.access_type=response.data.vcr_way;
        view.sub_type=response.data.equipment_type;
        view.producer_type=response.data.manufacturer_type;
        view.Mine_id_type=response.data.mine_list;
      }
    }).catch(function(error){console.log(error);});
  }
  function repair(view,existing){
    var options=view.$options,methods=options.methods;
    if(options._scopeId!=="data-v-e147e160"||!methods)return;
    var add=String(methods.handleClickAdd||""),reset=String(methods.resetForm||"");
    if(!/this\.addUpdateForm\s*=\s*\{\}/.test(add)||!/resetForm/.test(add)||!/resetFields/.test(reset))return;
    var patched=Object.assign({},methods,{handleClickAdd:addRecorder});
    if(/this\.addUpdateForm\.Mine_id\s*=\s*this\.Mine_id_type\[0\]\.id/.test(String(methods.getDictData||"")))
      patched.getDictData=loadRecorderDictionary;
    options.methods=patched;
    if(existing){
      view.handleClickAdd=patched.handleClickAdd.bind(view);
      if(patched.getDictData!==methods.getDictData)view.getDictData=patched.getDictData.bind(view);
    }
  }
  function install(){
    var element=root.document.getElementById("app"),application=element&&element.__vue__;
    if(!application)return;
    var Base=application.constructor;
    while(Base.super)Base=Base.super;
    Base.mixin({beforeCreate:function(){repair(this,false);}});
    function visit(view){repair(view,true);(view.$children||[]).forEach(visit);}
    visit(application);
  }
  if(root.document.readyState==="loading")root.document.addEventListener("DOMContentLoaded",install,{once:true});
  else install();
})(window);
'''


def patch_native_storage_notice(root):
    """Describe the native host collector when no valid disk snapshot exists."""
    frontend = Path(root) / 'frontend'
    index = (frontend / 'index.html').read_text(encoding='utf-8')
    script = re.search(r'<script[^>]+src=["\']((?:\./)?static/js/storage-management[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not script:
        raise ValueError('未找到当前存储管理页面脚本')
    relative = script.group(1)
    path = frontend / (relative[2:] if relative.startswith('./') else relative)
    source = path.read_text(encoding='utf-8')
    original = '请检查宿主机采集服务。当前不会使用容器根盘数据代替宿主机容量。'
    replacement = '请检查宿主机采集服务。当前容量以采集到的真实文件系统为准。'
    if replacement in source:
        return False
    if source.count(original) != 1:
        raise ValueError('无法定位存储管理原生采集提示')
    path.write_text(source.replace(original, replacement, 1), encoding='utf-8')
    return True


def patch_native_alarm_details(root):
    """Show the alarm's analysis type separately from its message."""
    frontend = Path(root) / 'frontend'
    index_path = frontend / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not asset:
        raise ValueError('未找到当前前端入口脚本')
    app_path = frontend / asset.group(1)
    app = app_path.read_text(encoding='utf-8')
    chunk_id = 'chunk-0ce522c0'
    chunk = re.search('"' + chunk_id + '":"([^"]+)"', app)
    if not chunk:
        raise ValueError('未找到当前报警页面脚本')
    old_name = chunk_id + '.' + chunk.group(1) + '.js'
    source = (frontend / 'assets/js' / old_name).read_text(encoding='utf-8')
    marker = '/* native-alarm-details-v1 */'
    if marker in source:
        return False
    old = 'e("div",{staticClass:"bjitems"},[t._v(" 报警类型: "),e("span",[t._v(t._s(t.bj_forms.algorithm_name))])])'
    new = ('e("div",{staticClass:"bjitems"},[t._v(" 解析类型: "),e("span",[t._v(t._s(t.bj_forms.analysis_type||"—"))])]),'
           'e("div",{staticClass:"bjitems"},[t._v(" 报警信息: "),e("span",[t._v(t._s(t.bj_forms.warning_message||t.bj_forms.algorithm_name))])])')
    if source.count(old) != 1:
        raise ValueError('无法定位报警信息弹窗字段')
    source = marker + '\n' + source.replace(old, new, 1)
    content = source.encode('utf-8')
    digest = hashlib.sha256(content).hexdigest()[:8]
    new_name = chunk_id + '.' + digest + '.js'
    (frontend / 'assets/js' / new_name).write_bytes(content)
    app = app.replace('"' + chunk_id + '":"' + chunk.group(1) + '"',
                      '"' + chunk_id + '":"' + digest + '"', 1)
    app_path.write_text(app, encoding='utf-8')
    index_path.write_text(index.replace(old_name, new_name), encoding='utf-8')
    return True


DIAGNOSIS_PLAN_STYLE = '''/* Native diagnosis plan dialog only. */
.native-diagnosis-plan.el-dialog{width:min(1000px,calc(100vw - 32px))!important;max-height:92vh;display:flex;flex-direction:column;margin-top:4vh!important;margin-bottom:4vh!important}
.native-diagnosis-plan>.el-dialog__header,.native-diagnosis-plan>.el-dialog__footer{flex:0 0 auto}
.native-diagnosis-plan>.el-dialog__body{overflow:auto;min-height:0;padding:14px 22px}
.native-diagnosis-plan>.el-dialog__body>br{display:none}
.native-diagnosis-plan .jia_boxF[data-v-6c4f7c9f]{height:auto;max-height:380px;overflow:auto;display:grid;grid-template-columns:150px minmax(200px,1fr);gap:12px;margin:10px 0}
.native-diagnosis-plan .jia_boxF .jia_left[data-v-6c4f7c9f],.native-diagnosis-plan .jia_boxF .jia_right[data-v-6c4f7c9f]{position:static;width:auto;height:auto}
.native-diagnosis-plan .jia_boxF .jia_right[data-v-6c4f7c9f]{padding-top:40px}
.native-diagnosis-plan .jia_boxF .jia_left>.el-checkbox{height:40px!important}
.native-diagnosis-plan .content_right[data-v-6c4f7c9f]{height:auto;margin:10px 0}
.native-diagnosis-plan .transferTreeBox[data-v-6c4f7c9f]{width:100%;max-width:750px;margin:0 auto;gap:12px}
.native-diagnosis-plan .transferTreeBox .SelectBox[data-v-6c4f7c9f]{width:calc((100% - 110px)/2);color:#303133}
.native-diagnosis-plan .jia_form .el-form-item{max-width:calc(50% - 16px)}
@media(max-width:650px){.native-diagnosis-plan .jia_form .el-form-item{width:100%;max-width:100%;margin-right:0}.native-diagnosis-plan .jia_boxF[data-v-6c4f7c9f]{grid-template-columns:115px minmax(150px,1fr)}}
'''


def patch_native_diagnosis_configuration(root):
    """Keep diagnosis options, saved selections and dialog controls usable."""
    frontend = Path(root) / 'frontend'
    index_path = frontend / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not asset:
        raise ValueError('未找到当前前端入口脚本')
    app_path = frontend / asset.group(1)
    app = app_path.read_text(encoding='utf-8')
    chunk_id = 'chunk-cdb3fbc6'
    chunk = re.search('"' + chunk_id + '":"([^"]+)"', app)
    if not chunk:
        raise ValueError('未找到视频质量诊断方案页面')
    old_name = chunk_id + '.' + chunk.group(1) + '.js'
    source = (frontend / 'assets/js' / old_name).read_text(encoding='utf-8')
    marker = '/* native-diagnosis-plan-v1 */'
    if marker in source:
        return False

    def replace(before, after):
        nonlocal source
        if source.count(before) != 1:
            raise ValueError('无法定位视频质量诊断方案补丁入口')
        source = source.replace(before, after, 1)

    def method(name, following, body):
        nonlocal source
        pattern = re.escape(name) + r'\([^)]*\)\{.*?\},' + re.escape(following) + r'\('
        source, count = re.subn(pattern, lambda _: body + ',' + following + '(', source, count=1, flags=re.S)
        if count != 1:
            raise ValueError('无法定位视频质量诊断方案方法：' + name)

    replace('attrs:{title:e.title,visible:e.open,width:"1000px","append-to-body":""}',
            'attrs:{title:e.title,visible:e.open,width:"1000px","custom-class":"native-diagnosis-plan",top:"4vh","append-to-body":""}')
    replace('attrs:{type:"primary"},on:{click:e.submitForm}',
            'attrs:{type:"primary",loading:e.saving,disabled:e.diagnosisLoading},on:{click:e.submitForm}')
    replace('return{loading:!1,ids:[]', 'return{loading:!1,saving:!1,diagnosisLoading:!1,ids:[]')
    replace(',{value:"months",label:"月"}', '')
    replace('created(){this.getDict(),this.getList(),this.getMonitorList()}',
            'created(){this.getDict().catch(error=>this.$message.error(error.message)),this.getList(),this.getMonitorList().catch(error=>this.$message.error(error.message))}')
    method('getDict', 'getDict2', '''getDict(){return this.$http.get(this.$url.url_5000+"/model_view/type_select").then(response=>{const body=response.data||{};if(Number(body.code)!==200||!Array.isArray(body.diagnosis_type_result))throw new Error(body.msg||"诊断项目加载失败");this.algorithmOptions=body.diagnosis_type_result;return this.algorithmOptions})}''')
    method('getDict2', 'handleUpdateMarkers', '''getDict2(){return this.getDict().then(rows=>{this.diagnosis_type_list=rows.map(row=>({...row}));if(!rows.length)this.$message.warning("暂无诊断项目，请检查诊断目录配置");return rows})}''')
    method('reset', 'handleQuery', '''reset(){this.form={id:null,name:"",interval_seconds:"1",time_type:"days",scheduled_status:1,scheduled_concent:""};this.checkedList=[];this.saving=false}''')
    method('handleAdd', 'handleUpdate', '''handleAdd(){this.reset();this.diagnosis_type_list=[];this.checkAll=false;this.isIndeterminate=false;this.rightData=[];this.open=true;this.title="添加方案配置";this.diagnosisLoading=true;return Promise.all([this.getDict2(),this.getMonitorList()]).catch(error=>this.$message.error(error.response&&error.response.data&&error.response.data.msg||error.message||"方案选项加载失败")).finally(()=>{this.diagnosisLoading=false})}''')
    method('handleUpdate', 'jkdfn', '''handleUpdate(row){this.reset();this.checkAll=false;this.isIndeterminate=false;this.title="修改方案配置";this.diagnosisLoading=true;return Promise.all([this.getDict(),this.getMonitorList(),this.$http.get(this.$url.url_5000+"/scheduler_task/task_detail",{params:{id:row.id}})]).then(results=>{const body=results[2].data||{};if(Number(body.code)!==200||!body.data)throw new Error(body.msg||"方案详情加载失败");const data=body.data,configured=data.diagnosis_type_list||[];this.form={...data,scheduled_status:[1,"1","启用"].includes(data.scheduled_status)?1:0};this.checkedList=configured.map(item=>item.name);this.diagnosis_type_list=this.algorithmOptions.map(item=>{const saved=configured.find(value=>String(value.id)===String(item.id));return saved?{...item,prewarn:saved.prewarn_threshold,warn:saved.warn_threshold}:{...item}});this.rightData=JSON.parse(JSON.stringify(data.rtsp_list||[]));const ids=new Set;const collect=nodes=>nodes.forEach(node=>{if(node.children&&node.children.length)collect(node.children);else ids.add(String(node.id))});collect(this.rightData);const remove=nodes=>nodes.filter(node=>!ids.has(String(node.id))).map(node=>node.children?{...node,children:remove(node.children)}:node);this.leftData=remove(this.leftData);this.handleCheckedCitiesChange(this.checkedList);this.open=true}).catch(error=>this.$message.error(error.response&&error.response.data&&error.response.data.msg||error.message||"方案详情加载失败")).finally(()=>{this.diagnosisLoading=false})}''')
    method('submitForm', 'findCamerasById', '''submitForm(){if(this.saving||this.diagnosisLoading)return;this.$refs.form.validate(valid=>{if(!valid)return;const types=this.findCheckedByName(this.diagnosis_type_list,this.checkedList);if(!types.length){this.$message.warning("请选择至少一个诊断项目");return}const hasSource=nodes=>nodes.some(node=>node.children&&node.children.length?hasSource(node.children):Boolean(node.rtsp));if(!hasSource(this.rightData)){this.$message.warning("请选择至少一个监控点并点击添加");return}const payload={...this.form,rtsp_list:JSON.stringify(this.rightData),diagnosis_type_list:JSON.stringify(types)},data=new FormData;Object.keys(payload).forEach(key=>{if(payload[key]!==null&&payload[key]!==undefined)data.append(key,payload[key])});this.saving=true;this.$http.post(this.$url.url_5000+(this.form.id!=null?"/scheduler_task/update_task":"/scheduler_task/add_task"),data,{headers:{"Content-Type":"multipart/form-data"}}).then(response=>{const body=response.data||{};if(Number(body.code)!==200&&!(body.code==null&&body.task_id))throw new Error(body.msg||"保存方案失败");this.$message.success(body.msg||"方案已保存");this.open=false;this.getList()}).catch(error=>this.$message.error(error.response&&error.response.data&&error.response.data.msg||error.message||"保存方案失败")).finally(()=>{this.saving=false})})}''')
    method('getMonitorList', 'getMonitorListFind', '''getMonitorList(){return this.$http.get(this.$url.url_5000+"/model_view/equipment_show",{params:{equipment_name:"",equipment_type:"",page:1,per_page:99999999}}).then(response=>{const body=response.data||{},data=body.data_list&&body.data_list.data;if(Number(body.code)!==200||!Array.isArray(data))throw new Error(body.msg||"监控点加载失败");this.mockTreeData=JSON.parse(JSON.stringify(data));this.leftData=JSON.parse(JSON.stringify(data));this.monitorF=[];this.monitorData=[];data.forEach(parent=>{this.monitorF.push(parent.equipment_name);(parent.children||[]).forEach(item=>this.monitorData.push({key:item.id,label:item.equipment_name,ip:item.equipment_ip,parent_ip:item.parent_ip,rtsp:item.rtsp,id:item.id,name:item.equipment_name}))});return this.leftData})}''')
    # Watch the new value so reopening an edited plan shows its saved thresholds.
    replace('initialMarker1Value(e,t){this.marker1Value=t,this.marker1Position=t}',
            'initialMarker1Value(e){this.marker1Value=e,this.marker1Position=e}')
    replace('initialMarker2Value(e,t){this.marker2Value=t,this.marker2Position=t}',
            'initialMarker2Value(e){this.marker2Value=e,this.marker2Position=e}')
    source = marker + '\n' + source
    new_name = chunk_id + '.' + hashlib.sha256(source.encode('utf-8')).hexdigest()[:8] + '.js'
    (frontend / 'assets/js' / new_name).write_text(source, encoding='utf-8')
    app = app.replace('"' + chunk_id + '":"' + chunk.group(1) + '"',
                      '"' + chunk_id + '":"' + new_name.split('.')[-2] + '"', 1)
    app_path.write_text(app, encoding='utf-8')
    css_name = 'native-diagnosis-plan.' + hashlib.sha256(DIAGNOSIS_PLAN_STYLE.encode('utf-8')).hexdigest()[:8] + '.css'
    css = frontend / 'static/css' / css_name
    css.parent.mkdir(parents=True, exist_ok=True)
    css.write_text(DIAGNOSIS_PLAN_STYLE, encoding='utf-8')
    index = index.replace(old_name, new_name)
    index = index.replace('</head>', '<link rel="stylesheet" href="./static/css/' + css_name + '"></head>', 1)
    index_path.write_text(index, encoding='utf-8')
    return True


def patch_native_diagnosis_rating(root):
    """Keep diagnosis result filters and the abstained result consistent."""
    frontend = Path(root) / 'frontend'
    index_path = frontend / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not asset:
        raise ValueError('未找到当前前端入口脚本')
    app_path = frontend / asset.group(1)
    app = app_path.read_text(encoding='utf-8')
    chunk_id = 'chunk-5a3630f6'
    chunk = re.search('"' + chunk_id + '":"([^"]+)"', app)
    if not chunk:
        raise ValueError('未找到视频质量诊断结果页面')
    old_name = chunk_id + '.' + chunk.group(1) + '.js'
    source = (frontend / 'assets/js' / old_name).read_text(encoding='utf-8')
    marker = '/* native-diagnosis-rating-v1 */'
    if marker in source:
        return False
    replacements = (
        ('diagnosis_resultOptions:[{value:"normal",label:"达标"},{value:"general",label:"一般"},{value:"poor",label:"很差"},{value:"fail",label:"失败"}]',
         'diagnosis_resultOptions:[{value:"达标",label:"达标"},{value:"一般",label:"一般"},{value:"很差",label:"很差"},{value:"失败",label:"失败"},{value:"未检测",label:"未检测"}]'),
        ('"达标"==i.row.diagnosis_type?t("span",{staticStyle:{color:"green"}},[e._v(e._s(i.row.diagnosis_type))]):t("span",{staticStyle:{color:"red"}},[e._v(e._s(i.row.diagnosis_type))])',
         't("span",{style:{color:"达标"===i.row.diagnosis_type?"green":"未检测"===i.row.diagnosis_type?"#909399":"red"}},[e._v(e._s(i.row.diagnosis_type))])'),
    )
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError('无法定位视频质量诊断结果补丁入口')
        source = source.replace(before, after, 1)
    source = marker + '\n' + source
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()[:8]
    new_name = chunk_id + '.' + digest + '.js'
    (frontend / 'assets/js' / new_name).write_text(source, encoding='utf-8')
    app = app.replace('"' + chunk_id + '":"' + chunk.group(1) + '"',
                      '"' + chunk_id + '":"' + digest + '"', 1)
    app_path.write_text(app, encoding='utf-8')
    index_path.write_text(index.replace(old_name, new_name), encoding='utf-8')
    return True


def patch_native_diagnosis_auto_reference(root):
    """Expose the shared automatic-reference setting beside diagnosis results."""
    frontend = Path(root) / 'frontend'
    index_path = frontend / 'index.html'
    index = index_path.read_text(encoding='utf-8')
    asset = re.search(r'<script[^>]+src=["\']((?:\./)?assets/js/app[^"\']+?\.js)(?:\?[^"\']*)?["\']', index)
    if not asset:
        raise ValueError('未找到当前前端入口脚本')
    app_path = frontend / asset.group(1)
    app = app_path.read_text(encoding='utf-8')
    chunk_id = 'chunk-5a3630f6'
    chunk = re.search('"' + chunk_id + '":"([^"]+)"', app)
    if not chunk:
        raise ValueError('未找到视频质量诊断结果页面')
    old_name = chunk_id + '.' + chunk.group(1) + '.js'
    source = (frontend / 'assets/js' / old_name).read_text(encoding='utf-8')
    marker = '/* native-diagnosis-auto-reference-v1 */'
    if marker in source:
        return False

    def replace(before, after):
        nonlocal source
        if source.count(before) != 1:
            raise ValueError('无法定位自动诊断基准前端补丁入口')
        source = source.replace(before, after, 1)

    replace('canSetReference:!1,referenceBusy:null,',
            'canSetReference:!1,referenceBusy:null,autoReferenceEnabled:!0,autoReferenceSaved:!0,autoReferenceReady:!1,autoReferenceLoading:!1,autoReferenceSaving:!1,autoReferenceError:"",')
    replace('mounted(){this.getList()},watch:{},methods:{getVcr(){',
            'mounted(){this.getList(),this.loadAutoReference()},watch:{},methods:{getVcr(){')
    replace('methods:{getVcr(){', '''methods:{loadAutoReference(){if(this.autoReferenceLoading)return;this.autoReferenceLoading=true;this.autoReferenceError="";return this.$http.get(this.$url.url_5000+"/model_views/diagnosis_reference_settings").then(response=>{const body=response.data||{};if(Number(body.code)!==200||!body.data||typeof body.data.auto_reference_enabled!=="boolean")throw new Error(body.msg||"自动基准设置读取失败");this.autoReferenceEnabled=body.data.auto_reference_enabled;this.autoReferenceSaved=this.autoReferenceEnabled;this.autoReferenceReady=true}).catch(error=>{this.autoReferenceEnabled=this.autoReferenceSaved;this.autoReferenceReady=false;this.autoReferenceError=error.response&&error.response.data&&error.response.data.msg||error.message||"自动基准设置读取失败";this.$message.error(this.autoReferenceError)}).finally(()=>{this.autoReferenceLoading=false})},changeAutoReference(value){if(typeof value!=="boolean"||!this.canSetReference||!this.autoReferenceReady||this.autoReferenceLoading||this.autoReferenceSaving)return;this.autoReferenceEnabled=value;this.autoReferenceSaving=true;return this.$http.post(this.$url.url_5000+"/model_views/diagnosis_reference_settings",{auto_reference_enabled:value},{headers:{"Content-Type":"application/json"}}).then(response=>{const body=response.data||{};if(Number(body.code)!==200||!body.data||typeof body.data.auto_reference_enabled!=="boolean")throw new Error(body.msg||"自动基准设置保存失败");this.autoReferenceEnabled=body.data.auto_reference_enabled;this.autoReferenceSaved=this.autoReferenceEnabled;this.$message.success("自动基准设置已保存")}).catch(error=>{this.autoReferenceEnabled=this.autoReferenceSaved;this.$message.error(error.response&&error.response.data&&error.response.data.msg||error.message||"自动基准设置保存失败");return this.loadAutoReference()}).finally(()=>{this.autoReferenceSaving=false})},getVcr(){''')
    replace('t("div",{staticClass:"content_table"},[t("div",{staticClass:"jia_table"},',
            '''t("div",{staticClass:"content_table"},[t("div",{staticClass:"native-auto-reference",staticStyle:{height:"36px",display:"flex",alignItems:"center",gap:"12px",fontSize:"13px"}},[t("el-switch",{attrs:{value:e.autoReferenceEnabled,disabled:!e.canSetReference||!e.autoReferenceReady||e.autoReferenceLoading||e.autoReferenceSaving,"active-text":"自动建立基准"},on:{change:e.changeAutoReference}}),t("span",{staticStyle:{color:"#909399"}},[e._v(e.autoReferenceLoading?"正在读取基准设置…":e.autoReferenceSaving?"正在保存…":"缺少基准时自动建立；已有基准保留，可手动重设")]),e.autoReferenceError?t("el-button",{attrs:{type:"text",size:"mini",disabled:e.autoReferenceLoading},on:{click:e.loadAutoReference}},[e._v("读取失败，重试")]):e._e()],1),t("div",{staticClass:"jia_table",staticStyle:{height:"calc(100% - 36px)"}},''')
    source = marker + '\n' + source
    digest = hashlib.sha256(source.encode('utf-8')).hexdigest()[:8]
    new_name = chunk_id + '.' + digest + '.js'
    (frontend / 'assets/js' / new_name).write_text(source, encoding='utf-8')
    app = app.replace('"' + chunk_id + '":"' + chunk.group(1) + '"',
                      '"' + chunk_id + '":"' + digest + '"', 1)
    app_path.write_text(app, encoding='utf-8')
    index_path.write_text(index.replace(old_name, new_name), encoding='utf-8')
    return True


def refresh_certificate_help(root, metadata):
    """Describe the deployed public CA while preserving installer validation."""
    frontend = Path(root) / 'frontend'
    certificates = frontend / 'static/certificates'
    values = {key: str(metadata[key]) for key in
              ('subject', 'commonName', 'sha256', 'notBeforeUtc', 'notAfterUtc')}
    values['sha256'] = values['sha256'].upper()
    script_path = certificates / 'install-dispatch-certificate.ps1'
    original_script = script_path.read_text(encoding='utf-8')
    script = original_script
    for variable, key in (('expectedHash', 'sha256'), ('expectedSubject', 'subject')):
        quoted = "'" + values[key].replace("'", "''") + "'"
        script, count = re.subn(r"(?m)^(\$" + variable + r"\s*=\s*)'(?:''|[^'])*'",
                                lambda match: match.group(1) + quoted, script, count=1)
        if count != 1:
            raise ValueError('无法定位证书安装脚本校验字段：' + variable)

    store_marker = '# native-certificate-store-v1'
    if store_marker not in script:
        before = ('$targetPath = Join-Path $storeLocation $certificate.Thumbprint\n'
                  'if (Test-Path -LiteralPath $targetPath) {')
        after = '''# native-certificate-store-v1
function Test-PlatformCertificateTrusted {
    param([string]$Thumbprint)
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store -ArgumentList @(
        [System.Security.Cryptography.X509Certificates.StoreName]::Root,
        [System.Security.Cryptography.X509Certificates.StoreLocation]::CurrentUser
    )
    try {
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
        $matches = $store.Certificates.Find(
            [System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,
            $Thumbprint, $false
        )
        return $matches.Count -gt 0
    }
    finally {
        $store.Close()
    }
}
if (Test-PlatformCertificateTrusted -Thumbprint $certificate.Thumbprint) {'''
        post_import = 'if (-not (Test-Path -LiteralPath $targetPath)) {'
        if script.count(before) != 1 or script.count(post_import) != 1:
            raise ValueError('无法定位证书安装脚本的信任状态检查')
        script = script.replace(before, after, 1).replace(post_import,
            'if (-not (Test-PlatformCertificateTrusted -Thumbprint $certificate.Thumbprint)) {', 1)

    help_path = frontend / 'static/js/certificate-help.js'
    original_help = help_path.read_text(encoding='utf-8')
    help_source = original_help
    for key, value in values.items():
        help_source, count = re.subn(r'(?m)^(\s*' + key + r':\s*).+(,)$',
                                    lambda match: match.group(1) + json.dumps(value, ensure_ascii=False) + match.group(2),
                                    help_source, count=1)
        if count != 1:
            raise ValueError('无法定位证书帮助字段：' + key)
    for old, new in (
        ('根证书已更新为 5 年有效期，旧版用户也需导入新根证书。',
         '安装前请核对当前根证书的主题、SHA256 和有效期；已信任同一指纹的证书无需重复导入。'),
        ("      list.appendChild(metadata('有效期', '5 年'));\n", ''),
        ('新旧根证书名称相同，请以完整 SHA256 区分。安装脚本不会自动删除旧根证书。',
         '请以完整 SHA256 区分根证书。安装脚本不会自动删除旧根证书。'),
        ('此内网配置的 5 年服务证书适用于 Windows Chrome / Edge；Safari / iOS 不保证兼容。上方命令与脚本仅适用于 Windows。macOS、Linux 和 Firefox 的证书存储可能独立，请按本组织终端策略配置，网页不会自动更改这些设置。',
         '上方命令与脚本仅适用于 Windows。Chrome / Edge 使用 Windows 证书存储；macOS、Linux、Firefox、Safari 和 iOS 请按本组织终端策略配置，网页不会自动更改这些设置。'),
        ('根证书已更新，旧版用户也需导入新证书；本提示不代表证书已安装。',
         '请核对本页根证书指纹；已信任同一指纹时无需重复导入。本提示不代表证书已安装。'),
    ):
        help_source = help_source.replace(old, new)

    readme = f'''内网 HTTPS 根证书安装说明

文件：dispatch-root-ca.cer（公开证书，不含私钥）
名称：{values['commonName']}
主题：{values['subject']}
SHA256：{values['sha256']}
生效时间（UTC）：{values['notBeforeUtc']}
到期时间（UTC）：{values['notAfterUtc']}

请以完整 SHA256 区分根证书。已信任同一指纹的证书无需重复导入。
脚本不会自动删除旧根证书。
安装根 CA 表示信任它签发的证书，请先与服务器管理员核对来源和完整指纹。
首次访问若因尚未信任证书而无法打开平台，请由管理员离线提供此安装包，
或由组织统一下发证书；无需绕过浏览器安全告警。

Windows 10 / 11，Windows PowerShell 5.1 或更高版本：
1. 将 ZIP 解压到同一文件夹，保持 .ps1 和 .cer 同目录。
2. 审阅 install-dispatch-certificate.ps1。
3. 如需仅校验公开证书而不安装，在普通 PowerShell 窗口执行：
   & '脚本所在目录\\install-dispatch-certificate.ps1' -ValidateOnly
4. 确认来源与指纹后，需要安装时执行：
   & '脚本所在目录\\install-dispatch-certificate.ps1'
5. 如系统弹出信任确认，核对后确认。已安装的证书会直接跳过。
6. 关闭并重新打开浏览器，再访问 HTTPS 地址。

脚本固定核验证书 SHA256 和 Subject，只导入 Cert:\\CurrentUser\\Root。
-ValidateOnly 仅校验证书，不修改证书信任库。
不要求管理员权限，不修改执行策略，不下载在线代码，不读取或安装私钥。
如组织策略阻止 .ps1，可使用平台“帮助中心 → 证书安装”中的交互命令，
或请终端管理员按组织策略安装；不要为此修改执行策略。

上方命令与脚本仅适用于 Windows。Chrome / Edge 使用 Windows 证书存储；
macOS、Linux、Firefox、Safari 和 iOS 请按组织终端策略配置。
网页本身无法检查本机是否已安装，也不会自动安装证书。
'''
    updates = ((script_path, original_script, script), (help_path, original_help, help_source),
               (certificates / 'README.txt', (certificates / 'README.txt').read_text(encoding='utf-8'), readme))
    changed = False
    for path, original, updated in updates:
        if original != updated:
            path.write_text(updated, encoding='utf-8')
            changed = True
    return changed
