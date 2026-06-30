import { request } from './client'

export const sitesApi = {
  list: () => request.get('sites/').json(),
  detail: (name) => request.get(`sites/${encodeURIComponent(name)}`).json(),
  apps: (name) => request.get(`sites/${encodeURIComponent(name)}/apps`).json(),
  backups: (name) => request.get(`sites/${encodeURIComponent(name)}/backups`).json(),
  config: (name, config) =>
    request.patch(`sites/${encodeURIComponent(name)}/config`, { json: config }).json(),
  wildcardDomains: () => request.get('sites/wildcard-domains').json(),
  create: (payload) => request.post('sites/create', { json: payload }).json(),
  createFromUpload: (formData) =>
    request.post('sites/create-from-upload', { body: formData }).json(),
  login: (name) => request.post(`sites/${encodeURIComponent(name)}/login`).json(),
  backup: (name) => request.post(`sites/${encodeURIComponent(name)}/backup`).json(),
  drop: (name) => request.post(`sites/${encodeURIComponent(name)}/drop`).json(),
  reinstall: (name, adminPassword) =>
    request
      .post(`sites/${encodeURIComponent(name)}/reinstall`, {
        json: { admin_password: adminPassword },
      })
      .json(),
  installApp: (name, app) =>
    request.post(`sites/${encodeURIComponent(name)}/install-app`, { json: { app } }).json(),
  uninstallApp: (name, app) =>
    request.post(`sites/${encodeURIComponent(name)}/uninstall-app`, { json: { app } }).json(),
  forceUninstallApp: (name, app) =>
    request
      .post(`sites/${encodeURIComponent(name)}/force-uninstall-app`, {
        json: { app },
      })
      .json(),
  forceDrop: (name) => request.post(`sites/${encodeURIComponent(name)}/force-drop`).json(),
  enableSsl: (name, email) =>
    request
      .post(`sites/${encodeURIComponent(name)}/enable-ssl`, {
        json: email ? { email } : {},
      })
      .json(),
  domains: (name) => request.get(`sites/${encodeURIComponent(name)}/domains`).json(),
  addDomain: (name, domain) =>
    request.post(`sites/${encodeURIComponent(name)}/domains`, { json: { domain } }).json(),
  removeDomain: (name, domain) =>
    request
      .delete(`sites/${encodeURIComponent(name)}/domains`, {
        json: { domain },
      })
      .json(),
  setPrimaryDomain: (name, domain) =>
    request
      .post(`sites/${encodeURIComponent(name)}/domains/primary`, {
        json: { domain },
      })
      .json(),
  dnsRecords: (name, domain) =>
    request
      .post(`sites/${encodeURIComponent(name)}/domains/dns-records`, {
        json: { domain },
      })
      .json(),
  backupSchedule: (name) => request.get(`sites/${encodeURIComponent(name)}/backup-schedule`).json(),
  setBackupSchedule: (name, schedule) =>
    request
      .post(`sites/${encodeURIComponent(name)}/backup-schedule`, {
        json: { schedule },
      })
      .json(),
  removeBackupSchedule: (name) =>
    request.delete(`sites/${encodeURIComponent(name)}/backup-schedule`).json(),
  downloadBackup: (name, filename) =>
    `/api/sites/${encodeURIComponent(name)}/backups/download?filename=${encodeURIComponent(filename)}`,
}
