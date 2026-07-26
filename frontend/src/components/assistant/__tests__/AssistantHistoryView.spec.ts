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
