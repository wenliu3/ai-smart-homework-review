# 学生作业提交生命周期实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让学生端根据无提交、草稿、正式提交和已批改状态动态展示有效步骤，并把重新提交改为评价结果页中的显式操作。

**架构：** 新建无副作用的生命周期工具统一判断正式提交状态、可见步骤和默认步骤；`useSubmissionManagement` 提供业务权限派生状态；`index.vue` 只维护重新提交交互状态和页面跳转。`SubmittedContent.vue` 负责只读展示最新提交，并通过事件把“重新提交”意图交给父组件。

**技术栈：** Vue 3、TypeScript、Element Plus、Vue Test Utils、Vitest。

---

## 文件职责

- 创建 `frontend/src/views/student/submissions/utils/submissionLifecycle.ts`：提交状态到页面步骤的纯函数映射。
- 创建 `frontend/src/views/student/submissions/utils/__tests__/submissionLifecycle.spec.ts`：覆盖每种状态和重交模式的映射。
- 修改 `frontend/src/views/student/submissions/composables/useSubmissionManagement.ts`：提供 `hasFormalSubmission`、`canResubmit`、`showSubmissionForm`、`showSubmittedContent`。
- 创建 `frontend/src/views/student/submissions/composables/__tests__/useSubmissionManagement.spec.ts`：验证组合式函数对真实状态数据的派生权限。
- 修改 `frontend/src/views/student/submissions/components/SubmittedContent.vue`：展示提交次数并提供可选的重新提交操作。
- 创建 `frontend/src/views/student/submissions/components/__tests__/SubmittedContent.spec.ts`：验证只读内容、提交元信息和重交事件。
- 修改 `frontend/src/views/student/submissions/index.vue`：动态步骤、重新提交模式、取消和成功后的评价页跳转。
- 修改 `frontend/src/views/student/submissions/__tests__/SubmissionWorkspace.spec.ts`：验证页面状态流和编辑器可见性。

### 任务 1：建立提交生命周期纯函数

**文件：**
- 创建：`frontend/src/views/student/submissions/utils/submissionLifecycle.ts`
- 创建：`frontend/src/views/student/submissions/utils/__tests__/submissionLifecycle.spec.ts`

- [ ] **步骤 1：编写失败的状态映射测试**

测试应覆盖以下断言：

```ts
expect(getSubmissionWorkspaceState(undefined, false)).toEqual({
  hasFormalSubmission: false,
  showSubmissionStep: true,
  submissionStepLabel: "提交作业",
  showResultsStep: false,
  resultsStepNumber: null,
  defaultTab: "assignment",
});
expect(getSubmissionWorkspaceState("draft", false).defaultTab).toBe(
  "submission"
);
expect(getSubmissionWorkspaceState("submitted", false)).toMatchObject({
  hasFormalSubmission: true,
  showSubmissionStep: false,
  showResultsStep: true,
  resultsStepNumber: 2,
  defaultTab: "results",
});
expect(getSubmissionWorkspaceState("ai_reviewed", true)).toMatchObject({
  showSubmissionStep: true,
  submissionStepLabel: "重新提交",
  resultsStepNumber: 3,
});
expect(getSubmissionWorkspaceState("teacher_reviewed", false).defaultTab).toBe(
  "results"
);
```

- [ ] **步骤 2：运行测试并确认红灯**

运行：

```powershell
cd frontend
npm test -- --run src/views/student/submissions/utils/__tests__/submissionLifecycle.spec.ts
```

预期：FAIL，提示 `submissionLifecycle` 模块或 `getSubmissionWorkspaceState` 不存在。

- [ ] **步骤 3：实现最小状态映射**

实现公开类型和函数：

