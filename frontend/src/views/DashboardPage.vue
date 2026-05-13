<template>
  <section>
    <div class="page-header">
      <div>
        <h1>首页统计</h1>
        <div class="page-subtitle">从岗位收藏到技能补齐，先看整体进展。</div>
      </div>
      <el-button type="primary" @click="$router.push('/jobs')">查看岗位</el-button>
    </div>

    <el-skeleton :loading="loading" animated>
      <div class="metric-grid">
        <el-card v-for="item in metrics" :key="item.label" class="metric-card" shadow="never">
          <span class="muted">{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <div class="muted">{{ item.hint }}</div>
        </el-card>
      </div>

      <el-card class="section-card recent-card" shadow="never">
        <template #header>
          <div class="card-header">
            <strong>最近收藏</strong>
            <el-link type="primary" @click="$router.push('/jobs')">全部岗位</el-link>
          </div>
        </template>
        <el-empty v-if="!recentJobs.length" description="还没有收藏岗位" />
        <el-table v-else :data="recentJobs" stripe>
          <el-table-column label="岗位" min-width="220">
            <template #default="{ row }">
              <el-link type="primary" @click="openDetail(row)">{{ row.title || "未命名岗位" }}</el-link>
              <div class="muted">{{ row.company }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="salary" label="薪资" width="120" />
          <el-table-column prop="location" label="地点" width="140" />
          <el-table-column prop="tracking_status" label="状态" width="130" />
          <el-table-column prop="score" label="匹配度" width="110" />
        </el-table>
      </el-card>
    </el-skeleton>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { getDashboard } from "../api";

const router = useRouter();
const loading = ref(true);
const stats = ref({});
const recentJobs = ref([]);

const metrics = computed(() => [
  { label: "适合岗位", value: stats.value.matched || 0, hint: "符合当前匹配配置" },
  { label: "高匹配岗位", value: stats.value.strong || 0, hint: "匹配度 80 分以上" },
  { label: "待处理", value: stats.value.pending || 0, hint: "还没有推进状态" },
  { label: "已投递", value: stats.value.applied || 0, hint: "已进入投递链路" },
  { label: "面试中", value: stats.value.interviewing || 0, hint: "有面试推进记录" },
  { label: "淘汰/不合适", value: stats.value.rejected || 0, hint: "已结束或放弃" },
  { label: "面试转化率", value: `${stats.value.conversion || 0}%`, hint: "面试中 / 已投递" }
]);

function openDetail(job) {
  router.push({ name: "job-detail", query: { job_key: job.job_key } });
}

onMounted(async () => {
  try {
    const data = await getDashboard();
    stats.value = data.stats || {};
    recentJobs.value = data.jobs || [];
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.recent-card {
  margin-top: 16px;
}
</style>
