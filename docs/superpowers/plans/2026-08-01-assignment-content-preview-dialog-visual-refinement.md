# 教师端作业内容预览弹窗视觉优化实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 将教师端作业内容预览弹窗升级为白色清爽文档布局和清透蓝配色，同时确保正文按 WangEditor 保存的安全 HTML 原样呈现。

**架构：** 保持现有详情页数据流和 `AssignmentContentPreviewDialog.vue` 组件边界不变。正文继续经过 DOMPurify 后一次性传给 `v-html`，通过复用 `editor-content-view` 回显规则保证格式一致；视觉优化仅发生在弹窗标题、时间信息、章节标题、附件和底部操作区。

**技术栈：** Vue 3、TypeScript、Element Plus、WangEditor 回显 CSS、DOMPurify、Vue Test Utils、Vitest、Docker Compose。

---

## 文件结构

- 修改：`frontend/src/views/teacher/assignments/detail/components/AssignmentContentPreviewDialog.vue`
  - 保持富文本净化和附件下载逻辑。
  - 增加自定义标题区、时间信息条、章节编号和清透蓝视觉样式。
  - 将正文容器接入现有 `editor-content-view` 回显规则。
- 修改：`frontend/src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts`
  - 增加富文本 DOM 顺序、格式保留和危险内容过滤测试。
  - 增加方案 A 视觉结构的组件测试。
- 不修改：`frontend/src/views/teacher/assignments/detail/index.vue`
  - 现有弹窗开关和 `assignmentDetail` 数据传递已经满足需求。
- 不修改：后端接口、数据库模型和 WangEditor 编辑组件。

### 任务 1：锁定富文本忠实呈现行为

**文件：**

- 修改：`frontend/src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts`
- 修改：`frontend/src/views/teacher/assignments/detail/components/AssignmentContentPreviewDialog.vue`

- [ ] **步骤 1：编写富文本忠实性失败测试**

在测试文件中增加代表性 WangEditor HTML：

```ts
const richDescription = `
  <h2>实验说明</h2>
  <p style="text-align: center; color: rgb(79, 115, 232);">
    <strong>保留格式</strong>
  </p>
  <p><br></p>
  <p>第一段</p>
  <blockquote>引用内容</blockquote>
  <ol><li>第一项</li><li><em>第二项</em></li></ol>
  <pre><code>const answer = 42;</code></pre>
  <table><tbody><tr><td>单元格</td></tr></tbody></table>
  <img src="/uploads/example.png" onerror="window.hacked = true">
  <script>window.hacked = true</script>
`;
```

新增测试：

```ts
it("按编辑器 HTML 原顺序呈现安全富文本，不做正文重排", () => {
  const wrapper = mountDialog(
    createAssignmentDetail({ description: richDescription })
  );

  const content = wrapper.get(".assignment-description");

  expect(content.classes()).toContain("editor-content-view");
  expect(content.find("h2").text()).toBe("实验说明");
  expect(content.find("p[style]").attributes("style")).toContain(
    "text-align: center"
  );
  expect(content.find("strong").text()).toBe("保留格式");
  expect(content.findAll("p")[1].html()).toContain("<br>");
  expect(content.find("blockquote").text()).toBe("引用内容");
  expect(content.findAll("ol > li").map((item) => item.text())).toEqual([
    "第一项",
    "第二项",
  ]);
  expect(content.find("pre code").text()).toBe("const answer = 42;");
  expect(content.find("table td").text()).toBe("单元格");
  expect(content.find("img").attributes("onerror")).toBeUndefined();
  expect(content.find("script").exists()).toBe(false);
  expect(content.find(".generated-summary").exists()).toBe(false);
  expect(content.find(".generated-callout").exists()).toBe(false);
});
```

- [ ] **步骤 2：运行测试并确认红灯**

运行：

```bash
cd frontend
npx vitest run src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts
```

预期：测试失败，原因是 `.assignment-description` 尚未包含 `editor-content-view` 回显类。

- [ ] **步骤 3：接入现有 WangEditor 回显规则**

将正文容器修改为：

```vue
<div
  v-if="sanitizedDescription"
  class="assignment-description editor-content-view"
  v-html="sanitizedDescription"
></div>
```

保留现有净化逻辑，不增加任何正文解析或转换：

```ts
const sanitizedDescription = computed(() =>
  DOMPurify.sanitize(props.assignmentDetail?.description || "", {
    USE_PROFILES: { html: true },
  })
);
```

在组件局部样式中重置全局回显类的容器外观，但不覆盖其子节点格式：

```css
.assignment-description.editor-content-view {
  min-height: 48px;
  margin: 0;
  padding: 0;
  overflow-x: visible;
  overflow-wrap: anywhere;
  border: 0;
  border-radius: 0;
}

.assignment-description :deep(img) {
  max-width: 100%;
  height: auto;
}

.assignment-description :deep(pre) {
  max-width: 100%;
  overflow-x: auto;
}
```

- [ ] **步骤 4：运行目标测试并确认绿灯**

