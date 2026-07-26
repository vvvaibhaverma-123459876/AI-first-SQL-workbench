import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ResponsiveContainer } from 'recharts'
import type { ChartType } from '../../types'

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#a855f7', '#06b6d4']

export function ChartView({
  chartType,
  columns,
  rows,
  xField,
  yFields,
}: {
  chartType: ChartType
  columns: string[]
  rows: Record<string, unknown>[]
  xField: string | null
  yFields: string[]
}) {
  if (chartType === 'table' || rows.length === 0) {
    return (
      <table className="w-full text-left text-xs">
        <thead className="sticky top-0 bg-slate-900">
          <tr>
            {columns.map((col) => (
              <th key={col} className="border-b border-slate-800 px-2 py-1 font-medium text-slate-400">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="odd:bg-slate-900/40">
              {columns.map((col) => (
                <td key={col} className="border-b border-slate-800/60 px-2 py-1 text-slate-300">
                  {String(row[col] ?? '')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    )
  }

  const x = xField ?? columns[0]
  const ys = yFields.length > 0 ? yFields : columns.filter((c) => c !== x).slice(0, 1)

  if (chartType === 'pie') {
    const valueField = ys[0]
    const data = rows.map((r) => ({ name: String(r[x] ?? ''), value: Number(r[valueField] ?? 0) }))
    return (
      <ResponsiveContainer width="100%" height={260}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" outerRadius={90} label>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (chartType === 'scatter') {
    const yField = ys[0]
    const data = rows.map((r) => ({ [x]: Number(r[x] ?? 0), [yField]: Number(r[yField] ?? 0) }))
    return (
      <ResponsiveContainer width="100%" height={260}>
        <ScatterChart>
          <CartesianGrid stroke="#1e293b" />
          <XAxis dataKey={x} name={x} stroke="#94a3b8" fontSize={11} />
          <YAxis dataKey={yField} name={yField} stroke="#94a3b8" fontSize={11} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} />
          <Scatter data={data} fill={COLORS[0]} />
        </ScatterChart>
      </ResponsiveContainer>
    )
  }

  const Chart = chartType === 'line' ? LineChart : BarChart
  return (
    <ResponsiveContainer width="100%" height={260}>
      <Chart data={rows}>
        <CartesianGrid stroke="#1e293b" />
        <XAxis dataKey={x} stroke="#94a3b8" fontSize={11} />
        <YAxis stroke="#94a3b8" fontSize={11} />
        <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b' }} />
        <Legend />
        {ys.map((field, i) =>
          chartType === 'line' ? (
            <Line key={field} type="monotone" dataKey={field} stroke={COLORS[i % COLORS.length]} dot={false} />
          ) : (
            <Bar key={field} dataKey={field} fill={COLORS[i % COLORS.length]} />
          ),
        )}
      </Chart>
    </ResponsiveContainer>
  )
}
