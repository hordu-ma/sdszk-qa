<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { getSessions, type SessionListItem } from "../api/session";
import { showFailToast } from "vant";

const router = useRouter();
const sessions = ref<SessionListItem[]>([]);
const loading = ref(false);

const loadSessions = async () => {
  loading.value = true;
  try {
    const res = await getSessions();
    sessions.value = res.items;
  } catch (error) {
    showFailToast("加载历史会话失败");
  } finally {
    loading.value = false;
  }
};

const goToChat = (sessionId: number) => {
  router.push(`/chat/${sessionId}`);
};

onMounted(() => {
  loadSessions();
});
</script>

<template>
  <div class="session-list-page">
    <van-nav-bar title="历史会话" left-arrow @click-left="$router.back()" />

    <div class="list-container">
      <van-empty
        v-if="!loading && sessions.length === 0"
        description="暂无历史会话"
      />

      <van-cell-group v-else>
        <van-cell
          v-for="session in sessions"
          :key="session.id"
          :title="session.case_title"
          :label="`状态: ${session.status} | ${new Date(
            session.started_at
          ).toLocaleString()}`"
          is-link
          @click="goToChat(session.id)"
        >
          <template #value>
            <van-tag
              :type="session.status === 'in_progress' ? 'primary' : 'success'"
            >
              {{
                session.status === "in_progress"
                  ? "进行中"
                  : "已结束"
              }}
            </van-tag>
          </template>
        </van-cell>
      </van-cell-group>
    </div>
  </div>
</template>

<style scoped>
.session-list-page {
  background: #fef3c7;
  min-height: 100vh;
}

.list-container {
  padding: 10px 0;
}

.session-list-page :deep(.van-cell-group) {
  background: transparent;
}

.session-list-page :deep(.van-cell) {
  background: #ffffff;
  margin: 10px 16px;
  border-radius: 11px;
  padding: 16px;
  border: 2px solid #fde68a;
  animation: sessionPop 0.4s ease-out backwards;
}

@keyframes sessionPop {
  0% {
    opacity: 0;
    transform: translateX(-20px);
  }
  100% {
    opacity: 1;
    transform: translateX(0);
  }
}

.session-list-page :deep(.van-cell:nth-child(1)) { animation-delay: 0.06s; }
.session-list-page :deep(.van-cell:nth-child(2)) { animation-delay: 0.12s; }
.session-list-page :deep(.van-cell:nth-child(3)) { animation-delay: 0.18s; }
.session-list-page :deep(.van-cell:nth-child(4)) { animation-delay: 0.24s; }

.session-list-page :deep(.van-cell:active) {
  background: #fffbeb;
  border-color: #fbbf24;
}

.session-list-page :deep(.van-cell__title) {
  color: #78350f;
  font-weight: 700;
  font-size: 15px;
}

.session-list-page :deep(.van-cell__label) {
  color: #92400e;
  margin-top: 6px;
  font-size: 12px;
}

.session-list-page :deep(.van-tag) {
  border-radius: 9px;
  padding: 4px 11px;
  font-weight: 600;
  font-size: 11px;
}

.session-list-page :deep(.van-tag--primary) {
  background: #0891b2;
  border: none;
}

.session-list-page :deep(.van-tag--success) {
  background: #059669;
  border: none;
}
</style>
