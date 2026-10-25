const assert=require('node:assert/strict');
const v=require('./static/voice.js');
assert.equal(v.clean('[資料](https://example.test/private) **完了**'),'資料 完了');
assert(!v.brief({result:'保存先 /Users/example/private/file.txt https://example.test/private'}).includes('/Users/'));
const data={projects:[{id:'p',name:'選択案件'},{id:'q',name:'他案件'}],tasks:[{project_id:'q',status:'確認待ち',title:'他案件の秘密',blocker:'読まない'},{project_id:'p',status:'未着手',title:'次の作業'}]};
assert(!v.important(data,'p').includes('他案件'));
assert(v.important(data,'p').includes('次の作業'));
assert(v.brief({result:'長文'.repeat(1000)}).length<=420);
console.log('音声要約: 案件限定・URL除去・長文制限の5検証OK');
