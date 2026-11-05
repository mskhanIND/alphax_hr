import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Cpu, Pencil, Plus, RefreshCw, Trash2, Upload } from 'lucide-react'
import { useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Table, Tabs, Textarea } from '../components/ui'
import { api, uploadFile } from '../lib/api'
import { fmtDateTime } from '../lib/format'
import { useI18n } from '../lib/i18n'

const PUSH = 'Device push (ZKTeco ADMS / iClock)'
const API = 'Push API (bridge or other brands)'
const DB = 'Database pull (BioTime / ZKTime)'
const FILE = 'File upload'
const STATUS_TONE: Record<string, string> = { Online: 'green', Offline: 'red', 'Never connected': 'gray', 'Waiting for approval': 'amber', Disabled: 'gray' }
const BLANK = { device_name: '', enabled: 1, brand: 'ZKTeco', connection: PUSH, serial_number: '', company: '', location: '', match_by: 'Attendance device ID',
  punch_rule: 'From the device (0 = IN, 1 = OUT)', time_offset_minutes: 0, allowed_ips: '', db_type: '', db_host: '', db_port: '', db_name: '', db_user: '',
  db_password: '', db_preset: 'BioTime (iclock_transaction)', db_table: '', db_user_column: '', db_time_column: '', db_state_column: '', db_sn_column: '', pull_every: 15 }

function Guide({ connection, server, pushUrl }: { connection: string; server: string; pushUrl: string }) {
  const { t } = useI18n()
  const box = 'rounded-xl bg-brand-50 p-3 text-sm text-brand'
  if (connection === PUSH) return (
    <div className={box}>
      <b>{t('On the device')}:</b> {t('Menu → Comm. → Cloud Server Setting (ADMS)')}.<br />
      {t('Server address')}: <code className="font-mono">{server}</code> · {t('Port')}: <code className="font-mono">443</code> ({t('HTTPS on')}) {t('or')} <code className="font-mono">80</code>.<br />
      {t('Enter the serial number exactly as on the device. A device that connects before it is added appears here as a new device to enable.')}
    </div>
  )
  if (connection === API) return (
    <div className={box}>
      {t('A bridge on the local network, or a device that can call a web address (Hikvision HTTP listening, Suprema, Anviz), sends punches to')}:<br />
      <code className="break-all font-mono">{pushUrl}</code><br />
      {t('with the header X-AlphaX-Device-Token and a JSON body')}: <code className="font-mono">{'{"device": "SN", "punches": [{"user": "12", "time": "2026-11-05 08:01:00", "state": "0"}]}'}</code>
    </div>
  )
  if (connection === DB) return <div className={box}>{t('AlphaX reads new punches from the attendance software database (ZKTeco BioTime, ZKTime / ZKAccess or your own tables) every few minutes. The database must be reachable from this server.')}</div>
  return <div className={box}>{t('Upload the attendance log exported from the device (attlog.dat from USB) or a CSV file: user, time, state.')}</div>
}

