const buildSiteSearchText = (site = {}, category = {}) => {
  return [
    site.name,
    site.description,
    site.url,
    category.name,
    ...(site.tags || []),
    site.sourceFolder,
    site.sourcePath,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
}

export const normalizeSearchQuery = (query = '') => {
  return query.trim().toLowerCase()
}

export const siteMatchesQuery = (site, category, query) => {
  if (!query) {
    return true
  }

  return buildSiteSearchText(site, category).includes(query)
}

export const filterCategoriesByQuery = (categories, { activeCategoryId = '', normalizedQuery = '' } = {}) => {
  const categoryList = Array.isArray(categories) ? categories : []

  return categoryList
    .filter(category => !activeCategoryId || category.id === activeCategoryId)
    .map(category => ({
      ...category,
      sites: (category.sites || []).filter(site => siteMatchesQuery(site, category, normalizedQuery)),
    }))
    .filter(category => !normalizedQuery || category.sites.length > 0)
}

export const findFirstMatchedCategoryId = (categories, normalizedQuery) => {
  if (!normalizedQuery) {
    return ''
  }

  return filterCategoriesByQuery(categories, { normalizedQuery })[0]?.id || ''
}
