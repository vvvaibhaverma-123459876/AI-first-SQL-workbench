import type { ChartType } from '../types'

// Extends the row-shape heuristic ResultsPanel's MiniBarChart already used
// (numeric vs. label columns, a sane row-count window) to also pick
// line/scatter/pie instead of defaulting to bar unconditionally.
export function suggestChart(columns: string[], rows: Record<string, unknown>[]): { chartType: ChartType; xField: string | null; yFields: string[] } {
  const isNumeric = (col: string) => rows.length > 0 && rows.every((r) => r[col] !== null && r[col] !== undefined && !isNaN(Number(r[col])))
  const numericCols = columns.filter(isNumeric)
  const labelCols = columns.filter((c) => !numericCols.includes(c))

  if (numericCols.length === 0 || rows.length < 2) {
    return { chartType: 'table', xField: null, yFields: [] }
  }

  const isTimeLike = (col: string) => /date|time|month|day|year|week/i.test(col)
  const timeCol = labelCols.find(isTimeLike)

  if (timeCol) {
    return { chartType: 'line', xField: timeCol, yFields: numericCols.slice(0, 3) }
  }
  if (labelCols.length >= 1 && numericCols.length === 1 && rows.length <= 8) {
    return { chartType: 'pie', xField: labelCols[0], yFields: [numericCols[0]] }
  }
  if (numericCols.length >= 2 && labelCols.length === 0) {
    return { chartType: 'scatter', xField: numericCols[0], yFields: [numericCols[1]] }
  }
  if (labelCols.length >= 1 && rows.length <= 30) {
    return { chartType: 'bar', xField: labelCols[0] ?? columns[0], yFields: numericCols.slice(0, 3) }
  }
  return { chartType: 'table', xField: null, yFields: [] }
}
