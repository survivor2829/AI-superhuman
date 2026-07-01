import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const appSource = readFileSync(resolve("src/App.tsx"), "utf8");

const requiredSnippets = [
  "const CUSTOMER_STEPS",
  "const NAV_ITEMS",
  "activeView",
  "连接微信",
  "导入话术",
  "确认客户",
  "开始触达",
  "查看结果",
  "高级诊断",
];

const forbiddenCustomerCopy = ["Backend", "RPA Sidecar", "preflight", "payload hash", "已加入发送名单", ">加入<"];
const customerActionBand = appSource.match(/<section className="action-band">([\s\S]*?)<\/section>/)?.[1] || "";
const requiredPrimaryButtons = ["静默同步通讯录", "选择话术文件", "开始发送"];
const hiddenFromCustomerActionBand = [
  "导入默认话术",
  "生成预览",
  "生成队列",
  "校准微信窗口",
  "只打开会话",
  "开始小批量",
  "跑下一批",
  "扫新消息",
  "扫朋友圈",
  "暂停",
];

const missing = requiredSnippets.filter((snippet) => !appSource.includes(snippet));
const forbidden = forbiddenCustomerCopy.filter((snippet) => appSource.includes(snippet));
const missingPrimaryButtons = requiredPrimaryButtons.filter((snippet) => !customerActionBand.includes(snippet));
const visibleDebugButtons = hiddenFromCustomerActionBand.filter((snippet) => customerActionBand.includes(snippet));

if (missing.length || forbidden.length || missingPrimaryButtons.length || visibleDebugButtons.length) {
  console.error(JSON.stringify({ missing, forbidden, missingPrimaryButtons, visibleDebugButtons }, null, 2));
  process.exit(1);
}
