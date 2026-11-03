import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Star } from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { fmtNumber } from '../lib/format'
import { useI18n } from '../lib/i18n'
import { Badge, Button, ErrorBox, Field, Modal, Spinner, Textarea } from './ui'

export function Stars({ value, onChange, label }: { value: number; onChange?: (v: number) => void; label: string }) {
  return (
    <div className="flex items-center gap-0.5" role={onChange ? 'radiogroup' : undefined} aria-label={label}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" disabled={!onChange} aria-label={`${label}: ${n}`} onClick={() => onChange?.(n === value ? 0 : n)}
          className={onChange ? 'cursor-pointer' : 'cursor-default'}>
          <Star className={`size-5 ${n <= Math.round(value) ? 'fill-amber-400 text-amber-400' : 'text-line'}`} />
        </button>
      ))}
    </div>
  )
}

const strip = (html?: string | null) => (html ?? '').replace(/<br\s*\/?>/g, '\n').replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&#x27;|&#39;/g, "'").replace(/&quot;/g, '"')

/** One appraisal: self rating (employee), goal scores and feedback (reporting manager / HR), finalise (HR). */
export function AppraisalForm({ name, onClose }: { name: string | null; onClose: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['appraisal', name], queryFn: () => api.appraisal(name!), enabled: !!name })
  const a = q.data
  const [self, setSelf] = useState<Record<string, number>>({})
  const [reflections, setReflections] = useState('')
  const [goals, setGoals] = useState<Record<string, number>>({})
  const [rates, setRates] = useState<Record<string, number>>({})
  const [feedback, setFeedback] = useState('')
  useEffect(() => {
    if (!a) return
    setSelf(Object.fromEntries(a.self_ratings.map((r: any) => [r.criteria, r.stars])))
    setReflections(strip(a.reflections))
    setGoals(Object.fromEntries(a.goals.map((g: any) => [g.kra, g.score])))
    setRates(a.manager_feedback?.ratings ?? {})
    setFeedback(strip(a.manager_feedback?.feedback))
  }, [a])
  const refresh = (d: any) => { qc.setQueryData(['appraisal', name], d); for (const k of ['my-appraisals', 'appraisal-cycle', 'team-appraisals']) qc.invalidateQueries({ queryKey: [k] }) }
  const saveSelf = useMutation({ mutationFn: () => api.saveSelfAppraisal(name!, self, reflections), onSuccess: refresh })
  const review = useMutation({ mutationFn: () => api.saveAppraisalReview(name!, goals, rates, feedback), onSuccess: refresh })
  const fin = useMutation({ mutationFn: () => api.finaliseAppraisal(name!), onSuccess: refresh })
  const err = saveSelf.error || review.error || fin.error
  return (
    <Modal open={!!name} onClose={onClose} wide title={a ? `${a.employee_name} · ${a.cycle}` : t('Appraisal')}
      footer={a && <>
        <Button variant="secondary" onClick={onClose}>{t('Close')}</Button>
        {a.can_self && <Button loading={saveSelf.isPending} onClick={() => saveSelf.mutate()}>{t('Save my self-appraisal')}</Button>}
        {a.can_review && <Button loading={review.isPending} onClick={() => review.mutate()}>{t('Save review')}</Button>}
        {a.can_finalise && <Button variant="secondary" loading={fin.isPending} onClick={() => fin.mutate()}>{t('Finalise')}</Button>}
      </>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : a && (
        <div className="flex flex-col gap-5" data-testid="appraisal-form">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {[['Goals', a.scores.goals], ['Self', a.scores.self], ['Manager', a.scores.feedback], ['Final score', a.scores.final]].map(([l, v]) => (
              <div key={l as string} className="rounded-xl bg-surface p-3 text-center">
                <div className="text-xs text-muted">{t(l as string)}</div>
                <div className="text-lg font-semibold">{fmtNumber(v as number, lang, 2)}<span className="text-xs text-muted"> / 5</span></div>
              </div>
            ))}
          </div>
          {a.docstatus === 1 && <Badge tone="green">{t('Final')}</Badge>}
          <section>
            <h3 className="mb-2 text-sm font-semibold">{t('Goals (scored by the manager)')}</h3>
            <ul className="divide-y divide-line rounded-xl border border-line">
              {a.goals.map((g: any) => (
                <li key={g.kra} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                  <span>{g.kra} <span className="text-xs text-muted">· {g.weight}%</span></span>
                  <Stars label={g.kra} value={goals[g.kra] ?? 0} onChange={a.can_review ? (v) => setGoals({ ...goals, [g.kra]: v }) : undefined} />
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3 className="mb-2 text-sm font-semibold">{t('Competencies')}</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted"><tr><th className="pb-1 text-start">{t('Criteria')}</th><th className="pb-1 text-start">{t('Self')}</th>
                  {(a.can_review || a.manager_feedback) && <th className="pb-1 text-start">{t('Manager')}</th>}</tr></thead>
                <tbody className="divide-y divide-line">
                  {a.self_ratings.map((r: any) => (
                    <tr key={r.criteria}>
                      <td className="py-2 pe-3">{r.criteria} <span className="text-xs text-muted">· {r.weight}%</span></td>
                      <td className="py-2 pe-3"><Stars label={`${t('Self')} ${r.criteria}`} value={self[r.criteria] ?? 0} onChange={a.can_self ? (v) => setSelf({ ...self, [r.criteria]: v }) : undefined} /></td>
                      {(a.can_review || a.manager_feedback) && <td className="py-2"><Stars label={`${t('Manager')} ${r.criteria}`} value={rates[r.criteria] ?? 0}
                        onChange={a.can_review ? (v) => setRates({ ...rates, [r.criteria]: v }) : undefined} /></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <Field label={t('Self reflection')}>
            <Textarea rows={3} value={reflections} disabled={!a.can_self} onChange={(e) => setReflections(e.target.value)} />
          </Field>
          {(a.can_review || a.manager_feedback) && (
            <Field label={a.manager_feedback?.reviewer_name ? `${t('Manager feedback')} · ${a.manager_feedback.reviewer_name}` : t('Manager feedback')}>
              <Textarea rows={3} value={feedback} disabled={!a.can_review} onChange={(e) => setFeedback(e.target.value)} />
            </Field>
          )}
          {err && <ErrorBox error={err} />}
        </div>
      )}
    </Modal>
  )
}
