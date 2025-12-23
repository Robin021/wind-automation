<template>
  <div class="dashboard">
    <!-- 欢迎卡片 -->
    <el-card class="welcome-card">
      <div class="welcome-content">
        <div class="welcome-text">
          <h2>👋 欢迎回来，{{ userStore.user?.username }}！</h2>
          <p>今天是 {{ today }}，祝您投资顺利～</p>
        </div>
        <el-tag 
          :class="['vip-tag', `vip-${userStore.vipLevel}`]"
          size="large"
        >
          {{ vipLevelText }}
        </el-tag>
      </div>
    </el-card>
    
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
            <el-icon :size="28"><Briefcase /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.myStocks }}</div>
            <div class="stat-label">我的股票</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);">
            <el-icon :size="28"><TrendCharts /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.signals }}</div>
            <div class="stat-label">今日信号</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);">
            <el-icon :size="28"><DataLine /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.stockLimit }}</div>
            <div class="stat-label">股票额度</div>
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon" style="background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%);">
            <el-icon :size="28"><Calendar /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats.daysRemaining }}</div>
            <div class="stat-label">会员剩余天数</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 快捷操作 -->
    <el-row :gutter="20">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>我的股票</span>
              <el-button type="primary" text @click="$router.push('/my-stocks')">
                查看全部 <el-icon><ArrowRight /></el-icon>
              </el-button>
            </div>
          </template>
          
          <el-table :data="recentStocks" style="width: 100%" v-loading="loading">
            <el-table-column prop="stock_code" label="代码" width="120" />
            <el-table-column prop="stock_name" label="名称" />
            <el-table-column prop="batch_date" label="分配日期" width="120" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
                  {{ row.status === 'active' ? '有效' : '已过期' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          
          <el-empty v-if="!loading && recentStocks.length === 0" description="暂无分配的股票" />
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>快捷操作</span>
          </template>
          
          <div class="quick-actions">
            <el-button 
              class="action-btn"
              @click="$router.push('/my-stocks')"
            >
              <el-icon :size="24"><Briefcase /></el-icon>
              <span>查看股票</span>
            </el-button>
            
            <el-button 
              v-if="userStore.isAdmin"
              class="action-btn"
              @click="$router.push('/admin/allocations')"
            >
              <el-icon :size="24"><Share /></el-icon>
              <span>分配股票</span>
            </el-button>
            
            <el-button 
              v-if="userStore.isAdmin"
              class="action-btn"
              @click="$router.push('/admin/users')"
            >
              <el-icon :size="24"><User /></el-icon>
              <span>用户管理</span>
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import dayjs from 'dayjs'
import { useUserStore } from '@/stores/user'
import api from '@/api'

const userStore = useUserStore()
const loading = ref(false)
const recentStocks = ref([])

const today = computed(() => dayjs().format('YYYY年MM月DD日'))

const vipLevelText = computed(() => {
  const levels = ['免费用户', 'VIP1', 'VIP2', 'VIP3', 'SVIP']
  return levels[userStore.vipLevel] || '未知'
})

const stats = ref({
  myStocks: 0,
  signals: 0,
  stockLimit: 5,
  daysRemaining: '∞',
})

async function fetchData() {
  loading.value = true
  try {
    const res = await api.get('/allocations/my')
    recentStocks.value = res.data.items.slice(0, 5)
    stats.value.myStocks = res.data.total
    
    // 获取 VIP 配置
    const configRes = await api.get('/config/vip-levels')
    const myLevel = configRes.data.find(c => c.level === userStore.vipLevel)
    if (myLevel) {
      stats.value.stockLimit = myLevel.stock_limit === -1 ? '不限' : myLevel.stock_limit
    }
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped lang="scss">
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.welcome-card {
  .welcome-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    
    .welcome-text {
      h2 {
        margin: 0 0 8px;
        font-size: 22px;
      }
      
      p {
        margin: 0;
        color: var(--text-secondary);
      }
    }
  }
}

.stat-row {
  .stat-card {
    :deep(.el-card__body) {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    
    .stat-icon {
      width: 56px;
      height: 56px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
    }
    
    .stat-info {
      .stat-value {
        font-size: 28px;
        font-weight: 600;
        color: var(--text-primary);
        line-height: 1.2;
      }
      
      .stat-label {
        font-size: 14px;
        color: var(--text-secondary);
      }
    }
  }
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  
  .action-btn {
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: flex-start;
    gap: 12px;
    font-size: 16px;
    
    :deep(.el-icon) {
      color: var(--primary-color);
    }
  }
}
</style>

