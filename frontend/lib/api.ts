export type TaskType = "image_processing" | "web_scraping" | "bulk_invoice";
export type JobStatus = "QUEUED" | "PROCESSING" | "SUCCESS" | "FAILED";

export type JobPayload = Record<string, unknown>;

export type JobCreateRequest = {
  task_type: TaskType;
  payload: JobPayload;
};

export type JobCreateResponse = {
  job_id: string;
  status: "QUEUED";
  message: string;
};

export type ImageResult = {
  image_b64: string;
  format: string;
  original_size: [number, number];
  final_size: [number, number];
  mode: string;
  operations_applied: string[];
};

export type ScrapingResult = {
  url: string;
  scraped: Record<string, string[]>;
};

export type InvoiceResult = {
  pdf_b64: string;
  filename: string;
  total: number;
  items_count: number;
  email: string;
};

export type TaskResult = ImageResult | ScrapingResult | InvoiceResult;

export type TrackedJobSeed = {
  job_id: string;
  task_type: TaskType;
};

export type JobResponse = {
  job_id: string;
  task_type: TaskType;
  status: JobStatus;
  retry_count: number;
  created_at: string;
  updated_at: string;
  worker_id: string | null;
  error_msg: string | null;
  result: TaskResult | null;
};

export type DashboardStats = {
  queue_depth: number;
  jobs_by_status: {
    QUEUED: number;
    PROCESSING: number;
    SUCCESS: number;
    FAILED: number;
  };
  dlq_count: number;
  avg_processing_time_ms: number;
  jobs_last_hour: number;
};

export const TASK_TYPES: TaskType[] = [
  "image_processing",
  "web_scraping",
  "bulk_invoice",
];

export type BackendReadyOptions = {
  timeoutMs?: number;
};

export const DEMO_PAYLOADS: Record<TaskType, JobPayload> = {
  image_processing: {
    image_url: "https://picsum.photos/800/600",
    operations: ["resize", "grayscale"],
  },
  web_scraping: {
    url: "https://example.com",
    selectors: ["h1", "p"],
  },
  bulk_invoice: {
    customer_id: "DEMO-001",
    line_items: [{ name: "Widget", qty: 2, unit_price: 49.99 }],
    email: "demo@example.com",
  },
};

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function buildDemoJob(taskType: TaskType): JobCreateRequest {
  return {
    task_type: taskType,
    payload: DEMO_PAYLOADS[taskType],
  };
}

export function getRandomTaskType(): TaskType {
  return TASK_TYPES[Math.floor(Math.random() * TASK_TYPES.length)];
}

export async function createJob(
  taskType: TaskType,
  payload: JobPayload,
): Promise<JobCreateResponse> {
  return request<JobCreateResponse>("/api/jobs", {
    method: "POST",
    body: JSON.stringify({
      task_type: taskType,
      payload,
    }),
  });
}

export async function getJob(jobId: string): Promise<JobResponse> {
  return request<JobResponse>(`/api/jobs/${jobId}`);
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return request<DashboardStats>("/api/dashboard-stats");
}

export async function checkBackendReady(
  options: BackendReadyOptions = {},
): Promise<DashboardStats> {
  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? 12000,
  );

  try {
    return await request<DashboardStats>("/api/dashboard-stats", {
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timeout);
  }
}
