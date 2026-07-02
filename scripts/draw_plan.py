"""
寸法線入り 清書平面図ジェネレータ（モジュール版）
旧 draw_dimensioned_plan.py の描画コアを流用。rooms定義は外から渡す。
"""
from PIL import Image, ImageDraw, ImageFont


def load_fonts(scale=1.0):
    base = "/System/Library/Fonts/ヒラギノ角ゴシック"
    try:
        return {
            "title": ImageFont.truetype(f"{base} W6.ttc", int(34 * scale)),
            "room": ImageFont.truetype(f"{base} W6.ttc", int(19 * scale)),
            "area": ImageFont.truetype(f"{base} W3.ttc", int(15 * scale)),
            "dim": ImageFont.truetype(f"{base} W3.ttc", int(14 * scale)),
            "sub": ImageFont.truetype(f"{base} W3.ttc", int(15 * scale)),
        }
    except Exception:
        d = ImageFont.load_default()
        return {k: d for k in ["title", "room", "area", "dim", "sub"]}


def _adjacent(r1, r2, eps=0.02):
    x1, y1, w1, h1 = r1; x2, y2, w2, h2 = r2
    if abs((x1 + w1) - x2) < eps or abs((x2 + w2) - x1) < eps:        # 縦に接触
        return min(y1 + h1, y2 + h2) - max(y1, y2) > eps
    if abs((y1 + h1) - y2) < eps or abs((y2 + h2) - y1) < eps:        # 横に接触
        return min(x1 + w1, x2 + w2) - max(x1, x2) > eps
    return False


def _group_rooms(rooms):
    """同名かつ隣接する矩形を連結成分でまとめる（L字部屋を1部屋に）。"""
    n = len(rooms)
    parent = list(range(n))
    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for i in range(n):
        for j in range(i + 1, n):
            if rooms[i][0] == rooms[j][0] and _adjacent(rooms[i][1:5], rooms[j][1:5]):
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(rooms[i])
    return list(groups.values())


def _subtract(intervals, cut):
    cs, ce = cut
    if ce <= cs:
        return intervals
    out = []
    for s, e in intervals:
        if ce <= s or cs >= e:
            out.append((s, e)); continue
        if cs > s:
            out.append((s, cs))
        if ce < e:
            out.append((ce, e))
    return out


def _union_edges(rects):
    """矩形群の和集合の外周セグメントを返す（内部共有辺は除外）。"""
    segs = []
    for (x, y, w, h) in rects:
        edges = [('v', x, y, y + h, 'left'), ('v', x + w, y, y + h, 'right'),
                 ('h', y, x, x + w, 'top'), ('h', y + h, x, x + w, 'bottom')]
        for orient, fixed, a, b, side in edges:
            intervals = [(a, b)]
            for (x2, y2, w2, h2) in rects:
                if (x2, y2, w2, h2) == (x, y, w, h):
                    continue
                if orient == 'v':
                    if side == 'left' and abs((x2 + w2) - fixed) < 1e-3:
                        intervals = _subtract(intervals, (max(a, y2), min(b, y2 + h2)))
                    elif side == 'right' and abs(x2 - fixed) < 1e-3:
                        intervals = _subtract(intervals, (max(a, y2), min(b, y2 + h2)))
                else:
                    if side == 'top' and abs((y2 + h2) - fixed) < 1e-3:
                        intervals = _subtract(intervals, (max(a, x2), min(b, x2 + w2)))
                    elif side == 'bottom' and abs(y2 - fixed) < 1e-3:
                        intervals = _subtract(intervals, (max(a, x2), min(b, x2 + w2)))
            for s, e in intervals:
                if e - s > 0.01:
                    segs.append((orient, fixed, s, e))
    return segs


