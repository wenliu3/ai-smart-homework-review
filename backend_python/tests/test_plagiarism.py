"""Unit tests for app.core.plagiarism 查重算法."""
import math

import pytest

from app.core import plagiarism as pl


# --------------------------- 文本清洗 ---------------------------
class TestSplitSentences:
    def test_splits_on_terminal_punctuation_and_newlines(self):
        text = "第一句。第二句！第三句？\n第四句；第五句"
        assert pl.split_sentences(text) == [
            "第一句",
            "第二句",
            "第三句",
            "第四句",
            "第五句",
        ]

    def test_drops_blank_fragments(self):
        assert pl.split_sentences("。。。\n\n  \n") == []

    def test_empty_string(self):
        assert pl.split_sentences("") == []


class TestCleanChars:
    def test_keeps_cn_en_lowercases_and_strips_others(self):
        assert pl.clean_chars("Hello, 世界! 123") == "hello世界"

    def test_removes_spaces(self):
        assert pl.clean_chars("a b c") == "abc"

    def test_all_stripped(self):
        assert pl.clean_chars("!!!123 ，。") == ""


class TestValidCharCount:
    def test_counts_only_valid_chars(self):
        assert pl.valid_char_count("Hi 世界!!!") == 4  # h,i,世,界

    def test_zero_for_punctuation_only(self):
        assert pl.valid_char_count("!!! 。，") == 0


# --------------------------- N-gram ---------------------------
class TestGetCharNgramSet:
    def test_generates_windows_per_sentence(self):
        # "abcd" with n=2 -> ab, bc, cd
        assert pl.get_char_ngram_set("abcd", 2) == {"ab", "bc", "cd"}

    def test_short_cleaned_kept_when_len_ge_2(self):
        # "ab" cleaned len 2, n=10 -> kept as-is
        assert pl.get_char_ngram_set("ab", 10) == {"ab"}

    def test_short_cleaned_dropped_when_len_lt_2(self):
        assert pl.get_char_ngram_set("a", 10) == set()

    def test_does_not_span_sentences(self):
        grams = pl.get_char_ngram_set("ab。cd", 3)
        # each sentence too short for n=3 but len>=2 -> kept whole
        assert grams == {"ab", "cd"}


class TestGetCharNgramTokens:
    def test_keeps_duplicates(self):
        # "aaaa" n=2 -> aa, aa, aa
        assert pl.get_char_ngram_tokens("aaaa", 2) == ["aa", "aa", "aa"]

    def test_drops_sentences_shorter_than_n(self):
        assert pl.get_char_ngram_tokens("ab。cdef", 3) == ["cde", "def"]


# --------------------------- 相似度 ---------------------------
class TestOverlapSimilarity:
    def test_identical_sets(self):
        s = {"a", "b", "c"}
        assert pl.overlap_similarity(s, set(s)) == 1.0

    def test_partial_overlap_uses_smaller_denominator(self):
        a = {"a", "b"}
        b = {"a", "b", "c", "d"}
        # intersection 2 / min(2,4)=2 -> 1.0
        assert pl.overlap_similarity(a, b) == 1.0

    def test_no_overlap(self):
        assert pl.overlap_similarity({"a"}, {"b"}) == 0.0

    def test_empty_returns_zero(self):
        assert pl.overlap_similarity(set(), {"a"}) == 0.0
        assert pl.overlap_similarity({"a"}, set()) == 0.0


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = {"a": 1.0, "b": 2.0}
        assert pl.cosine_similarity(v, dict(v)) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        assert pl.cosine_similarity({"a": 1.0}, {"b": 1.0}) == 0.0

    def test_known_value(self):
        a = {"x": 1.0, "y": 1.0}
        b = {"x": 1.0}
        # dot=1, |a|=sqrt2, |b|=1 -> 1/sqrt2
        assert pl.cosine_similarity(a, b) == pytest.approx(1 / math.sqrt(2))

    def test_zero_norm(self):
        assert pl.cosine_similarity({"a": 0.0}, {"a": 0.0}) == 0.0


