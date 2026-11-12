/**
 * Turn text plus a list of findings (start/end character offsets) into a flat list of
 * segments to render: plain text in between, and one segment per finding span. Used
 * by the Scan Center to underline/highlight each detected span inline.
 */

export interface SpanFinding {
  category: string;
  start: number;
  end: number;
  confidence: number;
  recognizer: string;
  checksum_valid?: boolean | null;
}

export interface TextSegment {
  text: string;
  findings: SpanFinding[];
}

/**
 * Builds segments from text and findings. Findings are sorted by start, invalid spans
 * (end <= start, or out of bounds) are dropped, and overlapping or adjacent spans are
 * merged into one segment that carries every finding touching it, so nothing is drawn
 * twice and nothing is silently hidden.
 */
export function buildHighlightSegments(text: string, findings: SpanFinding[]): TextSegment[] {
  const valid = findings
    .filter((f) => f.start >= 0 && f.end > f.start && f.end <= text.length)
    .slice()
    .sort((a, b) => a.start - b.start || a.end - b.end);

  if (valid.length === 0) {
    return text ? [{ text, findings: [] }] : [];
  }

  // Merge overlapping/adjacent finding spans into boundary groups first, so a segment's
  // finding list is exactly the findings active over that slice of text.
  type Group = { start: number; end: number; findings: SpanFinding[] };
  const groups: Group[] = [];
  for (const f of valid) {
    const last = groups[groups.length - 1];
    if (last && f.start <= last.end) {
      last.end = Math.max(last.end, f.end);
      last.findings.push(f);
    } else {
      groups.push({ start: f.start, end: f.end, findings: [f] });
    }
  }

  const segments: TextSegment[] = [];
  let cursor = 0;
  for (const g of groups) {
    if (g.start > cursor) segments.push({ text: text.slice(cursor, g.start), findings: [] });
    segments.push({ text: text.slice(g.start, g.end), findings: g.findings });
    cursor = g.end;
  }
  if (cursor < text.length) segments.push({ text: text.slice(cursor), findings: [] });

  return segments;
}
