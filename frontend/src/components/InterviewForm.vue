<template>
  <el-form label-position="top" class="interview-form">
    <el-row :gutter="12">
      <el-col :md="8" :xs="24">
        <el-form-item label="面试轮次" required>
          <el-select v-model="form.round_name" style="width: 100%">
            <el-option v-for="item in rounds" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :md="8" :xs="24">
        <el-form-item label="面试类型">
          <el-select v-model="form.interview_type" style="width: 100%">
            <el-option v-for="item in types" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :md="8" :xs="24">
        <el-form-item label="面试结果">
          <el-select v-model="form.result" style="width: 100%">
            <el-option v-for="item in results" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
      </el-col>
      <el-col :md="8" :xs="24">
        <el-form-item label="面试时间">
          <el-date-picker v-model="form.interview_time" type="datetime" value-format="YYYY-MM-DD HH:mm" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :md="8" :xs="24">
        <el-form-item label="表现分">
          <el-input-number v-model="form.performance_score" :min="0" :max="100" style="width: 100%" />
        </el-form-item>
      </el-col>
      <el-col :md="8" :xs="24">
        <el-form-item label="同步岗位状态">
          <el-select v-model="form.tracking_status" style="width: 100%">
            <el-option v-for="item in statuses" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
      </el-col>
    </el-row>

    <el-form-item label="面试总结">
      <el-input v-model="form.summary" type="textarea" :rows="3" placeholder="记录整体感受、结果、下一步准备" />
    </el-form-item>

    <el-divider>面试问题</el-divider>
    <div v-for="(question, index) in form.questions" :key="index" class="question-row">
      <el-input v-model="question.question" type="textarea" :rows="2" placeholder="面试问题" />
      <el-select v-model="question.skills" multiple filterable allow-create default-first-option placeholder="关联技能点">
        <el-option v-for="skill in skills" :key="skill.name" :label="skill.name" :value="skill.name" />
      </el-select>
      <el-input-number v-model="question.performance_score" :min="0" :max="100" />
      <el-input v-model="question.answer_summary" type="textarea" :rows="2" placeholder="回答复盘" />
    </div>

    <div class="form-actions">
      <el-button @click="addQuestion">增加问题</el-button>
      <el-button type="primary" :loading="saving" @click="submit">保存面试记录</el-button>
    </div>
  </el-form>
</template>

<script setup>
import { reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createInterview } from "../api";

const props = defineProps({
  job: { type: Object, default: () => ({}) },
  skills: { type: Array, default: () => [] }
});
const emit = defineEmits(["saved"]);

const rounds = ["一面", "二面", "三面", "技术面", "HR 面", "复盘"];
const types = ["电话面试", "视频面试", "现场面试", "笔试", "HR 沟通"];
const results = ["待反馈", "通过", "未通过", "待补充", "Offer", "放弃"];
const statuses = ["待处理", "已投递", "面试中", "待复盘", "已拿 Offer", "已淘汰"];
const saving = ref(false);
const form = reactive({
  round_name: "一面",
  interview_time: "",
  interview_type: "视频面试",
  result: "待反馈",
  tracking_status: "面试中",
  performance_score: 60,
  summary: "",
  questions: [{ question: "", skills: [], performance_score: 60, answer_summary: "" }]
});

function addQuestion() {
  form.questions.push({ question: "", skills: [], performance_score: 60, answer_summary: "" });
}

function validate() {
  if (!props.job.job_key) return "请先选择一个岗位";
  if (!form.round_name) return "请选择面试轮次";
  if (!form.questions.some((item) => item.question.trim())) return "至少记录一个面试问题";
  return "";
}

async function submit() {
  const message = validate();
  if (message) {
    ElMessage.warning(message);
    return;
  }

  try {
    saving.value = true;
    await createInterview({
      ...form,
      job_key: props.job.job_key,
      company: props.job.company,
      title: props.job.title,
      questions: form.questions.filter((item) => item.question.trim())
    });
    ElMessage.success("面试记录已保存");
    emit("saved");
  } catch (error) {
    ElMessage.error(error.message);
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.question-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr 130px 1.4fr;
  gap: 10px;
  margin-bottom: 10px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 980px) {
  .question-row {
    grid-template-columns: 1fr;
  }
}
</style>
