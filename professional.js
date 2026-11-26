(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const fmt = n => Number.isFinite(n) ? n.toFixed(5) : '—';
  const pct = n => Number.isFinite(n) ? n.toFixed(1) : '—';

  // Add a dedicated structure panel without requiring a charting dependency.
  if (!$('structurePanel')) {
    const wrap = document.createElement('div');
    wrap.className = 'two pro-panels';
    wrap.id = 'structurePanel';
    wrap.innerHTML = '<section class="panel"><div class="panel-head"><h2>Market structure</h2><span class="pill">RECENT SWING LEVELS</span></div><div class="level-grid"><div class="level-card"><span>Resistance</span><strong id="proResistance">—</strong></div><div class="level-card"><span>Support</span><strong id="proSupport">—</strong></div></div><p class="muted tiny" id="proStructureNote">Levels are estimated from recent candle swings.</p></section><section class="panel"><div class="panel-head"><h2>Pattern recognition</h2><span class="pill">LATEST 3 CANDLES</span></div><div id="proPatternList" class="pattern-list"><span class="muted tiny">Waiting for candles…</span></div><p class="muted tiny">Patterns are descriptive signals, not standalone trade instructions.</p></section>';
    document.querySelector('.two').insertAdjacentElement('beforebegin', wrap);
  }
  if (!$('proStyles')) {
    const style = document.createElement('style');
    style.id = 'proStyles';
    style.textContent = '.pro-panels{margin-top:16px}.level-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.level-card{background:#0a1422;border:1px solid #263750;border-radius:10px;padding:13px}.level-card span{display:block;color:#8fa1ba;font-size:10px;text-transform:uppercase;letter-spacing:1px}.level-card strong{display:block;font-size:18px;margin-top:6px}.pattern-list{display:flex;flex-wrap:wrap;gap:7px;min-height:35px}.pattern-chip{padding:6px 9px;border:1px solid #30435e;border-radius:8px;background:#0b1625;font-size:11px;color:#cbd8e8}.pattern-chip.bull{border-color:#1c7359;color:#64e0b5}.pattern-chip.bear{border-color:#854154;color:#ff91a4}.pattern-chip.neutral{border-color:#79632f;color:#f5d27f}.signal{min-height:82px}.notice{line-height:1.6}#reasons .reason{position:relative;padding-left:18px}#reasons .reason:before{content:"•";position:absolute;left:3px;color:#71a7ff}';
    document.head.appendChild(style);
  }

  function emaSeries(values, period) {
    if (!values.length) return [];
    const alpha = 2 / (period + 1), out = [values[0]];
    for (let i = 1; i < values.length; i++) out.push(values[i] * alpha + out[i - 1] * (1 - alpha));
    return out;
  }
  function rsi14(values) {
    if (values.length < 2) return 50;
    const start = Math.max(1, values.length - 14);
    let gain = 0, loss = 0, count = 0;
    for (let i = start; i < values.length; i++) {
      const d = values[i] - values[i - 1];
      if (d > 0) gain += d; else loss -= d;
      count++;
    }
    const avgGain = gain / Math.max(1, count), avgLoss = loss / Math.max(1, count);
    if (avgLoss === 0) return avgGain === 0 ? 50 : 100;
    return 100 - 100 / (1 + avgGain / avgLoss);
  }
  function getPatterns(data) {
    if (data.length < 2) return [];
    const a = data[data.length - 1], b = data[data.length - 2], c = data[data.length - 3];
    const body = x => Math.abs(x.close - x.open);
    const range = x => Math.max(1e-12, x.high - x.low);
    const upper = x => x.high - Math.max(x.open, x.close);
    const lower = x => Math.min(x.open, x.close) - x.low;
    const bull = x => x.close > x.open, bear = x => x.close < x.open;
    const out = [];
    if (body(a) / range(a) <= .1) out.push('Doji');
    if (lower(a) >= Math.max(body(a) * 2, range(a) * .45) && upper(a) <= range(a) * .25) out.push('Hammer / bullish pin bar');
    if (upper(a) >= Math.max(body(a) * 2, range(a) * .45) && lower(a) <= range(a) * .25) out.push('Shooting star / bearish pin bar');
    if (bull(a) && bear(b) && a.open <= b.close && a.close >= b.open) out.push('Bullish engulfing');
    if (bear(a) && bull(b) && a.open >= b.close && a.close <= b.open) out.push('Bearish engulfing');
    if (a.high < b.high && a.low > b.low) out.push('Inside bar');
    if (data.length >= 3) {
      const mid = (c.open + c.close) / 2;
      if (bear(c) && body(b) < body(c) * .6 && bull(a) && a.close > mid) out.push('Morning star (3-candle)');
      if (bull(c) && body(b) < body(c) * .6 && bear(a) && a.close < mid) out.push('Evening star (3-candle)');
      const threeBull = [c,b,a].every(bull) && c.close < b.close && b.close < a.close;
      const threeBear = [c,b,a].every(bear) && c.close > b.close && b.close > a.close;
      if (threeBull) out.push('Three white soldiers (simplified)');
      if (threeBear) out.push('Three black crows (simplified)');
    }
    return out;
  }
  function levels(data) {
    const recent = data.slice(-50);
    if (!recent.length) return {support:NaN,resistance:NaN};
    const price = recent[recent.length - 1].close;
    const lows = [], highs = [];
    for (let i = 1; i < recent.length - 1; i++) {
      if (recent[i].low <= recent[i-1].low && recent[i].low <= recent[i+1].low) lows.push(recent[i].low);
      if (recent[i].high >= recent[i-1].high && recent[i].high >= recent[i+1].high) highs.push(recent[i].high);
    }
    const below = lows.filter(v => v <= price).sort((x,y)=>y-x);
    const above = highs.filter(v => v >= price).sort((x,y)=>x-y);
    return {support: below[0] ?? Math.min(...recent.map(x=>x.low)), resistance: above[0] ?? Math.max(...recent.map(x=>x.high))};
  }
  function indicators() {
    const close = candles.map(x => x.close);
    const e9 = emaSeries(close,9), e21 = emaSeries(close,21), e50 = emaSeries(close,50);
    const fast = emaSeries(close,12), slow = emaSeries(close,26);
    const mac = fast.map((v,i)=>v-slow[i]), sig = emaSeries(mac,9);
    return {e9,e21,e50,rsi:rsi14(close),mac:mac.at(-1),sig:sig.at(-1)};
  }
  function evaluate(data) {
    const saved = candles;
    candles = data;
    const x = indicators(), ps = getPatterns(data), last = data[data.length-1];
    let bull = 0, bear = 0;
    const reasons = [];
    if (x.e9.at(-1) > x.e21.at(-1)) { bull++; reasons.push('EMA 9 is above EMA 21: short-term trend is bullish.'); }
    else { bear++; reasons.push('EMA 9 is below EMA 21: short-term trend is bearish.'); }
    if (last.close > x.e50.at(-1)) { bull++; reasons.push('Price is above EMA 50: broader bias is bullish.'); }
    else { bear++; reasons.push('Price is below EMA 50: broader bias is bearish.'); }
    if (x.rsi >= 52 && x.rsi < 70) { bull++; reasons.push('RSI shows positive momentum without being overbought.'); }
    else if (x.rsi <= 48 && x.rsi > 30) { bear++; reasons.push('RSI shows negative momentum without being oversold.'); }
    else reasons.push('RSI is neutral or at an extreme; no momentum point added.');
    if (x.mac > x.sig) { bull++; reasons.push('MACD is above its signal line.'); }
    else { bear++; reasons.push('MACD is below its signal line.'); }
    if (ps.some(p=>/Bullish|Hammer|Morning star|Three white/i.test(p))) { bull++; reasons.push('A bullish candle pattern was detected.'); }
    else if (ps.some(p=>/Bearish|Shooting star|Evening star|Three black/i.test(p))) { bear++; reasons.push('A bearish candle pattern was detected.'); }
    const threshold = Number($('threshold')?.value || 4);
    const score = Math.max(bull,bear);
    const signal = bull >= threshold && bull > bear ? 'CALL' : bear >= threshold && bear > bull ? 'PUT' : 'WAIT';
    const lv = levels(data);
    candles = saved;
    return {x,ps,bull,bear,score,signal,reasons,lv};
  }
  function safeText(el, value) { if (el) el.textContent = value; }
  function drawPro() {
    if (!candles || candles.length < 2) return;
    const cv=$('chart'), rect=cv.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
    if (!rect.width || !rect.height) return;
    cv.width=Math.round(rect.width*dpr);cv.height=Math.round(rect.height*dpr);
    const ctx=cv.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);
    const w=rect.width,h=rect.height,view=candles.slice(-75),x=indicators(),lv=levels(candles);
    let min=Math.min(...view.map(v=>v.low),lv.support),max=Math.max(...view.map(v=>v.high),lv.resistance);
    const pad=(max-min)*.12||.0001;min-=pad;max+=pad;
    const y=v=>h-23-(v-min)/(max-min)*(h-43),step=w/view.length;
    ctx.clearRect(0,0,w,h);ctx.strokeStyle='#1c2b41';ctx.lineWidth=1;
    for(let i=0;i<5;i++){const yy=12+i*(h-30)/4;ctx.beginPath();ctx.moveTo(0,yy);ctx.lineTo(w,yy);ctx.stroke()}
    view.forEach((a,i)=>{const xx=i*step+step/2,up=a.close>=a.open,col=up?'#2bd69b':'#ff637d';ctx.strokeStyle=col;ctx.fillStyle=col;ctx.beginPath();ctx.moveTo(xx,y(a.high));ctx.lineTo(xx,y(a.low));ctx.stroke();const top=y(Math.max(a.open,a.close)),bot=y(Math.min(a.open,a.close));ctx.fillRect(xx-Math.max(2,step*.28),top,Math.max(3,step*.56),Math.max(1,bot-top))});
    const line=(arr,col)=>{ctx.strokeStyle=col;ctx.lineWidth=1.5;ctx.beginPath();arr.slice(-view.length).forEach((v,i)=>{const xx=i*step+step/2,yy=y(v);i?ctx.lineTo(xx,yy):ctx.moveTo(xx,yy)});ctx.stroke()};
    line(x.e9,'#71a7ff');line(x.e21,'#f5c66a');
    const levelLine=(v,col,label)=>{if(!Number.isFinite(v))return;ctx.save();ctx.strokeStyle=col;ctx.setLineDash([5,4]);ctx.beginPath();ctx.moveTo(0,y(v));ctx.lineTo(w,y(v));ctx.stroke();ctx.setLineDash([]);ctx.fillStyle=col;ctx.font='10px system-ui';ctx.fillText(label+' '+v.toFixed(5),7,Math.max(12,y(v)-4));ctx.restore()};
    levelLine(lv.resistance,'#ff91a4','R');levelLine(lv.support,'#64e0b5','S');
  }
  function analyzePro() {
    if (!candles || candles.length < 30) { safeText($('signal'),'NEED MORE DATA'); return; }
    const r=evaluate(candles),last=candles.at(-1),x=r.x;
    safeText($('signal'),r.signal);$('signal').className=r.signal==='CALL'?'call':r.signal==='PUT'?'put':'neutral';
    safeText($('score'),r.score+'/5');$('meter').style.width=(r.score/5*100)+'%';
    $('reasons').replaceChildren();
    r.reasons.forEach(t=>{const d=document.createElement('div');d.className='reason';d.textContent=t;$('reasons').appendChild(d)});
    $('patterns').replaceChildren();
    (r.ps.length?r.ps:['No confirmed pattern on the latest candle']).forEach(t=>{const s=document.createElement('span');s.className='pill';s.textContent=t;$('patterns').appendChild(s)});
    safeText($('proPatternList'),'');
    const list=$('proPatternList');
    (r.ps.length?r.ps:['No clear pattern']).forEach(t=>{const s=document.createElement('span');s.className='pattern-chip '+(/Bullish|Hammer|Morning|soldiers/i.test(t)?'bull':/Bearish|Shooting|Evening|crows/i.test(t)?'bear':'neutral');s.textContent=t;list.appendChild(s)});
    safeText($('proResistance'),fmt(r.lv.resistance));safeText($('proSupport'),fmt(r.lv.support));
    safeText($('proStructureNote'),'Estimated from recent swing highs/lows over up to 50 candles; not guaranteed price barriers.');
    safeText($('rsi'),pct(x.rsi));safeText($('rsi2'),pct(x.rsi));
    safeText($('macd'),x.mac>x.sig?'Bullish':'Bearish');
    safeText($('trend'),x.e9.at(-1)>x.e21.at(-1)&&x.e21.at(-1)>x.e50.at(-1)?'Strong bullish':x.e9.at(-1)<x.e21.at(-1)&&x.e21.at(-1)<x.e50.at(-1)?'Strong bearish':'Mixed');
    safeText($('ema9'),fmt(x.e9.at(-1)));safeText($('ema21'),fmt(x.e21.at(-1)));safeText($('ema50'),fmt(x.e50.at(-1)));
    safeText($('macd2'),x.mac.toFixed(7)+' / '+x.sig.toFixed(7));
    safeText($('price'),fmt(last.close));safeText($('pairTitle'),$('pair').value+' · '+$('tf').value.toUpperCase());
    safeText($('count'),String(candles.length));
    if ($('delta') && !imported) $('delta').textContent='SYNTHETIC DEMO · NOT LIVE';
    drawPro();
  }
  function parseCSVPro(text) {
    const rows=[];let row=[],cell='',quoted=false;
    for(let i=0;i<text.length;i++){const ch=text[i];if(ch==='"'&&text[i+1]==='"'&&quoted){cell+='"';i++}else if(ch==='"'){quoted=!quoted}else if(ch===','&&!quoted){row.push(cell);cell=''}else if((ch==='\n'||ch==='\r')&&!quoted){if(ch==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(v=>v.trim()!==''))rows.push(row);row=[];cell=''}else cell+=ch}
    row.push(cell);if(row.some(v=>v.trim()!==''))rows.push(row);
    if(rows.length<2)throw Error('CSV has no candle rows.');
    const headers=rows.shift().map(v=>v.trim().toLowerCase().replace(/^\uFEFF/,''));
    const find=names=>headers.findIndex(h=>names.includes(h));
    const ix={time:find(['datetime','date','time','timestamp']),open:find(['open','o']),high:find(['high','h']),low:find(['low','l']),close:find(['close','c'])};
    if([ix.open,ix.high,ix.low,ix.close].some(v=>v<0))throw Error('CSV needs open, high, low and close columns. Add datetime or timestamp if available.');
    const parsed=rows.map((r,i)=>{
      const n=k=>Number(String(r[ix[k]]??'').trim());
      const o=n('open'),h=n('high'),l=n('low'),c=n('close');
      let time=ix.time>=0?String(r[ix.time]??'').trim():String(i);
      if(ix.time>=0&&/^\d{10,13}$/.test(time)){const num=Number(time);time=new Date(time.length===10?num*1000:num).toISOString()}
      return {datetime:time,open:o,high:h,low:l,close:c};
    }).filter(v=>[v.open,v.high,v.low,v.close].every(Number.isFinite)&&v.high>=Math.max(v.open,v.close)&&v.low<=Math.min(v.open,v.close)&&v.high>=v.low);
    if(parsed.length<30)throw Error('At least 30 valid OHLC candles are required. Check column names and values.');
    parsed.sort((a,b)=>{const x=Date.parse(a.datetime),y=Date.parse(b.datetime);return Number.isFinite(x)&&Number.isFinite(y)?x-y:0});
    return parsed;
  }
  function backtestPro() {
    const original=candles, min=Number($('threshold').value), outcomes=[];
    if(original.length<70){safeText($('btNote'),'Load at least 70 candles for a meaningful walk-forward test.');return}
    for(let i=60;i<original.length-1;i++){
      const result=evaluate(original.slice(0,i+1));
      if(result.signal==='WAIT')continue;
      const a=original[i],b=original[i+1],move=b.close-a.close;
      if(Math.abs(move)<1e-12)continue;
      outcomes.push(result.signal==='CALL'?move>0:move<0);
    }
    const wins=outcomes.filter(Boolean).length,n=outcomes.length,losses=n-wins,net=wins*.8-losses;
    safeText($('btTrades'),String(n));safeText($('btWin'),(n?wins/n*100:0).toFixed(1)+'%');
    safeText($('btNet'),net.toFixed(2));safeText($('btWL'),wins+' / '+losses);
    safeText($('btNote'),'Walk-forward, next-candle direction only. Assumes 0.8 unit net per win and 1 unit per loss; excludes spread, ties, latency, OTC payout changes and execution. Historical results do not predict future outcomes.');
  }

  // Replace the initial prototype's less complete calculations with the validated engine.
  window.calc = indicators;
  window.patterns = () => getPatterns(candles);
  window.analyze = analyzePro;
  window.draw = drawPro;
  window.parseCSV = parseCSVPro;
  window.backtest = backtestPro;
  $('analyze').onclick=analyzePro;
  $('refresh').onclick=()=>{makeDemo();analyzePro()};
  $('backtest').onclick=backtestPro;
  $('threshold').onchange=analyzePro;
  $('csv').onchange=async e=>{
    const file=e.target.files?.[0];if(!file)return;
    try{candles=parseCSVPro(await file.text());imported=true;analyzePro();safeText($('btNote'),'Imported '+candles.length+' valid candles from '+file.name+'. Run the walk-forward backtest to evaluate past signals.')}
    catch(err){alert('CSV import failed: '+err.message);e.target.value=''}
  };
  window.addEventListener('resize',()=>requestAnimationFrame(drawPro));
  // Re-run after the initial demo candles have been created by the legacy page script.
  if(candles.length)analyzePro();
})();