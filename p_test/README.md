# Playwright 测试使用说明

本目录集中存放测试文档、Excel 用例和 Playwright 自动化测试。测试通过拦截 `/api` 请求模拟后端和 AI 响应，因此不会写入真实 SQLite 数据库、不会使用真实 API Key，也不会产生模型调用费用。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `测试用例.xlsx` | 32 条功能、UI、安全与可访问性测试用例，含优先级和自动化状态。 |
| `generate_test_cases.py` | Excel 用例生成脚本；修改用例数据后执行即可重建工作簿。 |
| `playwright.config.js` | Playwright 配置：自动启动前端、使用 Chromium、失败保留证据。 |
| `tests/novel-workbench.spec.js` | 已落地的核心 UI 自动化用例。 |

## 首次使用

1. 确保已安装 Node.js 18 或更高版本。
2. 在项目根目录执行 `cd p_test`。
3. 执行 `npm install` 安装 Playwright 测试依赖。
4. 执行 `npx playwright install chromium` 下载 Chromium 测试浏览器。
5. 执行 `npm test`。该命令会自动启动 `frontend` 的 Vite 服务，并运行测试。

前端依赖已存在于 `frontend/node_modules` 时，无需重复安装前端依赖；如果缺失，请进入 `frontend` 执行 `npm install`。

## 常用命令

| 目标 | 命令 |
| --- | --- |
| 运行全部测试 | `npm test` |
| 打开交互式测试界面 | `npm run test:ui` |
| 查看 HTML 报告 | `npm run report` |
| 更新 Excel 用例文件 | `npm run cases` |
| 只运行一个文件 | `npx playwright test tests/novel-workbench.spec.js` |

## 当前已自动化覆盖

1. 空书架与书名必填校验。
2. 新建小说后跳转到正确的工作台。
3. 不存在小说的 404 错误反馈。
4. API Key 尾号脱敏与配置保存。
5. 章节 TXT 导出下载。

## 结果与排障

- HTML 报告会生成在 `p_test/playwright-report`；执行 `npm run report` 后查看。
- 失败截图、视频和 trace 位于 `p_test/test-results`。trace 可用 Playwright Trace Viewer 打开。
- 若端口 `4173` 被占用，请关闭占用服务，或修改 `playwright.config.js` 中的端口并同步修改 `baseURL`。
- 若浏览器缺失，重新执行 `npx playwright install chromium`。
- 这些测试只验证前端对规范接口的行为。真实 FastAPI、SQLite 与真实模型连通性应使用独立测试环境做补充冒烟，不要在自动化回归中填入真实密钥。
