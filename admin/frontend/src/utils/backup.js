// Shared backup schedule/retention formatting for the site Backups tab.

const WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

export function formatHour(h) {
  if (h === 0) return '12:00 AM'
  if (h < 12) return `${h}:00 AM`
  if (h === 12) return '12:00 PM'
  return `${h - 12}:00 PM`
}

export function cronToLabel(cron) {
  if (!cron) return ''
  const [, hour, dom, , dow] = cron.split(' ')
  const time = formatHour(parseInt(hour) || 0)
  if (dom !== '*') return `Monthly on day ${dom}, ${time}`
  if (dow !== '*') return `Weekly on ${WEEKDAYS[parseInt(dow)] || 'Sunday'}, ${time}`
  return `Daily at ${time}`
}

export function retentionSummary(retention) {
  if (!retention) return ''
  if (retention.scheme === 'fifo') return `keeping newest ${retention.keep_last}`
  return `keeping ${retention.keep_daily} daily · ${retention.keep_weekly} weekly · ${retention.keep_monthly} monthly · ${retention.keep_yearly} yearly`
}
