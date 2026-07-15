<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { showFailToast, showSuccessToast } from "vant";
import {
  cancelTask,
  createProject,
  getModelStatus,
  listDocuments,
  listProjects,
  listTasks,
  reviewDocument,
  retrieveBasis,
  retryTask,
  uploadDocument,
} from "../api/workbench";
import type {
  BasisCitation,
  KnowledgeDocument,
  ModelStatus,
  TaskRun,
  TeachingProject,
} from "../types/api";

const projects = ref<TeachingProject[]>([]);
const selectedProjectId = ref<number | null>(null);
const documents = ref<KnowledgeDocument[]>([]);
const tasks = ref<TaskRun[]>([]);
const citations = ref<BasisCitation[]>([]);
const modelStatus = ref<ModelStatus | null>(null);
const loading = ref(false);
const query = ref("");
const newProject = ref({ title: "", stage: "高中", course_type: "议题式" });
let timer: number | undefined;

const selectedProject = computed(() =>
  projects.value.find((item) => item.id === selectedProjectId.value),
);

async function refreshProjects() {
  projects.value = await listProjects();
  if (!selectedProjectId.value && projects.value[0]) {
    selectedProjectId.value = projects.value[0].id;
  }
}

async function refreshProjectData() {
  if (!selectedProjectId.value) return;
  const [documentItems, taskItems] = await Promise.all([
    listDocuments(selectedProjectId.value),
    listTasks(selectedProjectId.value),
  ]);
  documents.value = documentItems;
  tasks.value = taskItems;
}

async function handleCreateProject() {
  if (newProject.value.title.trim().length < 2) {
    showFailToast("请输入项目名称");
    return;
  }
  loading.value = true;
  try {
    const project = await createProject({ ...newProject.value, title: newProject.value.title.trim() });
    await refreshProjects();
    selectedProjectId.value = project.id;
    newProject.value.title = "";
    showSuccessToast("教学项目已创建");
  } finally {
    loading.value = false;
  }
}

async function handleUpload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file || !selectedProjectId.value) return;
  loading.value = true;
  try {
    await uploadDocument(selectedProjectId.value, file);
    await refreshProjectData();
    showSuccessToast("资料已进入处理队列");
  } catch {
    showFailToast("资料上传失败");
  } finally {
    input.value = "";
    loading.value = false;
  }
}

async function handleRetrieve() {
  if (!selectedProjectId.value || query.value.trim().length < 2) {
    showFailToast("请输入至少两个字的检索问题");
    return;
  }
  loading.value = true;
  try {
    const result = await retrieveBasis(selectedProjectId.value, query.value.trim());
    citations.value = result.citations;
    if (result.insufficient_basis) showFailToast("当前资料不足，系统未生成虚假依据");
  } finally {
    loading.value = false;
  }
}

async function handleReview(documentId: number, status: "approved" | "disabled") {
  try {
    await reviewDocument(documentId, status);
    await refreshProjectData();
    showSuccessToast(status === "approved" ? "资料已审核通过" : "资料已停用");
  } catch {
    showFailToast("当前账号没有资料审核权限");
  }
}

async function handleCancel(taskId: number) {
  await cancelTask(taskId);
  await refreshProjectData();
}

async function handleRetry(taskId: number) {
  await retryTask(taskId);
  await refreshProjectData();
}

watch(selectedProjectId, async () => {
  citations.value = [];
  await refreshProjectData();
});

onMounted(async () => {
  try {
    modelStatus.value = await getModelStatus();
    await refreshProjects();
    await refreshProjectData();
    timer = window.setInterval(refreshProjectData, 3000);
  } catch {
    showFailToast("工作台加载失败");
  }
});

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer);
});
</script>

