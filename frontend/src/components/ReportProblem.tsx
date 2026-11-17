import { Bug, Camera, CheckCircle2, ImagePlus, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { api, boot } from '../lib/api'
import { useI18n } from '../lib/i18n'
import { useSession } from '../lib/session'
import { recentErrors, recentPages, recordPage } from '../lib/trail'
import { Button, Field, Modal, Textarea } from './ui'

const MAX_EDGE = 1600

/** Picture of the page as the user sees it, taken before the dialog opens. JPEG, longest edge 1600px. */
async function captureScreen(): Promise<string | null> {
  try {
    const { toJpeg } = await import('html-to-image')
    const el = document.documentElement
    const w = window.innerWidth, h = window.innerHeight
    const scale = Math.min(1, MAX_EDGE / Math.max(w, h)) * Math.min(window.devicePixelRatio || 1, 1.5)
    return await toJpeg(el, {
      quality: 0.72, width: w, height: h, pixelRatio: scale, backgroundColor: '#ffffff', cacheBust: false,
      style: { transform: `translate(${-window.scrollX}px, ${-window.scrollY}px)` },
      filter: (n) => !(n instanceof HTMLElement && n.dataset.noShot === '1'),
    })
  } catch {
    return null
  }
}

function readFile(file: File): Promise<string> {
  return new Promise((ok, fail) => {
    const r = new FileReader()
    r.onload = () => ok(String(r.result))
    r.onerror = () => fail(r.error)
    r.readAsDataURL(file)
  })
}

function deviceInfo() {
  return `${navigator.userAgent} · screen ${window.innerWidth}×${window.innerHeight} · ${boot.lang}`
}

export default function ReportProblem() {
  const { t } = useI18n()
  const s = useSession()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [shot, setShot] = useState<string | null>(null)
  const [useShot, setUseShot] = useState(true)
  const [doing, setDoing] = useState('')
  const [wrong, setWrong] = useState('')
  const [err, setErr] = useState('')
  const [done, setDone] = useState<any>(null)
  const [page, setPage] = useState('')
  const [errors, setErrors] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => { recordPage(loc.pathname + loc.search) }, [loc.pathname, loc.search])

  if (!s.report_button) return null

  const start = async () => {
    setBusy(true)
    setPage(loc.pathname + loc.search + loc.hash)
    setErrors(recentErrors())
    const img = await captureScreen()
    setShot(img); setUseShot(!!img); setBusy(false)
    setDoing(''); setWrong(''); setErr(''); setDone(null); setOpen(true)
  }

  const pick = async (f?: File) => {
    if (!f) return
    if (f.size > 6 * 1024 * 1024) { setErr(t('The picture is too large (over 6 MB).')); return }
    setShot(await readFile(f)); setUseShot(true)
  }

  const send = async () => {
    if (wrong.trim().length < 3) { setErr(t('Please write what went wrong.')); return }
    setBusy(true); setErr('')
    try {
      const r = await api.reportProblem({
        went_wrong: wrong, doing, page, last_error: errors, recent_pages: recentPages(), device: deviceInfo(),
        screenshot: useShot && shot ? shot : '',
      })
      setDone(r)
    } catch (e: any) {
      setErr(e?.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button type="button" data-no-shot="1" onClick={start} disabled={busy}
        className="fixed bottom-20 end-4 z-30 flex items-center gap-2 rounded-full border border-line bg-white px-4 py-2.5 text-sm font-medium text-ink shadow-lg hover:bg-surface disabled:opacity-60 print:hidden lg:bottom-6"
        aria-label={t('Report a problem')}>
        <Bug className="size-4 text-red-600" />
        <span className="hidden sm:inline">{busy && !open ? t('Taking a picture…') : t('Report a problem')}</span>
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title={done ? t('Thank you') : t('Report a problem')}
        footer={done
          ? <><Link to="/me/reports" onClick={() => setOpen(false)} className="rounded-lg border border-line px-4 py-2 text-sm font-medium hover:bg-surface">{t('My reports')}</Link>
            <Button onClick={() => setOpen(false)}>{t('Close')}</Button></>
          : <><Button variant="secondary" onClick={() => setOpen(false)}>{t('Cancel')}</Button>
            <Button onClick={send} loading={busy}>{t('Send')}</Button></>}>
        {done ? (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <CheckCircle2 className="size-10 text-green-600" />
            <p className="font-medium">{t('Your report {0} was sent.').replace('{0}', done.name)}</p>
            <p className="text-sm text-muted">{t('The answer will appear under My reports. When it says "Fixed - please check", try again and press Pass or Fail.')}</p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <Field label={t('What went wrong?')}>
              <Textarea autoFocus rows={3} value={wrong} onChange={(e) => setWrong(e.target.value)}
                placeholder={t('e.g. I pressed Save and got "not permitted"')} />
            </Field>
            <Field label={t('What were you trying to do? (optional)')}>
              <Textarea rows={2} value={doing} onChange={(e) => setDoing(e.target.value)}
                placeholder={t('e.g. Apply annual leave for next week')} />
            </Field>
            <div className="rounded-xl border border-line p-3">
              {shot ? (
                <div className="flex items-start gap-3">
                  <img src={shot} alt="" className={`h-20 w-32 rounded border border-line object-cover object-top ${useShot ? '' : 'opacity-30'}`} />
                  <div className="flex flex-1 flex-col gap-2 text-sm">
                    <label className="flex items-center gap-2">
                      <input type="checkbox" checked={useShot} onChange={(e) => setUseShot(e.target.checked)} />
                      <span>{t('Include this picture of the page')}</span>
                    </label>
                    <button type="button" className="flex items-center gap-1 text-start text-brand hover:underline" onClick={() => fileRef.current?.click()}>
                      <ImagePlus className="size-4" />{t('Use another picture')}
                    </button>
                  </div>
                  {useShot && <button type="button" onClick={() => setUseShot(false)} className="text-muted" aria-label={t('Remove')}><X className="size-4" /></button>}
                </div>
              ) : (
                <button type="button" className="flex items-center gap-2 text-sm text-brand hover:underline" onClick={() => fileRef.current?.click()}>
                  <Camera className="size-4" />{t('Add a picture (optional)')}
                </button>
              )}
              <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => pick(e.target.files?.[0])} />
            </div>
            <details className="text-xs text-muted">
              <summary className="cursor-pointer">{t('Added automatically')}</summary>
              <ul className="mt-2 list-disc space-y-1 ps-5">
                <li>{t('Page')}: {page}</li>
                <li>{t('Site')}: {boot.site} · {t('Version')} {s.version}</li>
                <li>{t('Login')}: {s.user}</li>
                <li>{errors ? <>{t('Recent error messages')}:<pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap rounded bg-surface p-2">{errors}</pre></> : t('No error messages in the last 30 minutes')}</li>
              </ul>
            </details>
            {err && <p className="text-sm text-red-600">{err}</p>}
          </div>
        )}
      </Modal>
    </>
  )
}
