/* Elite Baseball League — RC125 PWA service worker
   Static shell only. API/game/account traffic is intentionally never cached. */
const CACHE_NAME='ebl-shell-rc128-v1';
const SHELL=['/','/index.html','/manifest.webmanifest','/assets/ebl_logo.png',
  '/assets/icon-192.png',
  '/assets/icon-512.png',
  '/assets/icon-maskable-512.png'];


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


  if(url.pathname.startsWith('/assets/') || url.pathname==='/manifest.webmanifest'){
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

self.addEventListener('push',event=>{
  event.waitUntil((async()=>{
    let data={};
    try{data=event.data?event.data.json():{}}catch(_){try{data={body:event.data?.text()||''}}catch(__){data={}}}
    const title=data.title||'Elite Baseball League';
    const body=data.body||'You have a new EBL update.';
    const url=data.url||'/#home';
    await self.registration.showNotification(title,{
      body,
      icon:'/assets/icon-192.png',
      badge:'/assets/icon-192.png',
      tag:'ebl-'+String(data.id||Date.now()),
      data:{url},
      renotify:false,
    });
  })());
});

self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const target=new URL(event.notification?.data?.url||'/#home',self.location.origin).href;
  event.waitUntil((async()=>{
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for(const client of windows){
      try{await client.navigate(target)}catch(_){}
      if('focus' in client)return client.focus();
    }
    if(self.clients.openWindow)return self.clients.openWindow(target);
  })());
});
