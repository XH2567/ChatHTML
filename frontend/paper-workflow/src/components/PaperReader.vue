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

  // 先尝试主窗口
  const mainSelection = window.getSelection();
  if (mainSelection && mainSelection.toString().trim()) {
    text = mainSelection.toString().trim();
    selectionObj = mainSelection;
    console.log('主窗口选中文本:', text);
  }

  // 如果主窗口没有，尝试 iframe
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
  marker.title = '点击查看历史记录';

  try {
    console.log('range commonAncestorContainer:', range.commonAncestorContainer);
    console.log('range.startContainer:', range.startContainer);

    const clonedRange = range.cloneRange();
    clonedRange.collapse(false);
    clonedRange.insertNode(marker);

    const storedRange = range.cloneRange();
    markerRanges.value.set(markerHash, storedRange);

    marker.addEventListener('mouseenter', () => highlightText(markerHash, true));
    marker.addEventListener('mouseleave', () => highlightText(markerHash, false));
    marker.addEventListener('click', () => loadHistoryForMarker(markerHash));

    updateMarkerItems();
    console.log('标记已注入成功, hash:', markerHash);
  } catch (e) {
    console.error('注入标记失败:', e);
  }
}

function highlightText(hash: string, highlight: boolean) {
  const storedRange = markerRanges.value.get(hash);
  if (!storedRange) return;

  try {
    const iframeDoc = iframeRef.value?.contentDocument;
    if (!iframeDoc) return;

    if (highlight) {
      const existingHighlight = iframeDoc.querySelector(`.ai-query-highlight[data-hash="${hash}"]`);
      if (existingHighlight) return;

      const highlightSpan = iframeDoc.createElement('span');
      highlightSpan.className = 'ai-query-highlight';
      highlightSpan.dataset.hash = hash;

      const contents = storedRange.cloneContents();
      highlightSpan.appendChild(contents);

      storedRange.deleteContents();
      storedRange.insertNode(highlightSpan);
    } else {
      const highlightSpan = iframeDoc.querySelector(`.ai-query-highlight[data-hash="${hash}"]`);
      if (highlightSpan) {
        const parent = highlightSpan.parentNode;
        while (highlightSpan.firstChild) {
          parent?.insertBefore(highlightSpan.firstChild, highlightSpan);
        }
        parent?.removeChild(highlightSpan);
      }
    }
  } catch (e) {
    console.error('高亮处理失败:', e);
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

  // Build positions within the NORMALIZED content
  // normalizedPositions[i] = position of segment i's first char in normalized content
  const normSegStarts: number[] = [];
  let pos = 0;
  for (let i = 0; i < segments.length; i++) {
    // Record the start position of this segment in normalized content
    normSegStarts.push(pos);
    const segNorm = segments[i].text.replace(/\n+/g, '\n');
    pos += segNorm.length;
  }

  // Find start segment
  let startSegIdx = 0;
  for (let i = normSegStarts.length - 1; i >= 0; i--) {
    if (normSegStarts[i] <= index) {
      startSegIdx = i;
      break;
    }
  }
  const startOffsetInNorm = index - normSegStarts[startSegIdx];

  // Find end segment
  let endSegIdx = 0;
  for (let i = normSegStarts.length - 1; i >= 0; i--) {
    if (normSegStarts[i] < endIndex) {
      endSegIdx = i;
      break;
    }
  }
  const endOffsetInNorm = endIndex - normSegStarts[endSegIdx];

  // Map normalized offset to original text node offset
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
        // Consume all consecutive \n in original as 1 in normalized
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
            background-color: #fef3c7;
            border-radius: 2px;
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
  <div class="relative flex h-[calc(100vh-5px)] w-full bg-slate-50 overflow-hidden">
    <!-- 悬浮按钮组 - 固定在页面右上角，助手打开时隐藏 -->
    <div v-if="!isSidebarOpen" class="absolute top-4 right-4 z-10 flex flex-col items-center gap-2">
      <button
        @click="toggleSidebar"
        :disabled="isDisabled"
        :class="[
          'p-2.5 border rounded-lg shadow-md transition-colors',
          isDisabled
            ? 'bg-slate-100 border-slate-200 cursor-not-allowed'
            : 'bg-white border-slate-200 hover:bg-slate-50'
        ]"
        :title="isDisabled ? (hasApiKey ? '已锁定，请先解锁' : '请先配置API密钥') : '打开AI助手'"
      >
        <Sparkles :size="20" :class="isDisabled ? 'text-slate-300' : 'text-amber-500'" />
      </button>
      <button
        v-if="hasApiKey"
        @click="isLocked = !isLocked"
        class="p-2.5 bg-white border border-slate-200 rounded-lg shadow-md hover:bg-slate-50 transition-colors"
        :title="isLocked ? '已锁定，点击解锁' : '已解锁，点击锁定'"
      >
        <Lock v-if="isLocked" :size="20" class="text-slate-400" />
        <LockOpen v-else :size="20" class="text-slate-400" />
      </button>
    </div>
    
    <!-- 标记索引 - 左端列表 -->
    <div v-if="markerItems.length > 0" :class="[
      'shrink-0 border-r border-slate-200 bg-white overflow-y-auto z-30 transition-all duration-200',
      markerPanelCollapsed ? 'w-12 pt-8' : 'w-48 pt-8 px-3'
    ]">
      <div class="flex items-start justify-end mb-3 px-2">
        <button @click="markerPanelCollapsed = !markerPanelCollapsed"
          class="text-slate-400 hover:text-slate-600 p-1 rounded hover:bg-slate-100 transition-colors"
          :title="markerPanelCollapsed ? '展开' : '折叠'">
          <svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline :points="markerPanelCollapsed ? '9 18 15 12 9 6' : '15 18 9 12 15 6'"/></svg>
        </button>
      </div>
      <div v-for="item in markerItems" :key="item.hash"
        @click="scrollToMarker(item.hash)"
        :class="[
          'flex items-start gap-2 rounded-lg cursor-pointer hover:bg-amber-50 transition-colors',
          markerPanelCollapsed ? 'p-1.5 justify-center' : 'p-2 text-xs text-slate-600 mb-1'
        ]"
        :title="markerPanelCollapsed ? item.excerpt : ''">
        <span :class="['rounded-full bg-amber-500 shrink-0', markerPanelCollapsed ? 'w-3 h-3' : 'w-3 h-3 mt-0.5']"></span>
        <span v-if="!markerPanelCollapsed" class="line-clamp-2 leading-relaxed">{{ item.excerpt }}</span>
      </div>
    </div>

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
          <span v-if="isContinuationMode" class="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-normal">继续对话</span>
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
