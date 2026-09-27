'use strict';
const $ = id => document.getElementById(id);
const state = {datasets: [], runs: [], dataset: null, run: null, series: '', page: 'overview', history: [], forecast: [], holdout: [], comparison: [], token: 0, polling: null, active: null};
const names = {seasonal_naive: 'Seasonal naive', moving_average: 'Moving average', ridge: 'Ridge regression', xgboost: 'XGBoost'};
const pages = {
 overview: ['Forecast overview', 'A clearer view of what’s next.', 'Understand demand. Compare the evidence. Make your next move.'],
 models: ['Model lab', 'Good predictions earn your trust.', 'Compare models on past windows, then inspect the untouched holdout.'],
 planner: ['Decision planner', 'Turn a forecast into a plan.', 'Explore demand, capacity, and inventory under explicit assumptions.'],
 data: ['Data workspace', 'Better decisions start here.', 'Import daily observations and inspect their quality and provenance.'],
 method: ['How it works', 'No black boxes. No hidden assumptions.', 'Understand the workflow, the metrics, and the limits of each prediction.']
};
const esc = value => String(value ?? '').replace(/[&<>"']/g, x => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[x]));
const num = (x, digits=0) => x == null ? '—' : Number(x).toLocaleString('en-US', {maximumFractionDigits:digits, minimumFractionDigits:digits});
const pct = x => x == null ? 'N/A' : `${num(x * 100, 1)}%`;
const date = x => new Date(`${x}T00:00:00`).toLocaleDateString('en-US', {month:'short',day:'numeric'});
const sum = (rows,key) => rows.reduce((a,b)=>a + b[key],0);
function notify(message, error=false) { $('notice').hidden=false; $('notice').textContent=message; $('notice').className=error?'error':''; }
function clearNotice() { $('notice').hidden=true; }
async function api(path, options={}) {
 const response = await fetch(`/api${path}`, options);
 if (!response.ok) {
  let message;
  try { const body=await response.json(); message=typeof body.detail==='string'?body.detail:JSON.stringify(body.detail); } catch { message=response.statusText; }
  throw new Error(message || `Request failed (${response.status})`);
 }
 return response.json();
}
const post = (path, body) => api(path, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function table(headers, rows) { return `<table><thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`; }
function kpi(label,value,sub,highlight=false,symbol='↗') { return `<div class="kpi ${highlight?'highlight':''}"><div class="kpi-symbol" aria-hidden="true">${symbol}</div><div class="kpi-label">${esc(label)}</div><div class="kpi-value">${esc(value)}</div><div class="kpi-sub">${esc(sub)}</div></div>`; }
function pageVisibility() {
 const ready = state.run?.status==='completed' && state.forecast.length>0;
 document.querySelectorAll('.page').forEach(el=>el.hidden=el.id!==`page-${state.page}` || (!ready && ['overview','models','planner'].includes(state.page)));
 $('empty-state').hidden=!!state.dataset || ['method','data'].includes(state.page);
 $('no-run').hidden=!state.dataset || ready || !!state.active || ['method','data'].includes(state.page);
 $('train-button').disabled=!state.dataset || !!state.active;
}
function navigate(page) {
 if (!pages[page]) page='overview';
 state.page=page;
 const [label,title,subtitle]=pages[page];
 $('breadcrumb').textContent=label; $('page-title').textContent=title; $('page-subtitle').textContent=subtitle;
 document.querySelectorAll('.nav-item').forEach(el=>{el.classList.toggle('active',el.dataset.page===page); el.setAttribute('aria-current',el.dataset.page===page?'page':'false'); el.title=pages[el.dataset.page][0]; el.setAttribute('aria-label',pages[el.dataset.page][0]);});
 pageVisibility();
 history.replaceState(null,'',`#${page}`);
 if(state.forecast.length){if(page==='overview')renderOverview();if(page==='models')renderModels();if(page==='planner')calculateScenario();}
}
function drawChart(id, rows, lines, {band=false, split=-1, title='Daily demand', yLabel='units / day'}={}) {
 const target=$(id); if(!rows.length){target.innerHTML='<p class="muted">No observations to display.</p>';return;}
 const W=Math.max(320,target.clientWidth||900),H=265,L=52,R=18,T=25,B=36;
 const values=rows.flatMap(r=>lines.map(l=>r[l.key]).concat(band?[r.lower,r.upper]:[])).filter(v=>typeof v==='number' && Number.isFinite(v));
 const maximum=Math.max(1,...values)*1.13;
 const x=i=>L+i*(W-L-R)/Math.max(1,rows.length-1), y=v=>H-B-v/maximum*(H-T-B);
 let content=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title><text x="${L}" y="12">${esc(yLabel)}</text>`;
 for(let i=0;i<=4;i++){const v=maximum*i/4;content+=`<line x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}" stroke="#edf0f5"/><text x="${L-12}" y="${y(v)+3}" text-anchor="end">${num(v)}</text>`;}
 const ticks=[...new Set((W<500?[0,.5,1]:[0,.2,.4,.6,.8,1]).map(f=>Math.round((rows.length-1)*f)))];
 for(const i of ticks) content+=`<text x="${x(i)}" y="${H-10}" text-anchor="${i===0?'start':i===rows.length-1?'end':'middle'}">${esc(date(rows[i].date))}</text>`;
 if(split>=0){content+=`<rect x="${x(split)}" y="${T}" width="${W-R-x(split)}" height="${H-T-B}" fill="#7860db" opacity=".025"/><line x1="${x(split)}" x2="${x(split)}" y1="${T}" y2="${H-B}" stroke="#c7bcea" stroke-dasharray="4 4"/><text x="${Math.min(x(split)+9,W-110)}" y="${T+12}" style="fill:#9a88c5;font-size:9px">FORECAST →</text>`;}
 if(band){const valid=rows.map((r,i)=>({r,i})).filter(o=>o.r.lower!=null); if(valid.length){let path=valid.map(o=>`${x(o.i)},${y(o.r.upper)}`).join(' ');path+=' '+[...valid].reverse().map(o=>`${x(o.i)},${y(o.r.lower)}`).join(' ');content+=`<polygon points="${path}" fill="#bda8f2" opacity=".24"/>`;}}
 for(const line of lines){let path='',inPath=false;rows.forEach((r,i)=>{if(r[line.key]==null){inPath=false;return;}path+=`${inPath?'L':'M'}${x(i).toFixed(2)},${y(r[line.key]).toFixed(2)} `;inPath=true;});content+=`<path d="${path}" fill="none" stroke="${line.color}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round" ${line.dash?'stroke-dasharray="5 4"':''}/>`;}
 content+='</svg><div class="chart-tooltip" role="status"></div>';
 target.innerHTML=content;
 const svg=target.querySelector('svg'), tooltip=target.querySelector('.chart-tooltip');
 svg.addEventListener('pointermove',event=>{const box=svg.getBoundingClientRect();const local=(event.clientX-box.left)/box.width*W;const i=Math.max(0,Math.min(rows.length-1,Math.round((local-L)/(W-L-R)*(rows.length-1))));const row=rows[i];tooltip.innerHTML=`<strong>${esc(row.date)}</strong>`+lines.filter(l=>row[l.key]!=null).map(l=>`<span>${esc(l.label)}: ${num(row[l.key],1)}</span>`).join('')+(band&&row.lower!=null?`<span>Band: ${num(row.lower,1)} – ${num(row.upper,1)}</span>`:'');tooltip.classList.add('visible');tooltip.style.left=`${Math.max(0,Math.min(event.clientX-box.left+12,box.width-tooltip.offsetWidth-5))}px`;tooltip.style.top='25px';});
 svg.addEventListener('pointerleave',()=>tooltip.classList.remove('visible'));
}
async function refreshDatasets(selectId=null) {
 state.datasets=await api('/datasets');
 $('dataset-select').innerHTML=state.datasets.length?state.datasets.map(d=>`<option value="${esc(d.id)}">${esc(d.name)}</option>`).join(''):'<option value="">No datasets yet</option>';
 const id=selectId || state.dataset?.id || state.datasets.find(d=>d.source==='synthetic-demo')?.id || state.datasets[0]?.id;
 if(id && state.datasets.some(d=>d.id===id)) { $('dataset-select').value=id; await selectDataset(id); }
 else { state.dataset=null; pageVisibility(); renderData(); }
}
async function selectDataset(id) {
 clearNotice(); state.token++; state.run=null; state.forecast=[];
 state.dataset=state.datasets.find(d=>d.id===id);
 if(!state.dataset) return;
 const series=state.dataset.quality.series;
 $('series-select').innerHTML=series.map(s=>`<option>${esc(s.series_id)}</option>`).join('');
 state.series=series[0].series_id;
 const q=state.dataset.quality;
 $('source-label').textContent=`${state.dataset.source==='synthetic-demo'?'SYNTHETIC DEMO':state.dataset.source==='public-dataset'?'PUBLIC HISTORICAL DATA':'UPLOADED DATA'} · ${num(q.rows)} daily observations · ${q.series_count} series`;
 await refreshRuns();
 await renderData();
 pageVisibility();
}
async function refreshRuns(preferred=null) {
 state.runs=await api('/runs');
 const available=state.runs.filter(r=>r.dataset_id===state.dataset?.id);
 $('run-select').innerHTML=available.length?available.map(r=>`<option value="${r.id}">${r.id.slice(0,8)} · ${r.horizon}d · ${r.status}</option>`).join(''):'<option value="">No runs</option>';
 const selected=available.find(r=>r.id===preferred) || available.find(r=>r.status==='completed') || available[0];
 if(selected){$('run-select').value=selected.id;await selectRun(selected.id);}else{state.run=null;state.forecast=[];}
 const active=state.runs.find(r=>['running','queued'].includes(r.status));
 if(active) pollRun(active.id);
 renderRuns();
}
async function selectRun(id) {
 const token=++state.token;
 const run=await api(`/runs/${id}`);
 if(token!==state.token)return;
 state.run=run;state.forecast=[];
 if(run.status==='completed') await loadSeries(token);
 else if(['queued','running'].includes(run.status)) pollRun(id);
 else notify(run.message,true);
 pageVisibility();
}
async function loadSeries(existingToken=null) {
 const token=existingToken??++state.token;
 if(state.run?.status!=='completed')return;
 const identity=state.run.id, series=encodeURIComponent(state.series), dataset=state.run.dataset_id;
 const [hist,forecast,holdout,comparison]=await Promise.all([
  api(`/datasets/${dataset}/history?series_id=${series}&limit=90`),
  api(`/runs/${identity}/forecast?series_id=${series}`),
  api(`/runs/${identity}/holdout?series_id=${series}`),
  api(`/runs/${identity}/comparison?series_id=${series}`)
 ]);
 if(token!==state.token)return;
 state.history=hist;state.forecast=forecast;state.holdout=holdout;state.comparison=comparison;
 pageVisibility();renderOverview();renderModels();
 if(state.page==='planner')await calculateScenario();
}
function seriesSummary(){return state.run?.summary?.series.find(s=>s.series_id===state.series);}
function renderOverview() {
 const f=state.forecast,h=state.history,s=seriesSummary(); if(!f.length||!s)return;
 const total=sum(f,'prediction'),avg=total/f.length,previous=sum(h.slice(-f.length),'value'),change=previous?(total/previous-1)*100:null;
 $('overview-kpis').innerHTML=kpi('Forecast demand',num(total),`Next ${f.length} days · ${state.series}`,true)+kpi('Average daily demand',num(avg),`Peak ${num(Math.max(...f.map(r=>r.prediction)))} units / day`)+kpi('Holdout WAPE',pct(s.holdout.wape),'Measured on unseen dates',false,'◈')+kpi('Selected model',names[s.model],`Chosen on 3 rolling windows`,false,'✓');
 $('overview-kpis').lastElementChild.querySelector('.kpi-value').style.fontSize='23px';
 $('forecast-title').textContent=`${state.series} · next ${f.length} days`;
 $('forecast-subtitle').textContent=`${date(f[0].date)} – ${date(f.at(-1).date)}, ${f[0].date.slice(0,4)} · last 60 observed days shown`;
 const hist=h.slice(-60),rows=hist.map(r=>({date:r.date,actual:r.value})).concat(f);
 rows[hist.length-1].prediction=hist.at(-1).value;
 drawChart('forecast-chart',rows,[{key:'actual',color:'#279a87',label:'Observed'},{key:'prediction',color:'#775ad8',label:'Forecast'}],{band:true,split:hist.length-1,title:`${state.series}: observed and forecast daily values`});
 const difference=s.baseline.mae?100*(1-s.holdout.mae/s.baseline.mae):null;
 const trend=change==null?'No nonzero prior-period total':`${num(Math.abs(change),1)}% ${change>=0?'above':'below'} the previous ${f.length} days`;
 const comparison=difference==null?'Baseline error is zero; relative improvement is undefined.':`Holdout MAE is ${num(Math.abs(difference),1)}% ${difference>=0?'lower':'higher'} than seasonal naive.`;
 $('insights').innerHTML=[['↗',trend,'This is a forecast-to-history comparison, not an observed growth rate.'],['◈',names[s.model]+' selected',comparison],['↔',pct(s.coverage)+' observed interval coverage','Nominal target: 80%. Coverage is measured only on the final holdout.']].map(([icon,title,body])=>`<div class="insight"><span class="insight-icon">${icon}</span><div><strong>${esc(title)}</strong><p>${esc(body)}</p></div></div>`).join('');
 $('forecast-table').innerHTML=table(['Date','Prediction','Lower band','Upper band','Model'],f.map(r=>`<tr><td>${esc(r.date)}</td><td>${num(r.prediction,1)}</td><td>${num(r.lower,1)}</td><td>${num(r.upper,1)}</td><td>${esc(names[r.model])}</td></tr>`));
 $('download-forecast').href=`/api/runs/${state.run.id}/download/forecast`;
}
function renderModels() {
 const s=seriesSummary(),run=state.run;if(!s)return;
 $('model-kpis').innerHTML=kpi('Holdout MAE',num(s.holdout.mae,1),'Average error in units',true,'◈')+kpi('Seasonal baseline MAE',num(s.baseline.mae,1),'Same holdout dates')+kpi('Observed coverage',pct(s.coverage),'Nominal interval level: 80%',false,'↔')+kpi('Holdout bias',num(s.holdout.bias,1),'Positive = overforecasting',false,'±');
 const rows=[...state.comparison].sort((a,b)=>a.mae-b.mae),max=Math.max(1,...rows.map(r=>r.mae));
 $('comparison-table').innerHTML=table(['Candidate','Selection MAE','Selection WAPE','Selection RMSE','Observations'],rows.map(r=>`<tr class="${r.selected?'chosen-row':''}"><td><strong>${esc(names[r.model])}</strong>${r.selected?'<span class="model-badge">Selected</span>':''}</td><td><div class="error-bar"><span style="width:${Math.round(r.mae/max*95)}px"></span>${num(r.mae,2)}</div></td><td>${pct(r.wape)}</td><td>${num(r.rmse,2)}</td><td>${r.n}</td></tr>`));
 const h=state.holdout;
 $('holdout-dates').textContent=`${h[0].date} to ${h.at(-1).date} · ${state.series} · ${names[s.model]}`;
 drawChart('holdout-chart',h,[{key:'actual',color:'#279a87',label:'Actual'},{key:'prediction',color:'#775ad8',label:'Selected model'},{key:'baseline',color:'#a5afc1',label:'Seasonal naive',dash:true}],{band:true,title:'Holdout actual values versus predictions'});
 $('fold-table').innerHTML=table(['Stage','Training through','Forecast starts','Forecast ends'],s.folds.map((f,i)=>`<tr><td><span class="tag">${i+1} · ${esc(f.purpose)}</span></td><td>${f.train_end}</td><td>${f.test_start}</td><td>${f.test_end}</td></tr>`));
 for(const kind of ['comparison','holdout','summary'])$(`download-${kind}`).href=`/api/runs/${run.id}/download/${kind}`;
}
async function calculateScenario(event=null) {
 event?.preventDefault(); if(!state.run||!state.forecast.length)return;
 const button=$('scenario-button');button.disabled=true;
 const token=state.token,run=state.run.id,series=state.series;
 try{
  const values={series_id:series,capacity:Number($('capacity').value),multiplier:Number($('multiplier').value),on_hand:Number($('on-hand').value),on_order:Number($('on-order').value),lead_days:Number($('lead-days').value),review_days:Number($('review-days').value),safety_stock:Number($('safety-stock').value)};
  const result=await post(`/runs/${run}/scenario`,values);
  if(token!==state.token)return;
  const c=result.capacity,i=result.inventory;
  $('planner-kpis').innerHTML=kpi('Expected demand',num(c.total_expected),`${state.forecast.length}-day scenario`,true)+kpi('Overloaded days',`${c.overloaded_days} / ${state.forecast.length}`,'Expected demand exceeds capacity',false,'!')+kpi('Unserved units',num(c.total_overflow),'Sum of daily expected overflow',false,'↗');
  drawChart('capacity-chart',c.days,[{key:'expected',color:'#775ad8',label:'Expected demand'},{key:'capacity',color:'#c78b43',label:'Capacity',dash:true}],{title:'Expected demand compared with daily capacity'});
  $('capacity-note').textContent=c.note;
  $('inventory-result').innerHTML=`<div class="inventory-numbers"><div><strong>${num(i.recommended_order)}</strong><span>Suggested order · units</span></div><div><strong>${num(i.target_stock)}</strong><span>Order-up-to target</span></div><div><strong>${num(i.inventory_position)}</strong><span>Current stock + on order</span></div></div><p class="small">Expected demand across ${i.protection_days} protection days: <strong>${num(i.expected_protection_demand)}</strong>. Potential pre-delivery shortfall, excluding existing inbound orders: <strong>${num(i.potential_shortfall_before_delivery)}</strong>.</p><p class="small muted">${esc(i.note)}</p>`;
  clearNotice();
 }catch(error){notify(error.message,true);$('planner-kpis').innerHTML='';$('capacity-chart').innerHTML='<p class="muted">Correct the scenario inputs to calculate results.</p>';$('inventory-result').innerHTML='';}
 finally{button.disabled=false;}
}
async function renderData() {
 if(!state.dataset){$('quality-content').innerHTML='<p class="muted">Import a CSV or load the demo to inspect data quality.</p>';$('data-table').innerHTML='';$('source-preview').innerHTML='';return;}
 const id=state.dataset.id;
 const detail=await api(`/datasets/${id}`);
 if(id!==state.dataset?.id)return;
 const q=detail.quality;
 $('dataset-title').textContent=detail.name;
 $('dataset-source').textContent=detail.source==='synthetic-demo'?'SYNTHETIC':detail.source==='public-dataset'?'PUBLIC DATA':'USER UPLOAD';
 $('quality-content').innerHTML=`<div class="quality-pills"><span class="quality-pill">✓ No duplicate keys</span><span class="quality-pill">✓ No missing days</span><span class="quality-pill">✓ Finite, nonnegative values</span></div><p class="source-info">${num(q.rows)} observations · ${q.series_count} series · Daily frequency<br>Imported ${esc(new Date(detail.created_at).toLocaleString())}<br>Input SHA-256: <code>${esc(q.sha256)}</code></p><p class="small muted">${q.warnings.map(esc).join(' ')}</p>${q.provenance?`<p class="source-info"><strong>Attribution:</strong> ${esc(q.provenance.citation)}<br>${esc(q.provenance.license)} · ${esc(q.provenance.transformation)}<br>${esc(q.provenance.limitation)}</p>`:''}`;
 $('data-table').innerHTML=table(['Series','Days','First date','Last date','Daily mean','Daily range'],detail.statistics.map(r=>`<tr><td>${esc(r.series_id)}</td><td>${num(r.days)}</td><td>${r.start}</td><td>${r.end}</td><td>${num(r.mean,1)}</td><td>${num(r.minimum)}–${num(r.maximum)}</td></tr>`));
 const preview=await api(`/datasets/${id}/history?series_id=${encodeURIComponent(state.series)}&limit=7`);
 if(id!==state.dataset?.id)return;
 $('source-preview').innerHTML=table(['Date','Series','Observed value'],preview.map(r=>`<tr><td>${r.date}</td><td>${esc(r.series_id)}</td><td>${num(r.value,1)}</td></tr>`));
 renderRuns();
}
function renderRuns(){const runs=state.runs.filter(r=>r.dataset_id===state.dataset?.id);$('runs-table').innerHTML=runs.length?table(['Run','Horizon','Status','Created','Artifacts'],runs.map(r=>`<tr><td>${r.id.slice(0,8)}</td><td>${r.horizon} days</td><td>${esc(r.status)}</td><td>${esc(new Date(r.created_at).toLocaleString())}</td><td>${r.status==='completed'?`<a href="/api/runs/${r.id}/download/summary">Summary ↗</a> · <a href="/api/runs/${r.id}/download/manifest">Provenance ↗</a>`:esc(r.message)}</td></tr>`)):'<p class="muted small">No runs for this dataset yet.</p>';}
function pollRun(id){
 if(state.active===id && state.polling)return;
 if(state.polling)clearTimeout(state.polling);
 state.active=id;$('training-state').hidden=false;pageVisibility();
 const tick=async()=>{
  try{const run=await api(`/runs/${id}`);$('training-message').textContent=run.message;
   if(['completed','failed'].includes(run.status)){state.active=null;state.polling=null;$('training-state').hidden=true;await refreshRuns(run.dataset_id===state.dataset?.id?id:null);pageVisibility();if(run.status==='failed')notify(run.message,true);else notify('Forecast complete. Results and holdout evaluation are ready.');return;}
   state.polling=setTimeout(tick,1000);
  }catch(error){state.active=null;state.polling=null;$('training-state').hidden=true;pageVisibility();notify(`Could not check training status: ${error.message}. Reload to reconnect.`,true);}
 };
 state.polling=setTimeout(tick,500);
}
$('dataset-select').addEventListener('change',event=>selectDataset(event.target.value).catch(e=>notify(e.message,true)));
$('series-select').addEventListener('change',async event=>{state.series=event.target.value;try{await loadSeries();await renderData();}catch(e){notify(e.message,true);}});
$('run-select').addEventListener('change',event=>selectRun(event.target.value).catch(e=>notify(e.message,true)));
$('train-button').addEventListener('click',async()=>{clearNotice();$('train-button').disabled=true;try{const run=await post('/runs',{dataset_id:state.dataset.id,horizon:Number($('horizon-select').value)});pollRun(run.id);}catch(e){notify(e.message,true);pageVisibility();}});
$('demo-button').addEventListener('click',async()=>{$('demo-button').disabled=true;try{const d=await post('/datasets/demo',{});await refreshDatasets(d.id);notify('Demo loaded. Click Run forecast to train and evaluate all four candidates.');}catch(e){notify(e.message,true);}finally{$('demo-button').disabled=false;}});
$('upload-form').addEventListener('submit',async event=>{event.preventDefault();const file=$('csv-file').files[0];if(!file)return;if(file.size>5*1024*1024){notify('CSV exceeds the 5 MiB limit.',true);return;}$('upload-button').disabled=true;try{const form=new FormData(event.target);const d=await api('/datasets',{method:'POST',body:form});await refreshDatasets(d.id);notify('Dataset validated and imported. Select a horizon to train your forecast.');}catch(e){notify(e.message,true);}finally{$('upload-button').disabled=false;}});
$('scenario-form').addEventListener('submit',calculateScenario);
$('multiplier').addEventListener('input',()=>{$('multiplier-label').textContent=`${Number($('multiplier').value).toFixed(2)}×`;});
$('import-shortcut').addEventListener('click',()=>navigate('data'));
$('download-template').addEventListener('click',()=>{const a=document.createElement('a');a.href='/static/example.csv';a.download='forecastlab-synthetic-example.csv';a.click();});
document.querySelectorAll('[data-page]').forEach(el=>el.addEventListener('click',()=>navigate(el.dataset.page)));
document.querySelectorAll('[data-goto]').forEach(el=>el.addEventListener('click',event=>{event.preventDefault();navigate(el.dataset.goto);}));
navigate(location.hash.slice(1)||'overview');
refreshDatasets().catch(error=>notify(`Could not load workspace: ${error.message}`,true));

let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(!state.forecast.length)return;if(state.page==='overview')renderOverview();if(state.page==='models')renderModels();if(state.page==='planner')calculateScenario();},150);});
