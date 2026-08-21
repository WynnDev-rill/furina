let memorySearchQuery='';
function filterMemory(value){memorySearchQuery=String(value||'').trim();renderMemory()}
function fuzzyItems(items,query,keys){
  if(!query||!window.Fuse)return items;
  const fuse=new window.Fuse(items,{keys,threshold:.38,ignoreLocation:true,useTokenSearch:true});
  return fuse.search(query).map(x=>x.item);
}
function renderMemory(){
  if(!memoryData)return;
  const labels={preference:'Preferensi',identity:'Identitas',profile:'Tentang kamu',goal:'Tujuan',user_note:'Catatan kamu',fact:'Fakta'},q=memorySearchQuery;
  const rows=fuzzyItems((memoryData.memories||[]).map(x=>({...x,_label:labels[x.kind]||'Memori'})),q,['text','_label']).slice(0,24);
  document.getElementById('memoryRows').innerHTML=rows.length?rows.map(x=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(x.text)}</div><div class="rowdesc">${esc(labels[x.kind]||'Memori')} · keyakinan ${Math.round((Number(x.confidence)||0)*100)}%</div></div><button class="btn" onclick="deleteMemory(${Number(x.id)})">Hapus</button></div>`).join(''):'<div class="empty">Tidak ada ingatan yang cocok.</div>';
  const beliefs=fuzzyItems((memoryData.beliefs||[]).map(x=>({...x,_label:labels[x.dimension]||x.dimension})),q,['value','dimension','_label']).slice(0,16);
  document.getElementById('beliefRows').innerHTML=beliefs.length?beliefs.map(x=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(labels[x.dimension]||x.dimension)}</div><div class="rowdesc">${esc(x.value)}</div></div><span class="badge">${esc(x.evidence||0)} bukti</span></div>`).join(''):'<div class="empty">Tidak ada pola yang cocok.</div>';
  const loops=fuzzyItems((memoryData.open_loops||[]).map(x=>({raw:x,text:typeof x==='string'?x:(x.text||x.title||JSON.stringify(x))})),q,['text']);
  document.getElementById('openLoops').innerHTML=loops.length?loops.map(x=>`<div class="row"><div class="rowmain"><div class="rowtitle">${esc(x.text)}</div></div></div>`).join(''):'<div class="empty">Tidak ada hal yang cocok.</div>';
}
