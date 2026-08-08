<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const emit = defineEmits<{
  success: []
}>()

const authStore = useAuthStore()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
  remember: false
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 20, message: '用户名长度为 2-20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, max: 20, message: '密码长度为 4-20 个字符', trigger: 'blur' }
  ]
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  
  loading.value = true
  
  try {
    await authStore.login({
      username: form.username,
      password: form.password,
      remember: form.remember
    })
    
    ElMessage.success('登录成功')
    emit('success')
  } catch (error: any) {
    ElMessage.error(error.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <el-form
    ref="formRef"
    :model="form"
    :rules="rules"
    class="login-form"
    @keyup.enter="handleSubmit"
  >
    <el-form-item prop="username">
      <el-input
        v-model="form.username"
        placeholder="用户名"
        prefix-icon="User"
        size="large"
      />
    </el-form-item>
    
    <el-form-item prop="password">
      <el-input
        v-model="form.password"
        type="password"
        placeholder="密码"
        prefix-icon="Lock"
        size="large"
        show-password
      />
    </el-form-item>
    
    <el-form-item>
      <div class="form-actions">
        <el-checkbox v-model="form.remember">记住我</el-checkbox>
        <el-link type="primary" :underline="false">忘记密码？</el-link>
      </div>
    </el-form-item>
    
    <el-form-item>
      <el-button
        type="primary"
        size="large"
        class="login-btn"
        :loading="loading"
        @click="handleSubmit"
      >
        登 录
      </el-button>
    </el-form-item>
  </el-form>
</template>

<style lang="scss" scoped>
.login-form {
  .form-actions {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .login-btn {
    width: 100%;
  }
}
</style>
