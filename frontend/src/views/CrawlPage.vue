<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">爬取任务</h1>
        <p class="page-description">提交产品名、详情 URL 或批量任务，后台执行爬取、功能提取和可选校对。</p>
      </div>
      <el-button
        :icon="Refresh"
        :loading="restoringHistory"
        @click="refreshCurrentJob"
      >
        刷新任务
      </el-button>
    </header>

    <div class="page-body">
      <div class="workflow-stack">
        <section class="panel">
          <div class="panel-header">
            <h2 class="panel-title">任务参数</h2>
          </div>
          <div class="panel-body">
            <el-form label-position="top" :model="form">
              <el-form-item label="模式">
                <el-segmented
                  v-model="form.mode"
                  :options="[
                    { label: '产品名搜索', value: 'search' },
                    { label: '直连 URL', value: 'direct' },
                    { label: '批量爬取', value: 'batch' },
                  ]"
                />
              </el-form-item>

              <el-form-item v-if="form.mode !== 'batch'" label="产品名称">
                <el-input v-model="form.productName" clearable />
              </el-form-item>

              <el-form-item v-if="form.mode === 'direct'" label="详情页 URL">
                <el-input v-model="form.url" clearable />
              </el-form-item>

              <div class="meta-grid">
                <el-form-item label="等待时间 ms">
                  <el-input-number
                    v-model="form.waitMs"
                    :min="0"
                    :step="500"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item v-if="form.mode === 'search'" label="匹配阈值">
                  <el-input-number
                    v-model="form.confidence"
                    :min="0"
                    :max="1"
                    :step="0.05"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item v-if="form.mode === 'batch'" label="并发数">
                  <el-input-number
                    v-model="form.batchConcurrency"
                    :min="1"
                    :step="1"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
                <el-form-item v-if="form.mode === 'batch'" label="处理上限">
                  <el-input-number
                    v-model="form.batchLimit"
                    :min="1"
                    :step="1"
                    :value-on-clear="null"
                    clearable
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
              </div>

              <el-form-item>
                <el-checkbox v-if="form.mode !== 'batch'" v-model="form.proofread">
                  启用校对
                </el-checkbox>
                <el-checkbox v-else v-model="form.refreshCatalog">
                  刷新目录缓存
                </el-checkbox>
                <el-checkbox v-model="form.headed">
                  显示浏览器
                </el-checkbox>
              </el-form-item>
              <el-alert
                class="form-hint"
                type="info"
                :closable="false"
                :title="form.headed ? '将强制使用有界面浏览器运行。' : '将强制使用 headless 模式运行；部分站点可能返回空白页。'"
              />

              <el-button
                type="primary"
                :icon="VideoPlay"
                :loading="submitting"
                @click="submitJob"
              >
                {{ form.mode === 'batch' ? '启动批量任务' : '启动任务' }}
              </el-button>
            </el-form>
          </div>
        </section>

        <section class="panel">
            <div class="panel-header">
              <h2 class="panel-title">任务状态</h2>
              <el-tag v-if="currentJob" :type="statusType(currentJob.status)">
                {{ statusText(currentJob.status) }}
              </el-tag>
            </div>
            <div class="panel-body">
              <template v-if="currentJob">
                <div class="meta-grid">
                  <div class="meta-item">
                    <div class="meta-label">任务 ID</div>
                    <div class="meta-value">{{ currentJob.id }}</div>
                  </div>
                  <div class="meta-item">
                    <div class="meta-label">输出目录</div>
                    <div class="meta-value">{{ currentJob.output_dir || '-' }}</div>
                  </div>
                  <div class="meta-item">
                    <div class="meta-label">创建时间</div>
                    <div class="meta-value">{{ formatDate(currentJob.created_at) }}</div>
                  </div>
                  <div class="meta-item">
                    <div class="meta-label">结束时间</div>
                    <div class="meta-value">{{ formatDate(currentJob.finished_at) }}</div>
                  </div>
                </div>
                <el-alert
                  v-if="currentJob.error"
                  class="job-error"
                  type="error"
                  :title="currentJob.error"
                  :closable="false"
                />
              </template>
              <div v-else class="empty-state">
                {{ restoringHistory ? '正在恢复历史结果' : '尚未提交任务' }}
              </div>
            </div>
        </section>

        <section v-if="batchResponse" class="panel">
            <div class="panel-header">
              <h2 class="panel-title">批量结果</h2>
              <el-tag :type="batchSummary.failed_count ? 'danger' : 'success'">
                {{ batchSummary.succeeded_count || 0 }} / {{ batchSummary.processed_count || 0 }}
              </el-tag>
            </div>
            <div class="panel-body">
              <div class="stack">
                <div class="meta-grid">
                  <div class="meta-item">
                    <div class="meta-label">目录产品</div>
                    <div class="meta-value">{{ batchSummary.catalog_count ?? 0 }}</div>
                  </div>
                  <div class="meta-item">
                    <div class="meta-label">本次处理</div>
                    <div class="meta-value">{{ batchSummary.processed_count ?? 0 }}</div>
                  </div>
                  <div class="meta-item">
                    <div class="meta-label">成功</div>
                    <div class="meta-value">{{ batchSummary.succeeded_count ?? 0 }}</div>
                  </div>
                  <div class="meta-item">
                    <div class="meta-label">失败</div>
                    <div class="meta-value">{{ batchSummary.failed_count ?? 0 }}</div>
                  </div>
                  <div class="meta-item">
                    <div class="meta-label">并发数</div>
                    <div class="meta-value">{{ batchSummary.concurrency ?? '-' }}</div>
                  </div>
                  <div class="meta-item">
                    <div class="meta-label">目录缓存</div>
                    <div class="meta-value">{{ batchSummary.cache_path || '-' }}</div>
                  </div>
                </div>

                <el-alert
                  v-if="batchWarnings.length"
                  type="warning"
                  :title="batchWarnings.join('；')"
                  :closable="false"
                />

                <div class="toolbar batch-actions">
                  <el-button
                    type="primary"
                    plain
                    :icon="View"
                    :disabled="!batchProducts.length"
                    @click="showAllBatchProofreading"
                  >
                    批量查看校对
                  </el-button>
                  <el-button
                    plain
                    :icon="Hide"
                    :disabled="!expandedBatchProductKeys.length"
                    @click="closeAllBatchProofreading"
                  >
                    关闭查看校对
                  </el-button>
                </div>

                <el-table
                  class="batch-table"
                  :data="batchProducts"
                  border
                  size="small"
                  empty-text="暂无产品结果"
                  :row-key="batchTableRowKey"
                  :expand-row-keys="expandedBatchProductKeys"
                  @expand-change="handleBatchExpandChange"
                >
                  <el-table-column type="expand" width="52">
                    <template #default="{ row }">
                      <div class="batch-proofreading-detail">
                        <el-alert
                          v-if="row.error"
                          type="error"
                          :title="row.error"
                          :closable="false"
                        />
                        <el-alert
                          v-else-if="row.proofreading?.error"
                          type="error"
                          :title="row.proofreading.error"
                          :closable="false"
                        />
                        <div v-else-if="batchCorrectedText(row)" class="diff-grid">
                          <div class="diff-column">
                            <div class="diff-title">源文本</div>
                            <p class="diff-text compact-diff-text">
                              <span
                                v-for="(segment, index) in batchSourceSegments(row)"
                                :key="`batch-source-${batchProductKey(row)}-${index}`"
                                :class="`diff-${segment.kind}`"
                              >
                                {{ segment.text }}
                              </span>
                            </p>
                          </div>
                          <div class="diff-column">
                            <div class="diff-title">校对后文本</div>
                            <p class="diff-text compact-diff-text">
                              <span
                                v-for="(segment, index) in batchCorrectedSegments(row)"
                                :key="`batch-corrected-${batchProductKey(row)}-${index}`"
                                :class="`diff-${segment.kind}`"
                              >
                                {{ segment.text }}
                              </span>
                            </p>
                          </div>
                        </div>
                        <div v-else class="diff-grid">
                          <div class="diff-column">
                            <div class="diff-title">源文本</div>
                            <p class="diff-text compact-diff-text">
                              {{ batchSourceText(row) || '未提取到功能文本' }}
                            </p>
                          </div>
                          <div class="diff-column">
                            <div class="diff-title">校对后文本</div>
                            <div class="empty-state">校对服务未返回 corrected 文本</div>
                          </div>
                        </div>
                      </div>
                    </template>
                  </el-table-column>
                  <el-table-column prop="product_name" label="产品" min-width="180" />
                  <el-table-column prop="client_name" label="厂商" min-width="140" />
                  <el-table-column label="状态" width="120">
                    <template #default="{ row }">
                      <el-tag :type="batchProductStatusType(row.status)" size="small">
                        {{ batchProductStatusText(row.status) }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="功能数" width="90">
                    <template #default="{ row }">
                      {{ row.features?.length ?? 0 }}
                    </template>
                  </el-table-column>
                  <el-table-column label="校对" width="100">
                    <template #default="{ row }">
                      <el-tag :type="batchProofreadingStatusType(row)" size="small">
                        {{ batchProofreadingStatusText(row) }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column label="链接" min-width="110">
                    <template #default="{ row }">
                      <el-link
                        v-if="row.detail_url"
                        :href="row.detail_url"
                        target="_blank"
                        type="primary"
                      >
                        详情页
                      </el-link>
                      <span v-else>-</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="操作" width="150" fixed="right">
                    <template #default="{ row }">
                      <el-button
                        type="primary"
                        link
                        :icon="isBatchProductExpanded(row) ? Hide : View"
                        @click.stop="toggleBatchProofreading(row)"
                      >
                        {{ isBatchProductExpanded(row) ? '关闭查看校对' : '查看校对' }}
                      </el-button>
                    </template>
                  </el-table-column>
                  <el-table-column prop="error" label="错误" min-width="180" show-overflow-tooltip />
                </el-table>
              </div>
            </div>
        </section>

        <section v-else-if="!shouldShowProofreading" class="panel">
            <div class="panel-header">
              <h2 class="panel-title">提取结果</h2>
            </div>
            <div class="panel-body">
              <template v-if="features">
                <div class="stack">
                  <div>
                    <strong>{{ features.product_name || '未命名产品' }}</strong>
                    <p v-if="displaySummary" class="page-description">{{ displaySummary }}</p>
                  </div>
                  <ol class="result-list">
                    <li v-for="item in displayFeatures" :key="item">{{ item }}</li>
                  </ol>
                </div>
              </template>
              <div v-else class="empty-state">任务完成后显示提取出的产品功能</div>
            </div>
        </section>

        <section v-else class="panel">
            <div class="panel-header">
              <h2 class="panel-title">校对对比</h2>
              <el-tag v-if="proofreading?.correct" :type="proofreadingChanged ? 'warning' : 'success'">
                {{ proofreadingChanged ? '有改动' : '无改动' }}
              </el-tag>
            </div>
            <div class="panel-body">
              <template v-if="proofreading">
                <el-alert
                  v-if="proofreading.error"
                  type="error"
                  :title="proofreading.error"
                  :closable="false"
                />
                <div v-else-if="correctedText" class="diff-grid">
                  <div class="diff-column">
                    <div class="diff-title">源文本</div>
                    <p class="diff-text">
                      <span
                        v-for="(segment, index) in sourceSegments"
                        :key="`source-${index}`"
                        :class="`diff-${segment.kind}`"
                      >
                        {{ segment.text }}
                      </span>
                    </p>
                  </div>
                  <div class="diff-column">
                    <div class="diff-title">校对后文本</div>
                    <p class="diff-text">
                      <span
                        v-for="(segment, index) in correctedSegments"
                        :key="`corrected-${index}`"
                        :class="`diff-${segment.kind}`"
                      >
                        {{ segment.text }}
                      </span>
                    </p>
                  </div>
                </div>
                <div v-else class="empty-state">校对服务未返回 corrected 文本</div>
              </template>
              <div v-else class="empty-state">启用校对后显示源文本与校对后文本</div>
            </div>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Hide, Refresh, VideoPlay, View } from '@element-plus/icons-vue'
import { createCrawlJob, getCrawlJob, getLatestRunForMode } from '../api/client'
import type {
  BatchAgentResponse,
  BatchProductResult,
  BatchSummary,
  CrawlMode,
  CrawlJobResponse,
  ProductFeatures,
} from '../api/types'
import { formatDate, statusText, statusType } from '../utils/format'
import {
  buildProofreadSourceText,
  correctedDiffSegments,
  diffText,
  sourceDiffSegments,
  stripFeatureNumber,
} from '../utils/text'

const STORAGE_PREFIX = 'agent-mcp-cdp:crawl'
const ACTIVE_MODE_KEY = `${STORAGE_PREFIX}:active-mode`
const RUNNING_JOB_KEY_PREFIX = `${STORAGE_PREFIX}:running-job:`
const CRAWL_MODES: CrawlMode[] = ['search', 'direct', 'batch']

const form = reactive({
  mode: readActiveMode(),
  productName: '超星泛雅智慧课程平台',
  url: '',
  waitMs: 5000,
  confidence: 0.3,
  proofread: false,
  headed: true,
  refreshCatalog: false,
  batchConcurrency: 3,
  batchLimit: null as number | null,
})

const submitting = ref(false)
const currentJob = ref<CrawlJobResponse | null>(null)
const expandedBatchProductKeys = ref<string[]>([])
const restoringHistory = ref(false)
let timer: number | undefined

const agentResponse = computed(() => currentJob.value?.agent_response ?? null)

const batchResponse = computed<BatchAgentResponse | null>(() => {
  const value = agentResponse.value
  if (!value || (!('batch' in value) && !('products' in value))) {
    return null
  }
  return value as BatchAgentResponse
})

const batchSummary = computed<BatchSummary>(() => batchResponse.value?.batch ?? {})

const batchProducts = computed<BatchProductResult[]>(() => {
  return batchResponse.value?.products ?? []
})

const batchWarnings = computed(() => batchSummary.value.warnings ?? [])

const features = computed<ProductFeatures | null>(() => {
  const agentResponse = currentJob.value?.agent_response
  if (batchResponse.value) {
    return null
  }
  if (!agentResponse) {
    return null
  }
  return agentResponse as ProductFeatures
})

const displaySummary = computed(() => {
  const summary = features.value?.summary?.trim()
  if (!summary || looksLikeJsonPayload(summary)) {
    return ''
  }
  return summary
})

const rawFeatures = computed(() => features.value?.features ?? [])

const displayFeatures = computed(() => rawFeatures.value.map(stripFeatureNumber).filter(Boolean))

const proofreading = computed(() => features.value?.proofreading ?? null)

const shouldShowProofreading = computed(() => Boolean(proofreading.value))

const sourceText = computed(() => buildProofreadSourceText(rawFeatures.value))

const correctedText = computed(() => proofreading.value?.correct?.trim() ?? '')

const diffSegments = computed(() => diffText(sourceText.value, correctedText.value))

const sourceSegments = computed(() => sourceDiffSegments(diffSegments.value))

const correctedSegments = computed(() => correctedDiffSegments(diffSegments.value))

const proofreadingChanged = computed(() => {
  return Boolean(correctedText.value) && sourceText.value !== correctedText.value
})

function looksLikeJsonPayload(value: string) {
  return (
    value.startsWith('{') ||
    value.startsWith('",') ||
    value.includes('"_source"') ||
    value.includes('"meta_group"') ||
    value.includes('\\"field\\"') ||
    value.includes('"icon_file"')
  )
}

async function submitJob() {
  if (form.mode !== 'batch' && !form.productName.trim()) {
    ElMessage.warning('请填写产品名称')
    return
  }
  if (form.mode === 'direct' && !form.url.trim()) {
    ElMessage.warning('请填写详情页 URL')
    return
  }

  submitting.value = true
  const jobMode = form.mode
  try {
    const isBatch = jobMode === 'batch'
    const job = await createCrawlJob({
      product_name: form.productName.trim() || '批量产品目录',
      url: jobMode === 'direct' ? form.url.trim() : null,
      search: jobMode === 'search',
      proofread: isBatch ? true : form.proofread,
      batch_proofread: isBatch,
      refresh_catalog: isBatch ? form.refreshCatalog : false,
      batch_concurrency: isBatch ? form.batchConcurrency : null,
      batch_limit: isBatch ? form.batchLimit : null,
      headed: form.headed,
      wait_ms: form.waitMs,
      confidence: form.confidence,
    })
    writeActiveMode(jobMode)
    writeRunningJobId(jobMode, job.id)
    if (form.mode === jobMode) {
      currentJob.value = job
    }
    ElMessage.success('任务已创建')
    if (form.mode === jobMode) {
      startPolling(job.id)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '创建任务失败')
  } finally {
    submitting.value = false
  }
}

function isCrawlMode(value: unknown): value is CrawlMode {
  return typeof value === 'string' && CRAWL_MODES.includes(value as CrawlMode)
}

function readActiveMode(): CrawlMode {
  if (typeof window === 'undefined') {
    return 'search'
  }
  const value = window.localStorage.getItem(ACTIVE_MODE_KEY)
  return isCrawlMode(value) ? value : 'search'
}

function writeActiveMode(mode: CrawlMode) {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(ACTIVE_MODE_KEY, mode)
}

function runningJobKey(mode: CrawlMode) {
  return `${RUNNING_JOB_KEY_PREFIX}${mode}`
}

function readRunningJobId(mode: CrawlMode): string | null {
  if (typeof window === 'undefined') {
    return null
  }
  return window.localStorage.getItem(runningJobKey(mode))
}

function writeRunningJobId(mode: CrawlMode, jobId: string) {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.setItem(runningJobKey(mode), jobId)
}

function clearRunningJobId(mode: CrawlMode) {
  if (typeof window === 'undefined') {
    return
  }
  window.localStorage.removeItem(runningJobKey(mode))
}

function isRunningJob(job: CrawlJobResponse | null): job is CrawlJobResponse {
  return job?.status === 'queued' || job?.status === 'running'
}

function batchProductStatusType(status: string | undefined) {
  if (status === 'succeeded') {
    return 'success'
  }
  if (status === 'proofreading_failed') {
    return 'warning'
  }
  if (status === 'failed') {
    return 'danger'
  }
  return 'info'
}

function batchProductStatusText(status: string | undefined) {
  const map: Record<string, string> = {
    succeeded: '成功',
    proofreading_failed: '校对失败',
    failed: '失败',
    pending: '等待中',
  }
  return map[status || ''] || status || '-'
}

function batchProductKey(row: BatchProductResult) {
  return row.id || row.detail_url || row.product_name || ''
}

function batchTableRowKey(row: BatchProductResult) {
  return batchProductKey(row)
}

function isBatchProductExpanded(row: BatchProductResult) {
  return expandedBatchProductKeys.value.includes(batchProductKey(row))
}

function toggleBatchProofreading(row: BatchProductResult) {
  const key = batchProductKey(row)
  if (!key) {
    return
  }
  if (expandedBatchProductKeys.value.includes(key)) {
    expandedBatchProductKeys.value = expandedBatchProductKeys.value.filter((item) => item !== key)
    return
  }
  expandedBatchProductKeys.value = [...expandedBatchProductKeys.value, key]
}

function showAllBatchProofreading() {
  expandedBatchProductKeys.value = batchProducts.value
    .map(batchProductKey)
    .filter(Boolean)
}

function closeAllBatchProofreading() {
  expandedBatchProductKeys.value = []
}

function handleBatchExpandChange(
  _row: BatchProductResult,
  expandedRows: BatchProductResult[],
) {
  expandedBatchProductKeys.value = expandedRows.map(batchProductKey).filter(Boolean)
}

function batchProofreadingStatusType(row: BatchProductResult) {
  if (row.error || row.proofreading?.error) {
    return 'danger'
  }
  if (!batchCorrectedText(row)) {
    return 'info'
  }
  return batchProofreadingChanged(row) ? 'warning' : 'success'
}

function batchProofreadingStatusText(row: BatchProductResult) {
  if (row.error || row.proofreading?.error) {
    return '失败'
  }
  if (!batchCorrectedText(row)) {
    return '未返回'
  }
  return batchProofreadingChanged(row) ? '有改动' : '无改动'
}

function batchSourceText(row: BatchProductResult) {
  return buildProofreadSourceText(row.features ?? [])
}

function batchCorrectedText(row: BatchProductResult) {
  return row.proofreading?.correct?.trim() ?? ''
}

function batchDiffSegments(row: BatchProductResult) {
  return diffText(batchSourceText(row), batchCorrectedText(row))
}

function batchSourceSegments(row: BatchProductResult) {
  return sourceDiffSegments(batchDiffSegments(row))
}

function batchCorrectedSegments(row: BatchProductResult) {
  return correctedDiffSegments(batchDiffSegments(row))
}

function batchProofreadingChanged(row: BatchProductResult) {
  return Boolean(batchCorrectedText(row)) && batchSourceText(row) !== batchCorrectedText(row)
}

watch(
  batchProducts,
  (products) => {
    if (!products.length) {
      expandedBatchProductKeys.value = []
      return
    }
    const availableKeys = new Set(products.map(batchProductKey))
    expandedBatchProductKeys.value = expandedBatchProductKeys.value.filter((key) => {
      return availableKeys.has(key)
    })
  },
  { immediate: true },
)

watch(
  () => form.mode,
  (mode) => {
    writeActiveMode(mode)
    stopPolling()
    expandedBatchProductKeys.value = []
    void restoreModeResult(mode)
  },
)

async function refreshCurrentJob() {
  if (!currentJob.value || isHistoricalJob(currentJob.value)) {
    await restoreModeResult(form.mode)
    return
  }
  await loadJob(currentJob.value.id)
}

function isHistoricalJob(job: CrawlJobResponse) {
  return job.id.startsWith('run:')
}

async function loadJob(id: string) {
  try {
    currentJob.value = await getCrawlJob(id)
    if (currentJob.value.status === 'succeeded' || currentJob.value.status === 'failed') {
      clearRunningJobId(form.mode)
      stopPolling()
    }
  } catch (error) {
    stopPolling()
    clearRunningJobId(form.mode)
    await restoreModeResult(form.mode, { silent: true })
    if (currentJob.value === null) {
      ElMessage.error(error instanceof Error ? error.message : '刷新任务失败')
    }
  }
}

async function restoreModeResult(
  mode: CrawlMode,
  options: { silent?: boolean } = {},
) {
  restoringHistory.value = true
  try {
    const runningJobId = readRunningJobId(mode)
    if (runningJobId) {
      try {
        const job = await getCrawlJob(runningJobId)
        if (form.mode !== mode) {
          return
        }
        currentJob.value = job
        if (isRunningJob(job)) {
          startPolling(job.id)
        } else {
          clearRunningJobId(mode)
        }
        return
      } catch {
        clearRunningJobId(mode)
      }
    }

    const historicalJob = await getLatestRunForMode(mode)
    if (form.mode === mode) {
      currentJob.value = historicalJob
    }
  } catch (error) {
    if (!options.silent) {
      ElMessage.error(error instanceof Error ? error.message : '恢复历史结果失败')
    }
  } finally {
    restoringHistory.value = false
  }
}

function startPolling(id: string) {
  stopPolling()
  timer = window.setInterval(() => {
    void loadJob(id)
  }, 1500)
}

function stopPolling() {
  if (timer !== undefined) {
    window.clearInterval(timer)
    timer = undefined
  }
}

onMounted(() => {
  writeActiveMode(form.mode)
  void restoreModeResult(form.mode)
})

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.job-error {
  margin-top: 14px;
}

.form-hint {
  margin: -4px 0 16px;
}

.workflow-stack {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.batch-actions {
  justify-content: flex-end;
}

:deep(.batch-table .el-table__expanded-cell) {
  padding: 0;
  background: #fbfdff;
}

.batch-proofreading-detail {
  padding: 14px 18px 18px 52px;
}

.diff-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.diff-column {
  min-width: 0;
}

.diff-title {
  margin-bottom: 8px;
  color: #41506a;
  font-size: 13px;
  font-weight: 700;
}

.diff-text {
  overflow: auto;
  max-height: 420px;
  min-height: 180px;
  margin: 0;
  padding: 12px;
  border: 1px solid #dce3ee;
  border-radius: 8px;
  background: #f8fafc;
  color: #263244;
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
}

.compact-diff-text {
  max-height: 260px;
  min-height: 120px;
}

.diff-delete {
  border-radius: 3px;
  background: #fee2e2;
  color: #991b1b;
  text-decoration: line-through;
}

.diff-insert {
  border-radius: 3px;
  background: #dcfce7;
  color: #166534;
}

@media (max-width: 980px) {
  .diff-grid {
    grid-template-columns: 1fr;
  }
}
</style>
