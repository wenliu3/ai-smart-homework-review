/**
 * 格式化日期时间
 * @param date 日期对象或日期字符串
 * @param format 格式化模板，默认为 'YYYY-MM-DD HH:mm:ss'
 * @returns 格式化后的日期字符串
 */
export const formatDate = (
  date: Date | string | number,
  format = "YYYY-MM-DD HH:mm:ss"
): string => {
  const d = new Date(date);

  if (isNaN(d.getTime())) {
    return "无效日期";
  }

  const year = d.getFullYear();
  const month = d.getMonth() + 1;
  const day = d.getDate();
  const hours = d.getHours();
  const minutes = d.getMinutes();
  const seconds = d.getSeconds();

  const formatMap: Record<string, number> = {
    YYYY: year,
    MM: month,
    DD: day,
    HH: hours,
    mm: minutes,
    ss: seconds,
  };

  return format.replace(/(YYYY|MM|DD|HH|mm|ss)/g, (match) => {
    const value = formatMap[match];
    return match === "YYYY"
      ? String(value)
      : value < 10
      ? `0${value}`
      : String(value);
  });
};

/**
 * 友好的时间显示
 * @param date 日期对象或日期字符串
 * @returns 友好的时间显示
 */
export const friendlyDate = (date: Date | string | number): string => {
  const d = new Date(date);

  if (isNaN(d.getTime())) {
    return "无效日期";
  }

  const now = new Date();
  const diff = now.getTime() - d.getTime();

  // 小于1分钟
  if (diff < 60 * 1000) {
    return "刚刚";
  }

  // 小于1小时
  if (diff < 60 * 60 * 1000) {
    return `${Math.floor(diff / (60 * 1000))}分钟前`;
  }

  // 小于1天
  if (diff < 24 * 60 * 60 * 1000) {
    return `${Math.floor(diff / (60 * 60 * 1000))}小时前`;
  }

  // 小于30天
  if (diff < 30 * 24 * 60 * 60 * 1000) {
    return `${Math.floor(diff / (24 * 60 * 60 * 1000))}天前`;
  }

  // 其他情况返回完整日期
  return formatDate(d, "YYYY-MM-DD");
};
