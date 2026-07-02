# -*- coding: utf-8 -*-
"""
ワンコマンド・パイプラインランナー(新規物件のトレース前準備を全自動化)。

  python3 run_pipeline.py <input.usdz|input.glb> <物件名> [--slab=Z] [--yaw=deg] [--flip]

やること(A→A2→B→C→D相当):
  1. projects/<物件名>/ を作成し glb/ へ変換(USDZならBlenderヘッドレス)or複製
  2. スキャン品質診断(壁にじみ→撮り直し判定)               → intermediate/scan_quality_pretrace.jpg
  3. 姿勢診断: Zヒストグラム+3方向正投影                    → intermediate/diag_zhist.jpg / diag_3views.jpg
  4. 層間(2F床)の自動検出(--slabで上書き可)
  5. 統合立面図の先出し(南/東・床/層間/天井ライン入り)      → intermediate/pre_section_south.jpg / _east.jpg
  6. エディタ生成(build_through_editors)                    → editor_through_1f.html / 2f.html
  7. 決定パラメータを project.json に台帳化

終わったら:
  - 診断画像をReadで目視確認(❌撮り直し推奨ならユーザーに提案して止まる判断)
  - python3 ../../serve_editor.py projects/<物件名> 8790 でトレース開始

上書きフラグ: --slab=2.87(層間z) --yaw=-1.0(反時計回り度) --flip(東西反転)
"""
import json
import subprocess
import sys
from datetime import datetime
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

FP = font_manager.FontProperties(fname="/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc")
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


def step(msg):
    print(f"\n━━ {msg}")


def convert_or_copy(src, proj, name):
    dst = proj / "glb" / f"{name}_full.glb"
    if dst.exists():
        print(f"既存GLBを使用: {dst.name}")
        return dst
    if src.suffix.lower() == ".usdz":
        subprocess.run([BLENDER, "--background", "--python",
                        str(BASE / "convert_usdz_glb.py"), "--", str(src), str(dst)],
                       check=True, capture_output=True, text=True)
        print(f"USDZ→GLB変換: {dst.name}")
    else:
        import shutil
        shutil.copy(src, dst)
        print(f"GLBを複製: {dst.name}")
    return dst


def detect_slab(z):
    """2階通しなら層間(密度の谷)を返す。単階なら None。"""
    span = np.percentile(z, 99.5) - np.percentile(z, 0.5)
    if span <= 4.2:
        return None
    h, e = np.histogram(z[(z > 1.8) & (z < 3.6)], bins=36)
    return float((e[np.argmin(h)] + e[np.argmin(h) + 1]) / 2)


def diag_zhist(z, slab, out):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(z, bins=120, color="#456")
    ax.axvline(0, color="#c33", ls="--", lw=1.2)
    ax.text(0, ax.get_ylim()[1] * 0.95, " 1F床=0", color="#c33", fontproperties=FP)
    if slab:
        ax.axvline(slab, color="#e80", ls="--", lw=1.2)
        ax.text(slab, ax.get_ylim()[1] * 0.85, f" 層間≒{slab:.2f}m", color="#e80", fontproperties=FP)
    ax.set_xlabel("高さz (m)", fontproperties=FP)
    ax.set_title("Zヒストグラム(谷=層間) — 2帯あれば2階通し", fontproperties=FP)
    fig.tight_layout(); fig.savefig(out, dpi=110, facecolor="white"); plt.close(fig)


def diag_3views(v, out):
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    for ax, (i, j, ttl) in zip(axes, [(0, 1, "真上(XY)"), (0, 2, "南から(XZ)"), (1, 2, "東から(YZ)")]):
        idx = np.random.default_rng(0).choice(len(v), min(60000, len(v)), replace=False)
        ax.scatter(v[idx, i], v[idx, j], s=0.5, c="#345", linewidths=0)
        ax.set_aspect("equal")
        ax.set_title(ttl, fontproperties=FP)
        if j == 1:
            ax.invert_yaxis()
    fig.suptitle("3方向正投影 — Z=上か/倒れ・上下逆がないか目視確認", fontproperties=FP, fontsize=13)
    fig.tight_layout(); fig.savefig(out, dpi=110, facecolor="white"); plt.close(fig)


