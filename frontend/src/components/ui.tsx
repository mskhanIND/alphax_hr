import clsx from 'clsx'
import { Loader2, X } from 'lucide-react'
import { useEffect, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from 'react'
import { useI18n } from '../lib/i18n'
import { initials } from '../lib/format'

export function Card({ className, children, title, action, subtitle }: { className?: string; children: ReactNode; title?: ReactNode; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <section className={clsx('rounded-2xl border border-line bg-white p-4 shadow-sm sm:p-5', className)}>
      {(title || action) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-base font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  )
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; loading?: boolean; size?: 'sm' | 'md' }
export function Button({ variant = 'primary', loading, size = 'md', className, children, disabled, ...rest }: BtnProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        'inline-flex items-center justify-center gap-2 rounded-xl font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand disabled:cursor-not-allowed disabled:opacity-50',
        size === 'sm' ? 'h-8 px-3 text-sm' : 'h-10 px-4 text-sm',
        variant === 'primary' && 'bg-brand text-white hover:bg-brand-700',
        variant === 'secondary' && 'border border-line bg-white text-ink hover:bg-surface',
        variant === 'ghost' && 'text-ink hover:bg-surface',
        variant === 'danger' && 'bg-red-600 text-white hover:bg-red-700',
        className,
      )}
    >
      {loading && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  )
}

const tones: Record<string, string> = {
  green: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  amber: 'bg-amber-50 text-amber-800 ring-amber-200',
  red: 'bg-red-50 text-red-700 ring-red-200',
  blue: 'bg-sky-50 text-sky-700 ring-sky-200',
  gray: 'bg-slate-100 text-slate-700 ring-slate-200',
}
export function Badge({ tone = 'gray', children }: { tone?: keyof typeof tones | string; children: ReactNode }) {
  return <span className={clsx('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset', tones[tone] ?? tones.gray)}>{children}</span>
}

export function statusTone(status?: string | null) {
  const s = (status ?? '').toLowerCase()
  if (/approved|present|submitted|paid|valid|active|completed/.test(s)) return 'green'
  if (/reject|absent|cancel|expired|left/.test(s)) return 'red'
  if (/open|pending|draft|half|within_30|late/.test(s)) return 'amber'
  if (/leave|within_60|within_90/.test(s)) return 'blue'
  return 'gray'
}

export function StatusBadge({ status }: { status?: string | null }) {
  const { t } = useI18n()
  if (!status) return null
  return <Badge tone={statusTone(status)}>{t(status)}</Badge>
}

/** A number tile. With ``onClick`` it is a filter: clicking shows the records behind the number (click again to clear). */
export function Stat({ label, value, hint, icon, tone = 'brand', onClick, active }: { label: string; value: ReactNode; hint?: ReactNode; icon?: ReactNode; tone?: 'brand' | 'amber' | 'red' | 'blue'; onClick?: () => void; active?: boolean }) {
  const Tag: any = onClick ? 'button' : 'div'
  return (
    <Tag type={onClick ? 'button' : undefined} onClick={onClick} aria-pressed={onClick ? !!active : undefined}
      className={clsx('rounded-2xl border bg-white p-4 text-start shadow-sm', onClick && 'cursor-pointer transition hover:border-brand/40 hover:shadow-md',
        active ? 'border-brand ring-2 ring-brand/30' : 'border-line')}>
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted">{label}</span>
        {icon && (
          <span className={clsx('grid size-8 place-items-center rounded-lg',
            tone === 'brand' && 'bg-brand-50 text-brand', tone === 'amber' && 'bg-amber-50 text-amber-700',
            tone === 'red' && 'bg-red-50 text-red-700', tone === 'blue' && 'bg-sky-50 text-sky-700')}>{icon}</span>
        )}
      </div>
      <div className="mt-2 text-2xl font-semibold tabular-nums text-ink">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </Tag>
  )
}

/** The bar under filter tiles: what is shown and a way back to everything. */
export function FilterNote({ label, count, onClear }: { label: ReactNode; count: number; onClear: () => void }) {
  const { t } = useI18n()
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl bg-brand-50 px-3 py-2 text-sm text-brand">
      <span><b>{label}</b> · {count} {t(count === 1 ? 'employee' : 'employees')}</span>
      <button type="button" onClick={onClear} className="ms-auto rounded-lg px-2 py-0.5 text-xs font-medium hover:bg-white">{t('Show all')}</button>
    </div>
  )
}

