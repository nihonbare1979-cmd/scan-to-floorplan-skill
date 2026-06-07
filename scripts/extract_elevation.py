"""
立面図／断面図モジュール（事実ベース）
点群を鉛直面に投影するだけ。寸法は描かず、実測の高さ目盛だけ添える。
床・天井が撮れた良質スキャンで有効。

normalize_floor() : 床を検出しZ=0へ
render_elevation(): 指定方向から見た立面(点群投影)を実測高さ目盛付きで描画
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def normalize_floor(verts):
    """床を検出しZ=0に補正。床=Zヒストグラムの最下側で最も鋭いピーク。
    返り値: (補正後verts, floor_z, ceil_z)"""
    z = verts[:, 2]
    h, e = np.histogram(z, bins=60)
    centers = (e[:-1] + e[1:]) / 2
    # 下半分で最大ピーク=床
    lo_half = centers < np.median(z)
    floor_z = centers[lo_half][np.argmax(h[lo_half])]
    # 上半分で最大ピーク=天井
    hi_half = centers > np.median(z)
    ceil_z = centers[hi_half][np.argmax(h[hi_half])]
    out = verts.copy()
    out[:, 2] -= floor_z
    return out, float(floor_z), float(ceil_z - floor_z)


def render_elevation(verts, colors, direction, out_path,
                     ceil_h=None, clip_top=3.2, dpi=130):
    """direction: 'south'(南から北を見る,XZ) / 'north' / 'east'(YZ) / 'west'
    床=0基準。天井より上(屋根・ノイズ)は clip_top でカット。"""
    v = verts.copy()
    # 床上〜clip_topの点だけ(屋根・スキャンノイズ除去)
    m = (v[:, 2] >= -0.1) & (v[:, 2] <= clip_top)
    v, c = v[m], colors[m]
    rgb = c[:, :3] / 255.0

    if direction in ("south", "north"):
        hor = v[:, 0]                      # 横軸=X
        if direction == "north":
            hor = -hor
        label = "東西方向 (m)"
    else:
        hor = v[:, 1]                      # 横軸=Y
        if direction == "west":
            hor = -hor
        label = "南北方向 (m)"

    width = hor.max() - hor.min()
    fig, ax = plt.subplots(figsize=(9, max(3.5, 9 * clip_top / max(width, 1))))
    ax.scatter(hor, v[:, 2], s=1.2, c=rgb, marker=".", linewidths=0)
    ax.axhline(0, color="#333", lw=1.5)             # 床ライン
    if ceil_h:
        ax.axhline(ceil_h, color="#c05028", lw=1.2, ls="--")
        ax.text(hor.min(), ceil_h + 0.05, f"天井高 ≒ {ceil_h*1000:.0f}mm",
                color="#c05028", fontsize=11,
                fontproperties=_jp_font())
    # 高さ目盛(0.5m刻み)
    for zz in np.arange(0, clip_top, 0.5):
        ax.axhline(zz, color="#ddd", lw=0.5, zorder=0)
    ax.set_aspect("equal")
    ax.set_ylim(-0.2, clip_top)
    ax.set_ylabel("高さ (m)", fontproperties=_jp_font())
    ax.set_xlabel(label, fontproperties=_jp_font())
    ax.set_title(f"立面図（{_dir_jp(direction)}から）  ※高さ=実測・要現場確認",
                 fontproperties=_jp_font())
    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi, facecolor="white")
    plt.close(fig)
    print(f"  保存: {out_path}")


def _jp_font():
    from matplotlib import font_manager
    for p in ["/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
              "/System/Library/Fonts/Hiragino Sans GB.ttc"]:
        try:
            return font_manager.FontProperties(fname=p)
        except Exception:
            continue
    return font_manager.FontProperties()


def _dir_jp(d):
    return {"south": "南", "north": "北", "east": "東", "west": "西"}.get(d, d)


if __name__ == "__main__":
    import sys
    from load_glb import load_points
    from config import MID_DIR
    glb = sys.argv[1] if len(sys.argv) > 1 else "glb/reference_01.glb"
    v, c = load_points(glb)
    v, fz, ch = normalize_floor(v)
    print(f"床Z={fz:.2f} 天井高≒{ch:.2f}m")
    MID_DIR.mkdir(exist_ok=True)
    for d in ("south", "east"):
        render_elevation(v, c, d, MID_DIR / f"ref_elev_{d}.png", ceil_h=ch)
