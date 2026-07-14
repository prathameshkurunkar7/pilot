import { request } from './client'

export const settingsApi = {
  get: () => request.get('settings/').json(),
  update: (data) => request.patch('settings/', { json: data }).json(),
  myIp: () => request.get('settings/my-ip').json(),
  audit: {
    types: () => request.get('settings/audit/types').json(),
    log: (params = {}) => request.get('settings/audit/log', { searchParams: params }).json(),
  },
}
