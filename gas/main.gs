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
  FORCE_RUN_INTERVAL_HOURS: 3, // 強制実行までの時間間隔（時間）

  // スキップ時間帯設定
  SKIP_START_HOUR: 2, // スキップ開始時刻（時）
  SKIP_END_HOUR: 6    // スキップ終了時刻（時）
};

/**
 * Smoozラベルを取得する。存在しない場合は作成する。
 * ラベルはPropertiesServiceにキャッシュして、毎回Gmail APIを呼ばないようにする。
 * さらに最適化: ラベルオブジェクト自体をキャッシュして、API呼び出しを完全に回避。
 *
 * @return {GoogleAppsScript.Gmail.GmailLabel} Smoozラベル
 */
let cachedLabel = null; // グローバル変数としてラベルをキャッシュ

function getSmoozLabel(countApiCall) {
  // グローバル変数にキャッシュされている場合はそれを返す（API呼び出しなし）
  if (cachedLabel) {
    return cachedLabel;
  }

  // キャッシュからラベルIDを取得
  const cachedLabelId = PropertiesService.getScriptProperties().getProperty("smoozLabelId");

  if (cachedLabelId) {
    try {
      if (countApiCall) countApiCall(); // GmailApp.getUserLabelById()の呼び出しをカウント
      const label = GmailApp.getUserLabelById(cachedLabelId);
      if (label) {
        cachedLabel = label; // グローバル変数にキャッシュ
        return label;
      }
    } catch (e) {
      // ラベルが削除された場合はキャッシュをクリア
      PropertiesService.getScriptProperties().deleteProperty("smoozLabelId");
    }
  }

  // ラベルが存在しない場合は作成（初回のみ）
  if (countApiCall) countApiCall(); // GmailApp.getUserLabelByName()の呼び出しをカウント
  let label = GmailApp.getUserLabelByName(Config.LABEL_NAME);
  if (!label) {
    if (countApiCall) countApiCall(); // GmailApp.createLabel()の呼び出しをカウント
    label = GmailApp.createLabel(Config.LABEL_NAME);
  }
  // ラベルIDをキャッシュ
  PropertiesService.getScriptProperties().setProperty("smoozLabelId", label.getId());
  cachedLabel = label; // グローバル変数にキャッシュ
  return label;
}

/**
 * 最新のSmoozメールスレッドを取得する。
 *
 * @return {GoogleAppsScript.Gmail.GmailThread|null} 最新のSmoozメールスレッド。存在しない場合は null。
 */
function getLatestThread(countApiCall) {
  const query = `${Config.SMOOZ_MAIL_QUERY} -label:${Config.LABEL_NAME}`;
  console.log(`検索クエリ: ${query}`);
  countApiCall(); // GmailApp.search()の呼び出しをカウント
  const threads = GmailApp.search(query);
  if (threads.length === 0) {
    console.log("新しいSmoozメールは見つかりませんでした");
  }
  return threads.length > 0 ? threads[0] : null;
}

/**
 * メールスレッドの情報を文字列として取得する。
 * 注意: この関数はGmail APIを複数回呼び出すため、使用を最小限に抑えること。
 * デバッグ時のみ使用を推奨。
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
    console.log(`処理対象のスレッドID: ${thread.getId()}`);

    try {
      thread.addLabel(label);
      console.log("✅ ラベル付与成功");
    } catch (e) {
      console.error(`❌ ラベルの付与に失敗: ${e.toString()}`);
    }
  });
  console.log("=== ラベル付与処理終了 ===\n");
}

/**
 * Smoozメールをチェックし、必要に応じて処理を行うメイン処理。
 * Gmail APIの使用制限を考慮して、不要な検索を削減しています。
 */
