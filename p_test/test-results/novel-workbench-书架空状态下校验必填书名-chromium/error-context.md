# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: novel-workbench.spec.js >> 书架空状态下校验必填书名
- Location: tests\novel-workbench.spec.js:76:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('请填写书名')
Expected: visible
Error: strict mode violation: getByText('请填写书名') resolved to 2 elements:
    1) <p class="msg err">请填写书名</p> aka getByText('请填写书名').first()
    2) <p class="msg err">请填写书名</p> aka getByText('请填写书名').nth(1)

Call log:
  - Expect "toBeVisible" getByText('请填写书名') with timeout 5000ms
  - waiting for getByText('请填写书名')

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - heading "AI 网文写作台" [level=1] [ref=e5]
    - navigation [ref=e6]:
      - link "书架" [ref=e7] [cursor=pointer]:
        - /url: /
      - link "API 配置" [ref=e8] [cursor=pointer]:
        - /url: /config
  - generic [ref=e9]:
    - generic [ref=e10]:
      - heading "书架" [level=2] [ref=e11]
      - button "＋ 新建小说" [ref=e12] [cursor=pointer]
    - paragraph [ref=e13]: 请填写书名
    - paragraph [ref=e14]: 书架空空如也。点击「新建小说」创建第一本书，填入设定后即可开始 AI 写作。
    - generic [ref=e16]:
      - heading "新建小说" [level=3] [ref=e17]
      - generic [ref=e18]: 书名 *
      - textbox "凡人修仙传" [ref=e19]
      - generic [ref=e20]:
        - generic [ref=e21]:
          - generic [ref=e22]: 题材
          - textbox "玄幻 / 都市 / 科幻" [ref=e23]
        - generic [ref=e24]:
          - generic [ref=e25]: 风格
          - textbox "轻松幽默 / 热血 / 悬疑" [ref=e26]
      - generic [ref=e27]:
        - generic [ref=e28]:
          - generic [ref=e29]: 主角
          - textbox "主角名" [ref=e30]
        - generic [ref=e31]:
          - generic [ref=e32]: 目标字数（可选）
          - spinbutton "500000" [ref=e33]: "0"
      - generic [ref=e34]: 世界观设定
      - textbox "如：修仙界，练气→筑基→金丹" [ref=e35]
      - generic [ref=e36]: 内容简介
      - textbox "一句话故事主线，AI 会据此把控剧情方向" [ref=e37]
      - paragraph [ref=e38]: 请填写书名
      - generic [ref=e39]:
        - button "创建" [active] [ref=e40] [cursor=pointer]
        - button "取消" [ref=e41] [cursor=pointer]
```

# Test source

```ts
  1   | import { expect, test } from '@playwright/test'
  2   | 
  3   | const novel = {
  4   |   id: 1,
  5   |   title: '自动化测试小说',
  6   |   genre: '科幻',
  7   |   style: '悬疑',
  8   |   protagonist: '林舟',
  9   |   status: '连载中',
  10  |   chapter_count: 1,
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
> 84  |   await expect(page.getByText('请填写书名')).toBeVisible()
      |                                         ^ Error: expect(locator).toBeVisible() failed
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
  111 |   await expect(page.getByLabel('API Key')).toHaveValue('')
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