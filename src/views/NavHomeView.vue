<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useNavigation } from '@/apis/useNavigation.js'
import { useThemeStore } from '@/stores/counter.js'
import {
  filterCategoriesByQuery,
  findFirstMatchedCategoryId,
  normalizeSearchQuery,
} from '@/utils/navigationSearch.js'
import googleLogo from '@/assets/goolge.png'
import baiduLogo from '@/assets/baidu.png'
import bingLogo from '@/assets/bing.png'
import duckLogo from '@/assets/duck.png'

const { categories, title, defaultSearchEngine, loading, error, fetchCategories } = useNavigation()
const themeStore = useThemeStore()

const searchQuery = ref('')
const selectedEngine = ref('bing')
const activeCategoryId = ref('')
const showMobileMenu = ref(false)
const collapsedCategories = ref({})

const isLocked = ref(false)
const isUnlocked = ref(false)
const unlockPassword = ref('')
const unlocking = ref(false)
const unlockError = ref('')

const searchEngines = {
  google: {
    label: 'Google',
    url: 'https://www.google.com/search?q=',
    icon: googleLogo,
  },
  baidu: {
    label: '百度',
    url: 'https://www.baidu.com/s?wd=',
    icon: baiduLogo,
  },
  bing: {
    label: 'Bing',
    url: 'https://www.bing.com/search?q=',
    icon: bingLogo,
  },
  duckduckgo: {
    label: 'DuckDuckGo',
    url: 'https://duckduckgo.com/?q=',
    icon: duckLogo,
  },
}

const allCategories = computed(() => Array.isArray(categories.value) ? categories.value : [])
const normalizedQuery = computed(() => normalizeSearchQuery(searchQuery.value))
const selectedEngineLabel = computed(() => searchEngines[selectedEngine.value]?.label || 'Bing')
const hasFilters = computed(() => Boolean(activeCategoryId.value || normalizedQuery.value))
const totalSiteCount = computed(() => {
  return allCategories.value.reduce((total, category) => total + (category.sites?.length || 0), 0)
})

const filteredCategories = computed(() => {
  return filterCategoriesByQuery(allCategories.value, {
    activeCategoryId: activeCategoryId.value,
    normalizedQuery: normalizedQuery.value,
  })
})

const visibleSiteCount = computed(() => {
  return filteredCategories.value.reduce((total, category) => total + (category.sites?.length || 0), 0)
})

const categoryNavItems = computed(() => {
  return allCategories.value.map(category => {
    const matchedCategory = filteredCategories.value.find(item => item.id === category.id)
    return {
      ...category,
      totalSites: category.sites?.length || 0,
      matchedSites: matchedCategory?.sites?.length || 0,
    }
  })
})

const pinnedSites = computed(() => {
  const uniqueSites = new Map()

  filteredCategories.value.forEach(category => {
    ;(category.sites || []).forEach(site => {
      if (!site.pinned && category.id !== 'common') {
        return
      }

      const key = site.normalizedUrl || site.url
      if (!uniqueSites.has(key)) {
        uniqueSites.set(key, {
          ...site,
          categoryId: category.id,
          categoryName: category.name,
          categoryIcon: category.icon,
        })
      }
    })
  })

  return Array.from(uniqueSites.values())
})

const searchSummary = computed(() => {
  if (normalizedQuery.value) {
    return `站内搜索：${searchQuery.value.trim()}`
  }

  if (activeCategoryId.value) {
    const currentCategory = allCategories.value.find(item => item.id === activeCategoryId.value)
    return currentCategory
      ? `当前聚焦 ${currentCategory.name}`
      : '当前分类视图'
  }

  return '当前工作台概览'
})

const emptyStateTitle = computed(() => {
  if (normalizedQuery.value) {
    return '没有找到匹配站点'
  }
  return '这个分类还没有内容'
})

const emptyStateDescription = computed(() => {
  if (normalizedQuery.value) {
    return '试试别的关键词，支持名称、描述、网址、标签和来源路径检索。'
  }
  return '这个分类暂时还没有收录站点。'
})

const formatCategoryOrder = (order) => {
  return String((order ?? 0) + 1).padStart(2, '0')
}

const isCategoryCollapsed = (categoryId) => {
  return Boolean(collapsedCategories.value[categoryId])
}

const toggleCategoryCollapse = (categoryId) => {
  collapsedCategories.value = {
    ...collapsedCategories.value,
    [categoryId]: !collapsedCategories.value[categoryId],
  }
}

const clearSearch = () => {
  searchQuery.value = ''
}

const resetFilters = () => {
  searchQuery.value = ''
  activeCategoryId.value = ''
}

