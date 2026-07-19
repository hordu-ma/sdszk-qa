<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type { ProjectVersion, TeachingArtifactKind } from "../types/api";

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
  versions: ProjectVersion[];
  saving: boolean;
}>();

const emit = defineEmits<{
  save: [content: Record<string, unknown>];
  dirtyChange: [dirty: boolean];
  updateLocks: [lockedPaths: string[]];
  regenerate: [data: { target_path: string; guidance: string }];
  generateArtifact: [artifactKind: TeachingArtifactKind];
  restore: [versionNumber: number];
}>();

const draft = ref<ArtifactDraft>(emptyDraft());
const initialSnapshot = ref("");
const editSummary = ref("");
const regenerationGuidance = ref("增强依据、活动与可观察证据的对应关系");
const restoreVersion = ref<number | null>(null);

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

const editorState = computed(() => asRecord(props.version?.content.editor_state));
const lockedPaths = computed(() => Array.isArray(editorState.value.locked_paths)
  ? editorState.value.locked_paths.map(asString).filter(Boolean)
  : []);
const teachingArtifacts = computed(() => asRecord(props.version?.content.teaching_artifacts));
const artifactKinds: Array<{ kind: Exclude<TeachingArtifactKind, "lesson_design">; label: string }> = [
  { kind: "task_sheet", label: "课堂任务单" },
  { kind: "rubric", label: "非评分观察量规" },
  { kind: "board_plan", label: "板书设计" },
  { kind: "slide_outline", label: "课件提纲" },
  { kind: "practice_task", label: "实践任务" },
];

function isLocked(path: string): boolean {
  return lockedPaths.value.some((locked) => (
    locked === path || locked.startsWith(`${path}.`) || path.startsWith(`${locked}.`)
  ));
}

function toggleLock(path: string) {
  const next = isLocked(path)
    ? lockedPaths.value.filter((locked) => locked !== path)
    : [...lockedPaths.value, path];
  emit("updateLocks", next);
}

function regenerate(path: string) {
  if (!regenerationGuidance.value.trim() || isLocked(path)) return;
  emit("regenerate", {
    target_path: path,
    guidance: regenerationGuidance.value.trim(),
  });
}

