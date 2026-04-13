import { ref } from 'vue'
import { mockData } from '../mock/mock_data.js'

const syncDocumentMeta = (siteTitle) => {
  document.title = siteTitle

  const faviconHref = `/logo.png?v=${Date.now()}`
  const faviconLinks = [
    { rel: 'icon', type: 'image/png' },
    { rel: 'shortcut icon', type: 'image/png' },
    { rel: 'apple-touch-icon', type: 'image/png' },
  ]

  faviconLinks.forEach(({ rel, type }) => {
    let link = document.querySelector(`link[rel="${rel}"]`)
    if (!link) {
      link = document.createElement('link')
      link.rel = rel
      document.head.appendChild(link)
    }

    link.type = type
    link.href = faviconHref
  })
}

export function useNavigation() {
  const categories = ref([])
  const title = ref('')
  const defaultSearchEngine = ref('bing')
  const loading = ref(false)
  const error = ref(null)

  const normalizeCategories = (items = []) => {
    return JSON.parse(JSON.stringify(items))
      .sort((left, right) => (left.order ?? 0) - (right.order ?? 0))
  }

  const fetchCategories = async () => {
    loading.value = true
    error.value = null

    try {
      // 开发环境模拟网络延迟
      if (import.meta.env.DEV) {
        await new Promise(resolve => setTimeout(resolve, 500))
      }

      // 默认使用本地mock数据
      categories.value = normalizeCategories(mockData.categories)
      title.value = mockData.title || '专属导航工作台'

      // 设置默认搜索引擎，如果未指定或不存在则使用bing
      const searchEngines = ['google', 'baidu', 'bing', 'duckduckgo']
      if (mockData.search && searchEngines.includes(mockData.search)) {
        defaultSearchEngine.value = mockData.search
      } else {
        defaultSearchEngine.value = 'bing'
      }

      syncDocumentMeta(title.value)


    } catch (err) {
      error.value = err.message
      console.error('Error fetching categories:', err)
      // 兜底：始终返回 mock 数据
      categories.value = normalizeCategories(mockData.categories)
      title.value = mockData.title || '专属导航工作台'

      // 设置默认搜索引擎
      const searchEngines = ['google', 'baidu', 'bing', 'duckduckgo']
      if (mockData.search && searchEngines.includes(mockData.search)) {
        defaultSearchEngine.value = mockData.search
      } else {
        defaultSearchEngine.value = 'bing'
      }

      syncDocumentMeta(title.value)
    } finally {
      loading.value = false
    }
  }

  return {
    categories,
    title,
    defaultSearchEngine,
    loading,
    error,
    fetchCategories
  }
}
