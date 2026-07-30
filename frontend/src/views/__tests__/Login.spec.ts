import ElementPlus from "element-plus";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";
import { createStore } from "vuex";
import { describe, expect, it, vi } from "vitest";

import Login from "../Login.vue";

async function mountLogin() {
  const loginAction = vi.fn().mockResolvedValue({
    mustChangePassword: false,
    user: { role: "teacher" },
  });
  const store = createStore({
    modules: {
      user: {
        namespaced: true,
        actions: { login: loginAction },
      },
    },
  });
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/login", component: Login },
      { path: "/dashboard", component: { template: "<div>dashboard</div>" } },
    ],
  });
  await router.push("/login");
  await router.isReady();
  const wrapper = mount(Login, {
    global: { plugins: [store, router, ElementPlus] },
  });
  return { wrapper, loginAction };
}

describe("Login", () => {
  it("只显示一个统一账号输入，不显示登录方式选择", async () => {
    const { wrapper } = await mountLogin();

    expect(wrapper.find('[data-testid="login-account"]').exists()).toBe(true);
    expect(wrapper.text()).not.toContain("登录方式");
    expect(
      wrapper
        .find('[data-testid="login-account"] input')
        .attributes("placeholder")
    ).toBe("请输入用户名、邮箱或学号");
  });

  it("去除账号首尾空白后发送统一登录字段", async () => {
    const { wrapper, loginAction } = await mountLogin();
    await wrapper
      .find('[data-testid="login-account"] input')
      .setValue("  teacher  ");
    await wrapper
      .find('[data-testid="login-password"] input')
      .setValue("123456789");
    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(loginAction).toHaveBeenCalledWith(expect.anything(), {
      usernameOrEmailOrStudentId: "teacher",
      password: "123456789",
      rememberMe: true,
    });
  });
});
