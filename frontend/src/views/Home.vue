<!-- Restored from the server app source map. Platform layout builds CSS only; the current runtime JavaScript, routes and navigation guards are preserved. -->
<template>
  <div class="home">
    <div class="home_title">
      <div class="title">
        <!-- <img src="../img/home/LOGO.png" alt=""> -->
        <img src="../img/home/LOGO3.png" alt="">
      </div>
      <!-- <span><i class="el-icon-user-solid"></i>admin</span> -->
      <div class="avator">
        <!-- <div class="home_system">
          <div class="icon">
            <img src="../img/home/帮助中心.png" alt="">
          </div>
          &nbsp;
          <div class="text">帮助中心&nbsp;&nbsp;|</div>
        </div> -->
        <el-dropdown class="avatar-container right-menu-item hover-effect" trigger="click" @visible-change="handleDropdownVisibleChange">
          <div class="avatar-wrapper" style="cursor: pointer">
            <img src="../img/home/帮助中心.png" class="user-avatar" style="float: left;width: 21px;height: 20px;" />
            <!-- <i class="el-icon-user-solid" style="float: left;color: #ffffff;"></i> -->
            <div style="
                  color: #ffffff;
                  font-size: 12px;
                  line-height: 14px;
                  font-family: 'Microsoft YaHei';
                  text-align: center;
                  float: left;
                  margin-left: 12px;
                  margin-top: 5px;
                ">
              帮助中心
            </div>
            <i :class="{'el-icon-caret-bottom': !isDropdownVisible, 'el-icon-caret-top': isDropdownVisible}" style="float: left;color: #ffffff;margin-top: 5px;margin-left: 8px;" />
          </div>
          <el-dropdown-menu slot="dropdown">
            <el-dropdown-item @click.native="handleSelect1">
              <span title="视频AI识别分析管理平台操作指导手册" style="display: block;width: 150px;overflow:hidden;white-space: nowrap;text-overflow: ellipsis;-o-text-overflow:ellipsis;">视频AI识别分析管理平台操作指导手册</span>
            </el-dropdown-item>
            <el-dropdown-item @click.native="handleSelect2">
              <span title="海康安防平台接入视频AI识别分析管理平台" style="display: block;width: 150px;overflow:hidden;white-space: nowrap;text-overflow: ellipsis;-o-text-overflow:ellipsis;">海康安防平台接入视频AI识别分析管理平台</span>
            </el-dropdown-item>
            <!-- <el-dropdown-item @click.native="handleSelect4">
              <span title="AI智能视觉算法指导手册" style="display: block;width: 150px;overflow:hidden;white-space: nowrap;text-overflow: ellipsis;-o-text-overflow:ellipsis;">AI智能视觉算法指导手册</span>
            </el-dropdown-item> -->
            <el-dropdown-item @click.native="handleSelect3">
              <span>关于</span>
            </el-dropdown-item>
          </el-dropdown-menu>













        </el-dropdown>
        <el-dropdown class="avatar-container right-menu-item hover-effect" trigger="click" @visible-change="handleDropdownVisibleChange">
          <div class="avatar-wrapper" style="cursor: pointer">
            <img src="../img/home/用户头像.png" class="user-avatar" style="float: left;width: 21px;height: 20px;" />
            <!-- <i class="el-icon-user-solid" style="float: left;color: #ffffff;"></i> -->
            <div style="
                  color: #ffffff;
                  font-size: 12px;
                  line-height: 14px;
                  font-family: 'Microsoft YaHei';
                  text-align: center;
                  float: left;
                  margin-left: 12px;
                  margin-top: 5px;
                ">
              {{ usernames }}
            </div>
            <i :class="{'el-icon-caret-bottom': !isDropdownVisible, 'el-icon-caret-top': isDropdownVisible}" style="float: left;color: #ffffff;margin-top: 5px;margin-left: 8px;" />
          </div>
          <el-dropdown-menu slot="dropdown">
            <el-dropdown-item @click.native="handleSelect">
              <span>退出登录</span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </el-dropdown>
      </div>
    </div>
    <div class="home_menu" v-if="activateOpen">
      <div class="menu">
        <el-menu :default-active="handleActive" class="el-menu-vertical-demo" unique-opened>
          <!-- <el-menu-item index="0-1" @click="handleOpen('硬件信息导出','activatebywjj')" v-if="!activateOpen"> -->
          <el-menu-item index="0-1" @click="handleOpen('硬件信息导出','activatebywjj')" v-show="false">
            <i class="el-icon-bangzhu"></i>
            <span slot="title">硬件信息导出</span>
          </el-menu-item>
          <!-- <el-menu-item index="0-2" @click="handleOpen('激活文件导入','activate2')" v-if="!activateOpen">
            <i class="el-icon-bangzhu"></i>
            <span slot="title">激活文件导入</span>
          </el-menu-item> -->
          <template v-for="(item, index) in menuData">
            <el-menu-item v-if="!item.children" :index="`${index + 1}`" :key="index + 1" @click="handleOpen(item.menu_name, item.menu_link)">
              <!-- <i :class="item.menu_icon"></i> -->
              <img :src="findNoActive(item.menu_name)" class="imgNoActive">
              <img :src="findActive(item.menu_name)" class="imgActive">&nbsp;&nbsp;
              <span slot="title">{{ item.menu_name }}</span>
            </el-menu-item>
            <el-submenu v-else :index="`${index + 1}`" :key="(index + 1)">
              <template slot="title">
                <!-- <i :class="item.menu_icon"></i> -->
                <img :src="findNoActive(item.menu_name)" class="imgNoActive">
                <img :src="findActive(item.menu_name)" class="imgActive">&nbsp;&nbsp;
                <!-- <img :src="findNoActive(item.menu_name)">&nbsp;&nbsp; -->
                <span>{{ item.menu_name }}</span>
              </template>
              <!-- Loop through children of current item -->
              <template v-for="(child, childIndex) in item.children">
                <el-menu-item :index="`${index + 1}-${childIndex + 1}`" :key="`${index + 1}-${childIndex + 1}`" @click="handleOpen(child.menu_name, child.menu_link)">
                  <!-- <i :class="child.menu_icon"></i> -->
                  <!-- <img :src="findNoActive(item.menu_name)" class="imgNoActive">
                  <img :src="findActive(item.menu_name)" class="imgActive">&nbsp;&nbsp; -->
                  <div class="point"></div>
                  <span class="spanbox">{{ child.menu_name }}</span>
                </el-menu-item>
              </template>
            </el-submenu>
          </template>
        </el-menu>
      </div>
    </div>
    <div class="home_content" v-if="activateOpen">
      <div class="menu_content">
        <div class="menu_content_title">{{ menuName }}</div>
        <div class="contents">
          <router-view></router-view>
        </div>
      </div>
    </div>
    <div class="home_content1" v-if="!activateOpen">
      <div class="menu_content">
        <div class="menu_content_title">{{ menuName }}</div>
        <div class="contents">
          <router-view></router-view>
        </div>
      </div>
    </div>


    <el-dialog
      title="关于" :visible.sync="centerDialogVisible" width="30%">
      <div class="div">
        <div class="imgs"></div>
        <p>视频AI识别分析管理平台</p>
        <div class="info">
          <span>版本信息: </span><span>{{objinfo}}</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import axios from 'axios'
