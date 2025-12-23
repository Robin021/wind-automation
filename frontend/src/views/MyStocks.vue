<template>
  <div class="my-stocks">
    <div class="page-header">
      <h2>我的股票</h2>
      <el-date-picker
        v-model="selectedDate"
        type="date"
        placeholder="选择日期"
        value-format="YYYY-MM-DD"
        @change="fetchData"
      />
    </div>
    
    <el-card>
      <el-table :data="stocks" v-loading="loading" style="width: 100%">
        <el-table-column prop="stock_code" label="股票代码" width="120">
          <template #default="{ row }">
            <span class="stock-code">{{ row.stock_code }}</span>
          </template>
        </el-table-column>
        
        <el-table-column prop="stock_name" label="股票名称" />

      <el-table-column prop="signal" label="信号" width="100">
        <template #default="{ row }">
          <el-tag
            :type="row.signal === 'Buy' ? 'success' : row.signal === 'Sell' ? 'danger' : 'info'"
            size="small"
          >
            {{ row.signal || '—' }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="signal_price" label="信号价" width="100" />

      <el-table-column prop="signal_time" label="生成时间" width="180" />
        
        <el-table-column prop="batch_date" label="分配日期" width="120" />
        
        <el-table-column prop="vip_level_at_allocation" label="分配时VIP" width="120">
          <template #default="{ row }">
            <el-tag 
              :class="['vip-tag', `vip-${row.vip_level_at_allocation}`]"
              size="small"
            >
              VIP{{ row.vip_level_at_allocation }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      
      <el-empty v-if="!loading && stocks.length === 0" description="暂无分配的股票">
        <template #image>
          <el-icon :size="80" color="#c0c4cc"><Briefcase /></el-icon>
        </template>
      </el-empty>
      
      <div class="pagination" v-if="total > 0">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchData"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/api'

const loading = ref(false)
const stocks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const selectedDate = ref(null)

function getStatusType(status) {
  const types = {
    active: 'success',
    expired: 'info',
    cancelled: 'danger',
  }
  return types[status] || 'info'
}

function getStatusText(status) {
  const texts = {
    active: '有效',
    expired: '已过期',
    cancelled: '已取消',
  }
  return texts[status] || status
}

async function fetchData() {
  loading.value = true
  try {
    const params = {
      status: 'active',
      skip: (page.value - 1) * pageSize,
      limit: pageSize,
    }
    if (selectedDate.value) {
      params.batch_date = selectedDate.value
    }
    
    const res = await api.get('/allocations/my', { params })
    stocks.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<style scoped lang="scss">
.my-stocks {
  .stock-code {
    font-family: 'Monaco', 'Menlo', monospace;
    color: var(--primary-color);
  }
  
  .pagination {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>

