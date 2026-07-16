<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { showConfirmDialog, showFailToast, showSuccessToast } from "vant";
import {
  cancelTask,
  clearMemory,
  compareVersions,
  createAlignmentCard,
  createClassProfile,
  createProject,
  createDesignBlueprint,
  deleteClassProfile,
  deletePinnedItem,
  diagnoseArtifact,
  downloadExport,
  exportArtifact,
  generateSection,
  getModelStatus,
  getPreference,
  listClassProfiles,
  listDocuments,
  listPinnedItems,
  listProjectVersions,
  listProjects,
  listTasks,
  pinProject,
  reviewDocument,
  retrieveBasis,
  retryTask,
  savePreference,
  uploadDocument,
} from "../api/workbench";
import type {
  BasisCitation,
  ClassProfile,
  KnowledgeDocument,
  MemoryRef,
  ModelStatus,
  PinnedItem,
  ProjectVersion,
  SkillStepResponse,
  TaskRun,
  TeachingProject,
  UserPreference,
  VersionDiff,
} from "../types/api";
import { useUserStore } from "../stores/user";

const userStore = useUserStore();

const projects = ref<TeachingProject[]>([]);
const selectedProjectId = ref<number | null>(null);
const documents = ref<KnowledgeDocument[]>([]);
const tasks = ref<TaskRun[]>([]);
const citations = ref<BasisCitation[]>([]);
const modelStatus = ref<ModelStatus | null>(null);
const preference = ref<UserPreference | null>(null);
const classProfiles = ref<ClassProfile[]>([]);
const pinnedItems = ref<PinnedItem[]>([]);
const versions = ref<ProjectVersion[]>([]);
const latestStep = ref<SkillStepResponse | null>(null);
const versionDiff = ref<VersionDiff | null>(null);
const loading = ref(false);
const query = ref("");
const newProject = ref({ title: "", stage: "高中", course_type: "议题式" });
const memoryForm = ref({
  default_stage: "高中",
  default_course_type: "议题式",
  textbook_version: "统编版",
  export_template: "standard-v2",
});
const profileForm = ref({ name: "", class_size: 45, focus: "家国情怀" });
const usePreference = ref(false);
const selectedProfileIds = ref<number[]>([]);
const sampleForm = ref({
  topic: "高中家国情怀议题式教学",
  core_question: "青年如何把个人理想融入国家发展？",
  basis_query: "家国情怀教学目标与评价证据",
});
const diffForm = ref({ from: 1, to: 1 });
let timer: number | undefined;

const selectedProject = computed(() =>
  projects.value.find((item) => item.id === selectedProjectId.value),
);
const latestVersionContent = computed<Record<string, unknown>>(
  () => versions.value[0]?.content || {},
);
const hasAlignmentCard = computed(() => Boolean(latestVersionContent.value.alignment_card));
const hasDesignBlueprint = computed(() => Boolean(latestVersionContent.value.design_blueprint));
const hasLessonDesign = computed(() => Boolean(latestVersionContent.value.lesson_design));
const hasDiagnosis = computed(() => Boolean(latestVersionContent.value.diagnosis));
const canReview = computed(() => ["admin", "reviewer"].includes(userStore.userInfo?.role || ""));
const hasMemory = computed(() => Boolean(
  preference.value || classProfiles.value.length || pinnedItems.value.length,
));

const selectedMemoryRefs = computed<MemoryRef[]>(() => {
  const refs: MemoryRef[] = selectedProfileIds.value.map((memory_id) => ({
    memory_type: "class_context_profile",
    memory_id,
  }));
  if (usePreference.value && preference.value) {
    refs.unshift({ memory_type: "user_preference", memory_id: preference.value.id });
  }
  return refs;
});

async function refreshProjects() {
  projects.value = await listProjects();
  if (!selectedProjectId.value && projects.value[0]) {
    selectedProjectId.value = projects.value[0].id;
  }
}

async function refreshProjectData() {
  if (!selectedProjectId.value) return;
  const [documentItems, taskItems, versionItems] = await Promise.all([
    listDocuments(selectedProjectId.value),
    listTasks(selectedProjectId.value),
    listProjectVersions(selectedProjectId.value),
  ]);
  documents.value = documentItems;
  tasks.value = taskItems;
  versions.value = versionItems;
  const latestVersion = versionItems[0];
  const earliestVersion = versionItems[versionItems.length - 1];
  if (latestVersion && earliestVersion) {
    diffForm.value.to = latestVersion.version_number;
    diffForm.value.from = earliestVersion.version_number;
  }
}

