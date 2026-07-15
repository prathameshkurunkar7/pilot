import { apiUrl, request } from './client'

export const setupApi = {
  bootstrap: () => request.get('bootstrap').json(),
  config: () => request.get('setup/config').json(),
  branches: () => request.get('setup/branches').json(),
  validateMariadb: (json) => request.post('setup/validate-mariadb', { json }).json(),
  validatePostgres: (json) => request.post('setup/validate-postgres', { json }).json(),
  save: (json) => request.post('setup/save', { json }).json(),
  start: () => request.post('setup/start').json(),
  finish: () => request.post('setup/finish').json(),
  streamUrl: (taskId) => apiUrl(`tasks/${taskId}/events`),
}