import store from '../store'
import { loginApi } from '../api/login.js';
// 引入JSON文件
import activeImg from './active.json'
import noActiveImg from './noActive.json'
export default {
  name: 'Home',
  components: {

  },
  data() {
    return {
      usernames:'',
      menuName: "",
      menuData: [],
      objinfo:'0.0.0',
      centerDialogVisible:false,
      // 判断系统激活与未激活的开关控制
      activateOpen: true,
      system: window.wgParameter.system,
      isDropdownVisible: false,
    }
  },
  computed: {
    handleActive() {
      const route = this.$route
      const { path, name } = route
      return this.handleIndex(name)
    },
  },
  created() {
    this.usernames = localStorage.getItem('userRoleName');
    this.getJudgment();
    // this.getMenuData();
  },
  methods: {
    handleSelect1() {
        window.open('/static/视频AI识别分析管理平台操作指导手册.pdf?v=20261018', '_blank');
    },
    handleSelect2() {
        window.open('/static/海康安防平台接入视频AI识别分析管理平台.pdf', '_blank');
    },
    handleSelect4() {
        window.open('/static/AI智能视觉算法指导手册.pdf', '_blank');
    },
    handleSelect3() {
        this.axioss()
        this.centerDialogVisible = true;
    },
    handleDropdownVisibleChange(val) {
      this.isDropdownVisible = val;
    },
    // 系统激活判断
    getJudgment() {
      if (this.system == 'JY' || this.system == 'UWB') {
        this.$http.get(loginApi.activateJudgment)
          .then(response => {
            if (response.data.code == 400) {
              this.activateOpen = false
            } else {
              this.activateOpen = true
              this.getMenuData()
            }
          })
          .catch(rek => {
            console.log(rek);
          })
      } else if (this.system == 'TFS') {
        this.activateOpen = true
        this.getMenuData()
      }

    },
    // 获取菜单的编号
    handleIndex(s) {
      var name;
      if(s == 'sfgl_child' || s == 'sfgl_childs'){
        name = 'sfgl'
      }else if(s == 'sxtpz_child' || s == 'sxtpz_childs'){
        name = 'sxtpz'
      }else{
        name = s
      }
      const menuData = this.menuData
      for (let i = 0; i < menuData.length; i++) {
        const menuItem = menuData[i];

        // Check if the current item matches the given name
        if (menuItem.menu_link === name) {
          return `${i + 1}`; // Return the index if name matches
        }

        console.log(menuItem,'--------')
console.log(name,'--------')
        // If item has children, check within children
        if (menuItem.children) {
          for (let j = 0; j < menuItem.children.length; j++) {
            const childItem = menuItem.children[j];
            if (childItem.menu_link === name) {
              return `${i + 1}-${j + 1}`; // Return child index if name matches
            }
          }
        }
      }
      return null; // Return null if no matching name found
    },
    // 获取当前菜单的名字
    handleIndexName(name) {
      const menuData = this.menuData
      for (let i = 0; i < menuData.length; i++) {
        const menuItem = menuData[i];

        // Check if the current item matches the given name
        if (menuItem.menu_link === name) {
          return menuItem.menu_name; // Return the index if name matches
        }

        // If item has children, check within children
        if (menuItem.children) {
          for (let j = 0; j < menuItem.children.length; j++) {
            const childItem = menuItem.children[j];
            if (childItem.menu_link === name) {
              return childItem.menu_name; // Return child index if name matches
            }
          }
        }
      }
      return null; // Return null if no matching name found
    },
    handleOpen(a, b) {
      this.menuName = a
      if (!b) return
      this.$router.push({ path: '/' + String(b).replace(/^\/+/, '') }).catch(error => {
        if (error.name !== 'NavigationDuplicated') console.error(error)
      })
    },
    handleMenuName() {
      const route = this.$route
      const { path, name } = route
      this.menuName = this.handleIndexName(name) || route.meta.title || ''
    },
    getMenuData() {
      this.$http.get(this.$url.url_5000 + '/menu_view/menu_show', {
        params: {
          user_id: this.$store.state.userId || localStorage.getItem('userId')
        },
      }).then(response => {

        this.menuData = response.data.menu_list
        store.state.menuData = response.data.menu_list
        this.handleMenuName()
      }).catch(rek => {
        console.log(rek);
      })
    },
    // 退出登陆
    handleSelect() {
      this.$confirm("确定注销并退出系统吗？", "提示", {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      })
        .then(() => {
          this.clearCookies();
          // 清除本地存储中的所有数据
          localStorage.clear();
          sessionStorage.clear();
          this.$router.go(0);
        })
        .catch(() => { });
    },
    // 清除Cookie
    clearCookies() {
      // 获取当前的所有 Cookies
      const cookies = document.cookie.split(";");

      // 循环删除每个 Cookie
      for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i];
        const eqPos = cookie.indexOf("=");
        const name = eqPos > -1 ? cookie.substr(0, eqPos) : cookie;
        document.cookie =
          name + "=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/";
      }
    },
    findActive(queryName) {
      let bestMatch = null;
      let highestScore = -Infinity;

      // 遍历数组，找到最佳匹配
      activeImg.forEach(item => {
        const score = this.calculateScore(queryName, item.name);
        // console.log("相似度匹配",score)
        if (score > highestScore) {
          highestScore = score;
          bestMatch = item.path;
        }
      });

      return bestMatch;
    },
    findNoActive(queryName) {
      let bestMatch = null;
      let highestScore = -Infinity;

      // 遍历数组，找到最佳匹配
      noActiveImg.forEach(item => {
        const score = this.calculateScore(queryName, item.name);
        if (score > highestScore) {
          highestScore = score;
          bestMatch = item.path;
        }
      });

      return bestMatch;
    },
    // 计算字符串匹配得分
    calculateScore(query, name) {
      const queryLength = query.length;
      const nameLength = name.length;
      let score = 0;

      // 检查前缀和部分匹配
      if (query === name.substring(0, queryLength)) {
        score += 1; // 完全前缀匹配
      } else {
        // 查找部分匹配
        const parts = name.split(' ');
        for (const part of parts) {
          if (part.includes(query)) {
            score += 1 / parts.length; // 部分匹配得分
          }
        }
      }

      return score;
    },
    axioss() {
      this.$http
        .get(
          this.$url.url_5000 + "/model_view/version_show",
          {
            params: {},
          },
          {
            withCredentials: true,
          }
        )
        .then((response) => {
          if (response.data.code === 200) {
            this.objinfo = response.data.data
          }
        })
    },

  },
  mounted() {
    this.handleMenuName()
    // 无需主动加载，默认加载第一项
    // this.handleOpen('实时视频', 'sssp')
  }
}
</script>

