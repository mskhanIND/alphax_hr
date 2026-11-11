import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Check, ExternalLink, GitMerge, Pencil, Plus, Trash2, Wand2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Stat, Tabs, Textarea } from '../components/ui'
import { api } from '../lib/api'
import { fmtDate, fmtMoney } from '../lib/format'
import { useI18n } from '../lib/i18n'

const STATUS_TONE: Record<string, string> = { 'No one in these professions': 'gray', Compliant: 'green', 'Below target': 'red', Violation: 'red', 'Not applicable': 'gray', 'Starts later': 'blue', 'No rule yet': 'gray' }

function ProfessionSelect({ value, professions, onChange }: { value: string; professions: any[]; onChange: (v: string) => void }) {
  const { t } = useI18n()
  const groups: Record<string, any[]> = {}
  for (const p of professions) (groups[p.localization_group || t('Other')] ??= []).push(p)
  return (
    <Select value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">—</option>
      {Object.entries(groups).map(([g, list]) => (
        <optgroup key={g} label={t(g)}>{list.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)}</optgroup>
      ))}
    </Select>
  )
}

function DesignationsTab({ d, onData, filter, setFilter }: { d: any; onData: (x: any) => void; filter: string; setFilter: (f: any) => void }) {
  const { t } = useI18n()
  const [sel, setSel] = useState<Set<string>>(new Set())
  const [merge, setMerge] = useState<string>('')
  const [mapTo, setMapTo] = useState<string>('')
  const ok = { onSuccess: (x: any) => { onData(x); setSel(new Set()); setMerge(''); setMapTo('') } }
  const map = useMutation({ mutationFn: (m: Record<string, string>) => api.mapDesignations(m), ...ok })
  const doMerge = useMutation({ mutationFn: () => api.mergeDesignations([...sel], merge), ...ok })
  const rows = d.designations.filter((r: any) => filter === 'all' || (filter === 'unmapped' ? !r.profession : filter === 'suggested' ? !r.profession && r.suggestion : filter === 'mapped' ? !!r.profession : r.violation))
  const suggested = d.designations.filter((r: any) => !r.profession && r.suggestion)
  const toggle = (n: string) => { const s = new Set(sel); if (s.has(n)) s.delete(n); else s.add(n); setSel(s) }
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Tabs value={filter} onChange={(v) => setFilter(v as any)} tabs={[{ value: 'all', label: t('All') },
          { value: 'unmapped', label: t('Not standardized'), badge: d.counts.total - d.counts.mapped },
          { value: 'violations', label: t('Saudis-only issues'), badge: d.counts.violations || undefined }]} />
        <span className="flex-1" />
        {d.can_edit && suggested.length > 0 && (
          <Button variant="secondary" loading={map.isPending} onClick={() => map.mutate(Object.fromEntries(suggested.map((r: any) => [r.name, r.suggestion])))}>
            <Wand2 className="size-4" />{t('Accept all suggestions')} ({suggested.length})</Button>
        )}
      </div>
      {d.can_edit && sel.size > 0 && (
        <div className="flex flex-wrap items-end gap-3 rounded-xl bg-brand-50 p-3">
          <span className="pb-2 text-sm font-medium">{sel.size} {t('selected')}</span>
          <Field label={t('Map to profession')}><ProfessionSelect value={mapTo} professions={d.professions} onChange={setMapTo} /></Field>
          <Button disabled={!mapTo} loading={map.isPending} onClick={() => map.mutate(Object.fromEntries([...sel].map((n) => [n, mapTo])))}>{t('Map')}</Button>
          <Field label={t('Merge into')}>
            <Select value={merge} onChange={(e) => setMerge(e.target.value)}><option value="">—</option>
              {d.designations.map((r: any) => <option key={r.name} value={r.name}>{r.name}</option>)}</Select>
          </Field>
          <Button variant="danger" disabled={!merge} loading={doMerge.isPending}
            onClick={() => { if (window.confirm(t('Merge the selected designations into {0}? Every employee and record moves to it.').replace('{0}', merge))) doMerge.mutate() }}>
            <GitMerge className="size-4" />{t('Merge')}</Button>
        </div>
      )}
      {(map.error || doMerge.error) && <ErrorBox error={map.error || doMerge.error} />}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs text-muted"><tr>
            {d.can_edit && <th className="w-8 pb-2" />}
            <th className="pb-2 text-start">{t('Designation')}</th><th className="pb-2 text-start">{t('Employees')}</th>
            <th className="pb-2 text-start">{t('Standard profession')}</th><th className="pb-2 text-start">{t('Saudization group')}</th>
          </tr></thead>
          <tbody className="divide-y divide-line">
            {rows.map((r: any) => (
              <tr key={r.name} className={r.violation ? 'bg-red-50/60' : undefined}>
                {d.can_edit && <td className="py-2"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={sel.has(r.name)} onChange={() => toggle(r.name)} aria-label={r.name} /></td>}
                <td className="py-2 pe-3 font-medium">{r.name}</td>
                <td className="py-2 pe-3 tabular-nums">{r.employees} <span className="text-xs text-muted">({r.saudis} {t('Saudi')} · {r.non_saudis} {t('non-Saudi')})</span></td>
                <td className="py-2 pe-3">
                  {d.can_edit
                    ? <div className="flex flex-wrap items-center gap-2">
                        <div className="min-w-48"><ProfessionSelect value={r.profession ?? ''} professions={d.professions} onChange={(v) => map.mutate({ [r.name]: v })} /></div>
                        {!r.profession && r.suggestion && <button className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-xs text-brand hover:bg-brand-100"
                          onClick={() => map.mutate({ [r.name]: r.suggestion })} title={t('Accept')}><Check className="size-3" />{r.suggestion} · {Math.round(r.score * 100)}%</button>}
                      </div>
                    : r.profession ?? '—'}
                </td>
                <td className="py-2">
                  {r.group ? <Badge tone={r.saudis_only ? 'red' : 'blue'}>{t(r.group)}{r.saudis_only ? ` · ${t('Saudis only')}` : ''}</Badge> : <span className="text-muted">—</span>}
                  {r.violation && <div className="mt-1 flex items-center gap-1 text-xs text-red-700"><AlertTriangle className="size-3" />{t('{0} non-Saudis hold a Saudis-only profession').replace('{0}', String(r.non_saudis))}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <Empty title={t('Nothing here')} />}
      </div>
    </div>
  )
}

function ReportTab({ d }: { d: any }) {
  const { t, lang } = useI18n()
  const groups = d.report.filter((g: any) => g.workers > 0 || g.rule)
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {groups.map((g: any) => {
        const req = g.rule ? Number(g.rule.percent) : 0
        return (
          <Card key={g.group}>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{t(g.group)}</span>
              <Badge tone={STATUS_TONE[g.status]}>{t(g.status)}</Badge>
              {g.rule && <span className="text-xs text-muted">{g.rule.kind === 'Saudis only' ? t('Saudis only') : `${req}%`} · {t('since')} {fmtDate(g.rule.effective_from, lang)}
                {Number(g.rule.min_workers) ? ` · ${t('from {0} workers').replace('{0}', String(g.rule.min_workers))}` : ''}
                {Number(g.rule.min_wage) ? ` · ${t('counts from {0}').replace('{0}', fmtMoney(g.rule.min_wage, lang))}` : ''}</span>}
            </div>
            <div className="mt-3 flex items-center gap-3">
              <div className="relative h-3 flex-1 rounded-full bg-surface">
                <div className={`h-3 rounded-full ${g.status === 'Compliant' ? 'bg-brand' : g.status === 'Below target' || g.status === 'Violation' ? 'bg-red-500' : 'bg-gray-300'}`} style={{ width: `${Math.min(100, g.percent)}%` }} />
                {req > 0 && req < 100 && <div className="absolute -top-1 h-5 w-0.5 bg-ink" style={{ left: `${req}%` }} title={`${t('Required')} ${req}%`} />}
              </div>
              <span className="w-16 text-end text-sm font-semibold tabular-nums">{g.percent}%</span>
            </div>
            <div className="mt-2 text-sm text-muted">
              {t('{0} workers, {1} Saudis counted').replace('{0}', String(g.workers)).replace('{1}', String(g.saudis_counted))}
              {g.saudis > g.saudis_counted && ` · ${t('{0} Saudis below the wage').replace('{0}', String(g.saudis - g.saudis_counted))}`}
            </div>
            {g.needed > 0 && <p className="mt-1 text-sm font-medium text-red-700">{t('Hire or move {0} more Saudis to reach {1}%.').replace('{0}', String(g.needed)).replace('{1}', String(req))}</p>}
            {g.next && <p className="mt-1 text-sm">{t('Next')}: <b>{g.next.kind === 'Saudis only' ? t('Saudis only') : `${g.next.percent}%`}</b> {t('from')} {fmtDate(g.next.effective_from, lang)}
              {g.needed_next ? ` · ${t('{0} more Saudis needed').replace('{0}', String(g.needed_next))}` : ''}</p>}
            {g.violations.length > 0 && (
              <ul className="mt-2 divide-y divide-line rounded-lg bg-red-50 px-2 text-sm text-red-800">
                {g.violations.map((v: any) => <li key={v.name} className="flex justify-between py-1"><span>{v.employee_name}</span><span className="text-xs">{v.designation}</span></li>)}
              </ul>
            )}
          </Card>
        )
      })}
      {groups.length === 0 && <Card><Empty title={t('Map designations to professions to see Saudization by profession.')} /></Card>}
    </div>
  )
}

function RuleForm({ rule, groups, onClose, onData }: { rule: any; groups: string[]; onClose: () => void; onData: (x: any) => void }) {
  const { t } = useI18n()
  const [v, setV] = useState<any>(rule ?? { kind: 'Minimum Saudi %', enabled: 1, min_workers: 0, min_wage: 0 })
  const set = (k: string, x: any) => setV((s: any) => ({ ...s, [k]: x }))
  const save = useMutation({ mutationFn: () => api.saveLocRule(v, rule?.name), onSuccess: (x) => { onData(x); onClose() } })
  return (
    <Modal open onClose={onClose} title={rule ? rule.rule_name : t('New Saudization rule')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={save.isPending} onClick={() => save.mutate()}>{t('Save')}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('Rule')}><Input value={v.rule_name ?? ''} onChange={(e) => set('rule_name', e.target.value)} disabled={!!rule} /></Field>
        <Field label={t('Saudization group')}><Input list="loc-groups" value={v.localization_group ?? ''} onChange={(e) => set('localization_group', e.target.value)} /></Field>
        <datalist id="loc-groups">{groups.map((g) => <option key={g} value={g} />)}</datalist>
        <Field label={t('Kind')}><Select value={v.kind} onChange={(e) => set('kind', e.target.value)}><option value="Minimum Saudi %">{t('Minimum Saudi %')}</option><option value="Saudis only">{t('Saudis only')}</option></Select></Field>
        {v.kind !== 'Saudis only' && <Field label={t('Minimum Saudi %')}><Input type="number" value={v.percent ?? ''} onChange={(e) => set('percent', e.target.value)} /></Field>}
        <Field label={t('In force from')}><Input type="date" value={v.effective_from ?? ''} onChange={(e) => set('effective_from', e.target.value)} /></Field>
        <Field label={t('Applies from workers in the group')}><Input type="number" value={v.min_workers ?? 0} onChange={(e) => set('min_workers', e.target.value)} /></Field>
        <Field label={t('Saudi counts from wage')}><Input type="number" value={v.min_wage ?? 0} onChange={(e) => set('min_wage', e.target.value)} /></Field>
        <Field label={t('Last checked')}><Input type="date" value={v.last_reviewed ?? ''} onChange={(e) => set('last_reviewed', e.target.value)} /></Field>
        <Field label={t('Source (link)')}><Input value={v.source ?? ''} onChange={(e) => set('source', e.target.value)} /></Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!Number(v.enabled)} onChange={(e) => set('enabled', e.target.checked ? 1 : 0)} />{t('Enabled')}</label>
        <div className="sm:col-span-2"><Field label={t('Notes')}><Textarea rows={2} value={v.notes ?? ''} onChange={(e) => set('notes', e.target.value)} /></Field></div>
      </div>
      {save.error && <div className="mt-3"><ErrorBox error={save.error} /></div>}
    </Modal>
  )
}

