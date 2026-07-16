import { request } from './client'

export const monitorApi = {
  stats: () => request.get('stats').json(),
  history: (window) => request.get('monitor-history', { searchParams: { window } }).json(),
  systemInfo: () => request.get('system-info').json(),
  wafAnalytics: (window) => request.get('waf-analytics', { searchParams: { window } }).json(),
}
