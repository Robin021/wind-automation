<template>
  <div class="admin-users">
    <div class="page-header">
      <h2>用户管理</h2>
      <div class="header-actions">
        <el-select v-model="filters.vip_level" placeholder="VIP等级" clearable style="width: 120px" @change="fetchUsers">
          <el-option :label="`VIP${i}`" :value="i" v-for="i in [0,1,2,3,4]" :key="i" />
        </el-select>
        <el-select v-model="filters.is_active" placeholder="状态" clearable style="width: 100px" @change="fetchUsers">
          <el-option label="启用" :value="true" />
          <el-option label="禁用" :value="false" />
        </el-select>
        <el-button type="primary" @click="showCreateDialog">新增用户</el-button>
      </div>
    </div>
    
    <el-card>
      <el-table :data="users" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="email" label="邮箱" />
        <el-table-column prop="vip_level" label="VIP等级" width="120">
          <template #default="{ row }">
            <el-tag :class="['vip-tag', `vip-${row.vip_level}`]">
              {{ getVipName(row.vip_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? '启用' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_admin" label="管理员" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_admin" type="warning" size="small">是</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" @click="showVipDialog(row)">设置VIP</el-button>
              <el-button size="small" type="warning" @click="resetPassword(row)">重置密码</el-button>
              <el-button size="small" :type="row.is_active ? 'danger' : 'success'" @click="toggleActive(row)">
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
              <el-button size="small" type="danger" @click="deleteUser(row)">删除</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
      
      <div class="pagination">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchUsers"
        />
      </div>
    </el-card>
    
    <!-- 新增用户对话框 -->
    <el-dialog v-model="createDialogVisible" :title="editMode ? '编辑用户' : '新增用户'" width="500px">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" :disabled="editMode" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="createForm.email" />
        </el-form-item>
        <el-form-item v-if="!editMode" label="密码">
          <el-input v-model="createForm.password" placeholder="留空自动生成" />
        </el-form-item>
        <el-form-item label="VIP等级">
          <el-select v-model="createForm.vip_level" style="width: 100%">
            <el-option v-for="i in [0,1,2,3,4]" :key="i" :label="`VIP${i}`" :value="i" />
          </el-select>
        </el-form-item>
        <el-form-item label="管理员">
          <el-switch v-model="createForm.is_admin" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="createForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUser" :loading="creating">{{ editMode ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <!-- VIP 设置对话框 -->
    <el-dialog v-model="vipDialogVisible" title="设置VIP等级" width="400px">
      <el-form label-width="80px">
        <el-form-item label="用户">
          {{ currentUser?.username }}
        </el-form-item>
        <el-form-item label="VIP等级">
          <el-select v-model="newVipLevel" style="width: 100%">
            <el-option 
              v-for="config in vipConfigs" 
              :key="config.level" 
              :label="`${config.name} (${config.stock_limit === -1 ? '不限' : config.stock_limit}只股票)`"
              :value="config.level" 
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="vipDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="setVipLevel" :loading="saving">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

const loading = ref(false)
const saving = ref(false)
const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20

const filters = reactive({
  vip_level: null,
  is_active: null,
})

const createDialogVisible = ref(false)
const creating = ref(false)
const createFormRef = ref()
const editMode = ref(false)
const editingUserId = ref(null)
const createForm = reactive({
  username: '',
  email: '',
  password: '',
  vip_level: 0,
  is_admin: false,
  is_active: true,
})
const createRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' },
  ],
}

const vipDialogVisible = ref(false)
const currentUser = ref(null)
const newVipLevel = ref(0)
const vipConfigs = ref([])

const vipNames = ['免费用户', 'VIP1', 'VIP2', 'VIP3', 'SVIP']

function getVipName(level) {
  return vipNames[level] || `VIP${level}`
}

async function fetchUsers() {
  loading.value = true
  try {
    const params = {
      skip: (page.value - 1) * pageSize,
      limit: pageSize,
      ...filters,
    }
    // 移除空值
    Object.keys(params).forEach(key => {
      if (params[key] === null || params[key] === '') {
        delete params[key]
      }
    })
    
    const res = await api.get('/users', { params })
    users.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

async function fetchVipConfigs() {
  try {
    const res = await api.get('/config/vip-levels')
    vipConfigs.value = res.data
  } catch (e) {
    console.error(e)
  }
}

function showVipDialog(user) {
  currentUser.value = user
  newVipLevel.value = user.vip_level
  vipDialogVisible.value = true
}

function showCreateDialog() {
  Object.assign(createForm, {
    username: '',
    email: '',
    password: '',
    vip_level: 0,
    is_admin: false,
    is_active: true,
  })
  editMode.value = false
  editingUserId.value = null
  createDialogVisible.value = true
}

function showEditDialog(user) {
  Object.assign(createForm, {
    username: user.username,
    email: user.email,
    password: '',
    vip_level: user.vip_level,
    is_admin: user.is_admin,
    is_active: user.is_active,
  })
  editMode.value = true
  editingUserId.value = user.id
  createDialogVisible.value = true
}

async function submitUser() {
  const valid = await createFormRef.value.validate().catch(() => false)
  if (!valid) return
  creating.value = true
  try {
    if (editMode.value) {
      await api.put(`/users/${editingUserId.value}`, {
        email: createForm.email,
        vip_level: createForm.vip_level,
        is_admin: createForm.is_admin,
        is_active: createForm.is_active,
      })
      ElMessage.success('保存成功')
    } else {
      const res = await api.post('/users/create', createForm)
      const tempPwd = res.data?.temp_password
      const msg = tempPwd ? `创建成功，临时密码：${tempPwd}` : '创建成功'
      ElMessage.success(msg)
    }
    createDialogVisible.value = false
    fetchUsers()
  } catch (e) {
    console.error(e)
  } finally {
    creating.value = false
  }
}

async function setVipLevel() {
  saving.value = true
  try {
    await api.post(`/users/${currentUser.value.id}/set-vip?vip_level=${newVipLevel.value}`)
    ElMessage.success('VIP等级设置成功')
    vipDialogVisible.value = false
    fetchUsers()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function toggleActive(user) {
  try {
    await ElMessageBox.confirm(
      `确定要${user.is_active ? '禁用' : '启用'}用户 ${user.username} 吗？`,
      '确认操作'
    )
    
    await api.put(`/users/${user.id}`, { is_active: !user.is_active })
    ElMessage.success('操作成功')
    fetchUsers()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
    }
  }
}

async function resetPassword(user) {
  try {
    const { value } = await ElMessageBox.prompt(
      '输入新密码（留空自动生成随机密码）',
      '重置密码',
      { confirmButtonText: '确定', cancelButtonText: '取消', inputPlaceholder: '可留空' }
    )
    const res = await api.post(`/users/${user.id}/reset-password`, { new_password: value || null })
    const temp = res.data?.temp_password
    ElMessage.success(temp ? `重置成功，临时密码：${temp}` : '重置成功')
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

async function deleteUser(user) {
  try {
    await ElMessageBox.confirm(`确定删除用户 ${user.username} 吗？`, '确认删除')
    await api.delete(`/users/${user.id}`)
    ElMessage.success('删除成功')
    fetchUsers()
  } catch (e) {
    if (e !== 'cancel') console.error(e)
  }
}

onMounted(() => {
  fetchUsers()
  fetchVipConfigs()
})
</script>

<style scoped lang="scss">
.admin-users {
  .header-actions {
    display: flex;
    gap: 12px;
  }
  
  .pagination {
    margin-top: 20px;
    display: flex;
    justify-content: flex-end;
  }
}
</style>

