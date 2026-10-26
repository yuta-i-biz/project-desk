/* Use the visible phone viewport when its keyboard reduces available space. */
(function(root){
 'use strict';
 function visibleHeight(innerHeight,viewport){
  if(!viewport||Math.abs((viewport.scale||1)-1)>.05)return innerHeight;
  return Math.max(1,Math.min(innerHeight,viewport.height));
 }
 if(typeof module!=='undefined')module.exports={visibleHeight};
 if(!root.document)return;
 let frame;
 const update=()=>{root.cancelAnimationFrame(frame);frame=root.requestAnimationFrame(()=>{
  root.document.documentElement.style.setProperty('--desk-viewport-height',visibleHeight(root.innerHeight,root.visualViewport)+'px');
 });};
 root.addEventListener('resize',update);
 root.visualViewport?.addEventListener('resize',update);
 update();
})(typeof window!=='undefined'?window:globalThis);
