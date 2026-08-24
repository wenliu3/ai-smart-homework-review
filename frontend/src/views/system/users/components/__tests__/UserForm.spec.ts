import ElementPlus from "element-plus";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi, beforeEach } from "vitest";

const updateUserMock = vi.fn().mockResolvedValue({ _id: "1", role: "teacher" });
const createUserMock = vi.fn().mockResolvedValue({ _id: "2" });
const getUserMock = vi.fn().mockResolvedValue({
  _id: "1",
  username: "s001",
  email: "s001@school.edu",
  name: "学生一",
  role: "student",
  studentId: "2024001",
  phone: "",
  status: "active",
});

vi.mock("@/api/user", () => ({
  getUser: (...args: unknown[]) => getUserMock(...(args as [string])),
  updateUser: (...args: unknown[]) => updateUserMock(...(args as [string, object])),
  createUser: (...args: unknown[]) => createUserMock(...(args as [object])),
}));

// 回归保护：角色修改不得再触发多角色分配接口
const assignRolesToUserMock = vi.fn();
const getRoleListMock = vi.fn();
vi.mock("@/api/user-role", () => ({
  assignRolesToUser: (...args: unknown[]) => assignRolesToUserMock(...args),
}));
vi.mock("@/api/role", () => ({
  getRoleList: (...args: unknown[]) => getRoleListMock(...args),
}));

import UserForm from "../UserForm.vue";

async function mountForm() {
  const wrapper = mount(UserForm, {
    global: { plugins: [ElementPlus] },
  });
  await wrapper.vm.openForm("edit", "1");
  await flushPromises();
  return wrapper;
}

/** 点击对话框底部的提交（创建/保存）按钮 */
async function clickSubmit(wrapper: ReturnType<typeof mount>) {
  const submitBtn = wrapper
    .findAll("button")
    .find((b) => ["创建", "保存", "创 建", "保 存"].includes(b.text().trim()));
  expect(submitBtn, "未找到提交按钮").toBeDefined();
  await submitBtn!.trigger("click");
  await flushPromises();
}

describe("UserForm 角色修改", () => {
  beforeEach(() => {
    updateUserMock.mockClear();
    createUserMock.mockClear();
    getUserMock.mockClear();
    assignRolesToUserMock.mockClear();
    getRoleListMock.mockClear();
  });

  it("编辑用户修改角色时只发送一个 PATCH 请求，不调用角色分配接口", async () => {
    const wrapper = await mountForm();

    expect(getUserMock).toHaveBeenCalledWith("1");

    // 把角色从 student 改为 teacher
    const select = wrapper.findComponent({ name: "ElSelect" });
    expect(select.exists()).toBe(true);
    select.vm.$emit("update:modelValue", "teacher");
    await flushPromises();

    await clickSubmit(wrapper);

    expect(updateUserMock).toHaveBeenCalledTimes(1);
    expect(updateUserMock).toHaveBeenCalledWith(
      "1",
      expect.objectContaining({ role: "teacher" })
    );
    // 单角色设计：role 随 PATCH 直接生效，禁止再调多角色分配接口
    expect(assignRolesToUserMock).not.toHaveBeenCalled();
    expect(getRoleListMock).not.toHaveBeenCalled();
    // 非学生角色不携带学号
    const payload = updateUserMock.mock.calls[0][1] as Record<string, unknown>;
    expect(payload.studentId).toBeUndefined();
  });

  it("编辑用户不改角色时同样只发送一个 PATCH 请求", async () => {
    const wrapper = await mountForm();

    await clickSubmit(wrapper);

    expect(updateUserMock).toHaveBeenCalledTimes(1);
    expect(updateUserMock).toHaveBeenCalledWith(
      "1",
      expect.objectContaining({ role: "student", studentId: "2024001" })
    );
    expect(assignRolesToUserMock).not.toHaveBeenCalled();
  });
});
