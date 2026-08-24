# 前后端接口一致性审计报告

> 审计日期：2026-08-24
> 审计范围：后端 `backend_python/app`（main.py + routers + schemas + crud + models + agent/tasks/脚本/测试）、前端 `frontend/src`（api + views + components + store + utils + router + types + 测试）
> 业务原则：系统不开放自行注册；用户仅由超级管理员新增或教师/超级管理员批量导入；单角色设计（student/teacher/superadmin）

---

## 一、审计方法与统计

- 后端路由识别计入 `main.py` 统一添加的 `/api` 前缀；动态路径按语义对应（如前端 `/users/${id}` ↔ 后端 `/users/{user_id}`）。
- 前端除 `src/api/**` 外，同时扫描了 views/components/store/utils/router/types 中的裸 `fetch`、`XMLHttpRequest`、`window.open`、`location.href`、`/uploads/` 直链与 SSE。
- 前端 axios 拦截器（`utils/request.ts:78-113`）已解包 `{code,data,message}`，业务代码拿到的是 `data` 字段；blob 响应返回完整 AxiosResponse。
- **审计前**：后端 129 条路由；**审计后**：96 个路径 / 111 个操作（删除 18 个无调用/重复接口，新增 1 个 C 类补实现）。

### 分类统计（按处理后状态）

| 分类 | 数量 | 说明 |
|---|---|---|
| A 前后端一致 | 92 | 方法/路径/字段/权限一致，未改动或仅加鉴权 |
| B 不一致（已修复） | 7 | 见"三、B 类修复明细" |
| C 前端调用后端不存在 | 1 | 已补后端实现（用户导入模板） |
| D 后端存在前端未用 | 4 | 已评估保留（含运维/预留），见"五" |
| E 重复/旧版/遗留（已删除） | 18 | 已连同 Schema/CRUD/前端封装/死代码删除 |
| F 非页面类接口（保留） | 12 | SSE/下载/Agent/运维/内部任务，见"五" |
| G 需人工确认 | 3 | 见"六" |

---

## 二、接口映射总表

> 响应结构统一为 `ok()` 包装：`{"code":200,"data":...,"message":"操作成功"}`；下表"响应"列仅描述 `data` 部分。
> "Token/角色"为**当前（修复后）**后端要求。编号 Pxx 为本次删除的接口。

### 2.1 认证（auth.py，6 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Path 参数 | Query 参数 | Body/Form 字段 | 前端响应类型 | 后端响应结构 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 登录页 | `api/auth.ts:login` / `store user/login` | POST | /v1/auth/login | POST /api/v1/auth/login | — | — | usernameOrEmailOrStudentId, password | LoginResult | token/refreshToken/expiresIn/userId/mustChangePassword/isFirstLogin/user | 公开 | Login.vue:276；测试 test_auth_login.py | A | 一致 |
| 2 | 退出登录 | `api/auth.ts:logout` / `store user/logout` | POST | /v1/auth/logout | POST /api/v1/auth/logout | — | — | — | {success} | {success} | 登录 | 布局顶栏、store user.ts:239 | A | 一致 |
| 3 | 令牌刷新 | `api/auth.ts:refreshToken` / `store user/refreshToken` | POST | /v1/auth/refresh-token | POST /api/v1/auth/refresh-token | — | — | refreshToken | RefreshTokenResult | token/refreshToken/expiresIn | 公开 | utils/request.ts 拦截器 | A | 一致 |
| 4 | 用户信息 | `api/auth.ts:getUserInfo` / `store user/getUserInfo` | GET | /v1/auth/profile | GET /api/v1/auth/profile | — | — | — | {user} | user{name,role,status,studentId,phone,avatar,...} | 登录 | store user.ts:131 | A | 一致 |
| 5 | 修改密码 | `api/auth.ts:changePassword` | PUT | /v1/auth/password | PUT /api/v1/auth/password | — | — | currentPassword,newPassword,confirmPassword | {message} | {message} | 登录 | ChangePasswordDialog.vue:242 | A | 一致（后端校验两次密码一致） |
| 6 | 首次强制改密 | `api/auth.ts:firstChangePassword` | PUT | /v1/auth/first-password-change | PUT /api/v1/auth/first-password-change | — | — | 同上 | {message} | {message} | 登录 | ForceChangePassword.vue | A | 一致 |
| P1 | ~~注册~~ | ~~api/auth.ts:register~~ | POST | /v1/auth/register | ~~POST /api/v1/auth/register~~ | — | — | username,password,confirmPassword,email,name | RegisterResult | token/userId/expiresIn | 公开 | Login.vue 注册分支（入口已注释） | E | **已删除**（含 RegisterRequest Schema、crud/auth.register、前端封装、store register action） |
| P2 | ~~旧版登录~~ | ~~api/user.ts:login（死代码）~~ | POST | /auth/login | ~~POST /api/auth/login~~ | — | — | email,password | any | 同新版 | 公开 | 全前端无调用 | E | **已删除**（login_legacy + LegacyLoginRequest） |
| P3 | ~~旧版注册~~ | ~~api/user.ts:register（死代码）~~ | POST | /auth/register | ~~POST /api/auth/register~~ | — | — | name,email,password | any | 同新版 | 公开 | 全前端无调用 | E | **已删除**（register_legacy + LegacyRegisterRequest） |
| P4 | ~~忘记密码~~ | ~~api/auth.ts:forgotPassword（无调用）~~ | POST | /v1/auth/forgot-password | ~~POST /api/v1/auth/forgot-password~~ | — | — | email | {success} | 假实现恒 success | 公开 | 无调用（登录页仅提示联系管理员） | E | **已删除**（假实现无业务入口） |
| P5 | ~~重置密码~~ | ~~api/auth.ts:resetPassword（无调用）~~ | POST | /v1/auth/reset-password | ~~POST /api/v1/auth/reset-password~~ | — | — | token,password | {success} | 固定抛 10010 | 公开 | 无调用 | E | **已删除**（未实现桩接口） |

