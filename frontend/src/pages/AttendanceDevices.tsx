import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import clsx from 'clsx'
import { Activity, AlertTriangle, UserCheck, CalendarCheck, Cpu, Database, Pencil, Plus, RefreshCw, Search, Trash2, Upload, Users } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { LinkInput } from '../components/LinkInput'
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, PageHeader, Select, Spinner, Table, Tabs, Textarea } from '../components/ui'
import { api, uploadFile } from '../lib/api'
import { fmtDateTime } from '../lib/format'
import { useI18n } from '../lib/i18n'

const PUSH = 'Device push (ZKTeco ADMS / iClock)'
const API = 'Push API (bridge or other brands)'
const DB = 'Database pull (BioTime / ZKTime)'
const FILE = 'File upload'
const TERMINAL = 'Via database source'
const PRESETS = ['BioTime (iclock_transaction)', 'ZKTime / ZKAccess (CHECKINOUT)', 'ADMS (CheckInOut + EmpDetails)', 'Custom']
const STATUS_TONE: Record<string, string> = { Online: 'green', Offline: 'red', 'Never connected': 'gray', 'Waiting for approval': 'amber', Disabled: 'gray', Active: 'green', Quiet: 'amber', 'Connection failed': 'red', 'Source not reachable': 'red', Excluded: 'gray' }
const BLANK = { device_name: '', enabled: 1, brand: 'ZKTeco', connection: PUSH, serial_number: '', company: '', location: '', branch: '', offline_alert_hours: 2, match_by: 'Attendance device ID',
  punch_rule: 'From the device (0 = IN, 1 = OUT)', time_offset_minutes: 0, allowed_ips: '', db_type: '', db_host: '', db_port: '', db_name: '', db_user: '',
  db_password: '', db_preset: 'BioTime (iclock_transaction)', db_table: '', db_user_column: '', db_time_column: '', db_state_column: '', db_sn_column: '', pull_every: 15, split_by_terminal: 1 }

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
  if (connection === DB) return <div className={box}>{t('AlphaX reads new punches from the attendance software database (ZKTeco BioTime, ZKTime / ZKAccess, an ADMS server or your own tables) every few minutes. The database must be reachable from this server.')}<br />{t('One connection covers every device that writes to this database: after saving, use Find terminals and each device is listed on its own.')}</div>
  if (connection === TERMINAL) return <div className={box}>{t('This terminal was found in a central attendance database; its punches arrive through that connection. Set its branch and location here.')}</div>
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
    <Modal open wide onClose={onClose} title={device?.name ? device.device_name : device?.connection === DB ? t('Connect attendance database') : t('Add device')}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button><Button loading={save.isPending} onClick={() => save.mutate()}>{t('Save')}</Button></>}>
      <div className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-2">
          {text('device_name', 'Device name')}
          {v.connection === TERMINAL ? <Field label={t('Connection')}><Input value={`${t(TERMINAL)}: ${v.source_device}`} disabled /></Field> : sel('connection', 'Connection', [PUSH, API, DB, FILE])}
          {sel('brand', 'Brand', ['ZKTeco', 'Hikvision', 'Suprema', 'Anviz', 'Dahua', 'Other'])}
          {v.connection !== DB && v.connection !== FILE && v.connection !== TERMINAL ? text('serial_number', 'Serial number (SN)') : null}
          <Field label={t('Company')}><LinkInput doctype="Company" value={v.company ?? ''} onChange={(x) => set('company', x)} /></Field>
          {text('location', 'Location / site')}
          {sel('match_by', 'Match device users by', ['Attendance device ID', 'Employee ID', 'National ID / Iqama'])}
          {sel('punch_rule', 'IN / OUT', ['From the device (0 = IN, 1 = OUT)', 'First IN, last OUT (ignore the keys)', 'Alternate (shift decides)', 'All IN', 'All OUT'])}
          <Field label={t('Branch')} hint={t('Punches by employees of another branch are flagged.')}><LinkInput doctype="Branch" value={v.branch ?? ''} onChange={(x) => set('branch', x)} /></Field>
          {v.connection !== FILE ? text('offline_alert_hours', 'Tell HR when offline for (hours)', 'number') : null}
          {text('time_offset_minutes', 'Device clock offset (minutes)', 'number')}
          <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!Number(v.enabled)} onChange={(e) => set('enabled', e.target.checked ? 1 : 0)} />{t('Enabled')}</label>
        </div>
        <Guide connection={v.connection} server={server} pushUrl={pushUrl} />
        {(v.connection === PUSH || v.connection === API) && <Field label={t('Allowed IP addresses')} hint={t('One per line. Empty = any address.')}><Textarea value={v.allowed_ips ?? ''} onChange={(e) => set('allowed_ips', e.target.value)} /></Field>}
        {v.connection === DB && (
          <div className="grid gap-3 sm:grid-cols-2">
            {sel('db_type', 'Database', ['', 'MySQL / MariaDB', 'PostgreSQL', 'SQL Server'])}
            {sel('db_preset', 'Software', PRESETS)}
            <Field label={t('Host')} hint={t('Server name or IP only; the port goes in Port.')}><Input value={v.db_host ?? ''} onChange={(e) => set('db_host', e.target.value)} /></Field>{text('db_port', 'Port', 'number')}{text('db_name', 'Database name')}{text('db_user', 'User')}
            <Field label={t('Password')} hint={device?.name ? t('Leave empty to keep the saved password.') : undefined}><Input type="password" value={v.db_password} onChange={(e) => set('db_password', e.target.value)} /></Field>
            {text('pull_every', 'Pull every (minutes)', 'number')}
            <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={!!Number(v.split_by_terminal)} onChange={(e) => set('split_by_terminal', e.target.checked ? 1 : 0)} />{t('Show each terminal separately')}</label>
            {v.db_preset === 'ADMS (CheckInOut + EmpDetails)' && <p className="text-xs text-muted sm:col-span-2">{t('Users are matched by the national ID in EmpDetails: set Match device users by to National ID / Iqama.')}</p>}
            {v.db_preset === 'Custom' && <p className="text-xs text-muted sm:col-span-2">{t('After saving, open Tables & columns on the card: AlphaX reads the database and proposes the tables and columns.')}</p>}
          </div>
        )}
        {save.error && <ErrorBox error={save.error} />}
      </div>
    </Modal>
  )
}

