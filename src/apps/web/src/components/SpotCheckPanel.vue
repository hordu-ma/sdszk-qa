<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { showFailToast, showSuccessToast } from "vant";
import {
  getL4SignalSummary,
  getSpotCheckDetail,
  listSpotChecks,
  sampleSpotChecks,
  submitSpotCheckReview,
} from "../api/workbench";
import type {
  L4SignalSummary,
  SpotCheckDetail,
  SpotCheckItem,
  SpotCheckVerdict,
} from "../types/api";

const props = defineProps<{
  canReview: boolean;
  projectId: number | null;
}>();

const queueItems = ref<SpotCheckItem[]>([]);
const statusCounts = ref<Record<string, number>>({});
const queueDisclaimer = ref("");
const selectedItemId = ref<number | null>(null);
const detail = ref<SpotCheckDetail | null>(null);
const projectSummary = ref<L4SignalSummary | null>(null);
const globalSummary = ref<L4SignalSummary | null>(null);
const loading = ref(false);
const sampleSize = ref(5);
const reviewForm = ref({
  review_kind: "independent" as "independent" | "arbitration",
  verdict: "confirmed" as SpotCheckVerdict,
  issue_tags: "",
  rubric_feedback: "",
  rationale: "",
});

const statusLabels: Record<string, string> = {
  pending: "待复核",
  single_review: "已单评",
  consensus: "双评共识",
  disputed: "存在分歧",
  arbitrated: "已仲裁",
};

const actionLabels: Record<string, string> = {
  accept: "采纳",
  ignore: "忽略",
  edit: "编辑后采纳",
  request_expert: "申请专家复核",
};

const activeSummary = computed(() => globalSummary.value ?? projectSummary.value);

async function refreshQueue() {
  if (!props.canReview) return;
  const queue = await listSpotChecks();
  queueItems.value = queue.items;
  statusCounts.value = queue.status_counts;
  queueDisclaimer.value = queue.disclaimer;
}

async function refreshSummaries() {
  if (props.projectId) {
    projectSummary.value = await getL4SignalSummary(props.projectId);
  } else {
    projectSummary.value = null;
  }
  if (props.canReview) {
    globalSummary.value = await getL4SignalSummary(null);
  }
}

async function handleSample() {
  loading.value = true;
  try {
    const queue = await sampleSpotChecks({ sample_size: sampleSize.value });
    showSuccessToast(`已抽入 ${queue.items.length} 个 SkillRun`);
    await refreshQueue();
  } catch {
    /* 请求层已提示 */
  } finally {
    loading.value = false;
  }
}

async function openDetail(itemId: number) {
  selectedItemId.value = itemId;
  detail.value = await getSpotCheckDetail(itemId);
}

