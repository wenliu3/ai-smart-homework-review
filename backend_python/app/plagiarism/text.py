"""文本查重算法 —— 字符级 N-gram + 词级 TF-IDF 余弦相似度

原理:
  1. 片段重合度: 字符级 N-gram + 重叠系数 —— 抓"整句/整段照抄"
  2. 主题相似度: jieba 分词 + TF-IDF 余弦相似度 —— 抓"同义替换/语序打乱"
  综合重复率 = 片段重合度 × 0.6 + 主题相似度 × 0.4

特性:
  - 显式模板剔除: 传入 template_text，比对前直接从每份提交的 n-gram 集合中减去模板自身的 n-gram
  - 自动公共片段识别: 当提交份数 >= 5 时，额外统计"在本批次里出现在 >= 60% 提交中"的 n-gram，自动剔除
  - 命中片段回溯: 疑似抄袭时，返回双方实际重合的 n-gram 片段样例，方便人工复核
  - 词级 TF-IDF: jieba 中文分词(按词而非单字)，英文/数字保持完整单词
"""
import re
import math
import jieba
from collections import Counter

from .config import (
    PHRASE_NGRAM, PHRASE_WEIGHT, TOPIC_WEIGHT,
    TOPIC_SUSPECT_THRESHOLD, PHRASE_SUSPECT_THRESHOLD,
    MIN_VALID_CHARS, PASS_RATE, MAX_SUBMISSIONS,
    COMMON_NGRAM_RATIO, COMMON_NGRAM_MIN_DOCS, SNIPPET_LIMIT,
)


# ===================== 文本清洗 =====================
def split_sentences(text):
    """按句末标点/换行切分句子"""
    sentences = re.split(r'[。！？；\n\r]+', text)
    return [s for s in sentences if s.strip()]


def clean_chars(s):
    """只保留中文汉字、英文字母和数字，英文统一转小写"""
    s = re.sub(r'[^\u4e00-\u9fff a-zA-Z0-9]', '', s)
    return s.replace(' ', '').lower()


def valid_char_count(text):
    """统计有效中英文字符总数"""
    return len(clean_chars(text))


# ===================== N-gram 生成 =====================
def get_char_ngram_set(text, n):
    """生成字符级 N-gram 集合(去重)，不跨句拼接，用于片段重合度"""
    grams = set()
    for sentence in split_sentences(text or ""):
        cleaned = clean_chars(sentence)
        if len(cleaned) < n:
            if len(cleaned) >= 2:
                grams.add(cleaned)
            continue
        for i in range(len(cleaned) - n + 1):
            grams.add(cleaned[i:i + n])
    return grams


_jieba_ready = False

def get_word_tokens(text):
    """使用 jieba 分词生成词级别 token 列表(保留重复)，用于 TF-IDF 词频统计。
    中文按词切分(如'自然语言'+'处理')，英文/数字保持完整单词。
    过滤标点、空白等无意义 token。"""
    global _jieba_ready
    if not _jieba_ready:
        jieba.initialize()
        _jieba_ready = True
    tokens = []
    for word in jieba.cut(text or ''):
        word = word.strip().lower()
        if not word:
            continue
        # 只保留含字母/数字/汉字的词，过滤纯标点和空白
        if re.search(r'[a-z0-9\u4e00-\u9fff]', word):
            tokens.append(word)
    return tokens


# ===================== 公共模板过滤 =====================
def compute_common_ngrams(ngram_sets, ratio=COMMON_NGRAM_RATIO):
    """统计在 >= ratio 比例的提交中都出现的 n-gram，视为公共模板内容"""
    n_docs = len(ngram_sets)
    if n_docs == 0:
        return set()
    df = Counter()
    for s in ngram_sets:
        for g in s:
            df[g] += 1
    threshold = max(2, math.ceil(n_docs * ratio))
    return {g for g, c in df.items() if c >= threshold}


def strip_ngrams(ngram_set, exclude_set):
    return ngram_set - exclude_set if exclude_set else ngram_set


