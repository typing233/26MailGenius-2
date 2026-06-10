import client from './client';

export const campaignsApi = {
  list: (params?: { status?: string; offset?: number; limit?: number }) =>
    client.get('/campaigns', { params }),
  get: (id: string) => client.get(`/campaigns/${id}`),
  create: (data: any) => client.post('/campaigns', data),
  update: (id: string, data: any) => client.put(`/campaigns/${id}`, data),
  delete: (id: string) => client.delete(`/campaigns/${id}`),
  schedule: (id: string, data: { scheduled_at: string; timezone: string }) =>
    client.post(`/campaigns/${id}/schedule`, data),
  sendNow: (id: string) => client.post(`/campaigns/${id}/send-now`),
  pause: (id: string) => client.post(`/campaigns/${id}/pause`),
  resume: (id: string) => client.post(`/campaigns/${id}/resume`),
  cancel: (id: string) => client.post(`/campaigns/${id}/cancel`),
  testSend: (id: string, data: { to_emails: string[]; variables?: Record<string, any> }) =>
    client.post(`/campaigns/${id}/test-send`, data),
  getProgress: (id: string) => client.get(`/campaigns/${id}/progress`),
  getStats: (id: string) => client.get(`/campaigns/${id}/stats`),
  getErrors: (id: string, params?: { offset?: number; limit?: number }) =>
    client.get(`/campaigns/${id}/errors`, { params }),
  retryError: (campaignId: string, jobId: string) =>
    client.post(`/campaigns/${campaignId}/errors/${jobId}/retry`),
};
