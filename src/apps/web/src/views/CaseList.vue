<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { getTopicList, type TopicListItem } from "../api/cases";
import { createSession } from "../api/session";
import { showLoadingToast, showFailToast, showToast } from "vant";

const router = useRouter();
const topics = ref<TopicListItem[]>([]);
const loading = ref(false);
const finished = ref(false);
const showCustomDialog = ref(false);
const customTopic = ref("");

const onLoad = async () => {
  if (topics.value.length > 0) {
    finished.value = true;
    loading.value = false;
    return;
  }

  try {
    const res = await getTopicList();
    topics.value = res;
    finished.value = true;
  } catch (e) {
    console.error(e);
    showFailToast("加载主题失败");
  } finally {
    loading.value = false;
  }
};

const onSelectTopic = async (item: TopicListItem) => {
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
  <div class="topic-list-page">
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
      <div class="topic-card topic-card-custom" @click="showCustomDialog = true">
        <div class="topic-title">自定义主题对话</div>
        <div class="topic-tags">
          <van-tag type="success">开箱即用</van-tag>
          <van-tag plain type="primary" style="margin-left: 5px">输入主题</van-tag>
        </div>
      </div>

      <div
        v-for="item in topics"
        :key="item.id"
        class="topic-card"
        @click="onSelectTopic(item)"
      >
        <div class="topic-title">{{ item.title }}</div>
        <div class="topic-tags">
          <van-tag type="primary">{{ item.department }}</van-tag>
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
.topic-list-page {
  background: #ecfdf5;
  min-height: 100vh;
}

.topic-card {
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

.topic-card:nth-child(1) { animation-delay: 0.08s; }
.topic-card:nth-child(2) { animation-delay: 0.16s; }
.topic-card:nth-child(3) { animation-delay: 0.24s; }
.topic-card:nth-child(4) { animation-delay: 0.32s; }

.topic-card:active {
  transform: scale(0.97);
  border-color: #6ee7b7;
}

.topic-card-custom {
  background: #fef3c7;
  border: 2px solid #fbbf24;
  position: relative;
  overflow: hidden;
}

.topic-card-custom::after {
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

.topic-title {
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 11px;
  color: #064e3b;
  line-height: 1.45;
}

.topic-card-custom .topic-title {
  color: #92400e;
}

.topic-tags {
  display: flex;
  gap: 7px;
}

.topic-tags :deep(.van-tag) {
  border-radius: 10px;
  padding: 5px 12px;
  font-weight: 600;
  font-size: 12px;
}

.topic-tags :deep(.van-tag--primary) {
  background: #0891b2;
  border: none;
}

.topic-tags :deep(.van-tag--success) {
  background: #059669;
  border: none;
}

.topic-tags :deep(.van-tag--danger) {
  background: #dc2626;
  border: none;
}

.topic-tags :deep(.van-tag--plain) {
  background: #dbeafe;
  color: #075985;
  border: 1px solid #93c5fd;
}
</style>