def pre_sections(v, c, slab, proj):
    rgb = c[:, :3] / 255.0
    zmax = float(np.percentile(v[:, 2], 99.5)) + 0.2
    m = (v[:, 2] > -0.2) & (v[:, 2] < zmax)
    for direction, col, lab in [("south", 0, "東西方向 (m)"), ("east", 1, "南北方向 (m)")]:
        hor = v[m, col]
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.scatter(hor, v[m, 2], s=1.0, c=rgb[m], marker=".", linewidths=0)
        lines = [(0, "1F床 GL=0")] + ([(slab, f"層間 ≒{slab:.2f}m")] if slab else []) \
              + [(zmax - 0.2, f"天井 ≒{zmax-0.2:.1f}m")]
        for zz, t in lines:
            ax.axhline(zz, color="#c05028", lw=1.0, ls="--")
            ax.text(hor.min(), zz + 0.05, t, color="#c05028", fontsize=10, fontproperties=FP)
        ax.set_aspect("equal"); ax.set_xlabel(lab, fontproperties=FP)
        ax.set_ylabel("高さ (m)", fontproperties=FP)
        ax.set_title(f"統合立面図(先出し・{'南' if direction=='south' else '東'}から) ※高さ=実測・叩き台",
                     fontproperties=FP, fontsize=13)
        out = proj / "intermediate" / f"pre_section_{direction}.jpg"
        fig.tight_layout(); fig.savefig(out, dpi=120, facecolor="white"); plt.close(fig)
        print(f"  立面先出し: {out.name}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {a.lstrip("-").split("=")[0]: (a.split("=")[1] if "=" in a else True)
            for a in sys.argv[1:] if a.startswith("--")}
    if len(args) < 2:
        print(__doc__); sys.exit(1)
    src, name = Path(args[0]).expanduser().resolve(), args[1]
    if not src.exists():
        print(f"入力が見つかりません: {src}")
        sys.exit(1)
    proj = BASE / "projects" / name
    for d in ("glb", "intermediate", "output"):
        (proj / d).mkdir(parents=True, exist_ok=True)
    import os
    os.chdir(proj)   # 以降の全出力は物件フォルダ基準
    print(f"物件フォルダ: {proj}")

    step("1/6 GLB準備")
    glb = convert_or_copy(src, proj, name)

    step("2/6 スキャン品質診断(撮り直し判定)")
    r = subprocess.run(["python3", str(BASE / "diagnose_scan.py"), str(glb)],
                       capture_output=True, text=True)
    print(r.stdout.strip())
    retake = "撮り直し推奨" in r.stdout

    step("3/6 姿勢診断(Zヒスト・3方向正投影)")
    v, c = load_points(glb)
    v, floor_z_raw, ceil_h = normalize_floor(v)
    slab = float(opts["slab"]) if "slab" in opts else detect_slab(v[:, 2])
    diag_zhist(v[:, 2], slab, proj / "intermediate" / "diag_zhist.jpg")
    diag_3views(v, proj / "intermediate" / "diag_3views.jpg")
    print(f"床z(生)={floor_z_raw:.3f} 天井高≒{ceil_h:.2f}m 層間={'%.2f' % slab if slab else '単階(検出なし)'}")

    step("4/6 統合立面図の先出し")
    pre_sections(v, c, slab, proj)

    step("5/6 エディタ生成")
    if slab:
        yaw = opts.get("yaw", "0")
        cmd = ["python3", str(BASE / "build_through_editors.py"), str(glb),
               str(floor_z_raw), str(slab), str(yaw)]
        if opts.get("flip"):
            cmd.append("true")
        r2 = subprocess.run(cmd, cwd=proj, capture_output=True, text=True)
        print(r2.stdout.strip() or r2.stderr.strip()[-500:])
        editors = sorted(p.name for p in proj.glob("editor_through_*.html"))
    else:
        print("単階スキャンのため通し用エディタは生成せず(build_property_editor.pyを手動で)")
        editors = []

    step("6/6 パラメータ台帳(project.json)")
    manifest = {"name": name, "source": str(src), "glb": str(glb.relative_to(proj)),
                "floor_z_raw": round(floor_z_raw, 3), "ceil_h": round(ceil_h, 2),
                "slab_z": round(slab, 2) if slab else None,
                "yaw": float(opts.get("yaw", 0)), "flip": bool(opts.get("flip", False)),
                "retake_recommended": retake,
                "created": datetime.now().strftime("%Y-%m-%d %H:%M")}
    (proj / "project.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps(manifest, ensure_ascii=False, indent=1))

    print("\n━━ 完了。次のアクション ━━")
    if retake:
        print("❌ 撮り直し推奨が出ています。トレース前にユーザーへ再スキャンを提案すること")
    print("1. 診断画像をReadで目視確認:")
    for f in ("scan_quality_pretrace.jpg", "diag_zhist.jpg", "diag_3views.jpg",
              "pre_section_south.jpg", "pre_section_east.jpg"):
        print(f"   {proj / 'intermediate' / f}")
    if editors:
        print(f"2. トレース開始: python3 {BASE}/serve_editor.py {proj} 8790")
        for e in editors:
            print(f"   → http://localhost:8790/{e}")


if __name__ == "__main__":
    main()
