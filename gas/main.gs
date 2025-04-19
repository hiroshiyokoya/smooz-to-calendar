// gas/main.gs

function checkSmoozMail() {
  const labelName = "Smooz";
  const label = GmailApp.getUserLabelByName(labelName) || GmailApp.createLabel(labelName);

  const threads = GmailApp.search('from:info@smooz.jp subject:【チケットレスサービス「Smooz」】 -label:' + labelName);
  if (threads.length === 0) return;

  const latestThread = threads[0];
  const alreadyProcessed = PropertiesService.getScriptProperties().getProperty("lastThreadId");
  if (alreadyProcessed === latestThread.getId().toString()) return;

  UrlFetchApp.fetch("https://YOUR_CLOUD_RUN_URL/fetch_and_update", {
    method: "post",
    muteHttpExceptions: true
  });

  PropertiesService.getScriptProperties().setProperty("lastThreadId", latestThread.getId());
  threads.forEach(thread => thread.addLabel(label));
}

function resetLastThreadId() {
  PropertiesService.getScriptProperties().deleteProperty("lastThreadId");
}
