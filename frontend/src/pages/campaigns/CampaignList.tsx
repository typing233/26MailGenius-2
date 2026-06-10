import { useQuery } from '@tanstack/react-query';
import { Button, Card, Space, Table, Tag, Select } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { campaignsApi } from '../../api/campaigns';

const STATUS_COLORS: Record<string, string> = {
  draft: 'default', scheduled: 'blue', sending: 'processing', paused: 'warning',
  completed: 'success', cancelled: 'error', failed: 'error',
};

export default function CampaignList() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<string>();

  const { data, isLoading } = useQuery({
    queryKey: ['campaigns', status],
    queryFn: () => campaignsApi.list({ status }).then((r) => r.data),
  });

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Status', dataIndex: 'status', key: 'status', render: (v: string) => <Tag color={STATUS_COLORS[v]}>{v}</Tag> },
    { title: 'Recipients', dataIndex: 'total_recipients', key: 'total_recipients' },
    { title: 'Sent', dataIndex: 'sent_count', key: 'sent_count' },
    { title: 'Opens', dataIndex: 'opened_count', key: 'opened_count' },
    { title: 'Clicks', dataIndex: 'clicked_count', key: 'clicked_count' },
    { title: 'Created', dataIndex: 'created_at', key: 'created_at', render: (v: string) => new Date(v).toLocaleDateString() },
    {
      title: 'Actions', key: 'actions',
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" onClick={() => navigate(`/campaigns/${record.id}`)}>View</Button>
          <Button type="link" onClick={() => navigate(`/campaigns/${record.id}/report`)}>Report</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card
      title="Campaigns"
      extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/campaigns/new')}>New Campaign</Button>}
    >
      <Space style={{ marginBottom: 16 }}>
        <Select placeholder="Filter by status" allowClear style={{ width: 150 }} value={status} onChange={setStatus}
          options={['draft', 'scheduled', 'sending', 'paused', 'completed', 'cancelled', 'failed'].map((s) => ({ value: s, label: s }))}
        />
      </Space>
      <Table columns={columns} dataSource={data?.items || []} rowKey="id" loading={isLoading} pagination={{ total: data?.total, pageSize: 20 }} />
    </Card>
  );
}