function DeviceForm({ device, onClose, server, pushUrl }: { device: any | null; onClose: () => void; server: string; pushUrl: string }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const [v, setV] = useState<any>(device ? { ...BLANK, ...device, db_password: '' } : BLANK)
  const set = (k: string, x: any) => setV((s: any) => ({ ...s, [k]: x }))
  const save = useMutation({ mutationFn: () => api.saveDevice(v, device?.name), onSuccess: (d) => { qc.setQueryData(['devices'], d); onClose() } })
  const text = (k: string, label: string, type = 'text') => <Field label={t(label)}><Input type={type} value={v[k] ?? ''} onChange={(e) => set(k, e.target.value)} /></Field>
  const sel = (k: string, label: string, opts: string[]) => <Field label={t(label)}><Select value={v[k] ?? ''} onChange={(e) => set(k, e.target.value)}>{opts.map((o) => <option key={o} value={o}>{o ? t(o) : '—'}</option>)}</Select></Field>
  return (
    <Modal open wide onClose={onClose} title={device ? device.device_name : t('Add device')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={save.isPending} onClick={() => save.mutate()}>{t('Save')}</Button></>}>
      <div className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {text('device_name', 'Device name')}
          {sel('connection', 'Connection', [PUSH, API, DB, FILE])}
          {sel('brand', 'Brand', ['ZKTeco', 'Hikvision', 'Suprema', 'Anviz', 'Dahua', 'Other'])}
          {v.connection !== DB && v.connection !== FILE ? text('serial_number', 'Serial number (SN)') : null}
          <Field label={t('Company')}><LinkInput doctype="Company" value={v.company ?? ''} onChange={(x) => set('company', x)} /></Field>
          {text('location', 'Location / site')}
          {sel('match_by', 'Match device users by', ['Attendance device ID', 'Employee ID', 'National ID / Iqama'])}
          {sel('punch_rule', 'IN / OUT', ['From the device (0 = IN, 1 = OUT)', 'Alternate (shift decides)', 'All IN', 'All OUT'])}
          {text('time_offset_minutes', 'Device clock offset (minutes)', 'number')}
          <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!Number(v.enabled)} onChange={(e) => set('enabled', e.target.checked ? 1 : 0)} />{t('Enabled')}</label>
        </div>
        <Guide connection={v.connection} server={server} pushUrl={pushUrl} />
        {(v.connection === PUSH || v.connection === API) && <Field label={t('Allowed IP addresses')} hint={t('One per line. Empty = any address.')}><Textarea value={v.allowed_ips ?? ''} onChange={(e) => set('allowed_ips', e.target.value)} /></Field>}
        {v.connection === DB && (
          <div className="grid gap-3 sm:grid-cols-2">
            {sel('db_type', 'Database', ['', 'MySQL / MariaDB', 'PostgreSQL', 'SQL Server'])}
            {sel('db_preset', 'Software', ['BioTime (iclock_transaction)', 'ZKTime / ZKAccess (CHECKINOUT)', 'Custom'])}
            {text('db_host', 'Host')}{text('db_port', 'Port', 'number')}{text('db_name', 'Database name')}{text('db_user', 'User')}
            <Field label={t('Password')} hint={device ? t('Leave empty to keep the saved password.') : undefined}><Input type="password" value={v.db_password} onChange={(e) => set('db_password', e.target.value)} /></Field>
            {text('pull_every', 'Pull every (minutes)', 'number')}
            {v.db_preset === 'Custom' && <>{text('db_table', 'Punch table')}{text('db_user_column', 'User column')}{text('db_time_column', 'Time column')}{text('db_state_column', 'IN/OUT column')}{text('db_sn_column', 'Device column')}</>}
          </div>
        )}
        {save.error && <ErrorBox error={save.error} />}
      </div>
    </Modal>
  )
}

