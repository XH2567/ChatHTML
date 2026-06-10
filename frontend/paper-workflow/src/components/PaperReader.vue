<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue';
import { Sparkles, X, Send, Loader2, Lock, LockOpen } from 'lucide-vue-next';
import { jobApi } from '../api/client';
import { useAuthStore } from '../stores/auth';
import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
});

const renderMarkdown = (text: string) => {
  return md.render(text);
};

async function sha256(text: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

const props = defineProps<{ jobId: string }>();

const iframeRef = ref<HTMLIFrameElement | null>(null);
const isSidebarOpen = ref(false);
const selectedText = ref('');
const chatInput = ref('');
const messages = ref<{ role: 'user' | 'bot'; content: string }[]>([]);
const isAiLoading = ref(false);
const lastManualToggle = ref(0);
const isLocked = ref(false);
const hasApiKey = ref(true);
const paperContainerRef = ref<HTMLDivElement | null>(null);
const markerRanges = ref<Map<string, Range>>(new Map());
const savedSelectionRange = ref<Range | null>(null);
const isContinuationMode = ref(false);
const activeHistoryHash = ref<string | null>(null);
const markerItems = ref<{ hash: string; excerpt: string }[]>([]);
const markerPanelCollapsed = ref(false);

function updateMarkerItems() {
  const iframeDoc = iframeRef.value?.contentDocument;
  if (!iframeDoc) { markerItems.value = []; return; }
  const markers = iframeDoc.querySelectorAll('.ai-query-marker');
  const items: { hash: string; excerpt: string }[] = [];
  markers.forEach(m => {
    const el = m as HTMLElement;
    const hash = el.dataset.hash;
    const excerpt = el.dataset.excerpt || '';
    if (hash) items.push({ hash, excerpt });
  });
  markerItems.value = items;
}

function scrollToMarker(hash: string) {
  const iframeDoc = iframeRef.value?.contentDocument;
  if (!iframeDoc) return;
  const marker = iframeDoc.querySelector(`.ai-query-marker[data-hash="${hash}"]`) as HTMLElement | null;
  if (marker) {
    marker.scrollIntoView({ behavior: 'smooth', block: 'center' });
    loadHistoryForMarker(hash);
  }
}

const authStore = useAuthStore();

const isDisabled = computed(() => !hasApiKey.value || isLocked.value);

const toggleSidebar = () => {
  lastManualToggle.value = Date.now();
  isSidebarOpen.value = !isSidebarOpen.value;
};

const closeSidebar = () => {
  lastManualToggle.value = Date.now();
  isSidebarOpen.value = false;
};

const artifactUrl = computed(() => {
  const token = localStorage.getItem('auth_token');
  return `/api/jobs/${props.jobId}/out/main.html?token=${token}`;
});

const handleGlobalSelection = () => {
  console.log('handleGlobalSelection 被调用');

  let text = '';
  let selectionObj: Selection | null = null;

  const mainSelection = window.getSelection();
  if (mainSelection && mainSelection.toString().trim()) {
    text = mainSelection.toString().trim();
    selectionObj = mainSelection;
    console.log('主窗口选中文本:', text);
  }

  if (!text && iframeRef.value?.contentWindow) {
    try {
      const iframeSelection = iframeRef.value.contentWindow.getSelection();
      if (iframeSelection && iframeSelection.toString().trim()) {
        text = iframeSelection.toString().trim();
        selectionObj = iframeSelection;
        console.log('iframe 选中文本:', text);
      }
    } catch (error) {
      console.log('无法访问iframe的selection对象:', error);
    }
  }

  console.log('最终选中文本:', text, '长度:', text?.length);

  if (!hasApiKey.value || isLocked.value) {
    console.log('AI助手不可用（未配置API密钥或已锁定），跳过自动打开');
    return;
  }

  const msSinceManual = Date.now() - lastManualToggle.value;
  if (msSinceManual < 1000) {
    console.log('用户刚手动操作过侧边栏，跳过自动打开');
    return;
  }

  if (text && text.length > 2) {
    selectedText.value = text;
    isContinuationMode.value = false;
    activeHistoryHash.value = null;
    messages.value = [];

    // 保存选中的 Range 对象
    if (selectionObj && selectionObj.rangeCount > 0) {
      savedSelectionRange.value = selectionObj.getRangeAt(0).cloneRange();
      console.log('选区已保存');
    } else {
      savedSelectionRange.value = null;
      console.log('无法保存选区（无有效selection）');
    }

    isSidebarOpen.value = true;
    console.log('侧边栏已打开，选中文本:', text);
  } else {
    selectedText.value = '';
    console.log('文本太短或为空，清空选中内容');
  }
};

const handleContainerWheel = (event: WheelEvent) => {
  const iframeWin = iframeRef.value?.contentWindow;
  const iframeEl = iframeRef.value;
  if (!iframeWin || !iframeEl) return;

  const target = event.target as Node;
  if (iframeEl.contains(target) || iframeEl === target) {
    return;
  }

  event.preventDefault();

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

async function injectMarker(text: string, range: Range, hash?: string) {
  const iframeDoc = iframeRef.value?.contentDocument;
  if (!iframeDoc) {
    console.error('injectMarker: 无法获取 iframe contentDocument');
    return;
  }

  const markerHash = hash || await sha256(text);
  const excerpt = text.slice(0, 100);

  console.log('injectMarker 被调用, text长度:', text.length, 'hash:', markerHash);

  const marker = iframeDoc.createElement('span');
  marker.className = 'ai-query-marker';
  marker.dataset.hash = markerHash;
  marker.dataset.excerpt = excerpt;

  try {
    console.log('range commonAncestorContainer:', range.commonAncestorContainer);
    console.log('range.startContainer:', range.startContainer);

    const clonedRange = range.cloneRange();
    clonedRange.collapse(false);
    clonedRange.insertNode(marker);

    const storedRange = range.cloneRange();
    markerRanges.value.set(markerHash, storedRange);

    marker.addEventListener('click', () => loadHistoryForMarker(markerHash));

    updateMarkerItems();
    console.log('标记已注入成功, hash:', markerHash);
  } catch (e) {
    console.error('注入标记失败:', e);
  }
}

async function loadHistoryForMarker(hash: string) {
  try {
    const history = await jobApi.getQueryHistoryForText(props.jobId, hash);
    messages.value = [
      { role: 'user', content: history.query },
      { role: 'bot', content: history.reply }
    ];
    selectedText.value = history.text_excerpt;
    isContinuationMode.value = true;
    activeHistoryHash.value = hash;
    lastManualToggle.value = Date.now();
    isSidebarOpen.value = true;
    console.log('进入继续模式, hash:', hash);
  } catch (err: any) {
    console.error('加载历史记录失败:', err);
  }
}

const askAi = async () => {
  if (!chatInput.value.trim()) return;

  const userQuery = chatInput.value;
  chatInput.value = '';

  // 非继续模式：清空对话，开始新的一轮
  if (!isContinuationMode.value) {
    messages.value = [];
  }

  messages.value.push({ role: 'user', content: userQuery });
  isAiLoading.value = true;

  try {
    let context = selectedText.value;

    if (context.length > 3000) {
      messages.value.push({ role: 'bot', content: `选中文本较长（${context.length} 字符），将使用前 3000 字符作为上下文，其余部分会被截断。如需处理全文，请分段选择后分别提问。` });
      context = context.slice(0, 3000);
    }

    // 继续模式：将对话历史注入查询，让 AI 理解上下文
    let queryToSend = userQuery;
    if (isContinuationMode.value) {
      const historyText = messages.value
        .slice(0, -1)
        .map(m => `${m.role === 'user' ? '用户' : 'AI'}: ${m.content}`)
        .join('\n\n');
      queryToSend = `以下是关于这段文本的对话历史：\n${historyText}\n\n---\n\n请根据以上对话历史，回答下面的新问题：\n${userQuery}`;
    }

    const data = await jobApi.askAi({
      query: queryToSend,
      context: context,
      full_paper: iframeRef.value?.contentDocument?.body.innerText.slice(0, 50000) || ''
    });
    messages.value.push({ role: 'bot', content: data.reply });

    // 非继续模式：保存历史并注入标记
    if (!isContinuationMode.value && selectedText.value && savedSelectionRange.value) {
      const hash = await sha256(selectedText.value);
      const excerpt = selectedText.value.slice(0, 3000);

      await jobApi.saveQueryHistory(props.jobId, {
        text_excerpt: excerpt,
        text_hash: hash,
        query: userQuery,
        reply: data.reply
      });

      await injectMarker(selectedText.value, savedSelectionRange.value);
    }
  } catch (err: any) {
    const errorMsg = err?.response?.data?.error || err?.message || '未知错误';
    messages.value.push({ role: 'bot', content: `AI 响应失败: ${errorMsg}` });
  } finally {
    isAiLoading.value = false;
  }
};

function findTextInDocument(doc: Document, text: string): Range | null {
  const blockTags = new Set([
    'P', 'DIV', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6',
    'LI', 'TD', 'TH', 'BLOCKQUOTE', 'PRE', 'HR',
    'FIGURE', 'FIGCAPTION', 'SECTION', 'HEADER', 'FOOTER',
    'NAV', 'ARTICLE', 'ASIDE', 'MAIN', 'OL', 'UL', 'DL',
  ]);

  type Segment = { text: string; node: Text | null };
  const segments: Segment[] = [];

  function walk(el: Node) {
    let child = el.firstChild;
    while (child) {
      if (child.nodeType === Node.TEXT_NODE) {
        const t = child as Text;
        if (t.textContent) {
          segments.push({ text: t.textContent, node: t });
        }
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        const tag = (child as Element).tagName;
        const isBlock = blockTags.has(tag);
        if (isBlock && segments.length > 0) {
          const last = segments[segments.length - 1];
          if (last.text.length > 0 && !last.text.endsWith('\n')) {
            segments.push({ text: '\n', node: null });
          }
        }
        walk(child);
        if (isBlock) {
          const last = segments[segments.length - 1];
          if (last && last.text.length > 0 && !last.text.endsWith('\n')) {
            segments.push({ text: '\n', node: null });
          }
        }
      }
      child = child.nextSibling;
    }
  }

  walk(doc.body);

  const content = segments.map(s => s.text).join('');
  const searchText = text.replace(/\n+/g, '\n');
  const contentNorm = content.replace(/\n+/g, '\n');
  const index = contentNorm.indexOf(searchText);
  if (index === -1) return null;

  const endIndex = index + searchText.length;

  const normSegStarts: number[] = [];
  let pos = 0;
  for (let i = 0; i < segments.length; i++) {
    normSegStarts.push(pos);
    const segNorm = segments[i].text.replace(/\n+/g, '\n');
    pos += segNorm.length;
  }

  let startSegIdx = 0;
  for (let i = normSegStarts.length - 1; i >= 0; i--) {
    if (normSegStarts[i] <= index) {
      startSegIdx = i;
      break;
    }
  }
  const startOffsetInNorm = index - normSegStarts[startSegIdx];

  let endSegIdx = 0;
  for (let i = normSegStarts.length - 1; i >= 0; i--) {
    if (normSegStarts[i] < endIndex) {
      endSegIdx = i;
      break;
    }
  }
  const endOffsetInNorm = endIndex - normSegStarts[endSegIdx];

  const startSeg = segments[startSegIdx];
  const endSeg = segments[endSegIdx];
  if (!startSeg || !endSeg) return null;

  function normOffsetToOriginal(segText: string, normOff: number): number {
    let origPos = 0;
    let normPos = 0;
    while (normPos < normOff && origPos < segText.length) {
      const nc = segText[origPos];
      const isNewline = nc === '\n';
      if (isNewline) {
        let origEnd = origPos;
        while (origEnd < segText.length && segText[origEnd] === '\n') origEnd++;
        if (normPos + 1 <= normOff) {
          normPos++;
          origPos = origEnd;
        } else {
          break;
        }
      } else {
        origPos++;
        normPos++;
      }
    }
    return origPos;
  }

  const origStartOffset = normOffsetToOriginal(startSeg.text, startOffsetInNorm);
  const origEndOffset = normOffsetToOriginal(endSeg.text, endOffsetInNorm);

  const range = doc.createRange();
  range.setStart(startSeg.node!, origStartOffset);
  range.setEnd(endSeg.node!, origEndOffset);
  return range;
}

async function restoreMarkers() {
  const iframeDoc = iframeRef.value?.contentDocument;
  if (!iframeDoc || !iframeDoc.body) return;

  try {
    const histories = await jobApi.getQueryHistory(props.jobId);
    console.log(`restoreMarkers: 获取到 ${histories.length} 条历史记录`);
    let restoredCount = 0;
    for (const h of histories) {
      if (iframeDoc.querySelector(`.ai-query-marker[data-hash="${h.text_hash}"]`)) continue;
      if (!h.text_excerpt) continue;

      const range = findTextInDocument(iframeDoc, h.text_excerpt);
      if (range) {
        await injectMarker(h.text_excerpt, range, h.text_hash);
        restoredCount++;
      }
    }
    console.log(`restoreMarkers: 成功恢复 ${restoredCount}/${histories.length} 个标记`);
    updateMarkerItems();

    // 自动加载最近一条历史记录到侧边栏
    if (histories.length > 0) {
      const recent = histories[0];
      messages.value = [
        { role: 'user', content: recent.query },
        { role: 'bot', content: recent.reply }
      ];
      selectedText.value = recent.text_excerpt;
      isContinuationMode.value = true;
      activeHistoryHash.value = recent.text_hash;
    }
  } catch (err) {
    console.error('恢复标记失败:', err);
  }
}

const onIframeLoad = () => {
  console.log('iframe 加载完成');

  if (iframeRef.value) {
    console.log('iframe 引用存在:', iframeRef.value);
    console.log('iframe src:', iframeRef.value.src);

    try {
      const iframeDoc = iframeRef.value.contentDocument;
      console.log('iframe contentDocument:', iframeDoc ? '可访问' : '不可访问（跨域限制）');

      if (iframeDoc) {
        iframeDoc.addEventListener('mouseup', handleGlobalSelection);
        console.log('iframe 内部 mouseup 事件监听器已添加');
        iframeDoc.addEventListener('selectionchange', handleGlobalSelection);
        console.log('iframe 内部 selectionchange 事件监听器已添加');

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
            line-height: 1.7 !important;
            font-family: 'Georgia', 'Times New Roman', 'Noto Serif CJK SC', serif !important;
            color: #1e293b !important;
            padding: 2rem !important;
            max-width: 900px !important;
            margin: 0 auto !important;
            background: #faf9f7 !important;
          }
          p {
            margin-bottom: 0.8em !important;
            text-align: justify !important;
          }
          h1, h2, h3, h4, h5, h6 {
            font-family: 'Helvetica Neue', 'Arial', 'Noto Sans SC', sans-serif !important;
            color: #0f172a !important;
            margin-top: 1.2em !important;
            margin-bottom: 0.5em !important;
            line-height: 1.3 !important;
          }
          img, video, canvas, svg, object, embed {
            max-width: 100% !important;
            height: auto !important;
            border-radius: 6px !important;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
          }
          pre, code, blockquote, table, .math, .equation {
            max-width: 100% !important;
            overflow-x: auto !important;
            white-space: pre-wrap !important;
            word-break: break-word !important;
          }
          code {
            font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace !important;
            font-size: 0.9em !important;
            background: rgba(0,0,0,0.04) !important;
            padding: 0.15em 0.4em !important;
            border-radius: 4px !important;
          }
          pre {
            background: #f1f5f9 !important;
            border: 1px solid #e2e8f0 !important;
            border-radius: 8px !important;
            padding: 1em !important;
            margin: 1em 0 !important;
          }
          pre code {
            background: transparent !important;
            padding: 0 !important;
          }
          blockquote {
            border-left: 4px solid #d97706 !important;
            padding: 0.5em 1em !important;
            margin: 1em 0 !important;
            background: rgba(245, 158, 11, 0.06) !important;
            border-radius: 0 8px 8px 0 !important;
          }
          table {
            display: block !important;
            overflow-x: auto !important;
            border-collapse: collapse !important;
            margin: 1em 0 !important;
            font-size: 0.9em !important;
          }
          th, td {
            border: 1px solid #e2e8f0 !important;
            padding: 0.5em 0.75em !important;
            text-align: left !important;
          }
          th {
            background: #f8fafc !important;
            font-weight: 600 !important;
          }
          a {
            color: #d97706 !important;
            text-decoration: none !important;
          }
          a:hover {
            text-decoration: underline !important;
          }
          ::selection {
            background: rgba(245, 158, 11, 0.25) !important;
          }
          .ai-query-marker {
            display: inline-block;
            width: 14px;
            height: 14px;
            background: #f59e0b;
            border-radius: 50%;
            margin-left: 4px;
            cursor: pointer;
            opacity: 0.7;
            transition: opacity 0.2s;
            vertical-align: middle;
          }
          .ai-query-marker:hover {
            opacity: 1;
          }
          .ai-query-highlight {
            background: linear-gradient(180deg, rgba(254, 243, 199, 0.4) 0%, rgba(253, 230, 138, 0.5) 100%);
            border-radius: 3px;
            padding: 0 1px;
          }
          @media (max-width: 768px) {
            body {
              padding: 1rem !important;
            }
          }
        `;
        iframeDoc.head.appendChild(style);
        console.log('iframe 防超界 CSS 已注入');

        restoreMarkers().catch(err => console.error('restoreMarkers error:', err));
      }
    } catch (error) {
      console.log('iframe 访问错误（跨域）:', error);
    }
  }

  document.addEventListener('mouseup', handleGlobalSelection);
  console.log('全局 mouseup 事件监听器已添加');

  document.addEventListener('selectionchange', handleGlobalSelection);
  console.log('全局 selectionchange 事件监听器已添加');

  const handleClick = () => {
    console.log('全局 click 事件触发');
    setTimeout(handleGlobalSelection, 100);
  };
  document.addEventListener('click', handleClick);
  console.log('全局 click 事件监听器已添加');
};

onMounted(async () => {
  setupWheelForwarding();
  const result = await authStore.getApiKey();
  hasApiKey.value = result.has_key;

  const tryRestoreMarkers = () => {
    const iframeDoc = iframeRef.value?.contentDocument;
    if (iframeDoc?.readyState === 'complete' && iframeDoc.body?.childNodes.length > 0) {
      console.log('onMounted: iframe 已就绪，执行 restoreMarkers');
      restoreMarkers().catch(err => console.error('restoreMarkers error:', err));
      return true;
    }
    return false;
  };

  await nextTick();
  if (!tryRestoreMarkers()) {
    let attempts = 0;
    const maxAttempts = 20;
    const interval = setInterval(() => {
      attempts++;
      if (tryRestoreMarkers() || attempts >= maxAttempts) {
        clearInterval(interval);
        if (attempts >= maxAttempts) {
          console.warn('onMounted: restoreMarkers 重试超时');
        }
      }
    }, 500);
  }
});

onUnmounted(() => {
  document.removeEventListener('mouseup', handleGlobalSelection);

  const container = paperContainerRef.value;
  if (container) {
    container.removeEventListener('wheel', handleContainerWheel);
  }
});
</script>

<template>
  <div class="relative flex h-[calc(100vh-5px)] w-full bg-gradient-to-br from-slate-50 via-white to-slate-100/80 overflow-hidden">
    <!-- 悬浮按钮组 - 固定在页面右上角，助手打开时隐藏 -->
    <div v-if="!isSidebarOpen" class="absolute top-4 right-4 z-10 flex flex-col items-center gap-2">
      <button
        @click="toggleSidebar"
        :disabled="isDisabled"
        :class="[
          'p-2.5 border rounded-xl shadow-lg transition-all duration-200 backdrop-blur-sm',
          isDisabled
            ? 'bg-slate-100/80 border-slate-200 cursor-not-allowed'
            : 'bg-white/90 border-slate-200/80 hover:bg-white hover:shadow-xl hover:scale-105 active:scale-95'
        ]"
        :title="isDisabled ? (hasApiKey ? '已锁定，请先解锁' : '请先配置API密钥') : '打开AI助手'"
      >
        <Sparkles :size="20" :class="isDisabled ? 'text-slate-300' : 'text-amber-500'" />
      </button>
      <button
        v-if="hasApiKey"
        @click="isLocked = !isLocked"
        class="p-2.5 bg-white/90 border border-slate-200/80 rounded-xl shadow-lg backdrop-blur-sm hover:bg-white hover:shadow-xl hover:scale-105 active:scale-95 transition-all duration-200"
        :title="isLocked ? '已锁定，点击解锁' : '已解锁，点击锁定'"
      >
        <Lock v-if="isLocked" :size="20" class="text-slate-400" />
        <LockOpen v-else :size="20" class="text-slate-400" />
      </button>
    </div>
    
    <!-- 标记索引 - 左端列表 -->
    <div v-if="markerItems.length > 0" :class="[
      'shrink-0 border-r border-slate-200/80 bg-white/80 backdrop-blur-sm overflow-y-auto z-30 transition-all duration-200',
      markerPanelCollapsed ? 'w-12 pt-8' : 'w-48 pt-8 px-3'
    ]">
      <div class="flex items-start justify-end mb-2 px-2">
        <button @click="markerPanelCollapsed = !markerPanelCollapsed"
          class="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition-all duration-200"
          :title="markerPanelCollapsed ? '展开' : '折叠'">
          <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline :points="markerPanelCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'"/></svg>
        </button>
      </div>
      <div v-for="item in markerItems" :key="item.hash"
        @click="scrollToMarker(item.hash)"
        :class="[
          'flex items-start gap-2 rounded-lg cursor-pointer transition-all duration-150 marker-item-hover',
          markerPanelCollapsed ? 'p-1.5 justify-center' : 'p-2.5 text-xs text-slate-600 mb-1'
        ]"
        :title="markerPanelCollapsed ? item.excerpt : ''">
        <span :class="[
          'rounded-full shrink-0 ring-2 ring-offset-1',
          markerPanelCollapsed ? 'w-3 h-3 ring-amber-300' : 'w-2.5 h-2.5 mt-0.5 ring-amber-200',
          'bg-gradient-to-br from-amber-400 to-orange-500'
        ]"></span>
        <span v-if="!markerPanelCollapsed" class="line-clamp-2 leading-relaxed hover:text-amber-700 transition-colors">{{ item.excerpt }}</span>
      </div>
    </div>

    <!-- 左侧：论文内容区（居中显示，侧边栏打开时平滑左移） -->
    <div ref="paperContainerRef" :class="[
      'flex-1 overflow-hidden paper-container transition-all duration-500 ease-in-out',
      isSidebarOpen ? 'translate-x-[-200px]' : 'translate-x-[-20px]'
    ]">
      <div class="h-full flex flex-col">
        <div class="flex-1 max-w-4xl mx-auto w-full px-6 py-6">
          <div class="h-full rounded-xl bg-white shadow-[0_0_0_1px_rgba(0,0,0,0.04),0_8px_32px_rgba(0,0,0,0.06),0_2px_8px_rgba(0,0,0,0.04)] overflow-hidden">
            <iframe 
              ref="iframeRef"
              :src="artifactUrl"
              @load="onIframeLoad"
              class="w-full h-full border-none bg-white"
            ></iframe>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧：AI 侧边栏 -->
    <aside :class="[
      'fixed top-0 right-0 h-full w-[400px] bg-white border-l border-slate-200 shadow-2xl transition-transform duration-300 z-50 flex flex-col',
      isSidebarOpen ? 'translate-x-0' : 'translate-x-full'
    ]">
      <!-- Header -->
      <div class="p-4 border-b bg-gradient-to-r from-slate-50 via-white to-slate-50 flex justify-between items-center">
        <div class="flex items-center gap-2 font-black text-slate-800">
          <div class="p-1.5 bg-gradient-to-br from-amber-400 to-orange-500 rounded-lg shadow-sm">
            <Sparkles class="text-white" :size="16" />
          </div>
          AI 论文助手
          <span v-if="isContinuationMode" class="text-xs bg-gradient-to-r from-amber-100 to-orange-100 text-amber-700 px-2.5 py-0.5 rounded-full font-medium border border-amber-200/50 shadow-sm">继续对话</span>
        </div>
        <button @click="closeSidebar" class="p-2 hover:bg-slate-200 rounded-full transition-colors">
          <X :size="18" class="text-slate-400" />
        </button>
      </div>

      <!-- Chat History -->
      <div class="flex-1 overflow-y-auto p-4 space-y-4 bg-gradient-to-b from-slate-50/50 to-white">
        <div v-if="selectedText" class="relative p-3 bg-gradient-to-br from-amber-50 to-orange-50/50 rounded-xl border border-amber-200/60 text-xs text-slate-700 shadow-[0_1px_3px_rgba(0,0,0,0.04)] overflow-hidden">
          <div class="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-amber-400 to-orange-400 rounded-r-full"></div>
          <div class="pl-2.5 leading-relaxed line-clamp-4">
            <span class="text-amber-500 select-none mr-1">"</span>{{ selectedText }}<span class="text-amber-500 select-none ml-1">"</span>
          </div>
        </div>

        <div v-for="(msg, i) in messages" :key="i" 
          :class="['max-w-[85%] p-3 rounded-2xl text-sm leading-relaxed shadow-sm', 
                  msg.role === 'user' 
                    ? 'ml-auto bg-gradient-to-br from-slate-800 to-slate-900 text-white rounded-br-md' 
                    : 'mr-auto bg-gradient-to-br from-slate-50 to-white text-slate-700 markdown-body border border-slate-100 rounded-bl-md']">
          <span v-if="msg.role === 'user'">{{ msg.content }}</span>
          <div v-else v-html="renderMarkdown(msg.content)"></div>
        </div>
        
        <div v-if="isAiLoading" class="flex items-center gap-2.5 text-slate-500 text-xs">
          <span class="relative flex items-center justify-center w-5 h-5">
            <span class="absolute inset-0 rounded-full bg-amber-400/20 animate-ping"></span>
            <Loader2 class="relative animate-spin text-amber-500" :size="16" />
          </span>
          <span class="bg-gradient-to-r from-amber-600 to-orange-600 bg-clip-text text-transparent font-medium">AI 正在思考...</span>
        </div>
      </div>

      <!-- Input Area -->
      <div class="p-4 border-t bg-gradient-to-t from-slate-50 to-white">
        <div class="relative group">
          <input 
            v-model="chatInput"
            @keyup.enter="askAi"
            type="text" 
            placeholder="询问关于划选内容或整篇论文的问题..."
            class="w-full pl-4 pr-12 py-3 bg-white border border-slate-200 rounded-xl text-sm outline-none transition-all duration-200 placeholder:text-slate-400 focus:border-amber-300 focus:shadow-[0_0_0_3px_rgba(251,191,36,0.15),0_2px_8px_rgba(0,0,0,0.04)] hover:border-slate-300"
          />
          <button @click="askAi" class="absolute right-1.5 top-1/2 -translate-y-1/2 p-2 bg-slate-900 text-white rounded-lg hover:bg-amber-600 active:scale-95 transition-all duration-150 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed">
            <Send :size="15" />
          </button>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.paper-container {
  background: linear-gradient(135deg, #f8f6f2 0%, #f0ece6 100%);
}

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

.markdown-body > div > *:first-child {
  margin-top: 0;
}

.markdown-body > div > *:last-child {
  margin-bottom: 0;
}

.message-enter {
  opacity: 0;
  transform: translateY(8px);
}

aside > div.flex-1 > div > div {
  animation: messageSlideIn 0.25s ease-out both;
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

aside > div.flex-1 > div > div:nth-child(1) { animation-delay: 0s; }
aside > div.flex-1 > div > div:nth-child(2) { animation-delay: 0.05s; }
aside > div.flex-1 > div > div:nth-child(3) { animation-delay: 0.1s; }
aside > div.flex-1 > div > div:nth-child(4) { animation-delay: 0.15s; }
aside > div.flex-1 > div > div:nth-child(5) { animation-delay: 0.2s; }

.marker-item-hover:hover {
  background: linear-gradient(135deg, rgba(245, 158, 11, 0.08), rgba(217, 119, 6, 0.04));
  transform: translateX(2px);
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.12);
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.2);
}
</style>
