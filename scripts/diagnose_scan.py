# -*- coding: utf-8 -*-
"""
スキャン品質の自動診断(撮り直し判定)。歪んだスキャンの上に工程を積む無駄を防ぐ。

■ モード1: トレース前(スキャン直後の撮り直し判定) — glbだけで動く
  python3 diagnose_scan.py <full.glb>
  床/天井/層間をZヒストグラムで自動検出し、腰高スライスの壁線の「にじみ幅」を測る。
  壁にじみ(=壁1枚が点群上で何cmの帯になっているか)が太いほどドリフト(歪み)が大きい。
  目安: 中央値 ≤12cm 良好 / 12〜18cm 注意 / >18cm 撮り直し推奨

■ モード2: トレース後(壁ごとの精密診断) — 物件プロジェクトフォルダで実行
  python3 diagnose_scan.py <full.glb> <rooms.json> [--floor-z 0.0] [--label 1f]
  トレース壁線 vs 点群壁の ズレ/傾き/反り/散らばり を壁ごとに定量化。
  反り>5cm・散らばり>10cmの壁には⚠を付ける(その壁の寸法は要現地確認)。

レポート画像は intermediate/scan_quality_<label>.jpg に保存。
"""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from load_glb import load_points
from extract_elevation import normalize_floor
from build_shared_editors import detect_yaw, rotate_xy

FP = font_manager.FontProperties(fname="/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc")
MID = Path.cwd() / "intermediate"

# 判定しきい値(扇町2号の実測=にじみ約16cm・反り中央2.3cmを「注意」水準として較正)
BLUR_GOOD, BLUR_WARN = 0.12, 0.18       # 壁にじみ(m)
BOW_WARN, SPREAD_WARN = 0.05, 0.10      # 壁ごとの反り/散らばり(m)


def _verdict_short(blur):
    if blur <= BLUR_GOOD:
        return "良好"
    if blur <= BLUR_WARN:
        return "注意"
    return "撮り直し推奨"


def _verdict(blur):
    if blur <= BLUR_GOOD:
        return "✅ 良好(このまま工程を進めてよい)"
    if blur <= BLUR_WARN:
        return "⚠️ 注意(図面化は可能だが寸法±5cm程度の誤差を想定。要現地確認を明記)"
    return "❌ 撮り直し推奨(ドリフト大。ループを閉じる・ゆっくり・明るくして再スキャン)"


def wall_blur(xy, axis_bins=0.02):
    """腰高スライスの行/列ヒストグラムから壁ピークの幅(FWHM)を測り、
    壁にじみの中央値(m)とピーク一覧を返す。"""
    widths = []
    for ax in (0, 1):
        vals = xy[:, ax]
        lo, hi = np.percentile(vals, [0.5, 99.5])
        nb = max(int((hi - lo) / axis_bins), 50)
        h, e = np.histogram(vals, bins=nb, range=(lo, hi))
        thr = np.percentile(h, 90)
        i = 0
        while i < nb:
            if h[i] >= thr:                       # ピーク帯の開始
                j = i
                while j < nb and h[j] >= thr * 0.5:   # 半値幅で測る
                    j += 1
                widths.append((j - i) * axis_bins)
                i = j
            else:
                i += 1
    widths = [w for w in widths if w >= axis_bins * 2]
    return (float(np.median(widths)) if widths else np.nan), widths


