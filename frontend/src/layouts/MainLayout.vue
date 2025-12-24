<template>
  <el-container class="main-layout">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="sidebar">
      <div class="logo">
        <el-icon :size="28"><TrendCharts /></el-icon>
        <span v-show="!isCollapse">Wind Auto</span>
      </div>
      
      <el-menu
        :default-active="$route.path"
        :collapse="isCollapse"
        :router="true"
        class="sidebar-menu"
        background-color="#1d1e1f"
        text-color="#bfcbd9"
        active-text-color="#409eff"
      >
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <span>首页</span>
        </el-menu-item>
        
        <el-menu-item index="/my-stocks">
          <el-icon><Briefcase /></el-icon>
          <span>我的股票</span>
        </el-menu-item>
        <el-menu-item index="/membership">
          <el-icon><Medal /></el-icon>
          <span>会员中心</span>
        </el-menu-item>
        
        <template v-if="userStore.isAdmin">
          <el-sub-menu index="admin">
            <template #title>
              <el-icon><Setting /></el-icon>
              <span>管理后台</span>
            </template>
            
            <el-menu-item index="/admin/users">
              <el-icon><User /></el-icon>
              <span>用户管理</span>
            </el-menu-item>
            
            <el-menu-item index="/admin/stocks">
              <el-icon><Files /></el-icon>
              <span>股票池</span>
            </el-menu-item>
            
            <el-menu-item index="/admin/allocations">
              <el-icon><Share /></el-icon>
              <span>分配管理</span>
            </el-menu-item>
            
            <el-menu-item index="/admin/config">
              <el-icon><Tools /></el-icon>
              <span>系统配置</span>
            </el-menu-item>
            
            <el-menu-item index="/admin/datasources">
              <el-icon><Connection /></el-icon>
              <span>数据源</span>
            </el-menu-item>
            <el-menu-item index="/admin/signals">
              <el-icon><TrendCharts /></el-icon>
              <span>信号计算</span>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>
    
    <!-- 主内容区 -->
    <el-container>
      <!-- 顶部导航 -->
      <el-header class="header">
        <div class="header-left">
          <el-icon 
            class="collapse-btn" 
            :size="20" 
            @click="isCollapse = !isCollapse"
          >
            <Fold v-if="!isCollapse" />
            <Expand v-else />
          </el-icon>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="$route.meta.title">
              {{ $route.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="header-right">
          <el-tag 
            :class="['vip-tag', `vip-${userStore.vipLevel}`]"
            size="small"
          >
            {{ vipLevelText }}
          </el-tag>
          
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="32" :icon="UserFilled" />
              <span class="username">{{ userStore.user?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>个人信息
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <!-- 内容区 -->
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { UserFilled } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()
const isCollapse = ref(false)

const vipLevelText = computed(() => {
  const levels = ['免费用户', 'VIP1', 'VIP2', 'VIP3', 'SVIP']
  return levels[userStore.vipLevel] || '未知'
})

function handleCommand(command) {
  if (command === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped lang="scss">
.main-layout {
  height: 100vh;
}

.sidebar {
  background-color: #1d1e1f;
  transition: width 0.3s;
  overflow: hidden;
  
  .logo {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    color: #fff;
    font-size: 18px;
    font-weight: 600;
    border-bottom: 1px solid #333;
  }
  
  .sidebar-menu {
    border-right: none;
    
    &:not(.el-menu--collapse) {
      width: 220px;
    }
  }
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid var(--border-color);
  padding: 0 20px;
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    
    .collapse-btn {
      cursor: pointer;
      color: var(--text-regular);
      
      &:hover {
        color: var(--primary-color);
      }
    }
  }
  
  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;
    
    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      
      .username {
        color: var(--text-primary);
      }
    }
  }
}

.main-content {
  background: var(--bg-color);
  padding: 20px;
  overflow-y: auto;
}
</style>
