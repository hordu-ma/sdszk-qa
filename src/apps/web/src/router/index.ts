import { createRouter, createWebHistory } from "vue-router";
import Login from "../views/Login.vue";
import TopicList from "../views/CaseList.vue";
import Chat from "../views/Chat.vue";
import SessionList from "../views/SessionList.vue";
import { useUserStore } from "../stores/user";
import { getUserInfo } from "../api/auth";

function isJwtExpired(token: string): boolean {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return true;

    const payloadBase64Url = parts[1];
    if (!payloadBase64Url) return true;
    const payloadBase64 = payloadBase64Url
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    const padded = payloadBase64.padEnd(
      payloadBase64.length + ((4 - (payloadBase64.length % 4)) % 4),
      "=",
    );
    const payloadJson = atob(padded);
    const payload = JSON.parse(payloadJson) as { exp?: number };
    if (typeof payload.exp !== "number") return true;
    return payload.exp <= Math.floor(Date.now() / 1000);
  } catch {
    return true;
  }
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/",
      redirect: "/topics",
    },
    {
      path: "/login",
      name: "login",
      component: Login,
    },
    {
      path: "/topics",
      name: "topics",
      component: TopicList,
      meta: { requiresAuth: true },
    },
    {
      path: "/chat/:sessionId",
      name: "chat",
      component: Chat,
      meta: { requiresAuth: true },
    },
    {
      path: "/sessions",
      name: "sessions",
      component: SessionList,
      meta: { requiresAuth: true },
    },
  ],
});

router.beforeEach(async (to, _from, next) => {
  const userStore = useUserStore();

  if (!to.meta.requiresAuth) {
    next();
    return;
  }

  if (!userStore.token) {
    next("/login");
    return;
  }

  if (isJwtExpired(userStore.token)) {
    userStore.clearToken();
    next("/login");
    return;
  }

  if (!userStore.userInfo) {
    try {
      const info = await getUserInfo();
      userStore.setUserInfo(info as any);
    } catch (_error) {
      userStore.clearToken();
      next("/login");
      return;
    }
  }

  next();
});

export default router;
