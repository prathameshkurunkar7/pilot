import { request } from './client'

export const appsApi = {
  registry: () => request.get('apps/registry').json(),
  installed: () => request.get('apps/').json(),
}
