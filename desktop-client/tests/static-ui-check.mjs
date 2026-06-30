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

const missing = requiredSnippets.filter((snippet) => !appSource.includes(snippet));
const forbidden = forbiddenCustomerCopy.filter((snippet) => appSource.includes(snippet));

if (missing.length || forbidden.length) {
  console.error(JSON.stringify({ missing, forbidden }, null, 2));
  process.exit(1);
}
