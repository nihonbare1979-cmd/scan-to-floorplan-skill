"""
通しスキャンの連続点群を、検証済み既存レイアウト(別スキャン由来)の座標系へ
剛体レジストレーション(flip4通り+並進, scale=1, 回転≒0)する。

手順:
  1. 既存1F部屋のエッジをラスタ化(ターゲット)
  2. 新スキャンの1F腰高スライスをラスタ化(ソース)
  3. flip 4通り×FFT相互相関で最良の並進を探索
  4. 検証用オーバーレイ画像を出力(目視確認)
  5. 採用変換を JSON で保存 → finish_through.py が点群全体に適用しランク/断面を描く

使い方:
  python3 register_through.py <full.glb> <1f_rooms.json>
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

FP = font_manager.FontProperties(fname="/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc")
BASE = Path(__file__).parent
MID = BASE / "intermediate"
MID.mkdir(exist_ok=True)
RES = 0.04
PAD = 2.0


def room_edges(rooms):
    segs = []
    for r in rooms:
        x, y, w, h = r["x"], r["y"], r["w"], r["h"]
        segs += [((x, y), (x + w, y)), ((x, y + h), (x + w, y + h)),
                 ((x, y), (x, y + h)), ((x + w, y), (x + w, y + h))]
    return segs


def rasterize_segments(segs, gx0, gy0, nx, ny):
    img = np.zeros((ny, nx), np.float32)
    for (a, b) in segs:
        n = max(2, int(np.hypot(b[0] - a[0], b[1] - a[1]) / (RES / 2)))
        xs = np.linspace(a[0], b[0], n)
        ys = np.linspace(a[1], b[1], n)
        ix = ((xs - gx0) / RES).astype(int)
        iy = ((ys - gy0) / RES).astype(int)
        ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
        img[iy[ok], ix[ok]] = 1.0
    return img


def rasterize_points(px, py, gx0, gy0, nx, ny):
    img = np.zeros((ny, nx), np.float32)
    ix = ((px - gx0) / RES).astype(int)
    iy = ((py - gy0) / RES).astype(int)
    ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
    np.add.at(img, (iy[ok], ix[ok]), 1.0)
    return (img > 0).astype(np.float32)


def gaussian_blur(img, sigma_px=2.0):
    # 簡易ガウシアン(分離可能)
    r = int(sigma_px * 3)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma_px) ** 2)
    k /= k.sum()
    out = np.apply_along_axis(lambda m: np.convolve(m, k, "same"), 0, img)
    out = np.apply_along_axis(lambda m: np.convolve(m, k, "same"), 1, out)
    return out


def fft_xcorr_shift(target, source):
    """sourceを動かしてtargetに最も重なるシフト(行,列)とスコアを返す。"""
    F = np.fft.rfft2(target)
    G = np.fft.rfft2(source[::-1, ::-1])     # 相関=畳み込み(反転)
    corr = np.fft.irfft2(F * G, s=target.shape)
    idx = np.unravel_index(np.argmax(corr), corr.shape)
    score = corr[idx]
    # 反転畳み込みのピーク位置 → シフト換算
    sy = idx[0] - (source.shape[0] - 1)
    sx = idx[1] - (source.shape[1] - 1)
    return sx, sy, score


def main():
    glb = sys.argv[1]
    rooms_path = sys.argv[2]
    rooms = json.loads(Path(rooms_path).read_text())["rooms"]
    bw = max(r["x"] + r["w"] for r in rooms)
    bh = max(r["y"] + r["h"] for r in rooms)

    # ターゲット(既存1F)キャンバス
    gx0, gy0 = -PAD, -PAD
    nx = int((bw + 2 * PAD) / RES)
    ny = int((bh + 2 * PAD) / RES)
    tgt = gaussian_blur(rasterize_segments(room_edges(rooms), gx0, gy0, nx, ny), 2.0)

    # ソース(新スキャン1F腰高)
    v, c = load_points(glb)
    v, fz, ch = normalize_floor(v)
    z = v[:, 2]
    m = (z > 0.9) & (z < 1.6)
    X = v[m, 0]
    Y = v[m, 1]

    best = None
    for sgx in (1, -1):
        for sgy in (1, -1):
            px = sgx * X
            py = sgy * Y
            # ソースをキャンバスへ: bbox-min を (0,0) 付近へ
            px2 = px - px.min()
            py2 = py - py.min()
            src = rasterize_points(px2, py2, gx0, gy0, nx, ny)
            sx, sy, score = fft_xcorr_shift(tgt, src)
            if best is None or score > best["score"]:
                best = dict(sgx=sgx, sgy=sgy, score=float(score),
                            pxmin=float(px.min()), pymin=float(py.min()),
                            sx_px=int(sx), sy_px=int(sy))
    # 採用変換: room_x = sgx*X - pxmin + gx0 + sx*RES  (px2=px-pxmin を gx0原点に置きsxシフト)
    # → room_x = sgx*X + (gx0 - pxmin + sx*RES)
    b = best
    b["off_x"] = gx0 - b["pxmin"] + b["sx_px"] * RES
    b["off_y"] = gy0 - b["pymin"] + b["sy_px"] * RES

    # ── 微調整: 壁ラスタ(blur)上で cloud→room のオーバーラップを最大化 ──
    def sample_score(ox, oy):
        rxv = b["sgx"] * X + ox
        ryv = b["sgy"] * Y + oy
        ix = ((rxv - gx0) / RES).astype(int)
        iy = ((ryv - gy0) / RES).astype(int)
        ok = (ix >= 0) & (ix < nx) & (iy >= 0) & (iy < ny)
        return float(tgt[iy[ok], ix[ok]].sum())

    base_ox, base_oy = b["off_x"], b["off_y"]
    bestf = (base_ox, base_oy, sample_score(base_ox, base_oy))
    for dox in np.arange(-0.5, 0.51, 0.04):
        for doy in np.arange(-0.5, 0.51, 0.04):
            s = sample_score(base_ox + dox, base_oy + doy)
            if s > bestf[2]:
                bestf = (base_ox + dox, base_oy + doy, s)
    b["off_x"], b["off_y"] = round(bestf[0], 3), round(bestf[1], 3)
    print("best flip sgx=%d sgy=%d  coarse_score=%.1f  refine_overlap=%.1f"
          % (b["sgx"], b["sgy"], b["score"], bestf[2]))
    print("offset_x=%.3f offset_y=%.3f (refined)" % (b["off_x"], b["off_y"]))

    def to_room(Xa, Ya):
        return b["sgx"] * Xa + b["off_x"], b["sgy"] * Ya + b["off_y"]

    # 検証オーバーレイ
    rx, ry = to_room(X, Y)
    fig, ax = plt.subplots(figsize=(8, 8 * bh / bw))
    ax.scatter(rx, ry, s=2, c="#3a7", alpha=0.35, marker=".", linewidths=0, label="新スキャン1F壁")
    for r in rooms:
        ax.add_patch(plt.Rectangle((r["x"], r["y"]), r["w"], r["h"],
                                   fill=False, ec="#c33", lw=1.2))
    ax.set_xlim(-PAD, bw + PAD); ax.set_ylim(bh + PAD, -PAD); ax.set_aspect("equal")
    ax.set_title("レジストレーション検証: 既存部屋(赤枠) vs 新スキャン1F壁(緑)", fontproperties=FP)
    ax.legend(prop=FP)
    fig.tight_layout(); fig.savefig(MID / "register_check.png", dpi=110, facecolor="white")
    plt.close(fig)

    (BASE / "through_transform.json").write_text(json.dumps(b, ensure_ascii=False, indent=2))
    print("保存: intermediate/register_check.png / through_transform.json")


if __name__ == "__main__":
    main()
