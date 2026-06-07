"""
扇町2号 間取りエディタ 一括ビルド。
  1) 点群GLB(ogimachi_1f/2f.glb)から下敷き画像(bg.png/b64)を生成
     ※ 1Fは点群が10.5度時計回りに傾いているため反時計回りに補正
  2) 確定座標(rooms_verified.VERIFIED)をエディタ用 rooms.json に変換
  3) build_editor.py でエディタHTMLを生成し、タイトルを扇町2号に書き換える

  python3 build_ogimachi_editor.py
出力:
  intermediate/ogimachi_<階>_bg.png / .b64
  ogimachi_<階>_rooms.json
  editor_ogimachi_<階>.html   ← Chromeで開いて点群に合わせて編集
"""
import base64
import json
import subprocess
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from load_glb import load_points
from rooms_verified import VERIFIED

BASE = Path(__file__).parent
MID = BASE / "intermediate"
MID.mkdir(exist_ok=True)

GLB = {"1f": BASE / "glb/ogimachi_1f.glb", "2f": BASE / "glb/ogimachi_2f.glb"}

# 各階の点群回転補正角(度, 正=反時計回り)。投影分散最大化で求めた値
ROTATE_DEG = {"1f": -10.5, "2f": 5.1}
# 東西ミラー: 下から撮影のため反転要(両階とも同じScaniverse)
FLIP_LR = {"1f": True, "2f": True}
# 下敷きの高さスライス帯(m)。Noneなら全点(2Fは南壁が低く薄いため全点投影)
SLICE = {"1f": (0.9, 1.3), "2f": None}


def room_type(name):
    if "和室" in name:
        return "和室"
    if "洋室" in name:
        return "洋室"
    if any(k in name for k in ["風呂", "トイレ", "洗面", "台所", "キッチン", "浴", "脱衣"]):
        return "水回り"
    if "玄関" in name:
        return "玄関"
    if any(k in name for k in ["廊下", "階段"]):
        return "廊下"
    if any(k in name for k in ["押入", "物置", "収納", "クローゼット"]):
        return "収納"
    if "床の間" in name:
        return "床の間"
    if "縁側" in name:
        return "縁側"
    return "未定"


def make_bg(floor):
    """点群を真上から見た下敷きPNGを生成し、base64も書き出す。返り値=点群bbox実寸(m)。"""
    v, c = load_points(GLB[floor])
    # 傾き補正: 回転行列をXY平面に適用
    rot_deg = ROTATE_DEG.get(floor, 0.0)
    if abs(rot_deg) > 0.01:
        rad = np.radians(rot_deg)
        cos_r, sin_r = np.cos(rad), np.sin(rad)
        R = np.array([[cos_r, -sin_r], [sin_r, cos_r]])
        v = v.copy()
        v[:, :2] = (R @ v[:, :2].T).T
    # 高さスライスで壁を出す。Noneまたは点が薄ければ全点
    sl = SLICE.get(floor, (0.9, 1.3))
    if sl is None:
        pts, col = v, c
    else:
        zf = v[:, 2] - v[:, 2].min()
        m = (zf > sl[0]) & (zf < sl[1])
        pts, col = (v[m], c[m]) if m.sum() > 2000 and len(c) == len(v) else (v, c)
    x, y = pts[:, 0], pts[:, 1]
    # 外れ値(ノイズ・屋外点)を除いて建物bboxを決める
    x0, x1 = np.percentile(x, [1, 99])
    y0, y1 = np.percentile(y, [1, 99])
    sel = (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1)

    # 下から撮影のため両軸反転＋後段で水平ミラー(FLIP_LR)
    xs, ys = -x[sel], -y[sel]
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    rgb = col[sel][:, :3] / 255.0 if len(col) == len(pts) else None

    fig, ax = plt.subplots(figsize=(8, 8 * (y1 - y0) / (x1 - x0)))
    py = -ys
    if sl is None:
        # 全点: 点密度(壁=床〜天井まで垂直に積もる=高密度)で壁を強調
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
    png = MID / f"ogimachi_{floor}_bg.png"
    fig.savefig(png, dpi=180, facecolor="white", bbox_inches="tight", pad_inches=0)
    plt.close(fig)
    # 東西反転: 階別に水平ミラー(1Fのみ)
    if FLIP_LR.get(floor, False):
        from PIL import Image as PilImage
        img = PilImage.open(png)
        img = img.transpose(PilImage.FLIP_LEFT_RIGHT)
        img.save(png)
    (MID / f"ogimachi_{floor}_bg.b64").write_text(
        base64.b64encode(png.read_bytes()).decode())
    return x1 - x0, y1 - y0


def make_rooms(floor):
    p = BASE / f"ogimachi_{floor}_rooms.json"
    if p.exists():
        # 既に編集済みJSONがあれば上書きしない(エディタ保存を保護)
        print(f"[{floor}] 既存 {p.name} を保持(初期化したい場合は削除して再実行)")
        return p
    spec = VERIFIED[floor]
    rooms = [{"name": n, "x": round(x, 2), "y": round(y, 2),
              "w": round(w, 2), "h": round(h, 2), "type": room_type(n)}
             for (n, x, y, w, h, _col) in spec["rooms"]]
    data = {
        "title": f"扇町2号 {floor.upper()} 平面図",
        "bldg_w": round(spec["bldg_w"], 2),
        "bldg_h": round(spec["bldg_h"], 2),
        "x_dims": [round(d, 2) for d in spec["x_dims_top"]],
        "y_dims": [round(d, 2) for d in spec["y_dims_left"]],
        "rooms": rooms,
    }
    p = BASE / f"ogimachi_{floor}_rooms.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    return p


def main():
    for fl in ["1f", "2f"]:
        bw, bh = make_bg(fl)
        rp = make_rooms(fl)
        vb = VERIFIED[fl]
        print(f"[{fl}] 点群bbox {bw:.2f}×{bh:.2f}m / 確定建物 "
              f"{vb['bldg_w']:.2f}×{vb['bldg_h']:.2f}m → {rp.name}")
        out_html = f"editor_ogimachi_{fl}.html"
        subprocess.run(
            ["python3", "build_editor.py", rp.name,
             f"intermediate/ogimachi_{fl}_bg.b64", out_html],
            cwd=BASE, check=True)
        # タイトルを「成合町3号」→「扇町2号」に書き換え
        p = BASE / out_html
        html = p.read_text()
        html = html.replace("成合町3号 間取りエディタ", f"扇町2号 {fl.upper()} 間取りエディタ")
        html = html.replace(">成合町3号 間取りエディタ<", f">扇町2号 {fl.upper()} 間取りエディタ<")
        p.write_text(html)
    print("\n完了: editor_ogimachi_1f.html / editor_ogimachi_2f.html をChromeで開いてください")


if __name__ == "__main__":
    main()
