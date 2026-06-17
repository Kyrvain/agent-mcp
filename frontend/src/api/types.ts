export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed'
export type CrawlMode = 'search' | 'direct' | 'batch'

export interface CrawlJobRequest {
  product_name: string
  url?: string | null
  search?: boolean | null
  list_only?: boolean
  proofread?: boolean
  batch_proofread?: boolean
  refresh_catalog?: boolean
  batch_limit?: number | null
  batch_concurrency?: number | null
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

export interface BatchSummary {
  catalog_count?: number
  processed_count?: number
  succeeded_count?: number
  failed_count?: number
  concurrency?: number
  cache_path?: string
  loaded_from_cache?: boolean
  refreshed_catalog?: boolean
  generated_at?: string | null
  warnings?: string[]
}

export interface BatchProductResult extends ProductFeatures {
  id?: string
  client_name?: string
  detail_url?: string
  status?: string
  error?: string
}

export interface BatchAgentResponse {
  batch?: BatchSummary
  products?: BatchProductResult[]
}
