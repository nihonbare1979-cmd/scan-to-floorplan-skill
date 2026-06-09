---
name: scan-to-floorplan
description: 3Dスキャン(Scaniverse USDZ)から寸法入り平面図・立面図・1F2F整合図・通し柱候補までを作る図面化パイプライン。1スキャンに2階分が入った「通しスキャン」なら1F/2Fの位置合わせを3Dデータから自動で行い通し柱と立面図まで出せる。物件の間取り図・構造叩き台を点群の実測値ベースで起こす。
trigger: 3Dスキャン・USDZ・GLB・間取り図・平面図・立面図・図面化・通し柱・通し柱候補・構造叩き台・物件スキャンの図面化の依頼が来たとき、または /scan-to-floorplan と入力したとき
user_invocable: true
---

## 概要
Scaniverseで撮った3Dスキャン(USDZ)を、寸法=点群実測の正確な図面に起こすパイプライン。事実ベースのみ(推定は載せない)。
**本命は「通しスキャン」**=1スキャンに1階と2階の両方を入れて撮る方式。これだと1F/2Fが最初から同一3D座標系に入るため、**1F/2Fの位置合わせ・縮尺合わせが不要**(従来の整合エディタ工程が消える)で、**統合立面図(断面)と通し柱の◎○△ランク**まで出せる。築古戸建で実証済み(扇町2号)。

