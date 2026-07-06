# 跨班级作业提交防冲突解决方案

## 问题背景

在多班级作业场景中，同一个学生可能同时在多个班级，并且同一个作业可能分配给多个班级。这导致了一个业务冲突：

**原始问题**：

```
E11000 duplicate key error collection: fullstack-app.submissions
index: assignmentId_1_studentId_1_classId_1
dup key: { assignmentId: ObjectId('...'), studentId: ObjectId('...'), classId: ObjectId('...') }
```

**业务场景冲突**：

- 学生张三同时在高三 1 班和数学提高班
- 数学作业 A 分配给了这两个班级
- 张三在高三 1 班提交了作业 A
- 张三在数学提高班又尝试提交作业 A → 产生冲突

## 解决方案

### 🎯 设计思路

采用**最小代价前端解决方案**：

1. **后端 API 增强**：检测跨班级提交情况
2. **前端友好提示**：显示"已在其他班级提交"状态
3. **防止重复提交**：禁用已提交作业的操作
4. **避免数据修改**：不改变现有数据库结构

### 🔧 技术实现

#### 后端修改

##### 1. 作业查询服务增强 (`AssignmentQueryService`)

```typescript
// 检查学生提交状态（包含跨班级检查）
private async checkStudentSubmission(
  assignmentId: string,
  userId: string,
  currentClassId?: string
): Promise<{
  hasSubmitted: boolean;
  hasDraft: boolean;
  status?: SubmissionStatus;
  submissionId?: string;
  hasSubmittedInOtherClass?: boolean;  // 新增：是否在其他班级提交
  otherClassSubmission?: any;          // 新增：其他班级提交信息
}>
```

**逻辑流程**：

1. 先检查当前班级是否有提交
2. 如果当前班级已提交 → 返回正常状态
3. 如果当前班级未提交 → 检查其他班级
4. 如果其他班级有提交 → 返回跨班级提交状态

##### 2. 业务状态扩展 (`AssignmentCommonService`)

```typescript
// 新增业务状态
private getBusinessStatus(
  hasSubmitted: boolean,
  isExpired: boolean,
  hasDraft: boolean = false,
  hasSubmittedInOtherClass: boolean = false  // 新增参数
): string {
  if (hasSubmitted) return 'completed';
  if (hasSubmittedInOtherClass) return 'submitted_elsewhere'; // 新状态
  if (hasDraft && !hasSubmitted) return 'draft';
  if (isExpired) return 'expired';
  return 'todo';
}
```

##### 3. API 响应格式扩展

```typescript
// 学生作业列表响应新增字段
{
  id: string,
  title: string,
  // ... 其他字段
  hasSubmittedInOtherClass: boolean,      // 是否在其他班级提交
  otherClassSubmission: {                 // 其他班级提交详情
    className: string,                    // 提交的班级名称
    status: SubmissionStatus,             // 提交状态
    submittedAt: Date                     // 提交时间
  } | null,
  canSubmit: boolean,                     // 是否可以提交（考虑跨班级情况）
  businessStatus: string                  // 业务状态（包含submitted_elsewhere）
}
```

#### 前端修改

##### 1. 状态标签扩展

```vue
<!-- 新增"已在其他班级提交"状态标签 -->
<el-tag
  v-else-if="assignment.hasSubmittedInOtherClass"
  type="danger"
  size="small"
  effect="light"
  class="mr-2"
>
  已在其他班级提交
</el-tag>
```

##### 2. 筛选选项扩展

```vue
<!-- 新增筛选选项 -->
<el-radio-group v-model="assignmentFilter" size="default">
  <el-radio-button value="all">全部</el-radio-button>
  <el-radio-button value="todo">待办</el-radio-button>
  <el-radio-button value="draft">草稿</el-radio-button>
  <el-radio-button value="completed">已提交</el-radio-button>
  <el-radio-button value="submitted_elsewhere">其他班级已提交</el-radio-button>  <!-- 新增 -->
  <el-radio-button value="expired">已过期</el-radio-button>
</el-radio-group>
```

##### 3. 作业卡片样式优化

```vue
<!-- 根据状态调整卡片样式 -->
<el-card
  :class="[
    'transition-all duration-200',
    assignment.hasSubmittedInOtherClass
      ? 'cursor-not-allowed opacity-60 bg-gray-50'  // 禁用样式
      : 'cursor-pointer hover:shadow-md'            // 正常样式
  ]"
  @click="handleAssignmentClick(assignment)"
>
```

