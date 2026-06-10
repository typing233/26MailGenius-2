import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Input, message, Popconfirm, Space, Table, Tag } from 'antd';
import { suppressionApi } from '../../api/services';

export default function SuppressionList() {
  const queryClient = useQueryClient();
  const [newEmail, setNewEmail] = useState('');

  const { data, isLoading } = useQuery({
    queryKey: ['suppression'],
    queryFn: () => suppressionApi.list().then((r) => r.data),
  });

  const addMutation = useMutation({
    mutationFn: () => suppressionApi.add(newEmail, 'manual'),
    onSuccess: () => { message.success('Added'); setNewEmail(''); queryClient.invalidateQueries({ queryKey: ['suppression'] }); },
    onError: (e: any) => message.error(e.response?.data?.detail || 'Failed'),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => suppressionApi.remove(id),
    onSuccess: () => { message.success('Removed'); queryClient.invalidateQueries({ queryKey: ['suppression'] }); },
  });

  const columns = [
    { title: 'Email', dataIndex: 'email', key: 'email' },
    { title: 'Reason', dataIndex: 'reason', key: 'reason', render: (v: string) => <Tag>{v}</Tag> },
    { title: 'Source', dataIndex: 'source', key: 'source' },
    { title: 'Suppressed At', dataIndex: 'suppressed_at', key: 'suppressed_at', render: (v: string) => new Date(v).toLocaleString() },
    {
      title: 'Actions', key: 'actions',
      render: (_: any, record: any) => (
        <Popconfirm title="Remove suppression?" onConfirm={() => removeMutation.mutate(record.id)}>
          <Button size="small" danger>Remove</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <Card title="Suppression List">
      <Space style={{ marginBottom: 16 }}>
        <Input placeholder="email@example.com" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} style={{ width: 300 }} />
        <Button type="primary" onClick={() => addMutation.mutate()} disabled={!newEmail} loading={addMutation.isPending}>Add to Suppression</Button>
      </Space>
      <Table columns={columns} dataSource={data?.items || []} rowKey="id" loading={isLoading} pagination={{ total: data?.total, pageSize: 50 }} />
    </Card>
  );
}
