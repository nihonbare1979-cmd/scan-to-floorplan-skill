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

DL_NAME = Path(rooms_path).name
rp = BASE / rooms_path
if rp.exists():
    data = json.loads(rp.read_text())
else:
    # 初期JSONが無ければ空の間取りから開始(ユーザーがブラウザで部屋を追加)
    data = {"title": "間取りエディタ", "bldg_w": 10.0, "bldg_h": 10.0,
            "x_dims": [0, 10.0], "y_dims": [0, 10.0], "rooms": []}
TITLE = data.get("title", "間取りエディタ")
bg = (BASE / bg_path).read_text().strip()

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
 </div>
 <canvas id="cv" width="760" height="820"></canvas>
 <p class="hint">部屋をクリックで選択 → 中をドラッグで移動 / 角・辺をドラッグでサイズ変更。<br>
 点群(下敷き)の壁に合わせて配置してください。スナップONで近い壁・0.05m単位に吸着します。</p>
</div>
<div id="panel">
 <h2>__TITLE__ 間取りエディタ</h2>
 <label>部屋名</label><input id="f_name" oninput="applyField()">
 <label>種別(色)</label>
 <select id="f_type" onchange="applyField()">
  <option>和室</option><option>洋室</option><option>水回り</option><option>玄関</option>
  <option>廊下</option><option>収納</option><option>床の間</option><option>縁側</option>
  <option>屋外</option><option>未定</option>
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
 <hr>
 <button class="primary" onclick="save()">💾 保存(JSONダウンロード)</button>
 <p class="hint">保存すると <b>__DLNAME__</b> がダウンロードされます。<br>
 「ダウンロードに保存した」と伝えてくれれば、こちらで清書します。</p>
 <textarea id="json" readonly></textarea>
</div>
<script>
const DATA = __DATA__;
const BG = "data:image/png;base64,__BG__";
const COL = {和室:'#fff5dc',洋室:'#e8e0f0',水回り:'#d7ebf0',玄関:'#faf0d7',
 廊下:'#f2f2e8',収納:'#e4d8c8',床の間:'#fce8d0',縁側:'#ece4ce',屋外:'#f5f5f5',未定:'#e1e1e1'};
const TATAMI=1.62, SCALE=70, MARGIN=40;
let rooms=DATA.rooms.map(r=>({...r})), sel=-1, snap=true, showBg=true;
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
  ctx.strokeStyle=i===sel?'#e2007a':'#333'; ctx.lineWidth=i===sel?3:1.5;
  ctx.strokeRect(X(r.x),Y(r.y),r.w*SCALE,r.h*SCALE);
  ctx.fillStyle='#222'; ctx.font='13px sans-serif'; ctx.textAlign='center';
  const cx=X(r.x+r.w/2), cy=Y(r.y+r.h/2);
  ctx.fillText(r.name,cx,cy-4);
  ctx.font='11px sans-serif'; ctx.fillStyle='#666';
  ctx.fillText((r.w*r.h).toFixed(1)+'㎡ / '+(r.w*r.h/TATAMI).toFixed(1)+'畳',cx,cy+12);
  if(i===sel){ctx.fillStyle='#e2007a';
   handles(r).forEach(h=>ctx.fillRect(h.px-4,h.py-4,8,8));}
 });
 // 外周
 ctx.strokeStyle='#000'; ctx.lineWidth=3;
 ctx.strokeRect(X(0),Y(0),DATA.bldg_w*SCALE,DATA.bldg_h*SCALE);
 document.getElementById('json').value=JSON.stringify(out(),null,1);
}
function handles(r){return[
 {id:'nw',px:X(r.x),py:Y(r.y)},{id:'ne',px:X(r.x+r.w),py:Y(r.y)},
 {id:'sw',px:X(r.x),py:Y(r.y+r.h)},{id:'se',px:X(r.x+r.w),py:Y(r.y+r.h)},
 {id:'n',px:X(r.x+r.w/2),py:Y(r.y)},{id:'s',px:X(r.x+r.w/2),py:Y(r.y+r.h)},
 {id:'w',px:X(r.x),py:Y(r.y+r.h/2)},{id:'e',px:X(r.x+r.w),py:Y(r.y+r.h/2)}];}
