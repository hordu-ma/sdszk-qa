<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ProjectVersion } from "../types/api";

type JsonRecord = Record<string, unknown>;

interface LearningTaskDraft {
  title: string;
  minutes: number;
  evidence: string;
}

interface ActivityDraft extends LearningTaskDraft {
  teacher_action: string;
  student_action: string;
}

interface ArtifactDraft {
  topic: string;
  coreQuestion: string;
  objectives: string;
  blueprintEvidence: string;
  learningTasks: LearningTaskDraft[];
  sectionName: string;
  opening: string;
  activities: ActivityDraft[];
  assessmentEvidence: string;
  teacherNotes: string;
}

const props = defineProps<{
  version: ProjectVersion | null;
  saving: boolean;
}>();

const emit = defineEmits<{
  save: [content: Record<string, unknown>];
  dirtyChange: [dirty: boolean];
}>();

const draft = ref<ArtifactDraft>(emptyDraft());
const initialSnapshot = ref("");
const editSummary = ref("");

function emptyDraft(): ArtifactDraft {
  return {
    topic: "",
    coreQuestion: "",
    objectives: "",
    blueprintEvidence: "",
    learningTasks: [],
    sectionName: "",
    opening: "",
    activities: [],
    assessmentEvidence: "",
    teacherNotes: "",
  };
}

function asRecord(value: unknown): JsonRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as JsonRecord
    : {};
}

