<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Save, X, Key } from 'lucide-vue-next';
import { useAuthStore } from '../stores/auth';
import { API_PROVIDERS } from '../types/api';

const props = defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  close: [];
}>();

const authStore = useAuthStore();
const apiKey = ref('');
const provider = ref('deepseek');
const model = ref('');
const isLoading = ref(false);
const isFetching = ref(true);
const saveSuccess = ref(false);
const errorMsg = ref('');

const loadSettings = async () => {
  isFetching.value = true;
  try {
    const result = await authStore.getApiKey();
    if (result.has_key) {
      apiKey.value = '********';
      if (result.provider) {
        provider.value = result.provider;
      }
      if (result.model) {
        model.value = result.model;
      }
    } else {
      apiKey.value = '';
      provider.value = 'deepseek';
      model.value = '';
    }
  } catch (e) {
    errorMsg.value = '无法获取API密钥状态';
  } finally {
    isFetching.value = false;
  }
};

const saveSettings = async () => {
  if (!apiKey.value.trim()) {
    errorMsg.value = '请输入API密钥';
    return;
  }

  if (apiKey.value.length < 8) {
    errorMsg.value = 'API密钥格式无效';
    return;
  }

  if (!model.value.trim()) {
    errorMsg.value = '请输入模型ID';
    return;
  }

  isLoading.value = true;
  errorMsg.value = '';

  const success = await authStore.setApiKey(apiKey.value.trim(), provider.value, model.value.trim());

  isLoading.value = false;

  if (success) {
    saveSuccess.value = true;
    setTimeout(() => {
      saveSuccess.value = false;
      emit('close');
    }, 2000);
  } else {
    errorMsg.value = authStore.error || '保存失败';
  }
};

const clearSettings = async () => {
  if (confirm('确定要清除API密钥吗？这将禁用划词提问功能。')) {
    isLoading.value = true;
    await authStore.deleteApiKey();
    apiKey.value = '';
    isLoading.value = false;
  }
};

onMounted(() => {
  if (props.isOpen) {
    loadSettings();
  }
});
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
    <div class="bg-white rounded-2xl w-full max-w-md mx-4 shadow-2xl border border-slate-200">
      <div class="p-6 border-b border-slate-100 flex justify-between items-center">
        <div class="flex items-center gap-3">
          <div class="p-2 bg-amber-50 rounded-lg">
            <Key class="text-amber-600" :size="20" />
          </div>
          <div>
            <h2 class="text-xl font-bold text-slate-900">AI 助手设置</h2>
            <p class="text-sm text-slate-500">配置划词提问功能</p>
          </div>
        </div>
        <button @click="emit('close')" class="p-2 hover:bg-slate-100 rounded-lg transition-colors">
          <X :size="20" />
        </button>
      </div>

      <div class="p-6 space-y-4">
        <div v-if="isFetching" class="text-center py-8 text-slate-400">
          加载中...
        </div>
        <template v-else>
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              AI 服务提供商
            </label>
            <select
              v-model="provider"
              :disabled="apiKey === '********'"
              class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:bg-slate-100"
            >
              <option v-for="p in API_PROVIDERS" :key="p.value" :value="p.value">
                {{ p.label }}
              </option>
            </select>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              模型 ID
            </label>
            <input
              v-model="model"
              type="text"
              :disabled="apiKey === '********'"
              placeholder="例如: deepseek-v4-flash, gpt-4, claude-3-sonnet"
              class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:bg-slate-100"
            />
            <p class="mt-2 text-xs text-slate-500">
              请输入您要使用的模型ID
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              API 密钥
            </label>
            <div class="relative">
              <input
                v-model="apiKey"
                type="password"
                :placeholder="apiKey === '********' ? '********' : 'sk-...'"
                :disabled="apiKey === '********'"
                class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:bg-slate-100"
              />
              <div class="absolute right-3 top-3">
                <Key class="text-slate-400" :size="16" />
              </div>
            </div>
            <p class="mt-2 text-xs text-slate-500">
              请输入您的AI服务API密钥
            </p>
            <p v-if="apiKey === '********'" class="mt-2 text-xs text-emerald-600">
              密钥已设置。如需更新请输入新密钥。
            </p>
          </div>

          <div v-if="errorMsg" class="p-4 bg-rose-50 border border-rose-100 rounded-xl">
            <div class="flex items-center gap-2 text-rose-700">
              <div class="w-2 h-2 rounded-full bg-rose-500"></div>
              <span class="text-sm font-medium">{{ errorMsg }}</span>
            </div>
          </div>

          <div v-if="saveSuccess" class="p-4 bg-emerald-50 border border-emerald-100 rounded-xl animate-pulse">
            <div class="flex items-center gap-2 text-emerald-700">
              <div class="w-2 h-2 rounded-full bg-emerald-500"></div>
              <span class="text-sm font-medium">设置保存成功！</span>
            </div>
          </div>
        </template>
      </div>

      <div class="p-6 border-t border-slate-100 flex justify-between">
        <button
          v-if="apiKey === '********'"
          @click="clearSettings"
          :disabled="isLoading"
          class="px-4 py-2 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors disabled:opacity-50"
        >
          清除设置
        </button>
        <div v-else></div>
        <div class="flex gap-3">
          <button
            @click="emit('close')"
            class="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          >
            取消
          </button>
          <button
            @click="saveSettings"
            :disabled="isLoading || isFetching"
            :class="[
              'px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors flex items-center gap-2',
              isLoading || isFetching ? 'bg-amber-400 cursor-not-allowed' : 'bg-amber-600 hover:bg-amber-700'
            ]"
          >
            <Save v-if="!isLoading" :size="16" />
            <span>{{ isLoading ? '保存中...' : '保存设置' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>