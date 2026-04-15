import { describe, expect, it } from 'vitest'
import { titleCase } from './utils/format'

describe('titleCase', () => {
  it('formats snake case labels', () => {
    expect(titleCase('support_tickets')).toBe('Support Tickets')
  })
})
