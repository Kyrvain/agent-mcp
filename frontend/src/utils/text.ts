export interface DiffSegment {
  text: string
  kind: 'equal' | 'insert' | 'delete'
}

export function stripFeatureNumber(value: string) {
  return value.replace(/^\s*\d+[\s.、)）-]*/, '').trim()
}

export function buildProofreadSourceText(features: string[]) {
  return features
    .map((item) => item.replace(/\r\n|\r|\n/g, '').trim())
    .filter(Boolean)
    .join('')
}

export function diffText(source: string, corrected: string) {
  if (!source && !corrected) {
    return [] as DiffSegment[]
  }
  if (source === corrected) {
    return [{ text: source, kind: 'equal' }] as DiffSegment[]
  }

  const sourceChars = Array.from(source)
  const correctedChars = Array.from(corrected)
  if (sourceChars.length * correctedChars.length > 1_000_000) {
    return fallbackDiff(source, corrected)
  }

  const width = correctedChars.length + 1
  const table = new Uint32Array((sourceChars.length + 1) * width)

  for (let i = sourceChars.length - 1; i >= 0; i -= 1) {
    for (let j = correctedChars.length - 1; j >= 0; j -= 1) {
      const index = i * width + j
      table[index] = sourceChars[i] === correctedChars[j]
        ? table[(i + 1) * width + j + 1] + 1
        : Math.max(table[(i + 1) * width + j], table[i * width + j + 1])
    }
  }

  const segments: DiffSegment[] = []
  let i = 0
  let j = 0
  while (i < sourceChars.length && j < correctedChars.length) {
    if (sourceChars[i] === correctedChars[j]) {
      pushSegment(segments, sourceChars[i], 'equal')
      i += 1
      j += 1
    } else if (table[(i + 1) * width + j] >= table[i * width + j + 1]) {
      pushSegment(segments, sourceChars[i], 'delete')
      i += 1
    } else {
      pushSegment(segments, correctedChars[j], 'insert')
      j += 1
    }
  }
  while (i < sourceChars.length) {
    pushSegment(segments, sourceChars[i], 'delete')
    i += 1
  }
  while (j < correctedChars.length) {
    pushSegment(segments, correctedChars[j], 'insert')
    j += 1
  }
  return segments
}

export function sourceDiffSegments(segments: DiffSegment[]) {
  return segments.filter((segment) => segment.kind !== 'insert')
}

export function correctedDiffSegments(segments: DiffSegment[]) {
  return segments.filter((segment) => segment.kind !== 'delete')
}

function pushSegment(segments: DiffSegment[], text: string, kind: DiffSegment['kind']) {
  const previous = segments[segments.length - 1]
  if (previous?.kind === kind) {
    previous.text += text
    return
  }
  segments.push({ text, kind })
}

function fallbackDiff(source: string, corrected: string) {
  let prefix = 0
  while (
    prefix < source.length &&
    prefix < corrected.length &&
    source[prefix] === corrected[prefix]
  ) {
    prefix += 1
  }

  let sourceSuffix = source.length
  let correctedSuffix = corrected.length
  while (
    sourceSuffix > prefix &&
    correctedSuffix > prefix &&
    source[sourceSuffix - 1] === corrected[correctedSuffix - 1]
  ) {
    sourceSuffix -= 1
    correctedSuffix -= 1
  }

  const segments: DiffSegment[] = []
  if (prefix > 0) {
    segments.push({ text: source.slice(0, prefix), kind: 'equal' })
  }
  if (sourceSuffix > prefix) {
    segments.push({ text: source.slice(prefix, sourceSuffix), kind: 'delete' })
  }
  if (correctedSuffix > prefix) {
    segments.push({ text: corrected.slice(prefix, correctedSuffix), kind: 'insert' })
  }
  if (sourceSuffix < source.length) {
    segments.push({ text: source.slice(sourceSuffix), kind: 'equal' })
  }
  return segments
}
