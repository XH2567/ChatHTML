import axios from 'axios';
import type { JobState } from '../types/api';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      localStorage.removeItem('auth_user_id');
      localStorage.removeItem('auth_username');
      if (window.location.pathname !== '/') {
        window.location.href = '/';
      }
    }
    return Promise.reject(error);
  }
);

export const jobApi = {
  async listJobs(): Promise<JobState[]> {
    const { data } = await api.get<JobState[]>('/jobs');
    return data;
  },

  async getJob(id: string): Promise<JobState> {
    const { data } = await api.get<JobState>(`/jobs/${id}`);
    return data;
  },

  async createJob(formData: FormData): Promise<JobState> {
    const { data } = await api.post<JobState>('/jobs', formData);
    return data;
  },

  async deleteJob(id: string): Promise<void> {
    await api.delete(`/jobs/${id}`);
  },

  async deleteAllJobs(): Promise<void> {
    await api.delete('/jobs');
  },

  async askAi(payload: {
    query: string;
    context: string;
    full_paper: string;
  }): Promise<{ reply: string }> {
    const { data } = await api.post('/chat', payload);
    return data;
  }
};

export const authApi = {
  register(username: string, password: string) {
    return api.post('/auth/register', { username, password });
  },
  login(username: string, password: string) {
    return api.post('/auth/login', { username, password });
  },
  logout() {
    return api.post('/auth/logout');
  },
  getMe() {
    return api.get('/auth/me');
  },
  getApiKey() {
    return api.get('/auth/api-key');
  },
  setApiKey(apiKey: string, provider?: string, model?: string) {
    return api.post('/auth/api-key', { api_key: apiKey, provider, model });
  },
  deleteApiKey() {
    return api.delete('/auth/api-key');
  },
};