function checkSmoozMail() {
  console.log("\n=== Smoozメールチェック開始 ===");

  // 深夜2時から6時の間はGmailチェックをスキップ（API呼び出しを削減）
  const now = new Date();
  const jstTime = Utilities.formatDate(now, "Asia/Tokyo", "HH");
  const hour = parseInt(jstTime);

  if (hour >= Config.SKIP_START_HOUR && hour < Config.SKIP_END_HOUR) {
    console.log(`現在時刻: ${hour}時（日本時間）`);
    console.log(`深夜${Config.SKIP_START_HOUR}時から${Config.SKIP_END_HOUR}時の間のため、Gmailチェックをスキップします`);
    console.log("=== Smoozメールチェック終了（スキップ） ===\n");
    return;
  }

  // API呼び出し回数をカウント（デバッグ用）
  let apiCallCount = 0;
  const countApiCall = () => { apiCallCount++; };

  // Gmail APIの制限エラーをキャッチするためのtry-catch
  try {
    // 最終実行からの経過時間を表示
    const lastRunTime = PropertiesService.getScriptProperties().getProperty("lastCloudRunTime");
    if (lastRunTime) {
      const lastRunDate = new Date(parseInt(lastRunTime));
      const hoursSinceLastRun = (now.getTime() - lastRunDate.getTime()) / (1000 * 60 * 60);
      console.log(`最終Cloud Run実行日時(${lastRunDate.toLocaleString("ja-JP", { timeZone: "Asia/Tokyo" })})から${Math.floor(hoursSinceLastRun)}時間${Math.floor((hoursSinceLastRun % 1) * 60)}分経過`);
    } else {
      console.log("Cloud Runの実行履歴がありません。初回実行時刻をセットします");
      PropertiesService.getScriptProperties().setProperty("lastCloudRunTime", new Date().getTime().toString());
    }

    // ラベル取得は初回のみAPI呼び出しが発生（グローバル変数にキャッシュされているため）
    // 2回目以降はAPI呼び出しなし
    const label = getSmoozLabel(countApiCall);

    let targetThreads = [];
    let isForceRun = false;

    // 1. 新しいSmoozメールをチェック（最も重要なので優先）
    const latestThread = getLatestThread(countApiCall);
    if (latestThread) {
      console.log("\n新しいSmoozメールを検出:");
      console.log(`スレッドID: ${latestThread.getId()}`);
      targetThreads.push(latestThread);
    }

    // 2. Smoozラベル付きスレッドの更新をチェック
    // 最適化: 新しいメールが見つかった場合は、ラベル付きスレッドの更新チェックをスキップ
    // （新しいメールが検出された時点で処理するため）
    // さらに最適化: このチェックは強制実行時もスキップ（強制実行は定期的に実行されるため）
    if (targetThreads.length === 0 && lastRunTime) {
      const lastRunDate = new Date(parseInt(lastRunTime));
      const hoursSinceLastRun = (now.getTime() - lastRunDate.getTime()) / (1000 * 60 * 60);

      // 強制実行間隔の半分以上経過している場合のみ、ラベル付きスレッドの更新をチェック
      // これにより、Gmail APIの呼び出し回数を大幅に削減
      // さらに最適化: このチェックは1日1回のみ実行（強制実行時のみ）
      // 通常の実行では新しいメールの検出のみを行う
      if (hoursSinceLastRun >= Config.FORCE_RUN_INTERVAL_HOURS) {
        // 強制実行時のみ、ラベル付きスレッドの更新をチェック
        // ただし、このチェックはGmail APIを大量に消費するため、最小限に抑える
        console.log("\n強制実行時: Smoozラベル付きスレッドの更新をチェック（最小限）...");
        // 最新の5件のみを処理（10件から5件に削減）
        countApiCall(); // GmailApp.search()の呼び出しをカウント
        const allSmoozThreads = GmailApp.search(`label:${Config.LABEL_NAME}`);
        const smoozThreads = allSmoozThreads.slice(0, 5); // 最新5件のみ処理

        for (const thread of smoozThreads) {
          let lastMessageDate;
          try {
            countApiCall(); // thread.getMessages()の呼び出しをカウント
            const messages = thread.getMessages();
            if (messages.length > 0) {
              lastMessageDate = messages[messages.length - 1].getDate();
            } else {
              continue;
            }
          } catch (e) {
            console.error(`スレッド ${thread.getId()} のメッセージ取得に失敗: ${e.toString()}`);
            continue;
          }

          if (lastMessageDate > lastRunDate) {
            console.log("\n更新されたスレッドを検出:");
            console.log(`スレッドID: ${thread.getId()}`);
            targetThreads.push(thread);
          }
        }
      } else {
        console.log("ラベル付きスレッドの更新チェックをスキップ（強制実行時のみ実行）");
      }
    }

    // 3. Config.FORCE_RUN_INTERVAL_HOURS時間以上Cloud Runを呼んでいない場合は強制的に呼び出す
    if (lastRunTime) {
      const lastRunDate = new Date(parseInt(lastRunTime));
      const hoursSinceLastRun = (now.getTime() - lastRunDate.getTime()) / (1000 * 60 * 60);

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

    // API呼び出し回数をログに記録
    console.log(`\n今回の実行でのGmail API呼び出し回数: ${apiCallCount}回`);

    // 1日の累計を記録（デバッグ用）
    const today = new Date().toDateString();
    const dailyCountKey = `gmailApiCalls_${today}`;
    const dailyCount = parseInt(PropertiesService.getScriptProperties().getProperty(dailyCountKey) || "0");
    const newDailyCount = dailyCount + apiCallCount;
    PropertiesService.getScriptProperties().setProperty(dailyCountKey, newDailyCount.toString());
    console.log(`本日の累計Gmail API呼び出し回数: ${newDailyCount}回`);

  } catch (e) {
    const errorMessage = e.toString();
    console.error(`❌ Gmail API エラー: ${errorMessage}`);

    // Gmail APIの制限エラーの場合
    if (errorMessage.indexOf("too many times") !== -1 || errorMessage.indexOf("Service invoked too many times") !== -1) {
      console.error("⚠️ Gmail APIの1日の使用制限に達しました。24時間後に自動的にリセットされます。");
      console.error("対策: トリガーの実行間隔を長くする（例: 5分間隔）ことを検討してください。");
    } else {
      console.error("予期しないエラーが発生しました:", errorMessage);
    }
  }

  console.log("=== Smoozメールチェック終了 ===\n");
}

/**
 * トリガー設定について:
 * このスクリプトは以下のトリガーで動作します:
 * 1. checkSmoozMail: 5分ごとに実行を推奨（GASの管理ページで設定）
 *
 * 注意: Gmail APIの使用制限を考慮して、1分間隔での実行は推奨しません。
 * 1分間隔の場合、1日で約2,880回のGmail API呼び出しが発生し、制限に達する可能性があります。
 * 5分間隔にすると、1日で約576回の呼び出しとなり、制限内に収まります。
 */
