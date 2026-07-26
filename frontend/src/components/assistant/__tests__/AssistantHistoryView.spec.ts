import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AssistantHistoryView from "../AssistantHistoryView.vue";

describe("AssistantHistoryView", () => {
  it("renders sessions and emits the selected id", async () => {
    const wrapper = mount(AssistantHistoryView, {
      props: {
        sessions: [
          {
            sessionId: "session-1",
            title: "学习计划",
            status: "active",
            createdAt: "2026-07-25T10:00:00",
            updatedAt: null,
          },
        ],
        loading: false,
        error: "",
      },
      global: {
        stubs: {
          "el-button": {
            template: "<button><slot /></button>",
          },
          "el-icon": { template: "<i><slot /></i>" },
          "el-empty": { template: "<div>暂无历史会话</div>" },
        },
      },
    });

    expect(wrapper.text()).toContain("学习计划");
    await wrapper.get('[data-testid="session-session-1"]').trigger("click");
    expect(wrapper.emitted("select")?.[0]).toEqual(["session-1"]);
  });
});

describe("AssistantHistoryView 会话管理", () => {
  const sessions = [{
    sessionId: "session-9",
    title: "微积分答疑",
    status: "active",
    createdAt: "2026-07-26T10:00:00",
    updatedAt: "2026-07-26T12:00:00",
  }];

  function mountView() {
    return mount(AssistantHistoryView, {
      props: { sessions, loading: false, error: "" },
      global: {
        stubs: {
          "el-icon": { template: "<i><slot /></i>" },
          "el-button": { template: "<button><slot /></button>" },
          "el-empty": { template: "<div />" },
        },
      },
    });
  }

  it("点击改名图标抛 rename 且不触发 select", async () => {
    const wrapper = mountView();

    await wrapper.get('[data-testid="rename-session-9"]').trigger("click");

    expect(wrapper.emitted("rename")?.[0]).toEqual(["session-9", "微积分答疑"]);
    expect(wrapper.emitted("select")).toBeUndefined();
  });

  it("点击删除图标抛 delete 且不触发 select", async () => {
    const wrapper = mountView();

    await wrapper.get('[data-testid="delete-session-9"]').trigger("click");

    expect(wrapper.emitted("delete")?.[0]).toEqual(["session-9"]);
    expect(wrapper.emitted("select")).toBeUndefined();
  });
});
