// Service worker RisparmioCasa: cache offline + controllo giornaliero (Periodic Background Sync, Chrome Android con app installata)
const CACHE="rc-v1";
const SHELL=["./","index.html","manifest.json","icons/icon-192.png","icons/icon-512.png"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)));self.skipWaiting()});
self.addEventListener("activate",e=>e.waitUntil(self.clients.claim()));
self.addEventListener("fetch",e=>{
  const u=new URL(e.request.url);
  if(u.origin!==location.origin)return;
  if(u.pathname.endsWith("feed.json")){ // rete prima, cache come riserva
    e.respondWith(fetch(e.request).then(r=>{const cl=r.clone();caches.open(CACHE).then(c=>c.put("data/feed.json",cl));return r}).catch(()=>caches.match("data/feed.json")));
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
