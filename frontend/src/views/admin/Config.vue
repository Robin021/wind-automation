<template>
  <div class="admin-config">
    <div class="page-header">
      <h2>系统配置</h2>
    </div>
    
    <el-card>
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const loading = ref(false)
const initializing = ref(false)
const vipConfigs = ref([])

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

onMounted(fetchVipConfigs)
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
}
</style>