```ts
import type { Submission } from "@/api/submissions";

export type SubmissionStatus = Submission["status"] | null | undefined;
export type SubmissionTab = "assignment" | "submission" | "results";

export interface SubmissionWorkspaceState {
  hasFormalSubmission: boolean;
  showSubmissionStep: boolean;
  submissionStepLabel: "提交作业" | "继续提交" | "重新提交";
  showResultsStep: boolean;
  resultsStepNumber: 2 | 3 | null;
  defaultTab: SubmissionTab;
}

export const isFormalSubmissionStatus = (status: SubmissionStatus) =>
  status === "submitted" ||
  status === "ai_reviewed" ||
  status === "teacher_reviewed";

export const getSubmissionWorkspaceState = (
  status: SubmissionStatus,
  isResubmitting: boolean
): SubmissionWorkspaceState => {
  const hasFormalSubmission = isFormalSubmissionStatus(status);
  if (!hasFormalSubmission) {
    return {
      hasFormalSubmission: false,
      showSubmissionStep: true,
      submissionStepLabel: status === "draft" ? "继续提交" : "提交作业",
      showResultsStep: false,
      resultsStepNumber: null,
      defaultTab: status === "draft" ? "submission" : "assignment",
    };
  }
  return {
    hasFormalSubmission: true,
    showSubmissionStep: isResubmitting,
    submissionStepLabel: "重新提交",
    showResultsStep: true,
    resultsStepNumber: isResubmitting ? 3 : 2,
    defaultTab: "results",
  };
};
```

- [ ] **步骤 4：运行测试并确认绿灯**

运行同一条 Vitest 命令，预期该测试文件全部 PASS。

- [ ] **步骤 5：提交任务 1**

```powershell
git add frontend/src/views/student/submissions/utils
git commit -m "test: define student submission lifecycle states"
```

### 任务 2：提供正式提交与重交权限状态

**文件：**
- 修改：`frontend/src/views/student/submissions/composables/useSubmissionManagement.ts`
- 创建：`frontend/src/views/student/submissions/composables/__tests__/useSubmissionManagement.spec.ts`

- [ ] **步骤 1：编写失败的组合式函数权限测试**

使用一个 Vue 测试组件调用 `useSubmissionManagement()`，取得返回对象后直接设置 `submissionData`。为测试数据工厂提供未来和过去截止时间，并断言：

```ts
const makeDetail = (
  submissionStatus: Submission["status"] | null,
  assignmentOverrides: Partial<Assignment> = {}
): MySubmissionDetail => ({
  assignment: {
    id: "21",
    title: "语料库分析",
    description: "",
    attachments: [],
    allowAttachments: true,
    dueDate: "2099-08-05T18:00:00",
    maxScore: 100,
    teacherName: "张老师",
    aiRule: null,
    status: "published",
    ...assignmentOverrides,
  },
  submission: submissionStatus
    ? {
        id: "8",
        content: "<p>已提交正文</p>",
        attachments: [],
        wordCount: 6,
        status: submissionStatus,
        submittedAt: "2026-08-01T12:00:00",
        updatedAt: "2026-08-01T12:00:00",
        createdAt: "2026-08-01T12:00:00",
        isDraft: submissionStatus === "draft",
        submissionCount: 1,
      }
    : null,
  aiReview: null,
  teacherReview: null,
});

management.submissionData.value = makeDetail("submitted");
expect(management.hasFormalSubmission.value).toBe(true);
expect(management.showSubmissionForm.value).toBe(false);
expect(management.showSubmittedContent.value).toBe(true);
expect(management.canResubmit.value).toBe(true);

management.submissionData.value = makeDetail("teacher_reviewed");
expect(management.canResubmit.value).toBe(false);

management.submissionData.value = makeDetail("submitted", {
  dueDate: "2000-01-01T00:00:00",
});
expect(management.canResubmit.value).toBe(false);

management.submissionData.value = makeDetail("ai_reviewed", {
  status: "terminated",
});
expect(management.canResubmit.value).toBe(false);
```

测试 mock 固定 `useRoute()` 返回 `assignmentId=21`、`classId=4`；`useAiReviewPolling()` 返回 `ref(false)`、`ref(0)` 和空操作函数，避免启动真实轮询。

- [ ] **步骤 2：运行组合式函数测试并确认红灯**

```powershell
cd frontend
npm test -- --run src/views/student/submissions/composables/__tests__/useSubmissionManagement.spec.ts
```

