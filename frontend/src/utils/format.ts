import type { JobStatus } from '../api/types'

export function prettyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2)
}

export function formatDate(value: string | null | undefined) {
  if (!value) {
    return '-'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

export function statusType(status: JobStatus) {
  if (status === 'succeeded') {
    return 'success'
  }
  if (status === 'failed') {
    return 'danger'
  }
  if (status === 'running') {
    return 'warning'
  }
  return 'info'
}

export function statusText(status: JobStatus) {
  const map: Record<JobStatus, string> = {
    queued: '排队中',
    running: '运行中',
    succeeded: '已完成',
    failed: '失败',
  }
  return map[status]
}
