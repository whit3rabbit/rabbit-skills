import { readFileSync } from 'node:fs'
import { defineTool } from '@deepseek-ai/dsh-tools'

export const name = 'schema-find-refs'
export const inject = ['tools']

const fixture = 'fixtures/schema.sql'
const lines = readFileSync(new URL(fixture, import.meta.url), 'utf8').split(/\r?\n/)

export function apply(ctx) {
  ctx.tools.register(defineTool({
    name: 'schema_find_refs',
    description: 'Find lines in the bundled SQLite example schema that mention a table identifier.',
    parameters: {
      table: { type: 'string', required: true, description: 'SQLite table identifier from the example schema' },
      limit: { type: 'integer', description: 'Maximum matches, from 1 to 10. Defaults to 5.' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          references: {
            type: 'array',
            required: true,
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                file: { type: 'string', required: true },
                line: { type: 'integer', required: true },
                text: { type: 'string', required: true },
              },
            },
          },
          truncated: { type: 'boolean', required: true },
        },
      },
      render: (_args, { references, truncated }) => {
        const matches = references.map(({ file, line, text }) => `${file}:${line} ${text}`)
        if (truncated) matches.push('More matches exist. Increase limit to see them.')
        return [{ type: 'text', text: matches.join('\n') || 'No matches in the bundled schema.' }]
      },
    },
    async execute({ table, limit = 5 }) {
      if (!/^[a-z_][a-z0-9_]{0,62}$/i.test(table)) {
        throw new Error('Provide a simple table identifier, for example orders.')
      }
      if (limit < 1 || limit > 10) {
        throw new Error('Set limit to an integer from 1 to 10.')
      }

      // This is an identifier lookup over a fixed fixture. It never runs SQL.
      const identifier = table.toLowerCase()
      const references = []
      for (const [index, line] of lines.entries()) {
        const tokens = line.toLowerCase().match(/[a-z_][a-z0-9_]*/g) ?? []
        if (!tokens.includes(identifier)) continue
        if (references.length === limit) return { references, truncated: true }
        references.push({ file: fixture, line: index + 1, text: line.trim() })
      }
      return { references, truncated: false }
    },
  }))
}
