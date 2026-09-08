"""
間取りエディタ(editor.html)を生成する。
rooms.json と 下敷きbase64 を埋め込み、単体で開けるHTMLにする。
通常は build_property_editor.py から呼ばれる。
  python3 build_editor.py <rooms.json> <bg.b64> <out.html>
rooms.json が無い場合は空の間取り(部屋ゼロ)から始める。
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent
# 引数: [rooms.json] [bg.b64] [out.html]
rooms_path = sys.argv[1] if len(sys.argv) > 1 else "rooms.json"
bg_path = sys.argv[2] if len(sys.argv) > 2 else "intermediate/bg.b64"
out_html = sys.argv[3] if len(sys.argv) > 3 else "editor.html"

def _resolve(p):
    """カレント(=物件プロジェクトフォルダ) → scripts/ の順で探す。"""
    q = Path(p)
    return q if q.exists() else BASE / p


DL_NAME = Path(rooms_path).name
rp = _resolve(rooms_path)
if rp.exists():
    data = json.loads(rp.read_text())
else:
    # 初期JSONが無ければ空の間取りから開始(ユーザーがブラウザで部屋を追加)
    data = {"title": "間取りエディタ", "bldg_w": 10.0, "bldg_h": 10.0,
            "x_dims": [0, 10.0], "y_dims": [0, 10.0], "rooms": []}
TITLE = data.get("title", "間取りエディタ")
bg = _resolve(bg_path).read_text().strip()

HTML = r"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<title>__TITLE__ 間取りエディタ</title>
<style>
 body{font-family:"Hiragino Kaku Gothic ProN",sans-serif;margin:0;display:flex;background:#f4f3ef}
 #left{flex:1;padding:12px}
 #panel{width:280px;padding:14px;background:#fff;border-left:1px solid #ddd;height:100vh;box-sizing:border-box;overflow:auto}
 canvas{background:#fff;border:1px solid #ccc;cursor:crosshair}
 h2{margin:4px 0 10px;font-size:16px}
 label{display:block;font-size:12px;color:#555;margin:8px 0 2px}
 input,select{width:100%;box-sizing:border-box;padding:5px;font-size:13px}
 .row{display:flex;gap:6px}
 .row>div{flex:1}
 button{margin:4px 2px;padding:7px 10px;font-size:13px;cursor:pointer;border:1px solid #bbb;background:#fafafa;border-radius:5px}
 button.primary{background:#2a7;color:#fff;border-color:#2a7}
 #json{width:100%;height:120px;font-size:11px;font-family:monospace}
 .hint{font-size:11px;color:#888;line-height:1.5}
 .toolbar{margin-bottom:8px}
</style></head><body>
<div id="left">
 <div class="toolbar">
  <button onclick="addRoom()">＋部屋追加</button>
  <button onclick="dupRoom()">複製</button>
  <button onclick="delRoom()">削除</button>
  <button id="bgBtn" onclick="toggleBg()">下敷き:ON</button>
  <button id="snapBtn" onclick="toggleSnap()">スナップ:ON</button>
  <button id="linkBtn" onclick="toggleLink()" title="辺を動かすと、その壁を共有する隣室も追従">壁連動:ON</button>
  <button onclick="addOp()">＋開口追加</button>
  <button onclick="toggleOpKind()">種類切替(戸→窓→壁撤去→壁新設)</button>
  <button onclick="addWallOp('壁撤去')" style="border-color:#c62828;color:#c62828">＋壁撤去</button>
  <button onclick="addWallOp('壁新設')" style="border-color:#111">＋壁新設</button>
  <button onclick="rotOp()">開口回転</button>
  <button onclick="delOp()">開口削除</button>
  <button onclick="addOutlet()" style="border-color:#d32f2f">＋コンセント</button>
  <button onclick="delOut()">コンセント削除</button>
  <button onclick="addApp()" style="border-color:#1565c0;color:#1565c0">＋家電/家具</button>
  <button onclick="rotApp()">家電回転</button>
  <button onclick="delApp()">家電削除</button>
 </div>
 <canvas id="cv" width="760" height="820"></canvas>
 <p class="hint">部屋をクリックで選択 → 中をドラッグで移動 / 角・辺をドラッグでサイズ変更。<br>
 点群(下敷き)の壁に合わせて配置してください。スナップONで近い壁・0.05m単位に吸着します。<br>
 <b>開口</b>(茶=戸/青=窓)はクリックで選択 → ドラッグで移動、「戸⇄窓」「開口削除」で修正。誤検出は削除してください。<br>
 <b>コンセント</b>: 「＋コンセント」で追加(部屋を選んでいればその部屋の中央に出る) → ドラッグで壁に吸着。色: 黒=現状 / 赤=計画◎必須 / 橙=計画○推奨 / 灰=計画△ / ×=撤去。右パネルで口数・高さ・専用回路・USB・アースを入力。壁の上に置くと<b>「取り付け側」でどちらの部屋向きか</b>を選べる(向き反転⇄で切替)。記号は取り付け側の部屋の内側に少しずれて表示。<br>
 <b>壁の撤去/新設</b>: 「＋壁撤去」「＋壁新設」(部屋を選んでいれば、その右側の壁に沿って出る)→ドラッグで壁に重ね、端の■で長さを調整(壁の端・部屋の角に吸着)。<span style="color:#c62828">撤去=赤点線(壁が消える)</span>、新設=太い黒線。一部だけ壊すなら短くする。<br>
 <b>家電/家具</b>: 「＋家電/家具」(部屋を選んでいればその中央に出る)→種類を選ぶと実寸・消費電力・専用回路の要否が入る→ドラッグで配置(壁に吸着)、「家電回転」で縦横。<b>階段下</b>は種別「階段下」の部屋を階段の上に重ねて置く(点線枠)。</p>
</div>
<div id="panel">
 <h2>__TITLE__ 間取りエディタ</h2>
 <label>部屋名</label><input id="f_name" oninput="applyField()">
 <label>役割(用途) — 図面に太字で表示</label><input id="f_role" list="roleList" oninput="applyField()" placeholder="寝室A / リビング / ダイニング …">
 <datalist id="roleList">
  <option>寝室A</option><option>寝室B</option><option>寝室C</option><option>寝室D</option>
  <option>リビング</option><option>ダイニング</option><option>キッチン</option><option>ワークスペース</option>
  <option>玄関</option><option>土間</option><option>洗面脱衣</option><option>浴室</option><option>トイレ</option>
  <option>収納</option><option>ホスト用倉庫</option><option>清掃用品置き場</option><option>廊下</option><option>縁側</option><option>屋外</option>
 </datalist>
 <label>種別(色)</label>
 <select id="f_type" onchange="applyField()">
  <option>和室</option><option>洋室</option><option>水回り</option><option>玄関</option>
  <option>廊下</option><option>収納</option><option>床の間</option><option>縁側</option>
  <option>出窓</option><option>階段下</option><option>屋外</option><option>未定</option>
 </select>
 <div class="row">
  <div><label>X(m)</label><input id="f_x" type="number" step="0.01" oninput="applyField()"></div>
  <div><label>Y(m)</label><input id="f_y" type="number" step="0.01" oninput="applyField()"></div>
 </div>
 <div class="row">
  <div><label>幅W(m)</label><input id="f_w" type="number" step="0.01" oninput="applyField()"></div>
  <div><label>高H(m)</label><input id="f_h" type="number" step="0.01" oninput="applyField()"></div>
 </div>
 <p id="info" class="hint"></p>
 <div id="outPanel" style="display:none;border:1px solid #ddd;padding:8px;border-radius:6px;background:#fafafa">
  <b style="font-size:13px">コンセント</b>
  <label>状態</label>
  <select id="o_status" onchange="applyOut()"><option>現状</option><option>計画◎必須</option><option>計画○推奨</option><option>計画△あれば</option><option>撤去</option></select>
  <label>取り付け側(どの部屋向きか)</label>
  <div class="row"><div><select id="o_face" onchange="applyFace()"></select></div><div><button onclick="flipFace()" style="width:100%;margin:0">向き反転 ⇄</button></div></div>
  <div class="row">
   <div><label>口数</label><input id="o_ports" type="number" step="1" min="1" oninput="applyOut()"></div>
   <div><label>高さ(cm)</label><input id="o_height" type="number" step="5" oninput="applyOut()"></div>
  </div>
  <label>用途メモ</label><input id="o_note" oninput="applyOut()" placeholder="枕元 / テレビ / 冷蔵庫 など">
  <label><input type="checkbox" id="o_ded" onchange="applyOut()" style="width:auto"> 専用回路</label>
  <label><input type="checkbox" id="o_usb" onchange="applyOut()" style="width:auto"> USB付き</label>
  <label><input type="checkbox" id="o_earth" onchange="applyOut()" style="width:auto"> アース付き</label>
  <p id="o_info" class="hint"></p>
 </div>
 <div id="appPanel" style="display:none;border:1px solid #ddd;padding:8px;border-radius:6px;background:#f3f7fd">
  <b style="font-size:13px">家電 / 家具</b>
  <label>種類</label><select id="a_kind" onchange="applyApp(true)"></select>
  <label>表示名(任意)</label><input id="a_label" oninput="applyApp()" placeholder="空なら種類名">
  <div class="row">
   <div><label>幅(m)</label><input id="a_w" type="number" step="0.05" oninput="applyApp()"></div>
   <div><label>奥行(m)</label><input id="a_h" type="number" step="0.05" oninput="applyApp()"></div>
  </div>
  <div class="row">
   <div><label>消費電力(W)</label><input id="a_watt" type="number" step="50" oninput="applyApp()"></div>
   <div><label>&nbsp;</label><label style="margin:0"><input type="checkbox" id="a_ded" onchange="applyApp()" style="width:auto"> 専用回路</label></div>
  </div>
  <label>メモ</label><input id="a_memo" oninput="applyApp()">
  <p id="a_info" class="hint"></p>
 </div>
 <div id="opPanel" style="display:none;border:1px solid #ddd;padding:8px;border-radius:6px;background:#fafafa">
  <b style="font-size:13px">開口 / 壁</b>
  <label>種類</label><select id="op_kind" onchange="applyOp()"><option>戸</option><option>窓</option><option>壁撤去</option><option>壁新設</option></select>
  <label>長さ(m)</label><input id="op_len" type="number" step="0.05" min="0.1" oninput="applyOp()">
  <p class="hint">端の■をドラッグで長さ調整(壁の端に吸着)。「開口回転」で縦横、「開口削除」で消去。</p>
 </div>
 <hr>
 <button class="primary" onclick="save()">💾 保存</button>
 <p id="saveMsg" class="hint">http経由(serve_editor.py)で開いていれば<b>サーバへ直接保存</b>されます(取り違えなし)。<br>
 file://で開いた場合は従来どおり <b>__DLNAME__</b> をダウンロードします。</p>
 <p style="font-size:11px;color:#666;margin:6px 0">壁の移動: 部屋を選び、辺の■ハンドルをドラッグ。<b>壁連動ON</b>なら向かいの部屋の辺も一緒に動く(壁1本だけ動かす時はOFF)。<b>役割(用途)</b>欄に寝室A・リビング等を入れると図面に赤太字で表示され保存される(部屋名はそのまま残る)→💾保存。</p>
 <textarea id="json" readonly></textarea>
</div>
<script>
const DATA = __DATA__;
const BG = "data:image/png;base64,__BG__";
const COL = {和室:'#fff5dc',洋室:'#e8e0f0',水回り:'#d7ebf0',玄関:'#faf0d7',
 廊下:'#f2f2e8',収納:'#e4d8c8',床の間:'#fce8d0',縁側:'#ece4ce',出窓:'#cfe6c8',階段下:'#fde2e2',屋外:'#f5f5f5',未定:'#e1e1e1'};
const TATAMI=1.62, SCALE=70, MARGIN=40;
let rooms=DATA.rooms.map(r=>({...r})), sel=-1, snap=true, showBg=true, linkWalls=true;
let ops=(DATA.openings||[]).map(o=>({...o})), selO=-1;
let outs=(DATA.outlets||[]).map(o=>({...o})), selOut=-1;
const APP={
 '冷蔵庫':[0.60,0.65,250,1],'洗濯機':[0.60,0.60,500,0],'乾燥機':[0.60,0.60,1200,1],'洗濯乾燥機':[0.60,0.65,1200,1],
 '電子レンジ':[0.50,0.40,1400,1],'炊飯器':[0.28,0.35,1200,0],'電気ケトル':[0.20,0.20,1200,0],'トースター':[0.35,0.30,1000,0],
 'IHクッキングヒーター(200V)':[0.60,0.55,5800,1],'食洗機':[0.45,0.55,1200,1],'エアコン':[0.80,0.25,800,1],'テレビ':[1.20,0.10,150,0],
 'ドライヤー(使用位置)':[0.30,0.30,1200,1],'温水洗浄便座':[0.45,0.55,400,0],'給湯器':[0.50,0.30,100,0],
 'Wi-Fiルーター':[0.20,0.20,15,0],'防犯カメラ':[0.10,0.10,10,0],'スマートロック':[0.10,0.10,5,0],
 '電気ストーブ':[0.40,0.30,1200,0],'加湿器':[0.25,0.25,300,0],'除湿機':[0.35,0.25,300,0],'掃除機充電':[0.20,0.20,50,0],
 'ベッド(シングル)':[1.00,2.00,0,0],'ベッド(ダブル)':[1.40,2.00,0,0],'布団(1組)':[1.00,2.10,0,0],'デスク':[1.20,0.60,0,0],
 'テーブル':[1.50,0.80,0,0],'ソファ':[1.80,0.85,0,0],'キッチンカウンター':[1.80,0.60,0,0],'その他':[0.50,0.50,0,0]};
let apps=(DATA.appliances||[]).map(a=>({...a})), selApp=-1;
const OCOL={'現状':'#222','計画◎必須':'#d32f2f','計画○推奨':'#ef8f00','計画△あれば':'#888','撤去':'#bbb'};
let drag=null;
const cv=document.getElementById('cv'), ctx=cv.getContext('2d');
const bgImg=new Image(); bgImg.src=BG; bgImg.onload=draw;
const X=m=>MARGIN+m*SCALE, Y=m=>MARGIN+m*SCALE;
const mX=px=>(px-MARGIN)/SCALE, mY=py=>(py-MARGIN)/SCALE;

function guides(axis){ // 吸着候補(他部屋の辺＋寸法線)
 let g=axis==='x'?[...DATA.x_dims]:[...DATA.y_dims];
 rooms.forEach((r,i)=>{if(i!==sel){if(axis==='x'){g.push(r.x,r.x+r.w)}else{g.push(r.y,r.y+r.h)}}});
 return g;
}
function snapVal(v,axis){
 if(!snap)return Math.round(v*100)/100;
 for(const g of guides(axis)) if(Math.abs(g-v)<0.12) return g;
 return Math.round(v/0.05)*0.05;
}
function draw(){
 ctx.clearRect(0,0,cv.width,cv.height);
 if(showBg&&bgImg.complete) ctx.drawImage(bgImg,X(0),Y(0),DATA.bldg_w*SCALE,DATA.bldg_h*SCALE);
 // 寸法グリッド
 ctx.strokeStyle='#e0a0a0'; ctx.lineWidth=1;
 DATA.x_dims.forEach(x=>{ctx.beginPath();ctx.moveTo(X(x),Y(0));ctx.lineTo(X(x),Y(DATA.bldg_h));ctx.stroke()});
 ctx.strokeStyle='#a0a0e0';
 DATA.y_dims.forEach(y=>{ctx.beginPath();ctx.moveTo(X(0),Y(y));ctx.lineTo(X(DATA.bldg_w),Y(y));ctx.stroke()});
 // 部屋
 rooms.forEach((r,i)=>{
  ctx.fillStyle=COL[r.type]||'#e1e1e1'; ctx.globalAlpha=showBg?0.55:0.9;
  ctx.fillRect(X(r.x),Y(r.y),r.w*SCALE,r.h*SCALE); ctx.globalAlpha=1;
  ctx.strokeStyle=i===sel?'#e2007a':(r.type==='階段下'?'#c0392b':'#333'); ctx.lineWidth=i===sel?3:1.5;
  if(r.type==='階段下')ctx.setLineDash([5,4]);
  ctx.strokeRect(X(r.x),Y(r.y),r.w*SCALE,r.h*SCALE); ctx.setLineDash([]);
  ctx.fillStyle='#222'; ctx.font='13px sans-serif'; ctx.textAlign='center';
  const cx=X(r.x+r.w/2), cy=Y(r.y+r.h/2);
  if(r.role){ctx.font='bold 14px sans-serif';ctx.fillStyle='#b3261e';ctx.fillText(r.role,cx,cy-16);
   ctx.font='12px sans-serif';ctx.fillStyle='#444';ctx.fillText(r.name,cx,cy-1);}
  else{ctx.fillText(r.name,cx,cy-4);}
  ctx.font='11px sans-serif'; ctx.fillStyle='#666';
  ctx.fillText((r.w*r.h).toFixed(1)+'㎡ / '+(r.w*r.h/TATAMI).toFixed(1)+'畳',cx,cy+12);
  if(i===sel){ctx.fillStyle='#e2007a';
   handles(r).forEach(h=>ctx.fillRect(h.px-4,h.py-4,8,8));}
 });
 // 家電/家具(青系=家電・茶系=家具)
 apps.forEach((a,i)=>{const px=X(a.x),py=Y(a.y),pw=a.w*SCALE,ph=a.h*SCALE,furn=!(a.watt>0);
  ctx.fillStyle=furn?'#efe6d6':'#dbeafe';ctx.globalAlpha=0.9;ctx.fillRect(px,py,pw,ph);ctx.globalAlpha=1;
  ctx.strokeStyle=i===selApp?'#e2007a':(furn?'#8d6e3f':'#1565c0');ctx.lineWidth=i===selApp?3:1.5;ctx.strokeRect(px,py,pw,ph);
  ctx.fillStyle='#123';ctx.textAlign='center';ctx.font='10px sans-serif';
  const lab=a.label||a.kind;ctx.fillText(lab,px+pw/2,py+ph/2+(a.watt>0?-1:4));
  if(a.watt>0){ctx.font='9px sans-serif';ctx.fillStyle=a.ded?'#c62828':'#1565c0';ctx.fillText(a.watt+'W'+(a.ded?' 専':''),px+pw/2,py+ph/2+10);}
 });
 // 開口(茶=戸/青=窓) / 壁撤去(赤点線・壁を消す) / 壁新設(太黒)・選択中はピンク
 ops.forEach((o,i)=>{
  const col=i===selO?'#e2007a':(o.kind==='窓'?'#1e6eb4':o.kind==='壁新設'?'#111':o.kind==='壁撤去'?'#c62828':'#965a28');
  const seg=()=>{ctx.beginPath();if(o.ori==='h'){ctx.moveTo(X(o.a0),Y(o.c));ctx.lineTo(X(o.a1),Y(o.c));}else{ctx.moveTo(X(o.c),Y(o.a0));ctx.lineTo(X(o.c),Y(o.a1));}};
  ctx.lineCap='butt';
  if(o.kind==='壁撤去'){ctx.setLineDash([]);ctx.strokeStyle='#fff';ctx.lineWidth=7;seg();ctx.stroke();
   ctx.setLineDash([7,5]);ctx.strokeStyle=col;ctx.lineWidth=i===selO?3:2;seg();ctx.stroke();ctx.setLineDash([]);}
  else{ctx.strokeStyle=col;ctx.lineWidth=(o.kind==='壁新設')?(i===selO?8:6):(i===selO?7:5);seg();ctx.stroke();}
  if(o.kind==='壁撤去'||o.kind==='壁新設'){ctx.font='bold 10px sans-serif';ctx.fillStyle=col;ctx.textAlign='center';
   const lx=o.ori==='h'?X((o.a0+o.a1)/2):X(o.c)+12, ly=o.ori==='h'?Y(o.c)-7:Y((o.a0+o.a1)/2);ctx.fillText(o.kind,lx,ly);}
  if(i===selO){ctx.fillStyle='#e2007a';opEnds(o).forEach(h=>ctx.fillRect(h.px-4,h.py-4,8,8));}
 });
 // コンセント
 outs.forEach((o,i)=>{const dp=drawPos(o),px=X(dp.x),py=Y(dp.y),c=OCOL[o.status]||'#222';
  if(o.dir){ctx.beginPath();ctx.moveTo(X(o.x),Y(o.y));ctx.lineTo(px,py);ctx.strokeStyle=c;ctx.lineWidth=2;ctx.stroke();}
  ctx.beginPath();ctx.arc(px,py,7,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();
  ctx.lineWidth=i===selOut?3:2;ctx.strokeStyle=i===selOut?'#e2007a':c;ctx.stroke();
  ctx.beginPath();ctx.moveTo(px-4,py-2);ctx.lineTo(px+4,py-2);ctx.moveTo(px-4,py+2);ctx.lineTo(px+4,py+2);ctx.strokeStyle=c;ctx.lineWidth=1.5;ctx.stroke();
  if(o.status==='撤去'){ctx.beginPath();ctx.moveTo(px-6,py-6);ctx.lineTo(px+6,py+6);ctx.moveTo(px+6,py-6);ctx.lineTo(px-6,py+6);ctx.strokeStyle='#d32f2f';ctx.stroke();}
  ctx.font='10px sans-serif';ctx.fillStyle=c;ctx.textAlign='left';
  ctx.fillText((o.ports||2)+'口'+(o.usb?'U':'')+(o.dedicated?'専':'')+(o.earth?'E':'')+(o.height?' '+o.height:''),px+9,py+4);});
 // 外周
 ctx.strokeStyle='#000'; ctx.lineWidth=3;
 ctx.strokeRect(X(0),Y(0),DATA.bldg_w*SCALE,DATA.bldg_h*SCALE);
 document.getElementById('json').value=JSON.stringify(out(),null,1);
}
function opHit(mx,my){
 for(let i=ops.length-1;i>=0;i--){const o=ops[i];
  if(o.ori==='h'){if(Math.abs(my-Y(o.c))<7&&mx>X(o.a0)-5&&mx<X(o.a1)+5)return i;}
  else{if(Math.abs(mx-X(o.c))<7&&my>Y(o.a0)-5&&my<Y(o.a1)+5)return i;}}
 return -1;
}
function handles(r){return[
 {id:'nw',px:X(r.x),py:Y(r.y)},{id:'ne',px:X(r.x+r.w),py:Y(r.y)},
 {id:'sw',px:X(r.x),py:Y(r.y+r.h)},{id:'se',px:X(r.x+r.w),py:Y(r.y+r.h)},
 {id:'n',px:X(r.x+r.w/2),py:Y(r.y)},{id:'s',px:X(r.x+r.w/2),py:Y(r.y+r.h)},
 {id:'w',px:X(r.x),py:Y(r.y+r.h/2)},{id:'e',px:X(r.x+r.w),py:Y(r.y+r.h/2)}];}
cv.onmousedown=e=>{
 const mx=e.offsetX,my=e.offsetY;
 const ti=outHit(mx,my);
 if(ti>=0){selOut=ti;sel=-1;selO=-1;drag={mode:'out'};syncPanel();draw();return;}
 selOut=-1;
 if(selO>=0){for(const h of opEnds(ops[selO])) if(Math.abs(h.px-mx)<8&&Math.abs(h.py-my)<8){drag={mode:'opend',end:h.id};return;}}
 const oi=opHit(mx,my);
 if(oi>=0){selO=oi;sel=-1;const o=ops[oi];
  drag={mode:'op',off:(o.ori==='h'?mX(mx):mY(my))-o.a0};syncPanel();draw();return;}
 selO=-1;
 const ai=appHit(mx,my);
 if(ai>=0){selApp=ai;sel=-1;const a=apps[ai];drag={mode:'app',ox:mX(mx)-a.x,oy:mY(my)-a.y};syncPanel();draw();return;}
 selApp=-1;
 if(sel>=0){for(const h of handles(rooms[sel])) if(Math.abs(h.px-mx)<7&&Math.abs(h.py-my)<7){drag={mode:'resize',id:h.id,links:linkWalls?findLinks(rooms[sel],h.id):[]};return;}}
 for(let i=rooms.length-1;i>=0;i--){const r=rooms[i];
  if(mx>X(r.x)&&mx<X(r.x+r.w)&&my>Y(r.y)&&my<Y(r.y+r.h)){sel=i;syncPanel();drag={mode:'move',ox:mX(mx)-r.x,oy:mY(my)-r.y};draw();return;}}
 sel=-1;syncPanel();draw();
};
cv.onmousemove=e=>{
 if(!drag)return; const mx=mX(e.offsetX), my=mY(e.offsetY);
 if(drag.mode==='out'&&selOut>=0){const o=outs[selOut];const s=snapWall(mx,my);o.x=s.x;o.y=s.y;setFace(o,s.room);syncPanel();draw();return;}
 if(drag.mode==='app'&&selApp>=0){const a=apps[selApp];const s=snapApp(a,mx-drag.ox,my-drag.oy);a.x=s.x;a.y=s.y;a.room=roomAt(a.x+a.w/2,a.y+a.h/2);syncPanel();draw();return;}
 if(drag.mode==='opend'&&selO>=0){const o=ops[selO];const v=o.ori==='h'?snapVal(mx,'x'):snapVal(my,'y');
  if(drag.end==='a0')o.a0=Math.min(v,o.a1-0.1);else o.a1=Math.max(v,o.a0+0.1);syncPanel();draw();return;}
 if(drag.mode==='op'&&selO>=0){const o=ops[selO], w=o.a1-o.a0;
  if(o.ori==='h'){o.a0=Math.round((mx-drag.off)*100)/100;o.a1=Math.round((o.a0+w)*100)/100;o.c=snapVal(my,'y');}
  else{o.a0=Math.round((my-drag.off)*100)/100;o.a1=Math.round((o.a0+w)*100)/100;o.c=snapVal(mx,'x');}
  syncPanel();draw();return;}
 if(sel<0)return; const r=rooms[sel];
 if(drag.mode==='move'){r.x=snapVal(mx-drag.ox,'x');r.y=snapVal(my-drag.oy,'y');}
 else{const id=drag.id;
  if(id.includes('w')){const nx=snapVal(mx,'x');r.w=Math.max(0.3,r.x+r.w-nx);r.x=nx;}
  if(id.includes('e')){r.w=Math.max(0.3,snapVal(mx,'x')-r.x);}
  if(id.includes('n')){const ny=snapVal(my,'y');r.h=Math.max(0.3,r.y+r.h-ny);r.y=ny;}
  if(id.includes('s')){r.h=Math.max(0.3,snapVal(my,'y')-r.y);}
  applyLinks(r,drag);}
 syncPanel();draw();
};
window.onmouseup=()=>drag=null;
function syncPanel(){
 document.getElementById('appPanel').style.display=selApp>=0?'block':'none';
 if(selApp>=0){const a=apps[selApp];const ks=document.getElementById('a_kind');if(!ks.options.length){for(const k in APP){const o=document.createElement('option');o.textContent=k;ks.appendChild(o);}}
  ks.value=a.kind;a_label.value=a.label||'';a_w.value=a.w;a_h.value=a.h;a_watt.value=a.watt||0;a_ded.checked=!!a.ded;a_memo.value=a.memo||'';
  document.getElementById('a_info').textContent=`部屋: ${a.room||'?'}  位置 (${a.x}, ${a.y})`;}
 document.getElementById('opPanel').style.display=selO>=0?'block':'none';
 if(selO>=0){const o=ops[selO];op_kind.value=o.kind;op_len.value=(o.a1-o.a0).toFixed(2);}
 const opn=document.getElementById('outPanel');
 if(selOut>=0){const o=outs[selOut];opn.style.display='block';o_status.value=o.status||'現状';o_ports.value=o.ports||2;o_height.value=o.height||25;o_note.value=o.note||'';o_ded.checked=!!o.dedicated;o_usb.checked=!!o.usb;o_earth.checked=!!o.earth;
  const fs=document.getElementById('o_face');const c=candidates(o.x,o.y);fs.innerHTML='';
  if(!c.length){fs.innerHTML='<option value="">(壁の上に置くと選べます)</option>';}
  c.forEach(k=>{const op=document.createElement('option');op.value=k.dir;op.textContent=k.room+' 側 ('+DIRJ[k.dir]+')';if(k.dir===o.dir)op.selected=true;fs.appendChild(op);});
  document.getElementById('o_info').textContent=`位置 (${o.x}, ${o.y})  取り付け側: ${o.room||'?'}${o.dir?' ('+DIRJ[o.dir]+'向き)':''}`;document.getElementById('info').textContent='';return;}
 opn.style.display='none';
 const r=rooms[sel];
 if(selO>=0){const o=ops[selO];
  document.getElementById('info').textContent=`開口[${o.kind}] 幅${(o.a1-o.a0).toFixed(2)}m 上端${o.top||'?'}m (${o.room||''} ${o.both?'両面検出':'片面検出'})`;return;}
 if(!r){document.getElementById('info').textContent='';return;}
 f_name.value=r.name;f_role.value=r.role||'';f_type.value=r.type;f_x.value=r.x.toFixed(2);f_y.value=r.y.toFixed(2);
 f_w.value=r.w.toFixed(2);f_h.value=r.h.toFixed(2);
 document.getElementById('info').textContent=`面積 ${(r.w*r.h).toFixed(1)}㎡ / ${(r.w*r.h/TATAMI).toFixed(1)}畳`;
}
function applyField(){if(sel<0)return;const r=rooms[sel];
 r.name=f_name.value;r.role=f_role.value;r.type=f_type.value;
 r.x=+f_x.value;r.y=+f_y.value;r.w=+f_w.value;r.h=+f_h.value;
 document.getElementById('info').textContent=`面積 ${(r.w*r.h).toFixed(1)}㎡ / ${(r.w*r.h/TATAMI).toFixed(1)}畳`;draw();}
function outHit(mx,my){for(let i=outs.length-1;i>=0;i--){const o=outs[i];const dp=drawPos(o);if(Math.hypot(mx-X(dp.x),my-Y(dp.y))<10)return i;}return -1;}
function roomAt(x,y){const r=rooms.find(r=>x>=r.x&&x<=r.x+r.w&&y>=r.y&&y<=r.y+r.h);return r?r.name:'';}
// 最寄りの部屋の辺(壁)に吸着(0.15m以内・スナップON時)
function snapWall(mx,my){let best=null;
 rooms.forEach(r=>{const cand=[];const cy=Math.min(Math.max(my,r.y),r.y+r.h),cx=Math.min(Math.max(mx,r.x),r.x+r.w);
  if(my>=r.y-0.05&&my<=r.y+r.h+0.05){cand.push({d:Math.abs(mx-r.x),x:r.x,y:cy});cand.push({d:Math.abs(mx-(r.x+r.w)),x:r.x+r.w,y:cy});}
  if(mx>=r.x-0.05&&mx<=r.x+r.w+0.05){cand.push({d:Math.abs(my-r.y),x:cx,y:r.y});cand.push({d:Math.abs(my-(r.y+r.h)),x:cx,y:r.y+r.h});}
  cand.forEach(c=>{if(!best||c.d<best.d)best={...c,room:r.name};});});
 if(snap&&best&&best.d<0.15)return{x:+best.x.toFixed(2),y:+best.y.toFixed(2),room:best.room};
 return{x:+mx.toFixed(2),y:+my.toFixed(2),room:roomAt(mx,my)};}
function appHit(mx,my){for(let i=apps.length-1;i>=0;i--){const a=apps[i];if(mx>X(a.x)&&mx<X(a.x+a.w)&&my>Y(a.y)&&my<Y(a.y+a.h))return i;}return -1;}
// 家電の辺を壁(部屋の辺)に吸着
function snapApp(a,x,y){if(!snap)return{x:+x.toFixed(2),y:+y.toFixed(2)};
 let bx=x,by=y,dx=0.12,dy=0.12;
 for(const g of guides('x')){if(Math.abs(g-x)<dx){dx=Math.abs(g-x);bx=g;} if(Math.abs(g-(x+a.w))<dx){dx=Math.abs(g-(x+a.w));bx=g-a.w;}}
 for(const g of guides('y')){if(Math.abs(g-y)<dy){dy=Math.abs(g-y);by=g;} if(Math.abs(g-(y+a.h))<dy){dy=Math.abs(g-(y+a.h));by=g-a.h;}}
 return{x:+bx.toFixed(2),y:+by.toFixed(2)};}
function addApp(){let cx,cy;if(sel>=0){const r=rooms[sel];cx=r.x+r.w/2;cy=r.y+r.h/2;}else{cx=mX(cv.width/2);cy=mY(cv.height/2);}
 const k='冷蔵庫',s=APP[k];apps.push({kind:k,label:'',x:+(cx-s[0]/2).toFixed(2),y:+(cy-s[1]/2).toFixed(2),w:s[0],h:s[1],watt:s[2],ded:!!s[3],memo:'',room:roomAt(cx,cy)});
 selApp=apps.length-1;sel=-1;selO=-1;selOut=-1;syncPanel();draw();}
function rotApp(){if(selApp<0)return;const a=apps[selApp];[a.w,a.h]=[a.h,a.w];syncPanel();draw();}
function delApp(){if(selApp<0)return;apps.splice(selApp,1);selApp=-1;syncPanel();draw();}
function applyApp(kindChanged){if(selApp<0)return;const a=apps[selApp];
 if(kindChanged){a.kind=a_kind.value;const s=APP[a.kind]||APP['その他'];a.w=s[0];a.h=s[1];a.watt=s[2];a.ded=!!s[3];syncPanel();draw();return;}
 a.label=a_label.value;a.w=Math.max(0.05,+a_w.value||0.05);a.h=Math.max(0.05,+a_h.value||0.05);a.watt=+a_watt.value||0;a.ded=a_ded.checked;a.memo=a_memo.value;draw();}
const DIRV={N:[0,-1],S:[0,1],E:[1,0],W:[-1,0]}, DIRJ={N:'上/北',S:'下/南',E:'右/東',W:'左/西'};
function drawPos(o){const v=DIRV[o.dir];return v?{x:o.x+0.13*v[0],y:o.y+0.13*v[1]}:{x:o.x,y:o.y};}
// 壁の点から4方向に少し入った先にある部屋＝取り付け側の候補
function candidates(x,y){const L=[];for(const d in DIRV){const v=DIRV[d];const rn=roomAt(x+0.06*v[0],y+0.06*v[1]);if(rn&&!L.some(k=>k.room===rn))L.push({dir:d,room:rn});}return L;}
function setFace(o,prefRoom){const c=candidates(o.x,o.y);if(!c.length){o.dir='';o.room=roomAt(o.x,o.y);return;}
 const keep=c.find(k=>k.dir===o.dir&&k.room===o.room);const m=keep||c.find(k=>k.room===prefRoom)||c[0];o.dir=m.dir;o.room=m.room;}
function applyFace(){if(selOut<0)return;const o=outs[selOut];const c=candidates(o.x,o.y).find(k=>k.dir===o_face.value);if(c){o.dir=c.dir;o.room=c.room;}syncPanel();draw();}
function flipFace(){if(selOut<0)return;const o=outs[selOut];const c=candidates(o.x,o.y);if(c.length<2)return;const i=c.findIndex(k=>k.dir===o.dir);const m=c[(i+1)%c.length];o.dir=m.dir;o.room=m.room;syncPanel();draw();}
outs.forEach(o=>{if(!o.dir)setFace(o,o.room);});   // 旧データ(向き未設定)の引き継ぎ
function addOutlet(){let cx,cy;if(sel>=0){const r=rooms[sel];cx=r.x+r.w/2;cy=r.y+r.h/2;}else{cx=mX(cv.width/2);cy=mY(cv.height/2);}
 outs.push({x:+cx.toFixed(2),y:+cy.toFixed(2),status:'現状',ports:2,height:25,note:'',dedicated:false,usb:false,earth:false,room:roomAt(cx,cy)});
 selOut=outs.length-1;sel=-1;selO=-1;syncPanel();draw();}
function delOut(){if(selOut<0)return;outs.splice(selOut,1);selOut=-1;syncPanel();draw();}
function applyOut(){if(selOut<0)return;const o=outs[selOut];o.status=o_status.value;o.ports=+o_ports.value||2;o.height=+o_height.value||0;o.note=o_note.value;o.dedicated=o_ded.checked;o.usb=o_usb.checked;o.earth=o_earth.checked;draw();}
function addRoom(){rooms.push({name:'新部屋',x:1,y:1,w:2,h:2,type:'未定'});sel=rooms.length-1;syncPanel();draw();}
function dupRoom(){if(sel<0)return;const r=rooms[sel];rooms.push({...r,x:r.x+0.3,y:r.y+0.3,name:r.name+'_copy'});sel=rooms.length-1;syncPanel();draw();}
function delRoom(){if(sel<0)return;rooms.splice(sel,1);sel=-1;syncPanel();draw();}
function toggleBg(){showBg=!showBg;bgBtn.textContent='下敷き:'+(showBg?'ON':'OFF');draw();}
function toggleSnap(){snap=!snap;snapBtn.textContent='スナップ:'+(snap?'ON':'OFF');}
function toggleLink(){linkWalls=!linkWalls;linkBtn.textContent='壁連動:'+(linkWalls?'ON':'OFF');}
function ovl(a0,a1,b0,b1){return Math.min(a1,b1)-Math.max(a0,b0)>0.05;}
// 壁連動: 動かす辺と同じ線上にあり、区間が重なる「向かいの部屋」の辺を集める(直接の隣室のみ)
function findLinks(r,id){const L=[],T=0.04;
 rooms.forEach((q,j)=>{if(j===sel)return;
  if(id.includes('e')&&Math.abs(q.x-(r.x+r.w))<T&&ovl(r.y,r.y+r.h,q.y,q.y+q.h))L.push({j,side:'w'});
  if(id.includes('w')&&Math.abs(q.x+q.w-r.x)<T&&ovl(r.y,r.y+r.h,q.y,q.y+q.h))L.push({j,side:'e'});
  if(id.includes('s')&&Math.abs(q.y-(r.y+r.h))<T&&ovl(r.x,r.x+r.w,q.x,q.x+q.w))L.push({j,side:'n'});
  if(id.includes('n')&&Math.abs(q.y+q.h-r.y)<T&&ovl(r.x,r.x+r.w,q.x,q.x+q.w))L.push({j,side:'s'});});
 return L;}
function applyLinks(r,d){(d.links||[]).forEach(l=>{const q=rooms[l.j];
 if(l.side==='w'){const nx=r.x+r.w;q.w=Math.max(0.3,q.x+q.w-nx);q.x=nx;}
 if(l.side==='e'){q.w=Math.max(0.3,r.x-q.x);}
 if(l.side==='n'){const ny=r.y+r.h;q.h=Math.max(0.3,q.y+q.h-ny);q.y=ny;}
 if(l.side==='s'){q.h=Math.max(0.3,r.y-q.y);}});}
function addOp(){ops.push({ori:'h',c:Math.round(mY(cv.height/2)*20)/20,a0:Math.round(mX(cv.width/2)*20)/20-0.4,a1:Math.round(mX(cv.width/2)*20)/20+0.4,kind:'戸',both:false,room:'手動',edge:''});selO=ops.length-1;sel=-1;syncPanel();draw();}
const KINDS=['戸','窓','壁撤去','壁新設'];
function toggleOpKind(){if(selO<0)return;const o=ops[selO];o.kind=KINDS[(KINDS.indexOf(o.kind)+1)%KINDS.length];syncPanel();draw();}
function applyOp(){if(selO<0)return;const o=ops[selO];o.kind=op_kind.value;const L=Math.max(0.1,+op_len.value||0.1);o.a1=+(o.a0+L).toFixed(2);draw();}
function opEnds(o){return o.ori==='h'?[{id:'a0',px:X(o.a0),py:Y(o.c)},{id:'a1',px:X(o.a1),py:Y(o.c)}]:[{id:'a0',px:X(o.c),py:Y(o.a0)},{id:'a1',px:X(o.c),py:Y(o.a1)}];}
// 壁撤去/新設: 部屋を選んでいればその東側の壁に沿って全長で作る(後で端を縮める)
function addWallOp(kind){let o;
 if(sel>=0){const r=rooms[sel];o={ori:'v',c:+(r.x+r.w).toFixed(2),a0:+r.y.toFixed(2),a1:+(r.y+r.h).toFixed(2)};}
 else{const cx=mX(cv.width/2),cy=mY(cv.height/2);o={ori:'h',c:Math.round(cy*20)/20,a0:Math.round(cx*20)/20-0.5,a1:Math.round(cx*20)/20+0.5};}
 ops.push({...o,kind,both:false,room:'手動',edge:''});selO=ops.length-1;sel=-1;selOut=-1;syncPanel();draw();}
function rotOp(){if(selO<0)return;const o=ops[selO];
 const c=o.c,m=(o.a0+o.a1)/2,w=o.a1-o.a0;
 o.ori=o.ori==='h'?'v':'h';o.c=Math.round(m*100)/100;
 o.a0=Math.round((c-w/2)*100)/100;o.a1=Math.round((c+w/2)*100)/100;
 syncPanel();draw();}
function delOp(){if(selO<0)return;ops.splice(selO,1);selO=-1;syncPanel();draw();}
function out(){return{...DATA,rooms:rooms.map(r=>({name:r.name,role:r.role||'',x:+r.x.toFixed(2),y:+r.y.toFixed(2),w:+r.w.toFixed(2),h:+r.h.toFixed(2),type:r.type})),
 openings:ops.map(o=>({ori:o.ori,c:+(+o.c).toFixed(2),a0:+(+o.a0).toFixed(2),a1:+(+o.a1).toFixed(2),kind:o.kind,top:o.top||null,both:!!o.both,room:o.room||'',edge:o.edge||''})),
 outlets:outs.map(o=>({x:+(+o.x).toFixed(2),y:+(+o.y).toFixed(2),status:o.status||'現状',ports:o.ports||2,height:o.height||0,note:o.note||'',dedicated:!!o.dedicated,usb:!!o.usb,earth:!!o.earth,room:o.room||'',dir:o.dir||''})),
 appliances:apps.map(a=>({kind:a.kind,label:a.label||'',x:+(+a.x).toFixed(2),y:+(+a.y).toFixed(2),w:+(+a.w).toFixed(2),h:+(+a.h).toFixed(2),watt:+a.watt||0,ded:!!a.ded,memo:a.memo||'',room:a.room||''}))};}
async function save(){
 const body=JSON.stringify(out(),null,2);
 const msg=document.getElementById('saveMsg');
 if(location.protocol.startsWith('http')){
  try{
   const res=await fetch('/save/__DLNAME__',{method:'POST',headers:{'Content-Type':'application/json'},body});
   const t=await res.text();
   if(res.ok){msg.innerHTML='✅ サーバへ直接保存しました: <b>'+t+'</b>';return;}
   msg.innerHTML='⚠️ サーバ保存失敗('+res.status+') → ダウンロードにフォールバックします';
  }catch(e){msg.innerHTML='⚠️ サーバ保存エラー → ダウンロードにフォールバックします';}
 }
 const blob=new Blob([body],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='__DLNAME__';a.click();}
draw();
</script></body></html>"""

html = (HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__BG__", bg).replace("__DLNAME__", DL_NAME)
            .replace("__TITLE__", TITLE))
out = Path(out_html)               # カレント(=物件プロジェクトフォルダ)に出力
out.write_text(html)
print("生成:", out.resolve(), f"({len(html)//1024} KB)")
