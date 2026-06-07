"""
1F土台 × 2F整合エディタ(editor_align.html)を生成。
1階を固定の下敷き(グレー)として表示し、2階を「全体移動・全体拡大縮小・個別調整」で
1階の壁に合わせ込む。1階の壁線にスナップ。保存で2階JSONを出力。
  python3 build_align_editor.py
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent
# 引数: [1f.json] [2f.json] [2f_bg.b64] [out.html] [dl_name] [title]
d1_path = sys.argv[1] if len(sys.argv) > 1 else "1f_rooms.json"
d2_path = sys.argv[2] if len(sys.argv) > 2 else "2f_rooms.json"
bg_path = sys.argv[3] if len(sys.argv) > 3 else "intermediate/2f_bg.b64"
out_html = sys.argv[4] if len(sys.argv) > 4 else "editor_align.html"
dl_name = sys.argv[5] if len(sys.argv) > 5 else Path(d2_path).name
title = sys.argv[6] if len(sys.argv) > 6 else "物件"
d1 = json.loads((BASE / d1_path).read_text())      # 1F(土台)
d2 = json.loads((BASE / d2_path).read_text())       # 2F(可動)
bg = (BASE / bg_path).read_text().strip()

HTML = r"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><title>__TITLE__ 1F×2F 整合エディタ</title>
<style>
 body{font-family:"Hiragino Kaku Gothic ProN",sans-serif;margin:0;display:flex;background:#f4f3ef}
 #left{flex:1;padding:12px}#panel{width:300px;padding:14px;background:#fff;border-left:1px solid #ddd;height:100vh;box-sizing:border-box;overflow:auto}
 canvas{background:#fff;border:1px solid #ccc}
 h2{margin:4px 0 8px;font-size:15px}h3{font-size:13px;margin:12px 0 4px;color:#444}
 label{display:block;font-size:12px;color:#555;margin:6px 0 2px}
 input,select{width:100%;box-sizing:border-box;padding:5px;font-size:13px}
 .row{display:flex;gap:6px}.row>div{flex:1}
 button{margin:3px 2px;padding:6px 9px;font-size:13px;cursor:pointer;border:1px solid #bbb;background:#fafafa;border-radius:5px}
 button.primary{background:#2a7;color:#fff;border-color:#2a7}
 button.big{font-size:16px;padding:8px 12px}
 .hint{font-size:11px;color:#888;line-height:1.5}
 .grp{background:#f7f7f4;border:1px solid #e3e3dd;border-radius:6px;padding:8px;margin:8px 0}
 #json{width:100%;height:90px;font-size:11px;font-family:monospace}
</style></head><body>
<div id="left">
 <div style="margin-bottom:6px">
  <button id="bgBtn" onclick="toggleBg()">2F点群:ON</button>
  <button id="baseBtn" onclick="toggleBase()">1F土台:ON</button>
  <button id="snapBtn" onclick="toggleSnap()">1F壁スナップ:ON</button>
  <button id="modeBtn" onclick="toggleMode()" style="background:#ffe7a0">モード:個別編集</button>
  <button onclick="addRoom()" style="background:#e3f4e3">＋部屋追加</button>
  <button onclick="dupRoom()">複製</button>
  <button onclick="delRoom()" style="background:#fde8e8">削除</button>
  <button onclick="undo()" style="background:#e8eefc">↶ 元に戻す(Ctrl+Z)</button>
 </div>
 <canvas id="cv" width="780" height="840"></canvas>
 <p class="hint">グレー=1階(固定の土台)　色付き=2階(可動)。<br>
 ①「全体調整」で2階をまるごと動かす/拡大縮小して1階の壁にざっくり合わせる →
 ②「個別編集」モードで各部屋を微調整。1F壁スナップONで吸着します。</p>
</div>
<div id="panel">
 <h2>1F×2F 整合エディタ</h2>
 <div class="grp">
  <h3>① 2階ぜんぶを動かす</h3>
  <div style="text-align:center">
   <button class="big" onclick="moveAll(0,-0.05)">▲</button><br>
   <button class="big" onclick="moveAll(-0.05,0)">◀</button>
   <button class="big" onclick="moveAll(0.05,0)">▶</button><br>
   <button class="big" onclick="moveAll(0,0.05)">▼</button>
  </div>
  <h3>② 2階ぜんぶの大きさ（縮尺）</h3>
  <div class="row">
   <div><button onclick="scaleAll(0.98)" style="width:100%">－ 縮小</button></div>
   <div><button onclick="scaleAll(1.02)" style="width:100%">＋ 拡大</button></div>
  </div>
  <button onclick="scaleAll(0.995)" style="width:48%">微縮小</button>
  <button onclick="scaleAll(1.005)" style="width:48%">微拡大</button>
  <p class="hint">現在の縮尺: <b id="scaleInfo">100.0%</b>　基準=2階の中心</p>
 </div>
 <div class="grp">
  <h3>③ 選択した部屋を微調整</h3>
  <label>部屋名</label><input id="f_name" oninput="applyField()">
  <label>種別(色)</label>
  <select id="f_type" onchange="applyField()">
   <option>和室</option><option>洋室</option><option>水回り</option><option>玄関</option>
   <option>廊下</option><option>収納</option><option>床の間</option><option>縁側</option>
   <option>屋外</option><option>未定</option>
  </select>
  <div class="row">
   <div><label>X</label><input id="f_x" type="number" step="0.01" oninput="applyField()"></div>
   <div><label>Y</label><input id="f_y" type="number" step="0.01" oninput="applyField()"></div>
   <div><label>W</label><input id="f_w" type="number" step="0.01" oninput="applyField()"></div>
   <div><label>H</label><input id="f_h" type="number" step="0.01" oninput="applyField()"></div>
  </div>
 </div>
 <button class="primary" onclick="save()" style="width:100%">💾 2階を保存</button>
 <p class="hint">合わせ終わったら保存 → <b>2階の整合JSON</b> がDLされます。「保存した」と伝えてください。</p>
 <textarea id="json" readonly></textarea>
</div>
<script>
const D1=__D1__, BASE1F=D1.rooms, D2=__D2__, BG="data:image/png;base64,__BG__";
const COL={和室:'#fff5dc',洋室:'#e8e0f0',水回り:'#d7ebf0',玄関:'#faf0d7',廊下:'#f2f2e8',収納:'#e4d8c8',床の間:'#fce8d0',縁側:'#ece4ce',屋外:'#f5f5f5',未定:'#e1e1e1'};
const TATAMI=1.62,SCALE=68,MARGIN=42;
let rooms=D2.rooms.map(r=>({...r})), sel=-1, snap=true, showBg=true, showBase=true, moveMode=false, scaleTotal=1, drag=null;
let history=[];
function pushHistory(){history.push(JSON.stringify(rooms));if(history.length>60)history.shift();}
function undo(){if(!history.length)return;rooms=JSON.parse(history.pop());sel=-1;syncPanel();draw();}
const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
const bgImg=new Image();bgImg.src=BG;bgImg.onload=draw;
const X=m=>MARGIN+m*SCALE,Y=m=>MARGIN+m*SCALE,mX=p=>(p-MARGIN)/SCALE,mY=p=>(p-MARGIN)/SCALE;

function baseEdges(){let g={x:[],y:[]};BASE1F.forEach(r=>{g.x.push(r.x,r.x+r.w);g.y.push(r.y,r.y+r.h)});return g;}
function snapVal(v,axis){
 if(!snap)return Math.round(v*100)/100;
 const gs=baseEdges()[axis];
 for(const g of gs) if(Math.abs(g-v)<0.15) return g;
 return Math.round(v/0.05)*0.05;
}
function bbox(){let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;rooms.forEach(r=>{x0=Math.min(x0,r.x);y0=Math.min(y0,r.y);x1=Math.max(x1,r.x+r.w);y1=Math.max(y1,r.y+r.h)});return{x0,y0,x1,y1,cx:(x0+x1)/2,cy:(y0+y1)/2};}
function moveAll(dx,dy){pushHistory();rooms.forEach(r=>{r.x+=dx;r.y+=dy});draw();}
function scaleAll(f){pushHistory();const b=bbox();rooms.forEach(r=>{r.x=b.cx+(r.x-b.cx)*f;r.y=b.cy+(r.y-b.cy)*f;r.w*=f;r.h*=f});scaleTotal*=f;document.getElementById('scaleInfo').textContent=(scaleTotal*100).toFixed(1)+'%';draw();}
function draw(){
 ctx.clearRect(0,0,cv.width,cv.height);
 // 1F土台(グレー)
 if(showBase){ctx.textAlign='center';
  BASE1F.forEach(r=>{ctx.fillStyle=COL[r.type]||'#eee';ctx.globalAlpha=0.95;ctx.fillRect(X(r.x),Y(r.y),r.w*SCALE,r.h*SCALE);ctx.globalAlpha=1;
   ctx.strokeStyle='#999';ctx.lineWidth=1.2;ctx.strokeRect(X(r.x),Y(r.y),r.w*SCALE,r.h*SCALE);
   ctx.fillStyle='#555';ctx.font='11px sans-serif';ctx.fillText(r.name,X(r.x+r.w/2),Y(r.y+r.h/2));});}
 // 2F点群(図面の上に薄く重ねる・2Fブロックの下)
 if(showBg&&bgImg.complete){const b=bbox();ctx.globalAlpha=0.55;ctx.drawImage(bgImg,X(b.x0),Y(b.y0),(b.x1-b.x0)*SCALE,(b.y1-b.y0)*SCALE);ctx.globalAlpha=1;}
 // 2F(色付き・可動)
 rooms.forEach((r,i)=>{ctx.fillStyle=COL[r.type]||'#e1e1e1';ctx.globalAlpha=0.5;ctx.fillRect(X(r.x),Y(r.y),r.w*SCALE,r.h*SCALE);ctx.globalAlpha=1;
  ctx.strokeStyle=i===sel?'#e2007a':'#1565c0';ctx.lineWidth=i===sel?3:2;ctx.strokeRect(X(r.x),Y(r.y),r.w*SCALE,r.h*SCALE);
  ctx.fillStyle='#0a3d8f';ctx.font='12px sans-serif';ctx.textAlign='center';ctx.fillText(r.name,X(r.x+r.w/2),Y(r.y+r.h/2));
  if(i===sel)handles(r).forEach(h=>{ctx.fillStyle='#e2007a';ctx.fillRect(h.px-4,h.py-4,8,8)});});
 ctx.strokeStyle='#000';ctx.lineWidth=2.5;ctx.strokeRect(X(0),Y(0),D1.bldg_w*SCALE,D1.bldg_h*SCALE);
 document.getElementById('json').value=JSON.stringify(out(),null,1);
}
function handles(r){return[{id:'nw',px:X(r.x),py:Y(r.y)},{id:'ne',px:X(r.x+r.w),py:Y(r.y)},{id:'sw',px:X(r.x),py:Y(r.y+r.h)},{id:'se',px:X(r.x+r.w),py:Y(r.y+r.h)},{id:'n',px:X(r.x+r.w/2),py:Y(r.y)},{id:'s',px:X(r.x+r.w/2),py:Y(r.y+r.h)},{id:'w',px:X(r.x),py:Y(r.y+r.h/2)},{id:'e',px:X(r.x+r.w),py:Y(r.y+r.h/2)}];}
cv.onmousedown=e=>{const mx=e.offsetX,my=e.offsetY;
 if(moveMode){pushHistory();drag={mode:'all',mx:mX(mx),my:mY(my)};return;}
 if(sel>=0)for(const h of handles(rooms[sel]))if(Math.abs(h.px-mx)<7&&Math.abs(h.py-my)<7){pushHistory();drag={mode:'resize',id:h.id};return;}
 for(let i=rooms.length-1;i>=0;i--){const r=rooms[i];if(mx>X(r.x)&&mx<X(r.x+r.w)&&my>Y(r.y)&&my<Y(r.y+r.h)){pushHistory();sel=i;syncPanel();drag={mode:'move',ox:mX(mx)-r.x,oy:mY(my)-r.y};draw();return;}}
 sel=-1;syncPanel();draw();};
cv.onmousemove=e=>{if(!drag)return;const mx=mX(e.offsetX),my=mY(e.offsetY);
 if(drag.mode==='all'){const dx=mx-drag.mx,dy=my-drag.my;rooms.forEach(r=>{r.x+=dx;r.y+=dy});drag.mx=mx;drag.my=my;draw();return;}
 if(sel<0)return;const r=rooms[sel];
 if(drag.mode==='move'){r.x=snapVal(mx-drag.ox,'x');r.y=snapVal(my-drag.oy,'y');}
 else{const id=drag.id;if(id.includes('w')){const nx=snapVal(mx,'x');r.w=Math.max(0.3,r.x+r.w-nx);r.x=nx;}if(id.includes('e'))r.w=Math.max(0.3,snapVal(mx,'x')-r.x);if(id.includes('n')){const ny=snapVal(my,'y');r.h=Math.max(0.3,r.y+r.h-ny);r.y=ny;}if(id.includes('s'))r.h=Math.max(0.3,snapVal(my,'y')-r.y);}
 syncPanel();draw();};
window.onmouseup=()=>drag=null;
function syncPanel(){const r=rooms[sel];if(!r)return;f_name.value=r.name;f_type.value=r.type||'未定';f_x.value=r.x.toFixed(2);f_y.value=r.y.toFixed(2);f_w.value=r.w.toFixed(2);f_h.value=r.h.toFixed(2);}
function applyField(){if(sel<0)return;const r=rooms[sel];r.name=f_name.value;r.type=f_type.value;r.x=+f_x.value;r.y=+f_y.value;r.w=+f_w.value;r.h=+f_h.value;draw();}
function addRoom(){pushHistory();rooms.push({name:'新部屋',x:1,y:1,w:2,h:2,type:'未定'});sel=rooms.length-1;syncPanel();draw();}
function dupRoom(){if(sel<0)return;pushHistory();const r=rooms[sel];rooms.push({...r,x:r.x+0.3,y:r.y+0.3,name:r.name+'_copy'});sel=rooms.length-1;syncPanel();draw();}
function delRoom(){if(sel<0)return;pushHistory();rooms.splice(sel,1);sel=-1;syncPanel();draw();}
function toggleBg(){showBg=!showBg;bgBtn.textContent='2F点群:'+(showBg?'ON':'OFF');draw();}
function toggleBase(){showBase=!showBase;baseBtn.textContent='1F土台:'+(showBase?'ON':'OFF');draw();}
function toggleSnap(){snap=!snap;snapBtn.textContent='1F壁スナップ:'+(snap?'ON':'OFF');}
function toggleMode(){moveMode=!moveMode;modeBtn.textContent='モード:'+(moveMode?'全体移動':'個別編集');modeBtn.style.background=moveMode?'#a0d8ff':'#ffe7a0';cv.style.cursor=moveMode?'move':'crosshair';}
function out(){return{...D2,rooms:rooms.map(r=>({name:r.name,x:+r.x.toFixed(2),y:+r.y.toFixed(2),w:+r.w.toFixed(2),h:+r.h.toFixed(2),type:r.type}))};}
function save(){const b=new Blob([JSON.stringify(out(),null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='__DLNAME__';a.click();}
window.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&(e.key==='z'||e.key==='Z')){e.preventDefault();undo();}});
draw();
</script></body></html>"""

html = (HTML.replace("__D1__", json.dumps(d1, ensure_ascii=False))
            .replace("__D2__", json.dumps(d2, ensure_ascii=False))
            .replace("__BG__", bg)
            .replace("__TITLE__", title)
            .replace("__DLNAME__", dl_name))
(BASE / out_html).write_text(html)
print("生成:", out_html, f"({len(html)//1024} KB)")
