<template>
  <div class="admin-datasources">
    <div class="page-header">
      <h2>数据源管理</h2>
      <el-button type="primary" @click="checkHealth" :loading="checking">
        <el-icon><Refresh /></el-icon> 检查状态
      </el-button>
    </div>
    
    <el-row :gutter="20">
      <el-col :span="12" v-for="source in dataSources" :key="source.name">
        <el-card class="source-card">
          <template #header>
            <div class="source-header">
              <div class="source-info">
                <el-icon :size="24">
                  <component :is="source.name === 'tushare' ? 'DataBoard' : 'DataLine'" />
                </el-icon>
                <span class="source-name">{{ source.name.toUpperCase() }}</span>
              </div>
              <el-tag :type="source.is_available ? 'success' : 'danger'">
                {{ source.is_available ? '正常' : '异常' }}
              </el-tag>
            </div>
          </template>
          
          <el-descriptions :column="1" size="small">
            <el-descriptions-item label="优先级">
              {{ source.priority }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-icon v-if="source.is_available" color="#67c23a"><CircleCheckFilled /></el-icon>
              <el-icon v-else color="#f56c6c"><CircleCloseFilled /></el-icon>
              {{ source.is_available ? '可用' : '不可用' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="source.error_message" label="错误信息">
              <span class="error-msg">{{ source.error_message }}</span>
            </el-descriptions-item>
            <el-descriptions-item v-if="source.last_check" label="最后检查">
              {{ formatTime(source.last_check) }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 测试接口 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>接口测试</span>
      </template>
      
      <el-form inline>
        <el-form-item label="股票代码">
          <el-input v-model="testCode" placeholder="如 600000.SH" style="width: 150px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="testQuote" :loading="testingQuote">
            获取行情
          </el-button>
        </el-form-item>
      </el-form>
      
      <el-card v-if="quoteResult" class="result-card" shadow="never">
        <el-descriptions :column="3" size="small" border>
          <el-descriptions-item label="代码">{{ quoteResult.code }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ quoteResult.name }}</el-descriptions-item>
          <el-descriptions-item label="日期">{{ quoteResult.date }}</el-descriptions-item>
          <el-descriptions-item label="开盘">{{ quoteResult.open }}</el-descriptions-item>
          <el-descriptions-item label="最高">{{ quoteResult.high }}</el-descriptions-item>
          <el-descriptions-item label="最低">{{ quoteResult.low }}</el-descriptions-item>
          <el-descriptions-item label="收盘">{{ quoteResult.close }}</el-descriptions-item>
          <el-descriptions-item label="成交量">{{ quoteResult.volume }}</el-descriptions-item>
          <el-descriptions-item label="成交额">{{ quoteResult.amount }}</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'
import api from '@/api'

const checking = ref(false)
const testingQuote = ref(false)
const dataSources = ref([])
const testCode = ref('600000.SH')
const quoteResult = ref(null)

function formatTime(isoString) {
  return dayjs(isoString).format('YYYY-MM-DD HH:mm:ss')
}

async function fetchStatus() {
  try {
    const res = await api.get('/datasources/status')
    dataSources.value = res.data
  } catch (e) {
    console.error(e)
  }
}

async function checkHealth() {
  checking.value = true
  try {
    const res = await api.post('/datasources/check')
    dataSources.value = res.data.results
    ElMessage.success('检查完成')
  } catch (e) {
    console.error(e)
  } finally {
    checking.value = false
  }
}

async function testQuote() {
  if (!testCode.value) {
    ElMessage.warning('请输入股票代码')
    return
  }
  
  testingQuote.value = true
  quoteResult.value = null
  try {
    const res = await api.get(`/datasources/quote/${testCode.value}`)
    quoteResult.value = res.data
    ElMessage.success('获取成功')
  } catch (e) {
    console.error(e)
  } finally {
    testingQuote.value = false
  }
}

onMounted(fetchStatus)
</script>

<style scoped lang="scss">
.admin-datasources {
  .source-card {
    .source-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      
      .source-info {
        display: flex;
        align-items: center;
        gap: 8px;
        
        .source-name {
          font-size: 18px;
          font-weight: 600;
        }
      }
    }
    
    .error-msg {
      color: var(--danger-color);
      font-size: 12px;
    }
  }
  
  .result-card {
    margin-top: 16px;
    background: var(--bg-color);
  }
}
</style>

