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
  jobId: string;        // 对应 Rust 的 job_id (camelCase)
  createdAt: string;    // ISO 8601 字符串
  status: JobStatus;
  sourceMode: SourceMode;
  arxivId: string | null;
  originalName: string | null;
  archiveSize: number | null;
  errors: string[];
  warnings: string[];
  durationSeconds: number | null;
  artifacts: Record<string, string>;
  stageDetails: StageDetail[];
}