# /scan-to-floorplan — Claude Code スキル

iPhone等の **3Dスキャン（Scaniverse の USDZ）から、寸法＝実測の正確な平面図・1F×2F整合図・通し柱候補まで**を一気通貫で作る Claude Code スキルです。築古の木造2階建てで1F/2F両方を完成させた実例ベースで作られています。

> 「業者に頼むと数万円の図面を、自分のスキャンから無料で起こしたい」——そんな空き家再生・DIYリフォーム・民泊検討の入口に使えます。

---

## できること

- 3Dスキャン（USDZ）を GLB に変換し、点群から間取りを起こす
- **スキャンの姿勢崩れ（横倒し・傾き・上下逆）を自動診断して補正**
- 点群を下敷きにブラウザでドラッグ操作して間取りをトレース
- 寸法＝点群実測の平面図を清書（畳数・面積つき）
- 1階と2階を重ねて整合させ、**通し柱の候補**を抽出
- すべて「事実ベース」（推定は載せない）

---

## 必要なもの

- **Claude Code**
- **iPhone/iPad（LiDAR搭載）＋ Scaniverse**（無料・USDZ書き出し）
- **Blender 5.x**（USDZ→GLB変換に使用・無料）
- **Python 3** と次のライブラリ：`pip3 install -r requirements.txt`
  - numpy / trimesh / matplotlib / Pillow
- **Google Chrome**（間取りエディターを開くため）

---

## インストール

```bash
# 1. このフォルダを ~/.claude/skills/scan-to-floorplan に配置
git clone https://github.com/nihonbare1979-cmd/scan-to-floorplan-skill.git ~/.claude/skills/scan-to-floorplan
#   （zipの場合は展開した scan-to-floorplan フォルダを ~/.claude/skills/ に置く）

# 2. 依存ライブラリをインストール
pip3 install -r ~/.claude/skills/scan-to-floorplan/requirements.txt

# 3. Claude Code を再起動
```

インストール後、Claude Code で `/scan-to-floorplan` が使えるようになります。

---

## 使い方

1. 物件の各フロアを Scaniverse でスキャンし、**USDZ形式**で書き出して Mac に送る（1階・2階は別ファイル）
2. Claude Code のチャットで `/scan-to-floorplan` と入力
3. あとは案内に従うだけ。Claude が変換・姿勢診断・下敷き生成まで進め、**ブラウザの間取りエディター**を開きます
4. 点群の壁に部屋ブロックを合わせてドラッグ → 保存
5. Claude が清書・整合・通し柱候補まで仕上げます

撮影のコツ：**各部屋をゆっくり一周し、壁の隅・天井角をなめる**／窓・鏡の前で止まらない（反射で座標が飛ぶ）／1フロアずつ別ファイルで。

---

## ファイル構成

```
scan-to-floorplan/
├── SKILL.md                      ← /scan-to-floorplan の挙動定義（メイン・8ステップ手順）
├── README.md                     ← このファイル
├── requirements.txt              ← Python依存ライブラリ
├── scripts/
│   ├── convert_usdz_glb.py       ← USDZ→GLB変換（Blenderヘッドレス）
│   ├── build_property_editor.py  ← 下敷き生成＋間取りエディター生成
│   ├── build_editor.py           ← 間取りエディター本体（上記から呼ばれる）
│   ├── build_align_editor.py     ← 1F×2F整合エディター（点群連動・undo・部屋追加）
│   ├── snap_rooms.py             ← 部屋の辺を壁線に吸着（微ズレ整列）
│   ├── structural_draft.py       ← 通し柱候補の抽出・重ね図
│   ├── generate_floorplan.py     ← 平面図の清書
│   ├── draw_plan.py              ← 清書の描画エンジン
│   ├── load_glb.py               ← GLB点群の読み込み
│   ├── rooms_verified.py         ← 初期部屋配置のサンプル（自分の物件用に上書き）
│   └── extract_elevation.py      ← 立面・断面用（任意）
└── docs/
    └── usage_guide.md            ← 姿勢診断のコツ・カスタマイズ詳細
```

---

## 自分の物件で使うには

このスキルは**スキャンデータを渡せば、その物件の図面を起こす**汎用ツールです。特定の物件データは含まれていません。`scripts/build_property_editor.py` にあなたの GLB を渡すと、その点群から下敷きと間取りエディターが生成され、ブラウザで部屋を配置していく流れになります。`scripts/rooms_verified.py` は手動確定した座標を保存しておくための空テンプレートです。

---

## 既知の制約

1. **1階・2階を別々にスキャンした場合**、点群の垂直連続がないため、通し柱の確度ランク（◎○△）と統合立面図（断面）は省略されます。1スキャンに2階分が入っていれば断面も作れます。
2. **スキャン品質に依存**：壁の隅が撮れていないと欠損します。撮り直しが最も確実な精度向上策です。
3. **通し柱は候補まで**：実測の裏付けがない柱まで特定すると“想像”になるため、候補提示で止める設計です。確定には現場での柱位置確認・建築士の確認が必要です。

---

## 免責事項

本スキルが生成するのは、3Dスキャンの実測値に基づく**叩き台の図面**です。正式な建築図面・構造設計の代わりにはなりません。リフォーム・解体・売買・構造に関わる判断は、ご自身の責任で、必要に応じて建築士・専門家に相談のうえ行ってください。

---

## 開発・保守

姿勢診断のロジックやカスタマイズの詳細は [`docs/usage_guide.md`](docs/usage_guide.md) を参照してください。