function Enrolment({ device, onClose, onQueued }: { device: any; onClose: () => void; onQueued: () => void }) {
  const { t } = useI18n()
  const q = useQuery<any>({ queryKey: ['device-enrolment', device.name], queryFn: () => api.deviceEnrolment(device.name) })
  const [pin, setPin] = useState('')
  const cmd = useMutation({ mutationFn: (x: { c: string; user?: string }) => api.deviceCommand(device.name, x.c, x.user), onSuccess: onQueued })
  const list = (title: string, rows: any[], render: (r: any) => ReactNode, tone = '') => (
    <section>
      <h3 className={clsx('mb-1 text-sm font-semibold', tone)}>{title} ({rows.length})</h3>
      {rows.length ? <ul className="max-h-48 divide-y divide-line overflow-auto rounded-lg border border-line text-sm">{rows.map((r, i) => <li key={i} className="flex justify-between gap-2 px-2 py-1.5">{render(r)}</li>)}</ul>
        : <p className="text-sm text-muted">{t('None')}</p>}
    </section>
  )
  return (
    <Modal open wide onClose={onClose} title={`${t('Users on the device')} · ${device.device_name}`}
      footer={<Button variant="secondary" onClick={onClose}>{t('Close')}</Button>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-muted">{q.data.users_known ? t('{0} users reported by the device.').replace('{0}', String(q.data.device_users))
            : t('The device has not reported its users yet; they arrive when users are added on it (or use Upload all logs again).')}</p>
          {list(t('Employees who left, still on the device'), q.data.left_on_device, (r) => <><span>{r.employee_name} <span className="text-muted">#{r.device_user}</span></span><Badge tone="red">{t(r.status)}</Badge></>, 'text-red-700')}
          {q.data.left_on_device.length > 0 && <Button className="self-start" variant="danger" loading={cmd.isPending} onClick={() => cmd.mutate({ c: 'Remove left employees' })}>{t('Remove them from the device')}</Button>}
          {list(t('Active employees without a device ID'), q.data.missing_id, (r) => <><span>{r.employee_name}</span><span className="text-muted">{r.department ?? ''}</span></>, 'text-amber-700')}
          {q.data.users_known && list(t('Employees with a device ID who are not on the device'), q.data.not_on_device, (r) => <><span>{r.employee_name}</span><span className="text-muted">#{r.attendance_device_id}</span></>)}
          {q.data.users_known && q.data.not_on_device.length > 0 && <Button className="self-start" variant="secondary" loading={cmd.isPending} onClick={() => cmd.mutate({ c: 'Send employees to device' })}>{t('Send employees to device')}</Button>}
          <div className="flex items-end gap-2 border-t border-line pt-3">
            <Field label={t('Delete one user from the device (user number)')}><Input value={pin} onChange={(e) => setPin(e.target.value)} inputMode="numeric" /></Field>
            <Button variant="secondary" disabled={!pin.trim()} loading={cmd.isPending} onClick={() => cmd.mutate({ c: 'Delete user from device', user: pin.trim() })}>{t('Delete')}</Button>
          </div>
          {cmd.error && <ErrorBox error={cmd.error} />}
        </div>
      )}
    </Modal>
  )
}


const MAP_GROUPS: { table: string; label: string; required?: boolean; cols: [string, string, boolean?][] }[] = [
  { table: 'db_table', label: 'Punch table', required: true, cols: [['db_user_column', 'User ID', true], ['db_time_column', 'Punch time', true], ['db_state_column', 'IN/OUT'], ['db_sn_column', 'Device serial number']] },
  { table: 'db_emp_table', label: 'People table (optional)', cols: [['db_emp_id_column', 'ID used in punches'], ['db_emp_key_column', 'Value to match employees by'], ['db_emp_name_column', 'Name'], ['db_emp_no_column', 'Employee number']] },
  { table: 'db_device_table', label: 'Devices table (optional)', cols: [['db_device_sn_column', 'Serial number'], ['db_device_name_column', 'Device name'], ['db_device_active_column', 'Active'], ['db_device_ip_column', 'IP address'], ['db_device_location_column', 'Location'], ['db_device_model_column', 'Model']] },
]
const MAP_KEYS = MAP_GROUPS.flatMap((g) => [g.table, ...g.cols.map((c) => c[0])])

function DbSetup({ device, onClose }: { device: any; onClose: () => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [step, setStep] = useState('map')
  const init: any = { punch_rule: device.punch_rule, db_in_values: device.db_in_values ?? '', db_out_values: device.db_out_values ?? '', match_by: device.match_by }
  MAP_KEYS.forEach((k) => { init[k] = device[k] ?? '' })
  // ADMS is a mapping preset (fields adjust it); BioTime / ZKTime are fixed queries, so mapping them by hand means Custom
  const [v, setV] = useState<any>({ ...init, db_preset: device.db_preset === 'ADMS (CheckInOut + EmpDetails)' ? device.db_preset : 'Custom' })
  const [tables, setTables] = useState<string[]>([])
  const [cols, setCols] = useState<Record<string, string[]>>({})
  const [sug, setSug] = useState<Record<string, string>>({})
  const set = (k: string, x: any) => setV((s: any) => ({ ...s, [k]: x }))
  const read = useMutation({
    mutationFn: () => api.deviceSchema(device.name, { db_preset: device.db_preset }),
    onSuccess: (r: any) => {
      setTables(r.tables); setCols(r.columns); setSug(r.mapping)
      setV((s: any) => { const n = { ...s }; MAP_KEYS.forEach((k) => { if (!n[k] && r.mapping[k]) n[k] = r.mapping[k] }); return n })
    },
  })
  const loadCols = async (table: string) => {
    if (!table || cols[table]) return
    const r = await api.deviceSchema(device.name, undefined, table)
    setCols((c) => ({ ...c, [table]: r.columns }))
  }
  const pv = useMutation({ mutationFn: () => api.devicePreview(device.name, v) })
  const save = useMutation({ mutationFn: () => api.saveDevice(v, device.name), onSuccess: (d) => { qc.setQueryData(['devices'], d); onClose() } })
  const pick = (k: string, options: string[], label: string, required = false) => (
    <Field label={<span className="flex flex-wrap items-center gap-1.5">{t(label)}{required && <span className="text-red-600">*</span>}
      {sug[k] && sug[k] !== v[k] && <button type="button" onClick={() => set(k, sug[k])} className="rounded-full bg-amber-50 px-2 text-[11px] text-amber-800">{t('suggest')}: {sug[k]}</button>}</span> as any}>
      <Select value={v[k] ?? ''} onChange={(e) => set(k, e.target.value)}>
        <option value="">—</option>
        {v[k] && !options.includes(v[k]) && <option value={v[k]}>{v[k]}</option>}
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </Select>
    </Field>
  )
  return (
    <Modal open wide onClose={onClose} title={`${t('Tables & columns')} · ${device.device_name}`}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Cancel')}</Button>
        {step === 'map' ? <Button onClick={() => { setStep('values'); pv.mutate() }} disabled={!v.db_table || !v.db_user_column || !v.db_time_column}>{t('Next')}</Button>
          : <Button loading={save.isPending} onClick={() => save.mutate()}>{t('Save')}</Button>}</>}>
      <div className="flex flex-col gap-4">
        <Tabs value={step} onChange={setStep} tabs={[{ value: 'map', label: `1. ${t('Tables & columns')}` }, { value: 'values', label: `2. ${t('IN / OUT and preview')}` }]} />
        {step === 'map' && <>
          <div className="flex flex-wrap items-center gap-2 rounded-xl bg-brand-50 p-3 text-sm text-brand">
            <Database className="size-4" />{t('AlphaX reads the table and column names from the database and proposes them. Check and adjust.')}
            <Button size="sm" className="ms-auto" loading={read.isPending} onClick={() => read.mutate()}><Search className="size-4" />{tables.length ? t('Read again') : t('Read the database')}</Button>
          </div>
          {read.error && <ErrorBox error={read.error} />}
          {MAP_GROUPS.map((g) => (
            <div key={g.table} className="rounded-xl border border-line p-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={<span className="flex flex-wrap items-center gap-1.5 font-medium">{t(g.label)}{g.required && <span className="text-red-600">*</span>}
                  {sug[g.table] && sug[g.table] !== v[g.table] && <button type="button" onClick={() => { set(g.table, sug[g.table]); loadCols(sug[g.table]) }} className="rounded-full bg-amber-50 px-2 text-[11px] text-amber-800">{t('suggest')}: {sug[g.table]}</button>}</span> as any}>
                  {tables.length ? <Select value={v[g.table] ?? ''} onChange={(e) => { set(g.table, e.target.value); loadCols(e.target.value) }}>
                    <option value="">—</option>{v[g.table] && !tables.includes(v[g.table]) && <option value={v[g.table]}>{v[g.table]}</option>}
                    {tables.map((o) => <option key={o} value={o}>{o}</option>)}</Select>
                    : <Input value={v[g.table] ?? ''} onChange={(e) => set(g.table, e.target.value)} placeholder={t('Read the database to choose')} />}
                </Field>
              </div>
              {v[g.table] && <div className="mt-3 grid gap-3 sm:grid-cols-4">
                {g.cols.map(([k, label, req]) => cols[v[g.table]]
                  ? <div key={k}>{pick(k, cols[v[g.table]], label, !!req)}</div>
                  : <Field key={k} label={t(label)}><Input value={v[k] ?? ''} onChange={(e) => set(k, e.target.value)} /></Field>)}
              </div>}
            </div>
          ))}
        </>}
        {step === 'values' && <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label={t('IN / OUT')}><Select value={v.punch_rule ?? ''} onChange={(e) => set('punch_rule', e.target.value)}>
              {['From the device (0 = IN, 1 = OUT)', 'First IN, last OUT (ignore the keys)', 'Alternate (shift decides)', 'All IN', 'All OUT'].map((o) => <option key={o} value={o}>{t(o)}</option>)}</Select></Field>
            <Field label={t('Values meaning IN')} hint={pv.data?.states?.length ? `${t('Found')}: ${pv.data.states.join(', ')}` : undefined}><Input value={v.db_in_values} onChange={(e) => set('db_in_values', e.target.value)} placeholder="0" /></Field>
            <Field label={t('Values meaning OUT')}><Input value={v.db_out_values} onChange={(e) => set('db_out_values', e.target.value)} placeholder="1" /></Field>
          </div>
          <div className="flex items-center gap-2"><span className="text-sm font-medium">{t('Latest punches as AlphaX reads them')}</span>
            <Button size="sm" variant="secondary" className="ms-auto" loading={pv.isPending} onClick={() => pv.mutate()}><RefreshCw className="size-4" />{t('Preview')}</Button></div>
          {pv.error && <ErrorBox error={pv.error} />}
          {pv.data && <Table head={[t('User'), t('Time'), t('Value'), t('IN / OUT'), t('Terminal'), t('Employee')]}>
            {pv.data.rows.map((r: any, i: number) => (
              <tr key={i}><td className="font-mono text-xs">{r.user}</td><td>{fmtDateTime(r.time, lang)}</td><td className="font-mono text-xs">{r.state ?? '—'}</td>
                <td>{r.log_type ? <Badge tone={r.log_type === 'IN' ? 'green' : 'blue'}>{t(r.log_type)}</Badge> : <span className="text-xs text-muted">{t('by the day')}</span>}</td>
                <td className="font-mono text-xs">{r.terminal ?? '—'}</td>
                <td>{r.employee_name ?? <span className="text-amber-700">{t('Not matched')}</span>}</td></tr>))}
          </Table>}
          {save.error && <ErrorBox error={save.error} />}
        </>}
      </div>
    </Modal>
  )
}

function SyncPanel({ device, can }: { device: any; can: boolean }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const first = new Date(); first.setDate(1)
  const [start, setStart] = useState(first.toISOString().slice(0, 10))
  const q = useQuery<any>({ queryKey: ['device-sync', device.name, start], queryFn: () => api.deviceSyncStatus(device.name, start) })
  const bf = useMutation({ mutationFn: () => api.deviceBackfill(device.name, start), onSuccess: () => { qc.invalidateQueries({ queryKey: ['device-sync', device.name] }); qc.invalidateQueries({ queryKey: ['devices'] }) } })
  const s = q.data
  const tile = (label: string, value: ReactNode, tone = '') => <div className="rounded-xl border border-line p-2.5"><div className={clsx('text-sm font-semibold', tone)}>{value}</div><div className="text-[11px] uppercase text-muted">{t(label)}</div></div>
  return (
    <div className="mt-3 flex flex-col gap-3 border-t border-line pt-3">
      <div className="flex flex-wrap items-end gap-2">
        <Field label={t('From')}><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="!w-44" /></Field>
        {s?.oldest && <Button size="sm" variant="ghost" onClick={() => setStart(s.oldest.slice(0, 10))}>{t('Use oldest')} ({s.oldest.slice(0, 10)})</Button>}
        {can && <Button size="sm" className="ms-auto" loading={bf.isPending} disabled={!s?.gap} onClick={() => bf.mutate()}><RefreshCw className="size-4" />{t('Read the missing punches')}</Button>}
      </div>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} /> : s && <>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {tile('Read up to', s.watermark ? fmtDateTime(s.watermark, lang) : '—')}
          {tile('Last successful read', s.last_success ? fmtDateTime(s.last_success, lang) : '—')}
          {tile('Connection', s.connected ? t('Connected') : t('Connection failed'), s.connected ? 'text-emerald-700' : 'text-red-700')}
          {tile('Oldest punch in the database', s.oldest ? s.oldest.slice(0, 10) : '—')}
        </div>
        <div className="grid grid-cols-3 gap-2">
          {tile('In the database', s.available)}{tile('In AlphaX', s.synced)}{tile('Missing', s.gap, s.gap ? 'text-amber-700' : 'text-emerald-700')}
        </div>
        {s.terminals.length > 0 && <Table head={[t('Terminal'), t('In the database'), t('In AlphaX'), t('Missing')]}>
          {s.terminals.map((r: any) => <tr key={r.device + (r.serial_number ?? '')}>
            <td>{r.device_name}{!r.included && <span className="ms-2 text-xs text-muted">({t('excluded')})</span>}<div className="text-xs text-muted">{r.serial_number ? `SN ${r.serial_number}` : ''}</div></td>
            <td>{r.available}</td><td>{r.synced}</td><td className={clsx(r.available > r.synced && 'text-amber-700')}>{Math.max(r.available - r.synced, 0)}</td></tr>)}
        </Table>}
        <p className="text-xs text-muted">{t('Reading again never doubles a punch. A terminal you include later: include it, then read the missing punches from the date you need.')}</p>
      </>}
      {bf.data && <p className="text-sm text-emerald-700">{bf.data.queued ? t('Reading in the background; refresh in a few minutes.') : `${t('New punches')}: ${bf.data.new} · ${t('Imported')}: ${bf.data.imported} · ${t('Unmatched')}: ${bf.data.unmatched}`}</p>}
      {bf.error && <ErrorBox error={bf.error} />}
    </div>
  )
}

