"""
1F/2Fをまたいで、近接する壁線を共通の1本へ吸着させる(階間の作図誤差を吸収)。
通しスキャンで両階が同一座標系にある前提。±tol以内のずれは「同一線」とみなす。

  python3 snap_cross_floor.py <1f.json> <2f.json> [tol_m]
既定 tol=0.10m(=10cm)。元ファイルは *_before_xsnap.json にバックアップ。
"""
import json
import sys
from pathlib import Path


def cluster(vals, tol):
    """近接値をまとめ 値→代表値(グループ平均)の辞書。
    グループ平均との距離で判定しチェーン暴走を防ぐ。"""
    s = sorted(set(round(v, 4) for v in vals))
    groups = [[s[0]]]
    for v in s[1:]:
        gmean = sum(groups[-1]) / len(groups[-1])
        if v - gmean < tol and v - groups[-1][-1] < tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    rep = {}
    for g in groups:
        m = round(sum(g) / len(g), 3)
        for v in g:
            rep[v] = m
    return rep


def edges(rooms):
    xs, ys = [], []
    for r in rooms:
        xs += [round(r["x"], 4), round(r["x"] + r["w"], 4)]
        ys += [round(r["y"], 4), round(r["y"] + r["h"], 4)]
    return xs, ys


def apply(rooms, xr, yr):
    moved = 0
    for r in rooms:
        x0, x1 = xr[round(r["x"], 4)], xr[round(r["x"] + r["w"], 4)]
        y0, y1 = yr[round(r["y"], 4)], yr[round(r["y"] + r["h"], 4)]
        if abs(x0 - r["x"]) > 1e-6 or abs(y0 - r["y"]) > 1e-6 \
           or abs((x1 - x0) - r["w"]) > 1e-6 or abs((y1 - y0) - r["h"]) > 1e-6:
            moved += 1
        r["x"], r["w"] = round(x0, 2), round(max(x1 - x0, 0.05), 2)
        r["y"], r["h"] = round(y0, 2), round(max(y1 - y0, 0.05), 2)
    return moved


def main():
    f1, f2 = sys.argv[1], sys.argv[2]
    tol = float(sys.argv[3]) if len(sys.argv) > 3 else 0.10
    d1, d2 = json.load(open(f1)), json.load(open(f2))
    # バックアップ
    for f, d in [(f1, d1), (f2, d2)]:
        bk = Path(f).with_name(Path(f).stem + "_before_xsnap.json")
        if not bk.exists():
            bk.write_text(json.dumps(d, ensure_ascii=False, indent=2))

    # 両階の辺をまとめてクラスタリング(=同一線判定を階間で共有)
    x1s, y1s = edges(d1["rooms"]); x2s, y2s = edges(d2["rooms"])
    xr = cluster(x1s + x2s, tol)
    yr = cluster(y1s + y2s, tol)

    m1 = apply(d1["rooms"], xr, yr)
    m2 = apply(d2["rooms"], xr, yr)
    for f, d in [(f1, d1), (f2, d2)]:
        json.dump(d, open(f, "w"), ensure_ascii=False, indent=2)
    nx, ny = len(set(xr.values())), len(set(yr.values()))
    print(f"階間スナップ完了(tol={tol*100:.0f}cm): 1F {m1}室補正 / 2F {m2}室補正")
    print(f"  共通壁線 縦{nx}本 横{ny}本")


if __name__ == "__main__":
    main()