function DeviceCard({ d, can, onEdit }: { d: any; can: boolean; onEdit: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [msg, setMsg] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ['devices'] })
  const act = useMutation({
    mutationFn: async (what: string) => {
      if (what === 'pull') return api.devicePull(d.name)
      if (what === 'test') return api.deviceTest(d.name)
      if (what === 'token') return api.deviceToken(d.name)
      if (what === 'delete') return api.deleteDevice(d.name)
      if (what === 'enable') return api.saveDevice({ enabled: 1 }, d.name)
      return api.deviceCommand(d.name, what)
    },
    onSuccess: (r: any, what) => {
      refresh()
      if (what === 'token') setToken(r.token)
      else if (what === 'test') setMsg(`${t('Connected')}: ${r.punches} ${t('punches')}${r.last ? ` · ${t('last')} ${r.last}` : ''}`)
      else if (what === 'pull') setMsg(`${t('New punches')}: ${r.new} · ${t('Imported')}: ${r.imported} · ${t('Unmatched')}: ${r.unmatched}`)
      else if (what !== 'delete' && what !== 'enable') setMsg(t('Command queued; the device picks it up within a minute.'))
    },
  })
  const up = useMutation({
    mutationFn: async (file: File) => { const f = await uploadFile('AlphaX Attendance Device', d.name, file); return api.deviceUpload(d.name, f.file_url) },
    onSuccess: (r: any) => { refresh(); setMsg(`${t('Punches in file')}: ${r.received} · ${t('Imported')}: ${r.imported} · ${t('Unmatched')}: ${r.unmatched} · ${t('Already had')}: ${r.already_had}`) },
  })
  const kind = d.connection === PUSH ? 'push' : d.connection === DB ? 'db' : d.connection === API ? 'api' : 'file'
  return (
    <Card>
      <div className="flex flex-wrap items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand/10 text-brand"><Cpu className="size-5" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{d.device_name}</span><Badge tone={STATUS_TONE[d.status] ?? 'gray'}>{t(d.status)}</Badge></div>
          <div className="text-xs text-muted">{t(d.brand)} · {t(d.connection)}{d.serial_number ? ` · SN ${d.serial_number}` : ''}{d.location ? ` · ${d.location}` : ''}{d.model ? ` · ${d.model}` : ''}</div>
          <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <span><span className="text-muted">{t('Last contact')}:</span> {d.last_contact ? fmtDateTime(d.last_contact, lang) : '—'}</span>
            <span><span className="text-muted">{t('Last punch')}:</span> {d.last_punch ? fmtDateTime(d.last_punch, lang) : '—'}</span>
            <span><span className="text-muted">{t('Punches (24 h)')}:</span> {d.punches_24h}</span>
            <span className={clsx(d.unmatched && 'text-amber-700')}><span className="text-muted">{t('Unmatched')}:</span> {d.unmatched}</span>
          </div>
        </div>
        {can && <div className="flex gap-1">
          <Button size="sm" variant="ghost" onClick={onEdit} aria-label={t('Edit')}><Pencil className="size-4" /></Button>
          <Button size="sm" variant="ghost" onClick={() => { if (confirm(t('Remove this device? Its imported punches are kept; a device with imported punches is only disabled.'))) act.mutate('delete') }} aria-label={t('Delete')}><Trash2 className="size-4 text-red-700" /></Button>
        </div>}
      </div>
      {can && (
        <div className="mt-3 flex flex-wrap gap-2 border-t border-line pt-3">
          {d.status === 'Waiting for approval' && <Button size="sm" onClick={() => act.mutate('enable')}>{t('Enable this device')}</Button>}
          {kind === 'push' && <>
            <Button size="sm" variant="secondary" loading={act.isPending && act.variables === 'Upload all logs again'} onClick={() => act.mutate('Upload all logs again')}>{t('Upload all logs again')}</Button>
            <Button size="sm" variant="secondary" onClick={() => act.mutate('Send employees to device')}>{t('Send employees to device')}</Button>
            <Button size="sm" variant="secondary" onClick={() => act.mutate('Read device info')}>{t('Read device info')}</Button>
            <Button size="sm" variant="secondary" onClick={() => { if (confirm(t('Restart the device?'))) act.mutate('Reboot') }}>{t('Reboot')}</Button>
          </>}
          {kind === 'db' && <>
            <Button size="sm" variant="secondary" loading={act.isPending && act.variables === 'test'} onClick={() => act.mutate('test')}>{t('Test connection')}</Button>
            <Button size="sm" variant="secondary" loading={act.isPending && act.variables === 'pull'} onClick={() => act.mutate('pull')}><RefreshCw className="size-4" />{t('Pull now')}</Button>
          </>}
          {kind === 'api' && <Button size="sm" variant="secondary" onClick={() => act.mutate('token')}>{d.has_token ? t('New token') : t('Create token')}</Button>}
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-line px-3 py-1.5 text-sm hover:bg-surface">
            <Upload className="size-4" />{up.isPending ? t('Importing…') : t('Import log file')}
            <input type="file" className="hidden" accept=".dat,.txt,.csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) up.mutate(f); e.target.value = '' }} />
          </label>
        </div>
      )}
      {token && <div className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{t('Token (shown once — copy it into the bridge now)')}: <code className="break-all font-mono">{token}</code></div>}
      {msg && <p className="mt-3 text-sm text-emerald-700">{msg}</p>}
      {(act.error || up.error) && <div className="mt-3"><ErrorBox error={act.error || up.error} /></div>}
    </Card>
  )
}

function Punches({ devices }: { devices: any[] }) {
  const { t, lang } = useI18n()
  const [device, setDevice] = useState('')
  const [status, setStatus] = useState('')
  const q = useQuery({ queryKey: ['device-logs', device, status], queryFn: () => api.deviceLogs({ device: device || undefined, status: status || undefined }) })
  return (
    <Card>
      <div className="mb-3 flex flex-wrap gap-2">
        <Select value={device} onChange={(e) => setDevice(e.target.value)} className="!w-56"><option value="">{t('All devices')}</option>{devices.map((d) => <option key={d.name} value={d.name}>{d.device_name}</option>)}</Select>
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="!w-44"><option value="">{t('All')}</option>{['Imported', 'Unmatched', 'Duplicate', 'Error', 'Pending'].map((s) => <option key={s} value={s}>{t(s)}</option>)}</Select>
      </div>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : !q.data?.length ? <Empty title={t('No punches yet')} /> : (
        <Table head={[t('Time'), t('Device user ID'), t('Employee'), t('IN / OUT'), t('Device'), t('Status')]}>
          {q.data.map((r: any) => (
            <tr key={r.name}>
              <td className="py-1.5 tabular-nums">{fmtDateTime(r.punch_time, lang)}</td><td>{r.device_user}</td><td>{r.employee_name ?? '—'}</td>
              <td>{r.log_type ? t(r.log_type) : '—'}</td><td className="text-muted">{r.device}</td>
              <td><Badge tone={r.status === 'Imported' ? 'green' : r.status === 'Unmatched' ? 'amber' : r.status === 'Error' ? 'red' : 'gray'}>{t(r.status)}</Badge>{r.message && r.status !== 'Imported' && <div className="text-xs text-muted">{r.message}</div>}</td>
            </tr>
          ))}
        </Table>
      )}
    </Card>
  )
}