cv.onmousedown=e=>{
 const mx=e.offsetX,my=e.offsetY;
 if(sel>=0){for(const h of handles(rooms[sel])) if(Math.abs(h.px-mx)<7&&Math.abs(h.py-my)<7){drag={mode:'resize',id:h.id};return;}}
 for(let i=rooms.length-1;i>=0;i--){const r=rooms[i];
  if(mx>X(r.x)&&mx<X(r.x+r.w)&&my>Y(r.y)&&my<Y(r.y+r.h)){sel=i;syncPanel();drag={mode:'move',ox:mX(mx)-r.x,oy:mY(my)-r.y};draw();return;}}
 sel=-1;syncPanel();draw();
};
cv.onmousemove=e=>{
 if(!drag||sel<0)return; const r=rooms[sel], mx=mX(e.offsetX), my=mY(e.offsetY);
 if(drag.mode==='move'){r.x=snapVal(mx-drag.ox,'x');r.y=snapVal(my-drag.oy,'y');}
 else{const id=drag.id;
  if(id.includes('w')){const nx=snapVal(mx,'x');r.w=Math.max(0.3,r.x+r.w-nx);r.x=nx;}
  if(id.includes('e')){r.w=Math.max(0.3,snapVal(mx,'x')-r.x);}
  if(id.includes('n')){const ny=snapVal(my,'y');r.h=Math.max(0.3,r.y+r.h-ny);r.y=ny;}
  if(id.includes('s')){r.h=Math.max(0.3,snapVal(my,'y')-r.y);}}
 syncPanel();draw();
};
window.onmouseup=()=>drag=null;
function syncPanel(){const r=rooms[sel];
 if(!r){document.getElementById('info').textContent='';return;}
 f_name.value=r.name;f_type.value=r.type;f_x.value=r.x.toFixed(2);f_y.value=r.y.toFixed(2);
 f_w.value=r.w.toFixed(2);f_h.value=r.h.toFixed(2);
 document.getElementById('info').textContent=`面積 ${(r.w*r.h).toFixed(1)}㎡ / ${(r.w*r.h/TATAMI).toFixed(1)}畳`;
}
function applyField(){if(sel<0)return;const r=rooms[sel];
 r.name=f_name.value;r.type=f_type.value;
 r.x=+f_x.value;r.y=+f_y.value;r.w=+f_w.value;r.h=+f_h.value;
 document.getElementById('info').textContent=`面積 ${(r.w*r.h).toFixed(1)}㎡ / ${(r.w*r.h/TATAMI).toFixed(1)}畳`;draw();}
function addRoom(){rooms.push({name:'新部屋',x:1,y:1,w:2,h:2,type:'未定'});sel=rooms.length-1;syncPanel();draw();}
function dupRoom(){if(sel<0)return;const r=rooms[sel];rooms.push({...r,x:r.x+0.3,y:r.y+0.3,name:r.name+'_copy'});sel=rooms.length-1;syncPanel();draw();}
function delRoom(){if(sel<0)return;rooms.splice(sel,1);sel=-1;syncPanel();draw();}
function toggleBg(){showBg=!showBg;bgBtn.textContent='下敷き:'+(showBg?'ON':'OFF');draw();}
function toggleSnap(){snap=!snap;snapBtn.textContent='スナップ:'+(snap?'ON':'OFF');}
function out(){return{...DATA,rooms:rooms.map(r=>({name:r.name,x:+r.x.toFixed(2),y:+r.y.toFixed(2),w:+r.w.toFixed(2),h:+r.h.toFixed(2),type:r.type}))};}
function save(){const blob=new Blob([JSON.stringify(out(),null,2)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='__DLNAME__';a.click();}
draw();
</script></body></html>"""

html = (HTML.replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__BG__", bg).replace("__DLNAME__", DL_NAME)
            .replace("__TITLE__", TITLE))
out = BASE / out_html
out.write_text(html)
print("生成:", out, f"({len(html)//1024} KB)")