### 2.2 用户（users.py，8 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Path 参数 | Query 参数 | Body/Form 字段 | 前端响应类型 | 后端响应结构 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7 | 用户列表 | `api/user.ts:getUsers` | GET | /users | GET /api/users | — | page,limit,role,keyword,status,sortField,sortOrder | — | UserListResponse | {items,total,page,limit} | **superadmin**（修复） | system/users/index.vue:217；system/classes/index.vue:193（选教师） | B | **修复**：原无任何鉴权；补 status 筛选（原后端忽略该参数）；items 不含 password |
| 8 | 用户详情（编辑回显） | `api/user.ts:getUser` | GET | /users/{userId} | GET /api/users/{user_id} | user_id:int | — | — | User | to_dict（含 roleIds，不含 password） | 登录 | UserForm.vue loadUserData | A | 一致 |
| 9 | 新增用户 | `api/user.ts:createUser` | POST | /users | POST /api/users | — | — | username,email,password,name,role,studentId(仅学生),phone,status | User | to_dict | superadmin | UserForm.vue:339 | B | **修复**：后端 UserCreate 增加服务端校验（用户名2-20/邮箱正则/密码≥6/角色与状态枚举/手机号/学生必填学号）；非学生清除学号；mustChangePassword 无前端输入项，保留后端默认 false；confirmPassword 仅前端比较 |
| 10 | 修改用户（含改角色） | `api/user.ts:updateUser` | PATCH | /users/{userId} | PATCH /api/users/{user_id} | user_id:int | — | name,email,role,studentId,phone,status | User | to_dict | superadmin | UserForm.vue:325；users/index.vue:284（改状态） | B | **修复**：单角色设计下 role 随本接口生效；UserForm 删除多余的 `assignRolesToUser` 第二次调用（原指向不存在的 PUT）；后端补邮箱/学号唯一性与角色-学号联动校验 |
| 11 | 删除用户 | `api/user.ts:deleteUser` | DELETE | /users/{id} | DELETE /api/users/{user_id} | user_id:int | — | — | {success,message} | {success,message} | superadmin | users/index.vue:265 | A | 一致 |
| 12 | 重置用户密码 | `api/user.ts:resetUserPassword` | POST | /users/{userId}/reset-password | POST /api/users/{user_id}/reset-password | user_id:int | — | newPassword? | {success,message} | {success,message}（含新密码） | superadmin | users/index.vue:312 | A | 一致（Schema 补 newPassword≥6 校验） |
| 13 | 批量导入 | `api/user.ts:importUsersBatch` | POST | /users/batch-import | POST /api/users/batch-import | — | — | 裸数组 [{name,studentId,username?,email?,phone?}] | any | {success,total,successCount,failureCount,failures} | teacher+superadmin | ImportUsersDialog.vue:352 | A | 一致；测试确认删注册不影响导入 |
| 14 | 批量删除 | `api/user.ts:deleteUsersBatch` | POST | /users/batch-delete | POST /api/users/batch-delete | — | — | {userIds} | {success,total,successCount,failureCount,failures?} | 同左 | superadmin | users/index.vue:357 | A | 一致 |
| P6 | ~~获取自己资料~~ | ~~api/user.ts:getUserProfile（死代码）~~ | GET | /users/profile | ~~GET /api/users/profile~~ | — | — | — | User | to_dict | 登录 | 无调用（实际走 /v1/auth/profile） | E | **已删除**（与 #4 重复） |
| P7 | ~~更新自己资料~~ | ~~api/user.ts:updateUserProfile（死代码）~~ | PUT | /users/profile | ~~PUT /api/users/profile~~ | — | — | name,phone,avatar | any | to_dict | 登录 | 无调用 | E | **已删除**（无业务入口）+ 删 ProfileUpdate Schema + crud.update_profile |
| P8 | ~~改自己密码(旧)~~ | ~~api/user.ts:changePassword（死代码）~~ | PUT | /users/password | ~~PUT /api/users/password~~ | — | — | currentPassword,newPassword | any | {success,message} | 登录 | 无调用（实际走 /v1/auth/password） | E | **已删除**（与 #5 重复） |
| P9 | ~~管理员改密(旧)~~ | ~~api/user.ts:updateUserPassword（死代码）~~ | PATCH | /users/{userId}/password | ~~PATCH /api/users/{user_id}/password~~ | user_id:int | — | oldPassword,newPassword | {success,message} | {success,message} | superadmin | 无调用（实际用 reset-password） | E | **已删除**（与 #12 重复）+ 删 UpdateUserPasswordRequest Schema + crud.update_user_password |

