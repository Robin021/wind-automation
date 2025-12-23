import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/api'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)
  
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.is_admin || false)
  const vipLevel = computed(() => user.value?.vip_level || 0)
  
  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.data.access_token
    localStorage.setItem('token', token.value)
    
    await fetchUser()
  }
  
  async function register(data) {
    await api.post('/auth/register', data)
  }
  
  async function fetchUser() {
    if (!token.value) return
    
    try {
      const res = await api.get('/auth/me')
      user.value = res.data
    } catch (e) {
      logout()
      throw e
    }
  }
  
  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }
  
  // 初始化时获取用户信息
  if (token.value) {
    fetchUser()
  }
  
  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    vipLevel,
    login,
    register,
    fetchUser,
    logout,
  }
})

