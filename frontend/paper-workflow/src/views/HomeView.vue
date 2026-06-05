<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { jobApi } from '../api/client';
import type { JobState } from '../types/api';
import JobCard from '../components/JobCard.vue';
import NewJobModal from '../components/NewJobModel.vue';
import SettingsModal from '../components/SettingsModal.vue';
import AuthModal from '../components/AuthModal.vue';
import UserMenu from '../components/UserMenu.vue';
import { Plus, RefreshCw, Trash2, LogIn } from 'lucide-vue-next';
import { useAuthStore } from '../stores/auth';

const authStore = useAuthStore();
const jobs = ref<JobState[]>([]);
const isRefreshing = ref(false);
const isModalOpen = ref(false);
const isAuthOpen = ref(false);
const isApiKeyOpen = ref(false);

const refresh = async () => {
  isRefreshing.value = true;
  try {
    jobs.value = await jobApi.listJobs();
  } finally {
    isRefreshing.value = false;
  }
};

const onJobCreated = (newJob: JobState) => {
  jobs.value.unshift(newJob);
};

const deleteJob = async (jobId: string) => {
  try {
    await jobApi.deleteJob(jobId);
    jobs.value = jobs.value.filter(job => job.jobId !== jobId);
  } catch (error) {
    console.error('删除任务失败:', error);
  }
};

const deleteAllJobs = async () => {
  if (!confirm('确定要删除所有任务吗？此操作不可撤销。')) {
    return;
  }
  try {
    await jobApi.deleteAllJobs();
    jobs.value = [];
  } catch (error) {
    console.error('删除所有任务失败:', error);
  }
};

const openAuthModal = () => {
  isAuthOpen.value = true;
};

const openApiKeyFromMenu = () => {
  isApiKeyOpen.value = true;
};

const onAuthChanged = () => {
  jobs.value = [];
  if (authStore.isAuthenticated) {
    refresh();
  }
};

watch(() => authStore.userId, (newUserId, oldUserId) => {
  if (newUserId !== oldUserId) {
    onAuthChanged();
  }
});

onMounted(() => {
  if (authStore.isAuthenticated) {
    refresh();
  }
});
</script>

<template>
  <div class="max-w-6xl mx-auto px-6 py-12">
    <header class="mb-12 flex justify-between items-end">
      <div>
        <div class="flex items-center gap-2 mb-4">
          <div class="w-3 h-3 rounded-full bg-amber-500 shadow-[0_0_12px_rgba(245,158,11,0.5)]"></div>
          <span class="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em]">Automated Workflow</span>
        </div>
        <h1 class="text-5xl font-black tracking-tighter text-slate-900 mb-4">
          Chat<span class="text-amber-600">HTML</span>
        </h1>
        <p class="text-slate-500 max-w-md leading-relaxed">
          从 arXiv 或本地源码一键转换论文为交互式 HTML，内置学术 AI 助手。
        </p>
      </div>

      <div class="flex gap-3">
        <template v-if="authStore.isAuthenticated">
          <button @click="refresh" class="p-4 glass-card rounded-2xl text-slate-600 hover:text-amber-600 transition-colors">
            <RefreshCw :class="{ 'animate-spin': isRefreshing }" :size="20" />
          </button>
          <button @click="deleteAllJobs" class="p-4 glass-card rounded-2xl text-slate-600 hover:text-rose-600 transition-colors">
            <Trash2 :size="20" />
          </button>
          <UserMenu :isOpen="true" @close="() => {}" @openApiKey="openApiKeyFromMenu" />
          <button @click="isModalOpen = true"
            class="flex items-center gap-2 px-6 py-4 bg-amber-600 hover:bg-amber-700 text-white rounded-2xl font-bold shadow-lg shadow-amber-200 transition-all">
            <Plus :size="20" />
            新建任务
          </button>
        </template>
        <template v-else>
          <button @click="openAuthModal"
            class="flex items-center gap-2 px-6 py-4 bg-amber-600 hover:bg-amber-700 text-white rounded-2xl font-bold shadow-lg shadow-amber-200 transition-all">
            <LogIn :size="20" />
            登录 / 注册
          </button>
        </template>
      </div>
    </header>

    <main>
      <div v-if="!authStore.isAuthenticated" class="text-center py-24 glass-card rounded-[3rem] border-dashed">
        <p class="text-slate-400 font-medium mb-4">请登录后使用论文处理功能</p>
        <button @click="openAuthModal" class="px-6 py-3 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-bold transition-colors">
          登录 / 注册
        </button>
      </div>
      <div v-else-if="jobs.length === 0" class="text-center py-24 glass-card rounded-[3rem] border-dashed">
        <p class="text-slate-400 font-medium">还没有任务，开始提交你的第一篇论文吧。</p>
      </div>
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <JobCard v-for="job in jobs" :key="job.jobId" :job="job" @delete="deleteJob" />
      </div>
    </main>

    <NewJobModal
      v-if="isModalOpen && authStore.isAuthenticated"
      @close="isModalOpen = false"
      @success="onJobCreated"
    />
    <SettingsModal
      v-if="isApiKeyOpen"
      :isOpen="isApiKeyOpen"
      @close="isApiKeyOpen = false"
    />
    <AuthModal
      v-if="isAuthOpen"
      @close="isAuthOpen = false"
    />
  </div>
</template>