运行同一步骤 2 的 Vitest 命令。

预期：富文本格式、节点顺序、安全过滤、空状态和关闭事件测试全部通过。

- [ ] **步骤 5：检查并提交任务 1**

```bash
git diff --check
git add frontend/src/views/teacher/assignments/detail/components/AssignmentContentPreviewDialog.vue frontend/src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts
git commit -m "fix: 忠实呈现作业富文本内容（任务 1/3）"
```

### 任务 2：实现方案 A 清透蓝视觉结构

**文件：**

- 修改：`frontend/src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts`
- 修改：`frontend/src/views/teacher/assignments/detail/components/AssignmentContentPreviewDialog.vue`

- [ ] **步骤 1：扩展 Dialog 测试替身以渲染自定义头部**

将 `DialogStub` 模板改为：

```ts
const DialogStub = defineComponent({
  props: {
    modelValue: Boolean,
    width: String,
    showClose: Boolean,
  },
  emits: ["update:modelValue"],
  template: `
    <section v-if="modelValue" data-testid="preview-dialog">
      <header><slot name="header" /></header>
      <slot />
      <footer><slot name="footer" /></footer>
    </section>
  `,
});
```

- [ ] **步骤 2：编写方案 A 结构失败测试**

新增测试：

```ts
it("按清爽文档布局展示标题、时间、章节和只读操作区", () => {
  const wrapper = mountDialog(createAssignmentDetail());

  const dialog = wrapper.getComponent(DialogStub);
  expect(dialog.props("width")).toBe("min(880px, 92vw)");
  expect(dialog.props("showClose")).toBe(false);
  expect(wrapper.get(".preview-kicker").text()).toContain("作业内容");
  expect(wrapper.get(".preview-dialog-title").text()).toContain(
    "实验2：神雕侠侣语料库分析"
  );
  expect(wrapper.get(".preview-class-list").text()).toContain(
    "自然语言处理 (NLP)"
  );
  expect(wrapper.findAll(".preview-time-item")).toHaveLength(2);
  expect(wrapper.findAll(".content-section-index").map((item) => item.text()))
    .toEqual(["01", "02"]);
  expect(wrapper.get(".read-only-hint").text()).toContain("原样显示");
  expect(wrapper.get('[data-testid="close-preview"]').classes())
    .toContain("preview-close-button");
});
```

- [ ] **步骤 3：运行测试并确认红灯**

运行：

```bash
cd frontend
npx vitest run src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts
```

预期：新测试失败，缺少自定义标题区、时间信息条、章节序号和底部提示。

- [ ] **步骤 4：实现自定义标题区和时间信息条**

调整 `<el-dialog>`：

```vue
<el-dialog
  :model-value="modelValue"
  width="min(880px, 92vw)"
  class="assignment-content-preview-dialog"
  :show-close="false"
  destroy-on-close
  append-to-body
  aria-label="作业内容"
  @update:model-value="emit('update:modelValue', $event)"
>
  <template #header>
    <div class="preview-dialog-header">
      <div class="preview-dialog-heading">
        <span class="preview-kicker">
          <el-icon><Reading /></el-icon>
          作业内容
        </span>
        <h2 class="preview-dialog-title">{{ assignmentDetail?.title }}</h2>
        <div class="preview-class-list">
          <el-icon><User /></el-icon>
          <template v-if="assignmentDetail?.classes?.length">
            <span
              v-for="classItem in assignmentDetail.classes"
              :key="classItem.id"
            >
              {{ classItem.name }}
            </span>
          </template>
          <span v-else>暂无关联班级</span>
        </div>
      </div>
      <div class="preview-header-actions">
        <el-tag :type="statusType" effect="light">{{ statusText }}</el-tag>
        <el-button
          class="preview-icon-close"
          :icon="Close"
          circle
          text
          aria-label="关闭"
          @click="closeDialog"
        />
      </div>
    </div>
  </template>

  <div v-if="assignmentDetail" class="preview-content">
    <div class="preview-time-panel">
      <div class="preview-time-item">...</div>
      <el-icon class="preview-time-arrow"><Right /></el-icon>
      <div class="preview-time-item">...</div>
    </div>
    <!-- 章节正文与附件 -->
  </div>
</el-dialog>
```

图标从 `@element-plus/icons-vue` 引入：`Reading`、`User`、`Close`、`Calendar`、`Clock`、`Right`、`View`，并保留现有 `Document`、`Download`。

- [ ] **步骤 5：实现章节、附件和底部操作区**

章节标题使用统一结构：

```vue
<div class="content-section-heading">
  <span class="content-section-index">01</span>
  <h3>作业要求</h3>
</div>
```

附件章节使用 `02`，保持原有附件数据和下载按钮。底部改为：

```vue
<template #footer>
  <div class="preview-dialog-footer">
    <span class="read-only-hint">
      <el-icon><View /></el-icon>
      正文按编辑器内容原样显示
    </span>
    <el-button
      type="primary"
      class="preview-close-button"
      data-testid="close-preview"
      @click="closeDialog"
    >
      关闭
    </el-button>
  </div>
</template>
```