export function Spinner({ label }: { label?: string }) {
  const { t } = useI18n()
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-muted" role="status">
      <Loader2 className="size-5 animate-spin" /> {label ?? t('Loading…')}
    </div>
  )
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n()
  const message = error instanceof Error ? error.message : String(error)
  // Frappe often returns several messages (e.g. one per missing field): show them as a list.
  const parts = message.split(/\n|(?=Error: )/).map((p) => p.replace(/^Error:\s*/, '').trim()).filter(Boolean)
  const missing = parts.map((p) => p.match(/^Value missing for [^:]+:\s*(.+)$/)?.[1]).filter(Boolean) as string[]
  return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">
      <p className="font-medium">{missing.length ? t('Please fill in') : t('Something went wrong')}</p>
      {missing.length ? (
        <ul className="mt-2 grid list-disc gap-x-6 gap-y-0.5 ps-5 sm:grid-cols-2">{missing.map((m) => <li key={m}>{m}</li>)}</ul>
      ) : parts.length > 1 ? (
        <ul className="mt-2 list-disc space-y-0.5 ps-5">{parts.map((p, i) => <li key={i}>{p}</li>)}</ul>
      ) : (
        <p className="mt-1">{message}</p>
      )}
      {onRetry && <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>{t('Try again')}</Button>}
    </div>
  )
}

export function Empty({ title, children, icon }: { title: string; children?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-center">
      {icon && <div className="grid size-12 place-items-center rounded-full bg-brand-50 text-brand">{icon}</div>}
      <p className="font-medium text-ink">{title}</p>
      {children && <p className="max-w-sm text-sm text-muted">{children}</p>}
    </div>
  )
}

export function Field({ label, children, hint, error }: { label: string; children: ReactNode; hint?: string; error?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-ink">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-700">{error}</span>}
    </label>
  )
}

const inputCls = 'h-10 w-full rounded-xl border border-line bg-white px-3 text-sm text-ink outline-none transition placeholder:text-slate-400 focus:border-brand focus:ring-2 focus:ring-brand/20 disabled:bg-surface'
export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={clsx(sized(props.className), props.className)} />
}
/** The base input classes, without w-full when the caller sets its own width. */
function sized(className?: string) {
  return /(^|\s)(w-|min-w-|max-w-)/.test(className ?? '') ? inputCls.replace('w-full ', '') : inputCls
}

export function Select({ children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={clsx(sized(props.className), props.className)}>{children}</select>
}
export function Textarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={clsx(inputCls, 'h-auto min-h-20 py-2', props.className)} />
}

export function Modal({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: ReactNode; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-0 sm:items-center sm:p-4" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" className={clsx('max-h-[92vh] w-full overflow-auto rounded-t-2xl bg-white shadow-xl sm:rounded-2xl', wide ? 'sm:max-w-3xl' : 'sm:max-w-lg')} onMouseDown={(e) => e.stopPropagation()}>
        <div className="sticky top-0 flex items-center justify-between border-b border-line bg-white px-5 py-3">
          <h3 className="font-semibold text-ink">{title}</h3>
          <button onClick={onClose} className="rounded-lg p-1 text-muted hover:bg-surface" aria-label="Close"><X className="size-5" /></button>
        </div>
        <div className="p-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>
  )
}

export function Avatar({ name, image, size = 40 }: { name?: string | null; image?: string | null; size?: number }) {
  if (image) return <img src={image} alt="" className="rounded-full object-cover" style={{ width: size, height: size }} />
  return (
    <span className="grid shrink-0 place-items-center rounded-full bg-brand-50 font-semibold text-brand" style={{ width: size, height: size, fontSize: size / 2.8 }}>
      {initials(name)}
    </span>
  )
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  )
}

export function Table({ head, children }: { head: ReactNode[]; children: ReactNode }) {
  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-line text-start text-xs uppercase tracking-wide text-muted">
            {head.map((h, i) => <th key={i} className="px-3 py-2 text-start font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">{children}</tbody>
      </table>
    </div>
  )
}

/** Segmented tabs. */
export function Tabs({ value, onChange, tabs, className }: { value: string; onChange: (v: string) => void; tabs: { value: string; label: ReactNode; badge?: ReactNode }[]; className?: string }) {
  return (
    <div className={clsx('flex gap-1 self-start overflow-x-auto rounded-xl bg-surface p-1 text-sm', className)} role="tablist">
      {tabs.map((x) => (
        <button key={x.value} role="tab" aria-selected={value === x.value} onClick={() => onChange(x.value)}
          className={clsx('flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5', value === x.value ? 'bg-white font-medium text-brand shadow-sm' : 'text-muted hover:text-ink')}>
          {x.label}{x.badge}
        </button>
      ))}
    </div>
  )
}
