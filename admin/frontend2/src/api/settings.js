import { request } from './client'

export const settingsApi = {
  get: () => request.get('settings/').json(),
}
