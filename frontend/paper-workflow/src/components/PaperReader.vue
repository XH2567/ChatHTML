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

// 1. 获取论文 HTML URL（通过Vite代理）
const artifactUrl = `/artifacts/${props.jobId}/out/main.html`;

// 2. 划词监听逻辑 - 使用全局事件监听
const handleGlobalSelection = () => {
  console.log('handleGlobalSelection 被调用');
  
  // 尝试从主窗口获取选中文本
  const selection = window.getSelection();
  console.log('主窗口 selection 对象:', selection);
  
  // 如果主窗口没有选中文本，尝试从iframe获取
  let text = selection?.toString().trim();
  
  if (!text && iframeRef.value?.contentWindow) {
    try {
      // 尝试从iframe窗口获取选中文本
      const iframeSelection = iframeRef.value.contentWindow.getSelection();
      text = iframeSelection?.toString().trim();
      console.log('iframe 选中文本:', text);
    } catch (error) {
      console.log('无法访问iframe的selection对象（跨域限制）:', error);
    }
  }
  
  console.log('最终选中文本:', text, '长度:', text?.length);
  if (text && text.length > 2) { // 降低长度要求，从5改为2
    selectedText.value = text;
    // 自动打开侧边栏
    isSidebarOpen.value = true;
    console.log('侧边栏已打开，选中文本:', text);
  } else {
    console.log('文本太短或为空，不打开侧边栏');
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
        model: localStorage.getItem('ai-model') || 'gpt-4o', 
        api_key: localStorage.getItem('ai-api-key') || '', 
        full_paper: iframeRef.value?.contentDocument?.body.innerText.slice(0, 50000) || ''
      });
      messages.value.push({ role: 'bot', content: data.reply });
    } catch (err) {
      messages.value.push({ role: 'bot', content: 'AI 响应失败，请检查网络或 API Key' });
    } finally {
      isAiLoading.value = false;
    }
};

// 4. 使用全局事件监听
const onIframeLoad = () => {
  console.log('iframe 加载完成');
  
  // 检查 iframe 是否可访问
  if (iframeRef.value) {
    console.log('iframe 引用存在:', iframeRef.value);
    console.log('iframe src:', iframeRef.value.src);
    
    try {
      const iframeDoc = iframeRef.value.contentDocument;
      console.log('iframe contentDocument:', iframeDoc ? '可访问' : '不可访问（跨域限制）');
      
      // 尝试在 iframe 内部添加事件监听（如果跨域允许）
      if (iframeDoc) {
        iframeDoc.addEventListener('mouseup', handleGlobalSelection);
        console.log('iframe 内部 mouseup 事件监听器已添加');
        iframeDoc.addEventListener('selectionchange', handleGlobalSelection);
        console.log('iframe 内部 selectionchange 事件监听器已添加');
      }
    } catch (error) {
      console.log('iframe 访问错误（跨域）:', error);
    }
  }
  
  // 在主窗口添加全局鼠标抬起事件监听
  document.addEventListener('mouseup', handleGlobalSelection);
  console.log('全局 mouseup 事件监听器已添加');
  
  // 同时添加 selectionchange 事件监听，更可靠地捕获文本选择
  document.addEventListener('selectionchange', handleGlobalSelection);
  console.log('全局 selectionchange 事件监听器已添加');
  
  // 添加点击事件监听作为备选方案
  const handleClick = () => {
    console.log('全局 click 事件触发');
    // 延迟执行，确保选择已经完成
    setTimeout(handleGlobalSelection, 100);
  };
  document.addEventListener('click', handleClick);
  console.log('全局 click 事件监听器已添加');
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
  // 移除事件监听
  document.removeEventListener('mouseup', handleGlobalSelection);
});
</script>

<template>
  <div class="relative flex h-screen w-full bg-slate-50 overflow-hidden">
    <!-- 左侧：论文内容区 -->
    <div :class="['flex-1 transition-all duration-500', isSidebarOpen ? 'mr-[400px]' : 'mr-0']">
      <!-- 手动打开侧边栏按钮 -->
      <button 
        @click="isSidebarOpen = !isSidebarOpen"
        class="absolute top-4 left-4 z-10 flex items-center gap-2 px-3 py-2 bg-white border border-slate-200 rounded-lg shadow-md hover:bg-slate-50 transition-colors"
      >
        <Sparkles :size="16" class="text-amber-500" />
        <span class="text-sm font-medium text-slate-700">
          {{ isSidebarOpen ? '关闭' : '打开' }} AI 助手
        </span>
      </button>
      
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