function Unmatched({ can }: { can: boolean }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['device-unmatched'], queryFn: api.deviceUnmatched })
  const [pick, setPick] = useState<Record<string, string>>({})
  const link = useMutation({
    mutationFn: (r: any) => api.deviceLinkUser(r.device, r.device_user, pick[`${r.device}|${r.device_user}`] || r.suggest?.name),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['device-unmatched'] }); qc.invalidateQueries({ queryKey: ['devices'] }) },
  })
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} />
  if (!q.data?.length) return <Card><p className="text-sm text-emerald-700">{t('Every punch is matched to an employee.')}</p></Card>
  return (
    <Card subtitle={t('Punches from these device users wait for an employee. Linking sets the employee’s attendance device ID and imports the waiting punches.')}>
      <Table head={[t('Device user ID'), t('Name on device'), t('Punches'), t('Last punch'), t('Device'), t('Employee'), '']}>
        {(q.data ?? []).map((r: any) => {
          const key = `${r.device}|${r.device_user}`
          return (
            <tr key={key}>
              <td className="py-2 font-medium">{r.device_user}</td><td>{r.user_name ?? '—'}</td><td>{r.n}</td><td className="tabular-nums">{fmtDateTime(r.last, lang)}</td>
              <td className="text-muted">{r.device}</td>
              <td className="min-w-56">{can ? <LinkInput doctype="Employee" value={pick[key] ?? r.suggest?.name ?? ''} onChange={(x) => setPick({ ...pick, [key]: x })} /> : '—'}</td>
              <td>{can && <Button size="sm" disabled={!(pick[key] || r.suggest)} loading={link.isPending && link.variables === r} onClick={() => link.mutate(r)}>{t('Link')}</Button>}</td>
            </tr>
          )
        })}
      </Table>
      {link.error && <div className="mt-3"><ErrorBox error={link.error} /></div>}
    </Card>
  )
}

export default function AttendanceDevices() {
  const { t } = useI18n()
  const q = useQuery({ queryKey: ['devices'], queryFn: api.devicesOverview, refetchInterval: 30_000 })
  const [tab, setTab] = useState('devices')
  const [edit, setEdit] = useState<any | null | undefined>(undefined)
  if (q.isLoading) return <Spinner />
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />
  const d = q.data
  return (
    <div className="flex flex-col gap-5">
      <PageHeader title={t('Attendance devices')} subtitle={t('Fingerprint and face devices: ZKTeco by device push, other brands by the push API or a bridge, attendance software by database, or log files.')}
        actions={d.can_edit ? <Button onClick={() => setEdit(null)}><Plus className="size-4" />{t('Add device')}</Button> : undefined} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'devices', label: t('Devices') },
        { value: 'punches', label: t('Punches') },
        { value: 'unmatched', label: t('Unmatched users'), badge: d.totals.Unmatched ? <span className="rounded-full bg-amber-100 px-1.5 text-xs text-amber-800">{d.totals.Unmatched}</span> : undefined }]} />
      {tab === 'devices' && (!d.devices.length ? <Card><Empty title={t('No devices yet')} icon={<Cpu />}>{t('Add a device, or point a ZKTeco device to this server: it appears here to enable.')}</Empty></Card>
        : d.devices.map((x: any) => <DeviceCard key={x.name} d={x} can={d.can_edit} onEdit={() => setEdit(x)} />))}
      {tab === 'punches' && <Punches devices={d.devices} />}
      {tab === 'unmatched' && <Unmatched can={d.can_edit} />}
      {edit !== undefined && <DeviceForm device={edit} server={d.server} pushUrl={d.push_url} onClose={() => setEdit(undefined)} />}
    </div>
  )
}
