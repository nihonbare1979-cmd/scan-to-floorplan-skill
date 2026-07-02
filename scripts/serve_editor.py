# -*- coding: utf-8 -*-
"""
間取りエディタ用ローカルサーバ(保存直書き対応)。
物件プロジェクトフォルダを配信し、エディタの💾保存を POST /save/<name>.json で
受けて同フォルダに直接書き込む。Chromeのダウンロード連番・保存先迷子の罠を根絶する。

使い方:
  python3 serve_editor.py <物件プロジェクトフォルダ> [port]
  例: python3 serve_editor.py projects/ogimachi2 8790
→ Chromeで http://localhost:8790/editor_shared_1f.html を開いてトレース→💾保存

保存時の安全策:
  - 上書き前に <name>_bak_YYYYmmdd-HHMMSS.json へ自動バックアップ
  - JSONとして解釈できないボディは拒否(400)
  - パス操作(../等)は拒否
"""
import json
import shutil
import sys
from datetime import datetime
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class EditorHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        root = Path(self.directory).resolve()
        if not self.path.startswith("/save/"):
            self.send_error(404)
            return
        name = Path(self.path[len("/save/"):]).name   # パス操作を除去
        if not name.endswith(".json") or "_bak_" in name:
            self.send_error(400, "invalid name")
            return
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0 or n > 10_000_000:
            self.send_error(400, "bad length")
            return
        body = self.rfile.read(n)
        try:
            d = json.loads(body)
            assert isinstance(d.get("rooms"), list)
        except Exception:
            self.send_error(400, "not a rooms json")
            return
        dst = root / name
        if dst.exists():
            bak = root / f"{dst.stem}_bak_{datetime.now():%Y%m%d-%H%M%S}.json"
            shutil.copy(dst, bak)
        dst.write_bytes(body)
        msg = f"{name} (部屋{len(d['rooms'])}・開口{len(d.get('openings', []))})"
        print(f"  保存: {dst}  {msg}")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg.encode())


def main():
    proj = Path(sys.argv[1]).resolve()
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8790
    if not proj.is_dir():
        print(f"フォルダがありません: {proj}")
        sys.exit(1)
    handler = partial(EditorHandler, directory=str(proj))
    srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"配信中: http://localhost:{port}/  ← {proj}")
    for f in sorted(proj.glob("editor_*.html")):
        print(f"  エディタ: http://localhost:{port}/{f.name}")
    print("💾保存はこのフォルダへ直接書き込まれます(旧版は *_bak_日時.json に退避)。Ctrl+Cで停止")
    srv.serve_forever()


if __name__ == "__main__":
    main()