<style lang="scss" scoped>
  .spanbox{
    width: 100px;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
    -o-text-overflow: ellipsis;
  }
  .div{
    width: 100%;height: 200px;
    text-align: center;
    P{
      font-weight: bold;
      font-size: 18px;
    }
    .imgs{
      width: 80px;
      height: 80px;
      margin: 0 auto;
      background: url(~@/assets/icon.jpg) no-repeat;
      background-size: 100% 100%;
    }
  }
  .el-dropdown-link {
    cursor: pointer;
    color: #fff;
  }
  .el-icon-arrow-down {
    font-size: 12px;
  }
.home {
  width: 100%;
  height: 100%;
  position: relative;

  .home_title {
    width: 100%;
    height: 56px;
    // background: #ffffff;
    // background-color: #1c2b36;
    background-image: url(../img/home/home_top.png);
    background-position: center;
    background-repeat: no-repeat;
    background-size: cover;
    display: flex;
    justify-content: space-between;
    align-items: center;
    .title {
      width: 270px;
      // width: 177px;
      height: 56px;
      display: flex;
      justify-content: center;
      align-items: center;
      scale: 0.9;
      img {
        // width: 177px;
        width: 270px;
        height: 33px;
        // width: 157px;
        // height: 25px;
      }
    }
    .avator {
      width: 20%;
      height: 100%;
      display: flex;
      justify-content: flex-end;
      align-items: center;
      padding-right: 15px;
      .home_system {
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        cursor: pointer;
        .icon {
          width: 14px;
          height: 14px;
          img {
            width: 14px;
            height: 14px;
          }
        }
        .text {
          width: 68px;
          height: 14px;
          font-size: 12px;
          color: #ffffff;
          line-height: 14px;
          text-align: left;
        }
      }
    }
  }

  .home_menu {
    width: 200px;
    height: calc(100% - 56px);
    border-right: 1px solid #e6e6e6;
    box-sizing: border-box;
    background-color: #fafbfd;
    position: absolute;
    top: 56px;
    left: 0;
    .menu {
      width: 100%;
      height: 100%;
      background: #fafbfd;
      overflow: hidden;
      overflow-y: scroll;
      background-image: url('../img/home/placeholder_left.png');
    background-position: bottom;
    background-size: 100% 45%;
    background-repeat: no-repeat;
    }
    /* 隐藏滚动条 */
    .menu::-webkit-scrollbar {
      width: 0px;
      background: transparent;
    }
  }

  .home_content {
    width: calc(100% - 200px);
    height: calc(100% - 56px);
    position: absolute;
    top: 56px;
    left: 200px;
    background-color: #f4f3f8;

    .menu_content {
      width: 100%;
      height: 100%;
      padding-top: 20px;

      .menu_content_title {
        width: calc(100% - 37px);
        height: 40px;
        display: flex;
        align-items: center;
        font-family: "Microsoft YaHei";
        font-weight: bold;
        font-size: 14px;
        color: #2d89ff;
        padding-left: 24px;
        margin-left: 24px;
        box-sizing: border-box;
        background-image: url('../img/home/placeholder_top.png');
        background-position: center;
        background-size: 100% 100%;
        background-repeat: no-repeat;
      }

      .contents {
        width: calc(100% - 37px);
        height: calc(100% - 87px);
        position: absolute;
        top: 60px;
        left: 24px;
        // background-color: #ffffff;
        // border-radius: 8px;
        // border: 1px solid #e7e7e9;
        // background-image: url('../img/home/placeholder_bottom.png');
        // background-position: bottom;
        // background-size: 100% 60%;
        // background-repeat: no-repeat;
      }
    }
  }
  .home_content1 {
    width: 100%;
    height: calc(100% - 56px);
    position: absolute;
    top: 56px;
    left: 0px;
    background-color: #f4f3f8;

    .menu_content {
      width: 100%;
      height: 100%;
      padding-top: 20px;

      .menu_content_title {
        width: calc(100% - 37px);
        height: 40px;
        display: flex;
        align-items: center;
        font-family: "Microsoft YaHei";
        font-weight: bold;
        font-size: 14px;
        color: #2d89ff;
        padding-left: 24px;
        margin-left: 24px;
        box-sizing: border-box;
        background-image: url('../img/home/placeholder_top.png');
        background-position: center;
        background-size: 100% 100%;
        background-repeat: no-repeat;
      }

      .contents {
        width: calc(100% - 37px);
        height: calc(100% - 87px);
        position: absolute;
        top: 60px;
        left: 24px;
        // background-color: #ffffff;
        // border-radius: 8px;
        // border: 1px solid #e7e7e9;
        // background-image: url('../img/home/placeholder_bottom.png');
        // background-position: bottom;
        // background-size: 100% 60%;
        // background-repeat: no-repeat;
      }
    }
  }
}

