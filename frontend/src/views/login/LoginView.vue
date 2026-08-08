<script setup lang="ts">
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import LoginForm from './components/LoginForm.vue'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 如果已登录，直接跳转
if (authStore.isAuthenticated) {
  const redirect = (route.query.redirect as string) || '/chat'
  router.replace(redirect)
}

function handleSuccess() {
  const redirect = (route.query.redirect as string) || '/chat'
  router.push(redirect)
}
</script>

<template>
  <div class="login-container">
    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <div class="brand-content">
        <div class="brand-logo">
          <el-icon :size="64" color="#fff"><ChatDotRound /></el-icon>
        </div>
        <h1 class="brand-title">EasyRAG</h1>
        <p class="brand-subtitle">智能对话 · 知识库 · 工作流编排</p>
      </div>
    </div>
    
    <!-- 右侧表单区 -->
    <div class="login-form-wrapper">
      <div class="login-box">
        <div class="login-header">
          <h2>账号登录</h2>
        </div>
        
        <LoginForm @success="handleSuccess" />
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.login-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  
  @media (max-width: 768px) {
    .login-brand {
      display: none;
    }
    .login-form-wrapper {
      width: 100%;
    }
  }
}

// 左侧品牌区
.login-brand {
  width: 50%;
  background: linear-gradient(135deg, #409eff, #66b1ff);
  display: flex;
  align-items: center;
  justify-content: center;
  
  .brand-content {
    text-align: center;
    color: #fff;
  }
  
  .brand-logo {
    margin-bottom: 24px;
  }
  
  .brand-title {
    font-size: 48px;
    font-weight: 600;
    margin: 0 0 16px;
    letter-spacing: 2px;
  }
  
  .brand-subtitle {
    font-size: 18px;
    opacity: 0.9;
    margin: 0;
  }
}

// 右侧表单区
.login-form-wrapper {
  width: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f7fa;
}

.login-box {
  width: 400px;
  padding: 40px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
  
  h2 {
    margin: 0;
    font-size: 24px;
    color: #303133;
  }
}
</style>