const smoothScrollTo = (container, targetTop, duration = 480) => {
  const startTop = container.scrollTop
  const distance = targetTop - startTop
  let startTime = null

  const animate = (currentTime) => {
    if (startTime === null) {
      startTime = currentTime
    }

    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    const ease = progress < 0.5
      ? 4 * progress * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 3) / 2

    container.scrollTop = startTop + distance * ease

    if (progress < 1) {
      requestAnimationFrame(animate)
    }
  }

  requestAnimationFrame(animate)
}

const scrollToTop = () => {
  const container = document.querySelector('.content-area')
  if (container) {
    smoothScrollTo(container, 0)
  }
}

const scrollToCategory = (categoryId) => {
  const container = document.querySelector('.content-area')
  const target = document.getElementById(`category-${categoryId}`)
  const header = document.querySelector('.search-header')

  if (!container || !target) {
    return
  }

  const headerOffset = (header?.offsetHeight || 0) + 16
  const targetTop = Math.max(target.offsetTop - headerOffset, 0)
  smoothScrollTo(container, targetTop)
}

const setActiveCategory = (categoryId) => {
  activeCategoryId.value = categoryId
}

const jumpToCategory = async (categoryId) => {
  activeCategoryId.value = categoryId
  await nextTick()
  scrollToCategory(categoryId)
}

const jumpToCategoryMobile = async (categoryId) => {
  closeMobileMenu()
  await nextTick()
  await jumpToCategory(categoryId)
}

const focusSearchResults = async () => {
  const firstCategoryId = findFirstMatchedCategoryId(allCategories.value, normalizedQuery.value)
  if (!firstCategoryId) {
    return
  }

  activeCategoryId.value = ''
  await nextTick()
  scrollToCategory(firstCategoryId)
}

const handleExternalSearch = () => {
  if (!searchQuery.value.trim()) {
    return
  }

  const engine = searchEngines[selectedEngine.value]
  const url = `${engine.url}${encodeURIComponent(searchQuery.value.trim())}`
  window.open(url, '_blank')
}

const handleImageError = (event) => {
  event.target.src = '/logo.png'
  event.target.onerror = null
}

const toggleMobileMenu = () => {
  showMobileMenu.value = !showMobileMenu.value
  document.body.style.overflow = showMobileMenu.value ? 'hidden' : ''
}

const closeMobileMenu = () => {
  showMobileMenu.value = false
  document.body.style.overflow = ''
}

const checkLockStatus = () => {
  const openLock = import.meta.env.VITE_OPEN_LOCK
  if (openLock && openLock.trim()) {
    isLocked.value = true
    isUnlocked.value = localStorage.getItem('nav_unlocked') === 'true'
    return
  }

  isLocked.value = false
  isUnlocked.value = true
}

const handleUnlock = async () => {
  unlocking.value = true
  unlockError.value = ''

  try {
    const response = await fetch('/api/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: unlockPassword.value }),
    })

    const result = await response.json()
    if (!result.success) {
      throw new Error(result.error || '访问密钥错误，请重新输入')
    }

    isUnlocked.value = true
    localStorage.setItem('nav_unlocked', 'true')
    unlockPassword.value = ''
  } catch (currentError) {
    unlockError.value = currentError.message
  } finally {
    unlocking.value = false
  }
}

onMounted(async () => {
  checkLockStatus()
  await fetchCategories()
  selectedEngine.value = defaultSearchEngine.value
})

onUnmounted(() => {
  document.body.style.overflow = ''
})
</script>