def mode1_pretrace(glb):
    v, _ = load_points(glb)
    v, fz, ch = normalize_floor(v)
    z = v[:, 2]
    span = np.percentile(z, 99.5) - np.percentile(z, 0.5)
    print(f"=== モード1: トレース前診断 ===\n点数 {len(v):,} / 高さ範囲 {span:.1f}m (床基準z=0)")

    # 層構造: 2階通しなら層間(谷)を検出
    bands = [("1F", 0.9, 1.6)]
    if span > 4.2:
        h, e = np.histogram(z[(z > 1.8) & (z < 3.6)], bins=36)
        slab = float((e[np.argmin(h)] + e[np.argmin(h) + 1]) / 2)
        bands.append(("2F", slab + 0.9, slab + 1.6))
        print(f"2階通しスキャンと判定 → 層間 z≒{slab:.2f}m")

    report = []
    for name, zlo, zhi in bands:
        m = (z > zlo) & (z < zhi)
        xy = v[m, :2]
        if m.sum() < 5000:
            print(f"{name}: 点不足({m.sum()})で判定不能")
            continue
        center = xy.mean(axis=0)
        yaw = detect_yaw(xy, center)
        xyr = rotate_xy(xy, center, yaw)
        blur, widths = wall_blur(xyr)
        report.append((name, m.sum(), yaw, blur, len(widths)))
        print(f"{name}: 腰高{m.sum():,}点 傾き{yaw:+.2f}° 壁にじみ中央値 {blur*100:.1f}cm "
              f"(壁ピーク{len(widths)}本)")
        print(f"  → {_verdict(blur)}")

    # レポート画像(帯ごとの密度マップ+判定)
    fig, axes = plt.subplots(1, len(bands), figsize=(7 * len(bands), 7), squeeze=False)
    for ax, (name, zlo, zhi) in zip(axes.flat, bands):
        m = (z > zlo) & (z < zhi)
        xy = v[m, :2]
        H, xe, ye = np.histogram2d(xy[:, 0], xy[:, 1], bins=300)
        ax.imshow(np.log1p(H).T, origin="lower", cmap="Greys",
                  extent=[xe[0], xe[-1], ye[0], ye[-1]], aspect="equal")
        rep = next((r for r in report if r[0] == name), None)
        sub = f"壁にじみ {rep[3]*100:.1f}cm — {_verdict_short(rep[3])}" if rep else "判定不能"
        ax.set_title(f"{name} 腰高スライス\n{sub}", fontproperties=FP, fontsize=11)
        ax.set_aspect("equal")
        ax.invert_yaxis()
    fig.suptitle("スキャン品質診断(トレース前) — 壁の帯が細いほど良質", fontproperties=FP, fontsize=13)
    MID.mkdir(exist_ok=True)
    out = MID / "scan_quality_pretrace.jpg"
    fig.tight_layout()
    fig.savefig(out, dpi=110, facecolor="white")
    plt.close(fig)
    print("レポート画像:", out)


