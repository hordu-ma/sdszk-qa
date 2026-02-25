<script setup lang="ts">
import { ref, nextTick, onMounted, computed } from "vue";
import { useRoute } from "vue-router";
import { useUserStore } from "../stores/user";
import { getSession, type SessionDetail } from "../api/session";
import { showToast, showFailToast } from "vant";
import type { MessageItem } from "../types";

const route = useRoute();
const userStore = useUserStore();

const sessionId = computed(() => Number(route.params.sessionId));

const messages = ref<MessageItem[]>([]);
const inputValue = ref("");
const sending = ref(false);
const loadingData = ref(true);
const messagesContainer = ref<HTMLElement | null>(null);
const sessionDetail = ref<SessionDetail | null>(null);

const isSessionEnded = computed(() => sessionDetail.value?.status !== "in_progress");

const scrollToBottom = async () => {
  await nextTick();
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

const loadData = async () => {
  loadingData.value = true;
  try {
    const detail = await getSession(sessionId.value);
    sessionDetail.value = detail;

    messages.value = detail.messages.map((m) => ({
      ...m,
      role: m.role as "user" | "assistant" | "system",
    }));

    scrollToBottom();
  } catch (e) {
    showFailToast("加载数据失败");
    console.error(e);
  } finally {
    loadingData.value = false;
  }
};

onMounted(() => {
  loadData();
});

const sendMessage = async () => {
  if (!inputValue.value.trim() || sending.value) return;

  if (isSessionEnded.value) {
    showToast("会话已结束，无法发送消息");
    return;
  }

  const content = inputValue.value.trim();

  messages.value.push({
    id: Date.now(),
    role: "user",
    content,
    tokens: null,
    latency_ms: null,
    created_at: new Date().toISOString(),
  });
  inputValue.value = "";
  scrollToBottom();

  sending.value = true;

  const assistantMsgIndex = messages.value.length;
  messages.value.push({
    id: Date.now() + 1,
    role: "assistant",
    content: "",
    tokens: null,
    latency_ms: null,
    created_at: new Date().toISOString(),
  });

  try {
    const response = await fetch("/api/chat/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: `Bearer ${userStore.token}`,
      },
      body: JSON.stringify({
        session_id: sessionId.value,
        message: content,
      }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => null);
      const errMsg = errData?.detail || response.statusText || "请求失败";
      const assistantMsg = messages.value[assistantMsgIndex];
      if (assistantMsg) {
        assistantMsg.content = "请求失败: " + errMsg;
      }
      showFailToast(errMsg);
      return;
    }

    if (!response.body) {
      const assistantMsg = messages.value[assistantMsgIndex];
      if (assistantMsg) {
        assistantMsg.content = "响应体为空，请稍后重试";
      }
      showFailToast("响应体为空，请稍后重试");
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let shouldStop = false;
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      while (true) {
        const eventEnd = buffer.indexOf("\n\n");
        if (eventEnd === -1) break;

        const eventBlock = buffer.slice(0, eventEnd);
        buffer = buffer.slice(eventEnd + 2);
        const eventLines = eventBlock.split("\n");

        for (const line of eventLines) {
          if (!line.startsWith("data:")) continue;

          const data = line.slice(5).trim();
          if (!data) continue;

          if (data === "[DONE]") {
            shouldStop = true;
            break;
          }

          try {
            const parsed = JSON.parse(data);
            if (parsed.error) {
              const assistantMsg = messages.value[assistantMsgIndex];
              if (assistantMsg) {
                assistantMsg.content = parsed.error;
              }
              showFailToast(parsed.error);
              shouldStop = true;
              break;
            }

            if (parsed.content) {
              const assistantMsg = messages.value[assistantMsgIndex];
              if (assistantMsg) {
                assistantMsg.content += parsed.content;
                scrollToBottom();
              }
            }

            if (parsed.done) {
              shouldStop = true;
              break;
            }
          } catch (_e) {
            // ignore malformed event chunks
          }
        }

        if (shouldStop) break;
      }

      if (shouldStop) break;
    }
  } catch (e) {
    const assistantMsg = messages.value[assistantMsgIndex];
    if (assistantMsg) assistantMsg.content = "网络错误，请重试";
    showFailToast("网络错误，请重试");
  } finally {
    sending.value = false;
    scrollToBottom();
  }
};
</script>

