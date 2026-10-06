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

/* EBL GAMECAST RC140 — field routes, bang-bang races, walk-off broadcast finish */
(function(){
  'use strict';
  const BUILD='RC140_FIELD_ROUTES_RACES_WALKOFF';
  const FPOS={LF:[145,135],CF:[300,75],RF:[455,135],SS:[215,220],'2B':[385,220],'3B':[180,270],'1B':[420,270],P:[300,282],C:[300,354]};
  const BASE={HOME:[300,382],'1B':[441,230],'2B':[300,125],'3B':[159,230]};
  let lastBip=null,lastLanding=null,lastStep=null;
  const N=(v,d=0)=>{const n=Number(v);return Number.isFinite(n)?n:d};
  const esc=v=>typeof escapeHtml==='function'?escapeHtml(String(v??'')):String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  function getPlayer(pid){try{return typeof gamecastPlayerById==='function'?gamecastPlayerById(pid):null}catch(_){return null}}
  function teamLabel(fid){try{return teamName(fid)||fid||'Team'}catch(_){return fid||'Team'}}
  function landing(e){
    const result=String(e?.result||'').toUpperCase(),ev=N(e?.exit_velocity,90),la=N(e?.launch_angle,10),angle=N(e?.spray_angle,0);
    let depth=160;
    if(result==='HR')depth=38;else if(result==='3B')depth=72;else if(result==='2B')depth=102;else if(result==='1B'||result==='ROE')depth=145;
    else depth=Math.max(74,170-Math.max(0,ev-80)*1.25-Math.max(0,la)*.72);
    return {x:Math.max(88,Math.min(512,300+angle*4.65)),y:Math.max(34,Math.min(220,depth))};
  }
  function ensureLayer(){
    const stage=document.getElementById('gcVisualStageGameday');
    if(!stage||stage.querySelector('.gcRC140Layer'))return;
    const layer=document.createElement('div');
    layer.className='gcRC140Layer';
    layer.innerHTML=`<div id="gcRC140Metric" class="gcRC140Metric"></div><div id="gcRC140Callout" class="gcRC140Callout"></div><div id="gcRC140Finish" class="gcRC140Finish"></div><div id="gcRC140Particles" class="gcRC140Particles" aria-hidden="true"></div>`;
    stage.appendChild(layer);
    const svg=document.getElementById('gcFieldSvgGameday');
    if(svg&&!svg.querySelector('#gcFielderRouteRC140')){
      const ns='http://www.w3.org/2000/svg';
      const path=document.createElementNS(ns,'path');path.id='gcFielderRouteRC140';path.setAttribute('class','gcFielderRouteRC140');svg.appendChild(path);
      const fg=document.createElementNS(ns,'g');fg.id='gcFielderMotionRC140';fg.setAttribute('class','gcFielderMotionRC140');
      fg.innerHTML='<circle r="15"></circle><circle class="trail" r="22"></circle><text y="4" text-anchor="middle">F</text>';svg.appendChild(fg);
      const rg=document.createElementNS(ns,'g');rg.id='gcRaceRunnerRC140';rg.setAttribute('class','gcRaceRunnerRC140');
      rg.innerHTML='<circle r="14"></circle><circle class="trail" r="21"></circle><text y="4" text-anchor="middle">R</text>';svg.appendChild(rg);
      const tag=document.createElementNS(ns,'g');tag.id='gcRaceTagRC140';tag.setAttribute('class','gcRaceTagRC140');
      tag.innerHTML='<rect x="-42" y="-13" width="84" height="26" rx="8"></rect><text y="4" text-anchor="middle">PLAY</text>';svg.appendChild(tag);
      const relay=document.createElementNS(ns,'path');relay.id='gcRelayPathRC140';relay.setAttribute('class','gcRelayPathRC140');svg.appendChild(relay);
      const rb=document.createElementNS(ns,'circle');rb.id='gcRelayBallRC140';rb.setAttribute('class','gcRelayBallRC140');rb.setAttribute('r','6');svg.appendChild(rb);
      const cut=document.createElementNS(ns,'g');cut.id='gcCutoffRC140';cut.setAttribute('class','gcCutoffRC140');
      cut.innerHTML='<circle r="12"></circle><text y="4" text-anchor="middle">CUT</text>';svg.appendChild(cut);
    }
  }
  function metric(html,kind=''){
    ensureLayer();const el=document.getElementById('gcRC140Metric');if(!el)return;
    el.className=`gcRC140Metric show ${kind}`;el.innerHTML=html;
    clearTimeout(el.__t);el.__t=setTimeout(()=>el.className='gcRC140Metric',2100);
  }
  function callout(text,kind=''){
    ensureLayer();const el=document.getElementById('gcRC140Callout');if(!el)return;
    el.className=`gcRC140Callout show ${kind}`;el.textContent=text;
    clearTimeout(el.__t);el.__t=setTimeout(()=>el.className='gcRC140Callout',1500);
  }
  function particles(kind='celebrate'){
    ensureLayer();const host=document.getElementById('gcRC140Particles');if(!host)return;
    host.innerHTML='';host.className=`gcRC140Particles burst ${kind}`;
    for(let i=0;i<34;i++){
      const s=document.createElement('i');
      s.style.setProperty('--i',String(i));
      s.style.setProperty('--x',`${8+((i*29)%84)}%`);
      s.style.setProperty('--d',`${.7+((i%7)*.08)}s`);
      s.style.setProperty('--r',`${(i*47)%180}deg`);
      host.appendChild(s);
    }
    clearTimeout(host.__t);host.__t=setTimeout(()=>{host.className='gcRC140Particles';host.innerHTML=''},2300);
  }
  function svgAnimate(group,path,dur=760,endPoint=null){
    if(!group)return;
    group.querySelectorAll('animateMotion').forEach(x=>x.remove());
    group.classList.add('show');group.setAttribute('transform','translate(0 0)');
    const ns='http://www.w3.org/2000/svg',am=document.createElementNS(ns,'animateMotion');
    am.setAttribute('dur',`${dur}ms`);am.setAttribute('path',path);am.setAttribute('fill','freeze');group.appendChild(am);
    try{am.beginElement()}catch(_){}
    setTimeout(()=>{
      if(!group.isConnected)return;
      group.querySelectorAll('animateMotion').forEach(x=>x.remove());
      if(endPoint)group.setAttribute('transform',`translate(${endPoint[0]} ${endPoint[1]})`);
    },dur+15);
  }
  function routeFielder(e,dive=false){
    ensureLayer();
    const pos=String(e?.fielder_position||e?.position||'').toUpperCase(),start=FPOS[pos];if(!start)return;
    const end=lastLanding||landing(e),route=document.getElementById('gcFielderRouteRC140'),g=document.getElementById('gcFielderMotionRC140');if(!route||!g)return;
    const curveY=Math.min(start[1],end.y)-26;
    const d=`M${start[0]} ${start[1]} Q${((start[0]+end.x)/2).toFixed(1)} ${curveY.toFixed(1)} ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;
    route.setAttribute('d',d);route.classList.add('show');
    const tx=g.querySelector('text');if(tx)tx.textContent=pos||'F';
    const origin=document.querySelector(`.gcFielderGameday[data-pos="${pos}"]`);if(origin)origin.classList.add('rc140MovingOrigin');
    g.classList.toggle('dive',!!dive);svgAnimate(g,d,dive?680:760,[end.x,end.y]);
    setTimeout(()=>{
      route.classList.remove('show');g.classList.remove('show','dive');g.setAttribute('transform',`translate(${start[0]} ${start[1]})`);if(origin)origin.classList.remove('rc140MovingOrigin');
    },dive?1200:1120);
  }
  function raceToFirst(e){
    ensureLayer();
    const result=String(e?.result||'').toUpperCase(),out=String(e?.out_type||'').toLowerCase(),pos=String(e?.fielder_position||'').toUpperCase();
    const infield=['P','C','1B','2B','3B','SS'].includes(pos);
    if(!infield||!(out.includes('ground')||['1B','ROE'].includes(result)))return;
    const g=document.getElementById('gcRaceRunnerRC140'),tag=document.getElementById('gcRaceTagRC140');if(!g)return;
    const p=getPlayer(e?.batter_id),t=g.querySelector('text');if(t)t.textContent=p?.jersey_number?String(N(p.jersey_number)).slice(-2):'R';
    const safe=['1B','ROE'].includes(result),dur=safe?690:990;
    const d=`M${BASE.HOME[0]} ${BASE.HOME[1]} L${BASE['1B'][0]} ${BASE['1B'][1]}`;
    svgAnimate(g,d,dur,BASE['1B']);
    if(tag){tag.setAttribute('transform',`translate(${BASE['1B'][0]-8} ${BASE['1B'][1]-36})`);tag.querySelector('text').textContent=safe?'SAFE':'OUT';tag.classList.add('show',safe?'safe':'out')}
    setTimeout(()=>{g.classList.remove('show');if(tag)tag.classList.remove('show','safe','out')},1450);
    setTimeout(()=>callout(safe?'BEATS THE THROW':'OUT AT FIRST',safe?'safe':'out'),safe?720:1000);
  }
  function animateRelay(fromPos,toKey='2B',label='CUTOFF RELAY'){
    ensureLayer();
    const start=FPOS[String(fromPos||'').toUpperCase()]||FPOS.C,target=FPOS[String(toKey||'').toUpperCase()]||BASE[String(toKey||'').toUpperCase()]||BASE['2B'];
    if(!start||!target)return;
    const path=document.getElementById('gcRelayPathRC140'),ball=document.getElementById('gcRelayBallRC140'),cut=document.getElementById('gcCutoffRC140');
    if(!path||!ball||!cut)return;
    const cx=start[0]+(target[0]-start[0])*.52,cy=start[1]+(target[1]-start[1])*.52;
    const d=`M${start[0]} ${start[1]} L${cx.toFixed(1)} ${cy.toFixed(1)} L${target[0]} ${target[1]}`;
    path.setAttribute('d',d);path.classList.add('show');
    cut.setAttribute('transform',`translate(${cx.toFixed(1)} ${cy.toFixed(1)})`);cut.classList.add('show');
    ball.innerHTML='';ball.setAttribute('cx','0');ball.setAttribute('cy','0');ball.classList.add('show');
    const ns='http://www.w3.org/2000/svg',am=document.createElementNS(ns,'animateMotion');am.setAttribute('dur','.82s');am.setAttribute('path',d);am.setAttribute('fill','freeze');ball.appendChild(am);try{am.beginElement()}catch(_){}
    const readout=document.getElementById('gcFieldReadoutGameday');if(readout)readout.textContent=label;
    setTimeout(()=>{path.classList.remove('show');ball.classList.remove('show');cut.classList.remove('show');ball.innerHTML=''},980);
  }
  function stealThrow(){animateRelay('C','2B','Catcher throw • runner vs throw')}
  function pickoffThrow(){animateRelay('P','1B','Pickoff throw to first')}

  function pitchMetric(e){
    const count=`${N(e?.balls)}-${N(e?.strikes)}`;
    metric(`<span>${esc(e?.pitch_type||'PITCH')}</span><b>${N(e?.velocity).toFixed(1)}</b><small>MPH • ${esc(e?.call||'')} • ${count}</small>`,'pitch');
  }
  function bipMetric(e){
    const cq=String(e?.contact_quality||'CONTACT').toUpperCase();
    metric(`<span>${esc(cq)}</span><b>${N(e?.exit_velocity).toFixed(1)}</b><small>MPH EV • ${N(e?.launch_angle).toFixed(0)}° LA • ${N(e?.spray_angle).toFixed(0)}° SPRAY</small>`,'contact');
  }
  function celebrateHR(e){
    const stage=document.getElementById('gcVisualStageGameday');if(stage){stage.classList.remove('gcRC140Homer');void stage.offsetWidth;stage.classList.add('gcRC140Homer');setTimeout(()=>stage.classList.remove('gcRC140Homer'),2200)}
    particles('homer');callout('HOME RUN','homer');
  }
  function walkoff(e){
    if(String(e?.half||'').toUpperCase()!=='BOT'||N(e?.inning)<9||!Array.isArray(e?.score)||N(e.score[1])<=N(e.score[0]))return false;
    ensureLayer();const host=document.getElementById('gcRC140Finish');if(!host)return true;
    const hitter=getPlayer(e?.batter_id),home=GG?.home_id;
    host.className='gcRC140Finish show walkoff';
    host.innerHTML=`<span>WALK-OFF</span><strong>${esc(teamLabel(home))} WIN</strong><b>${N(e.score[0])} – ${N(e.score[1])}</b><small>${hitter?esc(`#${N(hitter.jersey_number,24)} ${hitter.name}`):'Bottom of the ninth'}</small>`;
    particles('walkoff');
    clearTimeout(host.__t);host.__t=setTimeout(()=>host.className='gcRC140Finish',3200);
    return true;
  }
  function finalCard(e){
    ensureLayer();const host=document.getElementById('gcRC140Finish');if(!host||host.classList.contains('walkoff'))return;
    const s=e?.final_score||e?.score||[GG?.away_runs,GG?.home_runs],homeWin=N(s?.[1])>N(s?.[0]),winner=homeWin?GG?.home_id:GG?.away_id;
    host.className='gcRC140Finish show final';
    host.innerHTML=`<span>FINAL</span><strong>${esc(teamLabel(winner))}</strong><b>${N(s?.[0])} – ${N(s?.[1])}</b><small>EBL GAMEDAY</small>`;
    clearTimeout(host.__t);host.__t=setTimeout(()=>host.className='gcRC140Finish',2800);
  }
  function enhance(e){
    if(!e)return;ensureLayer();lastStep=e;
    if(e.type==='PITCH')pitchMetric(e);
    if(e.type==='BALL_IN_PLAY'){
      lastBip=e;lastLanding=landing(e);bipMetric(e);routeFielder(e,false);raceToFirst(e);
      if(String(e?.result||'').toUpperCase()==='HR')celebrateHR(e);
    }
    if(e.type==='GREAT_PLAY'){routeFielder({...lastBip,...e,fielder_position:e.fielder_position||e.position||lastBip?.fielder_position},true);callout('GREAT PLAY','defense')}
    if(e.type==='OUTFIELD_HOLD'){animateRelay(e.fielder_position||e.position||lastBip?.fielder_position,'2B','Cutoff relay • runner held');callout('STRONG THROW • RUNNER HELD','defense')}
    if(e.type==='FIELDING_ERROR')callout('ERROR','error');
    if(e.type==='STEAL_ATTEMPT'){stealThrow();callout(e.success?'STOLEN BASE':'CAUGHT STEALING',e.success?'safe':'out')}
    if(e.type==='PICKOFF'){pickoffThrow();callout('PICKED OFF','out')}
    if(e.type==='RUN')walkoff(e);
    if(e.type==='GAME_END')finalCard(e);
  }
  const priorRender=window.renderGamecast;
  if(typeof priorRender==='function')window.renderGamecast=function(){const r=priorRender.apply(this,arguments);ensureLayer();return r};
  const priorStep=window.step;
  if(typeof priorStep==='function')window.step=function(){
    const idx=N(typeof gi!=='undefined'?gi:0),e=Array.isArray(GG?.events)?GG.events[idx]:null;
    const r=priorStep.apply(this,arguments);if(e)setTimeout(()=>enhance(e),0);return r;
  };
  window.EBL_GAMECAST_BUILD=BUILD;
})();

/* EBL GAMECAST RC141 — broadcast director, key moments, pitch trails, game flow */
(function(){
  'use strict';
  const BUILD='RC141_BROADCAST_DIRECTOR_KEY_MOMENTS';
  const N=(v,d=0)=>{const n=Number(v);return Number.isFinite(n)?n:d};
  const esc=v=>typeof escapeHtml==='function'?escapeHtml(String(v??'')):String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  const evs=()=>Array.isArray(GG?.events)?GG.events:[];
  const player=pid=>{try{return typeof gamecastPlayerById==='function'?gamecastPlayerById(pid):null}catch(_){return null}};
  const teamLabel=fid=>{try{return teamName(fid)||fid||'Team'}catch(_){return fid||'Team'}};
  function inning(e){return `${String(e?.half||'TOP').toUpperCase()==='BOT'?'BOT':'TOP'} ${N(e?.inning,1)}`}
  function pitchCode(t){const m={'Four-Seam':'4S','Four Seam':'4S','Slider':'SL','Changeup':'CH','Sinker':'SI','Curve':'CU','Curveball':'CU'};return m[t]||String(t||'P').slice(0,2).toUpperCase()}

  function momentCatalog(){
    const all=evs(),out=[];
    all.forEach((e,index)=>{
      let label='',kind='moment',priority=0;
      if(e?.type==='BALL_IN_PLAY'&&String(e.result||'').toUpperCase()==='HR'){label='HOME RUN';kind='hr';priority=10}
      else if(e?.type==='RUN'){label=N(e.runs,1)>1?`${N(e.runs,1)} RUNS`:'RUN';kind='run';priority=9}
      else if(e?.type==='GREAT_PLAY'){label='GREAT PLAY';kind='defense';priority=8}
      else if(e?.type==='FIELDING_ERROR'){label='ERROR';kind='error';priority=7}
      else if(e?.type==='STEAL_ATTEMPT'&&e.success){label='STOLEN BASE';kind='steal';priority=6}
      else if(e?.type==='PITCHING_CHANGE'){label='PITCHING CHANGE';kind='pitching';priority=5}
      else if(e?.type==='OUT'&&String(e.out_type||'').toLowerCase().includes('strikeout')&&N(e.inning)>=7){
        const s=e.score||[0,0];if(Math.abs(N(s[0])-N(s[1]))<=2){label='LATE K';kind='strikeout';priority=4}
      }
      if(label)out.push({index,event:e,label,kind,priority});
    });
    if(out.length<=16)return out;
    const keep=out.slice().sort((a,b)=>b.priority-a.priority||a.index-b.index).slice(0,16).sort((a,b)=>a.index-b.index);
    return keep;
  }
  function momentSubtitle(m){
    const e=m.event||{},score=Array.isArray(e.score)?` • ${N(e.score[0])}-${N(e.score[1])}`:'';
    return `${inning(e)}${score}`;
  }
  function renderMomentStrip(){
    const timeline=document.querySelector('.gcTimelineGameday');if(!timeline)return;
    let host=document.getElementById('gcMomentStrip141');
    if(!host){host=document.createElement('div');host.id='gcMomentStrip141';host.className='gcMomentStrip141';timeline.insertAdjacentElement('afterend',host)}
    const moments=momentCatalog();
    host.innerHTML=`<div class="gcMomentHead141"><strong>KEY MOMENTS</strong><div><button class="gcMomentNav141" data-ebl-action="gamecast-jump-moment" data-direction="-1">‹</button><button class="gcMomentNav141" data-ebl-action="gamecast-jump-moment" data-direction="1">›</button></div></div><div class="gcMomentRail141">${moments.length?moments.map(m=>`<button class="gcMomentChip141 ${m.kind}" data-ebl-action="gamecast-seek-event" data-event="${m.index+1}" data-moment-index="${m.index}" title="${esc(m.label)} • ${esc(momentSubtitle(m))}"><span>${esc(m.label)}</span><small>${esc(momentSubtitle(m))}</small></button>`).join(''):'<span class="gcMomentEmpty141">Key moments will appear here as the game develops.</span>'}</div>`;
    updateMomentActive();
  }
  function updateMomentActive(){
    const cur=Math.max(0,N(typeof gi!=='undefined'?gi:0)-1),moments=momentCatalog(),latest=moments.filter(m=>m.index<=cur).pop();
    document.querySelectorAll('.gcMomentChip141').forEach(b=>b.classList.toggle('active',!!latest&&N(b.dataset.momentIndex,-1)===latest.index));
  }
  window.gcOpenEventRC141=function(target){
    const tab=document.querySelector('.gcDayTabGameday[data-gc-tab="CAST"]');
    if(typeof window.gameTab==='function')window.gameTab('CAST',tab);
    setTimeout(()=>{if(typeof window.gcSeekEventGameday==='function')window.gcSeekEventGameday(N(target))},0);
  };
  window.gcJumpMomentRC141=function(direction=1){
    const moments=momentCatalog();if(!moments.length)return;
    const cur=Math.max(0,N(typeof gi!=='undefined'?gi:0)-1),dir=N(direction,1);
    let target;
    if(dir>=0)target=moments.find(m=>m.index>cur)||moments[moments.length-1];
    else{const prior=moments.filter(m=>m.index<cur);target=prior.length?prior[prior.length-1]:moments[0]}
    if(target&&typeof window.gcSeekEventGameday==='function')window.gcSeekEventGameday(target.index+1);
  };

  function ensureDirectorUI(){
    const stage=document.getElementById('gcVisualStageGameday');
    if(stage&&!document.getElementById('gcCameraBug141')){
      const b=document.createElement('div');b.id='gcCameraBug141';b.className='gcCameraBug141';b.innerHTML='<span>CAMERA</span><b>PITCH</b>';stage.appendChild(b);
    }
    const zone=document.getElementById('gcZoneCanvasGameday');
    if(zone&&!document.getElementById('gcPitchTrail141')){
      const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
      svg.id='gcPitchTrail141';svg.setAttribute('class','gcPitchTrail141');svg.setAttribute('viewBox','0 0 100 100');svg.setAttribute('preserveAspectRatio','none');zone.insertBefore(svg,zone.firstChild);
    }
    const panel=document.getElementById('gcMatchupGameday');
    if(panel&&!document.getElementById('gcPitchMix141')){
      const d=document.createElement('div');d.id='gcPitchMix141';d.className='gcPitchMix141';panel.appendChild(d);
    }
    renderMomentStrip();updatePitchMix();
  }
  function setCamera(mode='PITCH'){
    const stage=document.getElementById('gcVisualStageGameday');if(!stage)return;
    stage.classList.remove('gcCamPitch141','gcCamField141','gcCamBases141','gcCamMoment141');
    const key=String(mode||'PITCH').toUpperCase();
    stage.classList.add(key==='FIELD'?'gcCamField141':key==='BASES'?'gcCamBases141':key==='MOMENT'?'gcCamMoment141':'gcCamPitch141');
    const bug=document.getElementById('gcCameraBug141');if(bug){const b=bug.querySelector('b');if(b)b.textContent=key}
  }
  function cameraForEvent(e){
    if(!e)return;
    if(e.type==='BALL_IN_PLAY'||e.type==='GREAT_PLAY'||e.type==='OUTFIELD_HOLD')setCamera('FIELD');
    else if(['STEAL_ATTEMPT','PICKOFF'].includes(e.type))setCamera('BASES');
    else if(['RUN','GAME_END'].includes(e.type)||String(e.result||'').toUpperCase()==='HR')setCamera('MOMENT');
    else if(['PA_START','PITCH','PITCHING_CHANGE'].includes(e.type))setCamera('PITCH');
  }

  function clearPitchTrails(){const svg=document.getElementById('gcPitchTrail141');if(svg)svg.innerHTML=''}
  function pitchTrail(e){
    const svg=document.getElementById('gcPitchTrail141');if(!svg)return;
    const px=Math.max(6,Math.min(94,8+N(e?.px,.5)*84)),py=Math.max(5,Math.min(95,8+(1-N(e?.pz,.5))*84));
    const hand=String(player(e?.pitcher_id)?.throws||'R').toUpperCase()==='L'?-1:1,t=String(e?.pitch_type||'').toLowerCase();
    let bendX=0,bendY=0;
    if(t.includes('slider')){bendX=13*hand;bendY=4}else if(t.includes('curve')){bendX=4*hand;bendY=17}else if(t.includes('sinker')){bendX=6*hand;bendY=12}else if(t.includes('change')){bendX=4*hand;bendY=9}else if(t.includes('four')||t.includes('fast')){bendY=-4}
    const sx=50-hand*7,sy=-8,cx=(sx+px)/2+bendX,cy=(sy+py)/2+bendY;
    const ns='http://www.w3.org/2000/svg',path=document.createElementNS(ns,'path');
    path.setAttribute('d',`M${sx} ${sy} Q${cx.toFixed(1)} ${cy.toFixed(1)} ${px.toFixed(1)} ${py.toFixed(1)}`);path.setAttribute('class','gcPitchTrailPath141');
    const older=svg.querySelectorAll('.gcPitchTrailPath141');older.forEach(x=>x.classList.add('old'));
    svg.appendChild(path);while(svg.children.length>5)svg.removeChild(svg.firstChild);
    const len=path.getTotalLength?.()||120;path.style.strokeDasharray=String(len);path.style.strokeDashoffset=String(len);requestAnimationFrame(()=>{path.style.strokeDashoffset='0'});
  }

  function pitchMixRows(pid){
    const end=Math.max(0,N(typeof gi!=='undefined'?gi:0)),rows={};
    for(let i=0;i<end;i++){
      const e=evs()[i];if(e?.type!=='PITCH'||N(e.pitcher_id)!==N(pid))continue;
      const k=e.pitch_type||'Pitch';if(!rows[k])rows[k]={n:0,v:0};rows[k].n++;rows[k].v+=N(e.velocity);
    }
    return Object.entries(rows).sort((a,b)=>b[1].n-a[1].n).slice(0,5);
  }
  function updatePitchMix(){
    const host=document.getElementById('gcPitchMix141');if(!host)return;
    const pid=GC_STATE?.pitcher_id,p=player(pid),rows=pitchMixRows(pid),total=rows.reduce((s,[,v])=>s+v.n,0);
    host.innerHTML=`<div class="gcMatchLabelGameday">PITCH MIX</div>${p&&rows.length?`<div class="gcPitchMixName141">${esc(p.name||'Pitcher')} <span>${total} P</span></div>${rows.map(([name,v])=>`<div class="gcPitchMixRow141"><b>${esc(pitchCode(name))}</b><span>${esc(name)}</span><i style="--w:${Math.max(8,Math.round(v.n/Math.max(1,total)*100))}%"></i><small>${v.n} • ${(v.v/v.n).toFixed(1)} mph</small></div>`).join('')}`:'<div class="gcQueueEmptyGameday">Pitch mix builds as the replay advances.</div>'}`;
  }

  function momentEventLabel(m){
    const e=m.event,p=player(e.batter_id)||player(e.runner_id)||player(e.fielder_id)||player(e.pitcher_id);
    return `${m.label}${p?` • #${N(p.jersey_number,24)} ${p.name}`:''}`;
  }
  function gameFlowData(){
    const scoring=evs().filter(e=>e?.type==='RUN'&&Array.isArray(e.score));
    const pts=[{x:0,a:0,h:0,label:'Start'}];
    scoring.forEach((e,i)=>pts.push({x:i+1,a:N(e.score[0]),h:N(e.score[1]),label:inning(e)}));
    if(!scoring.length)pts.push({x:1,a:N(GG?.away_runs),h:N(GG?.home_runs),label:'Final'});
    return pts;
  }
  function gameFlowChart(){
    const pts=gameFlowData(),w=640,h=190,pad=30,max=Math.max(1,...pts.map(p=>Math.max(p.a,p.h))),den=Math.max(1,pts.length-1);
    const xy=(p,key)=>[pad+(p.x/den)*(w-pad*2),h-pad-(p[key]/max)*(h-pad*2)];
    const path=key=>pts.map((p,i)=>{const [x,y]=xy(p,key);return `${i?'L':'M'}${x.toFixed(1)} ${y.toFixed(1)}`}).join(' ');
    const marks=key=>pts.slice(1).map(p=>{const [x,y]=xy(p,key);return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4"></circle>`}).join('');
    return `<div class="gcFlow141"><div class="gcFlowLegend141"><span class="away">${esc(teamLabel(GG?.away_id))}</span><span class="home">${esc(teamLabel(GG?.home_id))}</span></div><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-label="Game scoring flow"><g class="grid"><line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}"></line><line x1="${pad}" y1="${pad}" x2="${w-pad}" y2="${pad}"></line></g><path class="away" d="${path('a')}"></path><g class="awayMarks">${marks('a')}</g><path class="home" d="${path('h')}"></path><g class="homeMarks">${marks('h')}</g></svg><div class="gcFlowLabels141">${pts.slice(1).map(p=>`<span>${esc(p.label)}<b>${p.a}-${p.h}</b></span>`).join('')}</div></div>`;
  }
  function decidingMoment(){
    const runs=evs().map((e,index)=>({e,index})).filter(x=>x.e?.type==='RUN'&&Array.isArray(x.e.score));if(!runs.length)return null;
    const final=[N(GG?.away_runs),N(GG?.home_runs)],wi=final[1]>final[0]?1:0,oi=wi?0:1;
    for(let i=0;i<runs.length;i++){
      const s=runs[i].e.score;if(N(s[wi])<=N(s[oi]))continue;
      const stays=runs.slice(i+1).every(x=>N(x.e.score?.[wi])>N(x.e.score?.[oi]));if(stays)return runs[i];
    }
    return runs[runs.length-1];
  }
  function appendSummary141(){
    const grid=document.querySelector('#gameView .gcSummaryHeroGameday');if(!grid||document.getElementById('gcSummary141'))return;
    const moments=momentCatalog(),dec=decidingMoment(),de=dec?.e,p=de&&(player(de.batter_id)||player(de.runner_id));
    const card=document.createElement('section');card.id='gcSummary141';card.className='gcSummaryCardGameday gcSummaryWideGameday gcSummary141';
    card.innerHTML=`<h3>GAME FLOW</h3>${gameFlowChart()}<div class="gcSummarySplit141"><div><span class="gcSummaryLabel141">DECIDING PLAY</span>${de?`<b>${esc(inning(de))} • ${esc(teamLabel(de.team))}</b><small>${p?esc(`#${N(p.jersey_number,24)} ${p.name}`):'Scoring play'} • Score ${N(de.score?.[0])}-${N(de.score?.[1])}</small>`:'<b>No scoring play</b>'}</div><div><span class="gcSummaryLabel141">KEY MOMENTS</span><div class="gcSummaryMoments141">${moments.slice(-6).map(m=>`<button data-ebl-action="gamecast-open-event" data-event="${m.index+1}"><b>${esc(m.label)}</b><small>${esc(momentSubtitle(m))}</small></button>`).join('')||'<span class="muted">No key moments recorded.</span>'}</div></div></div>`;
    grid.appendChild(card);
  }

  function afterEvent(e,index){
    ensureDirectorUI();cameraForEvent(e);if(e?.type==='PA_START')clearPitchTrails();if(e?.type==='PITCH')pitchTrail(e);updatePitchMix();updateMomentActive();
    if(e?.type==='RUN'||e?.type==='BALL_IN_PLAY'||e?.type==='GREAT_PLAY')renderMomentStrip();
  }
  const priorRender=window.renderGamecast;
  if(typeof priorRender==='function')window.renderGamecast=function(){const r=priorRender.apply(this,arguments);ensureDirectorUI();setCamera('PITCH');return r};
  const priorStep=window.step;
  if(typeof priorStep==='function')window.step=function(){const index=Math.max(0,N(typeof gi!=='undefined'?gi:0)),e=evs()[index];const r=priorStep.apply(this,arguments);if(e)setTimeout(()=>afterEvent(e,index),0);return r};
  const priorSeek=window.gcSeekEventGameday;
  if(typeof priorSeek==='function')window.gcSeekEventGameday=function(target){const r=priorSeek.apply(this,arguments);ensureDirectorUI();const idx=Math.max(0,Math.min(evs().length-1,N(typeof gi!=='undefined'?gi:0)-1)),e=evs()[idx];cameraForEvent(e);updatePitchMix();updateMomentActive();clearPitchTrails();const start=Math.max(0,N(GC_STATE?.current_pa_start,0));let lp=null;for(let i=start;i<=idx;i++)if(evs()[i]?.type==='PITCH')lp=evs()[i];if(lp)pitchTrail(lp);return r};
  const priorSummary=window.renderGameSummaryGameday;
  if(typeof priorSummary==='function')window.renderGameSummaryGameday=function(){const r=priorSummary.apply(this,arguments);appendSummary141();return r};
  window.EBL_GAMECAST_BUILD=BUILD;
})();

