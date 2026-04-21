<script setup lang="ts">
import type { JobState } from '../types/api';
import { Loader2, CheckCircle2, XCircle, Clock, FileText, Database } from 'lucide-vue-next';
import { useRouter } from 'vue-router';

const props = defineProps<{ job: JobState }>();
const router = useRouter();

// 状态对应的 UI 配置
const statusUI = {
  completed: { color: 'text-emerald-600 bg-emerald-50', icon: CheckCircle2, label: '已完成' },
  error: { color: 'text-rose-600 bg-rose-50', icon: XCircle, label: '失败' },
  processing: { color: 'text-amber-600 bg-amber-50 animate-pulse', icon: Loader2, label: '处理中' },
  downloading: { color: 'text-blue-600 bg-blue-50 animate-pulse', icon: Loader2, label: '下载中' },
  validating: { color: 'text-indigo-600 bg-indigo-50 animate-pulse', icon: Loader2, label: '校验中' },
  queued: { color: 'text-slate-400 bg-slate-100', icon: Clock, label: '排队中' },
};

const getUI = (status: string) => {
  return statusUI[status as keyof typeof statusUI] || statusUI.queued;
};

const goToDetail = () => {
  router.push(`/jobs/${props.job.jobId}`);
};

</script>

<template>
  <div 
    @click="goToDetail"
    class="glass-card rounded-3xl p-6 transition-all hover:scale-[1.02] hover:shadow-2xl cursor-pointer group"
  >
    <div class="glass-card rounded-3xl p-6 transition-all hover:scale-[1.02] hover:shadow-2xl">
      <div class="flex justify-between items-start mb-6">
        <div class="flex flex-col">
          <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Project ID</span>
          <span class="font-mono text-sm font-black text-slate-800">{{ job.jobId.slice(0, 13) }}</span>
        </div>
        <div :class="['flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[10px] font-black uppercase tracking-tighter', getUI(job.status).color]">
          <component :is="getUI(job.status).icon" :size="12" stroke-width="3" />
          {{ getUI(job.status).label }}
        </div>
      </div>

      <div class="space-y-4 mb-6">
        <div class="flex items-center gap-3">
          <div class="p-2 bg-slate-100 rounded-lg text-slate-500">
            <Database v-if="job.sourceMode === 'arxiv'" :size="16" />
            <FileText v-else :size="16" />
          </div>
          <div>
            <div class="text-[10px] text-slate-400 font-bold uppercase">Source / ID</div>
            <div class="text-sm font-bold text-slate-700">
              {{ job.sourceMode === 'arxiv' ? job.arxivId : 'Manual Upload' }}
            </div>
          </div>
        </div>
      </div>

      <button class="w-full py-3 bg-slate-900 hover:bg-slate-800 text-white rounded-2xl text-xs font-bold transition-all shadow-lg shadow-slate-200">
        查看详情
      </button>
    </div>
  </div>
</template>