<template>
  <div v-if="isLocked && !isUnlocked" class="lock-container">
    <div class="lock-box">
      <h1 class="lock-title">🔐 访问验证</h1>
      <p class="lock-description">此导航站已启用访问保护</p>
      <form @submit.prevent="handleUnlock">
        <div class="lock-form-group">
          <label for="unlock-password" class="lock-label">请输入访问密钥</label>
          <input
            id="unlock-password"
            v-model="unlockPassword"
            type="password"
            placeholder="请输入访问密钥"
            required
            class="lock-input"
          />
        </div>
        <button type="submit" class="unlock-btn" :disabled="unlocking">
          {{ unlocking ? '验证中...' : '进入导航' }}
        </button>
      </form>
      <div v-if="unlockError" class="lock-error">
        {{ unlockError }}
      </div>
    </div>
  </div>

  <div v-else class="nav-home" :class="{ 'is-dark': themeStore.isDarkMode }">
    <aside class="sidebar">
      <div class="logo-section">
        <img src="/logo.png" alt="logo" class="logo" />
        <div class="logo-copy">
          <p class="logo-caption">Personal Bookmark Workspace</p>
          <h1 class="site-title">{{ title || '专属导航工作台' }}</h1>
        </div>
      </div>

      <div class="sidebar-panel">
        <p class="sidebar-kicker">Small, fast, private.</p>
        <h2 class="sidebar-heading">先保留原始导航骨架，后续再按你的节奏逐步增删站点。</h2>
        <div class="sidebar-stats">
          <div class="sidebar-stat-card">
            <span class="sidebar-stat-value">{{ allCategories.length }}</span>
            <span class="sidebar-stat-label">主分类</span>
          </div>
          <div class="sidebar-stat-card">
            <span class="sidebar-stat-value">{{ totalSiteCount }}</span>
            <span class="sidebar-stat-label">站点</span>
          </div>
          <div class="sidebar-stat-card">
            <span class="sidebar-stat-value">{{ pinnedSites.length }}</span>
            <span class="sidebar-stat-label">常用</span>
          </div>
        </div>
      </div>

      <nav class="category-nav">
        <div class="nav-header">
          <h2 class="nav-title">快速定位</h2>
          <button v-if="hasFilters" class="nav-reset-btn" @click="resetFilters">
            重置
          </button>
        </div>
        <ul class="category-list">
          <li
            class="category-item"
            :class="{ active: !activeCategoryId }"
            @click="setActiveCategory(''); scrollToTop()"
          >
            <span class="category-icon">🧭</span>
            <span class="category-name">全部分类</span>
            <span class="category-count">{{ totalSiteCount }}</span>
          </li>
          <li
            v-for="category in categoryNavItems"
            :key="category.id"
            class="category-item"
            :class="{ active: activeCategoryId === category.id }"
            @click="jumpToCategory(category.id)"
          >
            <span class="category-icon">{{ category.icon }}</span>
            <span class="category-name">{{ category.name }}</span>
            <span class="category-count">{{ category.totalSites }}</span>
          </li>
        </ul>
      </nav>

      <div class="sidebar-footer">
        <p class="sidebar-note">
          当前使用原始静态导航数据，后续可继续在后台逐步补充和调整。
        </p>
      </div>
    </aside>

    <main class="main-content">
      <header class="search-header">
        <div class="search-top-row">
          <div class="search-container">
            <div class="search-engine-selector">
              <img :src="searchEngines[selectedEngine].icon" :alt="selectedEngineLabel" class="engine-logo" />
              <select v-model="selectedEngine" class="engine-select" aria-label="选择搜索引擎">
                <option value="google">Google</option>
                <option value="baidu">百度</option>
                <option value="bing">Bing</option>
                <option value="duckduckgo">DuckDuckGo</option>
              </select>
            </div>
            <input
              v-model="searchQuery"
              type="text"
              class="search-input"
              placeholder="站内搜索名称、描述、网址、标签或来源分类"
              @keyup.enter="focusSearchResults"
            />
            <button
              v-if="searchQuery"
              class="clear-search-btn"
              type="button"
              @click="clearSearch"
            >
              清空
            </button>
          </div>

          <button
            class="external-search-btn"
            type="button"
            :disabled="!searchQuery.trim()"
            @click="handleExternalSearch"
          >
            外部搜索
          </button>

          <button
            class="theme-toggle-btn"
            type="button"
            :title="themeStore.isDarkMode ? '切换到日间模式' : '切换到夜间模式'"
            @click="themeStore.toggleTheme"
          >
            <svg v-if="!themeStore.isDarkMode" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 18C8.68629 18 6 15.3137 6 12C6 8.68629 8.68629 6 12 6C15.3137 6 18 8.68629 18 12C18 15.3137 15.3137 18 12 18ZM12 16C14.2091 16 16 14.2091 16 12C16 9.79086 14.2091 8 12 8C9.79086 8 8 9.79086 8 12C8 14.2091 9.79086 16 12 16ZM11 1H13V4H11V1ZM11 20H13V23H11V20ZM3.51472 4.92893L4.92893 3.51472L7.05025 5.63604L5.63604 7.05025L3.51472 4.92893ZM16.9497 18.364L18.364 16.9497L20.4853 19.0711L19.0711 20.4853L16.9497 18.364ZM19.0711 3.51472L20.4853 4.92893L18.364 7.05025L16.9497 5.63604L19.0711 3.51472ZM5.63604 16.9497L7.05025 18.364L4.92893 20.4853L3.51472 19.0711L5.63604 16.9497ZM23 11V13H20V11H23ZM4 11V13H1V11H4Z" />
            </svg>
            <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M10 7C10 10.866 13.134 14 17 14C18.9584 14 20.729 13.1957 21.9995 11.8995C22 11.933 22 11.9665 22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C12.0335 2 12.067 2 12.1005 2.00049C10.8043 3.27098 10 5.04157 10 7ZM4 12C4 16.4183 7.58172 20 12 20C15.0583 20 17.7158 18.2839 19.062 15.7621C18.3945 15.9187 17.7035 16 17 16C12.0294 16 8 11.9706 8 7C8 6.29648 8.08133 5.60547 8.2379 4.938C5.71611 6.28423 4 8.9417 4 12Z" />
            </svg>
          </button>

          <button class="mobile-menu-btn" type="button" @click="toggleMobileMenu">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M3 12H21M3 6H21M3 18H21" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </button>
        </div>

        <div class="search-sub-row">
          <div class="search-summary">
            <span class="summary-emphasis">{{ visibleSiteCount }}</span>
            <span class="summary-text">{{ searchSummary }}</span>
          </div>
        </div>

        <div class="filter-chip-row">
          <button
            class="filter-chip"
            :class="{ active: !activeCategoryId }"
            type="button"
            @click="setActiveCategory('')"
          >
            全部
          </button>
          <button
            v-for="category in categoryNavItems"
            :key="category.id"
            class="filter-chip"
            :class="{ active: activeCategoryId === category.id }"
            type="button"
            @click="setActiveCategory(category.id)"
          >
            <span>{{ category.icon }}</span>
            <span>{{ category.name }}</span>
            <span class="filter-chip-count">{{ category.totalSites }}</span>
          </button>
        </div>

        <div class="mobile-menu" :class="{ active: showMobileMenu }">
          <div class="mobile-menu-header">
            <h3 class="mobile-menu-title">分类导航</h3>
            <button class="mobile-close-btn" type="button" @click="closeMobileMenu">×</button>
          </div>
          <ul class="mobile-category-list">
            <li
              class="mobile-category-item"
              :class="{ active: !activeCategoryId }"
              @click="closeMobileMenu(); setActiveCategory(''); scrollToTop()"
            >
              <span class="category-icon">🧭</span>
              <span class="category-name">全部分类</span>
              <span class="category-count">{{ totalSiteCount }}</span>
            </li>
            <li
              v-for="category in categoryNavItems"
              :key="category.id"
              class="mobile-category-item"
              :class="{ active: activeCategoryId === category.id }"
              @click="jumpToCategoryMobile(category.id)"
            >
              <span class="category-icon">{{ category.icon }}</span>
              <span class="category-name">{{ category.name }}</span>
              <span class="category-count">{{ category.totalSites }}</span>
            </li>
          </ul>
        </div>

        <div
          class="mobile-menu-overlay"
          :class="{ active: showMobileMenu }"
          @click="closeMobileMenu"
        ></div>
      </header>

      <div class="content-area">
        <div v-if="loading" class="loading-state">
          <div class="loading-spinner"></div>
          <p class="state-text">正在整理导航内容...</p>
        </div>

        <div v-else-if="error" class="error-state">
          <p class="state-text">{{ error }}</p>
          <button class="retry-btn" type="button" @click="fetchCategories">重试</button>
        </div>

        <div v-else class="categories-container">
          <section class="hero-panel">
            <div class="hero-copy">
              <p class="hero-kicker">Bookmark-first Navigation</p>
              <h2 class="hero-title">{{ title || '专属导航工作台' }}</h2>
              <p class="hero-description">
                这是一套偏个人工作流的导航骨架。保留原始导航内容，只在前台增加筛选、折叠和常用区，方便你后续继续扩展。
              </p>
            </div>
            <div class="hero-metrics">
              <div class="hero-metric-card">
                <span class="hero-metric-value">{{ allCategories.length }}</span>
                <span class="hero-metric-label">主分类</span>
              </div>
              <div class="hero-metric-card">
                <span class="hero-metric-value">{{ totalSiteCount }}</span>
                <span class="hero-metric-label">总收录</span>
              </div>
              <div class="hero-metric-card">
                <span class="hero-metric-value">{{ pinnedSites.length }}</span>
                <span class="hero-metric-label">常用入口</span>
              </div>
            </div>
          </section>

          <section v-if="pinnedSites.length" class="pinned-section">
            <div class="section-header">
              <div>
                <p class="section-kicker">Priority Access</p>
                <h2 class="section-title">置顶常用</h2>
              </div>
              <span class="section-meta">{{ pinnedSites.length }} 个优先入口</span>
            </div>
            <div class="sites-grid pinned-grid">
              <a
                v-for="site in pinnedSites"
                :key="site.id"
                :href="site.url"
                target="_blank"
                rel="noopener noreferrer"
                class="site-card site-card-pinned"
              >
                <div class="site-card-top">
                  <div class="site-icon">
                    <img :src="site.icon" :alt="site.name" @error="handleImageError" />
                  </div>
                  <span class="site-badge">
                    {{ site.categoryIcon }} {{ site.categoryName }}
                  </span>
                </div>
                <div class="site-info">
                  <h3 class="site-name">{{ site.name }}</h3>
                  <p class="site-description">{{ site.description }}</p>
                  <p class="site-url">{{ site.url }}</p>
                </div>
              </a>
            </div>
          </section>

          <div v-if="filteredCategories.length" class="category-sections">
            <section
              v-for="category in filteredCategories"
              :id="`category-${category.id}`"
              :key="category.id"
              class="category-section"
            >
              <div class="section-header">
                <div>
                  <p class="section-kicker">Category {{ formatCategoryOrder(category.order) }}</p>
                  <h2 class="section-title">
                    <span class="section-icon">{{ category.icon }}</span>
                    <span>{{ category.name }}</span>
                  </h2>
                </div>
                <div class="section-actions">
                  <span class="section-meta">{{ category.sites.length }} 个站点</span>
                  <button
                    class="collapse-btn"
                    type="button"
                    @click="toggleCategoryCollapse(category.id)"
                  >
                    {{ isCategoryCollapsed(category.id) ? '展开' : '折叠' }}
                  </button>
                </div>
              </div>

              <div v-if="!isCategoryCollapsed(category.id)" class="sites-grid">
                <a
                  v-for="site in category.sites"
                  :key="site.id"
                  :href="site.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="site-card"
                >
                  <div class="site-card-top">
                    <div class="site-icon">
                      <img :src="site.icon" :alt="site.name" @error="handleImageError" />
                    </div>
                    <span v-if="site.pinned" class="site-badge site-badge-soft">常用</span>
                  </div>
                  <div class="site-info">
                    <h3 class="site-name">{{ site.name }}</h3>
                    <p class="site-description">{{ site.description }}</p>
                    <p class="site-url">{{ site.url }}</p>
                    <div class="site-tags">
                      <span
                        v-for="tag in (site.tags || []).slice(0, 2)"
                        :key="`${site.id}-${tag}`"
                        class="site-tag"
                      >
                        {{ tag }}
                      </span>
                    </div>
                  </div>
                </a>
              </div>

              <div v-else class="collapsed-placeholder">
                当前分组已折叠，点击右上角“展开”可恢复查看。
              </div>
            </section>
          </div>

          <div v-else class="empty-state">
            <div class="empty-state-box">
              <p class="hero-kicker">No Match</p>
              <h3 class="empty-state-title">{{ emptyStateTitle }}</h3>
              <p class="empty-state-description">{{ emptyStateDescription }}</p>
              <div class="empty-state-actions">
                <button class="retry-btn" type="button" @click="resetFilters">
                  重置筛选
                </button>
                <button
                  class="secondary-btn"
                  type="button"
                  :disabled="!searchQuery.trim()"
                  @click="handleExternalSearch"
                >
                  外部搜索
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.nav-home {
  --surface: #eef2e8;
  --surface-strong: rgba(255, 252, 244, 0.92);
  --surface-muted: rgba(255, 255, 255, 0.7);
  --surface-soft: rgba(240, 232, 214, 0.48);
  --text-main: #182119;
  --text-subtle: #5f675d;
  --text-soft: #7f877d;
  --line: rgba(24, 33, 25, 0.08);
  --line-strong: rgba(24, 33, 25, 0.16);
  --accent: #2f5b47;
  --accent-soft: rgba(47, 91, 71, 0.12);
  --accent-strong: #d86f2f;
  --shadow-soft: 0 20px 60px rgba(29, 34, 24, 0.08);
  --shadow-card: 0 18px 38px rgba(29, 34, 24, 0.08);
  min-height: 100vh;
  display: flex;
  background:
    radial-gradient(circle at top left, rgba(216, 111, 47, 0.12), transparent 34%),
    radial-gradient(circle at bottom right, rgba(47, 91, 71, 0.12), transparent 36%),
    linear-gradient(135deg, #f5f2ea 0%, #edf1e8 100%);
  color: var(--text-main);
  font-family: "IBM Plex Sans", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
}

.nav-home.is-dark {
  --surface: #121916;
  --surface-strong: rgba(21, 27, 24, 0.88);
  --surface-muted: rgba(28, 35, 31, 0.78);
  --surface-soft: rgba(47, 91, 71, 0.16);
  --text-main: #e7ede6;
  --text-subtle: #aab4ad;
  --text-soft: #7f8a83;
  --line: rgba(255, 255, 255, 0.08);
  --line-strong: rgba(255, 255, 255, 0.16);
  --accent: #80b692;
  --accent-soft: rgba(128, 182, 146, 0.18);
  --accent-strong: #f59f62;
  --shadow-soft: 0 20px 60px rgba(0, 0, 0, 0.28);
  --shadow-card: 0 18px 38px rgba(0, 0, 0, 0.24);
  background:
    radial-gradient(circle at top left, rgba(245, 159, 98, 0.14), transparent 30%),
    radial-gradient(circle at bottom right, rgba(128, 182, 146, 0.12), transparent 30%),
    linear-gradient(135deg, #0b1110 0%, #121916 100%);
}

.lock-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background:
    radial-gradient(circle at top left, rgba(216, 111, 47, 0.18), transparent 28%),
    linear-gradient(140deg, #111917 0%, #1d2a23 100%);
}

.lock-box {
  width: 100%;
  max-width: 420px;
  padding: 36px;
  border-radius: 28px;
  background: rgba(255, 252, 244, 0.96);
  box-shadow: 0 28px 80px rgba(0, 0, 0, 0.26);
}

.lock-title {
  margin: 0 0 8px;
  font-size: 30px;
  color: #182119;
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif;
}

.lock-description {
  margin: 0 0 28px;
  color: #5f675d;
  line-height: 1.7;
}

.lock-form-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.lock-label {
  font-size: 14px;
  color: #3d473f;
}

.lock-input {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid rgba(24, 33, 25, 0.14);
  border-radius: 16px;
  outline: none;
  font-size: 15px;
}

.lock-input:focus {
  border-color: rgba(47, 91, 71, 0.4);
  box-shadow: 0 0 0 4px rgba(47, 91, 71, 0.08);
}

.unlock-btn {
  width: 100%;
  margin-top: 16px;
  padding: 14px 20px;
  border: none;
  border-radius: 16px;
  background: linear-gradient(135deg, #2f5b47 0%, #d86f2f 100%);
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.unlock-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.lock-error {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(216, 111, 47, 0.12);
  color: #a04d1f;
}

.sidebar {
  width: 312px;
  min-height: 100vh;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  background: rgba(248, 244, 233, 0.74);
  border-right: 1px solid var(--line);
  backdrop-filter: blur(18px);
}

.nav-home.is-dark .sidebar {
  background: rgba(15, 21, 18, 0.88);
}

.logo-section,
.sidebar-panel,
.category-nav,
.sidebar-footer,
.search-header,
.hero-panel,
.category-section,
.empty-state-box {
  border: 1px solid var(--line);
  background: var(--surface-strong);
  box-shadow: var(--shadow-soft);
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
  border-radius: 28px;
}

.logo {
  width: 60px;
  height: 60px;
  border-radius: 18px;
  object-fit: cover;
}

.logo-copy {
  min-width: 0;
}

.logo-caption {
  margin: 0 0 4px;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-soft);
}

.site-title {
  margin: 0;
  font-size: 28px;
  color: var(--text-main);
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif;
}

.sidebar-panel {
  padding: 20px;
  border-radius: 28px;
}

.sidebar-kicker,
.hero-kicker,
.section-kicker {
  margin: 0 0 10px;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--accent-strong);
}

.sidebar-heading {
  margin: 0;
  font-size: 22px;
  line-height: 1.45;
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif;
}

.sidebar-stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-top: 18px;
}

.sidebar-stat-card,
.hero-metric-card {
  padding: 14px 12px;
  border-radius: 20px;
  background: var(--surface-soft);
  border: 1px solid var(--line);
}

.sidebar-stat-value,
.hero-metric-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: var(--text-main);
}

