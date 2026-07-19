<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type {
  ClassProfile,
  ProfessionalInputPayload,
  ProjectVersion,
  TeachingProject,
} from "../types/api";

type JsonRecord = Record<string, unknown>;

const props = defineProps<{
  project: TeachingProject | null;
  version: ProjectVersion | null;
  classProfiles: ClassProfile[];
  selectedProfileIds: number[];
  saving: boolean;
}>();

const emit = defineEmits<{
  confirm: [payload: ProfessionalInputPayload];
  dirtyChange: [dirty: boolean];
}>();

const form = ref<ProfessionalInputPayload>(emptyForm());
const initialSnapshot = ref("");

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function emptyForm(): ProfessionalInputPayload {
  return {
    topic: "",
    core_question: "",
    course_basis: "",
    class_context: "",
    course_type: "",
    lesson_minutes: 45,
    available_minutes: 45,
    teacher_intent: "",
    available_resources: "",
    assumptions_confirmed: false,
  };
}

const savedInput = computed(() => asRecord(props.version?.content.professional_input));
const confirmedInput = computed(() => asRecord(savedInput.value.confirmed_input));
const conflicts = computed(() => Array.isArray(savedInput.value.conflicts)
  ? savedInput.value.conflicts.map(asRecord)
  : []);
const assumptions = computed(() => Array.isArray(savedInput.value.assumptions)
  ? savedInput.value.assumptions.map(asString).filter(Boolean)
  : []);
const readyForAlignment = computed(() => savedInput.value.ready_for_alignment === true);
const invalidatedSections = computed(() => Array.isArray(savedInput.value.invalidated_sections)
  ? savedInput.value.invalidated_sections.map(asString).filter(Boolean)
  : []);

function resetForm() {
  const input = confirmedInput.value;
  form.value = {
    topic: asString(input.topic) || props.project?.title || "",
    core_question: asString(input.core_question),
    course_basis: asString(input.course_basis),
    class_context: asString(input.class_context),
    course_type: asString(input.course_type) || props.project?.course_type || "",
    lesson_minutes: asNumber(input.lesson_minutes, 45),
    available_minutes: asNumber(input.available_minutes, 45),
    teacher_intent: asString(input.teacher_intent),
    available_resources: asString(input.available_resources),
    assumptions_confirmed: savedInput.value.assumptions_confirmed === true,
  };
  initialSnapshot.value = JSON.stringify(form.value);
}

watch(
  () => [props.project?.id, props.version?.id],
  resetForm,
  { immediate: true },
);

const isDirty = computed(() => JSON.stringify(form.value) !== initialSnapshot.value);
watch(isDirty, (value) => emit("dirtyChange", value), { immediate: true });

const selectedProfiles = computed(() => props.classProfiles.filter(
  (profile) => props.selectedProfileIds.includes(profile.id),
));

function formatContext(context: JsonRecord): string {
  return Object.entries(context)
    .map(([key, value]) => `${key}=${String(value)}`)
    .join("，");
}

function applySelectedProfiles() {
  form.value.class_context = selectedProfiles.value
    .map((profile) => `${profile.name}：${formatContext(profile.context)}`)
    .join("\n");
}

function handleSubmit() {
  if (!props.project) return;
  emit("confirm", {
    ...form.value,
    topic: form.value.topic.trim(),
    core_question: form.value.core_question.trim(),
    course_basis: form.value.course_basis.trim(),
    class_context: form.value.class_context.trim(),
    course_type: form.value.course_type.trim(),
    teacher_intent: form.value.teacher_intent.trim(),
    available_resources: form.value.available_resources.trim(),
  });
}
</script>

