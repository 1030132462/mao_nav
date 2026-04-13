import test from 'node:test'
import assert from 'node:assert/strict'

import {
  filterCategoriesByQuery,
  findFirstMatchedCategoryId,
  normalizeSearchQuery,
  siteMatchesQuery,
} from '../src/utils/navigationSearch.js'

const categories = [
  {
    id: 'ai-tools',
    name: 'AI 智能',
    sites: [
      {
        id: 'chatgpt',
        name: 'ChatGPT',
        description: 'OpenAI 对话助手',
        url: 'https://chatgpt.com',
        tags: ['ai', 'assistant'],
        sourceFolder: 'Productivity',
        sourcePath: 'Workspace/AI',
      },
      {
        id: 'claude',
        name: 'Claude',
        description: 'Anthropic 助手',
        url: 'https://claude.ai',
      },
    ],
  },
  {
    id: 'dev-tools',
    name: '开发工具',
    sites: [
      {
        id: 'docker',
        name: 'Docker Hub',
        description: '容器镜像仓库',
        url: 'https://hub.docker.com',
        tags: ['container'],
      },
    ],
  },
]

test('normalizeSearchQuery trims and lowercases user input', () => {
  assert.equal(normalizeSearchQuery('  ChatGPT  '), 'chatgpt')
})

test('siteMatchesQuery searches tags and source metadata', () => {
  const query = normalizeSearchQuery('workspace')
  assert.equal(siteMatchesQuery(categories[0].sites[0], categories[0], query), true)
})

test('filterCategoriesByQuery keeps matched sites and removes empty categories', () => {
  const result = filterCategoriesByQuery(categories, {
    activeCategoryId: '',
    normalizedQuery: normalizeSearchQuery('docker'),
  })

  assert.deepEqual(result, [
    {
      ...categories[1],
      sites: [categories[1].sites[0]],
    },
  ])
})

test('findFirstMatchedCategoryId returns the first matching category id', () => {
  const categoryId = findFirstMatchedCategoryId(categories, normalizeSearchQuery('assistant'))
  assert.equal(categoryId, 'ai-tools')
})