async function refreshMemory() {
  const [preferenceItem, profiles, pins] = await Promise.all([
    getPreference(),
    listClassProfiles(),
    listPinnedItems(),
  ]);
  preference.value = preferenceItem;
  classProfiles.value = profiles;
  pinnedItems.value = pins;
  if (preferenceItem) {
    memoryForm.value = {
      default_stage: preferenceItem.default_stage || "高中",
      default_course_type: preferenceItem.default_course_type || "议题式",
      textbook_version: preferenceItem.textbook_version || "统编版",
      export_template: preferenceItem.export_template || "standard-v2",
    };
  }
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
    const result = await retrieveBasis(
      selectedProjectId.value,
      query.value.trim(),
      selectedMemoryRefs.value,
    );
    citations.value = result.citations;
    if (result.insufficient_basis) showFailToast("当前资料不足，系统未生成虚假依据");
  } finally {
    loading.value = false;
  }
}

async function handleSavePreference() {
  preference.value = await savePreference(memoryForm.value);
  usePreference.value = true;
  showSuccessToast("账户偏好已保存并显式选中");
}

async function handleCreateProfile() {
  if (!profileForm.value.name.trim()) {
    showFailToast("请输入班情档案名称");
    return;
  }
  const profile = await createClassProfile({
    name: profileForm.value.name.trim(),
    context: {
      class_size: profileForm.value.class_size,
      focus: profileForm.value.focus,
    },
  });
  selectedProfileIds.value.push(profile.id);
  profileForm.value.name = "";
  await refreshMemory();
  showSuccessToast("班情档案已创建并显式选中");
}

async function handleDeleteProfile(profileId: number) {
  await deleteClassProfile(profileId);
  selectedProfileIds.value = selectedProfileIds.value.filter((id) => id !== profileId);
  await refreshMemory();
}

async function handlePinProject() {
  if (!selectedProject.value) return;
  await pinProject(selectedProject.value);
  await refreshMemory();
  showSuccessToast("项目已钉选到个人 Memory");
}

async function handleDeletePin(itemId: number) {
  await deletePinnedItem(itemId);
  await refreshMemory();
}

async function handleClearMemory() {
  if (!hasMemory.value) return;
  const summary = [
    preference.value ? "1 项账户偏好" : "0 项账户偏好",
    `${classProfiles.value.length} 个班情档案`,
    `${pinnedItems.value.length} 个钉选项`,
  ].join("、");
  try {
    await showConfirmDialog({
      title: "确认清除个人 Memory？",
      message: `将清除 ${summary}。此操作不可撤销。`,
      confirmButtonText: "确认清除",
      confirmButtonColor: "#9d3926",
    });
  } catch {
    return;
  }
  loading.value = true;
  try {
    await clearMemory();
    usePreference.value = false;
    selectedProfileIds.value = [];
    await refreshMemory();
    showSuccessToast("个人 Memory 已清除");
  } finally {
    loading.value = false;
  }
}

async function runSampleStep(step: "alignment" | "blueprint" | "generate" | "diagnose") {
  if (!selectedProjectId.value) return;
  loading.value = true;
  try {
    if (step === "alignment") {
      latestStep.value = await createAlignmentCard({
        project_id: selectedProjectId.value,
        ...sampleForm.value,
        memory_refs: selectedMemoryRefs.value,
      });
    } else if (step === "blueprint") {
      latestStep.value = await createDesignBlueprint(
        selectedProjectId.value,
        selectedMemoryRefs.value,
      );
    } else if (step === "generate") {
      latestStep.value = await generateSection(
        selectedProjectId.value,
        selectedMemoryRefs.value,
      );
    } else {
      latestStep.value = await diagnoseArtifact(
        selectedProjectId.value,
        selectedMemoryRefs.value,
      );
    }
    await refreshProjectData();
    showSuccessToast(`已完成 ${latestStep.value.skill_id}，生成版本 v${latestStep.value.version_number}`);
  } finally {
    loading.value = false;
  }
}

