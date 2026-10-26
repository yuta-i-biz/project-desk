const assert=require('node:assert/strict');
const {capture}=require('./static/voice.js');
let recognizer;
class Speech{constructor(){recognizer=this;}start(){}stop(){}abort(){this.onend();}}
function setup(){let text,ended;const c=capture({Speech,onText:(f,i)=>text=[f,i],onEnd:r=>ended=r});return {c,get text(){return text},get ended(){return ended}};}
function result(s,final){const a=[{transcript:s}];a.isFinal=final;return a;}
let x=setup();recognizer.onresult({results:[result('調査',false)]});assert.deepEqual(x.text,['','調査']);recognizer.onresult({results:[result('調査して',true)]});recognizer.onresult({results:[result('調査して',true)]});recognizer.onend();assert.deepEqual(x.ended,{text:'調査して',submit:true});
x=setup();recognizer.onresult({results:[result('未確定',false)]});recognizer.onend();assert.equal(x.ended.submit,false);
x=setup();recognizer.onresult({results:[result('依頼',true)]});recognizer.onerror({error:'network'});recognizer.onend();assert.equal(x.ended.submit,false);
x=setup();recognizer.onresult({results:[result('依頼',true)]});x.c.cancel();assert.equal(x.ended.submit,false);
console.log('4 voice-input scenarios passed: interim/final deduplication, interim-only, error, cancellation');
