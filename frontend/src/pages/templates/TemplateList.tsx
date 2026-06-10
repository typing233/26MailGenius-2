import { useQuery } from '@tanstack/react-query';
import { Button, Card, Input, Select, Space, Table, Tag } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { templatesApi } from '../../api/templates';

export default function TemplateList() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string>();

  const { data, isLoading } = useQuery({
    queryKey: ['templates', search, category],
    queryFn: () => templatesApi.list({ search, category }).then((r) => r.data),
  });

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Subject', dataIndex: 'subject', key: 'subject', ellipsis: true },
    { title: 'Category', dataIndex: 'category', key: 'category', render: (v: string) => <Tag>{v}</Tag> },
    { title: 'Version', dataIndex: 'version', key: 'version' },
    { title: 'Active', dataIndex: 'is_active', key: 'is_active', render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? 'Yes' : 'No'}</Tag> },
    {
      title: 'Actions', key: 'actions',
      render: (_: any, record: any) => (
        <Button type="link" onClick={() => navigate(`/templates/${record.id}`)}>Edit</Button>
      ),
    },
  ];

  return (
    <Card
      title="Email Templates"
      extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/templates/new')}>New Template</Button>}
    >
      <Space style={{ marginBottom: 16 }}>
        <Input.Search placeholder="Search templates..." value={search} onChange={(e) => setSearch(e.target.value)} style={{ width: 300 }} />
        <Select placeholder="Category" allowClear style={{ width: 150 }} value={category} onChange={setCategory}
          options={[{ value: 'marketing', label: 'Marketing' }, { value: 'transactional', label: 'Transactional' }, { value: 'notification', label: 'Notification' }]}
        />
      </Space>
      <Table columns={columns} dataSource={data?.items || []} rowKey="id" loading={isLoading} pagination={{ total: data?.total, pageSize: 20 }} />
    </Card>
  );
}