### 2.3 班级（classes.py，11 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Path 参数 | Query 参数 | Body/Form 字段 | 前端响应类型 | 后端响应结构 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 15 | 班级列表 | `api/classes.ts:getClassList` | GET | /classes/list | GET /api/classes/list | — | page,limit,status,search,teacherId,sortField,sortOrder | — | ClassListResponse | {items,total,page,limit}（按角色隔离） | 登录 | teacher/classes、system/classes、student/classes、teacher/correcting、ClassSelector | A | 一致 |
| 16 | 班级详情 | `api/classes.ts:getClassDetail` | GET | /classes/{id} | GET /api/classes/{class_id} | class_id:int | — | — | Class | to_dict+teacherName | 登录+归属（**修复**） | teacher/classes/detail；system/classes | B | **修复**：原任意登录用户可查任意班级；现仅班级教师/superadmin/在班学生 |
| 17 | 创建班级 | `api/classes.ts:createClass/createClassForTeacher` | POST | /classes/create | POST /api/classes/create | — | — | name,description,maxStudents[,teacherId(管理员代建)] | CreateClassApiResponse | {message,classId} | teacher+superadmin（**修复**，原仅登录） | CreateClassDialog.vue；AdminCreateClassDialog.vue | B | **修复**：学生不可再创建班级 |
| 18 | 编辑班级 | `api/classes.ts:updateClass` | POST | /classes/{id}/edit | POST /api/classes/{class_id}/edit | class_id:int | — | name,description,maxStudents[,teacherId(管理员)] | {message} | {message} | teacher+superadmin（归属校验） | 同上 | A | 一致 |
| 19 | 解散班级 | `api/classes.ts:disbandClass` | POST | /classes/{id}/close | POST /api/classes/{class_id}/close | class_id:int | — | — | {message} | {message} | teacher+superadmin（**修复**：原管理员调用会 10007） | teacher/classes、system/classes | B | **修复**：superadmin 可越权属操作（crud 补 actor_role 放行） |
| 20 | 重置邀请码 | `api/classes.ts:regenerateClassCode` | POST | /classes/{id}/regenerate-code | POST /api/classes/{class_id}/regenerate-code | class_id:int | — | — | RegenerateCodeApiResponse | {message,inviteCode} | teacher+superadmin（同上修复） | teacher/classes、system/classes | B | **修复**：同 #19 |
| 21 | 班级学生列表 | `api/classes.ts:getClassStudents` | GET | /classes/{id}/students | GET /api/classes/{class_id}/students | class_id:int | page,limit,status,search | — | ClassStudentListResponse | {items,total,page,limit} | 登录+归属（**修复**） | teacher/classes/detail/StudentList.vue | B | **修复**：原任意登录用户可拉任意班级名单 |
| 22 | 添加学生 | `api/classes.ts:addStudentsToClass` | POST | /classes/{id}/students | POST /api/classes/{class_id}/students | class_id:int | — | {studentIds[]} | AddStudentsApiResponse | {success[],failed[]} | teacher（归属校验） | AddStudentDialog.vue | A | 一致 |
| 23 | 加入班级 | `api/classes.ts:joinClass` | POST | /classes/join | POST /api/classes/join | — | — | {classCode} | any | {message,classId} | student（**修复**，原仅登录） | JoinClassDialog.vue | A | 角色收紧，路径字段一致 |
| 24 | 学生状态 | `api/classes.ts:updateStudentStatus` | POST | /classes/{id}/students/status | POST /api/classes/{class_id}/students/status | class_id:int | — | {studentIds[],status} | any | {success,...} | teacher（归属校验） | StudentList.vue | A | 一致 |
| 25 | 退出班级 | `api/classes.ts:leaveClass` | POST | /classes/{id}/leave | POST /api/classes/{class_id}/leave | class_id:int | — | — | any | {message} | student（**修复**） | useClassManagement.ts | A | 角色收紧 |

### 2.4 作业（assignments.py，13 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Path 参数 | Query 参数 | Body/Form 字段 | 前端响应类型 | 后端响应结构 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 26 | 教师作业列表 | `api/assignments.ts:getAssignmentList` | GET | /teacher/assignments | GET /api/teacher/assignments | — | page,pageSize,status,title,startDate,endDate,sortBy,sortOrder | — | AssignmentListResponse | {items,total,page,pageSize} | teacher（**修复**） | teacher/correcting、AssignmentManagement.vue | A | 角色收紧；数据按 teacher_id 隔离（原有） |
| 27 | 作业详情(教师) | `api/assignments.ts:getAssignmentDetail` | GET | /teacher/assignments/{id} | GET /api/teacher/assignments/{assignment_id} | assignment_id:int | — | — | AssignmentDetail | to_dict+submissionStats+totalStudents | teacher+归属（**修复**） | teacher/assignments/detail、GradingDrawer | B | **修复**：原任意登录用户可查任意作业详情 |
| 28 | 作业学生列表 | `api/assignments.ts:getAssignmentStudents` | GET | /teacher/assignments/{id}/students | GET /api/teacher/assignments/{assignment_id}/students | assignment_id:int | page,limit,classId,studentName,studentNumber,submissionStatus | — | any | {items,total,page,limit,assignment} | teacher+归属（**修复**） | teacher/assignments/detail/index.vue | B | **修复**：原任意登录用户可遍历全校学生成绩 |
| 29 | 创建作业 | `api/assignments.ts:createAssignment` | POST | /teacher/assignments | POST /api/teacher/assignments | — | — | title,description,classes[],startDate,endDate,aiRule,attachments[],allowAttachments | Assignment | to_dict | teacher（**修复**，原仅登录） | assigmentsEidt/index.vue | B | **修复**：学生不可再创建作业 |
| 30 | 更新作业 | `api/assignments.ts:updateAssignment` | POST | /teacher/assignments/{id}/update | POST /api/teacher/assignments/{assignment_id}/update | assignment_id:int | — | 同创建（可选） | Assignment | to_dict | teacher+归属 | assigmentsEidt/index.vue | A | 一致 |
| 31 | 发布/终止 | `api/assignments.ts:publishAssignment/terminateAssignment` | POST | /teacher/assignments/{id}/status | POST /api/teacher/assignments/{assignment_id}/status | assignment_id:int | — | {status,terminatedReason?} | Assignment | to_dict | teacher+归属 | teacher/assignments/detail | A | 一致 |
| 32 | 删除作业 | `api/assignments.ts:deleteAssignment` | POST | /teacher/assignments/{id}/delete | POST /api/teacher/assignments/{assignment_id}/delete | assignment_id:int | — | — | void | {success,...} | teacher+归属 | teacher/assignments/index、AssignmentManagement | A | 一致 |
| 33 | 作业查重 | `api/assignments.ts:checkPlagiarism` | POST | /teacher/assignments/{assignmentId}/plagiarism | POST /api/teacher/assignments/{assignment_id}/plagiarism | assignment_id:int | — | FormData: template_file?,passRate?,phraseWeight?,topicWeight? | PlagiarismResult | {results,suspectCount,...} | teacher+归属（原有） | AssignmentDetailTabs.vue | A | 一致 |
| 34 | 提交对比 | `api/assignments.ts:compareSubmissions` | GET | /teacher/submissions/compare | GET /api/teacher/submissions/compare | — | submission_id,match_submission_id | — | CompareResult | {contentHtmlA/B,snippets,...} | teacher+归属（原有） | AssignmentDetailTabs.vue | A | 一致 |
| 35 | 查重 AI 建议 | `api/assignments.ts:getAiSuggestion` | POST | /teacher/submissions/{submissionId}/ai-suggestion | POST /api/teacher/submissions/{submission_id}/ai-suggestion | submission_id:int | — | {plagiarismInfo,matchSubmissionId?} | {suggestion} | {suggestion} | teacher+归属（原有） | AssignmentDetailTabs.vue | A | 一致 |
| 36 | 学生作业列表 | `api/assignments.ts:getMyAssignments` | GET | /student/assignments | GET /api/student/assignments | — | classId,businessStatus | — | any | 列表 | student（**修复**） | student/assignments、AssignmentList.vue | A | 角色收紧 |
| 37 | 学生作业统计 | `api/assignments.ts:getMyAssignmentStatistics` | GET | /student/assignments/statistics | GET /api/student/assignments/statistics | — | classId | — | any | 统计 | student（**修复**） | student/assignments/index.vue | A | 角色收紧 |
| 38 | 学生作业详情 | `api/assignments.ts:getStudentAssignment` | GET | /student/assignments/{assignmentId} | GET /api/student/assignments/{assignment_id} | assignment_id:int | classId | — | StudentAssignment | 详情 | student（**修复**；成员校验原有） | student/assignments/detail.vue | A | 角色收紧 |