.sidebar-stat-label,
.hero-metric-label {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-subtle);
}

.category-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 18px;
  border-radius: 28px;
  min-height: 0;
}

.nav-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.nav-title {
  margin: 0;
  font-size: 14px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-soft);
}

.nav-reset-btn,
.collapse-btn,
.clear-search-btn,
.secondary-btn {
  border: 1px solid var(--line-strong);
  background: transparent;
  color: var(--text-main);
}

.nav-reset-btn,
.collapse-btn,
.clear-search-btn,
.external-search-btn,
.theme-toggle-btn,
.mobile-menu-btn,
.retry-btn,
.secondary-btn {
  border-radius: 999px;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, background-color 0.2s ease;
}

.nav-reset-btn {
  padding: 7px 12px;
  font-size: 12px;
}

.nav-reset-btn:hover,
.collapse-btn:hover,
.clear-search-btn:hover,
.secondary-btn:hover {
  border-color: rgba(216, 111, 47, 0.42);
}

.category-list,
.mobile-category-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.category-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
}

.category-item,
.mobile-category-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 20px;
  cursor: pointer;
  color: var(--text-main);
  transition: transform 0.2s ease, background-color 0.2s ease;
}

.category-item {
  background: transparent;
}

.category-item:hover,
.mobile-category-item:hover {
  transform: translateX(3px);
  background: var(--accent-soft);
}