class TestBuildTfidfVectors:
    def test_returns_one_vector_per_doc(self):
        vecs = pl.build_tfidf_vectors([["a", "b"], ["a"]])
        assert len(vecs) == 2

    def test_tfidf_math(self):
        docs = [["a", "a", "b"], ["a"]]
        vecs = pl.build_tfidf_vectors(docs)
        # doc0: tf(a)=2/3, df(a)=2, idf=log(2/3)+1
        idf_a = math.log(2 / (1 + 2)) + 1
        assert vecs[0]["a"] == pytest.approx((2 / 3) * idf_a)


class TestComputeSimilarities:
    def test_weighted_combination(self):
        phrase_a = {"ab", "bc"}
        phrase_b = {"ab", "bc"}
        vec_a = {"x": 1.0}
        vec_b = {"x": 1.0}
        sim_phrase, sim_topic, sim_combined = pl.compute_similarities(
            phrase_a, vec_a, phrase_b, vec_b
        )
        assert sim_phrase == 1.0
        assert sim_topic == pytest.approx(1.0)
        expected = 1.0 * pl.PHRASE_WEIGHT + 1.0 * pl.TOPIC_WEIGHT
        assert sim_combined == pytest.approx(expected)


# --------------------------- 批量查重入口 ---------------------------
def _sub(id, name, number, content):
    return {"id": id, "studentName": name, "studentNumber": number, "content": content}


class TestRunPlagiarismCheck:
    def test_skips_short_submissions_and_reports_insufficient(self):
        subs = [
            _sub(1, "张三", "001", "太短"),
            _sub(2, "李四", "002", "也很短"),
        ]
        out = pl.run_plagiarism_check(subs)
        assert out["results"] == []
        assert len(out["skipped"]) == 2
        assert "不足2份" in out["message"]

    def test_identical_submissions_flagged_as_plagiarism(self):
        essay = "机器学习是人工智能的一个重要分支它通过数据训练模型让计算机具备预测能力" * 2
        subs = [
            _sub(1, "张三", "001", essay),
            _sub(2, "李四", "002", essay),
        ]
        out = pl.run_plagiarism_check(subs)
        assert out["total"] == 2
        assert out["suspectCount"] == 2
        top = out["results"][0]
        assert top["rate"] > pl.PASS_RATE
        assert top["status"] == "不合格(疑似抄袭)"
        assert top["matchName"] in {"张三", "李四"}

    def test_distinct_submissions_pass(self):
        a = "今天我学习了微积分中的极限与导数概念并完成了课后所有练习题目收获很大" * 2
        b = "周末我和朋友去公园放风筝天气晴朗心情愉快还拍了很多好看的风景照片" * 2
        subs = [_sub(1, "张三", "001", a), _sub(2, "李四", "002", b)]
        out = pl.run_plagiarism_check(subs)
        assert out["suspectCount"] == 0
        assert all(r["status"] == "合格" for r in out["results"])

    def test_results_sorted_by_rate_desc(self):
        essay = "自然语言处理是让计算机理解和生成人类语言的技术广泛应用于翻译和问答系统" * 2
        other = "海洋覆盖了地球表面绝大部分面积其中蕴藏着丰富的生物资源和矿产资源等" * 2
        subs = [
            _sub(1, "张三", "001", essay),
            _sub(2, "李四", "002", essay),
            _sub(3, "王五", "003", other),
        ]
        out = pl.run_plagiarism_check(subs)
        rates = [r["rate"] for r in out["results"]]
        assert rates == sorted(rates, reverse=True)

    def test_exceeds_max_submissions(self, monkeypatch):
        monkeypatch.setattr(pl, "MAX_SUBMISSIONS", 2)
        essay = "深度学习依赖于大量数据和强大算力通过多层神经网络自动提取特征完成任务" * 2
        subs = [_sub(i, f"s{i}", f"{i:03d}", essay) for i in range(3)]
        out = pl.run_plagiarism_check(subs)
        assert out["results"] == []
        assert "超过上限" in out["message"]
        assert out["total"] == 3

    def test_handles_missing_content_key(self):
        subs = [
            {"id": 1, "studentName": "张三", "studentNumber": "001"},
            {"id": 2, "studentName": "李四", "studentNumber": "002"},
        ]
        out = pl.run_plagiarism_check(subs)
        assert len(out["skipped"]) == 2
        assert out["results"] == []
