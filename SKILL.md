---
name: scan-to-floorplan
description: 3Dスキャン(Scaniverse USDZ)から寸法入り平面図・1F2F整合図・通し柱候補までを作る図面化パイプライン。物件の間取り図・構造叩き台を点群の実測値ベースで起こす。
trigger: 3Dスキャン・USDZ・GLB・間取り図・平面図・図面化・通し柱・構造叩き台・物件スキャンの図面化の依頼が来たとき、または /scan-to-floorplan と入力したとき
user_invocable: true
---

## 概要
iPhone等のScaniverseで撮った3Dスキャン(USDZ)を、寸法=点群実測の正確な平面図に起こすパイプライン。扇町2号で1F/2F両方を完成・確立した手順。事実ベースのみ(推定要素は載せない)。

## 前提
- スクリプト一式: `~/.claude/skills/scan-to-floorplan/scripts/`
- Blender 5.x: `/Applications/Blender.app/Contents/MacOS/Blender`
- 図面は必ず**Readツールでチャット内に直接表示**して見せる(プレビューペインは画像非表示)
- 完成図は `output/<物件名>/` に物件別収納
- 関連記憶: usdz-floorplan-pipeline / editor-json-save-pitfall

## ワークフロー(8ステップ)
以下は1フロアあたり。1F/2Fは別ファイルで撮影してもらう。

### ① USDZ → GLB 変換
ScaniverseでUSDZ書き出し(成合町・扇町で実証済みの形式)。`~/Downloads/`等から拾う。
```
Blender --background --python convert_usdz_glb.py -- <in.usdz> glb/<物件名>_1f.glb
```
`export_yup=False`でZ-up維持。旧データは`glb/_old_*/`へ退避。

### ② スキャン姿勢の診断(★最重要・決め打ち禁止)
スキャンは横倒し・傾き・上下逆で取り込まれることがある。必ず診断する:
1. **3方向の正投影**(生XY/生XZ/生YZ)を個別に高解像度で描き`Read`で目視 → どの面が真上ビュー(間取り)か特定。扇町1F=Z-up素直, 2F=床が88度倒れていた
2. 床が倒れている場合のみRANSAC床平面で水平化(床法線→Z)。ただし床と壁が同程度の大平面だと乱数で誤検出 → **目視優先**
3. **ヨー(水平面の傾き)**: 占有マップ(2Dヒストグラム)を-15〜15度回転し行/列投影の分散最大の角度を探索。扇町1F=-10.5度, 2F=5.1度
4. **東西/南北反転**: 下から撮影だと鏡像。両軸反転+PIL `FLIP_LEFT_RIGHT`で調整。扇町は両階とも反転要

### ③ 下敷き生成 + 間取りエディター
`build_property_editor.py`が「下敷き画像→エディタHTML」を一括生成。
- 引数: `<glb_path> <floor_name> [rotate_deg] [flip_lr] [slice_low] [slice_high]`
- パラメータ: 回転角(ヨー度) / 東西ミラー(true/false) / 高さスライス帯(省略で全点)
- **下敷き描画の使い分け**: 良質で壁が明瞭→腰高スライス(0.9-1.3m)+点描 / 壁が薄い・南側が低い→`SLICE=None`で全点+点密度ヒートマップ(壁は床〜天井まで垂直に積もる=高密度を黒く)
- 点サイズ`s=4`・濃いめ・dpi180で視認性確保

### ④ ブラウザで部屋トレース → 保存(落とし穴に注意)
Chromeでエディタを開き(`open -a "Google Chrome" editor_*.html`)、点群の壁に部屋ブロックをドラッグ/スナップ配置。`💾保存`でJSONダウンロード。
- **★Chrome連番の罠**: 既存同名があるとChromeは`名前 (1).json`を付ける。「保存した」と言われたら`ls -laht <名前>*.json`で**(1)(2)…と時系列を必ず確認**。中身も初期VERIFIED値と照合(取り違え事故の実績あり→editor-json-save-pitfall)

### ⑤ 清書
```
python3 generate_narukami.py <rooms.json> output/<物件名>/<物件>_1f_plan.jpg
```
Readで表示して確認。違和感あればエディタで再調整→再保存。

### ⑥ 1F × 2F 整合エディター
`build_align_editor.py`(引数: 1f.json 2f.json 2f_bg.b64 out.html dl_name title)。1F図面を色塗りの固定土台に、2Fを可動ブロックで重ねる。
- 1F土台=完成図と同じ配色(`COL[type]`) / 外周枠は1F基準(D1) / 2F点群は薄く(透過)・**2Fブロックのbboxに連動**(移動・縮尺追従)・描画順は図面の上
- 機能: 全体移動/縮尺・部屋追加/複製/削除・種別(色)変更・**undo(Ctrl+Z, 60手)**
- **階段を基準に合わせる**(1F2Fを貫くので最重要の手がかり)。保存は別名`*_aligned_rooms.json`(平面図用2Fを保護)

### ⑦ 微ズレ整列(snap)
```
python3 snap_rooms.py <aligned.json>
```
隣接する辺(0.12m以内)を共通の壁線に吸着 → 隙間・重なり解消。x_dims/y_dims(壁線)も再計算。元はバックアップ。

### ⑧ 通し柱候補
```
python3 structural_draft.py <1f.json> <2f_aligned.json> "<物件名>/<物件>" <タイトル>
```
1F壁と2F壁が重なる点を通し柱候補として`output/`にoverlay出力(黒=1F壁/赤=2F壁/青=候補)。
- **階別スキャンの制約**: 1F+2Fが別glbだと点群の垂直連続が無く、ランク(◎○△)と統合立面図(断面)は不可→スキップ。成合町のように1スキャンに2階分あれば断面も可
- **柱はこれ以上絞ると実測の裏付けが無く"想像"になる**。候補提示で止めるのが誠実(ユーザー方針)

## 出力一式(扇町2号の例)
`output/扇町2号/`: `ogimachi_1f_plan.jpg`(平面図) `ogimachi_2f_plan.jpg` `ogimachi_structural_overlay.jpg`(通し柱)

## 原則
- 寸法=点群実測、推定は載せない(事実ベース)
- 図面はReadでチャットに表示。リンクだけでは見えない
- 完成のたびGitHub(タイムマシン)に保存
