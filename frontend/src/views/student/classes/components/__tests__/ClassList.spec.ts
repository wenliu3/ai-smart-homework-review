import { flushPromises, mount } from "@vue/test-utils";
import { ref } from "vue";
import { describe, expect, it, vi } from "vitest";

const getClassList = vi.hoisted(() => vi.fn());
vi.mock("@/api/classes", () => ({ getClassList }));

import ClassList from "../ClassList.vue";

const mountClassList = () =>
  mount(ClassList, {
    global: {
      provide: {
        selectedClassId: ref<string | null>(null),
        setSelectedClass: vi.fn(),
        showJoinDialog: ref(false),
      },
      stubs: {
        "el-button": { template: "<button><slot /></button>" },
        "el-card": { template: "<article><slot /></article>" },
        "el-empty": true,
        "el-icon": { template: "<i><slot /></i>" },
        "el-input": { template: "<input />" },
        "el-skeleton": true,
        "el-tag": { template: "<span><slot /></span>" },
        "el-tooltip": { template: "<span><slot /></span>" },
      },
    },
  });

describe("ClassList", () => {
  it("renders the class name once and keeps the gradient accent decorative", async () => {
    getClassList.mockResolvedValue({
      items: [
        {
          _id: "3",
          name: "自然语言处理（NLP）",
          teacherName: "边国维",
          studentCount: 32,
          status: "active",
        },
      ],
      total: 1,
    });

    const first = mountClassList();
    await flushPromises();
    const firstAccent = first.get(".class-card__accent");
    const firstStyle = firstAccent.attributes("style");

    const second = mountClassList();
    await flushPromises();
    const secondStyle = second.get(".class-card__accent").attributes("style");

    expect(first.text().match(/自然语言处理（NLP）/g)).toHaveLength(1);
    expect(firstAccent.text()).toBe("");
    expect(firstAccent.attributes("aria-hidden")).toBe("true");
    expect(firstStyle).toContain("linear-gradient");
    expect(secondStyle).toBe(firstStyle);
  });
});