.home {
  .el-menu-vertical-demo {
    background: transparent;

    ::v-deep .el-submenu {
      .el-submenu__title {
        height: 40px;
        line-height: 40px;
        background: transparent;
      }
    }

    ::v-deep .el-menu-item {
      height: 40px;
      line-height: 40px;
    }
  }

  ::v-deep.el-menu {
    background: transparent;
    border: none;

    .imgNoActive {
      display: block;
    }

    .imgActive {
      display: none;
    }
  }

  ::v-deep .el-menu-item {
    width: 170px;
    height: 40px;
    line-height: 40px;
    background-color: #fafbfd !important;

    .imgNoActive {
      display: inline-block;
    }

    .imgActive {
      display: none;
    }
  }

  .el-submenu .el-menu-item {
    width: 170px;
    height: 40px;
    font-weight: bold;
    position: relative;
    left: 16px;
    color: #79818e;
    display: flex;
    justify-content: flex-start;
    align-items: center;

    .point {
      width: 4px;
      height: 4px;
      background-color: #79818e;
      border-radius: 50%;
      margin-right: 6px;
    }
  }

  /* 自定义选中状态的样式 */
  ::v-deep .el-menu-item.is-active {
    width: 170px;
    height: 40px;
    background-color: #0569ff !important; /* 背景颜色 */
    color: #ffffff; /* 文字颜色 */
    font-weight: bold; /* 加粗文字 */
    position: relative;
    left: 16px;
    border-radius: 5px;

    .imgActive {
      display: inline-block;
    }

    .imgNoActive {
      display: none;
    }

    &:before {
      /* 使用伪元素实现边框效果 */
      content: "";
      position: absolute;
      left: -16px;
      top: 0;
      bottom: 0;
      width: 4px;
      border-radius: 2px;
      background-color: #1962ec;
    }
  }

  ::v-deep .el-submenu.is-opened.is-active {
    .el-submenu__title {
      width: 170px;
      height: 40px;
      background-color: #0569ff !important; /* 背景颜色 */
      color: #ffffff; /* 文字颜色 */
      font-weight: bold; /* 加粗文字 */
      position: relative;
      left: 16px;
      border-radius: 5px;
      i {
        color: #ffffff;
      }

      .imgActive {
        display: inline-block;
      }

      .imgNoActive {
        display: none;
      }

      &:before {
        /* 使用伪元素实现边框效果 */
        content: "";
        position: absolute;
        left: -16px;
        top: 0;
        bottom: 0;
        width: 4px;
        border-radius: 2px;
        background-color: #1962ec;
      }
    }
    .el-menu {
      .el-menu-item.is-active {
        background-color: transparent !important;
        color: #0569ff;
        .point {
          background-color: #0569ff;
        }
        &::before {
          content: ""; /* 清空内容 */
          display: block; /* 保留占位，可以设置为 inline 或 block */
          width: 0;
          height: 0;
          margin: 0;
          padding: 0;
        }
      }
    }
  }

  /* 自定义悬停状态的样式 */
  .el-submenu {
    .el-menu-item:hover,
    .el-submenu .el-submenu__title:hover {
      width: 170px;
      height: 40px;
      background-color: #edf1fc !important; /* 背景颜色 */
      color: #1962ec; /* 文字颜色 */
      font-weight: bold; /* 加粗文字 */
      position: relative;
      left: 16px;

      .point {
        background-color: #1962ec;
      }
      span {
        color: #1962ec;
      }
    }
  }

  .el-menu-item,
  .el-submenu .el-submenu__title {
    .imgNoActive {
      display: inline-block;
    }

    .imgActive {
      display: none;
    }
  }
}
</style>

