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
        <el-switch
          v-model="showIndicators"
          active-text="详细"
          inactive-text="精简"
        />
        <el-button type="primary" :loading="running" @click="runSignals">
          计算信号
        </el-button>
      </div>
    </div>

    <el-card style="margin-bottom: 12px">
      <template #header>
        <div class="card-header">
          <span>信号参数</span>
          <div class="actions">
            <el-button size="small" @click="loadParams" :loading="paramsLoading">刷新</el-button>
            <el-button type="primary" size="small" @click="saveParams" :loading="paramsSaving">
              保存参数
            </el-button>
          </div>
        </div>
      </template>
      <el-form inline label-width="80px">
        <el-form-item label="SHORT">
          <el-input-number v-model="signalParams.short" :min="1" :max="200" :step="1" />
        </el-form-item>
        <el-form-item label="LONG">
          <el-input-number v-model="signalParams.long" :min="1" :max="400" :step="1" />
        </el-form-item>
        <el-form-item label="SMOOTH">
          <el-input-number v-model="signalParams.smooth" :min="1" :max="400" :step="1" />
        </el-form-item>
        <el-form-item>
          <span class="hint">修改后再点击“计算信号”生效</span>
        </el-form-item>
      </el-form>
    </el-card>

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
        <el-table-column
          prop="price"
          label="参考价"
          width="100"
          align="right"
          header-align="right"
          :formatter="formatNumber"
        />
        <el-table-column
          v-if="showIndicators"
          prop="match_price"
          label="MATCH"
          width="110"
          align="right"
          header-align="right"
          :formatter="formatNumber"
        />
        <el-table-column
          v-if="showIndicators"
          prop="mid"
          label="MID"
          width="160"
          align="right"
          header-align="right"
          :formatter="formatNumber"
          show-overflow-tooltip
        />
        <el-table-column
          v-if="showIndicators"
          prop="cho_short"
          label="CHO_S"
          width="110"
          align="right"
          header-align="right"
          :formatter="formatNumber"
        />
        <el-table-column
          v-if="showIndicators"
          prop="cho_long"
          label="CHO_L"
          width="110"
          align="right"
          header-align="right"
          :formatter="formatNumber"
        />
        <el-table-column
          v-if="showIndicators"
          prop="cho"
          label="CHO"
          width="110"
          align="right"
          header-align="right"
          :formatter="formatNumber"
        />
        <el-table-column
          v-if="showIndicators"
          prop="macho"
          label="MACHO"
          width="110"
          align="right"
          header-align="right"
          :formatter="formatNumber"
        />
        <el-table-column
          prop="generated_at"
          label="生成时间"
          width="190"
          :formatter="formatDateTime"
        />
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
const showIndicators = ref(true)
const signalParams = ref({ short: 3, long: 24, smooth: 24 })
const paramsLoading = ref(false)
const paramsSaving = ref(false)

const formatNumber = (_row, _column, value) => {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return '-'
  return num.toFixed(4)
}

const formatDateTime = (_row, _column, value) => {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  // 按北京时间展示
  return d.toLocaleString('zh-CN', {
    hour12: false,
    timeZone: 'Asia/Shanghai',
  })
}

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

async function loadParams() {
  paramsLoading.value = true
  try {
    const res = await api.get('/signals/params')
    signalParams.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    paramsLoading.value = false
  }
}

async function saveParams() {
  paramsSaving.value = true
  try {
    await api.post('/signals/params', signalParams.value)
    ElMessage.success('参数已保存')
  } catch (e) {
    console.error(e)
  } finally {
    paramsSaving.value = false
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

onMounted(() => {
  fetchSignals()
  loadParams()
})
</script>

<style scoped lang="scss">
.admin-signals {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .actions {
    display: flex;
    gap: 8px;
  }
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
  .hint {
    color: var(--text-secondary);
    font-size: 12px;
  }
}
</style>
