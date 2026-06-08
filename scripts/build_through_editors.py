"""
通しスキャン専用: 1F/2F を「同一座標系(共有原点・共有スケール)」で下敷き化し、
各階のエディタHTMLを生成する。

通常の build_property_editor.py は階ごとに percentile で別々にbboxを切るため、
1F/2Fの原点がズレて通し柱判定に使えない。本スクリプトは
  ・建物の共有extent(1Fフットプリント基準)を1回だけ決める
  ・1F/2Fとも同じextentに投影する → 座標が直接重なる(整合作業⑥が不要)

使い方:
  python3 build_through_editors.py <full.glb> <floor1_z> <slab_z> [yaw_deg] [flip_lr]
    floor1_z : 1F床のZ(生zから引く値。例 zmin+0.54)
    slab_z   : 1F天井/2F床スラブの境界(zf基準, 例 3.1)。これ未満=1F, 以上=2F
    yaw_deg  : 水平回転(度)
    flip_lr  : true で東西反転

出力:
  intermediate/through_1f_bg.png/.b64 , through_2f_bg.png/.b64
  ogimachi_through_1f_rooms.json / _2f_rooms.json  (空・共有bldg寸法)
  editor_through_1f.html / editor_through_2f.html
"""
import base64
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image as PilImage

from load_glb import load_points

BASE = Path(__file__).parent
MID = BASE / "intermediate"
MID.mkdir(exist_ok=True)


def yaw_rotate(v2, deg):
    if abs(deg) < 1e-3:
        return v2
    r = np.radians(deg)
    R = np.array([[np.cos(r), -np.sin(r)], [np.sin(r), np.cos(r)]])
    return (R @ v2.T).T


def render_slice(xs, ys, extent, out_png, slice_scatter=True, col=None):
    """xs,ys(=表示座標)を共有extent[x0,x1,y0,y1]で描く。"""
    x0, x1, y0, y1 = extent
    fig, ax = plt.subplots(figsize=(8, 8 * (y1 - y0) / max(x1 - x0, 0.01)))
    if slice_scatter:
        ax.scatter(xs, ys, s=4.0, c="#444444", marker=".", linewidths=0, alpha=0.6)
    else:
        nbx = max(60, int((x1 - x0) / 0.025))
        nby = max(60, int((y1 - y0) / 0.025))
        H, _, _ = np.histogram2d(xs, ys, bins=[nbx, nby], range=[[x0, x1], [y0, y1]])
        vmax = np.percentile(H[H > 0], 90) if (H > 0).any() else 1
        ax.imshow(H.T, origin="lower", extent=[x0, x1, y0, y1],
                  cmap="Greys", vmin=0, vmax=vmax, interpolation="nearest", aspect="equal")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.savefig(out_png, dpi=180, facecolor="white", bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def to_disp(v, flip_lr):
    """world(x,y) → 表示座標(xs,ys)。build_property_editor と同じ向き:
    xs=-x, 上下は y下向き。flip_lrでxsを反転。"""
    xs = -v[:, 0]
    ys = -v[:, 1]      # 表示は y を下向きにするため後で y軸反転して使う
    if flip_lr:
        xs = -xs
    return xs, ys


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    glb = Path(sys.argv[1])
    floor1_z = float(sys.argv[2])
    slab_zf = float(sys.argv[3])
    yaw = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    flip = (sys.argv[5].lower() == "true") if len(sys.argv) > 5 else False

    v, c = load_points(glb)
    v = v.copy()
    v[:, 2] = v[:, 2] - floor1_z          # 1F床=0
    v[:, :2] = yaw_rotate(v[:, :2], yaw)   # 水平回転
    zf = v[:, 2]

    # 階マスク(腰高スライス) — 共有extentは1Fフットプリント基準
    m1 = (zf > 0.9) & (zf < 1.6)                       # 1F 腰高
    m2 = (zf > slab_zf + 0.5) & (zf < slab_zf + 1.2)   # 2F 腰高

    # 共有extent: 1F全点(床上0.3〜天井下)の外周 = 建物フットプリント
    foot = (zf > 0.3) & (zf < slab_zf - 0.2)
    fx, fy = to_disp(v[foot], flip)
    fy = -fy  # y下向き表示へ
    x0, x1 = np.percentile(fx, [1, 99])
    y0, y1 = np.percentile(fy, [1, 99])
    bw, bh = x1 - x0, y1 - y0
    print(f"共有extent: x {x0:.2f}〜{x1:.2f} ({bw:.2f}m)  y {y0:.2f}〜{y1:.2f} ({bh:.2f}m)")

    results = {}
    for name, mask in [("1f", m1), ("2f", m2)]:
        xs, ys = to_disp(v[mask], flip)
        ys = -ys
        out_png = MID / f"through_{name}_bg.png"
        render_slice(xs, ys, (x0, x1, y0, y1), out_png, slice_scatter=True)
        if flip:
            img = PilImage.open(out_png).transpose(PilImage.FLIP_LEFT_RIGHT)
            img.save(out_png)
        b64 = MID / f"through_{name}_bg.b64"
        b64.write_text(base64.b64encode(out_png.read_bytes()).decode())
        results[name] = b64
        print(f"下敷き生成: {out_png.name}  ({mask.sum()}点)")

    # 共有bldg寸法の空JSON(原点0,0・幅bw・高bh)。座標系が共有=通し柱直接判定可
    for name in ("1f", "2f"):
        p = BASE / f"ogimachi_through_{name}_rooms.json"
        if p.exists():
            print(f"既存 {p.name} を保持")
            continue
        data = {"title": f"扇町2号 {name.upper()} 平面図",
                "bldg_w": round(bw, 2), "bldg_h": round(bh, 2),
                "x_dims": [0, round(bw, 2)], "y_dims": [0, round(bh, 2)], "rooms": []}
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    for name in ("1f", "2f"):
        out_html = f"editor_through_{name}.html"
        subprocess.run(["python3", "build_editor.py",
                        f"ogimachi_through_{name}_rooms.json",
                        str(results[name].relative_to(BASE)), out_html],
                       cwd=BASE, check=True)
    print("\n完了: editor_through_1f.html / editor_through_2f.html をChromeで開いてトレース")


if __name__ == "__main__":
    main()
