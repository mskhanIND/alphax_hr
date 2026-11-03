import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LocateFixed, MapPin, Plus } from 'lucide-react'
import { useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Spinner, Table } from '../components/ui'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'

function Form({ initial, onClose }: { initial: any; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const [f, setF] = useState<any>(initial ?? { radius_m: 150, enabled: 1 })
  const [locErr, setLocErr] = useState('')
  const set = (k: string, v: any) => setF((s: any) => ({ ...s, [k]: v }))
  const m = useMutation({ mutationFn: () => api.saveWorkLocation(f, initial?.name), onSuccess: () => { qc.invalidateQueries({ queryKey: ['work-locations'] }); onClose() } })
  const here = () => navigator.geolocation?.getCurrentPosition(
    (p) => { set('latitude', +p.coords.latitude.toFixed(6)); set('longitude', +p.coords.longitude.toFixed(6)); setLocErr('') },
    () => setLocErr(t('Location is blocked in this browser.')), { enableHighAccuracy: true, timeout: 10000 })
  return (
    <Modal open onClose={onClose} title={initial ? initial.location_name : t('New work location')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button disabled={!f.location_name} loading={m.isPending} onClick={() => m.mutate()}>{t('Save')}</Button></>}>
      <div className="grid gap-3">
        <Field label={t('Location')}><Input value={f.location_name ?? ''} disabled={!!initial} onChange={(e) => set('location_name', e.target.value)} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('Latitude')}><Input inputMode="decimal" value={f.latitude ?? ''} onChange={(e) => set('latitude', e.target.value)} /></Field>
          <Field label={t('Longitude')}><Input inputMode="decimal" value={f.longitude ?? ''} onChange={(e) => set('longitude', e.target.value)} /></Field>
        </div>
        <Button variant="secondary" size="sm" className="self-start" onClick={here}><LocateFixed className="size-4" />{t('Use my current location')}</Button>
        {locErr && <p className="text-xs text-red-600">{locErr}</p>}
        <Field label={t('Radius (metres)')} hint={t('Check-ins within this distance count as at the location.')}><Input type="number" min="20" value={f.radius_m ?? ''} onChange={(e) => set('radius_m', Number(e.target.value))} /></Field>
        <Field label={t('Company')} hint={t('Blank = all companies')}><LinkInput doctype="Company" value={f.company ?? ''} onChange={(v) => set('company', v)} /></Field>
        <Field label={t('Address')}><Input value={f.address ?? ''} onChange={(e) => set('address', e.target.value)} /></Field>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!f.enabled} onChange={(e) => set('enabled', e.target.checked ? 1 : 0)} />{t('Enabled')}</label>
        {m.error && <ErrorBox error={m.error} />}
      </div>
    </Modal>
  )
}

export default function WorkLocations() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['work-locations'], queryFn: api.workLocations })
  const [edit, setEdit] = useState<any>(undefined)
  const del = useMutation({ mutationFn: api.deleteWorkLocation, onSuccess: () => qc.invalidateQueries({ queryKey: ['work-locations'] }) })
  return (
    <div>
      <PageHeader title={t('Work locations')} subtitle={t('Where employees may check in. Choose the rule in HR status & setup → Settings, or per group in Attendance exceptions.')}
        actions={<Button onClick={() => setEdit(null)}><Plus className="size-4" />{t('New work location')}</Button>} />
      <Card>
        {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title={t('No work locations yet')} icon={<MapPin />} /> : (
          <Table head={[t('Location'), t('Coordinates'), t('Radius (metres)'), t('Company'), '']}>
            {q.data.map((l: any) => (
              <tr key={l.name}>
                <td className="py-2 font-medium">{l.location_name} {!l.enabled && <Badge>{t('Disabled')}</Badge>}</td>
                <td className="text-sm"><a className="text-brand underline" target="_blank" rel="noreferrer" href={`https://www.google.com/maps?q=${l.latitude},${l.longitude}`}>{l.latitude}, {l.longitude}</a></td>
                <td>{l.radius_m}</td><td className="text-sm">{l.company || t('All')}</td>
                <td className="whitespace-nowrap"><Button size="sm" variant="secondary" onClick={() => setEdit(l)}>{t('Edit')}</Button>
                  <Button size="sm" variant="secondary" loading={del.isPending && del.variables === l.name} onClick={() => del.mutate(l.name)}>{t('Delete')}</Button></td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
      {edit !== undefined && <Form initial={edit} onClose={() => setEdit(undefined)} />}
    </div>
  )
}
