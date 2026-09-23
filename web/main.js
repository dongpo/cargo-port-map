import * as maplibregl from 'maplibre-gl';
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url';
maplibregl.setWorkerUrl(workerUrl);
import 'maplibre-gl/dist/maplibre-gl.css';
import './style.css';
import {filterEdges,stats,greatCircle} from './model.js';
const assetPath=path=>`${import.meta.env.BASE_URL}${path.replace(/^\//,'')}`;
const $=id=>document.getElementById(id),fmt=n=>new Intl.NumberFormat('en').format(n);
let ports=[],byId=new Map(),edges=[],selected='',direction='both',manifest,requestId=0,popup;
const empty={type:'FeatureCollection',features:[]};
const map=new maplibregl.Map({container:'map',center:[35,19],zoom:1.55,minZoom:0,maxZoom:14,renderWorldCopies:false,
 style:{version:8,sources:{basemap:{type:'geojson',data:assetPath('basemap/countries.geojson'),attribution:'Natural Earth · public domain'}},layers:[{id:'ocean',type:'background',paint:{'background-color':'#091c27'}},{id:'land',type:'fill',source:'basemap',paint:{'fill-color':'#20343c'}},{id:'boundaries',type:'line',source:'basemap',paint:{'line-color':'#3d5157','line-width':.5}}]},attributionControl:true});