/* EBL GAMECAST RC142 — defensive playbook & batted-ball identity */
(function(){
  'use strict';
  const BUILD='RC142_DEFENSIVE_PLAYBOOK';
  const N=(v,d=0)=>{const n=Number(v);return Number.isFinite(n)?n:d};
  const esc=v=>typeof escapeHtml==='function'?escapeHtml(String(v??'')):String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  const evs=()=>Array.isArray(GG?.events)?GG.events:[];
  const player=pid=>{try{return typeof gamecastPlayerById==='function'?gamecastPlayerById(pid):null}catch(_){return null}};
  const POS_NUM={P:1,C:2,'1B':3,'2B':4,'3B':5,SS:6,LF:7,CF:8,RF:9};
  const POS_COORD={P:[300,282],C:[300,354],'1B':[420,270],'2B':[385,220],'3B':[180,270],SS:[215,220],LF:[145,135],CF:[300,75],RF:[455,135]};
  const BASE={HOME:[300,382],'1B':[441,230],'2B':[300,125],'3B':[159,230]};
  let lastBip142=null,pendingDefense142=null,lastDefenseIndex142=-1;

  function kind(e){
    const r=String(e?.result||'').toUpperCase(),o=String(e?.out_type||'').toLowerCase(),la=N(e?.launch_angle,10);
    if(r==='HR')return 'homer';
    if(o.includes('ground')||la<=5)return 'grounder';
    if(o.includes('line')||(la>5&&la<18))return 'liner';
    return 'fly';
  }
  function landing(e){
    const result=String(e?.result||'').toUpperCase(),ev=N(e?.exit_velocity,90),la=N(e?.launch_angle,10),ang=N(e?.spray_angle);
    let depth=160;
    if(result==='HR')depth=34;else if(result==='3B')depth=70;else if(result==='2B')depth=100;else if(result==='1B'||result==='ROE')depth=145;else depth=Math.max(70,170-Math.max(0,ev-80)*1.25-Math.max(0,la)*.72);
    return {x:Math.max(82,Math.min(518,300+ang*4.65)),y:Math.max(28,Math.min(226,depth))};
  }
  function notation(e,defense=pendingDefense142){
    const pos=String(e?.fielder_position||defense?.position||defense?.fielder_position||'').toUpperCase(),n=POS_NUM[pos]||'';
    const r=String(e?.result||'').toUpperCase(),o=String(e?.out_type||defense?.out_type||'').toLowerCase();
    if(defense?.type==='FIELDING_ERROR')return `E${POS_NUM[String(defense.position||'').toUpperCase()]||''}`.trim();
    if(defense?.type==='RANGE_MISS')return 'RANGE MISS';
    if(defense?.type==='FIELDING_COLLISION')return 'COLLISION';
    if(r==='OUT'&&o.includes('ground'))return pos==='1B'?'3U':(n?`${n}-3`:'GO');
    if(r==='OUT'&&o.includes('line'))return n?`L${n}`:'LO';
    if(r==='OUT'&&o.includes('fly'))return n?`F${n}`:'FO';
    if(r==='1B')return String(e?.defensive_note||'').toUpperCase()==='INFIELD_HIT'?'IF HIT':'1B';
    if(['2B','3B','HR','ROE'].includes(r))return r;
    return r||'BIP';
  }
  function playLabel(e){
    const k=kind(e);return k==='grounder'?'GROUND BALL':k==='liner'?'LINE DRIVE':k==='fly'?'FLY BALL':'HOME RUN';
  }
  function setPlayCamera(e){
    const stage=document.getElementById('gcVisualStageGameday');if(!stage)return;
    stage.classList.remove('gcPlayGrounder142','gcPlayLiner142','gcPlayFly142','gcPlayHomer142');
    const k=kind(e),cls=k==='grounder'?'gcPlayGrounder142':k==='liner'?'gcPlayLiner142':k==='homer'?'gcPlayHomer142':'gcPlayFly142';stage.classList.add(cls);
    const bug=document.querySelector('#gcCameraBug141 b');if(bug)bug.textContent=k==='grounder'?'INFIELD':k==='liner'?'LINE':k==='homer'?'DEEP':'FLY';
  }
  function clearPlayCamera(){const stage=document.getElementById('gcVisualStageGameday');if(stage)stage.classList.remove('gcPlayGrounder142','gcPlayLiner142','gcPlayFly142','gcPlayHomer142')}
  function fielderLabel(e,defense=pendingDefense142){
    const pid=e?.fielder_id||defense?.fielder_id,p=player(pid),pos=String(e?.fielder_position||defense?.position||defense?.fielder_position||'').toUpperCase();
    return p?`#${N(p.jersey_number,24)} ${p.name}${pos?` • ${pos}`:''}`:(pos||'Defense');
  }
  function ensureUI(){
    const stage=document.getElementById('gcVisualStageGameday');if(stage){stage.classList.add('gcRC142Active');if(!document.getElementById('gcPlayRead142')){const d=document.createElement('div');d.id='gcPlayRead142';d.className='gcPlayRead142';d.innerHTML='<span>BATTED BALL</span><b>WAITING FOR CONTACT</b><small>Play type and defensive sequence appear here.</small>';stage.appendChild(d)}}
    const svg=document.querySelector('#gcFieldReplayGameday svg');
    if(svg&&!document.getElementById('gcFlightPath142')){
      const ns='http://www.w3.org/2000/svg';
      const defs=document.createElementNS(ns,'defs');defs.innerHTML='<filter id="gcGlow142"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>';
      svg.appendChild(defs);
      const path=document.createElementNS(ns,'path');path.id='gcFlightPath142';path.setAttribute('class','gcFlightPath142');svg.appendChild(path);
      const ball=document.createElementNS(ns,'circle');ball.id='gcFlightBall142';ball.setAttribute('r','6');ball.setAttribute('cx','0');ball.setAttribute('cy','0');ball.setAttribute('class','gcFlightBall142');svg.appendChild(ball);
      const target=document.createElementNS(ns,'g');target.id='gcCatchTarget142';target.setAttribute('class','gcCatchTarget142');target.innerHTML='<circle r="24"></circle><circle r="11"></circle><text y="4" text-anchor="middle">CATCH</text>';svg.appendChild(target);
      const miss=document.createElementNS(ns,'g');miss.id='gcMissFielder142';miss.setAttribute('class','gcMissFielder142');miss.innerHTML='<circle r="13"></circle><text y="4" text-anchor="middle">F</text>';svg.appendChild(miss);
      const second=document.createElementNS(ns,'g');second.id='gcCollisionFielder142';second.setAttribute('class','gcCollisionFielder142');second.innerHTML='<circle r="13"></circle><text y="4" text-anchor="middle">F</text>';svg.appendChild(second);
      const errPath=document.createElementNS(ns,'path');errPath.id='gcErrorThrowPath142';errPath.setAttribute('class','gcErrorThrowPath142');svg.appendChild(errPath);
      const errBall=document.createElementNS(ns,'circle');errBall.id='gcErrorThrowBall142';errBall.setAttribute('r','6');errBall.setAttribute('class','gcErrorThrowBall142');svg.appendChild(errBall);
    }
    const panel=document.getElementById('gcMatchupGameday');
    if(panel&&!document.getElementById('gcDefenseRead142')){const d=document.createElement('div');d.id='gcDefenseRead142';d.className='gcDefenseRead142';d.innerHTML='<div class="gcMatchLabelGameday">DEFENSIVE READ</div><b>Waiting for a ball in play</b><small>Official fielder and scoring sequence will appear here.</small>';panel.appendChild(d)}
  }
  function resetOverlay(){
    const t=document.getElementById('gcCatchTarget142');if(t)t.classList.remove('show','great');
    const m=document.getElementById('gcMissFielder142');if(m)m.classList.remove('show','miss','error');
    const c=document.getElementById('gcCollisionFielder142');if(c)c.classList.remove('show','collision');
    const ep=document.getElementById('gcErrorThrowPath142');if(ep)ep.classList.remove('show');
    const eb=document.getElementById('gcErrorThrowBall142');if(eb){eb.classList.remove('show');eb.innerHTML=''}
  }
  function updateCards(e,defense=pendingDefense142){
    const read=document.getElementById('gcPlayRead142'),card=document.getElementById('gcDefenseRead142');
    const note=notation(e,defense),who=fielderLabel(e,defense),lbl=playLabel(e),result=String(e?.result||'').toUpperCase();
    if(read)read.innerHTML=`<span>${esc(lbl)}</span><b>${N(e?.exit_velocity).toFixed(1)} MPH • ${N(e?.launch_angle).toFixed(0)}°</b><small>${esc(note)}${who?` • ${esc(who)}`:''}</small>`;
    if(card){
      let detail='Ball in play';
      if(defense?.type==='FIELDING_ERROR')detail=`${String(defense.error_type||'field').toUpperCase()} ERROR`;
      else if(defense?.type==='RANGE_MISS')detail='RANGE MISS';
      else if(defense?.type==='FIELDING_COLLISION')detail='FIELDING COLLISION';
      else if(result==='OUT')detail=String(e?.out_type||'OUT').toUpperCase();
      else if(result==='ROE')detail='REACHED ON ERROR';
      else detail=result||'IN PLAY';
      card.innerHTML=`<div class="gcMatchLabelGameday">DEFENSIVE READ</div><div class="gcDefenseMain142"><strong>${esc(note)}</strong><div><b>${esc(detail)}</b><small>${esc(who||'Defense')}</small></div></div>`;
    }
  }
  function animateMotion(el,path,dur,end){
    if(!el)return;el.innerHTML='';el.setAttribute('cx','0');el.setAttribute('cy','0');el.classList.add('show');
    const ns='http://www.w3.org/2000/svg',am=document.createElementNS(ns,'animateMotion');am.setAttribute('dur',`${dur}ms`);am.setAttribute('path',path);am.setAttribute('fill','freeze');el.appendChild(am);try{am.beginElement()}catch(_){}
    setTimeout(()=>{if(!el.isConnected)return;el.innerHTML='';el.setAttribute('cx',end.x);el.setAttribute('cy',end.y)},dur+20);
  }
  function flight(e){
    ensureUI();resetOverlay();const p=document.getElementById('gcFlightPath142'),b=document.getElementById('gcFlightBall142');if(!p||!b)return;
    const end=landing(e),k=kind(e),midX=300+(end.x-300)*.5;let d,dur;
    if(k==='grounder'){d=`M300 382 Q${midX.toFixed(1)} 330 ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;dur=500}
    else if(k==='liner'){d=`M300 382 Q${midX.toFixed(1)} 205 ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;dur=470}
    else if(k==='homer'){d=`M300 382 Q${midX.toFixed(1)} 8 ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;dur=1220}
    else{d=`M300 382 Q${midX.toFixed(1)} ${Math.max(24,end.y-125).toFixed(1)} ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;dur=980}
    p.setAttribute('d',d);p.setAttribute('class',`gcFlightPath142 ${k} show`);animateMotion(b,d,dur,end);b.setAttribute('class',`gcFlightBall142 ${k} show`);
    setTimeout(()=>p.classList.remove('show'),dur+520);
    if(String(e?.result||'').toUpperCase()==='OUT'&&['liner','fly'].includes(k))setTimeout(()=>catchMoment(e,end,false),Math.max(360,dur-80));
  }
  function catchMoment(e,end,great=false){
    const t=document.getElementById('gcCatchTarget142');if(!t)return;const pos=String(e?.fielder_position||e?.position||'').toUpperCase();
    t.setAttribute('transform',`translate(${end.x} ${end.y})`);const tx=t.querySelector('text');if(tx)tx.textContent=great?'DIVE':(pos||'CATCH');t.classList.remove('show','great');void t.getBBox?.();t.classList.add('show');if(great)t.classList.add('great');setTimeout(()=>t.classList.remove('show','great'),1100);
  }
  function missAnimation(e,defense){
    const pos=String(defense?.position||defense?.fielder_position||e?.fielder_position||'').toUpperCase(),start=POS_COORD[pos],end=landing(e),g=document.getElementById('gcMissFielder142');if(!start||!g)return;
    const stop={x:start[0]+(end.x-start[0])*.78,y:start[1]+(end.y-start[1])*.78},tx=g.querySelector('text');if(tx)tx.textContent=pos||'F';g.setAttribute('transform',`translate(${start[0]} ${start[1]})`);g.className.baseVal='gcMissFielder142 show miss';
    const path=`M${start[0]} ${start[1]} Q${((start[0]+stop.x)/2).toFixed(1)} ${Math.min(start[1],stop.y)-18} ${stop.x.toFixed(1)} ${stop.y.toFixed(1)}`;
    const ns='http://www.w3.org/2000/svg',am=document.createElementNS(ns,'animateMotion');am.setAttribute('dur','.72s');am.setAttribute('path',path);am.setAttribute('fill','freeze');g.appendChild(am);try{am.beginElement()}catch(_){}
    setTimeout(()=>{g.querySelectorAll('animateMotion').forEach(x=>x.remove());g.classList.remove('show','miss')},1350);
  }
  function errorAnimation(e,defense){
    const type=String(defense?.error_type||'field').toLowerCase(),pos=String(defense?.position||e?.fielder_position||'').toUpperCase(),start=POS_COORD[pos]||landing(e),miss=document.getElementById('gcMissFielder142');
    if(type==='field'){
      if(miss){const tx=miss.querySelector('text');if(tx)tx.textContent=pos||'E';miss.setAttribute('transform',`translate(${start[0]} ${start[1]})`);miss.className.baseVal='gcMissFielder142 show error';setTimeout(()=>miss.classList.remove('show','error'),1200)}
      return;
    }
    const path=document.getElementById('gcErrorThrowPath142'),ball=document.getElementById('gcErrorThrowBall142');if(!path||!ball)return;
    const one=BASE['1B'],end=type==='receive'?one:{x:522,y:246},d=`M${start[0]} ${start[1]} Q${((start[0]+one[0])/2).toFixed(1)} ${Math.min(start[1],one[1])-34} ${end.x} ${end.y}`;
    path.setAttribute('d',d);path.classList.add('show');animateMotion(ball,d,650,end);setTimeout(()=>{path.classList.remove('show');ball.classList.remove('show')},1150);
    if(type==='receive')setTimeout(()=>{if(miss){const tx=miss.querySelector('text');if(tx)tx.textContent='1B';miss.setAttribute('transform',`translate(${one[0]} ${one[1]})`);miss.className.baseVal='gcMissFielder142 show error';setTimeout(()=>miss.classList.remove('show','error'),800)}},620);
  }
  function collisionAnimation(e,defense){
    const pos=String(defense?.position||e?.fielder_position||'CF').toUpperCase(),a=POS_COORD[pos]||POS_COORD.CF,end=landing(e),other=pos==='LF'?POS_COORD.CF:pos==='RF'?POS_COORD.CF:POS_COORD.RF;
    const one=document.getElementById('gcMissFielder142'),two=document.getElementById('gcCollisionFielder142');if(!one||!two)return;
    const set=(g,start,label)=>{const tx=g.querySelector('text');if(tx)tx.textContent=label;g.setAttribute('transform',`translate(${start[0]} ${start[1]})`);g.className.baseVal='gcMissFielder142 show collision';const d=`M${start[0]} ${start[1]} L${end.x} ${end.y}`,ns='http://www.w3.org/2000/svg',am=document.createElementNS(ns,'animateMotion');am.setAttribute('dur','.68s');am.setAttribute('path',d);am.setAttribute('fill','freeze');g.appendChild(am);try{am.beginElement()}catch(_){}};
    set(one,a,pos||'OF');const tx=two.querySelector('text');if(tx)tx.textContent='OF';two.setAttribute('transform',`translate(${other[0]} ${other[1]})`);two.className.baseVal='gcCollisionFielder142 show collision';const d2=`M${other[0]} ${other[1]} L${end.x} ${end.y}`,ns='http://www.w3.org/2000/svg',am2=document.createElementNS(ns,'animateMotion');am2.setAttribute('dur','.72s');am2.setAttribute('path',d2);am2.setAttribute('fill','freeze');two.appendChild(am2);try{am2.beginElement()}catch(_){}
    setTimeout(()=>{one.querySelectorAll('animateMotion').forEach(x=>x.remove());two.querySelectorAll('animateMotion').forEach(x=>x.remove());one.classList.remove('show','collision');two.classList.remove('show','collision')},1400);
  }
  function applyDefenseOutcome(e){
    if(!pendingDefense142)return;
    const d=pendingDefense142;pendingDefense142=null;
    if(d.type==='RANGE_MISS')missAnimation(e,d);
    else if(d.type==='FIELDING_ERROR')errorAnimation(e,d);
    else if(d.type==='FIELDING_COLLISION')collisionAnimation(e,d);
  }
  function defenseEvent(e,index){
    if(['FIELDING_ERROR','RANGE_MISS','FIELDING_COLLISION'].includes(e?.type)){pendingDefense142=e;lastDefenseIndex142=index;return}
    if(e?.type==='BALL_IN_PLAY'){
      lastBip142=e;ensureUI();setPlayCamera(e);updateCards(e,pendingDefense142);flight(e);applyDefenseOutcome(e);
    }
    if(e?.type==='GREAT_PLAY'&&lastBip142){const end=landing(lastBip142);catchMoment({...lastBip142,...e},end,true);const card=document.getElementById('gcDefenseRead142');if(card)card.innerHTML=`<div class="gcMatchLabelGameday">DEFENSIVE READ</div><div class="gcDefenseMain142"><strong>WEB GEM</strong><div><b>${esc(String(e.out_type||lastBip142.out_type||'OUT').toUpperCase())}</b><small>${esc(fielderLabel({...lastBip142,...e}))}</small></div></div>`}
    if(e?.type==='OUTFIELD_HOLD'&&lastBip142){const card=document.getElementById('gcDefenseRead142');if(card)card.innerHTML=`<div class="gcMatchLabelGameday">DEFENSIVE READ</div><div class="gcDefenseMain142"><strong>RUNNER HELD</strong><div><b>STRONG THROW</b><small>${esc(fielderLabel({...lastBip142,...e}))}</small></div></div>`}
    if(e?.type==='PA_START'){pendingDefense142=null;clearPlayCamera();const read=document.getElementById('gcPlayRead142');if(read)read.innerHTML='<span>BATTED BALL</span><b>WAITING FOR CONTACT</b><small>Play type and defensive sequence appear here.</small>'}
  }
  function latestBipBefore(idx){for(let i=Math.min(idx,evs().length-1);i>=0;i--)if(evs()[i]?.type==='BALL_IN_PLAY')return evs()[i];return null}
  function defensiveHighlights(){
    const all=evs(),out=[];
    all.forEach((e,index)=>{if(['GREAT_PLAY','OUTFIELD_HOLD','FIELDING_ERROR','RANGE_MISS','FIELDING_COLLISION'].includes(e?.type))out.push({e,index})});
    return out.slice(-8);
  }
  function appendSummary(){
    const grid=document.querySelector('#gameView .gcSummaryHeroGameday');if(!grid||document.getElementById('gcDefenseSummary142'))return;
    const rows=defensiveHighlights();const card=document.createElement('section');card.id='gcDefenseSummary142';card.className='gcSummaryCardGameday gcSummaryWideGameday gcDefenseSummary142';
    card.innerHTML=`<h3>DEFENSIVE HIGHLIGHTS</h3>${rows.length?`<div class="gcDefenseHighlights142">${rows.map(({e,index})=>{const p=player(e.fielder_id),label=e.type==='GREAT_PLAY'?'GREAT PLAY':e.type==='OUTFIELD_HOLD'?'STRONG THROW':e.type==='FIELDING_ERROR'?'ERROR':e.type==='RANGE_MISS'?'RANGE MISS':'COLLISION';return `<button data-ebl-action="gamecast-open-event" data-event="${index+1}"><span>${esc(`${String(e.half||'TOP').toUpperCase()==='BOT'?'BOT':'TOP'} ${N(e.inning,1)}`)}</span><b>${esc(label)}</b><small>${p?esc(`#${N(p.jersey_number,24)} ${p.name}`):esc(String(e.position||e.fielder_position||'Defense'))}</small></button>`}).join('')}</div>`:'<p class="muted">No exceptional defensive events were recorded.</p>'}`;
    grid.appendChild(card);
  }

  const priorRender=window.renderGamecast;
  if(typeof priorRender==='function')window.renderGamecast=function(){pendingDefense142=null;lastBip142=null;const r=priorRender.apply(this,arguments);ensureUI();return r};
  const priorStep=window.step;
  if(typeof priorStep==='function')window.step=function(){const index=Math.max(0,N(typeof gi!=='undefined'?gi:0)),e=evs()[index];const r=priorStep.apply(this,arguments);if(e)setTimeout(()=>defenseEvent(e,index),12);return r};
  const priorSeek=window.gcSeekEventGameday;
  if(typeof priorSeek==='function')window.gcSeekEventGameday=function(target){const r=priorSeek.apply(this,arguments);ensureUI();const idx=Math.max(0,Math.min(evs().length-1,N(typeof gi!=='undefined'?gi:0)-1)),b=latestBipBefore(idx);pendingDefense142=null;if(b){lastBip142=b;updateCards(b,null)}return r};
  const priorSummary=window.renderGameSummaryGameday;
  if(typeof priorSummary==='function')window.renderGameSummaryGameday=function(){const r=priorSummary.apply(this,arguments);appendSummary();return r};
  window.EBL_GAMECAST_BUILD=BUILD;
})();


/* EBL GAMECAST RC143 — mobile broadcast cleanup marker */
window.EBL_GAMECAST_MOBILE_BUILD='RC143_MOBILE_BROADCAST_CLEANUP';


/* EBL GAMECAST RC144 — simple reliable replay */
(function(){
  'use strict';
  const BUILD='RC144_SIMPLE_RELIABLE_REPLAY';
  const N=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
  const esc=v=>typeof escapeHtml==='function'?escapeHtml(String(v??'')):String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));
  const events=()=>Array.isArray(GG?.events)?GG.events:[];
  const pById=id=>{try{return typeof gamecastPlayerById==='function'?gamecastPlayerById(id):null}catch(_){return null}};
  const pName=id=>{const p=pById(id);return p?`#${N(p.jersey_number,24)} ${p.name}`:'Player'};
  const desc=e=>{try{return typeof describe==='function'?describe(e):String(e?.type||'PLAY').replaceAll('_',' ')}catch(_){return String(e?.type||'PLAY').replaceAll('_',' ')}};
  const inning=e=>`${String(e?.half||GC_STATE?.half||'TOP').toUpperCase()==='BOT'?'BOT':'TOP'} ${N(e?.inning,GC_STATE?.inning||1)}`;
  const pitchClass=call=>{const s=String(call||'').toLowerCase();if(s==='ball')return'ball';if(s.includes('foul'))return'foul';if(s.includes('in play'))return'play';return'strike'};
  const pitchXY=e=>({x:Math.max(6,Math.min(94,8+N(e?.px,.5)*84)),y:Math.max(5,Math.min(95,8+(1-N(e?.pz,.5))*84))});
  function resetState(){GC_STATE={score:[0,0],inning:1,half:'TOP',balls:0,strikes:0,outs:0,runner:null,base:0,batter_id:null,pitcher_id:null,pitch_no:0,last_event:null};}
  function setScoreboard(){
    const a=document.getElementById('gcAwayScore'),h=document.getElementById('gcHomeScore'),inn=document.getElementById('gcInning'),cnt=document.getElementById('gcCount');
    if(a)a.textContent=GC_STATE.score?.[0]??0;if(h)h.textContent=GC_STATE.score?.[1]??0;
    if(inn)inn.textContent=`${GC_STATE.half==='BOT'?'BOT':'TOP'} ${GC_STATE.inning||1}`;
    if(cnt)cnt.textContent=`${GC_STATE.balls||0}-${GC_STATE.strikes||0} • ${GC_STATE.outs||0} OUT${GC_STATE.outs===1?'':'S'}`;
    ['1','2','3'].forEach(n=>{const b=document.getElementById('gcB'+n);if(b)b.classList.toggle('on',N(n)===N(GC_STATE.base)&&!!GC_STATE.runner)});
    const r=document.getElementById('gcSimpleTimeline');if(r){r.max=String(events().length);r.value=String(Math.max(0,Math.min(events().length,N(gi))))}
    const t=document.getElementById('gcSimpleTimelineLabel');if(t)t.textContent=`${Math.max(0,Math.min(events().length,N(gi)))} / ${events().length}`;
  }
  window.gcUpdateScoreboard=setScoreboard;
  function matchupText(){
    const b=pById(GC_STATE.batter_id),p=pById(GC_STATE.pitcher_id);
    const el=document.getElementById('gcSimpleMatchup');
    if(el)el.innerHTML=b&&p?`<b>${esc(pName(GC_STATE.batter_id))}</b><span>vs ${esc(pName(GC_STATE.pitcher_id))}</span>`:'<b>Waiting for next batter</b><span>Matchup will appear here.</span>';
  }
  function currentPlay(title,text,meta=''){
    const el=document.getElementById('gcSimpleCurrent');if(!el)return;
    el.innerHTML=`<span class="gcSimpleKicker">${esc(title)}</span><strong>${esc(text)}</strong>${meta?`<small>${esc(meta)}</small>`:''}`;
  }
  function addPitch(e){
    const seq=document.getElementById('gcSimplePitchList'),dots=document.getElementById('gcSimpleDots');
    const n=N(e.pitch_no,GC_STATE.pitch_no+1);GC_STATE.pitch_no=n;const cls=pitchClass(e.call),xy=pitchXY(e);
    if(seq){if(n===1)seq.innerHTML='';const row=document.createElement('div');row.className='gcSimplePitch';row.innerHTML=`<span class="gcSimplePitchNo ${cls}">${n}</span><span><b>${esc(e.pitch_type||'Pitch')} • ${N(e.velocity).toFixed(1)} MPH</b><small>${esc(e.call||'')} • ${N(e.balls)}-${N(e.strikes)}</small></span>`;seq.appendChild(row)}
    if(dots){const d=document.createElement('i');d.className=`gcSimpleDot ${cls}`;d.style.left=xy.x+'%';d.style.top=xy.y+'%';d.textContent=n;dots.appendChild(d)}
    currentPlay('PITCH',`${e.pitch_type||'Pitch'} • ${N(e.velocity).toFixed(1)} MPH`,`${e.call||''} • Count ${N(e.balls)}-${N(e.strikes)}`);
  }
  function clearPA(){
    GC_STATE.pitch_no=0;const seq=document.getElementById('gcSimplePitchList'),dots=document.getElementById('gcSimpleDots');
    if(seq)seq.innerHTML='<div class="gcSimpleEmpty">No pitches yet.</div>';if(dots)dots.innerHTML='';
  }
  function meaningful(e){return !['PA_START','PITCH'].includes(String(e?.type||''))}
  function feed(e){
    if(!meaningful(e))return;const f=document.getElementById('gcSimpleFeed');if(!f)return;
    const row=document.createElement('div');row.className='gcSimpleFeedRow';row.innerHTML=`<span>${esc(e?.inning?inning(e):String(e?.type||'PLAY').replaceAll('_',' '))}</span><b>${esc(desc(e))}</b>`;f.prepend(row);while(f.children.length>18)f.removeChild(f.lastChild);
  }
  function ballInPlay(e){
    let meta='';if(Number.isFinite(Number(e.exit_velocity)))meta+=`${N(e.exit_velocity).toFixed(1)} MPH EV`;if(Number.isFinite(Number(e.launch_angle)))meta+=`${meta?' • ':''}${N(e.launch_angle).toFixed(0)}° LA`;
    if(e.fielder_position)meta+=`${meta?' • ':''}${e.fielder_position}`;
    currentPlay('BALL IN PLAY',String(e.result||e.out_type||'Ball in play'),meta);
    const field=document.getElementById('gcSimpleFieldText');if(field){const who=e.fielder_id?pName(e.fielder_id):(e.fielder_position||'Defense');field.innerHTML=`<b>${esc(e.result||e.out_type||'Ball in play')}</b><span>${esc(who)}${e.defensive_note?` • ${esc(e.defensive_note)}`:''}</span>`}
  }
  function updateState(e,silent=false){
    if(!e)return;GC_STATE.last_event=e;
    if(e.score)GC_STATE.score=[N(e.score[0]),N(e.score[1])];if(e.final_score)GC_STATE.score=[N(e.final_score[0]),N(e.final_score[1])];
    if(e.inning)GC_STATE.inning=N(e.inning,1);if(e.half&&['TOP','BOT'].includes(String(e.half).toUpperCase()))GC_STATE.half=String(e.half).toUpperCase();if(Number.isFinite(Number(e.outs)))GC_STATE.outs=N(e.outs);
    if(e.type==='PA_START'){GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.batter_id=e.batter_id;GC_STATE.pitcher_id=e.pitcher_id;clearPA();matchupText();if(!silent)currentPlay('AT BAT',pName(e.batter_id),`vs ${pName(e.pitcher_id)}`)}
    else if(e.type==='PITCH'){GC_STATE.balls=N(e.balls);GC_STATE.strikes=N(e.strikes);if(!silent)addPitch(e);else GC_STATE.pitch_no=N(e.pitch_no,GC_STATE.pitch_no+1)}
    else if(e.type==='BALL_IN_PLAY'){if(!silent)ballInPlay(e)}
    else if(e.type==='PA_END'){
      const r=String(e.result||'').toUpperCase();if(['1B','ROE'].includes(r)){GC_STATE.runner=e.batter_id;GC_STATE.base=1}else if(r==='BB'&&!GC_STATE.runner){GC_STATE.runner=e.batter_id;GC_STATE.base=1}else if(r==='2B'){GC_STATE.runner=e.batter_id;GC_STATE.base=2}else if(r==='3B'){GC_STATE.runner=e.batter_id;GC_STATE.base=3}else if(r==='HR'){GC_STATE.runner=null;GC_STATE.base=0}
      if(!silent)currentPlay('AT-BAT RESULT',desc(e),inning(e));
    }
    else if(e.type==='STEAL_ATTEMPT'){if(e.success&&GC_STATE.runner)GC_STATE.base=Math.min(3,(GC_STATE.base||1)+1);if(!e.success){GC_STATE.runner=null;GC_STATE.base=0}if(!silent)currentPlay('BASERUNNING',e.success?'Stolen base':'Caught stealing',desc(e))}
    else if(e.type==='PICKOFF'){GC_STATE.runner=null;GC_STATE.base=0;if(!silent)currentPlay('BASERUNNING','Picked off',desc(e))}
    else if(e.type==='RUN'){GC_STATE.runner=null;GC_STATE.base=0;if(!silent)currentPlay('RUN SCORES',desc(e),`${GC_STATE.score[0]}-${GC_STATE.score[1]}`)}
    else if(e.type==='PITCHING_CHANGE'){GC_STATE.pitcher_id=e.pitcher_id;if(!silent){matchupText();currentPlay('PITCHING CHANGE',desc(e),pName(e.pitcher_id))}}
    else if(e.type==='OUT'&&!silent)currentPlay('OUT',e.out_type||desc(e),inning(e));
    else if(e.type==='GREAT_PLAY'&&!silent)currentPlay('GREAT PLAY',desc(e),e.defensive_note||'');
    else if(e.type==='FIELDING_ERROR'&&!silent)currentPlay('ERROR',desc(e),e.defensive_note||'');
    else if(e.type==='INNING_END'){GC_STATE.outs=0;GC_STATE.balls=0;GC_STATE.strikes=0;GC_STATE.runner=null;GC_STATE.base=0;if(!silent)currentPlay('INNING COMPLETE',desc(e),inning(e))}
    else if(e.type==='GAME_END'&&!silent)currentPlay('FINAL',`${GC_STATE.score[0]} - ${GC_STATE.score[1]}`,desc(e));
    else if(!silent)currentPlay(String(e.type||'PLAY').replaceAll('_',' '),desc(e),e?.inning?inning(e):'');
    if(!silent)feed(e);
  }
  function rebuild(count){
    resetState();gi=0;const lim=Math.max(0,Math.min(events().length,N(count)));
    for(let i=0;i<lim;i++){updateState(events()[i],true);gi=i+1}
    clearPA();matchupText();
    const paStart=Math.max(0,[...Array(lim).keys()].reverse().find(i=>events()[i]?.type==='PA_START')??0);
    for(let i=paStart;i<lim;i++){const e=events()[i];if(e?.type==='PITCH')addPitch(e);if(e?.type==='BALL_IN_PLAY')ballInPlay(e)}
    const f=document.getElementById('gcSimpleFeed');if(f){f.innerHTML='';for(let i=Math.max(0,lim-30);i<lim;i++)feed(events()[i])}
    const last=lim?events()[lim-1]:null;if(last&&last.type!=='PITCH'&&last.type!=='BALL_IN_PLAY')currentPlay(String(last.type||'PLAY').replaceAll('_',' '),desc(last),last?.inning?inning(last):'');
    setScoreboard();
  }
  window.gcSeekEventGameday=function(target){clearInterval(timer);rebuild(target)};
  window.gcSeekEndGameday=function(){window.gcSeekEventGameday(events().length)};
  window.gcReplayGameday=function(){window.gcSeekEventGameday(0)};
  window.gcPlayGameday=function(ms=900){clearInterval(timer);timer=setInterval(window.step,Math.max(180,N(ms,900)))};
  window.gcPauseGameday=function(){clearInterval(timer)};
  window.gcSeekPaGameday=function(direction=1){
    const starts=[];events().forEach((e,i)=>{if(e?.type==='PA_START')starts.push(i)});if(!starts.length)return;
    const cur=Math.max(0,N(gi)-1);let target=starts[0];
    if(N(direction)>=0){target=starts.find(x=>x>cur)??starts[starts.length-1]}else{const prior=starts.filter(x=>x<cur);target=prior.length?prior[prior.length-1]:starts[0]}
    window.gcSeekEventGameday(target+1);
  };
  window.step=function(){
    if(gi>=events().length){clearInterval(timer);setScoreboard();return}
    const e=events()[gi++];updateState(e,false);setScoreboard();if(e.type==='GAME_END')clearInterval(timer);
  };
  window.renderGamecast=function(){
    clearInterval(timer);resetState();gi=0;const host=document.getElementById('gameView');if(!host)return;
    host.innerHTML=`<div class="gcSimpleReplay">
      <section class="gcSimpleMain">
        <div id="gcSimpleCurrent" class="gcSimpleCurrent"><span class="gcSimpleKicker">GAMECAST</span><strong>Ready to replay</strong><small>Press Play to watch the game unfold.</small></div>
        <div id="gcSimpleMatchup" class="gcSimpleMatchup"><b>Waiting for next batter</b><span>Matchup will appear here.</span></div>
        <div class="gcSimpleVisuals">
          <div class="gcSimpleZoneCard"><div class="gcSimpleLabel">PITCH LOCATION</div><div class="gcSimpleZone"><div class="gcSimpleZoneGrid"></div><div id="gcSimpleDots"></div></div></div>
          <div class="gcSimpleFieldCard"><div class="gcSimpleLabel">PLAY RESULT</div><div class="gcSimpleDiamond"><i></i><i></i><i></i><i></i></div><div id="gcSimpleFieldText" class="gcSimpleFieldText"><b>Waiting for contact</b><span>Fielding result appears here.</span></div></div>
        </div>
        <div class="gcSimpleControls"><button class="gcMiniBtnGameday primary" data-ebl-action="gamecast-play" data-speed="900">▶ PLAY</button><button class="gcMiniBtnGameday" data-ebl-action="gamecast-pause">Ⅱ PAUSE</button><button class="gcMiniBtnGameday" data-ebl-action="gamecast-play" data-speed="320">FAST</button><button class="gcMiniBtnGameday" data-ebl-action="gamecast-instant">END</button><button class="gcMiniBtnGameday" data-ebl-action="gamecast-replay">↺ REPLAY</button></div>
        <div class="gcSimpleTimelineWrap"><button class="gcTimelineBtnGameday" data-ebl-action="gamecast-seek-pa" data-direction="-1">‹ PA</button><input id="gcSimpleTimeline" type="range" min="0" max="${events().length}" value="0"><span id="gcSimpleTimelineLabel">0 / ${events().length}</span><button class="gcTimelineBtnGameday" data-ebl-action="gamecast-seek-pa" data-direction="1">PA ›</button></div>
      </section>
      <aside class="gcSimpleSide">
        <section class="gcPanelGameday"><div class="gcPanelHeadGameday"><strong>PITCHES THIS AT-BAT</strong><span id="gcPitchCountGameday"></span></div><div id="gcSimplePitchList" class="gcSimplePitchList"><div class="gcSimpleEmpty">No pitches yet.</div></div></section>
        <section class="gcPanelGameday"><div class="gcPanelHeadGameday"><strong>WHAT HAPPENED</strong><span>GAME FEED</span></div><div id="gcSimpleFeed" class="gcSimpleFeed"><div class="gcSimpleEmpty">Press Play to begin.</div></div></section>
      </aside>
    </div>`;
    const range=document.getElementById('gcSimpleTimeline');if(range){range.addEventListener('input',()=>{clearInterval(timer);document.getElementById('gcSimpleTimelineLabel').textContent=`${range.value} / ${events().length}`});range.addEventListener('change',()=>window.gcSeekEventGameday(N(range.value)))}
    setScoreboard();
  };
  window.EBL_GAMECAST_BUILD=BUILD;
})();
