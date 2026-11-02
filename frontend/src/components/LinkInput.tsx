import { useQuery } from '@tanstack/react-query'
import { useEffect, useId, useState } from 'react'
import { api } from '../lib/api'
import { Input } from './ui'

/** Text input with server-side suggestions for a Frappe Link field. */
export function LinkInput({ doctype, value, onChange, disabled, required }: { doctype: string; value: string; onChange: (v: string) => void; disabled?: boolean; required?: boolean }) {
  const id = useId()
  const [txt, setTxt] = useState(value ?? '')
  const [debounced, setDebounced] = useState('')
  useEffect(() => setTxt(value ?? ''), [value])
  useEffect(() => { const h = setTimeout(() => setDebounced(txt), 250); return () => clearTimeout(h) }, [txt])
  const q = useQuery({ queryKey: ['lookup', doctype, debounced], queryFn: () => api.lookup(doctype, debounced), enabled: !disabled, staleTime: 60_000 })
  return (
    <>
      <Input list={id} value={txt} disabled={disabled} required={required} autoComplete="off"
        onChange={(e) => { setTxt(e.target.value); onChange(e.target.value) }} />
      <datalist id={id}>
        {(q.data ?? []).map((o) => <option key={o.value} value={o.value}>{o.description || o.label || ''}</option>)}
      </datalist>
    </>
  )
}
