"""Small user/role UI repairs shared by native and existing container releases."""
from pathlib import Path
import re


ACCOUNT_MANAGEMENT_MARKER = '/* native-account-management-v1 */'


def account_management_script():
    return ACCOUNT_MANAGEMENT_MARKER + r'''
;(function(root){
  if(root.__platformAccountManagementV1)return;
  root.__platformAccountManagementV1=true;
  var scopes={"data-v-3b317cf0":"user","data-v-573bb8c3":"role"};
  function protectedRow(kind,row){
    if(!row)return false;
    if(typeof row.is_protected==="boolean")return row.is_protected;
    return kind==="user"?row.username==="sysadmin":
      ["sysadmin","bootstrap_superadmin","bootstrap-admin"].indexOf(row.permission_code)!==-1;
  }
  function props(node){return node.componentOptions&&node.componentOptions.propsData||node.data&&node.data.attrs||{};}
  function protectOperations(node,kind){
    if(!node)return;
    var slots=node.data&&node.data.scopedSlots;
    if(slots&&typeof slots.default==="function"&&props(node).label==="操作"){
      var original=slots.default;
      slots.default=function(scope){
        var buttons=original.apply(this,arguments);
        return protectedRow(kind,scope.row)?buttons.filter(function(button){return props(button).icon!=="el-icon-delete";}):buttons;
      };
      slots.$stable=false;
    }
    (node.children||[]).forEach(function(child){protectOperations(child,kind);});
    var children=node.componentOptions&&node.componentOptions.children;
    if(children&&children!==node.children)children.forEach(function(child){protectOperations(child,kind);});
  }
  function permissionRows(keys){
    var grouped={};
    keys.forEach(function(key){
      var match=String(key).match(/^(\d+)([crud])$/);
      if(!match)return;
      var id=Number(match[1]);
      if(id<1)return;
      var actions=grouped[id]||(grouped[id]=[]);
      if(actions.indexOf(match[2])===-1)actions.push(match[2]);
    });
    return Object.keys(grouped).sort(function(a,b){return Number(a)-Number(b);}).map(function(id){
      return {menu_id:Number(id),permissions_list:"["+grouped[id].join(",")+"]"};
    });
  }
  function checkedPermissions(nodes){
    var keys=[];
    function collect(node){
      var actions=node.permissions_list||[];
      if(typeof actions==="string"){
        try{actions=JSON.parse(actions);}catch(_){actions=actions.replace(/^\s*\[|\]\s*$/g,"").split(",");}
      }
      if(Array.isArray(actions))actions.forEach(function(action){
        action=String(action).trim().replace(/^["']|["']$/g,"");
        var id=Number(node.menu_id);
        if(id>0&&Math.floor(id)===id&&/^[crud]$/.test(action)&&keys.indexOf(id+action)===-1)keys.push(id+action);
      });
      (node.children||[]).forEach(collect);
    }
    nodes.forEach(collect);return keys;
  }
  function openPermissions(row){
    var view=this,id=row.id;
    view.treeTitle="菜单权限";view.treeOpen=true;view.keysId=id;
    view._rolePermissionsLoaded=false;
    var base=String(view.$url&&view.$url.url_5000||root.wgParameter.url_5000||"/api").replace(/\/$/,"");
    return view.$http.get(base+"/role_view/permission_manage_select",{params:{permission_id:id}}).then(function(response){
      if(view.keysId!==id)return;
      var body=response.data||{};
      if(Number(body.code)!==200||!Array.isArray(body.data))throw new Error(body.msg||body.message||"角色权限读取失败");
      return view.$nextTick().then(function(){
        if(view.keysId!==id)return;
        view.$refs.tree.setCheckedKeys(checkedPermissions(body.data));
        view._rolePermissionsLoaded=true;
      });
    }).catch(function(error){
      view.$message({type:"error",message:error.response&&error.response.data&&(error.response.data.msg||error.response.data.message)||error.message||"角色权限读取失败"});
    });
  }
  function savePermissions(){
    var view=this;
    if(view._rolePermissionsSaving)return;
    view._rolePermissionsSaving=true;
    return Promise.resolve().then(function(){
      var tree=view.$refs.tree;
      if(!tree||view._rolePermissionsLoaded===false)throw new Error("菜单权限尚未加载，请稍后重试");
      var keys=view.generateStrings(tree.getCheckedKeys().concat(tree.getHalfCheckedKeys()));
      var data=new FormData();
      data.append("permission_id",view.keysId);
      data.append("permissions_list",JSON.stringify(permissionRows(keys)));
      var base=String(view.$url&&view.$url.url_5000||root.wgParameter.url_5000||"/api").replace(/\/$/,"");
      return view.$http.post(base+"/role_view/permission_manage_update",data,{headers:{"Content-Type":"multipart/form-data"}});
    }).then(function(response){
      var body=response.data||{};
      if(Number(body.code)!==200)throw new Error(body.msg||body.message||"角色授权保存失败");
      view.$message({type:"success",message:body.msg||"角色授权已保存"});
      view.treeOpen=false;
    }).catch(function(error){
      view.$message({type:"error",message:error.response&&error.response.data&&error.response.data.msg||error.message||"角色授权保存失败"});
    }).then(function(){view._rolePermissionsSaving=false;});
  }
  function repair(view,existing){
    var options=view.$options,kind=scopes[options._scopeId];
    if(!kind||!options.methods||options._platformAccountManagementV1)return;
    options._platformAccountManagementV1=true;
    var methods=Object.assign({},options.methods),remove=methods.handleDelete;
    if(remove)methods.handleDelete=function(row){if(!protectedRow(kind,row))return remove.apply(this,arguments);};
    if(kind==="role"&&/generateStrings/.test(String(methods.handleSureKeys||""))&&/processArray/.test(String(methods.handleSureKeys||""))){
      methods.processArray=permissionRows;
      methods.handleAddKey=openPermissions;
      methods.handleSureKeys=savePermissions;
    }
    options.methods=methods;
    var render=options.render;
    if(render)options.render=function(){var node=render.apply(this,arguments);protectOperations(node,kind);return node;};
    if(existing){
      ["handleDelete","handleAddKey","handleSureKeys","processArray"].forEach(function(name){if(methods[name])view[name]=methods[name].bind(view);});
      view.$forceUpdate();
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


def install(root):
    """Ship an image asset too, since upgrades preserve the site's config.js."""
    frontend = Path(root) / 'frontend'
    path = frontend / 'static/js/account-management-v1.js'
    source = account_management_script()
    changed = not path.is_file() or path.read_text(encoding='utf-8') != source
    if changed:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding='utf-8')
    index = frontend / 'index.html'
    text = index.read_text(encoding='utf-8')
    if not re.search(r'static/js/account-management-v1\.js(?:[?"\'])', text):
        index.write_text(text.replace('</head>', '<script src="./static/js/account-management-v1.js"></script></head>', 1), encoding='utf-8')
        changed = True
    return changed
