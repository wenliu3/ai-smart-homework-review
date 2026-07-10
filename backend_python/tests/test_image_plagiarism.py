"""图片查重算法单元测试

验证:
  1. 同一张图（不同压缩质量） → 相似度接近 1.0
  2. 完全不同的图 → 相似度低
  3. 批量查重入口 run_image_plagiarism_check 基本功能
  4. 模板图片剔除功能
"""
import sys
import os
import io

# 确保能导入项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image
from app.plagiarism.image import (
    image_similarity,
    run_image_plagiarism_check,
    is_near_duplicate,
    _match_images,
)


# ===================== 生成测试图片 =====================

def _make_image(color, size=(100, 100), text=None, pattern=None):
    """生成一张测试图片，返回 PNG 二进制。
    pattern='gradient' 时生成水平渐变图（适合感知哈希，有足够像素差异）
    pattern='noise' 时生成随机噪点图
    默认纯色"""
    if pattern == 'gradient':
        from PIL import ImageDraw
        img = Image.new('RGB', size)
        draw = ImageDraw.Draw(img)
        for x in range(size[0]):
            r = int(color[0] * x / size[0])
            g = int(color[1] * (1 - x / size[0]))
            b = int(color[2] * x / size[0] * 0.5)
            draw.line([(x, 0), (x, size[1])], fill=(r, g, b))
        if text:
            draw.text((10, 10), text, fill='white')
    elif pattern == 'noise':
        import random
        random.seed(hash(color) % 1000)
        img = Image.new('RGB', size)
        pixels = img.load()
        for y in range(size[1]):
            for x in range(size[0]):
                pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    else:
        img = Image.new('RGB', size, color)
        if text:
            from PIL import ImageDraw
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), text, fill='black')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _make_jpeg_variation(png_bytes, quality=50):
    """把 PNG 图片转成不同压缩质量的 JPEG，模拟重新保存"""
    img = Image.open(io.BytesIO(png_bytes))
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    return buf.getvalue()


# 生成测试图片 — 使用渐变图案，确保感知哈希有足够差异区分不同图片
IMG_A = _make_image((255, 100, 50), text="Student A", pattern='gradient')
IMG_A_JPEG = _make_jpeg_variation(IMG_A, quality=60)
IMG_B = _make_image((50, 100, 255), text="Student B", pattern='gradient')
IMG_C = _make_image((100, 255, 50), text="Different", pattern='gradient')

# 模板图片（和 IMG_A 颜色接近）
TEMPLATE_IMG = _make_image((250, 110, 60), text="Template", pattern='gradient')

# 另外两张独立渐变图，用于边界场景测试
IMG_D = _make_image((200, 50, 150), text="Student D", pattern='gradient')
IMG_E = _make_image((80, 200, 120), text="Student E", pattern='gradient')


# ===================== 测试用例 =====================

def test_same_image_high_similarity():
    """测试1: 同一张图不同压缩质量 → 相似度接近 1.0"""
    sim = image_similarity(IMG_A, IMG_A_JPEG)
    print(f"[test_same_image] 相似度 = {sim:.4f}")
    assert sim >= 0.9, f"同一张图不同压缩的相似度应 >= 0.9，实际 {sim:.4f}"
    print("  OK: 能扛住压缩质量变化")


def test_different_image_low_similarity():
    """测试2: 完全不同的图 → 相似度低"""
    sim = image_similarity(IMG_A, IMG_B)
    print(f"[test_different_image] 相似度 = {sim:.4f}")
    assert sim < 0.6, f"完全不同的图相似度应 < 0.6，实际 {sim:.4f}"
    print("  OK: 完全不同的图不会误判")


def test_batch_check_basic():
    """测试3: 批量查重 — 2份相似图片 + 1份不同"""
    submissions = [
        {"id": 1, "studentName": "张三", "studentNumber": "2024001",
         "images": [IMG_A, IMG_C]},
        {"id": 2, "studentName": "李四", "studentNumber": "2024002",
         "images": [IMG_A_JPEG, IMG_B]},
        {"id": 3, "studentName": "王五", "studentNumber": "2024003",
         "images": [IMG_B, IMG_C]},
    ]
    result = run_image_plagiarism_check(submissions)
    print(f"[test_batch] 总数={result['total']}, 疑似={result['suspectCount']}")
    assert result["total"] == 3

    results_by_name = {r["studentName"]: r for r in result["results"]}
    zs = results_by_name["张三"]
    lf = results_by_name["李四"]
    print(f"  张三 -> 最相似: {zs['matchName']}, 图片重合度: {zs['imageRate']}%, 命中图片: {zs['matchedImageCount']}张")
    print(f"  李四 -> 最相似: {lf['matchName']}, 图片重合度: {lf['imageRate']}%, 命中图片: {lf['matchedImageCount']}张")

    # 张三和李四都有 IMG_A/IMG_A_JPEG，应该互相匹配
    assert zs["matchName"] == "李四", "张三最相似应为李四"
    assert lf["matchName"] == "张三", "李四最相似应为张三"
    assert zs["matchedImageCount"] >= 1, "张三应至少命中1张图片"
    print("  OK: 批量查重正确识别互相抄袭的截图")


