<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { Sparkles, X, Send, Loader2 } from 'lucide-vue-next';
import { jobApi } from '../api/client';
import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
});

// 将 Markdown 文本渲染为 HTML
const renderMarkdown = (text: string) => {
  return md.render(text);
};

const props = defineProps<{ jobId: string }>();

const iframeRef = ref<HTMLIFrameElement | null>(null);
const isSidebarOpen = ref(false);
const selectedText = ref('');
const chatInput = ref('');
const messages = ref<{ role: 'user' | 'bot'; content: string }[]>([]);
const isAiLoading = ref(false);
const lastManualToggle = ref(0);
const paperContainerRef = ref<HTMLDivElement | null>(null);

// 用户手动切换侧边栏
const toggleSidebar = () => {
  lastManualToggle.value = Date.now();
  isSidebarOpen.value = !isSidebarOpen.value;
};

// 用户手动关闭侧边栏
const closeSidebar = () => {
  lastManualToggle.value = Date.now();
  isSidebarOpen.value = false;
};

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
      console.log('无法访问iframe的selection对象:', error);
    }
  }
  
  console.log('最终选中文本:', text, '长度:', text?.length);
  
  // 如果用户刚刚手动操作过侧边栏（一秒内），则不自动打开
  const msSinceManual = Date.now() - lastManualToggle.value;
  if (msSinceManual < 1000) {
    console.log('用户刚手动操作过侧边栏，跳过自动打开');
    return;
  }
  
  if (text && text.length > 2) {
    selectedText.value = text;
    // 自动打开侧边栏
    isSidebarOpen.value = true;
    console.log('侧边栏已打开，选中文本:', text);
  } else {
    // 清空选中内容
    selectedText.value = '';
    console.log('文本太短或为空，清空选中内容');
  }
};

// 在论文内容框外部滚动滚轮时，转发到 iframe 内部
const handleContainerWheel = (event: WheelEvent) => {
  const iframeWin = iframeRef.value?.contentWindow;
  const iframeEl = iframeRef.value;
  if (!iframeWin || !iframeEl) return;
  
  // 如果事件目标在 iframe 内部，让 iframe 原生处理滚轮，避免双重滚动
  const target = event.target as Node;
  if (iframeEl.contains(target) || iframeEl === target) {
    return;
  }
  
  // 防止默认行为（例如页面整体滚动）
  event.preventDefault();
  
  // 将滚轮滚动转发到 iframe 内部
  iframeWin.scrollBy({
    top: event.deltaY,
    behavior: 'auto'
  });
};

const setupWheelForwarding = () => {
  const container = paperContainerRef.value;
  if (!container) {
    console.warn('paperContainerRef 不可用，无法设置滚轮转发');
    return;
  }
  container.addEventListener('wheel', handleContainerWheel, { passive: false });
  console.log('论文容器滚轮事件转发已设置');
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
        model: localStorage.getItem('ai-model') || 'deepseek-chat', 
        api_key: localStorage.getItem('ai-api-key') || '', 
        full_paper: iframeRef.value?.contentDocument?.body.innerText.slice(0, 50000) || ''
      });
      messages.value.push({ role: 'bot', content: data.reply });
    } catch (err: any) {
      // 尝试从后端响应中提取具体错误信息
      const errorMsg = err?.response?.data?.error || err?.message || '未知错误';
      messages.value.push({ role: 'bot', content: `AI 响应失败: ${errorMsg}` });
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
        
        // 注入 CSS 以防止论文内容超界（横向溢出）
        const style = document.createElement('style');
        style.textContent = `
          * {
            max-width: 100%;
            box-sizing: border-box;
          }
          body {
            overflow-x: hidden !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
            word-break: break-word !important;
          }
          img, video, canvas, svg, object, embed {
            max-width: 100% !important;
            height: auto !important;
          }
          pre, code, blockquote, table, .math, .equation {
            max-width: 100% !important;
            overflow-x: auto !important;
            white-space: pre-wrap !important;
            word-break: break-word !important;
          }
          table {
            display: block !important;
            overflow-x: auto !important;
          }
        `;
        iframeDoc.head.appendChild(style);
        console.log('iframe 防超界 CSS 已注入');
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
  
  // 设置滚轮事件转发（论文内容框外部滚动滚轮也能滚动论文内容）
  setupWheelForwarding();
});

