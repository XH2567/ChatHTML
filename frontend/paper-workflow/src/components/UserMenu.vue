<script setup lang="ts">
import { ref } from 'vue';
import { LogOut, Key, ChevronDown, User } from 'lucide-vue-next';
import { useAuthStore } from '../stores/auth';
import { useRouter } from 'vue-router';

const props = defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  close: [];
  openApiKey: [];
}>();

const authStore = useAuthStore();
const router = useRouter();
const showDropdown = ref(false);

const toggleDropdown = () => {
  showDropdown.value = !showDropdown.value;
};

const handleLogout = async () => {
  showDropdown.value = false;
  await authStore.logout();
  router.push('/');
};

const openApiKeySettings = () => {
  showDropdown.value = false;
  emit('openApiKey');
};
</script>

<template>
  <div class="relative">
    <button
      @click="toggleDropdown"
      class="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
    >
      <div class="w-6 h-6 bg-amber-100 rounded-full flex items-center justify-center">
        <User class="text-amber-600" :size="14" />
      </div>
      <span>{{ authStore.username }}</span>
      <ChevronDown :size="14" :class="{ 'rotate-180': showDropdown }" class="transition-transform" />
    </button>

    <div
      v-if="showDropdown"
      class="absolute right-0 mt-2 w-48 bg-white rounded-xl shadow-lg border border-slate-200 py-1 z-50"
    >
      <button
        @click="openApiKeySettings"
        class="w-full px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 flex items-center gap-2 transition-colors"
      >
        <Key :size="14" />
        API 密钥设置
      </button>
      <button
        @click="handleLogout"
        class="w-full px-4 py-2 text-sm text-rose-600 hover:bg-rose-50 flex items-center gap-2 transition-colors"
      >
        <LogOut :size="14" />
        退出登录
      </button>
    </div>
  </div>
</template>