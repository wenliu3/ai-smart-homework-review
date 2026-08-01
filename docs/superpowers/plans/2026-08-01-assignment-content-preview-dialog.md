# 教师端作业内容预览弹窗实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。

**目标：** 在教师作业详情页提供直接可见的只读作业内容按钮，并通过带灰色遮罩的模态弹窗展示发布内容与附件。

**架构：** `AssignmentHeader` 只负责按钮文案和 `preview` 事件；新的 `AssignmentContentPreviewDialog` 负责只读展示和附件下载；详情页持有弹窗显隐状态并把已加载的 `AssignmentDetail` 传给弹窗。全过程不新增后端请求。

**技术栈：** Vue 3 `<script setup>`、TypeScript、Element Plus、DOMPurify、Vue Test Utils、Vitest。

---

## 文件结构

- 修改 `frontend/src/views/teacher/assignments/detail/components/AssignmentHeader.vue`：分离返回导航，新增直接可见的预览按钮并发出 `preview` 事件。
- 创建 `frontend/src/views/teacher/assignments/detail/components/AssignmentContentPreviewDialog.vue`：渲染模态弹窗、作业元数据、净化后的富文本、附件和空状态。
- 修改 `frontend/src/views/teacher/assignments/detail/index.vue`：连接预览事件、弹窗显隐状态和作业详情数据。
- 创建 `frontend/src/views/teacher/assignments/detail/__tests__/AssignmentHeader.spec.ts`：覆盖状态文案和事件。
- 创建 `frontend/src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts`：覆盖内容、空状态、HTML 净化与关闭事件。
- 修改 `frontend/src/views/teacher/assignments/detail/__tests__/AssignmentDetail.spec.ts`：覆盖详情页打开弹窗的数据流，并保留编辑路由回归测试。

### 任务 1：详情页头部的查看入口

**文件：**
- 修改：`frontend/src/views/teacher/assignments/detail/components/AssignmentHeader.vue`
- 测试：`frontend/src/views/teacher/assignments/detail/__tests__/AssignmentHeader.spec.ts`

- [ ] **步骤 1：编写失败的头部组件测试**

创建包含完整最小 `AssignmentDetail` 的工厂函数，分别断言：

```ts
expect(wrapper.get('[data-testid="preview-assignment"]').text()).toContain(
  "查看作业内容"
);
await wrapper.get('[data-testid="preview-assignment"]').trigger("click");
expect(wrapper.emitted("preview")).toHaveLength(1);
```

草稿状态断言按钮文案为“预览作业内容”，详情为空时断言按钮禁用。

- [ ] **步骤 2：运行测试并确认因按钮缺失而失败**

运行：

```bash
cd frontend
npx vitest run src/views/teacher/assignments/detail/__tests__/AssignmentHeader.spec.ts
```

预期：FAIL，找不到 `data-testid="preview-assignment"`。

- [ ] **步骤 3：实现最小头部行为与布局**

在 `AssignmentHeader.vue` 中：

```ts
interface Emits {
  (e: "goBack"): void;
  (e: "preview"): void;
  // 保留现有事件
}

const previewButtonText = computed(() =>
  props.assignmentDetail?.status === "draft"
    ? "预览作业内容"
    : "查看作业内容"
);

const handlePreview = () => emit("preview");
```

将返回入口从业务按钮区域分离为标题上方的返回链接；右侧业务区域增加带 `View` 图标、`data-testid="preview-assignment"` 的预览按钮，详情为空时禁用。“操作”仍保留为下拉菜单。

- [ ] **步骤 4：运行头部测试确认通过**

运行同一步骤 2，预期测试全部 PASS 且没有 Vue 组件解析警告。

### 任务 2：只读作业内容模态弹窗

**文件：**
- 创建：`frontend/src/views/teacher/assignments/detail/components/AssignmentContentPreviewDialog.vue`
- 测试：`frontend/src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts`

- [ ] **步骤 1：编写失败的弹窗组件测试**

使用可渲染默认插槽的 `el-dialog` 测试桩，断言：

```ts
expect(wrapper.text()).toContain("实验2：神雕侠侣语料库分析");
expect(wrapper.text()).toContain("自然语言处理 (NLP)");
expect(wrapper.get(".assignment-description").html()).not.toContain("script");
expect(wrapper.text()).toContain("实验2-语料库分析.docx");
```

另一个用例传入空描述和空附件，断言“暂无作业要求”和“暂无作业附件”；点击关闭按钮断言 `update:modelValue` 发出 `false`。

