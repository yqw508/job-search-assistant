<template>
  <section>
    <div class="page-header">
      <div>
        <h1>岗位列表</h1>
        <div class="page-subtitle">筛选、排序、跟踪每一个收藏岗位。</div>
      </div>
      <el-tag type="info">{{ filteredJobs.length }} 个岗位</el-tag>
    </div>

    <div class="toolbar">
      <el-input v-model="keyword" clearable placeholder="搜索岗位、公司、地点、薪资" style="width: 280px" />
      <el-select v-model="status" clearable placeholder="状态" style="width: 160px">
        <el-option v-for="item in statuses" :key="item" :label="item" :value="item" />
      </el-select>
      <el-select v-model="matchFilter" placeholder="匹配结果" style="width: 150px">
        <el-option label="全部" value="all" />
        <el-option label="适合" value="matched" />
        <el-option label="不适合" value="unmatched" />
      </el-select>
      <el-select v-model="sortBy" placeholder="排序" style="width: 170px">
        <el-option label="匹配度优先" value="score" />
        <el-option label="最近更新" value="updated" />
        <el-option label="薪资上限" value="salary" />
      </el-select>
    </div>

    <el-table v-loading="loading" :data="pageJobs" border stripe>
      <el-table-column label="岗位" min-width="220">
        <template #default="{ row }">
          <el-link type="primary" @click="openDetail(row)">{{ row.title || "未命名岗位" }}</el-link>
          <div class="muted">{{ row.company || "公司未知" }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="salary" label="薪资" width="120" />
      <el-table-column prop="location" label="地点" width="150" />
      <el-table-column prop="company_size" label="规模" width="130" />
      <el-table-column prop="tracking_status" label="状态" width="130" />
      <el-table-column prop="score" label="匹配度" width="105" sortable />
      <el-table-column label="结果" min-width="180">
        <template #default="{ row }">
          <el-tag :type="row.matched ? 'success' : 'danger'">{{ row.matched ? "适合" : "不适合" }}</el-tag>
          <span v-if="row.exclusion_reason" class="muted risk-text">{{ row.exclusion_reason }}</span>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="page"
      v-model:page-size="pageSize"
      class="pager"
      layout="total, sizes, prev, pager, next"
      :page-sizes="[10, 20, 50]"
      :total="filteredJobs.length"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { getJobs } from "../api";

const router = useRouter();
const jobs = ref([]);
const loading = ref(true);
const keyword = ref("");
const status = ref("");
const matchFilter = ref("all");
const sortBy = ref("score");
const page = ref(1);
const pageSize = ref(10);

const statuses = computed(() => Array.from(new Set(jobs.value.map((job) => job.tracking_status).filter(Boolean))));

function salaryUpper(job) {
  const matches = String(job.salary || "").match(/\d+/g) || [];
  return matches.length ? Number(matches[matches.length - 1]) : 0;
}

const filteredJobs = computed(() => {
  const text = keyword.value.trim().toLowerCase();
  return [...jobs.value]
    .filter((job) => !status.value || job.tracking_status === status.value)
    .filter((job) => matchFilter.value === "all" || (matchFilter.value === "matched") === Boolean(job.matched))
    .filter((job) => {
      if (!text) return true;
      return [job.title, job.company, job.location, job.salary, job.company_size]
        .join(" ")
        .toLowerCase()
        .includes(text);
    })
    .sort((left, right) => {
      if (sortBy.value === "updated") return String(right.updated_at || "").localeCompare(String(left.updated_at || ""));
      if (sortBy.value === "salary") return salaryUpper(right) - salaryUpper(left);
      return Number(right.score || 0) - Number(left.score || 0);
    });
});

const pageJobs = computed(() => filteredJobs.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value));

watch([keyword, status, matchFilter, sortBy, pageSize], () => {
  page.value = 1;
});

function openDetail(job) {
  router.push({ name: "job-detail", query: { job_key: job.job_key } });
}

onMounted(async () => {
  try {
    const data = await getJobs();
    jobs.value = data.jobs || [];
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.pager {
  margin-top: 16px;
  justify-content: flex-end;
}

.risk-text {
  margin-left: 8px;
}
</style>
