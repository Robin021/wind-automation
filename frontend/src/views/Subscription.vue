<template>
  <div class="membership-page" v-loading="loading">
    <div class="page-header">
      <div>
        <h2>会员中心</h2>
        <p class="subtitle">查看当前权益，开通/续费订阅</p>
      </div>
      <el-tag :class="['vip-pill', `vip-${effectiveVip}`]">
        有效等级：VIP{{ effectiveVip }}
      </el-tag>
    </div>

    <el-row :gutter="16" class="status-cards">
      <el-col :md="8" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-title">当前权益</div>
          <div class="stat-value">VIP{{ effectiveVip }}</div>
          <div class="stat-desc">
            来源：{{ sourceLabel }}<span v-if="subscription?.vip_level">（账户标记 VIP{{ subscription.vip_level }}）</span>
          </div>
        </el-card>
      </el-col>
      <el-col :md="8" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-title">订阅有效期</div>
          <div class="stat-value">
            <span v-if="subscription?.expires_at">{{ formatDate(subscription.expires_at) }}</span>
            <span v-else>—</span>
          </div>
          <div class="stat-desc">
            <span v-if="subscription?.source === 'subscription'">正常</span>
            <span v-else-if="subscription?.source === 'expired'" class="danger-text">已过期</span>
            <span v-else>暂无订阅</span>
          </div>
        </el-card>
      </el-col>
      <el-col :md="8" :sm="12" :xs="24">
        <el-card shadow="hover">
          <div class="stat-title">支付环境</div>
          <div class="stat-value">
            <span v-if="mockEnabled">测试/Mock</span>
            <span v-else>待接入支付</span>
          </div>
          <div class="stat-desc">
            <span v-if="mockEnabled">可使用一键开通或模拟支付</span>
            <span v-else>创建订单后需真实支付</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <div class="section-title">选择订阅等级</div>
    <el-row :gutter="16" class="vip-cards">
      <el-col v-for="item in vipLevels" :key="item.level" :md="6" :sm="12" :xs="24">
        <el-card :class="['vip-card', { active: effectiveVip === item.level }]">
          <div class="vip-card__header">
            <div class="vip-name">VIP{{ item.level }} · {{ item.name }}</div>
            <el-tag size="small" effect="dark">股票上限 {{ stockLimitText(item.stock_limit) }}</el-tag>
          </div>
          <div class="vip-price">{{ priceText(item.level) }}</div>
          <p class="vip-desc">{{ item.description || '提升额度，获取更多股票分配。' }}</p>
          <div class="vip-actions">
            <el-button 
              type="primary" 
              :disabled="effectiveVip >= item.level"
              :loading="submitting"
              @click="createOrder(item.level)"
            >
              {{ effectiveVip >= item.level ? '已开通' : '微信订阅' }}
            </el-button>
            <el-button 
              v-if="mockEnabled" 
              text 
              :loading="submitting"
              @click="mockOpen(item.level)"
            >
              一键开通（测试）
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card v-if="payInfo" class="pay-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>支付信息</span>
          <el-tag size="small" type="warning">待支付</el-tag>
        </div>
      </template>
      <div class="pay-body">
        <div>
          <div class="pay-label">订单号</div>
          <code class="mono">{{ payInfo.order.out_trade_no }}</code>
        </div>
        <div v-if="payInfo.pay.code_url" class="qr-area">
          <div class="pay-label">扫码支付</div>
          <img
            class="qr-img"
            :src="qrSrc(payInfo.pay.code_url)"
            alt="微信扫码支付"
          />
          <div class="mono small">{{ payInfo.pay.code_url }}</div>
        </div>
        <div v-if="payInfo.pay.h5_url">
          <div class="pay-label">H5 链接</div>
          <div class="mono">{{ payInfo.pay.h5_url }}</div>
        </div>
        <div v-if="payInfo.pay.prepay_id">
          <div class="pay-label">预支付单号</div>
          <div class="mono">{{ payInfo.pay.prepay_id }}</div>
        </div>
        <el-alert
          v-if="!mockEnabled"
          type="info"
          :closable="false"
          title="请使用微信扫码/打开链接完成支付，支付成功后权益自动生效。"
          style="margin-top: 8px;"
        />
        <el-alert
          v-else
          type="success"
          :closable="false"
          title="当前为测试环境，可点击“模拟支付成功”快速生效。"
          style="margin-top: 8px;"
        />
        <div class="pay-actions">
          <el-button 
            v-if="mockEnabled"
            size="small" 
            type="success" 
            plain
            :loading="submitting"
            @click="mockPay(payInfo.order.out_trade_no)"
          >
            模拟支付成功
          </el-button>
          <el-button size="small" @click="payInfo = null">隐藏</el-button>
        </div>
      </div>
    </el-card>

    <el-card class="orders-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>最近订单</span>
        </div>
      </template>
      <el-table :data="orders" size="small" empty-text="暂无订单">
        <el-table-column prop="out_trade_no" label="订单号" min-width="180">
          <template #default="{ row }">
            <code class="mono">{{ row.out_trade_no }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="vip_level" label="VIP" width="80">
          <template #default="{ row }">
            <el-tag size="small">VIP{{ row.vip_level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="amount_fen" label="金额" width="120">
          <template #default="{ row }">
            ¥ {{ (row.amount_fen / 100).toFixed(2) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag size="small" :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

const loading = ref(false)
const submitting = ref(false)
const vipConfigs = ref([])
const priceConfigs = ref([])
const subscription = ref(null)
const orders = ref([])
const payInfo = ref(null)
const pollingTimer = ref(null)
const pollingTarget = ref(null)
const pollingAttempts = ref(0)

const fallbackConfigs = [
  { level: 1, name: 'VIP1', stock_limit: 10, description: '基础升级，获取更多股票。' },
  { level: 2, name: 'VIP2', stock_limit: 20, description: '进阶额度，更多机会。' },
  { level: 3, name: 'VIP3', stock_limit: 50, description: '高阶额度，覆盖主力池。' },
  { level: 4, name: 'SVIP', stock_limit: -1, description: '无限额度，全部股票池。' },
]

const vipLevels = computed(() => {
  const list = vipConfigs.value.length ? vipConfigs.value : fallbackConfigs
  return list.filter((i) => i.level > 0).sort((a, b) => a.level - b.level)
})

const priceMap = computed(() => {
  const map = {}
  priceConfigs.value.forEach((p) => {
    map[p.vip_level] = p
  })
  return map
})

const effectiveVip = computed(() => subscription.value?.effective_vip ?? 0)
const mockEnabled = computed(() => !!subscription.value?.mock_enabled)
const sourceLabel = computed(() => {
  const map = {
    subscription: '订阅',
    manual: '手工设置',
    expired: '订阅已过期',
    free: '免费',
  }
  return map[subscription.value?.source] || '未知'
})

function stockLimitText(limit) {
  if (limit === -1) return '不限'
  return `${limit} 支`
}

function priceText(level) {
  const price = priceMap.value[level]
  if (!price || !price.enabled) return '价格待定'
  return `¥ ${(price.price_fen / 100).toFixed(2)} / ${price.duration_months}个月`
}

function statusType(status) {
  if (status === 'paid') return 'success'
  if (status === 'pending') return 'warning'
  if (status === 'failed') return 'danger'
  return 'info'
}

function formatDate(val) {
  if (!val) return ''
  const d = new Date(val)
  return d.toLocaleString()
}

function qrSrc(codeUrl) {
  return `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(codeUrl)}`
}

async function fetchVipConfigs() {
  try {
    const res = await api.get('/config/vip-levels')
    vipConfigs.value = res.data
  } catch (e) {
    vipConfigs.value = fallbackConfigs
  }
}

async function fetchPriceConfigs() {
  try {
    const res = await api.get('/config/vip-prices')
    priceConfigs.value = res.data
  } catch (e) {
    priceConfigs.value = []
  }
}

async function fetchSubscription() {
  const res = await api.get('/subscriptions/me')
  subscription.value = res.data
}

async function fetchOrders() {
  const res = await api.get('/payments/my-orders')
  orders.value = res.data.items || []
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
  pollingTarget.value = null
  pollingAttempts.value = 0
}

async function pollPaymentStatus(targetOutTradeNo) {
  stopPolling()
  pollingTarget.value = targetOutTradeNo
  pollingAttempts.value = 0

  const maxAttempts = 60 // ~3 分钟，如果 3s 一次
  pollingTimer.value = setInterval(async () => {
    pollingAttempts.value += 1
    await Promise.all([fetchSubscription(), fetchOrders()])

    const matched = orders.value.find(o => o.out_trade_no === pollingTarget.value)
    const paid = matched && matched.status === 'paid'
    const vipUpgraded = subscription.value && subscription.value.effective_vip >= (matched?.vip_level || 0)

    if (paid || vipUpgraded) {
      stopPolling()
      payInfo.value = null
      ElMessage.success('支付成功，权益已生效')
    } else if (pollingAttempts.value >= maxAttempts) {
      stopPolling()
      ElMessage.info('支付状态轮询已停止，请手动刷新查看最新状态')
    }
  }, 3000)
}

async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([fetchVipConfigs(), fetchPriceConfigs(), fetchSubscription(), fetchOrders()])
  } finally {
    loading.value = false
  }
}

async function createOrder(level) {
  submitting.value = true
  payInfo.value = null
  try {
    const res = await api.post('/payments/wechat/create', { vip_level: level, channel: 'native' })
    payInfo.value = res.data

    if (res.data.order.is_test) {
      await mockPay(res.data.order.out_trade_no)
      payInfo.value = null
    } else {
      ElMessage.success('订单已创建，请完成支付')
      pollPaymentStatus(res.data.order.out_trade_no)
    }

    await fetchSubscription()
    await fetchOrders()
  } catch (e) {
    // 统一拦截器已处理错误提示
  } finally {
    submitting.value = false
  }
}

async function mockPay(outTradeNo) {
  try {
    await api.post('/payments/wechat/notify', {
      out_trade_no: outTradeNo,
      success: true,
    })
    ElMessage.success('已模拟支付并开通')
    await fetchSubscription()
    await fetchOrders()
  } catch (e) {
    // 错误提示由拦截器处理
  }
}

async function mockOpen(level) {
  submitting.value = true
  try {
    await api.post('/subscriptions/mock-upgrade', { vip_level: level })
    ElMessage.success(`已开通 VIP${level}（测试环境）`)
    await fetchSubscription()
    await fetchOrders()
  } catch (e) {
    // 已有拦截器提示
  } finally {
    submitting.value = false
  }
}

onMounted(refreshAll)
onBeforeUnmount(stopPolling)
</script>

<style scoped lang="scss">
.membership-page {
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;

    .subtitle {
      color: var(--text-secondary);
      margin-top: 4px;
      font-size: 13px;
    }
  }

  .vip-pill {
    font-weight: 600;
  }

  .status-cards {
    margin-bottom: 12px;

    .stat-title {
      color: var(--text-secondary);
      font-size: 13px;
    }
    .stat-value {
      font-size: 20px;
      font-weight: 700;
      margin: 6px 0;
    }
    .stat-desc {
      color: var(--text-secondary);
      font-size: 13px;
    }
    .danger-text {
      color: #f56c6c;
    }
  }

  .section-title {
    font-weight: 600;
    margin: 12px 0;
  }

  .vip-cards {
    margin-bottom: 16px;

    .vip-card {
      border-radius: 10px;

      &.active {
        border-color: var(--el-color-primary);
        box-shadow: 0 8px 24px rgba(64, 158, 255, 0.12);
      }
    }

    .vip-card__header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }

    .vip-name {
      font-weight: 700;
      font-size: 16px;
    }

    .vip-price {
      font-size: 20px;
      font-weight: 700;
      color: var(--el-color-primary);
      margin: 6px 0;
    }

    .vip-desc {
      color: var(--text-secondary);
      min-height: 38px;
      margin-bottom: 12px;
    }

    .vip-actions {
      display: flex;
      gap: 8px;
    }
  }

  .pay-card,
  .orders-card {
    margin-top: 12px;
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .pay-body {
    display: grid;
    gap: 8px;
  }

  .pay-label {
    color: var(--text-secondary);
    font-size: 13px;
  }

  .mono {
    font-family: ui-monospace, SFMono-Regular, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    background: #f6f8fa;
    padding: 2px 6px;
    border-radius: 4px;
  }

  .pay-actions {
    display: flex;
    gap: 8px;
    margin-top: 6px;
  }
}
</style>
