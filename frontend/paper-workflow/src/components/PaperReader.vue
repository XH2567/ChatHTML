<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { Sparkles, X, Send, Loader2 } from 'lucide-vue-next';
import { jobApi } from '../api/client';

const props = defineProps<{ jobId: string }>();

const iframeRef = ref<HTMLIFrameElement | null>(null);
const isSidebarOpen = ref(false);
const selectedText = ref('');
const chatInput = ref('');
const messages = ref<{ role: 'user' | 'bot'; content: string }[]>([]);
const isAiLoading = ref(false);

// 1. 获取论文 HTML 的 URL
const artifactUrl = `http://127.0.0.1:8000/api/jobs/${props.jobId}/artifacts/out/main.html`;

// 2. 划词监听逻辑
const handleSelection = () => {
  const selection = iframeRef.value?.contentWindow?.getSelection();
  const text = selection?.toString().trim();
  if (text && text.length > 5) {
    selectedText.value = text;
    // 自动打开侧边栏或显示浮动按钮（这里演示直接打开侧边栏）
    isSidebarOpen.value = true;
  }
};

// 3. 发送 AI 请求
const askAi = async () => {
  if (!chatInput.value.trim()) return;
  
  const userQuery = chatInput.value;
  messages.value.push({ role: 'user', content: userQuery });
  chatInput.value = '';
  isAiLoading.value = true;

  try {
    const data = await jobApi.askAi({
      query: userQuery,
      context: selectedText.value,
      model: 'gpt-4o', 
      apiKey: localStorage.getItem('ai-api-key') || '', 
      full_paper: iframeRef.value?.contentDocument?.body.innerText.slice(0, 50000) || ''
    });
    messages.value.push({ role: 'bot', content: data.reply });
  } catch (err) {
    messages.value.push({ role: 'bot', content: 'AI 响应失败，请检查网络或 API Key' });
  } finally {
    isAiLoading.value = false;
  }
};

// 4. 注入事件监听
const onIframeLoad = () => {
  const doc = iframeRef.value?.contentDocument;
  if (doc) {
    doc.addEventListener('mouseup', handleSelection);
  }
};

onMounted(() => {
  // 检查本地存储中是否有 API Key
  const key = localStorage.getItem('ai-api-key');
  if (!key) {
    console.warn("未检测到 AI API Key，请在设置中配置以启用对话功能。");
    // 你也可以在这里触发一个弹窗提示用户
  }
});

onUnmounted(() => {
  iframeRef.value?.contentDocument?.removeEventListener('mouseup', handleSelection);
});
</script>

<template>
  <div class="relative flex h-screen w-full bg-slate-50 overflow-hidden">
    <!-- 左侧：论文内容区 -->
    <div :class="['flex-1 transition-all duration-500', isSidebarOpen ? 'mr-[400px]' : 'mr-0']">
      <iframe 
        ref="iframeRef"
        :src="artifactUrl"
        @load="onIframeLoad"
        class="w-full h-full border-none bg-white shadow-inner"
      ></iframe>
    </div>

    <!-- 右侧：AI 侧边栏 -->
    <aside :class="[
      'fixed top-0 right-0 h-full w-[400px] bg-white border-l border-slate-200 shadow-2xl transition-transform duration-300 z-50 flex flex-col',
      isSidebarOpen ? 'translate-x-0' : 'translate-x-full'
    ]">
      <!-- Header -->
      <div class="p-4 border-b flex justify-between items-center bg-slate-50">
        <div class="flex items-center gap-2 font-black text-slate-800">
          <Sparkles class="text-amber-500" :size="20" />
          AI 论文助手
        </div>
        <button @click="isSidebarOpen = false" class="p-2 hover:bg-slate-200 rounded-full">
          <X :size="18" />
        </button>
      </div>

      <!-- Chat History -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        <div v-if="selectedText" class="p-3 bg-amber-50 rounded-xl border border-amber-100 text-xs text-slate-600 italic">
          “{{ selectedText }}”
        </div>

        <div v-for="(msg, i) in messages" :key="i" 
          :class="['max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed', 
                  msg.role === 'user' ? 'ml-auto bg-slate-900 text-white' : 'mr-auto bg-slate-100 text-slate-700']">
          {{ msg.content }}
        </div>
        
        <div v-if="isAiLoading" class="flex items-center gap-2 text-slate-400 text-xs animate-pulse">
          <Loader2 class="animate-spin" :size="14" /> AI 正在思考...
        </div>
      </div>

      <!-- Input Area -->
      <div class="p-4 border-t bg-white">
        <div class="relative">
          <input 
            v-model="chatInput"
            @keyup.enter="askAi"
            type="text" 
            placeholder="询问关于划选内容或整篇论文的问题..."
            class="w-full pl-4 pr-12 py-3 bg-slate-100 rounded-xl text-sm outline-none focus:ring-2 ring-amber-500/20"
          />
          <button @click="askAi" class="absolute right-2 top-1.5 p-1.5 bg-slate-900 text-white rounded-lg hover:bg-slate-800 transition-colors">
            <Send :size="16" />
          </button>
        </div>
      </div>
    </aside>
  </div>
</template>