import { request } from './client'

export const monitorApi = {
  stats: () => request.get('metrics').json(),
  history: (window) => request.get('monitor/history', { searchParams: { window } }).json(),
  systemInfo: () => request.get('system').json(),
}