### 2.5 提交与批改（submissions.py 4 条 + correcting.py 3 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Path 参数 | Query 参数 | Body/Form 字段 | 前端响应类型 | 后端响应结构 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 39 | 提交作业 | `SubmissionsApi.submit` | POST | /students/submissions/submit | POST /api/students/submissions/submit | — | — | assignmentId,classId,content?,attachments[],isDraft? | SubmitAssignmentResponse | 提交详情 | student | student/submissions/index.vue:627 等 | A | 一致 |
| 40 | 我的提交 | `SubmissionsApi.getMySubmission` | GET | /students/submissions/my/{assignmentId} | GET /api/students/submissions/my/{assignment_id} | assignment_id:int | — | — | MySubmissionDetail | {assignment,submission,aiReview,teacherReview} | student | useSubmissionManagement.ts:211 | A | 一致 |
| 41 | 学生删提交 | `SubmissionsApi.deleteSubmission` | POST | /students/submissions/delete | POST /api/students/submissions/delete | — | — | {submissionId} | {success,message,resourceId} | 同左 | student（归属校验原有） | useSubmissionManagement.ts:426 | A | 一致 |
| 42 | 教师删提交 | `SubmissionsApi.teacherDeleteSubmission`（**新增封装**） | POST | /teacher/submissions/delete | POST /api/teacher/submissions/delete | — | — | {submissionId} | {success,message,resourceId} | 同左 | teacher+归属（原有） | AssignmentDetailTable.vue:292（原裸 fetch 已改走 api 层） | B | **修复**：原组件绕过 api 层手动判 code===200，行为不一致 |
| 43 | 批改列表 | `api/correcting.ts:getSubmissionList` | GET | /teachers/submissions/list | GET /api/teachers/submissions/list | — | page,limit,assignmentId,classId,status,studentName,studentNumber,sortBy,sortOrder | — | SubmissionListResponse | {items,total,page,pageSize} | teacher+数据范围（**修复**） | teacher/correcting/index.vue | B | **修复**：原列表返回全校提交；现按 Assignment.teacher_id 过滤 |
| 44 | 批改详情 | `api/correcting.ts:getSubmissionDetail` | GET | /teachers/submissions/detail/{submissionId} | GET /api/teachers/submissions/detail/{submission_id} | submission_id:int | — | — | SubmissionRecord | 详情（含 attachments） | teacher+归属（**修复**） | grading.vue、GradingDrawer.vue | B | **修复**：原任意登录用户可查任意提交 |
| 45 | 提交批改 | `api/correcting.ts:submitTeacherReview` | POST | /teachers/submissions/review | POST /api/teachers/submissions/review | — | — | {submissionId,teacherScore,teacherReviewContent} | any | {success,message,submission} | teacher+归属（**修复**） | grading.vue、GradingDrawer.vue | B | **修复**：原任意登录用户可批改任意提交 |

### 2.6 看板（dashboard.py，7 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Path/Query 参数 | 前端响应类型 | 后端响应结构 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 46 | 管理员概览 | `api/dashboard.ts:getAdminOverview` | GET | /admin/dashboard/overview | GET /api/admin/dashboard/overview | query: refresh | AdminOverviewResponse | 统计+分布 | **superadmin**（修复） | store/modules/dashboard.ts；AdminDashboard.vue | B | **修复**：原仅登录 |
| 47 | AI 模型统计 | `api/dashboard.ts:getAiModelStats` | GET | /admin/dashboard/ai-models | GET /api/admin/dashboard/ai-models | query: refresh | AiModelStatsResponse | deepseek/mimo 统计 | **superadmin**（修复） | 同上 | B | **修复**：原仅登录 |
| 48 | 最近用户 | `api/dashboard.ts:getRecentUsers` | GET | /admin/dashboard/recent-users | GET /api/admin/dashboard/recent-users | query: limit | RecentUsersResponse | {users[]} | **superadmin**（修复） | AdminDashboard.vue:337 | B | **修复**：原仅登录 |
| 49 | 系统健康 | ~~getSystemHealth（死代码已删）~~ | GET | /admin/dashboard/health | GET /api/admin/dashboard/health | — | any | 运行时长/时间戳 | **superadmin** | 前端无调用 | D/F | **保留**（运维/健康检查接口），删除前端死封装 |
| 50 | 教师统计 | `api/dashboard.ts:getTeacherStats` | GET | /teacher/dashboard/stats | GET /api/teacher/dashboard/stats | query: refresh | TeacherStatsResponse | 统计 | **teacher**（修复） | store dashboard；TeacherDashboard.vue | B | **修复**：原仅登录 |
| 51 | 教师待办 | `api/dashboard.ts:getTeacherPendingTasks` | GET | /teacher/dashboard/pending-tasks | GET /api/teacher/dashboard/pending-tasks | — | TeacherPendingTasksResponse | {assignments,submissions} | **teacher**（修复） | TeacherDashboard.vue:428 | B | **修复**：原仅登录 |
| 52 | 学生统计 | `api/dashboard.ts:getStudentStats` | GET | /student/dashboard/stats | GET /api/student/dashboard/stats | query: refresh | StudentStatsResponse | 统计 | **student**（修复） | store dashboard；StudentDashboard.vue | B | **修复**：原仅登录 |
| P10-P14 | ~~教师绩效/快捷操作/学习进度/成就/学习建议~~ | ~~对应前端封装（无调用，已删）~~ | GET | /teacher/dashboard/performance-summary、/quick-actions、/student/dashboard/learning-progress、/achievements、/study-recommendations | ~~同路径~~ | — | any | 空占位数据 | 登录 | 前端无任何调用 | E | **已删除**（5 个占位接口返回空数组，无业务入口，连同 crud 函数与前端死封装删除） |