<template>
  <div class="chat-page">
    <van-nav-bar
      :title="sessionDetail?.case_title || '问答会话'"
      left-arrow
      @click-left="$router.back()"
      fixed
      placeholder
    />

    <van-notice-bar
      v-if="isSessionEnded"
      color="#1989fa"
      background="#ecf9ff"
      left-icon="info-o"
    >
      会话已结束，仅供查看
    </van-notice-bar>

    <van-loading v-if="loadingData" class="loading-center" size="24px" vertical>
      加载中...
    </van-loading>

    <div v-else class="message-list" ref="messagesContainer">
      <van-empty v-if="messages.length === 0" description="开始提问吧" />
      <div
        v-for="(msg, index) in messages"
        :key="msg.id || index"
        :class="['message-item', msg.role]"
      >
        <div class="avatar">
          <template v-if="msg.role === 'user'">师</template>
          <template v-else-if="msg.role === 'system'">系</template>
          <template v-else>助</template>
        </div>
        <div class="content">{{ msg.content }}</div>
      </div>
    </div>

    <div class="input-area" v-if="!isSessionEnded">
      <van-field
        v-model="inputValue"
        center
        clearable
        placeholder="请输入问题"
        @keyup.enter="sendMessage"
      >
        <template #button>
          <van-button
            size="small"
            type="primary"
            :loading="sending"
            :disabled="sending || !inputValue.trim()"
            @click="sendMessage"
          >
            发送
          </van-button>
        </template>
      </van-field>
    </div>
  </div>
</template>

<style scoped>
.chat-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #e8f4f8;
}

.loading-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 18px 14px 26px;
}

.message-item {
  display: flex;
  margin-bottom: 22px;
  opacity: 0;
  animation: msgAppear 0.45s ease-out forwards;
}

@keyframes msgAppear {
  0% {
    opacity: 0;
    transform: translateX(-12px);
  }
  100% {
    opacity: 1;
    transform: translateX(0);
  }
}

.message-item.user {
  flex-direction: row-reverse;
  animation: msgAppearRight 0.45s ease-out forwards;
}

@keyframes msgAppearRight {
  0% {
    opacity: 0;
    transform: translateX(12px);
  }
  100% {
    opacity: 1;
    transform: translateX(0);
  }
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: #cbd5e1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  color: #475569;
}

.message-item.user .avatar {
  background: #0369a1;
  color: #e0f2fe;
  margin-left: 11px;
  border: 2px solid #7dd3fc;
}

.message-item.assistant .avatar {
  background: #ea580c;
  color: #ffedd5;
  margin-right: 11px;
  border: 2px solid #fed7aa;
}

.message-item.system {
  justify-content: center;
}

.message-item.system .avatar {
  display: none;
}

.message-item.system .content {
  background: #f1f5f9;
  color: #64748b;
  font-size: 12px;
  max-width: 82%;
  text-align: center;
  padding: 9px 16px;
  border-radius: 14px;
  border: 1px dashed #cbd5e1;
}

.content {
  max-width: 70%;
  background: #ffffff;
  padding: 13px 17px;
  border-radius: 6px 16px 16px 16px;
  word-break: break-word;
  white-space: pre-wrap;
  text-align: left;
  line-height: 1.6;
  font-size: 14.5px;
  border-left: 3px solid #fbbf24;
  box-shadow:
    0 1px 3px rgba(0, 0, 0, 0.12),
    0 1px 2px rgba(0, 0, 0, 0.08);
}

.message-item.user .content {
  background: #0c4a6e;
  color: #e0f2fe;
  border-left: 3px solid #38bdf8;
  border-radius: 16px 6px 16px 16px;
}

.input-area {
  background: #ffffff;
  border-top: 2px solid #cbd5e1;
  padding: 13px 15px;
}

.input-area :deep(.van-field) {
  border-radius: 22px;
  border: 2px solid #cbd5e1;
  background: #f8fafc;
  padding: 9px 18px;
}

.input-area :deep(.van-field:focus-within) {
  border-color: #0284c7;
  background: #ffffff;
}

.input-area :deep(.van-field__control) {
  font-size: 14.5px;
}

.input-area :deep(.van-button--primary) {
  border-radius: 18px;
  padding: 9px 22px;
  background: #0369a1;
  border: none;
  font-weight: 600;
}

.input-area :deep(.van-button--primary:active) {
  background: #075985;
}
</style>
