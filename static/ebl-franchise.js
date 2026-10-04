/* Elite Baseball League — eblFranchiseBrandStudioScript */
let EBL_BRAND_LOGOS={primary:'',secondary:'',wordmark:''};
async function eblLogoFile(file,slot){
 if(!file)return;
 const statusId={primary:'brandPrimaryLogoStatus',secondary:'brandSecondaryLogoStatus',wordmark:'brandWordmarkStatus'}[slot];
 const status=document.getElementById(statusId||'');
 try{
  if(status)status.textContent='Loading '+(file.name||'logo')+'…';
  if(file.size>5*1024*1024)throw new Error('Logo source file must be 5 MB or smaller.');
  const reader=new FileReader();
  const source=await new Promise((ok,bad)=>{
   reader.onload=()=>ok(reader.result);
   reader.onerror=()=>bad(new Error('Android could not read that image. Try choosing it from Files instead of Photos.'));
   reader.readAsDataURL(file);
  });
  const img=new Image();
  await new Promise((ok,bad)=>{img.onload=ok;img.onerror=()=>bad(new Error('That image could not be decoded.'));img.src=source});
  const w=img.naturalWidth||img.width,h=img.naturalHeight||img.height,max=1024,scale=Math.min(1,max/Math.max(w,h));
  const canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(w*scale));canvas.height=Math.max(1,Math.round(h*scale));
  const ctx=canvas.getContext('2d');ctx.clearRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);
  let data=canvas.toDataURL('image/webp',.88);
  if(!data||data==='data:,')data=canvas.toDataURL('image/png');
  if(data.length>7_100_000)throw new Error('This logo is still over the 5 MB upload limit after optimization.');
  EBL_BRAND_LOGOS[slot]=data;
  if(status)status.textContent='✓ '+(file.name||'Logo selected')+' — ready to save';
  eblBrandPreview();
 }catch(err){
  console.error('EBL logo picker',err);
  if(status)status.textContent='Upload failed — tap to try again';
  eblAlert(err?.message||'Could not load that logo.');
 }
}
function eblBrandPreview(){
 const city=document.getElementById('brandCity')?.value.trim()||'ELITE';
 const nick=document.getElementById('brandTeam')?.value.trim()||'BALL CLUB';
 const p=document.getElementById('brandPrimaryInput')?.value||'#071A31',s=document.getElementById('brandSecondaryInput')?.value||'#D7262E',a=document.getElementById('brandAccentInput')?.value||'#D9E0E8';
 const box=document.getElementById('brandPreviewPanel');if(!box)return;
 const primary=EBL_BRAND_LOGOS.primary,secondary=EBL_BRAND_LOGOS.secondary,wordmark=EBL_BRAND_LOGOS.wordmark;
 box.style.background=`linear-gradient(145deg,${p},${s})`;box.style.color=a;
 box.innerHTML=`<div class="eblBrandPreview_logos">${primary?`<img src="${primary}" alt="Primary logo">`:teamLogoMarkup(1,p,s,a,`${city} ${nick}`)}${secondary?`<img src="${secondary}" alt="Secondary logo">`:''}</div>${wordmark?`<div class="eblBrandPreview_jerseyLabel">JERSEY WORDMARK</div><img class="eblBrandPreview_wordmark" src="${wordmark}" alt="${escapeHtml(nick)} jersey wordmark">`:''}<h2 style="margin:14px 0 2px">${escapeHtml(city)} ${escapeHtml(nick)}</h2><div style="opacity:.82">EBL FRANCHISE IDENTITY</div>`;
}
function eblFranchiseIdentityStudio(j){
 const b=j.branding||{},phase=String(j.phase||'REGULAR').toUpperCase(),day=Number(j.league_day||0),season=Number(j.season||0),inSeason=phase!=='OFFSEASON'&&day>0,used=!!b.inseason_edit_used||Number(b.inseason_edit_season||0)===season,locked=inSeason&&used;
 let city=b.city||'',nick=b.team_name||'';
 if((!city||!nick)&&(b.display_name||j.team?.name)){const q=String(b.display_name||j.team.name).trim().split(/\s+/);nick=nick||q.pop()||'';city=city||q.join(' ')}
 EBL_BRAND_LOGOS={primary:b.primary_logo_url||b.primary_logo||'',secondary:b.secondary_logo_url||b.secondary_logo||b.logo_secondary||'',wordmark:b.jersey_wordmark_url||b.jersey_wordmark||''};
 return `<div class="eblIdentityStudio">
 <div>
  <span class="newsMeta">FRANCHISE IDENTITY STUDIO</span><h2>Build Your Club's Identity</h2>
  <p class="muted">${locked?`Season ${season} branding edit already used. Your next free identity window opens in the offseason.`:inSeason?`Season ${season} in-season branding edit is available. Saving will use your one active-season identity change for this season.`:'Identity window is open. Preseason/offseason saves do not consume your one in-season edit.'} Changes preserve the franchise ID and all historical records.</p>
  <div class="grid"><label>City / Home Market<input id="brandCity" maxlength="40" value="${escapeHtml(city)}" ${locked?'disabled':''} oninput="eblBrandPreview()"></label><label>Team Name<input id="brandTeam" maxlength="40" value="${escapeHtml(nick)}" ${locked?'disabled':''} oninput="eblBrandPreview()"></label></div>
  <div class="grid"><label>Primary Color<input id="brandPrimaryInput" type="color" value="${b.primary_color||'#071A31'}" ${locked?'disabled':''} oninput="eblBrandPreview()"></label><label>Secondary Color<input id="brandSecondaryInput" type="color" value="${b.secondary_color||'#D7262E'}" ${locked?'disabled':''} oninput="eblBrandPreview()"></label><label>Accent Color<input id="brandAccentInput" type="color" value="${b.accent_color||'#D9E0E8'}" ${locked?'disabled':''} oninput="eblBrandPreview()"></label></div>
  <div class="grid">
   <label class="eblLogoDrop">Primary Logo<input type="file" accept="image/*" hidden ${locked?'disabled':''} onchange="eblLogoFile(this.files&&this.files[0],'primary')"><span id="brandPrimaryLogoStatus">${(b.primary_logo_url||b.primary_logo)?'Primary logo loaded — tap to replace':'Tap to upload primary logo'}<br><small>PNG, JPG or WebP • up to 5 MB</small></span></label>
   <label class="eblLogoDrop">Secondary Logo<input type="file" accept="image/*" hidden ${locked?'disabled':''} onchange="eblLogoFile(this.files&&this.files[0],'secondary')"><span id="brandSecondaryLogoStatus">${b.secondary_logo?'Secondary logo loaded — tap to replace':'Tap to upload secondary / alternate logo'}<br><small>PNG, JPG or WebP • up to 5 MB</small></span></label>
   <label class="eblLogoDrop eblWordmarkDrop">Jersey Wordmark<input type="file" accept="image/*" hidden ${locked?'disabled':''} onchange="eblLogoFile(this.files&&this.files[0],'wordmark')"><span id="brandWordmarkStatus">${b.jersey_wordmark?'Jersey wordmark loaded — tap to replace':'Tap to upload transparent chest wordmark'}<br><small>Wide transparent PNG/WebP recommended • up to 5 MB • used across the jersey chest</small></span></label>
  </div>
  <div class="grid"><label>Home Uniform<select id="brandHomeSelect" ${locked?'disabled':''}>${uniformOptions(b.uniform_home||'WHITE')}</select></label><label>Away Uniform<select id="brandAwaySelect" ${locked?'disabled':''}>${uniformOptions(b.uniform_away||'NAVY')}</select></label></div>
  <label class="brandRights"><input id="brandRights" type="checkbox" ${locked?'disabled':''}> <span>I confirm that I created this franchise identity or have permission to use it, and that it is not intended to impersonate an existing professional, collegiate, amateur, or other third-party club or brand.</span></label>
  <button class="btn" ${locked?'disabled':''} data-ebl-action="save-franchise-identity">${locked?'Season Branding Edit Used':inSeason?'Save Identity • Use Season Edit':'Save Franchise Identity'}</button>
 </div><div><div id="brandPreviewPanel" class="eblBrandPreview"></div></div></div>`;
}
async function eblSaveFranchiseIdentity(){
 const body={city:brandCity.value.trim(),team_name:brandTeam.value.trim(),primary_color:brandPrimaryInput.value,secondary_color:brandSecondaryInput.value,accent_color:brandAccentInput.value,primary_logo:EBL_BRAND_LOGOS.primary,secondary_logo:EBL_BRAND_LOGOS.secondary,jersey_wordmark:EBL_BRAND_LOGOS.wordmark,uniform_home:brandHomeSelect.value,uniform_away:brandAwaySelect.value,logo_style:1,rights_attested:Boolean(document.getElementById('brandRights')?.checked)};
 if(!body.city||!body.team_name){eblAlert('Enter both a city/home market and a team name.');return}
 if(!body.rights_attested){eblAlert('Confirm that you have the right to use this franchise name and artwork before saving.');return}
 try{await api('/api/coach/branding',{method:'POST',body:JSON.stringify(body)});eblToast('Franchise identity saved.','success');await loadLeague();await loadCoachHub()}catch(e){eblAlert(e.detail||e.error||'Could not save franchise identity.')}
}
const eblLoadCoachHub=window.loadCoachHub;
if(typeof eblLoadCoachHub==='function')window.loadCoachHub=async function(){
 const result=await eblLoadCoachHub.apply(this,arguments);
 try{const j=await api('/api/coach/team'),pane=document.getElementById('cBrand');if(j?.team&&pane){pane.innerHTML=eblFranchiseIdentityStudio(j);eblBrandPreview()}}catch(e){console.warn('production identity studio',e)}
 return result;
};
const eblTeamMark=window.teamMark;
window.teamMark=function(fid,small=false){
 const t=LEAGUE?.teams?.find(x=>x.id===fid)||{};
 const logo=t.primary_logo||t.secondary_logo;
 if(logo){const n=t.display_name||t.name||fid||'EBL';return `<span class="teamMark ${small?'sm':''}" title="${escapeHtml(n)}" style="overflow:hidden;background:${t.primary_color||'#071A31'}"><img src="${logo}" alt="" style="width:100%;height:100%;object-fit:contain"></span>`}
 return eblTeamMark?eblTeamMark(fid,small):'';
};
window.EBL_FRANCHISE_IDENTITY={version:'production',fields:['city','team-name','primary-color','secondary-color','accent-color','primary-logo','secondary-logo','jersey-wordmark'],inSeasonEditsPerSeason:1,preseasonOffseasonOpen:true};
