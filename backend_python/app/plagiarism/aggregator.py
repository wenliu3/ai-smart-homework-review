"""双维度查重结果合并 —— 将文本和图片两个维度的独立查重结果合并为一份综合报告。

职责:
  1. 按 (studentName, studentNumber) 关联两个维度的结果
  2. 生成"疑似抄袭原因"描述（如"文字+图片"），说明具体是哪个维度触发的
  3. 任意一个维度不合格即整体判定为"疑似抄袭"，但保留两个维度的具体数值，不合并为一个总分

路由层和 CRUD 层只需要调 aggregator.merge_results()，不用自己拼两个函数的返回值。
"""
from .config import PASS_RATE


def _build_suspect_reason(r: dict) -> str:
    """根据两个维度的 status 生成"疑似原因"描述"""
    reasons = []
    if r.get("status") and r["status"] not in ("合格", "-", None):
        reasons.append("文字")
    if r.get("imageStatus") and r["imageStatus"] not in ("合格", "-", None):
        reasons.append("图片")
    return "+".join(reasons) if reasons else ""


def _merge_image(merged: dict, key, image_map: dict):
    """把图片维度结果合并进 merged"""
    ir = image_map.get(key)
    if ir:
        merged["imageRate"] = ir["imageRate"]
        merged["imageStatus"] = ir["status"]
        merged["imageMatchName"] = ir["matchName"]
        merged["imageMatchId"] = ir["matchId"]
        merged["matchedImageCount"] = ir.get("matchedImageCount", 0)
        merged["totalImageCount"] = ir.get("totalImageCount", 0)
        merged["lowConfidence"] = ir.get("lowConfidence", False)
    else:
        merged["imageRate"] = None
        merged["imageStatus"] = "-"
        merged["imageMatchName"] = "-"
        merged["imageMatchId"] = "-"
        merged["matchedImageCount"] = 0
        merged["totalImageCount"] = 0
        merged["lowConfidence"] = False


def _max_rate(r: dict) -> float:
    """取两个维度中的最大重复率，用于排序"""
    rates = []
    if r.get("rate") is not None:
        rates.append(r["rate"])
    if r.get("imageRate") is not None:
        rates.append(r["imageRate"])
    return max(rates) if rates else 0


def merge_results(
    text_result: dict,
    code_result: dict = None,
    image_result: dict = None,
    skipped: list = None,
) -> dict:
    """合并文本和图片两个维度的查重结果。

    参数:
        text_result: run_plagiarism_check() 的返回值（作为基准，因为文本是必选维度）
        code_result: 已废弃，保留参数兼容旧调用，始终为 None
        image_result: run_image_plagiarism_check() 的返回值（可选）
        skipped: 额外的跳过记录（如文件解析失败），会合并到最终结果的 skipped 中

    返回:
        合并后的综合查重结果，包含每个学生的双维度数据、疑似原因、
        以及各维度的统计汇总。
    """
    image_result = image_result or {}

    # 构建 key → 各维度结果的映射
    image_map = {}
    for ir in image_result.get("results", []):
        image_map[(ir["studentName"], ir["studentNumber"])] = ir

    text_map = {}
    for tr in text_result.get("results", []):
        text_map[(tr["studentName"], tr["studentNumber"])] = tr

    # 收集所有出现过的学生 key
    all_keys = set()
    for tr in text_result.get("results", []):
        all_keys.add((tr["studentName"], tr["studentNumber"]))
    for ir in image_result.get("results", []):
        all_keys.add((ir["studentName"], ir["studentNumber"]))

    # 合并每个学生的双维度数据
    merged_results = []
    for key in all_keys:
        tr = text_map.get(key)
        if tr:
            merged = dict(tr)
        else:
            # 该学生没有文本结果（可能文本太短被跳过）
            merged = {
                "submissionId": None,
                "studentName": key[0],
                "studentNumber": key[1],
                "rate": None,
                "phraseRate": None,
                "topicRate": None,
                "status": "-",
                "matchName": "-",
                "matchId": "-",
                "matchSubmissionId": None,
                "matchedSnippets": [],
            }
        _merge_image(merged, key, image_map)
        merged["suspectReason"] = _build_suspect_reason(merged)
        merged_results.append(merged)

    # 按 max(文本rate, 图片imageRate) 降序
    merged_results.sort(key=_max_rate, reverse=True)

    # 整体疑似抄袭：任一维度不合格
    overall_suspect = sum(1 for r in merged_results if r["suspectReason"])

    all_skipped = (skipped or []) + text_result.get("skipped", [])

    has_image = bool(image_result.get("results"))

    result = {
        "results": merged_results,
        "skipped": all_skipped,
        "total": len(merged_results),
        "suspectCount": overall_suspect,
        "passRate": text_result.get("passRate", PASS_RATE),
        "templateFiltered": text_result.get("templateFiltered", False),
        "textResult": {
            "total": text_result.get("total", 0),
            "suspectCount": text_result.get("suspectCount", 0),
            "autoCommonFiltered": text_result.get("autoCommonFiltered", False),
        },
        "imageResult": {
            "total": image_result.get("total", 0),
            "suspectCount": image_result.get("suspectCount", 0),
        } if has_image else None,
        "imageCheckEnabled": has_image,
        "imageSuspectCount": image_result.get("suspectCount", 0) if has_image else 0,
        "imageTemplateFiltered": image_result.get("templateFiltered", False) if has_image else False,
    }

    if "message" in text_result:
        result["message"] = text_result["message"]

    return result