<!-- Root-scoped plain CSS; the builder supplies this server's existing Home scope ID. -->
<style scoped data-platform-layout>
.home {
  --platform-sidebar: 216px;
  display: grid;
  grid-template-columns: var(--platform-sidebar) minmax(0, 1fr);
  grid-template-rows: 56px minmax(0, 1fr);
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  box-sizing: border-box;
  background: var(--platform-background, #f4f7fb);
  color: var(--platform-text, #334155);
  font-family: Arial, "Microsoft YaHei", sans-serif;
}
.home > .home_title {
  grid-column: 1 / -1;
  grid-row: 1;
  position: relative;
  width: 100%;
  height: 56px;
  min-width: 0;
  gap: 12px;
  z-index: 10;
  background: var(--platform-primary, #2563eb);
  color: #fff;
  border-bottom: 1px solid rgba(255, 255, 255, .12);
  box-shadow: 0 1px 3px rgba(15, 23, 42, .08);
  box-sizing: border-box;
}
.home .home_title .title {
  width: 264px;
  flex: 0 0 auto;
  justify-content: flex-start;
  padding-left: 20px;
  box-sizing: border-box;
  scale: 1;
}
.home .home_title .title img {
  width: 236px;
  max-width: 100%;
  height: auto;
}
.home .home_title .avator {
  width: auto;
  min-width: 0;
  gap: 12px;
  padding-right: 20px;
  flex: 0 0 auto;
  box-sizing: border-box;
}
.home .home_title .avator .el-dropdown {
  color: #fff;
}
.home .home_title .avatar-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 5px 8px;
  border-radius: 6px;
  box-sizing: border-box;
  color: #fff;
}
.home .home_title .avatar-wrapper:hover {
  background: rgba(255, 255, 255, .1);
}
.home .home_title .avatar-wrapper > :is(div, i, img) {
  float: none !important;
  margin: 0 !important;
}
.home .home_title .avatar-wrapper > div {
  line-height: 20px !important;
  white-space: nowrap;
}
.home .home_title .avatar-wrapper > i {
  color: #fff !important;
}
.home .home_title .avatar-wrapper:focus-visible {
  outline: 2px solid rgba(255, 255, 255, .8);
  outline-offset: 2px;
}
.home > .home_menu {
  grid-column: 1;
  grid-row: 2;
  position: relative;
  top: auto;
  left: auto;
  width: auto;
  height: auto;
  min-height: 0;
  overflow: hidden;
  border-right: 1px solid var(--platform-border, #e2e8f0);
  background: var(--platform-surface, #fff);
}
.home .home_menu .menu {
  width: 100%;
  height: 100%;
  padding: 14px 10px 18px;
  box-sizing: border-box;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: #cbd5e1 transparent;
  background: var(--platform-surface, #fff);
}
.home .home_menu .menu::-webkit-scrollbar { width: 5px; background: transparent; }
.home .home_menu .menu::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
.home .home_menu .el-menu { background: transparent; border-right: 0; }
.home .home_menu :is(.el-menu-item, .el-submenu__title) {
  display: flex;
  align-items: center;
  width: 100% !important;
  min-height: 42px;
  height: auto !important;
  line-height: 20px !important;
  padding: 10px 12px !important;
  margin: 3px 0;
  position: relative;
  left: 0 !important;
  border-radius: 6px;
  color: var(--platform-text, #334155);
  background: transparent !important;
  font-size: 13px;
  box-sizing: border-box;
}
.home .home_menu .el-submenu__title { padding-right: 30px !important; }
.home .home_menu :is(.imgNoActive, .imgActive) { flex: 0 0 auto; width: 18px; height: 18px; }
.home .home_menu .imgNoActive { opacity: .8; }
.home .home_menu .el-submenu__title .el-submenu__icon-arrow { color: #94a3b8; right: 12px; }
.home .home_menu .el-menu .el-submenu__title img.imgActive[src=""],
.home .home_menu .el-menu .el-submenu__title img.imgActive:not([src]) {
  content: url("/static/img/home/menu_video.png");
  filter: brightness(0) invert(1);
}
.home .home_menu .spanbox {
  flex: 1;
  width: auto;
  min-width: 0;
  max-width: 100%;
  white-space: normal;
  overflow-wrap: anywhere;
}
.home .home_menu .el-submenu__title > span { min-width: 0; white-space: normal; overflow-wrap: anywhere; }
.home .home_menu .el-submenu .el-menu-item {
  min-height: 36px;
  padding: 8px 12px 8px 30px !important;
  font-size: 12px;
  font-weight: 400;
  color: var(--platform-muted, #64748b);
}
.home .home_menu .el-menu-item .point { flex: 0 0 4px; background: #94a3b8; }
.home .home_menu :is(.el-menu-item, .el-submenu__title):hover {
  color: var(--platform-primary, #2563eb) !important;
  background: var(--platform-subtle, #f8fafc) !important;
}
.home .home_menu .menu > .el-menu > .el-menu-item.is-active,
.home .home_menu .menu > .el-menu > .el-submenu.is-active > .el-submenu__title,
.home .home_menu .el-submenu.is-opened.is-active > .el-submenu__title {
  color: #fff !important;
  background: var(--platform-primary, #2563eb) !important;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(37, 99, 235, .12);
}
.home .home_menu .el-menu-item.is-active:before,
.home .home_menu .el-submenu.is-opened.is-active > .el-submenu__title:before {
  left: 0;
  width: 3px;
  background: var(--platform-primary, #2563eb);
}
.home .home_menu .el-submenu .el-menu-item.is-active {
  background: #eff6ff !important;
  color: var(--platform-primary, #2563eb) !important;
  font-weight: 500;
  box-shadow: none;
}
.home .home_menu .el-submenu .el-menu-item.is-active:before { display: none; }
.home .home_menu .el-submenu .el-menu-item.is-active .point { background: var(--platform-primary, #2563eb); }
.home .home_menu .el-submenu.is-active > .el-submenu__title i { color: #fff !important; }
.home .home_menu .el-submenu.is-active > .el-submenu__title .imgActive { display: inline-block; }
.home .home_menu .el-submenu.is-active > .el-submenu__title .imgNoActive { display: none; }
.home .home_menu :is(.el-menu-item, .el-submenu__title):focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: -2px;
}
.home > :is(.home_content, .home_content1) {
  grid-column: 2;
  grid-row: 2;
  position: relative;
  top: auto;
  left: auto;
  width: auto;
  height: auto;
  min-width: 0;
  min-height: 0;
  background: var(--platform-background, #f4f7fb);
}
.home > .home_content1 { grid-column: 1 / -1; }
.home :is(.home_content, .home_content1) > .menu_content {
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  min-width: 0;
  min-height: 0;
  padding: 16px 20px;
  box-sizing: border-box;
}
.home :is(.home_content, .home_content1) > .menu_content > .menu_content_title {
  flex: 0 0 32px;
  display: flex;
  align-items: center;
  width: 100%;
  height: 32px;
  min-width: 0;
  margin: 0 0 12px;
  padding: 0 2px;
  background: transparent;
  color: var(--platform-text, #334155);
  font-size: 15px;
  font-weight: 600;
  border: 0;
  border-radius: 0;
  box-sizing: border-box;
}
.home :is(.home_content, .home_content1) > .menu_content > .menu_content_title:before {
  content: "";
  flex: 0 0 3px;
  width: 3px;
  height: 14px;
  margin-right: 10px;
  border-radius: 2px;
  background: var(--platform-primary, #2563eb);
}
.home :is(.home_content, .home_content1) > .menu_content > .contents {
  flex: 1 1 0;
  position: relative;
  top: auto;
  left: auto;
  width: 100%;
  height: auto;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  background: transparent;
  box-sizing: border-box;
}
@media (max-width: 1200px) {
  .home { --platform-sidebar: 200px; }
  .home :is(.home_content, .home_content1) > .menu_content { padding: 14px 16px; }
}
@media (max-width: 900px) {
  .home { --platform-sidebar: 176px; }
  .home .home_menu .menu { padding: 12px 7px; }
  .home .home_title .title { width: 236px; padding-left: 16px; }
  .home .home_title .title img { width: 216px; }
  .home .home_title .avator { gap: 6px; padding-right: 12px; }
  .home :is(.home_content, .home_content1) > .menu_content { padding: 12px; }
}
@media (max-width: 600px) {
  .home { --platform-sidebar: 160px; }
  .home > .home_title { gap: 6px; }
  .home .home_title .title { width: 165px; padding-left: 12px; }
  .home .home_title .title img { width: 145px; }
  .home .home_title .avator { gap: 4px; padding-right: 8px; }
  .home .home_title .avatar-wrapper { gap: 6px; padding: 5px 4px; }
  .home .home_title .avatar-wrapper > div { max-width: 84px; overflow: hidden; text-overflow: ellipsis; }
  .home .home_title .avatar-wrapper .user-avatar { width: 18px !important; height: 18px !important; }
  .home .home_title .avatar-wrapper > i { font-size: 12px; }
  .home .home_menu .menu { padding: 10px 6px; }
  .home .home_menu :is(.el-menu-item, .el-submenu__title) { padding-left: 9px !important; font-size: 12px; }
  .home .home_menu .el-submenu__title { padding-right: 24px !important; }
  .home .home_menu .el-submenu .el-menu-item { padding-left: 24px !important; }
  .home .home_menu .el-submenu__icon-arrow { right: 8px; }
  .home :is(.home_content, .home_content1) > .menu_content { padding: 10px 8px; }
  .home :is(.home_content, .home_content1) > .menu_content > .menu_content_title { font-size: 14px; margin-bottom: 8px; }
}
@media (max-width: 380px) {
  .home { --platform-sidebar: 152px; }
  .home .home_title .title { width: 148px; padding-left: 8px; }
  .home .home_title .title img { width: 136px; }
  .home .home_title .avatar-wrapper { gap: 4px; padding-left: 2px; padding-right: 2px; }
  .home .home_title .avatar-wrapper > div { max-width: 66px; font-size: 11px !important; }
}
</style>