const REASON_TONE: Record<string, string> = { Iqama: 'green', 'Employee number': 'green', 'Device ID': 'blue', Name: 'amber' }

function MatchPeople({ device, onClose }: { device: any; onClose: () => void }) {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['device-people', device.name], queryFn: () => api.devicePeople(device.name) })
  const [pick, setPick] = useState<Record<string, string>>({})
  const [on, setOn] = useState<Record<string, boolean>>({})
  const [show, setShow] = useState('todo')
  const [find, setFind] = useState('')
  const rows: any[] = q.data?.people ?? []
  const choice = (r: any) => pick[r.device_user] ?? r.suggest ?? ''
  const checked = (r: any) => on[r.device_user] ?? (!!r.suggest && r.reason !== 'Name')
  const visible = rows.filter((r) => (show === 'all' || (show === 'todo' ? !r.employee : !!r.employee))
    && (!find || `${r.name ?? ''} ${r.device_user} ${r.emp_no ?? ''}`.toLowerCase().includes(find.toLowerCase())))
  const chosen = rows.filter((r) => !r.employee && checked(r) && choice(r))
  const link = useMutation({
    mutationFn: () => api.deviceLinkPeople(device.name, chosen.map((r) => ({ device_user: r.device_user, employee: choice(r) }))),
    onSuccess: () => { setPick({}); setOn({}); q.refetch(); qc.invalidateQueries({ queryKey: ['devices'] }); qc.invalidateQueries({ queryKey: ['device-unmatched'] }) },
  })
  return (
    <Modal open wide onClose={onClose} title={`${t('Match employees')} · ${device.device_name}`}
      footer={<><Button variant="secondary" onClick={onClose}>{t('Close')}</Button>
        <Button loading={link.isPending} disabled={!chosen.length} onClick={() => link.mutate()}><UserCheck className="size-4" />{t('Link selected')} ({chosen.length})</Button></>}>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorBox error={q.error} onRetry={() => q.refetch()} /> : (
        <div className="flex flex-col gap-3">
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-xl border border-line p-2"><div className="text-lg font-semibold text-emerald-700">{q.data.matched}</div><div className="text-xs text-muted">{t('Matched')}</div></div>
            <div className="rounded-xl border border-line p-2"><div className="text-lg font-semibold text-brand">{q.data.suggested}</div><div className="text-xs text-muted">{t('Suggested')}</div></div>
            <div className="rounded-xl border border-line p-2"><div className="text-lg font-semibold text-amber-700">{q.data.unmatched}</div><div className="text-xs text-muted">{t('To choose')}</div></div>
          </div>
          <p className="rounded-xl bg-brand-50 p-3 text-xs text-brand">{t('The link is kept on this connection, so an employee\'s existing Device ID or Iqama is never changed (empty ones are filled in). Waiting punches are imported at once. Suggestions by name are not ticked: check them first.')}</p>
          {!q.data.has_people_table && <p className="rounded-xl bg-amber-50 p-3 text-xs text-amber-900">{t('No people table is set, so only device users with waiting punches are listed. Set it in Tables & columns to see names.')}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <Select value={show} onChange={(e) => setShow(e.target.value)} className="!w-44">
              <option value="todo">{t('Not matched')}</option><option value="done">{t('Matched')}</option><option value="all">{t('All')}</option></Select>
            <Input value={find} onChange={(e) => setFind(e.target.value)} placeholder={t('Search name or ID')} className="!w-60" />
            {visible.some((r) => !r.employee && choice(r)) && <Button size="sm" variant="ghost" onClick={() => setOn(Object.fromEntries(visible.filter((r) => !r.employee && choice(r)).map((r) => [r.device_user, true])))}>{t('Tick all shown')}</Button>}
          </div>
          <Table head={['', t('In the attendance database'), t('IDs'), t('Waiting punches'), t('AlphaX employee'), '']}>
            {visible.slice(0, 300).map((r) => (
              <tr key={r.device_user}>
                <td>{!r.employee && <input type="checkbox" className="size-4 accent-[var(--color-brand)]" checked={checked(r) && !!choice(r)} disabled={!choice(r)}
                  onChange={(e) => setOn((o) => ({ ...o, [r.device_user]: e.target.checked }))} />}</td>
                <td><div className="font-medium">{r.name ?? <span className="text-muted">{t('No name')}</span>}</div>
                  {r.problem && r.problem !== 'Iqama format' && <div className="text-[11px] text-amber-700">{t(r.problem)}</div>}</td>
                <td className="font-mono text-xs">{r.national_id ? <div>{t('ID')} {r.national_id}</div> : null}<div className="text-muted">{t('User')} {r.id}{r.emp_no ? ` · ${t('No.')} ${r.emp_no}` : ''}</div></td>
                <td className={clsx(r.waiting && 'text-amber-700')}>{r.waiting || '—'}</td>
                <td className="min-w-56">{r.employee ? <span className="text-emerald-700">{r.employee_name}</span>
                  : <LinkInput doctype="Employee" value={choice(r)} onChange={(x) => { setPick((p) => ({ ...p, [r.device_user]: x })); setOn((o) => ({ ...o, [r.device_user]: !!x })) }} />}</td>
                <td>{!r.employee && r.reason && choice(r) === r.suggest && <Badge tone={REASON_TONE[r.reason] ?? 'gray'}>{t('by')} {t(r.reason)}</Badge>}</td>
              </tr>
            ))}
          </Table>
          {visible.length > 300 && <p className="text-xs text-muted">{t('Showing 300; search to narrow.')}</p>}
          {link.data && <div className="text-sm"><span className="text-emerald-700">{t('Linked')}: {link.data.linked} · {t('Imported')}: {link.data.imported ?? 0}</span>
            {link.data.problems?.length > 0 && <ul className="mt-1 list-disc ps-5 text-amber-800">{link.data.problems.map((x: string) => <li key={x}>{x}</li>)}</ul>}</div>}
          {link.error && <ErrorBox error={link.error} />}
        </div>
      )}
    </Modal>
  )
}

