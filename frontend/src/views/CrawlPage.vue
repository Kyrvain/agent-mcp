<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">爬取任务</h1>
        <p class="page-description">提交产品名或详情 URL，后台执行爬取、功能提取和可选校对。</p>
      </div>
      <el-button :icon="Refresh" @click="refreshCurrentJob" :disabled="!currentJob">
        刷新任务
      </el-button>
    </header>

    <div class="page-body">
      <div class="two-column">
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
                  ]"
                />
              </el-form-item>

              <el-form-item label="产品名称">
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
                <el-form-item label="匹配阈值">
                  <el-input-number
                    v-model="form.confidence"
                    :min="0"
                    :max="1"
                    :step="0.05"
                    controls-position="right"
                    style="width: 100%"
                  />
                </el-form-item>
              </div>

              <el-form-item>
                <el-checkbox v-model="form.proofread">启用校对</el-checkbox>
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
                启动任务
              </el-button>
            </el-form>
          </div>
        </section>

        <section class="stack">
          <div class="panel">
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
              <div v-else class="empty-state">尚未提交任务</div>
            </div>
          </div>

          <div v-if="!shouldShowProofreading" class="panel">
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
          </div>

          <div v-else class="panel">
            <div class="panel-header">
              <h2 class="panel-title">校对对比</h2>
              <el-tag v-if="proofreading?.correct" type="success">已返回校对文本</el-tag>
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
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, VideoPlay } from '@element-plus/icons-vue'
import { createCrawlJob, getCrawlJob } from '../api/client'
import type { CrawlJobResponse, ProductFeatures } from '../api/types'
import { formatDate, statusText, statusType } from '../utils/format'
import {
  buildProofreadSourceText,
  correctedDiffSegments,
  diffText,
  sourceDiffSegments,
  stripFeatureNumber,
} from '../utils/text'

type CrawlMode = 'search' | 'direct'

const form = reactive({
  mode: 'search' as CrawlMode,
  productName: '超星泛雅智慧课程平台',
  url: '',
  waitMs: 5000,
  confidence: 0.3,
  proofread: false,
  headed: true,
})

const submitting = ref(false)
const currentJob = ref<CrawlJobResponse | null>(null)
let timer: number | undefined

const features = computed<ProductFeatures | null>(() => {
  const agentResponse = currentJob.value?.agent_response
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
  if (!form.productName.trim()) {
    ElMessage.warning('请填写产品名称')
    return
  }
  if (form.mode === 'direct' && !form.url.trim()) {
    ElMessage.warning('请填写详情页 URL')
    return
  }

  submitting.value = true
  try {
    const job = await createCrawlJob({
      product_name: form.productName.trim(),
      url: form.mode === 'direct' ? form.url.trim() : null,
      search: form.mode === 'search',
      proofread: form.proofread,
      headed: form.headed,
      wait_ms: form.waitMs,
      confidence: form.confidence,
    })
    currentJob.value = job
    ElMessage.success('任务已创建')
    startPolling(job.id)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '创建任务失败')
  } finally {
    submitting.value = false
  }
}

async function refreshCurrentJob() {
  if (!currentJob.value) {
    return
  }
  await loadJob(currentJob.value.id)
}

async function loadJob(id: string) {
  try {
    currentJob.value = await getCrawlJob(id)
    if (currentJob.value.status === 'succeeded' || currentJob.value.status === 'failed') {
      stopPolling()
    }
  } catch (error) {
    stopPolling()
    ElMessage.error(error instanceof Error ? error.message : '刷新任务失败')
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

onBeforeUnmount(stopPolling)
</script>

<style scoped>
.job-error {
  margin-top: 14px;
}

.form-hint {
  margin: -4px 0 16px;
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
