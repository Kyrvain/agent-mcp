<template>
  <section class="page">
    <header class="page-header">
      <div>
        <h1 class="page-title">历史结果</h1>
        <p class="page-description">查看 data/runs 下已经落盘的爬取结果。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadRuns">刷新</el-button>
    </header>

    <div class="page-body">
      <section class="panel">
        <div class="panel-body">
          <el-table :data="runs" v-loading="loading" style="width: 100%">
            <el-table-column prop="id" label="Run ID" min-width="190" />
            <el-table-column label="更新时间" min-width="180">
              <template #default="{ row }">
                {{ formatDate(row.updated_at) }}
              </template>
            </el-table-column>
            <el-table-column label="文件" min-width="260">
              <template #default="{ row }">
                <div class="toolbar">
                  <el-tag v-if="row.has_result" size="small">result</el-tag>
                  <el-tag v-if="row.has_agent_response" size="small">agent</el-tag>
                  <el-tag v-if="row.has_features" size="small">features</el-tag>
                  <el-tag v-if="row.has_screenshot" size="small">screenshot</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link @click="router.push(`/runs/${row.id}`)">
                  查看
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { listRuns } from '../api/client'
import type { RunSummary } from '../api/types'
import { formatDate } from '../utils/format'

const router = useRouter()
const loading = ref(false)
const runs = ref<RunSummary[]>([])

async function loadRuns() {
  loading.value = true
  try {
    runs.value = await listRuns()
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载历史结果失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadRuns()
})
</script>