### 2.7 权限/菜单/角色（permissions.py，11 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Path 参数 | Body 字段 | 前端响应类型 | 后端响应结构 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 53 | 用户资源(角色/权限/菜单) | `api/user-role.ts:getUserResources` | GET | /permissions/user-roles/users/{userId}/resources | GET /api/permissions/user-roles/users/{user_id}/resources | user_id:str("current") | — | {roles,permissions,menus} | 同左 | 登录+**仅可查自己**（修复，superadmin 可查任意） | store/modules/auth.ts:99 | B | **修复**：原任意登录用户可查任意用户的角色/菜单/权限 |
| 54 | 菜单列表 | `api/menu.ts:getMenuList` | GET | /permissions/menus | GET /api/permissions/menus | query: tree,name,path,status,type | — | Menu[] | 列表/树 | **superadmin**（修复） | system/menus、RoleForm | B | **修复**：原仅登录 |
| 55 | 菜单详情 | `api/menu.ts:getMenuById` | GET | /permissions/menus/{id} | GET /api/permissions/menus/{menu_id} | menu_id:int | — | Menu | to_dict | **superadmin**（修复） | MenuForm.vue | B | **修复** |
| 56 | 创建菜单 | `api/menu.ts:createMenu` | POST | /permissions/menus | POST /api/permissions/menus | — | name,code,path,type,parentId?,icon?,sort,hidden,status,meta,isSystem | Menu | to_dict | **superadmin**（修复：原学生可建菜单） | MenuForm.vue | B | **修复** |
| 57 | 更新菜单 | `api/menu.ts:updateMenu` | PUT | /permissions/menus/{id} | PUT /api/permissions/menus/{menu_id} | menu_id:int | 同上（可选） | Menu | to_dict | **superadmin**（修复） | MenuForm.vue | B | **修复** |
| 58 | 删除菜单 | `api/menu.ts:deleteMenu` | DELETE | /permissions/menus/{id} | DELETE /api/permissions/menus/{menu_id} | menu_id:int | — | {success} | {success} | **superadmin**（修复） | system/menus/index.vue | B | **修复** |
| 59 | 角色列表 | `api/role.ts:getRoleList` | GET | /permissions/roles | GET /api/permissions/roles | query: page,limit,search,status,isSystem | — | {items,total,page,limit} | 同左 | **superadmin**（修复；原 UserForm 也调用，现已不再依赖） | system/roles/index.vue | B | **修复**：原仅登录 |
| 60 | 角色详情+菜单 | `api/role.ts:getRoleWithMenus` | GET | /permissions/roles/{id}/with-menus | GET /api/permissions/roles/{role_id}/with-menus | role_id:int | — | Role&{menus} | role+menus | **superadmin**（修复） | RoleForm.vue | B | **修复** |
| 61 | 创建角色 | `api/role.ts:createRole` | POST | /permissions/roles | POST /api/permissions/roles | — | name,code,description,menuIds,permissions,isSystem,status | Role | to_dict | **superadmin**（修复） | RoleForm.vue | B | **修复** |
| 62 | 更新角色 | `api/role.ts:updateRole` | PUT | /permissions/roles/{id} | PUT /api/permissions/roles/{role_id} | role_id:int | 同上（可选） | Role | to_dict | **superadmin**（修复） | RoleForm.vue | B | **修复** |
| 63 | 删除角色 | `api/role.ts:deleteRole` | DELETE | /permissions/roles/{id} | DELETE /api/permissions/roles/{role_id} | role_id:int | — | {success} | {success}（系统角色拒删） | **superadmin**（修复） | system/roles/index.vue | B | **修复** |
| P15-P17 | ~~用户角色/菜单/权限单独查询~~ | ~~user-role.ts 封装（无调用，已删）~~ | GET | /permissions/user-roles/users/{id}/roles、/menus、/permissions | ~~同路径~~ | user_id:str | — | — | — | — | 前端无调用（resources 一次返回三者） | E | **已删除**（与 #53 功能重复）+ 删 crud.get_user_roles/menus/permissions |
| P18 | ~~角色详情(无菜单)~~ | ~~role.ts:getRoleById（无调用，已删）~~ | GET | /permissions/roles/{id} | ~~GET /api/permissions/roles/{role_id}~~ | role_id:int | — | Role | to_dict | 登录 | 前端无调用（详情均走 with-menus） | E | **已删除**（与 #60 重复）+ 删 crud.get_role_by_id |
| P19 | ~~为角色分配菜单~~ | ~~role.ts:assignMenusToRole（无调用，已删）~~ | PUT | /permissions/roles/{id}/menus | ~~PUT /api/permissions/roles/{role_id}/menus~~ | role_id:int | {menuIds} | Role | to_dict | 登录 | 前端无调用（创建/更新角色已含 menuIds） | E | **已删除**（功能被 RoleCreate/Update 覆盖）+ 删 crud.assign_menus + AssignMenusRequest |
| — | ~~为用户分配角色~~ | ~~user-role.ts:assignRolesToUser（已删）~~ | PUT | /permissions/user-roles/users/{userId}/roles | **后端从未存在** | — | {roleIds} | boolean | — | — | UserForm.vue:355（角色变更时） | **C** | **修复**：删除前端调用与封装；单角色设计下 role 随 PATCH /users/{id} 修改（见 #10），不再 405 |