<template>
  <main class="workbench-page">
    <header class="hero">
      <div>
        <p class="eyebrow">阶段 1A · 可信平台骨架</p>
        <h1>鲁韵教学工作台</h1>
        <p>创建教学项目、加工授权资料，并用可定位引用验证可信检索。</p>
      </div>
      <div v-if="modelStatus" :class="['provider', { degraded: modelStatus.degraded }]">
        <span>{{ modelStatus.degraded ? "降级 Provider" : "默认 Provider" }}</span>
        <strong>{{ modelStatus.provider }} · {{ modelStatus.provider_model }}</strong>
      </div>
    </header>

    <nav class="top-links">
      <router-link to="/topics">问答入口</router-link>
      <router-link to="/sessions">历史会话</router-link>
    </nav>

    <section class="grid">
      <article class="panel projects-panel">
        <h2>1. 教学项目</h2>
        <div class="form-row">
          <input v-model="newProject.title" placeholder="例如：高中家国情怀议题式教学" />
          <select v-model="newProject.stage">
            <option>小学</option><option>初中</option><option>高中</option><option>大学</option>
          </select>
          <select v-model="newProject.course_type">
            <option>议题式</option><option>案例式</option><option>实践式</option>
          </select>
          <button :disabled="loading" @click="handleCreateProject">创建项目</button>
        </div>
        <div v-if="projects.length" class="project-tabs">
          <button
            v-for="project in projects"
            :key="project.id"
            :class="{ active: project.id === selectedProjectId }"
            @click="selectedProjectId = project.id"
          >
            {{ project.title }}
          </button>
        </div>
        <p v-else class="empty">还没有教学项目，请先创建。</p>
      </article>

      <article class="panel">
        <div class="panel-title">
          <div><h2>2. 可信资料</h2><p>{{ selectedProject?.title || "请先选择项目" }}</p></div>
          <label class="upload-button" :class="{ disabled: !selectedProjectId || loading }">
            上传资料
            <input type="file" accept=".docx,.pdf,.md,.txt" :disabled="!selectedProjectId || loading" @change="handleUpload" />
          </label>
        </div>
        <div class="document-list">
          <div v-for="document in documents" :key="document.id" class="document-item">
            <div><strong>{{ document.filename }}</strong><small>SHA256 {{ document.checksum_sha256.slice(0, 12) }}…</small></div>
            <div class="document-actions">
              <span :class="['status', document.status]">{{ document.status }}</span>
              <span :class="['status', document.review_status]">{{ document.review_status }}</span>
              <button v-if="document.status === 'ready' && document.review_status === 'pending'" @click="handleReview(document.id, 'approved')">审核通过</button>
              <button v-if="document.review_status === 'approved'" @click="handleReview(document.id, 'disabled')">停用</button>
            </div>
          </div>
          <p v-if="!documents.length" class="empty">支持 DOCX、文本型 PDF、Markdown 和 TXT。</p>
        </div>
      </article>

      <article class="panel retrieve-panel">
        <h2>3. 可信依据检索</h2>
        <div class="search-row">
          <input v-model="query" placeholder="例如：家国情怀教学目标应如何设置？" @keyup.enter="handleRetrieve" />
          <button :disabled="!selectedProjectId || loading" @click="handleRetrieve">运行 retrieve_basis</button>
        </div>
        <div v-if="citations.length" class="citation-list">
          <article v-for="citation in citations" :key="citation.chunk_id" class="citation">
            <header><strong>{{ citation.filename }}</strong><span>{{ citation.location_label }} · {{ citation.relevance }}</span></header>
            <p>{{ citation.content }}</p>
          </article>
        </div>
        <p v-else class="empty">检索结果会在这里显示文件名、位置和原文片段。</p>
      </article>

      <article class="panel">
        <h2>4. 异步任务</h2>
        <div class="task-list">
          <div v-for="task in tasks" :key="task.id" class="task-item">
            <div><strong>#{{ task.id }} {{ task.task_type }}</strong><small>第 {{ task.attempt }} 次 · {{ task.progress }}%</small></div>
            <div class="task-actions">
              <span :class="['status', task.status]">{{ task.status }}</span>
              <button v-if="task.status === 'queued' || task.status === 'running'" @click="handleCancel(task.id)">取消</button>
              <button v-if="task.status === 'failed' || task.status === 'cancelled'" @click="handleRetry(task.id)">重试</button>
            </div>
          </div>
          <p v-if="!tasks.length" class="empty">上传资料后可在这里查看任务进度、取消和重试。</p>
        </div>
      </article>
    </section>
  </main>
