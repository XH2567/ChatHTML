import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
});

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('auth_token'));
  const userId = ref<string | null>(localStorage.getItem('auth_user_id'));
  const username = ref<string | null>(localStorage.getItem('auth_username'));
  const isLoading = ref(false);
  const error = ref<string | null>(null);

  const isAuthenticated = computed(() => !!token.value);

  const setAuth = (authToken: string, authUserId: string, authUsername: string) => {
    token.value = authToken;
    userId.value = authUserId;
    username.value = authUsername;
    localStorage.setItem('auth_token', authToken);
    localStorage.setItem('auth_user_id', authUserId);
    localStorage.setItem('auth_username', authUsername);
  };

  const clearAuth = () => {
    token.value = null;
    userId.value = null;
    username.value = null;
    localStorage.removeItem('auth_token');
    localStorage.removeItem('auth_user_id');
    localStorage.removeItem('auth_username');
  };

  const register = async (user: string, pass: string) => {
    isLoading.value = true;
    error.value = null;
    try {
      const { data } = await api.post('/auth/register', { username: user, password: pass });
      setAuth(data.token, data.user_id, data.username);
      return true;
    } catch (err: any) {
      error.value = err?.response?.data?.error || '注册失败';
      return false;
    } finally {
      isLoading.value = false;
    }
  };

  const login = async (user: string, pass: string) => {
    isLoading.value = true;
    error.value = null;
    try {
      const { data } = await api.post('/auth/login', { username: user, password: pass });
      setAuth(data.token, data.user_id, data.username);
      return true;
    } catch (err: any) {
      error.value = err?.response?.data?.error || '登录失败';
      return false;
    } finally {
      isLoading.value = false;
    }
  };

  const logout = async () => {
    if (token.value) {
      try {
        await api.post('/auth/logout', {}, {
          headers: { Authorization: `Bearer ${token.value}` }
        });
      } catch (e) {
        // ignore
      }
    }
    clearAuth();
  };

  const getApiKey = async (): Promise<{ has_key: boolean; masked: string | null; provider: string | null; model: string | null }> => {
    const { data } = await api.get('/auth/api-key', {
      headers: { Authorization: `Bearer ${token.value}` }
    });
    return data;
  };

  const setApiKey = async (apiKey: string, provider: string, model: string): Promise<boolean> => {
    try {
      await api.post('/auth/api-key', { api_key: apiKey, provider, model }, {
        headers: { Authorization: `Bearer ${token.value}` }
      });
      return true;
    } catch (err: any) {
      error.value = err?.response?.data?.error || '保存API密钥失败';
      return false;
    }
  };

  const deleteApiKey = async (): Promise<boolean> => {
    try {
      await api.delete('/auth/api-key', {
        headers: { Authorization: `Bearer ${token.value}` }
      });
      return true;
    } catch (err: any) {
      error.value = err?.response?.data?.error || '删除API密钥失败';
      return false;
    }
  };

  return {
    token,
    userId,
    username,
    isLoading,
    error,
    isAuthenticated,
    register,
    login,
    logout,
    getApiKey,
    setApiKey,
    deleteApiKey,
  };
});