def mode2_posttrace(glb, rooms_json, floor_z=0.0, label="1f"):
    from finish_shared import cloud_new_frame, _find
    from finish_through import registered_cloud
    d = json.loads(Path(rooms_json).read_text())
    if _find("shared_frame.json").exists():
        v, _ = cloud_new_frame(glb)
    else:
        v, _ = registered_cloud(glb)
    m = (v[:, 2] > floor_z + 0.85) & (v[:, 2] < floor_z + 1.7)
    v = v[m]
    print(f"=== モード2: トレース後診断({label}) === 腰高{len(v):,}点")

    rows = []
    for r in d["rooms"]:
        x, y, w, h = r["x"], r["y"], r["w"], r["h"]
        for ori, c0, s0, s1, en in [("h", y, x, x + w, "北"), ("h", y + h, x, x + w, "南"),
                                     ("v", x, y, y + h, "西"), ("v", x + w, y, y + h, "東")]:
            L = s1 - s0
            if L < 1.2:
                continue
            if ori == "h":
                sel = (np.abs(v[:, 1] - c0) < 0.12) & (v[:, 0] > s0 + 0.15) & (v[:, 0] < s1 - 0.15)
                s, p = v[sel, 0], v[sel, 1]
            else:
                sel = (np.abs(v[:, 0] - c0) < 0.12) & (v[:, 1] > s0 + 0.15) & (v[:, 1] < s1 - 0.15)
                s, p = v[sel, 1], v[sel, 0]
            if len(s) < 120:
                continue
            t = (s - s0) / L
            th = [np.median(p[t < 1/3]) if (t < 1/3).sum() > 20 else np.nan,
                  np.median(p[(t >= 1/3) & (t < 2/3)]) if ((t >= 1/3) & (t < 2/3)).sum() > 20 else np.nan,
                  np.median(p[t >= 2/3]) if (t >= 2/3).sum() > 20 else np.nan]
            if any(np.isnan(th)):
                continue
            offset = float(np.median(p) - c0)
            tilt = float(np.degrees(np.arctan2(th[2] - th[0], L * 2/3)))
            bow = float(th[1] - (th[0] + th[2]) / 2)
            spread = float(np.percentile(np.abs(p - np.median(p)), 80))
            rows.append(dict(room=r["name"], edge=en, L=L, n=len(s),
                             offset=offset, tilt=tilt, bow=bow, spread=spread,
                             warn=(abs(bow) > BOW_WARN or spread > SPREAD_WARN)))
    if not rows:
        print("判定できる壁がありません")
        return

    rows.sort(key=lambda r: -abs(r["bow"]))
    print(f"{'':2}{'部屋':<8}{'辺':<3}{'ズレcm':>7}{'傾き°':>7}{'反りcm':>7}{'散らばりcm':>9}")
    for r in rows:
        mk = "⚠" if r["warn"] else " "
        print(f"{mk:2}{r['room']:<8}{r['edge']:<3}{r['offset']*100:>7.1f}{r['tilt']:>7.2f}"
              f"{r['bow']*100:>7.1f}{r['spread']*100:>9.1f}")
    a = np.array([[r["offset"], r["bow"], r["spread"]] for r in rows])
    nwarn = sum(r["warn"] for r in rows)
    print(f"\n壁{len(rows)}枚: |ズレ|中央 {np.median(np.abs(a[:,0]))*100:.1f}cm / "
          f"|反り|中央 {np.median(np.abs(a[:,1]))*100:.1f}cm / 散らばり中央 {np.median(a[:,2])*100:.1f}cm")
    print(f"⚠の壁(反り>{BOW_WARN*100:.0f}cm or 散らばり>{SPREAD_WARN*100:.0f}cm): {nwarn}枚 → 寸法は要現地確認")

    # レポート画像: 反りワースト棒グラフ
    top = rows[:12]
    fig, ax = plt.subplots(figsize=(10, 0.5 * len(top) + 2))
    names = [f"{r['room']}({r['edge']})" for r in top][::-1]
    vals = [abs(r["bow"]) * 100 for r in top][::-1]
    cols = ["#d32f2f" if abs(r["bow"]) > BOW_WARN else "#888" for r in top][::-1]
    ax.barh(names, vals, color=cols)
    ax.axvline(BOW_WARN * 100, color="#d32f2f", ls="--", lw=1)
    ax.set_xlabel("壁の反り(cm) 赤=要現地確認", fontproperties=FP)
    for lab in ax.get_yticklabels():
        lab.set_fontproperties(FP)
    ax.set_title(f"スキャン品質診断({label}): 壁の反りワースト  ⚠{nwarn}/{len(rows)}枚",
                 fontproperties=FP, fontsize=12)
    MID.mkdir(exist_ok=True)
    out = MID / f"scan_quality_{label}.jpg"
    fig.tight_layout()
    fig.savefig(out, dpi=120, facecolor="white")
    plt.close(fig)
    print("レポート画像:", out)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {a.split("=")[0].lstrip("-"): a.split("=")[1] for a in sys.argv[1:] if "=" in a and a.startswith("--")}
    if len(args) == 1:
        mode1_pretrace(args[0])
    elif len(args) >= 2:
        mode2_posttrace(args[0], args[1],
                        floor_z=float(opts.get("floor-z", 0.0)),
                        label=opts.get("label", "1f"))
    else:
        print(__doc__)