.category-item.active,
.mobile-category-item.active {
  background: linear-gradient(135deg, rgba(47, 91, 71, 0.16), rgba(216, 111, 47, 0.14));
  border: 1px solid rgba(216, 111, 47, 0.16);
}

.category-icon {
  width: 22px;
  text-align: center;
  flex-shrink: 0;
}

.category-name {
  flex: 1;
  min-width: 0;
}

.category-count {
  flex-shrink: 0;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-subtle);
  font-size: 12px;
}

.sidebar-footer {
  padding: 18px;
  border-radius: 28px;
}

.sidebar-note {
  margin: 0;
  color: var(--text-subtle);
  line-height: 1.7;
  font-size: 14px;
}

.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.search-header {
  position: sticky;
  top: 0;
  z-index: 30;
  margin: 22px 22px 0;
  padding: 18px;
  border-radius: 32px;
  backdrop-filter: blur(18px);
}

.search-top-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-container {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 10px;
  border-radius: 24px;
  background: var(--surface-muted);
  border: 1px solid var(--line);
}

.search-engine-selector {
  position: relative;
  width: 58px;
  height: 46px;
  border-radius: 16px;
  background: var(--surface);
  border: 1px solid var(--line);
  overflow: hidden;
  flex-shrink: 0;
}

.engine-logo {
  width: 24px;
  height: 24px;
  position: absolute;
  inset: 0;
  margin: auto;
  object-fit: contain;
  pointer-events: none;
}

