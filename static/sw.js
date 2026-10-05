/* Elite Baseball League — PWA service worker
   Static shell only. API/game/account traffic is intentionally never cached. */
const CACHE_NAME='ebl-shell-v4-rc135';
const SHELL=["/","/index.html","/manifest.webmanifest","/assets/ebl_logo.png","/ebl.css","/ebl-feedback.js","/ebl-core.js","/ebl-profile.js","/ebl-actions.js","/ebl-commands.js","/ebl-appearance.js","/ebl-franchise.js","/ebl-creator.js","/ebl-gamecast.js","/ebl-app-shell.js"];


self.addEventListener('install',event=>{
  event.waitUntil((async()=>{
    const cache=await caches.open(CACHE_NAME);
    await Promise.allSettled(SHELL.map(url=>cache.add(new Request(url,{cache:'reload'}))));
    await self.skipWaiting();
  })());
});


self.addEventListener('activate',event=>{
  event.waitUntil((async()=>{
    const keys=await caches.keys();
    await Promise.all(keys.filter(k=>k.startsWith('ebl-shell-')&&k!==CACHE_NAME).map(k=>caches.delete(k)));
    await self.clients.claim();
  })());
});


self.addEventListener('fetch',event=>{
  const req=event.request;
  if(req.method!=='GET')return;
  const url=new URL(req.url);
  if(url.origin!==self.location.origin)return;
  if(url.pathname.startsWith('/api/'))return;


  if(req.mode==='navigate'){
    event.respondWith((async()=>{
      try{
        const fresh=await fetch(req);
        if(fresh && fresh.ok){
          const cache=await caches.open(CACHE_NAME);
          cache.put('/index.html',fresh.clone()).catch(()=>{});
        }
        return fresh;
      }catch(_){
        return (await caches.match('/index.html')) || (await caches.match('/')) || Response.error();
      }
    })());
    return;
  }


  if(url.pathname.startsWith('/assets/') || SHELL.includes(url.pathname)){
    event.respondWith((async()=>{
      const cached=await caches.match(req);
      const network=fetch(req).then(async res=>{
        if(res && res.ok){
          const cache=await caches.open(CACHE_NAME);
          cache.put(req,res.clone()).catch(()=>{});
        }
        return res;
      }).catch(()=>null);
      return cached || (await network) || Response.error();
    })());
  }
});