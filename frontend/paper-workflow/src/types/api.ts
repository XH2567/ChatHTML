export type JobStatus =
  | 'created' | 'queued' | 'downloading' | 'validating'
  | 'extracting' | 'analyzing' | 'processing'
  | 'completed' | 'partial' | 'error';

export type SourceMode = 'upload' | 'arxiv';

export type StageStatus = 'pending' | 'running' | 'done' | 'error' | 'skipped';

export interface StageDetail {
  title: string;
  status: StageStatus;
  detail: string;
}

export interface JobState {
  jobId: string;
  userId: string | null;
  createdAt: string;
  status: JobStatus;
  sourceMode: SourceMode;
  arxivId: string | null;
  originalName: string | null;
  archiveSize: number | null;
  errors: string[];
  warnings: string[];
  durationSeconds: number | null;
  artifacts: Record<string, string>;
  sortOrder?: number;
  stageDetails: StageDetail[];
}

export interface AuthResponse {
  user_id: string;
  username: string;
  token: string;
}

export interface UserInfo {
  user_id: string;
  username: string;
}

export interface MaskedApiKey {
  has_key: boolean;
  masked: string | null;
  provider: string | null;
  model: string | null;
}

export type ApiProvider = 'deepseek' | 'openai' | 'anthropic' | 'google' | 'zhipu' | 'custom';

export const API_PROVIDERS: { value: ApiProvider; label: string }[] = [
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'anthropic', label: 'Anthropic' },
  { value: 'google', label: 'Google AI' },
  { value: 'zhipu', label: '智谱AI' },
  { value: 'custom', label: '自定义' },
];

export interface QueryHistory {
  text_excerpt: string;
  text_hash: string;
  query: string;
  reply: string;
  timestamp: string;
}