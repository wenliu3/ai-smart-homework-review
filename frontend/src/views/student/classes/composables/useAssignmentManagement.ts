import {
  SuccessFilled,
  CircleCheck,
  Edit,
  DocumentCopy,
  Timer,
  InfoFilled,
} from "@element-plus/icons-vue";

export function useAssignmentManagement() {
  // 获取作业状态类型
  const getAssignmentStatusType = (
    status: string
  ): "success" | "warning" | "info" | "primary" | "danger" => {
    const statusMap: Record<
      string,
      "success" | "warning" | "info" | "primary" | "danger"
    > = {
      draft: "info",
      published: "success",
      terminated: "danger",
    };
    return statusMap[status] || "info";
  };

  // 获取作业状态文本
  const getAssignmentStatusText = (status: string) => {
    const statusMap: Record<string, string> = {
      draft: "草稿",
      published: "进行中",
      terminated: "已终止",
    };
    return statusMap[status] || "未知";
  };

  // 判断作业是否过期
  const isAssignmentExpired = (assignment: any) => {
    if (!assignment.endDate) return false;
    return new Date() > new Date(assignment.endDate);
  };

  // 获取作业状态图标
  const getAssignmentIcon = (assignment: any) => {
    // 已提交优先显示
    if (assignment.hasSubmitted) {
      return CircleCheck;
    }

    // 有草稿但未提交
    if (assignment.hasDraft && !assignment.hasSubmitted) {
      return Edit;
    }

    // 未提交且过期显示警告图标
    if (isAssignmentExpired(assignment)) {
      return Timer;
    }

    // 未提交且未过期，根据作业状态显示
    const statusMap: Record<string, any> = {
      draft: Edit,
      published: SuccessFilled,
      terminated: DocumentCopy,
    };
    return statusMap[assignment.status] || InfoFilled;
  };

  // 获取作业图标颜色
  const getAssignmentIconColor = (assignment: any) => {
    // 已提交优先显示绿色
    if (assignment.hasSubmitted) {
      return "#67C23A";
    }

    // 有草稿但未提交显示蓝色
    if (assignment.hasDraft && !assignment.hasSubmitted) {
      return "#409EFF";
    }

    // 未提交且过期显示红色
    if (isAssignmentExpired(assignment)) {
      return "#F56565";
    }

    // 未提交且未过期，根据作业状态显示颜色
    const colorMap: Record<string, string> = {
      draft: "#909399",
      published: "#E6A23C",
      terminated: "#909399",
    };
    return colorMap[assignment.status] || "#909399";
  };

  return {
    getAssignmentStatusType,
    getAssignmentStatusText,
    isAssignmentExpired,
    getAssignmentIcon,
    getAssignmentIconColor,
  };
}
