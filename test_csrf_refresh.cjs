const fs=require('fs'),vm=require('vm'),assert=require('assert');
const src=fs.readFileSync(__dirname+'/static/app.js','utf8');
const fn=src.slice(src.indexOf('async function deskPost('),src.indexOf('async function api('));
let calls=[],meta={content:'stale'},fail=false;
const ctx={DOMParser:class{parseFromString(text){return {querySelector:()=>({content:text})}}},$:()=>meta,fetch:async(path,options)=>{calls.push({path,options});if(path==='/')return {ok:!fail,text:async()=> 'current'};assert.equal(options.headers['X-Desk-Token'],'current');return {ok:true};}};
vm.createContext(ctx);vm.runInContext(fn,ctx);
(async()=>{await ctx.deskPost('/api/tasks',{headers:{'Content-Type':'application/json'},body:'draft'});assert.equal(calls.length,2);assert.equal(meta.content,'current');assert.equal(calls[1].options.body,'draft');assert.equal(calls[0].options.mode,'same-origin');calls=[];fail=true;await assert.rejects(()=>ctx.deskPost('/api/tasks',{body:'draft'}));assert.equal(calls.length,1);console.log('PASS: stale token refreshed before one POST; failed refresh sends no POST; draft preserved');})();
