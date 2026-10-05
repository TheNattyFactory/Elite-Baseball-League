/* Elite Baseball League — eblGamecastGameday */
(function(){
  const BUILD='gameday-visual-replay';
  function esc(v){return typeof escapeHtml==='function'?escapeHtml(String(v??'')):String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));}
  function N(v,d=0){const n=Number(v);return Number.isFinite(n)?n:d}
  function player(pid){try{return typeof gamecastPlayerById==='function'?gamecastPlayerById(pid):null}catch(_){return null}}
  function art(p,action){
    if(!p)return '';
    try{if(typeof eblPlayerArt==='function')return eblPlayerArt(p,'lg',action||'portrait')}catch(_){ }
    try{if(typeof playerPortraitMarkup==='function')return playerPortraitMarkup(p,action||'portrait')}catch(_){ }
    return '';
  }
  function portrait(p,action){
    if(!p)return '<div class="playerPortrait"></div>';
    try{return playerPortraitMarkup(p,action||'portrait')}catch(_){return `<div class="playerPortrait">${art(p,'portrait')}</div>`}
  }
  function teamInfo(fid){
    const t=(LEAGUE?.teams||[]).find(x=>x.id===fid)||{};
    return {name:t.display_name||t.name||teamName(fid)||fid,mark:teamMark(fid,true)};
  }
  function hitterLine(p){
    if(!p)return 'Waiting for first plate appearance';
    const r=(GG?.box?.hitter_rows||[]).find(x=>N(x.player_id)===N(p.player_id??p.id))||p;
    return `${N(r.H)}-${N(r.AB)} • ${N(r.HR)} HR • ${N(r.RBI)} RBI${N(r.BB)?` • ${N(r.BB)} BB`:''}`;
  }
  function pitcherLine(p){
    if(!p)return 'Waiting for first pitch';
    const r=(GG?.box?.pitcher_rows||[]).find(x=>N(x.player_id)===N(p.player_id??p.id))||p;
    const outs=N(r.OUTS??r.outs);const ip=`${Math.floor(outs/3)}.${outs%3}`;
    return `${ip} IP • ${N(r.SO)} K • ${N(r.BB)} BB • ${N(r.ER)} ER`;
  }
  function callClass(call){
    const s=String(call||'').toLowerCase();
    if(s==='ball')return 'ball';if(s.includes('foul'))return 'foul';if(s.includes('in play'))return 'play';return 'strike';
  }
  function pitchCode(t){
    const map={'Four-Seam':'4S','Slider':'SL','Changeup':'CH','Sinker':'SI','Curve':'CU'};return map[t]||String(t||'P').slice(0,2).toUpperCase();
  }
  function inningLabel(e){return `${String(e?.half||'TOP').toUpperCase()==='BOT'?'BOT':'TOP'} ${N(e?.inning,1)}`}
  function scorebar(){
    const a=teamInfo(GG.away_id),h=teamInfo(GG.home_id);
    return `<div class="gcScorebarGameday">
      <div class="gcClubGameday">${a.mark}<div class="gcClubCopyGameday"><b>${esc(a.name)}</b><small>AWAY</small></div><strong id="gcAwayScore" class="gcClubScoreGameday">0</strong></div>
      <div class="gcCenterStateGameday"><div id="gcInning" class="gcStateLineGameday">TOP 1</div><div id="gcCount" class="gcCountLineGameday">0-0 • 0 OUTS</div><div class="gcBasesGameday"><i id="gcB3" class="gcBaseGameday b3"></i><i id="gcB2" class="gcBaseGameday b2"></i><i id="gcB1" class="gcBaseGameday b1"></i></div></div>
      <div class="gcClubGameday home"><strong id="gcHomeScore" class="gcClubScoreGameday">0</strong><div class="gcClubCopyGameday"><b>${esc(h.name)}</b><small>HOME</small></div>${h.mark}</div>
    </div>`;
  }
  function tabButton(mode,label,active=false){return `<button class="gcDayTabGameday${active?' active':''}" data-gc-tab="${mode}" data-ebl-action="game-tab" data-tab="${mode}">${label}</button>`}
  window.renderGameShell=function(){
    const host=document.getElementById('gcontent');if(!host)return;
    const dlg=document.getElementById('gc');if(dlg){dlg.classList.add('gcGamedayDialogGameday');if(!dlg.dataset.gc124Close){dlg.addEventListener('close',()=>clearInterval(timer));dlg.dataset.gc124Close='1'}}
    host.innerHTML=`<div class="gcDayShellGameday"><div class="gcDayTopGameday">
      <div class="gcDayEyebrowGameday"><span>EBL GAMEDAY • DAY ${N(GG?.league_day)}</span><button class="gcDayCloseGameday" aria-label="Close GameCast" data-ebl-action="close-dialog" data-dialog="gc">×</button></div>
      ${scorebar()}
      <div class="gcDayTabsGameday">${tabButton('CAST','REPLAY',true)}${tabButton('SUMMARY','SUMMARY')}${tabButton('BOX','BOX SCORE')}${tabButton('PBP','PLAYS')}</div>
    </div><div id="gameView" class="gcDayBodyGameday"></div></div>`;
    renderGamecast();
  };
  window.gameTab=function(mode,b){
    clearInterval(timer);
    document.querySelectorAll('.gcDayTabGameday').forEach(x=>x.classList.remove('active'));if(b)b.classList.add('active');
    if(mode==='CAST')renderGamecast();
    else if(mode==='SUMMARY')window.renderGameSummaryGameday();
    else if(mode==='BOX'){gcSetFinalStateGameday();renderBoxScore();}
    else if(mode==='PBP')renderFullPlayByPlay();
  };
  function matchupCard(p,label,kind){
    return `<div class="gcMatchCardGameday"><div class="gcMatchLabelGameday">${esc(label)}</div>${p?`<div class="gcMatchPersonGameday">${portrait(p,kind)}<div><b>#${N(p.jersey_number,24)} ${esc(p.name||'Player')}</b><small>${esc(p.primary_pos||'')}</small><div class="gcGameLineGameday">${kind==='pitching'?pitcherLine(p):hitterLine(p)}</div></div></div>`:'<div class="muted" style="padding:10px 0;font-size:10px">Waiting for matchup…</div>'}</div>`;
  }
  function updateMatchup(batterId,pitcherId){
    const b=player(batterId),p=player(pitcherId),box=document.getElementById('gcMatchupGameday');
    if(box)box.innerHTML=matchupCard(b,'AT BAT','batting')+matchupCard(p,'ON THE MOUND','pitching');
    const ba=document.getElementById('gcBatterArtGameday');if(ba)ba.innerHTML=art(b,'batting');
    const pa=document.getElementById('gcPitcherArtGameday');if(pa)pa.innerHTML=art(p,'pitching');
    const copy=document.getElementById('gcAtBatCopyGameday');if(copy)copy.innerHTML=b&&p?`<b>#${N(b.jersey_number,24)} ${esc(b.name)} vs #${N(p.jersey_number,24)} ${esc(p.name)}</b><span>${esc(hitterLine(b))}</span>`:'<b>Game replay</b><span>Waiting for the first matchup</span>';
  }
  function resetPitchVisual(){
    const stage=document.getElementById('gcVisualStageGameday');if(stage)stage.classList.remove('inPlay');
    const z=document.getElementById('gcZoneDotsGameday');if(z)z.innerHTML='';
    const rail=document.getElementById('gcPitchRailGameday');if(rail)rail.innerHTML='<div class="muted" style="padding:9px;font-size:10px">This at-bat is about to begin.</div>';
    const pc=document.getElementById('gcPitchCallGameday');if(pc)pc.innerHTML='<b>Waiting for first pitch</b><span>Pitch type, velocity, location and call will appear here.</span>';
    const res=document.getElementById('gcResultGameday');if(res){res.textContent='';res.className='gcResultGameday'}
  }
  window.renderGamecast=function(){
    gi=0;GC_STATE={score:[0,0],inning:1,half:'TOP',balls:0,strikes:0,outs:0,runner:null,base:0,batter_id:null,pitcher_id:null,pitch_no:0};
    const host=document.getElementById('gameView');if(!host)return;
    host.innerHTML=`<div class="gcReplayGridGameday">
      <aside class="gcPanelGameday gcPitchPanelGameday"><div class="gcPanelHeadGameday"><strong>PITCH SEQUENCE</strong><span id="gcPitchCountGameday">0 PITCHES</span></div><div id="gcPitchRailGameday" class="gcPitchRailGameday"><div class="muted" style="padding:9px;font-size:10px">This at-bat is about to begin.</div></div></aside>
      <section class="gcPanelGameday gcVisualCardGameday"><div id="gcVisualStageGameday" class="gcVisualStageGameday"><div class="gcStandsGameday"></div><div class="gcOutfieldWallGameday"></div><div class="gcMoundGameday"></div><div id="gcPitcherArtGameday" class="gcPitcherArtGameday"></div><div id="gcBatterArtGameday" class="gcBatterArtGameday"></div>
        <div id="gcZoneRigGameday" class="gcZoneRigGameday"><div id="gcZoneCanvasGameday" class="gcZoneCanvasGameday"><div class="gcStrikeZoneGameday"></div><div id="gcZoneDotsGameday"></div></div></div>
        <div id="gcFieldReplayGameday" class="gcFieldReplayGameday"><svg viewBox="0 0 600 420" preserveAspectRatio="none" aria-label="Ball in play field view"><path d="M300 390 L65 120 L300 28 L535 120 Z" fill="#2f6b3d" stroke="#e7e5d7" stroke-width="3"/><path d="M300 390 L158 230 L300 125 L442 230 Z" fill="#9d7348" stroke="#e7d1ad" stroke-width="2"/><path d="M300 390 L300 125 M300 390 L65 120 M300 390 L535 120" fill="none" stroke="#f4f4ea" stroke-width="2" opacity=".72"/><rect x="294" y="378" width="13" height="13" transform="rotate(45 300 384)" fill="#fff"/><rect x="435" y="224" width="12" height="12" transform="rotate(45 441 230)" fill="#fff"/><rect x="294" y="119" width="12" height="12" transform="rotate(45 300 125)" fill="#fff"/><rect x="153" y="224" width="12" height="12" transform="rotate(45 159 230)" fill="#fff"/><g fill="#d9e0e8" opacity=".8"><circle cx="300" cy="270" r="8"/><circle cx="210" cy="218" r="8"/><circle cx="390" cy="218" r="8"/><circle cx="145" cy="135" r="8"/><circle cx="300" cy="75" r="8"/><circle cx="455" cy="135" r="8"/></g><line id="gcTrajGameday" class="gcTrajGameday" x1="300" y1="382" x2="300" y2="160"/><circle id="gcFieldBallGameday" class="gcFieldBallGameday" cx="300" cy="160" r="7"/></svg></div>
        <div id="gcResultGameday" class="gcResultGameday"></div><div id="gcPitchCallGameday" class="gcPitchCallGameday"><b>Waiting for first pitch</b><span>Pitch type, velocity, location and call will appear here.</span></div>
      </div><div class="gcUnderStageGameday"><div id="gcAtBatCopyGameday" class="gcAtBatCopyGameday"><b>Game replay</b><span>Watch the final game unfold pitch by pitch.</span></div><div class="gcPlaybackGameday"><button class="gcMiniBtnGameday primary" data-ebl-action="gamecast-play" data-speed="850">▶ PLAY</button><button class="gcMiniBtnGameday" data-ebl-action="gamecast-pause">Ⅱ PAUSE</button><button class="gcMiniBtnGameday" data-ebl-action="gamecast-play" data-speed="300">FAST</button><button class="gcMiniBtnGameday" data-ebl-action="gamecast-instant">END</button><button class="gcMiniBtnGameday" data-ebl-action="gamecast-replay">↺ REPLAY</button></div></div></section>
      <aside id="gcMatchupGameday" class="gcMatchPanelGameday">${matchupCard(null,'AT BAT','batting')}${matchupCard(null,'ON THE MOUND','pitching')}<div id="gcStrategyLive" class="gcManagerGameday"><span>MANAGER DECISIONS</span><b>Game plan loaded</b></div></aside>
      <section class="gcPanelGameday gcLatestFeedGameday"><div class="gcPanelHeadGameday"><strong>LIVE FEED</strong><span>REPLAY</span></div><div id="gcFeedGameday" class="gcFeedGameday"></div></section>
    </div>`;
    gcUpdateScoreboard();clearInterval(timer);timer=setInterval(step,850);
  };
  window.gcPlayGameday=function(ms=850){clearInterval(timer);timer=setInterval(step,ms)};
  window.gcPauseGameday=function(){clearInterval(timer)};
  window.gcUpdateScoreboard=function(){
    const a=document.getElementById('gcAwayScore'),h=document.getElementById('gcHomeScore'),inn=document.getElementById('gcInning'),cnt=document.getElementById('gcCount');
    if(a)a.textContent=GC_STATE.score?.[0]??0;if(h)h.textContent=GC_STATE.score?.[1]??0;if(inn)inn.textContent=`${GC_STATE.half==='BOT'?'BOT':'TOP'} ${GC_STATE.inning||1}`;if(cnt)cnt.textContent=`${GC_STATE.balls||0}-${GC_STATE.strikes||0} • ${GC_STATE.outs||0} OUT${GC_STATE.outs===1?'':'S'}`;
    ['1','2','3'].forEach(n=>{const b=document.getElementById('gcB'+n);if(b)b.classList.toggle('on',N(n)===N(GC_STATE.base)&&!!GC_STATE.runner)});
  };
  function feedEvent(e){
    const feed=document.getElementById('gcFeedGameday');if(!feed)return;const d=document.createElement('div');d.className='gcFeedPlayGameday'+(typeof gcStrategyClass==='function'&&gcStrategyClass(e)?' strategy':'');d.innerHTML=`<span class="gcFeedTagGameday">${esc(e?.inning?inningLabel(e):String(e?.type||'PLAY').replaceAll('_',' '))}</span><span>${esc(describe(e))}</span>`;feed.prepend(d);while(feed.children.length>28)feed.removeChild(feed.lastChild);
  }
  function addPitch(e){
    const rail=document.getElementById('gcPitchRailGameday'),dots=document.getElementById('gcZoneDotsGameday'),pc=document.getElementById('gcPitchCallGameday'),counter=document.getElementById('gcPitchCountGameday');
    const num=N(e.pitch_no,GC_STATE.pitch_no+1),cls=callClass(e.call);GC_STATE.pitch_no=num;
    if(rail){if(num===1)rail.innerHTML='';const row=document.createElement('div');row.className='gcPitchRowGameday';row.innerHTML=`<span class="gcPitchNumGameday ${cls}">${num}</span><span><b>${esc(pitchCode(e.pitch_type))} • ${esc(e.call)}</b><small>${esc(e.pitch_type)}</small></span><span class="gcPitchVelGameday">${N(e.velocity).toFixed(1)} MPH</span>`;rail.prepend(row)}
    if(counter)counter.textContent=`${num} PITCH${num===1?'':'ES'}`;
    const x=Math.max(6,Math.min(94,8+N(e.px,.5)*84)),y=Math.max(5,Math.min(95,8+(1-N(e.pz,.5))*84));
    if(dots){const q=document.createElement('div');q.className=`gcPitchDotGameday ${cls}`;q.style.left=x+'%';q.style.top=y+'%';q.textContent=num;dots.appendChild(q)}
    if(pc)pc.innerHTML=`<b>${esc(e.pitch_type)} • ${N(e.velocity).toFixed(1)} MPH</b><span>${esc(e.call)} • Count ${N(e.balls)}-${N(e.strikes)}</span>`;
    animatePitch(e,x,y);
  }
  function animatePitch(e,x,y){
    const stage=document.getElementById('gcVisualStageGameday'),canvas=document.getElementById('gcZoneCanvasGameday');if(!stage||!canvas)return;
    const sr=stage.getBoundingClientRect(),zr=canvas.getBoundingClientRect(),b=document.createElement('i');b.className='gcLiveBallGameday';b.style.left='50%';b.style.top='34%';stage.appendChild(b);
    const tx=(zr.left-sr.left)+(x/100)*zr.width,ty=(zr.top-sr.top)+(y/100)*zr.height;requestAnimationFrame(()=>{b.style.left=tx+'px';b.style.top=ty+'px'});setTimeout(()=>b.remove(),650);
  }
  function showResult(text,big=false){const el=document.getElementById('gcResultGameday');if(!el)return;el.textContent=text;el.className='gcResultGameday show'+(big?' big':'');clearTimeout(window.__gc124Result);window.__gc124Result=setTimeout(()=>{if(el)el.className='gcResultGameday'},1750)}
  function showBallInPlay(e){
    const stage=document.getElementById('gcVisualStageGameday');if(stage)stage.classList.add('inPlay');
    const pc=document.getElementById('gcPitchCallGameday');if(pc)pc.innerHTML=`<b>${esc(String(e.result||'BALL IN PLAY'))}</b><span>${N(e.exit_velocity).toFixed(1)} MPH EV • ${N(e.launch_angle).toFixed(1)}° LA • ${esc(e.contact_quality||'Contact')}</span>`;
    const angle=N(e.spray_angle),result=String(e.result||'').toUpperCase(),ev=N(e.exit_velocity,90),la=N(e.launch_angle,10);let depth=160;
    if(result==='HR')depth=38;else if(result==='3B')depth=72;else if(result==='2B')depth=102;else if(result==='1B'||result==='ROE')depth=145;else depth=Math.max(80,170-Math.max(0,ev-80)*1.2-Math.max(0,la)*.65);
    const x=Math.max(88,Math.min(512,300+angle*4.65)),y=Math.max(34,Math.min(220,depth)),line=document.getElementById('gcTrajGameday'),ball=document.getElementById('gcFieldBallGameday');if(line){line.setAttribute('x2',x);line.setAttribute('y2',y)}if(ball){ball.setAttribute('cx',x);ball.setAttribute('cy',y)}showResult(result==='OUT'?esc(e.out_type||'BALL IN PLAY'):result,result==='HR');
  }
  function managerEvent(e){
    const el=document.getElementById('gcStrategyLive');if(!el)return;let text='';
    if(e.type==='PITCHING_CHANGE'){const p=player(e.pitcher_id);text=`${teamName(e.team)} • ${e.role||'RP'} ${p?`#${N(p.jersey_number,24)} ${p.name}`:'enters'}`}
    else if(e.type==='DEFENSIVE_SHIFT')text=`${teamName(e.team)} • ${String(e.mode||'STANDARD').replaceAll('_',' ')} alignment`;
    else if(e.type==='BUNT_ATTEMPT')text=`Offensive call • Bunt ${e.success?'executed':'attempted'}`;
    else if(e.type==='STEAL_ATTEMPT')text=`Baserunning call • Steal attempt ${e.success?'successful':'unsuccessful'}`;
    else if(e.type==='PICKOFF')text='Pickoff move • Runner erased';
    if(!text)return;el.innerHTML=`<span>MANAGER DECISION</span><b>${esc(text)}</b>`;el.classList.remove('pulse');void el.offsetWidth;el.classList.add('pulse');
  }
  window.step=function(){
    if(gi>=((GG?.events||[]).length)){clearInterval(timer);return}
    const e=GG.events[gi++];feedEvent(e);
    if(e.score)GC_STATE.score=[N(e.score[0]),N(e.score[1])];if(e.final_score)GC_STATE.score=[N(e.final_score[0]),N(e.final_score[1])];if(e.inning)GC_STATE.inning=N(e.inning,1);if(e.half&&['TOP','BOT'].includes(e.half))GC_STATE.half=e.half;if(Number.isFinite(Number(e.outs)))GC_STATE.outs=N(e.outs);
    if(e.type==='PA_START'){
      GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.pitch_no=0;GC_STATE.outs=N(e.outs,GC_STATE.outs);GC_STATE.batter_id=e.batter_id;GC_STATE.pitcher_id=e.pitcher_id;resetPitchVisual();updateMatchup(e.batter_id,e.pitcher_id);
    }
    if(e.type==='PITCH'){GC_STATE.balls=N(e.balls);GC_STATE.strikes=N(e.strikes);addPitch(e)}
    if(e.type==='BALL_IN_PLAY')showBallInPlay(e);
    if(e.type==='PA_END'){
      const r=String(e.result||'');if(['1B','ROE'].includes(r)){GC_STATE.runner=e.batter_id;GC_STATE.base=1}else if(r==='BB'&&!GC_STATE.runner){GC_STATE.runner=e.batter_id;GC_STATE.base=1}else if(r==='2B'){GC_STATE.runner=e.batter_id;GC_STATE.base=2}else if(r==='3B'){GC_STATE.runner=e.batter_id;GC_STATE.base=3}else if(r==='HR'){GC_STATE.runner=null;GC_STATE.base=0}
    }
    if(e.type==='STEAL_ATTEMPT'){if(e.success&&GC_STATE.runner)GC_STATE.base=Math.min(3,(GC_STATE.base||1)+1);managerEvent(e);showResult(e.success?'STOLEN BASE':'CAUGHT STEALING',true)}
    if(e.type==='PICKOFF'||(e.type==='OUT'&&e.out_type==='Caught Stealing')){GC_STATE.runner=null;GC_STATE.base=0;managerEvent(e);showResult(e.type==='PICKOFF'?'PICKED OFF':'CAUGHT STEALING',true)}
    if(e.type==='RUN'){GC_STATE.runner=null;GC_STATE.base=0;showResult(N(e.runs,1)>1?`${N(e.runs,1)} RUNS SCORE`:'RUN SCORES',true)}
    if(['PITCHING_CHANGE','DEFENSIVE_SHIFT','BUNT_ATTEMPT'].includes(e.type))managerEvent(e);
    if(e.type==='OUT'&&e.out_type==='Strikeout')showResult('STRIKEOUT',true);if(e.type==='GREAT_PLAY')showResult('GREAT PLAY',true);if(e.type==='FIELDING_ERROR')showResult('ERROR',true);if(e.type==='OUTFIELD_HOLD')showResult('STRONG THROW');
    if(e.type==='INNING_END'){GC_STATE.outs=0;GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.runner=null;GC_STATE.base=0}
    if(e.type==='GAME_END'){showResult('FINAL',true);clearInterval(timer)}
    gcUpdateScoreboard();
  };
  function gcSetFinalStateGameday(){GC_STATE.score=[N(GG?.away_runs),N(GG?.home_runs)];GC_STATE.inning=9;GC_STATE.half='BOT';GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.outs=3;GC_STATE.runner=null;GC_STATE.base=0;gcUpdateScoreboard()}
  function lineScore(){
    const a=GG?.line_score?.away||{},h=GG?.line_score?.home||{},at=GG?.totals?.away||{R:GG?.away_runs,H:0,E:0},ht=GG?.totals?.home||{R:GG?.home_runs,H:0,E:0};let heads='',ar='',hr='';for(let i=1;i<=9;i++){heads+=`<th>${i}</th>`;ar+=`<td>${a[String(i)]??0}</td>`;hr+=`<td>${h[String(i)]??0}</td>`}return `<div class="gcLineScoreGameday"><table><tr><th>TEAM</th>${heads}<th>R</th><th>H</th><th>E</th></tr><tr><td>${teamMark(GG.away_id,true)} ${esc(teamName(GG.away_id))}</td>${ar}<td><b>${N(at.R,GG.away_runs)}</b></td><td>${N(at.H)}</td><td>${N(at.E)}</td></tr><tr><td>${teamMark(GG.home_id,true)} ${esc(teamName(GG.home_id))}</td>${hr}<td><b>${N(ht.R,GG.home_runs)}</b></td><td>${N(ht.H)}</td><td>${N(ht.E)}</td></tr></table></div>`;
  }
  function leaderRows(fid){
    const hitters=(GG?.box?.hitter_rows||[]).filter(x=>x.team_id===fid).slice().sort((a,b)=>(N(b.HR)-N(a.HR))||(N(b.RBI)-N(a.RBI))||(N(b.H)-N(a.H))).slice(0,2);
    return hitters.map(p=>`<div class="gcLeaderGameday">${portrait(p,'batting')}<div><b>#${N(p.jersey_number,24)} ${esc(p.name)}</b><small>${esc(hitterLine(p))}</small></div></div>`).join('')||'<div class="muted">No batting line available.</div>';
  }
  window.renderGameSummaryGameday=function(){
    const runs=(GG?.events||[]).filter(e=>e.type==='RUN');const scoring=runs.map(e=>{const who=player(e.batter_id)||player(e.runner_id),team=e.team?teamName(e.team):'';return `<div class="gcScoringPlayGameday"><span>${inningLabel(e)}</span><div><b>${esc(team)}</b><div class="muted">${who?esc(`#${N(who.jersey_number,24)} ${who.name}`):'Scoring play'}${e.note?` • ${esc(e.note)}`:''}</div></div><b class="gcScorePillGameday">${N(e.score?.[0])}-${N(e.score?.[1])}</b></div>`}).join('')||'<p class="muted">No scoring plays were recorded.</p>';
    const host=document.getElementById('gameView');if(!host)return;host.innerHTML=`<div class="gcSummaryHeroGameday"><section class="gcSummaryCardGameday" style="grid-column:1/-1"><h3>FINAL LINE</h3>${lineScore()}</section><section class="gcSummaryCardGameday"><h3>SCORING PLAYS</h3>${scoring}</section><section class="gcSummaryCardGameday"><h3>${esc(teamName(GG.away_id))} • NOTABLE BATTING</h3>${leaderRows(GG.away_id)}<h3 class="eblSpaceTopM">${esc(teamName(GG.home_id))} • NOTABLE BATTING</h3>${leaderRows(GG.home_id)}</section></div>`;
    gcSetFinalStateGameday();
  };
  window.renderFullPlayByPlay=function(){
    const evs=GG?.events||[],groups=new Map();evs.forEach(e=>{const key=e.inning?`${e.half||'TOP'}|${e.inning}`:'GAME|0';if(!groups.has(key))groups.set(key,[]);groups.get(key).push(e)});let html='';for(const [key,arr] of groups){const [half,inn]=key.split('|');const label=half==='GAME'?'GAME':`${half==='BOT'?'BOTTOM':'TOP'} ${inn}`;html+=`<section class="gcPlaysGroupGameday"><div class="gcPlaysInningGameday">${label}</div><div class="gcPlaysListGameday">${arr.map(e=>{const icon=e.type==='PITCH'?'P':e.type==='BALL_IN_PLAY'?'BIP':e.type==='RUN'?'R':e.type==='OUT'?'OUT':'•';return `<div class="gcPlayGameday"><span class="gcPlayIconGameday">${icon}</span><div><b>${esc(describe(e))}</b><small>${esc(String(e.type||'PLAY').replaceAll('_',' '))}</small></div></div>`}).join('')}</div></section>`}document.getElementById('gameView').innerHTML=html||'<div class="gcSummaryCardGameday">No play-by-play available.</div>';
    gcSetFinalStateGameday();
  };
  window.EBL_GAMECAST_BUILD=BUILD;
})();


/* EBL GAMECAST RC134 — broadcast timeline + live replay state */
(function(){
  'use strict';
  const BUILD='RC135_GAMECAST_STADIUM_MOTION';

  function esc(v){
    if(typeof escapeHtml==='function') return escapeHtml(String(v??''));
    return String(v??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  }
  function N(v,d=0){const n=Number(v);return Number.isFinite(n)?n:d}
  function evs(){return Array.isArray(GG?.events)?GG.events:[]}
  function player(pid){
    try{return typeof gamecastPlayerById==='function'?gamecastPlayerById(pid):null}catch(_){return null}
  }
  function art(p,action){
    if(!p)return '';
    try{if(typeof eblPlayerArt==='function')return eblPlayerArt(p,'lg',action||'portrait')}catch(_){}
    try{if(typeof playerPortraitMarkup==='function')return playerPortraitMarkup(p,action||'portrait')}catch(_){}
    return '';
  }
  function portrait(p,action){
    if(!p)return '<div class="playerPortrait"></div>';
    try{return playerPortraitMarkup(p,action||'portrait')}catch(_){return `<div class="playerPortrait">${art(p,'portrait')}</div>`}
  }
  function safeDescribe(e){
    try{if(typeof describe==='function')return describe(e)}catch(_){}
    return String(e?.type||'PLAY').replaceAll('_',' ');
  }
  function inningLabel(e){return `${String(e?.half||'TOP').toUpperCase()==='BOT'?'BOT':'TOP'} ${N(e?.inning,1)}`}
  function pitchCode(t){
    const map={'Four-Seam':'4S','Four Seam':'4S','Slider':'SL','Changeup':'CH','Sinker':'SI','Curve':'CU','Curveball':'CU'};
    return map[t]||String(t||'P').slice(0,2).toUpperCase();
  }
  function callClass(call){
    const s=String(call||'').toLowerCase();
    if(s==='ball')return 'ball';
    if(s.includes('foul'))return 'foul';
    if(s.includes('in play'))return 'play';
    return 'strike';
  }
  function teamLabel(fid){
    try{return teamName(fid)||fid||'Team'}catch(_){return fid||'Team'}
  }
  function resetState(){
    GC_STATE={
      score:[0,0],inning:1,half:'TOP',balls:0,strikes:0,outs:0,
      runner:null,base:0,batter_id:null,pitcher_id:null,pitch_no:0,
      last_pitch:null,current_pa_start:-1,liveHitters:{},livePitchers:{},
      runnerVisualBase:0,lastBip:null,lastDefenseEvent:null,postPaRunnerEvent:null,crowdEnergy:12,
      playSpeed:850,isPlaying:false,broadcastHold:null
    };
  }
  function liveHitter(pid){
    const k=String(pid??'');
    if(!GC_STATE.liveHitters[k])GC_STATE.liveHitters[k]={AB:0,H:0,HR:0,RBI:0,BB:0,SO:0,R:0};
    return GC_STATE.liveHitters[k];
  }
  function livePitcher(pid){
    const k=String(pid??'');
    if(!GC_STATE.livePitchers[k])GC_STATE.livePitchers[k]={OUTS:0,H:0,BB:0,SO:0,P:0};
    return GC_STATE.livePitchers[k];
  }
  function liveHitterLine(pid){
    const s=liveHitter(pid);
    return `${s.H}-${s.AB} • ${s.HR} HR • ${s.RBI} RBI${s.BB?` • ${s.BB} BB`:''}`;
  }
  function livePitcherLine(pid){
    const s=livePitcher(pid),ip=`${Math.floor(s.OUTS/3)}.${s.OUTS%3}`;
    return `${ip} IP • ${s.SO} K • ${s.BB} BB • ${s.P} P`;
  }
  function finalHitterLine(row){
    return `${N(row?.H)}-${N(row?.AB)} • ${N(row?.HR)} HR • ${N(row?.RBI)} RBI${N(row?.BB)?` • ${N(row.BB)} BB`:''}`;
  }
  function finalPitcherLine(row){
    const outs=N(row?.OUTS??row?.outs),ip=`${Math.floor(outs/3)}.${outs%3}`;
    return `${ip} IP • ${N(row?.SO)} K • ${N(row?.BB)} BB • ${N(row?.ER)} ER`;
  }
  function matchupCard(p,label,kind){
    const pid=N(p?.player_id??p?.id);
    const line=kind==='pitching'?livePitcherLine(pid):liveHitterLine(pid);
    return `<div class="gcMatchCardGameday">
      <div class="gcMatchLabelGameday">${esc(label)}</div>
      ${p?`<div class="gcMatchPersonGameday">${portrait(p,kind)}<div><b>#${N(p.jersey_number,24)} ${esc(p.name||'Player')}</b><small>${esc(p.primary_pos||'')}</small><div class="gcGameLineGameday">${esc(line)}</div></div></div>`:
      '<div class="muted gcWaitingGameday">Waiting for matchup…</div>'}
    </div>`;
  }
  function updateMatchup(batterId,pitcherId){
    const b=player(batterId),p=player(pitcherId);
    const cards=document.getElementById('gcMatchupCardsGameday');
    if(cards)cards.innerHTML=matchupCard(b,'AT BAT','batting')+matchupCard(p,'ON THE MOUND','pitching');
    const ba=document.getElementById('gcBatterArtGameday');if(ba)ba.innerHTML=art(b,'batting');
    const pa=document.getElementById('gcPitcherArtGameday');if(pa)pa.innerHTML=art(p,'pitching');
    const copy=document.getElementById('gcAtBatCopyGameday');
    if(copy){
      copy.innerHTML=b&&p
        ?`<b>#${N(b.jersey_number,24)} ${esc(b.name)} vs #${N(p.jersey_number,24)} ${esc(p.name)}</b><span>${esc(liveHitterLine(batterId))}</span>`
        :'<b>Game replay</b><span>Waiting for the first matchup.</span>';
    }
    const lower=document.getElementById('gcLowerThirdGameday');
    if(lower){
      lower.innerHTML=b&&p?`<span>NOW BATTING</span><b>#${N(b.jersey_number,24)} ${esc(b.name)}</b><small>${esc(liveHitterLine(batterId))} • vs ${esc(p.name||'Pitcher')}</small>`:'';
      lower.classList.toggle('show',!!(b&&p));
    }
    updateQueue();
  }
  function nextBatters(){
    const out=[];
    for(let i=Math.max(0,N(gi));i<evs().length&&out.length<2;i++){
      const e=evs()[i];
      if(e?.type==='PA_START'&&e.batter_id){
        const last=out[out.length-1];
        if(!last||N(last.batter_id)!==N(e.batter_id))out.push(e);
      }
    }
    return out;
  }
  function updateQueue(){
    const el=document.getElementById('gcOnDeckGameday');if(!el)return;
    const q=nextBatters();
    if(!q.length){el.innerHTML='<div class="gcQueueEmptyGameday">No upcoming hitter queued.</div>';return}
    el.innerHTML=q.map((e,i)=>{
      const p=player(e.batter_id);
      return `<div class="gcQueueRowGameday"><span>${i===0?'ON DECK':'IN HOLE'}</span><b>${p?`#${N(p.jersey_number,24)} ${esc(p.name)}`:'Next hitter'}</b></div>`;
    }).join('');
  }
  function locationLabel(e){
    const x=N(e?.px,.5),z=N(e?.pz,.5);
    const horiz=x<.34?'inside':x>.66?'away':'middle';
    const vert=z<.34?'low':z>.66?'up':'mid-height';
    return horiz==='middle'&&vert==='mid-height'?'heart of the zone':`${vert} and ${horiz}`;
  }
  function clearResult(){
    const el=document.getElementById('gcResultGameday');if(el){el.textContent='';el.className='gcResultGameday'}
  }
  function showResult(text,big=false){
    const el=document.getElementById('gcResultGameday');if(!el)return;
    el.textContent=text;el.className='gcResultGameday show'+(big?' big':'');
    clearTimeout(window.__gc134Result);
    window.__gc134Result=setTimeout(()=>{if(el)el.className='gcResultGameday'},1900);
  }
  function resetPitchVisual(){
    const stage=document.getElementById('gcVisualStageGameday');if(stage)stage.classList.remove('inPlay');
    const z=document.getElementById('gcZoneDotsGameday');if(z)z.innerHTML='';
    const rail=document.getElementById('gcPitchRailGameday');
    if(rail)rail.innerHTML='<div class="muted gcWaitingGameday">This at-bat is about to begin.</div>';
    const pc=document.getElementById('gcPitchCallGameday');
    if(pc)pc.innerHTML='<b>Waiting for first pitch</b><span>Pitch type, velocity, location and call will appear here.</span>';
    const f=document.querySelectorAll('.gcFielderGameday.active');f.forEach(x=>x.classList.remove('active'));
    const fr=document.getElementById('gcFieldReadoutGameday');if(fr)fr.textContent='Ball-in-play tracking';
    clearResult();
  }
  function pitchXY(e){
    return {
      x:Math.max(6,Math.min(94,8+N(e?.px,.5)*84)),
      y:Math.max(5,Math.min(95,8+(1-N(e?.pz,.5))*84))
    };
  }
  function renderPitchRow(e){
    const rail=document.getElementById('gcPitchRailGameday'),dots=document.getElementById('gcZoneDotsGameday');
    const counter=document.getElementById('gcPitchCountGameday'),pc=document.getElementById('gcPitchCallGameday');
    const num=N(e.pitch_no,GC_STATE.pitch_no+1),cls=callClass(e.call),xy=pitchXY(e);
    if(rail){
      if(num===1)rail.innerHTML='';
      const row=document.createElement('div');row.className='gcPitchRowGameday';
      row.innerHTML=`<span class="gcPitchNumGameday ${cls}">${num}</span><span><b>${esc(pitchCode(e.pitch_type))} • ${esc(e.call)}</b><small>${esc(e.pitch_type)} • ${esc(locationLabel(e))}</small></span><span class="gcPitchVelGameday">${N(e.velocity).toFixed(1)} MPH</span>`;
      rail.prepend(row);
    }
    if(counter)counter.textContent=`${num} PITCH${num===1?'':'ES'}`;
    if(dots){
      const q=document.createElement('div');q.className=`gcPitchDotGameday ${cls}`;
      q.style.left=xy.x+'%';q.style.top=xy.y+'%';q.textContent=num;dots.appendChild(q);
    }
    if(pc)pc.innerHTML=`<b>${esc(e.pitch_type)} • ${N(e.velocity).toFixed(1)} MPH</b><span>${esc(e.call)} • ${esc(locationLabel(e))} • Count ${N(e.balls)}-${N(e.strikes)}</span>`;
    return xy;
  }
  function animatePitch(e,x,y){
    const stage=document.getElementById('gcVisualStageGameday'),canvas=document.getElementById('gcZoneCanvasGameday');
    if(!stage||!canvas)return;
    const sr=stage.getBoundingClientRect(),zr=canvas.getBoundingClientRect(),b=document.createElement('i');
    b.className='gcLiveBallGameday';stage.appendChild(b);
    const sx=sr.width*.5,sy=sr.height*.34;
    const tx=(zr.left-sr.left)+(x/100)*zr.width,ty=(zr.top-sr.top)+(y/100)*zr.height;
    const t=String(e?.pitch_type||'').toLowerCase();
    const throws=String(player(e?.pitcher_id)?.throws||'R').toUpperCase(),hand=throws==='L'?-1:1;
    let dx=0,dy=0;
    if(t.includes('slider')){dx=24*hand;dy=5}
    else if(t.includes('curve')){dx=8*hand;dy=28}
    else if(t.includes('sinker')){dx=10*hand;dy=18}
    else if(t.includes('change')){dx=7*hand;dy=14}
    else if(t.includes('four')||t.includes('fast')){dy=-7}
    const mx=(sx+tx)/2+dx,my=(sy+ty)/2+dy;
    if(typeof b.animate==='function'){
      const anim=b.animate([
        {left:sx+'px',top:sy+'px',transform:'translate(-50%,-50%) scale(.78)'},
        {left:mx+'px',top:my+'px',transform:'translate(-50%,-50%) scale(.92)',offset:.56},
        {left:tx+'px',top:ty+'px',transform:'translate(-50%,-50%) scale(1.05)'}
      ],{duration:560,easing:'cubic-bezier(.25,.64,.34,1)',fill:'forwards'});
      anim.onfinish=()=>b.remove();
    }else{
      b.style.left=tx+'px';b.style.top=ty+'px';setTimeout(()=>b.remove(),600);
    }
  }
  function addPitch(e,silent=false){
    GC_STATE.pitch_no=N(e.pitch_no,GC_STATE.pitch_no+1);
    GC_STATE.last_pitch=e;
    if(!silent){const xy=renderPitchRow(e);animatePitch(e,xy.x,xy.y)}
  }
  const FIELDER_POS={
    LF:[145,135],CF:[300,75],RF:[455,135],
    SS:[215,220],'2B':[385,220],'3B':[180,270],'1B':[420,270],
    P:[300,282],C:[300,354]
  };
  const BASE_POS={0:[300,382],1:[441,230],2:[300,125],3:[159,230],4:[300,382]};
  function fielderSvg(){
    return Object.entries(FIELDER_POS).map(([pos,[x,y]])=>
      `<g class="gcFielderGameday" data-pos="${pos}" transform="translate(${x} ${y})"><circle r="13"></circle><text y="4" text-anchor="middle">${pos}</text></g>`
    ).join('');
  }
  function setRunnerStatic(base,pid){
    const g=document.getElementById('gcRunnerMarkerGameday');if(!g)return;
    if(g.classList.contains('moving'))return;
    const b=N(base,0),pt=BASE_POS[b]||BASE_POS[0],p=player(pid);
    g.setAttribute('transform',`translate(${pt[0]} ${pt[1]})`);
    g.classList.toggle('show',!!pid&&b>0);
    const t=g.querySelector('text');if(t)t.textContent=p?.jersey_number?String(N(p.jersey_number)).slice(-2):'R';
  }
  function runnerPath(fromBase,toBase,fullCircuit=false){
    const from=BASE_POS[N(fromBase,0)]||BASE_POS[0];
    if(fullCircuit){
      const b1=BASE_POS[1],b2=BASE_POS[2],b3=BASE_POS[3],h=BASE_POS[4];
      return `M${from[0]} ${from[1]} L${b1[0]} ${b1[1]} L${b2[0]} ${b2[1]} L${b3[0]} ${b3[1]} L${h[0]} ${h[1]}`;
    }
    const to=BASE_POS[N(toBase,0)]||BASE_POS[0];
    return `M${from[0]} ${from[1]} L${to[0]} ${to[1]}`;
  }
  function animateRunner(fromBase,toBase,pid,opts={}){
    const svg=document.getElementById('gcFieldSvgGameday'),g=document.getElementById('gcRunnerMarkerGameday');
    if(!svg||!g||!pid)return;
    const full=!!opts.fullCircuit,path=runnerPath(fromBase,toBase,full),end=BASE_POS[full?4:N(toBase,0)]||BASE_POS[0];
    const p=player(pid),t=g.querySelector('text');if(t)t.textContent=p?.jersey_number?String(N(p.jersey_number)).slice(-2):'R';
    g.innerHTML=`<circle r="14"></circle><circle class="pulse" r="20"></circle><text y="4" text-anchor="middle">${p?.jersey_number?String(N(p.jersey_number)).slice(-2):'R'}</text>`;
    g.classList.add('show','moving');
    g.setAttribute('transform','translate(0 0)');
    const ns='http://www.w3.org/2000/svg',am=document.createElementNS(ns,'animateMotion');
    am.setAttribute('dur',full?'1.65s':(opts.fast?'.55s':'.82s'));am.setAttribute('path',path);am.setAttribute('fill','freeze');
    g.appendChild(am);
    try{am.beginElement()}catch(_){}
    setTimeout(()=>{
      if(!g.isConnected)return;
      g.querySelectorAll('animateMotion').forEach(x=>x.remove());
      g.setAttribute('transform',`translate(${end[0]} ${end[1]})`);
      g.classList.remove('moving');
      if(opts.removeAfter)setTimeout(()=>g.classList.remove('show'),280);
    },full?1680:(opts.fast?580:850));
  }
  function flashBase(base){
    const el=document.querySelector(`.gcFieldBaseGameday[data-base="${N(base)}"]`);
    if(!el)return;el.classList.remove('flash');void el.getBBox?.();el.classList.add('flash');setTimeout(()=>el.classList.remove('flash'),650);
  }
  function throwTargetFor(e){
    const out=String(e?.out_type||'').toLowerCase(),note=String(e?.defensive_note||'').toUpperCase();
    if(note==='HELD_TO_SINGLE')return '2B';
    if(out.includes('ground'))return '1B';
    if(e?.first_base_id&&N(e.putout_id)===N(e.first_base_id))return '1B';
    const po=player(e?.putout_id);
    const pos=String(po?.primary_pos||'').toUpperCase();
    return FIELDER_POS[pos]?pos:'';
  }
  function animateThrow(fromPos,toPos,label='THROW'){
    const a=FIELDER_POS[String(fromPos||'').toUpperCase()],b=FIELDER_POS[String(toPos||'').toUpperCase()]||BASE_POS[N(toPos,0)];
    const path=document.getElementById('gcThrowPathGameday'),ball=document.getElementById('gcThrowBallGameday');
    if(!a||!b||!path||!ball)return;
    const d=`M${a[0]} ${a[1]} Q${((a[0]+b[0])/2).toFixed(1)} ${Math.min(a[1],b[1])-32} ${b[0]} ${b[1]}`;
    path.setAttribute('d',d);path.classList.add('show');
    ball.innerHTML='';ball.setAttribute('cx','0');ball.setAttribute('cy','0');ball.classList.add('show');
    const ns='http://www.w3.org/2000/svg',am=document.createElementNS(ns,'animateMotion');
    am.setAttribute('dur','.48s');am.setAttribute('path',d);am.setAttribute('fill','freeze');ball.appendChild(am);try{am.beginElement()}catch(_){}
    const readout=document.getElementById('gcFieldReadoutGameday');if(readout)readout.textContent=label;
    setTimeout(()=>{path.classList.remove('show');ball.classList.remove('show');ball.innerHTML=''},620);
  }
  function catchPulse(pos){
    const p=FIELDER_POS[String(pos||'').toUpperCase()];if(!p)return;
    const ring=document.getElementById('gcCatchRingGameday');if(!ring)return;
    ring.setAttribute('cx',p[0]);ring.setAttribute('cy',p[1]);ring.classList.remove('pop');void ring.getBBox?.();ring.classList.add('pop');
    setTimeout(()=>ring.classList.remove('pop'),650);
  }
  function animateDefensivePlay(e){
    const pos=String(e?.fielder_position||'').toUpperCase(),result=String(e?.result||'').toUpperCase(),out=String(e?.out_type||'').toLowerCase();
    if(!pos)return;
    if(result==='OUT'){
      if(out.includes('ground')){
        setTimeout(()=>animateThrow(pos,throwTargetFor(e)||'1B',`${pos} to first • ${e.out_type||'Groundout'}`),430);
      }else setTimeout(()=>catchPulse(pos),420);
    }else if(String(e?.defensive_note||'').toUpperCase()==='HELD_TO_SINGLE'){
      setTimeout(()=>animateThrow(pos,'2B',`${pos} fires it in • runner held`),500);
    }
  }
  function fielderFocus(e){
    document.querySelectorAll('.gcFielderGameday.active').forEach(x=>x.classList.remove('active'));
    const pos=String(e?.fielder_position||'').toUpperCase().replace(/[^A-Z0-9]/g,'');
    if(pos){
      const el=document.querySelector(`.gcFielderGameday[data-pos="${pos}"]`);if(el)el.classList.add('active');
    }
    const readout=document.getElementById('gcFieldReadoutGameday');
    if(readout){
      const f=player(e?.fielder_id),who=f?`#${N(f.jersey_number,24)} ${f.name}`:(pos||'Defense');
      readout.textContent=`${who}${e?.defensive_note?` • ${e.defensive_note}`:''}`;
    }
  }
  function showBallInPlay(e,silent=false){
    GC_STATE.lastBip=e;
    const stage=document.getElementById('gcVisualStageGameday');if(stage)stage.classList.add('inPlay');
    const result=String(e.result||'').toUpperCase(),ev=N(e.exit_velocity,90),la=N(e.launch_angle,10),angle=N(e.spray_angle);
    const pc=document.getElementById('gcPitchCallGameday');
    if(pc)pc.innerHTML=`<b>${esc(result||'BALL IN PLAY')}</b><span>${ev.toFixed(1)} MPH EV • ${la.toFixed(1)}° LA • ${esc(e.contact_quality||'Contact')}</span>`;
    let depth=160;
    if(result==='HR')depth=38;else if(result==='3B')depth=72;else if(result==='2B')depth=102;
    else if(result==='1B'||result==='ROE')depth=145;
    else depth=Math.max(74,170-Math.max(0,ev-80)*1.25-Math.max(0,la)*.72);
    const x=Math.max(88,Math.min(512,300+angle*4.65)),y=Math.max(34,Math.min(220,depth));
    const midX=300+(x-300)*.46,arc=Math.min(120,34+Math.max(0,la)*2.1),midY=Math.max(42,382-(382-y)*.5-arc);
    const d=`M300 382 Q${midX.toFixed(1)} ${midY.toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)}`;
    const path=document.getElementById('gcTrajGameday'),ball=document.getElementById('gcFieldBallGameday');
    if(path)path.setAttribute('d',d);
    if(ball){
      ball.innerHTML='';
      if(!silent){
        ball.setAttribute('cx','0');ball.setAttribute('cy','0');
        const ns='http://www.w3.org/2000/svg',am=document.createElementNS(ns,'animateMotion');
        am.setAttribute('dur','.72s');am.setAttribute('path',d);am.setAttribute('fill','freeze');
        ball.appendChild(am);try{am.beginElement()}catch(_){}
        setTimeout(()=>{if(ball.isConnected){ball.innerHTML='';ball.setAttribute('cx',x);ball.setAttribute('cy',y)}},740);
      }else{
        ball.setAttribute('cx',x);ball.setAttribute('cy',y);
      }
    }
    fielderFocus(e);
    if(!silent){
      animateDefensivePlay(e);
      showResult(result==='OUT'?String(e.out_type||'BALL IN PLAY'):result,result==='HR');
    }
  }
  function updateLiveStats(e){
    if(!e)return;
    if(e.type==='PITCH'&&e.pitcher_id)livePitcher(e.pitcher_id).P++;
    if(e.type==='OUT'&&e.pitcher_id){
      const p=livePitcher(e.pitcher_id);p.OUTS++;
      if(String(e.out_type||'').toLowerCase().includes('strikeout'))p.SO++;
    }
    if(e.type==='PA_END'&&e.batter_id){
      const h=liveHitter(e.batter_id),r=String(e.result||'').toUpperCase();
      const hit=['1B','2B','3B','HR'].includes(r);
      if(r==='BB')h.BB++;else h.AB++;
      if(hit)h.H++;
      if(r==='HR')h.HR++;
      if(r==='K'||r==='SO'||r==='STRIKEOUT')h.SO++;
      if(e.pitcher_id){
        const p=livePitcher(e.pitcher_id);
        if(hit)p.H++;
        if(r==='BB')p.BB++;
      }
    }
    if(e.type==='RUN'){
      if(e.batter_id)liveHitter(e.batter_id).RBI+=Math.max(1,N(e.runs,1));
      if(e.runner_id)liveHitter(e.runner_id).R+=Math.max(1,N(e.runs,1));
    }
  }
  function managerEvent(e,silent=false){
    const el=document.getElementById('gcStrategyLive');if(!el)return;
    let text='';
    if(e.type==='PITCHING_CHANGE'){
      const p=player(e.pitcher_id);text=`${teamLabel(e.team)} • ${e.role||'RP'} ${p?`#${N(p.jersey_number,24)} ${p.name}`:'enters'}`;
    }else if(e.type==='DEFENSIVE_SHIFT')text=`${teamLabel(e.team)} • ${String(e.mode||'STANDARD').replaceAll('_',' ')} alignment`;
    else if(e.type==='BUNT_ATTEMPT')text=`Offensive call • Bunt ${e.success?'executed':'attempted'}`;
    else if(e.type==='STEAL_ATTEMPT')text=`Baserunning call • Steal attempt ${e.success?'successful':'unsuccessful'}`;
    else if(e.type==='PICKOFF')text='Pickoff move • Runner erased';
    if(!text)return;
    el.innerHTML=`<span>MANAGER DECISION</span><b>${esc(text)}</b>`;
    if(!silent){el.classList.remove('pulse');void el.offsetWidth;el.classList.add('pulse')}
  }
  function feedEvent(e){
    const feed=document.getElementById('gcFeedGameday');if(!feed)return;
    const d=document.createElement('div');
    let strategy=false;try{strategy=typeof gcStrategyClass==='function'&&gcStrategyClass(e)}catch(_){}
    d.className='gcFeedPlayGameday'+(strategy?' strategy':'');
    d.innerHTML=`<span class="gcFeedTagGameday">${esc(e?.inning?inningLabel(e):String(e?.type||'PLAY').replaceAll('_',' '))}</span><span>${esc(safeDescribe(e))}</span>`;
    feed.prepend(d);while(feed.children.length>24)feed.removeChild(feed.lastChild);
  }
  function latestFeed(targetCount){
    const feed=document.getElementById('gcFeedGameday');if(!feed)return;
    feed.innerHTML='';
    const start=Math.max(0,targetCount-12);
    for(let i=start;i<targetCount;i++)feedEvent(evs()[i]);
  }
  function spotlightHtml(pid){
    const p=player(pid);
    return p?`<div class="gcSpotlightArtGameday">${art(p,'portrait')}</div>`:'<div class="gcSpotlightArtGameday"></div>';
  }
  function showSpotlight(title,pid,subtitle,kind='moment'){
    const host=document.getElementById('gcSpotlightGameday');if(!host)return;
    const p=player(pid),fid=p?.franchise_id||'',mark=fid?teamMark(fid,true):'';
    host.className=`gcSpotlightGameday show ${kind}`;
    host.innerHTML=`<div class="gcSpotlightFrameGameday"><div class="gcSpotlightRibbonGameday"><span>EBL GAMEDAY</span><b>REPLAY MOMENT</b></div><div class="gcSpotlightInnerGameday">${spotlightHtml(pid)}<div class="gcSpotlightCopyGameday"><div class="gcSpotlightTeamGameday">${mark}<span>${esc(fid?teamLabel(fid):'ELITE BASEBALL LEAGUE')}</span></div><strong>${esc(title)}</strong><b>${esc(subtitle||'')}</b><small>${esc(`${GC_STATE.half==='BOT'?'Bottom':'Top'} ${GC_STATE.inning||1} • ${GC_STATE.score?.[0]??0}-${GC_STATE.score?.[1]??0}`)}</small></div></div></div>`;
    const wasPlaying=!!GC_STATE.isPlaying,speed=N(GC_STATE.playSpeed,850);
    if(wasPlaying){clearInterval(timer);GC_STATE.isPlaying=false}
    clearTimeout(window.__gc134Spotlight);clearTimeout(GC_STATE.broadcastHold);
    window.__gc134Spotlight=setTimeout(()=>{if(host)host.className='gcSpotlightGameday'},2050);
    if(wasPlaying)GC_STATE.broadcastHold=setTimeout(()=>window.gcPlayGameday(speed),1750);
  }
  function updateAtmosphere(e){
    const stage=document.getElementById('gcVisualStageGameday'),meter=document.getElementById('gcCrowdMeterGameday'),tag=document.getElementById('gcBroadcastSituationGameday');
    const diff=Math.abs(N(GC_STATE.score?.[0])-N(GC_STATE.score?.[1]));
    const baseline=12+Math.min(27,N(GC_STATE.inning,1)*3)+(diff<=1?16:diff<=3?7:0)+(GC_STATE.runner?9:0);
    let energy=e?baseline:Math.max(baseline,N(GC_STATE.crowdEnergy,baseline)*.93);
    const type=String(e?.type||'');
    if(type==='PITCH'&&N(e?.strikes)===2)energy+=9;
    if(['RUN','GREAT_PLAY','STEAL_ATTEMPT','PICKOFF','FIELDING_COLLISION'].includes(type))energy+=24;
    if(type==='BALL_IN_PLAY'&&String(e?.result||'').toUpperCase()==='HR')energy=100;
    if(type==='GAME_END')energy=100;
    energy=Math.max(8,Math.min(100,energy));
    GC_STATE.crowdEnergy=energy;
    if(stage){stage.style.setProperty('--gc-crowd',String(energy/100));stage.classList.toggle('crowdRoar',energy>=72);stage.classList.toggle('lateClose',N(GC_STATE.inning)>=7&&diff<=1)}
    if(meter){
      meter.querySelectorAll('i').forEach((bar,i)=>bar.classList.toggle('on',i<Math.ceil(energy/20)));
      meter.title=`Crowd energy ${energy}%`;
    }
    if(tag){
      let txt='EARLY INNING';
      if(N(gi)>=evs().length)txt='FINAL';
      else if(N(GC_STATE.inning)>=7&&diff<=1)txt='LATE & CLOSE';
      else if(GC_STATE.runner)txt='RUNNER ABOARD';
      else if(N(GC_STATE.strikes)===2)txt='TWO-STRIKE COUNT';
      tag.textContent=txt;
    }
  }
  function showFieldForRunner(ms=1050){
    const stage=document.getElementById('gcVisualStageGameday');if(!stage)return;
    stage.classList.add('inPlay','runnerFocus');
    clearTimeout(window.__gc135FieldReturn);
    window.__gc135FieldReturn=setTimeout(()=>stage.classList.remove('runnerFocus'),ms);
  }
  function paIndexes(){const a=[];evs().forEach((e,i)=>{if(e?.type==='PA_START')a.push(i)});return a}
  function updateTimeline(){
    const range=document.getElementById('gcTimelineRangeGameday'),label=document.getElementById('gcTimelineLabelGameday');
    const total=evs().length,done=Math.max(0,Math.min(total,N(gi)));
    if(range){range.max=String(total);range.value=String(done)}
    if(label)label.textContent=`${done} / ${total}`;
    const status=document.getElementById('gcReplayStatusGameday');
    if(status)status.textContent=done>=total?'FINAL':`${GC_STATE.half==='BOT'?'BOT':'TOP'} ${GC_STATE.inning||1}`;
  }
  window.gcUpdateScoreboard=function(){
    const a=document.getElementById('gcAwayScore'),h=document.getElementById('gcHomeScore'),
          inn=document.getElementById('gcInning'),cnt=document.getElementById('gcCount');
    if(a)a.textContent=GC_STATE.score?.[0]??0;
    if(h)h.textContent=GC_STATE.score?.[1]??0;
    if(inn)inn.textContent=`${GC_STATE.half==='BOT'?'BOT':'TOP'} ${GC_STATE.inning||1}`;
    if(cnt)cnt.textContent=`${GC_STATE.balls||0}-${GC_STATE.strikes||0} • ${GC_STATE.outs||0} OUT${GC_STATE.outs===1?'':'S'}`;
    ['1','2','3'].forEach(n=>{const b=document.getElementById('gcB'+n);if(b)b.classList.toggle('on',N(n)===N(GC_STATE.base)&&!!GC_STATE.runner)});
    setRunnerStatic(GC_STATE.runnerVisualBase||GC_STATE.base,GC_STATE.runner);
    updateTimeline();updateQueue();updateAtmosphere();
  };
  function applyMeta(e){
    if(e?.score)GC_STATE.score=[N(e.score[0]),N(e.score[1])];
    if(e?.final_score)GC_STATE.score=[N(e.final_score[0]),N(e.final_score[1])];
    if(e?.inning)GC_STATE.inning=N(e.inning,1);
    if(e?.half&&['TOP','BOT'].includes(String(e.half).toUpperCase()))GC_STATE.half=String(e.half).toUpperCase();
    if(Number.isFinite(Number(e?.outs)))GC_STATE.outs=N(e.outs);
  }
  function processEvent(e,silent=false,index=-1){
    if(!e)return;
    applyMeta(e);updateLiveStats(e);
    if(!silent)feedEvent(e);
    if(e.type==='PA_START'){
      GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.pitch_no=0;
      GC_STATE.outs=N(e.outs,GC_STATE.outs);GC_STATE.batter_id=e.batter_id;GC_STATE.pitcher_id=e.pitcher_id;GC_STATE.current_pa_start=index;
      if(!silent){resetPitchVisual();updateMatchup(e.batter_id,e.pitcher_id)}
    }
    if(e.type==='PITCH'){
      GC_STATE.balls=N(e.balls);GC_STATE.strikes=N(e.strikes);addPitch(e,silent);
    }
    if(e.type==='BALL_IN_PLAY'&&!silent)showBallInPlay(e,false);
    if(e.type==='PA_END'){
      const r=String(e.result||'').toUpperCase(),post=GC_STATE.postPaRunnerEvent;
      let dest=0,animateReach=true;
      if(post&&N(post.pid)===N(e.batter_id)){
        animateReach=false;
        if(post.alive){GC_STATE.runner=e.batter_id;GC_STATE.base=N(post.base,1);GC_STATE.runnerVisualBase=N(post.base,1);dest=N(post.base,1)}
        else{GC_STATE.runner=null;GC_STATE.base=0;GC_STATE.runnerVisualBase=0}
        GC_STATE.postPaRunnerEvent=null;
      }else{
        if(['1B','ROE'].includes(r)){GC_STATE.runner=e.batter_id;GC_STATE.base=1;dest=1}
        else if(r==='BB'&&!GC_STATE.runner){GC_STATE.runner=e.batter_id;GC_STATE.base=1;dest=1}
        else if(r==='2B'){GC_STATE.runner=e.batter_id;GC_STATE.base=2;dest=2}
        else if(r==='3B'){GC_STATE.runner=e.batter_id;GC_STATE.base=3;dest=3}
        else if(r==='HR'){GC_STATE.runner=null;GC_STATE.base=0;GC_STATE.runnerVisualBase=0}
      }
      if(dest&&animateReach){
        if(!silent){
          if(r==='BB')showFieldForRunner();
          setTimeout(()=>{animateRunner(0,dest,e.batter_id,{fast:r==='BB'});flashBase(dest)},r==='BB'?120:380);
        }
        GC_STATE.runnerVisualBase=dest;
      }
      if(!silent)updateMatchup(GC_STATE.batter_id,GC_STATE.pitcher_id);
    }
    if(e.type==='STEAL_ATTEMPT'){
      const rid=e.runner_id||GC_STATE.runner;
      const reach=String(GC_STATE.lastBip?.result||'').toUpperCase();
      const inferred=(N(rid)===N(GC_STATE.batter_id)?({'1B':1,'ROE':1,'2B':2,'3B':3}[reach]||0):0);
      const from=Math.max(1,N(GC_STATE.base||GC_STATE.runnerVisualBase||inferred,1)),to=Math.min(3,from+1);
      if(e.success){
        GC_STATE.runner=rid;GC_STATE.base=to;GC_STATE.runnerVisualBase=to;
        GC_STATE.postPaRunnerEvent={pid:rid,base:to,alive:true};
      }else{
        GC_STATE.postPaRunnerEvent={pid:rid,base:0,alive:false};
      }
      if(!silent){
        showFieldForRunner(1400);managerEvent(e);
        animateRunner(from,e.success?to:from,rid,{fast:true,removeAfter:!e.success});
        if(e.success){flashBase(to);showResult('STOLEN BASE',true)}
        else showResult('CAUGHT STEALING',true);
      }
    }
    if(e.type==='PICKOFF'||(e.type==='OUT'&&String(e.out_type||'').toLowerCase()==='caught stealing')){
      const rid=e.runner_id||GC_STATE.runner;
      const reach=String(GC_STATE.lastBip?.result||'').toUpperCase(),inferred=(N(rid)===N(GC_STATE.batter_id)?({'1B':1,'ROE':1,'2B':2,'3B':3}[reach]||0):0);
      const from=Math.max(1,N(GC_STATE.base||GC_STATE.runnerVisualBase||inferred,1));
      if(!silent){showFieldForRunner(1200);animateRunner(from,from,rid,{fast:true,removeAfter:true});managerEvent(e);showResult(e.type==='PICKOFF'?'PICKED OFF':'CAUGHT STEALING',true)}
      GC_STATE.postPaRunnerEvent={pid:rid,base:0,alive:false};
      GC_STATE.runner=null;GC_STATE.base=0;GC_STATE.runnerVisualBase=0;
    }
    if(e.type==='RUN'){
      const existing=GC_STATE.runner,rid=e.runner_id||e.batter_id||existing,wasBase=Math.max(1,N(GC_STATE.runnerVisualBase||GC_STATE.base,1));
      const hr=String(GC_STATE.lastBip?.result||'').toUpperCase()==='HR'&&N(e.batter_id)===N(GC_STATE.batter_id);
      if(!silent){
        showFieldForRunner(hr?2300:1250);
        if(hr&&N(e.runs,1)>1&&existing&&N(existing)!==N(e.batter_id)){
          animateRunner(wasBase,4,existing,{fast:true,removeAfter:true});
          setTimeout(()=>animateRunner(0,4,e.batter_id,{fullCircuit:true}),620);
        }else if(hr)animateRunner(0,4,rid,{fullCircuit:true});
        else animateRunner(wasBase,4,rid,{});
        flashBase(4);
        showResult(N(e.runs,1)>1?`${N(e.runs,1)} RUNS SCORE`:'RUN SCORES',true);
      }
      GC_STATE.runner=null;GC_STATE.base=0;GC_STATE.runnerVisualBase=0;
    }
    if(['PITCHING_CHANGE','DEFENSIVE_SHIFT','BUNT_ATTEMPT'].includes(e.type)){
      if(!silent)managerEvent(e);
      if(e.type==='PITCHING_CHANGE'&&e.pitcher_id)GC_STATE.pitcher_id=e.pitcher_id;
    }
    if(['GREAT_PLAY','OUTFIELD_HOLD','FIELDING_ERROR','FIELDING_COLLISION'].includes(e.type))GC_STATE.lastDefenseEvent=e;
    if(!silent&&e.type==='BALL_IN_PLAY'&&String(e.result||'').toUpperCase()==='HR'){
      showSpotlight('HOME RUN',e.batter_id,`${N(e.exit_velocity).toFixed(1)} MPH • ${N(e.launch_angle).toFixed(0)}°`,'home-run');
    }
    if(!silent&&e.type==='OUT'&&String(e.out_type||'').toLowerCase().includes('strikeout')){
      showResult('STRIKEOUT',true);showSpotlight('STRIKEOUT',e.pitcher_id,livePitcherLine(e.pitcher_id),'strikeout');
    }
    if(!silent&&e.type==='GREAT_PLAY'){
      showResult('GREAT PLAY',true);showSpotlight('GREAT PLAY',e.fielder_id,e.defensive_note||e.fielder_position||'Run-saving defense','defense');
    }
    if(!silent&&e.type==='PITCHING_CHANGE'){
      showSpotlight('PITCHING CHANGE',e.pitcher_id,`${teamLabel(e.team)} • ${e.role||'Reliever'}`,'pitching-change');
    }
    if(!silent&&e.type==='FIELDING_ERROR')showResult('ERROR',true);
    if(!silent&&e.type==='OUTFIELD_HOLD')showResult('STRONG THROW');
    if(e.type==='INNING_END'){GC_STATE.outs=0;GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.runner=null;GC_STATE.base=0}
    if(e.type==='GAME_END'&&!silent){showResult('FINAL',true);clearInterval(timer);GC_STATE.isPlaying=false}
    if(!silent)updateAtmosphere(e);
  }
  function renderCurrentSnapshot(targetCount){
    resetPitchVisual();
    updateMatchup(GC_STATE.batter_id,GC_STATE.pitcher_id);
    const start=Math.max(0,N(GC_STATE.current_pa_start,0));
    let bip=null,lastManager=null;
    for(let i=start;i<targetCount;i++){
      const e=evs()[i];
      if(e?.type==='PITCH')renderPitchRow(e);
      if(e?.type==='BALL_IN_PLAY')bip=e;
      if(['PITCHING_CHANGE','DEFENSIVE_SHIFT','BUNT_ATTEMPT','STEAL_ATTEMPT','PICKOFF'].includes(e?.type))lastManager=e;
    }
    if(bip)showBallInPlay(bip,true);
    if(lastManager)managerEvent(lastManager,true);
    latestFeed(targetCount);gcUpdateScoreboard();
  }
  window.gcSeekEventGameday=function(target){
    clearInterval(timer);GC_STATE.isPlaying=false;clearTimeout(GC_STATE.broadcastHold);
    const total=evs().length,count=Math.max(0,Math.min(total,Math.round(N(target))));
    resetState();gi=0;
    for(let i=0;i<count;i++){processEvent(evs()[i],true,i);gi=i+1}
    renderCurrentSnapshot(count);
  };
  window.gcSeekEndGameday=function(){window.gcSeekEventGameday(evs().length)};
  window.gcReplayGameday=function(){window.gcSeekEventGameday(0);window.gcPlayGameday(850)};
  window.gcSeekPaGameday=function(direction=1){
    const list=paIndexes();if(!list.length)return;
    const cur=N(GC_STATE.current_pa_start,-1);let target;
    if(N(direction)>=0)target=list.find(x=>x>cur);
    else{
      const prior=list.filter(x=>x<cur);
      target=prior.length?prior[prior.length-1]:list[0];
    }
    if(target===undefined)target=N(direction)>=0?list[list.length-1]:list[0];
    window.gcSeekEventGameday(target+1);
  };
  window.gcPlayGameday=function(ms=850){
    clearInterval(timer);clearTimeout(GC_STATE.broadcastHold);
    GC_STATE.playSpeed=Math.max(120,N(ms,850));GC_STATE.isPlaying=true;
    timer=setInterval(window.step,GC_STATE.playSpeed);
    const b=document.getElementById('gcReplayStatusGameday');if(b)b.classList.add('playing');
  };
  window.gcPauseGameday=function(){
    clearInterval(timer);clearTimeout(GC_STATE.broadcastHold);GC_STATE.isPlaying=false;
    const b=document.getElementById('gcReplayStatusGameday');if(b)b.classList.remove('playing');
  };
  window.step=function(){
    const all=evs();
    if(gi>=all.length){clearInterval(timer);GC_STATE.isPlaying=false;updateTimeline();return}
    const index=gi,e=all[gi++];
    processEvent(e,false,index);gcUpdateScoreboard();
  };

  function fieldSvg(){
    return `<svg id="gcFieldSvgGameday" viewBox="0 0 600 420" preserveAspectRatio="none" aria-label="Ball in play field view">
      <defs><filter id="gcGlow135" x="-80%" y="-80%" width="260%" height="260%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
      <path d="M300 390 L65 120 L300 28 L535 120 Z" fill="#2f6b3d" stroke="#e7e5d7" stroke-width="3"/>
      <path d="M300 390 L158 230 L300 125 L442 230 Z" fill="#9d7348" stroke="#e7d1ad" stroke-width="2"/>
      <path d="M300 390 L300 125 M300 390 L65 120 M300 390 L535 120" fill="none" stroke="#f4f4ea" stroke-width="2" opacity=".72"/>
      <rect class="gcFieldBaseGameday" data-base="4" x="294" y="378" width="13" height="13" transform="rotate(45 300 384)" fill="#fff"/>
      <rect class="gcFieldBaseGameday" data-base="1" x="435" y="224" width="12" height="12" transform="rotate(45 441 230)" fill="#fff"/>
      <rect class="gcFieldBaseGameday" data-base="2" x="294" y="119" width="12" height="12" transform="rotate(45 300 125)" fill="#fff"/>
      <rect class="gcFieldBaseGameday" data-base="3" x="153" y="224" width="12" height="12" transform="rotate(45 159 230)" fill="#fff"/>
      ${fielderSvg()}
      <path id="gcTrajGameday" class="gcTrajGameday" d="M300 382 Q300 250 300 160"/>
      <circle id="gcFieldBallGameday" class="gcFieldBallGameday" cx="300" cy="160" r="7"/>
      <path id="gcThrowPathGameday" class="gcThrowPathGameday" d=""/>
      <circle id="gcThrowBallGameday" class="gcThrowBallGameday" cx="0" cy="0" r="6"/>
      <circle id="gcCatchRingGameday" class="gcCatchRingGameday" cx="300" cy="210" r="18"/>
      <g id="gcRunnerMarkerGameday" class="gcRunnerMarkerGameday" transform="translate(300 382)"><circle r="14"></circle><circle class="pulse" r="20"></circle><text y="4" text-anchor="middle">R</text></g>
    </svg><div id="gcFieldReadoutGameday" class="gcFieldReadoutGameday">Ball-in-play tracking</div>`;
  }
  window.renderGamecast=function(){
    clearInterval(timer);resetState();gi=0;
    const host=document.getElementById('gameView');if(!host)return;
    host.innerHTML=`<div id="gcSpotlightGameday" class="gcSpotlightGameday"></div>
      <div class="gcReplayGridGameday gcReplayGridRC134">
        <aside class="gcPanelGameday gcPitchPanelGameday">
          <div class="gcPanelHeadGameday"><strong>PITCH SEQUENCE</strong><span id="gcPitchCountGameday">0 PITCHES</span></div>
          <div id="gcPitchRailGameday" class="gcPitchRailGameday"><div class="muted gcWaitingGameday">This at-bat is about to begin.</div></div>
        </aside>
        <section class="gcPanelGameday gcVisualCardGameday">
          <div id="gcVisualStageGameday" class="gcVisualStageGameday gcStadiumRC135">
            <div class="gcBroadcastBugGameday"><span class="live">REPLAY</span><strong>EBL GAMEDAY</strong><span id="gcBroadcastSituationGameday">EARLY INNING</span><div id="gcCrowdMeterGameday" class="gcCrowdMeterGameday" aria-label="Crowd energy"><i></i><i></i><i></i><i></i><i></i></div></div>
            <div class="gcCrowdGlowGameday"></div><div class="gcStandsGameday"></div><div class="gcOutfieldWallGameday"></div><div class="gcMoundGameday"></div>
            <div id="gcPitcherArtGameday" class="gcPitcherArtGameday"></div><div id="gcBatterArtGameday" class="gcBatterArtGameday"></div>
            <div id="gcZoneRigGameday" class="gcZoneRigGameday"><div id="gcZoneCanvasGameday" class="gcZoneCanvasGameday"><div class="gcStrikeZoneGameday"></div><div id="gcZoneDotsGameday"></div></div></div>
            <div id="gcFieldReplayGameday" class="gcFieldReplayGameday">${fieldSvg()}</div>
            <div id="gcResultGameday" class="gcResultGameday"></div>
            <div id="gcLowerThirdGameday" class="gcLowerThirdGameday"></div>
            <div id="gcPitchCallGameday" class="gcPitchCallGameday"><b>Waiting for first pitch</b><span>Pitch type, velocity, location and call will appear here.</span></div>
          </div>
          <div class="gcUnderStageGameday">
            <div id="gcAtBatCopyGameday" class="gcAtBatCopyGameday"><b>Game replay</b><span>Watch the final game unfold pitch by pitch.</span></div>
            <div id="gcReplayStatusGameday" class="gcReplayStatusGameday">TOP 1</div>
            <div class="gcPlaybackGameday">
              <button class="gcMiniBtnGameday primary" data-ebl-action="gamecast-play" data-speed="850">▶ PLAY</button>
              <button class="gcMiniBtnGameday" data-ebl-action="gamecast-pause">Ⅱ PAUSE</button>
              <button class="gcMiniBtnGameday" data-ebl-action="gamecast-play" data-speed="300">FAST</button>
              <button class="gcMiniBtnGameday" data-ebl-action="gamecast-instant">END</button>
              <button class="gcMiniBtnGameday" data-ebl-action="gamecast-replay">↺ REPLAY</button>
            </div>
            <div class="gcTimelineGameday">
              <button class="gcTimelineBtnGameday" data-ebl-action="gamecast-seek-pa" data-direction="-1" title="Previous plate appearance">‹ PA</button>
              <input id="gcTimelineRangeGameday" class="gcTimelineRangeGameday" type="range" min="0" max="${evs().length}" value="0" aria-label="Replay timeline">
              <span id="gcTimelineLabelGameday">0 / ${evs().length}</span>
              <button class="gcTimelineBtnGameday" data-ebl-action="gamecast-seek-pa" data-direction="1" title="Next plate appearance">PA ›</button>
            </div>
          </div>
        </section>
        <aside id="gcMatchupGameday" class="gcMatchPanelGameday">
          <div id="gcMatchupCardsGameday">${matchupCard(null,'AT BAT','batting')}${matchupCard(null,'ON THE MOUND','pitching')}</div>
          <div class="gcQueueCardGameday"><div class="gcMatchLabelGameday">COMING UP</div><div id="gcOnDeckGameday"></div></div>
          <div id="gcStrategyLive" class="gcManagerGameday"><span>MANAGER DECISIONS</span><b>Game plan loaded</b></div>
        </aside>
        <section class="gcPanelGameday gcLatestFeedGameday">
          <div class="gcPanelHeadGameday"><strong>LIVE FEED</strong><span>REPLAY</span></div><div id="gcFeedGameday" class="gcFeedGameday"></div>
        </section>
      </div>`;
    const range=document.getElementById('gcTimelineRangeGameday');
    if(range){
      range.addEventListener('input',()=>{clearInterval(timer);document.getElementById('gcTimelineLabelGameday').textContent=`${range.value} / ${evs().length}`});
      range.addEventListener('change',()=>window.gcSeekEventGameday(N(range.value)));
    }
    gcUpdateScoreboard();updateQueue();updateAtmosphere();window.gcPlayGameday(850);
  };

  function finalState(){
    GC_STATE.score=[N(GG?.away_runs),N(GG?.home_runs)];
    GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.outs=3;GC_STATE.runner=null;GC_STATE.base=0;GC_STATE.runnerVisualBase=0;GC_STATE.isPlaying=false;
    gcUpdateScoreboard();
  }
  function lineScore(){
    const a=GG?.line_score?.away||{},h=GG?.line_score?.home||{},
      at=GG?.totals?.away||{R:GG?.away_runs,H:0,E:0},ht=GG?.totals?.home||{R:GG?.home_runs,H:0,E:0};
    let heads='',ar='',hr='';
    for(let i=1;i<=9;i++){heads+=`<th>${i}</th>`;ar+=`<td>${a[String(i)]??0}</td>`;hr+=`<td>${h[String(i)]??0}</td>`}
    return `<div class="gcLineScoreGameday"><table><tr><th>TEAM</th>${heads}<th>R</th><th>H</th><th>E</th></tr>
      <tr><td>${teamMark(GG.away_id,true)} ${esc(teamLabel(GG.away_id))}</td>${ar}<td><b>${N(at.R,GG.away_runs)}</b></td><td>${N(at.H)}</td><td>${N(at.E)}</td></tr>
      <tr><td>${teamMark(GG.home_id,true)} ${esc(teamLabel(GG.home_id))}</td>${hr}<td><b>${N(ht.R,GG.home_runs)}</b></td><td>${N(ht.H)}</td><td>${N(ht.E)}</td></tr></table></div>`;
  }
  function leaderRows(fid){
    const hitters=(GG?.box?.hitter_rows||[]).filter(x=>x.team_id===fid).slice()
      .sort((a,b)=>(N(b.HR)-N(a.HR))||(N(b.RBI)-N(a.RBI))||(N(b.H)-N(a.H))).slice(0,2);
    return hitters.map(p=>`<div class="gcLeaderGameday">${portrait(p,'batting')}<div><b>#${N(p.jersey_number,24)} ${esc(p.name)}</b><small>${esc(finalHitterLine(p))}</small></div></div>`).join('')
      ||'<div class="muted">No batting line available.</div>';
  }
  function gameStars(){
    const candidates=[];
    for(const p of GG?.box?.hitter_rows||[]){
      const score=N(p.H)*1.5+N(p.HR)*4+N(p.RBI)*2+N(p.R)*.7+N(p.BB)*.45;
      candidates.push({score,p,kind:'batting',line:finalHitterLine(p)});
    }
    for(const p of GG?.box?.pitcher_rows||[]){
      const outs=N(p.OUTS??p.outs),score=outs*.33+N(p.SO)*1.3-N(p.ER)*1.5-N(p.BB)*.35;
      candidates.push({score,p,kind:'pitching',line:finalPitcherLine(p)});
    }
    return candidates.sort((a,b)=>b.score-a.score).slice(0,3).map((x,i)=>`<div class="gcStarGameday">
      <span class="gcStarRankGameday">${i+1}</span>${portrait(x.p,x.kind)}
      <div><b>${esc(x.p.name||'Player')}</b><small>${esc(x.line)}</small></div></div>`).join('')
      ||'<div class="muted">No game-star data available.</div>';
  }
  window.renderGameSummaryGameday=function(){
    const runs=evs().filter(e=>e.type==='RUN');
    const scoring=runs.map(e=>{
      const who=player(e.batter_id)||player(e.runner_id),team=e.team?teamLabel(e.team):'';
      return `<div class="gcScoringPlayGameday"><span>${inningLabel(e)}</span><div><b>${esc(team)}</b><div class="muted">${who?esc(`#${N(who.jersey_number,24)} ${who.name}`):'Scoring play'}${e.note?` • ${esc(e.note)}`:''}</div></div><b class="gcScorePillGameday">${N(e.score?.[0])}-${N(e.score?.[1])}</b></div>`;
    }).join('')||'<p class="muted">No scoring plays were recorded.</p>';
    const host=document.getElementById('gameView');if(!host)return;
    host.innerHTML=`<div class="gcSummaryHeroGameday gcSummaryFullGameday">
      <section class="gcSummaryCardGameday gcSummaryWideGameday"><h3>FINAL LINE</h3>${lineScore()}</section>
      <section class="gcSummaryCardGameday"><h3>SCORING PLAYS</h3>${scoring}</section>
      <section class="gcSummaryCardGameday"><h3>GAME STARS</h3><div class="gcStarsGameday">${gameStars()}</div></section>
      <section class="gcSummaryCardGameday gcSummaryWideGameday"><h3>NOTABLE BATTING</h3><div class="gcNotableGridGameday"><div><h4>${esc(teamLabel(GG.away_id))}</h4>${leaderRows(GG.away_id)}</div><div><h4>${esc(teamLabel(GG.home_id))}</h4>${leaderRows(GG.home_id)}</div></div></section>
    </div>`;
    finalState();
  };
  window.gameTab=function(mode,b){
    clearInterval(timer);
    document.querySelectorAll('.gcDayTabGameday').forEach(x=>x.classList.remove('active'));if(b)b.classList.add('active');
    if(mode==='CAST')window.renderGamecast();
    else if(mode==='SUMMARY')window.renderGameSummaryGameday();
    else if(mode==='BOX'){finalState();renderBoxScore()}
    else if(mode==='PBP'){if(typeof renderFullPlayByPlay==='function')renderFullPlayByPlay();finalState()}
  };
  window.EBL_GAMECAST_BUILD=BUILD;
})();