预期：FAIL，因为生产组合式函数尚未导出 `hasFormalSubmission` 和 `canResubmit`，且正式提交仍被判断为显示编辑器。

- [ ] **步骤 3：实现组合式函数派生状态**

在 `isOverdue` 定义后增加：

```ts
const hasFormalSubmission = computed(() =>
  isFormalSubmissionStatus(submissionData.value?.submission?.status)
);

const canResubmit = computed(() => {
  const status = submissionData.value?.submission?.status;
  const assignment = submissionData.value?.assignment;
  return (
    (status === "submitted" || status === "ai_reviewed") &&
    !isOverdue.value &&
    assignment?.status !== "terminated"
  );
});

const showSubmissionForm = computed(() => !hasFormalSubmission.value);
const showSubmittedContent = computed(() => hasFormalSubmission.value);
```

删除原来仅以 `teacher_reviewed` 判断表单和只读内容的两个计算属性，导入 `isFormalSubmissionStatus`，并在返回值中导出 `hasFormalSubmission` 和 `canResubmit`。

- [ ] **步骤 4：运行组合式函数测试并确认当前任务断言通过**

运行同一条组合式函数测试命令，预期全部 PASS。

- [ ] **步骤 5：提交任务 2**

```powershell
git add frontend/src/views/student/submissions/composables/useSubmissionManagement.ts frontend/src/views/student/submissions/composables/__tests__/useSubmissionManagement.spec.ts
git commit -m "refactor: expose student resubmission permissions"
```

### 任务 3：让已提交内容承载重新提交入口

**文件：**
- 修改：`frontend/src/views/student/submissions/components/SubmittedContent.vue`
- 创建：`frontend/src/views/student/submissions/components/__tests__/SubmittedContent.spec.ts`

- [ ] **步骤 1：编写失败的组件测试**

挂载一个 `submissionCount: 2` 的已提交记录并断言：

```ts
const submission: Submission = {
  id: "8",
  content: "<p>已提交正文</p>",
  attachments: [],
  wordCount: 6,
  status: "submitted",
  submittedAt: "2026-08-01T12:00:00",
  updatedAt: "2026-08-01T12:00:00",
  createdAt: "2026-08-01T12:00:00",
  isDraft: false,
  submissionCount: 2,
};
const wrapper = mount(SubmittedContent, {
  props: { submission, canResubmit: true },
  global: {
    stubs: {
      "el-button": { template: "<button @click='$emit(\"click\")'><slot /></button>" },
      AssignmentAttachmentList: true,
    },
  },
});

expect(wrapper.text()).toContain("第 2 次提交");
expect(wrapper.text()).toContain("重新提交");
await wrapper.get('[data-testid="resubmit-button"]').trigger("click");
expect(wrapper.emitted("resubmit")).toHaveLength(1);
```

再挂载 `canResubmit: false`，断言不存在 `[data-testid="resubmit-button"]`。

- [ ] **步骤 2：运行测试并确认红灯**

```powershell
cd frontend
npm test -- --run src/views/student/submissions/components/__tests__/SubmittedContent.spec.ts
```

预期：FAIL，因为组件尚未声明 `canResubmit`、提交次数文案和 `resubmit` 事件。

- [ ] **步骤 3：实现只读摘要操作区**

组件 props 与事件使用：

```ts
const props = withDefaults(
  defineProps<{
    submission?: Submission | null;
    canResubmit?: boolean;
  }>(),
  { submission: null, canResubmit: false }
);
const emit = defineEmits<{ (event: "resubmit"): void }>();
```

标题区显示 `第 {{ submission?.submissionCount || 1 }} 次提交` 和提交时间；仅当 `canResubmit` 时渲染：

```vue
<el-button
  v-if="canResubmit"
  data-testid="resubmit-button"
  type="primary"
  plain
  @click="emit('resubmit')"
>
  重新提交
</el-button>
```

按钮与元信息在窄屏下换行，不改变正文和附件的只读展示。

- [ ] **步骤 4：运行组件测试并确认绿灯**