function ProfessionForm({ prof, groups, onClose, onData }: { prof: any; groups: string[]; onClose: () => void; onData: (x: any) => void }) {
  const { t } = useI18n()
  const [v, setV] = useState<any>(prof ?? {})
  const set = (k: string, x: any) => setV((s: any) => ({ ...s, [k]: x }))
  const save = useMutation({ mutationFn: () => api.saveProfession(v, prof?.name), onSuccess: (x) => { onData(x); onClose() } })
  return (
    <Modal open onClose={onClose} title={prof ? prof.name : t('New profession')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={save.isPending} onClick={() => save.mutate()}>{t('Save')}</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t('Profession')}><Input value={v.profession_name ?? ''} onChange={(e) => set('profession_name', e.target.value)} disabled={!!prof} /></Field>
        <Field label={t('Profession (Arabic)')}><Input dir="rtl" value={v.title_ar ?? ''} onChange={(e) => set('title_ar', e.target.value)} /></Field>
        <Field label={t('Occupation code')}><Input value={v.code ?? ''} onChange={(e) => set('code', e.target.value)} /></Field>
        <Field label={t('Saudization group')}><Input list="loc-groups2" value={v.localization_group ?? ''} onChange={(e) => set('localization_group', e.target.value)} /></Field>
        <datalist id="loc-groups2">{groups.map((g) => <option key={g} value={g} />)}</datalist>
        <div className="sm:col-span-2"><Field label={t('Other titles')} hint={t('One per line: titles used for this profession, for matching designations.')}>
          <Textarea rows={3} value={v.aliases ?? ''} onChange={(e) => set('aliases', e.target.value)} /></Field></div>
      </div>
      {save.error && <div className="mt-3"><ErrorBox error={save.error} /></div>}
    </Modal>
  )
}

