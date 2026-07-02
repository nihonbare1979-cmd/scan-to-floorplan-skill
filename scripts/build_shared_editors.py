"""
通しスキャン専用: 1F/2Fを「実測スケールの同一座標系(北=上)」で下敷き化し、
各階の間取りエディタを生成する。位置合わせ・スケール・通し柱は不要(3Dで確定済み)。

特徴:
  - registered_cloud(部屋座標系・北=上)を使うので①の見慣れた向きに一致
  - 1F/2Fとも同一extent/同一原点 → トレース座標がそのまま通し柱判定に使える
  - 2Fの下敷きには1Fの壁を薄いグレーで重ねる(位置の目印)
  - 1Fエディタは信頼済み1Fレイアウトを出発点として読み込む(確認しながら微修正)

使い方:
  python3 build_shared_editors.py <full.glb> <信頼1f_rooms.json>
出力:
  intermediate/shared_1f_bg.png/.b64 , shared_2f_bg.png/.b64
  ogimachi_shared_1f_rooms.json (1F出発点) / ogimachi_shared_2f_rooms.json (空)
  editor_shared_1f.html / editor_shared_2f.html
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

from finish_through import registered_cloud

BASE = Path(__file__).parent
WORK = Path.cwd()                 # 物件プロジェクトフォルダで実行する想定(従来どおりscripts/直下でも可)
MID = WORK / "intermediate"
MID.mkdir(exist_ok=True)


def render_bg(out_png, bw, bh, main_xy, ref_xy=None, main_color="#1a1a1a"):
    """編集座標(x右・y下=南、原点0,0)で下敷きPNGを生成。
    画像は [0,bw]x[0,bh] をちょうど覆い、上端=y0=北。
    main_color: 主点群の色(1F=黒, 2F=青 など)。"""
    fig = plt.figure(figsize=(bw, bh))
    ax = fig.add_axes([0, 0, 1, 1])
    if ref_xy is not None:
        ax.scatter(ref_xy[0], ref_xy[1], s=5, c="#b8b8b8", marker=".", linewidths=0, alpha=0.55)
    ax.scatter(main_xy[0], main_xy[1], s=7, c=main_color, marker=".", linewidths=0, alpha=0.9)
    ax.set_xlim(0, bw); ax.set_ylim(bh, 0)     # y下=南
    ax.axis("off")
    fig.savefig(out_png, dpi=110, facecolor="white")
    plt.close(fig)


def detect_yaw(xy, center, lo=-5.0, hi=5.0, step=0.25):
    """壁が水平垂直になる回転角(CCW度)を、行/列ヒストグラムの分散最大で探索。"""
    best = (0.0, -1)
    p = xy - center
    for deg in np.arange(lo, hi + 1e-6, step):
        r = np.radians(deg)
        R = np.array([[np.cos(r), -np.sin(r)], [np.sin(r), np.cos(r)]])
        q = (R @ p.T).T
        hx, _ = np.histogram(q[:, 0], bins=200)
        hy, _ = np.histogram(q[:, 1], bins=200)
        s = hx.var() + hy.var()
        if s > best[1]:
            best = (float(deg), s)
    return best[0]


def rotate_xy(xy, center, deg):
    r = np.radians(deg)
    R = np.array([[np.cos(r), -np.sin(r)], [np.sin(r), np.cos(r)]])
    return (R @ (xy - center).T).T + center


def b64write(png):
    p = png.with_suffix(".b64")
    p.write_text(base64.b64encode(png.read_bytes()).decode())
    return p


def main():
    glb, rooms1_path = sys.argv[1], sys.argv[2]
    yaw_arg = sys.argv[3] if len(sys.argv) > 3 else "auto"   # CCW度 or "auto"
    v, c = registered_cloud(glb)               # 部屋座標系・床=0・北=上
    z = v[:, 2]
    m1 = (z > 0.85) & (z < 1.7)                 # 1F 腰高(密度UPで少し広め)
    m2 = (z > 3.2) & (z < 4.1)                  # 2F 腰高

    # ── 傾き補正: 1F壁が水平垂直になる角度を検出し、両階に同じ回転(整合維持) ──
    r1tmp = json.loads(Path(rooms1_path).read_text())["rooms"]
    cx = max(r["x"] + r["w"] for r in r1tmp) / 2.0
    cy = max(r["y"] + r["h"] for r in r1tmp) / 2.0
    center = np.array([cx, cy])
    if yaw_arg == "auto":
        yaw = detect_yaw(v[m1, :2], center)
    else:
        yaw = float(yaw_arg)
    v[:, :2] = rotate_xy(v[:, :2], center, yaw)
    print(f"傾き補正: {yaw:+.2f}° (CCW=反時計回り) を両階に適用")

    # 共有extent(両階の壁＋信頼1F範囲を内包)
    allx = np.concatenate([v[m1, 0], v[m2, 0]])
    ally = np.concatenate([v[m1, 1], v[m2, 1]])
    x0, x1 = np.percentile(allx, [1, 99])
    y0, y1 = np.percentile(ally, [1, 99])
    # 信頼1Fの範囲も含める
    r1 = json.loads(Path(rooms1_path).read_text())
    rx1 = max(r["x"] + r["w"] for r in r1["rooms"]); ry1 = max(r["y"] + r["h"] for r in r1["rooms"])
    x0 = min(x0, 0) - 0.3; y0 = min(y0, 0) - 0.3
    x1 = max(x1, rx1) + 0.3; y1 = max(y1, ry1) + 0.3
    ox, oy = -x0, -y0
    bw, bh = round(x1 - x0, 2), round(y1 - y0, 2)
    print(f"共有座標系: {bw}×{bh}m  原点シフト ox={ox:.2f} oy={oy:.2f}")
    # 仕上げ(finish_shared)が点群を同じ新フレームへ載せるための変換を保存
    (WORK / "shared_frame.json").write_text(json.dumps(
        {"yaw": yaw, "center": [float(center[0]), float(center[1])],
         "ox": float(ox), "oy": float(oy), "bw": bw, "bh": bh}, ensure_ascii=False, indent=2))

    def ed(xy):                                  # cloud→編集座標
        return xy[:, 0] + ox, xy[:, 1] + oy

    p1x, p1y = ed(v[m1]); p2x, p2y = ed(v[m2])
    # 1F下敷き(1Fのみ)
    bg1 = MID / "shared_1f_bg.png"
    render_bg(bg1, bw, bh, (p1x, p1y))
    # 2F下敷き(2F=青濃 + 1F=薄グレー目印)
    bg2 = MID / "shared_2f_bg.png"
    render_bg(bg2, bw, bh, (p2x, p2y), ref_xy=(p1x, p1y), main_color="#1565c0")
    b1, b2 = b64write(bg1), b64write(bg2)

    # 1F出発点 = 信頼1Fを「同じ傾き補正」で回してから新原点へシフト
    # (矩形は軸平行のまま中心だけ回す。小角なら誤差数cm)
    rooms1_shift = []
    for r in r1["rooms"]:
        ccx, ccy = r["x"] + r["w"] / 2.0, r["y"] + r["h"] / 2.0
        rc = rotate_xy(np.array([[ccx, ccy]]), center, yaw)[0]
        rr = dict(r)
        rr["x"] = round(rc[0] - r["w"] / 2.0 + ox, 2)
        rr["y"] = round(rc[1] - r["h"] / 2.0 + oy, 2)
        rooms1_shift.append(rr)
    j1 = WORK / "ogimachi_shared_1f_rooms.json"
    j1.write_text(json.dumps({"title": "扇町2号 1F 平面図(通し)", "bldg_w": bw, "bldg_h": bh,
                              "x_dims": [0, bw], "y_dims": [0, bh], "rooms": rooms1_shift},
                             ensure_ascii=False, indent=2))
    # 2Fは空(これからトレース)
    j2 = WORK / "ogimachi_shared_2f_rooms.json"
    j2.write_text(json.dumps({"title": "扇町2号 2F 平面図(通し)", "bldg_w": bw, "bldg_h": bh,
                              "x_dims": [0, bw], "y_dims": [0, bh], "rooms": []},
                             ensure_ascii=False, indent=2))

    for name, b in [("1f", b1), ("2f", b2)]:
        subprocess.run(["python3", str(BASE / "build_editor.py"),
                        f"ogimachi_shared_{name}_rooms.json", str(b.relative_to(WORK)),
                        f"editor_shared_{name}.html"], cwd=WORK, check=True)
    print("完了: editor_shared_1f.html / editor_shared_2f.html")
    print(f"  通し柱の基準: 1F/2Fとも同一座標系(原点シフト後)。床の間/押入の仕切り直上に2F南壁が来るか要確認")


if __name__ == "__main__":
    main()
