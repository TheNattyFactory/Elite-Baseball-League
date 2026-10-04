/* Elite Baseball League — ebl-static-command-router */
(()=>{
  const allowed=new Set(["login", "requestReset", "sendDM", "repairHumanRosters", "resetLeague", "simDay", "advanceSeason", "loadLab", "applyGenesisLeagueSize", "loadCoachApplications", "loadCoachAssignments", "backupNow", "loadStorageStatus", "optimizeStorage", "resetTestAccount", "loadBetaFeedback", "loadReports", "loadLegalRequests", "openBetaFeedback", "submitBetaFeedback"]);
  document.addEventListener('click',event=>{
    const control=event.target.closest('[data-ebl-command]');
    if(!control)return;
    const command=control.dataset.eblCommand||'';
    if(!allowed.has(command))return;
    const handler=window[command];
    if(typeof handler!=="function")return;
    event.preventDefault();
    handler();
  });
})();
