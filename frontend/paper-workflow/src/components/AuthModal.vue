<script setup lang="ts">
import { ref } from 'vue';
import { X, Loader2, LogIn, UserPlus } from 'lucide-vue-next';
import { useAuthStore } from '../stores/auth';

const emit = defineEmits<{
  close: [];
}>();

const authStore = useAuthStore();
const isLogin = ref(true);
const username = ref('');
const password = ref('');
const confirmPassword = ref('');
const isSubmitting = ref(false);
const errorMsg = ref('');

const toggleMode = () => {
  isLogin.value = !isLogin.value;
  errorMsg.value = '';
  password.value = '';
  confirmPassword.value = '';
};

const submit = async () => {
  if (!username.value.trim()) {
    errorMsg.value = '请输入用户名';
    return;
  }
  if (password.value.length < 6) {
    errorMsg.value = '密码至少需要6个字符';
    return;
  }
  if (!isLogin.value && password.value !== confirmPassword.value) {
    errorMsg.value = '两次输入的密码不一致';
    return;
  }

  isSubmitting.value = true;
  errorMsg.value = '';

  let success = false;
  if (isLogin.value) {
    success = await authStore.login(username.value, password.value);
  } else {
    success = await authStore.register(username.value, password.value);
  }

  isSubmitting.value = false;

  if (success) {
    emit('close');
  } else {
    errorMsg.value = authStore.error || '操作失败';
  }
};
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
    <div class="bg-white rounded-2xl w-full max-w-md mx-4 shadow-2xl border border-slate-200">
      <div class="p-6 border-b border-slate-100 flex justify-between items-center">
        <div class="flex items-center gap-3">
          <div class="p-2 bg-amber-50 rounded-lg">
            <UserPlus v-if="!isLogin" class="text-amber-600" :size="20" />
            <LogIn v-else class="text-amber-600" :size="20" />
          </div>
          <div>
            <h2 class="text-xl font-bold text-slate-900">{{ isLogin ? '登录' : '注册' }}</h2>
            <p class="text-sm text-slate-500">{{ isLogin ? '欢迎回来' : '创建新账户' }}</p>
          </div>
        </div>
        <button @click="emit('close')" class="p-2 hover:bg-slate-100 rounded-lg transition-colors">
          <X :size="20" />
        </button>
      </div>

      <form @submit.prevent="submit" class="p-6 space-y-4">
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-2">用户名</label>
          <input
            v-model="username"
            type="text"
            placeholder="输入用户名"
            class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-slate-700 mb-2">密码</label>
          <input
            v-model="password"
            type="password"
            placeholder="输入密码"
            class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          />
        </div>

        <div v-if="!isLogin">
          <label class="block text-sm font-medium text-slate-700 mb-2">确认密码</label>
          <input
            v-model="confirmPassword"
            type="password"
            placeholder="再次输入密码"
            class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          />
        </div>

        <div v-if="errorMsg" class="p-4 bg-rose-50 border border-rose-100 rounded-xl">
          <div class="flex items-center gap-2 text-rose-700">
            <div class="w-2 h-2 rounded-full bg-rose-500"></div>
            <span class="text-sm font-medium">{{ errorMsg }}</span>
          </div>
        </div>

        <button
          type="submit"
          :disabled="isSubmitting"
          :class="[
            'w-full py-3 text-sm font-medium text-white rounded-xl transition-colors flex items-center justify-center gap-2',
            isSubmitting ? 'bg-amber-400 cursor-not-allowed' : 'bg-amber-600 hover:bg-amber-700'
          ]"
        >
          <Loader2 v-if="isSubmitting" class="animate-spin" :size="16" />
          <span>{{ isLogin ? '登录' : '注册' }}</span>
        </button>
      </form>

      <div class="p-6 border-t border-slate-100 text-center">
        <button @click="toggleMode" class="text-sm text-slate-500 hover:text-amber-600 transition-colors">
          {{ isLogin ? '还没有账户？立即注册' : '已有账户？立即登录' }}
        </button>
      </div>
    </div>
  </div>
</template>