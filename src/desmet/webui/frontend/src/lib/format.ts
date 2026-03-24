/**
 * Content formatting utilities for trace observation input/output.
 *
 * Langfuse observations can contain:
 *  - Valid JSON strings  → pretty-print with indentation
 *  - Python object reprs → extract readable fields (CrewAI agents, tasks, crews)
 *  - Plain text         → pass through unchanged
 */

/**
 * Extract the value of a named field from a Python object repr string.
 * Handles both escaped (`role=\'...\'`) and unescaped (`role='...'`) forms.
 */
function extractPyField(s: string, key: string, maxLen = 300): string | null {
  // Escaped single-quote form: key=\'value\'
  const escaped = new RegExp(`${key}=\\\\'([^\\\\']{1,${maxLen}})\\\\'`);
  let m = s.match(escaped);
  if (m) return m[1];
  // Unescaped form: key='value'
  const plain = new RegExp(`${key}='([^']{1,${maxLen}})'`);
  m = s.match(plain);
  if (m) return m[1];
  return null;
}

/**
 * Format observation content for display.
 *
 * Priority:
 *  1. Valid JSON  → `JSON.stringify(..., null, 2)`
 *  2. Python CrewAI agent/task/crew repr → structured JSON summary
 *  3. Raw text    → pass through (rendered in `<pre>` by the caller)
 */
export function formatContent(raw: string | null | undefined): string {
  if (!raw) return '';
  const s = raw.trim();

  // ── 1. Try JSON ───────────────────────────────────────────────────────────
  try { return JSON.stringify(JSON.parse(s), null, 2); } catch {}

  // ── 2. Python CrewAI repr detection ──────────────────────────────────────
  // Matches Agent reprs which contain role= and backstory= field markers.
  const isAgentRepr =
    (s.includes("role=\\'") || s.includes("role='")) &&
    (s.includes("backstory=\\'") || s.includes("backstory='"));

  if (isAgentRepr) {
    const out: Record<string, string> = { _repr: 'crewai.Agent' };
    for (const key of ['role', 'goal', 'backstory']) {
      const v = extractPyField(s, key, key === 'backstory' ? 400 : 200);
      if (v) out[key] = v;
    }
    // Count tools from the tools=[...] section
    const toolsMatch = s.match(/tools=\[([^\]]*)\]/);
    if (toolsMatch) {
      const toolNames = [...toolsMatch[1].matchAll(/name=['\\]+'?(\w+)/g)].map(m => m[1]);
      if (toolNames.length > 0) out.tools = toolNames.join(', ');
    }
    return JSON.stringify(out, null, 2);
  }

  // Outer Python dict wrapping an agent repr: {'agent': '...repr...'}
  const outerMatch = s.match(/^\{'(\w+)':\s*'([\s\S]+)'\}$/);
  if (outerMatch) {
    const key = outerMatch[1];
    // Un-escape inner escaped quotes and recurse
    const inner = outerMatch[2].replace(/\\'/g, "'");
    const formatted = formatContent(inner);
    // If we got a structured result, wrap it
    try {
      return JSON.stringify({ [key]: JSON.parse(formatted) }, null, 2);
    } catch {
      return `${key}:\n${formatted}`;
    }
  }

  // ── 3. Pass through ───────────────────────────────────────────────────────
  return s;
}
