/* Advice only: task text never grants execution authority. */
(function(root){'use strict';
const labels={human:'あなたの判断・操作',ai:'AI側の確認・復旧',unknown:'担当・次の一手を確認',active:'進行記録あり',done:'完了'};
function classify(t){
 if(t.status==='完了')return {owner:'done',reason:'完了として記録済み'};
 const r=t.receipt||{},review=r.review?.status;
 if(r.execution_status==='failed'||['issues','unverified'].includes(review))return {owner:'ai',reason:review==='issues'?'検品で修正が必要':review==='unverified'?'品質確認が未完了':'実行が停止しています'};
 if(t.needs_check)return {owner:'ai',reason:'作業記録が古く、実行継続を確認する必要があります'};
 if(['作業中','実行中'].includes(t.status))return {owner:'active',reason:'作業中の記録です。常時実行を保証するものではありません'};
 // Human action requires an explicit blocker, not an inferred task title.
 const b=String(t.blocker||'');
 if(!/不要|必要なし|完了済/.test(b)&&/実機|実マイク|本人.*(操作|判断|確認)|今川さん.*(操作|判断|確認)|承認待ち|コピー承認/.test(b))return {owner:'human',reason:b};
 if(/接続|認証|エラー|失敗|未検証|再現試験|検査|検証/.test(b))return {owner:'ai',reason:b};
 if(r.execution_status==='succeeded'&&['reviewed','not_required'].includes(review)&&t.status==='確認待ち')return {owner:'human',reason:'成果物を確認し、採用するか判断してください'};
 return {owner:'unknown',reason:b||'担当と次の作業が明示されていません'};
}
function dateKey(value){return /^\d{4}-\d{2}-\d{2}$/.test(value||'')&&!Number.isNaN(Date.parse(value+'T00:00:00Z'))&&new Date(value+'T00:00:00Z').toISOString().slice(0,10)===value?value:null;}
function list(tasks,today){return tasks.filter(t=>t.status!=='完了').map(t=>{const due=dateKey(t.due_date);return {task:t,...classify(t),due,risk:due&&due<today?'期限超過':due===today?'本日期限':due?'期限あり':'期日未設定'};}).sort((a,b)=>(a.due||'9999').localeCompare(b.due||'9999')||String(a.task.id).localeCompare(String(b.task.id)));}
const api={classify,list,labels};if(typeof module!=='undefined')module.exports=api;else root.DeskActions=api;
})(typeof window!=='undefined'?window:globalThis);
