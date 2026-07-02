"""
通しスキャン仕上げ: レジストレーション変換で連続点群を既存レイアウト座標系へ載せ、
  ・1F/2F整合図＋通し柱候補(overlay)
  ・通し柱候補の◎○△ランク(床〜2F天井の垂直連続で判定)
  ・統合立面図(南/東の断面)
を出力する。

使い方:
  python3 finish_through.py <full.glb> <1f.json> <2f_aligned.json> <out_prefix> <title>
"""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from load_glb import load_points
from extract_elevation import normalize_floor
import structural_draft as S

FP = font_manager.FontProperties(fname="/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc")
BASE = Path(__file__).parent


def _find(name):
    """設定JSONを カレント(=物件プロジェクトフォルダ) → scripts/ の順で探す。"""
    p = Path.cwd() / name
    return p if p.exists() else BASE / name


def registered_cloud(glb):
    """変換JSONを適用し、点群を既存レイアウト座標系(room frame, 床=0)へ。"""
    t = json.loads(_find("through_transform.json").read_text())
    v, c = load_points(glb)
    v, fz, ch = normalize_floor(v)              # 1F床=0
    out = v.copy()
    out[:, 0] = t["sgx"] * v[:, 0] + t["off_x"]
    out[:, 1] = t["sgy"] * v[:, 1] + t["off_y"]
    return out, c


def draw_section(d1, posts, cloud, colors, out_path, direction, title):
    """登録済み点群で断面(立面)を描く。direction: 'south'(X横軸) / 'east'(Y横軸)。"""
    v, c = cloud, colors
    rgb = c[:, :3] / 255.0
    m = (v[:, 2] > -0.2) & (v[:, 2] < 5.6)
    hor = v[m, 0] if direction == "south" else v[m, 1]
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.scatter(hor, v[m, 2], s=1.0, c=rgb[m], marker=".", linewidths=0)
    for zz, lab in [(0, "1F床 GL=0"), (2.37, "1F天井/2F床スラブ ≒2.4m"), (5.2, "2F天井 ≒5.2m")]:
        ax.axhline(zz, color="#c05028", lw=1.0, ls="--")
        ax.text(hor.min(), zz + 0.05, lab, color="#c05028", fontsize=10, fontproperties=FP)
    for zz in np.arange(0, 5.6, 0.5):
        ax.axhline(zz, color="#eee", lw=0.4, zorder=0)
    # 通し柱候補の水平位置に縦ガイド
    for (x, y) in posts:
        gx = x if direction == "south" else y
        ax.axvline(gx, color="#1565c0", lw=0.9, alpha=0.45)
    ax.plot([], [], color="#1565c0", label="通し柱候補の位置")
    ax.legend(prop=FP, loc="upper right", fontsize=10)
    ax.set_aspect("equal"); ax.set_ylim(-0.3, 5.6)
    ax.set_xlabel("東西方向 (m)" if direction == "south" else "南北方向 (m)", fontproperties=FP)
    ax.set_ylabel("高さ (m)", fontproperties=FP)
    dlab = "南から(東西断面)" if direction == "south" else "東から(南北断面)"
    ax.set_title(f"{title} 統合立面図 {dlab}・1F+2F通し　※高さ=実測・叩き台",
                 fontproperties=FP, fontsize=13)
    fig.tight_layout(); fig.savefig(out_path, dpi=140, facecolor="white")
    plt.close(fig)
    print("  保存:", out_path)


def main():
    glb, f1, f2, prefix, title = sys.argv[1:6]
    d1 = json.loads(Path(f1).read_text())
    d2 = json.loads(Path(f2).read_text())
    outdir = Path.cwd() / "output" / prefix.split("/")[0]
    outdir.mkdir(parents=True, exist_ok=True)

    # 階段整合チェック
    print("=== 階段位置の整合 ===")
    for tag, d in [("1F", d1), ("2F", d2)]:
        for s in [r for r in d["rooms"] if "階段" in r["name"]]:
            print(f"  {tag}階段: x={s['x']:.2f}-{s['x']+s['w']:.2f} y={s['y']:.2f}-{s['y']+s['h']:.2f}")

    posts = S.draw_overlay(d1, d2, f"output/{prefix}_structural_overlay.jpg", title)
    print("通し柱候補:", [(round(x, 2), round(y, 2)) for x, y in posts])

    cloud, colors = registered_cloud(glb)
    ranked = S.rank_posts(posts, cloud)
    S.draw_ranked(d1, d2, ranked, f"output/{prefix}_posts_ranked.jpg", title)
    for (x, y, rk, n1, n2, vc) in ranked:
        print(f"  柱({x:.2f},{y:.2f}) {rk} 1F点{n1} 2F点{n2} 垂直被覆{vc}")

    draw_section(d1, posts, cloud, colors, f"output/{prefix}_section_south.jpg", "south", title)
    draw_section(d1, posts, cloud, colors, f"output/{prefix}_section_east.jpg", "east", title)


if __name__ == "__main__":
    main()