.engine-select {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}

.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  color: var(--text-main);
  font-size: 15px;
}

.search-input::placeholder {
  color: var(--text-soft);
}

.clear-search-btn,
.external-search-btn,
.theme-toggle-btn,
.mobile-menu-btn,
.retry-btn,
.secondary-btn {
  padding: 12px 16px;
  font-size: 14px;
}

.external-search-btn {
  border: none;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%);
  color: #fff;
}

.external-search-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.theme-toggle-btn,
.mobile-menu-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--line);
  background: var(--surface-muted);
  color: var(--text-main);
}

.mobile-menu-btn {
  display: none;
}

.search-sub-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
}

.search-summary {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text-subtle);
}

.summary-emphasis {
  font-size: 30px;
  font-weight: 700;
  color: var(--text-main);
}

.summary-text,
.search-hint {
  color: var(--text-subtle);
  font-size: 14px;
  line-height: 1.6;
}

.filter-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--surface-muted);
  color: var(--text-main);
  cursor: pointer;
}

.filter-chip.active {
  border-color: rgba(216, 111, 47, 0.24);
  background: linear-gradient(135deg, rgba(47, 91, 71, 0.14), rgba(216, 111, 47, 0.14));
}

.filter-chip-count {
  font-size: 12px;
  color: var(--text-soft);
}