运行同一条 SubmittedContent 测试命令，预期全部 PASS。

- [ ] **步骤 5：提交任务 3**

```powershell
git add frontend/src/views/student/submissions/components/SubmittedContent.vue frontend/src/views/student/submissions/components/__tests__/SubmittedContent.spec.ts
git commit -m "feat: add explicit student resubmission entry"
```

### 任务 4：实现动态步骤和重新提交模式

**文件：**
- 修改：`frontend/src/views/student/submissions/index.vue`
- 修改：`frontend/src/views/student/submissions/__tests__/SubmissionWorkspace.spec.ts`

- [ ] **步骤 1：编写失败的工作区状态流测试**

测试至少覆盖：

```ts
const getSubmissionDetail = vi.hoisted(() => vi.fn());

// composables mock 中每次挂载都使用当前工厂返回值创建 ref，
// 并根据 status 返回 hasFormalSubmission、canResubmit 等计算属性。
const mountWorkspace = (detail: MySubmissionDetail) => {
  getSubmissionDetail.mockReturnValue(detail);
  return shallowMount(SubmissionWorkspace, {
    global: {
      stubs: {
        "el-tabs": { template: "<div><slot /></div>" },
        "el-tab-pane": { template: "<section><slot name='label' /></section>" },
        SubmissionForm: {
          template: '<div data-testid="submission-form" />',
        },
        SubmittedContent: {
          props: ["canResubmit"],
          emits: ["resubmit"],
          template:
            '<div data-testid="submitted-content"><button v-if="canResubmit" data-testid="resubmit-button" @click="$emit(\'resubmit\')">重新提交</button></div>',
        },
        ReviewResults: { template: '<div data-testid="review-results" />' },
      },
      directives: { loading: () => undefined },
    },
  });
};

// 无提交：只有作业详情和提交作业
let wrapper = mountWorkspace(makeDetail(null));
expect(wrapper.text()).toContain("提交作业");
expect(wrapper.text()).not.toContain("评价结果");

// 草稿：显示继续提交，不显示评价结果
wrapper = mountWorkspace(makeDetail("draft"));
expect(wrapper.text()).toContain("继续提交");
expect(wrapper.text()).not.toContain("评价结果");

// submitted：默认只有作业详情、评价结果，不挂载编辑器
wrapper = mountWorkspace(makeDetail("submitted"));
expect(wrapper.text()).toContain("评价结果");
expect(wrapper.find('[data-testid="submission-form"]').exists()).toBe(false);
expect(wrapper.find('[data-testid="submitted-content"]').exists()).toBe(true);

// 显式重交：点击后才出现重新提交编辑器，取消后消失
await wrapper.get('[data-testid="resubmit-button"]').trigger("click");
expect(wrapper.text()).toContain("重新提交");
expect(wrapper.find('[data-testid="submission-form"]').exists()).toBe(true);
await wrapper.get('[data-testid="cancel-resubmit-button"]').trigger("click");
expect(wrapper.find('[data-testid="submission-form"]').exists()).toBe(false);
```

教师已批改、已截止、已终止三种数据均断言没有重交按钮。

- [ ] **步骤 2：运行工作区测试并确认红灯**

运行：

```powershell
cd frontend
npm test -- --run src/views/student/submissions/__tests__/SubmissionWorkspace.spec.ts
```

预期：FAIL，现有三个步骤无条件渲染，且正式提交默认仍进入提交编辑区。

- [ ] **步骤 3：实现动态步骤**

在 `index.vue` 中增加：

```ts
const isResubmitting = ref(false);
const workspaceState = computed(() =>
  getSubmissionWorkspaceState(
    submissionData.value?.submission?.status,
    isResubmitting.value
  )
);
const showEditableSubmission = computed(
  () => !hasFormalSubmission.value || isResubmitting.value
);

const beginResubmission = () => {
  if (!canResubmit.value) return;
  isResubmitting.value = true;
  activeTab.value = "submission";
};

const cancelResubmission = () => {
  isResubmitting.value = false;
  activeTab.value = "results";
};
```

