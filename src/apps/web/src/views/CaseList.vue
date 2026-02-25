<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { getCaseList, type CaseListItem } from "../api/cases";
import { createSession } from "../api/session";
import { showLoadingToast, showFailToast, showToast } from "vant";

const router = useRouter();
const cases = ref<CaseListItem[]>([]);
const loading = ref(false);
const finished = ref(false);
const showCustomDialog = ref(false);
const customTopic = ref("");

const onLoad = async () => {
  if (cases.value.length > 0) {
    finished.value = true;
    loading.value = false;
    return;
  }

  try {
    // 后端返回数组，不是 { items: [...] }
    const res = await getCaseList();
    cases.value = res;
    finished.value = true;
  } catch (e) {
    console.error(e);
    showFailToast("加载主题失败");
  } finally {
    loading.value = false;
  }
};

const onSelectCase = async (item: CaseListItem) => {
  const toast = showLoadingToast({
    message: "创建会话中...",
    forbidClick: true,
  });

  try {
    const res = await createSession({ case_id: item.id });
    toast.close();
    router.push(`/chat/${res.id}`);
  } catch (e) {
    toast.close();
    // error handled in interceptor
  }
};

const onCreateCustomTopic = async () => {
  const topic = customTopic.value.trim();
  if (topic.length < 2) {
    showToast("请输入至少2个字的主题");
    return;
  }

  const toast = showLoadingToast({
    message: "创建主题会话中...",
    forbidClick: true,
    duration: 0,
  });

  try {
    const res = await createSession({ mode: "custom", topic });
    toast.close();
    showCustomDialog.value = false;
    customTopic.value = "";
    router.push(`/chat/${res.id}`);
  } catch (e: any) {
    toast.close();
    const msg = e?.response?.data?.detail || "创建主题会话失败，请重试";
    showFailToast(msg);
  }
};
</script>

<template>
  <div class="case-list-page">
    <van-nav-bar
      title="主题列表"
      right-text="历史会话"
      @click-right="$router.push('/sessions')"
    />

    <van-list
      v-model:loading="loading"
      :finished="finished"
      finished-text="没有更多了"
      @load="onLoad"
    >
      <div class="case-card case-card-random" @click="showCustomDialog = true">
        <div class="case-title">自定义主题对话</div>
        <div class="case-tags">
          <van-tag type="success">开箱即用</van-tag>
          <van-tag plain type="primary" style="margin-left: 5px">输入主题</van-tag>
        </div>
      </div>

      <div
        v-for="item in cases"
        :key="item.id"
        class="case-card"
        @click="onSelectCase(item)"
      >
        <div class="case-title">{{ item.title }}</div>
        <div class="case-tags">
          <van-tag type="primary">{{ item.department }}</van-tag>
          <van-tag plain type="danger" style="margin-left: 5px">{{
            item.difficulty
          }}</van-tag>
        </div>
      </div>
    </van-list>

    <van-dialog
      v-model:show="showCustomDialog"
      title="输入你感兴趣的主题"
      show-cancel-button
      @confirm="onCreateCustomTopic"
    >
      <van-field
        v-model="customTopic"
        rows="3"
        autosize
        type="textarea"
        maxlength="120"
        placeholder="例如：高中思政课如何设计议题式教学"
      />
    </van-dialog>
  </div>
</template>

<style scoped>
.case-list-page {
  background: #ecfdf5;
  min-height: 100vh;
}

.case-card {
  background: #fefefe;
  padding: 19px;
  margin: 13px 15px;
  border-radius: 12px;
  border: 2px solid #d1fae5;
  transition: transform 0.25s, border-color 0.25s;
  cursor: pointer;
  animation: itemShow 0.5s ease-out backwards;
}

@keyframes itemShow {
  0% {
    opacity: 0;
    transform: scale(0.92);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

.case-card:nth-child(1) { animation-delay: 0.08s; }
.case-card:nth-child(2) { animation-delay: 0.16s; }
.case-card:nth-child(3) { animation-delay: 0.24s; }
.case-card:nth-child(4) { animation-delay: 0.32s; }

.case-card:active {
  transform: scale(0.97);
  border-color: #6ee7b7;
}

.case-card-random {
  background: #fef3c7;
  border: 2px solid #fbbf24;
  position: relative;
  overflow: hidden;
}

.case-card-random::after {
  content: "★";
  position: absolute;
  top: 15px;
  right: 15px;
  font-size: 22px;
  color: #f59e0b;
  animation: rotateIcon 4s linear infinite;
}

@keyframes rotateIcon {
  0% {
    transform: rotate(0deg);
  }
  100% {
    transform: rotate(360deg);
  }
}

.case-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 11px;
  color: #064e3b;
  line-height: 1.45;
}

.case-card-random .case-title {
  color: #92400e;
}

.case-tags {
  display: flex;
  gap: 7px;
}

.case-tags :deep(.van-tag) {
  border-radius: 10px;
  padding: 5px 12px;
  font-weight: 600;
  font-size: 12px;
}

.case-tags :deep(.van-tag--primary) {
  background: #0891b2;
  border: none;
}

.case-tags :deep(.van-tag--success) {
  background: #059669;
  border: none;
}

.case-tags :deep(.van-tag--danger) {
  background: #dc2626;
  border: none;
}

.case-tags :deep(.van-tag--plain) {
  background: #dbeafe;
  color: #075985;
  border: 1px solid #93c5fd;
}
</style>