onUnmounted(() => {
  // 移除事件监听
  document.removeEventListener('mouseup', handleGlobalSelection);
  
  // 移除滚轮事件转发
  const container = paperContainerRef.value;
  if (container) {
    container.removeEventListener('wheel', handleContainerWheel);
  }
});
</script>

<template>
  <div class="relative flex h-[calc(100vh-5px)] w-full bg-slate-50 overflow-hidden">
    <!-- 悬浮按钮 - 固定在页面右上角，仅图标，助手打开时隐藏 -->
    <button 
      v-if="!isSidebarOpen"
      @click="toggleSidebar"
      class="absolute top-4 right-4 z-10 p-2.5 bg-white border border-slate-200 rounded-lg shadow-md hover:bg-slate-50 transition-colors"
    >
      <Sparkles :size="20" class="text-amber-500" />
    </button>
    
    <!-- 左侧：论文内容区（居中显示，侧边栏打开时平滑左移） -->
    <div ref="paperContainerRef" :class="[
      'flex-1 overflow-hidden paper-container transition-all duration-500 ease-in-out',
      isSidebarOpen ? 'translate-x-[-200px]' : 'translate-x-[-20px]'
    ]">
      <div class="max-w-4xl mx-auto h-full pt-4 pb-[60px]">
        <iframe 
          ref="iframeRef"
          :src="artifactUrl"
          @load="onIframeLoad"
          class="w-full h-full border-none bg-white shadow-inner rounded-lg"
        ></iframe>
      </div>
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
        <button @click="closeSidebar" class="p-2 hover:bg-slate-200 rounded-full">
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
                  msg.role === 'user' ? 'ml-auto bg-slate-900 text-white' : 'mr-auto bg-slate-100 text-slate-700 markdown-body']">
          <span v-if="msg.role === 'user'">{{ msg.content }}</span>
          <div v-else v-html="renderMarkdown(msg.content)"></div>
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

<style scoped>
.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  margin-top: 0.75em;
  margin-bottom: 0.5em;
  font-weight: 700;
  line-height: 1.3;
}
.markdown-body h1 { font-size: 1.25rem; }
.markdown-body h2 { font-size: 1.125rem; }
.markdown-body h3 { font-size: 1rem; }
.markdown-body p {
  margin-bottom: 0.5em;
  line-height: 1.6;
}
.markdown-body p:last-child {
  margin-bottom: 0;
}
.markdown-body ul,
.markdown-body ol {
  padding-left: 1.5em;
  margin-bottom: 0.5em;
}
.markdown-body li {
  margin-bottom: 0.25em;
}
.markdown-body code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 0.8125rem;
  background: rgba(0,0,0,0.06);
  padding: 0.15em 0.4em;
  border-radius: 4px;
}
.markdown-body pre {
  margin: 0.5em 0;
  padding: 0.75em;
  background: #1e293b;
  border-radius: 8px;
  overflow-x: auto;
}
.markdown-body pre code {
  background: transparent;
  padding: 0;
  color: #e2e8f0;
  font-size: 0.75rem;
  line-height: 1.5;
}
.markdown-body strong {
  font-weight: 700;
}
.markdown-body em {
  font-style: italic;
}
.markdown-body a {
  color: #d97706;
  text-decoration: underline;
}
.markdown-body blockquote {
  border-left: 3px solid #d97706;
  padding-left: 0.75em;
  margin: 0.5em 0;
  color: #64748b;
}
.markdown-body hr {
  border: none;
  border-top: 1px solid #e2e8f0;
  margin: 0.75em 0;
}
.markdown-body table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.5em 0;
  font-size: 0.8125rem;
}
.markdown-body th,
.markdown-body td {
  border: 1px solid #e2e8f0;
  padding: 0.4em 0.6em;
  text-align: left;
}
.markdown-body th {
  background: #f8fafc;
  font-weight: 600;
}
</style>