<template>
  <article class="panel full-panel professional-input-panel">
    <div class="panel-title">
      <div>
        <p class="eyebrow">阶段 2 · WP2.1 内部纵向增量</p>
        <h2>6. 专业输入确认与冲突检查</h2>
        <p>先确认课程依据、班情、时间、资源和教师意图，再进入对齐卡。</p>
      </div>
      <span v-if="readyForAlignment" class="ready-badge" role="status">可进入对齐卡</span>
      <span v-else-if="savedInput.ready_for_alignment === false" class="blocked-badge" role="status">仍需处理</span>
    </div>

    <p class="impact-note">
      保存会生成不可变新版本；若当前已有对齐卡、蓝图、课时设计或诊断，将在新版本中失效，原版本仍保留。
    </p>

    <form v-if="project" class="professional-form" @submit.prevent="handleSubmit">
      <fieldset>
        <legend>任务身份与课程依据</legend>
        <label>教学主题<input v-model="form.topic" required /></label>
        <label>核心议题<textarea v-model="form.core_question" rows="2" required /></label>
        <label>课程依据摘要<textarea v-model="form.course_basis" rows="3" placeholder="可暂留空，但必须确认系统明示的假设" /></label>
        <label>课型<input v-model="form.course_type" required /></label>
        <label>教师意图<textarea v-model="form.teacher_intent" rows="3" required placeholder="例如：通过材料研读和小组讨论形成有依据的判断" /></label>
      </fieldset>

      <fieldset>
        <legend>班情、时间与资源条件</legend>
        <div class="memory-row">
          <p>已显式选中 {{ selectedProfiles.length }} 个班情档案</p>
          <button type="button" class="secondary-button" :disabled="!selectedProfiles.length" @click="applySelectedProfiles">应用已选班情并允许修改</button>
        </div>
        <label>本次班情确认<textarea v-model="form.class_context" rows="3" placeholder="不会静默推断；可从已选班情带入后覆盖" /></label>
        <div class="time-grid">
          <label>计划课时（分钟）<input v-model.number="form.lesson_minutes" type="number" min="20" max="180" required /></label>
          <label>实际可用时间（分钟）<input v-model.number="form.available_minutes" type="number" min="20" max="180" required /></label>
        </div>
        <label>可用资源与限制<textarea v-model="form.available_resources" rows="3" placeholder="例如：普通教室、多媒体可用；或明确填写无设备/无网络" /></label>
      </fieldset>

      <label class="assumption-confirm">
        <input v-model="form.assumptions_confirmed" type="checkbox" />
        我确认：未填写项将按下方“假设/待确认”继续，后续仍需补充真实信息。
      </label>
      <div class="form-actions">
        <button type="button" class="secondary-button" :disabled="saving || !isDirty" @click="resetForm">撤销未保存修改</button>
        <button type="submit" :disabled="saving || !isDirty">{{ saving ? "检查并保存中…" : "检查并保存输入确认" }}</button>
      </div>
    </form>
    <p v-else class="empty">请先选择教学项目。</p>

    <section v-if="conflicts.length" class="result-block conflicts" aria-live="polite">
      <h3>显式冲突</h3>
      <article v-for="item in conflicts" :key="asString(item.conflict_id)">
        <strong>{{ asString(item.message) }}</strong>
        <p>处理方式：{{ asString(item.resolution) }}</p>
      </article>
    </section>
    <section v-if="assumptions.length" class="result-block assumptions" aria-live="polite">
      <h3>假设/待确认</h3>
      <ul><li v-for="item in assumptions" :key="item">{{ item }}</li></ul>
    </section>
    <p v-if="invalidatedSections.length" class="invalidated-note">
      新版本已使以下下游成果失效：{{ invalidatedSections.join("、") }}。
    </p>
  </article>
</template>

<style scoped>
.professional-input-panel { display: grid; gap: 16px; }
.professional-input-panel h2, .professional-input-panel p { margin-top: 0; }
.panel-title, .memory-row, .form-actions, .time-grid { display: flex; gap: 12px; align-items: center; justify-content: space-between; }
.eyebrow { margin-bottom: 5px; color: #6d4b10; font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.ready-badge, .blocked-badge { border-radius: 999px; padding: 7px 11px; font-size: 12px; font-weight: 700; white-space: nowrap; }
.ready-badge { background: #dff4e8; color: #185a3d; }.blocked-badge { background: #ffe3d9; color: #8b2f20; }
.impact-note, .invalidated-note { border-radius: 10px; background: #fff6df; color: #6f4a08; padding: 12px; }
.professional-form { display: grid; gap: 16px; }
fieldset { display: grid; gap: 12px; border: 1px solid #d9e2db; border-radius: 12px; padding: 16px; }
legend { padding: 0 7px; color: #173f35; font-weight: 700; }
label { display: grid; gap: 6px; color: #263b30; font-size: 13px; font-weight: 600; }
input, textarea { width: 100%; box-sizing: border-box; border: 1px solid #aebcb2; border-radius: 8px; padding: 9px 10px; background: white; color: #172019; font: inherit; font-weight: 400; }
textarea { resize: vertical; line-height: 1.55; }
input:focus-visible, textarea:focus-visible, button:focus-visible { outline: 3px solid #d28a24; outline-offset: 2px; }
.time-grid { align-items: stretch; }.time-grid label { flex: 1; }
.memory-row p { margin: 0; color: #58675e; font-size: 13px; }
.assumption-confirm { grid-template-columns: auto 1fr; align-items: center; border: 1px solid #d8c28e; border-radius: 10px; background: #fffaf0; padding: 12px; }
.assumption-confirm input { width: auto; }
.form-actions { justify-content: flex-end; }
button { border: 0; border-radius: 9px; padding: 9px 13px; background: #286b58; color: white; cursor: pointer; font: inherit; }
button:disabled { opacity: .48; cursor: not-allowed; }.secondary-button { border: 1px solid #5a7c6d; background: white; color: #245747; }
.result-block { border-radius: 12px; padding: 14px 16px; }.result-block h3 { margin: 0 0 9px; }
.result-block article + article { border-top: 1px solid rgba(0, 0, 0, .1); margin-top: 10px; padding-top: 10px; }
.result-block article p, .result-block ul { margin-bottom: 0; }.conflicts { background: #fff0eb; color: #792c20; }.assumptions { background: #fff8e7; color: #654707; }
@media (max-width: 850px) { .panel-title, .memory-row, .time-grid { align-items: stretch; flex-direction: column; }.form-actions { flex-wrap: wrap; } }
</style>
