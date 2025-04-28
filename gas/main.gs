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

  // クエリ設定
  SMOOZ_MAIL_QUERY: "from:info@smooz.jp subject:【チケットレスサービス「Smooz」】",

  // API設定
  CLOUD_RUN_URL: "https://YOUR_CLOUD_RUN_URL/fetch_and_update", // 実際のURLに置換してください

  // 実行間隔設定
  FORCE_RUN_INTERVAL_HOURS: 3 // 強制実行までの時間間隔（時間）
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
  const query = `${Config.SMOOZ_MAIL_QUERY} -label:${Config.LABEL_NAME}`;
  console.log(`検索クエリ: ${query}`);
  const threads = GmailApp.search(query);
  if (threads.length === 0) {
    console.log("新しいSmoozメールは見つかりませんでした");
  }
  return threads.length > 0 ? threads[0] : null;
}

/**
 * メールスレッドの情報を文字列として取得する。
 *
 * @param {GoogleAppsScript.Gmail.GmailThread} thread メールスレッド
 * @return {string} メールスレッドの情報
 */
function getThreadInfo(thread) {
  const messages = thread.getMessages();
  const firstMessage = messages[0];
  const lastMessage = messages[messages.length - 1];
  const labels = thread.getLabels().map(l => l.getName());

  return `
スレッドID: ${thread.getId()}
件名: ${firstMessage.getSubject()}
送信者: ${firstMessage.getFrom()}
受信日時: ${firstMessage.getDate()}
最終更新: ${lastMessage.getDate()}
現在のラベル: ${labels.join(", ")}
メッセージ数: ${messages.length}
  `.trim();
}

/**
 * メールスレッドを処理する。
 *
 * @param {GoogleAppsScript.Gmail.GmailThread} thread メールスレッド
 * @param {GoogleAppsScript.Gmail.GmailLabel} label Smoozラベル
 */
function processThreads(threads, label) {
  console.log("\n=== ラベル付与処理開始 ===");
  threads.forEach(thread => {
    console.log("\n処理対象のスレッド情報:");
    console.log(getThreadInfo(thread));

    try {
      thread.addLabel(label);
      console.log("✅ ラベル付与成功");
      console.log("付与後のラベル:", thread.getLabels().map(l => l.getName()).join(", "));
    } catch (e) {
      console.error(`❌ ラベルの付与に失敗: ${e.toString()}`);
    }
  });
  console.log("=== ラベル付与処理終了 ===\n");
}

/**
 * Smoozメールをチェックし、必要に応じて処理を行うメイン処理。
 */
function checkSmoozMail() {
  console.log("\n=== Smoozメールチェック開始 ===");

  // 最終実行からの経過時間を表示
  const lastRunTime = PropertiesService.getScriptProperties().getProperty("lastCloudRunTime");
  if (lastRunTime) {
    const lastRunDate = new Date(parseInt(lastRunTime));
    const now = new Date();
    const hoursSinceLastRun = (now - lastRunDate) / (1000 * 60 * 60);
    console.log(`最終Cloud Run実行日時(${lastRunDate.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })})から${Math.floor(hoursSinceLastRun)}時間${Math.floor((hoursSinceLastRun % 1) * 60)}分経過`);
  } else {
    console.log("Cloud Runの実行履歴がありません。初回実行時刻をセットします");
    PropertiesService.getScriptProperties().setProperty("lastCloudRunTime", new Date().getTime().toString());
  }

  const label = getSmoozLabel();
  let targetThreads = [];
  let isForceRun = false;

  // 1. 新しいSmoozメールをチェック
  const latestThread = getLatestThread();
  if (latestThread) {
    console.log("\n新しいSmoozメールを検出:");
    console.log(getThreadInfo(latestThread));
    targetThreads.push(latestThread);
  }

  // 2. Smoozラベル付きスレッドの更新をチェック
  console.log("\nSmoozラベル付きスレッドの更新をチェック...");
  const smoozThreads = GmailApp.search(`label:${Config.LABEL_NAME}`);
  for (const thread of smoozThreads) {
    const messages = thread.getMessages();
    const lastMessage = messages[messages.length - 1];
    const lastMessageDate = lastMessage.getDate();

    // 最後のメッセージが最後の処理時間より新しい場合のみ処理対象に追加
    if (lastMessageDate > new Date(new Date().getTime() - 3600000)) {
      console.log("\n更新されたスレッドを検出:");
      console.log(getThreadInfo(thread));
      targetThreads.push(thread);
    }
  }

  // 3. Config.FORCE_RUN_INTERVAL_HOURS時間以上Cloud Runを呼んでいない場合は強制的に呼び出す
  if (lastRunTime) {
    const lastRunDate = new Date(parseInt(lastRunTime));
    const now = new Date();
    const hoursSinceLastRun = (now - lastRunDate) / (1000 * 60 * 60);

    if (hoursSinceLastRun >= Config.FORCE_RUN_INTERVAL_HOURS) {
      console.log(`\nCloud Runの最終実行から${Math.floor(hoursSinceLastRun)}時間が経過しています。強制的に実行します。`);
      isForceRun = true;
    }
  }

  // 処理対象がある場合または強制実行の場合にCloud Runを実行
  if (targetThreads.length > 0 || isForceRun) {
    console.log(`\n${isForceRun ? `${Config.FORCE_RUN_INTERVAL_HOURS}時間経過を検知` : targetThreads.length + "件のスレッドの更新を検知"}`);

    try {
      console.log("\nCloud Run へのリクエストを送信...");
      PropertiesService.getScriptProperties().setProperty("lastCloudRunTime", new Date().getTime().toString());

      const response = UrlFetchApp.fetch(Config.CLOUD_RUN_URL, {
        method: "post",
        muteHttpExceptions: true
      });

      const responseText = response.getContentText();
      console.log(`Cloud Run レスポンスコード: ${response.getResponseCode()}`);
      console.log(`Cloud Run レスポンス内容: ${responseText}`);

      if (response.getResponseCode() === 200) {
        console.log("✅ Cloud Run の処理が正常に完了しました");
        // 強制実行でない場合のみラベルを付与
        if (!isForceRun) {
          processThreads(targetThreads, label);
        }
      } else {
        console.error("❌ Cloud Run でエラーが発生しました");
      }
    } catch (e) {
      console.error("❌ Cloud Run へのリクエスト中にエラーが発生しました:", e.toString());
    }
  } else {
    console.log("更新を検知したスレッドはありません");
  }

  console.log("=== Smoozメールチェック終了 ===\n");
}

/**
 * トリガー設定について:
 * このスクリプトは以下のトリガーで動作します:
 * 1. checkSmoozMail: 1分ごとに実行（GASの管理ページで設定）
 */