function handleRestore() {
  if (restoreVersion.value === null) return;
  emit("restore", restoreVersion.value);
}

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
      <section class="generation-toolbar" aria-label="局部生成与版本恢复">
        <label>局部重生成要求
          <input v-model="regenerationGuidance" maxlength="1000" placeholder="说明只希望调整什么" />
        </label>
        <div class="restore-control">
          <label>恢复历史版本
            <select v-model.number="restoreVersion">
              <option :value="null">请选择</option>
              <option v-for="item in versions.slice(1)" :key="item.id" :value="item.version_number">v{{ item.version_number }}</option>
            </select>
          </label>
          <button type="button" class="secondary-button" :disabled="saving || restoreVersion === null" @click="handleRestore">创建恢复版本</button>
        </div>
        <p>恢复不会删除历史；章节锁定和每次局部生成都会创建不可变新版本。</p>
      </section>

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
          <span class="field-title">教学目标（每行一项）<button type="button" class="lock-button" @click="toggleLock('alignment_card.objectives')">{{ isLocked('alignment_card.objectives') ? '解除锁定' : '锁定' }}</button></span>
          <textarea v-model="draft.objectives" rows="5" required :disabled="isLocked('alignment_card.objectives')" />
        </label>
      </fieldset>

      <fieldset>
        <legend>目标—证据—任务蓝图</legend>
        <label>
          <span class="field-title">评价证据（每行一项）<span><button type="button" class="text-button" :disabled="isLocked('design_blueprint.evidence')" @click="regenerate('design_blueprint.evidence')">局部重生成</button><button type="button" class="lock-button" @click="toggleLock('design_blueprint.evidence')">{{ isLocked('design_blueprint.evidence') ? '解除锁定' : '锁定' }}</button></span></span>
          <textarea v-model="draft.blueprintEvidence" rows="4" :disabled="isLocked('design_blueprint.evidence')" />
        </label>
        <div class="repeat-heading">
          <strong>学习任务</strong>
          <button type="button" class="secondary-button" @click="addLearningTask">新增任务</button>
        </div>
        <article v-for="(task, index) in draft.learningTasks" :key="`task-${index}`" class="repeat-card">
          <label>任务 {{ index + 1 }} 标题<input v-model="task.title" required :disabled="isLocked(`design_blueprint.learning_tasks.${index}`)" /></label>
          <label>分钟数<input v-model.number="task.minutes" type="number" min="0" :disabled="isLocked(`design_blueprint.learning_tasks.${index}`)" /></label>
          <label>可观察证据<input v-model="task.evidence" :disabled="isLocked(`design_blueprint.learning_tasks.${index}`)" /></label>
          <div class="repeat-actions"><button type="button" class="text-button" :disabled="isLocked(`design_blueprint.learning_tasks.${index}`)" @click="regenerate(`design_blueprint.learning_tasks.${index}.evidence`)">重生成证据</button><button type="button" class="lock-button" @click="toggleLock(`design_blueprint.learning_tasks.${index}`)">{{ isLocked(`design_blueprint.learning_tasks.${index}`) ? '解锁' : '锁定' }}</button><button type="button" class="text-button" :disabled="isLocked(`design_blueprint.learning_tasks.${index}`)" :aria-label="`删除学习任务 ${index + 1}`" @click="draft.learningTasks.splice(index, 1)">删除</button></div>
        </article>
      </fieldset>

      <fieldset>
        <legend>课时设计</legend>
        <label>章节名称<input v-model="draft.sectionName" required /></label>
        <label><span class="field-title">课堂导入<span><button type="button" class="text-button" :disabled="isLocked('lesson_design.opening')" @click="regenerate('lesson_design.opening')">局部重生成</button><button type="button" class="lock-button" @click="toggleLock('lesson_design.opening')">{{ isLocked('lesson_design.opening') ? '解除锁定' : '锁定' }}</button></span></span><textarea v-model="draft.opening" rows="3" :disabled="isLocked('lesson_design.opening')" /></label>
        <div class="repeat-heading">
          <strong>课堂活动</strong>
          <button type="button" class="secondary-button" @click="addActivity">新增活动</button>
        </div>
        <article v-for="(activity, index) in draft.activities" :key="`activity-${index}`" class="repeat-card activity-card">
          <label>活动 {{ index + 1 }} 标题<input v-model="activity.title" required :disabled="isLocked(`lesson_design.activities.${index}`)" /></label>
          <label>分钟数<input v-model.number="activity.minutes" type="number" min="0" :disabled="isLocked(`lesson_design.activities.${index}`)" /></label>
          <label>教师活动<textarea v-model="activity.teacher_action" rows="2" :disabled="isLocked(`lesson_design.activities.${index}`)" /></label>
          <label>学生活动<textarea v-model="activity.student_action" rows="2" :disabled="isLocked(`lesson_design.activities.${index}`)" /></label>
          <label>课堂证据<textarea v-model="activity.evidence" rows="2" :disabled="isLocked(`lesson_design.activities.${index}`)" /></label>
          <div class="repeat-actions"><button type="button" class="text-button" :disabled="isLocked(`lesson_design.activities.${index}`)" @click="regenerate(`lesson_design.activities.${index}.evidence`)">重生成证据</button><button type="button" class="lock-button" @click="toggleLock(`lesson_design.activities.${index}`)">{{ isLocked(`lesson_design.activities.${index}`) ? '解锁' : '锁定' }}</button><button type="button" class="text-button" :disabled="isLocked(`lesson_design.activities.${index}`)" :aria-label="`删除课堂活动 ${index + 1}`" @click="draft.activities.splice(index, 1)">删除</button></div>
        </article>
        <label><span class="field-title">评价证据汇总（每行一项）<span><button type="button" class="text-button" :disabled="isLocked('lesson_design.assessment_evidence')" @click="regenerate('lesson_design.assessment_evidence')">局部重生成</button><button type="button" class="lock-button" @click="toggleLock('lesson_design.assessment_evidence')">{{ isLocked('lesson_design.assessment_evidence') ? '解除锁定' : '锁定' }}</button></span></span><textarea v-model="draft.assessmentEvidence" rows="4" :disabled="isLocked('lesson_design.assessment_evidence')" /></label>
        <label><span class="field-title">教师提示（每行一项）<span><button type="button" class="text-button" :disabled="isLocked('lesson_design.teacher_notes')" @click="regenerate('lesson_design.teacher_notes')">局部重生成</button><button type="button" class="lock-button" @click="toggleLock('lesson_design.teacher_notes')">{{ isLocked('lesson_design.teacher_notes') ? '解除锁定' : '锁定' }}</button></span></span><textarea v-model="draft.teacherNotes" rows="4" :disabled="isLocked('lesson_design.teacher_notes')" /></label>
      </fieldset>

      <fieldset>
        <legend>配套教学成果</legend>
        <p class="artifact-hint">从当前已确认蓝图和课时设计派生；量规只描述可观察证据，不计分、不排名。</p>
        <div class="artifact-grid">
          <article v-for="item in artifactKinds" :key="item.kind" class="artifact-card">
            <strong>{{ item.label }}</strong>
            <span>{{ teachingArtifacts[item.kind] ? '已生成' : '尚未生成' }}</span>
            <div><button type="button" :disabled="saving || isLocked(`teaching_artifacts.${item.kind}`)" @click="emit('generateArtifact', item.kind)">{{ teachingArtifacts[item.kind] ? '重新生成' : '生成' }}</button><button v-if="teachingArtifacts[item.kind]" type="button" class="lock-button" @click="toggleLock(`teaching_artifacts.${item.kind}`)">{{ isLocked(`teaching_artifacts.${item.kind}`) ? '解锁' : '锁定' }}</button></div>
            <pre v-if="teachingArtifacts[item.kind]">{{ JSON.stringify(teachingArtifacts[item.kind], null, 2) }}</pre>
          </article>
        </div>
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
.editor-title-row, .repeat-heading, .editor-actions, .field-title, .restore-control { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.editor-title-row h3 { margin: 0 0 4px; }.editor-title-row p { margin: 0; color: #58675e; font-size: 13px; }
.dirty-badge { border-radius: 999px; background: #fff0ce; color: #704900; padding: 5px 10px; font-size: 12px; }
.editor-empty, .save-hint { border-radius: 10px; background: #f4f7f4; color: #4c5d53; padding: 12px; }
form { display: grid; gap: 16px; margin-top: 16px; }
.generation-toolbar { display: grid; gap: 12px; border: 1px solid #c9d9d0; border-radius: 12px; background: #f4f8f5; padding: 14px; }.generation-toolbar p, .artifact-hint { margin: 0; color: #53655b; font-size: 13px; }.restore-control label { flex: 1; }
fieldset { display: grid; gap: 12px; border: 1px solid #d9e2db; border-radius: 12px; padding: 16px; }
legend { padding: 0 7px; color: #173f35; font-weight: 700; }
label { display: grid; gap: 6px; color: #263b30; font-size: 13px; font-weight: 600; }
input, textarea, select { width: 100%; box-sizing: border-box; border: 1px solid #aebcb2; border-radius: 8px; padding: 9px 10px; background: white; color: #172019; font: inherit; font-weight: 400; }
input:disabled, textarea:disabled { background: #edf1ee; color: #526057; }
textarea { resize: vertical; line-height: 1.55; }
input:focus-visible, textarea:focus-visible, button:focus-visible { outline: 3px solid #d28a24; outline-offset: 2px; }
.repeat-card { display: grid; grid-template-columns: 1.4fr 100px 1.4fr auto; gap: 10px; align-items: end; border-left: 3px solid #6f9e8c; background: #f7f9f7; padding: 12px; }
.activity-card { grid-template-columns: 1.4fr 100px 1fr 1fr; }.activity-card label:nth-of-type(5) { grid-column: 1 / -2; }.repeat-actions { display: flex; flex-wrap: wrap; gap: 5px; align-items: center; }
button { border: 0; border-radius: 9px; padding: 9px 13px; background: #286b58; color: white; cursor: pointer; font: inherit; }
button:disabled { opacity: .48; cursor: not-allowed; }.secondary-button, .lock-button { border: 1px solid #5a7c6d; background: white; color: #245747; }.lock-button { padding: 5px 8px; font-size: 12px; }.text-button { background: transparent; color: #8b2f20; padding-inline: 8px; }
.artifact-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }.artifact-card { display: grid; gap: 9px; border: 1px solid #d9e2db; border-radius: 10px; padding: 12px; }.artifact-card > span { color: #607068; font-size: 12px; }.artifact-card > div { display: flex; gap: 8px; }.artifact-card pre { max-height: 220px; overflow: auto; margin: 0; border-radius: 8px; background: #f5f7f5; padding: 10px; white-space: pre-wrap; font-size: 11px; }
.summary-field { margin-top: 2px; }.save-hint { margin: 0; font-size: 13px; }.editor-actions { justify-content: flex-end; }
@media (max-width: 850px) { .repeat-card, .activity-card, .artifact-grid { grid-template-columns: 1fr; }.activity-card label:nth-of-type(5) { grid-column: auto; }.editor-title-row, .restore-control { align-items: stretch; flex-direction: column; } }
</style>
