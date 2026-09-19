# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: novel-workbench.spec.js >> API 配置仅展示已保存密钥尾号并可保存
- Location: tests\novel-workbench.spec.js:106:1

# Error details

```
Error: expect(locator).toHaveValue(expected) failed

Locator: getByLabel('API Key')
Expected: ""
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toHaveValue" getByLabel('API Key') with timeout 5000ms
  - waiting for getByLabel('API Key')

```

```yaml
- banner:
  - heading "AI 网文写作台" [level=1]
  - navigation:
    - link "书架":
      - /url: /
    - link "API 配置":
      - /url: /config
- heading "API 配置" [level=2]
- text: 支持任意 OpenAI 兼容接口（DeepSeek / Kimi / 豆包 / 通义 / GLM…） Base URL
- textbox "https://api.deepseek.com/v1": https://example.test/v1
- text: API Key 已保存：尾号 1234
- textbox "sk-..."
- text: 模型名
- textbox "deepseek-chat": test-model
- text: 温度（0~2，写作建议 0.8）
- spinbutton: "0.8"
- button "保存配置"
- button "测试连接"
```

# Test source

```ts
  11  |   updated_at: '2026-09-16T08:00:00',
  12  | }
  13  | 
  14  | const novelDetail = {
  15  |   novel,
  16  |   volumes: [
  17  |     {
  18  |       id: 10,
  19  |       volume_no: 1,
  20  |       title: '第一卷',
  21  |       status: '连载中',
  22  |       outline: '',
  23  |       summary: '',
  24  |       chapter_count: 1,
  25  |       chapters: [
  26  |         {
  27  |           id: 101,
  28  |           chapter_no: 1,
  29  |           title: '第一章 测试',
  30  |           content: '这是用于导出验证的章节正文。',
  31  |           detailed_outline: '测试细纲',
  32  |           status: '草稿',
  33  |           word_count: 14,
  34  |           updated_at: '2026-09-16T08:00:00',
  35  |         },
  36  |       ],
  37  |     },
  38  |   ],
  39  | }
  40  | 
  41  | async function mockApi(page, options = {}) {
  42  |   const novels = options.novels ?? []
  43  |   await page.route('**/api/**', async (route) => {
  44  |     const request = route.request()
  45  |     const url = new URL(request.url())
  46  |     const path = url.pathname
  47  |     const respond = (body, status = 200) => route.fulfill({
  48  |       status,
  49  |       contentType: 'application/json; charset=utf-8',
  50  |       body: JSON.stringify(body),
  51  |     })
  52  | 
  53  |     if (path === '/api/novels' && request.method() === 'GET') return respond(novels)
  54  |     if (path === '/api/novels' && request.method() === 'POST') return respond(novel, 201)
  55  |     if (path === '/api/novels/1' && request.method() === 'GET') {
  56  |       return options.novelError ? respond({ detail: '小说不存在' }, 404) : respond(novelDetail)
  57  |     }
  58  |     if (path === '/api/config' && request.method() === 'GET') {
  59  |       return respond({ base_url: 'https://example.test/v1', model_name: 'test-model', context_window: 64000, temperature: 0.8, has_key: true, key_tail: '1234' })
  60  |     }
  61  |     if (path === '/api/config' && request.method() === 'PUT') {
  62  |       return respond({ base_url: 'https://example.test/v1', model_name: 'test-model', context_window: 64000, temperature: 0.8, has_key: true, key_tail: '1234' })
  63  |     }
  64  |     if (path === '/api/novels/1/export' && request.method() === 'POST') {
  65  |       return route.fulfill({
  66  |         status: 200,
  67  |         contentType: 'text/plain; charset=utf-8',
  68  |         headers: { 'Content-Disposition': "attachment; filename*=UTF-8''自动化测试小说.txt" },
  69  |         body: '第一章 测试\n\n这是用于导出验证的章节正文。',
  70  |       })
  71  |     }
  72  |     return respond({ detail: `未模拟接口：${request.method()} ${path}` }, 404)
  73  |   })
  74  | }
  75  | 
  76  | test('书架空状态下校验必填书名', async ({ page }) => {
  77  |   await mockApi(page)
  78  |   await page.goto('/')
  79  | 
  80  |   await expect(page.getByText('书架空空如也')).toBeVisible()
  81  |   await page.getByRole('button', { name: '新建小说' }).click()
  82  |   await page.getByRole('button', { name: '创建', exact: true }).click()
  83  | 
  84  |   await expect(page.getByText('请填写书名')).toBeVisible()
  85  | })
  86  | 
  87  | test('创建小说后进入对应工作台', async ({ page }) => {
  88  |   await mockApi(page)
  89  |   await page.goto('/')
  90  | 
  91  |   await page.getByRole('button', { name: '新建小说' }).click()
  92  |   await page.getByPlaceholder('凡人修仙传').fill(novel.title)
  93  |   await page.getByRole('button', { name: '创建', exact: true }).click()
  94  | 
  95  |   await expect(page).toHaveURL(/\/novel\/1$/)
  96  |   await expect(page.getByRole('heading', { name: novel.title })).toBeVisible()
  97  | })
  98  | 
  99  | test('不存在的小说显示后端错误', async ({ page }) => {
  100 |   await mockApi(page, { novelError: true })
  101 |   await page.goto('/novel/1')
  102 | 
  103 |   await expect(page.getByText('小说不存在')).toBeVisible()
  104 | })
  105 | 
  106 | test('API 配置仅展示已保存密钥尾号并可保存', async ({ page }) => {
  107 |   await mockApi(page)
  108 |   await page.goto('/config')
  109 | 
  110 |   await expect(page.getByText('已保存：尾号 1234')).toBeVisible()
> 111 |   await expect(page.getByLabel('API Key')).toHaveValue('')
      |                                            ^ Error: expect(locator).toHaveValue(expected) failed
  112 |   await page.getByRole('button', { name: '保存配置' }).click()
  113 |   await expect(page.getByText('已保存')).toBeVisible()
  114 | })
  115 | 
  116 | test('选择章节后可下载 TXT 导出文件', async ({ page }) => {
  117 |   await mockApi(page)
  118 |   await page.goto('/novel/1')
  119 | 
  120 |   await page.getByRole('button', { name: '导出 txt' }).click()
  121 |   await page.getByText('第一章 测试').click()
  122 |   const downloadPromise = page.waitForEvent('download')
  123 |   await page.getByRole('button', { name: '导出', exact: true }).click()
  124 |   const download = await downloadPromise
  125 | 
  126 |   expect(download.suggestedFilename()).toBe('自动化测试小说.txt')
  127 | })
  128 | 
```