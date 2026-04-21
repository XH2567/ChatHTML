<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { jobApi } from '../api/client';
import PaperReader from '../components/PaperReader.vue';
import { Loader2, ChevronLeft } from 'lucide-vue-next';

const route = useRoute();
const router = useRouter();
const jobId = route.params.id as string;
const job = ref<any>(null);
let pollTimer: number;

const checkStatus = async () => {
  job.value = await jobApi.getJob(jobId);
  // 如果还在处理，每 3 秒查一次
  if (['completed', 'error'].includes(job.value.status)) {
    clearTimeout(pollTimer);
  } else {
    pollTimer = setTimeout(checkStatus, 3000);
  }
};

onMounted(checkStatus);
onUnmounted(() => clearTimeout(pollTimer));
</script>

<template>
  <div class="h-screen flex flex-col">
    <!-- 顶部状态栏 -->
    <div class="h-14 bg-white border-b flex items-center px-4 justify-between">
      <button @click="router.push('/')" class="flex items-center gap-1 text-sm font-bold text-slate-500">
        <ChevronLeft :size="18" /> 返回
      </button>
      <div class="text-xs font-mono text-slate-400">{{ jobId }}</div>
      <div v-if="job?.status !== 'completed'" class="flex items-center gap-2 text-amber-600 text-sm font-bold">
        <Loader2 class="animate-spin" :size="16" /> {{ job?.status }}...
      </div>
      <div v-else class="text-emerald-600 text-sm font-bold">已就绪</div>
    </div>

    <!-- 内容区 -->
    <div class="flex-1 overflow-hidden">
      <!-- 只有状态是 completed 时才加载 Reader -->
      <PaperReader v-if="job?.status === 'completed'" :jobId="jobId" />
      
      <!-- 否则显示等待界面 -->
      <div v-else class="h-full flex flex-col items-center justify-center bg-slate-50 space-y-4">
        <Loader2 class="animate-spin text-slate-300" :size="48" />
        <p class="text-slate-500 animate-pulse">正在处理论文，请稍候...</p>
        <div class="text-xs text-slate-400 bg-slate-100 px-4 py-2 rounded-lg">
           当前阶段: {{ job?.status }}
        </div>
      </div>
    </div>
  </div>
</template>