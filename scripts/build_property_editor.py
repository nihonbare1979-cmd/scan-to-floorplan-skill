"""
物件 間取りエディタ 一括ビルド。

  1) 点群GLBから下敷き画像(bg.png/b64)を生成
  2) build_editor.py でエディタHTMLを生成

使い方:
  python3 build_property_editor.py <glb_path> <floor_name> [rotate_deg] [flip_lr] [slice_low] [slice_high]

  例(1階・10.5度補正・東西反転・腰高スライス):
    python3 build_property_editor.py glb/property_1f.glb 1f -10.5 true 0.9 1.3
  例(2階・5.1度補正・東西反転・全点投影):
    python3 build_property_editor.py glb/property_2f.glb 2f 5.1 true

出力:
  intermediate/<stem>_bg.png / .b64
  editor_<stem>.html   ← Chromeで開いて点群に合わせて間取りをトレース
"""
import base64
import subprocess
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from load_glb import load_points

BASE = Path(__file__).parent
MID = BASE / "intermediate"
MID.mkdir(exist_ok=True)


def parse_args():
    if len(sys.argv) < 3:
        print("使い方: python3 build_property_editor.py <glb_path> <floor_name> "
              "[rotate_deg] [flip_lr] [slice_low] [slice_high]")
        sys.exit(1)
    glb_path = Path(sys.argv[1])
    floor_name = sys.argv[2]
    rotate_deg = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    flip_lr = sys.argv[4].lower() == "true" if len(sys.argv) > 4 else False
    slice_range = None
    if len(sys.argv) > 6:
        slice_range = (float(sys.argv[5]), float(sys.argv[6]))
    return glb_path, floor_name, rotate_deg, flip_lr, slice_range


def make_bg(glb_path, floor_name, rotate_deg=0.0, flip_lr=False, slice_range=(0.9, 1.3)):
    """点群を真上から見た下敷きPNGを生成し、base64も書き出す。"""
    stem = glb_path.stem
    v, c = load_points(glb_path)

    if abs(rotate_deg) > 0.01:
        rad = np.radians(rotate_deg)
        cos_r, sin_r = np.cos(rad), np.sin(rad)
        R = np.array([[cos_r, -sin_r], [sin_r, cos_r]])
        v = v.copy()
        v[:, :2] = (R @ v[:, :2].T).T

    if slice_range is None:
        pts, col = v, c
    else:
        zf = v[:, 2] - v[:, 2].min()
        m = (zf > slice_range[0]) & (zf < slice_range[1])
        pts, col = (v[m], c[m]) if m.sum() > 2000 and len(c) == len(v) else (v, c)

    x, y = pts[:, 0], pts[:, 1]
    x0, x1 = np.percentile(x, [1, 99])
    y0, y1 = np.percentile(y, [1, 99])
    sel = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)

    xs, ys = -x[sel], -y[sel]
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    col_sel = col[sel][:, :3] / 255.0 if len(col) == len(pts) else None

    fig, ax = plt.subplots(figsize=(8, 8 * (y1 - y0) / max(x1 - x0, 0.01)))
    py = -ys

    if slice_range is None:
        nbx = max(60, int((x1 - x0) / 0.025))
        nby = max(60, int((y1 - y0) / 0.025))
        H, _, _ = np.histogram2d(xs, py, bins=[nbx, nby])
        vmax = np.percentile(H[H > 0], 90)
        ax.imshow(H.T, origin="lower", extent=[x0, x1, py.min(), py.max()],
                  cmap="Greys", vmin=0, vmax=vmax, interpolation="nearest", aspect="equal")
    else:
        ax.scatter(xs, py, s=4.0, c="#444444", marker=".", linewidths=0, alpha=0.6)

    ax.set_xlim(x0, x1)
    ax.set_ylim(-y1, -y0)
    ax.set_aspect("equal")
    ax.axis("off")

    png = MID / f"{stem}_bg.png"
    fig.savefig(png, dpi=180, facecolor="white", bbox_inches="tight", pad_inches=0)
    plt.close(fig)

    if flip_lr:
        from PIL import Image as PilImage
        img = PilImage.open(png)
        img = img.transpose(PilImage.FLIP_LEFT_RIGHT)
        img.save(png)

    b64_path = MID / f"{stem}_bg.b64"
    b64_path.write_text(base64.b64encode(png.read_bytes()).decode())
    print(f"下敷き生成: {png}")
    return str(b64_path), stem


def main():
    glb_path, floor_name, rotate_deg, flip_lr, slice_range = parse_args()
    b64_path, stem = make_bg(glb_path, floor_name, rotate_deg, flip_lr, slice_range)

    out_html = f"editor_{stem}.html"
    init_json = f"{stem}_rooms.json"
    subprocess.run(
        ["python3", "build_editor.py", init_json, b64_path, out_html],
        cwd=BASE, check=True)
    print(f"\n完了: {out_html} をChromeで開いて点群に合わせて間取りをトレースしてください")


if __name__ == "__main__":
    main()
