/* Elite Baseball League — Core Application */
async function api(url,opt={}){
  let r=await fetch(url,{
    credentials:'same-origin',
    headers:{'Content-Type':'application/json'},
    ...opt
  });


  const text=await r.text();
  let j;
  try{j=text?JSON.parse(text):{};}
  catch{j={error:`SERVER_RESPONSE_${r.status}`,message:text.slice(0,180)||'Server returned a non-JSON response'};}


  if(!r.ok)throw j;


  return j;
}

const ACTION_LOCKS=new Set();
async function onceAction(key,fn){
  if(ACTION_LOCKS.has(key))return;
  ACTION_LOCKS.add(key);
  try{return await fn();}
  finally{ACTION_LOCKS.delete(key);}
}


let ME=null,PLAYER=null,ACTIVE_PLAYERS=[],PLAYER_LIMIT=3,ENTITLEMENTS=null,CAREERS=[],LEAGUE=null,SCHEDULE=[],GG=null,gi=0,timer=null,D=null,READINESS=null;
let PLAYER_HQ_TAB='playerOverview';
let TEAM_ROSTER=[];
const HA=['CON','POW','VIS','DISC','TIM','SPD','BRIQ','LEAD','FLD','ARM','ACC','REAC','CALL'],
      PA=['STA','PCLT','CTRL','CMD','VEL','BRK','MOV','DEC','SEQ','FLD','ARM','ACC','REAC'];


const baseCost=v=>v<25?1:v<50?2:v<70?3:v<85?5:v<95?8:12;
const ageSurcharge=age=>age<25?0:age<30?2:age<35?4:age===35?6:6+(age-35);
const cost=(v,age=18)=>baseCost(v)+ageSurcharge(age);


document.querySelectorAll('.navbtn').forEach(
  b=>{
    b.onclick=()=>showPage(b.dataset.page,b);
    b.setAttribute('role','tab');
    b.setAttribute('aria-selected',b.classList.contains('active')?'true':'false');
    b.setAttribute('aria-controls',b.dataset.page||'');
    b.addEventListener('keydown',e=>{
      if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
      const tabs=[...document.querySelectorAll('.navbtn:not(.hidden)')];
      const i=tabs.indexOf(b);
      let next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(i+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
      e.preventDefault();tabs[next]?.focus();
    });
  }
);


function showPage(id,b){
  const page=document.querySelector('#'+id);
  if(!page)return;
  document.querySelectorAll('.page').forEach(x=>{x.classList.remove('active');x.setAttribute('aria-hidden','true')});
  document.querySelectorAll('.navbtn').forEach(x=>{x.classList.remove('active');x.setAttribute('aria-selected','false');x.removeAttribute('aria-current')});
  page.classList.add('active');
  page.setAttribute('aria-hidden','false');
  if(b){b.classList.add('active');b.setAttribute('aria-selected','true');b.setAttribute('aria-current','page')}
  if(id==='team' && ME)loadMyTeam();
  if(id==='support')loadSupport();
  // Coach HUD is page-critical: always refresh it when the Coach tab is opened.
  // This also recovers if an unrelated dashboard loader failed during initial refresh.
  if(id==='coach' && ME)loadCoachPortal();
  if(id==='admin' && ME?.role==='COMMISSIONER')loadAutoAdvanceStatus();
  // GameCast is an archive of FINAL games. Refresh it on entry so a just-simulated
  // league day is visible even if another dashboard loader failed or the tab was
  // already open during Sim Day.
  if(id==='gamecast' && ME){
    const gcRoot=document.getElementById('gamecastList');
    if(gcRoot && !gcRoot.innerHTML.trim())gcRoot.innerHTML='<div class="card eblSpaceTopMd"><span class="muted">Loading completed games…</span></div>';
    loadSchedule().catch(()=>{});
  }
}


function switchPane(sel,id,b){
  let root=b.closest('.card');
  root.querySelectorAll(sel+',.subtab').forEach(
    x=>x.classList.remove('active')
  );
  root.querySelector('#'+id).classList.add('active');
  b.classList.add('active');
}


function leaguePane(id,b){switchPane('.subpane',id,b)}
function analyticsPane(id,b){switchPane('.subpane',id,b)}
function awardPane(id,b){switchPane('.subpane',id,b)}
async function recoverAccount(){
 try{
  let j=await api('/api/account/recover',{method:'POST',body:JSON.stringify({username:recUser.value,recovery_code:recCode.value,new_password:recPw.value})});
  recMsg.innerHTML=`Password reset. Save your NEW recovery code somewhere safe: <b>${j.new_recovery_code}</b>`;
 }catch(e){recMsg.textContent=e.error||'Recovery failed'}
}


async function requestReset(){
 try{
  await api('/api/account/request-password-reset',{method:'POST',body:JSON.stringify({email:resetEmail.value})});
  recMsg.textContent='If that verified email exists, a secure reset link has been sent.';
 }catch(e){recMsg.textContent='Request could not be processed.'}
}

async function resendVerification(){return onceAction('resendVerification',async()=>{
 try{
  const j=await api('/api/account/resend-verification',{method:'POST'});
  loginMsg.textContent=j.sent===false?'We could not send the verification email. Please try again shortly.':'A new confirmation email has been sent. Check your inbox and spam folder.';
 }catch(e){loginMsg.textContent=e.error==='RATE_LIMITED'?'Too many verification emails requested. Try again later.':(e.error||'Could not resend confirmation email.')}
})}

async function register(){return onceAction('register',async()=>{
 try{
  const regMsg=document.getElementById('loginMsg');
  const username=String(document.getElementById('ru')?.value||'').trim();
  const password=String(document.getElementById('rp')?.value||'');
  const confirmPassword=String(document.getElementById('rp2')?.value||'');
  const email=String(document.getElementById('re')?.value||'').trim();
  const birthDate=String(document.getElementById('rdob')?.value||'').trim();
  if(!username||!password||!confirmPassword||!email||!birthDate){if(regMsg)regMsg.textContent='Fill out every account field before continuing.';return;}
  if(password!==confirmPassword){if(regMsg)regMsg.textContent='Passwords do not match.';return;}
  if(!birthDate){if(regMsg)regMsg.textContent='Enter your date of birth to confirm that you are at least 13 years old.';return;}
  if(!document.getElementById('rterms')?.checked){if(regMsg)regMsg.textContent='Please accept the EBL Community Rules, Terms of Service, and Privacy Policy.';return;}
  if(!document.getElementById('rbeta')?.checked){if(regMsg)regMsg.textContent='Please acknowledge that beta progress may be reset before official launch.';return;}
  let j=await api('/api/register',{method:'POST',body:JSON.stringify({username,password,email,birth_date:birthDate,accepted_terms:true,accepted_beta_reset:true})});
  ME=j.user;
  dashboard.classList.add('hidden');
  loginCard.classList.remove('hidden');
  if(regMsg)regMsg.innerHTML=j.verification_email_sent===false
   ? 'Your account was created, but the confirmation email could not be sent. <button class="btn" data-ebl-action="resend-verification">Try Again</button>'
   : 'Account created! Check your email for the EBL confirmation link. <button class="btn" data-ebl-action="resend-verification">Resend Email</button>';
 }catch(e){const regMsg=document.getElementById('loginMsg');if(regMsg)regMsg.textContent=e.error==='AGE_REQUIREMENT_NOT_MET'?'You must be at least 13 years old to create an EBL account.':(e.detail||e.error||'Registration failed')}
})}

async function login(){return onceAction('login',async()=>{
 try{
  let j=await api('/api/login',{method:'POST',body:JSON.stringify({username:lu.value,password:lp.value,remember_me:Boolean(document.getElementById('rememberMe')?.checked)})});
  ME=j.user;
  await refresh();
 }catch(e){loginMsg.textContent=e.error||'Login failed'}
})}

async function logout(){await api('/api/logout',{method:'POST'});location.href='/'}

async function handleAccountAction(){
 const path=location.pathname;
 const q=new URLSearchParams(location.search);
 if(path==='/create-account'){
  document.title='Create Account • Elite Baseball League';
  dashboard.classList.add('hidden');loginCard.classList.remove('hidden');
  loginCard.className='card createAccountShell';
  loginCard.innerHTML=`<img class="heroLogo" src="/assets/ebl_logo.png" alt="Elite Baseball League"><hr class="redline">
   <div class="createAccountHead"><span class="newsMeta">NEW EBL ACCOUNT</span><h2>Create Your Account</h2><p class="muted">Create the account first. After your email is verified, EBL takes you straight into Player Creation.</p></div>

   <div class="accountCreateGrid">
    <div><label class="label">USERNAME</label><input id="ru" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" maxlength="24" placeholder="username"></div>
    <div><label class="label">EMAIL</label><input id="re" name="email" type="email" autocomplete="email" autocapitalize="none" spellcheck="false" placeholder="verified email"></div>
    <div><label class="label">PASSWORD</label><input id="rp" name="new-password" type="password" autocomplete="new-password" minlength="8" maxlength="128" placeholder="8+ character password"></div>
    <div><label class="label">CONFIRM PASSWORD</label><input id="rp2" name="confirm-password" type="password" autocomplete="new-password" minlength="8" maxlength="128" placeholder="confirm password"></div>
    <div class="wide legalGate"><label for="rdob">DATE OF BIRTH</label><input id="rdob" name="birth-date" type="date" autocomplete="bday"><small>EBL is for users age 13 and older. Your birth date is checked only to confirm eligibility and is not stored in your EBL account.</small></div>
    <label class="wide accountCreateAgreement"><input id="rterms" type="checkbox"><span>I agree to the EBL Community Rules, Terms of Service, and Privacy Policy.</span></label>
    <label class="wide accountCreateAgreement"><input id="rbeta" type="checkbox"><span>I understand EBL is currently in beta and that player, season, and league progress may be reset before official launch.</span></label>
   </div>
   <div class="policyReview" style="margin:12px 0">Review: <button type="button" data-ebl-action="open-policy" data-policy="communityRules">Community Rules</button> • <button type="button" data-ebl-action="open-policy" data-policy="termsPolicy">Terms</button> • <button type="button" data-ebl-action="open-policy" data-policy="privacyPolicy">Privacy</button></div>
   <button class="btn loginPrimary" data-ebl-action="register-account">CREATE ACCOUNT & VERIFY EMAIL</button>
   <div id="loginMsg" class="muted eblSpaceTopSm"></div>
   <div style="margin-top:14px;text-align:center"><a class="btn" href="/">← BACK TO LOGIN</a></div>`;
  const bindEnter=['ru','re','rp','rp2','rdob'];
  bindEnter.forEach(id=>document.getElementById(id)?.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();register();}}));
  return true;
 }
 if(path==='/verify-email'){
  loginCard.classList.remove('hidden');dashboard.classList.add('hidden');
  loginMsg.textContent='Confirming your email...';
  try{
   const verified=await api('/api/account/verify-email',{method:'POST',body:JSON.stringify({user_id:q.get('user'),token:q.get('token')})});
   history.replaceState({},'', '/');
   loginMsg.textContent='Email confirmed! Opening Player Creation…';
   await refresh();
   goPage('player');
   if(!PLAYER)setCreatorStep(1);
  }catch(e){
   history.replaceState({},'', '/');
   loginMsg.innerHTML='That confirmation link is invalid or expired. If you are signed in, you can request a new one here: <button class="btn" data-ebl-action="resend-verification">Resend Email</button>';
  }
  return true;
 }
 if(path==='/reset-password'){
  loginCard.classList.remove('hidden');dashboard.classList.add('hidden');
  loginCard.innerHTML=`<img class="heroLogo" src="/assets/ebl_logo.png" alt="Elite Baseball League"><hr class="redline"><h2>Reset Your Password</h2><p class="muted">Choose a new password with at least 8 characters.</p><input id="newResetPw" type="password" placeholder="new password"><input id="newResetPw2" type="password" placeholder="confirm new password"><button class="btn" data-ebl-action="complete-password-reset">Save New Password</button><div id="loginMsg" class="muted"></div>`;
  return true;
 }
 return false;
}

async function completePasswordReset(){
 const q=new URLSearchParams(location.search);
 const p1=document.getElementById('newResetPw').value;
 const p2=document.getElementById('newResetPw2').value;
 const msg=document.getElementById('loginMsg');
 if(p1.length<8){msg.textContent='Password must be at least 8 characters.';return}
 if(p1!==p2){msg.textContent='Passwords do not match.';return}
 try{
  await api('/api/account/reset-password',{method:'POST',body:JSON.stringify({user_id:q.get('user'),token:q.get('token'),new_password:p1})});
  history.replaceState({},'', '/');
  loginCard.innerHTML=`<img class="heroLogo" src="/assets/ebl_logo.png" alt="Elite Baseball League"><hr class="redline"><h2>Password Updated</h2><p>Your password has been changed successfully.</p><button class="btn" data-ebl-action="reload-page">Return to Login</button>`;
 }catch(e){msg.textContent=e.error==='INVALID_OR_EXPIRED_TOKEN'?'This reset link is invalid or expired. Request a new reset email.':(e.error||'Password reset failed.')}
}

async function refresh(){
 let me=await api('/api/me');ME=me.user;window.ME=ME;
 if(!ME){
  accountTag.textContent='Not signed in';
  document.querySelectorAll('.authOnly').forEach(x=>x.classList.add('hidden'));
  await Promise.allSettled([loadLeague(),loadSchedule(),loadAwards(),loadNews(),loadReadiness(),loadCommunity(),loadPlayoffs()]);
  return;
 }
 document.querySelectorAll('.authOnly').forEach(x=>x.classList.remove('hidden'));
 if(ME.role==='PLAYER'){
  try{
   const sj=await api('/api/account/security');
   if(sj.security && !sj.security.email_verified){
    accountTag.innerHTML=`${ME.username} • EMAIL CONFIRMATION REQUIRED &nbsp; <button class="btn" data-ebl-action="logout">Logout</button>`;
    dashboard.classList.add('hidden');loginCard.classList.remove('hidden');
    document.querySelectorAll('.authOnly').forEach(x=>x.classList.add('hidden'));
    loginMsg.innerHTML='Please confirm your email before creating your EBL player. <button class="btn" data-ebl-action="resend-verification">Resend Email</button>';
    return;
   }
  }catch(e){}
 }
 accountTag.innerHTML=`<span class="notifWrap"><button class="btn notifBell" data-ebl-action="toggle-notifications" aria-label="Notifications">🔔<span id="notifCount" class="notifCount hidden">0</span></button></span> <button id="pmShortcut" class="btn pmShortcut" data-ebl-action="open-messages" aria-label="Private messages">💬 Messages <span id="pmCount" class="pmCount hidden">0</span></button> ${ME.username}${ME.beta_member?'<span class="betaTesterBadge">BETA TESTER</span>':''}${ME.founding_supporter?'<span class="foundingSupporterBadge">FOUNDING SUPPORTER</span>':''}${ME.supporter?'<span class="supporterBadge">SUPPORTER</span>':''} • ${ME.role} &nbsp; <button class="btn" data-ebl-action="logout">Logout</button><div id="notifBackdrop" class="notifBackdrop hidden" data-ebl-action="close-notifications"></div><div id="notifPanel" class="notifPanel hidden"></div>`;
 loginCard.classList.add('hidden');dashboard.classList.remove('hidden');adminNav.classList.toggle('hidden',ME.role!=='COMMISSIONER');coachNav.classList.remove('hidden');
 const initialLoads=await Promise.allSettled([loadLeague(),loadSchedule(),loadAnalytics(),loadAwards(),loadPlayer(),loadNews(),loadReadiness(),loadCommunity(),loadDMContacts(),loadDMUnread(),loadPlayoffs()]);
 initialLoads.forEach((r,i)=>{if(r.status==='rejected')console.warn('EBL dashboard loader failed',i,r.reason)});
 // Never let an unrelated page failure block Franchise Operations.
 await loadCoachPortal();
 if(ME.role==='COMMISSIONER')await Promise.allSettled([loadLeagueSizeAdmin(),loadCoachApplications(),loadCoachAssignments(),loadBetaFeedback()]);
 await Promise.allSettled([loadChat('EBL'),loadChat('TEAM')]);
 renderHome();
 startDMPoll();
 if(ME.role==='PLAYER' && !PLAYER && !(CAREERS||[]).length){
  setTimeout(()=>{goPage('player');setCreatorStep(1)},0);
 }
 const supportReturn=new URLSearchParams(location.search).get('support');
 if(supportReturn==='success'){
  history.replaceState({},'',location.pathname||'/');
  setTimeout(async()=>{goPage('support');await loadSupport();await pollSupporterReturn();await loadSupport();},100);
 }
}
function teamName(fid){let t=LEAGUE?.teams?.find(x=>x.id===fid);return t?(t.display_name||t.name||fid):fid}
async function openTeamLegacy(fid){
    try{
        const j=await api('/api/team/'+encodeURIComponent(fid));TEAM_ROSTER=j.roster;


        function season(p){
            if(p.season)return p.season;


            try{
                return JSON.parse(p.season_json || '{}');
            }catch{
                return {};
            }
        }


        function avg(s){
            const ab=Number(s.AB||0);
            const h=Number(s.H||0);
            return ab ? (h/ab).toFixed(3).replace(/^0/,'') : '.000';
        }


        function playerTag(p){
            return p.user_id ? 'PLAYER' : 'CPU';
        }


        function hitterLine(p){
            const s=season(p);


            return `
                <div class="depthPlayer">
                    <div class="depthMain">
                        <span class="depthPos">${p.primary_pos || 'UTIL'}</span>


                        <div class="depthIdentity">
                            <button class="playerLink" data-ebl-action="open-player-card" data-player="${p.id}">${p.name}</button>
                            <span class="muted">
                                ${playerTag(p)} • B/T ${p.bats || '?'} / ${p.throws || '?'}
                            </span>
                        </div>


                        <span class="depthStatus">${p.status || ''}</span>
                    </div>


                    <div class="depthStats">
                        <span><b>${avg(s)}</b> AVG</span>
                        <span><b>${s.HR||0}</b> HR</span>
                        <span><b>${s.RBI||0}</b> RBI</span>
                        <span><b>${s.SB||0}</b> SB</span>
                        <span><b>${Number(p.xp_wallet||0).toFixed(1)}</b> XP</span>
                    </div>
                </div>
            `;
        }


        function pitcherLine(p){
            const s=season(p);


            const outs=Number(s.OUTS||0);
            const ip=outs ? `${Math.floor(outs/3)}.${outs%3}` : '0.0';


            const er=Number(s.ER||0);
            const era=outs ? ((er*27)/outs).toFixed(2) : '0.00';


            return `
                <div class="depthPlayer">
                    <div class="depthMain">
                        <span class="depthPos">${p.primary_pos || 'P'}</span>


                        <div class="depthIdentity">
                            <button class="playerLink" data-ebl-action="open-player-card" data-player="${p.id}">${p.name}</button>
                            <span class="muted">
                                ${playerTag(p)} • Throws ${p.throws || '?'}
                            </span>
                        </div>


                        <span class="depthStatus">${p.status || ''}</span>
                    </div>


                    <div class="depthStats">
                        <span><b>${s.W||0}-${s.L||0}</b> W-L</span>
                        <span><b>${era}</b> ERA</span>
                        <span><b>${ip}</b> IP</span>
                        <span><b>${s.SO||0}</b> K</span>
                        <span><b>${s.SV||0}</b> SV</span>
                        <span><b>${Number(p.xp_wallet||0).toFixed(1)}</b> XP</span>
                    </div>
                </div>
            `;
        }


        const hitters=j.roster
            .filter(p=>p.type==='H')
            .sort((a,b)=>(a.slot_no||999)-(b.slot_no||999));


        const pitchers=j.roster
            .filter(p=>p.type!=='H')
            .sort((a,b)=>(a.slot_no||999)-(b.slot_no||999));


        const starters=hitters.filter(p=>
            ['C','1B','2B','3B','SS','LF','CF','RF','OF','DH']
                .includes(p.primary_pos)
        );


        const bench=hitters.filter(p=>!starters.includes(p));


        const rotation=pitchers.filter(p=>p.primary_pos==='SP');


        const bullpen=pitchers.filter(p=>p.primary_pos!=='SP');


        document.getElementById('gcontent').innerHTML=`
            <div class="gold">${j.division} Division</div>


            <h2>${j.team.name}</h2>


            <div class="depthTeamHeader">
                <span><b>${j.team.wins}-${j.team.losses}</b> Record</span>
                <span><b>${j.roster.length}</b> Players</span>
                <span><b>${j.team.runs_for-j.team.runs_against>=0?'+':''}${j.team.runs_for-j.team.runs_against}</b> Run Diff</span>
            </div>


            <h3 class="depthHeading">Position Players</h3>
            ${starters.map(hitterLine).join('') || '<p class="muted">No position players.</p>'}


            ${bench.length ? `
                <h3 class="depthHeading">Bench</h3>
                ${bench.map(hitterLine).join('')}
            ` : ''}


            <h3 class="depthHeading">Starting Rotation</h3>
            ${rotation.map(pitcherLine).join('') || '<p class="muted">No starters assigned.</p>'}


            <h3 class="depthHeading">Bullpen</h3>
            ${bullpen.map(pitcherLine).join('') || '<p class="muted">No relievers assigned.</p>'}
        `;


        document.getElementById('gc').showModal();


    }catch(e){
        eblAlert(e?.error || e?.message || 'Could not load roster');
    }
}
  function openPlayerCardLegacy(playerId){
    const p=TEAM_ROSTER.find(x=>Number(x.id)===Number(playerId));


    if(!p){
        eblAlert('Player data could not be found.');
        return;
    }


    function season(player){
        if(player.season)return player.season;


        try{
            return JSON.parse(player.season_json || '{}');
        }catch{
            return {};
        }
    }


    const s=season(p);
    const attrs=p.attributes || {};


    let statHtml='';


    if(p.type==='H'){
        const ab=Number(s.AB||0);
        const h=Number(s.H||0);
        const avg=ab ? (h/ab).toFixed(3).replace(/^0/,'') : '.000';


        statHtml=`
            <div class="playerCardStats">
                <div><b>${avg}</b><span>AVG</span></div>
                <div><b>${s.HR||0}</b><span>HR</span></div>
                <div><b>${s.RBI||0}</b><span>RBI</span></div>
                <div><b>${s.SB||0}</b><span>SB</span></div>
                <div><b>${s.SO||0}</b><span>SO</span></div>
            </div>
        `;
    }else{
        const outs=Number(s.OUTS||0);
        const ip=outs ? `${Math.floor(outs/3)}.${outs%3}` : '0.0';
        const er=Number(s.ER||0);
        const era=outs ? ((er*27)/outs).toFixed(2) : '0.00';


        statHtml=`
            <div class="playerCardStats">
                <div><b>${s.W||0}-${s.L||0}</b><span>W-L</span></div>
                <div><b>${era}</b><span>ERA</span></div>
                <div><b>${ip}</b><span>IP</span></div>
                <div><b>${s.SO||0}</b><span>K</span></div>
                <div><b>${s.SV||0}</b><span>SV</span></div>
            </div>
        `;
    }


    const attrHtml=Object.entries(attrs).map(([k,v])=>`
        <div class="attrBox">
            <span>${k}</span>
            <b>${v}</b>
        </div>
    `).join('');


    document.getElementById('gcontent').innerHTML=`
        <div class="gold">
            ${p.primary_pos || ''} • ${p.user_id ? 'PLAYER' : 'CPU'}
        </div>


        <h2>${p.name}</h2>


        <p class="muted">
            B/T ${p.bats || '?'} / ${p.throws || '?'} •
            ${Number(p.xp_wallet||0).toFixed(1)} XP
        </p>


        ${statHtml}


        <h3 class="eblSpaceTopLg">Attributes</h3>


        <div class="attrGrid">
            ${attrHtml}
        </div>


        <button class="btn eblSpaceTopLg"
               
                data-ebl-action="open-team" data-team="${p.franchise_id}">
            Back to Team
        </button>
    `;
  }

function jsq(v){return String(v??'').replace(/\\/g,'\\\\').replace(/'/g,"\\'")}

function teamProfilePane(id,b){
  const modal=document.getElementById('profileModal');
  if(!modal)return;
  modal.querySelectorAll('.teamProfilePane').forEach(x=>x.classList.add('hidden'));
  modal.querySelectorAll('.teamProfileTab').forEach(x=>x.classList.remove('active'));
  const pane=document.getElementById(id);
  if(pane)pane.classList.remove('hidden');
  if(b)b.classList.add('active');
}

function teamPlayerLink(p){
  const name=escapeHtml(String(p?.name||'Player'));
  if(p?.username)return `<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(p.username)}">${name}</button>`;
  return `<button class="clickableName" data-ebl-action="open-player-card" data-player="${Number(p?.id||0)}">${name}</button>`;
}
function teamRoleLabel(pid,fieldPositions){
  const hit=Object.keys(fieldPositions||{}).find(pos=>Number(fieldPositions[pos])===Number(pid));
  return hit||'';
}
function bullpenRoleMap(bp){
  const out={};
  ['CL','SU1','SU2'].forEach(k=>{if(bp?.[k])out[Number(bp[k])]=k;});
  ['MR','LR','EMERGENCY'].forEach(k=>(bp?.[k]||[]).forEach(id=>{if(!out[Number(id)])out[Number(id)]=k;}));
  return out;
}
async function loadMyTeam(){
  if(!window.teamPage)return;
  teamPage.innerHTML='<h1>⚾ Team Clubhouse</h1><p class="muted">Loading your team...</p>';
  try{
    const pid=PLAYER?.id?`?player_id=${encodeURIComponent(PLAYER.id)}`:'';
    const j=await api('/api/my-team'+pid);
    if(!j.team){
      teamPage.innerHTML=`<h1>⚾ Team Clubhouse</h1><div class="card"><h2>${j.reason==='FREE_AGENT'?'Free Agent':'No Team Yet'}</h2><p class="muted">Once this player signs with a franchise, the roster, lineup, pitching staff, team practice, and clubhouse details will appear here.</p>${j.reason==='FREE_AGENT'?`<button class="btn" data-ebl-action="open-market">REQUEST CONTRACT OFFERS</button><button class="btn ghost" data-ebl-action="open-player-contracts">OPEN CONTRACT HQ</button>`:''}</div>`;
      return;
    }
    TEAM_ROSTER=j.roster||[];

    //  hydrate every HUMAN teammate from the canonical public profile
    // before the Team page renders. Thin roster rows must not replace saved creator appearance.
    const humanProfiles = TEAM_ROSTER
      .filter(p => String(p.type||'').toUpperCase() !== 'CPU' && p.username)
      .map(async p => {
        try{
          const profile = await api('/api/profile/' + encodeURIComponent(p.username));
          const candidates = [
            ...(profile.current_players || []),
            ...(profile.players || []),
            ...(profile.former_players || [])
          ];
          const saved = candidates.find(x =>
            Number(x.id||x.player_id||0) === Number(p.id||p.player_id||0)
          );
          if(saved){
            const teamFields = {
              franchise_id:p.franchise_id,
              team_name:p.team_name,
              primary_pos:p.primary_pos,
              type:p.type,
              overall:p.overall,
              stats:p.stats,
              jersey_number:p.jersey_number
            };
            Object.assign(p, saved, teamFields);
          }
        }catch(e){
          console.warn('production teammate appearance hydrate', p?.name, e);
        }
      });

    if(humanProfiles.length) await Promise.allSettled(humanProfiles);

    const team=j.team||{},brand=j.branding||{},display=brand.display_name||team.name||team.id;
    //  every roster row, CPU or human, gets canonical franchise context before portrait rendering.
    const rosterTeamContext={...team,...brand,id:team.id||brand.franchise_id||'',name:display,display_name:display};
    TEAM_ROSTER.forEach(p=>{
      if(!p)return;
      if(!p.franchise_id)p.franchise_id=team.id||brand.franchise_id||'';
      const embedded=(p.team&&typeof p.team==='object')?p.team:{};
      p.team={...rosterTeamContext,...embedded};
    });
    if(typeof eblPrimeIdentityCache==='function')eblPrimeIdentityCache(TEAM_ROSTER);
    const uploadedLogo=(typeof EBLTeamLogo==='function'?EBLTeamLogo({...team,...brand},'primary'):'')||brand.primary_logo_url||brand.primary_logo||team.primary_logo_url||team.primary_logo||team.logo_url||team.logo||'';
    const logo=uploadedLogo
      ? `<div class="teamLogo uploadedFranchiseHero"><img src="${escapeHtml(String(uploadedLogo))}" alt="${escapeHtml(display)} logo"></div>`
      : teamLogoMarkup(Number(brand.logo_style||1),brand.primary_color||'#071A31',brand.secondary_color||'#D7262E',brand.accent_color||'#D9E0E8',display);
    const byId=new Map(TEAM_ROSTER.map(p=>[Number(p.id),p]));
    const lineup=(j.lineup||[]).map(Number).filter(Boolean);
    const rotation=(j.rotation||[]).map(Number).filter(Boolean);
    const bpRoles=bullpenRoleMap(j.bullpen||{});
    const hitters=TEAM_ROSTER.filter(p=>p.type==='H');
    const pitchers=TEAM_ROSTER.filter(p=>p.type==='P');
    const lineupRows=lineup.length?lineup.map((id,i)=>{const p=byId.get(id);if(!p)return'';const pos=teamRoleLabel(id,j.field_positions)||p.primary_pos||'—';return `<div class="roleRow"><b>${i+1}. ${pos}</b><span>${teamPlayerLink(p)} <span class="muted">#${Number(p.jersey_number??0)} • OVR ${Number(p.overall||0)}</span></span></div>`}).join(''):'<p class="muted">No batting order has been set yet.</p>';
    const rotationRows=rotation.length?rotation.map((id,i)=>{const p=byId.get(id);return p?`<div class="roleRow"><b>SP${i+1}</b><span>${teamPlayerLink(p)} <span class="muted">#${Number(p.jersey_number??0)} • OVR ${Number(p.overall||0)}</span></span></div>`:''}).join(''):'<p class="muted">No starting rotation has been set yet.</p>';
    const relievers=pitchers.filter(p=>!rotation.includes(Number(p.id)));
    const bullpenRows=relievers.length?relievers.map(p=>`<div class="roleRow"><b>${escapeHtml(bpRoles[Number(p.id)]||p.primary_pos||'RP')}</b><span>${teamPlayerLink(p)} <span class="muted">#${Number(p.jersey_number??0)} • OVR ${Number(p.overall||0)}</span></span></div>`).join(''):'<p class="muted">No bullpen pitchers.</p>';
    const hAvg=p=>{const st=p.stats||{},ab=Number(st.AB||0);return ab?Number(st.H||0)/ab:0};
    const eraVal=p=>{const st=p.stats||{},outs=Number(st.OUTS||0);return outs?Number(st.ER||0)*27/outs:999};
    const qualifiedHit=hitters.filter(p=>Number(p.stats?.AB||0)>0);
    const qualifiedPit=pitchers.filter(p=>Number(p.stats?.OUTS||0)>0);
    const leaderCard=(label,p,value)=>p?`<div class="statBox"><span class="label">${label}</span><b>${teamPlayerLink(p)}</b><small>${value}</small></div>`:`<div class="statBox"><span class="label">${label}</span><b>—</b><small>No stats yet</small></div>`;
    const avgLead=[...qualifiedHit].sort((a,b)=>hAvg(b)-hAvg(a))[0];
    const hrLead=[...hitters].sort((a,b)=>Number(b.stats?.HR||0)-Number(a.stats?.HR||0))[0];
    const rbiLead=[...hitters].sort((a,b)=>Number(b.stats?.RBI||0)-Number(a.stats?.RBI||0))[0];
    const eraLead=[...qualifiedPit].sort((a,b)=>eraVal(a)-eraVal(b))[0];
    const kLead=[...pitchers].sort((a,b)=>Number(b.stats?.SO||0)-Number(a.stats?.SO||0))[0];
    const teamLeaders=`<div class="card"><div style="display:flex;justify-content:space-between;align-items:end;gap:10px;flex-wrap:wrap"><div><span class="newsMeta">CLUBHOUSE BOARD</span><h2 style="margin:3px 0">Team Leaders</h2></div><span class="muted">Season ${Number(j.season||1)}</span></div><div class="grid eblSpaceTopSm">${leaderCard('BATTING AVG',avgLead,avgLead?hAvg(avgLead).toFixed(3).replace(/^0/,''):'.000')}${leaderCard('HOME RUNS',hrLead,Number(hrLead?.stats?.HR||0)+' HR')}${leaderCard('RBI',rbiLead,Number(rbiLead?.stats?.RBI||0)+' RBI')}${leaderCard('ERA',eraLead,eraLead&&eraVal(eraLead)<999?eraVal(eraLead).toFixed(2):'—')}${leaderCard('STRIKEOUTS',kLead,Number(kLead?.stats?.SO||0)+' K')}</div></div>`;
    const recentGames=(j.recent_games||[]);
    const recentHtml=recentGames.length?recentGames.map(g=>{const home=g.home_id===team.id,us=home?Number(g.home_score||0):Number(g.away_score||0),them=home?Number(g.away_score||0):Number(g.home_score||0),opp=home?g.away_id:g.home_id;return `<div class="roleRow"><b class="${us>them?'green':'red'}">${us>them?'W':'L'} ${us}-${them}</b><span class="compactTeamRef">Day ${g.league_day} • ${home?'vs':'at'} ${teamMark(opp,true)} ${escapeHtml(teamName(opp))}</span></div>`}).join(''):'<p class="muted">No completed games yet.</p>';
    const practice=j.practice||{};
    const attendance=(practice.attendance||[]);
    const attendanceIds=new Set(attendance.map(a=>Number(a.player_id)));
    const myOwnedTeamIds=new Set((ACTIVE_PLAYERS||[]).filter(x=>String(x.franchise_id||'')===String(team.id||'')).map(x=>Number(x.id)));
    const myTeamPlayers=TEAM_ROSTER.filter(p=>myOwnedTeamIds.has(Number(p.id)));
    const playerXp=p=>{const a=(ACTIVE_PLAYERS||[]).find(x=>Number(x.id)===Number(p.id));return Number(a?.xp_wallet??(Number(PLAYER?.id)===Number(p.id)?PLAYER?.xp_wallet:p.xp_wallet)??0)};
    const myIncompletePractice=myTeamPlayers.filter(p=>!attendanceIds.has(Number(p.id)));
    const reward=Number(practice.reward||.25);
    const practiceButton=myTeamPlayers.length>1
      ? (myIncompletePractice.length
          ? `<button class="btn" data-ebl-action=\"join-practice-all\" data-players='${JSON.stringify(myIncompletePractice.map(p=>Number(p.id)))}'>Practice All My Players • +${reward.toFixed(2)} XP each</button>`
          : `<button class="btn" disabled>✓ All My Players Practiced Today</button>`)
      : (practice.completed
          ? `<button class="btn" disabled>✓ Practice Complete • +${reward.toFixed(2)} XP</button>`
          : `<button class="btn" data-ebl-action="join-team-practice">Join Today's Practice • +${reward.toFixed(2)} XP</button>`);
    const myPracticeRows=myTeamPlayers.length?myTeamPlayers.map(p=>{
      const done=attendanceIds.has(Number(p.id));
      return `<div class="teamPracticePlayer">${eblPublicPortrait(p,'sm')}<div class="teamPracticeCopy"><b>${escapeHtml(p.name)}</b><small>${escapeHtml(p.primary_pos||'')} • ${playerXp(p).toFixed(2)} XP available</small></div><div class="teamPracticeActions">${done?'<span class="practiceCompleteBadge">✓ COMPLETE</span>':`<button class="btn" data-ebl-action="join-practice-player" data-player="${Number(p.id)}">JOIN • +${reward.toFixed(2)} XP</button>`}</div></div>`;
    }).join(''):'';
    const developmentRows=myTeamPlayers.length?myTeamPlayers.map(p=>`<div class="teamDevelopmentPlayer">${eblPublicPortrait(p,'sm')}<div class="teamDevelopmentCopy"><b>${escapeHtml(p.name)}</b><small>${escapeHtml(p.primary_pos||'')} • OVR ${Number(p.overall||0)}</small></div><div class="teamDevelopmentActions"><span class="teamXpBadge">⚡ ${playerXp(p).toFixed(2)} XP</span><button class="btn" data-ebl-action="open-player-development" data-player="${Number(p.id)}">SPEND XP →</button></div></div>`).join(''):'';
    const attendanceList=attendance.length?attendance.map(a=>`<span class="legacyBadge">✓ ${escapeHtml(String(a.name||a.username||'Player'))}</span>`).join(' '):'<span class="muted">No teammates have checked in yet.</span>';
    const rosterRows=TEAM_ROSTER.map(p=>`<tr><td><div class="rosterIdentity">${eblPublicPortrait(p,'sm')}<div>${teamPlayerLink(p)}</div></div></td><td>${escapeHtml(String(p.primary_pos||''))}</td><td>#${Number(p.jersey_number??0)}</td><td>${Number(p.overall||0)}</td><td>${p.user_id?'HUMAN':'CPU'}</td></tr>`).join('');
    const nextOpp=j.next_game?(j.next_game.away_id===team.id?j.next_game.home_id:j.next_game.away_id):null;
    const next=j.next_game?`<span class="legacyNextGame">Day ${j.next_game.league_day} • ${j.next_game.away_id===team.id?'at':'vs'} ${teamMark(nextOpp,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(nextOpp)}">${escapeHtml(teamName(nextOpp))}</button></span>`:'No game currently scheduled';
    const signedWelcomeKey=`ebl_signed_welcome_${PLAYER?.id||'x'}_${team.id}`;
    let signedWelcome='';
    try{
      if(PLAYER?.franchise_id && String(PLAYER.franchise_id)===String(team.id) && !localStorage.getItem(signedWelcomeKey)){
        signedWelcome=`<div class="card signedWelcome"><div>${teamMark(team.id)}<div><span class="newsMeta">WELCOME TO THE CLUBHOUSE</span><h2>${escapeHtml(PLAYER?.name||'Player')}, you're officially a ${escapeHtml(display)} player.</h2><p class="muted">Your roster, lineup, team practice, schedule, and season chase all live here.</p><div class="signedWelcomeActions"><button class="btn" data-ebl-action="signed-welcome-practice">JOIN TEAM PRACTICE</button><button class="btn ghost" data-ebl-action="go-page" data-page="schedule">VIEW SCHEDULE</button></div></div></div><button class="btn ghost dismissWelcome" data-ebl-action="signed-welcome-dismiss" data-key="${signedWelcomeKey}">GOT IT</button></div>`;
      }
    }catch(e){}
    teamPage.innerHTML=`
      ${signedWelcome}
      <div class="identity">${logo}<div><span class="gold">${escapeHtml(String(j.division||''))} Division</span><h1 style="margin:4px 0"><button class="clickableName" data-ebl-action="open-team" data-team="${jsq(team.id)}">${escapeHtml(display)}</button></h1><div class="big">${Number(team.wins||0)}-${Number(team.losses||0)}</div><div class="muted">Next: ${next}</div></div></div>
      ${teamLeaders}
      <div class="two"><div class="card"><span class="newsMeta">TEAM FORM</span><h2 style="margin:3px 0 8px">Recent Results</h2>${recentHtml}</div><div class="card"><span class="newsMeta">CLUBHOUSE</span><h2 style="margin:3px 0 8px">Team Identity</h2><p class="muted">${escapeHtml(display)} players share this clubhouse, lineup, practice board, and season chase. Coach decisions update here for the whole roster.</p><button class="btn ghost" data-ebl-action="open-team" data-team="${jsq(team.id)}">Open Franchise Profile</button></div></div>
      <div class="card" style="margin-top:14px;border-left:4px solid var(--gold)">
        <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap"><div><span class="newsMeta">DAILY TEAM PRACTICE</span><h2 style="margin:4px 0">Clubhouse Practice</h2><p class="muted eblNoMargin">Each of your players can practice once per calendar day. If you have multiple players on this club, send them all with one tap.</p></div>${practiceButton}</div>
        ${myPracticeRows?`<div class="teamPracticeRoster">${myPracticeRows}</div>`:''}
        <details class="eblSpaceTopM"><summary>${attendance.length}/${Number(practice.human_total||0)} human players checked in today</summary><div class="legacyStrip eblSpaceTopSm">${attendanceList}</div></details>
      </div>
      ${developmentRows?`<div class="card" style="border-left:4px solid var(--blue)"><div><span class="newsMeta">MY PLAYER DEVELOPMENT</span><h2 style="margin:4px 0">Spend XP</h2><p class="muted eblNoMargin">Your players' XP is individual. Pick a player here and go straight to that player's Attributes & XP screen—no manual player switching required.</p></div><div class="teamDevelopmentRoster">${developmentRows}</div></div>`:''}
      <div class="two">
        <div class="card"><h2>Starting Lineup</h2><p class="muted">The coach's currently saved batting order and defensive alignment.</p>${lineupRows}</div>
        <div class="card"><h2>Pitching Staff</h2><p class="muted">Current rotation and bullpen roles.</p><h3>Rotation</h3>${rotationRows}<h3 class="eblSpaceTopMd">Bullpen</h3>${bullpenRows}</div>
      </div>
      <div class="card"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap"><div><h2 style="margin-bottom:2px">Full Roster</h2><p class="muted" style="margin-top:0">${hitters.length} position players • ${pitchers.length} pitchers</p></div></div><div class="tablewrap"><table><thead><tr><th>Player</th><th>Pos</th><th>No.</th><th>OVR</th><th>Type</th></tr></thead><tbody>${rosterRows}</tbody></table></div></div>`;
  }catch(e){
    teamPage.innerHTML=`<h1>⚾ Team Clubhouse</h1><p class="red">${escapeHtml(String(e?.error||e?.message||'Could not load team page'))}</p>`;
  }
}
async function joinTeamPracticeFor(playerId){
  const pid=Number(playerId||0);
  if(!pid){showCareerToast('Choose a player first.');return;}
  return onceAction(`practice:${pid}`,async()=>{
    try{
      const j=await api('/api/team/practice',{method:'POST',body:JSON.stringify({player_id:pid})});
      const active=(ACTIVE_PLAYERS||[]).find(x=>Number(x.id)===pid);
      if(active&&j.xp_wallet!=null)active.xp_wallet=Number(j.xp_wallet);
      if(Number(PLAYER?.id)===pid&&j.xp_wallet!=null)PLAYER.xp_wallet=Number(j.xp_wallet);
      showCareerToast(j.already_completed?"Today's practice is already complete.":`PRACTICE COMPLETE • +${Number(j.xp||.25).toFixed(2)} XP`);
      if(Number(PLAYER?.id)===pid)await loadPlayer(pid);
      await loadMyTeam();
      renderHome();
    }catch(e){showCareerToast(e?.error||'Could not join practice');}
  });
}
async function joinTeamPractice(){
  if(!PLAYER?.id){showCareerToast('Select a player first.');return;}
  return joinTeamPracticeFor(PLAYER.id);
}
async function joinAllTeamPractice(playerIds){
  const ids=[...new Set((playerIds||[]).map(Number).filter(Boolean))];
  if(!ids.length){showCareerToast('All of your players have already practiced today.');return;}
  return onceAction('practice:all',async()=>{
    let completed=0,earned=0,failed=0;
    for(const pid of ids){
      try{
        const j=await api('/api/team/practice',{method:'POST',body:JSON.stringify({player_id:pid})});
        if(!j.already_completed){completed++;earned+=Number(j.xp||.25);}
        const active=(ACTIVE_PLAYERS||[]).find(x=>Number(x.id)===pid);
        if(active&&j.xp_wallet!=null)active.xp_wallet=Number(j.xp_wallet);
        if(Number(PLAYER?.id)===pid&&j.xp_wallet!=null)PLAYER.xp_wallet=Number(j.xp_wallet);
      }catch(e){failed++;}
    }
    if(PLAYER?.id)await loadPlayer(PLAYER.id);
    await loadMyTeam();
    renderHome();
    if(completed)showCareerToast(`${completed} PLAYER${completed===1?'':'S'} PRACTICED • +${earned.toFixed(2)} XP TOTAL`);
    else if(failed)showCareerToast('Practice could not be completed for one or more players.');
    else showCareerToast('All of your players have already practiced today.');
  });
}
async function openPlayerDevelopment(playerId){
  const pid=Number(playerId||PLAYER?.id||0);
  if(!pid){showCareerToast('Choose a player first.');return;}
  PLAYER_HQ_TAB='playerDevelopment';
  if(Number(PLAYER?.id)!==pid)await selectPlayer(pid);
  goPage('player');
  renderPlayer();
  const b=document.querySelector('#playerHQ .subtabs .subtab:nth-child(4)');
  playerHQ('playerDevelopment',b);
  requestAnimationFrame(()=>document.getElementById('playerDevelopment')?.scrollIntoView({behavior:'smooth',block:'start'}));
}

async function openTeam(fid){
  try{
    const j=await api('/api/team/'+encodeURIComponent(fid));
    TEAM_ROSTER=j.roster||[];
    const team=j.team||{};
    const b=j.branding||{};
    const display=b.display_name||team.name||fid;
    const uploadedProfileLogo=(typeof EBLTeamLogo==='function'?EBLTeamLogo({...team,...b},'primary'):'')||b.primary_logo_url||b.primary_logo||team.primary_logo_url||team.primary_logo||team.logo_url||team.logo||'';
    const logo=uploadedProfileLogo
      ? `<div class="teamLogo uploadedFranchiseProfile"><img src="${escapeHtml(String(uploadedProfileLogo))}" alt="${escapeHtml(display)} logo"></div>`
      : teamLogoMarkup(
          Number(b.logo_style||1),
          b.primary_color||'#071A31',
          b.secondary_color||'#D7262E',
          b.accent_color||'#D9E0E8',
          display
        );
    const hitters=TEAM_ROSTER.filter(p=>p.type==='H');
    const pitchers=TEAM_ROSTER.filter(p=>p.type==='P');
    const avg=s=>{const ab=Number(s?.AB||0),h=Number(s?.H||0);return ab?(h/ab).toFixed(3).replace(/^0/, ''):'.000'};
    const era=s=>{const outs=Number(s?.OUTS||0),er=Number(s?.ER||0);return outs?((er*27)/outs).toFixed(2):'0.00'};
    const ip=s=>{const outs=Number(s?.OUTS||0);return `${Math.floor(outs/3)}.${outs%3}`};
    const playerButton=p=>{
      const name=escapeHtml(String(p.name||'Player'));
      if(p.username)return `<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(p.username)}">${name}</button>`;
      return `<button class="clickableName" data-ebl-action="open-player-card" data-player="${Number(p.id)}">${name}</button>`;
    };
    const champ=(j.championships||[]).map(x=>`<span class="champBanner brandedChampBanner">${teamMark(team.id,true)} 🏆 Season ${x.season} EBL Champions</span>`).join('');
    const history=(j.history||[]).length
      ? `<div class="tablewrap"><table><tr><th>Season</th><th>W</th><th>L</th><th>RS</th><th>RA</th><th>Finish</th></tr>${j.history.map(h=>`<tr><td>${h.season}</td><td>${h.wins}</td><td>${h.losses}</td><td>${h.runs_for}</td><td>${h.runs_against}</td><td>${h.champion?'🏆 CHAMPION':escapeHtml(String(h.playoff_finish||'—'))}</td></tr>`).join('')}</table></div>`
      : '<p class="muted">Franchise season history will build here.</p>';
    const hitterRows=hitters.length?hitters.map(p=>{const s=p.stats||{};return `<tr><td>${playerButton(p)}</td><td>${escapeHtml(String(p.primary_pos||''))}</td><td><b>${Number(p.overall||0)||'—'}</b></td><td>${avg(s)}</td><td>${s.HR||0}</td><td>${s.RBI||0}</td><td>${s.SB||0}</td><td>${p.username?`<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(p.username)}">@${escapeHtml(p.username)}</button>`:'CPU'}</td></tr>`}).join(''):'<tr><td colspan="8" class="muted">No position players.</td></tr>';
    const pitcherRows=pitchers.length?pitchers.map(p=>{const s=p.stats||{};return `<tr><td>${playerButton(p)}</td><td>${escapeHtml(String(p.primary_pos||''))}</td><td><b>${Number(p.overall||0)||'—'}</b></td><td>${s.W||0}-${s.L||0}</td><td>${era(s)}</td><td>${ip(s)}</td><td>${s.SO||0}</td><td>${s.SV||0}</td></tr>`}).join(''):'<tr><td colspan="8" class="muted">No pitchers.</td></tr>';
    document.getElementById('profileContent').innerHTML=`
      <div class="profileHero">
        <div class="profileLogo">${logo}</div>
        <div>
          <div class="gold">${escapeHtml(String(j.division||''))} Division</div>
          <h1>${escapeHtml(display)}</h1>
          <div class="big">${team.wins||0}-${team.losses||0}</div>
          <div class="muted">EBL franchise for ${j.seasons_in_ebl||1} season${Number(j.seasons_in_ebl||1)===1?'':'s'} • Founded Season ${j.founded_season||1}</div>
          <div class="legacyStrip">
            <span class="legacyBadge">${TEAM_ROSTER.length} Active Players</span>
            <span class="legacyBadge">${j.championship_count||0} Championship${Number(j.championship_count||0)===1?'':'s'}</span>
            <span class="legacyBadge">Run Diff ${(Number(team.runs_for||0)-Number(team.runs_against||0))>=0?'+':''}${Number(team.runs_for||0)-Number(team.runs_against||0)}</span>
          </div>
          <div class="legacyStrip">${champ||'<span class="muted">Hunting for the first EBL championship.</span>'}</div>
        </div>
      </div>
      <div class="subtabs">
        <button class="subtab teamProfileTab active" data-ebl-action="team-profile-pane" data-pane="teamRosterPane">CURRENT ROSTER</button>
        <button class="subtab teamProfileTab" data-ebl-action="team-profile-pane" data-pane="teamHistoryPane">FRANCHISE HISTORY</button>
      </div>
      <div id="teamRosterPane" class="teamProfilePane">
        <h2>Position Players</h2>
        <div class="tablewrap"><table><tr><th>Player</th><th>Pos</th><th>OVR</th><th>AVG</th><th>HR</th><th>RBI</th><th>SB</th><th>Owner</th></tr>${hitterRows}</table></div>
        <h2 class="eblSpaceTopLg">Pitching Staff</h2>
        <div class="tablewrap"><table><tr><th>Pitcher</th><th>Role</th><th>OVR</th><th>W-L</th><th>ERA</th><th>IP</th><th>K</th><th>SV</th></tr>${pitcherRows}</table></div>
      </div>
      <div id="teamHistoryPane" class="teamProfilePane hidden">
        <h2>Franchise History</h2>
        <div class="legacyStrip">${champ||'<span class="muted">No championships yet.</span>'}</div>
        ${history}
      </div>`;
    const modal=document.getElementById('profileModal');
    if(!modal.open)modal.showModal();
  }catch(e){
    eblAlert(e?.error||e?.message||'Could not load team profile');
  }
}

function openPlayerCard(playerId){
  const p=TEAM_ROSTER.find(x=>Number(x.id)===Number(playerId));
  if(p?.username){openUserProfile(p.username);return;}
  openPlayerCardLegacy(playerId);
}

function profilePlayerCard(p){
  const c=p.career||{};
  const team=p.franchise_id?`<span class="legacyTeamRef">${teamMark(p.franchise_id,true)}<button class="clickableName" data-ebl-action="open-team" data-team="${jsq(p.franchise_id)}">${escapeHtml(String(p.team_name||p.franchise_id))}</button></span>`:'Free Agent';
  const champs=(c.championships||[]).map(x=>`<button class="champBanner brandedChampBanner" data-ebl-action="open-team" data-team="${jsq(x.franchise_id)}">${teamMark(x.franchise_id,true)} 🏆 S${x.season} ${escapeHtml(String(x.team_name||x.franchise_id))}</button>`).join('');
  const status=p.active?'ACTIVE CAREER':'CAREER COMPLETE';
  const con=p.contract||{};
  const contractLine=con.status?`<div class="muted eblSpaceTopMicro">Contract • ${Number(con.salary||0).toFixed(2)} XP/game • ${Number(con.years||0)} season${Number(con.years||0)===1?'':'s'}${Number(con.bonus||0)?` • ${Number(con.bonus).toFixed(2)} XP bonus`:''}</div>`:'';
  const currentLine=careerLine({stats:p.stats||{},rates:(c.current_season||{}).rates||{}},p.type);
  const contractHistory=(c.contract_history||[]).map(x=>`<div class="recordCard"><b class="legacyTeamRef">${x.franchise_id?teamMark(x.franchise_id,true):''}${escapeHtml(String(x.team_name||x.franchise_id||'Team'))}</b><div class="muted">${Number(x.salary||0).toFixed(2)} XP/game • ${Number(x.years||0)} season${Number(x.years||0)===1?'':'s'}${Number(x.bonus||0)?` • ${Number(x.bonus).toFixed(2)} XP bonus`:''}</div></div>`).join('');
  return `<div class="profilePlayer">
    <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap">
      ${typeof eblPlayerArt==='function'?eblPlayerArt(p,'lg','portrait'):eblAvatarHtml(p,'card')}
      <div style="flex:1;min-width:210px"><div style="display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap"><div><h3 class="eblNoMargin">${escapeHtml(String(p.name||'Player'))} <span class="gold">${escapeHtml(String(p.primary_pos||''))}</span></h3><div class="muted">${team} • #${Number(p.jersey_number??0)} • Age ${Number(p.age||18)} • ${status}${p.hometown?` • From ${escapeHtml(p.hometown)}`:''}</div>${contractLine}</div><span class="legacyBadge">${p.type==='P'?'Pitcher':'Position Player'}</span></div>
      ${p.active?`<div class="recordCard eblSpaceTopXs"><span class="label">CURRENT SEASON</span><div>${escapeHtml(currentLine||'Season underway')}</div></div>`:''}</div>
    </div>
    <div class="grid eblSpaceTopSm">
      <div class="statBox"><span class="label">SEASONS</span><b>${c.seasons_completed||0}</b></div>
      <div class="statBox"><span class="label">AWARDS</span><b>${c.award_count||0}</b></div>
      <div class="statBox"><span class="label">ALL-STARS</span><b>${c.all_star_count||0}</b></div>
      <div class="statBox"><span class="label">TITLES</span><b>${c.championship_count||0}</b></div>
      <div class="statBox"><span class="label">STATUS</span><b>${p.active?'Active':'Retired'}</b></div>
    </div>
    ${careerTotalsGrid(c,p.type)}
    ${champs?`<div class="legacyStrip eblSpaceTopSm">${champs}</div>`:''}
    <details class="eblSpaceTopSm"><summary class="clickableName">Full Career History</summary>
      <h4>Season by Season</h4>${careerHistoryHtml(c,p.type)}
      <h4>Career Timeline</h4>${careerTimelineHtml(c)}
      <h4>Honors</h4>${careerHonorsHtml(c)}
      ${(c.teams||[]).length?`<h4>Teams</h4><div class="legacyTeamJourney">${c.teams.map(x=>`<span class="legacyTeamRef">${x.franchise_id?teamMark(x.franchise_id,true):''}${escapeHtml(x.team_name||'Free Agent')}</span>`).join('<span class="journeyArrow">→</span>')}</div>`:''}
      ${contractHistory?`<h4>Contract History</h4>${contractHistory}`:''}
    </details>
  </div>`;
}

async function openUserProfile(username){
  try{
    const j=await api('/api/profile/'+encodeURIComponent(username));
    const u=j.profile||{};
    const created=u.created_at?new Date(String(u.created_at).replace(' ','T')+'Z'):null;
    const days=created&&!Number.isNaN(created.getTime())?Math.max(1,Math.floor((Date.now()-created.getTime())/86400000)):null;
    let actions='';
    const f=j.friendship;
    if(!j.is_self){
      actions+=`<button class="btn" data-ebl-action="message-profile" data-user="${Number(u.id)}">Message</button> <button class="btn ghost" data-ebl-action="report-profile" data-user="${Number(u.id)}" data-username="${escapeHtml(u.username)}">Report</button> <button class="btn ghost" data-ebl-action="block-profile" data-user="${Number(u.id)}" data-username="${escapeHtml(u.username)}">Block</button>`;
      if(!f)actions+=`<button class="btn" data-ebl-action="friend-request" data-user="${Number(u.id)}" data-username="${escapeHtml(u.username)}">Add Friend</button>`;
      else if(f.status==='PENDING'&&Number(f.addressee_user_id)===Number(ME?.id))actions+=`<button class="btn" data-ebl-action="friend-accept" data-user="${Number(u.id)}" data-username="${escapeHtml(u.username)}">Accept Friend</button>`;
      else if(f.status==='PENDING')actions+=`<button class="btn" disabled>Friend Request Sent</button>`;
      else if(f.status==='ACCEPTED')actions+=`<button class="btn" data-ebl-action="friend-remove" data-user="${Number(u.id)}" data-username="${escapeHtml(u.username)}">Friends ✓</button>`;
    }
    const legacy=j.legacy||{};
    const champs=(j.championships||[]).map(c=>`<button class="champBanner" data-ebl-action="open-team" data-team="${jsq(c.franchise_id)}">🏆 Season ${c.season} • ${escapeHtml(String(c.team_name||c.franchise_id))}</button>`).join('');
    document.getElementById('profileContent').innerHTML=`
      <div class="gold">EBL MEMBER PROFILE</div>
      <h1>@${escapeHtml(String(u.username||username))}</h1>
      <div class="muted">${escapeHtml(String(u.role||'PLAYER'))} • Joined ${u.created_at?escapeHtml(String(u.created_at)):'EBL Genesis'}${days?` • ${days} day${days===1?'':'s'} in the EBL`:''} • ${(j.current_players||[]).length} active player${(j.current_players||[]).length===1?'':'s'}</div>
      <div class="profileActions">${actions}</div>
      <div class="grid">
        <div class="statBox"><span class="label">CAREER PLAYERS</span><b>${legacy.players??(j.players||[]).length}</b></div>
        <div class="statBox"><span class="label">COMPLETED SEASONS</span><b>${legacy.completed_seasons||0}</b></div>
        <div class="statBox"><span class="label">AWARDS</span><b>${legacy.awards||0}</b></div>
        <div class="statBox"><span class="label">CHAMPIONSHIPS</span><b>${legacy.championships??(j.championships||[]).length}</b></div>
      </div>
      <h2 class="eblSpaceTopLg">Championship Legacy</h2>
      <div class="legacyStrip">${champs||'<span class="muted">No EBL championships yet.</span>'}</div>
      <h2 class="eblSpaceTopLg">Current Players</h2>
      ${(j.current_players||[]).map(profilePlayerCard).join('')||'<p class="muted">No active players.</p>'}
      <h2 class="eblSpaceTopLg">Former Players</h2>
      ${(j.former_players||[]).map(profilePlayerCard).join('')||'<p class="muted">No former players yet.</p>'}`;
    const modal=document.getElementById('profileModal');
    if(!modal.open)modal.showModal();
  }catch(e){
    eblAlert(e?.error||e?.message||'Could not load member profile');
  }
}

async function friendRequest(uid,username){
  try{await api('/api/friends/request',{method:'POST',body:JSON.stringify({user_id:uid})});await Promise.all([openUserProfile(username),loadCommunity()])}
  catch(e){eblAlert(e?.error||'Could not send friend request')}
}
async function acceptFriend(uid,username){
  try{await api('/api/friends/accept',{method:'POST',body:JSON.stringify({user_id:uid})});await Promise.all([openUserProfile(username),loadCommunity()])}
  catch(e){eblAlert(e?.error||'Could not accept friend request')}
}
async function removeFriend(uid,username){
  try{await api('/api/friends/remove',{method:'POST',body:JSON.stringify({user_id:uid})});await Promise.all([openUserProfile(username),loadCommunity()])}
  catch(e){eblAlert(e?.error||'Could not update friendship')}
}
async function messageProfile(uid){
  const modal=document.getElementById('profileModal');
  if(modal?.open)modal.close();
  goPage('messages');
  await loadDMContacts();
  await openDM(uid);
}


let NOTIFICATIONS=[];
async function loadNotifications(){
  if(!ME)return;
  try{
    const j=await api('/api/notifications');NOTIFICATIONS=j.notifications||[];
    const badge=document.getElementById('notifCount');
    if(badge){badge.textContent=j.unread||0;badge.classList.toggle('hidden',!(j.unread>0));}
    renderNotifications();
  }catch(e){}
}
function renderNotifications(){
  const panel=document.getElementById('notifPanel');if(!panel)return;
  panel.innerHTML=`<div class="notifHeader"><h3 class="eblNoMargin">Notifications</h3><div><button class="btn" data-ebl-action="mark-notifications-read">Mark all read</button> <button class="btn notifClose" data-ebl-action="close-notifications" aria-label="Close notifications">×</button></div></div>`+
    (NOTIFICATIONS.length?NOTIFICATIONS.map(n=>`<div class="notifItem ${n.is_read?'':'unread'}" data-ebl-action="open-notification" data-notification="${n.id}"><b>${escapeHtml(n.title||'Notification')}</b><div class="muted">${escapeHtml(n.body||'')}</div><small class="muted">${n.created_at||''}</small></div>`).join(''):'<p class="muted">No notifications yet.</p>');
}
function closeNotifications(){
  document.getElementById('notifPanel')?.classList.add('hidden');
  document.getElementById('notifBackdrop')?.classList.add('hidden');
}
function toggleNotifications(){
  const p=document.getElementById('notifPanel'),b=document.getElementById('notifBackdrop');if(!p)return;
  const opening=p.classList.contains('hidden');
  p.classList.toggle('hidden',!opening);
  if(b)b.classList.toggle('hidden',!opening);
}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeNotifications()});
async function markNotificationsRead(id=null){
  try{await api('/api/notifications/read',{method:'POST',body:JSON.stringify(id?{id}:{})});await loadNotifications()}catch(e){}
}
async function openNotification(id){
  const n=NOTIFICATIONS.find(x=>Number(x.id)===Number(id));if(!n)return;
  await markNotificationsRead(id);
  closeNotifications();
  if(n.type==='DM'&&n.ref_id){goPage('messages');await openDM(Number(n.ref_id));return;}
  if(n.type==='CONTRACT'){PLAYER_HQ_TAB='playerContracts';goPage('player');await loadPlayer();return;}
  if(n.type==='COACH_CONTRACT'){goPage('coach');await loadCoachHub();setTimeout(()=>openCoachContracts(),0);return;}
  if(n.type==='GAME'&&n.ref_id){try{await watch(n.ref_id)}catch(e){goPage('gamecast')}return;}
  if(n.type==='AWARD'){goPage('awards');return;}
}

async function loadPlayer(playerId=null){try{
 const wanted=playerId||Number(localStorage.getItem('ebl_selected_player')||0)||0;
 let j=await api('/api/my-player'+(wanted?'?player_id='+encodeURIComponent(wanted):''));
 PLAYER=j.player;ACTIVE_PLAYERS=j.players||[];PLAYER_LIMIT=Number(j.player_limit||3);ENTITLEMENTS=j.entitlements||ENTITLEMENTS;CAREERS=j.careers||[];
 // Keep every active career's XP visible in the multi-player switcher. Newer
 // servers include xp_wallet directly; while an older backend is still deployed,
 // hydrate the two non-selected careers through the same canonical /api/my-player route.
 if(PLAYER?.id){
   const selectedSummary=ACTIVE_PLAYERS.find(x=>Number(x.id)===Number(PLAYER.id));
   if(selectedSummary)selectedSummary.xp_wallet=Number(PLAYER.xp_wallet||0);
 }
 const missingWallets=ACTIVE_PLAYERS.filter(x=>x.xp_wallet==null&&Number(x.id)!==Number(PLAYER?.id));
 if(missingWallets.length){
   const walletRows=await Promise.all(missingWallets.map(async x=>{
     try{const r=await api('/api/my-player?player_id='+encodeURIComponent(x.id));return {id:Number(x.id),xp_wallet:Number(r?.player?.xp_wallet||0)};}
     catch(e){return {id:Number(x.id),xp_wallet:0};}
   }));
   for(const w of walletRows){const row=ACTIVE_PLAYERS.find(x=>Number(x.id)===w.id);if(row)row.xp_wallet=w.xp_wallet;}
 }
 // A selected-player id can survive logout/login in localStorage. If that id belongs
 // to a different account, the backend now falls back to this user's newest player.
 // Keep the browser selection synchronized with the player actually returned.
 if(PLAYER?.id){
   localStorage.setItem('ebl_selected_player',String(PLAYER.id));
 }else if(ACTIVE_PLAYERS.length){
   localStorage.removeItem('ebl_selected_player');
   const fallbackId=Number(ACTIVE_PLAYERS[ACTIVE_PLAYERS.length-1]?.id||ACTIVE_PLAYERS[0]?.id||0);
   if(fallbackId){
     j=await api('/api/my-player?player_id='+encodeURIComponent(fallbackId));
     PLAYER=j.player;ACTIVE_PLAYERS=j.players||ACTIVE_PLAYERS;PLAYER_LIMIT=Number(j.player_limit||PLAYER_LIMIT);ENTITLEMENTS=j.entitlements||ENTITLEMENTS;CAREERS=j.careers||CAREERS;
     if(PLAYER?.id)localStorage.setItem('ebl_selected_player',String(PLAYER.id));
   }
 }
 // Contract cards need the current franchise directory before they render. If the
 // player payload wins the initial-load race, resolve the league from the same backend
 // database instead of exposing an internal franchise id such as EBL-F01.
 if(PLAYER?.offers?.length && !LEAGUE){
   try{LEAGUE=await api('/api/league');renderStandings()}catch(e){console.warn('Could not resolve contract-offer team names',e)}
 }
 // Pitchers created before the repertoire rollout (or served once from an older
 // /api/my-player shape) should never lose the Pitch Arsenal UI. Hydrate the
 // canonical repertoire directly as a compatibility fallback.
 if(PLAYER?.type==='P'&&!PLAYER.repertoire){
   try{
     const r=await api('/api/player/repertoire?player_id='+encodeURIComponent(PLAYER.id));
     if(r?.repertoire)PLAYER.repertoire=r.repertoire;
   }catch(e){console.warn('Could not hydrate pitcher repertoire',e)}
 }
 renderPlayer();
}catch{PLAYER=null;ACTIVE_PLAYERS=[];CAREERS=[]}}
async function selectPlayer(pid){localStorage.setItem('ebl_selected_player',String(pid));await loadPlayer(pid);await Promise.all([loadSchedule(),loadLeague()]);renderHome();await Promise.all([loadChat('EBL'),loadChat('TEAM')]);}
function playerSwitcherHtml(){
 if(!ACTIVE_PLAYERS.length)return '';
 const supporter=Boolean(ENTITLEMENTS?.supporter),entitled=Number(ENTITLEMENTS?.entitled_player_limit||(supporter?3:1));
 const policyOn=Boolean(ENTITLEMENTS?.policy_enforced),full=ACTIVE_PLAYERS.length>=PLAYER_LIMIT;
 const tier=`<span class="${supporter?'supporterBadge':'freeBadge'}">${supporter?'EBL SUPPORTER • 3 PLAYER SLOTS':'FREE • 1 PLAYER SLOT'}</span>`;
 const addButton=!full?`<button class="btn playerSwitchBtn" data-ebl-action="start-additional-player"><b>+ CREATE PLAYER</b><small>${ACTIVE_PLAYERS.length}/${PLAYER_LIMIT} slots used</small></button>`:(policyOn&&!supporter?`<button class="btn playerSwitchBtn supporterGate" data-ebl-action="go-page" data-page="support"><b>UNLOCK 3 PLAYER SLOTS</b><small>Supporter account required</small></button>`:'');
 const betaNote=!policyOn&&!supporter&&ACTIVE_PLAYERS.length>=entitled?`<div class="muted eblSpaceTopTiny">Genesis testing currently leaves all 3 career slots open. Public slot rules are already wired for launch.</div>`:'';
 return `<div class="card eblSpaceBottomM"><div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap"><div><b>MY EBL PLAYERS</b> ${tier}<div class="muted">Switch players here. XP ready to spend is shown on every active career.</div>${betaNote}</div><div class="playerSwitcherButtons">${ACTIVE_PLAYERS.map(x=>`<button class="btn playerSwitchBtn ${Number(x.id)===Number(PLAYER?.id)?'active':''}" data-ebl-action="select-player" data-player="${Number(x.id)}"><b>${escapeHtml(x.name)}</b><small>${escapeHtml(x.primary_pos)} • ${Number(x.xp_wallet||0).toFixed(2)} XP</small></button>`).join('')}${addButton}</div></div></div>`;
}
function startAdditionalPlayer(){createCard.classList.remove('hidden');setCreatorStep(1);createCard.scrollIntoView({behavior:'smooth',block:'start'});}

function initials(n){return (n||'EB').split(/\s+/).slice(0,2).map(x=>x[0]).join('').toUpperCase()}
function fmt3(v){return Number(v||0).toFixed(3).replace(/^0/,'')}
function statBox(k,v){return `<div class="statBox"><span class="label">${k}</span><b>${v}</b></div>`}
function hitterStats(p){
 let s=p.season||{},ab=s.AB||0,pa=s.PA||0,h=s.H||0,bb=s.BB||0,tb=(s['1B']||0)+2*(s['2B']||0)+3*(s['3B']||0)+4*(s.HR||0);
 let avg=ab?h/ab:0,obp=pa?(h+bb)/pa:0,slg=ab?tb/ab:0;
 return [{id:'bat',title:'BATTING',stats:[['G',s.G||0],['PA',pa],['AB',ab],['H',h],['AVG',fmt3(avg)],['OBP',fmt3(obp)],['SLG',fmt3(slg)],['HR',s.HR||0],['2B',s['2B']||0],['3B',s['3B']||0],['BB',bb],['SO',s.SO||0],['R',s.R||0],['RBI',s.RBI||0]]},
 {id:'fld',title:'FIELDING',stats:[['G',s.FG||0],['PO',s.PO||0],['A',s.A||0],['E',s.E||0],['DP',s.DP||0],['FLD%',s.FLD_PCT||'1.000'],['OAA',s.OAA||0]]},
 {id:'run',title:'BASERUNNING',stats:[['SB',s.SB||0],['CS',s.CS||0],['SB%',(s.SB||s.CS)?((s.SB||0)/((s.SB||0)+(s.CS||0))*100).toFixed(1)+'%':'0.0%'],['XBT',s.XBT||0],['OOB',s.OOB||0],['BsR',s.BSR||'0.0']]}]}
function pitcherStats(p){let s=p.season||{},outs=s.OUTS||0,ip=(outs/3).toFixed(1),era=outs?(s.ER||0)*27/outs:0,whip=outs?((s.H||0)+(s.BB||0))/(outs/3):0;return [{id:'pit',title:'PITCHING',stats:[['G',s.G||0],['GS',s.GS||0],['IP',ip],['W',s.W||0],['L',s.L||0],['SV',s.SV||0],['H',s.H||0],['ER',s.ER||0],['BB',s.BB||0],['SO',s.SO||0],['ERA',era.toFixed(2)],['WHIP',whip.toFixed(2)]]},{id:'pfld',title:'FIELDING',stats:[['PO',s.PO||0],['A',s.A||0],['E',s.E||0],['DP',s.DP||0],['FLD%',s.FLD_PCT||'1.000']]}]}
function careerIP(outs){outs=Number(outs||0);return `${Math.floor(outs/3)}.${outs%3}`}
function careerLine(row,type){
 const s=row?.stats||{},r=row?.rates||{};
 if(type==='P')return `${s.W||0}-${s.L||0} • ${careerIP(s.OUTS)} IP • ${Number(r.ERA||0).toFixed(2)} ERA • ${Number(r.WHIP||0).toFixed(2)} WHIP • ${s.SO||0} K${s.SV?` • ${s.SV} SV`:''}`;
 return `${s.H||0} H • ${s.HR||0} HR • ${s.RBI||0} RBI • ${s.SB||0} SB • ${Number(r.AVG||0).toFixed(3)} AVG • ${Number(r.OPS||0).toFixed(3)} OPS`;
}
function careerTotalsGrid(c,type){
 const s=c?.career_totals||{},r=c?.career_rates||{};
 const vals=type==='P'
  ? [['G',s.G||0],['W',s.W||0],['L',s.L||0],['SV',s.SV||0],['IP',careerIP(s.OUTS)],['SO',s.SO||0],['ERA',Number(r.ERA||0).toFixed(2)],['WHIP',Number(r.WHIP||0).toFixed(2)]]
  : [['G',s.G||0],['PA',s.PA||0],['H',s.H||0],['HR',s.HR||0],['RBI',s.RBI||0],['SB',s.SB||0],['AVG',Number(r.AVG||0).toFixed(3)],['OPS',Number(r.OPS||0).toFixed(3)]];
 return `<div class="grid">${vals.map(x=>statBox(x[0],x[1])).join('')}</div>`;
}
function careerHistoryHtml(c,type){
 const rows=[];
 if(c?.current_season)rows.push({...c.current_season,current:true});
 for(const h of (c?.history||[]))rows.push(h);
 if(!rows.length)return '<p class="muted">Your first completed season will appear here.</p>';
 return rows.map(x=>`<div class="recordCard"><div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start"><div><b>Season ${x.season}${x.current?' • CURRENT':''}</b><div class="muted">${escapeHtml(x.team_name||'Free Agent')}</div></div>${x.current?'<span class="gold">IN PROGRESS</span>':'<span class="muted">FINAL</span>'}</div><div class="eblSpaceTopXs">${careerLine(x,type)}</div></div>`).join('');
}
function careerTimelineHtml(c){
 const rows=c?.timeline||[];
 if(!rows.length)return '<p class="muted">Career milestones will appear here as this player builds an EBL legacy.</p>';
 const icon={DEBUT:'⚾',CONTRACT:'✍️',AWARD:'🏅',CHAMPIONSHIP:'🏆',RETIREMENT:'★'};
 return rows.map(x=>`<div class="recordCard"><div style="display:flex;gap:10px;align-items:flex-start"><b style="font-size:20px">${icon[x.kind]||'•'}</b><div><b>${escapeHtml(String(x.title||'Career milestone'))}</b><div class="muted">${escapeHtml(String(x.detail||''))}</div></div></div></div>`).join('');
}
function careerHonorsHtml(c){
 const starCount=Number(c?.all_star_count||0);
 const stars=starCount?`<div class="recordCard"><b>⭐ ${starCount}× EBL All-Star</b><div class="muted">Each selection is a permanent career badge.</div></div>`:'';
 const champs=(c?.championships||[]).map(x=>`<div class="recordCard"><b>🏆 EBL Champion — Season ${x.season}</b><div class="muted">${escapeHtml(x.team_name||x.franchise_id||'Team')}</div></div>`).join('');
 const awards=(c?.awards||[]).filter(x=>x.award_code!=='ALL_STAR_SELECTION').map(x=>`<div class="recordCard"><b>${escapeHtml(x.award_name||'Award')}</b><div class="muted">Season ${x.season} • ${escapeHtml(String(x.period||'').replaceAll('_',' '))}${x.team_name?' • '+escapeHtml(x.team_name):''} • +${Number(x.xp_awarded||0).toFixed(0)} XP</div></div>`).join('');
 return stars+champs+awards || '<p class="muted">No EBL honors yet.</p>';
}
function careerArchiveHtml(){
 if(!CAREERS.length)return '';
 const totalSeasons=CAREERS.reduce((n,p)=>n+(p.career?.seasons_completed||0),0);
 const totalAwards=CAREERS.reduce((n,p)=>n+(p.career?.award_count||0),0);
 const totalChamps=CAREERS.reduce((n,p)=>n+(p.career?.championship_count||0),0);
 return `
   <div class="card eblSpaceTopL">
     <h2>Career Archive</h2>
     <p class="muted">Retired EBL players remain permanently attached to your account.</p>
     <div class="grid">
       ${statBox('RETIRED PLAYERS',CAREERS.length)}
       ${statBox('COMPLETED SEASONS',totalSeasons)}
       ${statBox('AWARDS',totalAwards)}
       ${statBox('CHAMPIONSHIPS',totalChamps)}
     </div>
     <div class="eblSpaceTopMd">
       ${CAREERS.map(p=>{
          const c=p.career||{};
          const teams=(c.teams||[]).map(x=>`<span class="legacyTeamRef">${x.franchise_id?teamMark(x.franchise_id,true):''}${escapeHtml(x.team_name||'Free Agent')}</span>`).join('<span class="journeyArrow">→</span>')||'Free Agent';
          return `<div class="recordCard">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:flex-start">
              <div>
                <b>${ME?.username?`<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(ME.username)}">${escapeHtml(p.name)}</button>`:escapeHtml(p.name)}</b>
                <div class="muted careerArchiveLine"><span>${escapeHtml(p.primary_pos||'')} • ${p.type==='P'?'Pitcher':'Position Player'}</span><span class="legacyTeamJourney">${teams}</span></div>
              </div>
              <span class="muted">RETIRED</span>
            </div>
            <div class="grid eblSpaceTopSm">
              ${statBox('SEASONS',c.seasons_completed||0)}
              ${statBox('AWARDS',c.award_count||0)}
              ${statBox('CHAMPIONSHIPS',c.championship_count||0)}
              ${statBox('FINAL AGE',p.age||'—')}
            </div>
            <h3 class="eblSpaceTopM">Career Totals</h3>
            ${careerTotalsGrid(c,p.type)}
            <details class="eblSpaceTopM">
              <summary>View season history and honors</summary>
              <h3 class="eblSpaceTopM">Season-by-Season</h3>
              ${careerHistoryHtml(c,p.type)}
              <h3 class="eblSpaceTopM">Honors</h3>
              ${careerHonorsHtml(c)}
            </details>
          </div>`;
       }).join('')}
     </div>
   </div>`;
}
function statTabs(defs,prefix=''){return `<div class="statTabs">${defs.map((d,i)=>`<button class="subtab ${i?'':'active'}" data-ebl-action="player-stat-pane" data-pane="${prefix+d.id}">${d.title}</button>`).join('')}</div>${defs.map((d,i)=>`<div id="${prefix+d.id}" class="statPane ${i?'':'active'}"><div class="statGrid">${d.stats.map(x=>statBox(x[0],x[1])).join('')}</div></div>`).join('')}`}
function playerStat(id,b){let card=b.closest('.card');card.querySelectorAll('.statPane,.statTabs .subtab').forEach(x=>x.classList.remove('active'));card.querySelector('#'+id).classList.add('active');b.classList.add('active')}
function playerRecentGamesHtml(p){
  if(!p?.franchise_id)return '<p class="muted">Sign with a team and your completed games will appear here.</p>';
  const finals=(SCHEDULE||[]).filter(g=>g.status==='FINAL'&&(g.away_id===p.franchise_id||g.home_id===p.franchise_id)).slice(-10).reverse();
  if(!finals.length)return '<p class="muted">No completed team games yet. Your game history will build here after Opening Day.</p>';
  return finals.map(g=>{
    const home=g.home_id===p.franchise_id,opp=home?g.away_id:g.home_id;
    const myRuns=home?g.home_runs:g.away_runs,oppRuns=home?g.away_runs:g.home_runs;
    const result=Number(myRuns)>Number(oppRuns)?'W':Number(myRuns)<Number(oppRuns)?'L':'T';
    return `<div class="game" data-ebl-action="watch-game" data-game="${jsq(g.id)}"><div class="gameLine"><div><b>Day ${g.league_day} • ${result} ${myRuns}-${oppRuns}</b><div class="muted compactTeamRef">${home?'vs':'@'} ${teamMark(opp,true)} ${escapeHtml(teamName(opp))}</div></div><span class="gold">VIEW GAMECAST ›</span></div></div>`;
  }).join('');
}
function refreshPlayerRecentGames(){
  const box=document.getElementById('playerRecentGames');
  if(box&&PLAYER)box.innerHTML=playerRecentGamesHtml(PLAYER);
}

function renderPlayer(){
    if(!PLAYER){
        playerMain.innerHTML=CAREERS.length ? `
            <h2>No Active EBL Player</h2>
            <p class="muted">Your previous careers are preserved below. When you are ready, begin your next EBL career.</p>
            ${careerArchiveHtml()}
        ` : `
            <h2>No EBL player yet</h2>
            <p class="muted">Build your first Genesis player below.</p>
        `;
        createCard.classList.remove('hidden');
        setCreatorStep(1);
        return;
    }


    createCard.classList.add('hidden');


    const p=PLAYER;
    const team=p.team?.name || 'Free Agent';
    const defs=p.type==='P' ? pitcherStats(p) : hitterStats(p);


    // Player HQ identity = player portrait. Team logos stay attached to team references only.
    const hqIdentityPlayer=(typeof eblResolveCanonicalPlayerIdentity==='function'?eblResolveCanonicalPlayerIdentity(p):p);
    const profileAvatar=(typeof eblPlayerArt==='function')
        ? `<div class="playerHQIdentityPortrait">${eblPlayerArt(hqIdentityPlayer,'sm','portrait')}</div>`
        : playerPortraitMarkup(hqIdentityPlayer);


    const teamLink=p.franchise_id
        ? `<span class="playerTeamIdentity">${teamMark(p.franchise_id,true)}<button class="playerLink" data-ebl-action="open-team" data-team="${p.franchise_id}">${team}</button></span>`
        : team;


    const contract=p.contract
        ? `${p.contract.salary}/G • ${p.contract.years_remaining} yr`
        : '—';


    const attrs=p.attributes||{};
    const attrRow=k=>{
        if(!(k in attrs))return '';
        if(k==='CALL'&&p.primary_pos!=='C')return '';
        const v=attrs[k];
        return `
        <div class="attr">
            <div>
                <div class="attrNameRow"><b>${k}</b>${attrInfoHtml(k)}</div>
                <div class="bar"><span style="width:${Math.min(100,v)}%"></span></div>
            </div>
            <span>${v}</span>
            <button class="btn" data-ebl-action="spend-attribute" data-attribute="${k}">UPGRADE +1 • ${cost(v,p.age||18)} XP</button>
        </div>`;
    };
    const attrGroup=(title,keys)=>{
        const rows=keys.map(attrRow).join('');
        return rows?`<div class="attrGroup"><div class="attrGroupTitle">${title}</div>${rows}</div>`:'';
    };
    const attrHtml=p.type==='P'
        ? [
            attrGroup('PITCHING',['CTRL','CMD','VEL','BRK','MOV','DEC','SEQ','STA','PCLT']),
            attrGroup('FIELDING',['FLD','ARM','ACC','REAC'])
          ].join('')
        : [
            attrGroup('HITTING',['CON','POW','VIS','DISC','TIM']),
            attrGroup('BASERUNNING',['SPD','BRIQ','LEAD']),
            attrGroup('FIELDING',p.primary_pos==='C'?['CALL','FLD','ARM','ACC','REAC']:['FLD','ARM','ACC','REAC'])
          ].join('');


    const activeOffers=p.offers||[];
    const openOfferCount=activeOffers.filter(o=>o.status==='OPEN').length;
    const heldOfferCount=activeOffers.filter(o=>o.status==='HELD').length;
    const offers=activeOffers.map(o=>{
        const fid=o.franchise_id||o.team_id||'';
        const cachedName=teamName(fid);
        const offerTeamName=o.team_display_name||o.team_name||((cachedName&&String(cachedName)!==String(fid))?cachedName:fid)||'EBL Club';
        const renewal=String(o.offer_type||'FREE_AGENT').toUpperCase()==='RENEWAL';
        return `
        <div class="offer ${renewal?'renewalOffer':''}">
            <div class="newsMeta" style="margin-bottom:5px">${renewal?'RENEWAL OFFER FROM':'CONTRACT OFFER FROM'}</div>
            <div style="display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap">
                <span class="contractTeamRef">${teamMark(fid,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(fid)}">${escapeHtml(offerTeamName)}</button></span>
                <div>
                    ${renewal?'<span class="pill gold">RENEWAL</span>':''}
                    ${o.returning_offer?'<span class="pill gold">RETURN OFFER</span>':''}
                    ${o.status==='HELD'?'<span class="pill">HELD</span>':''}
                </div>
            </div>
            ${renewal?`<div class="muted" style="margin:4px 0 6px">Begins Season ${Number(o.effective_season||0)} if accepted. Your current contract remains unchanged through this season.</div>`:(o.returning_offer?'<div class="muted" style="margin:4px 0 6px">Your former team wants you back.</div>':'')}
            ${!renewal&&o.proposed_role?`<div class="taskCard" style="margin:8px 0"><b>Proposed team role: ${escapeHtml(o.proposed_role)}</b>${String(o.proposed_role)!==String(p.primary_pos)?`<div class="muted">Your preferred position is ${escapeHtml(p.primary_pos)}. You can change that preference later without changing the coach-assigned role.</div>`:'<div class="muted">Matches your current preferred position.</div>'}</div>`:''}
            ${renewal?'':`${o.bonus} XP signing bonus • `}${Number(o.salary||0).toFixed(2)} XP/game • ${o.years} season(s)<br>
            ${renewal&&o.message?`<div class="taskCard" style="margin:9px 0"><b>Coach's plan</b><div class="muted">${escapeHtml(o.message)}</div></div>`:''}
            <button class="btn" data-ebl-action="respond-offer" data-offer="${o.id}" data-response="ACCEPT">Accept</button>
            ${o.status==='HELD'?'':`<button class="btn" data-ebl-action="respond-offer" data-offer="${o.id}" data-response="HOLD">Hold</button>`}
            <button class="btn" data-ebl-action="respond-offer" data-offer="${o.id}" data-response="REJECT">Reject</button>
        </div>
    `}).join('');


    playerMain.innerHTML=`
        ${playerSwitcherHtml()}
        <div id="playerHQ">


            <div class="identity">
                ${profileAvatar}


                <div>
                    <div class="gold">${p.position_group|| (p.type==='P'?'PITCHER':'INF')} • Preferred ${p.primary_pos}${p.roster_role?` • Team role ${p.roster_role}`:''}</div>
                    <h1>${ME?.username?`<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(ME.username)}">${escapeHtml(p.name)}</button>`:escapeHtml(p.name)}</h1>


                    <div class="muted">
                        #${Number(p.jersey_number??24)} • Age ${p.age||18} • Bats ${p.bats} • Throws ${p.throws} • ${teamLink}${p.hometown?`<br>From ${escapeHtml(p.hometown)}`:''}
                    </div>
                </div>
            </div>


            <div class="subtabs eblSpaceTopL">
                <button class="subtab active"
                        data-ebl-action="player-hq-pane" data-pane="playerOverview">
                    OVERVIEW
                </button>


                <button class="subtab"
                        data-ebl-action="player-hq-pane" data-pane="playerContracts">
                    CONTRACTS${(p.offers||[]).length?` (${(p.offers||[]).length})`:''}
                </button>


                <button class="subtab"
                        data-ebl-action="player-hq-pane" data-pane="playerStats">
                    SEASON STATS
                </button>


                <button class="subtab"
                        data-ebl-action="player-hq-pane" data-pane="playerDevelopment">
                    ATTRIBUTES & XP
                </button>


                <button class="subtab"
                        data-ebl-action="player-hq-pane" data-pane="playerCareer">
                    CAREER
                </button>
            </div>




            <div id="playerOverview" class="playerPane">


                <div class="grid eblSpaceTopMd">


                    <div class="statBox">
                        <span class="label">AVAILABLE XP</span>
                        <b class="gold">${Number(p.xp_wallet||0).toFixed(3)}</b>
                    </div>


                    <div class="statBox">
                        <span class="label">STATUS</span>
                        <b>${p.status}</b>
                    </div>


                    <div class="statBox">
                        <span class="label">CONTRACT</span>
                        <b>${contract}</b>
                    </div>


                    <div class="statBox">
                        <span class="label">TEAM</span>
                        <b>${p.franchise_id?`<span class="playerTeamIdentity">${teamMark(p.franchise_id,true)}${teamLink}</span>`:team}</b>
                    </div>

                    <div class="statBox">
                        <span class="label">CONTRACT OFFERS</span>
                        <b>${activeOffers.length}</b>
                    </div>


                </div>

                ${(activeOffers||[]).some(o=>String(o.offer_type||'').toUpperCase()==='RENEWAL')?`<div class="taskCard eblSpaceTopMd"><span class="newsMeta">ACTION REQUIRED</span><h3 class="eblSpaceTopMicro">Contract renewal decision waiting</h3><p class="muted">Your club has sent a renewal plan for next season. Review the rate, term, and coach's explanation before you decide.</p><button class="btn" data-ebl-action="open-player-contracts">Review Renewal</button></div>`:''}

                <div class="playerXpQuickCard">
                    <div><span class="newsMeta">PLAYER DEVELOPMENT</span><h3>${Number(p.xp_wallet||0).toFixed(2)} XP available</h3><p class="muted">Turn earned XP into permanent attribute upgrades.</p></div>
                    <button class="btn" data-ebl-action="open-player-development" data-player="${Number(p.id)}">SPEND XP →</button>
                </div>

                <div class="card eblSpaceTopMd">
                    <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:9px">
                        <div><span class="newsMeta">PLAYER AVATAR</span><h3 style="margin:2px 0 0">${escapeHtml(p.name)}</h3></div>
                        <span class="pill">#${Number(p.jersey_number??24)}</span>
                    </div>
                    ${typeof eblPlayerArt==='function'?eblPlayerArt(p,'lg','portrait'):eblAvatarHtml(p,'hero')}
                    <div class="muted eblSpaceTopTiny">Your EBL illustrated player avatar uses your saved face, hair, facial hair, eyes, game-day cosmetics, jersey number, handedness, position, and team colors.</div>
                </div>


                ${p.status==='FREE_AGENT' ? `
                    <div class="firstCareerGuide">
                        <span class="newsMeta">CONTRACT MARKET</span>
                        <h3>${Number(p.career_seasons||0)>0?'Choose Your Next Team':'Find Your First EBL Team'}</h3>
                        <p class="muted">${activeOffers.length ? `${activeOffers.length} active offer${activeOffers.length===1?'':'s'} waiting${heldOfferCount?` (${heldOfferCount} held)`:''}. Open the Contracts tab to compare every option.${p.former_team?' Your former club can also offer you a path back.':''}` : 'You are a free agent. Open the Contracts tab to request offers and choose your next team.'}</p>
                        <button class="btn" data-ebl-action="open-player-contracts">View Contract Offers</button>
                    </div>
                ` : p.contract ? `
                    <div class="firstCareerGuide">
                        <span class="newsMeta">WELCOME TO THE LEAGUE</span>
                        <h3>${escapeHtml(team)} • ${escapeHtml(p.primary_pos)}</h3>
                        <p class="muted">Your first contract is signed. Your team, schedule, stats, development, and career history now update from this Player HQ.</p>
                        <button class="btn" data-ebl-action="go-page" data-page="home">Go to EBL Home</button>
                        <button class="btn ghost" data-ebl-action="go-page" data-page="league">View League & Schedule</button>
                    </div>
                ` : ''}

                <h2 class="eblSpaceTopLg">Current Season</h2>
                ${statTabs(defs,'ov_')}

                <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-top:20px">
                    <h2 class="eblNoMargin">Recent Games</h2>
                    <button class="btn ghost" data-ebl-action="go-page" data-page="gamecast">All Completed Games</button>
                </div>
                <p class="muted">Your team's latest completed games. Tap any game to open the full GameCast and box score.</p>
                <div id="playerRecentGames">${playerRecentGamesHtml(p)}</div>

                <h2 class="eblSpaceTopLg">Player Information</h2>


                <div class="grid">


                    <div class="statBox">
                        <span class="label">PREFERRED POSITION</span>
                        <b>${p.primary_pos}</b>
                    </div>

                    <div class="statBox">
                        <span class="label">TEAM ROLE</span>
                        <b>${p.roster_role||'—'}</b>
                    </div>

                    <div class="statBox">
                        <span class="label">BATS</span>
                        <b>${p.bats}</b>
                    </div>


                    <div class="statBox">
                        <span class="label">THROWS</span>
                        <b>${p.throws}</b>
                    </div>


                    <div class="statBox">
                        <span class="label">PLAYER TYPE</span>
                        <b>${p.user_id ? 'HUMAN' : 'CPU'}</b>
                    </div>


                </div>

                ${batteryRelationshipHtml(p)}

            </div>


            <div id="playerContracts" class="playerPane hidden">
                <h2 class="eblSpaceTopL">Contracts & Free Agency</h2>
                <p class="muted">This is your contract center. Review active offers, return to a former club when they offer, or request more CPU-market options while you are a free agent.</p>
                ${p.contract ? `
                    <div class="card">
                        <span class="newsMeta">CURRENT CONTRACT</span>
                        <h3 class="contractTeamHero">${p.franchise_id?teamMark(p.franchise_id,true):''}<span>${escapeHtml(team)}</span></h3>
                        <p><b>${Number(p.contract.salary||0).toFixed(2)} XP/game</b> • ${p.contract.years_remaining} year(s) remaining • ${Number(p.contract.bonus||0).toFixed(1)} XP signing bonus</p>
                    </div>
                    ${p.renewal_agreement?`<div class="card" style="border-left:4px solid var(--green)"><span class="newsMeta">NEXT CONTRACT AGREED</span><h3>Staying with ${escapeHtml(p.renewal_agreement.team_display_name||p.renewal_agreement.team_name||team)}</h3><p><b>${Number(p.renewal_agreement.salary||0).toFixed(2)} XP/game</b> • ${Number(p.renewal_agreement.years||0)} season(s) • begins Season ${Number(p.renewal_agreement.effective_season||0)}</p>${p.renewal_agreement.message?`<div class="muted"><b>Coach's plan:</b> ${escapeHtml(p.renewal_agreement.message)}</div>`:''}</div>`:''}
                ` : `
                    <div class="card">
                        <span class="newsMeta">FREE AGENT</span>
                        <h3>${p.former_team?`<span class="contractTeamHero">${teamMark(p.former_team.franchise_id,true)}<span>Most recent team: <button class="teamLink" data-ebl-action="open-team" data-team="${jsq(p.former_team.franchise_id)}">${escapeHtml(p.former_team.team_name||p.former_team.franchise_id)}</button></span></span>`:'Choose your EBL team'}</h3>
                        <p class="muted">CPU clubs now build human clubhouses instead of scattering players across the league. Your first CPU-market offer comes from the fullest compatible CPU-run team. Hold it if you want to keep shopping; you can still carry up to three open offers. You currently have ${openOfferCount} open${heldOfferCount?` and ${heldOfferCount} held`:''}.</p>
                        ${openOfferCount<3?'<button class="btn" data-ebl-action="open-market">Request Another CPU Offer</button>':'<span class="pill">3 OPEN OFFERS</span>'}
                    </div>
                `}
                <h3>Active Offers</h3>
                ${offers || '<p class="muted">No active contract offers yet.</p>'}
            </div>




            <div id="playerStats" class="playerPane hidden">


                <h2 class="eblSpaceTopL">Season Statistics</h2>


                ${statTabs(defs,'ss_')}


                <div class="grid eblSpaceTopL">


                    <div class="statBox">
                        <span class="label">TEAM</span>
                        <b>${p.franchise_id?`<span class="contractTeamRef">${teamMark(p.franchise_id,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(p.franchise_id)}">${escapeHtml(team)}</button></span>`:escapeHtml(team)}</b>
                    </div>


                    <div class="statBox">
                        <span class="label">PREFERRED POSITION</span>
                        <b>${p.primary_pos}</b>
                    </div>

                    <div class="statBox">
                        <span class="label">TEAM ROLE</span>
                        <b>${p.roster_role||'—'}</b>
                    </div>

                    <div class="statBox">
                        <span class="label">STATUS</span>
                        <b>${p.status}</b>
                    </div>


                    <div class="statBox">
                        <span class="label">XP</span>
                        <b>${Number(p.xp_wallet||0).toFixed(3)}</b>
                    </div>


                </div>

                ${p.preferred_position_change_open ? `
                <div class="card eblSpaceTopMd">
                    <h3>Preferred Position</h3>
                    <p class="muted">${p.status==='SIGNED'?`Your club currently uses you as <b>${escapeHtml(p.roster_role||p.primary_pos)}</b>. You may change your preferred position within ${escapeHtml(p.position_group||'your roster group')} at any time; this does not move you out of the coach-assigned team role.`:'Set the position you prefer to play. During the offseason or before Opening Day, free agents may also change roster group. Once games are underway, roster-family changes lock, but your preferred position within the same group can still change.'}</p>
                    <div class="grid">
                        <div><label class="label">ROSTER GROUP</label><select id="changeGroup" onchange="refreshChangePositions()" ${p.position_group_change_open?'':'disabled'}>${(p.type==='P'?['PITCHER']:['INF','OF']).map(g=>`<option ${g===(p.position_group|| (p.type==='P'?'PITCHER':'INF'))?'selected':''}>${g}</option>`).join('')}</select></div>
                        <div><label class="label">PREFERRED POSITION</label><select id="changePos"></select></div>
                    </div>
                    <div id="changePosNote" class="muted" style="margin:8px 0"></div>
                    <button class="btn" data-ebl-action="change-player-position">Save Preferred Position</button>
                </div>` : ''}

            </div>




            <div id="playerDevelopment" class="playerPane hidden">


                <h2 class="eblSpaceTopL">Development</h2>


                <p class="muted">Spend earned XP to develop your player.</p>
                <div class="developmentHowTo"><b>How to spend XP:</b> choose the attribute you want below and tap <b>UPGRADE +1</b>. The displayed XP cost is deducted immediately, and the new rating becomes part of this player's permanent build.</div>


                <div class="statBox" style="margin:12px 0">
                    <span class="label">AVAILABLE XP</span>
                    <b class="gold">${Number(p.xp_wallet||0).toFixed(3)}</b>
                </div>


                <div id="attrs">
                    ${attrHtml}
                </div>

                ${p.type==='P'?pitcherArsenalHtml(p):''}

            </div>




            <div id="playerCareer" class="playerPane hidden">

                <h2 class="eblSpaceTopL">EBL Career & Legacy</h2>
                <p class="muted">Every completed season, championship, and award becomes part of your permanent EBL record.</p>

                <div class="grid">
                    <div class="statBox"><span class="label">STATUS</span><b>${p.active ? (p.status==='FREE_AGENT'?'Free Agent':'Active') : 'Retired'}</b></div>
                    <div class="statBox"><span class="label">CURRENT TEAM</span><b>${team}</b></div>
                    <div class="statBox"><span class="label">SEASONS COMPLETED</span><b>${p.career?.seasons_completed||0}</b></div>
                    <div class="statBox"><span class="label">AWARDS</span><b>${p.career?.award_count||0}</b></div>
                    <div class="statBox"><span class="label">ALL-STAR SELECTIONS</span><b>⭐ ${p.career?.all_star_count||0}</b></div>
                    <div class="statBox"><span class="label">CHAMPIONSHIPS</span><b>${p.career?.championship_count||0}</b></div>
                    <div class="statBox"><span class="label">AGE</span><b>${p.age||18}</b></div>
                </div>

                <h2 class="eblSpaceTopLg">Career Totals</h2>
                ${careerTotalsGrid(p.career,p.type)}

                <h2 class="eblSpaceTopLg">Season-by-Season</h2>
                ${careerHistoryHtml(p.career,p.type)}

                <h2 class="eblSpaceTopLg">Honors</h2>
                ${careerHonorsHtml(p.career)}

                <h2 class="eblSpaceTopLg">Career Timeline</h2>
                <div class="card">
                    <b>Genesis Career Begins</b>
                    <p class="muted">${p.name} entered the Elite Baseball League as a ${p.primary_pos}${p.career?.first_season?` in Season ${p.career.first_season}`:''}.</p>
                </div>
                ${(p.career?.teams||[]).length>1 ? `<div class="card eblSpaceTopSm"><b>Teams</b><p class="muted">${p.career.teams.map(x=>escapeHtml(x.team_name||'Free Agent')).join(' → ')}</p></div>` : ''}

                ${careerArchiveHtml()}

                ${p.veteran_extension?.eligible ? `
                    <div class="card" style="margin-top:14px;border-left:4px solid ${p.veteran_extension?.required?'var(--red)':'var(--gold)'}">
                        <span class="newsMeta">VETERAN CAREER</span>
                        <h3>${p.veteran_extension?.required?`Career Decision — Season ${Number(p.veteran_extension.next_career_season||0)}`:`Career Season ${Number(p.veteran_extension.next_career_season||0)} ${p.veteran_extension?.paid?'Secured':'Extension Window'}`}</h3>
                        ${p.veteran_extension?.required ? `<p>You have completed <b>${Number(p.veteran_extension.completed_seasons||0)} EBL seasons</b>. Spend <b>${Number(p.veteran_extension.cost||0).toFixed(0)} personal XP</b> during this offseason to stay healthy and guarantee one more season.</p><div class="grid"><div class="statBox"><span class="label">EXTENSION COST</span><b>${Number(p.veteran_extension.cost||0).toFixed(0)} XP</b></div><div class="statBox"><span class="label">PLAYER WALLET</span><b>${Number(p.xp_wallet||0).toFixed(1)} XP</b></div></div><button class="btn eblSpaceTopSm" data-ebl-action="extend-veteran-career">Extend Career • ${Number(p.veteran_extension.cost||0).toFixed(0)} XP</button>` : p.veteran_extension?.paid ? `<p class="muted"><b>Career extension paid.</b> Season ${Number(p.veteran_extension.next_career_season||0)} is guaranteed. No retirement roll or random health check applies.</p>` : `<p class="muted">Veteran extensions open during the offseason after each completed season from Year 12 onward.</p>`}
                        <p class="muted" style="margin-top:9px">Extension costs rise with longevity: 25 XP after Year 12, then 35, 50, 70, 95, 125, and +35 XP for each season beyond Year 18.</p>
                    </div>
                ` : ''}

                ${String(LEAGUE?.phase||'').toUpperCase()==='OFFSEASON' && p.active ? `
                    <div class="card eblSpaceTopMd">
                        <h3>Offseason Retirement Window</h3>
                        <p class="muted">Retirement is permanent. Your player remains in EBL history, but the active career ends and your roster spot is released.${p.veteran_extension?.required?' If you do not purchase the veteran extension before the commissioner advances the season, retirement will happen automatically.':''}</p>
                        <button class="btn ghost" data-ebl-action="retire-player">Retire Player</button>
                    </div>
                ` : ''}

            </div>


        </div>
    `;
      const tabMap={
        playerOverview:0,
        playerContracts:1,
        playerStats:2,
        playerDevelopment:3,
        playerCareer:4
    };


    const buttons=document.querySelectorAll('#playerHQ .subtab');
    const tabIndex=tabMap[PLAYER_HQ_TAB] ?? 0;
    const activeButton=buttons[tabIndex];


    playerHQ(
        PLAYER_HQ_TAB || 'playerOverview',
        activeButton
    );
}


function playerHQ(id,b){
    PLAYER_HQ_TAB=id;


    document.querySelectorAll('#playerHQ .playerPane')
        .forEach(x=>x.classList.add('hidden'));


    document.querySelectorAll('#playerHQ .subtab')
        .forEach(x=>x.classList.remove('active'));


    const pane=document.getElementById(id);


    if(pane) pane.classList.remove('hidden');
    if(b) b.classList.add('active');
    if(id==='playerOverview' && document.getElementById('changeGroup'))refreshChangePositions();
}

function positionOptionsForChange(group){return group==='PITCHER'?['SP','RP']:group==='OF'?['LF','CF','RF']:['SS','2B','3B','1B','C']}
function refreshChangePositions(){
 const g=document.getElementById('changeGroup'),pos=document.getElementById('changePos'),note=document.getElementById('changePosNote');if(!g||!pos)return;
 const opts=positionOptionsForChange(g.value);const current=PLAYER?.primary_pos;pos.innerHTML=opts.map(x=>`<option ${x===current?'selected':''}>${x}</option>`).join('');
 if(note)note.innerHTML=g.value!=='PITCHER'?'<b>Catcher:</b> Any position player can be assigned to C. Only players whose preferred position is C can develop CALL.':'';
}
async function changePlayerPosition(){return onceAction('changePosition',async()=>{
 try{const group=changeGroup.value,position=changePos.value;await api('/api/player/change-position',{method:'POST',body:JSON.stringify({player_id:PLAYER?.id,position_group:group,position})});await loadPlayer(PLAYER?.id);renderHome();}catch(e){eblAlert(e.error||'Could not change position')}})}
                
let CREATOR={first_name:'',last_name:'',name:'',hometown_city:'',hometown_region:'',hometown:'',position_group:'INF',position:'SS',bats:'R',throws:'R',jersey_number:24,face_id:1,skin_color_id:1,hair_id:1,facial_hair_id:1,eye_color_id:6,hair_color_id:3,nose_id:1,eye_shape_id:1,mouth_id:1,ear_size_id:2,eye_black_id:1,eyewear_id:1,chain_id:1,sleeve_id:1,body_build_id:1,pool:50,attributes:{},pitches:['FOUR_SEAM','SLIDER','CHANGEUP']};
let POSITION_DEMAND=[];
const SKIN_TONES=[{name:'Fair',color:'#f2c59d'},{name:'Light',color:'#e7b58d'},{name:'Warm',color:'#dca47b'},{name:'Tan',color:'#c98c68'},{name:'Medium',color:'#bd7c57'},{name:'Deep',color:'#8d573e'},{name:'Rich',color:'#754733'},{name:'Dark',color:'#633c2e'}];
const FACE_PRESETS=[
 {skin:'#f0c4a6',hair:'#4a2d20',eye:'#22313f',label:'Classic',radius:'48% 48% 44% 44%',beard:''},
 {skin:'#dca37c',hair:'#2a1b16',eye:'#1e2b35',label:'Wide',radius:'44% 44% 48% 48%',beard:'stubble'},
 {skin:'#c98d66',hair:'#4b3022',eye:'#283441',label:'Oval',radius:'52% 52% 46% 46%',beard:''},
 {skin:'#b97855',hair:'#261b17',eye:'#17232d',label:'Square',radius:'42% 42% 34% 34%',beard:'beard'},
 {skin:'#f1c7a4',hair:'#7a4a24',eye:'#3b4a52',label:'Angular',radius:'48% 48% 30% 30%',beard:'goatee'},
 {skin:'#8e5b43',hair:'#1e1714',eye:'#17212a',label:'Narrow',radius:'47% 47% 43% 43%',beard:''},
 {skin:'#6f4937',hair:'#161212',eye:'#111a22',label:'Broad',radius:'42% 42% 46% 46%',beard:'stubble'},
 {skin:'#d7a078',hair:'#3d281d',eye:'#26343e',label:'Round',radius:'54% 54% 44% 44%',beard:''},
 {skin:'#a86d4f',hair:'#231914',eye:'#18232c',label:'Chiseled',radius:'46% 46% 35% 35%',beard:'beard'},
 {skin:'#e1b08b',hair:'#5b3622',eye:'#2a3942',label:'Soft Jaw',radius:'50% 50% 48% 48%',beard:'goatee'}
,
 {skin:'#efbd98',hair:'#3b241b',eye:'#273945',label:'Heart',radius:'53% 53% 42% 42%',beard:''},
 {skin:'#cd916d',hair:'#1c1715',eye:'#20303a',label:'Rectangular',radius:'44% 44% 42% 42%',beard:'stubble'},
 {skin:'#aa6d50',hair:'#342219',eye:'#1a2933',label:'Diamond',radius:'48% 48% 38% 38%',beard:''},
 {skin:'#7b4d39',hair:'#171313',eye:'#18242c',label:'Wide Jaw',radius:'43% 43% 52% 52%',beard:'beard'},
 {skin:'#e7b38d',hair:'#684126',eye:'#334650',label:'High Cheeks',radius:'50% 50% 39% 39%',beard:''},
 {skin:'#bc7d5c',hair:'#2a1c17',eye:'#21313b',label:'Long Oval',radius:'49% 49% 53% 53%',beard:'goatee'},
 {skin:'#925c43',hair:'#1a1513',eye:'#15222b',label:'Compact',radius:'51% 51% 41% 41%',beard:''},
 {skin:'#e9b994',hair:'#8a5a31',eye:'#30434e',label:'Tapered',radius:'46% 46% 47% 47%',beard:'stubble'},
 {skin:'#704536',hair:'#211713',eye:'#16232b',label:'Long Square',radius:'43% 43% 48% 48%',beard:'beard'},
 {skin:'#d59a74',hair:'#452b1e',eye:'#263842',label:'Defined Jaw',radius:'45% 45% 51% 51%',beard:''}
];
const HAIR_NAMES=['Classic Crop','Short Fade','Textured Top','Loose Waves','Side Part','Buzz Cut','Medium Flow','Slick Back','Shaved','Curly/Afro','High Fade','Low Fade','Taper Fade','Crew Cut','Ivy League','French Crop','Pompadour','Quiff','Undercut','Long Flow','Long Curls','Tight Coils','High Top','Twists','Short Locs','Long Locs','Braids','Mullet'];
const FACIAL_HAIR_NAMES=['Clean Shaven','Light Stubble','Goatee','Full Beard','Mustache','Heavy Stubble','Short Boxed Beard','Medium Beard','Long Beard','Circle Beard','Soul Patch','Chevron Mustache','Handlebar Mustache','Beard + Mustache'];
const EYE_COLORS=[
 {name:'Brown',color:'#4a2f22'},
 {name:'Hazel',color:'#74652f'},
 {name:'Green',color:'#4f7657'},
 {name:'Blue',color:'#497ca1'},
 {name:'Gray',color:'#697681'},
 {name:'Dark',color:'#18232d'}
];
const HAIR_COLORS=[
 {name:'Black',color:'#171717'}, {name:'Dark Brown',color:'#2b1b15'}, {name:'Brown',color:'#4a2d20'},
 {name:'Light Brown',color:'#75503a'}, {name:'Auburn',color:'#71351f'}, {name:'Blonde',color:'#c9a66b'},
 {name:'Light Blonde',color:'#e1c98b'}, {name:'Gray',color:'#777b80'}, {name:'White',color:'#d8d8d2'}
];
const NOSE_NAMES=['Classic','Button','Straight','Broad'];
const EYE_SHAPE_NAMES=['Classic','Narrow','Round','Relaxed'];
const MOUTH_NAMES=['Neutral','Soft Smile','Wide Smile','Firm'];
const EAR_SIZE_NAMES=['Small','Standard','Large'];
const EYE_BLACK_NAMES=['None','Single Stripe','Double Stripe','Down Triangle','Cross'];
const EYEWEAR_NAMES=['None','Sport Goggles','Thin Frames','Round Frames','Wraparound'];
const CHAIN_NAMES=['None','Gold Chain','Two Gold Chains','Silver Chain','Two Silver Chains','Large Gold Chain','Large Silver Chain'];
const BODY_BUILD_NAMES=['Normal','Heavy','Muscular'];
const SLEEVE_NAMES=['None','Left Arm','Right Arm','Both Arms'];

const EBL_PITCH_CATALOG=[
 {key:'FOUR_SEAM',label:'Four-Seam',emphasis:['VEL','CMD'],description:'Primary velocity pitch. Velocity leads; command helps it live at the edges.'},
 {key:'SINKER',label:'Sinker',emphasis:['MOV','VEL'],description:'Late movement and useful velocity; naturally fits weak-contact pitchers.'},
 {key:'CUTTER',label:'Cutter',emphasis:['MOV','VEL','BRK'],description:'A firm movement pitch that blends velocity with shorter break.'},
 {key:'SLIDER',label:'Slider',emphasis:['BRK','MOV'],description:'Breaking-ball weapon that leans on break with movement behind it.'},
 {key:'CURVEBALL',label:'Curveball',emphasis:['BRK','CTRL'],description:'Large shape that rewards break and enough control to land it.'},
 {key:'CHANGEUP',label:'Changeup',emphasis:['MOV','SEQ','DEC'],description:'Speed separation and movement; sequencing and deception help it play up.'},
 {key:'SPLITTER',label:'Splitter',emphasis:['MOV','BRK'],description:'Late drop that leans on movement and break rather than raw velocity.'}
];
const EBL_PITCH_WEIGHTS={
 FOUR_SEAM:{VEL:.70,CMD:.30},SINKER:{MOV:.60,VEL:.25,CMD:.15},CUTTER:{MOV:.45,VEL:.35,BRK:.20},
 SLIDER:{BRK:.60,MOV:.25,DEC:.15},CURVEBALL:{BRK:.65,CTRL:.20,DEC:.15},CHANGEUP:{MOV:.45,SEQ:.30,DEC:.25},
 SPLITTER:{MOV:.45,BRK:.40,CMD:.15}
};
function pitchCatalogRow(key){return EBL_PITCH_CATALOG.find(x=>x.key===key)}
function pitchFitScore(key,attrs){const w=EBL_PITCH_WEIGHTS[key]||{};return Object.entries(w).reduce((n,[a,v])=>n+Number(attrs?.[a]||0)*v,0)}
function pitchFitLabel(key,attrs){
 const scores=EBL_PITCH_CATALOG.map(x=>pitchFitScore(x.key,attrs));const top=Math.max(...scores,0),score=pitchFitScore(key,attrs);
 if(top<=0)return 'Build fit updates as you spend your 50 XP.';
 if(score>=top*.82)return 'Great fit for your current build.';
 if(score>=top*.58)return 'Good fit for your current build.';
 return 'Usable — this pitch leans on skills outside your current emphasis.';
}
function creatorPitchSelectorHtml(){
 const selected=new Set(CREATOR.pitches||[]);
 return `<div class="card eblSpaceTopMd"><span class="newsMeta">PITCH REPERTOIRE</span><h3 style="margin:3px 0">Choose exactly 3 pitches</h3><p class="muted">Your pitches do not have separate ratings. They use the pitching attributes above. The labels below only explain which skills each pitch naturally leans on.</p><div class="grid">${EBL_PITCH_CATALOG.map(x=>`<button type="button" class="taskCard eblClickable ${selected.has(x.key)?'selected':''}" data-ebl-action="creator-pitch-toggle" data-pitch="${x.key}" aria-pressed="${selected.has(x.key)?'true':'false'}"><b>${selected.has(x.key)?'✓ ':''}${x.label}</b><div class="muted">Leans on: ${x.emphasis.join(' • ')}</div><small>${x.description}</small><div class="${pitchFitLabel(x.key,CREATOR.attributes).startsWith('Great')?'green':'muted'}">${pitchFitLabel(x.key,CREATOR.attributes)}</div></button>`).join('')}</div><div class="muted eblSpaceTopXs"><b>${selected.size}/3 selected.</b> There are no bad legal combinations; repertoire gives your pitcher identity, not a hidden pass/fail build check.</div></div>`;
}
function toggleCreatorPitch(key){
 const valid=EBL_PITCH_CATALOG.some(x=>x.key===key);if(!valid)return;
 const picks=[...(CREATOR.pitches||[])];const i=picks.indexOf(key);
 if(i>=0)picks.splice(i,1);else if(picks.length<3)picks.push(key);else return eblAlert('Choose exactly 3 pitches. Remove one before adding another.');
 CREATOR.pitches=picks;creatorAttributes();
}
function pitcherArsenalHtml(p){
 if(p?.type!=='P')return '';
 if(!p.repertoire)return `<div class="card eblSpaceTopMd"><span class="newsMeta">PITCH ARSENAL</span><h3 style="margin:3px 0">Repertoire unavailable</h3><p class="muted">Your pitcher should always have a 3–5 pitch repertoire. Refresh this player after the server update; the league will restore a starting arsenal automatically without charging XP.</p></div>`;
 const rep=p.repertoire||{},owned=new Set(rep.pitches||[]),catalog=rep.catalog?.length?rep.catalog:EBL_PITCH_CATALOG;
 const current=`<div class="legacyStrip">${[...owned].map(k=>{const row=catalog.find(x=>x.key===k)||pitchCatalogRow(k)||{label:k};return `<span class="legacyBadge">⚾ ${escapeHtml(row.label||k)}</span>`}).join('')}</div>`;
 const learn=rep.can_learn?catalog.filter(x=>!owned.has(x.key)).map(x=>`<div class="taskCard"><b>${escapeHtml(x.label)}</b><div class="muted">Leans on: ${(x.emphasis||[]).join(' • ')}</div><small>${escapeHtml(x.description||'')}</small><div class="muted eblSpaceTopTiny">${pitchFitLabel(x.key,p.attributes||{})}</div><button class="btn eblSpaceTopXs" data-ebl-action="learn-pitch" data-pitch="${x.key}">LEARN • ${Number(rep.next_pitch_cost||0).toFixed(0)} XP</button></div>`).join(''):'';
 return `<div class="card eblSpaceTopMd"><span class="newsMeta">PITCH ARSENAL</span><h3 style="margin:3px 0">${rep.pitch_count||owned.size}/${rep.max_pitches||5} pitches</h3><p class="muted">Pitches use your existing CTRL/CMD/VEL/BRK/MOV/DEC/SEQ ratings. Learning another pitch gives you another look; it does not create a second rating tree or an automatic effectiveness bonus.</p>${current}${rep.can_learn?`<h4 class="eblSpaceTopMd">Add another pitch</h4><div class="grid">${learn}</div>`:'<p class="green eblSpaceTopSm"><b>Full five-pitch repertoire.</b></p>'}</div>`;
}
function batteryRelationshipHtml(p){
 const rows=p?.relationships?.batteries||[];if(!rows.length)return '';
 return `<div class="card eblSpaceTopMd"><span class="newsMeta">BATTERY HISTORY</span><h3 style="margin:3px 0">Pitcher–Catcher Familiarity</h3><p class="muted">Battery Charge is earned by qualifying seasons together. It improves execution craft only while that exact pitcher and catcher work together; it never changes permanent ratings or velocity.</p><div class="tablewrap"><table><tr><th>Battery</th><th>Qualified seasons</th><th>Current streak</th><th>Charge</th></tr>${rows.map(r=>`<tr><td>${escapeHtml(r.pitcher_name||'Pitcher')} / ${escapeHtml(r.catcher_name||'Catcher')}</td><td>${Number(r.total_qualified_seasons||0)}</td><td>${Number(r.consecutive_seasons||0)}</td><td>+${Number(r.bonus||0).toFixed(2)}</td></tr>`).join('')}</table></div></div>`;
}
async function learnPitch(key){return onceAction(`learnPitch:${key}`,async()=>{
 try{const j=await api('/api/player/learn-pitch',{method:'POST',body:JSON.stringify({player_id:PLAYER?.id,pitch:key})});await loadPlayer(PLAYER?.id);renderPlayer();renderHome();showCareerToast(`PITCH LEARNED • ${pitchCatalogRow(key)?.label||key} • -${Number(j.cost||0).toFixed(0)} XP`);}catch(e){showCareerToast(e.error==='INSUFFICIENT_XP'?`NEED ${Number(e.cost||0).toFixed(0)} XP TO LEARN THIS PITCH`:(e.error||'Could not learn pitch'));}
})}

function eblHairColor(model){const id=Math.max(1,Math.min(HAIR_COLORS.length,Number(model?.hair_color_id)||3));return (HAIR_COLORS[id-1]||HAIR_COLORS[2]).color}
function setCreatorStep(n){
 document.querySelectorAll('.creatorStep').forEach((x,i)=>{x.classList.toggle('active',i===n-1);x.classList.toggle('done',i<n-1)});
 try{
   if(n===1)creatorBasic(); if(n===2)creatorAppearance(); if(n===3)creatorAttributes(); if(n===4)creatorReview();
 }catch(err){
   console.error('EBL creator step failed',n,err);
   const stage=document.getElementById('creatorStage');
   if(stage)stage.innerHTML=`<div class="card"><b>Creator step could not load.</b><p class="muted">${escapeHtml(err?.message||String(err))}</p><button class="btn" data-ebl-action="creator-step" data-step="1">BACK TO BASIC INFO</button></div>`;
 }
}
function demandLabel(level){
 return {HIGH_NEED:'HIGH NEED',AVAILABLE:'AVAILABLE',CROWDED:'CROWDED',FULL:'FULL'}[level]||'CHECKING';
}
function demandFor(pos){return POSITION_DEMAND.find(x=>x.position===pos)}
let CATCHER_DEMAND=null;
function positionDemandHtml(){
 const positions=['INF','OF','PITCHER'];
 if(!POSITION_DEMAND.length)return `<p class="muted">Checking current EBL roster demand…</p>`;
 const broad=`<div class="grid">${positions.map(pos=>{
   const d=demandFor(pos)||{};
   return `<div class="statBox"><span class="label">${pos}</span><b>${demandLabel(d.level)}</b><span class="muted">${d.opportunities??'—'} roster opportunities</span></div>`;
 }).join('')}</div>`;
 const c=CATCHER_DEMAND;
 return broad+(c?`<div class="card eblSpaceTopSm"><b>🥎 Catcher specialty</b><p class="muted">Catcher is an on-field assignment, not a roster gate. Any position player can catch; C specialists are the only players who can develop CALL. ${c.opportunities} catcher opportunity${c.opportunities===1?'':'ies'} currently remain.</p></div>`:'');
}
let POSITION_DEMAND_LOADING=null;
let POSITION_DEMAND_READY=false;
async function loadPositionDemand(force=false){
 if(POSITION_DEMAND_READY && !force){
   if(document.getElementById('positionDemand'))document.getElementById('positionDemand').innerHTML=positionDemandHtml();
   return;
 }
 if(POSITION_DEMAND_LOADING)return POSITION_DEMAND_LOADING;
 POSITION_DEMAND_LOADING=(async()=>{
  try{
    const j=await api('/api/league/position-demand');
    POSITION_DEMAND=j.positions||[]; CATCHER_DEMAND=j.catcher_specialty||null;POSITION_DEMAND_READY=true;
    if(document.getElementById('positionDemand'))document.getElementById('positionDemand').innerHTML=positionDemandHtml();
  }catch(e){
    if(document.getElementById('positionDemand'))document.getElementById('positionDemand').innerHTML='<p class="muted">Roster demand is temporarily unavailable. You can still create your player.</p>';
  }finally{POSITION_DEMAND_LOADING=null}
 })();
 return POSITION_DEMAND_LOADING;
}
function creatorPositionsForGroup(group){
 return group==='PITCHER'?['SP','RP']:group==='OF'?['LF','CF','RF']:['SS','2B','3B','1B','C'];
}
function creatorPositionOptions(){
 const positions=creatorPositionsForGroup(CREATOR.position_group);
 if(!positions.includes(CREATOR.position))CREATOR.position=positions[0];
 return positions.map(x=>`<option ${CREATOR.position===x?'selected':''}>${x}</option>`).join('');
}
function creatorGroupChanged(){
 CREATOR.position_group=cgroup.value;
 const positions=creatorPositionsForGroup(CREATOR.position_group);
 CREATOR.position=positions[0];
 if(CREATOR.position_group==='PITCHER' && (!Array.isArray(CREATOR.pitches)||CREATOR.pitches.length!==3))CREATOR.pitches=['FOUR_SEAM','SLIDER','CHANGEUP'];
 cpos.innerHTML=creatorPositionOptions();
 const note=document.getElementById('catcherCreatorNote');
 if(note)note.innerHTML=CREATOR.position_group==='INF'?`<b>Catcher specialization:</b> Any position player can catch in an emergency or by coach choice. Choose C if you want to develop CALL and build specifically for the position. CALL only affects games while you are catching.`:'';
}
function creatorBasic(){
 creatorStage.innerHTML=`<div class="playerIdentityGrid">
 <div><label class="label">FIRST</label><input id="cfirst" maxlength="24" autocomplete="given-name" value="${escapeHtml(CREATOR.first_name||'')}" placeholder="First"></div>
 <div><label class="label">LAST</label><input id="clast" maxlength="24" autocomplete="family-name" value="${escapeHtml(CREATOR.last_name||'')}" placeholder="Last"></div>
 <div><label class="label">FROM CITY</label><input id="ccity" maxlength="50" autocomplete="address-level2" value="${escapeHtml(CREATOR.hometown_city||'')}" placeholder="City"></div>
 <div><label class="label">STATE / COUNTRY</label><input id="cregion" maxlength="60" autocomplete="address-level1" value="${escapeHtml(CREATOR.hometown_region||'')}" placeholder="Georgia, USA"></div>
 <div><label class="label">ROSTER GROUP</label><select id="cgroup" onchange="creatorGroupChanged()">${['INF','OF','PITCHER'].map(x=>`<option ${CREATOR.position_group===x?'selected':''}>${x}</option>`).join('')}</select></div>
 <div><label class="label">PREFERRED POSITION</label><select id="cpos" onchange="CREATOR.position=this.value">${creatorPositionOptions()}</select></div>
 <div><label class="label">BATS</label><select id="cbats">${['R','L','S'].map(x=>`<option ${CREATOR.bats===x?'selected':''}>${x}</option>`).join('')}</select></div>
 <div><label class="label">THROWS</label><select id="cthrows">${['R','L'].map(x=>`<option ${CREATOR.throws===x?'selected':''}>${x}</option>`).join('')}</select></div>
 <div class="wide"><label class="label">PREFERRED JERSEY #</label><input id="cjersey" type="number" min="0" max="99" value="${Number(CREATOR.jersey_number??24)}"><div class="muted">0–99. If your number is already taken when you sign, EBL assigns the next available number.</div></div>
 </div>
 <div class="creatorLocationNote"><b>Your EBL identity:</b> <span class="muted">Your player will be shown as First Last and “From City, State/Country” throughout the league.</span></div>
 <div id="catcherCreatorNote" class="muted eblSpaceTopSm">${CREATOR.position_group==='INF'?`<b>Catcher specialization:</b> Any position player can catch in an emergency or by coach choice. Choose C if you want to develop CALL and build specifically for the position. CALL only affects games while you are catching.`:''}</div>
 <div class="buildIntro"><b>Current Genesis Position Demand</b><p class="muted">Roster opportunities are grouped as INF, OF, and PITCHER so players can move within a baseball family instead of being trapped by one exact-position market. Your preferred position still shapes identity and game-day use.</p><div id="positionDemand">${positionDemandHtml()}</div></div>
 <div class="eblSpaceTopMd"><button class="btn" data-ebl-action="creator-save-basic">NEXT: APPEARANCE</button></div>`;
 loadPositionDemand();
}
function saveBasic(){
 const firstEl=document.getElementById('cfirst'), lastEl=document.getElementById('clast');
 const cityEl=document.getElementById('ccity'), regionEl=document.getElementById('cregion'), jerseyEl=document.getElementById('cjersey');
 const groupEl=document.getElementById('cgroup'), posEl=document.getElementById('cpos');
 const batsEl=document.getElementById('cbats'), throwsEl=document.getElementById('cthrows');
 if(!firstEl||!lastEl||!cityEl||!regionEl||!jerseyEl||!groupEl||!posEl||!batsEl||!throwsEl){
   console.error('EBL creator basic controls missing');
   return eblAlert('Player creator could not continue. Please refresh and try again.');
 }
 const first=firstEl.value.trim(), last=lastEl.value.trim();
 const validNamePart=part=>/^[\p{L}\p{M}][\p{L}\p{M}'’.-]*$/u.test(part);
 if(!first||!last)return eblAlert('Enter your player’s first and last name before continuing.');
 if(!validNamePart(first)||!validNamePart(last))return eblAlert('Use letters, apostrophes, periods, or hyphens for the player name.');
 if(first.length>24||last.length>24||(first+' '+last).length>49)return eblAlert('Player first and last name are too long.');
 const city=cityEl.value.trim(), region=regionEl.value.trim();
 if(!city||!region)return eblAlert('Enter both the player’s city and state/country before continuing.');
 if(city.length>50||region.length>60||(city+', '+region).length>80)return eblAlert('Player hometown must be 80 characters or fewer.');
 const num=Number(jerseyEl.value);if(!Number.isInteger(num)||num<0||num>99)return eblAlert('Jersey number must be from 0 to 99.');
 CREATOR.first_name=first;CREATOR.last_name=last;CREATOR.name=`${first} ${last}`;
 CREATOR.hometown_city=city;CREATOR.hometown_region=region;CREATOR.hometown=`${city}, ${region}`;
 CREATOR.position_group=groupEl.value;CREATOR.position=posEl.value;CREATOR.bats=batsEl.value;CREATOR.throws=throwsEl.value;CREATOR.jersey_number=num;
 setCreatorStep(2);
}
function facialHairClass(id){return ['', 'stubble','goatee','beard','mustache'][Math.max(1,Math.min(5,Number(id||1)))-1]||''}
let AVATAR_GRAD_SEQ=0;
function cartoonAvatarSvg(faceId=1,hairId=1,facialId=1,eyeColor='#25364a',team1='#0d3153',team2='#d7262e',team3='#f4f7fb',thumb=false,jerseyNumber=24,hairColor=null){
 const f=FACE_PRESETS[(Math.max(1,Math.min(20,+faceId))-1)]||FACE_PRESETS[0];
 const hair=hairColor||f.hair||'#3a241b',skin=f.skin||'#c9906b';
 const gradId=`avatarSkin_${++AVATAR_GRAD_SEQ}`;
 const shape=[
  [88,84],[91,82],[86,86],[94,80],[84,88],[88,82],[96,84],[86,90],[92,86],[89,88],
  [86,86],[94,88],[88,82],[98,84],[90,82],[86,94],[92,80],[87,88],[94,94],[96,86]
 ][Math.max(1,Math.min(20,+faceId))-1] || [88,84];
 const fw=shape[0],fh=shape[1];
 const x=100-fw/2,y=68-fh/2+18;
 const hairPaths=[
  `<path d="M${x+7} ${y+29} Q100 ${y-9} ${x+fw-7} ${y+29} Q${x+fw-1} ${y+9} ${x+fw-15} ${y+3} Q100 ${y-8} ${x+12} ${y+4} Q${x+2} ${y+11} ${x+7} ${y+29}Z"/>`,
  `<path d="M${x+8} ${y+23} Q100 ${y+2} ${x+fw-8} ${y+23} L${x+fw-5} ${y+10} Q100 ${y-4} ${x+5} ${y+11}Z"/>`,
  `<path d="M${x+2} ${y+30} Q${x+14} ${y+2} ${x+31} ${y+15} Q${x+44} ${y-6} ${x+57} ${y+13} Q${x+74} ${y-3} ${x+fw-2} ${y+19} L${x+fw-4} ${y+34}Z"/>`,
  `<path d="M${x+2} ${y+31} Q${x+20} ${y-8} ${x+39} ${y+11} Q${x+55} ${y-9} ${x+72} ${y+12} Q${x+84} ${y-2} ${x+fw-1} ${y+20} L${x+fw-2} ${y+35}Z"/>`,
  `<path d="M${x+4} ${y+28} Q${x+22} ${y+0} ${x+45} ${y+8} Q${x+67} ${y+1} ${x+fw-6} ${y+26} Q${x+fw-21} ${y+12} ${x+fw-34} ${y+17} Q${x+32} ${y+8} ${x+4} ${y+28}Z"/>`,
  `<path d="M${x+8} ${y+22} Q100 ${y+7} ${x+fw-8} ${y+22} L${x+fw-5} ${y+14} Q100 ${y+3} ${x+5} ${y+14}Z"/>`,
  `<path d="M${x} ${y+34} Q${x+18} ${y-9} ${x+42} ${y+5} Q${x+68} ${y-10} ${x+fw} ${y+29} L${x+fw-5} ${y+45} Q100 ${y+22} ${x+5} ${y+45}Z"/>`,
  `<path d="M${x+3} ${y+25} Q${x+29} ${y-5} ${x+50} ${y+11} Q${x+66} ${y+4} ${x+fw-3} ${y+20} Q${x+fw-26} ${y+11} ${x+fw-45} ${y+21} Q${x+24} ${y+8} ${x+3} ${y+25}Z"/>`,
  `<path d="M${x+8} ${y+18} Q100 ${y+8} ${x+fw-8} ${y+18}" fill="none" stroke="${hair}" stroke-width="6" stroke-linecap="round" opacity=".55"/>`,
  `<path d="M${x+2} ${y+31} Q${x+15} ${y-9} ${x+35} ${y+6} Q${x+52} ${y-10} ${x+68} ${y+7} Q${x+84} ${y-6} ${x+fw} ${y+27} L${x+fw-4} ${y+40} Q100 ${y+18} ${x+4} ${y+40}Z"/>`
 ][Math.max(1,Math.min(10,+hairId))-1];
 const facial=(()=>{
  if(+facialId===2)return `<path d="M76 112 Q100 128 124 112 Q119 142 100 149 Q81 142 76 112Z" fill="${hair}" opacity=".18"/>`;
  if(+facialId===3)return `<path d="M91 123 Q100 129 109 123 L106 145 Q100 151 94 145Z" fill="${hair}" opacity=".88"/>`;
  if(+facialId===4)return `<path d="M73 113 Q100 132 127 113 Q125 142 114 151 Q100 161 86 151 Q75 142 73 113Z" fill="${hair}" opacity=".84"/>`;
  if(+facialId===5)return `<path d="M85 119 Q92 113 100 119 Q108 113 115 119 Q108 125 100 124 Q92 125 85 119Z" fill="${hair}" opacity=".92"/>`;
  return '';
 })();
 const cap=thumb?'':`<g><path d="M52 54 Q100 16 148 54 L143 71 Q100 48 57 71Z" fill="${team1}" stroke="${team3}" stroke-width="3"/><path d="M112 51 Q150 51 163 65 Q140 76 111 69Z" fill="${team1}" stroke="${team3}" stroke-width="3"/><text x="93" y="57" text-anchor="middle" font-size="16" font-weight="900" fill="${team3}">E</text></g>`;
 const torso=thumb?'':`<g><path d="M38 210 Q52 169 79 161 L121 161 Q148 169 162 210 L162 270 L38 270Z" fill="${team1}" stroke="${team3}" stroke-width="4"/><path d="M79 161 Q100 180 121 161" fill="none" stroke="${team3}" stroke-width="5"/><path d="M68 189 L132 189" stroke="${team2}" stroke-width="5"/><text x="100" y="229" text-anchor="middle" font-size="34" font-weight="950" fill="${team3}" stroke="#0008" stroke-width="1">${String(jerseyNumber).padStart(2,'0')}</text><text x="100" y="251" text-anchor="middle" font-size="11" font-weight="900" letter-spacing="2" fill="${team3}" opacity=".88">EBL</text></g>`;
 return `<svg class="avatarArt" viewBox="0 0 200 ${thumb?175:280}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
 <defs><linearGradient id="${gradId}" x1="0" x2="1"><stop offset="0" stop-color="#000" stop-opacity=".08"/><stop offset=".2" stop-color="${skin}"/><stop offset=".8" stop-color="${skin}"/><stop offset="1" stop-color="#000" stop-opacity=".1"/></linearGradient></defs>
 ${torso}<rect x="86" y="142" width="28" height="35" rx="10" fill="${skin}"/>${cap}
 <ellipse cx="${x+2}" cy="104" rx="9" ry="14" fill="${skin}" stroke="#0002"/><ellipse cx="${x+fw-2}" cy="104" rx="9" ry="14" fill="${skin}" stroke="#0002"/>
 <ellipse cx="100" cy="104" rx="${fw/2}" ry="${fh/2}" fill="url(#${gradId})" stroke="#0003" stroke-width="2"/>
 <g fill="${hair}">${hairPaths}</g>
 <path d="M70 91 Q80 86 89 91" fill="none" stroke="${hair}" stroke-width="4" stroke-linecap="round"/><path d="M111 91 Q120 86 130 91" fill="none" stroke="${hair}" stroke-width="4" stroke-linecap="round"/>
 <ellipse cx="82" cy="102" rx="7" ry="8" fill="#fff"/><ellipse cx="118" cy="102" rx="7" ry="8" fill="#fff"/><circle cx="83" cy="103" r="4.4" fill="${eyeColor}"/><circle cx="117" cy="103" r="4.4" fill="${eyeColor}"/><circle cx="84" cy="101.5" r="1.4" fill="#fff"/><circle cx="118" cy="101.5" r="1.4" fill="#fff"/>
 <path d="M100 104 Q96 116 102 118" fill="none" stroke="#8f5f4f" stroke-width="2.5" stroke-linecap="round"/>
 <path d="M82 128 Q100 141 118 128 Q113 145 100 148 Q87 145 82 128Z" fill="#fff" stroke="#7b4242" stroke-width="2"/><path d="M86 136 Q100 145 114 136" fill="#dc6e72" opacity=".8"/>
 ${facial}
 ${thumb?'':`<circle cx="63" cy="104" r="3" fill="#d88b78" opacity=".55"/><circle cx="137" cy="104" r="3" fill="#d88b78" opacity=".55"/>`}
 </svg>`;
}
function faceThumbMarkup(f,hairId=1,facialId=CREATOR.facial_hair_id,eyeColor=(EYE_COLORS[(CREATOR.eye_color_id||6)-1]||EYE_COLORS[5]).color){
 const faceId=Math.max(1,FACE_PRESETS.indexOf(f)+1);
 const model=eblAppearancePlayer({
   ...CREATOR,
   face_id:faceId,
   hair_id:hairId,
   facial_hair_id:facialId,
   eye_color_id:Math.max(1,EYE_COLORS.findIndex(x=>x.color===eyeColor)+1)||CREATOR.eye_color_id
 });
 return `<div class="faceThumb faceThumbLegacy">${stationaryPlayerSvg(model,true,'portrait')}</div>`;
}

let EBL_THREE_PROMISE=null;
let EBL_3D_ANIM=null;
async function loadEblThree(){
 if(window.THREE)return window.THREE;
 if(!EBL_THREE_PROMISE){
   EBL_THREE_PROMISE=import('https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js')
     .then(m=>{window.THREE=m;return m})
     .catch(()=>null);
 }
 return EBL_THREE_PROMISE;
}
const EBL_FACE_GEOMETRY={
 1:{scale:[1,1,1],jaw:[.92,.60,.90],jawY:3.94,ear:.65,eye:.225,brow:.08,nose:1,mouth:1},
 2:{scale:[1.06,.98,.98],jaw:[1.08,.62,.94],jawY:3.95,ear:.69,eye:.245,brow:.035,nose:1.08,mouth:1.08},
 3:{scale:[.96,1.08,.98],jaw:[.88,.66,.90],jawY:3.91,ear:.62,eye:.215,brow:.10,nose:.94,mouth:.96},
 4:{scale:[1.04,1.02,1],jaw:[1.16,.58,.96],jawY:3.91,ear:.68,eye:.24,brow:-.02,nose:1.10,mouth:1.10},
 5:{scale:[1.02,1.04,.98],jaw:[.82,.56,.88],jawY:3.90,ear:.65,eye:.23,brow:-.10,nose:1.08,mouth:.94},
 6:{scale:[.90,1.09,.96],jaw:[.80,.68,.86],jawY:3.91,ear:.59,eye:.205,brow:.06,nose:1.02,mouth:.90},
 7:{scale:[1.13,.98,1.02],jaw:[1.14,.64,.98],jawY:3.96,ear:.72,eye:.26,brow:.02,nose:1.06,mouth:1.12},
 8:{scale:[1.07,1.04,1.03],jaw:[1.02,.72,.96],jawY:3.96,ear:.69,eye:.235,brow:.12,nose:.92,mouth:1.04},
 9:{scale:[.98,1.10,.97],jaw:[.86,.52,.88],jawY:3.88,ear:.63,eye:.23,brow:-.12,nose:1.12,mouth:.92},
 10:{scale:[1,1.02,.94],jaw:[.96,.70,.86],jawY:3.96,ear:.64,eye:.22,brow:.14,nose:.90,mouth:1.02}
};
function eblFaceGeometry(faceId){return EBL_FACE_GEOMETRY[Math.max(1,Math.min(20,Number(faceId)||1))]||EBL_FACE_GEOMETRY[1]}
function eblFaceScale(faceId){return eblFaceGeometry(faceId).scale}

function eblSkinForFace(faceId){return (FACE_PRESETS[(Math.max(1,Math.min(20,Number(faceId)||1))-1)]||FACE_PRESETS[0]).skin||'#c9906b'}
function eblHairForFace(faceId){return (FACE_PRESETS[(Math.max(1,Math.min(20,Number(faceId)||1))-1)]||FACE_PRESETS[0]).hair||'#3a241b'}
function eblHairForModel(model){return model?.hair_color_id?eblHairColor(model):eblHairForFace(model?.face_id)}
function eblMakeNumberSprite(THREE,num,color='#fff'){
 const c=document.createElement('canvas');c.width=256;c.height=256;const x=c.getContext('2d');
 x.clearRect(0,0,256,256);x.font='900 150px system-ui,Arial';x.textAlign='center';x.textBaseline='middle';x.fillStyle=color;x.strokeStyle='rgba(0,0,0,.55)';x.lineWidth=12;x.strokeText(String(num),128,138);x.fillText(String(num),128,138);
 const tex=new THREE.CanvasTexture(c);tex.colorSpace=THREE.SRGBColorSpace;
 const mat=new THREE.SpriteMaterial({map:tex,transparent:true,depthWrite:false});const sp=new THREE.Sprite(mat);sp.scale.set(.72,.72,1);return sp;
}
function eblPlayerPose(p,requested='auto'){
 const r=String(requested||'auto').toLowerCase();
 if(['batting','fielding','pitching','catching'].includes(r))return r;
 if(p?.position_group==='PITCHER'||p?.type==='P')return 'pitching';
 return 'batting';
}
async function renderCreator3D(hostId='creator3dPreview',source=CREATOR,pose='auto'){
 const host=document.getElementById(hostId);if(!host)return;
 const model=source||CREATOR;
 const compact=host.classList.contains('home3dMini');
 host.classList.add('eblAvatarHost');
 host.innerHTML=`<div class="avatar3dBadge">EBL PLAYER</div>${stationaryPlayerSvg(model,compact,pose)}`;
}
function creatorAppearance(){
 const creatorStage=document.getElementById('creatorStage');if(!creatorStage)return;
 const current=FACE_PRESETS[CREATOR.face_id-1]||FACE_PRESETS[0];
 const eye=EYE_COLORS[(CREATOR.eye_color_id||6)-1]||EYE_COLORS[5];
 creatorStage.innerHTML=`<div class="creatorHero"><div><span class="badge">PLAYER APPEARANCE</span><br><b>Build your EBL look</b><div class="muted">Choose a distinct face shape, hairstyle, hair color, facial hair and eye color. Your exact look follows your player across EBL.</div></div><div>⚾</div></div>
 <div class="appearanceGrid"><div class="appearancePanel">
 <h3>FACE</h3><div class="presetGrid">${FACE_PRESETS.map((f,i)=>`<div class="preset ${CREATOR.face_id===i+1?'selected':''}" data-ebl-action="creator-pick" data-picker="pickFace" data-value="${i+1}">${faceThumbMarkup(f,CREATOR.hair_id)}<div class="presetLabel">${f.label}</div></div>`).join('')}</div>
 <h3 class="eblSpaceTopLg">SKIN TONE</h3><div class="colorChoices">${SKIN_TONES.map((x,i)=>`<button class="colorChoice ${Number(CREATOR.skin_color_id||1)===i+1?'selected':''}" style="background:${x.color}" title="${x.name}" aria-label="${x.name}" data-ebl-action="creator-pick" data-picker="pickSkinTone" data-value="${i+1}"></button>`).join('')}</div>
 <h3 class="eblSpaceTopLg">HAIR STYLE</h3><div class="presetGrid">${HAIR_NAMES.map((n,i)=>`<div class="preset ${CREATOR.hair_id===i+1?'selected':''}" data-ebl-action="creator-pick" data-picker="pickHair" data-value="${i+1}">${faceThumbMarkup(current,i+1)}<div class="presetLabel">${n}</div></div>`).join('')}</div>
 <h3 class="eblSpaceTopLg">HAIR COLOR</h3><div class="colorChoices">${HAIR_COLORS.map((x,i)=>`<button class="colorChoice ${CREATOR.hair_color_id===i+1?'selected':''}" style="background:${x.color}" title="${x.name}" aria-label="${x.name}" data-ebl-action="creator-pick" data-picker="pickHairColor" data-value="${i+1}"></button>`).join('')}</div>
 <h3 class="eblSpaceTopLg">FACIAL HAIR</h3><div class="presetGrid">${FACIAL_HAIR_NAMES.map((n,i)=>`<div class="preset ${CREATOR.facial_hair_id===i+1?'selected':''}" data-ebl-action="creator-pick" data-picker="pickFacialHair" data-value="${i+1}">${faceThumbMarkup(current,CREATOR.hair_id,i+1,eye.color)}<div class="presetLabel">${n}</div></div>`).join('')}</div>
 <h3 class="eblSpaceTopLg">EYE COLOR</h3><div class="colorChoices">${EYE_COLORS.map((x,i)=>`<button class="colorChoice ${CREATOR.eye_color_id===i+1?'selected':''}" style="background:${x.color}" title="${x.name}" aria-label="${x.name}" data-ebl-action="creator-pick" data-picker="pickEyeColor" data-value="${i+1}"></button>`).join('')}</div>
 <h3 class="eblSpaceTopLg">GAME-DAY COSMETICS</h3>
 <div class="presetGrid">${EYE_BLACK_NAMES.map((n,i)=>`<div class="preset ${CREATOR.eye_black_id===i+1?'selected':''}" data-ebl-action="creator-pick" data-picker="pickEyeBlack" data-value="${i+1}"><div class="presetLabel">Eye Black<br><b>${n}</b></div></div>`).join('')}</div>
 <div class="presetGrid eblSpaceTopXs">${EYEWEAR_NAMES.map((n,i)=>`<div class="preset ${CREATOR.eyewear_id===i+1?'selected':''}" data-ebl-action="creator-pick" data-picker="pickEyewear" data-value="${i+1}"><div class="presetLabel">Eyewear<br><b>${n}</b></div></div>`).join('')}</div>
 <div class="presetGrid eblSpaceTopXs">${CHAIN_NAMES.map((n,i)=>`<div class="preset ${CREATOR.chain_id===i+1?'selected':''}" data-ebl-action="creator-pick" data-picker="pickChain" data-value="${i+1}"><div class="presetLabel">Chain<br><b>${n}</b></div></div>`).join('')}</div>
 <div class="presetGrid eblSpaceTopXs">${SLEEVE_NAMES.map((n,i)=>`<div class="preset ${CREATOR.sleeve_id===i+1?'selected':''}" data-ebl-action="creator-pick" data-picker="pickSleeve" data-value="${i+1}"><div class="presetLabel">Sleeves<br><b>${n}</b></div></div>`).join('')}</div>
 </div><div><h3>LIVE PLAYER PREVIEW</h3><div id="creator3dPreview" class="avatar3dPreview"></div><div class="muted" style="margin:7px 2px 0">This is the same illustrated player portrait used on EBL Home, Player HQ, public profiles, rosters, and GameCast.</div><div class="card" style="margin-top:10px;text-align:center"><b>${escapeHtml(CREATOR.name||'Your Player')}</b><div class="muted">#${CREATOR.jersey_number} • ${escapeHtml(CREATOR.position||'EBL')} • ${current.label} • ${HAIR_NAMES[CREATOR.hair_id-1]} • ${(HAIR_COLORS[(CREATOR.hair_color_id||3)-1]||HAIR_COLORS[2]).name} hair • ${FACIAL_HAIR_NAMES[CREATOR.facial_hair_id-1]} • ${eye.name} eyes</div></div></div></div>
 <div class="eblSpaceTopMd"><button class="btn" data-ebl-action="creator-step" data-step="1">BACK</button> <button class="btn" data-ebl-action="creator-begin-attributes">NEXT: ATTRIBUTES</button></div>`;
 requestAnimationFrame(()=>renderCreator3D('creator3dPreview'));
}
function avatarMarkup(){ return stationaryPlayerSvg({...CREATOR,primary_pos:CREATOR.position||'UTIL'}); }
function pickFace(id){CREATOR.face_id=id;creatorAppearance()} function pickSkinTone(id){CREATOR.skin_color_id=Math.max(1,Math.min(8,Number(id)||1));creatorAppearance()} function pickHair(id){CREATOR.hair_id=id;creatorAppearance()} function pickHairColor(id){CREATOR.hair_color_id=id;creatorAppearance()} function pickFacialHair(id){CREATOR.facial_hair_id=id;creatorAppearance()} function pickEyeColor(id){CREATOR.eye_color_id=id;creatorAppearance()} function pickEyeBlack(id){CREATOR.eye_black_id=id;creatorAppearance()} function pickEyewear(id){CREATOR.eyewear_id=id;creatorAppearance()} function pickChain(id){CREATOR.chain_id=id;creatorAppearance()} function pickSleeve(id){CREATOR.sleeve_id=id;creatorAppearance()}
function beginAttributes(){
 let pitcher=CREATOR.position_group==='PITCHER',names=pitcher?PA:HA;
 if(!CREATOR.attributes || Object.keys(CREATOR.attributes).join(',')!==names.join(',')){CREATOR.attributes=Object.fromEntries(names.map(x=>[x,0]));CREATOR.pool=50}
 setCreatorStep(3);
}
  
let CREATOR_ATTR_TAB=null;


const CREATOR_ATTR_HELP={
 CON:'Contact — lowers swing-and-miss risk and helps you square up more pitches. Best for average-focused hitters and anyone who hates empty at-bats.',
 POW:'Power — raises exit velocity and extra-base-hit damage. Best for sluggers, but it works best when CON/TIM are high enough to actually square the ball up.',
 VIS:'Vision — helps recognize strikes, handle velocity/break, and avoid bad swings. A strong support stat for almost every hitter build.',
 DISC:'Discipline — cuts chase rate outside the zone and creates more walks. Great for patient on-base builds; less useful if you want an ultra-aggressive profile.',
 TIM:'Timing — improves barrel rate, reduces weak/foul contact, and produces cleaner launch angles. One of the strongest stats for turning swings into quality contact.',
 SPD:'Speed — improves steal pressure, steal success, and speed-created extra bases. Best when paired with BRIQ/LEAD instead of built alone.',
 BRIQ:'Baserunning Instinct — improves reads and decision-making on steals while lowering pickoff risk. Makes raw speed play smarter.',
 LEAD:'Lead / Pickoff — improves jumps, steal frequency/success, and pickoff avoidance. Pair with SPD for a true base-stealing threat.',
 FLD:'Fielding — lowers error risk and helps convert difficult balls into outs. More valuable at demanding defensive positions.',
 ARM:'Arm Strength — improves throwing impact; especially important for catchers controlling the running game and positions that need strong throws.',
 ACC:'Arm Accuracy — reduces throwing errors and helps defensive throws finish plays cleanly. Strongest when paired with ARM.',
 REAC:'Reaction — improves first step and range on balls in play. Helps good defenders reach plays that weaker defenders never get to.',
 CALL:'Call Game — catcher-only skill that gives the pitcher a subtle command and break boost while you are catching. Best for defense-first catchers.',
 STA:'Stamina — extends in-game endurance and also improves between-game fatigue recovery. It helps command, velocity, and break hold up deeper into outings, with diminishing returns at very high ratings.',
 PCLT:'Pitching Clutch — helps retain execution in late, close, high-leverage situations. More valuable for relievers/closers and pitchers who work tight games.',
 CTRL:'Control — governs how often you get the ball into the strike zone. Higher CTRL means fewer free passes and more chances to work from favorable counts.',
 CMD:'Command — governs where your strikes go. Higher CMD improves precision and edge execution, making strikes harder to square up instead of simply throwing more of them.',
 VEL:'Velocity — increases pitch speed, whiff pressure, and suppression of contact quality. A direct overpowering tool.',
 BRK:'Break — creates bigger pitch shape and swing-and-miss movement. Strong BRK makes sliders, curves and other breaking pitches harder to track and square up.',
 MOV:'Movement — creates late life and weak contact rather than only big break. Higher MOV suppresses exit velocity and nudges contact toward lower launch angles and more ground-ball style outcomes.',
 DEC:'Deception — makes pitches harder to read out of the hand. It improves swing difficulty and chase pressure, letting average raw stuff play above its radar-gun value.',
 SEQ:'Sequencing — improves how effectively your pitches work together. Better SEQ reduces predictable repeats and makes a changed look more effective, especially with two strikes.'
};
function creatorAttrHelp(k){return CREATOR_ATTR_HELP[k]||'Develop this skill to shape your player.'}

function creatorBuildGuideHtml(pitcher){
 if(pitcher){
  return `<div class="buildGuide">
   <div class="buildGuideCard"><b>POWER PITCHER</b><small>VEL + DEC + CTRL. Overpower hitters with speed and a hard-to-read delivery, but weak CMD can still leave too many hittable strikes.</small></div>
   <div class="buildGuideCard"><b>STRIKEOUT ARTIST</b><small>BRK + DEC + SEQ. Win with chase, changing looks and put-away pitches rather than pure strike throwing.</small></div>
   <div class="buildGuideCard"><b>COMMAND PITCHER</b><small>CTRL + CMD + SEQ. Live around the zone, hit better spots and stay unpredictable. Lower raw VEL/BRK means fewer easy overpowering outs.</small></div>
   <div class="buildGuideCard"><b>GROUND-BALL PITCHER</b><small>MOV + CMD + CTRL. Trade some strikeouts for weak contact, lower launch angles and more balls your defense can turn into outs.</small></div>
   <div class="buildGuideCard"><b>WORKHORSE STARTER</b><small>STA + CTRL + MOV. Hold your stuff deeper into games and keep traffic manageable over long outings.</small></div>
   <div class="buildGuideCard"><b>LATE-INNING RELIEVER</b><small>VEL + BRK + PCLT. Spend less on STA and lean into short-burst stuff for high-leverage innings.</small></div>
  </div><div class="buildTradeoff"><strong>Build rule:</strong> CTRL gets pitches into the zone; CMD puts them in better spots. BRK creates big swing-and-miss shape; MOV creates late weak-contact life. DEC makes stuff harder to read; SEQ makes the arsenal work together. STA and PCLT shape how that toolkit holds up.</div>`;
 }
 return `<div class="buildGuide">
  <div class="buildGuideCard"><b>CONTACT HITTER</b><small>Prioritize CON + TIM + VIS. You should put more balls in play and make cleaner contact, but sacrifice some top-end home-run power.</small></div>
  <div class="buildGuideCard"><b>SLUGGER</b><small>Prioritize POW + TIM, with enough CON/VIS to make the power usable. Huge damage ceiling, but a one-dimensional power build can still swing through pitches.</small></div>
  <div class="buildGuideCard"><b>ON-BASE HITTER</b><small>Prioritize DISC + VIS + CON. More walks and better at-bats, but less damage unless you invest in POW/TIM too.</small></div>
  <div class="buildGuideCard"><b>SPEED / DEFENSE</b><small>Prioritize SPD with BRIQ/LEAD, or FLD/REAC/ARM/ACC for defense. You create value outside pure hitting but give up offensive firepower.</small></div>
 </div><div class="buildTradeoff"><strong>Build rule:</strong> POW creates damage, but CON/VIS/TIM help you reach that damage more often. SPD works best with BRIQ/LEAD, and defensive stats matter most if you actually want your player to win value with the glove.</div>`;
}

const PLAYER_ATTR_INFO={
 CON:{name:'Contact',text:'Improves your ability to make contact when you swing. In-game it directly fights pitcher velocity, break and command in the whiff calculation, and it also raises batted-ball quality once you put the ball in play.',game:'More contact, fewer swinging misses, better average contact quality.'},
 POW:{name:'Power',text:'Raises the quality of balls you put in play. Power contributes heavily to exit velocity and also improves launch-angle quality, increasing doubles and home-run potential.',game:'More hard contact, extra-base hits and home-run damage.'},
 VIS:{name:'Vision',text:'Helps you recognize pitches and track the ball. Vision makes you more competitive against velocity and break, helps you swing at strikes, and reduces chase swings outside the zone.',game:'Better pitch recognition, fewer whiffs and fewer bad swings.'},
 DISC:{name:'Discipline',text:'Controls how willing your hitter is to chase pitches outside the strike zone. Higher Discipline sharply reduces chase rate, especially when combined with Vision.',game:'More walks, fewer chase swings and better plate appearances.'},
 TIM:{name:'Timing',text:'One of the biggest contact-quality skills. Timing fights velocity and break on swings, reduces foul-ball frequency, improves exit velocity and shifts launch angle toward more productive contact.',game:'More barrels, cleaner contact and fewer weak/foul swings.'},
 SPD:{name:'Speed',text:'Affects baserunning pressure and extra-base outcomes. Faster runners attempt more steals, succeed more often, and have a better chance to turn safe contact into triples.',game:'More steal chances, better steal success and more speed-created bases.'},
 BRIQ:{name:'Baserunning Instinct',text:'Represents reads and decision-making on the bases. It increases smart steal attempts and steal success while lowering pickoff risk.',game:'Better jumps, smarter aggression and fewer baserunning mistakes.'},
 LEAD:{name:'Lead / Pickoff',text:'Represents how well you take and manage leads. It increases steal frequency and success while reducing the chance of being picked off.',game:'Bigger controlled leads, stronger jumps and better pickoff avoidance.'},
 FLD:{name:'Fielding',text:'Your main defensive reliability rating. It lowers fielding-error risk and improves the chance of converting difficult balls in play into outs.',game:'Fewer errors and more difficult plays turned into outs.'},
 ARM:{name:'Arm Strength',text:'Controls throwing strength from your defensive position. For catchers it is the biggest defensive weapon against stolen-base attempts.',game:'Stronger throws and better control of the running game.'},
 ACC:{name:'Arm Accuracy',text:'Improves the accuracy of defensive throws. It lowers throwing-error risk and contributes to catcher defense against steals.',game:'Cleaner throws, fewer throwing errors and better runner control.'},
 REAC:{name:'Reaction',text:'Improves first-step response on balls in play. Reaction combines with Fielding to make difficult defensive plays and also helps reduce errors and catcher steal success against you.',game:'Better range, more great plays and more reliable defense.'},
 CALL:{name:'Call Game',text:'Catcher-only skill. While you are catching, Call Game gives your pitcher a subtle command and breaking-ball execution boost over the course of many plate appearances.',game:'Slightly better pitcher command and pitch movement when you catch.'},
 STA:{name:'Stamina',text:'Controls both in-game endurance and between-game recovery. Higher STA delays fatigue penalties during an outing and helps a pitcher shed workload fatigue between league days. Very high ratings use diminishing returns so an uncapped build cannot become permanently fresh.',game:'Longer effective outings and faster recovery between appearances.'},
 PCLT:{name:'Pitching Clutch',text:'Helps a pitcher retain command and movement in high-leverage late-game situations. It does not guarantee an out; it protects your physical skills when the game is tight.',game:'Better execution in late, close games.'},
 CTRL:{name:'Control',text:'Controls how often you reach the strike zone. Better Control cuts free passes and gives you more favorable counts, but it does not guarantee that every strike is well located.',game:'More strikes and fewer walks.'},
 CMD:{name:'Command',text:'Controls precision inside the zone. Command improves edge execution and makes strikes harder to square up, separating strike throwing from true location skill.',game:'Better locations, fewer hittable strikes and stronger edge execution.'},
 VEL:{name:'Velocity',text:'Raises pitch speed and makes swings more difficult. Velocity directly increases whiff pressure and also suppresses hitter contact quality when the ball is put in play.',game:'More overpowering pitches, more whiffs and weaker contact.'},
 BRK:{name:'Break',text:'Creates larger pitch shape and swing-and-miss movement. Break raises chase and whiff pressure, especially when paired with deception and sequencing.',game:'More chase, more missed bats and nastier put-away pitches.'},
 MOV:{name:'Movement',text:'Represents late life on the pitch rather than only big breaking-ball shape. Movement reduces contact quality and pushes more balls toward lower launch angles.',game:'More weak contact, lower launch angles and more ground-ball style outcomes.'},
 DEC:{name:'Deception',text:'Represents how difficult your delivery and pitch release are to read. Deception makes hitters later and less certain, letting your raw stuff play up.',game:'More swing difficulty and chase pressure, even without elite velocity.'},
 SEQ:{name:'Sequencing',text:'Represents how well your pitches set each other up. Better Sequencing makes your mix less predictable and rewards changing looks instead of repeating the same pitch.',game:'More effective pitch mixing and better two-strike finishing ability.'}
};
function closeAttrInfo(except=null){document.querySelectorAll('.attrInfoWrap.open').forEach(w=>{if(w!==except)w.classList.remove('open')})}
function toggleAttrInfo(btn,event){event.stopPropagation();const wrap=btn.closest('.attrInfoWrap');const opening=!wrap.classList.contains('open');closeAttrInfo(wrap);wrap.classList.toggle('open',opening)}
function attrInfoHtml(k){const i=PLAYER_ATTR_INFO[k]||{name:k,text:'Develop this skill to improve your player.',game:''};return `<span class="attrInfoWrap"><button type="button" class="attrInfoBtn" aria-label="About ${i.name}" title="About ${i.name}" data-ebl-action="creator-info-toggle" data-ebl-stop="1">i</button><span class="attrInfoBubble" data-ebl-action="stop-click" data-ebl-stop="1"><button type="button" class="attrInfoClose" aria-label="Close information" data-ebl-action="creator-info-close" data-ebl-stop="1">×</button><b>${i.name}</b>${i.text}${i.game?`<small><strong>In game:</strong> ${i.game}</small>`:''}</span></span>`}
document.addEventListener('click',()=>closeAttrInfo());
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeAttrInfo()});
function resetCreatorBuild(){
 const pitcher=CREATOR.position_group==='PITCHER',names=pitcher?PA:HA;
 CREATOR.attributes=Object.fromEntries(names.map(x=>[x,0]));
 CREATOR.pool=50;
 creatorAttributes();
}
function removeCreatorAttr(k){
 if(!CREATOR.attributes[k])return;
 CREATOR.attributes[k]--;
 CREATOR.pool++;
 creatorAttributes();
}

function creatorAttributes(){
    D={...CREATOR,pool:CREATOR.pool,attributes:CREATOR.attributes};


    const pitcher=CREATOR.position_group==='PITCHER';


    const groups=pitcher
        ? [
            {id:'buildPitch',title:'PITCHING CORE',attrs:['CTRL','CMD','VEL','BRK','MOV','DEC','SEQ']},
            {id:'buildTraits',title:'PITCHER TRAITS',attrs:['STA','PCLT']},
            {id:'buildField',title:'FIELDING',attrs:['FLD','ARM','ACC','REAC']}
          ]
        : [
            {id:'buildHit',title:'HITTING',attrs:['CON','POW','VIS','DISC','TIM']},
            {id:'buildField',title:'FIELDING',attrs:(CREATOR.position==='C'?['CALL','FLD','ARM','ACC','REAC']:['FLD','ARM','ACC','REAC'])},
            {id:'buildRun',title:'BASERUNNING',attrs:['SPD','BRIQ','LEAD']}
          ];


    if(!CREATOR_ATTR_TAB || !groups.some(g=>g.id===CREATOR_ATTR_TAB)){
        CREATOR_ATTR_TAB=groups[0].id;
    }


    creatorStage.innerHTML=`
        <div class="grid">
            <div class="statBox">
                <span class="label">STARTING POOL</span>
                <b>50 XP</b>
            </div>


            <div class="statBox">
                <span class="label">REMAINING</span>
                <b class="gold">${CREATOR.pool} XP</b>
            </div>


            <div class="statBox">
                <span class="label">SPENT</span>
                <b>${50-CREATOR.pool} XP</b>
            </div>
        </div>

        <div class="buildIntro">
            <b>Build your player with 50 starting XP</b>
            <p class="muted">Every +1 costs 1 starting XP on this screen. Your ratings are not cosmetic — they directly change what happens in the simulation. Concentrating points creates a real strength; spreading them out creates a safer all-around player. You must spend all 50 XP before creating your player.</p>
            ${creatorBuildGuideHtml(pitcher)}
            <div class="eblSpaceTopSm"><button class="btn ghost" data-ebl-action="creator-reset-build">Reset 50 XP Build</button></div>
        </div>


        <div class="statTabs">
            ${groups.map(g=>`
                <button
                    class="subtab ${g.id===CREATOR_ATTR_TAB?'active':''}"
                    data-ebl-action="creator-builder-tab" data-tab="${g.id}">
                    ${g.title}
                </button>
            `).join('')}
        </div>


        ${groups.map(g=>`
            <div
                id="${g.id}"
                class="statPane ${g.id===CREATOR_ATTR_TAB?'active':''}">
                ${g.attrs
                    .filter(a=>a in CREATOR.attributes)
                    .map(a=>creatorAttr(a))
                    .join('')}
            </div>
        `).join('')}

        ${pitcher?creatorPitchSelectorHtml():''}

        <div class="eblSpaceTopMd">
            <button class="btn" data-ebl-action="creator-step" data-step="2">BACK</button>
            <button class="btn" data-ebl-action="creator-review">NEXT: REVIEW</button>
        </div>
    `;
}


function creatorAttr(k){
    let v=CREATOR.attributes[k];
    return `
        <div class="attr">
            <div>
                <div class="attrNameRow"><b>${k}</b>${attrInfoHtml(k)}</div>
                <div class="attrHelp">${creatorAttrHelp(k)}</div>
                <div class="bar"><span style="width:${Math.min(100,v*4)}%"></span></div>
            </div>
            <div class="attrControls">
                <button class="btn ghost" data-ebl-action="creator-attr-remove" data-attribute="${k}" ${v<=0?'disabled':''}>−</button>
                <span><b>${v}</b></span>
                <button class="btn" data-ebl-action="creator-attr-add" data-attribute="${k}" ${CREATOR.pool<=0?'disabled':''}>+1</button>
            </div>
        </div>
    `;
}

function addCreatorAttr(k){
    if(CREATOR.pool<=0)return;


    CREATOR.attributes[k]++;
    CREATOR.pool--;


    creatorAttributes();
}


function builderTab(id,b){
    CREATOR_ATTR_TAB=id;


    const card=b.closest('.card')||document;


    card.querySelectorAll('.statPane')
        .forEach(x=>x.classList.remove('active'));


    card.querySelectorAll('.statTabs .subtab')
        .forEach(x=>x.classList.remove('active'));


    const pane=document.getElementById(id);


    if(pane)pane.classList.add('active');
    b.classList.add('active');
}
function attributeReview(){if(CREATOR.pool!==0)return eblAlert('Spend all 50 XP first.');if(CREATOR.position_group==='PITCHER'&&(!Array.isArray(CREATOR.pitches)||CREATOR.pitches.length!==3))return eblAlert('Choose exactly 3 starting pitches.');setCreatorStep(4)}
function creatorReview(){
 creatorStage.innerHTML=`<div class="two"><div class="card"><div class="identity"><div class="avatar">${initials(CREATOR.name)}</div><div><h2>${escapeHtml(CREATOR.name)}</h2><div class="muted">${CREATOR.position_group} • Preferred ${CREATOR.position} • Bats ${CREATOR.bats} • Throws ${CREATOR.throws}</div><div class="muted">From ${escapeHtml(CREATOR.hometown||'')}</div></div></div>
 <h3 class="eblSpaceTopMd">50-XP Build</h3><p class="muted">Review your starting strengths carefully. You can go back and rebalance before creating the player.</p>${Object.entries(CREATOR.attributes).map(([k,v])=>`<div class="attr"><b>${k}</b><span>${v}</span><span></span></div>`).join('')}${CREATOR.position_group==='PITCHER'?`<h3 class="eblSpaceTopMd">Starting Repertoire</h3><div class="legacyStrip">${(CREATOR.pitches||[]).map(k=>`<span class="legacyBadge">⚾ ${pitchCatalogRow(k)?.label||k}</span>`).join('')}</div><p class="muted">Three pitches are included at creation. A fourth costs 5 XP later; a fifth costs 8 XP.</p>`:''}</div>
 <div class="card"><h3>Appearance</h3><div class="avatarPreview">${avatarMarkup()}</div><p class="muted">Face ${CREATOR.face_id} • ${HAIR_NAMES[CREATOR.hair_id-1]} • ${FACIAL_HAIR_NAMES[CREATOR.facial_hair_id-1]} • ${(HAIR_COLORS[(CREATOR.hair_color_id||3)-1]||HAIR_COLORS[2]).name} hair • ${(EYE_COLORS[(CREATOR.eye_color_id||6)-1]||EYE_COLORS[5]).name} eyes</p></div></div>
 <button class="btn" data-ebl-action="creator-step" data-step="3">BACK</button> <button class="btn" data-ebl-action="creator-finish">CREATE EBL PLAYER</button>`;
}
async function finishCreator(){return onceAction('finishCreator',async()=>{
 try{
   if(!String(CREATOR.first_name||'').trim()||!String(CREATOR.last_name||'').trim())return eblAlert('First and last name are required. Go back to Basic Info.');
   if(!String(CREATOR.hometown_city||'').trim()||!String(CREATOR.hometown_region||'').trim())return eblAlert('City and state/country are required. Go back to Basic Info.');
   if(CREATOR.position!=='C' && CREATOR.attributes?.CALL){return eblAlert('CALL is a catcher-only rating. Set CALL back to 0 or choose C as your preferred position.');}
   if(CREATOR.position_group==='PITCHER'&&(!Array.isArray(CREATOR.pitches)||CREATOR.pitches.length!==3))return eblAlert('Choose exactly 3 starting pitches.');
   let payload={first_name:CREATOR.first_name,last_name:CREATOR.last_name,name:CREATOR.name,hometown_city:CREATOR.hometown_city,hometown_region:CREATOR.hometown_region,hometown:CREATOR.hometown||'',position_group:CREATOR.position_group,position:CREATOR.position,bats:CREATOR.bats,throws:CREATOR.throws,face_id:CREATOR.face_id,skin_color_id:CREATOR.skin_color_id||1,hair_id:CREATOR.hair_id,facial_hair_id:CREATOR.facial_hair_id,eye_color_id:CREATOR.eye_color_id,hair_color_id:CREATOR.hair_color_id,nose_id:CREATOR.nose_id||1,eye_shape_id:CREATOR.eye_shape_id||1,mouth_id:CREATOR.mouth_id||1,ear_size_id:CREATOR.ear_size_id||2,eye_black_id:CREATOR.eye_black_id,eyewear_id:CREATOR.eyewear_id,chain_id:CREATOR.chain_id,sleeve_id:CREATOR.sleeve_id,body_build_id:CREATOR.body_build_id||1,jersey_number:CREATOR.jersey_number,attributes:CREATOR.attributes,pitches:CREATOR.position_group==='PITCHER'?CREATOR.pitches:undefined};
   let created=await api('/api/player/create',{method:'POST',body:JSON.stringify(payload)});
   PLAYER_HQ_TAB='playerOverview';
   const newId=created?.player?.id||null;
   if(newId)localStorage.setItem('ebl_selected_player',String(newId));
   await loadPlayer(newId);
   renderHome();
   goPage('player');
 }catch(e){eblAlert(e.error||'Could not create player')}
})}
async function spend(a){return onceAction(`spend:${a}`,async()=>{
  try{
    await api('/api/player/spend-xp',{
      method:'POST',
      body:JSON.stringify({attribute:a,player_id:PLAYER?.id})
    });
    await loadPlayer();
    renderPlayer();renderHome();
    showCareerToast(`${a} UPGRADED • XP ${Number(PLAYER?.xp_wallet||0).toFixed(2)}`);
  }catch(e){
    showCareerToast(e.error||'Upgrade failed');
  }
})}
async function reportProfile(userId,username){
  const reason=await eblPrompt(`Report @${username}: briefly describe the issue.`,'');
  if(reason===null||!reason.trim())return;
  try{await api('/api/safety/report',{method:'POST',body:JSON.stringify({reported_user_id:userId,reason:'PROFILE_REPORT',detail:reason.trim()})});eblToast('Report sent to EBL moderation.','success');}
  catch(e){eblAlert(e.error||'Could not send report');}
}
async function blockProfile(userId,username){
  if(!await eblConfirm(`Block @${username}? They will no longer be able to privately message you.`,{title:'Block Member',confirmLabel:'BLOCK',tone:'danger'}))return;
  try{await api('/api/safety/block',{method:'POST',body:JSON.stringify({blocked_user_id:userId})});eblToast(`@${username} blocked.`,'success');const modal=document.getElementById('profileModal');if(modal?.open)modal.close();}
  catch(e){eblAlert(e.error||'Could not block member');}
}
async function market(){return onceAction(`market:${PLAYER?.id||'none'}`,async()=>{
 try{
  if(!PLAYER?.id){showCareerToast('Create or select a player first.');return;}
  showCareerToast('CONTACTING EBL CLUBS…');
  await api('/api/player/request-cpu-market',{method:'POST',body:JSON.stringify({player_id:PLAYER.id})});
  PLAYER_HQ_TAB='playerContracts';
  await loadPlayer(PLAYER.id);
  renderHome();renderPlayer();
  goPage('player');
  showCareerToast('CONTRACT OFFERS READY • Review your options');
 }catch(e){showCareerToast(e.error||'Could not request offers')}
})}

function showCareerToast(message){
 let el=document.getElementById('careerToast');
 if(!el){
  el=document.createElement('div');el.id='careerToast';el.className='careerToast';
  el.setAttribute('role','status');el.setAttribute('aria-live','polite');
  document.body.appendChild(el);
 }
 el.textContent=message;el.classList.add('show');
 clearTimeout(window.EBL_CAREER_TOAST_TIMER);
 window.EBL_CAREER_TOAST_TIMER=setTimeout(()=>el.classList.remove('show'),4200);
}

async function refreshPlayerSourceOfTruth(playerId,{includeTeam=false}={}){
 const failures=[];
 // The player row is authoritative. Load it first so every downstream view sees the
 // newly committed franchise_id, contract, jersey number, XP wallet, and team identity.
 try{await loadPlayer(playerId)}catch(e){failures.push({surface:'player',error:e})}
 const core=[];
 if(typeof loadLeague==='function')core.push(['league',()=>loadLeague()]);
 if(typeof loadSchedule==='function')core.push(['schedule',()=>loadSchedule()]);
 if(typeof window.loadPublicDirectory==='function')core.push(['directory',()=>window.loadPublicDirectory(true)]);
 const coreResults=await Promise.allSettled(core.map(x=>x[1]()));
 coreResults.forEach((r,i)=>{if(r.status==='rejected')failures.push({surface:core[i][0],error:r.reason})});

 // These surfaces all derive player/team identity from the same database state. A failed
 // secondary refresh must never make a completed signing look like it failed.
 const downstream=[];
 if(includeTeam&&typeof loadMyTeam==='function')downstream.push(['team',()=>loadMyTeam()]);
 if(typeof loadAwards==='function')downstream.push(['awards',()=>loadAwards()]);
 if(typeof loadAnalytics==='function')downstream.push(['analytics',()=>loadAnalytics()]);
 if(typeof loadNews==='function')downstream.push(['news',()=>loadNews()]);
 if(typeof loadCommunity==='function')downstream.push(['community',()=>loadCommunity()]);
 if(typeof loadDMContacts==='function')downstream.push(['messages',()=>loadDMContacts()]);
 if(typeof loadChat==='function')downstream.push(['team-chat',()=>loadChat('TEAM')]);
 const downstreamResults=await Promise.allSettled(downstream.map(x=>x[1]()));
 downstreamResults.forEach((r,i)=>{if(r.status==='rejected')failures.push({surface:downstream[i][0],error:r.reason})});
 try{renderHome()}catch(e){failures.push({surface:'home-render',error:e})}
 try{renderPlayer()}catch(e){failures.push({surface:'player-render',error:e})}
 if(failures.length)console.warn('EBL source-of-truth refresh had partial failures',failures);
 return failures;
}

async function respond(id,action){return onceAction(`offer:${id}`,async()=>{
 const playerId=PLAYER?.id;
 if(!playerId){showCareerToast('Select a player first.');return;}
 const priorOffer=(PLAYER?.offers||[]).find(o=>Number(o.id)===Number(id))||{};
 const priorFid=priorOffer.franchise_id||priorOffer.team_id||'';
 const priorCachedName=priorFid?teamName(priorFid):'';
 const priorTeamName=priorOffer.team_display_name||priorOffer.team_name||((priorCachedName&&String(priorCachedName)!==String(priorFid))?priorCachedName:'');
 let result;
 try{
  result=await api('/api/player/respond-offer',{method:'POST',body:JSON.stringify({offer_id:id,action,player_id:playerId})});
 }catch(e){
  showCareerToast(e?.detail||e?.error||'Could not update offer');
  return;
 }

 PLAYER_HQ_TAB=(action==='ACCEPT'?'playerOverview':'playerContracts');
 const failures=await refreshPlayerSourceOfTruth(playerId,{includeTeam:action==='ACCEPT'});
 const fid=PLAYER?.franchise_id||result?.franchise_id||priorFid||'';
 const cachedName=fid?teamName(fid):'';
 const name=result?.team_display_name||result?.team_name||priorTeamName||PLAYER?.team?.display_name||PLAYER?.team?.name||((cachedName&&String(cachedName)!==String(fid))?cachedName:'EBL club');

 if(action==='ACCEPT'){
  showCareerToast(`SIGNED • Welcome to ${name}${result?.assigned_role?` • Role: ${result.assigned_role}`:''}`);
  if(fid)goPage('team');
 }else if(action==='HOLD'){
  showCareerToast(`Offer held • ${name}`);
 }else{
  showCareerToast(`Offer declined • ${name}`);
 }

 // A successful contract mutation stays successful even if one noncritical screen could
 // not refresh immediately. The next navigation will fetch that surface again.
 if(failures.length&&action==='ACCEPT')console.warn('Signing committed; one or more views will retry on next open.');
})}
async function loadLeague(){
 let j=await api('/api/league');
 LEAGUE=j;window.LEAGUE=LEAGUE;
 renderStandings();
 renderBetaStatus();
 // Schedule and GameCast load in parallel with League on first boot.
 // Repaint them once canonical franchise names/logos are available so raw EBL-Fxx
 // ids can never remain on screen after the source of truth arrives.
 if(Array.isArray(SCHEDULE)){
   renderSchedule();
   renderTicker();
   renderGamecastList();
   refreshPlayerRecentGames();
 }
 if(PLAYER)renderPlayer();
}
const GENESIS_PLAYER_TARGET=150;
function renderBetaStatus(){
 const box=document.getElementById('betaStatusCard');if(!box||!LEAGUE)return;
 const season=Number(LEAGUE.season||1),day=Number(LEAGUE.day||0),phase=String(LEAGUE.phase||'REGULAR').toUpperCase();
 const waitingForGenesis=season===1&&day===0&&(phase==='REGULAR'||phase==='PRESEASON');
 const targetRaw=Number(READINESS?.genesis_player_target);
 const genesisTarget=Number.isFinite(targetRaw)&&targetRaw>0?Math.floor(targetRaw):GENESIS_PLAYER_TARGET;
 const humanRaw=Number(READINESS?.human);
 const countKnown=Number.isFinite(humanRaw);
 const humanPlayers=countKnown?Math.max(0,Math.floor(humanRaw)):0;
 const pct=countKnown?Math.max(0,Math.min(100,Math.round((humanPlayers/genesisTarget)*100))):0;
 const remaining=countKnown?Math.max(0,genesisTarget-humanPlayers):GENESIS_PLAYER_TARGET;
 if(waitingForGenesis){
  const countLine=countKnown?`<b>${humanPlayers} / ${genesisTarget} PLAYERS</b><span>${remaining>0?`${remaining} player${remaining===1?'':'s'} until Opening Day`:'Opening Day target reached'}</span>`:`<b>OPENING DAY TARGET: ${genesisTarget}</b><span>Loading current Genesis registration…</span>`;
  box.innerHTML=`<div class="betaStatusHead"><div><span class="betaSiteBadge">GENESIS REGISTRATION</span><h2>Season 1 Begins at ${genesisTarget} Players</h2><div class="muted">Create your ballplayer before Opening Day. Season 1 begins once ${genesisTarget} human players have entered the league.</div></div><button class="btn ghost" data-ebl-action="open-beta-feedback">Send Feedback</button></div><div class="genesisProgress"><div class="genesisProgressText">${countLine}</div><div class="genesisProgressBar" role="progressbar" aria-label="Genesis player registration progress" aria-valuemin="0" aria-valuemax="${genesisTarget}" aria-valuenow="${countKnown?humanPlayers:0}"><span style="width:${pct}%"></span></div></div><div class="betaStatusGrid"><div class="betaStatusStat"><b>PRESEASON</b><span>Registration open • Opening Day unlocks at ${genesisTarget} players.</span></div><div class="betaStatusStat"><b>Build Your Player</b><span>Create, develop, and prepare your ballplayer before the first pitch.</span></div><div class="betaStatusStat"><b>Player-only Launch</b><span>CPU clubs manage teams during Genesis; human coaching opens later.</span></div></div><div class="muted eblSpaceTopSm"><b>Beta notice:</b> EBL is still being tested and balanced before official launch. Careers, statistics, progression, and league systems may be adjusted or reset during Genesis.</div>`;
  return;
 }
 const phaseLabel=phase==='REGULAR'?`Calendar Day ${day}/95`:phase.replaceAll('_',' ');
 const half=day<=49?'FIRST HALF':day<=95?'SECOND HALF':'POSTSEASON';
 box.innerHTML=`<div class="betaStatusHead"><div><span class="betaSiteBadge">EBL BETA</span><h2>Season ${season} Is Live</h2><div class="muted">Season ${season} is underway. Follow your player, club, statistics, contracts, awards, and league history as the schedule develops.</div></div><button class="btn ghost" data-ebl-action="open-beta-feedback">Send Feedback</button></div><div class="betaStatusGrid"><div class="betaStatusStat"><b>${phaseLabel}</b><span>${half}</span></div><div class="betaStatusStat"><b>Player-only Beta</b><span>CPU clubs manage teams; human coaching opens later.</span></div><div class="betaStatusStat"><b>Pitcher Recovery</b><span>100% after Day 49 / All-Star break, before playoffs, and on Opening Day.</span></div></div><div class="muted eblSpaceTopSm"><b>Beta notice:</b> balance, careers, statistics, and league history may be adjusted or reset before official launch. Found a problem? Please send it — that is what the beta is for.</div>`;
}

function playoffPicture(){
  const gamesPlayed=(LEAGUE?.teams||[]).reduce((n,t)=>n+Number(t.wins||0)+Number(t.losses||0),0);
  if((LEAGUE?.day||0)<1 || gamesPlayed===0)return {champs:new Set(),wc1:null,wc2:null,active:false};
  const champs=[];
  for(const d of (LEAGUE?.divisions||[])){
    const ts=(LEAGUE.teams||[]).filter(t=>t.division===d).sort((a,b)=>b.wins-a.wins||((b.runs_for-b.runs_against)-(a.runs_for-a.runs_against))||b.runs_for-a.runs_for);
    if(ts[0])champs.push(ts[0].id);
  }
  const rest=(LEAGUE?.teams||[]).filter(t=>!champs.includes(t.id)).sort((a,b)=>b.wins-a.wins||((b.runs_for-b.runs_against)-(a.runs_for-a.runs_against))||b.runs_for-a.runs_for);
  return {champs:new Set(champs),wc1:rest[0]?.id,wc2:rest[1]?.id,active:true};
}
function renderStandings(){
  if(!LEAGUE)return;
  const pic=playoffPicture();
  let html=`<div class="gold">Season ${LEAGUE.season} • League Day ${LEAGUE.day}</div>`;
  if(pic.active)html+=`<p class="muted"><span class="playoffMark">DIV</span> current division leader &nbsp; <span class="playoffMark">WC1</span>/<span class="playoffMark">WC2</span> current wild cards</p>`;
  for(const d of LEAGUE.divisions){
    const teams=LEAGUE.teams.filter(t=>t.division===d).sort((a,b)=>b.wins-a.wins||((b.runs_for-b.runs_against)-(a.runs_for-a.runs_against)));
    const lead=teams[0]?.wins||0;
    html+=`<div class="division"><h3>${d} Division</h3><div class="tablewrap"><table class="standingsTable"><thead><tr><th>Team</th>${pic.active?'<th class="seedCell">STATUS</th>':''}<th>W</th><th>L</th><th>PCT</th><th>GB</th><th>RS</th><th>RA</th><th>DIFF</th></tr></thead><tbody>${teams.map(t=>{
      const g=t.wins+t.losses,pct=g?t.wins/g:0,gb=((lead-t.wins)+(t.losses-(teams[0]?.losses||0)))/2;
      const mark=pic.champs.has(t.id)?'<span class="playoffMark">DIV</span>':t.id===pic.wc1?'<span class="playoffMark">WC1</span>':t.id===pic.wc2?'<span class="playoffMark">WC2</span>':'';
      return `<tr class="${PLAYER?.franchise_id===t.id?'meRow':''}"><td><span class="standingsTeamRef">${teamMark(t.id,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${t.id}">${t.name}</button></span></td>${pic.active?`<td class="seedCell">${mark||'—'}</td>`:''}<td>${t.wins}</td><td>${t.losses}</td><td>${pct.toFixed(3).replace(/^0/,'')}</td><td>${gb<=0?'—':gb.toFixed(1)}</td><td>${t.runs_for}</td><td>${t.runs_against}</td><td>${t.runs_for-t.runs_against>=0?'+':''}${t.runs_for-t.runs_against}</td></tr>`;
    }).join('')}</tbody></table></div></div>`;
  }
  standingsPane.innerHTML=html;
}
async function loadSchedule(){
 const gcRoot=document.getElementById('gamecastList');
 try{
  const j=await api('/api/schedule');
  SCHEDULE=Array.isArray(j.games)?j.games:[];
  // Keep the archive independent from the League schedule/ticker surfaces. A render
  // problem elsewhere must never leave GameCast blank.
  renderGamecastList();
  try{renderSchedule()}catch(e){console.warn('EBL schedule render failed',e)}
  try{renderTicker()}catch(e){console.warn('EBL ticker render failed',e)}
  try{refreshPlayerRecentGames()}catch(e){console.warn('EBL recent-game refresh failed',e)}
  return j;
 }catch(e){
  if(gcRoot)gcRoot.innerHTML=`<div class="card eblSpaceTopMd"><b>GameCast archive unavailable.</b><div class="muted">${escapeHtml(String(e?.error||e?.message||'Could not load completed games.'))}</div></div>`;
  throw e;
 }
}
async function loadPlayoffs(){
  const pane=document.getElementById('playoffsPane');
  if(!pane)return;
  try{
    const j=await api('/api/playoffs/bracket');
    const phase=String(j.phase||'REGULAR');
    const currentRound=String(j.round||'');
    const champId=j.champion||'';
    const champName=champId?teamName(champId):'';
    const roundLabel=currentRound?currentRound.replaceAll('_',' '):'Not started';
    const status=phase==='REGULAR'
      ? `<div class="playoffStatus"><b>PLAYOFF RACE</b><div class="muted">Season ${j.season} postseason field is still being decided. The bracket will populate when playoff games are created.</div></div>`
      : phase==='PLAYOFFS'
        ? `<div class="playoffStatus"><b>EBL PLAYOFFS • ${roundLabel}</b><div class="muted">Season ${j.season} postseason is underway.</div></div>`
        : `<div class="playoffStatus"><b>SEASON ${j.season} COMPLETE</b><div>${champName?`🏆 <button class="clickableName" data-ebl-action="open-team" data-team="${champId}">${champName}</button> — EBL Champions`:'Postseason complete'}</div></div>`;

    const rounds=(j.rounds||[]).map(r=>{
      const cards=(r.series||[]).map(series=>{
        const teams=series.teams||[];
        const teamRows=teams.length?teams.map(t=>{
          const win=series.winner_id===t.id;
          return `<div class="seriesTeam ${win?'seriesWinner':''}"><span class="seriesTeamIdentity">${teamMark(t.id,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${t.id}">${escapeHtml(String(t.name||teamName(t.id)||t.id))}</button></span><b>${Number(t.wins||0)}</b></div>`;
        }).join(''):'<div class="muted">Matchup not set</div>';
        const games=(series.games||[]).filter(g=>g.status==='FINAL');
        const latest=games.length?games[games.length-1]:null;
        const footer=series.winner_name
          ? `<div class="gold seriesWinnerLine eblSpaceTopTiny">Winner: ${series.winner_id?teamMark(series.winner_id,true):''} ${escapeHtml(String(series.winner_name))}</div>`
          : latest?`<div class="muted seriesLatest eblSpaceTopTiny">${teamMark(latest.away_id,true)} ${teamName(latest.away_id)} ${latest.away_runs}-${latest.home_runs} ${teamName(latest.home_id)} ${teamMark(latest.home_id,true)}</div>`
          : `<div class="muted eblSpaceTopTiny">Best of ${Number(series.wins_needed||0)*2-1}</div>`;
        return `<div class="seriesCard"><div class="seriesCode">${escapeHtml(String(series.code||''))}</div>${teamRows}${footer}</div>`;
      }).join('');
      return `<div class="bracketRound"><h3>${escapeHtml(String(r.name||''))}</h3>${cards||'<p class="muted">Not set</p>'}</div>`;
    }).join('');

    pane.innerHTML=status+`<div class="bracket">${rounds}</div>`;
  }catch(e){
    pane.innerHTML=`<div class="playoffStatus"><b>Playoff bracket unavailable</b><div class="muted">${escapeHtml(String(e?.error||e?.message||'Unable to load bracket'))}</div></div>`;
  }
}
function renderSchedule(){let day=LEAGUE?.day||0,filterTeam=PLAYER?.franchise_id;let upcoming=SCHEDULE.filter(g=>g.league_day>=Math.max(1,day) && g.league_day<=day+7);schedulePane.innerHTML=`<div class="muted" style="margin:0 0 10px">81 games • 27 three-game series • 95-day calendar • team off days built between selected series</div><div class="subtabs"><button class="subtab active" data-ebl-action="schedule-filter" data-filter="ALL">ALL EBL</button><button class="subtab" data-ebl-action="schedule-filter" data-filter="MINE">MY TEAM</button></div><div id="scheduleRows">${scheduleRows(upcoming,'ALL')}</div>`}
function scheduleFilter(mode,b){
 const pane=document.getElementById('schedulePane');
 if(!pane)return;
 pane.querySelectorAll('.subtab').forEach(x=>x.classList.remove('active'));
 if(b)b.classList.add('active');
 const day=Number(LEAGUE?.day||0);
 const upcoming=(Array.isArray(SCHEDULE)?SCHEDULE:[]).filter(g=>Number(g.league_day)>=Math.max(1,day)&&Number(g.league_day)<=day+7);
 const rows=document.getElementById('scheduleRows');
 if(rows)rows.innerHTML=scheduleRows(upcoming,mode);
}


function renderGamecastList(){
 const root=document.getElementById('gamecastList');
 if(!root)return;

 const finals=(Array.isArray(SCHEDULE)?SCHEDULE:[])
   .filter(g=>String(g.status||'').toUpperCase()==='FINAL')
   .sort((a,b)=>Number(b.league_day||0)-Number(a.league_day||0)||String(b.id||'').localeCompare(String(a.id||'')));

 if(!finals.length){
   root.innerHTML='<div class="card eblSpaceTopMd"><b>No completed games yet.</b><div class="muted">Completed league games will appear here automatically after Sim Day finishes.</div></div>';
   return;
 }

 const byDay=new Map();
 finals.forEach(g=>{
   const d=Number(g.league_day||0);
   if(!byDay.has(d))byDay.set(d,[]);
   byDay.get(d).push(g);
 });

 const myTeam=PLAYER?.franchise_id||'';
 const html=[...byDay.entries()].map(([day,games])=>{
   const cards=games.map(g=>{
     const awayName=teamName(g.away_id);
     const homeName=teamName(g.home_id);
     const mine=myTeam&&(g.away_id===myTeam||g.home_id===myTeam);
     return `<button class="gcArchiveGame ${mine?'mine':''}" data-ebl-action="watch-game" data-game="${jsq(g.id)}" aria-label="Open ${escapeHtml(awayName)} at ${escapeHtml(homeName)} GameCast">
       <div class="gcArchiveTeams">
         <span class="gcArchiveTeam">${teamMark(g.away_id,true)}<span>${escapeHtml(awayName)}</span><b>${Number(g.away_runs??0)}</b></span>
         <span class="gcArchiveTeam">${teamMark(g.home_id,true)}<span>${escapeHtml(homeName)}</span><b>${Number(g.home_runs??0)}</b></span>
       </div>
       <span class="gcArchiveWatch">FINAL • WATCH</span>
     </button>`;
   }).join('');
   return `<section class="gcArchiveDay"><div class="gcArchiveDayHead"><b>League Day ${day}</b><span class="muted">${games.length} game${games.length===1?'':'s'}</span></div><div class="gcArchiveGrid">${cards}</div></section>`;
 }).join('');

 root.innerHTML=html;
}
function scheduleRows(games,mode){
 const list=Array.isArray(games)?games:[];
 if(mode==='MINE'&&PLAYER?.franchise_id){
   const fid=PLAYER.franchise_id,start=Math.max(1,Number(LEAGUE?.day||0)),end=Math.min(95,start+7),byDay=new Map();
   list.filter(g=>g.away_id===fid||g.home_id===fid).forEach(g=>byDay.set(Number(g.league_day),g));
   const rows=[];
   for(let d=start;d<=end;d++){
     const g=byDay.get(d);
     if(!g){rows.push(`<div class="game brandedGame offDay"><div class="gameLine"><span><b>Day ${d}</b> • OFF DAY</span><span class="muted">RECOVERY / TRAVEL</span></div></div>`);continue}
     rows.push(`<div class="game brandedGame" ${g.status==='FINAL'?`data-ebl-action="watch-game" data-game="${g.id}"`:''}><div class="gameLine"><span><b>Day ${g.league_day}</b> • <span class="gameTeam">${teamMark(g.away_id,true)} ${teamName(g.away_id)}</span> <b>@</b> <span class="gameTeam">${teamMark(g.home_id,true)} ${teamName(g.home_id)}</span></span><span class="${g.status==='FINAL'?'green':'muted'}">${g.status==='FINAL'?`${g.away_runs}-${g.home_runs} • WATCH`:'UPCOMING'}</span></div></div>`);
   }
   return rows.join('');
 }
 return list.map(g=>`<div class="game brandedGame" ${g.status==='FINAL'?`data-ebl-action="watch-game" data-game="${g.id}"`:''}><div class="gameLine"><span><b>Day ${g.league_day}</b> • <span class="gameTeam">${teamMark(g.away_id,true)} ${teamName(g.away_id)}</span> <b>@</b> <span class="gameTeam">${teamMark(g.home_id,true)} ${teamName(g.home_id)}</span></span><span class="${g.status==='FINAL'?'green':'muted'}">${g.status==='FINAL'?`${g.away_runs}-${g.home_runs} • WATCH`:'UPCOMING'}</span></div></div>`).join('')||'<p class="muted">No games in this window.</p>';
}
function eblAvatarHtml(player,size='card'){
 const safe=['mini','card','hero'].includes(size)?size:'card';
 const model=eblAppearanceModel(player);
 return `<div class="eblIdentityPortrait eblIdentityPortrait--${safe}">${stationaryPlayerSvg(model,safe==='mini')}</div>`;
}
function eblPlayerIdentityHtml(player,size='mini'){
 const q=typeof eblGetIdentity==='function'?eblGetIdentity(player||{}):(player||{});
 const mapped=size==='hero'?'lg':size==='card'?'md':'xs';
 if(typeof eblIdentityLink==='function') return eblIdentityLink(q,{size:mapped});
 const name=escapeHtml(String(q?.name||q?.player_name||'Player'));
 return `<div class="playerIdentityRow">${eblAvatarHtml(q,size)}<div class="playerIdentityText">${name}</div></div>`;
}
function eblPlayerFeatureHtml(player,kicker='EBL PLAYER'){
 const name=leaguePlayerName(player);
 const team=escapeHtml(String(player?.team_name||player?.team||teamName(player?.franchise_id)||'EBL'));
 const teamIdentity=player?.franchise_id?`<span class="featureTeamRef">${teamMark(player.franchise_id,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(player.franchise_id)}">${team}</button></span>`:team;
 const pos=escapeHtml(String(player?.primary_pos||player?.position||''));
 const num=Number(player?.jersey_number||0);
 return `<div class="eblPlayerFeature">${eblPublicPortrait(player,'lg')}<div class="eblPlayerFeatureCopy"><span class="eblPlayerFeatureKicker">${escapeHtml(kicker)}</span><strong>${name}</strong><span>${team}${pos?` • ${pos}`:''}${num?` • #${num}`:''}</span></div></div>`;
}
function leaguePlayerIdentity(x,size='mini'){
 const q=typeof eblGetIdentity==='function'?eblGetIdentity(x||{}):(x||{});
 if(typeof eblIdentityLink==='function'){
   const mapped=size==='card'?'md':size==='mini'?'xs':'sm';
   return eblIdentityLink(q,{size:mapped});
 }
 const link=leaguePlayerName(q);
 return q?.face_id?`<span class="leagueIdentity">${eblAvatarHtml(q,size)}<span class="leagueIdentityName">${link}</span></span>`:link;
}
function leaguePlayerName(x){
 const name=escapeHtml(String(x?.name||x?.player_name||x?.holder_name||'Player'));
 if(x?.username)return `<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(x.username)}">${name}</button>`;
 const pid=Number(x?.id||x?.player_id||x?.holder_player_id||0);
 return pid?`<button class="clickableName" data-ebl-action="open-player-card" data-player="${pid}">${name}</button>`:name;
}
async function loadAnalytics(){
 let j=await api('/api/analytics'),L=j.league;
 const xpTable=(ME?.role==='COMMISSIONER'&&Object.keys(j.xp||{}).length)?`<h3>Commissioner XP Economy</h3><table><tr><th>Source</th><th>Total XP</th><th>Events</th></tr>${Object.entries(j.xp).map(([k,v])=>`<tr><td>${k}</td><td>${v.total.toFixed(3)}</td><td>${v.events}</td></tr>`).join('')}</table>`:'';
 aLeague.innerHTML=`<div class="grid">${[['Games',L.games],['Runs/Game',L.runs_per_game.toFixed(2)],['AVG',fmt3(L.avg)],['K%',(L.k_pct*100).toFixed(1)+'%'],['BB%',(L.bb_pct*100).toFixed(1)+'%'],['HR%',(L.hr_pct*100).toFixed(1)+'%']].map(x=>statBox(x[0],x[1])).join('')}</div>${xpTable}`;
 aBat.innerHTML=`<div class="tablewrap"><table><tr><th>#</th><th>Player</th><th>Team</th><th>Pos</th><th>OPS</th><th>HR</th><th>XP</th></tr>${j.leaders.ops.map((x,i)=>`<tr><td>${i+1}</td><td>${leaguePlayerIdentity(x)}</td><td><span class="analyticsTeamRef">${teamMark(x.team,true)}<button class="clickableName" data-ebl-action="open-team" data-team="${jsq(x.team)}">${escapeHtml(x.team_display_name||x.team_name||teamName(x.team))}</button></span></td><td>${x.pos}</td><td>${x.ops.toFixed(3)}</td><td>${x.hr}</td><td>${x.xp.toFixed(3)}</td></tr>`).join('')}</table></div>`;
 aPitch.innerHTML=`<div class="tablewrap"><table><tr><th>#</th><th>Pitcher</th><th>Team</th><th>ERA</th><th>WHIP</th><th>SO</th><th>XP</th></tr>${j.leaders.pitching.map((x,i)=>`<tr><td>${i+1}</td><td>${leaguePlayerIdentity(x)}</td><td><span class="analyticsTeamRef">${teamMark(x.team,true)}<button class="clickableName" data-ebl-action="open-team" data-team="${jsq(x.team)}">${escapeHtml(x.team_display_name||x.team_name||teamName(x.team))}</button></span></td><td>${x.era.toFixed(2)}</td><td>${x.whip.toFixed(2)}</td><td>${x.so}</td><td>${x.xp.toFixed(3)}</td></tr>`).join('')}</table></div>`;
}
async function loadAwards(){
 let j=await api('/api/awards');const xp=j.xp_values||{};
 // Awards may load before League on first boot. Resolve the canonical franchise
 // directory before rendering so internal EBL-Fxx ids never leak into award races.
 if(!LEAGUE?.teams?.length){try{await loadLeague()}catch(e){}}
 const teamRef=x=>awardTeamRef(x?.team,x?.team_display_name||x?.team_name||'');
 mvpPane.innerHTML=`<p class="gold">MVP winner: +${xp.MVP||15} XP</p>`+raceList(j.mvp,x=>`${x.pos} • ${teamRef(x)} • OPS ${x.ops.toFixed(3)} • ${x.hr} HR`);
 batTitle.innerHTML=`<p class="gold">Batting Title: +${xp.BATTING_TITLE||10} XP</p>`+raceList(j.batting,x=>`${teamRef(x)} • AVG ${x.avg.toFixed(3)} • OBP ${x.obp.toFixed(3)}`);
 pitchTitle.innerHTML=`<h3>Pitcher of the Season</h3><p class="muted">Eligibility: starting pitchers (SP) only.</p><p class="gold">Winner: +${xp.PITCHER_OF_SEASON||15} XP</p>${raceList(j.starting_pitching||[],x=>`${teamRef(x)} • ERA ${x.era.toFixed(2)} • WHIP ${x.whip.toFixed(2)} • ${x.so} K`)}<h3 class="eblSpaceTopLg">Reliever of the Season</h3><p class="muted">Eligibility: relief pitchers only (RP, MR, LR, SU and CL bullpen roles).</p><p class="gold">Winner: +${xp.RELIEVER_OF_SEASON||10} XP</p>${raceList(j.relief_pitching||[],x=>`${teamRef(x)} • ERA ${x.era.toFixed(2)} • WHIP ${x.whip.toFixed(2)} • ${x.so} K • ${x.sv||0} SV`)}`;
 sbTitle.innerHTML=`<p class="gold">Stolen Base Title: +${xp.SB_TITLE||10} XP</p>`+raceList(j.stolen_bases,x=>`${teamRef(x)} • ${x.sb} SB • OBP ${x.obp.toFixed(3)}`);
 const as=document.getElementById('allStarPane'),asg=j.all_star||null;
 if(as){
   const roster=(rows,label)=>`<div class="card"><h3>${label}</h3><div class="legacyStrip">${(rows||[]).map(x=>`<span class="legacyBadge">⭐ ${leaguePlayerName(x)} • ${awardTeamRef(x.franchise_id)}</span>`).join('')||'<span class="muted">Selections post at the All-Star break.</span>'}</div></div>`;
   as.innerHTML=asg?`<div class="grid"><div class="statBox"><span class="label">GOLD ALL-STARS</span><b>${Number(asg.gold_runs||0)}</b></div><div class="statBox"><span class="label">RED ALL-STARS</span><b>${Number(asg.red_runs||0)}</b></div><div class="statBox"><span class="label">SELECTION BONUS</span><b>+${Number(xp.ALL_STAR_SELECTION||1).toFixed(0)} XP</b></div><div class="statBox"><span class="label">MIDSEASON BREAK</span><b>After Day ${Number(asg.league_day||49)}</b></div></div><p class="muted">Every selection receives a permanent All-Star badge and selection XP. Players also earn normal performance-style game XP for appearing in the exhibition.</p>${roster(asg.gold_roster,'Gold All-Stars')}${roster(asg.red_roster,'Red All-Stars')}`:`<h2>EBL All-Star Game</h2><p class="gold">All-Star selection: +${Number(xp.ALL_STAR_SELECTION||1).toFixed(0)} XP + permanent career badge</p><p class="muted">The All-Star Game is played automatically at the midseason break. Selected players also earn game-performance XP for participating.</p>`;
 }
 fieldTitle.innerHTML=`<p class="gold">Each positional Fielding Title: +${xp.FIELDING||10} XP</p>`+Object.entries(j.fielding).map(([pos,rows])=>`<h3>${pos}</h3>${raceList(rows,x=>`${teamRef(x)} • OAA ${Number(x.oaa||0).toFixed(2)} • ${x.e||0} E • ${x.fld_pct||'1.000'} FLD`)}`).join('');
 if(j.history?.length){fieldTitle.innerHTML+=`<h2 style="margin-top:20px">Award History</h2>${j.history.slice(0,30).map(a=>`<div class="recordCard"><b>${a.award_name}</b> — ${leaguePlayerName(a)} <span class="gold">+${a.xp_awarded} XP</span><div class="muted">Season ${a.season} • ${String(a.period).replaceAll('_',' ')}</div></div>`).join('')}`}
}

function awardTeamRef(fid,label=''){
 if(fid===undefined||fid===null||fid==='')return '';
 const resolved=String(label||teamName(fid)||fid);
 return `<span class="awardTeamInline">${teamMark(fid,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(fid)}">${escapeHtml(resolved)}</button></span>`;
}
function raceList(rows,detail){return rows.length?rows.map((x,i)=>`<div class="race awardRaceRow"><span class="medal awardRaceRank">${i+1}</span>${x?.face_id?`<div class="raceIdentity awardRaceIdentity">${eblPublicPortrait(x,'sm')}<div class="awardRaceCopy"><b class="awardRacePlayer">${leaguePlayerName(x)}</b><div class="muted awardRaceDetail">${detail(x)}</div></div></div>`:`<div class="awardRaceCopy"><b class="awardRacePlayer">${leaguePlayerName(x)}</b><div class="muted awardRaceDetail">${detail(x)}</div></div>`}<span class="awardRaceTrophy">${i<3?'🏆':''}</span></div>`).join(''):'<p class="muted">Race begins on Opening Day.</p>'}
function dismissOnboarding(){
 try{localStorage.setItem('ebl_onboarding_dismissed','1')}catch{}
 if(window.onboardingCard)onboardingCard.classList.add('hidden');
}
function onboardingDismissed(){
 try{return localStorage.getItem('ebl_onboarding_dismissed')==='1'}catch{return false}
}
function cycleHomePlayer(dir){
 if(!ACTIVE_PLAYERS.length)return;
 const current=ACTIVE_PLAYERS.findIndex(x=>Number(x.id)===Number(PLAYER?.id));
 const base=current>=0?current:0;
 const next=(base+dir+ACTIVE_PLAYERS.length)%ACTIVE_PLAYERS.length;
 selectPlayer(Number(ACTIVE_PLAYERS[next].id));
}
function homePlayerCycleHtml(){
 if(ACTIVE_PLAYERS.length<=1)return '';
 return `<div class="homePlayerCycle"><button class="btn homeCycleBtn" data-ebl-action="home-cycle-player" data-dir="-1" aria-label="Previous player">‹</button><div class="homePlayerDots">${ACTIVE_PLAYERS.map(x=>`<button class="homePlayerDot ${Number(x.id)===Number(PLAYER?.id)?'active':''}" data-ebl-action="select-player" data-player="${Number(x.id)}" title="${escapeHtml(x.name)}"></button>`).join('')}</div><button class="btn homeCycleBtn" data-ebl-action="home-cycle-player" data-dir="1" aria-label="Next player">›</button></div>`;
}
function renderHome(){
 if(window.onboardingCard){
  if(ME?.role==='PLAYER' && !PLAYER && !onboardingDismissed()){
   onboardingCard.classList.remove('hidden');
   onboardingCard.innerHTML=`<span class="betaSiteBadge">WELCOME TO GENESIS</span><h2>Create Your First EBL Player</h2><p class="muted">You are joining at the beginning of EBL history. Season 1 opens when Genesis registration reaches ${GENESIS_PLAYER_TARGET} human players, so build your ballplayer now and be ready for Opening Day.</p><div class="onboardingSteps"><div class="onboardingStep"><b><span class="onboardingNum">1</span>Create Your Player</b><span class="muted">Choose identity, appearance, position, and spend your starting 50 XP.</span></div><div class="onboardingStep"><b><span class="onboardingNum">2</span>Enter the League</b><span class="muted">CPU clubs handle team management during Genesis so human players can join without waiting for coaches.</span></div><div class="onboardingStep"><b><span class="onboardingNum">3</span>Follow Your Career</b><span class="muted">Watch games, stats, contracts, XP, awards, fatigue, playoffs, and season rollover as your career develops.</span></div><div class="onboardingStep"><b><span class="onboardingNum">4</span>Help Build EBL</b><span class="muted">Use the Beta Feedback button anywhere in EBL for bugs, confusing screens, balance notes, or ideas.</span></div></div><button class="btn" data-ebl-action="go-page" data-page="player">Create My EBL Player</button> <button class="btn ghost" data-ebl-action="open-beta-feedback" data-category="FEEDBACK">Send Beta Feedback</button> <button class="btn ghost" data-ebl-action="dismiss-onboarding">Skip Guide</button><div class="muted eblSpaceTopM"><b>Optional community:</b> Discord and Instagram are extra ways to follow the beta. They are never required to play and provide no gameplay advantage. <a href="https://discord.gg/7EdEfcKPR" target="_blank" rel="noopener noreferrer">Discord</a> • <a href="https://www.instagram.com/elite_baseball_league/" target="_blank" rel="noopener noreferrer">Instagram</a></div>`;
  }else onboardingCard.classList.add('hidden');
 }
 if(!PLAYER){homePlayer.innerHTML='<h2>Create Your Player</h2><p class="muted">Your Genesis career starts with 50 XP and a blank history.</p>';homeTeam.innerHTML='<h2>No Team Yet</h2><p class="muted">Create a player, enter the CPU market, and sign your first EBL contract.</p>';nextGame.innerHTML='<h2>Next Game</h2><p class="muted">Your schedule appears after signing.</p>';return}
 let p=PLAYER,t=p.team;const renewalAction=(p.offers||[]).find(o=>String(o.offer_type||'').toUpperCase()==='RENEWAL'),veteranAction=p.veteran_extension?.required;homePlayer.innerHTML=`<div class="identity"><div class="homeAvatarWrap homeAvatarBranded">${p.franchise_id?`<div class="homePlayerTeamBackdrop">${teamLogoImg(p.franchise_id,'secondary','homePlayerBackdropLogo')}</div>`:''}${typeof eblPlayerArt==='function'?eblPlayerArt(p,'lg','portrait'):eblAvatarHtml(p,'card')}</div><div><span class="muted">MY PLAYERS • ${ACTIVE_PLAYERS.length}/${PLAYER_LIMIT} SLOTS</span><h2>${ME?.username?`<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(ME.username)}">${escapeHtml(p.name)}</button>`:escapeHtml(p.name)}</h2><div>#${Number(p.jersey_number??24)} • ${p.primary_pos}${p.hometown?` • ${escapeHtml(p.hometown)}`:''} • OVR ${p.overall||'—'} • ${(+p.xp_wallet)>0?`${(+p.xp_wallet).toFixed(3)} XP available`:'No XP available'}</div><button class="btn ghost eblSpaceTopXs" data-ebl-action="go-page" data-page="player">Open Player HQ</button></div></div>${veteranAction?`<div class="taskCard eblSpaceTopM"><b>🏅 Veteran career decision</b><div class="red">Spend ${Number(p.veteran_extension?.cost||0).toFixed(0)} XP to secure career Season ${Number(p.veteran_extension?.next_career_season||0)} before offseason rollover.</div><button class="btn eblSpaceTopTiny" data-ebl-action="open-player-career">Review Career Decision</button></div>`:''}${renewalAction?`<div class="taskCard eblSpaceTopM"><b>📄 Renewal decision waiting</b><div class="muted">${Number(renewalAction.salary||0).toFixed(2)} XP/game • ${Number(renewalAction.years||0)} season(s)</div><button class="btn eblSpaceTopTiny" data-ebl-action="open-player-contracts">Review Contract</button></div>`:''}${homePlayerCycleHtml()}`;
 homeTeam.innerHTML=t?`<div class="identity">${teamMark(p.franchise_id)}<div><span class="muted">MY TEAM</span><h2><button class="clickableName" data-ebl-action="open-team" data-team="${p.franchise_id}">${t.name}</button></h2><div class="big">${t.wins}-${t.losses}</div><div class="gold">${t.division} Division</div></div></div>`:`<span class="muted">MY TEAM</span><h2>Free Agent</h2><p>Request CPU contract offers to begin your EBL career.</p><button class="btn" data-ebl-action="open-market">REQUEST CONTRACT OFFERS</button><button class="btn ghost" data-ebl-action="open-player-contracts">OPEN CONTRACT HQ</button>`;
 let ng=p.franchise_id?SCHEDULE.find(g=>g.status==='SCHEDULED'&&(g.away_id===p.franchise_id||g.home_id===p.franchise_id)&&g.league_day>=(LEAGUE?.day||0)):null;
 nextGame.innerHTML=ng?`<span class="muted">NEXT GAME • DAY ${ng.league_day}</span><div class="homeNextMatchup"><span>${teamMark(ng.away_id,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(ng.away_id)}">${teamName(ng.away_id)}</button></span><b>@</b><span>${teamMark(ng.home_id,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(ng.home_id)}">${teamName(ng.home_id)}</button></span></div><p>${ng.away_id===p.franchise_id?'Road game':'Home game'}</p><button class="btn ghost" data-ebl-action="go-page" data-page="schedule">VIEW SCHEDULE</button>`:`<h2>Next Game</h2><p class="muted">${p.franchise_id?'Your next scheduled game will appear here.':'Accept a contract and your first EBL game will appear here automatically.'}</p>${!p.franchise_id?`<div class="launchPath"><span>1. Request offers</span><span>2. Choose a team</span><span>3. Play ball</span></div>`:''}`;
 if(window.recentPerf){
   const rg=p.recent_game,st=rg?.stats||{};
   if(!rg){recentPerf.innerHTML='<span class="muted">No completed appearance yet. Your latest game line will appear here.</span>';}
   else if(p.type==='P'){
     const outs=Number(st.OUTS||0),ip=`${Math.floor(outs/3)}.${outs%3}`;
     recentPerf.innerHTML=`<b>Day ${rg.league_day}</b><div class="big" style="font-size:22px;margin-top:6px">${ip} IP • ${st.SO||0} K • ${st.BB||0} BB • ${st.ER||0} ER</div><div class="muted eblSpaceTopMicro">${st.H||0} H allowed${st.SV?` • ${st.SV} SV`:''}</div>`;
   }else{
     const hits=Number(st.H||0),ab=Number(st.AB||0);
     recentPerf.innerHTML=`<b>Day ${rg.league_day}</b><div class="big" style="font-size:22px;margin-top:6px">${hits}-for-${ab} • ${st.HR||0} HR • ${st.RBI||0} RBI</div><div class="muted eblSpaceTopMicro">${st.BB||0} BB • ${st.SO||0} K • ${st.SB||0} SB</div>`;
   }
 }
}
async function loadChat(ch){try{let j=await api('/api/chat/'+ch+(ch==='TEAM'&&PLAYER?.id?'?player_id='+encodeURIComponent(PLAYER.id):''));let box=ch==='EBL'?eblChat:teamChat;box.innerHTML=j.messages.map(m=>{const fid=m.player?.franchise_id||m.franchise_id||m.team_id||'';const avatar=m.player&&typeof eblPublicPortrait==='function'?eblPublicPortrait({...m.player,franchise_id:fid},'xs'):(fid?teamMark(fid,true):'');return `<div class="chatmsg"><div class="chatIdentity"><span class="chatPlayerAvatar">${avatar}</span><b><button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(m.username)}">@${escapeHtml(m.username)}</button></b> <span class="muted">${m.created_at}</span></div>${escapeHtml(m.message)}</div>`}).join('');box.scrollTop=box.scrollHeight}catch{}}
function escapeHtml(x){return String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function esc(x){return escapeHtml(x)}
async function sendChat(ch){let input=ch==='EBL'?eblMsg:teamMsg,msg=input.value.trim();if(!msg)return;try{await api('/api/chat/send',{method:'POST',body:JSON.stringify({channel:ch,message:msg,player_id:PLAYER?.id})});input.value='';loadChat(ch)}catch(e){eblAlert(e.error)}}




let NEWS=[];




let DM_CONTACTS=[],DM_ACTIVE=null,DM_UNREAD=0,DM_POLL_TIMER=null;
function renderDMUnread(count){
 DM_UNREAD=Math.max(0,Number(count)||0);
 const badge=document.getElementById('pmCount'),btn=document.getElementById('pmShortcut');
 if(badge){badge.textContent=DM_UNREAD>99?'99+':String(DM_UNREAD);badge.classList.toggle('hidden',DM_UNREAD===0);}
 if(btn){btn.classList.toggle('hasUnread',DM_UNREAD>0);btn.setAttribute('aria-label',DM_UNREAD?`${DM_UNREAD} unread private message${DM_UNREAD===1?'':'s'}`:'Private messages');}
 const nav=[...document.querySelectorAll('.navbtn[data-page="messages"]')][0];
 if(nav)nav.textContent=DM_UNREAD?`MESSAGES (${DM_UNREAD>99?'99+':DM_UNREAD})`:'MESSAGES';
}
async function loadDMUnread(){
 if(!ME){renderDMUnread(0);return;}
 try{const j=await api('/api/dm/unread');renderDMUnread(j.unread||0)}catch(e){}
}
function startDMPoll(){
 if(DM_POLL_TIMER)clearInterval(DM_POLL_TIMER);
 DM_POLL_TIMER=setInterval(()=>{if(ME)loadDMUnread()},15000);
}
async function openMessagesPage(){goPage('messages');await loadDMContacts();await loadDMUnread();}
async function loadDMContacts(){
 try{
  let j=await api('/api/dm/contacts');DM_CONTACTS=j.contacts||[];renderDMUnread(j.unread||0);
  dmContacts.innerHTML=DM_CONTACTS.length?DM_CONTACTS.map(c=>`<div class="dmContact ${DM_ACTIVE===c.id?'active':''}" data-ebl-action="open-dm" data-user="${c.id}"><div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start"><div><div class="dmIdentity">${c.franchise_id?teamMark(c.franchise_id,true):''}<b><button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(c.username)}" data-ebl-stop="1">@${escapeHtml(c.username)}</button>${Number(c.unread||0)>0?` <span class="dmUnread">${Number(c.unread)>99?'99+':Number(c.unread)}</span>`:''}</b></div><div class="muted">${c.player_name?`<button class="clickableName muted" data-ebl-action="open-user-profile" data-username="${jsq(c.username)}" data-ebl-stop="1">${escapeHtml(c.player_name)}</button>`:escapeHtml(c.role)}${c.team_name?' • '+escapeHtml(c.team_name):''}</div></div><button class="btn" style="padding:5px 8px" data-ebl-action="open-user-profile" data-username="${jsq(c.username)}" data-ebl-stop="1">Profile</button></div></div>`).join(''):'<p class="muted">No other users yet.</p>';
 }catch(e){}
}
async function openDM(id){
 DM_ACTIVE=id;let c=DM_CONTACTS.find(x=>x.id===id);dmTitle.innerHTML=c?`Conversation with <button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(c.username)}">@${escapeHtml(c.username)}</button> <button class="btn" style="margin-left:8px;padding:5px 8px" data-ebl-action="open-user-profile" data-username="${jsq(c.username)}">View Profile</button>`:'Conversation';
 let j=await api('/api/dm/thread/'+id);
 dmThread.innerHTML=j.messages.map(m=>{const uname=m.sender_user_id===ME.id?(ME?.username||m.sender_name):(DM_CONTACTS.find(x=>Number(x.id)===Number(m.sender_user_id))?.username||m.sender_name);return `<div class="dmBubble ${m.sender_user_id===ME.id?'mine':''}"><div class="dmMeta"><button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(uname)}">@${escapeHtml(uname)}</button> • ${m.created_at}</div>${escapeHtml(m.message)}</div>`}).join('');
 dmThread.scrollTop=dmThread.scrollHeight;
 await loadDMContacts();
}
async function sendDM(){
 if(!DM_ACTIVE)return eblAlert('Choose a contact first.');
 let msg=dmMsg.value.trim();if(!msg)return;
 try{await api('/api/dm/send',{method:'POST',body:JSON.stringify({recipient_user_id:DM_ACTIVE,message:msg})});dmMsg.value='';await openDM(DM_ACTIVE);await loadDMUnread()}catch(e){eblAlert(e.error)}
}
async function loadCommunity(){
 try{
  const [rv,rc]=await Promise.all([api('/api/rivalries'),api('/api/records')]);
  rivalryBoard.innerHTML=rv.rivalries.length?rv.rivalries.map(r=>`<div class="rivalry"><div class="rivalryTeams"><span>${teamMark(r.team_a||r.team_a_id,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(r.team_a||r.team_a_id)}">${escapeHtml(String(r.team_a_name))}</button></span><b>VS</b><span>${teamMark(r.team_b||r.team_b_id,true)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(r.team_b||r.team_b_id)}">${escapeHtml(String(r.team_b_name))}</button></span></div><div class="muted">${r.games} meetings • ${r.a_wins}-${r.b_wins} • ${r.one_run_games} one-run games</div><div class="heat"><span style="width:${Math.min(100,r.intensity)}%"></span></div><small>Intensity ${Math.round(r.intensity)}/100</small></div>`).join(''):'<p class="muted">No rivalries yet. They have to be earned.</p>';
  recordBook.innerHTML=rc.records.length?rc.records.map(r=>`<div class="recordCard"><span class="newsMeta">${escapeHtml(String(r.record_label||'EBL RECORD'))}</span><br><div class="recordHolderBrand">${r.franchise_id?teamMark(r.franchise_id,true):''}<b>${r.holder_type==='PLAYER'?leaguePlayerIdentity({player_id:r.holder_id,name:r.holder_name,username:r.username,face_id:r.face_id,hair_id:r.hair_id,hair_color_id:r.hair_color_id,facial_hair_id:r.facial_hair_id,eye_color_id:r.eye_color_id,eye_black_id:r.eye_black_id,eyewear_id:r.eyewear_id,chain_id:r.chain_id,sleeve_id:r.sleeve_id,jersey_number:r.jersey_number,primary_pos:r.primary_pos,franchise_id:r.franchise_id}):escapeHtml(String(r.holder_name||r.holder_id||''))}</b></div> — ${escapeHtml(String(r.record_value??''))}<div class="muted">${escapeHtml(String(r.detail||''))} • Day ${Number(r.league_day||0)}</div></div>`).join(''):'<p class="muted">Genesis begins with a blank record book.</p>';
  if(window.friendsPanel){
   if(!ME){friendsPanel.innerHTML='<p class="muted">Sign in to add friends and send private messages. Rivalries and the EBL record book remain public.</p>';return;}
   try{
    const fr=await api('/api/friends');
    const incoming=(fr.incoming||[]).map(x=>`<div class="friendCard"><div><div class="friendIdentity"><b><button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(x.username)}">@${escapeHtml(x.username)}</button></b></div><div class="muted">EBL member profile${x.role?` • ${escapeHtml(x.role)}`:''}</div></div><div><button class="btn" data-ebl-action="friend-accept" data-user="${x.user_id}" data-username="${escapeHtml(x.username)}">Accept</button> <button class="btn" data-ebl-action="open-user-profile" data-username="${jsq(x.username)}">Profile</button></div></div>`).join('');
    const friends=(fr.friends||[]).map(x=>`<div class="friendCard"><div><b><button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(x.username)}">@${escapeHtml(x.username)}</button></b><div class="muted">EBL member profile${x.role?` • ${escapeHtml(x.role)}`:''}</div></div><div><button class="btn" data-ebl-action="message-profile" data-user="${x.user_id}">Message</button> <button class="btn" data-ebl-action="open-user-profile" data-username="${jsq(x.username)}">Profile</button></div></div>`).join('');
    const outgoing=(fr.outgoing||[]).map(x=>`<div class="friendCard"><div><b><button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(x.username)}">@${escapeHtml(x.username)}</button></b><div class="muted">Friend request pending</div></div><button class="btn" data-ebl-action="friend-remove" data-user="${x.user_id}" data-username="${escapeHtml(x.username)}">Cancel</button></div>`).join('');
    friendsPanel.innerHTML=(incoming?`<h3>Requests</h3>${incoming}`:'')+(friends?`<h3 class="eblSpaceTopM">Friends</h3>${friends}`:'')+(outgoing?`<h3 class="eblSpaceTopM">Sent</h3>${outgoing}`:'')||'<p class="muted">No friends yet. Open a user profile and send a friend request.</p>';
   }catch(e){friendsPanel.innerHTML='<p class="muted">Could not load friends.</p>'}
  }
 }catch(e){
  if(window.rivalryBoard)rivalryBoard.innerHTML='<p class="muted">Rivalry board is temporarily unavailable.</p>';
  if(window.recordBook)recordBook.innerHTML='<p class="muted">Record book is temporarily unavailable.</p>';
 }
}

async function loadReadiness(){
 try{
  let r=await api('/api/league/readiness'),pct=r.total?Math.round(r.filled/r.total*100):0;
  READINESS=r;window.EBL_READINESS=r;
  renderBetaStatus();
  const bar=document.getElementById('readinessBar'),text=document.getElementById('readinessText'),positions=document.getElementById('positionReadiness');
  if(bar?.querySelector('span'))bar.querySelector('span').style.width=pct+'%';
  if(text)text.innerHTML=`<b>${r.filled}/${r.total}</b> roster slots filled • ${r.human} human • ${r.cpu} CPU • Phase: <b>${r.phase}</b>`;
  if(positions)positions.innerHTML=(r.positions||[]).map(p=>`<div class="statBox"><b>${p.position_group}</b><span>${p.filled}/${p.total}</span><small>${p.human} human</small></div>`).join('');
 }catch(e){}
}
async function loadNews(){
 try{
  let j=await api('/api/news');NEWS=j.news||[];renderNews('ALL');renderHomeNews();
 }catch(e){
  if(newsFeed)newsFeed.innerHTML='<p class="muted">The newsroom is waiting for the first EBL games to create history.</p>';
 }
}
function renderNews(filter){
 if(!window.newsFeed)return;
 let rows=filter==='ALL'?NEWS:NEWS.filter(n=>n.category===filter);
 newsFeed.innerHTML=rows.length?rows.map(n=>{const fid=n.franchise_id||n.team_id||n.team||'';return `<article class="newsStory">${fid?`<div class="newsTeamMark">${teamMark(fid,true)}</div>`:''}<div class="newsMeta"><span class="newsBadge">${n.category.replaceAll('_',' ')}</span>SEASON ${n.season||LEAGUE?.season||1} • DAY ${n.league_day}</div><div class="newsHeadline">${n.headline}</div><div class="newsBody">${n.body}</div></article>`}).join(''):'<p class="muted">No stories in this section yet. Genesis history is still being written.</p>';
}
function newsFilter(f,b){document.querySelectorAll('#news .subtab').forEach(x=>x.classList.remove('active'));b.classList.add('active');renderNews(f)}
function renderHomeNews(){
 if(!window.homeNews)return;
 let rows=NEWS.slice(0,5);
 homeNews.innerHTML=rows.length?rows.map(n=>{const fid=n.franchise_id||n.team_id||n.team||'';return `<div class="headlineCompact brandedHeadline">${fid?teamMark(fid,true):''}<div><span class="newsMeta">${n.category.replaceAll('_',' ')} • SEASON ${n.season||LEAGUE?.season||1} • DAY ${n.league_day}</span><br><b>${n.headline}</b></div></div>`}).join(''):'<p class="muted">No headlines yet. The first pitch of Genesis will start the story.</p>';
}
let SUPPORT_CONFIG=null;
async function startSupporterCheckout(plan='monthly'){
 if(!ME){loginCard.classList.remove('hidden');dashboard.classList.add('hidden');loginMsg.textContent='Sign in to attach a Supporter subscription to your EBL account.';return}
 const root=document.getElementById('supportActions');
 const label=plan==='yearly'?'yearly':'monthly';
 try{
  if(root)root.innerHTML=`<span class="muted">Opening secure Stripe ${label} checkout…</span>`;
  const j=await api('/api/support/checkout',{method:'POST',body:JSON.stringify({plan:label})});
  if(j?.already_supporter){await loadSupport();return}
  if(!j?.url)throw {error:'CHECKOUT_URL_MISSING'};
  location.href=j.url;
 }catch(e){
  if(root)root.innerHTML=`<div class="offer"><b>Checkout could not start.</b><div class="muted">${escapeHtml(e?.error||'Please try again.')}</div></div>`;
 }
}
async function pollSupporterReturn(){
 if(!ME)return false;
 const root=document.getElementById('supportActions');
 for(let i=0;i<10;i++){
  try{
   const e=await api('/api/account/entitlements');
   ENTITLEMENTS=e.entitlements||ENTITLEMENTS;
   if(ENTITLEMENTS?.standard_supporter&&ENTITLEMENTS?.subscription_plan){
    ME.supporter=true;ME.genesis_supporter_only=false;
    const plan=String(ENTITLEMENTS.subscription_plan||'').toUpperCase();
    if(root)root.insertAdjacentHTML('afterbegin',`<div class="supportCurrent"><b>✓ VERIFIED SUBSCRIPTION — SUPPORTER ACTIVE</b><span>Stripe confirmed ${plan?plan+' ':''}billing and EBL upgraded this account automatically.</span></div>`);
    return true;
   }
  }catch(_){}
  await new Promise(r=>setTimeout(r,750));
 }
 if(root)root.insertAdjacentHTML('afterbegin','<div class="offer"><b>Checkout returned — verification is still processing.</b><div class="muted">Refresh this page in a moment. EBL does not grant Supporter until the signed Stripe webhook confirms the subscription.</div></div>');
 return false;
}
async function loadSupport(){
 const root=document.getElementById('supportActions');if(!root)return;
 try{
  const j=await api('/api/support');SUPPORT_CONFIG=j||{};
  if(ME){
   try{const e=await api('/api/account/entitlements');ENTITLEMENTS=e.entitlements||ENTITLEMENTS;if(ENTITLEMENTS){ME.supporter=Boolean(ENTITLEMENTS.supporter);ME.genesis_supporter=Boolean(ENTITLEMENTS.genesis_supporter);ME.genesis_supporter_only=Boolean(ENTITLEMENTS.genesis_supporter_only);}}catch(_){}
  }
  const buttons=[];
  const monthly=j?.plans?.monthly,yearly=j?.plans?.yearly;
  if(j?.checkout_path){
   if(ME?.supporter&&!ENTITLEMENTS?.genesis_supporter_only){
    buttons.push('<button class="btn supportBtn primary" disabled>✓ EBL Supporter Active</button>');
    if(j?.portal_url)buttons.push(`<a class="btn supportBtn" href="${escapeHtml(j.portal_url)}" target="_blank" rel="noopener noreferrer">⚙ Manage Billing / Cancel</a>`);
   }else{
    if(monthly)buttons.push(`<button class="btn supportBtn primary" data-ebl-action="supporter-checkout" data-plan="monthly">❤ ${j.mode==='test'?'Test ':''}Monthly — $${Number(monthly.price_usd||5).toFixed(2).replace(/\.00$/,'')}/mo</button>`);
    if(yearly)buttons.push(`<button class="btn supportBtn" data-ebl-action="supporter-checkout" data-plan="yearly">★ ${j.mode==='test'?'Test ':''}Yearly — $${Number(yearly.price_usd||54).toFixed(2).replace(/\.00$/,'')}/yr <span class="gold">SAVE ${Number(j.yearly_savings_pct||10)}%</span></button>`);
   }
  }
  const modeNote=j?.mode==='test'
   ? '<span class="muted" style="align-self:center"><b>TEST MODE:</b> Stripe test cards only — no real charge.</span>'
   : `<span class="muted" style="align-self:center">Secure recurring billing hosted by ${escapeHtml(j.provider||'Stripe')}. Cancel before the next renewal to stop future charges.</span>`;
  root.innerHTML=buttons.length?`${buttons.join('')}${modeNote}`:'<div class="offer"><b>Supporter checkout is being set up.</b><div class="muted eblSpaceTopMicro">The Free and Supporter account rules are already built; payment activation will come before public recruiting.</div></div>';
  if(ME){
   try{
    const box=document.getElementById('supportEntitlementCard');
    box?.querySelector('.supportCurrent')?.remove();
    if(box&&ENTITLEMENTS){
      const plan=String(ENTITLEMENTS.subscription_plan||'').toUpperCase();
      const end=ENTITLEMENTS.subscription_period_end||ENTITLEMENTS.supporter_expires_at||'';
      const endText=end?new Date(end).toLocaleDateString():'';
      const billing=ENTITLEMENTS.standard_supporter&&plan?` • ${plan}${endText?(ENTITLEMENTS.cancel_at_period_end?' active through ':' renews around ')+endText:''}`:'';
      const promo=ENTITLEMENTS.genesis_supporter_only?` • Genesis early-account bonus #${Number(ENTITLEMENTS.genesis_supporter_rank||0)} • free through Season ${Number(ENTITLEMENTS.genesis_supporter_through_season||1)}`:'';
      box.insertAdjacentHTML('afterbegin',`<div class="supportCurrent"><b>${ENTITLEMENTS.genesis_supporter_only?'GENESIS SUPPORTER — FREE EARLY-ACCOUNT BENEFITS':(ENTITLEMENTS.supporter?'YOU ARE AN EBL SUPPORTER':'YOUR ACCOUNT: FREE')}${ENTITLEMENTS.founding_supporter?' <span class="foundingSupporterBadge">FOUNDING SUPPORTER</span>':''}</b><span>${Number(ENTITLEMENTS.active_players||0)}/${Number(ENTITLEMENTS.entitled_player_limit||1)} entitled active player slots used${promo}${billing}${ENTITLEMENTS.policy_enforced?'':' • Genesis slot enforcement paused'}</span>${ENTITLEMENTS.genesis_supporter_only?'<span class="muted">You can still choose a paid Supporter plan during Genesis; a verified real-money Genesis subscription earns the permanent Founding Supporter marker.</span>':''}</div>`);
    }
   }catch(_){}
  }
 }catch(e){root.innerHTML='<span class="muted">Support options are temporarily unavailable.</span>'}
}
function goPage(id){let b=document.querySelector(`.navbtn[data-page="${id}"]`);if(b)b.click()}


function uniformOptions(selected){return ['WHITE','NAVY','RED','GRAY','BLACK','CREAM'].map(x=>`<option ${x===selected?'selected':''}>${x}</option>`).join('')}
function teamAbbr(name){
 const parts=String(name||'EBL').trim().split(/\s+/);
 return parts.length>1?(parts[0][0]+parts[parts.length-1].slice(0,2)).toUpperCase():parts[0].slice(0,3).toUpperCase();
}
function teamGeneratedGlyph(style){
 const shapes=['⚾','★','◆','⬟','✦','▲','●','◈','✧','⬢'];
 return shapes[(Number(style||1)-1)%shapes.length];
}
function teamLogoMarkup(style,p,s,a,name){
 const mark=teamGeneratedGlyph(style),abbr=teamAbbr(name);
 const square=Number(style||1)%3===0;
 return `<div style="width:220px;height:220px;border-radius:${square?'28%':'50%'};background:radial-gradient(circle at 35% 28%,${a}2b,transparent 34%),linear-gradient(145deg,${p},${p}dd);border:11px solid ${s};box-shadow:inset 0 0 0 5px ${a},0 12px 30px #0007;display:flex;flex-direction:column;align-items:center;justify-content:center;color:${a};font-weight:950;text-align:center;position:relative;overflow:hidden"><div style="position:absolute;inset:16px;border:2px solid ${a}66;border-radius:inherit"></div><div style="font-size:72px;line-height:.9;text-shadow:0 3px 0 #0005;z-index:1">${mark}</div><div style="font-size:28px;letter-spacing:.12em;margin-top:8px;z-index:1">${abbr}</div><div style="font-size:12px;letter-spacing:.05em;padding:7px 18px 0;opacity:.92;z-index:1">${escapeHtml(name)}</div></div>`;
}

function teamLogoUrl(fid,kind='primary'){
 const t=typeof fid==='object'?(fid||{}):(LEAGUE?.teams?.find(x=>String(x.id)===String(fid))||{});
 const primary=t.primary_logo_url||t.primary_logo||t.logo_url||t.logo||t.logo_primary||t.primaryLogoUrl||t.primaryLogo||'';
 const secondary=t.secondary_logo_url||t.secondary_logo||t.logo_secondary||t.secondaryLogoUrl||t.secondaryLogo||'';
 return kind==='secondary'?(secondary||primary):(primary||secondary);
}
function teamLogoImg(fid,kind='primary',className=''){
 const t=typeof fid==='object'?(fid||{}):(LEAGUE?.teams?.find(x=>String(x.id)===String(fid))||{});
 const src=teamLogoUrl(t,kind);
 if(!src)return '';
 const name=t.display_name||t.name||[t.city,t.team_name].filter(Boolean).join(' ')||'EBL franchise';
 return `<img class="${escapeHtml(className)}" src="${escapeHtml(String(src))}" alt="${escapeHtml(name)} logo" loading="lazy" onerror="this.style.display='none'">`;
}
function teamMark(fid,small=false){
 const t=LEAGUE?.teams?.find(x=>String(x.id)===String(fid))||{};
 const n=t.display_name||t.name||fid||'EBL';
 const p=t.primary_color||'#071A31',sec=t.secondary_color||'#D7262E',a=t.accent_color||'#D9E0E8';
 const logo=(typeof EBLTeamLogo==='function'?EBLTeamLogo(t,small?'secondary':'primary'):'')||teamLogoUrl(t,small?'secondary':'primary');
 if(logo){
   return `<span class="teamMark ${small?'sm':''} uploadedTeamMark" style="--tm1:${p};--tm2:${sec};--tm3:${a}" title="${escapeHtml(n)}" role="img" aria-label="${escapeHtml(n)} logo"><img src="${escapeHtml(String(logo))}" alt="" loading="lazy" decoding="async" onerror="this.style.display='none';this.nextElementSibling.style.display='grid'"><span class="teamMarkFallback" aria-hidden="true">${teamAbbr(n)}</span></span>`;
 }
 const glyph=teamGeneratedGlyph(t.logo_style||1),abbr=teamAbbr(n).slice(0,3);
 return `<span class="teamMark ${small?'sm':''} officialGeneratedTeamMark" style="--tm1:${p};--tm2:${sec};--tm3:${a};position:relative;overflow:hidden" title="${escapeHtml(n)}" role="img" aria-label="${escapeHtml(n)} team mark"><span aria-hidden="true" style="font-size:${small?'12':'16'}px;line-height:1;transform:translateY(-1px)">${glyph}</span><span aria-hidden="true" style="position:absolute;left:1px;right:1px;bottom:${small?'0':'1'}px;font-size:${small?'5':'7'}px;line-height:1;font-weight:950;letter-spacing:.02em;text-shadow:0 1px 2px #000">${escapeHtml(abbr)}</span></span>`;
}


function teamIdentityLink(fid,small=true){
 if(fid===undefined||fid===null||fid==='')return '';
 const name=teamName(fid);
 return `<button class="teamIdentityLink" data-ebl-action="open-team" data-team="${jsq(fid)}" aria-label="Open ${escapeHtml(name)} team page">${teamMark(fid,small)}<span>${escapeHtml(name)}</span></button>`;
}

// EBL_AVATAR_SILHOUETTE_PERSONALITY_PASS
function eblAppearancePlayer(p={}){
 const a=p.appearance||p.avatar||{};
 return {
  ...p,
  jersey_number:p.jersey_number??a.jersey_number??24,
  face_id:p.face_id??a.face_id??1,
  skin_color_id:p.skin_color_id??a.skin_color_id??1,
  hair_id:p.hair_id??a.hair_id??1,
  hair_color_id:p.hair_color_id??a.hair_color_id??3,
  facial_hair_id:p.facial_hair_id??a.facial_hair_id??1,
  eye_color_id:p.eye_color_id??a.eye_color_id??6,
  nose_id:p.nose_id??a.nose_id??1,
  eye_shape_id:p.eye_shape_id??a.eye_shape_id??1,
  mouth_id:p.mouth_id??a.mouth_id??1,
  ear_size_id:p.ear_size_id??a.ear_size_id??2,
  eye_black_id:p.eye_black_id??a.eye_black_id??1,
  eyewear_id:p.eyewear_id??a.eyewear_id??a.goggles_id??1,
  chain_id:p.chain_id??a.chain_id??1,
  sleeve_id:p.sleeve_id??a.sleeve_id??1,
  body_build_id:p.body_build_id??a.body_build_id??1,
  bats:p.bats??a.bats??'R',
  throws:p.throws??a.throws??'R',
  primary_pos:p.primary_pos??p.position??a.primary_pos??'UTIL',
  franchise_id:p.franchise_id??p.team_id??a.franchise_id??null
 };
}

function stationaryPlayerSvg(p,compact=false,pose='auto'){
 p=eblAppearancePlayer(p||{});
 const face=Math.max(1,Math.min(20,Number(p.face_id)||1));
 const hairId=Math.max(1,Math.min(28,Number(p.hair_id)||1));
 const facial=Math.max(1,Math.min(14,Number(p.facial_hair_id)||1));
 const eyeId=Math.max(1,Math.min(6,Number(p.eye_color_id)||6));
 const hairColorId=Math.max(1,Math.min(9,Number(p.hair_color_id)||3));
 const skinId=Math.max(1,Math.min(8,Number(p.skin_color_id)||1));
 const jersey=String(p.jersey_number??24).padStart(2,'0').slice(-2);
 const pos=escapeHtml(String(p.primary_pos||'UTIL'));
 const initials=escapeHtml(String(teamInitials(p.franchise_id)||'E').slice(0,3));
 const team=teamPalette(p.franchise_id);
 const t1=team[0]||'#123a5a',t2=team[1]||'#d92832',t3=team[2]||'#f5f7fa';
 const skins=['','#f2c59d','#e7b58d','#dca47b','#c98c68','#bd7c57','#8d573e','#754733','#633c2e'];
 const eyes=['','#4b2d1f','#765133','#2f6690','#3d7b5a','#77736b','#4b2d1f'];
 const hairs=['','#2b1a14','#4a2c20','#6b4028','#8a5b38','#b17b4e','#d9bd78','#d6c27b','#9a6a42','#171717'];
 const skin=skins[skinId],eye=eyes[eyeId],hair=hairs[hairColorId];

 // AVATAR current FOUNDATION: actual geometry, not overlays.
 const faces=[
 null,
 'M106 126 Q106 88 150 83 Q194 88 194 126 L190 158 Q184 188 150 205 Q116 188 110 158Z',
 'M104 124 Q105 89 150 85 Q195 89 196 124 L191 169 Q181 198 150 208 Q119 198 109 169Z',
 'M111 119 Q116 82 150 78 Q184 82 189 119 L186 165 Q178 195 150 211 Q122 195 114 165Z',
 'M103 126 Q104 91 150 85 Q196 91 197 126 L191 164 L174 195 L150 208 L126 195 L109 164Z',
 'M112 119 Q114 83 150 79 Q186 83 188 119 L185 164 L169 196 L150 210 L131 196 L115 164Z',
 'M115 118 Q119 82 150 79 Q181 82 185 118 L183 168 Q175 200 150 214 Q125 200 117 168Z',
 'M101 127 Q103 92 150 86 Q197 92 199 127 L193 166 Q183 195 150 204 Q117 195 107 166Z',
 'M105 121 Q108 86 150 82 Q192 86 195 121 Q199 157 185 181 Q171 204 150 205 Q129 204 115 181 Q101 157 105 121Z',
 'M108 120 Q111 84 150 80 Q189 84 192 120 L188 160 L176 188 L150 210 L124 188 L112 160Z',
 'M104 124 Q106 88 150 83 Q194 88 196 124 L191 160 L178 190 L150 206 L122 190 L109 160Z'
 ];
 const faceFamily=((face-1)%5)+1;
 const facePaths={
  1:'M106 124 Q107 88 150 83 Q193 88 194 124 L190 160 Q184 188 150 204 Q116 188 110 160Z',
  2:'M101 125 Q102 90 150 84 Q198 90 199 125 L194 166 Q184 197 150 207 Q116 197 106 166Z',
  3:'M112 119 Q116 82 150 78 Q184 82 188 119 L185 163 Q176 194 150 212 Q124 194 115 163Z',
  4:'M103 123 Q105 88 150 82 Q195 88 197 123 L191 160 L176 190 L150 207 L124 190 L109 160Z',
  5:'M108 119 Q112 83 150 79 Q188 83 192 119 L188 158 L173 190 L150 213 L127 190 L112 158Z'
 };
 const facePath=facePaths[faceFamily];

 const hairGroup=((hairId-1)%9)+1;
 const hairBack = hairGroup===6 ? '' :
   hairGroup===1 ? `<path d="M105 128 Q104 90 123 76 Q150 60 178 77 Q197 92 195 129 L185 145 L181 116 Q168 101 150 101 Q130 101 119 118 L114 145Z" fill="${hair}"/>` :
   hairGroup===2 ? `<path d="M107 127 Q108 92 127 78 Q150 66 176 79 Q193 92 193 126 L185 139 L180 115 Q165 103 150 103 Q131 103 120 117 L115 140Z" fill="${hair}"/>` :
   hairGroup===3 ? `<path d="M101 130 Q98 88 119 70 Q140 54 158 67 Q183 55 199 92 L197 142 Q187 129 181 113 Q164 96 148 101 Q126 96 116 119 L112 151 Q101 143 101 130Z" fill="${hair}"/>` :
   hairGroup===4 ? `<path d="M99 130 Q96 82 122 67 Q150 48 179 68 Q204 85 201 132 L194 171 Q181 160 180 126 Q167 99 149 101 Q126 99 116 126 L112 171 Q99 160 99 130Z" fill="${hair}"/>` :
   hairGroup===5 ? `<path d="M104 129 Q102 88 124 72 Q148 58 178 74 Q197 90 196 129 L188 151 Q180 129 179 113 Q162 101 150 102 Q130 100 119 119 L113 151Z" fill="${hair}"/>` :
   hairGroup===7 ? `<path d="M97 129 Q94 78 120 62 Q147 44 177 62 Q205 78 203 132 L196 183 Q183 173 179 128 Q166 98 149 100 Q125 98 115 128 L110 183 Q97 171 97 129Z" fill="${hair}"/>` :
   hairGroup===8 ? `<path d="M104 126 Q103 87 130 69 Q161 52 191 82 L194 124 Q175 105 151 102 Q126 103 113 125 L111 146Z" fill="${hair}"/>` :
   `<path d="M108 126 Q107 95 125 80 Q150 66 176 80 Q193 94 192 126 L184 140 L180 117 Q164 105 150 105 Q132 105 120 119 L115 140Z" fill="${hair}"/>`;

 const hairFront = hairGroup===6 ? '' :
   hairGroup===1 ? `<path d="M108 111 Q120 84 149 81 Q178 82 192 108 Q170 99 150 102 Q129 99 108 111Z" fill="${hair}"/>` :
   hairGroup===2 ? `<path d="M112 108 Q124 88 151 86 Q177 87 188 107 Q168 101 150 103 Q130 101 112 108Z" fill="${hair}"/>` :
   hairGroup===3 ? `<path d="M105 111 Q109 76 132 72 Q145 61 157 72 Q179 66 195 105 Q174 96 151 100 Q127 95 105 111Z" fill="${hair}"/>` :
   hairGroup===4 ? `<path d="M102 112 Q104 74 128 67 Q147 52 163 67 Q187 62 198 104 Q175 95 151 99 Q126 94 102 112Z" fill="${hair}"/>` :
   hairGroup===5 ? `<path d="M106 110 Q126 78 151 81 Q178 79 193 106 Q170 95 151 101 Q131 96 106 110Z" fill="${hair}"/>` :
   hairGroup===7 ? `<path d="M101 111 Q101 69 128 62 Q149 46 165 63 Q190 58 200 103 Q176 94 151 98 Q125 93 101 111Z" fill="${hair}"/>` :
   hairGroup===8 ? `<path d="M105 108 Q130 71 163 72 Q184 74 196 101 Q171 91 151 99 Q129 94 105 108Z" fill="${hair}"/>` :
   `<path d="M111 108 Q123 89 150 87 Q176 88 189 108 Q169 101 150 103 Q130 101 111 108Z" fill="${hair}"/>`;

 const beard = facial===1 ? '' :
   facial===2 ? `<path d="M121 169 Q127 193 150 200 Q173 193 179 169" fill="none" stroke="${hair}" stroke-width="4" stroke-dasharray="2 4" opacity=".45"/>` :
   facial===3 ? `<path d="M137 181 Q150 188 163 181 L159 201 Q150 207 141 201Z" fill="${hair}"/><path d="M137 174 Q150 168 163 174" fill="none" stroke="${hair}" stroke-width="5" stroke-linecap="round"/>` :
   facial===4 ? `<path d="M112 159 Q116 199 150 217 Q184 199 188 159 Q180 196 164 207 Q150 217 136 207 Q120 196 112 159Z" fill="${hair}"/><path d="M131 173 Q150 165 169 173" fill="none" stroke="${skin}" stroke-width="7"/>` :
   facial===5 ? `<path d="M128 173 Q139 165 150 171 Q161 165 172 173 Q161 180 150 177 Q139 180 128 173Z" fill="${hair}"/>` :
   facial===6 ? `<path d="M117 165 Q122 199 150 209 Q178 199 183 165" fill="none" stroke="${hair}" stroke-width="7" stroke-dasharray="2 3" opacity=".62"/>` :
   facial===7 ? `<path d="M115 165 Q120 198 150 211 Q180 198 185 165 Q177 193 163 202 Q150 210 137 202 Q123 193 115 165Z" fill="${hair}"/><path d="M132 174 Q150 167 168 174" fill="none" stroke="${skin}" stroke-width="8"/>` :
   facial===8 ? `<path d="M111 160 Q115 204 150 220 Q185 204 189 160 Q181 199 164 211 Q150 222 136 211 Q119 199 111 160Z" fill="${hair}"/><path d="M130 173 Q150 165 170 173" fill="none" stroke="${skin}" stroke-width="7"/>` :
   facial===9 ? `<path d="M108 157 Q111 209 150 229 Q189 209 192 157 Q184 204 165 218 Q150 231 135 218 Q116 204 108 157Z" fill="${hair}"/><path d="M128 173 Q150 164 172 173" fill="none" stroke="${skin}" stroke-width="7"/>` :
   facial===10 ? `<path d="M130 171 Q150 164 170 171" fill="none" stroke="${hair}" stroke-width="6" stroke-linecap="round"/><path d="M136 180 Q150 190 164 180 L160 201 Q150 208 140 201Z" fill="${hair}"/>` :
   facial===11 ? `<path d="M144 187 Q150 192 156 187 L155 201 Q150 205 145 201Z" fill="${hair}"/>` :
   facial===12 ? `<path d="M126 172 Q139 163 150 171 Q161 163 174 172 Q162 180 150 177 Q138 180 126 172Z" fill="${hair}"/>` :
   facial===13 ? `<path d="M124 171 Q137 160 150 171 Q163 160 176 171 Q169 180 160 179 Q170 187 178 183 M140 179 Q130 187 122 183" fill="none" stroke="${hair}" stroke-width="6" stroke-linecap="round"/>` :
   `<path d="M113 161 Q118 201 150 216 Q182 201 187 161 Q179 195 164 205 Q150 215 136 205 Q121 195 113 161Z" fill="${hair}"/><path d="M128 171 Q150 163 172 171" fill="none" stroke="${hair}" stroke-width="7" stroke-linecap="round"/><path d="M133 177 Q150 171 167 177" fill="none" stroke="${skin}" stroke-width="6"/>`;

 // Deliberate athletic proportions. Build selector can be wired later; current starts balanced.
 const shoulder=compact?54:67, torsoTop=220;
 return `<svg viewBox="0 0 300 330" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHtml(String(p.name||'EBL player'))}">
 <defs><filter id="v2shadow"><feDropShadow dx="0" dy="5" stdDeviation="4" flood-opacity=".22"/></filter></defs>
 <g filter="url(#v2shadow)" stroke="#111820" stroke-linejoin="round" stroke-linecap="round">
   <circle cx="150" cy="160" r="116" fill="${t1}" opacity=".18" stroke="none"/>
   ${hairBack}
   <path d="${facePath}" fill="${skin}" stroke-width="5"/>
   <ellipse cx="106" cy="145" rx="8" ry="15" fill="${skin}" stroke-width="4"/>
   <ellipse cx="194" cy="145" rx="8" ry="15" fill="${skin}" stroke-width="4"/>
   ${hairFront}
   <path d="M103 117 Q105 79 150 73 Q195 79 197 117 Q177 106 150 106 Q123 106 103 117Z" fill="${t1}" stroke-width="5"/>
   <path d="M150 74 L150 106" stroke="${t3}" stroke-width="2" opacity=".30"/>
   <path d="M150 106 Q180 105 202 116 Q178 122 151 116Z" fill="${t1}" stroke-width="4"/>
   <path d="M153 113 Q179 112 198 116" fill="none" stroke="${t2}" stroke-width="3"/>
   <circle cx="150" cy="74" r="4" fill="${t2}" stroke="none"/>
   <text x="150" y="99" text-anchor="middle" fill="${t3}" font-size="15" font-weight="900" font-family="Arial Black,Arial" stroke="none">${initials}</text>

   <path d="M121 133 Q132 126 143 132" fill="none" stroke="${hair}" stroke-width="4"/>
   <path d="M157 132 Q168 126 179 133" fill="none" stroke="${hair}" stroke-width="4"/>
   <path d="M120 145 Q131 137 143 145 Q132 153 120 145Z" fill="#fff" stroke-width="3"/>
   <path d="M157 145 Q169 137 180 145 Q168 153 157 145Z" fill="#fff" stroke-width="3"/>
   <ellipse cx="132" cy="145" rx="4.4" ry="5" fill="${eye}" stroke="none"/><circle cx="132" cy="145" r="2.1" fill="#111820" stroke="none"/>
   <ellipse cx="168" cy="145" rx="4.4" ry="5" fill="${eye}" stroke="none"/><circle cx="168" cy="145" r="2.1" fill="#111820" stroke="none"/>
   <circle cx="133" cy="143.5" r="1" fill="#fff" stroke="none"/><circle cx="169" cy="143.5" r="1" fill="#fff" stroke="none"/>
   <path d="M150 145 Q145 158 147 164 Q151 168 157 164" fill="none" stroke="#875448" stroke-width="2.2"/>
   <path d="M134 179 Q150 185 166 179" fill="none" stroke="#7b4242" stroke-width="3.2"/>
   ${beard}

   <path d="M132 199 L132 222 Q150 235 168 222 L168 199" fill="${skin}" stroke-width="5"/>
   <path d="M${150-shoulder} 330 Q${150-shoulder+2} 258 118 ${torsoTop} Q135 214 150 229 Q165 214 182 ${torsoTop} Q${150+shoulder-2} 258 ${150+shoulder} 330Z" fill="${t1}" stroke-width="6"/>
   <path d="M118 220 Q150 244 182 220" fill="none" stroke="${t2}" stroke-width="7"/>
   <path d="M124 221 Q150 239 176 221" fill="none" stroke="${t3}" stroke-width="2.5"/>
   <path d="M150 237 L150 327" stroke="${t2}" stroke-width="3" opacity=".65"/>
   <path d="M106 245 L93 322 M194 245 L207 322" fill="none" stroke="${t3}" stroke-width="2" opacity=".18"/>
   <text x="150" y="282" text-anchor="middle" fill="${t3}" font-size="40" font-weight="900" font-family="Arial Black,Arial" stroke="#111820" stroke-width="2" paint-order="stroke">${jersey}</text>
   <text x="150" y="307" text-anchor="middle" fill="${t3}" font-size="13" font-weight="900" font-family="Arial" letter-spacing="2" stroke="none">${initials}</text>
   <text x="82" y="301" fill="${t3}" font-size="12" font-weight="900" font-family="Arial" stroke="none">${pos}</text>
 </g></svg>`;
}

function eblActionPlayerSvg(p,action='batting'){
 p=eblAppearancePlayer(p||{});
 const a=String(action||'batting').toLowerCase();
 const team=teamPalette(p.franchise_id), t1=team[0]||'#123a5a',t2=team[1]||'#d92832',t3=team[2]||'#f5f7fa';
 const jersey=String(p.jersey_number??24).padStart(2,'0').slice(-2);
 const name=escapeHtml(String(p.name||'EBL Player'));
 const label={batting:'AT BAT',pitching:'ON THE MOUND',fielding:'IN THE FIELD',running:'ON THE BASEPATHS'}[a]||'GAME ACTION';
 const face=Math.max(1,Math.min(20,Number(p.face_id)||1));
 const hairId=Math.max(1,Math.min(28,Number(p.hair_id)||1));
 const hairColorId=Math.max(1,Math.min(9,Number(p.hair_color_id)||3));
 const skin=['','#f2c59d','#dca47b','#bd7c57','#8d573e','#633c2e','#e7b58d','#c98c68','#a96c4d','#754733','#efc7a6','#efbd98','#cd916d','#aa6d50','#7b4d39','#e7b38d','#bc7d5c','#925c43','#e9b994','#704536','#d59a74'][face];
 const hair=['','#2b1a14','#4a2c20','#6b4028','#8a5b38','#b17b4e','#d9bd78','#d6c27b','#9a6a42','#171717'][hairColorId];
 const initials=escapeHtml(String(teamInitials(p.franchise_id)||'E').slice(0,3));
 const head=`<g>
   <circle cx="0" cy="0" r="31" fill="${skin}" stroke="#111820" stroke-width="5"/>
   <path d="M-29 -8 Q-22-36 0-37 Q25-35 30-7 Q11-18-5-16 Q-18-17-29-8Z" fill="${hair}" stroke="#111820" stroke-width="4"/>
   <path d="M-31-17 Q-27-49 2-51 Q31-48 34-18 Q14-28-1-27 Q-17-28-31-17Z" fill="${t1}" stroke="#111820" stroke-width="5"/>
   <path d="M0-51 Q1-38 0-27" stroke="${t3}" stroke-width="2" opacity=".35"/>
   <path d="M0-27 Q31-29 48-14 Q22-10 0-17Z" fill="${t2}" stroke="#111820" stroke-width="4"/>
   <circle cx="-11" cy="0" r="6" fill="#fff" stroke="#111820" stroke-width="2"/><circle cx="12" cy="0" r="6" fill="#fff" stroke="#111820" stroke-width="2"/>
   <circle cx="-10" cy="1" r="2.5" fill="#111820"/><circle cx="13" cy="1" r="2.5" fill="#111820"/>
   <path d="M-12 17 Q1 26 15 16" fill="#fff" stroke="#111820" stroke-width="3"/>
   <text x="1" y="-31" text-anchor="middle" fill="${t3}" font-size="11" font-weight="900" font-family="Arial Black,Arial" stroke="none">${initials}</text>
 </g>`;
 const torso=`<g>
   <path d="M-38 0 Q0-17 38 0 L47 70 Q0 85-47 70Z" fill="${t3}" stroke="#111820" stroke-width="6"/>
   <path d="M-34 2 Q0 18 34 2" fill="none" stroke="${t2}" stroke-width="6"/>
   <path d="M0 11 L0 69" stroke="${t1}" stroke-width="2" opacity=".55"/>
   <text x="0" y="54" text-anchor="middle" fill="${t1}" font-size="26" font-weight="900" font-family="Arial Black,Arial" stroke="none">${jersey}</text>
 </g>`;
 let player='';
 if(a==='pitching'){
   player=`<g transform="translate(174 139) rotate(-8)">${head}<g transform="translate(0 38)">${torso}</g>
   <path d="M-34 52 Q-78 66-91 103" fill="none" stroke="${skin}" stroke-width="18"/><circle cx="-92" cy="105" r="10" fill="#fff" stroke="#111820" stroke-width="4"/>
   <path d="M34 52 Q73 28 91-7" fill="none" stroke="${skin}" stroke-width="18"/><circle cx="94" cy="-11" r="8" fill="#fff" stroke="#111820" stroke-width="3"/>
   <path d="M-26 108 Q-48 155-16 202" fill="none" stroke="${t3}" stroke-width="28"/><path d="M24 108 Q60 146 91 178" fill="none" stroke="${t3}" stroke-width="28"/>
   <path d="M-18 199 l-27 12" stroke="#111820" stroke-width="17"/><path d="M91 178 l28 8" stroke="#111820" stroke-width="17"/><path d="M-43 214 l-8 5 M114 188 l9 5" stroke="${t3}" stroke-width="3"/></g>`;
 }else if(a==='fielding'){
   player=`<g transform="translate(171 145) rotate(7)">${head}<g transform="translate(0 38)">${torso}</g>
   <path d="M-35 55 Q-76 75-103 101" fill="none" stroke="${skin}" stroke-width="18"/>
   <g transform="translate(-111 106) rotate(-18)"><path d="M0 0 Q28-20 43 5 Q40 34 13 40 Q-8 26 0 0Z" fill="#9a6038" stroke="#111820" stroke-width="5"/><path d="M7 5 Q22 0 35 9 M5 14 Q22 9 37 18 M8 23 Q22 19 34 27" fill="none" stroke="#e3b17a" stroke-width="2.5"/></g>
   <path d="M35 56 Q67 72 82 93" fill="none" stroke="${skin}" stroke-width="18"/>
   <path d="M-24 108 Q-62 145-82 184" fill="none" stroke="${t3}" stroke-width="28"/><path d="M24 108 Q60 143 80 184" fill="none" stroke="${t3}" stroke-width="28"/>
   <path d="M-82 184 l-27 11" stroke="#111820" stroke-width="17"/><path d="M80 184 l27 11" stroke="#111820" stroke-width="17"/><path d="M-105 198 l-9 5 M103 198 l9 5" stroke="${t3}" stroke-width="3"/></g>`;
 }else if(a==='running'){
   player=`<g transform="translate(171 143) rotate(13)">${head}<g transform="translate(0 38)">${torso}</g>
   <path d="M-34 55 Q-71 28-86 0" fill="none" stroke="${skin}" stroke-width="18"/><path d="M34 55 Q69 77 88 103" fill="none" stroke="${skin}" stroke-width="18"/>
   <path d="M-24 108 Q-57 145-92 163" fill="none" stroke="${t3}" stroke-width="28"/><path d="M24 108 Q61 126 94 168" fill="none" stroke="${t3}" stroke-width="28"/>
   <path d="M-92 163 l-30-4" stroke="#111820" stroke-width="17"/><path d="M94 168 l29 16" stroke="#111820" stroke-width="17"/><path d="M-118 162 l-10 1 M118 185 l10 6" stroke="${t3}" stroke-width="3"/></g>
   <path d="M259 304 l25 12 -25 12 -25-12z" fill="#fff" stroke="#111820" stroke-width="4"/>`;
 }else{
   const flip=String(p.bats||'R').toUpperCase()==='L'?-1:1;
   player=`<g transform="translate(176 145)">${head}<g transform="translate(0 38)">${torso}</g>
   <path d="M-35 55 Q-70 35-81 10" fill="none" stroke="${skin}" stroke-width="18"/><path d="M35 55 Q70 38 80 15" fill="none" stroke="${skin}" stroke-width="18"/>
   <g transform="scale(${flip} 1)"><path d="M74 20 L121-96" stroke="#d7a85b" stroke-width="10" stroke-linecap="round"/><circle cx="75" cy="19" r="9" fill="${skin}" stroke="#111820" stroke-width="3"/></g>
   <path d="M-24 108 Q-47 151-64 194" fill="none" stroke="${t3}" stroke-width="28"/><path d="M24 108 Q54 147 73 194" fill="none" stroke="${t3}" stroke-width="28"/>
   <path d="M-64 194 l-29 7" stroke="#111820" stroke-width="17"/><path d="M73 194 l29 7" stroke="#111820" stroke-width="17"/><path d="M-89 204 l-9 4 M98 204 l9 4" stroke="${t3}" stroke-width="3"/></g>`;
 }
 return `<svg viewBox="0 0 360 360" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${name} ${label.toLowerCase()}">
 <rect x="7" y="7" width="346" height="346" rx="29" fill="#071725" stroke="${t2}" stroke-width="4"/>
 <circle cx="180" cy="176" r="145" fill="${t1}" opacity=".22"/>
 <path d="M22 307 Q180 277 338 307" fill="none" stroke="${t3}" stroke-width="3" opacity=".25"/>
 ${player}
 <!-- Sports Cartoon current: hands + baseball mechanics -->
 ${a==='batting'?`<g stroke="#111820" stroke-linecap="round" stroke-linejoin="round">
   <!-- two-hand bat grip -->
   <circle cx="245" cy="166" r="8" fill="${skin}" stroke-width="3.5"/>
   <circle cx="238" cy="174" r="8" fill="${skin}" stroke-width="3.5"/>
   <path d="M240 171 L286 74" stroke="#d5a45a" stroke-width="9"/>
   <path d="M284 77 L291 61" stroke="#111820" stroke-width="4"/>
   <path d="M241 171 Q222 181 205 185" fill="none" stroke="${skin}" stroke-width="13"/>
   <path d="M236 178 Q216 190 199 191" fill="none" stroke="${skin}" stroke-width="13"/>
 </g>`:''}
 ${a==='pitching'?`<g stroke="#111820" stroke-linejoin="round">
   <!-- throwing hand, ball seams, glove-side hand -->
   <circle cx="267" cy="118" r="9" fill="${skin}" stroke-width="3.5"/>
   <circle cx="276" cy="106" r="8" fill="#fff" stroke-width="3"/>
   <path d="M270 102 Q276 106 282 102 M270 110 Q276 106 282 110" fill="none" stroke="#c53a3a" stroke-width="1.8"/>
   <g transform="translate(86 224) rotate(18)">
    <path d="M0 0 Q24-18 39 4 Q38 30 12 37 Q-8 24 0 0Z" fill="#955d36" stroke-width="4"/>
    <path d="M6 7 Q20 1 32 10 M6 16 Q20 10 33 19" fill="none" stroke="#e2b17b" stroke-width="2"/>
   </g>
 </g>`:''}
 ${a==='fielding'?`<g stroke="#111820" stroke-linejoin="round">
   <!-- glove is connected to forearm; bare hand ready above pocket -->
   <path d="M82 245 Q67 252 59 265" fill="none" stroke="${skin}" stroke-width="13"/>
   <g transform="translate(48 267) rotate(-24)">
    <path d="M0 0 Q29-21 45 5 Q42 35 13 42 Q-9 27 0 0Z" fill="#955d36" stroke-width="4"/>
    <path d="M7 5 Q22 0 36 10 M5 15 Q22 9 38 20 M8 25 Q22 19 35 29" fill="none" stroke="#e2b17b" stroke-width="2.2"/>
   </g>
   <circle cx="246" cy="235" r="8" fill="${skin}" stroke-width="3"/>
 </g>`:''}
 ${a==='running'?`<g fill="none" stroke="${skin}" stroke-width="13" stroke-linecap="round">
   <!-- opposing arm drive -->
   <path d="M117 190 Q91 171 82 145"/>
   <path d="M232 190 Q257 209 266 235"/>
 </g><g fill="${skin}" stroke="#111820" stroke-width="3">
   <circle cx="81" cy="143" r="8"/><circle cx="267" cy="237" r="8"/>
 </g>`:''}
  <!-- Sports Cartoon current: anatomy + uniform construction -->
 ${a==='batting'?`<g stroke="#111820" stroke-linejoin="round">
   <circle cx="105" cy="181" r="10" fill="${skin}" stroke-width="4"/><circle cx="247" cy="185" r="10" fill="${skin}" stroke-width="4"/>
   <path d="M119 250 Q112 273 105 294" fill="none" stroke="${t2}" stroke-width="5" opacity=".55"/>
   <path d="M229 250 Q238 273 244 294" fill="none" stroke="${t2}" stroke-width="5" opacity=".55"/>
   <path d="M82 304 Q66 306 55 316 Q73 322 94 315Z" fill="#f3f5f7" stroke-width="4"/>
   <path d="M257 304 Q274 307 286 317 Q268 323 247 315Z" fill="#f3f5f7" stroke-width="4"/>
 </g>`:''}
 ${a==='pitching'?`<g stroke="#111820" stroke-linejoin="round">
   <circle cx="90" cy="225" r="9" fill="${skin}" stroke-width="4"/><circle cx="259" cy="127" r="9" fill="${skin}" stroke-width="4"/>
   <path d="M138 252 Q126 271 123 293 M224 246 Q239 262 254 280" fill="none" stroke="${t2}" stroke-width="5" opacity=".55"/>
   <path d="M117 301 Q98 305 89 315 Q108 321 129 313Z" fill="#f3f5f7" stroke-width="4"/>
   <path d="M264 286 Q282 288 293 299 Q275 305 255 297Z" fill="#f3f5f7" stroke-width="4"/>
 </g>`:''}
 ${a==='fielding'?`<g stroke="#111820" stroke-linejoin="round">
   <circle cx="95" cy="251" r="9" fill="${skin}" stroke-width="4"/><circle cx="249" cy="241" r="9" fill="${skin}" stroke-width="4"/>
   <path d="M134 251 Q117 270 105 293 M218 250 Q237 270 247 293" fill="none" stroke="${t2}" stroke-width="5" opacity=".55"/>
   <path d="M101 302 Q82 305 72 315 Q92 321 112 313Z" fill="#f3f5f7" stroke-width="4"/>
   <path d="M251 302 Q270 305 280 315 Q260 321 240 313Z" fill="#f3f5f7" stroke-width="4"/>
 </g>`:''}
 ${a==='running'?`<g stroke="#111820" stroke-linejoin="round">
   <circle cx="93" cy="153" r="9" fill="${skin}" stroke-width="4"/><circle cx="257" cy="244" r="9" fill="${skin}" stroke-width="4"/>
   <path d="M128 247 Q109 264 90 281 M222 244 Q243 261 260 286" fill="none" stroke="${t2}" stroke-width="5" opacity=".55"/>
   <path d="M82 288 Q63 289 51 298 Q69 306 91 300Z" fill="#f3f5f7" stroke-width="4"/>
   <path d="M268 292 Q286 296 296 307 Q277 312 258 303Z" fill="#f3f5f7" stroke-width="4"/>
 </g>`:''}
 <g fill="none" stroke="${t1}" stroke-width="2.5" opacity=".30">
   <path d="M147 209 Q174 218 201 208"/>
   <path d="M145 220 Q174 228 203 218"/>
 </g>
  <!-- Sports Cartoon current: grounded action details -->
 <g fill="none" stroke="${t3}" stroke-linecap="round" opacity=".18">
   <path d="M40 286 Q91 272 131 282" stroke-width="3"/>
   <path d="M228 282 Q274 271 320 287" stroke-width="3"/>
 </g>
 ${a==='batting'?`<g fill="none" stroke="${t2}" opacity=".28" stroke-linecap="round"><path d="M269 79 Q297 94 311 122" stroke-width="4"/><path d="M278 67 Q314 84 329 116" stroke-width="2"/></g>`:''}
 ${a==='pitching'?`<g fill="none" stroke="${t2}" opacity=".28" stroke-linecap="round"><path d="M262 93 Q291 79 316 91" stroke-width="4"/><path d="M269 105 Q302 94 326 109" stroke-width="2"/></g>`:''}
 ${a==='running'?`<g fill="none" stroke="${t2}" opacity=".26" stroke-linecap="round"><path d="M68 188 L35 196" stroke-width="5"/><path d="M75 204 L45 216" stroke-width="3"/></g>`:''}
 ${a==='fielding'?`<g transform="translate(55 74)" fill="none" stroke="${t3}" opacity=".16"><path d="M0 0 Q20 13 39 2 M5 14 Q23 26 42 15" stroke-width="3"/></g>`:''}
  <g font-family="Arial Black,Arial" font-weight="900"><text x="22" y="31" fill="${t2}" font-size="12" letter-spacing="2">${label}</text>
 <text x="22" y="341" fill="${t3}" font-size="17">${name}</text><text x="337" y="341" text-anchor="end" fill="${t2}" font-size="17">#${jersey}</text></g></svg>`;
}

function eblActionArtHtml(p,action='batting',cls=''){
 return `<div class="eblActionArt ${escapeHtml(cls)}">${eblActionPlayerSvg(p,action)}</div>`;
}
function playerPortraitMarkup(p,pose='auto'){
 const q=typeof eblGetIdentity==='function'?eblGetIdentity(p||{}):(typeof eblIdentityCompat==='function'?eblIdentityCompat(p||{}):(p||{}));
 const action=(pose&&pose!=='auto'&&pose!=='portrait')?pose:'portrait';
 if(typeof eblPlayerArt==='function'){
   return `<div class="playerPortrait canonicalPlayerPortrait" data-pos="#${Number(q?.jersey_number??24)} • ${escapeHtml(q?.primary_pos||'EBL')}">${eblPlayerArt(q,'lg',action)}</div>`;
 }
 return `<div class="playerPortrait" data-pos="#${Number(q?.jersey_number??24)} • ${escapeHtml(q?.primary_pos||'EBL')}">${stationaryPlayerSvg(q)}</div>`;
}
function updateBrandPreview(){
 if(!window.brandPreview)return;
 brandPreview.innerHTML=teamLogoMarkup(+brandLogo.value,brandPrimary.value,brandSecondary.value,brandAccent.value,brandName.value||'EBL TEAM');
}
async function saveBranding(){
 try{
  await api('/api/coach/branding',{method:'POST',body:JSON.stringify({display_name:brandName.value,logo_style:+brandLogo.value,primary_color:brandPrimary.value,secondary_color:brandSecondary.value,accent_color:brandAccent.value,uniform_home:brandHome.value,uniform_away:brandAway.value})});
  eblToast('Team identity saved.','success');await loadLeague();await loadCoachHub();
 }catch(e){eblAlert(e.error)}
}
async function loadCoachPortal(){
  if(!ME)return;
  if(ME.role==='COMMISSIONER')return loadCoachHub();
  coachHub.innerHTML='<p class="muted">Loading coaching status...</p>';
  try{
    const j=await api('/api/coach/application');
    const a=j.application||null;
    if(j.assigned_team)return loadCoachHub();
    if(a?.status==='PENDING'){
      coachHub.innerHTML=`<div class="card" style="border-left:4px solid var(--silver)"><h2>Application Under Review</h2><p>Your EBL coaching application has been sent to the Commissioner.</p><p class="muted">Submitted ${escapeHtml(a.created_at||'recently')}. You can keep playing normally while it is reviewed.</p></div>`;return;
    }
    if(j.approved||a?.status==='APPROVED'){
      coachHub.innerHTML=`<div class="card" style="border-left:4px solid var(--red)"><h2>Approved EBL Coach</h2><p>Your coaching application has been approved.</p><p class="muted">You are waiting for a franchise assignment. Once the Commissioner assigns a club, the full Franchise Operations HUD unlocks here.</p></div>`;return;
    }
    if(j.applications_open===false){
      coachHub.innerHTML='<div class="card" style="border-left:4px solid var(--gold)"><span class="newsMeta">COACHING CAREER</span><h2>Coach Applications Closed</h2><p class="muted">The Commissioner is not accepting new coaching applications right now. Your player career is unaffected.</p></div>';return;
    }
    renderCoachApplication(a,j.available_teams||[]);
  }catch(e){
    coachHub.innerHTML=`<div class="card"><h2>Coach Applications Temporarily Unavailable</h2><p class="muted">${escapeHtml(e?.error||e?.message||'Could not load coaching status.')}</p></div>`;
  }
}
function renderCoachApplication(previous,availableTeams=null){
  const teams=Array.isArray(availableTeams)?availableTeams:(LEAGUE?.teams||[]);
  const opts=teams.map(t=>`<option value="${escapeHtml(t.id)}">${escapeHtml(t.name)}</option>`).join('');
  coachHub.innerHTML=`<div class="coachDash"><div class="card" style="border-top:3px solid var(--red)"><span class="newsMeta">COACHING CAREER</span><h2>Apply to Be an EBL Coach</h2><p class="muted">Build a franchise, manage players and contracts, set your lineup and pitching staff, and write your own EBL coaching legacy.</p></div><div class="card"><div class="grid"><label>Preferred Franchise<select id="coachApplyTeam"><option value="">Any available franchise</option>${opts}</select></label><label>Baseball / Sim Experience <span class="muted">(optional)</span><input id="coachApplyExperience" maxlength="300" placeholder="Tell us a little about your experience"></label></div><label>Why do you want to coach in the EBL?<textarea id="coachApplyWhy" maxlength="800" rows="4" placeholder="What makes coaching fun for you, and what would you bring to a franchise?"></textarea></label><label>Management Philosophy<textarea id="coachApplyPhilosophy" maxlength="800" rows="4" placeholder="How would you build and manage your club?"></textarea></label><label style="display:flex;gap:8px;align-items:flex-start;margin:12px 0"><input id="coachApplyRules" type="checkbox" style="width:auto;margin-top:3px"><span>I understand that coaches manage one franchise, must follow EBL league rules, and cannot sign their own created player.</span></label><button class="btn" data-ebl-action="submit-coach-application">Submit Coaching Application</button><div id="coachApplyMsg" class="muted eblSpaceTopXs"></div></div></div>`;
}
async function submitCoachApplication(){
  const out=document.getElementById('coachApplyMsg');
  const why=document.getElementById('coachApplyWhy')?.value.trim()||'';
  const philosophy=document.getElementById('coachApplyPhilosophy')?.value.trim()||'';
  if(!why||!philosophy){out.textContent='Please complete both coaching questions.';return}
  if(!document.getElementById('coachApplyRules')?.checked){out.textContent='Please acknowledge the coaching rules.';return}
  try{
    await api('/api/coach/apply',{method:'POST',body:JSON.stringify({preferred_franchise_id:document.getElementById('coachApplyTeam')?.value||null,experience:document.getElementById('coachApplyExperience')?.value.trim()||'',reason:why,philosophy,rules_ack:true})});
    await loadCoachPortal();
  }catch(e){out.textContent=e?.error||e?.message||'Application could not be submitted.'}
}
async function loadCoachHub(){
 try{
  let j=await api('/api/coach/team');
  if(!j.team){coachHub.innerHTML='<p class="muted">No franchise assigned.</p>';return}
  let H=j.roster.filter(x=>x.type==='H'),P=j.roster.filter(x=>x.type==='P');
  window.__EBL_COACH_HITTERS=H;
  window.__EBL_COACH_PITCHERS=P;
  window.__EBL_COACH_STRATEGY=j.strategy||{};
  if(typeof eblPrimeIdentityCache==='function')eblPrimeIdentityCache(j.roster||[]);
  let lineup=j.lineup||[],rot=j.rotation||[],bp=j.strategy?.bullpen||{},def=j.strategy?.defense||{};
  const next=j.next_game,opp=next?(next.away_id===j.team.id?next.home_id:next.away_id):null;
  const humanCount=j.roster.filter(x=>x.user_id).length;
  const lineupReady=(lineup||[]).length===9,rotationReady=(rot||[]).length>=3&&(rot||[]).length<=5;
  const rebuildBonusActive=Boolean(j.team?.development_bonus_active) && Number(j.season||1)>1;
  const rebuildBonusPct=Number(j.team?.development_bonus_effective||0)*100;
  const rebuildBonusText=rebuildBonusActive?`+${rebuildBonusPct.toFixed(2)}%`:'Starts Season 2';
  const expiring=(j.contracts||[]).filter(c=>c.user_id&&Number(c.years_remaining)===1);
  const renewalUnsent=expiring.filter(c=>j.renewal_window_open&&!c.renewal);
  const renewalPending=expiring.filter(c=>['OPEN','HELD'].includes(String(c.renewal?.status||'')));
  const renewalAccepted=expiring.filter(c=>String(c.renewal?.status||'')==='ACCEPTED');
  const devCoaches=j.development_coaches||[],devRules=j.development_coach_rules||{first_free:true,maximum:3,hiring_close_day:49};
  const stadium=j.stadium||{stadium_name:(j.team?.name||'EBL')+' Ballpark',park_profile:'NEUTRAL',profile_name:'Neutral Park',hitter:{},pitcher:{},edit_open:false,profiles:[]};
  const devHiringOpen=String(j.phase||'REGULAR').toUpperCase()==='REGULAR'&&Number(j.league_day||0)<Number(devRules.hiring_close_day||49);
  const coachActions=[];
  if(devHiringOpen&&devCoaches.length===0)coachActions.push(`<div class="taskCard eblClickable" data-ebl-action="open-coach-upgrades"><b>🎯 Choose your free development coach</b><div class="red">Every club gets one specialist free each season. Pick the direction you want this roster to grow.</div></div>`);
  if(!lineupReady)coachActions.push(`<div class="taskCard eblClickable" data-ebl-action="open-coach-roster"><b>📋 Set your lineup</b><div class="red">9 starters required before game day.</div></div>`);
  if(!rotationReady)coachActions.push(`<div class="taskCard eblClickable" data-ebl-action="open-coach-pitching"><b>🔥 Set your rotation</b><div class="red">Choose 3–5 starters.</div></div>`);
  if(j.renewal_window_open&&renewalUnsent.length)coachActions.push(`<div class="taskCard eblClickable" data-ebl-action="open-coach-contracts"><b>📄 ${renewalUnsent.length} renewal decision${renewalUnsent.length===1?'':'s'} needed</b><div class="red">Expiring contracts can be negotiated now through the end of the regular season.</div></div>`);
  if(renewalPending.length)coachActions.push(`<div class="taskCard eblClickable" data-ebl-action="open-coach-contracts"><b>⏳ ${renewalPending.length} renewal offer${renewalPending.length===1?'':'s'} waiting</b><div class="muted">Players have not decided yet.</div></div>`);
  coachHub.innerHTML=`<div class="coachDash">
   <div class="card"><div class="identity">${teamMark(j.team.id)}<div><span class="muted">COACH DESK • DAY ${j.league_day}</span><h2>${j.team.name}</h2><div>${j.phase} • ${j.team.wins}-${j.team.losses} • ${humanCount}/16 human players</div></div></div><div class="baseballDivider"></div>
    <div class="grid">
      <div class="taskCard"><b>⚾ Next Game</b><div>${next?`<span class="compactTeamRef">Day ${next.league_day} • ${next.away_id===j.team.id?'@':'vs'} ${teamMark(opp,true)} ${teamName(opp)}</span>`:'No game scheduled'}</div></div>
      <div class="taskCard eblClickable" ${lineupReady?'':'data-ebl-action="open-coach-roster"'}><b>📋 Lineup</b><div class="${lineupReady?'green':'red'}">${lineupReady?'Ready • 9 starters':'Needs attention • tap to fix'}</div></div>
      <div class="taskCard eblClickable" ${rotationReady?'':'data-ebl-action="open-coach-pitching"'}><b>🔥 Rotation</b><div class="${rotationReady?'green':'red'}">${rotationReady?`Ready • ${rot.length}-man rotation`:'Needs attention • tap to fix'}</div></div>
      <div class="taskCard eblClickable" data-ebl-action="open-coach-contracts"><b>📄 Contracts</b><div>${j.renewal_window_open?(renewalUnsent.length?`<span class="red">${renewalUnsent.length} renewal${renewalUnsent.length===1?'':'s'} need action</span>`:`<span class="green">${renewalAccepted.length} renewed</span>${renewalPending.length?` • ${renewalPending.length} waiting`:''}`):`${j.contracts?.length||0} signed • renewals open Day ${Number(j.renewal_open_day||60)}`}</div></div>
    </div>
    <div class="coachSection"><h3>Action Center</h3>${coachActions.length?`<div class="grid">${coachActions.join('')}</div>`:'<div class="taskCard" style="border-left-color:var(--green)"><b>✓ Nothing urgent right now</b><div class="muted">The Coach Desk will surface lineup, rotation, development, contract, and renewal work here when it needs attention.</div></div>'}</div>
   </div>
   <div class="card"><h3>Franchise XP</h3><div class="big">${Number(j.team.xp_after_signed_players||0).toFixed(1)}</div><div class="muted"><b>XP left after signed-player payroll</b> • full 81-game salary commitments are shown immediately when a human player signs</div><div class="moneyBar" style="margin:10px 0"><span style="width:${Math.min(100,Number(j.team.spend_pct||0))}%"></span></div><div><b>${Number(j.team.signed_payroll_commitment||0).toFixed(1)} XP</b> current-season signed payroll • ${Number(j.team.salary_paid_to_date||0).toFixed(1)} paid so far</div><div class="muted">Safe spendable XP: <b>${Number(j.team.xp_available||0).toFixed(1)}</b> • ${Number(j.team.open_roster_minimum_reserve||0).toFixed(1)} held for unsigned/CPU roster jobs • ${Number(j.team.reserved_offers||0).toFixed(1)} reserved for open offers</div>${j.renewal_window_open?`<div class="eblSpaceTopTiny"><b>${Number(j.team.next_season_committed_payroll||0).toFixed(1)} XP</b> projected next-season signed payroll • <b>${Number(j.team.next_season_projected_treasury||j.team.next_season_base_budget||0).toFixed(1)} XP</b> projected safe treasury (${Number(j.team.next_season_base_budget||0).toFixed(1)} recurring + ${Math.max(0,Number(j.team.next_season_projected_treasury||0)-Number(j.team.next_season_base_budget||0)).toFixed(1)} projected rollover)</div>`:''}<div class="muted">Players still receive salary XP game-by-game. This commitment view simply makes the entire season cost visible up front.</div></div>
   </div>
   <div class="grid">
   <div class="statBox"><span class="label">FRANCHISE</span><b class="coachFranchiseIdentity">${teamMark(j.team.id,true)} ${j.team.name}</b></div>
   <div class="statBox"><span class="label">RECORD</span><b>${j.team.wins}-${j.team.losses}</b></div>
   <div class="statBox"><span class="label">XP AFTER PLAYERS</span><b>${Number(j.team.xp_after_signed_players||0).toFixed(1)}</b></div>
   <div class="statBox"><span class="label">SAFE SPENDABLE</span><b>${Number(j.team.xp_available||0).toFixed(1)}</b></div>
   <div class="statBox"><span class="label">ANNUAL PAYROLL</span><b>${Number(j.team.signed_payroll_commitment||0).toFixed(1)}</b></div>
   <div class="statBox"><span class="label">OPEN OFFERS</span><b>${j.offers.length}</b></div></div>
   <div class="subtabs"><button class="subtab active" data-ebl-action="coach-pane" data-pane="cGameDay">GAME DAY</button><button class="subtab" data-ebl-action="coach-pane" data-pane="cRoster">ROSTER & LINEUP</button><button class="subtab" data-ebl-action="coach-pane" data-pane="cBrand">TEAM BRANDING</button><button class="subtab" data-ebl-action="coach-pane" data-pane="cPitch">PITCHING STAFF</button><button class="subtab" data-ebl-action="coach-pane" data-pane="cDepth">OFFENSE</button><button class="subtab" data-ebl-action="coach-pane" data-pane="cDefense">DEFENSE</button><button class="subtab" data-ebl-action="coach-pane" data-pane="cMarket">CONTRACTS</button><button class="subtab" data-ebl-action="coach-pane" data-pane="cUpgrades">FRANCHISE UPGRADES</button></div>


   <div id="cBrand" class="subpane">
    <div class="two">
      <div>
        <h2>Team Identity</h2>
        <div class="roleRow"><b>Team Name</b><input id="brandName" maxlength="40" value="${j.branding?.display_name||j.team.name}"></div>
        <div class="roleRow"><b>Logo Style</b><select id="brandLogo">${[1,2,3,4,5,6,7,8,9,10].map(x=>`<option value="${x}" ${x==(j.branding?.logo_style||1)?'selected':''}>Logo ${x}</option>`).join('')}</select></div>
        <div class="roleRow"><b>Primary</b><input id="brandPrimary" type="color" value="${j.branding?.primary_color||'#071A31'}"></div>
        <div class="roleRow"><b>Secondary</b><input id="brandSecondary" type="color" value="${j.branding?.secondary_color||'#D7262E'}"></div>
        <div class="roleRow"><b>Accent</b><input id="brandAccent" type="color" value="${j.branding?.accent_color||'#D9E0E8'}"></div>
        <div class="roleRow"><b>Home Uniform</b><select id="brandHome">${uniformOptions(j.branding?.uniform_home||'WHITE')}</select></div>
        <div class="roleRow"><b>Away Uniform</b><select id="brandAway">${uniformOptions(j.branding?.uniform_away||'NAVY')}</select></div>
        <button class="btn" data-ebl-action="save-branding">Save Team Identity</button>
      </div>
      <div><h2>Preview</h2><div id="brandPreview" class="avatarPreview" style="min-height:300px"></div></div>
    </div>
   </div>
   <div id="cGameDay" class="subpane active">
    ${coachGameDay(j,lineup,rot,bp,def,H,P,next,opp,lineupReady,rotationReady)}
   </div>
   <div id="cRoster" class="subpane">
    <div class="coachPaneHead"><div><span class="newsMeta">GAME MANAGEMENT</span><h2>Starting Nine</h2><p class="muted">Set the batting order and defensive alignment. Use the arrows to move hitters without rebuilding the lineup.</p></div><div class="coachReadyBadge ${lineupReady?'ready':'needs'}">${lineupReady?'LINEUP READY':'SET LINEUP'}</div></div>
    <div class="coachFieldLegend"><span>ORDER</span><span>PLAYER</span><span>FIELD</span><span>MOVE</span></div>
    <div id="coachLineup">${[0,1,2,3,4,5,6,7,8].map(i=>lineupRowHTML(i,lineup[i],H,j.field_positions||{})).join('')}</div>
    <div class="coachSaveBar"><span class="muted">Changes take effect after you save.</span><button class="btn" data-ebl-action="save-coach-lineup">Save Starting Nine</button></div>
   </div>
   <div id="cPitch" class="subpane">
    <div class="coachPaneHead"><div><span class="newsMeta">PITCHING STAFF</span><h2>Rotation & Bullpen</h2><p class="muted">Build the staff hierarchy the game engine will use. Readiness stays visible while you make decisions.</p></div></div>
    <h3 class="depthHeading">Starting Rotation</h3>
    <p class="muted">Choose 3–5 starters. A shorter rotation gives you more bullpen arms, but starters return sooner and may carry fatigue if workload outpaces recovery.</p>
    <div class="coachPitchGrid">${[0,1,2,3,4].map(i=>renderCoachPitchCard(i,rot[i],P)).join('')}</div>

    <div class="coachSection"><h3>Pitcher Recovery</h3><div class="coachRecoveryGrid">${P.map(p=>renderCoachRecoveryCard(p)).join('')}</div></div>

    <h3 class="coachSection depthHeading">Bullpen Roles</h3>
    <div class="coachBullpenHelp"><b>Moving a starter is now one tap.</b> Use <b>Move to Bullpen</b> on a rotation card and EBL will remove him from the rotation, compact the rotation, and place him in Middle Relief. CL, SU1, and SU2 are unique primary jobs. Middle Relief, Long Relief, and Emergency are usage pools and can overlap.</div>
    <div class="coachRoleGrid">
      ${coachSingleRole('CL','Closer','9th inning',bp.CL,P)}
      ${coachSingleRole('SU1','Setup 1','Primary setup',bp.SU1,P)}
      ${coachSingleRole('SU2','Setup 2','Secondary setup',bp.SU2,P)}
    </div>
    <div class="coachMultiRoles">
      <div class="coachMultiRole"><b>Middle Relief</b><span>Middle innings / matchup bridge</span><select id="bpMR" multiple size="5">${playerOptions(P,null,bp.MR||[])}</select></div>
      <div class="coachMultiRole"><b>Long Relief</b><span>Long outings / early exits</span><select id="bpLR" multiple size="4">${playerOptions(P,null,bp.LR||[])}</select></div>
      <div class="coachMultiRole"><b>Emergency</b><span>Last-resort pitching depth</span><select id="bpEmergency" multiple size="3">${playerOptions(P,null,bp.EMERGENCY||[])}</select></div>
    </div>
    <div id="coachPitchWarning" class="coachStaffWarning hidden"></div>
    <div class="coachSaveBar"><span class="muted">Rotation order and bullpen hierarchy save together.</span><button class="btn" data-ebl-action="save-pitching-staff">Save Pitching Staff</button></div>
   </div>


   <div id="cDepth" class="subpane">
    <div class="coachPaneHead"><div><span class="newsMeta">OFFENSIVE IDENTITY</span><h2>Offensive Strategy</h2><p class="muted">EBL carries a starting nine with no position-player bench. Set how aggressively those nine run and use the bunt; there are no pinch hitters, pinch runners, or defensive substitutes.</p></div><div class="coachDefenseBadge">STARTING 9</div></div>
    <div class="coachOffenseGrid">
      <div class="coachOffenseCard"><span class="coachPitchTag">RUN</span><div><b>Steal Aggression</b><small>How often eligible runners challenge the defense.</small></div><select id="stealAgg">${['LOW','NORMAL','HIGH'].map(x=>`<option ${x===(j.strategy?.substitutions?.steal_aggression||'NORMAL')?'selected':''}>${x}</option>`).join('')}</select></div>
      <div class="coachOffenseCard"><span class="coachPitchTag">BUNT</span><div><b>Bunt Aggression</b><small>How willing the offense is to use the bunt in appropriate situations.</small></div><select id="buntAgg">${['LOW','NORMAL','HIGH'].map(x=>`<option ${x===(j.strategy?.substitutions?.bunt_aggression||'NORMAL')?'selected':''}>${x}</option>`).join('')}</select></div>
    </div>
    <div class="coachNoBenchRule"><b>EBL Roster Rule</b><span>The nine position players in the Starting Nine remain the position-player unit for the game. Pitching changes come from the pitching staff; position-player substitutions are not part of the current EBL roster model.</span></div>
    <div class="coachSaveBar"><span class="muted">These tendencies feed the simulation's offensive decision logic.</span><button class="btn" data-ebl-action="save-offense">Save Offensive Strategy</button></div>
   </div>
   <div id="cDefense" class="subpane">
    <div class="coachPaneHead"><div><span class="newsMeta">RUN PREVENTION</span><h2>Defensive Strategy</h2><p class="muted">Set the club's default positioning and handedness adjustments. Situational calls stay separate so the engine can apply them only when appropriate.</p></div><div class="coachDefenseBadge">FIELD PLAN</div></div>
    <div class="coachDefenseLayout">
      <div class="coachDefenseBoard">
        <div class="coachDiamond">
          <div class="fieldPos fpCF">CF</div><div class="fieldPos fpLF">LF</div><div class="fieldPos fpRF">RF</div>
          <div class="fieldPos fpSS">SS</div><div class="fieldPos fp2B">2B</div>
          <div class="fieldPos fp3B">3B</div><div class="fieldPos fp1B">1B</div>
          <div class="fieldPos fpP">P</div><div class="fieldPos fpC">C</div>
        </div>
        <div class="muted coachFieldNote">Positioning preview • strategy settings control the team plan, not individual player assignments.</div>
      </div>
      <div class="coachDefenseControls">
        <div class="coachDefenseCard"><span class="coachPitchTag">ALL</span><div><b>Default Alignment</b><small>Base positioning for normal situations</small></div>${shiftSelect('defDefault',def.default_shift||'STANDARD')}</div>
        <div class="coachDefenseCard"><span class="coachPitchTag">LHB</span><div><b>vs Left-Handed Batters</b><small>Override the default against LHB</small></div>${shiftSelect('defL',def.vs_lhb||'STANDARD')}</div>
        <div class="coachDefenseCard"><span class="coachPitchTag">RHB</span><div><b>vs Right-Handed Batters</b><small>Override the default against RHB</small></div>${shiftSelect('defR',def.vs_rhb||'STANDARD')}</div>
        <div class="coachSituationCard"><div><b>Corners In</b><small>Bring 1B/3B closer when the situation calls for it.</small></div><label class="coachSwitch"><input type="checkbox" id="cornersIn" ${def.corners_in?'checked':''}><span></span></label></div>
        <div class="coachSituationCard"><div><b>Infield In</b><small>Trade range for a better chance to cut down a runner at home.</small></div><label class="coachSwitch"><input type="checkbox" id="infieldIn" ${def.infield_in?'checked':''}><span></span></label></div>
      </div>
    </div>
    <div class="coachDefenseSummary" id="coachDefenseSummaryPanel"></div>
    <div class="coachSaveBar"><span class="muted">The saved field plan becomes the club's defensive strategy.</span><button class="btn" data-ebl-action="save-defense">Save Defensive Plan</button></div>
   </div>
   <div id="cMarket" class="subpane">
    <div class="card" style="border-left:4px solid ${j.renewal_window_open?'var(--red)':'var(--line)'}">
      <span class="newsMeta">CONTRACT PLANNING</span><h2>${j.renewal_window_open?'Renewal Window Open':'Renewals Open on Day '+Number(j.renewal_open_day||60)}</h2>
      <p class="muted">${j.renewal_window_open?'Expiring human contracts can be negotiated now through the end of the regular season. Choose either the player’s current rate or next season’s veteran minimum, choose 1–3 seasons, and explain the roster/XP plan. Accepted renewals begin next season; no XP is paid early.':'Until Day '+Number(j.renewal_open_day||60)+', expiring contracts remain locked. When the window opens, every renewal that needs attention will appear in the Coach Desk Action Center.'}</p>
      ${j.renewal_window_open?(expiring.length?`<div class="upgradeGrid">${expiring.map(c=>{const r=c.renewal||null;const status=String(r?.status||'');return `<div class="upgradeCard"><div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start"><div><h3>${escapeHtml(c.name)}</h3><div class="muted">${escapeHtml(c.primary_pos)} • current ${Number(c.salary||0).toFixed(2)}/G • expires after this season</div></div>${status==='ACCEPTED'?'<span class="pill green">RENEWED</span>':status?'<span class="pill">OFFER SENT</span>':'<span class="pill red">ACTION</span>'}</div>${status==='ACCEPTED'?`<p><b>${Number(r.salary||0).toFixed(2)}/G • ${Number(r.years||0)} season(s)</b> beginning Season ${Number(r.effective_season||j.season+1)}</p>${r.message?`<div class="muted"><b>Plan:</b> ${escapeHtml(r.message)}</div>`:''}`:status?`<p><b>${Number(r.salary||0).toFixed(2)}/G • ${Number(r.years||0)} season(s)</b> • waiting on player</p>${r.message?`<div class="muted"><b>Your plan:</b> ${escapeHtml(r.message)}</div>`:''}<button class="btn ghost eblSpaceTopXs" data-ebl-action="cancel-offer" data-offer="${Number(r.id)}">Cancel & Revise</button>`:`<div class="grid eblSpaceTopSm"><label>Rate<select id="renewMode${Number(c.player_id)}"><option value="CURRENT">Keep current rate • ${Number(c.renewal_same_rate||c.salary||0).toFixed(2)}/G</option><option value="VETERAN_MIN">Veteran minimum • ${Number(c.renewal_veteran_minimum||.30).toFixed(2)}/G</option></select></label><label>Term<select id="renewYears${Number(c.player_id)}"><option value="1">1 season</option><option value="2" selected>2 seasons</option><option value="3">3 seasons</option></select></label></div><label class="label" style="display:block;margin-top:8px">Coach's plan / explanation</label><textarea id="renewMsg${Number(c.player_id)}" maxlength="600" rows="4" placeholder="Explain why you want them back and how you plan to use the club's XP — roster, development coach, facilities, future signings, etc."></textarea><div class="muted" style="margin:6px 0">Future years of a multi-season renewal rise +.01 XP/game at each rollover.</div><button class="btn" data-ebl-action="send-renewal-offer" data-player="${Number(c.player_id)}">Send Renewal Offer</button>`}</div>`}).join('')}</div>`:'<p class="muted">No human contracts expire after this season.</p>') : ''}
    </div>
    <div class="coachGrid"><div><h2>Free Agents</h2><p class="muted">Offer up to 25 XP as a one-time signing bonus and a 1–3 season contract. Every rookie contract is fixed at <b>.30 XP/game</b>. Veteran minimum salary rises .01 per completed service season, and multi-year veteran contracts rise .01 XP/game at each season rollover.</p><button class="btn" data-ebl-action="load-coach-free-agents">Refresh Free Agents</button><div id="coachFAs"></div></div>
    <div><h2>Open Free-Agent Offers</h2>${j.offers.filter(o=>String(o.offer_type||'FREE_AGENT').toUpperCase()!=='RENEWAL').length?j.offers.filter(o=>String(o.offer_type||'FREE_AGENT').toUpperCase()!=='RENEWAL').map(o=>`<div class="offer"><b>${o.username?`<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(o.username)}">${escapeHtml(o.name)}</button>`:escapeHtml(o.name)}</b> • ${o.primary_pos}${o.username?` • <button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(o.username)}">@${escapeHtml(o.username)}</button>`:''}<br>${o.proposed_role?`Proposed role ${escapeHtml(o.proposed_role)} • `:''}${o.bonus} XP bonus • ${o.salary}/G • ${o.years} yr<br><button class="btn" data-ebl-action="cancel-offer" data-offer="${o.id}">Cancel Offer</button></div>`).join(''):'<p class="muted">No open free-agent offers.</p>'}
    <h2 class="coachSection">Active Contracts</h2>${(j.contracts||[]).length?`<div class="contractGrid">${j.contracts.map(c=>`<div class="contractCard"><div class="contractIdentity">${typeof eblIdentitySurfaceRenderer==='function'?eblIdentitySurfaceRenderer({player_id:c.player_id,name:c.name,username:c.username,franchise_id:j.team.id},{size:'xs'}):(c.username?`<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(c.username)}">${escapeHtml(c.name)}</button> <button class="clickableName muted" data-ebl-action="open-user-profile" data-username="${jsq(c.username)}">@${escapeHtml(c.username)}</button>`:escapeHtml(c.name))}${c.user_id&&Number(c.years_remaining)===1?'<span class="pill red">EXPIRING</span>':''}</div><div class="contractFacts"><span><small>POS</small><b>${escapeHtml(c.primary_pos||'—')}</b></span><span><small>SALARY</small><b>${Number(c.salary||0).toFixed(2)}/G</b></span><span><small>BONUS</small><b>${Number(c.bonus||0).toFixed(1)}</b></span><span><small>YEARS LEFT</small><b>${Number(c.years_remaining||0)}</b></span></div></div>`).join('')}</div>`:'<p class="muted">No active contracts.</p>'}</div></div>
   </div>
   <div id="cUpgrades" class="subpane">
    <h2>Franchise Treasury & Revenue</h2>
    <p class="muted">Every club begins from the 480 XP league base. Each completed season permanently grows annual funding by <b>+5 XP for the top third, +4 for the middle third, or +3 for the bottom third</b>. Final placement also pays <b>1–30 spendable XP</b>, while rebuilding clubs earn up to a <b>+5% game-XP development boost</b>. Unused treasury rolls over without a cap.</p>
    <div class="grid"><div class="statBox"><span class="label">CURRENT TREASURY</span><b>${Number(j.team.xp_budget||0).toFixed(1)}</b></div><div class="statBox"><span class="label">RECURRING FUNDING</span><b>${Number(j.team.next_season_base_budget||480).toFixed(1)}</b></div><div class="statBox"><span class="label">PERMANENT STANDINGS GROWTH</span><b>+${Number(j.team.permanent_pool_growth||0).toFixed(1)}</b></div><div class="statBox"><span class="label">REVENUE GROWTH</span><b>+${Number(j.team.revenue_upgrade_bonus||0).toFixed(1)}/YR</b></div><div class="statBox"><span class="label">LAST FINISH REWARD</span><b>+${Number(j.team.finish_reward||0).toFixed(1)}</b></div><div class="statBox"><span class="label">LAST POOL GROWTH</span><b>+${Number(j.team.last_pool_growth||0).toFixed(1)}</b></div><div class="statBox"><span class="label">PLAYER DEVELOPMENT</span><b>${rebuildBonusText}</b></div></div>
    ${(()=>{
      const fmt=mods=>Object.entries(mods||{}).map(([k,v])=>`${v>0?'+':''}${Number(v)} ${k}`).join(' • ')||'No rating modifier';
      const profiles=(stadium.profiles||[]);
      const opts=profiles.map(x=>`<option value="${escapeHtml(x.key)}" ${x.key===stadium.park_profile?'selected':''}>${escapeHtml(x.name)} — ${escapeHtml(fmt({...x.hitter,...x.pitcher}))}</option>`).join('');
      const locked=!stadium.edit_open;
      return `<div class="card eblSpaceTopM"><span class="newsMeta">HOME BALLPARK</span><h2>${escapeHtml(stadium.stadium_name||((j.team?.name||'EBL')+' Ballpark'))}</h2><p class="muted"><b>${escapeHtml(stadium.profile_name||'Neutral Park')}</b> • ${escapeHtml(stadium.description||'No gameplay modifier.')}</p><div class="grid"><label>Stadium Name<input id="coachStadiumName" maxlength="60" value="${escapeHtml(stadium.custom_name||stadium.stadium_name||'')}" ${locked?'disabled':''}></label><label>Park Profile<select id="coachParkProfile" ${locked?'disabled':''}>${opts}</select></label></div><div class="muted eblSpaceTopXs"><b>Current game effect:</b> Hitters ${escapeHtml(fmt(stadium.hitter))} • Pitchers ${escapeHtml(fmt(stadium.pitcher))}. The same park effect applies to both clubs; your edge comes from building a roster that fits the park.</div><div class="muted eblSpaceTopTiny">Park factors never change permanent player ratings and are not amplified by Stadium Level.</div><button class="btn eblSpaceTopSm" ${locked?'disabled':''} data-ebl-action="save-coach-stadium">${locked?'LOCKED UNTIL OFFSEASON':'Save Stadium'}</button></div>`;
    })()}
    <div class="card eblSpaceTopM"><b>Optional Revenue Investments</b><p class="muted" style="margin:6px 0 0">Each revenue category has <b>5 permanent levels</b>. Upgrade costs rise <b>50 → 65 → 80 → 100 → 125 XP</b>, while that category's annual funding grows to <b>+5 → +10 → +20 → +40 → +80 XP/year</b>. Build them when your treasury can support it; they are long-term wealth investments, not roster requirements.</p></div>
    ${(()=>{const costs=(j.team.revenue_upgrade_costs||[50,65,80,100,125]).map(Number),bonuses=[0,...(j.team.revenue_upgrade_bonuses||[5,10,20,40,80]).map(Number)],max=Number(j.team.revenue_branch_max||5),branches=[
      ['seating','Stadium Seating','Expand capacity, premium seating and game-day attendance.'],
      ['concessions','Concessions','Improve food, beverage and ballpark sales operations.'],
      ['marketing','Marketing','Grow the club brand, promotions and local fan reach.'],
      ['sponsorships','Corporate Partnerships','Build recurring commercial and partner revenue.'],
      ['merchandising','Merchandising','Expand team merchandise and retail operations.'],
      ['media','Media Operations','Grow broadcasts, digital coverage and club media revenue.']
    ];return `<div class="upgradeGrid eblSpaceTopM">${branches.map(([key,name,desc])=>{let lvl=Math.max(0,Math.min(max,Number(j.team[key+'_level']||0))),locked=lvl>=max,next=lvl+1,cost=locked?0:Number(costs[lvl]??0),current=Number(bonuses[lvl]??0),nextBonus=locked?current:Number(bonuses[next]??current),gain=Math.max(0,nextBonus-current);return `<div class="upgradeCard"><h3>${name}</h3><div><b>Level ${lvl}/${max}</b> • +${current} XP/year</div><div class="muted">${desc}</div>${locked?`<div class="muted">Maximum revenue development reached • +${current} XP/year permanently</div>`:`<div class="muted">Next: ${cost} XP • Level ${next} becomes +${nextBonus} XP/year <b>(+${gain}/year)</b></div>`}<button class="btn" ${locked?'disabled':''} data-ebl-action="buy-franchise-upgrade" data-upgrade="${key}">${locked?'BRANCH MAX':`Upgrade • ${cost} XP`}</button></div>`}).join('')}</div>`})()}

    <h2 class="coachSection">Baseball Operations</h2>
    <p class="muted">Permanent facilities improve how your organization develops and recovers without directly buying player ratings.</p>
    ${(()=>{const costs=[50,65,80,100,125],tl=Number(j.team.training_level||0),rl=Number(j.team.recovery_level||0);return `<div class="upgradeGrid">
      <div class="upgradeCard"><h3>Training Facility</h3><div><b>Level ${tl}/5</b> • Daily practice ${Number(0.25+tl*.01).toFixed(2)} XP</div><div class="muted">Each level adds +0.01 XP to every completed daily team practice.</div><button class="btn" ${tl>=5?'disabled':''} data-ebl-action="buy-facility-upgrade" data-facility="training">${tl>=5?'MAX LEVEL':'Upgrade • '+costs[Math.min(4,tl)]+' XP'}</button></div>
      <div class="upgradeCard"><h3>Recovery Center</h3><div><b>Level ${rl}/5</b> • +${rl*2} fatigue recovery/day</div><div class="muted">Pitchers recover faster between league days. Each level adds +2 fatigue recovery per day.</div><button class="btn" ${rl>=5?'disabled':''} data-ebl-action="buy-facility-upgrade" data-facility="recovery">${rl>=5?'MAX LEVEL':'Upgrade • '+costs[Math.min(4,rl)]+' XP'}</button></div>
    </div>`})()}
    <h2 class="coachSection">Seasonal Development Staff</h2>
    <p class="muted">Every franchise gets its first development specialist <b>free each season</b>. Add up to two more specialists with team XP, then choose how intense each paid program should be. Permanent coach points stay with players even if they later change teams.</p>
    ${(()=>{
      const coaches=j.development_coaches||[],rules=j.development_coach_rules||{first_free:true,maximum:3,base_cost:30,hiring_close_day:49,intensity:[{level:1,name:'Standard',cost:30,days:[0,49,95]},{level:2,name:'Focused',cost:35,days:[0,24,49,95]},{level:3,name:'Elite',cost:40,days:[0,24,49,70,95]}]},day=Number(j.league_day||0),phase=String(j.phase||'REGULAR').toUpperCase(),open=phase==='REGULAR'&&day<Number(rules.hiring_close_day||49);
      const options=(j.development_coach_options&&j.development_coach_options.length)?j.development_coach_options:[{coach_type:'SPEED',name:'Speed Coach',attribute:'SPD',category:'BASERUNNING',applies_to:'HITTERS'}];
      const used=new Set(coaches.map(x=>String(x.coach_type||'').toUpperCase()));
      const available=options.filter(o=>!used.has(String(o.coach_type||'').toUpperCase()));
      const cats=['HITTING','BASERUNNING','FIELDING','PITCHING'];
      const chooser=cats.map(cat=>{const rows=available.filter(o=>o.category===cat);if(!rows.length)return '';return `<optgroup label="${cat}">${rows.map(o=>`<option value="${escapeHtml(o.coach_type)}">${escapeHtml(o.name)} • +${escapeHtml(o.attribute)} • ${escapeHtml(o.applies_to||'ELIGIBLE')}</option>`).join('')}</optgroup>`}).join('');
      const parseList=(raw,fallback=[])=>{if(Array.isArray(raw))return raw.map(Number);try{return JSON.parse(raw||'[]').map(Number)}catch{return fallback}};
      const existing=coaches.map(x=>{
        const spec=options.find(o=>o.coach_type===x.coach_type)||{name:x.coach_type,attribute:x.attribute,applies_to:'ELIGIBLE PLAYERS'};
        const checkpoints=parseList(x.checkpoint_days??x.checkpoint_days_json,[0,40,81]);
        const applied=parseList(x.applied_days??x.applied_days_json,[]);
        const hiredDay=Number(x.hired_day||0);
        const schedule=checkpoints.map(d=>{const label=d===0?'Opening':`Day ${d}`;if(applied.includes(Number(d))){if(d>0&&d<hiredDay)return `<span class="pill">${label} • missed</span>`;return `<span class="pill green">✓ ${label}</span>`}return `<span class="pill">${label} • waiting</span>`}).join(' ');
        return `<div class="upgradeCard"><div style="display:flex;justify-content:space-between;gap:8px;align-items:flex-start"><div><h3>${escapeHtml(spec.name)}</h3><div><b>+${escapeHtml(spec.attribute)}</b> • ${escapeHtml(spec.applies_to||'ELIGIBLE PLAYERS')}</div></div><span class="pill ${Number(x.is_free||0)?'green':''}">${Number(x.is_free||0)?'FREE':Number(x.cost||0).toFixed(0)+' XP'}</span></div><div class="muted eblSpaceTopTiny">${escapeHtml(x.intensity_name||({1:'Standard',2:'Focused',3:'Elite'}[Number(x.intensity||1)]||'Standard'))} intensity • Slot ${Number(x.coach_slot||1)}/${Number(rules.maximum||3)}</div><div style="display:flex;gap:5px;flex-wrap:wrap;margin-top:8px">${schedule}</div></div>`;
      }).join('');
      const firstFree=coaches.length===0;
      const intensityRows=(rules.intensity||[]).length?rules.intensity:[{level:1,name:'Standard',cost:30,days:[0,49,95]},{level:2,name:'Focused',cost:35,days:[0,24,49,95]},{level:3,name:'Elite',cost:40,days:[0,24,49,70,95]}];
      const intensitySelect=intensityRows.map(t=>`<option value="${Number(t.level)}">${escapeHtml(t.name)} • ${Number(t.cost||30).toFixed(0)} XP • ${((t.days||[]).map(d=>Number(d)===0?'Opening':'Day '+Number(d))).join(', ')}</option>`).join('');
      const canAdd=open&&coaches.length<Number(rules.maximum||3)&&available.length>0;
      const addCard=canAdd?`<div class="upgradeCard"><h3>${firstFree?'Your Free Seasonal Coach':'Add Development Coach'}</h3><div><b>${firstFree?'FREE':'30–40 XP'}</b> • choose one roster direction</div><label class="label" style="display:block;margin-top:10px">SPECIALIST</label><select id="seasonDevCoachSelect" style="width:100%;margin-top:6px">${chooser}</select>${firstFree?`<div class="muted eblSpaceTopXs"><b>Standard intensity:</b> +1 when selected, +1 at Day 49, +1 at Day 95. Your first coach is free every season.</div>`:`<label class="label" style="display:block;margin-top:10px">INTENSITY</label><select id="seasonDevCoachIntensity" style="width:100%;margin-top:6px">${intensitySelect}</select><div class="muted eblSpaceTopXs">Standard: 30 XP / 3 boosts • Focused: 35 XP / 4 boosts • Elite: 40 XP / 5 boosts. Hiring after an early checkpoint does not back-pay the missed boost.</div>`}<button class="btn eblSpaceTopSm" data-ebl-action="hire-development-coach" data-free="${firstFree?'1':'0'}">${firstFree?'Choose Free Coach':'Add Paid Coach'}</button></div>`:'';
      const closed=!open?`<div class="upgradeCard"><h3>Hiring Window Closed</h3><div class="muted">Development staff must be chosen before League Day ${Number(rules.hiring_close_day||49)}. Current staff continue through all remaining scheduled checkpoints.</div></div>`:'';
      return `<div class="grid"><div class="statBox"><span class="label">COACHES</span><b>${coaches.length}/${Number(rules.maximum||3)}</b></div><div class="statBox"><span class="label">FREE COACH</span><b>${coaches.length?'USED':'AVAILABLE'}</b></div><div class="statBox"><span class="label">HIRING WINDOW</span><b>${open?'OPEN':'CLOSED'}</b></div></div><div class="upgradeGrid eblSpaceTopSm">${existing}${addCard}${closed}</div>`
    })()}
    <h2 class="coachSection">Team Sponsorships</h2>
    <p class="muted">A sponsorship costs 25 XP and gives every active player on the club a temporary +1 team modifier for the current season and the next season. It does not permanently change a player's trained attribute.</p>
    ${(()=>{const active=j.sponsorships||[],attrs=[['ARM','Arm Equipment Partner'],['ACC','Precision Equipment Partner'],['FLD','Fielding Equipment Partner'],['REAC','Reaction Training Partner'],['SPD','Performance Footwear Partner']];return `<div class="upgradeGrid">${attrs.map(([a,n])=>{const x=active.find(z=>z.attribute===a);return `<div class="upgradeCard"><h3>${n}</h3><div><b>+1 ${a}</b> • 25 XP • 2 seasons</div>${x?`<div class="muted">ACTIVE • Seasons ${x.start_season}–${x.end_season}</div><button class="btn" disabled>ACTIVE</button>`:`<div class="muted">Applies while a player is on this team's active roster.</div><button class="btn" data-ebl-action="buy-team-sponsor" data-attribute="${a}">Sign Sponsor • 25 XP</button>`}</div>`}).join('')}</div>`})()}
   </div>
   </div>`;
 if(window.brandPreview){updateBrandPreview();['brandName','brandLogo','brandPrimary','brandSecondary','brandAccent'].forEach(id=>document.querySelector('#'+id)?.addEventListener('input',updateBrandPreview));}
 setTimeout(()=>{try{refreshPitchStaff()}catch(e){}},0);
 }catch(e){coachHub.innerHTML=`<p class="red">${e.error||'Could not load coach interface'}</p>`}
}
async function reloadCoachPaneKeepPosition(id){const y=window.scrollY;await loadCoachHub();coachPane(id,null);requestAnimationFrame(()=>window.scrollTo({top:y,behavior:'auto'}))}
async function buyFranchiseUpgrade(kind){try{const j=await api('/api/coach/franchise-upgrade',{method:'POST',body:JSON.stringify({kind})});eblToast(`${kind} upgraded to Level ${j.level}. This branch now adds +${Number(j.branch_annual_bonus||0).toFixed(0)} XP/year (${Number(j.annual_gain||0).toFixed(0)} more than before).`,'success',4800);await reloadCoachPaneKeepPosition('cUpgrades')}catch(e){eblAlert(e.error==='INSUFFICIENT_RESERVE'?`Need ${e.cost} treasury XP.`:e.error==='MAX_LEVEL'?'That revenue branch is already Level 5.':(e.error||'Upgrade failed'))}}
async function buyFacilityUpgrade(kind){try{const j=await api('/api/coach/facility-upgrade',{method:'POST',body:JSON.stringify({kind})});eblToast(`${kind} facility upgraded to Level ${j.level}.`,'success');await reloadCoachPaneKeepPosition('cUpgrades')}catch(e){eblAlert(e.error==='INSUFFICIENT_RESERVE'?`Need ${e.cost} treasury XP.`:(e.error||'Facility upgrade failed'))}}
async function saveCoachStadium(){
 const stadium_name=document.getElementById('coachStadiumName')?.value.trim()||'';
 const park_profile=document.getElementById('coachParkProfile')?.value||'NEUTRAL';
 try{const j=await api('/api/coach/stadium',{method:'POST',body:JSON.stringify({stadium_name,park_profile})});eblToast(`${j.stadium?.stadium_name||'Home stadium'} set to ${j.stadium?.profile_name||'Neutral Park'}.`,'success',4200);await reloadCoachPaneKeepPosition('cUpgrades')}
 catch(e){eblAlert(e.error==='STADIUM_LOCKED_IN_SEASON'?'Stadium identity and park factors lock once the season begins. Change them in the offseason.':e.error==='INVALID_STADIUM_NAME'?'Stadium names must be 60 characters or fewer.':(e.error||'Could not update stadium.'))}
}
async function buyTeamSponsor(attribute){try{const j=await api('/api/coach/sponsor',{method:'POST',body:JSON.stringify({attribute})});eblToast(`Sponsor signed: +1 ${attribute} for Seasons ${j.start_season}–${j.end_season}.`,'success',4400);await reloadCoachPaneKeepPosition('cUpgrades')}catch(e){eblAlert(e.error==='INSUFFICIENT_RESERVE'?`Need ${e.cost} treasury XP.`:(e.error||'Sponsorship failed'))}}
async function hireDevelopmentCoach(coach_type='SPEED',intensity=1){try{const j=await api('/api/coach/development-coach',{method:'POST',body:JSON.stringify({coach_type,intensity:Number(intensity||1)})});const schedule=(j.checkpoints||[]).map(d=>Number(d)===0?'Opening':'Day '+Number(d)).join(', ');eblToast(`${j.name||'Development coach'} added • ${j.free?'FREE':Number(j.cost||0).toFixed(0)+' XP'} • ${j.intensity_name||'Standard'} intensity. +1 ${j.attribute||j.coach?.attribute||''} applied now; schedule: ${schedule}.`,'success',5200);await reloadCoachPaneKeepPosition('cUpgrades')}catch(e){if(e.error==='INSUFFICIENT_RESERVE')eblAlert(`Need ${e.cost} treasury XP.`);else if(e.error==='DEVELOPMENT_COACH_LIMIT')eblAlert(`Development staff is capped at ${e.maximum||3} coaches per season.`);else if(e.error==='DEVELOPMENT_COACH_DUPLICATE_SPECIALTY')eblAlert('That specialist is already on your staff this season. Choose a different development focus.');else eblAlert(e.detail||e.error||'Could not hire development coach.')}}
async function sendRenewalOffer(pid){
 const mode=document.getElementById('renewMode'+pid)?.value||'CURRENT';
 const years=Number(document.getElementById('renewYears'+pid)?.value||2);
 const message=document.getElementById('renewMsg'+pid)?.value.trim()||'';
 if(message.length<10){eblAlert('Add a short explanation of the contract and your XP/roster plan.');return}
 try{const r=await api('/api/coach/renewal-offer',{method:'POST',body:JSON.stringify({player_id:pid,salary_mode:mode,years,message})});eblToast(`Renewal sent • ${Number(r.salary||0).toFixed(2)} XP/game • ${years} season(s)`,'success');await loadCoachHub();setTimeout(()=>openCoachContracts(),0)}
 catch(e){eblAlert(e.error==='NEXT_SEASON_PAYROLL_EXCEEDED'?`That renewal would project ${Number(e.projected_payroll||0).toFixed(1)} XP of next-season payroll against ${Number(e.projected_treasury??e.base_budget??0).toFixed(1)} XP of projected next-season treasury.`:e.error==='RENEWAL_MESSAGE_REQUIRED'?'Add a short explanation so the player understands the plan.':(e.error||'Could not send renewal offer'))}
}
function openCoachPaneById(id){const pane=document.getElementById(id);if(!pane)return;const btn=[...document.querySelectorAll('#coachHub .subtabs .subtab')].find(x=>(x.getAttribute('onclick')||'').includes(`'${id}'`));coachPane(id,btn||null);setTimeout(()=>pane.scrollIntoView({behavior:'smooth',block:'start'}),0)}
function openCoachContracts(){openCoachPaneById('cMarket')}
function openCoachRoster(){openCoachPaneById('cRoster')}
function openCoachPitching(){openCoachPaneById('cPitch')}
function openCoachUpgrades(){openCoachPaneById('cUpgrades')}

function coachPane(id,b){if(b)switchPane('.subpane',id,b);else{document.querySelectorAll('#coachHub .subpane').forEach(x=>x.classList.remove('active'));document.getElementById(id)?.classList.add('active');}}
function playerOptions(arr,selected,multi=[]){return arr.map(x=>`<option value="${x.id}" ${(x.id==selected||multi.includes(x.id))?'selected':''}>${x.name} — ${x.primary_pos}</option>`).join('')}

function coachPitchMeta(p={}){
 const r=p.recovery||{readiness:100,fatigue:0};
 return `${escapeHtml(p.primary_pos||'P')} • #${Number(p.jersey_number||0)} • ${Number(r.readiness??100)}% ready${Number(r.fatigue||0)>0?` • ${Number(r.fatigue).toFixed(1)} fatigue`:' • fresh'}`;
}
function renderCoachPitchCard(i,id,P){
 const p=P.find(x=>Number(x.id)===Number(id))||{};
 const r=p.recovery||{readiness:100,fatigue:0};
 return `<div class="coachPitchCard">
   <div class="coachPitchTag">SP${i+1}</div>
   <div class="coachPitchPortrait">${p.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(p,'sm'):''}</div>
   <div class="coachPitchInfo"><b>${escapeHtml(p.name||'Select Starter')}</b><span>${p.id?coachPitchMeta(p):'Rotation slot open'}</span><div class="coachReadiness"><i style="width:${Math.max(0,Math.min(100,Number(r.readiness??100)))}%"></i></div></div>
   <select id="rot${i}" onchange="refreshPitchStaff()">${i>=3?'<option value="">— Open rotation slot —</option>':''}${playerOptions(P,id)}</select>
   <div class="coachOrderBtns"><button type="button" class="coachMove" data-ebl-action="coach-move-starter" data-index="${i}" data-dir="-1" ${i===0?'disabled':''}>▲</button><button type="button" class="coachMove" data-ebl-action="coach-move-starter" data-index="${i}" data-dir="1" ${i===4?'disabled':''}>▼</button></div>
   <div class="coachPitchActions">${p.id?`<button type="button" class="coachBullpenMove" data-ebl-action="coach-starter-bullpen" data-index="${i}">Move to Bullpen</button>`:''}</div>
 </div>`;
}
function renderCoachRecoveryCard(p={}){
 const r=p.recovery||{readiness:100,fatigue:0};
 return `<div class="coachRecoveryCard">${typeof eblPublicPortrait==='function'?eblPublicPortrait(p,'sm'):''}<div><b>${escapeHtml(p.name||'Pitcher')}</b><span>${Number(r.readiness??100)}% ready • ${Number(r.fatigue||0)>0?Number(r.fatigue).toFixed(1)+' fatigue':'fully recovered'}</span><div class="coachReadiness"><i style="width:${Math.max(0,Math.min(100,Number(r.readiness??100)))}%"></i></div></div></div>`;
}
function coachSingleRole(id,label,desc,value,P){
 const p=P.find(x=>Number(x.id)===Number(value))||{};
 return `<div class="coachRoleCard" data-role="${id}"><div class="coachRoleTop"><span class="coachPitchTag">${id}</span><div><b>${label}</b><small>${desc}</small></div></div><div class="coachRolePlayer"><div class="coachPitchPortrait">${p.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(p,'sm'):''}</div><div class="coachPitchInfo"><b>${escapeHtml(p.name||'Unassigned')}</b><span>${p.id?coachPitchMeta(p):'Choose a pitcher'}</span></div></div><select id="bp${id}" onchange="refreshPitchStaff()"><option value="">—</option>${playerOptions(P,value)}</select></div>`;
}
function moveStarter(i,dir){
 const j=i+dir;if(j<0||j>4)return;const a=document.querySelector('#rot'+i),b=document.querySelector('#rot'+j);if(!a||!b)return;const t=a.value;a.value=b.value;b.value=t;refreshPitchStaff();
}
function bullpenSelects(){
 return ['bpCL','bpSU1','bpSU2','bpMR','bpLR','bpEmergency'].map(id=>document.getElementById(id)).filter(Boolean);
}
function selectedRotation(){
 return [...Array(5)].map((_,i)=>Number(document.getElementById('rot'+i)?.value||0)).filter(Boolean);
}
function syncBullpenEligibility(){
 const starterSet=new Set(selectedRotation());
 bullpenSelects().forEach(sel=>{
   [...sel.options].forEach(opt=>{
     const pid=Number(opt.value||0);
     if(!pid)return;
     const isStarter=starterSet.has(pid);
     opt.disabled=isStarter;
     if(isStarter&&opt.selected)opt.selected=false;
   });
 });
}
function addPitcherToMulti(id,pid){
 const sel=document.getElementById(id);if(!sel)return;
 const opt=[...sel.options].find(o=>Number(o.value)===Number(pid));
 if(opt){opt.disabled=false;opt.selected=true;}
}
function removePitcherFromBullpen(pid){
 ['bpCL','bpSU1','bpSU2'].forEach(id=>{const el=document.getElementById(id);if(el&&Number(el.value)===Number(pid))el.value='';});
 ['bpMR','bpLR','bpEmergency'].forEach(id=>{const el=document.getElementById(id);if(el)[...el.options].forEach(o=>{if(Number(o.value)===Number(pid))o.selected=false;});});
}
function moveStarterToBullpen(i){
 const slots=[...Array(5)].map((_,n)=>document.getElementById('rot'+n));
 const pid=Number(slots[i]?.value||0);if(!pid)return;
 const current=slots.map(x=>Number(x?.value||0)).filter(Boolean);
 if(current.length<=3){eblAlert('EBL requires at least 3 starting pitchers. Add another starter before moving this one to the bullpen.');return;}
 const P=window.__EBL_COACH_PITCHERS||[],p=P.find(x=>Number(x.id)===pid)||{};
 removePitcherFromBullpen(pid);
 const remaining=current.filter(x=>x!==pid);
 slots.forEach((sel,n)=>{if(sel)sel.value=remaining[n]?String(remaining[n]):'';});
 syncBullpenEligibility();
 addPitcherToMulti('bpMR',pid);
 addPitcherToMulti('bpEmergency',pid);
 refreshPitchStaff();
 const mr=document.getElementById('bpMR');if(mr)mr.closest('.coachMultiRole')?.scrollIntoView({behavior:'smooth',block:'center'});
 const warning=document.getElementById('coachPitchWarning');
 if(warning){warning.classList.remove('hidden');warning.textContent=`${p.name||'Pitcher'} moved out of the rotation and into Middle Relief. He is also available for Emergency duty. Save Pitching Staff when you are ready.`;}
}
function refreshPitchStaff(){
 const P=window.__EBL_COACH_PITCHERS||[];
 syncBullpenEligibility();
 const rotationCount=selectedRotation().length;
 document.querySelectorAll('.coachPitchCard').forEach((card,i)=>{
   const id=Number(document.querySelector('#rot'+i)?.value||0),p=P.find(x=>Number(x.id)===id)||{},r=p.recovery||{readiness:100,fatigue:0};
   const portrait=card.querySelector('.coachPitchPortrait'),info=card.querySelector('.coachPitchInfo'),action=card.querySelector('.coachPitchActions');
   if(portrait)portrait.innerHTML=p.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(p,'sm'):'';
   if(info)info.innerHTML=`<b>${escapeHtml(p.name||'Select Starter')}</b><span>${p.id?coachPitchMeta(p):'Rotation slot open'}</span><div class="coachReadiness"><i style="width:${Math.max(0,Math.min(100,Number(r.readiness??100)))}%"></i></div>`;
   if(action)action.innerHTML=p.id?`<button type="button" class="coachBullpenMove" data-ebl-action="coach-starter-bullpen" data-index="${i}" ${rotationCount<=3?'disabled title="Minimum 3 starters"':''}>Move to Bullpen</button>`:'';
 });
 document.querySelectorAll('.coachRoleCard').forEach(card=>{
   const role=card.dataset.role,id=Number(document.querySelector('#bp'+role)?.value||0),p=P.find(x=>Number(x.id)===id)||{};
   const portrait=card.querySelector('.coachPitchPortrait'),info=card.querySelector('.coachPitchInfo');
   if(portrait)portrait.innerHTML=p.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(p,'sm'):'';
   if(info)info.innerHTML=`<b>${escapeHtml(p.name||'Unassigned')}</b><span>${p.id?coachPitchMeta(p):'Choose a pitcher'}</span>`;
 });
 const primary=['CL','SU1','SU2'].map(r=>Number(document.querySelector('#bp'+r)?.value||0)).filter(Boolean);
 const warning=document.querySelector('#coachPitchWarning'),dup=primary.length!==new Set(primary).size;
 if(warning&&dup){warning.classList.remove('hidden');warning.textContent='Closer, Setup 1, and Setup 2 must be three different pitchers. Middle Relief, Long Relief, and Emergency may overlap.';}
 else if(warning&&!warning.textContent?.includes('moved out of the rotation')){warning.classList.add('hidden');warning.textContent='';}
}


function depthCard(pos,H,selected=[]){
 const ids=Array.isArray(selected)?selected:[selected].filter(Boolean);
 const top=H.find(p=>Number(p.id)===Number(ids[0]))||{};
 return `<div class="coachDepthCard">
   <div class="coachDepthHead"><span class="coachPitchTag">${pos}</span><div><b>${escapeHtml(top.name||'Set backups')}</b><small>${ids.length?`${ids.length} ranked backup${ids.length===1?'':'s'}`:'No backups ranked'}</small></div></div>
   <div class="coachDepthPlayer">${top.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(top,'sm'):''}<div><b>${escapeHtml(top.name||'Open depth')}</b><span>${top.id?`${escapeHtml(top.primary_pos||'—')} • #${Number(top.jersey_number||0)}${top.overall!=null?` • OVR ${Number(top.overall)}`:''}`:'Choose players below'}</span></div></div>
   <select id="depth_${pos}" multiple size="4" onchange="refreshDepth()">${playerOptions(H,null,ids)}</select>
 </div>`;
}
function benchRole(id,tag,title,desc,H,selected=[]){
 const ids=Array.isArray(selected)?selected:[selected].filter(Boolean);
 const top=H.find(p=>Number(p.id)===Number(ids[0]))||{};
 return `<div class="coachBenchCard" data-bench-id="${id}"><div class="coachRoleTop"><span class="coachPitchTag">${tag}</span><div><b>${title}</b><small>${desc}</small></div></div><div class="coachDepthPlayer">${top.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(top,'sm'):''}<div><b>${escapeHtml(top.name||'No priority set')}</b><span>${top.id?`${escapeHtml(top.primary_pos||'—')} • #${Number(top.jersey_number||0)}`:'Rank options below'}</span></div></div><select id="${id}" multiple size="5" onchange="refreshDepth()">${playerOptions(H,null,ids)}</select></div>`;
}
function refreshDepth(){
 const H=window.__EBL_COACH_HITTERS||[];
 document.querySelectorAll('.coachDepthCard').forEach(card=>{
   const sel=card.querySelector('select'),id=Number(sel?.selectedOptions?.[0]?.value||0),p=H.find(x=>Number(x.id)===id)||{};
   const box=card.querySelector('.coachDepthPlayer');
   if(box)box.innerHTML=`${p.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(p,'sm'):''}<div><b>${escapeHtml(p.name||'Open depth')}</b><span>${p.id?`${escapeHtml(p.primary_pos||'—')} • #${Number(p.jersey_number||0)}${p.overall!=null?` • OVR ${Number(p.overall)}`:''}`:'Choose players below'}</span></div>`;
 });
 document.querySelectorAll('.coachBenchCard').forEach(card=>{
   const sel=card.querySelector('select'),id=Number(sel?.selectedOptions?.[0]?.value||0),p=H.find(x=>Number(x.id)===id)||{},box=card.querySelector('.coachDepthPlayer');
   if(box)box.innerHTML=`${p.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(p,'sm'):''}<div><b>${escapeHtml(p.name||'No priority set')}</b><span>${p.id?`${escapeHtml(p.primary_pos||'—')} • #${Number(p.jersey_number||0)}`:'Rank options below'}</span></div>`;
 });
 const catcher=Number(document.querySelector('#backupC')?.value||0),warn=document.querySelector('#coachDepthWarning');
 if(warn){warn.classList.toggle('hidden',!!catcher);warn.textContent=catcher?'':'No backup catcher is assigned. Set one so the sim has a catcher option if the starter leaves the game.';}
}


function shiftSelect(id,value){
 const opts=['STANDARD','PULL','OPPOSITE','STRAIGHT_UP'];
 const labels={STANDARD:'Standard',PULL:'Shade Pull Side',OPPOSITE:'Shade Opposite Field',STRAIGHT_UP:'Straight Up'};
 return `<select id="${id}" onchange="refreshDefense()">${opts.map(x=>`<option value="${x}" ${x===value?'selected':''}>${labels[x]}</option>`).join('')}</select>`;
}
function refreshDefense(){
 const label=v=>({STANDARD:'Standard',PULL:'Pull-side shade',OPPOSITE:'Opposite-field shade',STRAIGHT_UP:'Straight up'}[v]||v);
 const d=document.querySelector('#defDefault')?.value||'STANDARD',l=document.querySelector('#defL')?.value||'STANDARD',r=document.querySelector('#defR')?.value||'STANDARD';
 const c=!!document.querySelector('#cornersIn')?.checked,i=!!document.querySelector('#infieldIn')?.checked;
 const box=document.querySelector('#coachDefenseSummaryPanel');
 if(box)box.innerHTML=`<div><span>DEFAULT</span><b>${label(d)}</b></div><div><span>vs LHB</span><b>${label(l)}</b></div><div><span>vs RHB</span><b>${label(r)}</b></div><div><span>SITUATIONAL</span><b>${[c?'Corners in':'',i?'Infield in':''].filter(Boolean).join(' • ')||'Standard depth'}</b></div>`;
}


function coachGameDay(j,lineup,rot,bp,def,H,P,next,opp,lineupReady,rotationReady){
 const opponent=next?teamName(opp):'TBD';
 const venue=next?(next.away_id===j.team.id?'AWAY':'HOME'):'—';
 const gameDay=Number(j?.genesis_plan?.league_day||next?.league_day||j?.league_day||1);
 const genesisStarterSlot=Number(j?.genesis_plan?.starter_slot||0);
 const starterSlot=genesisStarterSlot>0?genesisStarterSlot-1:((rot&&rot.length)?((Math.max(1,gameDay)-1)%rot.length):0);
 const starterId=Number(j?.genesis_plan?.starter_id||((rot&&rot.length)?rot[starterSlot]:0))||null;
 const starter=P.find(p=>Number(p.id)===Number(starterId))||{};
 const closer=P.find(p=>Number(p.id)===Number(bp?.CL))||{};
 const steal=j.strategy?.substitutions?.steal_aggression||'NORMAL';
 const bunt=j.strategy?.substitutions?.bunt_aggression||'NORMAL';
 const byHitter=new Map((H||[]).map(p=>[Number(p.id),p]));
 const byPitcher=new Map((P||[]).map(p=>[Number(p.id),p]));
 const lineupPreview=(lineup||[]).slice(0,9).map((slot,i)=>{
   const pid=Number((slot?.player_id??slot?.id??slot) || 0),p=byHitter.get(pid)||{};
   const field=slot?.position||slot?.field_pos||slot?.pos||p.primary_pos||'—';
   return `<div class="coachGameLine"><span>${i+1}</span>${p.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(p,'sm'):''}<div><b>${escapeHtml(p.name||'Open Slot')}</b><small>${escapeHtml(field)}${p.jersey_number!=null?` • #${Number(p.jersey_number)}`:''}</small></div></div>`;
 }).join('') || '<p class="muted">Set the Starting Nine to build the game card.</p>';
 const rotationPreview=(rot||[]).map((id,i)=>{const p=byPitcher.get(Number(id))||{},isNext=i===starterSlot;return `<div class="coachGameStaff ${isNext?'coachNextStarter':''}"><span>SP${i+1}${isNext?' • NEXT':''}</span><b>${escapeHtml(p.name||'Open')}</b><small>${p.id?coachPitchMeta(p):'Not set'}</small></div>`}).join('') || '<p class="muted">No rotation set.</p>';
 const bullpenPreview=[['CL',bp?.CL],['SU1',bp?.SU1],['SU2',bp?.SU2]].map(([role,id])=>{const p=byPitcher.get(Number(id))||{};return `<div class="coachGameStaff"><span>${role}</span><b>${escapeHtml(p.name||'Unassigned')}</b><small>${p.id?coachPitchMeta(p):'Set role'}</small></div>`}).join('');
 const checks=[
   ['Starting Nine',lineupReady,lineupReady?'9 hitters set':'Lineup needs attention','cRoster'],
   ['Rotation',rotationReady,rotationReady?`${rot.length}-man rotation set`:'Choose 3–5 starters','cPitch'],
   ['Bullpen',!!bp?.CL,bp?.CL?'Closer assigned':'Closer not assigned','cPitch'],
   ['Offense',true,`${steal} steals • ${bunt} bunts`,'cDepth'],
   ['Defense',!!def?.default_shift,def?.default_shift||'No field plan','cDefense']
 ];
 return `<div class="coachGameHero">
   <div><span class="newsMeta">NEXT MATCHUP</span><h2>${next?`<span class="coachMatchupIdentity">${teamMark(j.team.id)}<span>${venue==='AWAY'?'@':'vs'}</span>${teamMark(opp)}<button class="teamLink" data-ebl-action="open-team" data-team="${jsq(opp)}">${escapeHtml(opponent)}</button></span>`:'No Game Scheduled'}</h2><p class="muted">${next?`League Day ${next.league_day} • ${venue}`:'Your next opponent will appear here when the schedule is available.'}</p></div>
   <div class="coachGameMark">${teamMark(j.team.id)}</div>
 </div>
 <div class="coachGameGrid coachGameDayGrid">
   <div class="coachGameCard"><span>PROJECTED STARTER • SP${starterSlot+1}</span>${starter.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(starter,'sm'):''}<div><b>${escapeHtml(starter.name||'Not Set')}</b><small>${starter.id?`${coachPitchMeta(starter)} • Genesis Day ${gameDay}`:'Set your rotation in Pitching Staff'}</small></div></div>
   <div class="coachGameCard"><span>LATE-INNING ARM</span>${closer.id&&typeof eblPublicPortrait==='function'?eblPublicPortrait(closer,'sm'):''}<div><b>${escapeHtml(closer.name||'Not Set')}</b><small>${closer.id?'Closer':'Assign a closer'}</small></div></div>
   <div class="coachGameCard"><span>POSITION PLAYERS</span><div class="coachNineBadge">9</div><div><b>Starting Nine</b><small>No position-player bench or substitutions</small></div></div>
 </div>
 <div class="coachSection"><div class="coachPaneHead"><div><h3>Game Readiness</h3><p class="muted">Check the actual EBL game plan before the sim reaches your next game.</p></div><div class="coachReadyBadge ${checks.every(x=>x[1])?'ready':'needs'}">${checks.filter(x=>x[1]).length}/${checks.length} READY</div></div>
 <div class="coachChecklist">${checks.map(([label,ok,detail,pane])=>`<button type="button" class="coachCheck ${ok?'ok':'needs'}" data-ebl-action="coach-jump" data-pane="${pane}"><span>${ok?'✓':'!'}</span><div><b>${label}</b><small>${escapeHtml(String(detail))}</small></div><i>›</i></button>`).join('')}</div></div>
 <div class="coachGenesisLock"><div><span class="newsMeta">GENESIS GAME PLAN</span><b>${next&&j?.genesis_plan?.game_id?'CONNECTED TO SCHEDULED GAME':'WAITING FOR SCHEDULE'}</b><small>${next?`Game ${escapeHtml(String(j.genesis_plan?.game_id||next.id||'—'))} • Day ${gameDay} • SP${starterSlot+1} ${escapeHtml(starter.name||'Not Set')}`:'The saved coach plan will connect automatically when a game is scheduled.'}</small></div><span class="coachGenesisSignal">${lineupReady&&rotationReady?'READY FOR GENESIS':'SETUP NEEDED'}</span></div>
 <div class="coachGamePlan">
   <div><span>OFFENSIVE APPROACH</span><b>${escapeHtml(steal)} STEAL • ${escapeHtml(bunt)} BUNT</b></div>
   <div><span>DEFENSIVE PLAN</span><b>${escapeHtml(def?.default_shift||'STANDARD')} • LHB ${escapeHtml(def?.vs_lhb||'STANDARD')} • RHB ${escapeHtml(def?.vs_rhb||'STANDARD')}</b></div>
 </div>
 <div class="coachGameSheet">
   <div class="coachGameSheetPanel"><div class="coachGameSheetHead"><div><span class="newsMeta">SAVED CARD</span><h3>Starting Nine</h3></div><button class="btn ghost" data-ebl-action="coach-jump" data-pane="cRoster">Edit Lineup</button></div><div class="coachGameLineup">${lineupPreview}</div></div>
   <div class="coachGameSheetPanel"><div class="coachGameSheetHead"><div><span class="newsMeta">PITCHING PLAN</span><h3>Rotation & Late Innings</h3></div><button class="btn ghost" data-ebl-action="coach-jump" data-pane="cPitch">Edit Staff</button></div><div class="coachGameStaffList">${rotationPreview}${bullpenPreview}</div></div>
 </div>`;
}
function coachJump(id){
 const pane=document.querySelector('#'+id);if(!pane)return;
 document.querySelectorAll('#coachHub .subpane').forEach(x=>x.classList.remove('active'));pane.classList.add('active');
 document.querySelectorAll('#coachHub .subtab').forEach(x=>x.classList.remove('active'));
 const btn=[...document.querySelectorAll('#coachHub .subtab')].find(x=>(x.getAttribute('onclick')||'').includes(`'${id}'`));if(btn)btn.classList.add('active');
 pane.scrollIntoView({behavior:'smooth',block:'start'});
}

function lineupRowHTML(i,id,H,fieldPositions={}){
 const posList=['C','1B','2B','3B','SS','LF','CF','RF','DH'];
 const savedPos=Object.keys(fieldPositions||{}).find(p=>Number(fieldPositions[p])===Number(id))||posList[i];
 const player=H.find(p=>Number(p.id)===Number(id))||H[i]||{};
 return `<div class="coachLineupCard" data-lineup-row="${i}">
   <div class="coachOrder">${i+1}</div>
   <div class="coachMiniPortrait">${typeof eblPublicPortrait==='function'?eblPublicPortrait(player,'sm'):''}</div>
   <div class="coachLineupInfo">
     <b>${escapeHtml(player.name||'Select Player')}</b>
     <span>${escapeHtml(player.primary_pos||'—')} • #${Number(player.jersey_number||0)}${player.overall!=null?` • OVR ${Number(player.overall)}`:''}</span>
   </div>
   <select id="fieldPos${i}" aria-label="Defensive position for batting slot ${i+1}">${posList.map(p=>`<option ${p===savedPos?'selected':''}>${p}</option>`).join('')}</select>
   <select id="bat${i}" onchange="refreshCoachLineupCards()" aria-label="Player batting ${i+1}">${playerOptions(H,id)}</select>
   <div class="coachOrderBtns">
     <button type="button" class="coachMove" data-ebl-action="coach-move-batter" data-index="${i}" data-dir="-1" ${i===0?'disabled':''}>▲</button>
     <button type="button" class="coachMove" data-ebl-action="coach-move-batter" data-index="${i}" data-dir="1" ${i===8?'disabled':''}>▼</button>
   </div>
 </div>`;
}
function moveCoachBat(i,dir){
 const j=i+dir;if(j<0||j>8)return;
 const a=document.querySelector('#bat'+i),b=document.querySelector('#bat'+j);
 if(!a||!b)return;
 const t=a.value;a.value=b.value;b.value=t;
 refreshCoachLineupCards();
}
function refreshCoachLineupCards(){
 document.querySelectorAll('.coachLineupCard').forEach((row,i)=>{
   const sel=document.querySelector('#bat'+i);
   const opt=sel?.selectedOptions?.[0];
   const id=Number(sel?.value||0);
   const p=(window.__EBL_COACH_HITTERS||[]).find(x=>Number(x.id)===id)||{};
   const info=row.querySelector('.coachLineupInfo');
   const portrait=row.querySelector('.coachMiniPortrait');
   if(info)info.innerHTML=`<b>${escapeHtml(p.name||opt?.textContent||'Select Player')}</b><span>${escapeHtml(p.primary_pos||'—')} • #${Number(p.jersey_number||0)}${p.overall!=null?` • OVR ${Number(p.overall)}`:''}</span>`;
   if(portrait&&typeof eblPublicPortrait==='function')portrait.innerHTML=eblPublicPortrait(p,'sm');
 });
}
function shiftRow(label,id,val){let opts=['STANDARD','PULL','OPPO','NO_DOUBLES','BUNT_DEFENSE','INFIELD_IN'];return `<div class="roleRow"><b>${label}</b><select id="${id}">${opts.map(x=>`<option ${x===val?'selected':''}>${x.replaceAll('_',' ')}</option>`).join('')}</select></div>`}
async function saveCoachLineup(){
 const ids=[...Array(9)].map((_,i)=>+document.querySelector('#bat'+i).value);
 const positions=[...Array(9)].map((_,i)=>document.querySelector('#fieldPos'+i).value);
 if(new Set(ids).size!==9){eblAlert('Choose nine unique hitters.');return}
 if(new Set(positions).size!==9){eblAlert('Use each defensive position exactly once.');return}
 const field_positions={};positions.forEach((pos,i)=>field_positions[pos]=ids[i]);
 try{await api('/api/coach/set-lineup',{method:'POST',body:JSON.stringify({batting_order:ids,field_positions})});eblToast('Batting order and field alignment saved.','success')}catch(e){eblAlert(e.detail||e.error)}
}
function multiVals(id){return [...document.querySelector('#'+id).selectedOptions].map(x=>+x.value)}
async function savePitchingStaff(){
 let rotation=selectedRotation();
 if(rotation.length<3||rotation.length>5||new Set(rotation).size!==rotation.length){eblAlert('Choose 3–5 unique starting pitchers.');return}
 const starterSet=new Set(rotation);
 const cleanOne=id=>{const v=valOrNull(id);return v&&!starterSet.has(v)?v:null};
 const cleanMany=id=>[...new Set(multiVals(id).filter(v=>!starterSet.has(v)))];
 let bullpen={CL:cleanOne('bpCL'),SU1:cleanOne('bpSU1'),SU2:cleanOne('bpSU2'),MR:cleanMany('bpMR'),LR:cleanMany('bpLR'),EMERGENCY:cleanMany('bpEmergency')};
 const prim=[bullpen.CL,bullpen.SU1,bullpen.SU2].filter(Boolean);
 if(prim.length!==new Set(prim).size){eblAlert('Closer, Setup 1, and Setup 2 must be different pitchers. Middle Relief, Long Relief, and Emergency may overlap.');return;}
 try{
  await api('/api/coach/set-rotation',{method:'POST',body:JSON.stringify({rotation,bullpen})});
  eblToast(`${rotation.length}-man rotation and bullpen saved.`,'success');
  await loadCoachHub();
 }catch(e){eblAlert(e.detail||e.error||'Could not save pitching staff.')}
}
function valOrNull(id){let v=document.querySelector('#'+id).value;return v?+v:null}
function currentDefense(){return {default_shift:defDefault.value,vs_lhb:defL.value,vs_rhb:defR.value,corners_in:cornersIn.checked,infield_in:infieldIn.checked}}
async function saveDefense(){
 try{
  await api('/api/coach/set-strategy',{method:'POST',body:JSON.stringify({defense:currentDefense()})});
  eblToast('Defensive plan saved.','success');
  await loadCoachHub();
 }catch(e){eblAlert(e.detail||e.error||'Could not save defensive plan.')}
}


function depthRow(pos,H,selected){
 return `<div class="roleRow"><b>${pos}</b><select id="depth_${pos.replace('1','one').replace('2','two').replace('3','three')}" multiple size="3">${playerOptions(H,null,selected)}</select></div>`;
}
function depthId(pos){return 'depth_'+pos.replace('1','one').replace('2','two').replace('3','three')}
async function saveOffense(){
 const substitutions={
   steal_aggression:document.getElementById('stealAgg')?.value||'NORMAL',
   bunt_aggression:document.getElementById('buntAgg')?.value||'NORMAL'
 };
 try{
  await api('/api/coach/set-strategy',{method:'POST',body:JSON.stringify({substitutions})});
  eblToast('Offensive strategy saved.','success');
  await loadCoachHub();
 }catch(e){eblAlert(e.detail||e.error||'Could not save offensive strategy.')}
}

async function saveDepthSubs(){
 try{
  let j=await api('/api/coach/team');
  let bench={};
  ['C','1B','2B','3B','SS','LF','CF','RF','DH'].forEach(pos=>bench[pos]=multiVals(depthId(pos)));
  let substitutions={
    pinch_hit:multiVals('phOrder'),
    pinch_run:multiVals('prOrder'),
    def_replacement:multiVals('drOrder'),
    catcher_backup:valOrNull('backupC'),
    late_inning_defense_inning:+lateDefInning.value,
    pinch_hit_threshold:phThresh.value,
    steal_aggression:stealAgg.value,
    bunt_aggression:buntAgg.value
  };
  await api('/api/coach/set-strategy',{method:'POST',body:JSON.stringify({bullpen:j.strategy.bullpen,defense:j.strategy.defense,bench,substitutions})});
  eblToast('Depth chart and substitution preferences saved.','success');
 }catch(e){eblAlert(e.error||'Could not save depth chart')}
}
let COACH_FREE_AGENTS={};
async function loadCoachFreeAgents(){
 try{
  let j=await api('/api/coach/free-agents');
  COACH_FREE_AGENTS=Object.fromEntries((j.players||[]).map(p=>[p.id,p]));
  coachFAs.innerHTML=j.players.slice(0,75).map(p=>{
   const roles=p.offer_roles||[];
   const service=Number(p.service_seasons??p.career_seasons??0);
   const rookie=p.is_rookie_contract!==undefined?!!p.is_rookie_contract:(service===0&&Number(p.minimum_offer_salary??.30)<=.3001);
   const marketLine=rookie
    ? `<br><span class="muted">Rookie contract • fixed .30/G</span>`
    : p.returning_player
      ? `<br><span class="muted returningPlayerTeam">${p.previous_franchise_id?teamMark(p.previous_franchise_id,true):''}<span>Veteran • ${service} completed season${service===1?'':'s'} • Previous ${Number(p.previous_team_salary).toFixed(2)}/G • Minimum ${Number(p.minimum_offer_salary).toFixed(2)}/G</span></span>`
      : `<br><span class="muted">Veteran • ${service} completed season${service===1?'':'s'} • Service-time minimum ${Number(p.minimum_offer_salary).toFixed(2)}/G</span>`;
   return `<div class="offer"><b>${p.username?`<button class="clickableName" data-ebl-action="open-user-profile" data-username="${jsq(p.username)}">${escapeHtml(p.name)}</button>`:escapeHtml(p.name)}</b> • Preferred ${p.primary_pos}${p.username?` • <button class="clickableName muted" data-ebl-action="open-user-profile" data-username="${jsq(p.username)}">@${escapeHtml(p.username)}</button>`:''}${marketLine}<br><span class="muted">${Object.entries(p.attributes).slice(0,6).map(([k,v])=>`${k} ${v}`).join(' • ')}</span><div style="margin:8px 0"><label class="label">OFFER AS</label><select id="coachOfferRole${p.id}" ${roles.length?'':'disabled'}>${roles.map(r=>`<option value="${escapeHtml(r)}">${escapeHtml(r)}${r===p.primary_pos?' • preferred':''}</option>`).join('')||'<option>No compatible roster role</option>'}</select></div><button class="btn" ${roles.length?'':'disabled'} data-ebl-action="coach-offer" data-player="${p.id}">Offer Contract</button></div>`
  }).join('')||'<p class="muted">No free agents.</p>'
 }catch(e){eblAlert(e.error)}
}
async function coachOffer(pid){
 let p=COACH_FREE_AGENTS[pid]||{},min=Number(p.minimum_offer_salary??.30),service=Number(p.service_seasons??p.career_seasons??0),rookie=p.is_rookie_contract!==undefined?!!p.is_rookie_contract:(service===0&&min<=.3001),proposed_role=document.getElementById('coachOfferRole'+pid)?.value||'';
 let bonus=+await eblPrompt('Signing bonus XP (0–25; one-time bonus)','0');
 let salary=rookie?.30:+await eblPrompt(`Veteran salary XP/game (service-time minimum ${min.toFixed(2)}). Multi-year deals rise .01/G each season.`,min.toFixed(2));
 let years=+await eblPrompt(rookie?'Rookie contract is fixed at .30 XP/game. Years (1-3)':`Veteran contract • ${service} completed season${service===1?'':'s'}. Years (1-3)`,'2');
 try{
  let r=await api('/api/coach/offer',{method:'POST',body:JSON.stringify({player_id:pid,bonus,salary,years,proposed_role})});
  await loadCoachHub();
  eblToast(`${rookie?'Rookie offer sent at the league-standard .30 XP/game.':`Veteran offer sent at ${Number(salary).toFixed(2)} XP/game.`} Proposed role: ${r.proposed_role||proposed_role}.`,'success',4600)
 }catch(e){
  eblAlert(e.error==='ROOKIE_SALARY_FIXED'
   ?'Rookie contracts are fixed at .30 XP/game.'
   :e.error==='SALARY_FLOOR_REQUIRED'
    ?`That player is a veteran. The service-time minimum is ${Number(e.minimum_salary??min).toFixed(2)} XP/game.`
    :e.error==='PROPOSED_ROLE_UNAVAILABLE'
     ?`That role just filled. Available now: ${(e.available_roles||[]).join(', ')||'none'}.`
     :e.error==='RE_SIGN_RAISE_REQUIRED'
      ?`Re-signing requires at least ${Number(e.minimum_salary).toFixed(2)} XP/game.`
      :e.error==='SIGNING_POOL_EXCEEDED'
       ?`That offer would exceed the protected signing pool. Available: ${Number(e.signing_pool?.available||0).toFixed(1)} XP.`
       :(e.error||'Could not send offer'))
 }
}
async function cancelOffer(id){try{await api('/api/coach/cancel-offer',{method:'POST',body:JSON.stringify({offer_id:id})});await loadCoachHub()}catch(e){eblAlert(e.error)}}
async function extendVeteranCareer(){
    if(!PLAYER)return;
    const v=PLAYER.veteran_extension||{};
    const cost=Number(v.cost||0),season=Number(v.next_career_season||0),wallet=Number(PLAYER.xp_wallet||0);
    if(!v.required){eblAlert(v.paid?`Career Season ${season} is already secured.`:'No veteran extension is due right now.');return}
    if(wallet+1e-9<cost){eblAlert(`You need ${cost.toFixed(0)} personal XP to extend this career. Current wallet: ${wallet.toFixed(1)} XP.`);return}
    if(!await eblConfirm(`Spend ${cost.toFixed(0)} personal XP to guarantee ${PLAYER.name||'this player'} returns for career Season ${season}?`))return;
    try{
        const j=await api('/api/player/veteran-extension',{method:'POST',body:JSON.stringify({player_id:PLAYER?.id})});
        eblToast(`${j.player_name||PLAYER.name} is cleared for career Season ${j.next_career_season}. ${Number(j.cost||0).toFixed(0)} XP spent.`,'success',4600);
        await loadPlayer();
        renderPlayer();
        renderHome();
    }catch(e){
        if(e?.error==='INSUFFICIENT_XP')eblAlert(`You need ${Number(e.cost||0).toFixed(0)} XP. Current wallet: ${Number(e.xp_wallet||0).toFixed(1)} XP.`);
        else if(e?.error==='VETERAN_EXTENSION_WINDOW_CLOSED')eblAlert('Veteran career extensions are purchased during the offseason.');
        else eblAlert(e?.error||e?.message||'Could not extend this career.');
    }
}

async function retirePlayer(){
    if(!PLAYER)return;
    const name=PLAYER.name||'this player';
    if(!await eblConfirm(`Retire ${name}? This permanently ends the active EBL career and releases the roster spot.`,{title:'Retire Player',confirmLabel:'CONTINUE',tone:'danger'}))return;
    if(!await eblConfirm(`Final confirmation: retire ${name} from the Elite Baseball League?`,{title:'Final Confirmation',confirmLabel:'RETIRE CAREER',tone:'danger'}))return;
    try{
        const j=await api('/api/player/retire',{method:'POST',body:JSON.stringify({confirm:true,player_id:PLAYER?.id})});
        eblToast(`${j.player_name||name} has retired. The career remains in EBL history.`,'success',4600);
        PLAYER=null;
        await refresh();
        show('player');
    }catch(e){
        if(e?.error==='RETIREMENT_WINDOW_CLOSED'){
            eblAlert(`Retirement is only available during the offseason. Current phase: ${e.phase||'unknown'}.`);
        }else{
            eblAlert(e?.error||e?.message||'Could not retire player.');
        }
    }
}

async function loadAutoAdvanceStatus(){
    const out=document.getElementById('autoAdvanceStatus');
    if(!out)return;
    try{
        const j=await api('/api/commish/auto-advance');
        const input=document.getElementById('autoAdvancePerDay');
        if(input)input.value=Number(j.per_day||1);
        const next=j.next_at_iso?new Date(j.next_at_iso):null;
        const last=j.last_at_iso?new Date(j.last_at_iso):null;
        const cadence=Number(j.per_day||1)===1?'once per day':`${Number(j.per_day||1)} times per day`;
        out.innerHTML=j.enabled
          ? `<b class="green">AUTO ADVANCE ON</b> • ${cadence} • next run ${next&&!Number.isNaN(next.getTime())?escapeHtml(next.toLocaleString()):'scheduled'} • regular-season Day ${Number(j.league_day||0)}`
          : `<b>AUTO ADVANCE OFF</b> • Regular-season Day ${Number(j.league_day||0)}${last&&!Number.isNaN(last.getTime())?` • last automatic run ${escapeHtml(last.toLocaleString())}`:''}`;
    }catch(e){out.textContent='Could not load auto-advance status: '+(e?.error||e?.message||'Unknown error')}
}
async function saveAutoAdvance(enabled){
    const out=document.getElementById('autoAdvanceStatus');
    const perDay=Math.max(1,Math.min(24,Math.floor(Number(document.getElementById('autoAdvancePerDay')?.value||1))));
    try{
        out.textContent=enabled?'Saving automatic schedule...':'Stopping automatic schedule...';
        await api('/api/commish/auto-advance',{method:'POST',body:JSON.stringify({enabled,per_day:perDay})});
        await loadAutoAdvanceStatus();
    }catch(e){out.textContent='Auto advance update failed: '+(e?.error||e?.message||'Unknown error')}
}

async function simDay(){return onceAction('simDay',async()=>{
    const out=document.getElementById('simout');
    try{
        out.textContent='Simulating league day...';
        const j=await api('/api/commish/sim-day',{method:'POST'});
        if(j.message==='PLAYOFFS_CREATED'){
            out.textContent='Regular season complete — Quarterfinals created!';
        }else{
            out.textContent=`League Day ${j.day} complete — ${j.results?.length||0} games`;
        }
        await refresh();
    }catch(e){
        out.textContent='Simulation failed: '+(e?.error || e?.message || 'Unknown error');
    }
})}
async function advanceSeason(){
    const out=document.getElementById('simout');
    if(!await eblConfirm('Advance to the next EBL season? This should only be used after the current season has reached OFFSEASON.',{title:'Advance Season',confirmLabel:'ADVANCE SEASON',tone:'warn'})){
        return;
    }
    return onceAction('advanceSeason',async()=>{
    try{
        out.textContent='Advancing to next season...';


        const j=await api('/api/commish/next-season',{
            method:'POST'
        });


        const season=j.season ?? j.next_season ?? j.new_season;
        const o=j.offseason||{};
        const details=[
            `${j.games_created||0} games scheduled`,
            `${o.contracts_expired||0} contracts expired`,
            `${o.contracts_advanced||0} contracts carried forward`,
            `${o.offers_expired||0} offers expired`,
            `${o.retired||0} retirements`
        ];
        out.innerHTML=season
            ? `<b>Season ${season} is ready.</b> Opening Day setup complete.<br><span class="muted">${details.join(' • ')}</span>`
            : (j.message || 'Next season created successfully.');


        await refresh();


    }catch(e){
        if(e?.error==='SEASON_NOT_COMPLETE'){
            out.textContent=`Cannot advance yet — league phase is ${e.phase || 'not OFFSEASON'}.`;
        }else{
            out.textContent='Season advance failed: '+(e?.error || e?.message || 'Unknown error');
        }

    }
    })
}


let LEAGUE_FRANCHISE_CHOICES=[];
let LEAGUE_SELECTED_FRANCHISES=new Set();
function renderLeagueFranchisePicker(){
  const box=document.getElementById('leagueFranchisePicker'),countOut=document.getElementById('leagueFranchiseCount');
  if(!box)return;
  const wanted=Number(document.getElementById('leagueTeamCount')?.value||8);
  box.innerHTML=LEAGUE_FRANCHISE_CHOICES.map(t=>{
    const selected=LEAGUE_SELECTED_FRANCHISES.has(t.id);
    const name=String(t.display_name||t.name||t.id);
    const p=t.primary_color||'#071A31',sec=t.secondary_color||'#D7262E',a=t.accent_color||'#D9E0E8';
    const shapes=['⚾','★','◆','⬟','✦','▲','●','E','B','L'];
    const mark=shapes[(Number(t.logo_style||1)-1)%shapes.length];
    return `<button type="button" class="franchiseChoice ${selected?'selected':''}" data-ebl-action="toggle-league-franchise" data-team="${jsq(t.id)}" style="--fc3:${a}"><span class="franchiseChoiceLogo" style="background:${p};border:4px solid ${sec};color:${a}">${mark}</span><span><span class="franchiseChoiceName">${escapeHtml(name)}</span><span class="franchiseChoiceColors"><i style="background:${p}"></i><i style="background:${sec}"></i><i style="background:${a}"></i></span></span></button>`;
  }).join('');
  if(countOut)countOut.textContent=`${LEAGUE_SELECTED_FRANCHISES.size} of ${wanted} teams selected.`;
}
function toggleLeagueFranchise(fid){
  const wanted=Number(document.getElementById('leagueTeamCount')?.value||8);
  if(LEAGUE_SELECTED_FRANCHISES.has(fid))LEAGUE_SELECTED_FRANCHISES.delete(fid);
  else if(LEAGUE_SELECTED_FRANCHISES.size<wanted)LEAGUE_SELECTED_FRANCHISES.add(fid);
  else {eblAlert(`You already selected ${wanted} teams. Remove one before choosing another.`);return}
  renderLeagueFranchisePicker();
}
function syncLeagueSelectionToCount(){
  const wanted=Number(document.getElementById('leagueTeamCount')?.value||8);
  const current=[...LEAGUE_SELECTED_FRANCHISES];
  if(current.length>wanted)LEAGUE_SELECTED_FRANCHISES=new Set(current.slice(0,wanted));
  if(LEAGUE_SELECTED_FRANCHISES.size<wanted){
    for(const t of LEAGUE_FRANCHISE_CHOICES){if(LEAGUE_SELECTED_FRANCHISES.size>=wanted)break;if(!LEAGUE_SELECTED_FRANCHISES.has(t.id))LEAGUE_SELECTED_FRANCHISES.add(t.id)}
  }
  renderLeagueFranchisePicker();
}
async function loadLeagueSizeAdmin(){
  const sel=document.getElementById('leagueTeamCount'),out=document.getElementById('leagueSizeOut');
  if(!sel||ME?.role!=='COMMISSIONER')return;
  try{
    const j=await api('/api/commish/season-membership');
    LEAGUE_FRANCHISE_CHOICES=j.franchises||[];
    const max=LEAGUE_FRANCHISE_CHOICES.length,min=Number(j.minimum_active_teams||8),current=Number(j.current_active||min);
    sel.innerHTML='';
    for(let n=min;n<=max;n+=2){const o=document.createElement('option');o.value=n;o.textContent=`${n} teams`;if(n===current)o.selected=true;sel.appendChild(o)}
    sel.onchange=syncLeagueSelectionToCount;
    const active=LEAGUE_FRANCHISE_CHOICES.filter(t=>t.current_status==='ACTIVE').map(t=>t.id);
    LEAGUE_SELECTED_FRANCHISES=new Set(active);
    syncLeagueSelectionToCount();
    out.textContent=`Current league: ${current} active teams. ${max} franchise brands are available.`;
  }catch(e){out.textContent='Could not load league-size controls: '+(e?.error||e?.message||'Unknown error')}
}
async function applyGenesisLeagueSize(){
  const n=Number(document.getElementById('leagueTeamCount')?.value||0),out=document.getElementById('leagueSizeOut');
  if(!n)return;
  const selected=[...LEAGUE_SELECTED_FRANCHISES];
  if(selected.length!==n){eblAlert(`Choose exactly ${n} franchises first. You currently have ${selected.length} selected.`);return}
  const names=selected.map(id=>LEAGUE_FRANCHISE_CHOICES.find(t=>t.id===id)?.display_name||LEAGUE_FRANCHISE_CHOICES.find(t=>t.id===id)?.name||id);
  if(!await eblConfirm(`Build Genesis with these ${n} teams?\n\n${names.join(', ')}\n\nSeason 1 results and standings will reset to Day 0.`))return;
  if(!await eblConfirm('Accounts and player identities remain, but current-season results are erased. Continue?'))return;
  try{
    out.textContent=`Building your ${n}-team Genesis league...`;
    const j=await api('/api/commish/reset-league',{method:'POST',body:JSON.stringify({team_count:n,active_franchise_ids:selected})});
    out.textContent=`Genesis reset complete: ${j.active_team_count||n} custom-selected teams • ${j.games_created||0} games scheduled.`;
    await refresh();
    await loadLeagueSizeAdmin();
  }catch(e){out.textContent='League setup failed: '+(e?.error||e?.message||'Unknown error')}
}
async function loadCoachApplications(){
  const out=document.getElementById('coachApplicationsOut');if(!out||ME?.role!=='COMMISSIONER')return;
  out.innerHTML='<span class="muted">Loading applications...</span>';
  try{
    const j=await api('/api/commish/coach-applications'),apps=j.applications||[];
    if(!apps.length){out.innerHTML='<p class="muted">No coaching applications yet.</p>';return}
    out.innerHTML=apps.map(a=>`<div class="offer"><b>${esc(a.username||'Account')}</b> <span class="newsBadge">${esc(a.status||'PENDING')}</span><div class="muted">Preferred franchise: ${esc(a.preferred_franchise_name||'Any available franchise')} • Submitted ${esc(a.created_at||'')}</div><p><b>Why coach:</b> ${esc(a.reason||'')}</p><p><b>Management philosophy:</b> ${esc(a.philosophy||'')}</p>${a.experience?`<p><b>Experience:</b> ${esc(a.experience)}</p>`:''}${a.status==='PENDING'?`<label>Commissioner note<input id="coachReviewNote${a.id}" maxlength="500" placeholder="Optional review note"></label><button class="btn" data-ebl-action="review-coach-application" data-application="${a.id}" data-decision="approve">Approve</button> <button class="btn ghost" data-ebl-action="review-coach-application" data-application="${a.id}" data-decision="deny">Deny</button>`:`<div class="muted">${a.assigned_franchise_name?'Assigned: '+esc(a.assigned_franchise_name):a.status==='APPROVED'?'Approved — awaiting franchise assignment':''}</div>`}</div>`).join('');
  }catch(e){out.textContent='Could not load coach applications: '+(e?.error||e?.message||'Unknown error')}
}
async function reviewCoachApplication(id,decision){
  const note=document.getElementById(`coachReviewNote${id}`)?.value.trim()||'';
  try{await api(`/api/commish/coach-application/${decision}`,{method:'POST',body:JSON.stringify({application_id:id,review_note:note})});await Promise.all([loadCoachApplications(),loadCoachAssignments()])}catch(e){eblAlert(e?.error||e?.message||'Coach application review failed')}
}
async function loadCoachAssignments(){
  const out=document.getElementById('coachAssignmentOut');
  if(!out)return;
  out.innerHTML='<span class="muted">Loading coach accounts and teams...</span>';
  try{
    const j=await api('/api/commish/coach-assignments');
    const coaches=j.coaches||[];
    const teams=j.teams||[];
    if(!coaches.length){
      out.innerHTML='<p class="muted">No COACH accounts exist yet. Register/promote a coach account first.</p>';
      return;
    }
    const coachOptions=coaches.map(c=>`<option value="${c.id}">${esc(c.username)}${c.franchise_name?' — '+esc(c.franchise_name):' — Unassigned'}</option>`).join('');
    const teamOptions=teams.map(t=>`<option value="${esc(t.id)}">${esc(t.name)}${t.coach_username?' — '+esc(t.coach_username):''}</option>`).join('');
    const assigned=teams.filter(t=>t.coach_username);
    out.innerHTML=`
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px">
        <label>Coach account<select id="assignCoachUser"><option value="">Choose coach...</option>${coachOptions}</select></label>
        <label>Franchise<select id="assignCoachTeam"><option value="">Choose team...</option>${teamOptions}</select></label>
      </div>
      <div class="eblSpaceTopSm">
        <button class="btn" data-ebl-action="assign-coach-team">Assign Coach</button>
        <button class="btn" data-ebl-action="unassign-coach-team">Remove Coach From Team</button>
      </div>
      <div class="muted eblSpaceTopSm">${assigned.length?assigned.map(t=>`${esc(t.coach_username)} → ${esc(t.name)}`).join('<br>'):'No teams currently have a human coach.'}</div>`;
  }catch(e){
    out.textContent='Could not load coach assignments: '+(e?.error||e?.message||'Unknown error');
  }
}

async function assignCoachToTeam(){
  const coachId=Number(document.getElementById('assignCoachUser')?.value||0);
  const fid=document.getElementById('assignCoachTeam')?.value||'';
  if(!coachId||!fid){eblAlert('Choose both a coach account and a franchise.');return}
  try{
    const j=await api('/api/commish/assign-coach',{method:'POST',body:JSON.stringify({coach_user_id:coachId,franchise_id:fid})});
    eblToast(`${j.coach_username} now controls ${j.franchise_name}. Log into that coach account and open COACH.`,'success',4800);
    await loadCoachAssignments();
  }catch(e){eblAlert(e?.error||e?.message||'Coach assignment failed')}
}

async function unassignCoachFromTeam(){
  const fid=document.getElementById('assignCoachTeam')?.value||'';
  if(!fid){eblAlert('Choose the franchise to remove the coach from.');return}
  if(!await eblConfirm('Remove the human coach from this franchise?'))return;
  try{
    await api('/api/commish/assign-coach',{method:'POST',body:JSON.stringify({coach_user_id:null,franchise_id:fid})});
    await loadCoachAssignments();
  }catch(e){eblAlert(e?.error||e?.message||'Coach removal failed')}
}

async function setSupporterTest(enabled){
 const target=String(document.getElementById('supporterTestTarget')?.value||'').trim();
 const out=document.getElementById('supporterTestOut');
 if(!target){if(out)out.textContent='Enter a username or email.';return;}
 try{
  const j=await api('/api/commish/supporter',{method:'POST',body:JSON.stringify({target,supporter:Boolean(enabled),source:'COMMISSIONER_TEST'})});
  if(out)out.innerHTML=`<b>@${escapeHtml(j.username)}</b> • ${j.entitlements?.supporter?'SUPPORTER — 3 entitled player slots':'FREE — 1 entitled player slot'}`;
  if(ME&&String(ME.username||'').toLowerCase()===String(j.username||'').toLowerCase()){await refresh();}
 }catch(e){if(out)out.textContent=e.error||'Could not update supporter entitlement.';}
}

async function resetTestAccount(){
    const target=document.getElementById('resetTestTarget').value.trim();
    const out=document.getElementById('resetTestOut');

    if(!target){
        out.textContent='Enter a username or email.';
        return;
    }

    if(!await eblConfirm(`Reset player test state for "${target}"? The login, password and verified email stay intact, but all EBL test players/career state and coach assignment for this account will be cleared.`)){
        return;
    }

    out.textContent='Resetting player state...';

    try{
        const j=await api('/api/commish/reset-test-account',{
            method:'POST',
            body:JSON.stringify({target})
        });
        const coach=j.coach_state_cleared||{};
        const coachBits=[];
        if(Number(coach.assignments||0))coachBits.push(`${Number(coach.assignments)} coach assignment(s)`);
        if(Number(coach.applications||0))coachBits.push(`${Number(coach.applications)} coach application(s)`);
        if(coach.role_reset)coachBits.push('COACH → PLAYER');
        out.textContent=`Reset complete: ${j.username} • ${j.resulting_role||j.original_role||'PLAYER'}. Removed ${j.removed_players||0} player(s) and restored ${j.restored_slots||0} roster slot(s)${coachBits.length?` • cleared ${coachBits.join(', ')}`:''}. Login preserved; Player Creator is ready.`;
        document.getElementById('resetTestTarget').value='';
        await refresh();
    }catch(e){
        out.textContent='Reset failed: '+(e.error || e.message || 'Unknown error');
    }
}


  async function repairHumanRosters(){
    if(!await eblConfirm('Repair roster slots for currently signed human players?')) return;


    const out=document.getElementById('simout');


    try{
        out.textContent='Repairing human rosters...';


        const j=await api('/api/commish/repair-human-rosters',{
            method:'POST'
        });


        out.textContent=
            'Roster repair complete — '+
            j.repaired.length+
            ' repaired, '+
            j.skipped.length+
            ' already correct/skipped';


        await refresh();


    }catch(e){
        out.textContent=
            'Repair failed: '+
            (e?.error || e?.message || 'Unknown error');
    }
  }
 async function resetLeague(){
    if(!await eblConfirm('Reset the current league back to Day 0? Season stats, standings and current-season game results will be erased. Human players/accounts remain; CPU rosters will be rebuilt to the new 18-player format.',{title:'Reset League',confirmLabel:'CONTINUE',tone:'danger'})) return;
    if(!await eblConfirm('Are you sure? This cannot be undone from the website.',{title:'Final Confirmation',confirmLabel:'RESET LEAGUE',tone:'danger'})) return;

    const out=document.getElementById('simout');
    out.textContent='Resetting league...';

    let j;
    try{
        j=await api('/api/commish/reset-league',{method:'POST'});
    }catch(e){
        out.textContent='Reset failed: '+(e?.error || e?.message || 'Unknown error');
        return;
    }

    out.textContent='League reset complete — Day '+j.day;
    try{
        await refresh();
        out.textContent='League reset complete — Day '+j.day;
    }catch(e){
        console.error('Post-reset refresh failed',e);
        out.textContent='League reset complete — Day '+j.day+' (screen refresh had an error; reload the page if needed)';
    }
} 
 
function policyPane(id,b){switchPane('.subpane',id,b)}
function openPolicy(id){
 goPage('rules');
 const tabs=[...document.querySelectorAll('#rules .subtab')];
 const target=tabs.find(b=>String(b.getAttribute('onclick')||'').includes("'"+id+"'"));
 policyPane(id,target||tabs[0]);
 document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'start'});
}

async function loadPolicies(){
 communityRules.innerHTML=`<h2>Community Rules</h2><div class="policyDate">Effective October 1, 2026</div><p>EBL is built around competitive baseball, long-term careers, and a community that can enjoy the league without harassment, cheating, scams, or impersonation.</p><div class="policySection"><h3>1. Treat people like teammates and opponents</h3><ul><li>No harassment, threats, hate speech, sexual harassment, stalking, doxxing, targeted abuse, or encouragement of violence.</li><li>No spam, scams, deceptive impersonation, phishing, or attempts to obtain another member's account credentials.</li><li>Private messages, team chat, profiles, player names, and uploaded images are subject to the same rules as public chat.</li></ul></div><div class="policySection"><h3>2. Protect competitive integrity</h3><ul><li>No exploits, automation intended to gain an unfair advantage, account sharing to bypass limits, multi-account collusion, match manipulation, or intentionally corrupting league systems.</li><li>Report bugs instead of using them for competitive benefit. EBL may reverse clearly erroneous or exploited game results, XP, contracts, transactions, or awards.</li></ul></div><div class="policySection"><h3>3. Names, images, logos, and team branding</h3><ul><li>Only upload content you created, own, are licensed to use, or otherwise have permission to use.</li><li>Personal profile images are user-provided content and do not imply EBL endorsement. EBL does not promise to pre-screen every personal upload, but may remove content after a valid complaint or moderation review.</li><li>Official EBL franchise names, logos, uniforms, and wordmarks receive higher scrutiny because they become part of the league itself. Coaches must attest that submitted franchise branding is authorized and is not intended to impersonate an existing professional, collegiate, amateur, or other third-party club.</li><li>EBL may reject or remove team identities that are confusingly similar to third-party brands, inappropriate for a general audience, misleading, or otherwise create legal or community risk.</li></ul></div><div class="policySection"><h3>4. Reports and enforcement</h3><p>Use in-service reports instead of escalating conflicts. Depending on severity and history, EBL may warn, mute, suspend, remove content, revoke coaching privileges, reverse exploit-driven benefits, or terminate an account. Serious misconduct may be acted on immediately.</p></div><div class="policyCallout"><b>Age requirement:</b> EBL is intended for users age 13 and older. Users who identify themselves as under 13 are not permitted to create an account.</div>`;
 termsPolicy.innerHTML=`<h2>Terms of Service</h2><div class="policyDate">Effective October 1, 2026</div><p>These Terms govern access to Elite Baseball League ("EBL"), including the website, game simulation, player careers, community features, coaching tools, and optional supporter or cosmetic features.</p><div class="policySection"><h3>1. Eligibility and agreement</h3><p>You must be at least 13 years old to create or use an EBL account. If you are under the age of majority where you live, use EBL and make purchases only with permission from a parent or legal guardian. By creating an account, you agree to these Terms, the Privacy Policy, and the Community Rules.</p></div><div class="policySection"><h3>2. Beta and evolving service</h3><p>During beta or stress-test periods, EBL may change rules, balance, schedules, league formats, player careers, statistics, awards, virtual progression, or other features. Beta player, season, and league progress may be reset when reasonably necessary for testing or launch preparation. EBL will try to communicate material resets in advance when practical.</p></div><div class="policySection"><h3>3. Accounts</h3><p>Provide accurate registration information, keep your password secure, and do not sell, transfer, or share access in a way that defeats account or competitive limits. You are responsible for activity performed through your account until you notify EBL of unauthorized access.</p></div><div class="policySection"><h3>4. Virtual XP, salaries, contracts, awards, and supporter features</h3><p>All XP, player salaries, signing bonuses, contracts, awards, roster rights, careers, cosmetics, supporter badges, and other in-game values are fictional game mechanics. They are not money, stored value, securities, property accounts, or promises of payment and have no cash-out value. EBL does not permit wagering on game results or conversion of game value into real-world money.</p><p>Optional supporter features and cosmetics are intended to add more EBL experiences or customization, not competitive power. Unless a future published rule expressly states otherwise, purchases do not increase attributes, XP earnings, salary advantages, roster priority, award eligibility, or simulation performance.</p></div><div class="policySection"><h3>5. Purchases and recurring Supporter subscriptions</h3><p>If paid features are enabled, price and material purchase terms will be shown before checkout. EBL Supporter may be offered as a recurring monthly or annual subscription. Unless canceled, the selected plan renews automatically at the then-disclosed billing interval. The current launch pricing is $5 per month or $54 per year, with the annual plan priced 10% below twelve monthly payments. Payment is handled by Stripe-hosted checkout. Cancel before the next renewal to stop future charges; cancellation normally leaves already-paid access active through the end of the paid billing period. Users under the age of majority may make purchases only with parent or guardian permission. Refunds, chargebacks, cancellations, and legally required remedies are handled according to the checkout terms, applicable law, and any product-specific policy presented at purchase.</p></div><div class="policySection"><h3>6. User content</h3><p>You keep the rights you hold in content you upload. You give EBL a non-exclusive, worldwide, royalty-free license to host, store, reproduce, resize, display, and transmit that content as reasonably necessary to operate, moderate, back up, and present EBL. You represent that you have the rights needed to submit the content. This license does not give EBL ownership of your original content.</p></div><div class="policySection"><h3>7. Third-party intellectual property</h3><p>Do not upload or adopt branding that infringes copyright, trademark, publicity, privacy, or other rights. EBL may remove or restrict reported content while a complaint is reviewed. Official franchise branding is subject to commissioner approval and rights attestation. Rights holders may submit copyright or trademark concerns through the Legal / Privacy Requests tab on this page.</p></div><div class="policySection"><h3>8. Moderation and service integrity</h3><p>EBL may moderate content, suspend features, freeze transactions, or restrict accounts when reasonably necessary to enforce these Terms, protect users, investigate abuse, preserve league integrity, comply with law, or protect the service. EBL may preserve relevant records for security, fraud prevention, dispute resolution, or legal obligations.</p></div><div class="policySection"><h3>9. Availability and changes</h3><p>EBL is provided on an evolving basis. No specific feature, league format, roster, statistic, award, player career, or uninterrupted availability is guaranteed. Scheduled or emergency maintenance may temporarily limit access.</p></div><div class="policySection"><h3>10. Disclaimers and limitation</h3><p>To the maximum extent permitted by applicable law, EBL is provided "as is" and "as available" without warranties that the service will be uninterrupted or error-free. To the maximum extent permitted by law, EBL and its operators are not liable for indirect, incidental, special, consequential, or punitive damages arising from use of the service. Nothing in these Terms limits rights or liability that cannot legally be limited.</p></div><div class="policySection"><h3>11. Governing law</h3><p>These Terms are governed by the laws of the State of Georgia, without regard to conflict-of-law principles, except where applicable law requires otherwise.</p></div><div class="policySection"><h3>12. Changes to these Terms</h3><p>EBL may update these Terms as the service changes. Material changes will be posted through the service, and continued use after an update takes effect constitutes acceptance where permitted by law.</p></div><div class="policyCallout"><b>Independent game:</b> Elite Baseball League is a fictional baseball simulation and is not affiliated with or endorsed by Major League Baseball or any professional or collegiate sports organization.</div>`;
 privacyPolicy.innerHTML=`<h2>Privacy Policy</h2><div class="policyDate">Effective October 1, 2026</div><p>This Policy describes information EBL collects and uses to operate accounts, the baseball simulation, community features, moderation, and optional supporter features.</p><div class="policySection"><h3>1. Age screening</h3><p>EBL is for users age 13 and older. Registration asks for a date of birth only to determine whether the age requirement is met. EBL's registration system does not store the submitted birth date in the account database after the eligibility check.</p></div><div class="policySection"><h3>2. Information collected</h3><ul><li><b>Account:</b> username, verified email address, hashed password, account role, verification and recovery status.</li><li><b>Security and technical:</b> session identifiers, login timestamps, IP address, user agent/device information, rate-limit and security records.</li><li><b>Game and profile:</b> player identities, appearance choices, attributes, statistics, contracts, team affiliation, awards, public profile fields, optional profile images, coaching activity, and league history.</li><li><b>Community:</b> public/team chat, private messages, friend activity, blocks, moderation reports, and beta feedback.</li><li><b>Legal/privacy requests:</b> the contact information and details you choose to submit through the Legal / Privacy Requests form.</li><li><b>Supporter/payment status:</b> if paid features are enabled, EBL may receive transaction or entitlement status from a hosted payment provider. Full payment-card details are intended to remain with the payment provider rather than EBL.</li></ul></div><div class="policySection"><h3>3. How information is used</h3><p>EBL uses information to authenticate accounts, verify email, recover passwords, run games and seasons, save player and team history, deliver community features, prevent abuse, enforce rules, respond to reports and requests, maintain security, diagnose errors, back up the service, and administer optional supporter features.</p></div><div class="policySection"><h3>4. Sharing and service providers</h3><p>Information may be processed by service providers needed to host EBL, send account email, store backups, provide payment checkout, or operate other infrastructure. EBL may also disclose information when reasonably necessary to comply with law, protect rights or safety, investigate fraud or abuse, or respond to valid legal process. EBL does not sell personal information for money or use personal information for cross-context behavioral advertising.</p></div><div class="policySection"><h3>5. Public information</h3><p>Player names, statistics, team affiliation, league history, awards, profile fields you make public, and some uploaded profile/team imagery may be visible to other users or the public. Do not place private information in player names, bios, chat, team branding, or other public fields.</p></div><div class="policySection"><h3>6. Retention</h3><p>Different records are kept for different periods. Some live chat is automatically pruned on a short rolling basis, while league history, statistics, security records, reports, account records, direct messages, backups, and transaction/audit records may be retained longer when needed to operate EBL, preserve league history, prevent abuse, resolve disputes, or meet legal obligations. When information is no longer reasonably needed, EBL may delete or de-identify it.</p></div><div class="policySection"><h3>7. Security</h3><p>EBL uses measures such as password hashing, email verification, session controls, rate limiting, backups, and moderation/security logs. No online system can guarantee absolute security, so users should use a unique password and promptly report suspected account compromise.</p></div><div class="policySection"><h3>8. Your requests</h3><p>You may request help with account information, correction, deletion, privacy questions, or intellectual-property complaints through the Legal / Privacy Requests tab. Some records may need to be retained where permitted or required for fraud prevention, league integrity, transaction records, backups, dispute resolution, or law.</p></div><div class="policySection"><h3>9. Third-party services</h3><p>Optional links such as Discord, Instagram, payment providers, or other external services are governed by those services' own terms and privacy practices. EBL is not responsible for their independent data practices.</p></div><div class="policySection"><h3>10. Changes</h3><p>EBL may update this Privacy Policy when the service or its data practices change. Material updates will be posted through the service.</p></div>`;
 legalRequestsPolicy.innerHTML=`<h2>Legal & Privacy Requests</h2><div class="policyDate">Public request channel</div><p>Use this form for account/privacy requests or to report copyright, trademark, impersonation, or other rights concerns. You do not need to be signed in.</p><div class="policyCallout"><b>Copyright reports:</b> identify the copyrighted work, identify where the challenged material appears in EBL, provide your contact information, explain your good-faith belief that the use is unauthorized, confirm that the information is accurate and that you are the owner or authorized to act for the owner, and type your name as an electronic signature.</div><div class="legalRequestGrid"><label>Request Type<select id="legalRequestKind"><option value="PRIVACY">Privacy / Account Data</option><option value="COPYRIGHT">Copyright</option><option value="TRADEMARK">Trademark / Brand</option><option value="ACCOUNT">Account Access / Deletion</option><option value="OTHER">Other Legal Request</option></select></label><label>Your Name<input id="legalRequestName" maxlength="100" autocomplete="name" placeholder="name"></label><label>Email<input id="legalRequestEmail" maxlength="254" type="email" autocomplete="email" placeholder="contact email"></label><label>Content URL or Location<input id="legalRequestUrl" maxlength="500" placeholder="optional link, profile, team, or page"></label><label class="wide">Subject<input id="legalRequestSubject" maxlength="160" placeholder="brief subject"></label><label class="wide">Details<textarea id="legalRequestDetail" maxlength="4000" placeholder="Describe the request and include enough information for EBL to locate and review the issue."></textarea></label></div><button class="btn" data-ebl-action="submit-legal-request">Submit Request</button><div id="legalRequestMsg" class="muted eblSpaceTopXs"></div><p class="legalRequestNote">Submitting this form does not guarantee a particular outcome. EBL may ask for additional information needed to verify identity, authority, ownership, or the location of reported material.</p>`;
}

async function submitLegalRequest(){
 const msg=document.getElementById('legalRequestMsg');
 const body={
  kind:String(document.getElementById('legalRequestKind')?.value||'OTHER'),
  name:String(document.getElementById('legalRequestName')?.value||'').trim(),
  email:String(document.getElementById('legalRequestEmail')?.value||'').trim(),
  content_url:String(document.getElementById('legalRequestUrl')?.value||'').trim(),
  subject:String(document.getElementById('legalRequestSubject')?.value||'').trim(),
  detail:String(document.getElementById('legalRequestDetail')?.value||'').trim()
 };
 if(!body.name||!body.email||body.detail.length<20){if(msg)msg.textContent='Enter your name, a valid contact email, and at least 20 characters of detail.';return}
 try{
  const j=await api('/api/legal/request',{method:'POST',body:JSON.stringify(body)});
  if(msg)msg.innerHTML=`<b>Request received.</b> Reference #${Number(j.request_id||0)}. Keep this number for your records.`;
  ['legalRequestName','legalRequestEmail','legalRequestUrl','legalRequestSubject','legalRequestDetail'].forEach(id=>{const el=document.getElementById(id);if(el)el.value=''});
 }catch(e){if(msg)msg.textContent=e?.detail||e?.error||e?.message||'Request could not be submitted.'}
}
async function loadLegalRequests(){
 const out=document.getElementById('legalRequestQueue');if(!out||ME?.role!=='COMMISSIONER')return;
 try{
  const j=await api('/api/commish/legal-requests');const rows=j.requests||[];
  out.innerHTML=rows.length?rows.map(r=>`<div class="offer"><b>#${Number(r.id)} ${escapeHtml(r.kind||'OTHER')} • ${escapeHtml(r.subject||'No subject')}</b> <span class="newsBadge">${escapeHtml(r.status||'OPEN')}</span><div class="muted">${escapeHtml(r.name||'')} • ${escapeHtml(r.email||'')} • ${escapeHtml(r.created_at||'')}</div>${r.content_url?`<div class="muted">Location: ${escapeHtml(r.content_url)}</div>`:''}<p>${escapeHtml(r.detail||'')}</p>${r.status==='OPEN'?`<button class="btn" data-ebl-action="resolve-legal-request" data-request="${Number(r.id)}">Mark Resolved</button>`:''}</div>`).join(''):'<p class="muted">No legal/privacy requests yet.</p>';
 }catch(e){out.innerHTML=`<p class="muted">Could not load requests: ${escapeHtml(e?.error||e?.message||'Unknown error')}</p>`}
}
async function resolveLegalRequest(id){
 const resolution=await eblPrompt('Resolution / internal note:','Reviewed and resolved');if(resolution===null)return;
 try{await api('/api/commish/resolve-legal-request',{method:'POST',body:JSON.stringify({request_id:id,resolution})});await loadLegalRequests()}catch(e){eblAlert(e?.error||e?.message||'Could not resolve request')}
}

function openBetaFeedback(type='BUG'){
 const modal=document.getElementById('betaFeedbackModal');if(!modal)return;
 const sel=document.getElementById('betaFeedbackType');if(sel&&['BUG','FEEDBACK','IDEA'].includes(type))sel.value=type;
 const msg=document.getElementById('betaFeedbackMsg');if(msg)msg.textContent='';
 if(!modal.open)modal.showModal();
}
function currentBetaFeedbackPage(){const active=document.querySelector('.page.active');return `${location.pathname}${location.search||''}${active?.id?` • ${active.id}`:''}`.slice(0,240)}
async function submitBetaFeedback(){
 const detail=document.getElementById('betaFeedbackDetail')?.value.trim()||'';const msg=document.getElementById('betaFeedbackMsg');
 if(detail.length<3){if(msg)msg.textContent='Tell us a little more about what happened.';return}
 try{const j=await api('/api/beta/feedback',{method:'POST',body:JSON.stringify({category:document.getElementById('betaFeedbackType')?.value||'FEEDBACK',detail,page:currentBetaFeedbackPage()})});if(msg)msg.innerHTML='<div class="betaFeedbackThanks"><b>Thank you.</b> Your beta feedback was sent.</div>';document.getElementById('betaFeedbackDetail').value='';setTimeout(()=>document.getElementById('betaFeedbackModal')?.close(),900)}catch(e){if(msg)msg.textContent=e?.error||e?.message||'Feedback could not be sent.'}
}
async function loadBetaFeedback(){
 const out=document.getElementById('betaFeedbackQueue');if(!out||ME?.role!=='COMMISSIONER')return;
 try{const j=await api('/api/commish/beta-feedback');const rows=j.feedback||[];out.innerHTML=rows.length?rows.map(r=>`<div class="offer"><b>#${Number(r.id)} ${escapeHtml(r.category||'FEEDBACK')}</b> <span class="newsBadge">${escapeHtml(r.status||'OPEN')}</span><div class="muted">${escapeHtml(r.username||'Unknown user')} • ${escapeHtml(r.page||'Unknown page')} • ${escapeHtml(r.created_at||'')}</div><p>${escapeHtml(r.detail||'')}</p>${r.status==='OPEN'?`<button class="btn" data-ebl-action="review-beta-feedback" data-feedback="${Number(r.id)}">Mark Reviewed</button>`:''}</div>`).join(''):'<p class="muted">No beta feedback yet.</p>'}catch(e){out.innerHTML=`<p class="muted">Could not load beta feedback: ${escapeHtml(e?.error||e?.message||'Unknown error')}</p>`}
}
async function reviewBetaFeedback(id){try{await api('/api/commish/resolve-beta-feedback',{method:'POST',body:JSON.stringify({feedback_id:id})});await loadBetaFeedback()}catch(e){eblAlert(e?.error||e?.message||'Could not update feedback')}}

async function loadReports(){
 try{let j=await api('/api/commish/reports');reportQueue.innerHTML=j.reports.length?j.reports.map(r=>`<div class="offer"><b>#${r.id} ${r.reason}</b> • ${r.status}<br><span class="muted">${r.reporter} reported ${r.reported||'content'} • ${r.created_at}</span><br>${escapeHtml(r.detail||'')} ${r.status==='OPEN'?`<br><button class="btn" data-ebl-action="moderate-user" data-user="${r.reported_user_id}" data-moderation="MUTE">Mute 24h</button> <button class="btn" data-ebl-action="moderate-user" data-user="${r.reported_user_id}" data-moderation="SUSPEND">Suspend 24h</button> <button class="btn" data-ebl-action="resolve-report" data-report="${r.id}">Resolve</button>`:''}</div>`).join(''):'<p class="muted">No reports.</p>'}catch(e){eblAlert(e.error)}
}
async function moderateUser(uid,action){if(!uid)return;let reason=await eblPrompt('Reason:',action);if(reason===null)return;try{await api('/api/commish/moderate',{method:'POST',body:JSON.stringify({user_id:uid,action,minutes:1440,reason})});await loadReports()}catch(e){eblAlert(e.error)}}
async function resolveReport(id){let resolution=await eblPrompt('Resolution:','Reviewed');if(resolution===null)return;await api('/api/commish/resolve-report',{method:'POST',body:JSON.stringify({report_id:id,resolution})});loadReports()}
async function backupNow(){try{let j=await api('/api/commish/backup-now',{method:'POST'});eblToast('Backup created: '+j.path,'success',4200)}catch(e){eblAlert(e.error)}}
function fmtBytes(n){
  n=Number(n||0);if(!n)return '0 B';
  const u=['B','KB','MB','GB'];let i=0;
  while(n>=1024&&i<u.length-1){n/=1024;i++}
  return n.toFixed(i?1:0)+' '+u[i];
}
async function loadStorageStatus(){
  const out=document.getElementById('storageOut');
  out.textContent='Checking storage...';
  try{
    const j=await api('/api/commish/storage-status');const x=j.storage||{};
    out.innerHTML=`DB <b>${fmtBytes(x.db_bytes)}</b> • WAL ${fmtBytes(x.wal_bytes)} • Backups ${fmtBytes(x.backup_bytes)} (${x.backup_count||0}) • Free <b>${fmtBytes(x.free_bytes)}</b><br><span class="muted">Game events ${fmtBytes(x.events_bytes)} • Box scores ${fmtBytes(x.box_bytes)} • ${x.final_games||0} final games</span>`;
  }catch(e){out.textContent='Storage check failed: '+(e?.error||e?.message||'Unknown error')}
}
async function optimizeStorage(){
  if(!await eblConfirm('Optimize EBL storage now? This removes old backup copies and turns old-season GameCast into compact text summaries, compresses older current-season play-by-play, and preserves scores, box scores, stats, standings, and recent full GameCast data.',{title:'Optimize Storage',confirmLabel:'OPTIMIZE',tone:'warn'}))return;
  const out=document.getElementById('storageOut');out.textContent='Optimizing storage...';
  try{
    const j=await api('/api/commish/optimize-storage',{method:'POST'});const x=j.storage||{};
    out.innerHTML=`Optimization complete • ${j.compacted_games||0} games compacted • ${j.removed_backups||0} old backups removed<br>DB <b>${fmtBytes(x.db_bytes)}</b> • WAL ${fmtBytes(x.wal_bytes)} • Free <b>${fmtBytes(x.free_bytes)}</b>`;
  }catch(e){out.textContent='Storage optimization failed: '+(e?.error||e?.message||'Unknown error')}
}
let EBL_SIM_LAB=null;
function simLabAttrLine(p){
  const a=p?.attributes||{};
  const keys=p?.type==='P'?['CTRL','CMD','VEL','BRK','MOV','DEC','SEQ','STA']:['CON','POW','VIS','DISC','TIM','SPD'];
  return keys.map(k=>`${k} ${Number(a[k]||0)}`).join(' • ');
}
function simLabPlayerCheck(p,kind,checked){
  return `<label style="display:block;padding:10px 12px;margin:7px 0;border:1px solid #27445f;border-radius:12px;background:#081b2b;cursor:pointer">
    <input type="checkbox" data-lab-${kind} value="${Number(p.id)}" ${checked?'checked':''} style="margin-right:8px;transform:scale(1.15)">
    <b>${escapeHtml(p.name||'Player')}</b> <span class="muted">${escapeHtml(p.primary_pos||'')} • ${escapeHtml(p.team_name||'Free Agent')}${p.human?' • HUMAN':' • CPU'}</span>
    <div class="muted" style="font-size:.78rem;margin:4px 0 0 25px">${escapeHtml(simLabAttrLine(p))}</div>
  </label>`;
}
async function loadLab(){
  const j=await api('/api/simulation-lab');
  EBL_SIM_LAB=j;
  const hitters=(j.players||[]).filter(p=>p.type==='H');
  const pitchers=(j.players||[]).filter(p=>p.type==='P');
  let hc=0,pc=0;
  const hitterHtml=hitters.map(p=>simLabPlayerCheck(p,'hitter',!!p.human&&hc++<10)).join('');
  const pitcherHtml=pitchers.map(p=>simLabPlayerCheck(p,'pitcher',!!p.human&&pc++<8)).join('');
  const baseline=Object.keys(j.baseline||{}).length?`<div class="grid eblSpaceTopSm">${Object.entries(j.baseline).map(([k,v])=>statBox(k,typeof v==='number'?v.toFixed(3):v)).join('')}</div>`:'';
  labBody.innerHTML=`
    <div class="offer eblSpaceTopLg">
      <h2 style="margin-top:0">Build vs. Build Simulation Lab</h2>
      <p class="muted">Runs the current EBL pitch/contact equations head-to-head. Fatigue, leverage, park effects, baserunning and defensive errors are removed so we can see what the builds themselves are doing.</p>
      ${baseline}
      <div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:12px">
        <div><h3>Hitters</h3><div class="muted">Human builds are selected first. Pick up to 10.</div><div style="max-height:390px;overflow:auto;padding-right:4px">${hitterHtml||'<p class="muted">No active hitters.</p>'}</div></div>
        <div><h3>Pitchers</h3><div class="muted">Pick up to 8. SP/RP labels do not change the isolated test.</div><div style="max-height:390px;overflow:auto;padding-right:4px">${pitcherHtml||'<p class="muted">No active pitchers.</p>'}</div></div>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:10px;align-items:end;margin-top:14px">
        <label style="min-width:155px">PA per matchup
          <select id="simLabPa" style="width:100%"><option value="500">500</option><option value="1000" selected>1,000</option><option value="2000">2,000</option><option value="5000">5,000</option></select>
        </label>
        <button class="btn" data-ebl-action="sim-lab-select-humans">Select Human Builds</button>
        <button class="btn" data-ebl-action="run-build-vs-build">Run Build vs. Build</button>
      </div>
      <div id="simLabStatus" class="muted eblSpaceTopSm">Seed ${Number(j.seed||7500831).toLocaleString()} • ${escapeHtml(j.engine||'EBL engine')}</div>
      <div id="simLabResults" class="eblSpaceTopMd"></div>
    </div>`;
}
function simLabSelectHumans(){
  if(!EBL_SIM_LAB)return;
  const humanIds=new Set((EBL_SIM_LAB.players||[]).filter(p=>p.human).map(p=>Number(p.id)));
  document.querySelectorAll('[data-lab-hitter],[data-lab-pitcher]').forEach(el=>{el.checked=humanIds.has(Number(el.value))});
}
function simLabPct(v){return `${(Number(v||0)*100).toFixed(1)}%`}
async function runBuildVsBuild(){
  const hitter_ids=[...document.querySelectorAll('[data-lab-hitter]:checked')].map(x=>Number(x.value));
  const pitcher_ids=[...document.querySelectorAll('[data-lab-pitcher]:checked')].map(x=>Number(x.value));
  const pa_per_test=Number(document.getElementById('simLabPa')?.value||1000);
  const status=document.getElementById('simLabStatus'),out=document.getElementById('simLabResults');
  if(!hitter_ids.length||!pitcher_ids.length){status.textContent='Select at least one hitter and one pitcher.';return}
  if(hitter_ids.length>10||pitcher_ids.length>8){status.textContent='Limit this test to 10 hitters and 8 pitchers.';return}
  status.textContent=`Running ${hitter_ids.length*pitcher_ids.length} matchups × ${pa_per_test.toLocaleString()} PA...`;
  out.innerHTML='';
  try{
    const j=await api('/api/simulation-lab/matchups',{method:'POST',body:JSON.stringify({hitter_ids,pitcher_ids,pa_per_test,seed:Number(EBL_SIM_LAB?.seed||7500831)})});
    status.textContent=`Complete • ${j.matchups.length} matchups • ${Number(j.pa_per_test).toLocaleString()} PA each • neutral context`;
    const rows=(j.matchups||[]).map(m=>{
      const x=m.stats||{};
      const h=m.hitter||{},p=m.pitcher||{};
      return `<tr>
        <td style="min-width:145px"><b>${escapeHtml(h.name||'')}</b><div class="muted" style="font-size:.72rem">${escapeHtml(h.team_name||'')}</div></td>
        <td style="min-width:145px"><b>${escapeHtml(p.name||'')}</b><div class="muted" style="font-size:.72rem">${escapeHtml(p.team_name||'')}</div></td>
        <td>${Number(x.avg||0).toFixed(3)}</td><td>${Number(x.obp||0).toFixed(3)}</td><td>${Number(x.slg||0).toFixed(3)}</td><td><b>${Number(x.ops||0).toFixed(3)}</b></td>
        <td>${simLabPct(x.bb_pct)}</td><td>${simLabPct(x.k_pct)}</td><td>${simLabPct(x.hr_pct)}</td><td>${Number(x.avg_ev||0).toFixed(1)}</td><td>${simLabPct(x.barrel_pct)}</td>
      </tr>`;
    }).join('');
    out.innerHTML=`<div style="overflow-x:auto"><table style="min-width:980px;width:100%"><thead><tr><th>HITTER</th><th>PITCHER</th><th>AVG</th><th>OBP</th><th>SLG</th><th>OPS</th><th>BB%</th><th>K%</th><th>HR%</th><th>EV</th><th>BARREL%</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="muted eblSpaceTopSm">This isolates hitter/pitcher attributes. It intentionally does not include fatigue, catcher CALL, fielding, team upgrades, park effects, steals, or game situation.</p>`;
  }catch(e){status.textContent='Simulation Lab failed: '+(e?.error||e?.message||'Unknown error')}
}
async function hydrateGamecastAppearance(game){
    // Box-score rows are historical stat snapshots and may not carry the full
    // appearance payload. Pull the two current team rosters and merge only
    // identity/appearance fields so GameCast uses the same saved player look
    // as Home, Player HQ and team profiles.
    const ids=[game?.away_id,game?.home_id].filter(Boolean);
    if(!ids.length)return game;
    try{
        const results=await Promise.all(ids.map(fid=>api('/api/team/'+encodeURIComponent(fid)).catch(()=>null)));
        const byId=new Map();
        results.forEach(j=>(j?.roster||[]).forEach(p=>byId.set(Number(p.id),p)));
        const appearanceKeys=['name','primary_pos','jersey_number','face_id','skin_color_id','hair_id','hair_color_id','facial_hair_id','eye_color_id','nose_id','eye_shape_id','mouth_id','ear_size_id','eye_black_id','eyewear_id','chain_id','sleeve_id','body_build_id','bats','throws','franchise_id','type','username'];
        const mergeRow=row=>{
            const live=byId.get(Number(row?.player_id));
            if(!live)return row;
            const out={...row};
            appearanceKeys.forEach(k=>{if(live[k]!==undefined&&live[k]!==null)out[k]=live[k]});
            return out;
        };
        if(game?.box){
            game.box.hitter_rows=(game.box.hitter_rows||[]).map(mergeRow);
            game.box.pitcher_rows=(game.box.pitcher_rows||[]).map(mergeRow);
        }
    }catch(e){console.warn('GameCast appearance hydration skipped',e)}
    return game;
}
async function watch(id){
    let j=await api('/api/game/'+id);
    GG=await hydrateGamecastAppearance(j.game);
    gi=0;
    clearInterval(timer);
    renderGameShell();
    document.getElementById('gc').showModal();
}


function renderGameShell(){
    document.getElementById('gcontent').innerHTML=`
        <div class="gold">Day ${GG.league_day} • FINAL</div>
        <div class="gcFranchiseHeader">
          <div class="gcFranchiseSide">${teamMark(GG.away_id)}<div><b>${GG.away_name || teamName(GG.away_id)}</b><strong>${GG.away_runs}</strong></div></div>
          <span class="gcFinal">FINAL</span>
          <div class="gcFranchiseSide home"><div><b>${GG.home_name || teamName(GG.home_id)}</b><strong>${GG.home_runs}</strong></div>${teamMark(GG.home_id)}</div>
        </div>


        <div class="subtabs">
            <button class="subtab active" data-ebl-action="game-tab" data-tab="BOX">BOX SCORE</button>
            <button class="subtab" data-ebl-action="game-tab" data-tab="CAST">GAMECAST</button>
            <button class="subtab" data-ebl-action="game-tab" data-tab="PBP">PLAY-BY-PLAY</button>
        </div>


        <div id="gameView"></div>
    `;


    renderBoxScore();
}


function gameTab(mode,b){
    clearInterval(timer);


    b.parentElement.querySelectorAll('.subtab')
        .forEach(x=>x.classList.remove('active'));


    b.classList.add('active');


    if(mode==='BOX')renderBoxScore();
    if(mode==='CAST')renderGamecast();
    if(mode==='PBP')renderFullPlayByPlay();
}


function ipFmt(outs){
    outs=Number(outs||0);
    return `${Math.floor(outs/3)}.${outs%3}`;
}


function renderBoxScore(){
    const away=GG.away_name || teamName(GG.away_id);
    const home=GG.home_name || teamName(GG.home_id);


    const aLine=GG.line_score?.away || {};
    const hLine=GG.line_score?.home || {};


    const at=GG.totals?.away || {R:GG.away_runs,H:0,E:0};
    const ht=GG.totals?.home || {R:GG.home_runs,H:0,E:0};


    let innings='';
    for(let i=1;i<=9;i++){
        innings+=`<th>${i}</th>`;
    }


    let awayInn='';
    let homeInn='';


    for(let i=1;i<=9;i++){
        awayInn+=`<td>${aLine[String(i)] ?? 0}</td>`;
        homeInn+=`<td>${hLine[String(i)] ?? 0}</td>`;
    }


    const hitters=GG.box?.hitter_rows || [];
    const pitchers=GG.box?.pitcher_rows || [];
    const fielders=GG.box?.fielding_rows || [];


    function batting(teamId){
        const rows=hitters.filter(x=>x.team_id===teamId);


        return `
            <div class="tablewrap">
                <table>
                    <tr>
                        <th>PLAYER</th>
                        <th>AB</th>
                        <th>R</th>
                        <th>H</th>
                        <th>2B</th>
                        <th>HR</th>
                        <th>RBI</th>
                        <th>BB</th>
                        <th>SO</th>
                        <th>SB</th>
                    </tr>
                    ${rows.map(p=>`
                        <tr>
                            <td><button class="clickableName" data-ebl-action="open-game-player" data-player="${p.player_id}" data-team="${teamId}">#${Number(p.jersey_number??24)} ${p.name}</button></td>
                            <td>${p.AB||0}</td>
                            <td>${p.R||0}</td>
                            <td>${p.H||0}</td>
                            <td>${p["2B"]||0}</td>
                            <td>${p.HR||0}</td>
                            <td>${p.RBI||0}</td>
                            <td>${p.BB||0}</td>
                            <td>${p.SO||0}</td>
                            <td>${p.SB||0}</td>
                        </tr>
                    `).join('')}
                </table>
            </div>
        `;
    }


    function pitching(teamId){
        const rows=pitchers.filter(x=>x.team_id===teamId);


        return `
            <div class="tablewrap">
                <table>
                    <tr>
                        <th>PITCHER</th>
                        <th>IP</th>
                        <th>H</th>
                        <th>ER</th>
                        <th>BB</th>
                        <th>SO</th>
                        <th>W</th>
                        <th>L</th>
                        <th>SV</th>
                    </tr>
                    ${rows.map(p=>`
                        <tr>
                            <td><button class="clickableName" data-ebl-action="open-game-player" data-player="${p.player_id}" data-team="${teamId}">#${Number(p.jersey_number??24)} ${p.name}</button></td>
                            <td>${ipFmt(p.OUTS)}</td>
                            <td>${p.H||0}</td>
                            <td>${p.ER||0}</td>
                            <td>${p.BB||0}</td>
                            <td>${p.SO||0}</td>
                            <td>${p.W||0}</td>
                            <td>${p.L||0}</td>
                            <td>${p.SV||0}</td>
                        </tr>
                    `).join('')}
                </table>
            </div>
        `;
    }


    function fielding(teamId){
        const rows=fielders.filter(x=>x.team_id===teamId);
        if(!rows.length)return `<div class="card"><span class="muted">No fielding detail was stored for this game.</span></div>`;
        return `
            <div class="tablewrap">
                <table>
                    <tr>
                        <th>FIELDER</th>
                        <th>POS</th>
                        <th>PO</th>
                        <th>A</th>
                        <th>E</th>
                        <th>DP</th>
                        <th>FLD%</th>
                    </tr>
                    ${rows.map(f=>`
                        <tr>
                            <td><button class="clickableName" data-ebl-action="open-game-player" data-player="${f.player_id}" data-team="${teamId}">#${Number(f.jersey_number??24)} ${escapeHtml(f.name||'Player')}</button></td>
                            <td>${escapeHtml(String(f.position||''))}</td>
                            <td>${Number(f.PO||0)}</td>
                            <td>${Number(f.A||0)}</td>
                            <td>${Number(f.E||0)}</td>
                            <td>${Number(f.DP||0)}</td>
                            <td>${escapeHtml(String(f.FLD_PCT||'1.000'))}</td>
                        </tr>
                    `).join('')}
                </table>
            </div>
        `;
    }


    document.getElementById('gameView').innerHTML=`
        <h3>Line Score</h3>


        <div class="tablewrap">
            <table>
                <tr>
                    <th>TEAM</th>
                    ${innings}
                    <th>R</th>
                    <th>H</th>
                    <th>E</th>
                </tr>


                <tr>
                    <td><b>${away}</b></td>
                    ${awayInn}
                    <td><b>${at.R}</b></td>
                    <td>${at.H}</td>
                    <td>${at.E}</td>
                </tr>


                <tr>
                    <td><b>${home}</b></td>
                    ${homeInn}
                    <td><b>${ht.R}</b></td>
                    <td>${ht.H}</td>
                    <td>${ht.E}</td>
                </tr>
            </table>
        </div>


        <h3 class="eblSpaceTopLg">${away} Batting</h3>
        ${batting(GG.away_id)}


        <h3 class="eblSpaceTopLg">${home} Batting</h3>
        ${batting(GG.home_id)}


        <h3 class="eblSpaceTopLg">${away} Pitching</h3>
        ${pitching(GG.away_id)}


        <h3 class="eblSpaceTopLg">${home} Pitching</h3>
        ${pitching(GG.home_id)}

        <h3 class="eblSpaceTopLg">${away} Fielding</h3>
        ${fielding(GG.away_id)}

        <h3 class="eblSpaceTopLg">${home} Fielding</h3>
        ${fielding(GG.home_id)}
    `;
}


async function openGamePlayer(playerId,teamId){
  try{
    const j=await api('/api/team/'+encodeURIComponent(teamId));
    TEAM_ROSTER=j.roster||[];
    const p=TEAM_ROSTER.find(x=>Number(x.id)===Number(playerId));
    if(p?.username){await openUserProfile(p.username);return;}
    if(p){openPlayerCard(playerId);return;}
  }catch(e){}
  eblAlert('Player profile is not available.');
}
function gamecastPlayerById(pid){
 const rows=[...(GG?.box?.hitter_rows||[]),...(GG?.box?.pitcher_rows||[]),...(GG?.box?.fielding_rows||[])];
 return rows.find(x=>Number(x.player_id)===Number(pid))||null;
}
function gamecastMatchupCard(p,label){
 if(!p)return `<div class="card eblTextCenter"><span class="muted">${label}</span><div>Waiting for matchup…</div></div>`;
 const portrait=playerPortraitMarkup(p,String(label||'').toLowerCase().includes('pitch')?'pitching':'batting');
 return `<div class="card" style="padding:10px;text-align:center;min-width:0"><span class="newsMeta">${label}</span><div style="display:flex;align-items:center;justify-content:center;gap:10px;margin-top:6px">${portrait}<div><b style="font-size:18px">#${Number(p.jersey_number??24)} ${escapeHtml(p.name||'Player')}</b><div class="muted">${escapeHtml(p.primary_pos||'')}</div></div></div></div>`;
}
let GC_STATE={score:[0,0],inning:1,half:'TOP',balls:0,strikes:0,outs:0,runner:null,base:0};
function gcTeamInfo(fid){const t=(LEAGUE?.teams||[]).find(x=>x.id===fid)||{};return {name:t.display_name||t.name||fid,mark:teamMark(fid,true)}}
function gamecastLineupStrip(fid,label){
 const rows=(GG?.box?.hitter_rows||[]).filter(x=>x.team_id===fid);
 return `<div class="gcLineup"><div class="gcLineupTitle"><b>${label}</b><span class="muted">BATTING ORDER</span></div><div class="gcLineupRow">${rows.slice(0,9).map((p,i)=>`<div class="gcLineupChip" data-gc-player="${Number(p.player_id)}"><span class="gold">${i+1}</span> <b>#${Number(p.jersey_number??24)} ${escapeHtml(p.name||'Player')}</b><span class="muted">${escapeHtml(p.primary_pos||'')}</span></div>`).join('')}</div></div>`;
}
function gcScoreboardMarkup(){
 const a=gcTeamInfo(GG.away_id),h=gcTeamInfo(GG.home_id);
 return `<div class="gcScoreboard"><div class="gcTeam">${a.mark}<div><div class="gcTeamName">${escapeHtml(a.name)}</div><div id="gcAwayScore" class="gcScore">0</div></div></div><div class="gcState"><div id="gcInning" class="gcInning">TOP 1</div><div id="gcCount" class="gcCount">0-0 • 0 OUT</div><div class="gcBases"><span id="gcB3" class="gcBase b3"></span><span id="gcB2" class="gcBase b2"></span><span id="gcB1" class="gcBase b1"></span></div></div><div class="gcTeam home"><div><div class="gcTeamName">${escapeHtml(h.name)}</div><div id="gcHomeScore" class="gcScore">0</div></div>${h.mark}</div></div>`;
}
function gcUpdateScoreboard(){
 const a=document.getElementById('gcAwayScore'),h=document.getElementById('gcHomeScore'),inn=document.getElementById('gcInning'),cnt=document.getElementById('gcCount');
 if(a)a.textContent=GC_STATE.score[0]??0;if(h)h.textContent=GC_STATE.score[1]??0;if(inn)inn.textContent=`${GC_STATE.half==='BOT'?'BOT':'TOP'} ${GC_STATE.inning}`;if(cnt)cnt.textContent=`${GC_STATE.balls}-${GC_STATE.strikes} • ${GC_STATE.outs} OUT${GC_STATE.outs===1?'':'S'}`;
 ['1','2','3'].forEach(n=>{const b=document.getElementById('gcB'+n);if(b)b.classList.toggle('on',Number(n)===Number(GC_STATE.base)&&!!GC_STATE.runner)});
 const runner=document.getElementById('gcRunner');if(runner){runner.className='gcFieldRunner'+(GC_STATE.runner?` show r${Math.max(1,Math.min(3,GC_STATE.base||1))}`:'');runner.textContent=GC_STATE.runner?`#${gamecastPlayerById(GC_STATE.runner)?.jersey_number??''}`:'';}
}
function gcHighlightBatter(pid){document.querySelectorAll('.gcLineupChip').forEach(el=>el.classList.toggle('active',Number(el.dataset.gcPlayer)===Number(pid)))}
function gcFlash(text,kind=''){const el=document.getElementById('gcFlash');if(!el)return;el.innerHTML=`<div class="gcFlashCard ${kind}">${text}</div>`;clearTimeout(window.__gcFlashTimer);window.__gcFlashTimer=setTimeout(()=>{if(el)el.innerHTML=''},2600)}
function gcBanner(text,big=false){const el=document.getElementById('gcResult');if(!el)return;el.textContent=text;el.className='gcResultBanner show'+(big?' big':'');clearTimeout(window.__gcBannerTimer);window.__gcBannerTimer=setTimeout(()=>{if(el)el.className='gcResultBanner'},1500)}
function renderGamecast(){
    gi=0;
    GC_STATE={score:[0,0],inning:1,half:'TOP',balls:0,strikes:0,outs:0,runner:null,base:0};
    document.getElementById('gameView').innerHTML=`
        <div class="gcBroadcast">
          ${gcScoreboardMarkup()}
          <div class="gcLineups">${gamecastLineupStrip(GG.away_id,teamName(GG.away_id))}${gamecastLineupStrip(GG.home_id,teamName(GG.home_id))}</div>
          <div id="gcStrategyLive" class="gcStrategyLive"><span>MANAGER DECISIONS</span><b>Game plan loaded</b></div>
          <div id="gcFlash" class="gcFlash"></div>
        </div>
        <div class="gcgrid">
            <div class="field">
                <div class="dirt"></div><div class="grass"></div><div id="ball" class="ball"></div>
                <div id="gcRunner" class="gcFieldRunner"></div><div id="gcResult" class="gcResultBanner"></div>
            </div>
            <div>
                <div id="gcMatchup" style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">${gamecastMatchupCard(null,'AT BAT')}${gamecastMatchupCard(null,'ON THE MOUND')}</div>
                <div class="card"><h3 id="match">GameCast</h3><div id="pt" class="muted"></div><div id="zone" class="zone"></div><div id="metric" class="gold"></div></div>
                <button class="btn" data-ebl-action="gamecast-speed" data-speed="1600">Live</button><button class="btn" data-ebl-action="gamecast-speed" data-speed="300">Fast</button><button class="btn" data-ebl-action="gamecast-instant">Instant</button><button class="btn" data-ebl-action="gamecast-replay">Replay</button>
            </div>
        </div>
        <div class="card"><h3>Play-by-Play</h3><div id="feed" class="feed"></div></div>
    `;
    gcUpdateScoreboard();
    clearInterval(timer);timer=setInterval(step,450);
}


function renderFullPlayByPlay(){
    const plays=(GG.events || [])
        .map(e=>`<div class="play${gcStrategyClass(e)}">${escapeHtml(describe(e))}</div>`)
        .reverse()
        .join('');


    document.getElementById('gameView').innerHTML=`
        <div class="card">
            <h3>Complete Play-by-Play</h3>
            <div class="feed">${plays}</div>
        </div>
    `;
}


function speed(ms){
    clearInterval(timer);
    timer=setInterval(step,ms);
}


function replay(){
    clearInterval(timer);
    renderGamecast();
}


function instant(){
    clearInterval(timer);
    while(gi<GG.events.length)step();
}
function step(){
 if(gi>=GG.events.length){clearInterval(timer);return}
 const e=GG.events[gi++],d=document.createElement('div');d.className='play'+gcStrategyClass(e);d.textContent=describe(e);feed.prepend(d);
 if(e.score)GC_STATE.score=[Number(e.score[0]||0),Number(e.score[1]||0)];
 if(e.final_score)GC_STATE.score=[Number(e.final_score[0]||0),Number(e.final_score[1]||0)];
 if(e.inning)GC_STATE.inning=Number(e.inning);if(e.half&&['TOP','BOT'].includes(e.half))GC_STATE.half=e.half;
 if(Number.isFinite(Number(e.outs)))GC_STATE.outs=Number(e.outs);
 if(e.type==='PA_START'){
   GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.outs=Number(e.outs||GC_STATE.outs||0);
   match.textContent=`#${gamecastPlayerById(e.batter_id)?.jersey_number??'—'} ${e.batter} vs #${gamecastPlayerById(e.pitcher_id)?.jersey_number??'—'} ${e.pitcher}`;
   const box=document.getElementById('gcMatchup');if(box)box.innerHTML=gamecastMatchupCard(gamecastPlayerById(e.batter_id),'AT BAT')+gamecastMatchupCard(gamecastPlayerById(e.pitcher_id),'ON THE MOUND');
   gcHighlightBatter(e.batter_id);
 }
 if(e.type==='PITCH'){
   GC_STATE.balls=Number(e.balls||0);GC_STATE.strikes=Number(e.strikes||0);pt.textContent=`${e.pitch_type} ${e.velocity} MPH — ${e.call}`;
   let q=document.createElement('div');q.className='dot';q.style.left=(e.px*100)+'%';q.style.top=((1-e.pz)*100)+'%';zone.appendChild(q);
 }
 if(e.type==='BALL_IN_PLAY'){metric.textContent=`EV ${e.exit_velocity} • LA ${e.launch_angle}° • ${e.contact_quality}`;ball.style.left=(50+e.spray_angle*.7)+'%';ball.style.top='20%';gcBanner(String(e.result||'IN PLAY'),e.result==='HR');}
 if(e.type==='PA_END'){
   const r=e.result;if(r==='1B'||r==='BB'||r==='ROE'){GC_STATE.runner=e.batter_id;GC_STATE.base=1}else if(r==='2B'){GC_STATE.runner=e.batter_id;GC_STATE.base=2}else if(r==='3B'){GC_STATE.runner=e.batter_id;GC_STATE.base=3}else if(r==='HR'){GC_STATE.runner=null;GC_STATE.base=0}
 }
 if(e.type==='STEAL_ATTEMPT'&&e.success&&GC_STATE.runner){GC_STATE.base=Math.min(3,(GC_STATE.base||1)+1);gcFlash(`#${gamecastPlayerById(e.runner_id)?.jersey_number??''} ${gamecastPlayerById(e.runner_id)?.name||'Runner'} steals a base!`,'run')}
 if((e.type==='PICKOFF')||(e.type==='OUT'&&e.out_type==='Caught Stealing')){GC_STATE.runner=null;GC_STATE.base=0}
 if(e.type==='RUN'){GC_STATE.runner=null;GC_STATE.base=0;gcFlash(`${Number(e.runs||1)>1?Number(e.runs)+' RUNS':'RUN'} SCORES • ${GC_STATE.score[0]}-${GC_STATE.score[1]}`,'run');gcBanner('RUN SCORES',true)}
 if(e.type==='PITCHING_CHANGE'){const p=gamecastPlayerById(e.pitcher_id);gcFlash(`Pitching change • ${teamMark(e.team,true)} ${p?`#${p.jersey_number??''} ${escapeHtml(p.name)}`:escapeHtml(e.role||'Reliever')} enters the game`,'change');gcStrategyDecision(e)}
 if(['DEFENSIVE_SHIFT','BUNT_ATTEMPT','STEAL_ATTEMPT'].includes(e.type))gcStrategyDecision(e);
 if(e.type==='GREAT_PLAY'){const p=gamecastPlayerById(e.fielder_id);gcFlash(`⭐ GREAT PLAY${p?` • #${p.jersey_number??''} ${escapeHtml(p.name)}`:''}`,'defense');gcBanner('GREAT PLAY',true)}
 if(e.type==='FIELDING_ERROR'){const p=gamecastPlayerById(e.fielder_id);gcFlash(`ERROR${p?` • #${p.jersey_number??''} ${escapeHtml(p.name)}`:''}${e.position?` (${escapeHtml(e.position)})`:''}`,'defense');gcBanner('ERROR',true)}
 if(e.type==='OUTFIELD_HOLD'){const p=gamecastPlayerById(e.fielder_id);gcFlash(`Strong throw${p?` • #${p.jersey_number??''} ${escapeHtml(p.name)}`:''} holds the batter to a single`,'defense')}
 if(e.type==='INNING_END'){GC_STATE.outs=0;GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.runner=null;GC_STATE.base=0}
 if(e.type==='GAME_END'){gcFlash(`FINAL • ${teamName(GG.away_id)} ${GC_STATE.score[0]} — ${GC_STATE.score[1]} ${teamName(GG.home_id)}`,'run');gcBanner('FINAL',true)}
 gcUpdateScoreboard();
}


function gcStrategyDecision(e){
 const el=document.getElementById('gcStrategyLive');if(!el)return;
 const player=id=>gamecastPlayerById(id),name=id=>{const p=player(id);return p?`#${p.jersey_number??'—'} ${p.name}`:'player'};
 let label='MANAGER DECISION',text='';
 if(e.type==='PITCHING_CHANGE')text=`${teamName(e.team)} • ${e.role||'RP'} ${name(e.pitcher_id)} enters${e.reason==='STARTER_HOOK'?' after starter hook':''}`;
 if(e.type==='PINCH_HITTER')text=`${teamName(e.team)} • Pinch hit: ${name(e.player_id)} for ${name(e.replaced_id)}`;
 if(e.type==='PINCH_RUNNER')text=`${teamName(e.team)} • Pinch run: ${name(e.player_id)} for ${name(e.replaced_id)}`;
 if(e.type==='DEFENSIVE_SHIFT')text=`${teamName(e.team)} • ${String(e.mode||'STANDARD').replaceAll('_',' ')} alignment`;
 if(e.type==='DEFENSIVE_REPLACEMENT_WINDOW')text=`${teamName(e.team)} • Late-inning defensive replacement plan activated`;
 if(e.type==='BUNT_ATTEMPT')text=`Offensive call • Bunt ${e.success?'executed':'attempted'}`;
 if(e.type==='STEAL_ATTEMPT')text=`Baserunning call • Steal attempt ${e.success?'successful':'unsuccessful'}`;
 if(!text)return;
 el.innerHTML=`<span>${label}</span><b>${escapeHtml(text)}</b>`;
 el.classList.remove('pulse');void el.offsetWidth;el.classList.add('pulse');
}
function gcStrategyClass(e){
 return ['PITCHING_CHANGE','DEFENSIVE_SHIFT','BUNT_ATTEMPT','STEAL_ATTEMPT'].includes(e?.type)?' strategy':'';
}

function gcPlayerText(pid,pos=''){
 const p=gamecastPlayerById(pid);
 if(!p)return pos?`${pos}`:'fielder';
 return `#${p.jersey_number??'—'} ${p.name}${pos?` (${pos})`:''}`;
}
function describe(e){
 switch(e.type){
  case'GAME_START':return`${e.away_name} at ${e.home_name}`;
  case'STADIUM_CONTEXT':{const h=Object.entries(e.hitter||{}).map(([k,v])=>`${Number(v)>0?'+':''}${Number(v)} ${k}`),p=Object.entries(e.pitcher||{}).map(([k,v])=>`${Number(v)>0?'+':''}${Number(v)} ${k}`),fx=[...h,...p].join(' • ')||'Neutral';return`${e.stadium_name||'Home Ballpark'} — ${e.profile_name||'Neutral Park'} (${fx})`;}
  case'PA_START':{const b=gamecastPlayerById(e.batter_id),p=gamecastPlayerById(e.pitcher_id);return`${e.half} ${e.inning}: #${b?.jersey_number??'—'} ${e.batter} vs #${p?.jersey_number??'—'} ${e.pitcher}`;}
  case'PITCH':return`${e.pitch_type} ${e.velocity} MPH — ${e.call}`;
  case'BALL_IN_PLAY':{
    const f=e.fielder_id?` toward ${gcPlayerText(e.fielder_id,e.fielder_position||'')}`:'';
    return`${e.result}: ${e.exit_velocity} MPH, ${e.launch_angle}°${f}`;
  }
  case'PITCHING_CHANGE':{const p=gamecastPlayerById(e.pitcher_id);return`Pitching change: ${teamName(e.team)} brings in ${p?`#${p.jersey_number??'—'} ${p.name}`:(e.role||'reliever')} (${e.role||'RP'})`;}
  case'PINCH_HITTER':{const p=gamecastPlayerById(e.player_id),r=gamecastPlayerById(e.replaced_id);return`Pinch hitter: ${p?`#${p.jersey_number??'—'} ${p.name}`:'Bench bat'}${r?` for #${r.jersey_number??'—'} ${r.name}`:''}`;}
  case'PINCH_RUNNER':{const p=gamecastPlayerById(e.player_id),r=gamecastPlayerById(e.replaced_id);return`Pinch runner: ${p?`#${p.jersey_number??'—'} ${p.name}`:'Bench runner'}${r?` for #${r.jersey_number??'—'} ${r.name}`:''}`;}
  case'DEFENSIVE_SHIFT':return`${teamName(e.team)} uses ${String(e.mode||'STANDARD').replaceAll('_',' ')} alignment`;
  case'STEAL_ATTEMPT':return`Steal attempt — ${e.success?'SAFE':'OUT'}`;
  case'PICKOFF':return`Runner picked off`;
  case'BUNT_ATTEMPT':return`Bunt attempt — ${e.success?'successful':'out recorded'}`;
  case'DEFENSIVE_REPLACEMENT_WINDOW':return`${teamName(e.team)} goes to late-inning defensive replacements`;
  case'GREAT_PLAY':return`Great play by ${gcPlayerText(e.fielder_id,e.position||'')} — ${e.out_type||'out'} recorded`;
  case'FIELDING_ERROR':return`${gcPlayerText(e.fielder_id,e.position||'')} charged with a ${String(e.error_type||'field')}ing error`;
  case'FIELDING_COLLISION':return`Defensive collision involving ${gcPlayerText(e.fielder_id,e.position||'')}`;
  case'OUTFIELD_HOLD':return`${gcPlayerText(e.fielder_id,e.position||'')} uses the arm to hold the batter to a single`;
  case'OUT':{
    if(e.out_type==='Groundout'){
      const a=(e.assist_ids||[])[0]||e.fielder_id;
      if(a&&e.putout_id&&Number(a)!==Number(e.putout_id))return`Groundout: ${gcPlayerText(a,e.fielder_position||'')} to ${gcPlayerText(e.putout_id,'1B')} — ${e.outs} out(s)`;
      if(e.putout_id)return`Groundout: ${gcPlayerText(e.putout_id,e.fielder_position||'1B')} unassisted — ${e.outs} out(s)`;
    }
    if((e.out_type==='Flyout'||e.out_type==='Lineout')&&e.putout_id)return`${e.out_type} to ${gcPlayerText(e.putout_id,e.fielder_position||'')} — ${e.outs} out(s)`;
    return`${e.out_type} — ${e.outs} out(s)`;
  }
  case'RUN':return`Run scores! ${e.score[0]}-${e.score[1]}`;
  case'PA_END':return`PA: ${e.result}`;
  case'INNING_END':return`End ${e.half} ${e.inning}`;
  case'GAME_END':return`FINAL ${e.final_score[0]}-${e.final_score[1]}`;
  default:return e.type;
 }
}

loadPolicies();
(async()=>{if(!(await handleAccountAction()))await refresh()})();
setInterval(()=>{if(ME){loadChat('EBL');loadChat('TEAM');loadNotifications()}},15000);
