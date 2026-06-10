import { useQuery } from '@tanstack/react-query';
import { Button, Card, Space, Table, Tag } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { segmentsApi } from '../../api/services';

export default function SegmentList() {
  const navigate = useNavigate();
  const { data, isLoading } = useQuery({
    queryKey: ['segments'],
    queryFn: () => segmentsApi.list().then((r) => r.data),
  });

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Description', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: 'Conditions', dataIndex: 'conditions', key: 'conditions', render: (v: any[]) => <Tag>{v.length} rules</Tag> },
    { title: 'Est. Count', dataIndex: 'estimated_count', key: 'estimated_count', render: (v: number) => v ?? '-' },
    {
      title: 'Actions', key: 'actions',
      render: (_: any, record: any) => (
        <Space>
          <Button type="link" onClick={() => navigate(`/segments/${record.id}`)}>Edit</Button>
          <Button type="link" onClick={() => segmentsApi.evaluate(record.id)}>Evaluate</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card title="Segments" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/segments/new')}>New Segment</Button>}>
      <Table columns={columns} dataSource={data || []} rowKey="id" loading={isLoading} />
    </Card>
  );
}
