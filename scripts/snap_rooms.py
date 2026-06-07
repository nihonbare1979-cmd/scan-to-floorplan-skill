"""
部屋の辺を共通の壁線に吸着させて整列する(隙間・重なり解消)。
  python3 snap_rooms.py <in.json> [out.json] [tol_m]
近接する辺(既定0.12m以内)を1本の壁線にまとめ、各部屋のx/y/w/hを丸める。
"""
import json
import sys

inp = sys.argv[1]
outp = sys.argv[2] if len(sys.argv) > 2 else inp
tol = float(sys.argv[3]) if len(sys.argv) > 3 else 0.12

d = json.load(open(inp))
rooms = d["rooms"]


def cluster(vals, tol):
    """近接値を1グループにまとめ、各値→代表値(グループ平均)の辞書を返す。"""
    s = sorted(set(vals))
    groups = [[s[0]]]
    for v in s[1:]:
        if v - groups[-1][-1] < tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    rep = {}
    for g in groups:
        m = round(sum(g) / len(g), 3)
        for v in g:
            rep[v] = m
    return rep


xs, ys = [], []
for r in rooms:
    xs += [r["x"], r["x"] + r["w"]]
    ys += [r["y"], r["y"] + r["h"]]
xr = cluster(xs, tol)
yr = cluster(ys, tol)

moved = 0
for r in rooms:
    nx0, nx1 = xr[r["x"]], xr[r["x"] + r["w"]]
    ny0, ny1 = yr[r["y"]], yr[r["y"] + r["h"]]
    if (abs(nx0 - r["x"]) > 1e-6 or abs(ny0 - r["y"]) > 1e-6
            or abs((nx1 - nx0) - r["w"]) > 1e-6 or abs((ny1 - ny0) - r["h"]) > 1e-6):
        moved += 1
    r["x"], r["w"] = round(nx0, 2), round(nx1 - nx0, 2)
    r["y"], r["h"] = round(ny0, 2), round(ny1 - ny0, 2)

d["x_dims"] = sorted(set(xr.values()))
d["y_dims"] = sorted(set(yr.values()))
json.dump(d, open(outp, "w"), ensure_ascii=False, indent=2)
print(f"整列完了: {len(rooms)}室中 {moved}室を補正 / 壁線 縦{len(set(xr.values()))}本 横{len(set(yr.values()))}本")