### 2.8 AI 模型（ai_models.py，9 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|
| 64 | 模型列表 | `aiModelApi.getList` | GET | /admin/ai-models | GET /api/admin/ai-models | superadmin（原有） | system/ai_model/index.vue | A | 一致 |
| 65 | 活跃模型 | `aiModelApi.getActiveModels` | GET | /admin/ai-models/active | GET /api/admin/ai-models/active | teacher+superadmin（原有） | AiRuleForm.vue:331 | A | 一致 |
| 66 | 初始化 | ~~aiModelApi.initializeModels（无调用，保留）~~ | POST | /admin/ai-models/initialize | POST /api/admin/ai-models/initialize | superadmin | 前端无调用 | D | **保留**（运维初始化入口，见"五"） |
| 67 | 模型详情 | ~~aiModelApi.getDetail（无调用，保留）~~ | GET | /admin/ai-models/{code} | GET /api/admin/ai-models/{code} | superadmin | 前端无调用 | D | **保留**（详情 REST 端点，编辑弹窗回显用 getList 数据） |
| 68 | 更新配置 | `aiModelApi.updateConfig` | PUT | /admin/ai-models/{code} | PUT /api/admin/ai-models/{code} | superadmin | system/ai_model:557 | A | 一致 |
| 69 | 设默认 | `aiModelApi.setDefault` | POST | /admin/ai-models/{code}/default | POST /api/admin/ai-models/{code}/default | superadmin | system/ai_model:528 | A | 一致 |
| 70 | 余额 | `aiModelApi.getBalance` | GET | /admin/ai-models/{code}/balance | GET /api/admin/ai-models/{code}/balance | superadmin | system/ai_model:490 | A | 一致 |
| 71 | 连接测试 | `aiModelApi.testConnection` | POST | /admin/ai-models/{code}/test | POST /api/admin/ai-models/{code}/test | superadmin | system/ai_model:539 | A | 一致 |
| 72 | 用量统计 | ~~aiModelApi.getStats（无调用，保留）~~ | GET | /admin/ai-models/{code}/stats | GET /api/admin/ai-models/{code}/stats | superadmin | 前端无调用 | D | **保留**（用量统计 API，看板 ai-models 统计另有端点） |

### 2.9 AI 规则（ai_rules.py，8 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Body/Query | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 73 | 规则列表 | `api/ai-rule.ts:getAiRuleList` | GET | /v1/ai-rules | GET /api/v1/ai-rules | query: page,pageSize,status,visibility,modelType,search | teacher+superadmin（**修复**） | teacher/ai-rules/index.vue | B | **修复**：原仅登录（学生可读全部规则 prompt） |
| 74 | 可用规则 | `api/ai-rule.ts:getAvailableAiRules` | GET | /v1/ai-rules/available/list | query: status | teacher+superadmin（**修复**） | AiRuleSelector.vue | B | **修复** |
| 75 | 规则详情 | `api/ai-rule.ts:getAiRuleById` | GET | /v1/ai-rules/{id} | GET /api/v1/ai-rules/{rule_id} | — | teacher+superadmin（**修复**） | AiRuleDetail.vue | B | **修复** |
| 76 | 创建规则 | `api/ai-rule.ts:createAiRule` | POST | /v1/ai-rules | body: name,modelType,prompt,description?,maxScore?,criteria? | teacher+superadmin（**修复**；createdBy 注入当前用户） | AiRuleForm.vue | B | **修复**：原学生可创建批改规则 |
| 77 | 更新规则 | `api/ai-rule.ts:updateAiRule` | POST | /v1/ai-rules/{id}/update | body: 可选字段 | teacher+superadmin+**仅创建人/superadmin**（**修复**） | AiRuleForm.vue | B | **修复**：原任何登录用户可篡改任意规则 |
| 78 | 删除规则 | `api/ai-rule.ts:deleteAiRule` | POST | /v1/ai-rules/{id}/delete | — | 同上（**修复**） | teacher/ai-rules/index.vue | B | **修复** |
| 79 | 启停规则 | `api/ai-rule.ts:toggleAiRuleStatus` | POST | /v1/ai-rules/{id}/toggle-status | — | 同上（**修复**） | teacher/ai-rules/index.vue | B | **修复** |
| 80 | 复制规则 | `api/ai-rule.ts:copyAiRule` | POST | /v1/ai-rules/{id}/copy | body: {name?} | teacher+superadmin（副本归属复制者） | teacher/ai-rules/index.vue | B | **修复**：角色收紧 |

### 2.10 文件上传（upload.py 4 条 + 静态挂载 + templates.py 1 条）

| 编号 | 前端页面/功能 | 前端函数/调用点 | 方法 | 前端路径 | 后端路由 | Body/Form | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 81 | 上传附件 | SubmissionForm.vue:311（XHR 进度条，技术性绕行） | POST | /upload/files | POST /api/upload/files | FormData: files[] | 登录 | student/submissions/components/SubmissionForm.vue | A | 一致（XHR 为进度条所需，带 Bearer） |
| 82 | 下载文件 | FilePreviewDialog.vue:157 等 9 处裸 fetch（带 Bearer 取 blob） | GET | /upload/download/{filename} | GET /api/upload/download/{filename} | — | 登录+**路径穿越防护**（**修复**） | 多处 | B | **修复**：filename 含 `..`/分隔符直接 400；文件所有者模型缺失（见 G 类） |
| 83 | 预览文件 | FilePreviewDialog.vue:89（裸 fetch） | GET | /upload/preview/{filename} | GET /api/upload/preview/{filename} | — | 登录+路径穿越防护（**修复**） | FilePreviewDialog.vue | B | **修复**：同上 |
| 84 | 删除文件 | SubmissionForm.vue:352/366、assigmentsEidt:582（裸 fetch/XHR） | DELETE | /upload/delete/{filename} | DELETE /api/upload/delete/{filename} | — | 登录+路径穿越防护（**修复**：子目录文件如 plagiarism_tmp 不可删） | 3 处 | B | **修复**：任意登录用户原先可删任意根目录文件；所有者校验缺失列为 G 类 |
| 85 | 附件静态直链 | useSubmissionUtils.ts:56 `window.open(fileUrl)` 等 | GET | /uploads/...（无 /api 前缀） | main.py:68 静态挂载 | — | **无鉴权** | 学生附件展示、window.open | F/G | **保留**（静态服务改造见 G 类 #G1） |
| 86 | 下载导入模板 | `api/template.ts:downloadTemplate` | GET | /v1/templates/{type} | GET /api/v1/templates/{template_type}（**新增**） | — | teacher+superadmin | ImportUsersDialog.vue:221 | **C** | **补后端实现**：routers/templates.py 用 openpyxl 生成与前端解析列头一致的 xlsx；含 404/403 测试 |