function DeviceCard({ d, can, onEdit, terminals = [], onEditTerminal }: { d: any; can: boolean; onEdit: () => void; terminals?: any[]; onEditTerminal?: (x: any) => void }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const [msg, setMsg] = useState<string | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const refresh = () => qc.invalidateQueries({ queryKey: ['devices'] })
  const act = useMutation({
    mutationFn: async (what: string) => {
      if (what === 'pull') return api.devicePull(d.name)
      if (what === 'test') return api.deviceTest(d.name)
      if (what === 'discover') return api.deviceDiscover(d.name)
      if (what === 'token') return api.deviceToken(d.name)
      if (what === 'delete') return api.deleteDevice(d.name)
      if (what === 'enable') return api.saveDevice({ enabled: 1 }, d.name)
      return api.deviceCommand(d.name, what)
    },
    onSuccess: (r: any, what) => {
      refresh()
      if (what === 'token') setToken(r.token)
      else if (what === 'discover') { qc.setQueryData(['devices'], r); setMsg(`${t('Terminals found')}: ${r.terminals.length} · ${t('new')}: ${r.new}`) }
      else if (what === 'test') setMsg(`${t('Connected')}: ${r.punches} ${t('punches')}${r.terminals != null ? ` · ${r.terminals} ${t('terminals')}` : ''}${r.last ? ` · ${t('last')} ${r.last}` : ''}`)
      else if (what === 'pull') setMsg(`${t('New punches')}: ${r.new} · ${t('Imported')}: ${r.imported} · ${t('Unmatched')}: ${r.unmatched}`)
      else if (what !== 'delete' && what !== 'enable') setMsg(t('Command queued; the device picks it up within a minute.'))
    },
  })
  const up = useMutation({
    mutationFn: async (file: File) => { const f = await uploadFile('AlphaX Attendance Device', d.name, file); return api.deviceUpload(d.name, f.file_url) },
    onSuccess: (r: any) => { refresh(); setMsg(`${t('Punches in file')}: ${r.received} · ${t('Imported')}: ${r.imported} · ${t('Unmatched')}: ${r.unmatched} · ${t('Already had')}: ${r.already_had}`) },
  })
  const kind = d.connection === PUSH ? 'push' : d.connection === DB ? 'db' : d.connection === API ? 'api' : 'file'
  const [enrol, setEnrol] = useState(false)
  const [setup, setSetup] = useState(false)
  const [sync, setSync] = useState(false)
  const [match, setMatch] = useState(false)
  const include = useMutation({ mutationFn: (x: { name: string; on: boolean }) => api.saveDevice({ enabled: x.on ? 1 : 0 }, x.name), onSuccess: (r) => qc.setQueryData(['devices'], r) })
  return (
    <Card>
      <div className="flex flex-wrap items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-brand/10 text-brand"><Cpu className="size-5" /></span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2"><span className="font-semibold">{d.device_name}</span><Badge tone={STATUS_TONE[d.status] ?? 'gray'}>{t(d.status)}</Badge></div>
          <div className="text-xs text-muted">{kind === 'db' ? `${t('Attendance database')} · ${d.db_name ?? ''}${d.db_host ? ` @ ${d.db_host}` : ''}` : `${t(d.brand)} · ${t(d.connection)}`}{d.serial_number ? ` · SN ${d.serial_number}` : ''}{d.location ? ` · ${d.location}` : ''}{d.model ? ` · ${d.model}` : ''}</div>
          <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
            <span><span className="text-muted">{t('Last contact')}:</span> {d.last_contact ? fmtDateTime(d.last_contact, lang) : '—'}</span>
            <span><span className="text-muted">{t('Last punch')}:</span> {d.last_punch ? fmtDateTime(d.last_punch, lang) : '—'}</span>
            <span><span className="text-muted">{t('Punches (24 h)')}:</span> {d.punches_24h}</span>
            <span className={clsx(d.unmatched && 'text-amber-700')}><span className="text-muted">{t('Unmatched')}:</span> {d.unmatched}</span>
            {d.outside_7d > 0 && <span className="text-amber-700"><span className="text-muted">{t('Other branch (7 days)')}:</span> {d.outside_7d}</span>}
          </div>
          {d.last_error && <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-red-50 p-2 text-xs text-red-800"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            <span><b>{t('Connection failed')}</b>{d.last_error_on ? ` · ${t('since')} ${fmtDateTime(d.last_error_on, lang)}` : ''}{d.failures > 1 ? ` · ${d.failures} ${t('attempts')}` : ''}<br />{d.last_error}<br />
            <span className="text-red-700">{t('Punches stay in the attendance database and are read once the connection works again.')}</span></span></p>}
          {d.hint && <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-amber-50 p-2 text-xs text-amber-900"><AlertTriangle className="mt-0.5 size-3.5 shrink-0" />{d.hint}</p>}
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
            <Button size="sm" variant="secondary" onClick={() => setEnrol(true)}><Users className="size-4" />{t('Users on the device')}</Button>
            <Button size="sm" variant="secondary" onClick={() => { if (confirm(t('Delete all punches stored on the device? Only possible when every punch from it has been imported.'))) act.mutate('Clear device logs') }}>{t('Clear device logs')}</Button>
          </>}
          {kind === 'db' && <>
            <Button size="sm" variant="secondary" loading={act.isPending && act.variables === 'test'} onClick={() => act.mutate('test')}>{t('Test connection')}</Button>
            <Button size="sm" variant="secondary" onClick={() => setSetup(true)}><Database className="size-4" />{t('Tables & columns')}</Button>
            <Button size="sm" variant="secondary" loading={act.isPending && act.variables === 'discover'} onClick={() => act.mutate('discover')}><Search className="size-4" />{t('Find terminals')}</Button>
            <Button size="sm" variant="secondary" onClick={() => setMatch(true)}><UserCheck className="size-4" />{t('Match employees')}</Button>
            <Button size="sm" variant={sync ? 'primary' : 'secondary'} onClick={() => setSync((x) => !x)}><Activity className="size-4" />{t('Sync status')}</Button>
            <Button size="sm" variant="secondary" loading={act.isPending && act.variables === 'pull'} onClick={() => act.mutate('pull')}><RefreshCw className="size-4" />{t('Pull now')}</Button>
          </>}
          {kind === 'api' && <Button size="sm" variant="secondary" onClick={() => act.mutate('token')}>{d.has_token ? t('New token') : t('Create token')}</Button>}
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-xl border border-line px-3 py-1.5 text-sm hover:bg-surface">
            <Upload className="size-4" />{up.isPending ? t('Importing…') : t('Import log file')}
            <input type="file" className="hidden" accept=".dat,.txt,.csv" onChange={(e) => { const f = e.target.files?.[0]; if (f) up.mutate(f); e.target.value = '' }} />
          </label>
        </div>
      )}
      {terminals.length > 0 && (
        <div className="mt-3 border-t border-line pt-3">
          <div className="mb-2 text-sm font-medium">{t('Terminals')} ({terminals.length})</div>
          <Table head={[t('Include'), t('Terminal'), t('Status'), t('Branch'), t('Last punch'), t('Punches (24 h)'), t('Unmatched'), '']}>
            {terminals.map((x) => (
              <tr key={x.name} className={clsx(!Number(x.enabled) && 'opacity-60')}>
                <td><input type="checkbox" className="size-4 accent-[var(--color-brand)]" disabled={!can || include.isPending} checked={!!Number(x.enabled)}
                  onChange={(e) => include.mutate({ name: x.name, on: e.target.checked })} aria-label={t('Include')} /></td>
                <td><div className="font-medium">{x.location && x.location !== d.location ? x.location : x.device_name}</div><div className="text-xs text-muted">SN {x.serial_number}{x.last_ip ? ` · ${x.last_ip}` : ''}{x.model ? ` · ${x.model}` : ''}</div></td>
                <td><Badge tone={STATUS_TONE[x.status] ?? 'gray'}>{t(x.status)}</Badge>{!Number(x.source_active ?? 1) && <div className="mt-0.5 text-[11px] text-muted">{t('Inactive in the source')}</div>}</td>
                <td>{x.branch || <span className="text-muted">—</span>}</td>
                <td>{x.last_punch ? fmtDateTime(x.last_punch, lang) : '—'}</td>
                <td>{x.punches_24h}</td>
                <td className={clsx(x.unmatched && 'text-amber-700')}>{x.unmatched}</td>
                <td>{can && onEditTerminal && <Button size="sm" variant="ghost" onClick={() => onEditTerminal(x)} aria-label={t('Edit')}><Pencil className="size-4" /></Button>}</td>
              </tr>
            ))}
          </Table>
        </div>
      )}
      {sync && <SyncPanel device={d} can={can} />}
      {match && <MatchPeople device={d} onClose={() => setMatch(false)} />}
      {setup && <DbSetup device={d} onClose={() => setSetup(false)} />}
      {enrol && <Enrolment device={d} onClose={() => setEnrol(false)} onQueued={() => { setEnrol(false); setMsg(t('Command queued; the device picks it up within a minute.')) }} />}
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
              <td><Badge tone={r.status === 'Imported' ? 'green' : r.status === 'Unmatched' ? 'amber' : r.status === 'Error' ? 'red' : 'gray'}>{t(r.status)}</Badge>{r.message && r.status !== 'Imported' && <div className="text-xs text-muted">{r.message}</div>}{!!r.outside_branch && <div className="text-xs text-amber-700">{t('Other branch')}</div>}</td>
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

