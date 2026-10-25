/* Browser-native speech; no API key, no microphone capture until requested. */
(function(root){
'use strict';
function clean(text){return String(text||'').replace(/\[([^\]]+)\]\([^)]*\)/g,'$1').replace(/https?:\/\/\S+/g,'リンク').replace(/\/[A-Za-z][^\s。、]+/g,'保存先').replace(/[`#*<>]/g,'').replace(/\s+/g,' ').trim();}
function brief(task){const r=task.receipt||{};return clean((r.summary||task.result||task.blocker||task.next_action||'').slice(0,1400)).slice(0,420);}
function important(data,pid){const tasks=(data.tasks||[]).filter(t=>t.project_id===pid);const waiting=tasks.filter(t=>['確認待ち','保留'].includes(t.status));const pending=tasks.filter(t=>t.status!=='完了');const today=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());const due=pending.filter(t=>String(t.deadline||t.due_date||'').replaceAll('/','-').slice(0,10)===today);const p=(data.projects||[]).find(p=>p.id===pid);return clean((p?.name||'選択した案件')+'。未完了は'+pending.length+'件、確認待ちは'+waiting.length+'件です。'+(due.length?'本日期限は'+due.length+'件。'+due.slice(0,2).map(t=>t.title).join('。')+'。':'')+(waiting[0]?'確認が必要です。'+waiting[0].title+'。'+(waiting[0].blocker||''):'')+(pending[0]?'次の作業は、'+(pending[0].next_action||pending[0].title):'登録タスクは完了です。')).slice(0,600);}
const api={clean,brief,important};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
if(!root.document)return;
let enabled=false,armed=false,conversation=false,known=new Map(),first=true;try{enabled=localStorage.getItem('desk-speech')==='on';}catch{}
function notice(text){const n=document.querySelector('#voice-status');if(n)n.textContent=text;}
function stop(){root.speechSynthesis?.cancel();}
function say(text,done){if(!enabled||!armed||document.hidden)return;if(!root.speechSynthesis||!root.SpeechSynthesisUtterance){notice('読み上げ非対応のブラウザです。');return;}stop();const u=new SpeechSynthesisUtterance(clean(text));u.lang='ja-JP';u.rate=1;const voice=root.speechSynthesis.getVoices().find(v=>v.lang.startsWith('ja'));if(voice)u.voice=voice;u.onend=()=>{notice('読み上げ完了。マイクで続きの指示を話せます。');if(conversation&&!document.hidden)done?.();};u.onerror=()=>notice('再生できない場合は、もう一度読み上げボタンを押してください。');root.speechSynthesis.speak(u);notice('重要な箇所を読み上げています。');}
api.controls=function(data,pid){
 const el=document.createElement('div');el.className='speech-controls';
 const button=(label,fn)=>{const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=fn;el.append(b);return b;};
 const toggle=button(enabled?(armed?'🔊 読み上げ ON':'🔊 読み上げを再開'):'🔇 読み上げ OFF',()=>{if(enabled&&armed){enabled=false;armed=false;conversation=false;stop();}else{enabled=true;armed=true;say('読み上げをオンにしました。'+important(data,pid));}try{localStorage.setItem('desk-speech',enabled?'on':'off');}catch{}toggle.textContent=enabled?'🔊 読み上げ ON':'🔇 読み上げ OFF';});toggle.setAttribute('aria-pressed',String(enabled&&armed));
 button('重要なことを読む',()=>{enabled=true;armed=true;say(important(data,pid));});
 button('停止',()=>{conversation=false;stop();notice('読み上げを停止しました。');});
 const talk=button('会話モード '+(conversation?'ON':'OFF'),()=>{conversation=!conversation;if(conversation){enabled=true;armed=true;}talk.textContent='会話モード '+(conversation?'ON':'OFF');notice(conversation?'話した内容を選択中の案件へ自動送信します。外部操作の承認条件は維持されます。マイクで話し始めてください。':'音声入力は送信前に確認できます。');});talk.setAttribute('aria-label','音声の自動送信を切り替える');
 const status=document.createElement('p');status.id='voice-status';status.setAttribute('role','status');status.textContent='画面を開いている間に利用できます。音声認識はブラウザのサービスを使う場合があります。';el.append(status);return el;
};
api.isConversation=()=>conversation;
api.listen=()=>{stop();};
api.notify=function(data,pid,listening=false){
 if(listening||document.hidden)return;
 const relevant=(data.tasks||[]).filter(t=>t.project_id===pid&&!t.read_only);const news=[];
 for(const t of relevant){const marker=t.status+'|'+(t.receipt?.summary||t.result||'');if(!first&&known.has(t.id)&&known.get(t.id)!==marker&&['確認待ち','保留','完了'].includes(t.status))news.push(t);known.set(t.id,marker);}
 first=false;
 if(news.length&&!document.hidden)say(news.slice(-2).map(t=>t.title+'。'+brief(t)).join('。'),()=>document.querySelector('.voice-button')?.click());
};
document.addEventListener('visibilitychange',()=>{if(document.hidden){stop();conversation=false;}});
root.DeskVoice=api;
})(typeof window!=='undefined'?window:globalThis);
