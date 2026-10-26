const assert=require('node:assert/strict');
const {visibleHeight}=require('./static/viewport.js');
assert.equal(visibleHeight(800,null),800);
assert.equal(visibleHeight(800,{height:420,scale:1}),420);
assert.equal(visibleHeight(800,{height:800,scale:1}),800);
assert.equal(visibleHeight(800,{height:400,scale:2}),800);
assert.equal(visibleHeight(600,{height:700,scale:1}),600);
console.log('Viewport: 5 checks passed');