function MarkingStrip({ can }: { can: boolean }) {
  const { t, lang } = useI18n()
  const qc = useQueryClient()
  const q = useQuery<any>({ queryKey: ['attendance-marking'], queryFn: api.attendanceMarking })
  const run = useMutation({ mutationFn: api.markAttendanceNow, onSuccess: () => qc.invalidateQueries({ queryKey: ['attendance-marking'] }) })
  if (!q.data) return null
  const m = q.data
  const week = Object.entries(m.week ?? {}).map(([k, n]) => `${t(k)} ${n}`).join(' · ')
  return (
    <div className={clsx('flex flex-wrap items-center gap-3 rounded-xl border p-3 text-sm', m.enabled ? 'border-brand/20 bg-brand-50' : 'border-amber-200 bg-amber-50')}>
      <CalendarCheck className="size-5 shrink-0 text-brand" />
      <div className="min-w-0 flex-1">
        <div className="font-medium">{m.enabled ? t('Punches become HRMS attendance every night') : t('Punches are not turned into HRMS attendance')}</div>
        <div className="text-xs text-muted">
          {m.enabled ? t('{0} employees who punch · last {1} days re-checked for late punches').replace('{0}', String(m.employees)).replace('{1}', String(m.window))
            : t('Payroll, leave and HRMS reports will not see these days. Switch it on in Settings → Attendance & check-in.')}
          {m.last?.at && ` · ${t('last run')} ${fmtDateTime(m.last.at, lang)}`}{week && ` · ${t('this week')}: ${week}`}
        </div>
        {run.data && <div className="text-xs text-emerald-700">{t('Marked')}: {run.data.marked ?? 0} · {t('Corrected')}: {run.data.corrected ?? 0} · {t('Kept (HR or request)')}: {run.data.kept ?? 0}{run.data.errors ? ` · ${t('Errors')}: ${run.data.errors}` : ''}</div>}
      </div>
      {can && m.enabled && <Button size="sm" variant="secondary" loading={run.isPending} onClick={() => run.mutate()}>{t('Mark now')}</Button>}
      {run.error && <ErrorBox error={run.error} />}
    </div>
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
        actions={d.can_edit ? <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setEdit({ ...BLANK, connection: DB, db_type: 'SQL Server', db_preset: 'ADMS (CheckInOut + EmpDetails)', match_by: 'National ID / Iqama', offline_alert_hours: 2, name: undefined })}><Plus className="size-4" />{t('Connect attendance database')}</Button>
          <Button onClick={() => setEdit(null)}><Plus className="size-4" />{t('Add device')}</Button></div> : undefined} />
      <MarkingStrip can={d.can_edit} />
      <Tabs value={tab} onChange={setTab} tabs={[{ value: 'devices', label: t('Devices') },
        { value: 'punches', label: t('Punches') },
        { value: 'unmatched', label: t('Unmatched users'), badge: d.totals.Unmatched ? <span className="rounded-full bg-amber-100 px-1.5 text-xs text-amber-800">{d.totals.Unmatched}</span> : undefined }]} />
      {tab === 'devices' && (!d.devices.length ? <Card><Empty title={t('No devices yet')} icon={<Cpu />}>{t('Add a device, or point a ZKTeco device to this server: it appears here to enable.')}</Empty></Card>
        : d.devices.filter((x: any) => !x.source_device || !d.devices.some((s: any) => s.name === x.source_device)).map((x: any) => (
          <DeviceCard key={x.name} d={x} can={d.can_edit} onEdit={() => setEdit(x)} onEditTerminal={setEdit}
            terminals={d.devices.filter((y: any) => y.source_device === x.name)} />)))}
      {tab === 'punches' && <Punches devices={d.devices} />}
      {tab === 'unmatched' && <Unmatched can={d.can_edit} />}
      {edit !== undefined && <DeviceForm device={edit} server={d.server} pushUrl={d.push_url} onClose={() => setEdit(undefined)} />}
    </div>
  )
}