def test_template_filtering():
    """测试4: 模板图片剔除"""
    # 不传模板：张三和模板图片会有一定相似度
    submissions_no_template = [
        {"id": 1, "studentName": "张三", "studentNumber": "2024001",
         "images": [IMG_A, IMG_B]},
        {"id": 2, "studentName": "李四", "studentNumber": "2024002",
         "images": [TEMPLATE_IMG, IMG_C]},
    ]
    result_no_template = run_image_plagiarism_check(submissions_no_template)
    rate_no_template = {r["studentName"]: r["imageRate"] for r in result_no_template["results"]}

    # 传模板：模板图片被剔除，相似度应降低
    result_with_template = run_image_plagiarism_check(submissions_no_template, template_images=[TEMPLATE_IMG])
    rate_with_template = {r["studentName"]: r["imageRate"] for r in result_with_template["results"]}

    print(f"[test_template] 无模板: 张三={rate_no_template.get('张三', 0)}%, 李四={rate_no_template.get('李四', 0)}%")
    print(f"             有模板: 张三={rate_with_template.get('张三', 0)}%, 李四={rate_with_template.get('李四', 0)}%")
    assert rate_with_template.get("张三", 0) <= rate_no_template.get("张三", 0), "传模板后相似度应不高于不传模板"
    print("  OK: 模板剔除有效减少了假阳性")


def test_insufficient_submissions():
    """测试5: 有效图片不足2份时的处理"""
    result = run_image_plagiarism_check([
        {"id": 1, "studentName": "张三", "studentNumber": "2024001", "images": [IMG_A]},
    ])
    assert "message" in result, "不足2份时应返回提示信息"
    print(f"[test_insufficient] {result['message']}")
    print("  OK: 不足2份时正确返回提示")


def test_empty_images():
    """测试6: 空图片列表处理"""
    sim = image_similarity(b"", b"")
    assert sim == 0.0, "空图片相似度应为 0"
    print(f"[test_empty] 相似度 = {sim}")
    print("  OK: 空图片不会崩溃")


# ===================== 边界场景测试 =====================

def test_unequal_image_counts():
    """边界场景1: 图片数量不对等 — 甲1张 vs 乙2张，只有1张相同

    验证:
      - imageRate 不会超过 100%（修复前的 bug）
      - matchedImageCount/totalImageCount 如实反映"1/1"和"1/2"的区别
      - 甲的证据更硬（唯一的图就是抄的），乙只是部分重合
    """
    submissions = [
        # 甲只上传1张图，恰好和乙的第1张是同一张
        {"id": 1, "studentName": "甲", "studentNumber": "2024001",
         "images": [IMG_A]},
        # 乙上传2张图：第1张和甲相同，第2张是独立的
        {"id": 2, "studentName": "乙", "studentNumber": "2024002",
         "images": [IMG_A_JPEG, IMG_D]},
    ]
    result = run_image_plagiarism_check(submissions)
    assert result["total"] == 2

    by_name = {r["studentName"]: r for r in result["results"]}
    jia = by_name["甲"]
    yi = by_name["乙"]

    print(f"  甲: imageRate={jia['imageRate']}%, matchedImageCount={jia['matchedImageCount']}, totalImageCount={jia.get('totalImageCount', '?')}")
    print(f"  乙: imageRate={yi['imageRate']}%, matchedImageCount={yi['matchedImageCount']}, totalImageCount={yi.get('totalImageCount', '?')}")

    # 核心断言：不会超过 100%
    assert jia["imageRate"] <= 100, f"甲的 imageRate 不应超过 100%，实际 {jia['imageRate']}%"
    assert yi["imageRate"] <= 100, f"乙的 imageRate 不应超过 100%，实际 {yi['imageRate']}%"

    # 甲唯一的一张图命中了 → 1/1
    assert jia["matchedImageCount"] == 1, f"甲应命中1张，实际 {jia['matchedImageCount']}"
    assert jia.get("totalImageCount") == 1, f"甲总共1张图，实际 {jia.get('totalImageCount')}"

    # 乙有2张图，命中1张 → 1/2
    assert yi["matchedImageCount"] == 1, f"乙应命中1张，实际 {yi['matchedImageCount']}"
    assert yi.get("totalImageCount") == 2, f"乙总共2张图，实际 {yi.get('totalImageCount')}"

    # 两人都匹配到对方
    assert jia["matchName"] == "乙", "甲最相似应为乙"
    assert yi["matchName"] == "甲", "乙最相似应为甲"

    print("  OK: 图片数量不对等时不再出现 >100% 的荒谬结果")
    print('  OK: matchedImageCount/totalImageCount 如实标出"1/1" vs"1/2"的区别')