.mobile-menu {
  position: fixed;
  top: 0;
  right: -100%;
  width: 280px;
  height: 100vh;
  padding: 18px;
  background: var(--surface-strong);
  border-left: 1px solid var(--line);
  box-shadow: var(--shadow-card);
  transition: right 0.28s ease;
  z-index: 40;
}

.mobile-menu.active {
  right: 0;
}

.mobile-menu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.mobile-menu-title {
  margin: 0;
  font-size: 18px;
  color: var(--text-main);
}

.mobile-close-btn {
  border: none;
  background: transparent;
  color: var(--text-main);
  font-size: 28px;
  cursor: pointer;
}

.mobile-category-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mobile-menu-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.36);
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.28s ease, visibility 0.28s ease;
  z-index: 35;
}

.mobile-menu-overlay.active {
  opacity: 1;
  visibility: visible;
}

.content-area {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px;
}

.loading-state,
.error-state,
.empty-state {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-state,
.error-state {
  flex-direction: column;
}

.loading-spinner {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 4px solid rgba(47, 91, 71, 0.12);
  border-top-color: var(--accent);
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.state-text {
  margin: 16px 0 0;
  color: var(--text-subtle);
}

.retry-btn {
  margin-top: 16px;
  border: none;
  background: linear-gradient(135deg, var(--accent) 0%, var(--accent-strong) 100%);
  color: #fff;
}

.categories-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 1360px;
  margin: 0 auto;
}

.hero-panel {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.9fr);
  gap: 20px;
  padding: 24px;
  border-radius: 34px;
}

