import axios from 'axios';
import type { JobState } from '../types/api';

const api = axios.create({
  baseURL: 'http://127.0.0.1:8000/api',
});

export const jobApi = {
  // 获取任务列表
  async listJobs(): Promise<JobState[]> {
    const { data } = await api.get<JobState[]>('/jobs');
    return data;
  },
  
  // 获取单个任务详情（用于轮询）
  async getJob(id: string): Promise<JobState> {
    const { data } = await api.get<JobState>(`/jobs/${id}`);
    return data;
  },

  // 创建任务
  async createJob(formData: FormData): Promise<JobState> {
    const { data } = await api.post<JobState>('/jobs', formData);
    return data;
  },

  // 删除单个任务
  async deleteJob(id: string): Promise<void> {
    await api.delete(`/jobs/${id}`);
  },

  // 删除所有任务
  async deleteAllJobs(): Promise<void> {
    await api.delete('/jobs');
  },

  // 统一管理 AI 聊天请求
  async askAi(payload: {
    query: string;
    context: string;
    model: string;
    apiKey: string;
    full_paper: string;
  }): Promise<{ reply: string }> {
    const { data } = await api.post('/chat', payload);
    return data;
  }
};