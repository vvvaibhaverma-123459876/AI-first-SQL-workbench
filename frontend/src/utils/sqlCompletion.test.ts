import { describe, expect, it } from 'vitest'
import { buildSqlCompletionCandidates } from './sqlCompletion'

describe('buildSqlCompletionCandidates', () => {
  it('offers every table and every column from the live schema', () => {
    const candidates = buildSqlCompletionCandidates([
      {
        schema_name: null,
        name: 'widgets',
        columns: [
          { name: 'id', type: 'INTEGER', nullable: false },
          { name: 'label', type: 'TEXT', nullable: true },
        ],
      },
    ])

    expect(candidates.find((c) => c.label === 'widgets' && c.kind === 'table')).toBeTruthy()
    expect(candidates.find((c) => c.label === 'id' && c.kind === 'column')).toBeTruthy()
    expect(candidates.find((c) => c.label === 'label' && c.kind === 'column')).toBeTruthy()
  })

  it('dedupes a column name that repeats within the same table across two schema fetches', () => {
    const table = {
      schema_name: null,
      name: 'widgets',
      columns: [
        { name: 'id', type: 'INTEGER', nullable: false },
        { name: 'id', type: 'INTEGER', nullable: false },
      ],
    }
    const candidates = buildSqlCompletionCandidates([table])
    expect(candidates.filter((c) => c.label === 'id' && c.kind === 'column')).toHaveLength(1)
  })

  it('returns no candidates for a connection with no tables', () => {
    expect(buildSqlCompletionCandidates([])).toEqual([])
  })
})
