<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import PageHeader from '@/components/common/PageHeader.vue'
import { ElMessage } from 'element-plus'
import { User, Lock, InfoFilled, Check, Key } from '@element-plus/icons-vue'

const authStore = useAuthStore()

const profileForm = ref({
  username: '',
  nickname: '',
  avatar: '',
  email: ''
})

const passwordForm = ref({
  oldPassword: '',
  newPassword: '',
  confirmPassword: ''
})

const loading = ref(false)

onMounted(() => {
  // 初始化表单数据
  if (authStore.user) {
    profileForm.value.username = authStore.user.username || ''
    profileForm.value.nickname = authStore.nickname || ''
    profileForm.value.avatar = authStore.user.avatar || ''
    profileForm.value.email = authStore.user.email || ''
  }
})

async function handleUpdateProfile() {
  loading.value = true
  try {
    // TODO: 调用 API 更新用户信息
    await new Promise(resolve => setTimeout(resolve, 500))
    ElMessage.success('个人信息已更新')
  } catch (error) {
    ElMessage.error('更新失败')
  } finally {
    loading.value = false
  }
}

async function handleUpdatePassword() {
  if (passwordForm.value.newPassword !== passwordForm.value.confirmPassword) {
    ElMessage.error('两次输入的密码不一致')
    return
  }
  loading.value = true
  try {
    // TODO: 调用 API 修改密码
    await new Promise(resolve => setTimeout(resolve, 500))
    ElMessage.success('密码已修改')
    passwordForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
  } catch (error) {
    ElMessage.error('密码修改失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="profile-view">
    <PageHeader title="个人中心" subtitle="管理您的个人信息和账户设置" />
    
    <div class="profile-container">
      <!-- 基本信息卡片 -->
      <el-card class="profile-card">
        <template #header>
          <div class="card-header">
            <el-icon><User /></el-icon>
            <span>基本信息</span>
          </div>
        </template>
        
        <el-form :model="profileForm" label-width="100px">
          <el-form-item label="头像">
            <el-avatar :size="64" :src="profileForm.avatar">
              {{ profileForm.nickname?.charAt(0) || profileForm.username?.charAt(0) || 'U' }}
            </el-avatar>
          </el-form-item>
          
          <el-form-item label="用户名">
            <el-input v-model="profileForm.username" placeholder="请输入用户名" />
          </el-form-item>
          
          <el-form-item label="昵称">
            <el-input v-model="profileForm.nickname" placeholder="请输入昵称" />
          </el-form-item>
          
          <el-form-item label="邮箱">
            <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="handleUpdateProfile">
              <el-icon><Check /></el-icon>
              保存修改
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
      
      <!-- 修改密码卡片 -->
      <el-card class="profile-card">
        <template #header>
          <div class="card-header">
            <el-icon><Lock /></el-icon>
            <span>修改密码</span>
          </div>
        </template>
        
        <el-form :model="passwordForm" label-width="100px">
          <el-form-item label="当前密码">
            <el-input 
              v-model="passwordForm.oldPassword" 
              type="password" 
              placeholder="请输入当前密码"
              show-password
            />
          </el-form-item>
          
          <el-form-item label="新密码">
            <el-input 
              v-model="passwordForm.newPassword" 
              type="password" 
              placeholder="请输入新密码"
              show-password
            />
          </el-form-item>
          
          <el-form-item label="确认密码">
            <el-input 
              v-model="passwordForm.confirmPassword" 
              type="password" 
              placeholder="请再次输入新密码"
              show-password
            />
          </el-form-item>
          
          <el-form-item>
            <el-button type="primary" :loading="loading" @click="handleUpdatePassword">
              <el-icon><Key /></el-icon>
              修改密码
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
      
      <!-- 账户信息卡片 -->
      <el-card class="profile-card">
        <template #header>
          <div class="card-header">
            <el-icon><InfoFilled /></el-icon>
            <span>账户信息</span>
          </div>
        </template>
        
        <el-descriptions :column="1" border>
          <el-descriptions-item label="用户ID">{{ authStore.user?.id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="角色">
            <el-tag v-for="role in authStore.user?.roles" :key="role" size="small">
              {{ role }}
            </el-tag>
            <span v-if="!authStore.user?.roles?.length">-</span>
          </el-descriptions-item>
          <el-descriptions-item label="注册时间">-</el-descriptions-item>
          <el-descriptions-item label="最后登录">-</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.profile-view {
  padding: 0;
}

.profile-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 20px;
  margin-top: 16px;
}

.profile-card {
  .card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 500;
  }
  
  :deep(.el-card__header) {
    padding: 16px 20px;
    border-bottom: 1px solid #e4e7ed;
  }
  
  :deep(.el-card__body) {
    padding: 20px;
  }
}

:deep(.el-descriptions__label) {
  width: 120px;
}
</style>
