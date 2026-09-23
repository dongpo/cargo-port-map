export function filterEdges(edges,port='',direction='both'){
 return edges.filter(e=>!port||(direction==='inbound'?e.destination_id===port:direction==='outbound'?e.origin_id===port:e.origin_id===port||e.destination_id===port));
}
export function stats(edges){return {voyages:edges.reduce((n,e)=>n+e.voyage_count,0),ports:new Set(edges.flatMap(e=>[e.origin_id,e.destination_id])).size};}
// Spherical interpolation, split exactly at the antimeridian so no line crosses the map's center.
export function greatCircle(a,b,steps=64){
 const rad=Math.PI/180,vec=([x,y])=>[Math.cos(y*rad)*Math.cos(x*rad),Math.cos(y*rad)*Math.sin(x*rad),Math.sin(y*rad)];
 const u=vec(a),v=vec(b),omega=Math.acos(Math.max(-1,Math.min(1,u.reduce((s,x,i)=>s+x*v[i],0))));
 const points=[];
 for(let i=0;i<=steps;i++){
  const t=i/steps;let p;
  if(Math.abs(Math.sin(omega))<1e-8){let dx=b[0]-a[0];if(dx>180)dx-=360;if(dx< -180)dx+=360;p=[a[0]+dx*t,a[1]+(b[1]-a[1])*t];}
  else {const x=u.map((n,k)=>(Math.sin((1-t)*omega)*n+Math.sin(t*omega)*v[k])/Math.sin(omega));p=[Math.atan2(x[1],x[0])/rad,Math.atan2(x[2],Math.hypot(x[0],x[1]))/rad];}
  p[0]=((p[0]+540)%360)-180;points.push(p);
 }
 const parts=[[points[0]]];
 for(let i=1;i<points.length;i++){
  const prev=points[i-1],cur=points[i];
  if(Math.abs(cur[0]-prev[0])>180){const sign=prev[0]>0?1:-1,unwrapped=cur[0]+360*sign,t=(180*sign-prev[0])/(unwrapped-prev[0]),y=prev[1]+(cur[1]-prev[1])*t;parts.at(-1).push([180*sign,y]);parts.push([[-180*sign,y],cur]);}
  else parts.at(-1).push(cur);
 }
 return {type:'MultiLineString',coordinates:parts.filter(p=>p.length>=2)};
}
