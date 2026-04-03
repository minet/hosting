import { useState } from 'react'

export function usePagination<T>(items: T[], pageSize = 10) {
  const [visible, setVisible] = useState(pageSize)

  const shown = items.slice(0, visible)
  const remaining = items.length - visible
  const hasMore = remaining > 0

  function showMore() {
    setVisible(v => v + pageSize)
  }

  function reset() {
    setVisible(pageSize)
  }

  return { shown, hasMore, remaining, showMore, reset, total: items.length }
}
