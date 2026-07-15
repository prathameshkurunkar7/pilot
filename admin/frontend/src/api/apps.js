import { request } from './client'

export const appsApi = {
  marketplace: () => request.get('marketplace/apps').json(),
  installed: () => request.get('apps').json(),
  fetchUpdates: () => request.post('apps/fetch').json(),
  add: (payload) => request.post('apps', { json: payload }).json(),
}
