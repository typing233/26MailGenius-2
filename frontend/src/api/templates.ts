import client from './client';

export const templatesApi = {
  list: (params?: { category?: string; search?: string; offset?: number; limit?: number }) =>
    client.get('/templates', { params }),
  get: (id: string) => client.get(`/templates/${id}`),
  create: (data: any) => client.post('/templates', data),
  update: (id: string, data: any) => client.put(`/templates/${id}`, data),
  delete: (id: string) => client.delete(`/templates/${id}`),
  preview: (id: string, variables: Record<string, any>) =>
    client.post(`/templates/${id}/preview`, { variables }),
  validate: (id: string) => client.post(`/templates/${id}/validate`),
  renderTest: (data: { html_body: string; variables: Record<string, any> }) =>
    client.post('/templates/render-test', data),
  getVersions: (id: string) => client.get(`/templates/${id}/versions`),
  restoreVersion: (id: string, version: number) =>
    client.post(`/templates/${id}/versions/${version}/restore`),
};