async function handleCompareVersions() {
  if (!selectedProjectId.value || diffForm.value.from === diffForm.value.to) {
    showFailToast("请选择两个不同版本");
    return;
  }
  versionDiff.value = await compareVersions(
    selectedProjectId.value,
    diffForm.value.from,
    diffForm.value.to,
  );
}

async function handleExportArtifact() {
  if (!selectedProjectId.value) return;
  loading.value = true;
  try {
    const result = await exportArtifact(selectedProjectId.value, selectedMemoryRefs.value);
    const blob = await downloadExport(result.download_url);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = result.filename;
    link.click();
    URL.revokeObjectURL(url);
    latestStep.value = result;
    showSuccessToast("标准 Word 已生成");
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
  latestStep.value = null;
  versionDiff.value = null;
  await refreshProjectData();
});

onMounted(async () => {
  try {
    modelStatus.value = await getModelStatus();
    await Promise.all([refreshProjects(), refreshMemory()]);
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
        <p class="eyebrow">阶段 1 · 可信底座与纵向样板</p>
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
              <button v-if="canReview && document.status === 'ready' && document.review_status === 'pending'" @click="handleReview(document.id, 'approved')">审核通过</button>
              <button v-if="canReview && document.review_status === 'approved'" @click="handleReview(document.id, 'disabled')">停用</button>
              <small v-if="!canReview && document.status === 'ready' && document.review_status === 'pending'" class="review-hint">待审核员处理</small>
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
            <div>
              <strong>#{{ task.id }} {{ task.task_type }}</strong>
              <small>第 {{ task.attempt }} 次 · {{ task.progress }}%</small>
              <small v-if="task.error_message" class="task-error">失败原因：{{ task.error_message }}</small>
            </div>
            <div class="task-actions">
              <span :class="['status', task.status]">{{ task.status }}</span>
              <button v-if="task.status === 'queued' || task.status === 'running'" @click="handleCancel(task.id)">取消</button>
              <button v-if="task.status === 'failed' || task.status === 'cancelled'" @click="handleRetry(task.id)">重试</button>
            </div>
          </div>
          <p v-if="!tasks.length" class="empty">上传资料后可在这里查看任务进度、取消和重试。</p>
        </div>
      </article>

      <article class="panel full-panel">
        <div class="panel-title">
          <div>
            <h2>5. 个人 Memory（显式确认）</h2>
            <p>只有下方勾选的偏好和班情才会注入下一次 SkillRun。</p>
          </div>
          <button class="danger-button" :disabled="loading || !hasMemory" @click="handleClearMemory">清除个人 Memory</button>
        </div>
        <div class="memory-grid">
          <section>
            <h3>账户偏好</h3>
            <div class="stack-form">
              <input v-model="memoryForm.default_stage" placeholder="默认学段" />
              <input v-model="memoryForm.default_course_type" placeholder="默认课型" />
              <input v-model="memoryForm.textbook_version" placeholder="教材版本" />
              <input v-model="memoryForm.export_template" placeholder="导出模板" />
            </div>
            <div class="memory-actions">
              <button @click="handleSavePreference">保存偏好</button>
              <label v-if="preference" class="check-row">
                <input v-model="usePreference" type="checkbox" />本次显式使用
              </label>
            </div>
          </section>
          <section>
            <h3>班情档案</h3>
            <div class="stack-form">
              <input v-model="profileForm.name" placeholder="例如：高一3班" />
              <input v-model.number="profileForm.class_size" type="number" min="1" placeholder="班额" />
              <input v-model="profileForm.focus" placeholder="本班关注点" />
              <button @click="handleCreateProfile">新增班情</button>
            </div>
            <label v-for="profile in classProfiles" :key="profile.id" class="memory-item">
              <input v-model="selectedProfileIds" type="checkbox" :value="profile.id" />
              <span><strong>{{ profile.name }}</strong><small>{{ profile.context }}</small></span>
              <button @click.prevent="handleDeleteProfile(profile.id)">删除</button>
            </label>
          </section>
          <section>
            <h3>钉选项目/模板</h3>
            <button :disabled="!selectedProject" @click="handlePinProject">钉选当前项目</button>
            <div v-for="item in pinnedItems" :key="item.id" class="memory-item">
              <span><strong>{{ item.name }}</strong><small>{{ item.item_type }}</small></span>
              <button @click="handleDeletePin(item.id)">取消钉选</button>
            </div>
            <p v-if="!pinnedItems.length" class="empty">尚无钉选项。</p>
          </section>
        </div>
      </article>

      <article class="panel full-panel sample-panel">
        <h2>6. 高中议题式纵向样板</h2>
        <p class="hint">固定顺序：课程依据对齐卡 → 目标—证据—任务蓝图 → 课时分块 → 非评分诊断 → Word 导出。</p>
        <div class="sample-inputs">
          <input v-model="sampleForm.topic" placeholder="样板主题" />
          <input v-model="sampleForm.core_question" placeholder="核心议题" />
          <input v-model="sampleForm.basis_query" placeholder="依据检索问题" />
        </div>
        <div class="pipeline-actions">
          <button :disabled="loading || !selectedProjectId" @click="runSampleStep('alignment')">1 对齐卡</button>
          <button :disabled="loading || !selectedProjectId || !hasAlignmentCard" title="请先完成对齐卡" @click="runSampleStep('blueprint')">2 教学蓝图</button>
          <button :disabled="loading || !selectedProjectId || !hasDesignBlueprint" title="请先完成教学蓝图" @click="runSampleStep('generate')">3 课时设计</button>
          <button :disabled="loading || !selectedProjectId || !hasLessonDesign" title="请先完成课时设计" @click="runSampleStep('diagnose')">4 形成性诊断</button>
          <button :disabled="loading || !selectedProjectId || !hasDiagnosis" title="请先完成形成性诊断" @click="handleExportArtifact">5 导出 Word</button>
        </div>
        <p v-if="selectedProjectId" class="workflow-progress">
          当前进度：对齐卡 {{ hasAlignmentCard ? "✓" : "○" }} · 教学蓝图 {{ hasDesignBlueprint ? "✓" : "○" }} ·
          课时设计 {{ hasLessonDesign ? "✓" : "○" }} · 形成性诊断 {{ hasDiagnosis ? "✓" : "○" }}
        </p>
        <div v-if="latestStep" class="step-result">
          <header><strong>{{ latestStep.skill_id }}</strong><span>v{{ latestStep.version_number }}</span></header>
          <pre>{{ JSON.stringify(latestStep, null, 2) }}</pre>
        </div>
      </article>

      <article class="panel full-panel">
        <h2>7. 版本差异</h2>
        <div class="diff-controls">
          <label>从
            <select v-model.number="diffForm.from">
              <option v-for="version in versions" :key="`from-${version.id}`" :value="version.version_number">v{{ version.version_number }}</option>
            </select>
          </label>
          <label>到
            <select v-model.number="diffForm.to">
              <option v-for="version in versions" :key="`to-${version.id}`" :value="version.version_number">v{{ version.version_number }}</option>
            </select>
          </label>
          <button @click="handleCompareVersions">比较</button>
        </div>
        <div v-if="versionDiff" class="diff-list">
          <article v-for="section in versionDiff.changed_sections" :key="section.section">
            <strong>{{ section.section }}</strong>
            <div><pre>{{ JSON.stringify(section.before, null, 2) }}</pre><pre>{{ JSON.stringify(section.after, null, 2) }}</pre></div>
          </article>
          <p v-if="!versionDiff.changed_sections.length" class="empty">两个版本没有结构化差异。</p>
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
.grid { max-width: 1320px; margin: 0 auto; display: grid; grid-template-columns: 1.15fr .85fr; gap: 18px; }.panel { background: white; border: 1px solid #dde4de; border-radius: 18px; padding: 24px; box-shadow: 0 8px 26px rgba(33, 57, 43, .06); }.projects-panel, .full-panel { grid-column: 1 / -1; }.panel h2 { margin: 0 0 16px; font-size: 19px; }.panel h3 { margin: 0 0 12px; font-size: 15px; }
.form-row, .search-row { display: flex; gap: 10px; }.form-row input, .search-row input { flex: 1; }.form-row input, .form-row select, .search-row input { border: 1px solid #cfd8d1; border-radius: 10px; padding: 11px 12px; background: white; color: #172019; }.panel button, .upload-button { border: 0; border-radius: 10px; padding: 10px 14px; background: #286b58; color: white; cursor: pointer; font: inherit; }.panel button:disabled, .upload-button.disabled { opacity: .45; cursor: not-allowed; }
.project-tabs { display: flex; gap: 8px; margin-top: 16px; flex-wrap: wrap; }.project-tabs button { background: #edf3ef; color: #285143; }.project-tabs button.active { background: #173f35; color: white; }
.panel-title, .document-item, .task-item, .citation header { display: flex; justify-content: space-between; align-items: center; gap: 12px; }.panel-title p { margin: -10px 0 12px; color: #637068; font-size: 13px; }.upload-button input { display: none; }
.document-item, .task-item { border-top: 1px solid #edf0ed; padding: 12px 0; }.document-item div, .task-item div:first-child { display: grid; gap: 3px; }.document-item small, .task-item small { color: #778179; }.task-error { color: #9d3926 !important; max-width: 680px; overflow-wrap: anywhere; }.review-hint { color: #875b0b !important; }.status { border-radius: 999px; background: #e8ece9; padding: 4px 9px; font-size: 12px; }.status.ready, .status.completed { background: #dcf5e8; color: #17633f; }.status.failed, .status.cancelled { background: #fde5df; color: #9d3926; }.status.processing, .status.running, .status.queued { background: #fff0ce; color: #875b0b; }
.document-actions { display: flex !important; align-items: center; gap: 6px !important; }.document-actions button { padding: 5px 8px; font-size: 12px; }.status.approved { background: #dcf5e8; color: #17633f; }.status.pending { background: #fff0ce; color: #875b0b; }.status.disabled, .status.rejected { background: #edf0ed; color: #657068; }
.retrieve-panel { min-height: 350px; }.citation-list { display: grid; gap: 10px; margin-top: 16px; }.citation { border-left: 4px solid #4c8d77; background: #f5f8f6; padding: 14px; border-radius: 8px; }.citation header span { color: #6b756e; font-size: 12px; }.citation p { white-space: pre-wrap; line-height: 1.65; margin: 10px 0 0; color: #36443a; }.task-actions { display: flex; gap: 7px; align-items: center; }.task-actions button { padding: 5px 9px; font-size: 12px; }.empty { color: #7b857e; font-size: 13px; }
.memory-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; }.memory-grid section { border: 1px solid #e4e9e5; border-radius: 12px; padding: 16px; }.stack-form { display: grid; gap: 8px; }.stack-form input, .sample-inputs input, .diff-controls select { border: 1px solid #cfd8d1; border-radius: 9px; padding: 9px 10px; }.memory-actions, .pipeline-actions, .diff-controls { display: flex; gap: 9px; align-items: center; flex-wrap: wrap; margin-top: 12px; }.check-row, .memory-item { display: flex; gap: 8px; align-items: center; }.memory-item { border-top: 1px solid #edf0ed; padding: 9px 0; }.memory-item span { display: grid; gap: 2px; flex: 1; }.memory-item small { color: #778179; }.memory-item button { padding: 5px 8px; font-size: 12px; }.danger-button { background: #9d3926 !important; }.hint, .workflow-progress { color: #637068; }.workflow-progress { font-size: 13px; margin: 10px 0 0; }.sample-inputs { display: grid; grid-template-columns: 1fr 1.4fr 1fr; gap: 9px; }.step-result { margin-top: 16px; border: 1px solid #d7e1da; border-radius: 10px; overflow: hidden; }.step-result header { display: flex; justify-content: space-between; background: #edf3ef; padding: 10px 12px; }.step-result pre, .diff-list pre { white-space: pre-wrap; overflow: auto; font-size: 12px; line-height: 1.5; padding: 12px; margin: 0; background: #f8faf8; }.diff-controls label { display: flex; gap: 6px; align-items: center; }.diff-list { display: grid; gap: 12px; margin-top: 16px; }.diff-list article { border: 1px solid #e1e7e2; border-radius: 10px; padding: 12px; }.diff-list article > div { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 8px; }
@media (max-width: 850px) { .workbench-page { padding: 14px; }.hero { align-items: stretch; flex-direction: column; padding: 24px; }.grid { grid-template-columns: 1fr; }.projects-panel, .full-panel { grid-column: auto; }.form-row, .search-row { flex-direction: column; }.provider { min-width: 0; }.memory-grid, .sample-inputs, .diff-list article > div { grid-template-columns: 1fr; } }
</style>
