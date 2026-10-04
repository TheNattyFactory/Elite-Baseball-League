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
