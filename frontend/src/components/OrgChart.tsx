import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ChevronDown, ChevronRight, Download } from 'lucide-react'
import { useMemo, useState } from 'react'
import { api, downloadUrl } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Avatar, ErrorBox, Spinner } from './ui'

interface Person { name: string; employee_name: string; designation?: string; department?: string; reports_to?: string; image?: string }
interface Node extends Person { children: Node[]; size: number }

/** Build the reporting tree. Managers outside the filter (or missing) make their reports roots. */
function buildTree(rows: Person[]): Node[] {
  const byId = new Map<string, Node>(rows.map((r) => [r.name, { ...r, children: [], size: 0 }]))
  const roots: Node[] = []
  for (const node of byId.values()) {
    const parent = node.reports_to && node.reports_to !== node.name ? byId.get(node.reports_to) : undefined
    if (parent) parent.children.push(node)
    else roots.push(node)
  }
  const count = (n: Node, seen: Set<string>): number => {
    if (seen.has(n.name)) return 0 // guards against reporting loops in the data
    seen.add(n.name)
    n.children.sort((a, b) => a.employee_name.localeCompare(b.employee_name))
    n.size = n.children.reduce((s, c) => s + 1 + count(c, seen), 0)
    return n.size
  }
  const seen = new Set<string>()
  roots.forEach((r) => count(r, seen))
  // Big teams first, then people without a manager listed alphabetically.
  return roots.sort((a, b) => b.size - a.size || a.employee_name.localeCompare(b.employee_name))
}

function Branch({ node, depth, onOpen, open, toggle, highlight }: {
  node: Node; depth: number; onOpen: (id: string) => void; open: Set<string>; toggle: (id: string) => void; highlight: string
}) {
  const { t } = useI18n()
  const expanded = open.has(node.name)
  const hit = highlight && node.employee_name.toLowerCase().includes(highlight.toLowerCase())
  return (
    <li>
      <div className="flex items-center gap-1" style={{ paddingInlineStart: depth * 20 }}>
        {node.children.length ? (
          <button onClick={() => toggle(node.name)} className="rounded p-1 text-muted hover:bg-surface" aria-label={expanded ? t('Collapse') : t('Expand')}>
            {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4 flip-rtl" />}
          </button>
        ) : <span className="w-6" />}
        <button onClick={() => onOpen(node.name)}
          className={clsx('flex min-w-0 flex-1 items-center gap-3 rounded-xl border px-3 py-2 text-start hover:bg-surface', hit ? 'border-brand bg-brand-50' : 'border-transparent')}>
          <Avatar name={node.employee_name} image={node.image} size={32} />
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{node.employee_name}</span>
            <span className="block truncate text-xs text-muted">{[node.designation, node.department].filter(Boolean).join(' · ')}</span>
          </span>
          {node.size > 0 && <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-muted">{node.size} {t('in team')}</span>}
        </button>
      </div>
      {expanded && node.children.length > 0 && (
        <ul>{node.children.map((c) => <Branch key={c.name} node={c} depth={depth + 1} onOpen={onOpen} open={open} toggle={toggle} highlight={highlight} />)}</ul>
      )}
    </li>
  )
}

export function OrgChart({ department, search, onOpen }: { department?: string; search: string; onOpen: (id: string) => void }) {
  const { t } = useI18n()
  const q = useQuery<{ rows: Person[] }>({ queryKey: ['orgChart', department], queryFn: () => api.orgChart({ department }) })
  const tree = useMemo(() => buildTree(q.data?.rows ?? []), [q.data])
  const [open, setOpen] = useState<Set<string> | null>(null)
  const [orphans, setOrphans] = useState(false)
  // Expand the top level by default; when searching, expand the path to every match.
  const expanded = useMemo(() => {
    if (search) {
      const ids = new Set<string>()
      const rows = new Map((q.data?.rows ?? []).map((r) => [r.name, r]))
      for (const r of rows.values()) {
        if (!r.employee_name.toLowerCase().includes(search.toLowerCase())) continue
        let cur = r.reports_to ? rows.get(r.reports_to) : undefined
        const guard = new Set<string>()
        while (cur && !guard.has(cur.name)) { ids.add(cur.name); guard.add(cur.name); cur = cur.reports_to ? rows.get(cur.reports_to) : undefined }
      }
      return ids
    }
    return open ?? new Set(tree.filter((n) => n.children.length).map((n) => n.name))
  }, [search, open, tree, q.data])
  const toggle = (id: string) => {
    const next = new Set(expanded)
    if (next.has(id)) next.delete(id); else next.add(id)
    setOpen(next)
  }
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const all = q.data?.rows ?? []
  const ids = new Set(all.map((r) => r.name))
  // No manager at all, or a manager who is not an active employee here.
  const noManager = all.filter((r) => !r.reports_to || !ids.has(r.reports_to))
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm text-muted">
        <span>{tree.filter((n) => n.children.length).length} {t('managers at the top')}</span>
        <span>·</span>
        <button className={`rounded-full px-2 py-0.5 ${orphans ? 'bg-amber-100 text-amber-900' : 'hover:bg-surface'}`} aria-pressed={orphans} onClick={() => setOrphans((o) => !o)}>
          {noManager.length} {t('without a reporting manager')}
        </button>
        <span className="flex-1" />
        <a className="inline-flex items-center gap-1 text-brand hover:underline" href={downloadUrl('hr.export_org_chart', { department, file_format: 'xlsx' })}><Download className="size-4" />{t('Export')}</a>
        <button className="text-brand hover:underline" onClick={() => setOpen(new Set((q.data?.rows ?? []).map((r) => r.name)))}>{t('Expand all')}</button>
        <button className="text-brand hover:underline" onClick={() => setOpen(new Set())}>{t('Collapse all')}</button>
      </div>
      {orphans ? (
        <div>
          <p className="mb-2 text-sm text-amber-900">{t('Set "Reports to" on these employees so they appear under their manager.')}</p>
          <ul className="divide-y divide-line">
            {noManager.map((r) => (
              <li key={r.name}>
                <button onClick={() => onOpen(r.name)} className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-start hover:bg-surface">
                  <Avatar name={r.employee_name} image={r.image} size={32} />
                  <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{r.employee_name}</span>
                    <span className="block truncate text-xs text-muted">{[r.designation, r.department].filter(Boolean).join(' · ')}</span></span>
                  <span className="text-xs text-amber-800">{r.reports_to ? t('Manager not active / not in filter') : t('No reporting manager')}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {tree.map((n) => <Branch key={n.name} node={n} depth={0} onOpen={onOpen} open={expanded} toggle={toggle} highlight={search} />)}
        </ul>
      )}
    </div>
  )
}
