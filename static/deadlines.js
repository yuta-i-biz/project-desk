(function(root){
'use strict';
function day(v){const m=String(v||'').trim().match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[（(][月火水木金土日][)）])?$/);if(!m)return '';const s=m[1]+'-'+m[2].padStart(2,'0')+'-'+m[3].padStart(2,'0');const d=new Date(s+'T00:00:00Z');return !isNaN(+d)&&d.toISOString().slice(0,10)===s?s:'';}
function summarize(data,today,company='',query=''){
 const projects=new Map((data.projects||[]).map(p=>[p.id,p]));const groups=new Map();const seen=new Set();
 const wanted=p=>(!company||p.company===company);
 function entry(p){const c=p.company||'未分類';if(!groups.has(c))groups.set(c,{company:c,projects:new Map(),late:0,soon:0,unknown:0});const g=groups.get(c);if(!g.projects.has(p.id))g.projects.set(p.id,{id:p.id,name:p.name,tasks:[],late:0,soon:0,unknown:0});return [g,g.projects.get(p.id)];}
 for(const t of data.tasks||[]){const p=projects.get(t.project_id);if(!p||!wanted(p)||t.status==='完了'||seen.has(t.id))continue;seen.add(t.id);if(query&&!(p.name+' '+p.company+' '+t.title).toLowerCase().includes(query.toLowerCase()))continue;
 const due=day(t.due_date||t.deadline);const diff=due?(Date.parse(due+'T00:00:00Z')-Date.parse(today+'T00:00:00Z'))/86400000:null;const risk=!due?'期日不明':diff<0?'期限超過':diff===0?'本日期限':diff<=7?'7日以内':'今後';if(risk==='今後')continue;
 const [g,pj]=entry(p);const key=risk==='期限超過'?'late':risk==='期日不明'?'unknown':'soon';g[key]++;pj[key]++;pj.tasks.push({...t,due,risk,days_late:diff<0?-diff:0});
 }
 for(const p of projects.values()){if(p.reference_only||!wanted(p)||(query&&!(p.name+' '+p.company).toLowerCase().includes(query.toLowerCase())))continue;if(!(data.tasks||[]).some(t=>t.project_id===p.id)){const [,pj]=entry(p);pj.unassessed=true;}}
 return [...groups.values()].map(g=>({...g,projects:[...g.projects.values()].sort((a,b)=>b.late-a.late||b.soon-a.soon||a.name.localeCompare(b.name)).map(p=>({...p,tasks:p.tasks.sort((a,b)=>b.days_late-a.days_late||a.due.localeCompare(b.due))}))})).sort((a,b)=>b.late-a.late||a.company.localeCompare(b.company));
}
const api={day,summarize};if(typeof module!=='undefined')module.exports=api;root.DeskDeadlines=api;
})(typeof window!=='undefined'?window:globalThis);
