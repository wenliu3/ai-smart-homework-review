# 学生端核心体验改版实现计划

> **面向 AI 代理的工作者：** 在当前会话中使用 TDD 分阶段执行本计划，步骤使用复选框跟踪。

**目标：** 在不新增业务模块的前提下，统一并提升学生端学习中心、班级、作业、提交与评价体验，同时补齐教师作业附件链路。

**架构：** 后端仅扩展现有提交详情响应；前端增加学生端共享样式和附件展示组件，逐页重组现有 Vue 组件而不改变 API 路由与 Vuex 架构。交互测试锁定数据契约，最终通过类型检查、单元测试和 Docker 视觉验收。

**技术栈：** FastAPI、SQLAlchemy、Vue 3、TypeScript、Element Plus、Vuex 4、pytest、Vitest

---

### 任务 1：补齐教师附件响应契约

**文件：**
- 创建：`backend_python/tests/unit/test_student_submission_detail.py`
- 修改：`backend_python/app/crud/submission.py`
- 修改：`frontend/src/api/submissions.ts`

- [ ] 编写测试，断言 `get_my_submission()` 的 `assignment` 包含 `attachments` 和 `allowAttachments`。
- [ ] 运行测试并确认因字段缺失而失败。
- [ ] 在提交详情 CRUD 中返回两个字段，并同步前端类型。
- [ ] 重新运行测试并确认通过。

### 任务 2：建立学生端共享附件组件与视觉基础

**文件：**
- 创建：`frontend/src/views/student/components/AssignmentAttachmentList.vue`
- 创建：`frontend/src/views/student/components/__tests__/AssignmentAttachmentList.spec.ts`
- 创建：`frontend/src/views/student/student-theme.css`

- [ ] 编写组件测试，覆盖文件名、大小、类型图标、下载事件和无附件不渲染。
- [ ] 运行 Vitest 并确认组件尚不存在而失败。
- [ ] 实现附件组件和共享页面/卡片/状态样式。
- [ ] 重新运行组件测试并确认通过。

### 任务 3：重构作业详情与提交核心页

**文件：**
- 修改：`frontend/src/views/student/submissions/index.vue`
- 修改：`frontend/src/views/student/submissions/components/AssignmentInfo.vue`
- 修改：`frontend/src/views/student/submissions/components/SubmissionForm.vue`
- 修改：`frontend/src/views/student/submissions/components/ReviewResults.vue`
- 修改：`frontend/src/views/student/submissions/components/SubmittedContent.vue`

- [ ] 在 `AssignmentInfo` 测试中锁定教师附件、状态摘要和截止信息。
- [ ] 先运行测试确认失败，再接入共享附件组件。
- [ ] 重组标题区、三标签、正文、提交表单、固定操作区和评价结果层级。
- [ ] 运行相关组件测试与类型检查。

### 任务 4：统一学生作业详情与作业列表

**文件：**
- 修改：`frontend/src/views/student/assignments/index.vue`
- 修改：`frontend/src/views/student/assignments/detail.vue`

- [ ] 为列表状态筛选和详情附件展示添加组件测试。
- [ ] 先确认测试失败，再实现桌面列表、小屏卡片和统一附件组件。
- [ ] 保持现有路由与提交入口参数不变。
- [ ] 运行相关测试与类型检查。

### 任务 5：优化班级课程卡片

**文件：**
- 修改：`frontend/src/views/student/classes/index.vue`
- 修改：`frontend/src/views/student/classes/components/ClassList.vue`
- 修改：`frontend/src/views/student/classes/components/AssignmentList.vue`

- [ ] 使用现有班级字段实现确定性渐变封面和课程卡片层级。
- [ ] 优化班级切换、作业状态、截止时间和响应式布局。
- [ ] 不增加封面字段或课程资源入口。
- [ ] 运行前端测试与类型检查。

### 任务 6：重组学生学习中心

**文件：**
- 修改：`frontend/src/views/dashboard/StudentDashboard.vue`
- 修改：`frontend/src/views/dashboard/components/StatCard.vue`

- [ ] 重组欢迎区、关键统计、待办和最近提交的首屏顺序。
- [ ] 统一统计卡片样式并保留现有 Vuex 数据源和图表。
- [ ] 校验紧急截止、空状态与移动端布局。
- [ ] 运行前端测试与类型检查。

### 任务 7：回归与运行环境验收

**文件：**
- 验证以上全部变更文件。

- [ ] 运行 `npm test` 与 `npx vue-tsc --noEmit`。
- [ ] 运行相关后端 pytest 与 `python -m compileall -q backend_python/app`。
- [ ] 运行 `git diff --check` 并检查未触碰无关改动。
- [ ] 重建 Docker 后端与前端，确认服务健康。
- [ ] 使用学生账号验证附件显示与下载、作业筛选、提交和评价标签。
