const PRIMARY_TEXT_KEYS = [
  'content',
  'chapter_content',
  'chapter_text',
  'full_content',
  'text',
  'body',
  'story',
  'chapter',
  'real_summary',
  'summary'
] as const

const AUXILIARY_TEXT_KEYS = [
  'parsed_json',
  'final_content',
  'result',
  'data'
] as const

const GUARDRAIL_ONLY_KEYS = ['guardrail', 'parsed_json', 'chapter_mission'] as const

function cleanText(text: string, parseJson = true): string {
  let stripped = text.trim()
  if (!stripped) {
    return ''
  }

  if (
    parseJson &&
    ((stripped.startsWith('{') && stripped.endsWith('}')) ||
      (stripped.startsWith('[') && stripped.endsWith(']')))
  ) {
    try {
      const parsed = JSON.parse(stripped)
      const extracted = extractNestedText(parsed)
      if (extracted) {
        return extracted
      }
      if (typeof parsed === 'object' && parsed && GUARDRAIL_ONLY_KEYS.some((key) => key in parsed)) {
        return ''
      }
    } catch {
      // Ignore malformed JSON-like content and keep the original text.
    }
  }

  if (stripped.startsWith('"') && stripped.endsWith('"') && stripped.length >= 2) {
    stripped = stripped.slice(1, -1)
  }

  return stripped
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, '\\')
}

function extractNestedText(value: unknown): string | null {
  if (value === null || value === undefined) {
    return null
  }

  if (typeof value === 'string') {
    const cleaned = cleanText(value)
    return cleaned || null
  }

  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }

  if (Array.isArray(value)) {
    for (const item of value) {
      const nested = extractNestedText(item)
      if (nested) {
        return nested
      }
    }
    return null
  }

  if (typeof value === 'object') {
    const record = value as Record<string, unknown>

    for (const key of PRIMARY_TEXT_KEYS) {
      if (record[key]) {
        const nested = extractNestedText(record[key])
        if (nested) {
          return nested
        }
      }
    }

    for (const key of AUXILIARY_TEXT_KEYS) {
      if (record[key]) {
        const nested = extractNestedText(record[key])
        if (nested) {
          return nested
        }
      }
    }

    if (GUARDRAIL_ONLY_KEYS.some((key) => key in record)) {
      return null
    }
  }

  return null
}

export function extractChapterContent(value: unknown): string {
  return extractNestedText(value) ?? ''
}

export function getChapterCharacterCount(value: unknown): number {
  return extractChapterContent(value).replace(/\s+/g, '').length
}

export function getRoundedChapterCharacterCount(value: unknown): number {
  const count = getChapterCharacterCount(value)
  if (count <= 0) {
    return 0
  }
  return Math.max(100, Math.round(count / 100) * 100)
}

export function getChapterPreview(
  value: unknown,
  limit = 150,
  fallback = '正文提取失败，请重新生成该章节'
): string {
  const content = extractChapterContent(value)
  if (!content) {
    return fallback
  }
  if (limit <= 0 || content.length <= limit) {
    return content
  }
  return `${content.slice(0, limit)}...`
}