def draw_plan(rooms, bldg_w, bldg_h, title, out_path,
              x_dims_top=None, y_dims_left=None, note="", openings=None,
              tatami_m2=1.62):
    """rooms: [(name, x, y, w, h, color), ...] 単位m
    openings: [(x, y, kind), ...] 開口部マーカー(任意)。kind: door/sliding/window
    """
    SCALE = 95
    MARGIN_L, MARGIN_T, MARGIN_R, MARGIN_B = 95, 130, 50, 90
    BG, WALL, DIMC = (250, 249, 245), (40, 40, 40), (110, 110, 110)
    fonts = load_fonts()

    W = int(bldg_w * SCALE) + MARGIN_L + MARGIN_R
    H = int(bldg_h * SCALE) + MARGIN_T + MARGIN_B
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    def px(m): return int(MARGIN_L + m * SCALE)
    def py(m): return int(MARGIN_T + m * SCALE)

    d.rectangle([0, 0, W, 54], fill=(55, 45, 30))
    d.text((24, 12), title, font=fonts["title"], fill=(255, 248, 235))

    # ── 塗り（各矩形）──
    for name, x, y, w, h, color in rooms:
        d.rectangle([px(x), py(y), px(x + w), py(y + h)],
                    fill=color, outline=(150, 140, 120), width=1)

    # ── 同名・隣接の矩形を1部屋（L字可）に統合 ──
    groups = _group_rooms(rooms)

    # 内部壁は統合境界のみ描画（グループ内の共有壁＝内部壁は描かない）
    d.rectangle([px(0), py(0), px(bldg_w), py(bldg_h)], outline=WALL, width=4)
    for g in groups:
        rects = [(x, y, w, h) for (_n, x, y, w, h, _c) in g]
        for orient, fixed, a, b in _union_edges(rects):
            if orient == "v":
                d.line([px(fixed), py(a), px(fixed), py(b)], fill=WALL, width=2)
            else:
                d.line([px(a), py(fixed), px(b), py(fixed)], fill=WALL, width=2)

    # ── 部屋ラベル（グループに1つ・最大矩形の中心、面積は合計）──
    for g in groups:
        name = g[0][0]
        area = sum(w * h for (_n, _x, _y, w, h, _c) in g)
        bx, by, bw_, bh_ = max(((x, y, w, h) for (_n, x, y, w, h, _c) in g),
                               key=lambda r: r[2] * r[3])
        cx, cy = px(bx + bw_ / 2), py(by + bh_ / 2)
        d.text((cx, cy - 11), name, font=fonts["room"], fill=(45, 35, 25), anchor="mm")
        d.text((cx, cy + 10), f"{area:.1f}㎡ / {area / tatami_m2:.1f}畳",
               font=fonts["area"], fill=(90, 80, 65), anchor="mm")

    # ── 開口部(点群実測・detect_openings.py形式のdict) ──
    #    戸=壁を切り欠き+茶線 / 窓=壁を切り欠き+青二重線。位置・幅は実測値。
    #    描かれている壁線上の開口のみ記号化(同名続き間の内側=壁なしには描かない)
    measured = [op for op in (openings or []) if isinstance(op, dict)]
    openings = [op for op in (openings or []) if not isinstance(op, dict)] or None
    if measured:
        wall_segs = [("v", 0.0, 0.0, bldg_h), ("v", bldg_w, 0.0, bldg_h),
                     ("h", 0.0, 0.0, bldg_w), ("h", bldg_h, 0.0, bldg_w)]
        for g in groups:
            rects = [(x, y, w, h) for (_n, x, y, w, h, _c) in g]
            wall_segs += _union_edges(rects)

        def on_wall(op):
            for orient, fixed, a, b in wall_segs:
                if orient != op["ori"]:
                    continue
                if abs(fixed - op["c"]) < 0.08:
                    ov = min(b, op["a1"]) - max(a, op["a0"])
                    if ov > 0.5 * (op["a1"] - op["a0"]):
                        return True
            return False
        measured = [op for op in measured if on_wall(op)]
    if measured:
        DOOR_C, WIN_C = (150, 90, 40), (30, 110, 180)
        for op in measured:
            a0, a1, c = op["a0"], op["a1"], op["c"]
            if op["ori"] == "h":     # 水平壁(x方向) c=y
                p0, p1, pc = px(a0), px(a1), py(c)
                d.line([p0, pc, p1, pc], fill=BG, width=8)          # 壁を切り欠く
                if op["kind"] == "窓":
                    for off in (-3, 3):
                        d.line([p0, pc + off, p1, pc + off], fill=WIN_C, width=2)
                else:
                    d.line([p0, pc, p1, pc], fill=DOOR_C, width=2)
                    for jx in (p0, p1):                              # 方立ての小口
                        d.line([jx, pc - 5, jx, pc + 5], fill=DOOR_C, width=2)
            else:                    # 垂直壁(y方向) c=x
                p0, p1, pc = py(a0), py(a1), px(c)
                d.line([pc, p0, pc, p1], fill=BG, width=8)
                if op["kind"] == "窓":
                    for off in (-3, 3):
                        d.line([pc + off, p0, pc + off, p1], fill=WIN_C, width=2)
                else:
                    d.line([pc, p0, pc, p1], fill=DOOR_C, width=2)
                    for jy in (p0, p1):
                        d.line([pc - 5, jy, pc + 5, jy], fill=DOOR_C, width=2)
        # 凡例
        lx, ly = MARGIN_L + 170, H - MARGIN_B + 56
        d.line([lx, ly, lx + 26, ly], fill=DOOR_C, width=3)
        d.text((lx + 32, ly), "戸・掃き出し(実測)", font=fonts["sub"], fill=(90, 80, 65), anchor="lm")
        for off in (-2, 2):
            d.line([lx + 190, ly + off, lx + 216, ly + off], fill=WIN_C, width=2)
        d.text((lx + 222, ly), "窓(実測)", font=fonts["sub"], fill=(90, 80, 65), anchor="lm")

    # ── 開口部マーカー(旧形式タプル・壁を切り欠いて開口記号を描く) ──
    if openings:
        OPEN_W = int(0.7 * SCALE)  # 開口の見かけ幅 ≒700mm
        colmap = {"door": (200, 90, 40), "sliding": (60, 120, 190),
                  "window": (40, 160, 200)}
        for op in openings:
            ox, oy, kind = op[0], op[1], op[2]
            orient = op[3] if len(op) > 3 else "v"
            col = colmap.get(kind, (150, 150, 150))
            cx, cy = px(ox), py(oy)
            vertical = (orient == "v")
            if vertical:
                y0o, y1o = cy - OPEN_W // 2, cy + OPEN_W // 2
                d.line([cx, y0o, cx, y1o], fill=BG, width=6)        # 壁を白く切る
                d.line([cx, y0o, cx, y1o], fill=col, width=2)       # 開口色
                if kind == "door":  # ドアの開き弧
                    d.arc([cx, cy - OPEN_W // 2, cx + OPEN_W, cy + OPEN_W // 2],
                          90, 180, fill=col, width=2)
            else:
                x0o, x1o = cx - OPEN_W // 2, cx + OPEN_W // 2
                d.line([x0o, cy, x1o, cy], fill=BG, width=6)
                d.line([x0o, cy, x1o, cy], fill=col, width=2)
                if kind == "door":
                    d.arc([cx - OPEN_W // 2, cy, cx + OPEN_W // 2, cy + OPEN_W],
                          180, 270, fill=col, width=2)
        # 凡例
        lx, ly = MARGIN_L, H - MARGIN_B + 56
        for i, (k, label) in enumerate([("door", "ドア/開口"), ("sliding", "引戸/襖")]):
            d.line([lx + i * 130, ly, lx + i * 130 + 22, ly], fill=colmap[k], width=3)
            d.text((lx + i * 130 + 28, ly), label, font=fonts["sub"],
                   fill=(90, 80, 65), anchor="lm")

    def dim_line_h(x0, x1, ytop, value_m):
        ya = py(0) - ytop
        d.line([px(x0), ya, px(x1), ya], fill=DIMC, width=1)
        for xx in (x0, x1):
            d.line([px(xx), ya - 5, px(xx), ya + 5], fill=DIMC, width=1)
            d.line([px(xx), py(0), px(xx), ya], fill=(200, 200, 200), width=1)
        d.text((px((x0 + x1) / 2), ya - 9), f"{value_m*1000:.0f}",
               font=fonts["dim"], fill=(70, 70, 70), anchor="mb")

    if x_dims_top:
        for i in range(len(x_dims_top) - 1):
            dim_line_h(x_dims_top[i], x_dims_top[i + 1], 30, x_dims_top[i + 1] - x_dims_top[i])
        dim_line_h(0, bldg_w, 62, bldg_w)

    def dim_line_v(y0, y1, xleft, value_m):
        xa = px(0) - xleft
        d.line([xa, py(y0), xa, py(y1)], fill=DIMC, width=1)
        for yy in (y0, y1):
            d.line([xa - 5, py(yy), xa + 5, py(yy)], fill=DIMC, width=1)
            d.line([px(0), py(yy), xa, py(yy)], fill=(200, 200, 200), width=1)
        mid = py((y0 + y1) / 2)
        tmp = Image.new("RGBA", (60, 20), (0, 0, 0, 0))
        ImageDraw.Draw(tmp).text((30, 10), f"{value_m*1000:.0f}",
                                 font=fonts["dim"], fill=(70, 70, 70), anchor="mm")
        tmp = tmp.rotate(90, expand=True)
        img.paste(tmp, (xa - tmp.width - 2, mid - tmp.height // 2), tmp)

    if y_dims_left:
        for i in range(len(y_dims_left) - 1):
            dim_line_v(y_dims_left[i], y_dims_left[i + 1], 30, y_dims_left[i + 1] - y_dims_left[i])
        dim_line_v(0, bldg_h, 62, bldg_h)

    # 方位
    nx, ny = px(bldg_w) - 18, py(0) + 24
    d.line([nx, ny + 22, nx, ny - 12], fill=WALL, width=2)
    d.polygon([(nx, ny - 20), (nx - 6, ny - 8), (nx + 6, ny - 8)], fill=WALL)
    d.text((nx, ny + 34), "N", font=fonts["sub"], fill=WALL, anchor="mm")

    # スケールバー
    bx, by = px(0), py(bldg_h) + 34
    d.line([bx, by, bx + SCALE, by], fill=WALL, width=3)
    for xx in (bx, bx + SCALE):
        d.line([xx, by - 5, xx, by + 5], fill=WALL, width=2)
    d.text((bx + SCALE // 2, by + 8), "1m", font=fonts["sub"], fill=WALL, anchor="mt")

    if note:
        d.text((bx + SCALE + 40, by - 4), note, font=fonts["sub"], fill=(130, 115, 90))
    d.text((W - 24, by + 4), "寸法単位: mm", font=fonts["sub"], fill=(130, 115, 90), anchor="rt")

    out_path = str(out_path)
    img.save(out_path, "JPEG" if out_path.endswith("jpg") else "PNG", quality=94)
    print(f"  保存: {out_path}  {W}×{H}px")
    return out_path