##### 4. 详细信息提示

```vue
<!-- 显示具体在哪个班级提交的 -->
<div
  v-if="assignment.hasSubmittedInOtherClass && assignment.otherClassSubmission"
  class="mt-2 text-xs text-orange-600 bg-orange-50 p-2 rounded"
>
  <el-icon class="mr-1"><InfoFilled /></el-icon>
  已在「{{ assignment.otherClassSubmission.className }}」班级提交
  <span v-if="assignment.otherClassSubmission.submittedAt">
    （{{ formatDate(assignment.otherClassSubmission.submittedAt) }}）
  </span>
</div>
```

##### 5. 点击拦截处理

```typescript
// 处理作业点击事件
const handleAssignmentClick = (assignment) => {
  // 如果已在其他班级提交，显示提示并阻止进入
  if (assignment.hasSubmittedInOtherClass) {
    const className = assignment.otherClassSubmission?.className || "其他班级";
    ElMessage.warning(
      `该作业已在「${className}」班级提交，无法在当前班级重复作答`
    );
    return;
  }

  // 正常跳转到作业详情
  viewAssignment(assignment.id);
};
```

## 🎨 用户体验设计

### 视觉状态区分

1. **正常可作答作业**：

   - 正常悬停效果
   - 清晰的状态标签
   - 可点击进入

2. **已在其他班级提交**：

   - 灰色背景，降低不透明度
   - 红色"已在其他班级提交"标签
   - 详细提示信息（班级名称、提交时间）
   - 禁用点击（cursor-not-allowed）

3. **交互反馈**：
   - 点击已提交作业时显示友好提示
   - 明确告知在哪个班级已提交
   - 避免用户困惑

### 筛选和查找

1. **新增筛选选项**：

   - "其他班级已提交"独立筛选
   - 方便教师和学生快速查看跨班级情况

2. **状态优先级**：
   ```
   已提交（当前班级） > 已在其他班级提交 > 有草稿 > 未提交
   ```

## 🔍 业务场景示例

### 场景 1：学生视角

**张三的班级情况**：

- 正式班级：高三 1 班
- 补课班级：数学提高班

**作业分配**：

- 数学练习 A：分配给 [高三 1 班, 数学提高班]

**操作流程**：

1. 张三在高三 1 班提交了数学练习 A
2. 张三切换到数学提高班查看作业列表
3. 看到数学练习 A 显示"已在其他班级提交"
4. 卡片呈灰色状态，显示"已在「高三 1 班」班级提交"
5. 点击时提示：该作业已在「高三 1 班」班级提交，无法在当前班级重复作答

### 场景 2：教师视角

**李老师的班级**：

- 同时负责高三 1 班和数学提高班

**查看学生提交情况**：

1. 在数学提高班的批改界面
2. 看到张三没有在当前班级提交
3. 但系统显示张三已在高三 1 班提交
4. 避免误判学生未完成作业

## ✅ 方案优势

### 1. 最小化改动

- ✅ 不需要修改数据库结构
- ✅ 不需要数据迁移
- ✅ 不影响现有功能

### 2. 用户友好

- ✅ 清晰的状态提示
- ✅ 详细的操作反馈
- ✅ 避免用户困惑

### 3. 业务合理

- ✅ 支持多班级场景
- ✅ 防止重复提交
- ✅ 保持数据一致性

### 4. 技术可靠

- ✅ 前端防护为主
- ✅ 后端数据增强
- ✅ 降低系统风险

## 🚀 扩展可能

未来如果需要，可以考虑：

1. **批量操作优化**：允许教师批量查看学生的跨班级提交情况
2. **报告增强**：在班级报告中显示跨班级提交统计
3. **权限细化**：配置是否允许跨班级提交的策略
4. **通知机制**：当学生在其他班级提交时，通知相关教师

## 📝 总结

这个解决方案通过前端用户体验优化，有效解决了跨班级作业提交的冲突问题，既保持了系统的灵活性，又避免了复杂的数据库层面修改。用户可以清晰地了解作业的提交状态，避免重复提交，同时为多班级教学场景提供了良好的支持。
