import {feature} from 'topojson-client';import fs from 'node:fs';
const world=JSON.parse(fs.readFileSync('node_modules/world-atlas/countries-50m.json'));
const geo=feature(world,world.objects.countries);
for(const f of geo.features){
 const polys=f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[f.geometry.coordinates],fixed=[];
 for(const poly of polys){
  // Unwrap quantized dateline rings, then repeat only crossing polygons on the other side.
  // The Antarctic polar cap intentionally spans all longitudes below the Mercator extent.
  if(poly[0].some(p=>p[1]<-89)){
   // world-atlas encodes Antarctica as a spherical cap with a coastal hole.
   // Convert that spherical representation to a planar Mercator coastline shell.
   const coast=poly[1].slice(0,-1),cut=coast.findIndex((p,i)=>i>0&&Math.abs(p[0]-coast[i-1][0])>180);
   const ring=[...coast.slice(cut),...coast.slice(0,cut)],start=ring[0],end=ring.at(-1);
   const first=start[0]<0?-180:180,last=-first;
   ring.unshift([first,start[1]]);ring.push([last,end[1]],[last,-85.051128],[first,-85.051128],ring[0]);
   fixed.push([ring]);continue;
  }
  const rings=poly.map(ring=>{const out=[ring[0].slice()];for(const p of ring.slice(1)){let x=p[0];const prev=out.at(-1)[0];while(x-prev>180)x-=360;while(x-prev< -180)x+=360;out.push([x,p[1]]);}return out;});
  fixed.push(rings);const xs=rings.flat().map(p=>p[0]);if(Math.max(...xs)>180)fixed.push(rings.map(r=>r.map(([x,y])=>[x-360,y])));if(Math.min(...xs)< -180)fixed.push(rings.map(r=>r.map(([x,y])=>[x+360,y])));
 }
 f.geometry={type:'MultiPolygon',coordinates:fixed};
}
fs.mkdirSync('public/basemap',{recursive:true});fs.writeFileSync('public/basemap/countries.geojson',JSON.stringify(geo));
