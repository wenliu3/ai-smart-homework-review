# AI 规则管理模块

## 功能概述

AI 规则管理模块是一个完整的前端模块，用于管理 AI 提示词规则。该模块采用模块化设计，减少耦合，使用 Element Plus 组件库构建用户界面。

## 主要功能

### 1. 规则管理

- **创建规则**：支持创建新的 AI 规则，包含名称、描述、模型类型、提示词等信息
- **编辑规则**：修改现有规则的各项属性
- **删除规则**：软删除规则（系统规则不可删除）
- **复制规则**：快速复制现有规则并创建新规则

### 2. 查询和筛选

- **搜索功能**：支持按规则名称搜索
- **状态筛选**：按启用/禁用状态筛选
- **可见性筛选**：按私有/公开/系统可见性筛选
- **模型类型筛选**：目前只支持 DeepSeek 模型
- **分页显示**：支持分页浏览，可调整每页显示数量

### 3. 规则详情

- **完整信息展示**：查看规则的所有详细信息
- **提示词预览**：专门的提示词内容展示区域
- **复制功能**：一键复制提示词内容
- **权限控制**：根据用户权限显示编辑按钮

### 4. 权限管理

- **角色权限**：只有教师和管理员可以管理 AI 规则
- **所有权控制**：用户只能编辑自己创建的规则
- **管理员特权**：管理员可以管理所有规则，包括创建系统规则

## 技术特性

### 1. 响应式设计

- 支持桌面端和移动端适配
- 移动端使用下拉菜单优化操作体验
- 自适应布局，在不同屏幕尺寸下都有良好表现

### 2. 组件化架构

- **模块独立**：完全独立的模块，可以单独部署和维护
- **组件拆分**：按功能拆分为表格、表单、详情等独立组件
- **低耦合**：组件间通过事件通信，减少直接依赖

### 3. 用户体验

- **加载状态**：所有异步操作都有加载提示
- **错误处理**：完善的错误提示和异常处理
- **操作反馈**：操作成功/失败都有明确的用户反馈
- **数据验证**：前端表单验证，确保数据质量

## 目录结构

```
src/views/teacher/ai-rules/
├── index.vue                    # 主页面
├── components/                  # 组件目录
│   ├── AiRuleTable.vue         # 规则列表表格组件
│   ├── AiRuleForm.vue          # 规则表单组件（新增/编辑）
│   └── AiRuleDetail.vue        # 规则详情组件
├── README.md                   # 模块说明文档
└── api/
    └── ai-rule.ts              # API接口封装
```

## 组件说明

### 1. AiRuleTable.vue - 规则列表表格

**功能**：

- 展示规则列表数据
- 支持响应式布局
- 提供操作按钮（查看、编辑、复制、删除）

**Props**：

- `ruleData`: 规则数据数组
- `loading`: 加载状态
- `isMobile`: 是否为移动端

**Events**：

- `edit`: 编辑规则
- `delete`: 删除规则
- `copy`: 复制规则
- `view`: 查看规则详情

### 2. AiRuleForm.vue - 规则表单

**功能**：

- 创建新规则
- 编辑现有规则
- 表单验证
- 权限控制（系统规则仅管理员可创建）

**Props**：

- `isMobile`: 是否为移动端

**Events**：

- `success`: 操作成功

**Methods**：

- `openForm(mode, ruleId)`: 打开表单，mode 为'add'或'edit'

### 3. AiRuleDetail.vue - 规则详情

**功能**：

- 展示规则完整信息
- 提示词内容预览
- 复制提示词功能
- 权限控制编辑按钮

**Props**：

- `isMobile`: 是否为移动端

**Events**：

- `success`: 操作成功
- `edit`: 编辑规则

**Methods**：

- `openDetail(ruleId)`: 打开详情页面

## API 接口

### 接口列表

- `GET /api/v1/ai-rules` - 获取规则列表
- `GET /api/v1/ai-rules/:id` - 获取规则详情
- `POST /api/v1/ai-rules` - 创建规则
- `POST /api/v1/ai-rules/:id/update` - 更新规则
- `POST /api/v1/ai-rules/:id/delete` - 删除规则
- `POST /api/v1/ai-rules/:id/copy` - 复制规则
- `GET /api/v1/ai-rules/available/list` - 获取可用规则列表

### 数据结构

```typescript
interface AiRule {
  id: string;
  name: string;
  description?: string; // 可选字段，规则描述
  modelType: "deepseek"; // 目前只支持DeepSeek模型
  prompt: string;
  status: "active" | "inactive";
  visibility: "private" | "public" | "system";
  tags: string[];
  createdBy?: {
    id: string;
    name: string;
  };
  createdAt: string;
  updatedAt: string;
}
```

## 使用方法

### 1. 基本使用

```vue
<template>
  <div>
    <!-- AI规则管理页面 -->
    <router-view />
  </div>
</template>
```

### 2. 路由配置

```javascript
{
  path: '/teacher/ai-rules',
  name: 'AiRules',
  component: () => import('@/views/teacher/ai-rules/index.vue'),
  meta: {
    title: 'AI规则管理',
    requiresAuth: true,
    roles: ['teacher', 'super_admin']
  }
}
```

### 3. 权限配置

确保用户具有教师或管理员角色才能访问此模块。

## 样式说明

### 1. 自定义样式

模块使用少量自定义样式，主要用于：

- 响应式布局辅助类
- 提示词内容的代码字体显示
- 标签和状态的间距调整

### 2. Element Plus 主题

完全基于 Element Plus 的默认主题，确保与系统整体风格一致。

## 扩展说明

### 1. 添加新功能

- 在对应组件中添加新的方法和事件
- 在 API 文件中添加新的接口调用
- 更新类型定义

### 2. 自定义样式

- 优先使用 Tailwind CSS 类
- 必要时在组件的`<style scoped>`中添加自定义样式
- 保持与 Element Plus 主题的一致性

### 3. 国际化

- 所有文本都可以提取为国际化配置
- 使用 Vue I18n 进行多语言支持

## 注意事项

1. **权限控制**：确保后端 API 有相应的权限验证
2. **数据验证**：前后端都需要进行数据验证
3. **错误处理**：所有 API 调用都需要适当的错误处理
4. **性能优化**：大量数据时考虑虚拟滚动或分页加载
5. **安全性**：提示词内容可能包含敏感信息，注意权限控制
