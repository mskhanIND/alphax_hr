import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ChevronDown } from 'lucide-react'
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { Input } from './ui'

/** Text input with server-side suggestions for a Frappe Link field. The list opens right under the field (the
 * browser's own suggestion list opens beside it in some windows) and works with the keyboard. It is drawn on top
 * of the page (not inside the field's box), so a dialog or card that scrolls cannot hide it; near the bottom of
 * the window it opens upwards. */
export function LinkInput({ doctype, value, onChange, onSelect, disabled, required, source = 'hr', placeholder }: { doctype: string; value: string; onChange: (v: string) => void; onSelect?: (v: string) => void; disabled?: boolean; required?: boolean; source?: 'hr' | 'ess'; placeholder?: string }) {
  const { t } = useI18n()
  const [txt, setTxt] = useState(value ?? '')
  const [debounced, setDebounced] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const [pos, setPos] = useState<{ left: number; width: number; top?: number; bottom?: number; maxHeight: number } | null>(null)
  useEffect(() => setTxt(value ?? ''), [value])
  useEffect(() => { const h = setTimeout(() => setDebounced(txt), 200); return () => clearTimeout(h) }, [txt])
  useEffect(() => {
    const close = (e: MouseEvent) => {
      const n = e.target as Node
      if (box.current && !box.current.contains(n) && !(list.current && list.current.contains(n))) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  useLayoutEffect(() => {
    if (!open) return
    const place = () => {
      const r = box.current?.getBoundingClientRect()
      if (!r) return
      const below = window.innerHeight - r.bottom - 8
      const above = r.top - 8
      const up = below < 200 && above > below
      setPos({ left: r.left, width: r.width, maxHeight: Math.min(256, up ? above : below),
        ...(up ? { bottom: window.innerHeight - r.top + 4 } : { top: r.bottom + 4 }) })
    }
    place()
    window.addEventListener('scroll', place, true)  // any scrolling parent (a dialog body) moves the field
    window.addEventListener('resize', place)
    return () => { window.removeEventListener('scroll', place, true); window.removeEventListener('resize', place) }
  }, [open])
  const q = useQuery({ queryKey: ['lookup', source, doctype, open ? debounced : '__closed'], enabled: !disabled && open, staleTime: 60_000,
    queryFn: () => (source === 'ess' ? api.essLookup : api.lookup)(doctype, txt === value ? '' : debounced) })
  const items: any[] = q.data ?? []
  // with onSelect the picked value is handed over and the field is cleared for the next one (lists of people)
  const pick = (v: string) => { if (onSelect) { setTxt(''); onSelect(v) } else { setTxt(v); onChange(v) } setOpen(false) }
  return (
    <div ref={box} className="relative">
      <Input value={txt} placeholder={placeholder} disabled={disabled} required={required} autoComplete="off" role="combobox" aria-expanded={open}
        className="pe-8"
        onFocus={() => setOpen(true)}
        onChange={(e) => { setTxt(e.target.value); onChange(e.target.value); setOpen(true); setActive(0) }}
        onKeyDown={(e) => {
          if (!open && (e.key === 'ArrowDown' || e.key === 'Enter')) { setOpen(true); return }
          if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)) }
          else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
          else if (e.key === 'Enter' && items[active]) { e.preventDefault(); pick(items[active].value) }
          else if (e.key === 'Escape' && open) { e.stopPropagation(); setOpen(false) }  // close the list, not the dialog around it
          else if (e.key === 'Tab') setOpen(false)
        }} />
      {!disabled && <button type="button" tabIndex={-1} aria-label={t('Show list')} onClick={() => setOpen((o) => !o)}
        className="absolute inset-y-0 end-0 flex w-8 items-center justify-center text-muted"><ChevronDown className="size-4" /></button>}
      {open && !disabled && pos && createPortal(
        <ul ref={list} role="listbox" style={{ position: 'fixed', left: pos.left, width: pos.width, top: pos.top, bottom: pos.bottom, maxHeight: pos.maxHeight }}
          className="z-[1000] overflow-auto rounded-xl border border-line bg-white py-1 shadow-lg">
          {q.isLoading ? <li className="px-3 py-2 text-sm text-muted">…</li>
            : !items.length ? <li className="px-3 py-2 text-sm text-muted">{t('Nothing found')}</li>
            : items.map((o, i) => (
              <li key={o.value} role="option" aria-selected={i === active} onMouseDown={(e) => { e.preventDefault(); pick(o.value) }} onMouseEnter={() => setActive(i)}
                className={clsx('cursor-pointer px-3 py-1.5 text-sm', i === active ? 'bg-brand-50 text-brand' : o.value === value ? 'font-medium' : '')}>
                <div className="truncate">{o.label || o.value}</div>
                {o.description && <div className="truncate text-xs text-muted">{o.description}</div>}
              </li>))}
        </ul>, document.body)}
    </div>
  )
}