## 前提
- スクリプト一式: `~/.claude/skills/scan-to-floorplan/scripts/`
- Blender 5.x: `/Applications/Blender.app/Contents/MacOS/Blender`
- 図面は必ず**Readでチャット内に直接表示**して見せる。さらに**ギャラリーHTML+プレビューペイン**で1画面閲覧できる(後述H)
- 物件データ(glb/output/intermediate/editor_*.html/*_rooms.json/*_frame.json)は公開リポなので`.gitignore`済み。汎用スクリプトのみ公開
- 完成図は `scripts/output/<物件名>/` に収納。ユーザーの私的バックアップ `~/projects/claude-code/ogimachi-floorplan/` にもコピーしGitHub保存
- 関連記憶: usdz-floorplan-pipeline / editor-json-save-pitfall

---

# ★推奨ワークフロー: 通しスキャン(1スキャンに2階分) — 新規物件はこれ

合言葉: **「位置合わせは3Dにやらせる。人は壁をなぞるだけ」**

### A. USDZ → GLB
```
Blender --background --python convert_usdz_glb.py -- <in.usdz> glb/<物件>_full.glb
```
`export_yup=False`でZ-up維持。

### B. 姿勢診断と階の分離(★最重要・決め打ち禁止)
1. `load_glb.summarize`で範囲確認。**Z幅が約6mあれば2階通し**(各階2.5〜3m)。
2. **Zヒストグラム**を描く → 低密度の谷=層間(1F天井+2F床スラブ)。そこで1F/2Fを分離。例(扇町2号): 1F床z≈0.0 / 層間 z≈2.4〜2.9 / 2F床 z≈2.86 / 2F天井 z≈5.2。
3. **3方向正投影**(生XY/XZ/YZ)を`Read`で目視 → Z=上か、倒れ/上下逆がないか確認。XZ・YZに上下2帯が見えれば正常な2階積み。
4. ヨー(水平の傾き)は各階の腰高スライスで自動検出(行/列ヒスト分散最大)。通常ほぼ0でよい。

### C. 統合立面図(断面)= トレース不要で即生成できる
点群を鉛直面に投影するだけ。床=0/層間≒2.4m/2F天井≒5.2mの実測ラインを添える。南面(X横軸)・東面(Y横軸)。通しスキャン最大の利点の一つ。`finish_shared.py`/`finish_through.py`が自動で出すが、トレース前に先出しして見せると喜ばれる。

### D. 共有座標系エディタを生成(1F/2Fを同一原点・同一実測スケール)
新規物件(過去レイアウトなし):
```
python3 build_through_editors.py glb/<物件>_full.glb <floor1_z> <slab_zf> [yaw] [flip]
```
既存の検証済み1Fレイアウトを下敷き出発点に使う場合(扇町2号で使用):
```
python3 build_shared_editors.py glb/<物件>_full.glb <信頼1f_rooms.json> [yaw_ccw]
```
- 両階を**同一extent・同一原点・北=上**で下敷き化 → トレース座標がそのまま通し柱判定に使える(整合作業不要)
- **2Fの下敷きには1Fの壁を薄グレーで重ねる**(位置の目印)。**2F壁=青/1F壁=黒**で色分け
- 点は濃いめ(s=7, alpha=0.9, dpi110)。傾き補正は引数(**画面で反時計回り=負角**)。数値計測が0でもユーザーの目を優先して微調整可
- `build_shared_editors`は`shared_frame.json`(回転・原点シフト)を保存し、Gの仕上げが点群を同じ新フレームへ載せるのに使う

### E. ブラウザでトレース → 保存
`open -a "Google Chrome" editor_shared_*.html`(または`editor_through_*.html`)。**開く前に古いエディタHTMLは削除**(タブが増えると取り違える)。
- 各階の壁を点群に合わせてなぞる。**位置合わせは不要**(3Dで確定済み)
- **出窓**は種別「出窓」(緑)を選び、外壁から外へ飛び出す細い矩形で配置(奥行0.3〜0.6m程度)
- **★Chrome連番の罠**: 既存同名があると`名前 (1).json`になる。「保存した」と言われたら**保存場所とファイルを時系列で必ず特定**し、部屋数・座標・種別を中身照合(取り違え実績あり→editor-json-save-pitfall)。Downloads以外に保存される設定のこともあるので`find ~ -name "*.json" -mmin -45`で広く探す

### F. 階間スナップ(1F/2Fまたいで壁を共通線へ)
```
python3 snap_cross_floor.py <1f.json> <2f.json> [tol=0.10]
```
±tol(既定10cm)以内の壁を「同一線」とみなし共通の壁線へ吸着(作図誤差を吸収)。グループ平均との距離で判定しチェーン暴走を防ぐ。元は`*_before_xsnap.json`にバックアップ。**「数cm〜10cm程度のずれは同一線」はユーザー方針**。

### G. 仕上げ一発(通し柱ランク・統合立面図・寸法清書)
`build_shared_editors`を使った場合(`shared_frame.json`あり):
```
python3 finish_shared.py glb/<物件>_full.glb <1f.json> <2f.json> "<物件>/<接頭>" <タイトル>
```
`build_through_editors`を使った新規物件の場合(レイアウト未登録)は、トレース済み1Fへ点群を登録してから従来仕上げ:
```
python3 register_through.py glb/<物件>_full.glb <1f.json>      # 点群→トレース1F座標系へ剛体登録(FFT相互相関)
python3 finish_through.py  glb/<物件>_full.glb <1f.json> <2f.json> "<物件>/<接頭>" <タイトル>
python3 generate_floorplan.py <1f.json> output/<物件>/<物件>_1f_plan.jpg   # 寸法清書(各階)
```
出力: `_structural_overlay.jpg`(整合+候補) / `_posts_ranked.jpg`(◎○△) / `_section_south.jpg`・`_section_east.jpg`(統合立面) / `_1F平面図.jpg`・`_2F平面図.jpg`(寸法清書)。
- **同一座標系なので通し柱ランクが高精度に出る**(扇町2号で◎27本)。別撮り+手動スケール合わせ方式は◎0だった
- ランクは床〜2F天井の点の垂直連続(n1/n2/被覆)で判定。**柱はこれ以上絞ると実測の裏付けが無く"想像"になる→候補提示で止めるのが誠実**(ユーザー方針)

### H. プレビューペインで1画面閲覧(ギャラリーHTML)
プレビューペインは生の.jpgを表示しにくい → 画像をbase64で埋めたHTMLにすれば確実に出る。
```
python3 make_gallery.py <出力フォルダ> index.html "<タイトル>"
```
`captions.json`(任意, {ファイル名:説明})でキャプション付与。配信は`launch.json`に静的サーバを定義し`preview_start`:
```
{"name":"<物件>-gallery","runtimeExecutable":"python3",
 "runtimeArgs":["-m","http.server","8787","--directory","<絶対パス>"],"port":8787}
```
※`launch.json`は**作業中のプロジェクト直下の`.claude/`**が読まれる。画像更新時は`index.html`再生成のみでよく(サーバ再起動不要)、ユーザーはリロードで反映。サーバが落ちたら`preview_start`で再起動。

---

# 別撮り(1F/2Fを別ファイルで撮影)— レガシー/補助

通しで撮れない場合の従来手順。**半間ズレ等の歪みが入りやすく非推奨**(別撮り2Fを1Fへ手動スケール合わせした図面は誤差が乗る → 可能なら通しで撮り直す)。
- ①USDZ→GLB ②姿勢診断 ③`build_property_editor.py`で各階下敷き+エディタ ④トレース ⑤`generate_floorplan.py`清書 ⑥`build_align_editor.py`で2Fを1Fに重ねて整合(階段基準) ⑦`snap_rooms.py`整列 ⑧`structural_draft.py`で通し柱overlay。
- 別glbだと点群の垂直連続が無く、◎○△ランクと統合立面図は不可(候補overlayまで)。

---

## スクリプト一覧
- `convert_usdz_glb.py` USDZ→GLB(Z-up維持)
- `load_glb.py` GLB読込・座標正規化・範囲要約
- `extract_elevation.py` 床検出(Z=0化)・立面投影
- `build_through_editors.py` 生スキャンから1F/2F共有extent下敷き+エディタ(新規物件)
- `build_shared_editors.py` 既存1Fを基準に共有座標系下敷き+エディタ(色分け/1F目印/傾き補正/`shared_frame.json`保存)
- `build_editor.py` エディタHTML本体(種別に**出窓**含む)。`build_property_editor.py`は別撮り用
- `snap_cross_floor.py` 1F/2F階間スナップ(共通壁線へ吸着)
- `snap_rooms.py` 単一フロア内スナップ
- `register_through.py` 点群をトレース済み1F座標系へ剛体登録(FFT相互相関・flip+並進)
- `finish_shared.py` 共有座標系の仕上げ(通し柱ランク/立面/寸法清書)。`build_shared_editors`とペア
- `finish_through.py` 登録した点群で仕上げ(`register_through`とペア)
- `structural_draft.py` 通し柱overlay・ランク・断面の描画関数群
- `generate_floorplan.py` rooms.json→寸法入り平面図(種別色に**出窓**含む)
- `make_gallery.py` 成果物をbase64埋め込みギャラリーHTML化(プレビュー用)

## 原則
- 寸法=点群実測、推定は載せない(事実ベース)。開口部などの推定はOFF
- 図面はReadでチャット表示+ギャラリーHTMLでプレビュー。リンクだけでは見えない
- 通し柱・構造判断は「候補/叩き台・要現場確認」を必ず明示。最終判断はユーザー・専門家
- 完成のたびGitHub(タイムマシン)に保存。公開リポへ物件データを上げない
