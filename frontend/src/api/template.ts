import { downloadFile } from "@/utils/request";

/**
 * 下载模板文件
 * @param type 模板类型
 * @param filename 文件名
 */
export const downloadTemplate = (type: string, filename?: string) => {
  return downloadFile(
    `/v1/templates/${type}`,
    undefined,
    filename || `${type}_template.xlsx`
  );
};
