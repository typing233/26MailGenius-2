import client from './client';

export const mailingListsApi = {
  list: () => client.get('/lists'),
  get: (id: string) => client.get(`/lists/${id}`),
};

export const segmentsApi = {
  list: () => client.get('/segments'),
  get: (id: string) => client.get(`/segments/${id}`),
  create: (data: any) => client.post('/segments', data),
  update: (id: string, data: any) => client.put(`/segments/${id}`, data),
  delete: (id: string) => client.delete(`/segments/${id}`),
  evaluate: (id: string) => client.post(`/segments/${id}/evaluate`),
};

export const channelsApi = {
  list: () => client.get('/channels'),
  get: (id: string) => client.get(`/channels/${id}`),
  create: (data: any) => client.post('/channels', data),
  update: (id: string, data: any) => client.put(`/channels/${id}`, data),
  delete: (id: string) => client.delete(`/channels/${id}`),
  test: (id: string, to_email: string) => client.post(`/channels/${id}/test`, { to_email }),
  getHealth: (id: string) => client.get(`/channels/${id}/health`),
};

export const reportsApi = {
  getDashboard: () => client.get('/reports/dashboard'),
  getCampaignSummary: (id: string) => client.get(`/reports/campaigns/${id}/summary`),
  getTimeline: (id: string) => client.get(`/reports/campaigns/${id}/timeline`),
  getFunnel: (id: string) => client.get(`/reports/campaigns/${id}/funnel`),
  exportReport: (data: any) => client.post('/reports/export', data, { responseType: 'blob' }),
};

export const deadLetterApi = {
  list: (params?: { offset?: number; limit?: number }) => client.get('/dead-letter', { params }),
  get: (id: string) => client.get(`/dead-letter/${id}`),
  retry: (id: string) => client.post(`/dead-letter/${id}/retry`),
  skip: (id: string) => client.post(`/dead-letter/${id}/skip`),
  batchRetry: () => client.post('/dead-letter/batch-retry'),
};

export const suppressionApi = {
  list: (params?: { offset?: number; limit?: number }) => client.get('/suppression', { params }),
  add: (email: string, reason?: string) => client.post('/suppression', null, { params: { email, reason } }),
  remove: (id: string) => client.delete(`/suppression/${id}`),
};