function isRecord(value: unknown): value is JsonRecord {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asNumber(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function asStringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map(asString).filter(Boolean) : [];
}

function lines(value: unknown): string {
  return asStringList(value).join("\n");
}

function parseLines(value: string): string[] {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function cloneJsonRecord(value: Record<string, unknown>): JsonRecord {
  return JSON.parse(JSON.stringify(value)) as JsonRecord;
}

function toDraft(content: JsonRecord): ArtifactDraft {
  const alignment = asRecord(content.alignment_card);
  const blueprint = asRecord(content.design_blueprint);
  const design = asRecord(content.lesson_design);
  const learningTasks = Array.isArray(blueprint.learning_tasks)
    ? blueprint.learning_tasks.map((item) => {
      const task = asRecord(item);
      return {
        title: asString(task.title),
        minutes: asNumber(task.minutes),
        evidence: asString(task.evidence),
      };
    })
    : [];
  const activities = Array.isArray(design.activities)
    ? design.activities.map((item) => {
      const activity = asRecord(item);
      return {
        title: asString(activity.title),
        minutes: asNumber(activity.minutes),
        evidence: asString(activity.evidence),
        teacher_action: asString(activity.teacher_action),
        student_action: asString(activity.student_action),
      };
    })
    : [];
  return {
    topic: asString(alignment.topic),
    coreQuestion: asString(alignment.core_question),
    objectives: lines(alignment.objectives),
    blueprintEvidence: lines(blueprint.evidence),
    learningTasks,
    sectionName: asString(design.section_name),
    opening: asString(design.opening),
    activities,
    assessmentEvidence: lines(design.assessment_evidence),
    teacherNotes: lines(design.teacher_notes),
  };
}

function resetDraft() {
  draft.value = toDraft(props.version?.content || {});
  initialSnapshot.value = JSON.stringify(draft.value);
  editSummary.value = "";
}

watch(() => props.version?.id, resetDraft, { immediate: true });

const isDirty = computed(() => JSON.stringify(draft.value) !== initialSnapshot.value);
watch(isDirty, (value) => emit("dirtyChange", value), { immediate: true });

const canEdit = computed(() => Boolean(
  props.version
  && isRecord(props.version.content.alignment_card)
  && isRecord(props.version.content.design_blueprint)
  && isRecord(props.version.content.lesson_design),
));

function addLearningTask() {
  draft.value.learningTasks.push({ title: "", minutes: 5, evidence: "" });
}

function addActivity() {
  draft.value.activities.push({
    title: "",
    minutes: 5,
    evidence: "",
    teacher_action: "",
    student_action: "",
  });
}

function buildEditedContent(): Record<string, unknown> {
  const content = cloneJsonRecord(props.version?.content || {});
  const sourceAlignment = asRecord(content.alignment_card);
  const sourceBlueprint = asRecord(content.design_blueprint);
  const sourceDesign = asRecord(content.lesson_design);

  content.alignment_card = {
    ...sourceAlignment,
    topic: draft.value.topic.trim(),
    core_question: draft.value.coreQuestion.trim(),
    objectives: parseLines(draft.value.objectives),
  };
  content.design_blueprint = {
    ...sourceBlueprint,
    core_question: draft.value.coreQuestion.trim(),
    objectives: parseLines(draft.value.objectives),
    evidence: parseLines(draft.value.blueprintEvidence),
    learning_tasks: draft.value.learningTasks.map((task) => ({
      title: task.title.trim(),
      minutes: Math.max(0, Number(task.minutes) || 0),
      evidence: task.evidence.trim(),
    })),
  };
  content.lesson_design = {
    ...sourceDesign,
    section_name: draft.value.sectionName.trim(),
    opening: draft.value.opening.trim(),
    activities: draft.value.activities.map((activity, index) => ({
      sequence: index + 1,
      title: activity.title.trim(),
      minutes: Math.max(0, Number(activity.minutes) || 0),
      teacher_action: activity.teacher_action.trim(),
      student_action: activity.student_action.trim(),
      evidence: activity.evidence.trim(),
    })),
    assessment_evidence: parseLines(draft.value.assessmentEvidence),
    teacher_notes: parseLines(draft.value.teacherNotes),
  };
  delete content.diagnosis;
  content._trace = {
    action: "teacher_edit",
    source_version: props.version?.version_number,
    edited_sections: ["alignment_card", "design_blueprint", "lesson_design"],
    edit_summary: editSummary.value.trim() || "教师结构化编辑",
  };
  return content;
}

function handleSave() {
  if (!isDirty.value || !canEdit.value) return;
  emit("save", buildEditedContent());
}
</script>

<template>
  <section class="artifact-editor" aria-labelledby="artifact-editor-title">
    <div class="editor-title-row">
      <div>
        <h3 id="artifact-editor-title">教学成果专业编辑</h3>
        <p v-if="version">基于 v{{ version.version_number }} 编辑；保存后生成新版本，原版本保持不变。</p>
      </div>
      <span v-if="isDirty" class="dirty-badge" role="status">有未保存修改</span>
    </div>

    <p v-if="!canEdit" class="editor-empty">
      请先完成对齐卡、教学蓝图和课时设计，再进入结构化编辑。
    </p>

    <form v-else @submit.prevent="handleSave">
      <fieldset>
        <legend>课程依据与目标</legend>
        <label>
          样板主题
          <input v-model="draft.topic" required />
        </label>
        <label>
          核心议题
          <textarea v-model="draft.coreQuestion" rows="2" required />
        </label>
        <label>
          教学目标（每行一项）
          <textarea v-model="draft.objectives" rows="5" required />
        </label>
      </fieldset>

      <fieldset>
        <legend>目标—证据—任务蓝图</legend>
        <label>
          评价证据（每行一项）
          <textarea v-model="draft.blueprintEvidence" rows="4" />
        </label>
        <div class="repeat-heading">
          <strong>学习任务</strong>
          <button type="button" class="secondary-button" @click="addLearningTask">新增任务</button>
        </div>
        <article v-for="(task, index) in draft.learningTasks" :key="`task-${index}`" class="repeat-card">
          <label>任务 {{ index + 1 }} 标题<input v-model="task.title" required /></label>
          <label>分钟数<input v-model.number="task.minutes" type="number" min="0" /></label>
          <label>可观察证据<input v-model="task.evidence" /></label>
          <button type="button" class="text-button" :aria-label="`删除学习任务 ${index + 1}`" @click="draft.learningTasks.splice(index, 1)">删除</button>
        </article>
      </fieldset>

      <fieldset>
        <legend>课时设计</legend>
        <label>章节名称<input v-model="draft.sectionName" required /></label>
        <label>课堂导入<textarea v-model="draft.opening" rows="3" /></label>
        <div class="repeat-heading">
          <strong>课堂活动</strong>
          <button type="button" class="secondary-button" @click="addActivity">新增活动</button>
        </div>
        <article v-for="(activity, index) in draft.activities" :key="`activity-${index}`" class="repeat-card activity-card">
          <label>活动 {{ index + 1 }} 标题<input v-model="activity.title" required /></label>
          <label>分钟数<input v-model.number="activity.minutes" type="number" min="0" /></label>
          <label>教师活动<textarea v-model="activity.teacher_action" rows="2" /></label>
          <label>学生活动<textarea v-model="activity.student_action" rows="2" /></label>
          <label>课堂证据<textarea v-model="activity.evidence" rows="2" /></label>
          <button type="button" class="text-button" :aria-label="`删除课堂活动 ${index + 1}`" @click="draft.activities.splice(index, 1)">删除</button>
        </article>
        <label>评价证据汇总（每行一项）<textarea v-model="draft.assessmentEvidence" rows="4" /></label>
        <label>教师提示（每行一项）<textarea v-model="draft.teacherNotes" rows="4" /></label>
      </fieldset>

      <label class="summary-field">
        本次修改说明
        <input v-model="editSummary" maxlength="200" placeholder="例如：调整第二个学习任务和课堂证据" />
      </label>
      <p class="save-hint">保存会清除旧诊断结果；请重新运行形成性诊断后再导出。</p>
      <div class="editor-actions">
        <button type="button" class="secondary-button" :disabled="saving || !isDirty" @click="resetDraft">撤销未保存修改</button>
        <button type="submit" :disabled="saving || !isDirty">{{ saving ? "保存中…" : "保存为新版本" }}</button>
      </div>
    </form>
  </section>
</template>

<style scoped>
.artifact-editor { margin-top: 18px; border-top: 1px solid #dfe6e0; padding-top: 18px; }
.editor-title-row, .repeat-heading, .editor-actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.editor-title-row h3 { margin: 0 0 4px; }.editor-title-row p { margin: 0; color: #58675e; font-size: 13px; }
.dirty-badge { border-radius: 999px; background: #fff0ce; color: #704900; padding: 5px 10px; font-size: 12px; }
.editor-empty, .save-hint { border-radius: 10px; background: #f4f7f4; color: #4c5d53; padding: 12px; }
form { display: grid; gap: 16px; margin-top: 16px; }
fieldset { display: grid; gap: 12px; border: 1px solid #d9e2db; border-radius: 12px; padding: 16px; }
legend { padding: 0 7px; color: #173f35; font-weight: 700; }
label { display: grid; gap: 6px; color: #263b30; font-size: 13px; font-weight: 600; }
input, textarea { width: 100%; box-sizing: border-box; border: 1px solid #aebcb2; border-radius: 8px; padding: 9px 10px; background: white; color: #172019; font: inherit; font-weight: 400; }
textarea { resize: vertical; line-height: 1.55; }
input:focus-visible, textarea:focus-visible, button:focus-visible { outline: 3px solid #d28a24; outline-offset: 2px; }
.repeat-card { display: grid; grid-template-columns: 1.4fr 100px 1.4fr auto; gap: 10px; align-items: end; border-left: 3px solid #6f9e8c; background: #f7f9f7; padding: 12px; }
.activity-card { grid-template-columns: 1.4fr 100px 1fr 1fr; }.activity-card label:nth-of-type(5) { grid-column: 1 / -2; }
button { border: 0; border-radius: 9px; padding: 9px 13px; background: #286b58; color: white; cursor: pointer; font: inherit; }
button:disabled { opacity: .48; cursor: not-allowed; }.secondary-button { border: 1px solid #5a7c6d; background: white; color: #245747; }.text-button { background: transparent; color: #8b2f20; padding-inline: 8px; }
.summary-field { margin-top: 2px; }.save-hint { margin: 0; font-size: 13px; }.editor-actions { justify-content: flex-end; }
@media (max-width: 850px) { .repeat-card, .activity-card { grid-template-columns: 1fr; }.activity-card label:nth-of-type(5) { grid-column: auto; }.editor-title-row { align-items: flex-start; flex-direction: column; } }
</style>
