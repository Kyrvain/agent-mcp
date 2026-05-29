export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface CrawlJobRequest {
  product_name: string
  url?: string | null
  search?: boolean | null
  list_only?: boolean
  proofread?: boolean
  cdp_url?: string | null
  browser_executable?: string | null
  headed?: boolean | null
  wait_ms?: number | null
  confidence?: number | null
}

export interface CrawlJobResponse {
  id: string
  status: JobStatus
  request: CrawlJobRequest
  created_at: string
  started_at: string | null
  finished_at: string | null
  output_dir: string | null
  error: string | null
  result: Record<string, unknown> | null
  agent_response: Record<string, unknown> | null
}

export interface RunSummary {
  id: string
  path: string
  updated_at: string
  has_result: boolean
  has_agent_response: boolean
  has_features: boolean
  has_screenshot: boolean
}

export interface ProductFeatures {
  product_name?: string
  summary?: string
  features?: string[]
  evidence?: string[]
  warnings?: string[]
  proofreading?: ProofreadingPayload
}

export interface ProofreadingPayload {
  service_url?: string | null
  correct?: string | null
  result?: unknown
  raw_response?: string | null
  error?: string | null
}
