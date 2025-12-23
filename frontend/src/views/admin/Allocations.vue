<template>
  <div class="admin-allocations">
    <div class="page-header">
      <h2>分配管理</h2>
      <div class="header-actions">
        <el-date-picker
          v-model="selectedDate"
          type="date"
          placeholder="选择日期"
          value-format="YYYY-MM-DD"
          @change="fetchAllocations"
        />
        <el-button type="primary" @click="showAllocateDialog">
          <el-icon><Share /></el-icon> 执行分配
        </el-button>
      </div>
    </div>
    
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stat-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.totalUsers }}</div>
          <div class="stat-label">活跃用户数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.totalStocks }}</div>
          <div class="stat-label">股票池数量</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.todayAllocations }}</div>
          <div class="stat-label">今日分配数</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">{{ stats.allocatedUsers }}</div>
          <div class="stat-label">已分配用户</div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-card>
      <el-table :data="allocations" v-loading="loading" style="width: 100%">
        <el-table-column prop="user_id" label="用户ID" width="80" />
        <el-table-column prop="stock_code" label="股票代码" width="120">
          <template #default="{ row }">
            <span class="stock-code">{{ row.stock_code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="stock_name" label="股票名称" />
        <el-table-column prop="batch_date" label="分配日期" width="120" />
        <el-table-column prop="vip_level_at_allocation" label="VIP等级" width="100">
          <template #default="{ row }">
            <el-tag :class="['vip-tag', `vip-${row.vip_level_at_allocation}`]" size="small">
              VIP{{ row.vip_level_at_allocation }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '有效' : '过期' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchAllocations"
        />
      </div>
    </el-card>
    
    <!-- 分配对话框 -->
    <el-dialog v-model="allocateDialogVisible" title="执行股票分配" width="500px">
      <el-form label-width="100px">
        <el-form-item label="分配日期">
          <el-date-picker
            v-model="allocateForm.batch_date"
            type="date"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="分配对象">
          <el-radio-group v-model="allocateForm.target">
            <el-radio label="all">所有活跃用户</el-radio>
            <el-radio label="selected">指定用户</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="allocateForm.target === 'selected'" label="选择用户">
          <el-select 
            v-model="allocateForm.user_ids" 
            multiple 
            filterable 
            style="width: 100%"
            placeholder="选择用户"
          >
            <el-option 
              v-for="user in userOptions" 
              :key="user.id" 
              :label="`${user.username} (VIP${user.vip_level})`" 
              :value="user.id" 
            />
          </el-select>
        </el-form-item>
      </el-form>
      
      <el-alert 
        type="warning" 
        :closable="false"
        style="margin-top: 16px"
      >
        <template #title>
          注意：执行分配将覆盖所选用户在该日期的现有分配记录
        </template>
      </el-alert>
      
      <template #footer>
        <el-button @click="allocateDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="executeAllocate" :loading="allocating">
          执行分配
        </el-button>
      </template>
    </el-dialog>
    
    <!-- 分配结果对话框 -->
    <el-dialog v-model="resultDialogVisible" title="分配结果" width="700px">
      <el-table :data="allocateResult" max-height="400">
        <el-table-column prop="username" label="用户" width="120" />
        <el-table-column prop="vip_level" label="VIP等级" width="100">
          <template #default="{ row }">
            <el-tag :class="['vip-tag', `vip-${row.vip_level}`]" size="small">
              VIP{{ row.vip_level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="stock_limit" label="额度" width="80" />
        <el-table-column prop="allocated_count" label="分配数" width="80" />
        <el-table-column prop="stocks" label="股票列表">
          <template #default="{ row }">
            <div class="stocks-preview">
              {{ row.stocks.slice(0, 3).map(s => s.code).join(', ') }}
              <span v-if="row.stocks.length > 3">... 等 {{ row.stocks.length }} 只</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button type="primary" @click="resultDialogVisible = false">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import api from '@/api'

const loading = ref(false)
const allocating = ref(false)
const allocations = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const selectedDate = ref(dayjs().format('YYYY-MM-DD'))

const stats = ref({
  totalUsers: 0,
  totalStocks: 0,
  todayAllocations: 0,
  allocatedUsers: 0,
})

const allocateDialogVisible = ref(false)
const resultDialogVisible = ref(false)
const userOptions = ref([])
const allocateResult = ref([])

const allocateForm = reactive({
  batch_date: dayjs().format('YYYY-MM-DD'),
  target: 'all',
  user_ids: [],
})

async function fetchAllocations() {
  loading.value = true
  try {
    const params = {
      skip: (page.value - 1) * pageSize,
      limit: pageSize,
    }
    if (selectedDate.value) {
      params.batch_date = selectedDate.value
    }
    
    const res = await api.get('/allocations', { params })
    allocations.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function fetchStats() {
  try {
    // 获取用户数
    const usersRes = await api.get('/users', { params: { limit: 1, is_active: true } })
    stats.value.totalUsers = usersRes.data.total
    
    // 获取股票数
    const stocksRes = await api.get('/stocks', { params: { limit: 1, is_active: true } })
    stats.value.totalStocks = stocksRes.data.total
    
    // 获取今日分配数
    const todayAllocRes = await api.get('/allocations', { 
      params: { batch_date: dayjs().format('YYYY-MM-DD'), limit: 1 } 
    })
    stats.value.todayAllocations = todayAllocRes.data.total
  } catch (e) {
    console.error(e)
  }
}

async function fetchUsers() {
  try {
    const res = await api.get('/users', { params: { limit: 1000, is_active: true } })
    userOptions.value = res.data.items
  } catch (e) {
    console.error(e)
  }
}

function showAllocateDialog() {
  allocateForm.batch_date = dayjs().format('YYYY-MM-DD')
  allocateForm.target = 'all'
  allocateForm.user_ids = []
  allocateDialogVisible.value = true
}

async function executeAllocate() {
  allocating.value = true
  try {
    const params = new URLSearchParams()
    params.append('batch_date', allocateForm.batch_date)
    
    if (allocateForm.target === 'selected' && allocateForm.user_ids.length > 0) {
      allocateForm.user_ids.forEach(id => params.append('user_ids', id))
    }
    
    const res = await api.post(`/allocations/allocate?${params.toString()}`)
    ElMessage.success(res.data.message)
    
    allocateResult.value = res.data.results
    allocateDialogVisible.value = false
    resultDialogVisible.value = true
    
    fetchAllocations()
    fetchStats()
  } catch (e) {
    console.error(e)
  } finally {
    allocating.value = false
  }
}

onMounted(() => {
  fetchAllocations()
  fetchStats()
  fetchUsers()
})
</script>

<style scoped lang="scss">
.admin-allocations {
  .header-actions {
    display: flex;
    gap: 12px;
  }
  
  .stat-row {
    margin-bottom: 20px;
    
    .stat-card {
      text-align: center;
      
      .stat-value {
        font-size: 32px;
        font-weight: 600;
        color: var(--primary-color);
      }
      
      .stat-label {
        font-size: 14px;
        color: var(--text-secondary);
        margin-top: 4px;
      }
    }
  }
  
  .stock-code {
    font-family: 'Monaco', 'Menlo', monospace;
    color: var(--primary-color);
  }
  
  .stocks-preview {
    font-size: 12px;
    color: var(--text-secondary);
  }
  
  .pagination {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>

