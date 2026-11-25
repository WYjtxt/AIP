/* native-template-administrator-v1 */
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