async function handleSubmitReview() {
  if (!selectedItemId.value) return;
  if (reviewForm.value.rationale.trim().length < 2) {
    showFailToast("请填写复核依据");
    return;
  }
  loading.value = true;
  try {
    await submitSpotCheckReview(selectedItemId.value, {
      review_kind: reviewForm.value.review_kind,
      verdict: reviewForm.value.verdict,
      issue_tags: reviewForm.value.issue_tags
        .split(/[,，]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
      rubric_feedback: reviewForm.value.rubric_feedback.trim() || null,
      rationale: reviewForm.value.rationale.trim(),
    });
    showSuccessToast("复核记录已保存");
    reviewForm.value.rationale = "";
    reviewForm.value.rubric_feedback = "";
    await refreshQueue();
    await openDetail(selectedItemId.value);
    await refreshSummaries();
  } catch {
    /* 请求层已提示 */
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await refreshQueue();
  await refreshSummaries();
});

watch(
  () => props.projectId,
  async () => {
    await refreshSummaries();
  },
);
</script>

<template>
  <article class="panel full-panel spot-check-panel">
    <div class="panel-title">
      <div>
        <h2>10. WP2.4 抽检复核与 L4 信号（内部工程）</h2>
        <p>
          诊断 SkillRun 抽检走双评—分歧—第三人仲裁；教师逐条决定按规则维度汇总为
          L4 信号（authorized_for_training=false），仅用于规则字典与量规迭代。
        </p>
      </div>
    </div>

    <div class="spot-check-grid">
      <section v-if="canReview">
        <h3>抽检队列</h3>
        <div class="pipeline-actions">
          <label class="check-row">
            抽样数
            <input v-model.number="sampleSize" type="number" min="1" max="20" />
          </label>
          <button :disabled="loading" @click="handleSample">抽取诊断运行</button>
          <button :disabled="loading" @click="refreshQueue">刷新</button>
        </div>
        <p v-if="Object.keys(statusCounts).length" class="hint">
          <span v-for="(count, key) in statusCounts" :key="key" class="status">
            {{ statusLabels[key] || key }} × {{ count }}
          </span>
        </p>
        <div class="queue-list">
          <button
            v-for="item in queueItems"
            :key="item.id"
            :class="['queue-button', { active: item.id === selectedItemId }]"
            @click="openDetail(item.id)"
          >
            <strong>#{{ item.id }} · run {{ item.skill_run_id }} · {{ item.skill_id }}</strong>
            <small>
              {{ statusLabels[item.status] || item.status }}
              <template v-if="item.resolved_verdict">
                · 结论 {{ item.resolved_verdict }}
              </template>
            </small>
          </button>
          <p v-if="!queueItems.length" class="empty">队列为空，可先抽取最近完成的诊断运行。</p>
        </div>
      </section>

      <section v-if="canReview && detail">
        <h3>证据与复核</h3>
        <p class="hint">
          Skill {{ detail.item.skill_id }} v{{ detail.item.skill_version }} ·
          状态 {{ statusLabels[detail.item.status] || detail.item.status }}
        </p>
        <details>
          <summary>查看 SkillRun 输入 / 输出与模型清单快照</summary>
          <pre>{{ JSON.stringify({
            input: detail.skill_run?.input_payload,
            output: detail.skill_run?.output_payload,
            snapshot: detail.item.context_snapshot,
          }, null, 2) }}</pre>
        </details>
        <ul class="review-list">
          <li v-for="review in detail.reviews" :key="review.id">
            <strong>{{ review.review_kind === "arbitration" ? "仲裁" : "独立复核" }}</strong>
            · {{ review.verdict === "confirmed" ? "结论成立" : "需要调整" }}
            <template v-if="review.issue_tags.length">· {{ review.issue_tags.join("、") }}</template>
            <p>{{ review.rationale }}</p>
            <p v-if="review.rubric_feedback" class="hint">量规反馈：{{ review.rubric_feedback }}</p>
          </li>
          <li v-if="!detail.reviews.length" class="empty">尚无复核记录。</li>
        </ul>
        <div class="stack-form">
          <select v-model="reviewForm.review_kind">
            <option value="independent">独立复核</option>
            <option value="arbitration">分歧仲裁（须第三人）</option>
          </select>
          <select v-model="reviewForm.verdict">
            <option value="confirmed">confirmed · 诊断结论成立</option>
            <option value="needs_adjustment">needs_adjustment · 需要调整</option>
          </select>
          <input v-model="reviewForm.issue_tags" placeholder="问题标签，逗号分隔（可为空）" />
          <textarea
            v-model="reviewForm.rubric_feedback"
            rows="2"
            placeholder="对规则字典/量规修订的反馈（可为空）"
          />
          <textarea v-model="reviewForm.rationale" rows="3" placeholder="复核依据或仲裁理由" />
          <button :disabled="loading" @click="handleSubmitReview">提交不可变复核记录</button>
        </div>
      </section>

      <section>
        <h3>L4 信号按规则维度汇总</h3>
        <p v-if="activeSummary" class="hint">{{ activeSummary.disclaimer }}</p>
        <template v-for="summary in [activeSummary]" :key="summary?.scope">
          <div v-if="summary">
            <p class="hint">
              范围：{{ summary.scope === "global" ? "全部项目" : "当前项目" }}
              · 项目 {{ summary.project_count }} 个 · 信号 {{ summary.total_signals }} 条
            </p>
            <article
              v-for="dimension in summary.dimensions"
              :key="dimension.dimension"
              class="dimension-row"
            >
              <strong>{{ dimension.dimension }}</strong>
              <small>
                <span v-for="(count, action) in dimension.actions" :key="action">
                  <template v-if="count">{{ actionLabels[action] || action }} × {{ count }}　</template>
                </span>
              </small>
              <small class="hint">
                规则：{{ dimension.rules.map((rule) => `${rule.rule_id}（${rule.total_signals}）`).join("、") }}
              </small>
            </article>
            <p v-if="!summary.dimensions.length" class="empty">
              还没有教师逐条决定产生的 L4 信号。
            </p>
          </div>
          <p v-else class="empty">选择项目后可查看该项目的 L4 信号汇总。</p>
        </template>
      </section>
    </div>
  </article>
</template>

<style scoped>
.spot-check-grid { display: grid; grid-template-columns: 1fr 1.2fr 1fr; gap: 16px; }
.spot-check-grid > section { border: 1px solid #e1e7e2; border-radius: 12px; padding: 16px; }
.spot-check-panel input, .spot-check-panel select, .spot-check-panel textarea { width: 100%; box-sizing: border-box; border: 1px solid #cfd8d1; border-radius: 9px; padding: 9px 10px; background: white; color: #172019; }
.check-row input { width: 80px; }
.queue-list { display: grid; gap: 7px; margin-top: 12px; }
.queue-button { display: grid; gap: 3px; text-align: left; background: #edf3ef !important; color: #285143 !important; }
.queue-button.active { background: #173f35 !important; color: white !important; }
.review-list { list-style: none; padding: 0; margin: 12px 0; display: grid; gap: 10px; }
.review-list li { border-top: 1px solid #edf0ed; padding-top: 8px; font-size: 13px; }
.review-list p { margin: 4px 0 0; color: #36443a; }
.dimension-row { border-top: 1px solid #edf0ed; padding: 9px 0; display: grid; gap: 4px; }
.spot-check-panel details pre { white-space: pre-wrap; overflow: auto; max-height: 300px; font-size: 12px; background: #f8faf8; padding: 10px; border-radius: 8px; }
.status { border-radius: 999px; background: #e8ece9; padding: 3px 8px; font-size: 12px; margin-right: 6px; }
@media (max-width: 850px) { .spot-check-grid { grid-template-columns: 1fr; } }
</style>
