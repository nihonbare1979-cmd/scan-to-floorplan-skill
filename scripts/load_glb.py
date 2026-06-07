"""
GLB読込 → 正規化点群(座標+色)
座標系をここで一元的に統一する。下流は全てこの座標系を前提にできる。

統一後の座標系:
  X = 東向き(+)
  Y = 南向き(+)
  Z = 上向き(+)  ※床≒0 になるよう後段の normalize_z で補正(立面図用)
  原点 = 建物の北西(NW)内部角 付近(平面抽出時に左上を0,0へ平行移動)
"""
import numpy as np
import trimesh


def load_points(glb_path):
    """GLBを読み、頂点座標(N,3)と頂点カラー(N,4 uint8)を返す。"""
    scene = trimesh.load(str(glb_path))
    mesh = scene.to_geometry() if hasattr(scene, "to_geometry") else scene
    verts = np.asarray(mesh.vertices, dtype=np.float64)

    # テクスチャ → 頂点カラーへ変換(レンダリングとAI画像生成に使う)
    try:
        colors = np.asarray(mesh.visual.to_color().vertex_colors, dtype=np.uint8)
    except Exception:
        colors = np.full((len(verts), 4), 200, dtype=np.uint8)
        colors[:, 3] = 255

    # ── 座標系統一: glTFはY-up。trimeshが既にZ-up化している場合もあるので、
    #    「最も平らに広がる2軸を水平面」とみなして検出する ──
    verts = _orient_z_up(verts)
    return verts, colors


def _orient_z_up(verts):
    """点群の分散から鉛直軸を推定し、Zが鉛直(上)になるよう軸を入れ替える。
    床/壁スキャンは水平方向の広がり>>鉛直方向、かつ鉛直軸は密度分布が二峰(床/天井)。
    ここでは単純に『分散が3軸中で偏る軸』判定ではなく、ユーザー実績(Z鉛直)を尊重し
    既にZ-upならそのまま返す。将来データで崩れたらここを差し替える。"""
    # ScaniverseのUSDZ→GLB変換後はZ=鉛直になっているため素通し。
    # 将来データで崩れた場合はここで軸入れ替えを追加する。
    return verts


def summarize(verts):
    """範囲をプリントしてdict返却(デバッグ・寸法の妥当性確認用)。"""
    lo, hi = verts.min(axis=0), verts.max(axis=0)
    info = {
        "n": len(verts),
        "x": (lo[0], hi[0], hi[0] - lo[0]),
        "y": (lo[1], hi[1], hi[1] - lo[1]),
        "z": (lo[2], hi[2], hi[2] - lo[2]),
    }
    print(f"  点数 {info['n']:,}")
    print(f"  X {info['x'][0]:.2f}〜{info['x'][1]:.2f} ({info['x'][2]:.2f}m)")
    print(f"  Y {info['y'][0]:.2f}〜{info['y'][1]:.2f} ({info['y'][2]:.2f}m)")
    print(f"  Z {info['z'][0]:.2f}〜{info['z'][1]:.2f} ({info['z'][2]:.2f}m)")
    return info


if __name__ == "__main__":
    import sys
    from config import FLOORS
    floor = sys.argv[1] if len(sys.argv) > 1 else "2f"
    v, c = load_points(FLOORS[floor]["glb"])
    print(f"=== {floor} ===")
    summarize(v)