.hero-title {
  margin: 0;
  font-size: 40px;
  line-height: 1.18;
  color: var(--text-main);
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif;
}

.hero-description {
  margin: 16px 0 0;
  max-width: 720px;
  color: var(--text-subtle);
  line-height: 1.8;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.section-title {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin: 0;
  font-size: 28px;
  color: var(--text-main);
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif;
}

.section-icon {
  font-size: 28px;
}

.section-meta {
  color: var(--text-subtle);
  font-size: 13px;
}

.section-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.collapse-btn {
  padding: 10px 14px;
  font-size: 13px;
}

.pinned-section,
.category-section {
  padding: 22px;
  border-radius: 30px;
  background: var(--surface-strong);
  border: 1px solid var(--line);
  box-shadow: var(--shadow-card);
}

.sites-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 16px;
}

.site-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  border-radius: 24px;
  border: 1px solid var(--line);
  background: var(--surface-muted);
  color: inherit;
  text-decoration: none;
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
}

.site-card:hover {
  transform: translateY(-4px);
  border-color: rgba(216, 111, 47, 0.24);
  box-shadow: var(--shadow-card);
}

.site-card-pinned {
  background: linear-gradient(180deg, rgba(216, 111, 47, 0.12), rgba(47, 91, 71, 0.08));
}

.site-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.site-icon {
  width: 52px;
  height: 52px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: var(--surface);
  border: 1px solid var(--line);
}

.site-icon img {
  width: 30px;
  height: 30px;
  object-fit: contain;
}

.site-badge,
.site-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}

.site-badge {
  background: rgba(216, 111, 47, 0.12);
  color: #b35a27;
}

.site-badge-soft {
  background: rgba(47, 91, 71, 0.12);
  color: var(--accent);
}

.site-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.site-name {
  margin: 0;
  font-size: 18px;
  color: var(--text-main);
}

.site-description,
.site-url {
  margin: 0;
  color: var(--text-subtle);
  line-height: 1.6;
}

.site-url {
  font-size: 13px;
  color: var(--text-soft);
  word-break: break-all;
}

.site-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.site-tag {
  background: var(--surface-soft);
  color: var(--text-subtle);
}

.collapsed-placeholder {
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px dashed var(--line-strong);
  color: var(--text-subtle);
  background: var(--surface-soft);
}

.empty-state-box {
  width: 100%;
  max-width: 620px;
  padding: 32px;
  border-radius: 32px;
  text-align: center;
}

.empty-state-title {
  margin: 0;
  font-size: 30px;
  color: var(--text-main);
  font-family: "Source Han Serif SC", "Noto Serif SC", "Songti SC", serif;
}

.empty-state-description {
  margin: 14px 0 0;
  color: var(--text-subtle);
  line-height: 1.8;
}

.empty-state-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  margin-top: 20px;
}

.secondary-btn {
  padding: 12px 16px;
}

@media (max-width: 1120px) {
  .sidebar {
    display: none;
  }

  .mobile-menu-btn {
    display: inline-flex;
  }

  .hero-panel {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .search-header,
  .content-area {
    margin: 0;
    padding: 16px;
  }

  .search-header {
    border-radius: 0 0 28px 28px;
  }

  .search-top-row,
  .search-sub-row,
  .section-header {
    flex-direction: column;
    align-items: stretch;
  }

  .search-container {
    order: 1;
  }

  .external-search-btn,
  .theme-toggle-btn,
  .mobile-menu-btn {
    width: 100%;
    justify-content: center;
  }

  .hero-title {
    font-size: 34px;
  }

  .hero-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .sites-grid {
    grid-template-columns: 1fr;
  }

  .filter-chip-row {
    overflow-x: auto;
    flex-wrap: nowrap;
    padding-bottom: 6px;
  }

  .filter-chip {
    flex-shrink: 0;
  }
}

@media (max-width: 560px) {
  .lock-box,
  .hero-panel,
  .category-section,
  .pinned-section,
  .empty-state-box {
    padding: 20px;
    border-radius: 24px;
  }

  .hero-metrics,
  .sidebar-stats {
    grid-template-columns: 1fr;
  }

  .summary-emphasis {
    font-size: 24px;
  }

  .section-title {
    font-size: 24px;
  }
}
</style>
