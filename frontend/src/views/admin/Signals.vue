<template>
  <div class="admin-signals">
    <div class="page-header">
      <h2>信号计算</h2>
      <div class="header-actions">
        <el-date-picker
          v-model="tradeDate"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="交易日"
          style="width: 160px"
        />
        <el-button type="primary" :loading="running" @click="runSignals">
          计算信号
        </el-button>
      </div>
    </div>

    <el-card>
      <div class="summary">
        <div>当前交易日：{{ tradeDate || '未选择' }}</div>
        <div>记录数：{{ total }}</div>
      </div>
      <el-table :data="signals" v-loading="loading" height="560">
        <el-table-column prop="trade_date" label="交易日" width="110" />
        <el-table-column prop="code" label="代码" width="110" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="signal" label="信号" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.signal === 'Buy' ? 'success' : row.signal === 'Sell' ? 'danger' : 'info'"
              size="small"
            >
              {{ row.signal }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price" label="参考价" width="100" />
        <el-table-column prop="generated_at" label="生成时间" width="180" />
        <el-table-column prop="note" label="备注" />
      </el-table>
      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchSignals"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import api from '@/api'

const tradeDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const running = ref(false)
const signals = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50

async function fetchSignals() {
  loading.value = true
  try {
    const params = {
      trade_date: tradeDate.value,
      skip: (page.value - 1) * pageSize,
      limit: pageSize,
    }
    const res = await api.get('/signals', { params })
    signals.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function runSignals() {
  if (!tradeDate.value) {
    ElMessage.warning('请先选择交易日')
    return
  }
  running.value = true
  try {
    // 信号计算需要较长时间（分批限频），设置5分钟超时
    await api.post(`/signals/run?trade_date=${tradeDate.value}`, {}, {
      timeout: 300000  // 5分钟
    })
    ElMessage.success('信号计算完成')
    page.value = 1
    fetchSignals()
  } catch (e) {
    if (e.code === 'ECONNABORTED') {
      ElMessage.error('请求超时，信号计算可能需要更长时间，请稍后刷新查看结果')
    } else {
      ElMessage.error('信号计算失败：' + (e.response?.data?.detail || e.message))
    }
    console.error(e)
  } finally {
    running.value = false
  }
}

onMounted(fetchSignals)
</script>

<style scoped lang="scss">
.admin-signals {
  .header-actions {
    display: flex;
    gap: 12px;
    align-items: center;
  }
  .summary {
    display: flex;
    gap: 24px;
    margin-bottom: 12px;
    color: var(--text-secondary);
  }
  .pagination {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>

