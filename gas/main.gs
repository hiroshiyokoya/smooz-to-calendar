// gas/main.gs

/**
 * Smoozメールの処理を行うGoogle Apps Script。
 */

// 定数
const LABEL_NAME = "Smooz";
const LAST_THREAD_ID_PROPERTY = "lastThreadId";
const SMOOZ_MAIL_QUERY = "from:info@smooz.jp subject:【チケットレスサービス「Smooz」】 -label:";
const CLOUD_RUN_URL = "https://YOUR_CLOUD_RUN_URL/fetch_and_update"; // 実際のURLに置換してください

/**
 * Smoozラベルを取得する。存在しない場合は作成する。
 *
 * @return {GoogleAppsScript.Gmail.GmailLabel} Smoozラベル
 */
function getSmoozLabel() {
  const label = GmailApp.getUserLabelByName(LABEL_NAME) || GmailApp.createLabel(LABEL_NAME);
  return label;
}

/**
 * 最新のSmoozメールスレッドを取得する。
 *
 * @return {GoogleAppsScript.Gmail.GmailThread|null} 最新のSmoozメールスレッド。存在しない場合は null。
 */
function getLatestThread() {
  const threads = GmailApp.search(SMOOZ_MAIL_QUERY + LABEL_NAME);
  return threads.length > 0 ? threads[0] : null;
}

/**
 * メールスレッドが既に処理済みかどうかを判定する。
 *
 * @param {GoogleAppsScript.Gmail.GmailThread} thread メールスレッド
 * @return {boolean} 処理済みであれば true、未処理であれば false
 */
function isAlreadyProcessed(thread) {
  const alreadyProcessed = PropertiesService.getScriptProperties().getProperty(LAST_THREAD_ID_PROPERTY);
  return alreadyProcessed === thread.getId().toString();
}

/**
 * 処理済みのスレッドIDを記録する。
 *
 * @param {GoogleAppsScript.Gmail.GmailThread} thread 処理済みメールスレッド
 */
function updateLastThreadId(thread) {
  PropertiesService.getScriptProperties().setProperty(LAST_THREAD_ID_PROPERTY, thread.getId());
}

/**
 * メールスレッドを処理する。
 *
 * @param {GoogleAppsScript.Gmail.GmailThread} thread メールスレッド
 * @param {GoogleAppsScript.Gmail.GmailLabel} label Smoozラベル
 */
function processThreads(threads, label) {
  threads.forEach(thread => thread.addLabel(label));
}

/**
 * Smoozメールをチェックし、必要に応じて処理を行うメイン処理。
 */
function checkSmoozMail() {
  const label = getSmoozLabel();
  const latestThread = getLatestThread();

  // 最新のスレッドがない場合には終了
  if (!latestThread) return;

  // 処理済みのスレッドであった場合には終了
  if (isAlreadyProcessed(latestThread)) return;

  // fetch_and_updateを実行する。
  try {
    const response = UrlFetchApp.fetch(CLOUD_RUN_URL, {
      method: "post",
      muteHttpExceptions: true
    });
    console.log("正常に実行されました:" + response.getContentText());
  } catch (e) {
    console.error("実行中にエラーが発生しました:", e);
  }

  updateLastThreadId(latestThread)
  processThreads([latestThread], label);
}

/**
 * 最後に処理したスレッドのIDをリセットする。
 */
function resetLastThreadId() {
  PropertiesService.getScriptProperties().deleteProperty(LAST_THREAD_ID_PROPERTY);
}