# ===================== 相似度计算 =====================
def overlap_similarity(set_a, set_b):
    """重叠系数: 交集占较小集合的比例"""
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    smaller = min(len(set_a), len(set_b))
    return inter / smaller if smaller else 0.0


def build_tfidf_vectors(all_token_lists, excluded_tokens=None):
    """为全体作业构建 TF-IDF 向量；excluded_tokens 中的词直接不进入词表
    （公共模板内容不该占权重，而不只是被 IDF 稀释）"""
    excluded = excluded_tokens or set()
    n_docs = len(all_token_lists)
    df = Counter()
    for tokens in all_token_lists:
        for t in set(tokens):
            if t in excluded:
                continue
            df[t] += 1

    vectors = []
    for tokens in all_token_lists:
        tf = Counter(t for t in tokens if t not in excluded)
        total = sum(tf.values()) or 1
        vec = {}
        for t, cnt in tf.items():
            tf_val = cnt / total
            idf_val = math.log(n_docs / (1 + df[t])) + 1
            vec[t] = tf_val * idf_val
        vectors.append(vec)
    return vectors


def cosine_similarity(vec_a, vec_b):
    """稀疏向量余弦相似度"""
    common = set(vec_a) & set(vec_b)
    if not common:
        return 0.0
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def compute_similarities(phrase_a, topic_vec_a, phrase_b, topic_vec_b):
    """返回 (片段重合度, 主题相似度, 综合相似度)，均为 0~1 小数

    综合相似度采用非线性组合：
    - 主题相似度(TF-IDF余弦)本质测的是词汇重合度，同题作业天然偏高(70-90%)
    - 只有当主题相似度极高(>=TOPIC_SUSPECT_THRESHOLD)且片段重合度已超过警戒线时，
      才说明可能存在"换词不换意"的改写式抄袭，此时主题相似度才参与加权
    - 否则综合相似度 = 片段重合度，避免同题作业被误判
    """
    sim_phrase = overlap_similarity(phrase_a, phrase_b)
    sim_topic = cosine_similarity(topic_vec_a, topic_vec_b)
    if sim_topic >= TOPIC_SUSPECT_THRESHOLD and sim_phrase >= PHRASE_SUSPECT_THRESHOLD:
        sim_combined = sim_phrase * PHRASE_WEIGHT + sim_topic * TOPIC_WEIGHT
    else:
        sim_combined = sim_phrase
    return sim_phrase, sim_topic, sim_combined


def get_matched_snippets(text_a, text_b, n=PHRASE_NGRAM, exclude_set=None, limit=SNIPPET_LIMIT):
    """返回两份文本中实际重合的 n-gram 片段样例（已剔除模板部分），供人工复核。
    按长度倒序，越长的重合片段越可能是真实抄袭证据。"""
    set_a = strip_ngrams(get_char_ngram_set(text_a, n), exclude_set)
    set_b = strip_ngrams(get_char_ngram_set(text_b, n), exclude_set)
    common = set_a & set_b
    return sorted(common, key=len, reverse=True)[:limit]


