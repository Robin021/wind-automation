<template>
  <div class="admin-stocks">
    <div class="page-header">
      <h2>股票池管理</h2>
      <div class="header-actions">
        <el-input 
          v-model="keyword" 
          placeholder="搜索代码或名称" 
          clearable 
          style="width: 200px"
          @clear="fetchStocks"
          @keyup.enter="fetchStocks"
        >
          <template #append>
            <el-button :icon="Search" @click="fetchStocks" />
          </template>
        </el-input>
        <el-button type="primary" @click="showImportDialog">
          <el-icon><Upload /></el-icon> 导入
        </el-button>
        <el-button type="primary" @click="showAddDialog">
          <el-icon><Plus /></el-icon> 添加
        </el-button>
      </div>
    </div>
    
    <el-card>
      <el-table :data="stocks" v-loading="loading" style="width: 100%">
        <el-table-column prop="code" label="代码" width="120">
          <template #default="{ row }">
            <span class="stock-code">{{ row.code }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="market" label="市场" width="80" />
        <el-table-column prop="industry" label="行业" width="120" />
        <el-table-column label="标签" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.is_st" type="danger" size="small">ST</el-tag>
            <el-tag v-if="row.is_kcb" type="warning" size="small">科创</el-tag>
            <el-tag v-if="row.is_cyb" size="small">创业</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="80">
          <template #default="{ row }">
            <el-switch 
              :model-value="row.is_active" 
              @change="toggleActive(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button size="small" @click="showEditDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteStock(row)">删除</el-button>
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
          @current-change="fetchStocks"
        />
      </div>
    </el-card>
    
    <!-- 添加/编辑对话框 -->
    <el-dialog v-model="editDialogVisible" :title="editMode ? '编辑股票' : '添加股票'" width="500px">
      <el-form :model="stockForm" :rules="stockRules" ref="stockFormRef" label-width="80px">
        <el-form-item label="代码" prop="code">
          <el-input v-model="stockForm.code" :disabled="editMode" placeholder="如 600000.SH" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="stockForm.name" />
        </el-form-item>
        <el-form-item label="市场">
          <el-select v-model="stockForm.market" style="width: 100%">
            <el-option label="上海" value="SH" />
            <el-option label="深圳" value="SZ" />
            <el-option label="北交所" value="BJ" />
          </el-select>
        </el-form-item>
        <el-form-item label="行业">
          <el-input v-model="stockForm.industry" />
        </el-form-item>
        <el-form-item label="标签">
          <el-checkbox v-model="stockForm.is_st">ST</el-checkbox>
          <el-checkbox v-model="stockForm.is_kcb">科创板</el-checkbox>
          <el-checkbox v-model="stockForm.is_cyb">创业板</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveStock" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
    
    <!-- 导入对话框 -->
    <el-dialog v-model="importDialogVisible" title="导入股票" width="500px">
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".xlsx,.xls"
        :on-change="handleFileChange"
      >
        <el-icon :size="40"><Upload /></el-icon>
        <div class="el-upload__text">拖拽文件到这里，或 <em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">
            支持 Excel 文件（.xlsx/.xls），需包含 code、name 列
          </div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="importStocks" :loading="importing" :disabled="!uploadFile">
          导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Upload, Plus } from '@element-plus/icons-vue'
import api from '@/api'

const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const stocks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const keyword = ref('')

const editDialogVisible = ref(false)
const importDialogVisible = ref(false)
const editMode = ref(false)
const currentStockId = ref(null)
const stockFormRef = ref()
const uploadRef = ref()
const uploadFile = ref(null)

const stockForm = reactive({
  code: '',
  name: '',
  market: '',
  industry: '',
  is_st: false,
  is_kcb: false,
  is_cyb: false,
})

const stockRules = {
  code: [{ required: true, message: '请输入股票代码', trigger: 'blur' }],
  name: [{ required: true, message: '请输入股票名称', trigger: 'blur' }],
}

async function fetchStocks() {
  loading.value = true
  try {
    const params = {
      skip: (page.value - 1) * pageSize,
      limit: pageSize,
      is_active: null,
    }
    if (keyword.value) {
      params.keyword = keyword.value
    }
    
    const res = await api.get('/stocks', { params })
    stocks.value = res.data.items
    total.value = res.data.total
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

function showAddDialog() {
  editMode.value = false
  currentStockId.value = null
  Object.assign(stockForm, {
    code: '',
    name: '',
    market: '',
    industry: '',
    is_st: false,
    is_kcb: false,
    is_cyb: false,
  })
  editDialogVisible.value = true
}

function showEditDialog(stock) {
  editMode.value = true
  currentStockId.value = stock.id
  Object.assign(stockForm, stock)
  editDialogVisible.value = true
}

async function saveStock() {
  const valid = await stockFormRef.value.validate().catch(() => false)
  if (!valid) return
  
  saving.value = true
  try {
    if (editMode.value) {
      await api.put(`/stocks/${currentStockId.value}`, stockForm)
    } else {
      await api.post('/stocks', stockForm)
    }
    ElMessage.success('保存成功')
    editDialogVisible.value = false
    fetchStocks()
  } catch (e) {
    console.error(e)
  } finally {
    saving.value = false
  }
}

async function toggleActive(stock) {
  try {
    await api.post(`/stocks/${stock.id}/toggle-active`)
    fetchStocks()
  } catch (e) {
    console.error(e)
  }
}

async function deleteStock(stock) {
  try {
    await ElMessageBox.confirm(`确定要删除股票 ${stock.code} ${stock.name} 吗？`, '确认删除')
    await api.delete(`/stocks/${stock.id}`)
    ElMessage.success('删除成功')
    fetchStocks()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
    }
  }
}

function showImportDialog() {
  uploadFile.value = null
  uploadRef.value?.clearFiles()
  importDialogVisible.value = true
}

function handleFileChange(file) {
  uploadFile.value = file.raw
}

async function importStocks() {
  if (!uploadFile.value) return
  
  importing.value = true
  try {
    const formData = new FormData()
    formData.append('file', uploadFile.value)
    
    const res = await api.post('/stocks/import', formData)
    ElMessage.success(res.data.message)
    importDialogVisible.value = false
    fetchStocks()
  } catch (e) {
    console.error(e)
  } finally {
    importing.value = false
  }
}

onMounted(fetchStocks)
</script>

<style scoped lang="scss">
.admin-stocks {
  .header-actions {
    display: flex;
    gap: 12px;
  }
  
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

