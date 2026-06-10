import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, message, Space, Table, Tag } from 'antd';
import { deadLetterApi } from '../../api/services';

export default function DeadLetterQueue() {
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ['dead-letter'],
    queryFn: () => deadLetterApi.list().then((r) => r.data),
    refetchInterval: 30000,
  });

  const retryMutation = useMutation({
    mutationFn: (id: string) => deadLetterApi.retry(id),
    onSuccess: () => { message.success('Retry queued'); queryClient.invalidateQueries({ queryKey: ['dead-letter'] }); },
  });

  const skipMutation = useMutation({
    mutationFn: (id: string) => deadLetterApi.skip(id),
    onSuccess: () => { message.success('Skipped'); queryClient.invalidateQueries({ queryKey: ['dead-letter'] }); },
  });

  const batchRetryMutation = useMutation({
    mutationFn: () => deadLetterApi.batchRetry(),
    onSuccess: (res) => { message.success(res.data.message); queryClient.invalidateQueries({ queryKey: ['dead-letter'] }); },
  });

  const columns = [
    { title: 'Campaign', dataIndex: 'campaign_id', key: 'campaign_id', ellipsis: true },
    { title: 'Subscriber', dataIndex: 'subscriber_id', key: 'subscriber_id', ellipsis: true },
    { title: 'Error', dataIndex: 'final_error', key: 'final_error', ellipsis: true },
    { title: 'Moved At', dataIndex: 'moved_at', key: 'moved_at', render: (v: string) => new Date(v).toLocaleString() },
    {
      title: 'Actions', key: 'actions',
      render: (_: any, record: any) => (
        <Space>
          <Button size="small" type="primary" onClick={() => retryMutation.mutate(record.id)}>Retry</Button>
          <Button size="small" onClick={() => skipMutation.mutate(record.id)}>Skip</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="Dead Letter Queue"
      extra={<Button type="primary" danger onClick={() => batchRetryMutation.mutate()} loading={batchRetryMutation.isPending}>Batch Retry All</Button>}
    >
      <p><Tag color="error">{data?.total || 0} unresolved</Tag></p>
      <Table columns={columns} dataSource={data?.items || []} rowKey="id" loading={isLoading} pagination={{ total: data?.total, pageSize: 20 }} />
    </Card>
  );
}
