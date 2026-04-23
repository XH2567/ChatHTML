<script setup lang="ts">
import { ref } from 'vue';
import { jobApi } from '../api/client';
import { X, Upload, Hash, Loader2, AlertCircle } from 'lucide-vue-next';

// 定义事件，让父组件知道任务创建成功了
const emit = defineEmits(['close', 'success']);

const sourceMode = ref<'upload' | 'arxiv'>('upload');
const arxivId = ref('');
const selectedFile = ref<File | null>(null);
const isSubmitting = ref(false);
const validationError = ref<string | null>(null);

const handleFileChange = (e: Event) => {
  const target = e.target as HTMLInputElement;
  if (target.files) {
    selectedFile.value = target.files[0];
    validationError.value = null; // 选择文件后清除错误提示
  }
};

const submit = async () => {
  // 前端输入校验
  if (sourceMode.value === 'arxiv') {
    if (!arxivId.value.trim()) {
      validationError.value = '请输入 arXiv ID';
      return;
    }
  } else {
    if (!selectedFile.value) {
      validationError.value = '请选择一个文件上传';
      return;
    }
  }

  isSubmitting.value = true;
  validationError.value = null;
  try {
    const formData = new FormData();
    formData.append('source_mode', sourceMode.value);
    
    if (sourceMode.value === 'arxiv') {
      formData.append('arxiv_id', arxivId.value.trim());
    } else if (selectedFile.value) {
      formData.append('source_file', selectedFile.value);
    }

    const newJob = await jobApi.createJob(formData);
    emit('success', newJob);
    emit('close');
  } catch (err) {
    alert('创建任务失败，请检查后端连接');
  } finally {
    isSubmitting.value = false;
  }
};

// 切换模式时清除校验错误和已选文件
const switchMode = (mode: 'upload' | 'arxiv') => {
  sourceMode.value = mode;
  validationError.value = null;
};
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-sm" @click.self="emit('close')">
    <div class="bg-white w-full max-w-lg rounded-[2.5rem] overflow-hidden animate-in fade-in zoom-in duration-300 shadow-xl">
      <!-- Header -->
      <div class="px-8 py-6 border-b border-slate-100 flex justify-between items-center bg-white">
        <h2 class="text-2xl font-black tracking-tight">新建论文任务</h2>
        <button @click="emit('close')" class="p-2 hover:bg-slate-100 rounded-full transition-colors">
          <X :size="20" />
        </button>
      </div>

      <!-- Form -->
      <div class="p-8 space-y-6">
        <!-- Mode Switcher -->
        <div class="flex p-1 bg-slate-100 rounded-2xl">
          <button @click="switchMode('upload')" 
            :class="['flex-1 py-2 text-xs font-bold rounded-xl transition-all', sourceMode === 'upload' ? 'bg-white shadow-sm text-slate-900' : 'text-slate-400']">
            文件上传
          </button>
          <button @click="switchMode('arxiv')" 
            :class="['flex-1 py-2 text-xs font-bold rounded-xl transition-all', sourceMode === 'arxiv' ? 'bg-white shadow-sm text-slate-900' : 'text-slate-400']">
            arXiv ID
          </button>
        </div>

        <!-- Arxiv ID Input -->
        <div v-if="sourceMode === 'arxiv'" class="space-y-2">
          <label class="text-[10px] font-black uppercase text-slate-400 tracking-widest ml-1">arXiv Identifier</label>
          <div class="relative">
            <Hash class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" :size="18" />
            <input v-model="arxivId" type="text" placeholder="例如: 2401.12345" 
              class="w-full pl-12 pr-4 py-4 bg-slate-50 border-2 transition-all font-medium outline-none"
              :class="validationError && sourceMode === 'arxiv' ? 'border-red-300 focus:border-red-500' : 'border-transparent focus:border-amber-500/20 focus:bg-white'"
              @input="validationError = null" />
          </div>
        </div>

        <!-- File Upload Input -->
        <div v-else class="space-y-2">
          <label class="text-[10px] font-black uppercase text-slate-400 tracking-widest ml-1">Source Package (.tar.gz)</label>
          <label class="group flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-3xl cursor-pointer transition-all"
            :class="validationError && sourceMode === 'upload' ? 'border-red-300 hover:border-red-400 bg-red-50/30' : 'border-slate-200 hover:border-amber-500/40 hover:bg-amber-50/30'">
            <div class="flex flex-col items-center justify-center pt-5 pb-6">
              <Upload class="text-slate-400 group-hover:text-amber-600 mb-3 transition-colors" :size="32" />
              <p class="text-sm font-bold text-slate-500">{{ selectedFile ? selectedFile.name : '点击或拖拽上传' }}</p>
            </div>
            <input type="file" class="hidden" @change="handleFileChange" accept=".tar.gz,.tgz" />
          </label>
        </div>

        <!-- 校验错误提示 -->
        <div v-if="validationError" class="flex items-start gap-2 p-4 bg-red-50 border border-red-100 rounded-2xl">
          <AlertCircle class="text-red-500 shrink-0 mt-0.5" :size="16" />
          <p class="text-sm font-medium text-red-700">{{ validationError }}</p>
        </div>

        <!-- Submit Button -->
        <button @click="submit" :disabled="isSubmitting"
          class="w-full py-4 bg-slate-900 text-white rounded-2xl font-black text-sm shadow-xl shadow-slate-200 hover:bg-slate-800 disabled:opacity-50 transition-all flex items-center justify-center gap-2">
          <Loader2 v-if="isSubmitting" class="animate-spin" :size="18" />
          {{ isSubmitting ? '正在创建...' : '提交任务' }}
        </button>
      </div>
    </div>
  </div>
</template>
