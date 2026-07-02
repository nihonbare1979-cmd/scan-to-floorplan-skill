"""
共有座標系トレース(build_shared_editors由来)の仕上げ。
  - 通し柱候補＋◎○△ランク(同一座標系なので登録不要)
  - 統合立面図(南/東)
  - 1F/2F平面図(寸法線つき・両階を同じ原点に正規化)

使い方:
  python3 finish_shared.py <full.glb> <1f_traced.json> <2f_traced.json> <out_prefix> <title>
"""
import json
import sys
from pathlib import Path

import numpy as np

from finish_through import registered_cloud, draw_section
from build_shared_editors import rotate_xy
import structural_draft as S
import generate_floorplan as GF

BASE = Path(__file__).parent


def _find(name):
    """設定JSONを カレント(=物件プロジェクトフォルダ) → scripts/ の順で探す。"""
    p = Path.cwd() / name
    return p if p.exists() else BASE / name


def cloud_new_frame(glb):
    """点群を、トレースと同じ新フレーム(回転+原点シフト)へ載せる。"""
    t = json.loads(_find("shared_frame.json").read_text())
    v, c = registered_cloud(glb)
    v[:, :2] = rotate_xy(v[:, :2], np.array(t["center"]), t["yaw"])
    v[:, 0] += t["ox"]; v[:, 1] += t["oy"]
    return v, c


def derive_dims(rooms, axis, tol=0.12):
    """部屋の辺からクラスタリングして寸法線位置を作る。"""
    vals = []
    for r in rooms:
        if axis == "x":
            vals += [r["x"], r["x"] + r["w"]]
        else:
            vals += [r["y"], r["y"] + r["h"]]
    vals = sorted(vals)
    out = []
    for v in vals:
        if not out or v - out[-1] > tol:
            out.append(round(v, 2))
        else:
            out[-1] = round((out[-1] + v) / 2, 2)
    return out


def make_plan(traced_path, out_path):
    """各階を自前の外形に正規化(min→0)して寸法線つき平面図を清書。"""
    d = json.loads(Path(traced_path).read_text())
    ox = min(r["x"] for r in d["rooms"])
    oy = min(r["y"] for r in d["rooms"])
    rooms = []
    for r in d["rooms"]:
        rr = dict(r); rr["x"] = round(r["x"] - ox, 2); rr["y"] = round(r["y"] - oy, 2)
        rooms.append(rr)
    bw = round(max(r["x"] + r["w"] for r in rooms), 2)
    bh = round(max(r["y"] + r["h"] for r in rooms), 2)
    # 開口(detect_openings.py由来)も同じ正規化でシフト
    openings = []
    for op in d.get("openings", []):
        oo = dict(op)
        if op["ori"] == "h":
            oo["c"] = round(op["c"] - oy, 2)
            oo["a0"] = round(op["a0"] - ox, 2); oo["a1"] = round(op["a1"] - ox, 2)
        else:
            oo["c"] = round(op["c"] - ox, 2)
            oo["a0"] = round(op["a0"] - oy, 2); oo["a1"] = round(op["a1"] - oy, 2)
        openings.append(oo)
    data = {"title": d["title"], "bldg_w": bw, "bldg_h": bh,
            "x_dims": derive_dims(rooms, "x"), "y_dims": derive_dims(rooms, "y"),
            "rooms": rooms, "openings": openings}
    GF.render(data, out_path)
    print("  保存:", out_path, f"({len(rooms)}室 {bw}×{bh}m 開口{len(openings)})")


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

    # 通し柱(同一座標系なので直接)
    posts = S.draw_overlay(d1, d2, f"output/{prefix}_structural_overlay.jpg", title)
    print("通し柱候補:", len(posts), "本")
    cloud, colors = cloud_new_frame(glb)
    ranked = S.rank_posts(posts, cloud)
    S.draw_ranked(d1, d2, ranked, f"output/{prefix}_posts_ranked.jpg", title)
    for (x, y, rk, n1, n2, vc) in ranked:
        if rk in ("◎", "○"):
            print(f"  ★柱({x:.2f},{y:.2f}) {rk} 1F点{n1} 2F点{n2} 垂直被覆{vc}")

    # 統合立面図
    draw_section(d1, posts, cloud, colors, f"output/{prefix}_section_south.jpg", "south", title)
    draw_section(d1, posts, cloud, colors, f"output/{prefix}_section_east.jpg", "east", title)

    # 平面図(各階を自前の外形に正規化)
    make_plan(f1, f"output/{prefix}_1F平面図.jpg")
    make_plan(f2, f"output/{prefix}_2F平面図.jpg")


if __name__ == "__main__":
    main()