### 2.11 查重（plagiarism.py，5 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Body/Query | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 87 | 临时查重 | `api/plagiarism.ts:adhocCheck` | POST | /plagiarism/adhoc-check | POST /api/plagiarism/adhoc-check | FormData: files[],template_file?,passRate?,phraseWeight?,topicWeight? | teacher+superadmin（原有） | teacher/plagiarism/index.vue | A | 一致 |
| 88 | 对比预览 | `api/plagiarism.ts:compareFiles` | GET | /plagiarism/{checkId}/compare | query: index_a,index_b | teacher+superadmin | teacher/plagiarism | A | 一致 |
| 89 | 下载报告 | `api/plagiarism.ts:downloadReport`（**改走封装**，原页面裸 fetch 重复实现已删除） | GET | /plagiarism/{checkId}/report | Excel 流 | teacher+superadmin | teacher/plagiarism/index.vue:685 | B | **修复**：api 层封装原类型声明错误（拦截器 blob 返回完整 response），已修正并统一入口 |
| 90 | AI 建议 | `api/plagiarism.ts:getAiSuggestion` | POST | /plagiarism/{checkId}/ai-suggestion | query: index,compare_index? | teacher+superadmin | teacher/plagiarism | A | 一致 |
| 91 | 清理临时文件 | `api/plagiarism.ts:cleanupCheckFiles` | DELETE | /plagiarism/{checkId}/files | — | teacher+superadmin | teacher/plagiarism | A | 一致 |

### 2.12 操作日志（logs.py，1 条）

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Query 参数 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 92 | 操作日志 | `api/logs.ts:getLogs` | GET | /admin/logs | GET /api/admin/logs | page,pageSize(1-100),operator,action,module,keyword,startDate,endDate | superadmin（原有，前后端均用 pageSize） | system/logs/index.vue | A | 一致 |

### 2.13 助手（assistant.py 15 条 + chat.py 5 条）

