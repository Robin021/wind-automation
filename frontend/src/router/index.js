import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/Login.vue'),
      meta: { guest: true },
    },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      redirect: '/dashboard',
      meta: { requiresAuth: true },
      children: [
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('@/views/Dashboard.vue'),
          meta: { title: '首页' },
        },
        {
          path: 'my-stocks',
          name: 'MyStocks',
          component: () => import('@/views/MyStocks.vue'),
          meta: { title: '我的股票' },
        },
        {
          path: 'membership',
          name: 'Membership',
          component: () => import('@/views/Subscription.vue'),
          meta: { title: '会员中心' },
        },
        // 管理员路由
        {
          path: 'admin/users',
          name: 'AdminUsers',
          component: () => import('@/views/admin/Users.vue'),
          meta: { title: '用户管理', requiresAdmin: true },
        },
        {
          path: 'admin/stocks',
          name: 'AdminStocks',
          component: () => import('@/views/admin/Stocks.vue'),
          meta: { title: '股票池管理', requiresAdmin: true },
        },
        {
          path: 'admin/allocations',
          name: 'AdminAllocations',
          component: () => import('@/views/admin/Allocations.vue'),
          meta: { title: '分配管理', requiresAdmin: true },
        },
        {
          path: 'admin/config',
          name: 'AdminConfig',
          component: () => import('@/views/admin/Config.vue'),
          meta: { title: '系统配置', requiresAdmin: true },
        },
        {
          path: 'admin/datasources',
          name: 'AdminDataSources',
          component: () => import('@/views/admin/DataSources.vue'),
          meta: { title: '数据源管理', requiresAdmin: true },
        },
        {
          path: 'admin/signals',
          name: 'AdminSignals',
          component: () => import('@/views/admin/Signals.vue'),
          meta: { title: '信号计算', requiresAdmin: true },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFound.vue'),
    },
  ],
})

// 路由守卫（等待用户信息加载，避免误判管理员跳转）
router.beforeEach(async (to, from, next) => {
  const userStore = useUserStore()

  // 如果有 token 但未拉取用户信息，先拉取
  if (userStore.token && !userStore.user) {
    try {
      await userStore.fetchUser()
    } catch (e) {
      // 拉取失败，视为未登录
      userStore.logout()
    }
  }

  // 需要登录的页面
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  // 需要管理员权限
  if (to.meta.requiresAdmin && !userStore.isAdmin) {
    next({ name: 'Dashboard' })
    return
  }

  // 已登录用户访问登录页
  if (to.meta.guest && userStore.isLoggedIn) {
    next({ name: 'Dashboard' })
    return
  }

  next()
})

export default router
