"""图片查重算法 —— 感知哈希 (perceptual hash) 比对

原理:
  感知哈希把图片缩成一个很小的灰度缩略图(8x8=64像素)，
  按每个像素相对于均值是偏亮还是偏暗，生成一串 0/1 位串。
  图片"看起来像"，这串位串就像，能扛住重新压缩/轻微缩放/截图裁边等干扰。
  两张图的相似度用汉明距离(有几个二进制位不同)衡量，距离越小越像。

  同时实现 aHash(均值哈希) 和 dHash(差值哈希)，取更严格(距离更大)的那个，减少误判。

  实验报告里的"运行结果截图"理论上应该千人千面，如果两份提交里的截图感知哈希
  几乎一致 → 很可能是直接复制了别人的截图，比文字/代码重合更难有"合理解释"。

依赖: Pillow (pip install Pillow)
"""
import io

from PIL import Image

from .config import (
    HASH_SIZE, DISTANCE_THRESHOLD, PASS_RATE, MAX_IMAGES_PER_SUBMISSION,
)


# ===================== 感知哈希 =====================
def _to_grayscale_pixels(image_bytes: bytes, size: int, extra_col: int = 0):
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert('L')
        img = img.resize((size + extra_col, size), Image.LANCZOS)
        return list(img.getdata()), (size + extra_col)
    except Exception:
        return None, 0


def average_hash(image_bytes: bytes, hash_size: int = HASH_SIZE) -> int:
    """均值哈希：像素比整体均值亮为1，暗为0"""
    pixels, _ = _to_grayscale_pixels(image_bytes, hash_size)
    if not pixels:
        return None
    avg = sum(pixels) / len(pixels)
    bits = ''.join('1' if p > avg else '0' for p in pixels)
    return int(bits, 2)


def difference_hash(image_bytes: bytes, hash_size: int = HASH_SIZE) -> int:
    """差值哈希：每个像素和右边相邻像素比较亮暗，对整体亮度变化更鲁棒"""
    pixels, row_len = _to_grayscale_pixels(image_bytes, hash_size, extra_col=1)
    if not pixels:
        return None
    bits = []
    for row in range(hash_size):
        row_pixels = pixels[row * row_len:(row + 1) * row_len]
        for col in range(hash_size):
            bits.append('1' if row_pixels[col] > row_pixels[col + 1] else '0')
    return int(''.join(bits), 2)


def hamming_distance(hash_a: int, hash_b: int) -> int:
    return bin(hash_a ^ hash_b).count('1')


def image_similarity(image_a: bytes, image_b: bytes, hash_size: int = HASH_SIZE) -> float:
    """返回 0~1 相似度。aHash 和 dHash 都算，取距离更大(更严格)的那个，
    避免单一哈希算法的偶然巧合导致误判。"""
    try:
        a_ahash, b_ahash = average_hash(image_a, hash_size), average_hash(image_b, hash_size)
        a_dhash, b_dhash = difference_hash(image_a, hash_size), difference_hash(image_b, hash_size)
    except Exception:
        return 0.0
    dist = max(hamming_distance(a_ahash, b_ahash), hamming_distance(a_dhash, b_dhash))
    total_bits = hash_size * hash_size
    return max(0.0, 1 - dist / total_bits)


def is_near_duplicate(image_a: bytes, image_b: bytes, hash_size: int = HASH_SIZE,
                       distance_threshold: int = DISTANCE_THRESHOLD) -> bool:
    a_ahash = average_hash(image_a, hash_size)
    b_ahash = average_hash(image_b, hash_size)
    if a_ahash is None or b_ahash is None:
        return False
    a_dhash = difference_hash(image_a, hash_size)
    b_dhash = difference_hash(image_b, hash_size)
    if a_dhash is None or b_dhash is None:
        return False
    dist = max(hamming_distance(a_ahash, b_ahash), hamming_distance(a_dhash, b_dhash))
    return dist <= distance_threshold


# ===================== 一对一贪心匹配 =====================
def _match_images(images_a: list, images_b: list, hash_size: int = HASH_SIZE,
                   distance_threshold: int = DISTANCE_THRESHOLD) -> list:
    """一对一贪心匹配：每张图最多参与一次匹配，避免"一张图同时命中对方多张图"
    导致命中数被重复计算。逻辑：
      1. 算出所有 (i, j) 图片对里距离 <= 阈值的候选
      2. 按距离从小到大(越像越优先)排序，贪心地依次确认匹配
      3. 一旦某张图被用掉(不管是 A 侧还是 B 侧)，后续候选里包含它的都跳过
    与图片顺序无关——这里是穷举所有 i x j 组合，不是按位置对应，
    所以哪怕两人上传顺序完全相反甚至交叉穿插，也不影响识别结果。
    返回按距离升序的 (i, j, distance) 匹配列表。"""
    if not images_a or not images_b:
        return []
    hashes_a = [(average_hash(img, hash_size), difference_hash(img, hash_size)) for img in images_a]
    hashes_b = [(average_hash(img, hash_size), difference_hash(img, hash_size)) for img in images_b]

    candidates = []
    for i, (a1, a2) in enumerate(hashes_a):
        if a1 is None or a2 is None:
            continue
        for j, (b1, b2) in enumerate(hashes_b):
            if b1 is None or b2 is None:
                continue
            dist = max(hamming_distance(a1, b1), hamming_distance(a2, b2))
            if dist <= distance_threshold:
                candidates.append((dist, i, j))
    candidates.sort(key=lambda c: c[0])

    used_a, used_b = set(), set()
    matched = []
    for dist, i, j in candidates:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        matched.append((i, j, dist))
    return matched


