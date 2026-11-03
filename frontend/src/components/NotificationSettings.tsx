import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, BellOff } from 'lucide-react'
import { currentSubscription, disablePush, enablePush, pushSupported, sendTestPush } from '../lib/push'
import { isIOS, isStandalone } from '../lib/pwa'
import { useI18n } from '../lib/i18n'
import { Button, Card, ErrorBox } from './ui'

/** Turn phone notifications on/off for this device. */
export function NotificationSettings() {
  const { t } = useI18n()
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['push-sub'], queryFn: async () => !!(await currentSubscription()) })
  const on = useMutation({ mutationFn: enablePush, onSuccess: () => qc.invalidateQueries({ queryKey: ['push-sub'] }) })
  const off = useMutation({ mutationFn: disablePush, onSuccess: () => qc.invalidateQueries({ queryKey: ['push-sub'] }) })
  const testM = useMutation({ mutationFn: sendTestPush })
  const iosNeedsInstall = isIOS() && !isStandalone()
  return (
    <Card title={t('Notifications on this device')} subtitle={t('Approvals, decisions on your requests, messages from HR and announcements')}>
      {!pushSupported() || iosNeedsInstall ? (
        <p className="text-sm text-muted">{iosNeedsInstall ? t('On iPhone, add this app to the home screen (Share → Add to Home Screen), open it from there, then turn notifications on.') : t('This browser cannot show notifications.')}</p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          {q.data ? (
            <>
              <span className="flex items-center gap-1.5 text-sm text-emerald-700"><Bell className="size-4" />{t('On')}</span>
              <Button size="sm" variant="secondary" loading={testM.isPending} onClick={() => testM.mutate()}>{t('Send a test')}</Button>
              <Button size="sm" variant="secondary" loading={off.isPending} onClick={() => off.mutate()}><BellOff className="size-4" />{t('Turn off')}</Button>
            </>
          ) : (
            <Button size="sm" loading={on.isPending} onClick={() => on.mutate()}><Bell className="size-4" />{t('Turn on notifications')}</Button>
          )}
        </div>
      )}
      {(on.error || off.error || testM.error) && <div className="mt-2"><ErrorBox error={on.error || off.error || testM.error} /></div>}
    </Card>
  )
}
