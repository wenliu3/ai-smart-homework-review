"""作业查重算法 — 移植自 ai-homework/test.py

原理:
  1. 片段重合度: 字符级 N-gram + 重叠系数 —— 抓"整句/整段照抄"
  2. 主题相似度: 字符二元组 + TF-IDF 余弦相似度 —— 抓"同义替换/语序打乱"
  综合重复率 = 片段重合度 × 0.6 + 主题相似度 × 0.4
"""
import re
import math
from collections import Counter


# ===================== 配置 =====================
PHRASE_NGRAM = 10       # 片段重合度字符窗口长度
TOPIC_NGRAM = 2         # 主题相似度字符窗口长度
PHRASE_WEIGHT = 0.6     # 片段重合度权重
TOPIC_WEIGHT = 0.4      # 主题相似度权重
MIN_VALID_CHARS = 40    # 有效字符数少于该值视为无效作业
PASS_RATE = 30          # 合格阈值(%): 综合重复率超过该值判定为"疑似抄袭"
MAX_SUBMISSIONS = 200   # 单次查重最大比对数量，防止 O(n²) 导致长时间阻塞


# ===================== 文本清洗 =====================
def split_sentences(text):
    """按句末标点/换行切分句子"""
    sentences = re.split(r'[。！？；\n\r]+', text)
    return [s for s in sentences if s.strip()]


def clean_chars(s):
    """只保留中文汉字和英文字母，英文统一转小写"""
    s = re.sub(r'[^\u4e00-\u9fff a-zA-Z]', '', s)
    return s.replace(' ', '').lower()


def valid_char_count(text):
    """统计有效中英文字符总数"""
    return len(clean_chars(text))


# ===================== 相似度计算 =====================
def get_char_ngram_set(text, n):
    """生成字符级 N-gram 集合(去重)，不跨句拼接，用于片段重合度"""
    grams = set()
    for sentence in split_sentences(text):
        cleaned = clean_chars(sentence)
        if len(cleaned) < n:
            if len(cleaned) >= 2:
                grams.add(cleaned)
            continue
        for i in range(len(cleaned) - n + 1):
            grams.add(cleaned[i:i + n])
    return grams


def get_char_ngram_tokens(text, n):
    """生成字符级 N-gram 列表(保留重复)，用于 TF-IDF 词频统计"""
    tokens = []
    for sentence in split_sentences(text):
        cleaned = clean_chars(sentence)
        if len(cleaned) < n:
            continue
        for i in range(len(cleaned) - n + 1):
            tokens.append(cleaned[i:i + n])
    return tokens


def overlap_similarity(set_a, set_b):
    """重叠系数: 交集占较小集合的比例"""
    if not set_a or not set_b:
        return 0.0
    inter = len(set_a & set_b)
    smaller = min(len(set_a), len(set_b))
    return inter / smaller if smaller else 0.0


def build_tfidf_vectors(all_token_lists):
    """为全体作业构建 TF-IDF 向量"""
    n_docs = len(all_token_lists)
    df = Counter()
    for tokens in all_token_lists:
        for t in set(tokens):
            df[t] += 1

    vectors = []
    for tokens in all_token_lists:
        tf = Counter(tokens)
        total = len(tokens) or 1
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
    """返回 (片段重合度, 主题相似度, 综合相似度)，均为 0~1 小数"""
    sim_phrase = overlap_similarity(phrase_a, phrase_b)
    sim_topic = cosine_similarity(topic_vec_a, topic_vec_b)
    sim_combined = sim_phrase * PHRASE_WEIGHT + sim_topic * TOPIC_WEIGHT
    return sim_phrase, sim_topic, sim_combined


# ===================== 批量查重入口 =====================
def run_plagiarism_check(submissions: list) -> list:
    """
    对一组学生提交进行查重比对。

    参数:
        submissions: [{"id": 1, "studentName": "张三", "studentNumber": "2024001", "content": "作业文本..."}]

    返回:
        [{"studentName": "张三", "studentNumber": "2024001", "rate": 85.5,
          "phraseRate": 90.0, "topicRate": 78.3, "status": "不合格(疑似抄袭)",
          "matchName": "李四", "matchId": "2024002", "submissionId": 1, "matchSubmissionId": 2}]
        按重复率从高到低排序
    """
    # 过滤无效作业(字符太少)
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

    # 预先构建向量
    phrase_sets = [get_char_ngram_set(s["content"], PHRASE_NGRAM) for s in valid]
    topic_token_lists = [get_char_ngram_tokens(s["content"], TOPIC_NGRAM) for s in valid]
    topic_vectors = build_tfidf_vectors(topic_token_lists)

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
        })

    # 按重复率从高到低排序
    results.sort(key=lambda x: x["rate"], reverse=True)

    return {
        "results": results,
        "skipped": skipped,
        "total": n,
        "suspectCount": sum(1 for r in results if r["status"] != "合格"),
        "passRate": PASS_RATE,
    }