function RulesTab({ d, onData }: { d: any; onData: (x: any) => void }) {
  const { t, lang } = useI18n()
  const [rule, setRule] = useState<any | undefined>(undefined)
  const [prof, setProf] = useState<any | undefined>(undefined)
  const del = useMutation({ mutationFn: api.deleteProfession, onSuccess: onData })
  const create = useMutation({ mutationFn: api.designationFromProfession, onSuccess: onData })
  const existing = useMemo(() => new Set(d.designations.map((x: any) => x.name)), [d.designations])
  return (
    <div className="flex flex-col gap-5">
      <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{t('Saudization decisions change several times a year. These rules were checked on the date shown — confirm them on the HRSD site and keep them up to date.')}
        {' '}<a className="inline-flex items-center gap-1 font-medium underline" href="https://www.hrsd.gov.sa/en/localization-decisions" target="_blank" rel="noreferrer">HRSD<ExternalLink className="size-3" /></a></p>
      <Card title={t('Saudization rules')} action={d.can_edit ? <Button size="sm" onClick={() => setRule(null)}><Plus className="size-4" />{t('Add rule')}</Button> : undefined}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted"><tr>
              <th className="pb-2 text-start">{t('Saudization group')}</th><th className="pb-2 text-start">{t('Rule')}</th><th className="pb-2 text-start">{t('In force from')}</th>
              <th className="pb-2 text-start">{t('Applies from')}</th><th className="pb-2 text-start">{t('Saudi counts from wage')}</th><th className="pb-2 text-start">{t('Last checked')}</th><th />
            </tr></thead>
            <tbody className="divide-y divide-line">
              {d.rules.map((r: any) => (
                <tr key={r.name} className={Number(r.enabled) ? undefined : 'opacity-50'}>
                  <td className="py-2 pe-3">{t(r.localization_group)}</td>
                  <td className="py-2 pe-3"><Badge tone={r.kind === 'Saudis only' ? 'red' : 'blue'}>{r.kind === 'Saudis only' ? t('Saudis only') : `${r.percent}%`}</Badge>
                    {r.notes && <div className="mt-0.5 max-w-md text-xs text-muted">{r.notes}</div>}</td>
                  <td className="py-2 pe-3">{fmtDate(r.effective_from, lang)}</td>
                  <td className="py-2 pe-3">{Number(r.min_workers) ? t('{0} workers').replace('{0}', String(r.min_workers)) : '—'}</td>
                  <td className="py-2 pe-3">{Number(r.min_wage) ? fmtMoney(r.min_wage, lang) : '—'}</td>
                  <td className="py-2 pe-3">{r.last_reviewed ? fmtDate(r.last_reviewed, lang) : '—'}</td>
                  <td className="py-2 text-end">{d.can_edit && <Button size="sm" variant="ghost" onClick={() => setRule(r)} aria-label={t('Edit')}><Pencil className="size-4" /></Button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title={t('Standard professions')} subtitle={t('Your designations map to these. Names follow the Saudi occupational classification as used on Qiwa.')}
        action={d.can_edit ? <Button size="sm" onClick={() => setProf(null)}><Plus className="size-4" />{t('Add profession')}</Button> : undefined}>
        <ul className="divide-y divide-line text-sm">
          {d.professions.map((p: any) => (
            <li key={p.name} className="flex flex-wrap items-center gap-2 py-2">
              <span className="font-medium">{p.name}</span>{p.title_ar && <span dir="rtl" className="text-muted">{p.title_ar}</span>}
              {p.localization_group && <Badge>{t(p.localization_group)}</Badge>}
              <span className="flex-1" />
              {d.can_edit && !existing.has(p.name) && <Button size="sm" variant="ghost" loading={create.isPending && create.variables === p.name} onClick={() => create.mutate(p.name)}>{t('Create designation')}</Button>}
              {d.can_edit && <Button size="sm" variant="ghost" onClick={() => setProf(p)} aria-label={t('Edit')}><Pencil className="size-4" /></Button>}
              {d.can_edit && <Button size="sm" variant="ghost" onClick={() => del.mutate(p.name)} aria-label={t('Delete')}><Trash2 className="size-4" /></Button>}
            </li>
          ))}
        </ul>
        {(del.error || create.error) && <ErrorBox error={del.error || create.error} />}
      </Card>
      {rule !== undefined && <RuleForm rule={rule} groups={d.groups} onClose={() => setRule(undefined)} onData={onData} />}
      {prof !== undefined && <ProfessionForm prof={prof} groups={d.groups} onClose={() => setProf(undefined)} onData={onData} />}
    </div>
  )
}

export default function Designations() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['designations'], queryFn: api.designationsOverview })
  const [tab, setTab] = useState('designations')
  const onData = (x: any) => qc.setQueryData(['designations'], x)
  const control = useMutation({ mutationFn: api.saveSaudiControl, onSuccess: onData })
  const [dfilter, setDfilter] = useState<string>('all')
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  const show = (f: string) => { setTab('designations'); setDfilter((x) => (x === f && f !== 'all' ? 'all' : f)) }
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Designations & Saudization')}
        subtitle={t('One standard profession behind every designation, so Saudization rules by profession can be checked and enforced.')} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t('Designations')} value={d.counts.total} onClick={() => show('all')} active={tab === 'designations' && dfilter === 'all'} />
        <Stat label={t('Standardized')} value={`${d.counts.mapped} / ${d.counts.total}`} onClick={() => show('mapped')} active={tab === 'designations' && dfilter === 'mapped'} />
        <Stat label={t('Suggestions ready')} value={d.counts.suggested} tone="blue" onClick={() => show('suggested')} active={tab === 'designations' && dfilter === 'suggested'} />
        <Stat label={t('Saudis-only issues')} value={d.counts.violations} tone={d.counts.violations ? 'red' : 'brand'} onClick={() => show('violations')} active={tab === 'designations' && dfilter === 'violations'} />
      </div>
      {d.can_edit && (
        <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-white p-3 text-sm">
          <span className="font-medium">{t('When a non-Saudi is given a Saudis-only profession')}:</span>
          <Select value={d.control} onChange={(e) => control.mutate(e.target.value)} className="w-auto">
            <option value="Block">{t('Block the save')}</option><option value="Warn">{t('Warn only')}</option><option value="Off">{t('Allow')}</option>
          </Select>
          <span className="text-xs text-muted">{t('Employees already in such a designation are listed here and keep saving; tick "Counts as Saudi (Nitaqat)" for mothers of Saudis and children of Saudi women.')}</span>
        </div>
      )}
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'designations', label: t('Designations') }, { value: 'report', label: t('Saudization by profession') },
        { value: 'rules', label: t('Rules & professions') }]} />
      {tab === 'designations' && <DesignationsTab d={d} onData={onData} filter={dfilter} setFilter={setDfilter} />}
      {tab === 'report' && <ReportTab d={d} />}
      {tab === 'rules' && <RulesTab d={d} onData={onData} />}
    </div>
  )
}