map.addControl(new maplibregl.NavigationControl({showCompass:false}),'top-right');
map.addControl(new maplibregl.ScaleControl({unit:'nautical'}),'bottom-right');
let tileError=false;
map.on('error',()=>{if(!tileError){tileError=true;$('notice').hidden=false;$('notice').textContent='A map resource could not load. Reload the page or check the local server.';}});
function worldView(duration=0){map.fitBounds([[-180,-58],[180,75]],{padding:{top:130,bottom:60,left:25,right:25},duration});}
const mapReady=new Promise(resolve=>map.on('load',()=>{worldView();resolve();}));
async function json(path){const r=await fetch(assetPath(path));if(!r.ok)throw new Error('Processed data unavailable. Run the ETL build and reload.');return r.json();}
function label(p){return p?.name||p?.id||'Unknown port';}
function notice(s){$('notice').hidden=!s;$('notice').textContent=s;}
function updatePortOptions(){const q=$('search').value.toLowerCase(),filtered=ports.filter(p=>`${label(p)} ${p.flag||''} ${p.id}`.toLowerCase().includes(q));$('port').replaceChildren(new Option('All observed ports',''));for(const p of filtered)$('port').add(new Option(`${label(p)} · ${p.flag||'—'}`,p.id));if(selected&&!filtered.some(p=>p.id===selected)){$('port').add(new Option(label(byId.get(selected)),selected));}$('port').value=selected;}
function choosePort(id,fly=true){selected=id;$('port').value=id;popup?.remove();if(id&&fly){const p=byId.get(id);map.flyTo({center:[p.longitude,p.latitude],zoom:3.7,duration:900});}render();}
function showRoute(e){popup?.remove();const o=byId.get(e.origin_id),d=byId.get(e.destination_id);const box=document.createElement('div');box.className='route-popup';const title=document.createElement('strong');title.textContent=`${label(o)} → ${label(d)}`;const count=document.createElement('p');count.textContent=`${fmt(e.voyage_count)} observed vessel voyages`;const detail=document.createElement('small');detail.textContent=`${$('month').selectedOptions[0].textContent} · Cargo only\nPort-pair connection; not a sailed track.`;box.append(title,count,detail);popup=new maplibregl.Popup({maxWidth:'320px'}).setLngLat([d.longitude,d.latitude]).setDOMContent(box).addTo(map);}
function render(){
 const visible=filterEdges(edges,selected,direction),s=stats(visible),active=new Set(visible.flatMap(e=>[e.origin_id,e.destination_id]));
 $('voyage-count').textContent=fmt(s.voyages);$('port-count').textContent=fmt(s.ports);$('connection-count').textContent=fmt(visible.length);
 $('connections-title').textContent=selected?label(byId.get(selected)):'Top connections';
 $('selection-note').textContent=selected?`${direction==='both'?'Inbound + outbound':direction} · ${$('month').selectedOptions[0].textContent}`:'Ranked by observed vessel voyages.';
 const drawn=[...visible].sort((a,b)=>b.voyage_count-a.voyage_count).slice(0,3000);
 const max=drawn.reduce((n,e)=>Math.max(n,e.voyage_count),1),widthScale=9/max;
 map.getSource('routes').setData({type:'FeatureCollection',features:drawn.map(e=>({type:'Feature',properties:{...e,inbound:selected&&e.destination_id===selected?1:0},geometry:greatCircle([byId.get(e.origin_id).longitude,byId.get(e.origin_id).latitude],[byId.get(e.destination_id).longitude,byId.get(e.destination_id).latitude])}))});
 map.setPaintProperty('routes','line-width',['*',['get','voyage_count'],widthScale]);
 map.getSource('ports').setData({type:'FeatureCollection',features:ports.filter(p=>active.has(p.id)||p.id===selected).map(p=>({type:'Feature',properties:{id:p.id,name:label(p),selected:p.id===selected?1:0},geometry:{type:'Point',coordinates:[p.longitude,p.latitude]}}))});
 $('map-title').textContent=selected?`${label(byId.get(selected))} connections`:$('month').value==='all'?'A year of connections':$('month').selectedOptions[0].textContent;
 $('map-subtitle').textContent=`${fmt(visible.length)} directed port pairs${visible.length>3000?' · strongest 3,000 drawn':''} · ${manifest.is_sample?'Live-data cohort':'Global query'} · ${manifest.year}`;
 $('map-caption').textContent=`${manifest.is_sample?`${manifest.cohort_vessels} cargo vessels in sample`:'Global cargo query'}  /  ${fmt(manifest.events)} source visits  /  ${manifest.dataset.split(':')[1]}`;
 $('connections-list').replaceChildren();
 for(const e of [...visible].sort((a,b)=>b.voyage_count-a.voyage_count).slice(0,10)){
  const btn=document.createElement('button');btn.className='connection';const name=document.createElement('span');name.textContent=`${label(byId.get(e.origin_id))} → ${label(byId.get(e.destination_id))}`;const n=document.createElement('b');n.textContent=fmt(e.voyage_count);btn.append(name,n);btn.onclick=()=>showRoute(e);$('connections-list').append(btn);
 }
 if(!visible.length){const p=document.createElement('p');p.className='empty';p.textContent='No observed voyages for this selection. Try another month or port.';$('connections-list').append(p);}
 document.querySelectorAll('[data-direction]').forEach(b=>{b.classList.toggle('active',b.dataset.direction===direction);b.disabled=!selected&&b.dataset.direction!=='both';});
 window.__cargoReady=true;
}
async function changePeriod(){const current=++requestId;popup?.remove();try{const data=await json(`/data/${$('month').value}.json`);if(current!==requestId)return;edges=data.edges;render();}catch(e){notice(e.message);}}
try{
 [manifest,ports]=await Promise.all([json('/data/manifest.json'),json('/data/ports.json')]);byId=new Map(ports.map(p=>[p.id,p]));ports.sort((a,b)=>label(a).localeCompare(label(b)));
 $('coverage').textContent=manifest.is_sample?'LIVE DATA · VESSEL COHORT SAMPLE':'LIVE DATA · COMPLETE GLOBAL QUERY';$('coverage').title=manifest.sample_method||'Complete API extraction for the stated window. AIS coverage remains incomplete.';
 $('year-label').textContent=manifest.year;$('month').options[0].textContent=`Full year · ${manifest.year}`;
 for(let m=1;m<=12;m++)$('month').add(new Option(new Intl.DateTimeFormat('en',{month:'long',year:'numeric',timeZone:'UTC'}).format(new Date(Date.UTC(manifest.year,m-1,1))),`${manifest.year}-${String(m).padStart(2,'0')}`));
 updatePortOptions();await mapReady;
 map.addSource('routes',{type:'geojson',data:empty});map.addSource('ports',{type:'geojson',data:empty});
 map.addLayer({id:'routes',type:'line',source:'routes',paint:{'line-color':['case',['==',['get','inbound'],1],'#ffbd72','#4cddc3'],'line-opacity':.6,'line-width':1}});
 map.addLayer({id:'route-hit',type:'line',source:'routes',paint:{'line-width':14,'line-opacity':0}});
 map.addLayer({id:'ports',type:'circle',source:'ports',paint:{'circle-radius':['case',['==',['get','selected'],1],7,3.5],'circle-color':['case',['==',['get','selected'],1],'#ffffff','#80edda'],'circle-stroke-color':'#143c45','circle-stroke-width':1.5}});
 map.on('click','ports',e=>choosePort(e.features[0].properties.id));
 map.on('click','route-hit',e=>{if(map.queryRenderedFeatures(e.point,{layers:['ports']}).length)return;showRoute(e.features[0].properties);});
 for(const l of ['ports','route-hit']){map.on('mouseenter',l,()=>map.getCanvas().style.cursor='pointer');map.on('mouseleave',l,()=>map.getCanvas().style.cursor='');}
 $('month').onchange=changePeriod;$('port').onchange=()=>choosePort($('port').value);$('search').oninput=updatePortOptions;
 document.querySelectorAll('[data-direction]').forEach(b=>b.onclick=()=>{direction=b.dataset.direction;popup?.remove();render();});
 $('reset').onclick=()=>{popup?.remove();document.querySelector('aside').scrollTo({top:0,behavior:'smooth'});selected='';direction='both';$('search').value='';updatePortOptions();worldView(700);render();};
 await changePeriod();
}catch(e){notice(e.message);$('coverage').textContent='DATA UNAVAILABLE';}
