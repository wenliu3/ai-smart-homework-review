"""查重模块统一入口

对外暴露:
  - run_full_check(): 一站式查重，文本+图片双维度 + 合并结果
  - merge_results(): 仅合并各维度的独立结果
  - extract_all_from_file(): 从文件中提取文本和图片
  - extract_all_from_docx(): 从 docx 中提取文本和图片（复用 Document 对象）
  - 各维度的独立查重函数和提取函数

用法:
    from app.plagiarism import run_full_check

    result = run_full_check(
        text_submissions=[{"id": 1, "studentName": "张三", "studentNumber": "001", "content": "..."}],
        image_submissions=[{"id": 1, "studentName": "张三", "studentNumber": "001", "images": [bytes]}],
        template_text="任务书原文...",
        template_images=[bytes, bytes],
    )
"""
from .config import (
    PASS_RATE, MAX_SUBMISSIONS,
    PHRASE_NGRAM, PHRASE_WEIGHT, TOPIC_WEIGHT, MIN_VALID_CHARS,
    COMMON_NGRAM_RATIO, COMMON_NGRAM_MIN_DOCS, SNIPPET_LIMIT,
    HASH_SIZE, DISTANCE_THRESHOLD, MAX_IMAGES_PER_SUBMISSION,
)
from .text import (
    run_plagiarism_check,
    valid_char_count,
    split_sentences,
    clean_chars,
    get_char_ngram_set,
    get_word_tokens,
    compute_common_ngrams,
    strip_ngrams,
    overlap_similarity,
    build_tfidf_vectors,
    cosine_similarity,
    compute_similarities,
    get_matched_snippets,
)
from .image import (
    run_image_plagiarism_check,
    image_similarity,
    is_near_duplicate,
    average_hash,
    difference_hash,
    hamming_distance,
    compute_template_hashes,
    _match_images,
)
from .extractors import (
    extract_file_text,
    extract_all_from_file,
    extract_all_from_docx,
    extract_images_from_docx,
    docx_to_html,
    file_to_html,
)
from .aggregator import merge_results


def run_full_check(
    text_submissions: list,
    image_submissions: list = None,
    template_text: str = None,
    template_images: list = None,
    skipped: list = None,
    pass_rate: int = None,
    phrase_weight: float = None,
    topic_weight: float = None,
) -> dict:
    """一站式双维度查重（文本 + 图片）。

    参数:
        text_submissions: [{"id", "studentName", "studentNumber", "content"}] — 文本查重数据（必选）
        image_submissions: [{"id", "studentName", "studentNumber", "images": [bytes]}] — 图片查重数据（可选）
        template_text: 可选，任务书原文，比对前剔除模板 n-gram
        template_images: 可选，示例截图列表，比对前剔除模板图片
        skipped: 额外的跳过记录（如文件解析失败）

    返回:
        合并后的综合查重结果，包含每个学生的双维度数据、疑似原因、统计汇总。
    """
    # 文本维度
    if not text_submissions or len(text_submissions) < 2:
        text_result = {
            "results": [],
            "skipped": [],
            "message": "有效文本数量不足2份，无法进行文本查重比对",
        }
    else:
        text_result = run_plagiarism_check(
            text_submissions, template_text=template_text or None,
            pass_rate=pass_rate, phrase_weight=phrase_weight, topic_weight=topic_weight,
        )

    # 图片维度
    image_result = None
    if image_submissions and len(image_submissions) >= 2:
        image_result = run_image_plagiarism_check(image_submissions, template_images=template_images or None)

    # 合并双维度结果
    return merge_results(text_result, None, image_result, skipped=skipped, pass_rate=pass_rate)
