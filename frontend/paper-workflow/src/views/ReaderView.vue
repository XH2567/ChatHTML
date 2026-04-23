<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { jobApi } from '../api/client';
import PaperReader from '../components/PaperReader.vue';
import { Loader2, ChevronLeft, AlertCircle } from 'lucide-vue-next';

const route = useRoute();
const router = useRouter();
const jobId = route.params.id as string;
const job = ref<any>(null);
const loading = ref(true);
const errorMessage = ref<string | null>(null);
let pollTimer: number;

const checkStatus = async () => {
  try {
    loading.value = true;
    errorMessage.value = null;
    job.value = await jobApi.getJob(jobId);
    loading.value = false;
    
    // 如果还在处理，每 3 秒查一次
    if (['completed', 'error'].includes(job.value.status)) {
      clearTimeout(pollTimer);
    } else {
      pollTimer = setTimeout(checkStatus, 3000);
    }
  } catch (error: any) {
    console.error('获取任务状态失败:', error);
    loading.value = false;
    // 如果 API 调用失败，也停止轮询
    clearTimeout(pollTimer);
    
    if (error.response?.status === 404) {
      errorMessage.value = '任务不存在或已被删除';
    } else {
      errorMessage.value = '获取任务状态失败，请检查网络连接';
    }
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
      <div v-if="job?.status === 'error'" class="flex items-center gap-2 text-red-600 text-sm font-bold">
        <AlertCircle :size="16" /> 处理失败
      </div>
      <div v-else-if="job?.status !== 'completed'" class="flex items-center gap-2 text-amber-600 text-sm font-bold">
        <Loader2 class="animate-spin" :size="16" /> {{ job?.status }}...
      </div>
      <div v-else class="text-emerald-600 text-sm font-bold">已就绪</div>
    </div>

    <!-- 内容区 -->
    <div class="flex-1 overflow-hidden">
      <!-- 只有状态是 completed 时才加载 Reader -->
      <PaperReader v-if="job?.status === 'completed'" :jobId="jobId" />
      
      <!-- 错误状态显示 -->
      <div v-else-if="job?.status === 'error'" class="h-full flex flex-col items-center justify-center bg-slate-50 space-y-4 p-8">
        <AlertCircle class="text-red-500" :size="64" />
        <h2 class="text-2xl font-bold text-red-700">处理失败</h2>
        <p class="text-slate-600 text-center max-w-2xl">
          论文处理过程中出现错误，请检查上传的文件或 arXiv ID 是否正确，然后重试。
        </p>
        <div v-if="job?.errors && job.errors.length > 0" class="mt-4 w-full max-w-2xl">
          <h3 class="text-lg font-semibold text-slate-700 mb-2">错误详情：</h3>
          <div class="bg-red-50 border border-red-200 rounded-lg p-4 space-y-2">
            <div v-for="(error, index) in job.errors" :key="index" class="text-red-700 text-sm font-mono">
              {{ error }}
            </div>
          </div>
        </div>
        <div class="mt-6 flex gap-4">
          <button @click="router.push('/')" class="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition">
            返回首页
          </button>
          <button @click="checkStatus" class="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 transition">
            重试检查
          </button>
        </div>
      </div>
      
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
