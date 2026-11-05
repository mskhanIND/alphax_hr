import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Lightbulb } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api, uploadFile, type RequestField, type RequestType } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Button, ErrorBox, Field, Input, Modal, Select, Spinner, Textarea } from './ui'

export function fieldLabel(f: RequestField, lang: string) {
  return lang === 'ar' && f.label_ar ? f.label_ar : f.label
}
export function typeTitle(rt: { title: string; title_ar?: string } | undefined, lang: string, fallback = '') {
  if (!rt) return fallback
  return lang === 'ar' && rt.title_ar ? rt.title_ar : rt.title
}

function Input1({ f, value, onChange }: { f: RequestField; value: any; onChange: (v: any) => void }) {
  if (f.type === 'Select') return (
    <Select value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
      <option value="">—</option>
      {(f.options ?? []).map((o) => <option key={o} value={o}>{f.option_labels?.[o] ?? o}</option>)}
    </Select>
  )
  if (f.type === 'Text') return <Textarea value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
  if (f.type === 'Check') return <input type="checkbox" className="size-5" checked={!!value} onChange={(e) => onChange(e.target.checked ? 1 : 0)} />
  const type = f.type === 'Date' ? 'date' : f.type === 'Time' ? 'time' : f.type === 'Int' || f.type === 'Currency' ? 'number' : 'text'
  return <Input type={type} value={value ?? ''} onChange={(e) => onChange(e.target.value)} />
}

/** Help-centre answers that match what the employee is asking, shown before the request is sent. */
function HelpSuggestions({ text, onSolved }: { text: string; onSolved: () => void }) {
  const { t, lang } = useI18n()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  useEffect(() => { const h = setTimeout(() => setQuery(text.trim()), 450); return () => clearTimeout(h) }, [text])
  const q = useQuery({ queryKey: ['help-suggest', query], queryFn: () => api.helpSuggest(query), enabled: query.length >= 4, staleTime: 60_000 })
  const art = useQuery({ queryKey: ['help-article', open], queryFn: () => api.helpArticle(open!), enabled: !!open })
  if (!q.data?.length) return null
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3 text-sm">
      <div className="mb-2 flex items-center gap-2 font-medium text-amber-900"><Lightbulb className="size-4" />{t('Before you send: these answers may help')}</div>
      <ul className="flex flex-col gap-1">
        {q.data.map((a: any) => (
          <li key={a.name}>
            <button type="button" className="text-start text-brand hover:underline" onClick={() => setOpen(open === a.name ? null : a.name)}>
              {lang === 'ar' && a.title_ar ? a.title_ar : a.title}
            </button>
            {open === a.name && (
              <div className="mt-1 rounded-lg bg-white p-3 text-sm leading-relaxed">
                {art.isLoading ? <Spinner /> : (
                  <>
                    <div className="max-h-48 overflow-auto whitespace-pre-line">{(lang === 'ar' && art.data?.body_ar ? art.data.body_ar : art.data?.body ?? '').replace(/<[^>]+>/g, '')}</div>
                    <Button size="sm" variant="secondary" className="mt-2" onClick={() => { api.helpFeedback(a.name, 1).catch(() => undefined); onSolved() }}>{t('This answered my question')}</Button>
                  </>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

/** New request: pick a type, fill the type's own fields, optionally attach a document. */
export function RequestForm({ open, onClose, employee, initialType, category }: { open: boolean; onClose: () => void; employee?: string; initialType?: string; category?: string }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const types = useQuery({ queryKey: ['request-types'], queryFn: () => api.requestTypes(), enabled: open })
  const [type, setType] = useState('')
  const [values, setValues] = useState<Record<string, any>>({})
  const [reason, setReason] = useState('')
  const [file, setFile] = useState<File | null>(null)
  useEffect(() => { if (open && initialType) { setType(initialType); setValues({}) } }, [open, initialType])
  const rt: RequestType | undefined = types.data?.find((x) => x.name === type)
  const reset = () => { setType(''); setValues({}); setReason(''); setFile(null) }
  const m = useMutation({
    mutationFn: async () => {
      const r = await api.createRequest(type, values, reason || undefined, employee)
      if (file) await uploadFile('AlphaX Request', r.name, file)
      return r
    },
    onSuccess: () => {
      reset(); onClose()
      for (const k of ['my-requests', 'requests', 'myRequests']) qc.invalidateQueries({ queryKey: [k] })
    },
  })
  const missing = rt ? rt.fields.filter((f) => f.reqd && (values[f.fieldname] === undefined || values[f.fieldname] === '')) : []
  const groups: Record<string, RequestType[]> = {}
  for (const x of types.data ?? []) if (!x.special && (!category || x.category === category)) (groups[x.category] ??= []).push(x)
  return (
    <Modal open={open} onClose={onClose} title={t('New request')}
      footer={<>
        <Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        <Button disabled={!rt || !!rt.unavailable || missing.length > 0 || (!!rt?.requires_attachment && !file)} loading={m.isPending} onClick={() => m.mutate()}>{t('Submit request')}</Button>
      </>}>
      {types.isLoading ? <Spinner /> : types.error ? <ErrorBox error={types.error} /> : (
        <div className="grid gap-4">
          <Field label={t('Request type')}>
            <Select value={type} onChange={(e) => { setType(e.target.value); setValues({}) }}>
              <option value="">—</option>
              {Object.entries(groups).map(([cat, list]) => (
                <optgroup key={cat} label={t(cat)}>
                  {list.map((x) => <option key={x.name} value={x.name} disabled={!!x.unavailable}>{typeTitle(x, lang)}{x.unavailable ? ` — ${x.unavailable}` : ''}</option>)}
                </optgroup>
              ))}
            </Select>
          </Field>
          {rt?.description && <p className="text-sm text-muted">{rt.description}</p>}
          {rt?.unavailable && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{rt.unavailable}</p>}
          {rt && (
            <p className="text-xs text-muted">
              {[rt.needs_manager ? t('Manager approval') : null, rt.needs_hr ? t('HR approval') : null, rt.needs_management ? t('Management approval') : null,
                rt.output === 'Letter' ? t('Letter issued as PDF') : null, `${t('Target')}: ${rt.sla_days} ${t('days')}`].filter(Boolean).join(' · ')}
            </p>
          )}
          {rt?.fields.map((f) => (
            <Field key={f.fieldname} label={fieldLabel(f, lang) + (f.reqd ? ' *' : '')}>
              <Input1 f={f} value={values[f.fieldname]} onChange={(v) => setValues((s) => ({ ...s, [f.fieldname]: v }))} />
            </Field>
          ))}
          {rt && <Field label={rt.category === 'Help' ? t('Your question') : t('Reason / notes')}><Textarea value={reason} onChange={(e) => setReason(e.target.value)} /></Field>}
          {rt && (
            <Field label={t('Supporting document') + (rt.requires_attachment ? ' *' : '')}>
              <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
            </Field>
          )}
          {rt && !rt.special && !employee && (
            <HelpSuggestions text={[typeTitle(rt, lang), ...rt.fields.filter((f) => f.type === 'Data' || f.type === 'Text' || f.type === 'Select').map((f) => values[f.fieldname] ?? ''), reason].join(' ')}
              onSolved={() => { reset(); onClose() }} />
          )}
          {m.error && <ErrorBox error={m.error} />}
        </div>
      )}
    </Modal>
  )
}
