import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Building2, ChevronDown, ChevronRight, Download, GitFork, ListTree } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { api, downloadUrl } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Avatar, Button, ErrorBox, Spinner } from './ui'

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


export type OrgLayout = 'chart' | 'tree' | 'department'

/** One person as a card in the top-down chart. */
function ChartNode({ node, onOpen, open, toggle, highlight, seen }: {
  node: Node; onOpen: (id: string) => void; open: Set<string>; toggle: (id: string) => void; highlight: string; seen: Set<string>
}) {
  const { t } = useI18n()
  seen.add(node.name)
  const kids = node.children.filter((c) => !seen.has(c.name))
  const expanded = open.has(node.name)
  const hit = highlight && node.employee_name.toLowerCase().includes(highlight.toLowerCase())
  return (
    <li>
      <div className={clsx('relative w-44 rounded-xl border bg-white px-3 pb-2 pt-3 text-center shadow-sm', hit ? 'border-brand ring-2 ring-brand/30' : 'border-line')}
        style={{ borderTop: '4px solid var(--color-brand)' }}>
        <button onClick={() => onOpen(node.name)} className="flex w-full flex-col items-center gap-1">
          <Avatar name={node.employee_name} image={node.image} size={36} />
          <span className="block w-full truncate text-sm font-semibold">{node.employee_name}</span>
          <span className="block w-full truncate text-xs text-muted">{node.designation || '—'}</span>
          {node.department && <span className="block w-full truncate text-[11px] text-muted/80">{node.department}</span>}
        </button>
        {kids.length > 0 && (
          <button onClick={() => toggle(node.name)} className="mt-1 inline-flex items-center gap-1 rounded-full bg-surface px-2 py-0.5 text-[11px] text-muted hover:bg-brand-50"
            aria-label={expanded ? t('Collapse') : t('Expand')}>
            {expanded ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3 flip-rtl" />}{node.size} {t('in team')}
          </button>
        )}
      </div>
      {expanded && kids.length > 0 && (
        <ul>{kids.map((c) => <ChartNode key={c.name} node={c} onOpen={onOpen} open={open} toggle={toggle} highlight={highlight} seen={seen} />)}</ul>
      )}
    </li>
  )
}

function DepartmentView({ rows, onOpen, highlight }: { rows: Person[]; onOpen: (id: string) => void; highlight: string }) {
  const { t } = useI18n()
  const ids = new Map(rows.map((r) => [r.name, r]))
  const level = (r: Person) => { let l = 1, cur = r; const g = new Set<string>(); while (cur.reports_to && ids.has(cur.reports_to) && !g.has(cur.name)) { g.add(cur.name); cur = ids.get(cur.reports_to)!; l++ } return l }
  const team = new Map<string, number>()
  for (const r of rows) if (r.reports_to) team.set(r.reports_to, (team.get(r.reports_to) ?? 0) + 1)
  const groups = new Map<string, Person[]>()
  for (const r of rows) { const k = r.department || t('No department'); groups.set(k, [...(groups.get(k) ?? []), r]) }
  const depts = [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {depts.map(([dept, people]) => {
        const sorted = [...people].sort((a, b) => level(a) - level(b) || (team.get(b.name) ?? 0) - (team.get(a.name) ?? 0) || a.employee_name.localeCompare(b.employee_name))
        return (
          <div key={dept} className="rounded-2xl border border-line">
            <div className="flex items-center justify-between rounded-t-2xl bg-brand-50 px-4 py-2.5">
              <span className="flex min-w-0 items-center gap-2 font-semibold text-brand"><Building2 className="size-4 shrink-0" /><span className="truncate">{dept}</span></span>
              <span className="rounded-full bg-white px-2 py-0.5 text-xs text-muted">{people.length}</span>
            </div>
            <ul className="divide-y divide-line">
              {sorted.map((r) => {
                const mgr = r.reports_to ? ids.get(r.reports_to) : undefined
                const hit = highlight && r.employee_name.toLowerCase().includes(highlight.toLowerCase())
                return (
                  <li key={r.name}>
                    <button onClick={() => onOpen(r.name)} className={clsx('flex w-full items-center gap-3 px-4 py-2 text-start hover:bg-surface', hit && 'bg-brand-50')}>
                      <Avatar name={r.employee_name} image={r.image} size={30} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">{r.employee_name}</span>
                        <span className="block truncate text-xs text-muted">{r.designation || '—'}{mgr ? ` · ${t('Reports to')} ${mgr.employee_name}` : ''}</span>
                      </span>
                      {(team.get(r.name) ?? 0) > 0 && <span className="rounded-full bg-surface px-2 py-0.5 text-xs text-muted">{team.get(r.name)} {t('in team')}</span>}
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        )
      })}
    </div>
  )
}

function OrgExport({ department, layout }: { department?: string; layout: OrgLayout }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as globalThis.Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  const item = (label: string, file_format: string, l: OrgLayout = layout) => (
    <a className="block px-4 py-2 text-sm hover:bg-surface" onClick={() => setOpen(false)}
      href={downloadUrl('hr.export_org_chart', { department, file_format, layout: l })}>{label}</a>
  )
  return (
    <div className="relative" ref={ref}>
      <Button size="sm" variant="secondary" onClick={() => setOpen((o) => !o)}><Download className="size-4" />{t('Export')}</Button>
      {open && (
        <div className="absolute end-0 z-20 mt-1 w-64 overflow-hidden rounded-xl border border-line bg-white py-1 shadow-lg">
          <div className="px-4 pb-1 pt-2 text-xs font-medium uppercase text-muted">PDF</div>
          {item(t('Chart (boxes)'), 'pdf', 'chart')}
          {item(t('Tree (indented list)'), 'pdf', 'tree')}
          {item(t('By department'), 'pdf', 'department')}
          <div className="px-4 pb-1 pt-2 text-xs font-medium uppercase text-muted">Word</div>
          {item(t('Reporting lines (outline)'), 'docx', 'tree')}
          {item(t('By department'), 'docx', 'department')}
          <div className="px-4 pb-1 pt-2 text-xs font-medium uppercase text-muted">{t('Data')}</div>
          {item(t('Excel (.xlsx)'), 'xlsx')}
        </div>
      )}
    </div>
  )
}

const LAYOUTS: [OrgLayout, string, ReactNode][] = [
  ['chart', 'Chart', <GitFork key="c" className="size-4 rotate-180" />],
  ['tree', 'Tree', <ListTree key="t" className="size-4" />],
  ['department', 'By department', <Building2 key="d" className="size-4" />],
]

export function OrgChart({ department, search, onOpen }: { department?: string; search: string; onOpen: (id: string) => void }) {
  const { t } = useI18n()
  const q = useQuery<{ rows: Person[] }>({ queryKey: ['orgChart', department], queryFn: () => api.orgChart({ department }) })
  const tree = useMemo(() => buildTree(q.data?.rows ?? []), [q.data])
  const [open, setOpen] = useState<Set<string> | null>(null)
  const [orphans, setOrphans] = useState(false)
  const [layout, setLayout] = useState<OrgLayout>(() => (localStorage.getItem('alphax-org-layout') as OrgLayout) || 'chart')
  const pick = (l: OrgLayout) => { setLayout(l); try { localStorage.setItem('alphax-org-layout', l) } catch { /* private mode */ } }
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
        <div className="flex rounded-xl border border-line p-0.5" role="tablist" aria-label={t('Chart type')}>
          {LAYOUTS.map(([l, label, icon]) => (
            <button key={l} role="tab" aria-selected={layout === l} onClick={() => pick(l)}
              className={clsx('flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs', layout === l ? 'bg-brand text-white' : 'text-muted hover:bg-surface')}>{icon}{t(label)}</button>
          ))}
        </div>
        {layout !== 'department' && <>
          <button className="text-brand hover:underline" onClick={() => setOpen(new Set((q.data?.rows ?? []).map((r) => r.name)))}>{t('Expand all')}</button>
          <button className="text-brand hover:underline" onClick={() => setOpen(new Set())}>{t('Collapse all')}</button>
        </>}
        <OrgExport department={department} layout={layout} />
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
      ) : layout === 'department' ? <DepartmentView rows={all} onOpen={onOpen} highlight={search} />
      : layout === 'chart' ? (
        <div className="flex flex-col gap-8">
          {(() => {
            const seen = new Set<string>()
            const heads = tree.filter((n) => n.children.length)
            const loose = tree.filter((n) => !n.children.length)
            return <>
              {heads.map((n) => (
                <div key={n.name} className="oc-tree overflow-x-auto pb-2"><ul className="mx-auto w-max min-w-full">
                  <ChartNode node={n} onOpen={onOpen} open={expanded} toggle={toggle} highlight={search} seen={seen} />
                </ul></div>
              ))}
              {loose.length > 0 && (
                <div>
                  <div className="mb-2 text-sm font-medium text-amber-800">{t('Without a reporting manager')} ({loose.length})</div>
                  <div className="flex flex-wrap gap-2">
                    {loose.map((n) => (
                      <button key={n.name} onClick={() => onOpen(n.name)} className="flex w-56 items-center gap-2 rounded-xl border border-line bg-white px-3 py-2 text-start hover:bg-surface">
                        <Avatar name={n.employee_name} image={n.image} size={28} />
                        <span className="min-w-0"><span className="block truncate text-sm font-medium">{n.employee_name}</span>
                          <span className="block truncate text-xs text-muted">{n.designation || n.department || '—'}</span></span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </>
          })()}
        </div>
      ) : (
        <ul className="flex flex-col gap-0.5">
          {tree.map((n) => <Branch key={n.name} node={n} depth={0} onOpen={onOpen} open={expanded} toggle={toggle} highlight={search} />)}
        </ul>
      )}
    </div>
  )
}