# ===================== 批量查重入口 =====================
def run_plagiarism_check(submissions: list, template_text: str = None) -> dict:
    """
    对一组学生提交进行查重比对。

    参数:
        submissions: [{"id": 1, "studentName": "张三", "studentNumber": "2024001", "content": "作业文本..."}]
        template_text: 可选。任务书原文/起始代码原文。传入后会先从每份提交里剔除模板自身的
                        n-gram，避免"大家都抄了同一份任务书/起始代码"被误判为互相抄袭。
                        强烈建议：只要有 2 份及以上提交，就应该传这个参数。

    返回:
        [{"studentName": "张三", "studentNumber": "2024001", "rate": 85.5,
          "phraseRate": 90.0, "topicRate": 78.3, "status": "不合格(疑似抄袭)",
          "matchName": "李四", "matchId": "2024002", "submissionId": 1, "matchSubmissionId": 2,
          "matchedSnippets": ["...", "..."]}]
        按重复率从高到低排序
    """
    valid = []
    skipped = []
    for s in submissions:
        text = s.get("content", "") or ""
        if valid_char_count(text) < MIN_VALID_CHARS:
            skipped.append({"studentName": s["studentName"], "studentNumber": s["studentNumber"], "reason": "有效字符数过少"})
            continue
        valid.append(s)

    n = len(valid)
    if n < 2:
        return {
            "results": [],
            "skipped": skipped,
            "message": "有效作业数量不足2份，无法进行查重比对",
        }

    if n > MAX_SUBMISSIONS:
        return {
            "results": [],
            "skipped": skipped,
            "total": n,
            "suspectCount": 0,
            "passRate": PASS_RATE,
            "message": f"有效作业数量({n})超过上限({MAX_SUBMISSIONS}份)，请缩小范围后重试",
        }

    # 显式模板的 n-gram（用于片段重合度剔除）
    template_phrase_set = get_char_ngram_set(template_text, PHRASE_NGRAM) if template_text else set()
    
    # 每份提交先剔除显式模板的 n-gram
    phrase_sets = [
        strip_ngrams(get_char_ngram_set(s["content"], PHRASE_NGRAM), template_phrase_set)
        for s in valid
    ]
    topic_token_lists = [get_word_tokens(s["content"]) for s in valid]
    
    # 模板的 jieba 词直接从 TF-IDF 词表中排除
    # jieba 分词后模板只有几个词(如'东莞'/'理工学院'/'实验报告')，排除影响小
    template_topic_set = set(get_word_tokens(template_text)) if template_text else set()
    
    # 批次够大时，自动识别“全班共有”的公共片段/词汇并剔除
    auto_common_phrase = set()
    auto_common_topic = set(template_topic_set)
    if n >= COMMON_NGRAM_MIN_DOCS:
        auto_common_phrase = compute_common_ngrams(phrase_sets, COMMON_NGRAM_RATIO)
        auto_common_topic |= compute_common_ngrams([set(t) for t in topic_token_lists], COMMON_NGRAM_RATIO)
    
    phrase_sets = [strip_ngrams(s, auto_common_phrase) for s in phrase_sets]
    topic_vectors = build_tfidf_vectors(topic_token_lists, excluded_tokens=auto_common_topic)

    merged_exclude_phrase = template_phrase_set | auto_common_phrase

    # 两两比对
    results = []
    for i in range(n):
        best_combined = best_phrase = best_topic = 0.0
        best_match = None
        best_match_idx = -1
        for j in range(n):
            if i == j:
                continue
            sim_phrase, sim_topic, sim_combined = compute_similarities(
                phrase_sets[i], topic_vectors[i],
                phrase_sets[j], topic_vectors[j],
            )
            if sim_combined > best_combined:
                best_combined, best_phrase, best_topic = sim_combined, sim_phrase, sim_topic
                best_match = valid[j]
                best_match_idx = j

        rate = round(best_combined * 100, 2)
        status = "不合格(疑似抄袭)" if rate > PASS_RATE else "合格"

        matched_snippets = []
        if best_match_idx >= 0 and status != "合格":
            matched_snippets = get_matched_snippets(
                valid[i]["content"], best_match["content"], PHRASE_NGRAM, merged_exclude_phrase,
            )

        results.append({
            "submissionId": valid[i]["id"],
            "studentName": valid[i]["studentName"],
            "studentNumber": valid[i]["studentNumber"],
            "rate": rate,
            "phraseRate": round(best_phrase * 100, 2),
            "topicRate": round(best_topic * 100, 2),
            "status": status,
            "matchName": best_match["studentName"] if best_match else "-",
            "matchId": best_match["studentNumber"] if best_match else "-",
            "matchSubmissionId": valid[best_match_idx]["id"] if best_match_idx >= 0 else None,
            "matchedSnippets": matched_snippets,
        })

    # 按重复率从高到低排序
    results.sort(key=lambda x: x["rate"], reverse=True)

    return {
        "results": results,
        "skipped": skipped,
        "total": n,
        "suspectCount": sum(1 for r in results if r["status"] != "合格"),
        "passRate": PASS_RATE,
        "templateFiltered": bool(template_text),
        "autoCommonFiltered": n >= COMMON_NGRAM_MIN_DOCS,
    }
