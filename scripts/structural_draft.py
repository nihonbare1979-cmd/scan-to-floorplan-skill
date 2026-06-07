"""
構造叩き台: 1F/2F整合 → 通し柱候補の抽出
通し柱は1F・2Fを貫く → 両階の図面で同じXYに壁の角が来る。
両階で一致する角を「通し柱候補」として抽出する（叩き台・要現場確認）。
※同一座標系(9.04x9.72, 同じ原点・東西反転)で1F/2Fを作成済みなので直接重ねられる。
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

FP = font_manager.FontProperties(fname="/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc")


def corners(rooms):
    """各部屋矩形の4隅を返す。"""
    pts = []
    for r in rooms:
        x, y, w, h = r["x"], r["y"], r["w"], r["h"]
        pts += [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
    return pts


def edges(rooms):
    """各部屋矩形の4辺(線分)を返す。"""
    segs = []
    for r in rooms:
        x, y, w, h = r["x"], r["y"], r["w"], r["h"]
        segs += [((x, y), (x + w, y)), ((x, y + h), (x + w, y + h)),
                 ((x, y), (x, y + h)), ((x + w, y), (x + w, y + h))]
    return segs


def cluster(points, tol=0.18):
    """近接点をまとめ、各クラスタの重心と「集まった数」を返す。"""
    pts = list(points)
    used = [False] * len(pts)
    out = []
    for i in range(len(pts)):
        if used[i]:
            continue
        grp = [pts[i]]
        used[i] = True
        for j in range(i + 1, len(pts)):
            if not used[j] and abs(pts[j][0] - pts[i][0]) < tol and abs(pts[j][1] - pts[i][1]) < tol:
                grp.append(pts[j]); used[j] = True
        cx = sum(p[0] for p in grp) / len(grp)
        cy = sum(p[1] for p in grp) / len(grp)
        out.append((round(cx, 2), round(cy, 2), len(grp)))
    return out


def _on_seg(pt, seg, tol=0.20):
    """点ptが軸平行線分seg上(perp距離<tol かつ範囲内)にあるか。"""
    (ax, ay), (bx, by) = seg
    px, py = pt
    if abs(ay - by) < 1e-6:      # 水平辺
        return abs(py - ay) < tol and min(ax, bx) - tol < px < max(ax, bx) + tol
    if abs(ax - bx) < 1e-6:      # 垂直辺
        return abs(px - ax) < tol and min(ay, by) - tol < py < max(ay, by) + tol
    return False


def through_posts(rooms1, rooms2, tol=0.22):
    """通し柱候補 = 2Fの角が1Fの壁線上に乗る点 ∪ 1Fの角が2Fの壁線上に乗る点。
    （2階の荷重を支える垂直材が1階に通る位置）"""
    e1, e2 = edges(rooms1), edges(rooms2)
    cand = []
    for (cx, cy, _n) in cluster(corners(rooms2)):
        if any(_on_seg((cx, cy), s, tol) for s in e1):
            cand.append((cx, cy))
    for (cx, cy, _n) in cluster(corners(rooms1)):
        if any(_on_seg((cx, cy), s, tol) for s in e2):
            cand.append((cx, cy))
    return [(x, y) for (x, y, _n) in cluster(cand, 0.25)]


def draw_overlay(d1, d2, out_path, title="成合町3号"):
    BW, BH = d1["bldg_w"], d1["bldg_h"]
    fig, ax = plt.subplots(figsize=(9, 9 * BH / BW))
    # 1F 壁(黒)
    for (a, b) in edges(d1["rooms"]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#333", lw=1.6, zorder=2)
    # 2F 壁(赤・破線)
    for (a, b) in edges(d2["rooms"]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#d22", lw=1.4, ls=(0, (4, 2)), zorder=3)
    # 外周
    ax.plot([0, BW, BW, 0, 0], [0, 0, BH, BH, 0], color="#000", lw=3, zorder=1)
    # 通し柱候補
    posts = through_posts(d1["rooms"], d2["rooms"])
    for (x, y) in posts:
        ax.add_patch(plt.Rectangle((x - 0.06, y - 0.06), 0.12, 0.12,
                                   fc="#1565c0", ec="black", lw=1, zorder=5))
    ax.plot([], [], color="#333", lw=2, label="1階の壁")
    ax.plot([], [], color="#d22", lw=2, ls="--", label="2階の壁")
    ax.scatter([], [], marker="s", c="#1565c0", edgecolors="black", s=80, label="通し柱 候補")
    ax.legend(prop=FP, loc="upper left", fontsize=10)
    ax.set_xlim(-0.4, BW + 0.4); ax.set_ylim(BH + 0.4, -0.4); ax.set_aspect("equal")
    ax.set_title(f"{title} 1F/2F整合図 ＋ 通し柱候補（叩き台・要確認）", fontproperties=FP, fontsize=14)
    ax.set_xticks(range(0, 10)); ax.set_yticks(range(0, 10))
    ax.grid(True, color="#eee", lw=0.5)
    fig.tight_layout(); fig.savefig(out_path, dpi=140, facecolor="white")
    plt.close(fig)
    print(f"  保存: {out_path}  通し柱候補 {len(posts)}本")
    return posts


def rank_posts(posts, v, r=0.22):
    """各候補の床〜2F天井の垂直点密度から通し柱の確度をランク分け。
    返り値: [(x, y, rank, n1, n2, vcov)] rank: ◎/○/△/?"""
    xy, z = v[:, :2], v[:, 2]
    NB, ZMAX = 18, 5.3
    out = []
    for (px, py) in posts:
        m = (abs(xy[:, 0] - px) < r) & (abs(xy[:, 1] - py) < r)
        zz = z[m]
        n1 = int(((zz > 0.1) & (zz < 2.3)).sum())     # 1F分の点
        n2 = int(((zz > 2.4) & (zz < 5.2)).sum())     # 2F分の点
        bins = [((zz >= b * ZMAX / NB) & (zz < (b + 1) * ZMAX / NB)).sum() for b in range(NB)]
        vcov = sum(1 for b in bins if b >= 3) / NB
        if n1 + n2 < 40:
            rk = "?"                                   # データ不足
        elif n1 >= 100 and n2 >= 100 and vcov >= 0.8:
            rk = "◎"                                   # 床〜2F天井まで連続=通し柱濃厚
        elif (n1 >= 80 and n2 >= 80) or (vcov >= 0.65 and min(n1, n2) >= 60):
            rk = "○"                                   # 両階に点あり
        else:
            rk = "△"                                   # 主に片階のみ=通し柱でない可能性
        out.append((px, py, rk, n1, n2, round(vcov, 2)))
    return out


def draw_ranked(d1, d2, ranked, out_path):
    BW, BH = d1["bldg_w"], d1["bldg_h"]
    fig, ax = plt.subplots(figsize=(9, 9 * BH / BW))
    for (a, b) in edges(d1["rooms"]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#bbb", lw=1.2, zorder=2)
    for (a, b) in edges(d2["rooms"]):
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#e3a0a0", lw=1.0, ls=(0, (4, 2)), zorder=2)
    ax.plot([0, BW, BW, 0, 0], [0, 0, BH, BH, 0], color="#888", lw=2, zorder=1)
    style = {"◎": ("#c62828", 0.20), "○": ("#ef9a00", 0.15), "△": ("#9e9e9e", 0.09), "?": ("#fff", 0.09)}
    cnt = {"◎": 0, "○": 0, "△": 0, "?": 0}
    for (x, y, rk, n1, n2, vc) in ranked:
        col, sz = style[rk]
        ec = "#777" if rk == "?" else "black"
        ax.add_patch(plt.Rectangle((x - sz, y - sz), sz * 2, sz * 2, fc=col, ec=ec, lw=1.3, zorder=5))
        cnt[rk] += 1
    for rk, lab in [("◎", "通し柱 濃厚(床〜2F天井に連続)"), ("○", "両階に点あり"),
                    ("△", "主に片階のみ"), ("?", "データ不足")]:
        ax.scatter([], [], marker="s", c=style[rk][0], edgecolors="black",
                   s=90, label=f"{rk} {lab}（{cnt[rk]}）")
    ax.legend(prop=FP, loc="upper left", fontsize=9)
    ax.set_xlim(-0.4, BW + 0.4); ax.set_ylim(BH + 0.4, -0.4); ax.set_aspect("equal")
    ax.set_title("成合町3号 通し柱候補ランク（点群の垂直連続で判定・要現場確認）",
                 fontproperties=FP, fontsize=13)
    ax.set_xticks(range(0, 10)); ax.set_yticks(range(0, 10)); ax.grid(True, color="#eee", lw=0.5)
    fig.tight_layout(); fig.savefig(out_path, dpi=140, facecolor="white")
    plt.close(fig)
    print(f"  保存: {out_path}  ◎{cnt['◎']} ○{cnt['○']} △{cnt['△']} ?{cnt['?']}")


def load_aligned_cloud(glb="glb/narukami_3.glb", bw=9.04):
    """点群を平面図と同じ建物座標(原点NW・東西反転・床=0)に変換して返す。"""
    from load_glb import load_points
    from extract_elevation import normalize_floor
    v, c = load_points(glb)
    v, fz, ch = normalize_floor(v)         # 1F床=0
    x0, y0 = v[:, 0].min(), v[:, 1].min()
    v[:, 0] = bw - (v[:, 0] - x0)          # X反転(平面図と同じ)
    v[:, 1] = v[:, 1] - y0
    return v, c


def draw_section(d1, posts, out_path, glb="glb/narukami_3.glb"):
    """統合立面図(南から見た断面): 1F+2Fを縦に積んだ実測断面。
    床=0 / 1F天井≒2.35 / 2F天井≒5.2。通し柱候補のX位置を縦ガイドで示す。"""
    v, c = load_aligned_cloud(glb, d1["bldg_w"])
    rgb = c[:, :3] / 255.0
    m = (v[:, 2] > -0.1) & (v[:, 2] < 5.6)
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.scatter(v[m, 0], v[m, 2], s=1.0, c=rgb[m], marker=".", linewidths=0)
    # 床・天井ライン
    for zz, lab in [(0, "1F床 GL=0"), (2.35, "1F天井/2F床 ≒2.35m"), (5.21, "2F天井 ≒5.2m")]:
        ax.axhline(zz, color="#c05028", lw=1.2, ls="--")
        ax.text(0, zz + 0.06, lab, color="#c05028", fontsize=10, fontproperties=FP)
    # 通し柱候補のX位置に縦ガイド
    for (x, y) in posts:
        ax.axvline(x, color="#1565c0", lw=1.0, alpha=0.5)
    ax.plot([], [], color="#1565c0", label="通し柱候補のX位置")
    ax.legend(prop=FP, loc="upper right", fontsize=10)
    ax.set_xlim(-0.3, d1["bldg_w"] + 0.3); ax.set_ylim(-0.3, 5.6)
    ax.set_aspect("equal")
    ax.set_xlabel("東西方向 (m)", fontproperties=FP)
    ax.set_ylabel("高さ (m)", fontproperties=FP)
    ax.set_title("成合町3号 統合立面図(南から見た断面・1F+2F)　※高さ=実測・叩き台",
                 fontproperties=FP, fontsize=13)
    fig.tight_layout(); fig.savefig(out_path, dpi=140, facecolor="white")
    plt.close(fig)
    print(f"  保存: {out_path}")


if __name__ == "__main__":
    import os
    import sys
    a = sys.argv
    # 引数: [1f.json] [2f.json] [out_prefix] [title] [glb]  省略時は成合町
    d1f = a[1] if len(a) > 1 else "narukami_rooms.json"
    d2f = a[2] if len(a) > 2 else "narukami_2f_rooms.json"
    prefix = a[3] if len(a) > 3 else "narukami"
    title = a[4] if len(a) > 4 else "成合町3号"
    glb = a[5] if len(a) > 5 else ("glb/narukami_3.glb" if len(a) <= 3 else None)

    d1 = json.loads(open(d1f).read())
    d2 = json.loads(open(d2f).read())
    # 階段位置の整合チェック
    s1 = [r for r in d1["rooms"] if "階段" in r["name"]]
    s2 = [r for r in d2["rooms"] if "階段" in r["name"]]
    print("=== 階段位置の整合 ===")
    for s in s1: print(f"  1F階段: x={s['x']:.2f}-{s['x']+s['w']:.2f} y={s['y']:.2f}-{s['y']+s['h']:.2f}")
    for s in s2: print(f"  2F階段: x={s['x']:.2f}-{s['x']+s['w']:.2f} y={s['y']:.2f}-{s['y']+s['h']:.2f}")
    posts = draw_overlay(d1, d2, f"output/{prefix}_structural_overlay.jpg", title)
    print("通し柱候補座標:", [(round(x, 2), round(y, 2)) for x, y in posts])
    # 統合立面図(断面)は1F+2F連続点群が要る。glb指定があれば実行
    if glb and os.path.exists(glb):
        try:
            draw_section(d1, posts, f"output/{prefix}_section.jpg", glb)
        except Exception as e:
            print("断面図スキップ:", e)
    else:
        print("断面図スキップ: 単一の1F+2F連続点群が無いため(階別スキャンの制約)")
