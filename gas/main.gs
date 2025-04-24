// gas/main.gs

/**
 * Smoozメールの処理を行うGoogle Apps Script。
 */

/**
 * 設定値
 */
const Config = {
  // ラベル設定
  LABEL_NAME: "Smooz",

  // プロパティ設定
  PROPERTY_LAST_THREAD_ID: "lastThreadId",
  PROPERTY_LAST_PROCESSED_TIME: "lastProcessedTime",

  // クエリ設定
  SMOOZ_MAIL_QUERY: "from:info@smooz.jp subject:【チケットレスサービス「Smooz」】 -label:",

  // API設定
  CLOUD_RUN_URL: "https://YOUR_CLOUD_RUN_URL/fetch_and_update", // 実際のURLに置換してください

  // デバッグ設定
  DEBUG_MODE: false // デバッグ時は true に設定
};

/**
 * Smoozラベルを取得する。存在しない場合は作成する。
 *
 * @return {GoogleAppsScript.Gmail.GmailLabel} Smoozラベル
 */
function getSmoozLabel() {
  const label = GmailApp.getUserLabelByName(Config.LABEL_NAME) || GmailApp.createLabel(Config.LABEL_NAME);
  return label;
}

/**
 * 最新のSmoozメールスレッドを取得する。
 *
 * @return {GoogleAppsScript.Gmail.GmailThread|null} 最新のSmoozメールスレッド。存在しない場合は null。
 */
function getLatestThread() {
  const threads = GmailApp.search(Config.SMOOZ_MAIL_QUERY + "-label:" + Config.LABEL_NAME);
  return threads.length > 0 ? threads[0] : null;
}

/**
 * メールスレッドが既に処理済みかどうかを判定する。
 *
 * @param {GoogleAppsScript.Gmail.GmailThread} thread メールスレッド
 * @return {boolean} 処理済みであれば true、未処理であれば false
 */
function isAlreadyProcessed(thread) {
  // デバッグモードの場合は常に未処理として扱う
  if (Config.DEBUG_MODE) {
    return false;
  }

  const lastThreadId = PropertiesService.getScriptProperties().getProperty(Config.PROPERTY_LAST_THREAD_ID);
  const lastProcessedTime = PropertiesService.getScriptProperties().getProperty(Config.PROPERTY_LAST_PROCESSED_TIME);

  // スレッドIDが同じで、かつ最新のメールの受信時間が前回の処理時間より前の場合
  if (lastThreadId === thread.getId().toString() && lastProcessedTime) {
    const lastMessage = thread.getMessages()[thread.getMessageCount() - 1];
    const lastMessageTime = lastMessage.getDate().getTime();
    return lastMessageTime <= parseInt(lastProcessedTime);
  }

  return false;
}

/**
 * 処理済みのスレッドIDと処理時間を記録する。
 *
 * @param {GoogleAppsScript.Gmail.GmailThread} thread 処理済みメールスレッド
 */
function updateLastThreadId(thread) {
  PropertiesService.getScriptProperties().setProperty(Config.PROPERTY_LAST_THREAD_ID, thread.getId());
  PropertiesService.getScriptProperties().setProperty(Config.PROPERTY_LAST_PROCESSED_TIME, new Date().getTime().toString());
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
    const response = UrlFetchApp.fetch(Config.CLOUD_RUN_URL, {
      method: "post",
      muteHttpExceptions: true
    });

    const responseText = response.getContentText();
    if (response.getResponseCode() === 200) {
      console.log("Cloud Run の処理が正常に完了しました");
    } else {
      console.error("Cloud Run でエラーが発生しました:", responseText);
    }
  } catch (e) {
    console.error("Cloud Run へのリクエスト中にエラーが発生しました:", e.toString());
  }

  updateLastThreadId(latestThread);
  processThreads([latestThread], label);
}

/**
 * 最後に処理したスレッドのIDと処理時間をリセットする。
 */
function resetLastThreadId() {
  PropertiesService.getScriptProperties().deleteProperty(Config.PROPERTY_LAST_THREAD_ID);
  PropertiesService.getScriptProperties().deleteProperty(Config.PROPERTY_LAST_PROCESSED_TIME);
  console.log("処理済みのスレッドIDと処理時間をリセットしました");
}