def _match_hashes(hashes_a: list, hashes_b: list, distance_threshold: int = DISTANCE_THRESHOLD) -> list:
    """使用预计算的哈希进行一对一贪心匹配（避免重复计算 Image.open）"""
    if not hashes_a or not hashes_b:
        return []
    candidates = []
    for i, (a1, a2) in enumerate(hashes_a):
        if a1 is None or a2 is None:
            continue
        for j, (b1, b2) in enumerate(hashes_b):
            if b1 is None or b2 is None:
                continue
            dist = max(hamming_distance(a1, b1), hamming_distance(a2, b2))
            if dist <= distance_threshold:
                candidates.append((dist, i, j))
    candidates.sort(key=lambda c: c[0])

    used_a, used_b = set(), set()
    matched = []
    for dist, i, j in candidates:
        if i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        matched.append((i, j, dist))
    return matched


# ===================== 模板图片剔除 =====================
def compute_template_hashes(template_images: list, hash_size: int = HASH_SIZE) -> set:
    """老师示例截图的哈希集合，比对前从每个学生的图片里剔除这些"""
    hashes = set()
    for img in template_images or []:
        try:
            hashes.add(average_hash(img, hash_size))
        except Exception:
            continue
    return hashes


def _filter_template_images(images: list, template_hashes: set, hash_size: int = HASH_SIZE) -> list:
    if not template_hashes:
        return images
    kept = []
    for img in images:
        try:
            h = average_hash(img, hash_size)
        except Exception:
            kept.append(img)
            continue
        if not any(hamming_distance(h, t) <= DISTANCE_THRESHOLD for t in template_hashes):
            kept.append(img)
    return kept


# ===================== 批量查重入口 =====================
def run_image_plagiarism_check(submissions: list, template_images: list = None) -> dict:
    """
    参数:
        submissions: [{"id", "studentName", "studentNumber", "images": [bytes, bytes, ...]}]
                     images 是这份提交里所有截图的原始二进制内容列表
        template_images: 可选，老师提供的示例截图(原始二进制列表)，比对前会从每个学生的
                          图片集合里剔除与模板高度相似的图，避免"大家都用了同一张示例图"
                          被误判为互相抄袭

    返回结构风格与 text.py / code.py 保持一致。
    每条结果额外带 matchedImageCount，表示和最相似对象之间有几张图被判定为疑似复制，
    方便老师直接定位是哪几张截图有问题。
    """
    valid = [s for s in submissions if s.get("images")]
    n = len(valid)
    if n < 2:
        return {"results": [], "message": "有效图片数量不足2份提交，无法进行查重比对"}

    template_hashes = compute_template_hashes(template_images)
    filtered_images = [_filter_template_images(s["images"], template_hashes) for s in valid]

    # 限制每份提交的图片数量，防止 O(图片数²) 导致长时间阻塞
    for i in range(n):
        if len(filtered_images[i]) > MAX_IMAGES_PER_SUBMISSION:
            filtered_images[i] = filtered_images[i][:MAX_IMAGES_PER_SUBMISSION]

    # 预计算所有图片的哈希（一次性计算，避免两两比对中重复 Image.open，性能提升数百倍）
    all_hashes = []
    for i in range(n):
        hashes = []
        for img in filtered_images[i]:
            try:
                a = average_hash(img)
                d = difference_hash(img)
                if a is not None and d is not None:
                    hashes.append((a, d))
            except Exception:
                continue
        all_hashes.append(hashes)

    results = []
    for i in range(n):
        best_rate = 0.0
        best_match = None
        best_match_idx = -1
        best_matched_count = 0
        for j in range(n):
            if i == j:
                continue
            if not all_hashes[i] or not all_hashes[j]:
                continue
            # 使用预计算的哈希进行一对一贪心匹配
            matched_pairs = _match_hashes(all_hashes[i], all_hashes[j])
            matched_count = len(matched_pairs)
            # 用"较小图片集合里被命中的比例"作为该学生这一对的相似度；
            # 因为是一对一匹配，matched_count 天然 <= smaller_count，不会再超过100%
            smaller_count = min(len(all_hashes[i]), len(all_hashes[j])) or 1
            rate = matched_count / smaller_count
            if rate > best_rate:
                best_rate = rate
                best_match = valid[j]
                best_match_idx = j
                best_matched_count = matched_count

        rate_pct = round(best_rate * 100, 2)
        total_imgs = len(all_hashes[i])
        # 单张图片命中时样本量太小，标记低置信度提醒老师
        low_confidence = (total_imgs == 1 and best_matched_count >= 1)
        results.append({
            "submissionId": valid[i]["id"],
            "studentName": valid[i]["studentName"],
            "studentNumber": valid[i]["studentNumber"],
            "imageRate": rate_pct,
            "status": "不合格(疑似抄袭)" if rate_pct > PASS_RATE else "合格",
            "matchName": best_match["studentName"] if best_match else "-",
            "matchId": best_match["studentNumber"] if best_match else "-",
            "matchSubmissionId": valid[best_match_idx]["id"] if best_match_idx >= 0 else None,
            "matchedImageCount": best_matched_count,
            "totalImageCount": total_imgs,
            "lowConfidence": low_confidence,
        })

    results.sort(key=lambda x: x["imageRate"], reverse=True)
    return {
        "results": results,
        "total": n,
        "suspectCount": sum(1 for r in results if r["status"] != "合格"),
        "passRate": PASS_RATE,
        "templateFiltered": bool(template_images),
    }
