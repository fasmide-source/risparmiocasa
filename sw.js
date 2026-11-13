// Service worker RisparmioCasa: cache offline + controllo giornaliero (Periodic Background Sync, Chrome Android con app installata)
const CACHE="rc-v7";
const SHELL=["./","index.html","manifest.json","icons/icon-192.png","icons/icon-512.png"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)));self.skipWaiting()});
self.addEventListener("activate",e=>e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim())));
self.addEventListener("fetch",e=>{
  const u=new URL(e.request.url);
  if(u.origin!==location.origin)return;
  if(u.pathname.endsWith(".json")||u.pathname.endsWith(".html")||u.pathname.endsWith("/")){ // rete prima, cache come riserva
    const key=u.pathname;
    e.respondWith(fetch(e.request).then(r=>{const cl=r.clone();caches.open(CACHE).then(c=>c.put(key,cl));return r}).catch(()=>caches.match(key).then(r=>r||caches.match("index.html"))));
    return;
  }
  e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request)));
});
async function dailyCheck(){
  try{
    const r=await fetch("data/feed.json?t="+Date.now(),{cache:"no-store"}); if(!r.ok)return;
    const j=await r.json(); const c=await caches.open(CACHE);
    const prev=await c.match("rc-last-update"); const last=prev?await prev.text():"";
    if(j.updated && j.updated!==last){
      await c.put("rc-last-update",new Response(j.updated));
      const n=(j.items||[]).filter(i=>!last||i.found>last).length;
      if(n) await self.registration.showNotification("RisparmioCasa",{body:n+" nuove opportunità di risparmio",icon:"icons/icon-192.png",tag:"rc-daily"});
    }
  }catch(e){}
}
self.addEventListener("periodicsync",e=>{if(e.tag==="rc-daily")e.waitUntil(dailyCheck())});
self.addEventListener("notificationclick",e=>{e.notification.close();e.waitUntil(clients.openWindow("./"))});
