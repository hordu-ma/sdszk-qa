<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { showToast } from "vant";
import { useUserStore } from "../stores/user";
import { login, getUserInfo } from "../api/auth";

const router = useRouter();
const userStore = useUserStore();

const username = ref("");
const password = ref("");
const loading = ref(false);

const onSubmit = async () => {
  if (!username.value || !password.value) {
    showToast("请输入用户名和密码");
    return;
  }

  loading.value = true;
  try {
    const res: any = await login({
      username: username.value,
      password: password.value,
    });

    // 假设 res 就是 Token 对象，或者 res.access_token 存在
    // 这里需要根据 request.ts 的响应拦截器调整
    // request.ts 返回 response.data
    // 如果 login 接口只返回 token
    userStore.setToken(res.access_token);

    // 获取用户信息
    const userRes: any = await getUserInfo();
    userStore.setUserInfo(userRes);

    showToast("登录成功");
    router.push("/");
  } catch (error) {
    console.error(error);
  } finally {
    loading.value = false;
  }
};
</script>

<template>
  <div class="login-page">
    <div class="header">
      <h2>鲁韵思政</h2>
      <p>思政教学设计与教研问答系统</p>
    </div>

    <van-form @submit="onSubmit">
      <van-cell-group inset>
        <van-field
          v-model="username"
          name="username"
          label="用户名"
          placeholder="请输入用户名"
          :rules="[{ required: true, message: '请填写用户名' }]"
        />
        <van-field
          v-model="password"
          type="password"
          name="password"
          label="密码"
          placeholder="请输入密码"
          :rules="[{ required: true, message: '请填写密码' }]"
        />
      </van-cell-group>
      <div style="margin: 30px 16px">
        <van-button
          round
          block
          type="primary"
          native-type="submit"
          :loading="loading"
        >
          登录
        </van-button>
      </div>
    </van-form>
  </div>
</template>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  background: #e0f2fe;
  padding: 0 20px;
}

.header {
  text-align: center;
  margin-bottom: 45px;
  animation: headerFade 0.8s ease-out;
}

@keyframes headerFade {
  0% {
    opacity: 0;
    transform: translateY(-25px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

.header h2 {
  margin-bottom: 8px;
  color: #0c4a6e;
  font-size: 28px;
  font-weight: 800;
  letter-spacing: 1px;
}

.header p {
  color: #0369a1;
  font-size: 15px;
  font-weight: 500;
}

.login-page :deep(.van-cell-group--inset) {
  margin: 0;
  border-radius: 14px;
  overflow: hidden;
  border: 2px solid #bae6fd;
  animation: formSlide 0.8s ease-out 0.2s backwards;
}

@keyframes formSlide {
  0% {
    opacity: 0;
    transform: translateY(30px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-page :deep(.van-cell) {
  padding: 16px;
  background: #ffffff;
}

.login-page :deep(.van-field__label) {
  color: #0c4a6e;
  font-weight: 600;
  width: 70px;
}

.login-page :deep(.van-field__control) {
  color: #0369a1;
}

.login-page :deep(.van-button) {
  height: 48px;
  font-size: 16px;
  font-weight: 700;
  background: #0369a1;
  border: none;
  animation: btnPop 0.8s ease-out 0.4s backwards;
}

@keyframes btnPop {
  0% {
    opacity: 0;
    transform: scale(0.85);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

.login-page :deep(.van-button:active) {
  background: #075985;
  transform: scale(0.96);
}
</style>
