<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">运行详情</h1>
        <p class="page-description">{{ id }}</p>
      </div>
      <div class="toolbar">
        <el-button :icon="Back" @click="router.push('/runs')">返回</el-button>
        <el-button :icon="Refresh" :loading="loading" @click="loadDetail">刷新</el-button>
      </div>
    </header>

    <div class="page-body">
      <section class="panel">
        <div class="panel-body">
          <el-tabs>
            <el-tab-pane label="agent_response">
              <pre class="code-block">{{ prettyJson(agentResponse) }}</pre>
            </el-tab-pane>
            <el-tab-pane label="result">
              <pre class="code-block">{{ prettyJson(result) }}</pre>
            </el-tab-pane>
            <el-tab-pane label="features.md">
              <pre class="plain-block">{{ features || '暂无 features.md' }}</pre>
            </el-tab-pane>
            <el-tab-pane label="截图">
              <img
                class="screenshot"
                :src="screenshotUrl(id)"
                alt="页面截图"
                @error="screenshotFailed = true"
              />
              <el-alert
                v-if="screenshotFailed"
                type="warning"
                title="未能加载截图"
                :closable="false"
              />
            </el-tab-pane>
          </el-tabs>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Back, Refresh } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import {
  getRunAgentResponse,
  getRunFeatures,
  getRunResult,
  screenshotUrl,
} from '../api/client'
import { prettyJson } from '../utils/format'

const props = defineProps<{
  id: string
}>()

const router = useRouter()
const loading = ref(false)
const result = ref<Record<string, unknown> | null>(null)
const agentResponse = ref<Record<string, unknown> | null>(null)
const features = ref('')
const screenshotFailed = ref(false)

async function loadDetail() {
  loading.value = true
  screenshotFailed.value = false
  try {
    const [nextResult, nextAgentResponse, nextFeatures] = await Promise.all([
      getRunResult(props.id),
      getRunAgentResponse(props.id),
      getRunFeatures(props.id),
    ])
    result.value = nextResult
    agentResponse.value = nextAgentResponse
    features.value = nextFeatures
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载运行详情失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadDetail()
})
</script>
