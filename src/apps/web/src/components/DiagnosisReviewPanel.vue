<script setup lang="ts">
import { computed, ref, watch } from "vue";
import type {
  DiagnosisContent,
  DiagnosisDecisionAction,
  DiagnosisStructureNode,
  ProjectVersion,
} from "../types/api";

const props = defineProps<{
  version: ProjectVersion | null;
  structureNodes: DiagnosisStructureNode[];
  saving: boolean;
}>();

const emit = defineEmits<{
  confirmStructure: [nodes: DiagnosisStructureNode[]];
  decide: [data: { itemId: string; action: DiagnosisDecisionAction; editedSuggestion?: string }];
  applyRevision: [];
}>();

const nodes = ref<DiagnosisStructureNode[]>([]);
const edits = ref<Record<string, string>>({});
watch(() => props.structureNodes, (value) => {
  nodes.value = value.map((item) => ({ ...item }));
}, { immediate: true, deep: true });

const structure = computed(() => {
  const value = props.version?.content.diagnosis_structure;
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {};
});
const diagnosis = computed<DiagnosisContent | null>(() => {
  const value = props.version?.content.diagnosis;
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as unknown as DiagnosisContent
    : null;
});
const acceptedCount = computed(() => Object.values(diagnosis.value?.decisions || {})
  .filter((item) => item.action === "accept" || item.action === "edit").length);

function decide(itemId: string, action: DiagnosisDecisionAction) {
  emit("decide", {
    itemId,
    action,
    editedSuggestion: action === "edit" ? edits.value[itemId] : undefined,
  });
}

function currentDecision(itemId: string) {
  return diagnosis.value?.decisions?.[itemId]?.action || "";
}
</script>

<template>
  <section class="diagnosis-panel">
    <header><div><h3>证据化诊断与教师确认</h3><p>先校正结构，再逐条决定。结果只记为 L4 交互信号，不形成教师评分或排名。</p></div></header>
    <div class="structure-block">
      <h4>教案结构识别</h4>
      <div v-for="node in nodes" :key="node.path" class="structure-row">
        <input v-model="node.title" aria-label="结构标题" />
        <select v-model="node.section_type" aria-label="结构类型">
          <option value="alignment_card">课程依据</option>
          <option value="design_blueprint">教学蓝图</option>
          <option value="lesson_design">课时设计</option>
        </select>
        <small>{{ node.path }}<span v-if="node.excerpt"> · {{ node.excerpt }}</span></small>
      </div>
      <button type="button" :disabled="saving || !nodes.length" @click="emit('confirmStructure', nodes)">
        {{ structure.confirmed ? "重新确认结构" : "确认结构" }}
      </button>
    </div>

    <div v-if="diagnosis" class="diagnosis-items" aria-live="polite">
      <header><h4>{{ diagnosis.conclusion }}</h4><span>已采纳 {{ acceptedCount }} 项</span></header>
      <article v-for="item in diagnosis.items" :key="item.item_id" :class="item.status">
        <div class="item-title"><strong>{{ item.dimension }}</strong><span>{{ item.status === "aligned" ? "已对齐" : "需关注" }}</span></div>
        <dl>
          <dt>原文位置</dt><dd>{{ item.source_path }}</dd>
          <dt>规则依据</dt><dd>{{ item.rule_basis }}</dd>
          <dt>可见证据</dt><dd>{{ item.evidence }}</dd>
          <dt>影响</dt><dd>{{ item.impact }}</dd>
          <dt>建议</dt><dd>{{ item.suggestion }}</dd>
          <dt>示例改写</dt><dd>{{ item.example_revision }}</dd>
        </dl>
        <textarea v-model="edits[item.item_id]" rows="2" :placeholder="item.example_revision" aria-label="编辑修订建议" />
        <div class="decision-actions">
          <button :disabled="saving" @click="decide(item.item_id, 'accept')">采纳</button>
          <button :disabled="saving" class="secondary" @click="decide(item.item_id, 'ignore')">忽略</button>
          <button :disabled="saving || !edits[item.item_id]?.trim()" class="secondary" @click="decide(item.item_id, 'edit')">编辑后采纳</button>
          <button :disabled="saving" class="secondary" @click="decide(item.item_id, 'request_expert')">申请专家复核</button>
          <small v-if="currentDecision(item.item_id)">当前决定：{{ currentDecision(item.item_id) }}</small>
        </div>
      </article>
      <button type="button" :disabled="saving || !acceptedCount" @click="emit('applyRevision')">仅应用已采纳项，生成二次修改稿</button>
    </div>
    <p v-else class="empty">确认结构后运行形成性诊断，即可逐条处理建议。</p>
  </section>
</template>

<style scoped>
.diagnosis-panel { margin-top: 18px; display: grid; gap: 16px; border-top: 1px solid #d8e2dc; padding-top: 18px; }
h3, h4, p { margin: 0; }.diagnosis-panel > header p, .empty { color: #607066; margin-top: 6px; }
.structure-block, .diagnosis-items article { border: 1px solid #c9d9d0; border-radius: 12px; padding: 14px; background: #f8fbf9; }
.structure-row { display: grid; grid-template-columns: 1.5fr 1fr; gap: 8px; margin: 10px 0; }.structure-row small { grid-column: 1 / -1; color: #617168; }
.diagnosis-items { display: grid; gap: 12px; }.diagnosis-items > header, .item-title, .decision-actions { display: flex; align-items: center; justify-content: space-between; gap: 8px; flex-wrap: wrap; }
.diagnosis-items article.needs_attention { border-left: 5px solid #bd5c3a; }.diagnosis-items article.aligned { border-left: 5px solid #4e8068; }
dl { display: grid; grid-template-columns: 90px 1fr; gap: 6px 10px; }dt { font-weight: 700; }dd { margin: 0; }
input, select, textarea { width: 100%; box-sizing: border-box; border: 1px solid #afc0b7; border-radius: 7px; padding: 8px; background: white; }
button { border: 0; border-radius: 8px; padding: 9px 13px; background: #2f6955; color: white; cursor: pointer; }.secondary { background: white; color: #315f50; border: 1px solid #7d998e; }button:disabled { opacity: .5; cursor: not-allowed; }
@media (max-width: 760px) { .structure-row, dl { grid-template-columns: 1fr; }.structure-row small { grid-column: auto; } }
</style>