> 两套助手（新版 /assistant/* 多角色 SSE + 旧版 /teacher/assistant/* 仅教师）并存，均为页面实际功能，全部保留。

| 编号 | 前端页面/功能 | 前端函数 | 方法 | 前端路径 | 后端路由 | Token/角色要求 | 实际调用证据 | 分类 | 处理结果 |
|---|---|---|---|---|---|---|---|---|---|---|
| 93-107 | 新版助手（15 条） | `api/assistant.ts`（fetch SSE 流 + REST） | POST/GET/DELETE/PATCH | /assistant/runs/stream、/assistant/runs/{run_id}[/artifacts/cancel/feedback]、/assistant/sessions[...]、/assistant/approvals[...] | 同路径 | run/会话：三角色；审批：teacher+superadmin；admin content-access：superadmin（均原有且归属校验完整） | AssistantPanel.vue、AssistantApprovalView.vue、GradingDimensionsPanel.vue、useSubmissionManagement.ts、api/__tests__/assistant.spec.ts | A | 一致；SSE 用 fetch+ReadableStream（EventSource 不支持 POST），401 借道 axios 刷新链路重试 |
| 108-112 | 旧版教师助手（5 条） | 旧版页面/`chat` 相关 | POST/GET/DELETE | /teacher/assistant/chat/stream、/teacher/assistant/sessions[...] | 同路径 | teacher（SSE 流式） | 旧版教师助手入口 | F | **保留**（仍在使用的旧版功能通道，见"五"） |

---

## 三、B 类修复明细（不一致项）

| # | 问题 | 位置 | 修复 |
|---|---|---|---|
| 1 | `GET /api/users` 无鉴权（docstring 写"需登录"但未挂依赖），用户名录/邮箱/学号/手机号可匿名拉取 | routers/users.py | `require_roles("superadmin")`（调用方仅系统用户管理与系统班级选教师）；补 status 筛选实现（前端一直传但后端忽略） |
| 2 | 修改角色时前端先 PATCH 成功、再 PUT 不存在的 `/permissions/user-roles/users/{id}/roles` 导致"实际成功却提示失败" | UserForm.vue:346-360 | 删除第二次调用与 loadRoleMapping/roleMapping/getRoleList 依赖及前端封装；单角色统一走 PATCH |
| 3 | `mustChangePassword/avatar/meta` 等字段前后端不对齐 | schemas/user.py、types/user.ts | CreateUserDto 删除后端不接受的 avatar/meta；后端保留 mustChangePassword 默认 false（管理员新增用户不强制首改密；批量导入/重置密码则强制）；UpdateUserDto 保留 avatar（后端接受且模型有列） |
| 4 | UserStatus 前端两值 vs 后端三值 | types/user.ts:9 | 补 `locked`；UserForm 状态单选与列表筛选补"锁定"选项；表格开关对 locked 显示为关、开启即解锁 |
| 5 | 创建/更新用户后端零校验（可绕过前端直接打接口） | schemas/user.py、crud/user.py | 服务端校验：username 2-20、name 非空、邮箱正则、密码≥6、role/status Literal 枚举、手机号 `1[3-9]\d{9}`、学生必填学号、非学生清空学号、用户名/邮箱/学号唯一性（学号原可重复创建） |
| 6 | 批改三端点无教师归属校验（列表全校泄露、详情/批改可被任意登录用户操作） | routers/correcting.py、crud/correcting.py | teacher 角色限制 + `_assert_teacher_ownership`；列表按 Assignment.teacher_id 过滤 |
| 7 | 看板 12 端点仅登录未限角色；权限菜单/角色 16 端点学生可增删改 | routers/dashboard.py、routers/permissions.py | 按路径前缀收紧（admin→superadmin、teacher→teacher、student→student；菜单/角色→superadmin；用户资源仅可查自己） |

其余 B 类（班级详情/学生名单、作业详情/学生列表、解散/重置邀请码管理员越权、AI 规则归属、上传路径穿越、教师删提交与查重下载绕过 api 层）已在总表逐行标注，均为本次修复并附测试。

---

## 四、C 类处理结果（前端调用、后端不存在）

| 前端调用 | 调用位置 | 处理 |
|---|---|---|
| PUT /api/permissions/user-roles/users/{userId}/roles | UserForm.vue（角色变更） | **删除前端调用**（页面逻辑冗余——PATCH 已含 role；按单角色设计不为保留错误前端新增多角色接口） |
| GET /api/v1/templates/user-import | api/template.ts → ImportUsersDialog.vue"下载导入模板"按钮 | **补后端实现**（routers/templates.py，openpyxl 生成列头为 用户名/姓名/邮箱/学号/手机号 的 xlsx；teacher+superadmin；已测 200/404/403） |

---

## 五、保留但前端未使用的接口及保留原因（D/F 类）

| 接口 | 分类 | 保留原因 |
|---|---|---|
| GET /api/admin/dashboard/health | F | 运维健康检查（用户规则明确健康检查/运维接口保留） |
| POST /api/admin/ai-models/initialize | D | 模型初始化运维入口（superadmin 专用，部署期使用） |
| GET /api/admin/ai-models/{code}、/stats | D | AI 模型详情/用量统计 REST 端点（模块完整性；编辑回显当前用列表数据，详情端点留作运维与外部诊断） |
| GET /api/uploads/*（静态挂载） | F/G | 学生附件、查重标黄 PDF 的展示直链（img/window.open 无法带 Bearer）；加鉴权需改前端展示链路，列入 G 类决策 |
| POST /api/assistant/runs/stream 等 15 条 | A/F | 新版助手页面实际使用（SSE/审批/产物） |
| /api/teacher/assistant/* 5 条 | F | 旧版教师助手仍在使用（SSE 流式通道），非死代码 |
| POST /api/teacher/assignments/{id}/plagiarism 等 | A | 教师作业查重页面实际使用 |
| 上传/下载/预览/删除 4 条 | A/F | 10 处前端调用（XHR 进度条与 blob 预览的技术性绕行均带 Bearer，路径已穿越加固） |

后端内部调用不经过 router、不受本次删除影响：agent/service.py、agent/tools/*、tasks/grading.py（Celery）、middleware/operation_log.py、seed.py 等直接调用 crud（agent_run/agent_session/agent_chat/ai_model.increment_usage/submission.apply_ai_grading_result/agent_approval/operation_log 等），已逐一核对无引用被删除函数。

---

## 六、G 类：需人工确认（未自动处理）

| # | 事项 | 现状与建议 |
|---|---|---|
| G1 | `/uploads` 静态文件无鉴权（学生附件、查重标黄 PDF 可凭 URL 访问） | 静态服务无法校验 JWT；前端 img/window.open 直链不带 Authorization。若要收紧需引入签名 URL 或文件所有权表并改造前端展示链路，超出本次一致性范围，建议单独立项 |
| G2 | 上传文件的"所有者"校验缺失（uploads 无归属表，download/preview/delete 仅登录+路径加固） | 需新增文件所有权模型（filename→owner）或在提交/作业附件中反查，涉及 schema 变更；当前已阻断路径穿越与子目录（plagiarism_tmp）删除 |
| G3 | `users.role_ids` 死字段（模型+baseline 迁移中定义，后端无任何读写；权限逻辑实际基于 User.role ↔ Role.code） | 全仓库仅 2 处引用（模型定义+建列迁移）。按"删除需全仓库引用检查+安全迁移"原则，本次保留未删；to_dict 仍输出 roleIds:[]，无害。如需删除应出独立迁移并确认无外部消费方 |

另：本次新增学号唯一索引迁移 `f8d2a4c1e9b3` 内置重复数据守卫（存在重复学号时迁移失败并列出前 20 组），本环境无 `.env`/生产库可连，无法预检生产数据；执行迁移前可先跑检查 SQL：
`SELECT student_id, COUNT(*) c FROM users WHERE student_id IS NOT NULL AND student_id<>'' GROUP BY student_id HAVING c>1;`

---

## 七、验证结果

| 验证项 | 命令 | 结果 |
|---|---|---|
| 后端单测 | `D:\miniforge\envs\scientific_research\python.exe -m pytest backend_python/tests -q` | **773 passed**（含新增 71 个契约/权限用例） |
| 后端语法 | `python -m compileall -q backend_python/app backend_python/alembic/versions backend_python/tests` | 通过（exit 0） |
| 路由/OpenAPI | 临时脚本 `app.openapi()` | **96 paths / 111 operations**（审计前 129 条 → 删 18 增 1） |
| 前端单测 | `npm test` | **221 passed（33 files）**（含新增 UserForm.spec 2 例、更新 auth-request/user.spec） |
| 前端类型 | `npx vue-tsc --noEmit` | 通过（0 错误） |
| 前端构建 | `npm run build` | 成功 |
| 前端 lint | `npm run lint` | **无法运行（既有问题）**：frontend 目录无 `.gitignore`（lint 脚本 `--ignore-path .gitignore` 报 ENOENT）且项目无任何 ESLint 配置文件（.eslintrc.*）。与本次改动无关，列入待人工处理 |

### 新增测试覆盖

- `tests/unit/test_auth_removed_endpoints.py`：注册×2/旧版登录/忘记密码/重置密码均 404；登录仍可用。
- `tests/unit/test_users_api.py`（31 例）：11 项参数校验（缺学号/非法邮箱/密码<6/空白用户名/空白姓名/非法角色/非法状态/手机号格式×2 等）、重复用户名/邮箱/学号 409、教师与超管免学号、非学生清除学号、GET /users 四种鉴权（无 token/学生/教师/超管）与敏感字段检查、status 筛选、单 PATCH 改角色及角色-学号联动、locked 状态、教师不可新增。
- `tests/security/test_api_permission_guards.py`（27 例）：看板角色隔离、菜单/角色 superadmin 限制、用户资源自查限制、批改列表数据范围与详情/批改归属、作业详情/学生列表归属、班级详情/名单访问控制、AI 规则创建人校验、上传路径穿越、模板下载 200/404/403。
- `frontend/.../UserForm.spec.ts`（2 例）：修改角色只发一个 PATCH、不再调用 assignRolesToUser/getRoleList、非学生不带学号。
