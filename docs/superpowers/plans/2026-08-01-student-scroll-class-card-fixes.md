# 学生端滚动与班级卡片修复实现计划

> 按已确认设计执行：先建立失败的回归测试，再做最小修复，最后完成类型检查、构建和浏览器场景复测。

**目标：** 恢复学生提交工作区的纵向滚动，并移除班级卡片中由名称前两个字造成的重复展示。

**实现原则：** 延续 `AppLayout.vue` 的单滚动容器模型；提交页根节点占满可用高度并负责纵向滚动。班级卡片保留基于名称的稳定渐变，但封面只作为无文本装饰条。

---

### 任务 1：提交工作区滚动回归

**文件：**
- 修改：`frontend/src/views/student/submissions/index.vue`
- 测试：`frontend/src/views/student/submissions/__tests__/SubmissionWorkspace.spec.ts`

- [ ] 增加样式契约回归测试，要求最终 `.submission-container` 使用 `height: 100%`、`min-height: 0`、`overflow-y: auto`、`overflow-x: hidden`。
- [ ] 单独运行该测试并确认测试因当前 `height: auto`、`overflow: visible` 而失败。
- [ ] 将学生端覆盖样式改为已确认的滚动容器样式。
- [ ] 再次运行测试并确认通过。

### 任务 2：班级卡片去除重复文字

**文件：**
- 修改：`frontend/src/views/student/classes/components/ClassList.vue`
- 测试：`frontend/src/views/student/classes/components/__tests__/ClassList.spec.ts`

- [ ] 使用“自然语言处理（NLP）”作为测试数据，断言完整班级名只出现一次且装饰区域没有文本。
- [ ] 单独运行该测试并确认测试因现有 `getClassInitials()` 渲染“自然”而失败。
- [ ] 将 72px 文本封面替换为无文本、`aria-hidden` 的细渐变装饰条，删除 `getClassInitials()` 和旧封面样式。
- [ ] 再次运行测试并确认通过。

### 任务 3：完整验证与浏览器复测

**验证：**
- [ ] 运行 `npm test`。
- [ ] 运行 `npx vue-tsc --noEmit`。
- [ ] 运行 `npm run build-only`。
- [ ] 运行 `git diff --check` 并审查工作区状态。
- [ ] 重建 Compose 前端容器，确认健康检查及首页 HTTP 200。
- [ ] 使用学生账号按截图路径复测班级卡片、作业详情与提交编辑区的纵向滚动，并检查无横向溢出及新增控制台错误。

### 任务 4：提交修复

- [ ] 提交实现与回归测试，提交信息：`fix: restore student page scrolling and simplify class cards`。