/* EBL GAMECAST RC136 — self-contained zero-player showcase */
(function(){
  'use strict';
  const SHOWCASE_BUILD='RC136_ZERO_PLAYER_SHOWCASE';

  function N(v,d=0){const n=Number(v);return Number.isFinite(n)?n:d}
  function demoTeams(){
    const teams=Array.isArray(LEAGUE?.teams)?LEAGUE.teams:[];
    const away=teams[0]||{id:'EBL-SHOWCASE-A',name:'Showcase Visitors',display_name:'Showcase Visitors'};
    const home=teams[1]||teams[0]||{id:'EBL-SHOWCASE-H',name:'Showcase Home',display_name:'Showcase Home'};
    return {away,home};
  }
  function teamDisplay(t,fallback){return t?.display_name||t?.name||fallback}
  function demoPlayer(id,team,name,pos,jersey,look={}){
    const pitcher=pos==='P'||pos==='SP'||pos==='RP'||pos==='CL';
    return {
      player_id:id,id,team_id:team,franchise_id:team,name,primary_pos:pos,type:pitcher?'P':'H',
      jersey_number:jersey,bats:look.bats||'R',throws:look.throws||'R',
      face_id:look.face_id||1,hair_id:look.hair_id||1,facial_hair_id:look.facial_hair_id||1,
      eye_color_id:look.eye_color_id||6,nose_id:look.nose_id||1,eye_shape_id:look.eye_shape_id||1,
      mouth_id:look.mouth_id||1,ear_size_id:look.ear_size_id||2,hair_color_id:look.hair_color_id||3,
      eye_black_id:look.eye_black_id||1,eyewear_id:look.eyewear_id||1,chain_id:look.chain_id||1,
      sleeve_id:look.sleeve_id||1,body_build_id:look.body_build_id||1,skin_color_id:look.skin_color_id||1
    };
  }
  function stat(p,vals){return Object.assign({},p,vals)}
  function buildShowcaseGame(){
    const {away,home}=demoTeams(),A=away.id,H=home.id;
    const ap=[
      demoPlayer(-1001,A,'Marcus Bennett','CF',7,{face_id:3,hair_id:5,skin_color_id:5,eye_black_id:2,bats:'L'}),
      demoPlayer(-1002,A,'Nico Ramirez','1B',24,{face_id:7,hair_id:3,facial_hair_id:4,skin_color_id:4,body_build_id:4}),
      demoPlayer(-1003,A,'Andre Sullivan','SS',2,{face_id:2,hair_id:8,skin_color_id:6,eye_black_id:3}),
      demoPlayer(-1004,A,'Cole Navarro','RF',18,{face_id:8,hair_id:2,facial_hair_id:2,skin_color_id:2,sleeve_id:2}),
      demoPlayer(-1005,A,'Dylan Hayes','LF',11,{face_id:5,hair_id:7,skin_color_id:3,bats:'L'}),
      demoPlayer(-1101,A,'Victor Cruz','SP',35,{face_id:9,hair_id:6,facial_hair_id:3,skin_color_id:4}),
      demoPlayer(-1102,A,'Rafael Cross','CL',54,{face_id:4,hair_id:4,facial_hair_id:5,skin_color_id:5})
    ];
    const hp=[
      demoPlayer(-2001,H,'Eli Turner','2B',6,{face_id:1,hair_id:10,skin_color_id:2,bats:'L'}),
      demoPlayer(-2002,H,'Caleb Price','1B',33,{face_id:7,hair_id:4,facial_hair_id:4,skin_color_id:6,body_build_id:5}),
      demoPlayer(-2003,H,'Jordan Reed','LF',12,{face_id:6,hair_id:5,skin_color_id:3,eye_black_id:4}),
      demoPlayer(-2004,H,'Mason Cole','SS',1,{face_id:2,hair_id:8,skin_color_id:4}),
      demoPlayer(-2005,H,'Darius Lane','CF',27,{face_id:8,hair_id:3,facial_hair_id:2,skin_color_id:7,eye_black_id:2}),
      demoPlayer(-2006,H,'Nolan Vega','RF',9,{face_id:3,hair_id:2,skin_color_id:5}),
      demoPlayer(-2100,H,'Mateo Ortiz','SP',41,{face_id:4,hair_id:6,facial_hair_id:3,skin_color_id:5}),
      demoPlayer(-2101,H,'Grant Miller','RP',46,{face_id:5,hair_id:1,facial_hair_id:5,skin_color_id:2})
    ];
    const byId=new Map([...ap,...hp].map(p=>[p.player_id,p]));
    const nm=id=>byId.get(id)?.name||'Player';
    const E=[];
    const push=e=>E.push(e);

    push({type:'GAME_START',inning:8,half:'TOP',score:[2,1],away_name:teamDisplay(away,'Visitors'),home_name:teamDisplay(home,'Home')});
    push({type:'PA_START',inning:8,half:'TOP',score:[2,1],outs:0,batter_id:-1001,pitcher_id:-2101,batter:nm(-1001),pitcher:nm(-2101)});
    push({type:'PITCH',inning:8,half:'TOP',score:[2,1],batter_id:-1001,pitcher_id:-2101,pitch_no:1,pitch_type:'Four-Seam',velocity:96.4,px:.49,pz:.59,call:'Called Strike',balls:0,strikes:1,outs:0});
    push({type:'PITCH',inning:8,half:'TOP',score:[2,1],batter_id:-1001,pitcher_id:-2101,pitch_no:2,pitch_type:'Slider',velocity:86.7,px:.78,pz:.31,call:'Ball',balls:1,strikes:1,outs:0});
    push({type:'PITCH',inning:8,half:'TOP',score:[2,1],batter_id:-1001,pitcher_id:-2101,pitch_no:3,pitch_type:'Sinker',velocity:94.3,px:.42,pz:.44,call:'In Play',balls:1,strikes:1,outs:0});
    push({type:'BALL_IN_PLAY',inning:8,half:'TOP',score:[2,1],batter_id:-1001,pitcher_id:-2101,result:'1B',exit_velocity:101.8,launch_angle:9,spray_angle:31,contact_quality:'Hard contact',fielder_id:-2006,fielder_position:'RF',defensive_note:'HELD_TO_SINGLE'});
    push({type:'OUTFIELD_HOLD',inning:8,half:'TOP',score:[2,1],fielder_id:-2006,position:'RF',fielder_position:'RF'});
    push({type:'PA_END',inning:8,half:'TOP',score:[2,1],outs:0,batter_id:-1001,pitcher_id:-2101,result:'1B'});
    push({type:'STEAL_ATTEMPT',inning:8,half:'TOP',score:[2,1],outs:0,runner_id:-1001,batter_id:-1001,pitcher_id:-2101,success:true});
    push({type:'PA_START',inning:8,half:'TOP',score:[2,1],outs:0,batter_id:-1002,pitcher_id:-2101,batter:nm(-1002),pitcher:nm(-2101)});
    push({type:'PITCH',inning:8,half:'TOP',score:[2,1],batter_id:-1002,pitcher_id:-2101,pitch_no:1,pitch_type:'Changeup',velocity:84.9,px:.25,pz:.28,call:'Ball',balls:1,strikes:0,outs:0});
    push({type:'PITCH',inning:8,half:'TOP',score:[2,1],batter_id:-1002,pitcher_id:-2101,pitch_no:2,pitch_type:'Four-Seam',velocity:97.1,px:.52,pz:.61,call:'In Play',balls:1,strikes:0,outs:0});
    push({type:'BALL_IN_PLAY',inning:8,half:'TOP',score:[2,1],batter_id:-1002,pitcher_id:-2101,result:'HR',exit_velocity:107.8,launch_angle:28,spray_angle:15,contact_quality:'Barreled'});
    push({type:'RUN',inning:8,half:'TOP',score:[4,1],team:A,batter_id:-1002,runner_id:-1001,runs:2,note:'Two-run home run'});
    push({type:'PA_END',inning:8,half:'TOP',score:[4,1],outs:0,batter_id:-1002,pitcher_id:-2101,result:'HR'});
    push({type:'PA_START',inning:8,half:'TOP',score:[4,1],outs:0,batter_id:-1003,pitcher_id:-2101,batter:nm(-1003),pitcher:nm(-2101)});
    push({type:'PITCH',inning:8,half:'TOP',score:[4,1],batter_id:-1003,pitcher_id:-2101,pitch_no:1,pitch_type:'Slider',velocity:88.2,px:.54,pz:.48,call:'Swinging Strike',balls:0,strikes:1,outs:0});
    push({type:'PITCH',inning:8,half:'TOP',score:[4,1],batter_id:-1003,pitcher_id:-2101,pitch_no:2,pitch_type:'Curve',velocity:80.6,px:.39,pz:.35,call:'Swinging Strike',balls:0,strikes:2,outs:0});
    push({type:'OUT',inning:8,half:'TOP',score:[4,1],batter_id:-1003,pitcher_id:-2101,out_type:'Strikeout',outs:1});
    push({type:'PA_END',inning:8,half:'TOP',score:[4,1],outs:1,batter_id:-1003,pitcher_id:-2101,result:'K'});
    push({type:'PA_START',inning:8,half:'TOP',score:[4,1],outs:1,batter_id:-1004,pitcher_id:-2101,batter:nm(-1004),pitcher:nm(-2101)});
    push({type:'PITCH',inning:8,half:'TOP',score:[4,1],batter_id:-1004,pitcher_id:-2101,pitch_no:1,pitch_type:'Sinker',velocity:95.0,px:.57,pz:.42,call:'In Play',balls:0,strikes:0,outs:1});
    push({type:'BALL_IN_PLAY',inning:8,half:'TOP',score:[4,1],batter_id:-1004,pitcher_id:-2101,result:'OUT',out_type:'Groundout',exit_velocity:94.4,launch_angle:-4,spray_angle:-11,contact_quality:'Ground ball',fielder_id:-2004,fielder_position:'SS'});
    push({type:'OUT',inning:8,half:'TOP',score:[4,1],batter_id:-1004,pitcher_id:-2101,out_type:'Groundout',outs:2,fielder_id:-2004,fielder_position:'SS'});
    push({type:'PA_END',inning:8,half:'TOP',score:[4,1],outs:2,batter_id:-1004,pitcher_id:-2101,result:'OUT'});
    push({type:'PA_START',inning:8,half:'TOP',score:[4,1],outs:2,batter_id:-1005,pitcher_id:-2101,batter:nm(-1005),pitcher:nm(-2101)});
    push({type:'PITCH',inning:8,half:'TOP',score:[4,1],batter_id:-1005,pitcher_id:-2101,pitch_no:1,pitch_type:'Four-Seam',velocity:96.8,px:.46,pz:.66,call:'In Play',balls:0,strikes:0,outs:2});
    push({type:'BALL_IN_PLAY',inning:8,half:'TOP',score:[4,1],batter_id:-1005,pitcher_id:-2101,result:'OUT',out_type:'Flyout',exit_velocity:99.1,launch_angle:32,spray_angle:-3,contact_quality:'Deep fly',fielder_id:-2005,fielder_position:'CF'});
    push({type:'GREAT_PLAY',inning:8,half:'TOP',score:[4,1],fielder_id:-2005,position:'CF',fielder_position:'CF',out_type:'Flyout',defensive_note:'Diving catch at the warning track',outs:2});
    push({type:'OUT',inning:8,half:'TOP',score:[4,1],batter_id:-1005,pitcher_id:-2101,out_type:'Flyout',outs:3,fielder_id:-2005,fielder_position:'CF'});
    push({type:'PA_END',inning:8,half:'TOP',score:[4,1],outs:3,batter_id:-1005,pitcher_id:-2101,result:'OUT'});
    push({type:'INNING_END',inning:8,half:'TOP',score:[4,1],outs:3});

    push({type:'PITCHING_CHANGE',inning:9,half:'BOT',score:[4,1],outs:0,team:A,pitcher_id:-1102,role:'CL'});
    push({type:'PA_START',inning:9,half:'BOT',score:[4,1],outs:0,batter_id:-2001,pitcher_id:-1102,batter:nm(-2001),pitcher:nm(-1102)});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,1],batter_id:-2001,pitcher_id:-1102,pitch_no:1,pitch_type:'Four-Seam',velocity:98.2,px:.51,pz:.63,call:'Called Strike',balls:0,strikes:1,outs:0});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,1],batter_id:-2001,pitcher_id:-1102,pitch_no:2,pitch_type:'Slider',velocity:89.1,px:.43,pz:.41,call:'In Play',balls:0,strikes:1,outs:0});
    push({type:'BALL_IN_PLAY',inning:9,half:'BOT',score:[4,1],batter_id:-2001,pitcher_id:-1102,result:'2B',exit_velocity:104.0,launch_angle:19,spray_angle:-12,contact_quality:'Lined to the gap',fielder_id:-1005,fielder_position:'LF'});
    push({type:'PA_END',inning:9,half:'BOT',score:[4,1],outs:0,batter_id:-2001,pitcher_id:-1102,result:'2B'});
    push({type:'PA_START',inning:9,half:'BOT',score:[4,1],outs:0,batter_id:-2002,pitcher_id:-1102,batter:nm(-2002),pitcher:nm(-1102)});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,1],batter_id:-2002,pitcher_id:-1102,pitch_no:1,pitch_type:'Slider',velocity:88.5,px:.72,pz:.25,call:'Ball',balls:1,strikes:0,outs:0});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,1],batter_id:-2002,pitcher_id:-1102,pitch_no:2,pitch_type:'Four-Seam',velocity:99.0,px:.50,pz:.57,call:'In Play',balls:1,strikes:0,outs:0});
    push({type:'BALL_IN_PLAY',inning:9,half:'BOT',score:[4,1],batter_id:-2002,pitcher_id:-1102,result:'HR',exit_velocity:109.6,launch_angle:31,spray_angle:22,contact_quality:'Barreled'});
    push({type:'RUN',inning:9,half:'BOT',score:[4,3],team:H,batter_id:-2002,runner_id:-2001,runs:2,note:'Two-run home run'});
    push({type:'PA_END',inning:9,half:'BOT',score:[4,3],outs:0,batter_id:-2002,pitcher_id:-1102,result:'HR'});
    push({type:'PA_START',inning:9,half:'BOT',score:[4,3],outs:0,batter_id:-2003,pitcher_id:-1102,batter:nm(-2003),pitcher:nm(-1102)});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,3],batter_id:-2003,pitcher_id:-1102,pitch_no:1,pitch_type:'Changeup',velocity:87.4,px:.37,pz:.43,call:'In Play',balls:0,strikes:0,outs:0});
    push({type:'BALL_IN_PLAY',inning:9,half:'BOT',score:[4,3],batter_id:-2003,pitcher_id:-1102,result:'1B',exit_velocity:93.1,launch_angle:5,spray_angle:30,contact_quality:'Line drive',fielder_id:-1004,fielder_position:'RF',defensive_note:'HELD_TO_SINGLE'});
    push({type:'OUTFIELD_HOLD',inning:9,half:'BOT',score:[4,3],fielder_id:-1004,position:'RF',fielder_position:'RF'});
    push({type:'PA_END',inning:9,half:'BOT',score:[4,3],outs:0,batter_id:-2003,pitcher_id:-1102,result:'1B'});
    push({type:'STEAL_ATTEMPT',inning:9,half:'BOT',score:[4,3],outs:0,runner_id:-2003,batter_id:-2003,pitcher_id:-1102,success:true});
    push({type:'PA_START',inning:9,half:'BOT',score:[4,3],outs:0,batter_id:-2004,pitcher_id:-1102,batter:nm(-2004),pitcher:nm(-1102)});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,3],batter_id:-2004,pitcher_id:-1102,pitch_no:1,pitch_type:'Slider',velocity:90.1,px:.57,pz:.46,call:'Swinging Strike',balls:0,strikes:1,outs:0});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,3],batter_id:-2004,pitcher_id:-1102,pitch_no:2,pitch_type:'Four-Seam',velocity:99.4,px:.47,pz:.68,call:'Swinging Strike',balls:0,strikes:2,outs:0});
    push({type:'OUT',inning:9,half:'BOT',score:[4,3],batter_id:-2004,pitcher_id:-1102,out_type:'Strikeout',outs:1});
    push({type:'PA_END',inning:9,half:'BOT',score:[4,3],outs:1,batter_id:-2004,pitcher_id:-1102,result:'K'});
    push({type:'PA_START',inning:9,half:'BOT',score:[4,3],outs:1,batter_id:-2005,pitcher_id:-1102,batter:nm(-2005),pitcher:nm(-1102)});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,3],batter_id:-2005,pitcher_id:-1102,pitch_no:1,pitch_type:'Slider',velocity:89.4,px:.82,pz:.30,call:'Ball',balls:1,strikes:0,outs:1});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,3],batter_id:-2005,pitcher_id:-1102,pitch_no:2,pitch_type:'Four-Seam',velocity:98.7,px:.41,pz:.54,call:'Foul',balls:1,strikes:1,outs:1});
    push({type:'PITCH',inning:9,half:'BOT',score:[4,3],batter_id:-2005,pitcher_id:-1102,pitch_no:3,pitch_type:'Sinker',velocity:97.3,px:.53,pz:.49,call:'In Play',balls:1,strikes:1,outs:1});
    push({type:'BALL_IN_PLAY',inning:9,half:'BOT',score:[4,3],batter_id:-2005,pitcher_id:-1102,result:'HR',exit_velocity:111.2,launch_angle:27,spray_angle:-3,contact_quality:'Perfect timing'});
    push({type:'RUN',inning:9,half:'BOT',score:[4,5],team:H,batter_id:-2005,runner_id:-2003,runs:2,note:'Walk-off two-run home run'});
    push({type:'PA_END',inning:9,half:'BOT',score:[4,5],outs:1,batter_id:-2005,pitcher_id:-1102,result:'HR'});
    push({type:'GAME_END',inning:9,half:'BOT',score:[4,5],final_score:[4,5],outs:1});

    const hitter_rows=[
      stat(ap[0],{AB:4,R:1,H:1,'2B':0,HR:0,RBI:0,BB:0,SO:0,SB:1}),
      stat(ap[1],{AB:4,R:1,H:2,'2B':0,HR:1,RBI:2,BB:0,SO:0,SB:0}),
      stat(ap[2],{AB:4,R:0,H:1,'2B':0,HR:0,RBI:1,BB:0,SO:1,SB:0}),
      stat(ap[3],{AB:4,R:1,H:1,'2B':1,HR:0,RBI:0,BB:0,SO:0,SB:0}),
      stat(ap[4],{AB:4,R:1,H:2,'2B':0,HR:0,RBI:1,BB:0,SO:0,SB:0}),
      stat(hp[0],{AB:4,R:1,H:2,'2B':1,HR:0,RBI:0,BB:0,SO:0,SB:0}),
      stat(hp[1],{AB:4,R:1,H:1,'2B':0,HR:1,RBI:2,BB:0,SO:0,SB:0}),
      stat(hp[2],{AB:4,R:1,H:2,'2B':0,HR:0,RBI:0,BB:0,SO:0,SB:1}),
      stat(hp[3],{AB:4,R:0,H:1,'2B':0,HR:0,RBI:1,BB:0,SO:1,SB:0}),
      stat(hp[4],{AB:4,R:2,H:2,'2B':0,HR:1,RBI:2,BB:0,SO:0,SB:0}),
      stat(hp[5],{AB:3,R:0,H:0,'2B':0,HR:0,RBI:0,BB:1,SO:1,SB:0})
    ];
    const pitcher_rows=[
      stat(ap[5],{OUTS:24,H:4,ER:1,BB:2,SO:7,W:0,L:0,SV:0}),
      stat(ap[6],{OUTS:1,H:4,ER:4,BB:0,SO:1,W:0,L:1,SV:0}),
      stat(hp[6],{OUTS:21,H:4,ER:2,BB:1,SO:6,W:0,L:0,SV:0}),
      stat(hp[7],{OUTS:6,H:3,ER:2,BB:0,SO:2,W:1,L:0,SV:0})
    ];
    const fielding_rows=[
      stat(hp[3],{position:'SS',PO:1,A:3,E:0}),
      stat(hp[4],{position:'CF',PO:4,A:0,E:0}),
      stat(hp[5],{position:'RF',PO:2,A:1,E:0}),
      stat(ap[2],{position:'SS',PO:1,A:4,E:0}),
      stat(ap[3],{position:'RF',PO:2,A:1,E:0}),
      stat(ap[4],{position:'LF',PO:3,A:0,E:0})
    ];
    return {
      __showcase:true,id:'EBL-SHOWCASE-RC136',season:N(LEAGUE?.season,1),league_day:0,status:'FINAL',
      away_id:A,home_id:H,away_name:teamDisplay(away,'Showcase Visitors'),home_name:teamDisplay(home,'Showcase Home'),
      away_runs:4,home_runs:5,
      line_score:{away:{'1':1,'2':0,'3':1,'4':0,'5':0,'6':0,'7':0,'8':2,'9':0},home:{'1':0,'2':1,'3':0,'4':0,'5':0,'6':0,'7':0,'8':0,'9':4}},
      totals:{away:{R:4,H:7,E:0},home:{R:5,H:8,E:0}},
      box:{hitter_rows,pitcher_rows,fielding_rows},
      events:E
    };
  }

  window.launchGamecastShowcase=async function(){
    if(!Array.isArray(LEAGUE?.teams)||LEAGUE.teams.length<2){
      try{if(typeof loadLeague==='function')await loadLeague()}catch(_){}
    }
    const dlg=document.getElementById('gc');
    if(!dlg)return;
    window.__EBL_GG_BEFORE_SHOWCASE=GG;
    GG=buildShowcaseGame();window.GG=GG;gi=0;clearInterval(timer);
    dlg.classList.add('gcShowcaseModeGameday');
    if(!dlg.dataset.showcaseRestore){
      dlg.addEventListener('close',()=>{
        dlg.classList.remove('gcShowcaseModeGameday');
        if(GG?.__showcase){
          GG=window.__EBL_GG_BEFORE_SHOWCASE||null;
          window.GG=GG;
        }
      });
      dlg.dataset.showcaseRestore='1';
    }
    renderGameShell();
    const eyebrow=dlg.querySelector('.gcDayEyebrowGameday span');
    if(eyebrow)eyebrow.innerHTML='EBL GAMEDAY <b class="gcShowcaseBadgeGameday">SHOWCASE</b>';
    if(!dlg.open)dlg.showModal();
  };
  window.EBL_GAMECAST_SHOWCASE_BUILD=SHOWCASE_BUILD;
})();
