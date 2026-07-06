import { format, formatDistanceToNow, isValid, parseISO } from "date-fns";
import { zhCN } from "date-fns/locale";

/**
 * 格式化日期时间
 * @param date 日期字符串或Date对象
 * @param formatStr 格式化字符串
 * @returns 格式化后的日期字符串
 */
export function formatDateTime(
  date: string | Date,
  formatStr: string = "yyyy-MM-dd HH:mm"
): string {
  if (!date) return "--";

  try {
    const dateObj = typeof date === "string" ? parseISO(date) : date;

    if (!isValid(dateObj)) {
      return "--";
    }

    return format(dateObj, formatStr, { locale: zhCN });
  } catch (error) {
    console.warn("日期格式化失败:", error);
    return "--";
  }
}

/**
 * 格式化日期（不包含时间）
 * @param date 日期字符串或Date对象
 * @returns 格式化后的日期字符串
 */
export function formatDate(date: string | Date): string {
  return formatDateTime(date, "yyyy-MM-dd");
}

/**
 * 格式化时间（不包含日期）
 * @param date 日期字符串或Date对象
 * @returns 格式化后的时间字符串
 */
export function formatTime(date: string | Date): string {
  return formatDateTime(date, "HH:mm:ss");
}

/**
 * 格式化相对时间（多久之前）
 * @param date 日期字符串或Date对象
 * @returns 相对时间字符串
 */
export function formatRelativeTime(date: string | Date): string {
  if (!date) return "--";

  try {
    const dateObj = typeof date === "string" ? parseISO(date) : date;

    if (!isValid(dateObj)) {
      return "--";
    }

    return formatDistanceToNow(dateObj, {
      addSuffix: true,
      locale: zhCN,
    });
  } catch (error) {
    console.warn("相对时间格式化失败:", error);
    return "--";
  }
}

/**
 * 检查日期是否为今天
 * @param date 日期字符串或Date对象
 * @returns 是否为今天
 */
export function isToday(date: string | Date): boolean {
  if (!date) return false;

  try {
    const dateObj = typeof date === "string" ? parseISO(date) : date;
    const today = new Date();

    return dateObj.toDateString() === today.toDateString();
  } catch (error) {
    return false;
  }
}

/**
 * 检查日期是否即将到期（24小时内）
 * @param date 日期字符串或Date对象
 * @returns 是否即将到期
 */
export function isUrgent(date: string | Date): boolean {
  if (!date) return false;

  try {
    const dateObj = typeof date === "string" ? parseISO(date) : date;
    const now = new Date();
    const hoursLeft = (dateObj.getTime() - now.getTime()) / (1000 * 60 * 60);

    return hoursLeft > 0 && hoursLeft < 24;
  } catch (error) {
    return false;
  }
}

/**
 * 获取日期范围描述
 * @param startDate 开始日期
 * @param endDate 结束日期
 * @returns 日期范围描述
 */
export function getDateRangeText(
  startDate: string | Date,
  endDate: string | Date
): string {
  if (!startDate || !endDate) return "--";

  try {
    const start =
      typeof startDate === "string" ? parseISO(startDate) : startDate;
    const end = typeof endDate === "string" ? parseISO(endDate) : endDate;

    if (!isValid(start) || !isValid(end)) {
      return "--";
    }

    const startStr = format(start, "MM-dd", { locale: zhCN });
    const endStr = format(end, "MM-dd", { locale: zhCN });

    return `${startStr} 至 ${endStr}`;
  } catch (error) {
    console.warn("日期范围格式化失败:", error);
    return "--";
  }
}

/**
 * 计算两个日期之间的天数差
 * @param date1 日期1
 * @param date2 日期2
 * @returns 天数差（正数表示date1在date2之后）
 */
export function getDaysDifference(
  date1: string | Date,
  date2: string | Date
): number {
  if (!date1 || !date2) return 0;

  try {
    const d1 = typeof date1 === "string" ? parseISO(date1) : date1;
    const d2 = typeof date2 === "string" ? parseISO(date2) : date2;

    if (!isValid(d1) || !isValid(d2)) {
      return 0;
    }

    const diffTime = d1.getTime() - d2.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  } catch (error) {
    return 0;
  }
}

/**
 * 格式化持续时间（秒转换为可读格式）
 * @param seconds 秒数
 * @returns 格式化后的持续时间
 */
export function formatDuration(seconds: number): string {
  if (!seconds || seconds < 0) return "0秒";

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hours > 0) {
    return `${hours}小时${minutes}分钟`;
  } else if (minutes > 0) {
    return `${minutes}分钟${secs}秒`;
  } else {
    return `${secs}秒`;
  }
}
