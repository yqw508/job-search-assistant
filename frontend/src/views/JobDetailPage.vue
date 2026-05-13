<template>
  <section>
    <div class="page-header">
      <div>
        <h1>{{ job.title || "岗位详情" }}</h1>
        <div class="page-subtitle">{{ job.company || "公司未知" }} · {{ job.location || "地点未知" }} · {{ job.company_size || "规模未知" }}</div>
      </div>
      <el-button @click="$router.push('/jobs')">返回列表</el-button>
    </div>

    <el-empty v-if="missingKey" description="缺少岗位标识，请从岗位列表进入详情页" />
    <el-skeleton v-else :loading="loading" animated>
      <el-row :gutter="16">
        <el-col :lg="16" :xs="24">
          <el-card class="panel" shadow="never">
            <template #header>
              <div class="card-header">
                <strong>{{ job.salary || "薪资未知" }}</strong>
                <el-tag :type="job.matched ? 'success' : 'danger'">{{ job.matched ? "适合" : "不适合" }}</el-tag>
              </div>
            </template>

            <div class="tag-list">
              <el-tag v-for="chip in chips" :key="chip" effect="plain">{{ chip }}</el-tag>
            </div>
            <el-divider />
            <h3>职位描述</h3>
            <div class="description">{{ job.description || "暂无职位描述" }}</div>
          </el-card>
        </el-col>

        <el-col :lg="8" :xs="24">
          <el-card class="panel side-panel" shadow="never">
            <template #header>匹配分析</template>
            <el-progress :percentage="Number(job.score || 0)" />
            <el-alert v-if="job.exclusion_reason" class="detail-alert" type="warning" :closable="false" :title="job.exclusion_reason" />
            <div class="tag-list">
              <el-tag v-for="reason in job.matched_reasons || []" :key="reason" type="success" effect="plain">{{ reason }}</el-tag>
            </div>
          </el-card>

          <el-card class="panel side-panel" shadow="never">
            <template #header>岗位跟踪</template>
            <el-form label-position="top">
              <el-form-item label="当前状态">
                <el-select v-model="trackingStatus" style="width: 100%">
                  <el-option v-for="item in trackingOptions" :key="item" :label="item" :value="item" />
                </el-select>
              </el-form-item>
              <el-form-item label="备注">
                <el-input v-model="notes" type="textarea" :rows="3" />
              </el-form-item>
              <el-button type="primary" :loading="savingStatus" @click="saveStatus">保存状态</el-button>
            </el-form>
          </el-card>

          <el-card class="panel side-panel" shadow="never">
            <template #header>相关技能</template>
            <el-empty v-if="!skillMentions.length" description="暂无技能提取结果" />
            <div v-else class="tag-list">
              <el-tag v-for="skill in skillMentions" :key="skill.skill_name" effect="plain">
                {{ skill.skill_name }} · {{ skill.importance || 0 }}
              </el-tag>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <el-card class="section-card" shadow="never">
        <template #header>记录一次面试</template>
        <InterviewForm :job="job" :skills="skills" @saved="reload" />
      </el-card>

      <el-card class="section-card" shadow="never">
        <template #header>面试记录</template>
        <InterviewList :interviews="interviews" />
      </el-card>
    </el-skeleton>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { getJobDetail, updateJobStatus } from "../api";
import InterviewForm from "../components/InterviewForm.vue";
import InterviewList from "../components/InterviewList.vue";

const route = useRoute();
const router = useRouter();
const loading = ref(true);
const savingStatus = ref(false);
const job = ref({});
const interviews = ref([]);
const skills = ref([]);
const skillMentions = ref([]);
const trackingStatus = ref("");
const notes = ref("");
const trackingOptions = ["待处理", "已投递", "面试中", "待复盘", "已拿 Offer", "已淘汰", "不合适"];
const missingKey = computed(() => !route.query.job_key);

const chips = computed(() =>
  [job.value.experience, job.value.education, job.value.industry, job.value.financing]
    .concat((job.value.matched_reasons || []).slice(0, 4))
    .filter(Boolean)
);

async function reload() {
  if (missingKey.value) return;
  const data = await getJobDetail(route.query.job_key);
  job.value = data.job || {};
  interviews.value = data.interviews || [];
  skills.value = data.skills || [];
  skillMentions.value = data.skill_mentions || [];
  trackingStatus.value = job.value.tracking_status || "待处理";
  notes.value = job.value.notes || "";
}

async function saveStatus() {
  try {
    savingStatus.value = true;
    await updateJobStatus({ job_key: job.value.job_key, tracking_status: trackingStatus.value, notes: notes.value });
    ElMessage.success("岗位状态已保存");
    await reload();
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    savingStatus.value = false;
  }
}

onMounted(async () => {
  if (missingKey.value) {
    loading.value = false;
    setTimeout(() => router.push("/jobs"), 1200);
    return;
  }
  try {
    await reload();
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
.side-panel {
  margin-bottom: 16px;
}

.detail-alert {
  margin: 14px 0;
}
</style>
