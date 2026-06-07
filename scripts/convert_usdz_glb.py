"""
USDZ → GLB 変換 (Blenderヘッドレス)。成合町と同一設定。
  Blender --background --python convert_usdz_glb.py -- <入力.usdz> <出力.glb>
ポイント: export_yup=False で Z-up を維持(下流のload_glbがZ-up前提)。
"""
import bpy
import sys

argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.usd_import(filepath=src)
bpy.ops.export_scene.gltf(
    filepath=dst,
    export_format="GLB",
    export_yup=False,        # Z-up維持
)
print(f"OK: {src} -> {dst}")