- [ ] **步骤 2：运行测试并确认因组件缺失而失败**

运行：

```bash
cd frontend
npx vitest run src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts
```

预期：FAIL，无法解析 `AssignmentContentPreviewDialog.vue`。

- [ ] **步骤 3：实现弹窗和安全只读渲染**

组件使用：

```vue
<el-dialog
  :model-value="modelValue"
  width="min(800px, 92vw)"
  class="assignment-content-preview-dialog"
  @update:model-value="emit('update:modelValue', $event)"
>
```

使用 `DOMPurify.sanitize(props.assignmentDetail?.description || "")` 生成 `sanitizedDescription`，并在 `.assignment-description` 中 `v-html` 渲染。依次展示状态、班级、时间、描述、附件；附件下载复用现有鉴权下载方式，并在非成功响应或 URL 缺失时给出提示。弹窗内容区域最大高度 `80vh` 并内部滚动。

- [ ] **步骤 4：运行弹窗测试确认通过**

运行同一步骤 2，预期全部 PASS。

### 任务 3：详情页数据流集成

**文件：**
- 修改：`frontend/src/views/teacher/assignments/detail/index.vue`
- 修改：`frontend/src/views/teacher/assignments/detail/__tests__/AssignmentDetail.spec.ts`

- [ ] **步骤 1：先扩展详情页测试并确认失败**

在现有挂载基础上发出头部事件：

```ts
wrapper.findComponent(AssignmentHeader).vm.$emit("preview");
await wrapper.vm.$nextTick();

const dialog = wrapper.findComponent(AssignmentContentPreviewDialog);
expect(dialog.props("modelValue")).toBe(true);
expect(dialog.props("assignmentDetail")?.id).toBe("21");
```

保留原有编辑导航断言。

- [ ] **步骤 2：运行详情页测试并确认因未接线而失败**

运行：

```bash
cd frontend
npx vitest run src/views/teacher/assignments/detail/__tests__/AssignmentDetail.spec.ts
```

预期：FAIL，弹窗不存在或 `modelValue` 不是 `true`。

- [ ] **步骤 3：实现最小集成**

在详情页中：

```ts
const previewVisible = ref(false);
const handlePreview = () => {
  previewVisible.value = true;
};
```

给 `AssignmentHeader` 增加 `@preview="handlePreview"`；挂载 `AssignmentContentPreviewDialog`，使用 `v-model="previewVisible"` 并传入 `assignmentDetail`。

- [ ] **步骤 4：运行三个目标测试文件**

```bash
cd frontend
npx vitest run \
  src/views/teacher/assignments/detail/__tests__/AssignmentHeader.spec.ts \
  src/views/teacher/assignments/detail/__tests__/AssignmentContentPreviewDialog.spec.ts \
  src/views/teacher/assignments/detail/__tests__/AssignmentDetail.spec.ts
```

预期：全部 PASS。

### 任务 4：完整验证与本地 Docker 更新

**文件：**
- 验证所有上述修改文件。

- [ ] **步骤 1：运行完整前端测试**

```bash
cd frontend
npm test
```

预期：所有测试文件和测试用例通过，失败数为 0。

- [ ] **步骤 2：运行类型检查和生产构建**

```bash
cd frontend
npm run build
```

预期：`vue-tsc --noEmit` 与 `vite build` 均退出码 0。

- [ ] **步骤 3：检查变更范围**

```bash
git diff --check
git status --short
git diff -- frontend/src/views/teacher/assignments/detail
```

预期：无空白错误；变更仅包含计划、既有编辑跳转修复、预览组件及对应测试。

- [ ] **步骤 4：重建本地前端容器**

```bash
docker compose --env-file .env.docker up -d --build frontend
docker compose --env-file .env.docker ps
```

预期：`ai-review-frontend` 为 healthy，其余依赖服务正常运行。

- [ ] **步骤 5：浏览器验收**

在教师作业详情页验证：

1. “查看作业内容”直接可见。
2. 点击后出现居中弹窗和灰色遮罩。
3. 弹窗显示标题、班级、时间、富文本要求和附件。
4. 关闭后 URL、筛选和详情页状态不变。
5. “编辑作业”仍能进入 `TeacherAssignmentsEdit` 并保留作业 ID。

- [ ] **步骤 6：提交实现**

验证通过后，仅暂存本计划范围内的文件并创建一个功能提交；不推送远端，除非用户另行要求。
