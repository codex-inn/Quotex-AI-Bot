(() => {
  const base = (window.QUOTEX_API_BASE || '').replace(/\/$/, '');
  const controls = document.querySelector('.controls');
  const source = document.createElement('div'); source.className='field';
  source.innerHTML='<label>Market source</label><select id="marketSource"><option value="spot">Live spot Forex</option><option value="otc">Quotex OTC</option></select>';
  const cadence=document.createElement('div'); cadence.className='field';
  cadence.innerHTML='<label>Target update</label><select id="liveCadence"><option value="1000">1 second (if feed permits)</option><option value="5000">5 seconds</option><option value="10000">10 seconds</option></select>';
  controls.insertBefore(source,controls.firstChild); controls.insertBefore(cadence,controls.children[2]);
  const pair=$('pair'),tf=$('tf');
  const spotPairs=Array.from(pair.options).map(o=>({value:o.value,label:o.textContent}));
  const spotFrames=Array.from(tf.options).map(o=>({value:o.value,label:o.textContent}));
  const liveStatus=document.createElement('span'); liveStatus.className='pill'; liveStatus.id='liveStatus'; liveStatus.textContent='LIVE: NOT CONNECTED'; document.querySelector('header .status').appendChild(liveStatus);
  let socket=null,lastTick=0,lastPrice=null,timer=null,generation=0,otcEnabled=false;
  const status=(s,c)=>{liveStatus.textContent=s;liveStatus.style.color=c||'#a9bdd5'};
  const market=()=>document.getElementById('marketSource').value;
  const interval=()=>({'1m':'1min','5m':'5min','15m':'15min'})[tf.value]||'1min';
  const bucketSize=()=>({'1min':60000,'5min':300000,'15min':900000})[interval()];
  function stop(){generation++;if(socket){socket.onclose=null;socket.close();socket=null}if(timer){clearInterval(timer);timer=null}lastTick=0}
  function notice(msg){const box=document.querySelector('.notice');box.textContent='';const b=document.createElement('b');b.textContent='Live data: ';box.append(b,document.createTextNode(msg+' Analysis is rule-based, not predictive certainty. No trades are placed.'))}
  function configureChoices(){
    pair.replaceChildren(); tf.replaceChildren();
    const pairs=market()==='otc'?(otcEnabled?[{value:'EURUSD_otc',label:'EUR/USD OTC'}]:[]):spotPairs;
    const frames=market()==='otc'?(otcEnabled?[{value:'1m',label:'1 minute (60 seconds)'}]:[]):spotFrames;
    for(const x of pairs)pair.add(new Option(x.label,x.value));
    for(const x of frames)tf.add(new Option(x.label,x.value));
    pair.disabled=market()==='otc'&&!otcEnabled;tf.disabled=market()==='otc'&&!otcEnabled;
    if(market()==='otc'&&!otcEnabled){status('OTC NOT CONFIGURED','#f5c66a');notice('OTCharts is not configured on the backend. Set its private backend secret to enable the supported OTC pair.');}
  }
  async function pollOtc(g){
    const url=base+'/api/otc/candles?symbol='+encodeURIComponent(pair.value)+'&tf=60&limit=160';
    const res=await fetch(url),data=await res.json();if(!res.ok)throw Error(data.detail||'OTC candle request failed');if(g!==generation)return;
    if(!Array.isArray(data.values)||!data.values.length)throw Error('No OTC candles were returned');
    candles=data.values;imported=true;lastPrice=candles.at(-1).close;analyze();
    $('delta').textContent='QUOTEX OTC · REST';$('delta').style.color='#2bd69b';
    status('OTC CANDLES · '+new Date().toLocaleTimeString(),'#2bd69b');
    notice('Loaded '+candles.length+' OTCharts Quotex OTC candles. The app polls this REST endpoint every 60 seconds; it is not a tick stream or WebSocket feed.');
  }
  async function connectOtc(){
    stop();const g=generation;
    if(!base){status('BACKEND URL REQUIRED','#f5c66a');notice('Deploy the backend, add OTCHARTS_API_KEY in its private secret settings, and set the backend URL in config.js.');return}
    if(!otcEnabled){status('OTC NOT CONFIGURED','#f5c66a');return}
    status('LOADING OTC CANDLES…','#f5c66a');
    try{await pollOtc(g);if(g!==generation)return;timer=setInterval(async()=>{try{await pollOtc(g)}catch(e){if(g===generation){status('OTC POLL FAILED','#ff637d');notice('OTCharts REST candle polling failed: '+e.message)}}},60000)}
    catch(e){if(g===generation){status('OTC LOAD FAILED','#ff637d');notice('Could not load Quotex OTC candles: '+e.message+'. Check the backend secret and provider access.')}}
  }
  function tick(price,timestamp){const p=Number(price),t=Number(timestamp);if(!Number.isFinite(p)||!Number.isFinite(t))return;const d=new Date(t>1e12?t:t*1000);if(Number.isNaN(d.getTime()))return;const size=bucketSize(),bucket=Math.floor(d.getTime()/size)*size,key=new Date(bucket).toISOString();let c=candles.at(-1);let cb=c?Math.floor(new Date(String(c.datetime).replace(' ','T')+(String(c.datetime).includes('Z')?'':'Z')).getTime()/size)*size:0;if(!c||cb!==bucket){candles.push({datetime:key,open:lastPrice??p,high:p,low:p,close:p});if(candles.length>500)candles.shift()}else{c.high=Math.max(c.high,p);c.low=Math.min(c.low,p);c.close=p}lastPrice=p;lastTick=Date.now();imported=true;analyze();$('delta').textContent='LIVE SPOT FX';$('delta').style.color='#2bd69b';status('LIVE · '+new Date().toLocaleTimeString(),'#2bd69b')}
  async function connectSpot(){
    stop();const g=generation;
    if(!base){status('BACKEND URL REQUIRED','#f5c66a');notice('Demo mode is active. Deploy the backend, add your Twelve Data key to its secret settings, and set the backend URL in config.js.');return}
    status('CONNECTING…','#f5c66a');
    try{const url=base+'/api/candles?symbol='+encodeURIComponent(pair.value)+'&interval='+interval()+'&outputsize=160';const res=await fetch(url),data=await res.json();if(!res.ok)throw Error(data.detail||'Candle request failed');if(g!==generation)return;candles=data.values;imported=true;lastPrice=candles.at(-1).close;analyze();notice('Loaded '+candles.length+' '+interval()+' spot-FX candles from Twelve Data. Provider WebSocket ticks update the active candle; actual tick frequency depends on plan, symbol permissions and provider delivery.');const ws=base.replace(/^http/,'ws')+'/ws?symbol='+encodeURIComponent(pair.value);socket=new WebSocket(ws);socket.onopen=()=>{if(g===generation)status('STREAM CONNECTING…','#f5c66a')};socket.onmessage=e=>{if(g!==generation)return;let m;try{m=JSON.parse(e.data)}catch{return}if(m.event==='subscribing')status('SUBSCRIBING…','#f5c66a');else if(m.event==='subscribe-status'){if(m.status==='ok'&&m.success&&m.success.length)status('STREAM LIVE','#2bd69b');else{status('SUBSCRIPTION FAILED','#ff637d');notice('The provider did not confirm this Forex pair subscription. Check plan and symbol entitlement.')}}else if(m.event==='price')tick(m.price,m.timestamp);else if(m.event==='error'){status('PROVIDER ERROR','#ff637d');notice('Provider error: '+(m.message||'unknown')+'. Check API plan, symbol access and backend logs.')}};socket.onerror=()=>{if(g===generation)status('STREAM ERROR','#ff637d')};socket.onclose=()=>{if(g===generation)status('STREAM DISCONNECTED','#ff637d')};timer=setInterval(()=>{const target=Number($('liveCadence').value);if(lastTick&&Date.now()-lastTick>Math.max(15000,target*5))status('STALE · WAITING FOR TICK','#f5c66a')},1000)}catch(e){if(g!==generation)return;status('DATA LOAD FAILED','#ff637d');notice('Could not load live spot-FX candles: '+e.message+'. Check backend, API key, permissions and CORS.')}}
  async function configureOtc(){
    if(!base){otcEnabled=false;configureChoices();return}
    try{const res=await fetch(base+'/health');const data=await res.json();otcEnabled=Array.isArray(data.otc_supported_symbols)&&data.otc_supported_symbols.includes('EURUSD_otc')&&data.otc_supported_timeframes_seconds?.includes(60)&&data.quotex_otc==='available'}
    catch{otcEnabled=false}
    configureChoices();
  }
  async function changeMarket(){stop();await configureOtc();if(market()==='otc')connectOtc();else{configureChoices();connectSpot()}}
  $('marketSource').addEventListener('change',changeMarket);
  $('liveCadence').addEventListener('change',()=>{if(lastTick)status('LIVE · TARGET '+Number($('liveCadence').value)/1000+'s','#2bd69b')});
  pair.addEventListener('change',()=>{if(base)market()==='otc'?connectOtc():connectSpot()});
  tf.addEventListener('change',()=>{if(base)market()==='otc'?connectOtc():connectSpot()});
  $('refresh').addEventListener('click',()=>{if(base)market()==='otc'?connectOtc():connectSpot()});
  configureOtc().then(()=>{configureChoices();if(base)connectSpot();else{status('DEMO · LIVE NOT CONFIGURED','#f5c66a');notice('Demo mode is active. Deploy the backend and configure provider keys as private backend secrets. Quotex OTC availability requires OTCHARTS_API_KEY.')}});
})();