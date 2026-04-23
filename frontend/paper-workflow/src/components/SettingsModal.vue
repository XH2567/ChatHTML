<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { Save, X, Key } from 'lucide-vue-next';

const props = defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  close: [];
  saved: [];
}>();

const apiKey = ref('');
const isLoading = ref(false);
const saveSuccess = ref(false);

// 从localStorage加载设置
const loadSettings = () => {
  const savedKey = localStorage.getItem('ai-api-key');
  if (savedKey) {
    apiKey.value = savedKey;
  }
};

// 保存设置到localStorage
const saveSettings = () => {
  if (!apiKey.value.trim()) {
    alert('请输入API密钥');
    return;
  }

  isLoading.value = true;
  
  // 模拟保存过程
  setTimeout(() => {
    localStorage.setItem('ai-api-key', apiKey.value.trim());
    
    isLoading.value = false;
    saveSuccess.value = true;
    
    // 2秒后关闭成功提示
    setTimeout(() => {
      saveSuccess.value = false;
      emit('saved');
    }, 2000);
  }, 500);
};

// 清除设置
const clearSettings = () => {
  if (confirm('确定要清除API密钥吗？这将禁用划词提问功能。')) {
    localStorage.removeItem('ai-api-key');
    apiKey.value = '';
  }
};

onMounted(() => {
  loadSettings();
});
</script>

<template>
  <div v-if="isOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
    <div class="bg-white rounded-2xl w-full max-w-md mx-4 shadow-2xl border border-slate-200">
      <!-- Header -->
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

      <!-- Content -->
      <div class="p-6 space-y-4">
        <!-- API Key Input -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-2">
            API 密钥
          </label>
          <div class="relative">
            <input
              v-model="apiKey"
              type="password"
              placeholder="sk-..."
              class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
            />
            <div class="absolute right-3 top-3">
              <Key class="text-slate-400" :size="16" />
            </div>
          </div>
          <p class="mt-2 text-xs text-slate-500">
            请输入您的AI服务API密钥，例如OpenAI、DeepSeek等
          </p>
        </div>

        <!-- Success Message -->
        <div v-if="saveSuccess" class="p-4 bg-emerald-50 border border-emerald-100 rounded-xl animate-pulse">
          <div class="flex items-center gap-2 text-emerald-700">
            <div class="w-2 h-2 rounded-full bg-emerald-500"></div>
            <span class="text-sm font-medium">设置保存成功！</span>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="p-6 border-t border-slate-100 flex justify-between">
        <button
          @click="clearSettings"
          class="px-4 py-2 text-sm text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-colors"
        >
          清除设置
        </button>
        <div class="flex gap-3">
          <button
            @click="emit('close')"
            class="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          >
            取消
          </button>
          <button
            @click="saveSettings"
            :disabled="isLoading"
            :class="[
              'px-4 py-2 text-sm font-medium text-white rounded-lg transition-colors flex items-center gap-2',
              isLoading ? 'bg-amber-400 cursor-not-allowed' : 'bg-amber-600 hover:bg-amber-700'
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

<style scoped>
/* 简化样式 */
</style>
