/* Elite Baseball League — ebl-feedback-system */
(function(){
  window.eblToast=function(message,tone='success',timeout=3600){
    const msg=String(message??'').trim(); if(!msg)return;
    let stack=document.getElementById('eblNoticeStack');
    if(!stack){stack=document.createElement('div');stack.id='eblNoticeStack';stack.setAttribute('role','region');stack.setAttribute('aria-live','polite');stack.setAttribute('aria-label','EBL updates');document.body.appendChild(stack)}
    const note=document.createElement('div');note.className='eblNotice';note.dataset.tone=tone;
    const symbol=tone==='error'?'!':tone==='warn'?'!':'✓';
    note.innerHTML=`<div class="eblNoticeMark" aria-hidden="true">${symbol}</div><div class="eblNoticeCopy"><span class="eblNoticeKicker">EBL UPDATE</span><div class="eblNoticeText"></div></div><button class="eblNoticeClose" type="button" aria-label="Dismiss">×</button>`;
    note.querySelector('.eblNoticeText').textContent=msg;
    const dismiss=()=>{if(!note.isConnected)return;note.classList.add('leaving');setTimeout(()=>note.remove(),180)};
    note.querySelector('.eblNoticeClose').addEventListener('click',dismiss);
    stack.prepend(note);while(stack.children.length>4)stack.lastElementChild?.remove();
    if(timeout!==0)setTimeout(dismiss,Math.max(1400,Number(timeout)||3600));
  };
  window.eblAlert=function(message,tone){
    const msg=String(message??'').trim();
    const inferred=tone||(/could not|failed|error|not available|unavailable/i.test(msg)?'error':(/need |required|choose |enter |confirm |must |cannot |can't |already |only available|under 6 mb|use png|spend all/i.test(msg)?'warn':'info'));
    window.eblToast(msg,inferred,inferred==='error'?5200:4300);
  };

  function eblActionDialog(options={}){
    return new Promise(resolve=>{
      const prior=document.getElementById('eblActionDialog');
      if(prior?.open)prior.close();
      prior?.remove();
      const isPrompt=options.mode==='prompt';
      const dlg=document.createElement('dialog');
      dlg.id='eblActionDialog';dlg.className='eblActionDialog';dlg.dataset.tone=options.tone||'default';
      dlg.innerHTML=`<form method="dialog" class="eblActionShell"><div class="eblActionKicker">ELITE BASEBALL LEAGUE</div><h3 class="eblActionTitle"></h3><p class="eblActionMessage"></p>${isPrompt?'<input class="eblActionInput" autocomplete="off">':''}<div class="eblActionButtons"><button class="btn eblActionCancel" value="cancel" type="button"></button><button class="btn eblActionConfirm" value="confirm" type="button"></button></div></form>`;
      document.body.appendChild(dlg);
      dlg.querySelector('.eblActionTitle').textContent=options.title||'Confirm Action';
      dlg.querySelector('.eblActionMessage').textContent=String(options.message||'');
      const cancel=dlg.querySelector('.eblActionCancel'),confirm=dlg.querySelector('.eblActionConfirm'),input=dlg.querySelector('.eblActionInput');
      cancel.textContent=options.cancelLabel||'CANCEL';confirm.textContent=options.confirmLabel||(isPrompt?'CONTINUE':'CONFIRM');
      if(options.tone==='danger')confirm.classList.add('danger');else if(options.tone==='warn')confirm.classList.add('warn');
      if(input){input.value=String(options.defaultValue??'');input.placeholder=options.placeholder||'';input.type=options.inputType||'text';if(options.min!=null)input.min=options.min;if(options.max!=null)input.max=options.max;if(options.step!=null)input.step=options.step}
      let settled=false;
      const finish=value=>{if(settled)return;settled=true;try{dlg.close()}catch(_){ }setTimeout(()=>dlg.remove(),0);resolve(value)};
      cancel.addEventListener('click',()=>finish(isPrompt?null:false));
      confirm.addEventListener('click',()=>finish(isPrompt?(input?.value??''):true));
      dlg.addEventListener('cancel',e=>{e.preventDefault();finish(isPrompt?null:false)});
      dlg.addEventListener('click',e=>{if(e.target===dlg)finish(isPrompt?null:false)});
      if(input)input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();confirm.click()}});
      dlg.showModal();
      requestAnimationFrame(()=>{if(input){input.focus();input.select()}else confirm.focus()});
    });
  }
  window.eblConfirm=function(message,options={}){return eblActionDialog({...options,message,mode:'confirm'})};
  window.eblPrompt=function(message,defaultValue='',options={}){return eblActionDialog({...options,message,defaultValue,mode:'prompt'})};
})();