</template>

<style scoped>
.workbench-page { min-height: 100vh; background: #f3f5f0; color: #172019; padding: 32px; }
.hero { max-width: 1320px; margin: 0 auto; padding: 32px 36px; border-radius: 22px; background: #173f35; color: white; display: flex; justify-content: space-between; gap: 24px; align-items: end; }
.hero h1 { margin: 4px 0 8px; font-size: 34px; }.hero p { margin: 0; color: #d9e8df; }.eyebrow { font-size: 12px; letter-spacing: .14em; text-transform: uppercase; }
.provider { min-width: 260px; padding: 14px 16px; border: 1px solid #77a995; border-radius: 12px; display: grid; gap: 4px; }.provider span { font-size: 12px; color: #b9d4c8; }.provider.degraded { border-color: #e7af60; background: #4c3a1d; }
.top-links { max-width: 1320px; margin: 14px auto; display: flex; gap: 10px; }.top-links a { color: #245b4c; background: white; border: 1px solid #d9dfd9; border-radius: 999px; padding: 8px 14px; }
.grid { max-width: 1320px; margin: 0 auto; display: grid; grid-template-columns: 1.15fr .85fr; gap: 18px; }.panel { background: white; border: 1px solid #dde4de; border-radius: 18px; padding: 24px; box-shadow: 0 8px 26px rgba(33, 57, 43, .06); }.projects-panel { grid-column: 1 / -1; }.panel h2 { margin: 0 0 16px; font-size: 19px; }
.form-row, .search-row { display: flex; gap: 10px; }.form-row input, .search-row input { flex: 1; }.form-row input, .form-row select, .search-row input { border: 1px solid #cfd8d1; border-radius: 10px; padding: 11px 12px; background: white; color: #172019; }.panel button, .upload-button { border: 0; border-radius: 10px; padding: 10px 14px; background: #286b58; color: white; cursor: pointer; font: inherit; }.panel button:disabled, .upload-button.disabled { opacity: .45; cursor: not-allowed; }
.project-tabs { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }.project-tabs button { background: #edf3ef; color: #285143; }.project-tabs button.active { background: #173f35; color: white; }
.panel-title, .document-item, .task-item, .citation header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }.panel-title p { margin: -10px 0 12px; color: #637068; font-size: 13px; }.upload-button input { display: none; }
.document-item, .task-item { border-top: 1px solid #edf0ed; padding: 12px 0; }.document-item div, .task-item div:first-child { display: grid; gap: 3px; }.document-item small, .task-item small { color: #778179; }.status { border-radius: 999px; background: #e8ece9; padding: 4px 9px; font-size: 12px; }.status.ready, .status.completed { background: #dcf5e8; color: #17633f; }.status.failed, .status.cancelled { background: #fde5df; color: #9d3926; }.status.processing, .status.running, .status.queued { background: #fff0ce; color: #875b0b; }
.document-actions { display: flex !important; align-items: center; gap: 6px !important; }.document-actions button { padding: 5px 8px; font-size: 12px; }.status.approved { background: #dcf5e8; color: #17633f; }.status.pending { background: #fff0ce; color: #875b0b; }.status.disabled, .status.rejected { background: #edf0ed; color: #657068; }
.retrieve-panel { min-height: 350px; }.citation-list { display: grid; gap: 10px; margin-top: 16px; }.citation { border-left: 4px solid #4c8d77; background: #f5f8f6; padding: 14px; border-radius: 8px; }.citation header span { color: #6b756e; font-size: 12px; }.citation p { white-space: pre-wrap; line-height: 1.65; margin: 10px 0 0; color: #36443a; }.task-actions { display: flex; gap: 7px; align-items: center; }.task-actions button { padding: 5px 9px; font-size: 12px; }.empty { color: #7b857e; font-size: 13px; }
@media (max-width: 850px) { .workbench-page { padding: 14px; }.hero { align-items: stretch; flex-direction: column; padding: 24px; }.grid { grid-template-columns: 1fr; }.projects-panel { grid-column: auto; }.form-row, .search-row { flex-direction: column; }.provider { min-width: 0; } }
</style>
