import type { CrawlJobRequest, CrawlJobResponse, RunSummary } from './types'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      detail = await response.text()
    }
    throw new Error(detail || `Request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}

export function createCrawlJob(payload: CrawlJobRequest) {
  return request<CrawlJobResponse>('/api/crawl-jobs', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getCrawlJob(id: string) {
  return request<CrawlJobResponse>(`/api/crawl-jobs/${id}`)
}

export function listRuns() {
  return request<RunSummary[]>('/api/runs')
}

export function getRunResult(id: string) {
  return request<Record<string, unknown>>(`/api/runs/${id}/result`)
}

export function getRunAgentResponse(id: string) {
  return request<Record<string, unknown>>(`/api/runs/${id}/agent-response`)
}

export async function getRunFeatures(id: string) {
  const response = await fetch(`/api/runs/${id}/features`)
  if (!response.ok) {
    throw new Error(response.statusText || `Request failed: ${response.status}`)
  }
  return response.text()
}

export function screenshotUrl(id: string) {
  return `/api/runs/${id}/screenshot`
}
