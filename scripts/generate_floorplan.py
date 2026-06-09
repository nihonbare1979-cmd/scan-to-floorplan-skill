"""
平面図ジェネレータ(rooms.json → 寸法入り平面図JPG)
  python3 generate_floorplan.py <rooms.json> [出力先.jpg]
出力先を省略するとタイトルから自動命名。
"""
import json
import sys
from pathlib import Path
from draw_plan import draw_plan

TYPE_COLOR = {
    "水回り": (215, 235, 240), "和室": (255, 245, 220), "洋室": (232, 224, 240),
    "玄関": (250, 240, 215), "廊下": (242, 242, 232), "収納": (228, 216, 200),
    "床の間": (252, 232, 208), "縁側": (236, 228, 206), "出窓": (207, 230, 200),
    "屋外": (245, 245, 245), "未定": (225, 225, 225),
}
# type=未定 のとき名前から色を推定する補助
NAME_HINT = {
    "和室": "和室", "洋室": "洋室", "書斎": "洋室", "風呂": "水回り", "浴": "水回り",
    "洗面": "水回り", "トイレ": "水回り", "便所": "水回り", "キッチン": "水回り",
    "台所": "水回り", "玄関": "玄関", "廊下": "廊下", "階段": "廊下",
    "押入": "収納", "納戸": "収納", "床の間": "床の間", "縁側": "縁側",
    "出窓": "出窓",
}


def _color(r):
    t = r.get("type", "未定")
    if t == "未定":
        for key, tt in NAME_HINT.items():
            if key in r["name"]:
                return TYPE_COLOR[tt]
    return TYPE_COLOR.get(t, (225, 225, 225))


def render(data, out_path):
    rooms = [(r["name"], r["x"], r["y"], r["w"], r["h"], _color(r)) for r in data["rooms"]]
    draw_plan(rooms, data["bldg_w"], data["bldg_h"],
              data.get("title", "平面図") + "（寸法=実測）", out_path,
              x_dims_top=data.get("x_dims"), y_dims_left=data.get("y_dims"),
              note="3Dスキャン実測ベース")


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "rooms.json"
    data = json.loads(Path(src).read_text())
    if len(sys.argv) > 2:
        out = sys.argv[2]
    else:
        out = "output/" + data.get("title", "平面図").replace(" ", "_") + ".jpg"
    render(data, out)