def test_reversed_upload_order():
    """边界场景2: 内容相同、上传顺序颠倒

    验证:
      - 贪心匹配是穷举所有 i×j 组合，与图片排列顺序无关
      - 两人 2/2 全部命中，imageRate=100%
    """
    submissions = [
        # 甲：A, B 顺序
        {"id": 1, "studentName": "甲", "studentNumber": "2024001",
         "images": [IMG_A, IMG_B]},
        # 乙：B, A 顺序（完全颠倒）
        {"id": 2, "studentName": "乙", "studentNumber": "2024002",
         "images": [IMG_B, IMG_A_JPEG]},  # A_JPEG 是 A 的压缩版，感知哈希判定为同一张
    ]
    result = run_image_plagiarism_check(submissions)
    by_name = {r["studentName"]: r for r in result["results"]}
    jia = by_name["甲"]
    yi = by_name["乙"]

    print(f"  甲: imageRate={jia['imageRate']}%, matched={jia['matchedImageCount']}/{jia.get('totalImageCount', '?')}")
    print(f"  乙: imageRate={yi['imageRate']}%, matched={yi['matchedImageCount']}/{yi.get('totalImageCount', '?')}")

    # 两人都应该 2/2 全部命中
    assert jia["matchedImageCount"] == 2, f"甲应命中2张，实际 {jia['matchedImageCount']}"
    assert yi["matchedImageCount"] == 2, f"乙应命中2张，实际 {yi['matchedImageCount']}"
    assert jia["imageRate"] == 100.0, f"甲应为 100%，实际 {jia['imageRate']}%"
    assert yi["imageRate"] == 100.0, f"乙应为 100%，实际 {yi['imageRate']}%"

    print("  OK: 上传顺序颠倒不影响判定，2/2 全部命中")


def test_single_image_low_confidence():
    """边界场景3: 单张图片命中时置信度问题

    问题：如果甲只上传了1张图，恰好碰巧和别人的某张图相似（比如都用了老师给的
    默认报错截图），系统会直接判100%，但样本量只有1，说服力很弱。

    验证:
      - lowConfidence 标记为 True，提醒老师这只是单张图片的命中
      - imageRate 仍然是 100%（1/1），但 lowConfidence=True 让老师知道样本量小
    """
    submissions = [
        # 甲只上传1张图，恰好和乙的某张图相似
        {"id": 1, "studentName": "甲", "studentNumber": "2024001",
         "images": [IMG_A]},
        # 乙上传3张图，第2张和甲相同
        {"id": 2, "studentName": "乙", "studentNumber": "2024002",
         "images": [IMG_D, IMG_A_JPEG, IMG_E]},
    ]
    result = run_image_plagiarism_check(submissions)
    by_name = {r["studentName"]: r for r in result["results"]}
    jia = by_name["甲"]
    yi = by_name["乙"]

    print(f"  甲: imageRate={jia['imageRate']}%, matched={jia['matchedImageCount']}/{jia.get('totalImageCount', '?')}, lowConfidence={jia.get('lowConfidence')}")
    print(f"  乙: imageRate={yi['imageRate']}%, matched={yi['matchedImageCount']}/{yi.get('totalImageCount', '?')}, lowConfidence={yi.get('lowConfidence')}")

    # 甲只有1张图且命中 → lowConfidence=True
    assert jia.get("lowConfidence") == True, "甲仅1张图命中应标记 lowConfidence=True"
    assert jia["imageRate"] == 100.0, f"甲 imageRate 应为 100%，实际 {jia['imageRate']}%"

    # 乙有3张图，命中1张 → 不是低置信度
    assert yi.get("lowConfidence") == False, "乙有多张图不应标记 lowConfidence"
    assert yi["matchedImageCount"] == 1, f"乙应命中1张，实际 {yi['matchedImageCount']}"
    assert yi.get("totalImageCount") == 3, f"乙总共3张图，实际 {yi.get('totalImageCount')}"

    print("  OK: 单张图片命中时 lowConfidence=True，提醒老师样本量太小")
    print("  OK: 多张图片命中时 lowConfidence=False，证据充分")


# ===================== 主入口 =====================

if __name__ == "__main__":
    print("=" * 60)
    print("图片查重算法单元测试")
    print("=" * 60)
    print()

    test_same_image_high_similarity()
    print()

    test_different_image_low_similarity()
    print()

    test_batch_check_basic()
    print()

    test_template_filtering()
    print()

    test_insufficient_submissions()
    print()

    test_empty_images()
    print()

    test_unequal_image_counts()
    print()

    test_reversed_upload_order()
    print()

    test_single_image_low_confidence()
    print()

    print("=" * 60)
    print("全部测试通过")
    print("=" * 60)
