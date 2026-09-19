import { expect, test } from '@playwright/test'

const novel = {
  id: 1,
  title: '自动化测试小说',
  genre: '科幻',
  style: '悬疑',
  protagonist: '林舟',
  status: '连载中',
  chapter_count: 1,
  updated_at: '2026-09-16T08:00:00',
}

const novelDetail = {
  novel,
  volumes: [
    {
      id: 10,
      volume_no: 1,
      title: '第一卷',
      status: '连载中',
      outline: '',
      summary: '',
      chapter_count: 1,
      chapters: [
        {
          id: 101,
          chapter_no: 1,
          title: '第一章 测试',
          content: '这是用于导出验证的章节正文。',
          detailed_outline: '测试细纲',
          status: '草稿',
          word_count: 14,
          updated_at: '2026-09-16T08:00:00',
        },
      ],
    },
  ],
}

async function mockApi(page, options = {}) {
  const novels = options.novels ?? []
  await page.route('**/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const respond = (body, status = 200) => route.fulfill({
      status,
      contentType: 'application/json; charset=utf-8',
      body: JSON.stringify(body),
    })

    if (path === '/api/novels' && request.method() === 'GET') return respond(novels)
    if (path === '/api/novels' && request.method() === 'POST') return respond(novel, 201)
    if (path === '/api/novels/1' && request.method() === 'GET') {
      return options.novelError ? respond({ detail: '小说不存在' }, 404) : respond(novelDetail)
    }
    if (path === '/api/config' && request.method() === 'GET') {
      return respond({ base_url: 'https://example.test/v1', model_name: 'test-model', context_window: 64000, temperature: 0.8, has_key: true, key_tail: '1234' })
    }
    if (path === '/api/config' && request.method() === 'PUT') {
      return respond({ base_url: 'https://example.test/v1', model_name: 'test-model', context_window: 64000, temperature: 0.8, has_key: true, key_tail: '1234' })
    }
    if (path === '/api/novels/1/export' && request.method() === 'POST') {
      return route.fulfill({
        status: 200,
        contentType: 'text/plain; charset=utf-8',
        headers: { 'Content-Disposition': "attachment; filename*=UTF-8''自动化测试小说.txt" },
        body: '第一章 测试\n\n这是用于导出验证的章节正文。',
      })
    }
    return respond({ detail: `未模拟接口：${request.method()} ${path}` }, 404)
  })
}

test('书架空状态下校验必填书名', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')

  await expect(page.getByText('书架空空如也')).toBeVisible()
  await page.getByRole('button', { name: '新建小说' }).click()
  await page.getByRole('button', { name: '创建', exact: true }).click()

  await expect(page.getByText('请填写书名')).toBeVisible()
})

test('创建小说后进入对应工作台', async ({ page }) => {
  await mockApi(page)
  await page.goto('/')

  await page.getByRole('button', { name: '新建小说' }).click()
  await page.getByPlaceholder('凡人修仙传').fill(novel.title)
  await page.getByRole('button', { name: '创建', exact: true }).click()

  await expect(page).toHaveURL(/\/novel\/1$/)
  await expect(page.getByRole('heading', { name: novel.title })).toBeVisible()
})

test('不存在的小说显示后端错误', async ({ page }) => {
  await mockApi(page, { novelError: true })
  await page.goto('/novel/1')

  await expect(page.getByText('小说不存在')).toBeVisible()
})

test('API 配置仅展示已保存密钥尾号并可保存', async ({ page }) => {
  await mockApi(page)
  await page.goto('/config')

  await expect(page.getByText('已保存：尾号 1234')).toBeVisible()
  await expect(page.getByLabel('API Key')).toHaveValue('')
  await page.getByRole('button', { name: '保存配置' }).click()
  await expect(page.getByText('已保存')).toBeVisible()
})

test('选择章节后可下载 TXT 导出文件', async ({ page }) => {
  await mockApi(page)
  await page.goto('/novel/1')

  await page.getByRole('button', { name: '导出 txt' }).click()
  await page.getByText('第一章 测试').click()
  const downloadPromise = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出', exact: true }).click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toBe('自动化测试小说.txt')
})