模板按 `workspaceState.showSubmissionStep` 和 `workspaceState.showResultsStep` 控制两个步骤，标签使用 `submissionStepLabel` 和连续的 `resultsStepNumber`。提交表单只在 `showEditableSubmission` 时挂载；重新提交模式在操作栏增加带 `data-testid="cancel-resubmit-button"` 的“取消重交”按钮。

在评价结果 section 顶部挂载：

```vue
<SubmittedContent
  v-if="hasFormalSubmission"
  :submission="submissionData.submission"
  :can-resubmit="canResubmit"
  @resubmit="beginResubmission"
/>
```

- [ ] **步骤 4：修正初始化与提交成功流转**

`initializeTab()` 在非重交模式下使用 `workspaceState.defaultTab`；正式提交统一进入 `results`。正式提交或重新提交 API 成功并完成 `loadData()` 后执行：

```ts
isResubmitting.value = false;
showAiProcessingFullscreen.value = false;
clearAiTimeout();
activeTab.value = "results";
```

失败和取消确认时不退出重新提交模式。若数据刷新后 `canResubmit` 变为 `false`，退出重交并返回评价结果。

- [ ] **步骤 5：运行工作区与提交组件测试并确认绿灯**

```powershell
cd frontend
npm test -- --run src/views/student/submissions/__tests__/SubmissionWorkspace.spec.ts src/views/student/submissions/components/__tests__/SubmittedContent.spec.ts src/views/student/submissions/components/__tests__/SubmissionForm.spec.ts src/views/student/submissions/components/__tests__/ReviewResults.spec.ts
```

预期：所有相关测试 PASS。

- [ ] **步骤 6：提交任务 4**

```powershell
git add frontend/src/views/student/submissions/index.vue frontend/src/views/student/submissions/__tests__/SubmissionWorkspace.spec.ts
git commit -m "feat: align student submission workspace with lifecycle"
```

### 任务 5：完整验证与真实浏览器验收

**文件：**
- 验证：`frontend/`

- [ ] **步骤 1：运行完整前端测试**

```powershell
cd frontend
npm test
```

预期：所有测试文件和测试用例通过，0 failures。

- [ ] **步骤 2：运行类型检查与生产构建**

```powershell
npx vue-tsc --noEmit
npm run build-only
```

预期：两条命令退出码均为 0。若构建只改变 `auto-imports.d.ts` 或 `components.d.ts` 的换行，恢复这两个生成文件，不提交换行噪音。

- [ ] **步骤 3：检查差异与工作区**

```powershell
git diff --check
git status --short
```

预期：无空白错误；仅有计划内文件或工作区干净。

- [ ] **步骤 4：重建 Compose 前端并检查健康状态**

```powershell
docker compose --env-file 'D:\Pychrom Project\ai-smart-homework-review\.env.docker' -p ai-smart-homework-review up -d --build frontend
docker compose --env-file 'D:\Pychrom Project\ai-smart-homework-review\.env.docker' -p ai-smart-homework-review ps
```

预期：`ai-review-frontend` healthy，`http://localhost/` 返回 200。

- [ ] **步骤 5：按生命周期场景进行浏览器验收**

使用本地学生账号进入目标作业并检查：

1. 无提交/草稿时没有“评价结果”步骤。
2. 正式提交后自动进入评价结果，编辑器和上传入口消失。
3. 评价页显示只读正文、附件、提交次数和“重新提交”。
4. 点击“重新提交”后编辑器出现且带入当前内容；取消后返回评价结果。
5. 完成重交后再次回到评价结果并显示新一轮进度。
6. 教师已批改、已截止或已终止时没有重新提交入口。
7. 页面无横向溢出，控制台无新增错误。

- [ ] **步骤 6：提交验证产生的必要调整**

若浏览器验收发现并修复计划范围内问题，重新运行相关测试并提交：

```powershell
git add frontend/src/views/student/submissions
git commit -m "fix: close student submission lifecycle review gaps"
```

若没有必要调整，不创建空提交。
