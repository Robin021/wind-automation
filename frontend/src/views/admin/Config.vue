<template>
  <div class="admin-config">
    <div class="page-header">
      <h2>系统配置</h2>
    </div>
    
    <el-card style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span>VIP 等级配置</span>
          <el-button type="primary" size="small" @click="initVipLevels" :loading="initializing">
            重置为默认
          </el-button>
        </div>
      </template>
      
      <el-table :data="vipConfigs" v-loading="loading" style="width: 100%">
        <el-table-column prop="level" label="等级" width="80">
          <template #default="{ row }">
            <el-tag :class="['vip-tag', `vip-${row.level}`]">
              VIP{{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" width="150">
          <template #default="{ row }">
            <el-input 
              v-model="row.name" 
              size="small" 
              @change="updateVipConfig(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="stock_limit" label="股票上限" width="150">
          <template #default="{ row }">
            <el-input-number 
              v-model="row.stock_limit" 
              size="small"
              :min="-1"
              @change="updateVipConfig(row)"
            />
            <span v-if="row.stock_limit === -1" class="limit-tip">（不限）</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明">
          <template #default="{ row }">
            <el-input 
              v-model="row.description" 
              size="small"
              placeholder="等级说明（可选）"
              @change="updateVipConfig(row)"
            />
          </template>
        </el-table-column>
      </el-table>
      
      <el-alert 
        type="info" 
        :closable="false"
        style="margin-top: 16px"
      >
        <template #title>
          提示：股票上限设为 -1 表示不限制数量（适用于最高等级）
        </template>
      </el-alert>
    </el-card>

    <el-card style="margin-bottom: 16px">
      <template #header>
        <div class="card-header">
          <span>免费用户试用期</span>
        </div>
      </template>
      <el-form label-width="160px">
        <el-form-item label="试用天数">
          <el-input-number v-model="freeTrialDays" :min="0" :max="365" @change="saveFreeTrial" />
          <span class="limit-tip">0 表示关闭，超过试用期后 VIP0 不再分配</span>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>VIP 价格配置（单位：分，订阅周期固定 3 个月）</span>
        </div>
      </template>

      <el-table :data="priceConfigs" v-loading="loadingPrice" style="width: 100%">
        <el-table-column prop="vip_level" label="等级" width="80">
          <template #default="{ row }">
            <el-tag :class="['vip-tag', `vip-${row.vip_level}`]">VIP{{ row.vip_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="price_fen" label="价格（分）" width="200">
          <template #default="{ row }">
            <div class="price-input">
              <el-input-number
                v-model="row.price_fen"
                :min="0"
                :step="100"
                size="small"
                @change="updateVipPrice(row)"
              />
              <span class="price-hint">约 ¥ {{ (row.price_fen / 100).toFixed(2) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="duration_months" label="周期（月）" width="120">
          <template #default="{ row }">
            <el-input-number v-model="row.duration_months" :min="1" :max="24" size="small" @change="updateVipPrice(row)" />
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="启用" width="120">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="updateVipPrice(row)" />
          </template>
        </el-table-column>
      </el-table>

      <el-alert
        type="info"
        :closable="false"
        style="margin-top: 12px"
        title="必须为每个要售卖的等级配置价格并启用，否则前端下单会提示“该 VIP 等级暂不可购买”。"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const loading = ref(false)
const initializing = ref(false)
const vipConfigs = ref([])
const loadingPrice = ref(false)
const priceConfigs = ref([])
const freeTrialDays = ref(0)

async function fetchVipConfigs() {
  loading.value = true
  try {
    const res = await api.get('/config/vip-levels')
    vipConfigs.value = res.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function fetchVipPrices() {
  loadingPrice.value = true
  try {
    const res = await api.get('/config/vip-prices')
    const map = new Map(res.data.map(item => [item.vip_level, item]))
    const levels = [1, 2, 3, 4]
    priceConfigs.value = levels.map(l => map.get(l) || { vip_level: l, price_fen: 0, duration_months: 3, enabled: false })
  } catch (e) {
    console.error(e)
  } finally {
    loadingPrice.value = false
  }
}

async function updateVipConfig(config) {
  try {
    await api.post('/config/vip-levels', config)
    ElMessage.success('配置已保存')
  } catch (e) {
    console.error(e)
    fetchVipConfigs() // 恢复原值
  }
}

async function initVipLevels() {
  try {
    await ElMessageBox.confirm('确定要重置VIP等级配置为默认值吗？', '确认操作')
    
    initializing.value = true
    await api.post('/config/vip-levels/init')
    ElMessage.success('已重置为默认配置')
    fetchVipConfigs()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
    }
  } finally {
    initializing.value = false
  }
}

async function updateVipPrice(price) {
  try {
    await api.post('/config/vip-prices', {
      vip_level: price.vip_level,
      price_fen: price.price_fen,
      duration_months: price.duration_months || 3,
      enabled: price.enabled,
    })
    ElMessage.success(`VIP${price.vip_level} 价格已保存`)
  } catch (e) {
    console.error(e)
    fetchVipPrices()
  }
}

async function fetchFreeTrial() {
  try {
    const res = await api.get('/config/free-trial')
    freeTrialDays.value = res.data.free_trial_days || 0
  } catch (e) {
    console.error(e)
  }
}

async function saveFreeTrial() {
  try {
    await api.post('/config/free-trial', { free_trial_days: freeTrialDays.value || 0 })
    ElMessage.success('试用期已保存')
  } catch (e) {
    console.error(e)
    fetchFreeTrial()
  }
}

onMounted(() => {
  fetchVipConfigs()
  fetchVipPrices()
  fetchFreeTrial()
})
</script>

<style scoped lang="scss">
.admin-config {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .limit-tip {
    font-size: 12px;
    color: var(--text-secondary);
    margin-left: 8px;
  }

  .price-input {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .price-hint {
    font-size: 12px;
    color: var(--text-secondary);
  }
}
</style>
