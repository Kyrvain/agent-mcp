<template>
  <el-config-provider>
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-mark">A</div>
          <div>
            <div class="brand-name">Agent MCP CDP</div>
            <div class="brand-subtitle">产品功能提取台</div>
          </div>
        </div>

        <el-menu
          class="nav-menu"
          :default-active="route.path"
          router
        >
          <el-menu-item index="/">
            <el-icon><Search /></el-icon>
            <span>爬取任务</span>
          </el-menu-item>
          <el-menu-item index="/runs">
            <el-icon><FolderOpened /></el-icon>
            <span>历史结果</span>
          </el-menu-item>
        </el-menu>
      </aside>

      <main class="main">
        <router-view />
      </main>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { FolderOpened, Search } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'

const route = useRoute()
</script>