- [ ] **步骤 6：实现清透蓝样式与响应式布局**

使用规格中的固定颜色：

```css
.preview-content {
  --preview-primary: #4f73e8;
  --preview-primary-deep: #3659c7;
  --preview-primary-soft: #f0f4ff;
  --preview-primary-border: #dfe7ff;
  --preview-text: #26324a;
  --preview-muted: #7b869b;
  --preview-line: #e7ebf2;
  --preview-soft: #f8fafe;
  color: var(--preview-text);
}
```

对 Teleport 到 `body` 的 Element Plus 弹窗使用 `:global` 选择器设置外壳：

```css
:global(.assignment-content-preview-dialog.el-dialog) {
  max-width: 92vw;
  margin-top: 8vh;
  overflow: hidden;
  border-radius: 15px;
  box-shadow: 0 28px 72px rgba(31, 43, 72, 0.24);
}

:global(.assignment-content-preview-dialog.el-dialog::before) {
  display: block;
  height: 4px;
  background: linear-gradient(90deg, #4f73e8, #3659c7);
  content: "";
}

:global(.assignment-content-preview-dialog .el-dialog__header) {
  margin: 0;
  padding: 0;
}

:global(.assignment-content-preview-dialog .el-dialog__body) {
  max-height: calc(84vh - 166px);
  padding: 0 26px 18px;
  overflow-y: auto;
}

:global(.assignment-content-preview-dialog .el-dialog__footer) {
  padding: 0;
}
```

实现时间条、章节序号、白色正文、弱背景附件行和底部操作区。正文容器不得重新增加背景、边框或语义样式。

在 `@media (max-width: 640px)` 中：

- 标题和操作区允许换行。
- 时间条改成单列并隐藏箭头。
- 正文与附件取消额外左缩进。
- 附件行允许换行。
- 隐藏底部只读辅助提示。

- [ ] **步骤 7：运行目标测试并确认绿灯**

运行：

```bash
cd frontend
npx vitest run src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts
```

预期：组件全部测试通过。

- [ ] **步骤 8：运行详情页相关回归测试**

```bash
cd frontend
npx vitest run \
  src/views/teacher/assignments/detail/__tests__/AssignmentHeader.spec.ts \
  src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts \
  src/views/teacher/assignments/detail/__tests__/AssignmentDetail.spec.ts
```

预期：三个测试文件全部通过，查看入口、弹窗和编辑路由无回归。

- [ ] **步骤 9：检查并提交任务 2**

```bash
git diff --check
git add frontend/src/views/teacher/assignments/detail/components/AssignmentContentPreviewDialog.vue frontend/src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts
git commit -m "style: 优化作业内容预览弹窗（任务 2/3）"
```

### 任务 3：完整验证、Docker 更新与真实页面验收

**文件：**

- 验证：`frontend/src/views/teacher/assignments/detail/components/AssignmentContentPreviewDialog.vue`
- 验证：`frontend/src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts`

- [ ] **步骤 1：运行完整前端测试**

```bash
cd frontend
npm test
```

预期：所有 Vitest 测试文件和用例通过，失败数为 0。

- [ ] **步骤 2：运行类型检查和生产构建**

```bash
cd frontend
npm run build
```

预期：`vue-tsc --noEmit` 与 `vite build` 均以退出码 0 完成。

- [ ] **步骤 3：确认工作区无意外文件变化**

```bash
git diff --check
git status --short
git diff --stat
```

只允许计划中列出的组件与测试文件发生变化；构建生成文件不进入提交。

- [ ] **步骤 4：更新本地 Docker 前端**

```bash
docker compose --env-file .env.docker up -d --build --no-deps frontend
docker compose --env-file .env.docker ps frontend
```

预期：`ai-review-frontend` 重新创建并进入 `healthy` 状态，后端和数据库容器不重建。

- [ ] **步骤 5：浏览器验收真实作业**

打开：

```text
http://localhost/teacher/assignments/detail?id=21
```

依次验证：

1. 点击“查看作业内容”只出现一个弹窗。
2. 弹窗为白色清爽文档布局，顶部、时间条、章节序号和按钮使用清透蓝。
3. 作业正文仍按原段落顺序显示，保留编号、空行、缩进和编辑器格式。
4. 页面中不存在原型曾添加的摘要步骤、自动提示卡片或语义重排内容。
5. 附件名称、大小和下载按钮显示正常。
6. 右上角关闭、底部关闭和遮罩关闭均返回原详情页。
7. 遮罩为半透明深灰色，背景页面不可操作。
8. 在窄屏宽度下标题、时间、正文和附件无横向溢出。

- [ ] **步骤 6：在本地 `main` 合并后重新验证**

按 `finishing-a-development-branch` 流程将功能分支本地合并回 `main`，然后在 `main` 上重新运行：

```bash
cd frontend
npm test
npm run build
```

重新从 `main` 构建 Docker 前端并确认健康。未获得用户明确指示时不推送远端。
