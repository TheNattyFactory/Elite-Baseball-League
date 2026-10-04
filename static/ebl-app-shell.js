/* Elite Baseball League — eblPWA */
(()=>{
  const BUILD='production-PWA';
  let deferredInstallPrompt=null;
  const installBtn=()=>document.getElementById('eblInstallApp');
  const help=()=>document.getElementById('eblInstallHelp');
  const helpBody=()=>document.getElementById('eblInstallHelpBody');
  const isStandalone=()=>window.matchMedia?.('(display-mode: standalone)').matches || window.navigator.standalone===true;
  const isIOS=()=>/iphone|ipad|ipod/i.test(navigator.userAgent);

  function showInstallButton(){
    if(isStandalone())return;
    installBtn()?.classList.remove('hidden');
  }
  function hideInstallButton(){installBtn()?.classList.add('hidden');}
  function openHelp(message){
    const body=helpBody(); if(body)body.innerHTML=message;
    help()?.classList.remove('hidden');
  }
  window.closeEBLInstallHelp=()=>help()?.classList.add('hidden');

  window.installEBLApp=async()=>{
    if(deferredInstallPrompt){
      try{
        deferredInstallPrompt.prompt();
        await deferredInstallPrompt.userChoice;
      }catch(_){ }
      deferredInstallPrompt=null;
      hideInstallButton();
      return;
    }
    if(isIOS()){
      openHelp('<b>On iPhone or iPad:</b><ol class="pwaHelpSteps"><li>Tap the Share button in Safari.</li><li>Choose <b>Add to Home Screen</b>.</li><li>Tap <b>Add</b>. EBL will open in its own app window.</li></ol>');
    }else{
      openHelp('<b>Install EBL from your browser menu.</b><ol class="pwaHelpSteps"><li>Open the browser menu.</li><li>Choose <b>Install app</b> or <b>Add to Home screen</b>.</li><li>Open EBL from your new app icon.</li></ol>');
    }
  };

  window.addEventListener('beforeinstallprompt',e=>{
    e.preventDefault();
    deferredInstallPrompt=e;
    showInstallButton();
  });
  window.addEventListener('appinstalled',()=>{deferredInstallPrompt=null;hideInstallButton();});
  window.matchMedia?.('(display-mode: standalone)').addEventListener?.('change',e=>{if(e.matches)hideInstallButton();});

  document.addEventListener('DOMContentLoaded',()=>{
    installBtn()?.addEventListener('click',window.installEBLApp);
    if(isIOS() && !isStandalone())showInstallButton();
  });

  if('serviceWorker' in navigator){
    window.addEventListener('load',()=>{
      navigator.serviceWorker.register('/sw.js',{scope:'/'}).catch(err=>console.warn('EBL service worker registration failed',err));
    });
  }
  window.EBL_PWA_BUILD=BUILD;
})();
