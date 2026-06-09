"""
成果物ギャラリーHTML生成。フォルダ内の画像をbase64で1枚のHTMLに埋め込み、
Claudeのプレビューペインで1画面スクロール閲覧できるようにする。
(プレビューペインは生の.jpgは表示しにくいが、HTMLなら確実に描画できる)

使い方:
  python3 make_gallery.py <画像フォルダ> [出力.html] [タイトル]
キャプションは captions.json (任意, {ファイル名: 説明}) があれば使用。
"""
import base64
import json
import sys
from pathlib import Path

EXT = {".jpg", ".jpeg", ".png"}


def main():
    folder = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else folder / "gallery.html"
    title = sys.argv[3] if len(sys.argv) > 3 else folder.name

    cap_file = folder / "captions.json"
    caps = json.loads(cap_file.read_text()) if cap_file.exists() else {}

    imgs = sorted([p for p in folder.iterdir() if p.suffix.lower() in EXT])
    # まとめ画像があれば先頭へ
    imgs.sort(key=lambda p: (0 if "まとめ" in p.name or "ギャラリー" in p.name else 1, p.name))

    cards = []
    for p in imgs:
        if p == out:
            continue
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(p.read_bytes()).decode()
        cap = caps.get(p.name, p.stem)
        cards.append(f"""
  <figure>
    <figcaption><span class="cap">{cap}</span><span class="fn">{p.name}</span></figcaption>
    <img src="data:{mime};base64,{b64}" alt="{p.name}">
  </figure>""")

    html = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>{title}</title>
<style>
 body{{margin:0;background:#f4f3ef;font-family:"Hiragino Kaku Gothic ProN",sans-serif;color:#222}}
 header{{position:sticky;top:0;background:#2b2b2b;color:#fff;padding:14px 20px;font-size:18px;z-index:9;
   box-shadow:0 2px 6px rgba(0,0,0,.2)}}
 header small{{color:#bbb;font-weight:normal;font-size:13px;margin-left:10px}}
 main{{max-width:1000px;margin:0 auto;padding:20px}}
 figure{{margin:0 0 28px;background:#fff;border:1px solid #ddd;border-radius:10px;overflow:hidden;
   box-shadow:0 1px 4px rgba(0,0,0,.06)}}
 figcaption{{display:flex;justify-content:space-between;align-items:baseline;
   padding:11px 16px;background:#fafafa;border-bottom:1px solid #eee}}
 .cap{{font-size:15px;font-weight:600}}
 .fn{{font-size:11px;color:#999;font-family:monospace}}
 img{{display:block;width:100%;height:auto}}
 nav{{padding:4px 20px 16px;font-size:12px}}
 nav a{{color:#1565c0;margin-right:14px;text-decoration:none}}
</style></head><body>
<header>{title}<small>成果物ギャラリー（プレビュー用・全{len(cards)}点）</small></header>
<main>{''.join(cards)}</main>
</body></html>"""
    out.write_text(html)
    print(f"生成: {out}  ({len(cards)}点 / {len(html)//1024} KB)")


if __name__ == "__main__":
    main()
