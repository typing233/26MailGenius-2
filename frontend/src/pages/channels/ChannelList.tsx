import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Form, Input, InputNumber, message, Modal, Space, Switch, Table, Tag } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { channelsApi } from '../../api/services';

export default function ChannelList() {
  const queryClient = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['channels'],
    queryFn: () => channelsApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (values: any) => channelsApi.create(values),
    onSuccess: () => { message.success('Channel created'); setModalOpen(false); form.resetFields(); queryClient.invalidateQueries({ queryKey: ['channels'] }); },
  });

  const testMutation = useMutation({
    mutationFn: ({ id, email }: { id: string; email: string }) => channelsApi.test(id, email),
    onSuccess: (res) => message.info(res.data.message),
  });

  const columns = [
    { title: 'Name', dataIndex: 'name', key: 'name' },
    { title: 'Host', dataIndex: 'host', key: 'host' },
    { title: 'Port', dataIndex: 'port', key: 'port' },
    { title: 'Active', dataIndex: 'is_active', key: 'is_active', render: (v: boolean) => <Tag color={v ? 'green' : 'red'}>{v ? 'Yes' : 'No'}</Tag> },
    { title: 'Priority', dataIndex: 'priority', key: 'priority' },
    { title: 'Failures', dataIndex: 'consecutive_failures', key: 'failures', render: (v: number) => <Tag color={v >= 5 ? 'error' : v > 0 ? 'warning' : 'success'}>{v}</Tag> },
    { title: 'Limits', key: 'limits', render: (_: any, r: any) => `${r.hourly_limit}/hr, ${r.daily_limit}/day` },
    {
      title: 'Actions', key: 'actions',
      render: (_: any, record: any) => (
        <Space>
          <Button size="small" onClick={() => { const email = prompt('Test email address:'); if (email) testMutation.mutate({ id: record.id, email }); }}>Test</Button>
          <Button size="small" danger onClick={() => channelsApi.delete(record.id).then(() => queryClient.invalidateQueries({ queryKey: ['channels'] }))}>Delete</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card title="SMTP Channels" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)}>Add Channel</Button>}>
      <Table columns={columns} dataSource={data || []} rowKey="id" loading={isLoading} />

      <Modal title="Add SMTP Channel" open={modalOpen} onCancel={() => setModalOpen(false)} onOk={() => form.submit()} confirmLoading={createMutation.isPending}>
        <Form form={form} layout="vertical" onFinish={(v) => createMutation.mutate(v)}>
          <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="host" label="Host" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="port" label="Port" initialValue={587}><InputNumber min={1} max={65535} /></Form.Item>
          <Form.Item name="username" label="Username"><Input /></Form.Item>
          <Form.Item name="password" label="Password"><Input.Password /></Form.Item>
          <Form.Item name="use_tls" label="Use TLS" valuePropName="checked" initialValue={true}><Switch /></Form.Item>
          <Form.Item name="priority" label="Priority (0=highest)" initialValue={0}><InputNumber min={0} /></Form.Item>
          <Form.Item name="daily_limit" label="Daily Limit" initialValue={10000}><InputNumber min={100} /></Form.Item>
          <Form.Item name="hourly_limit" label="Hourly Limit" initialValue={1000}><InputNumber min={10} /></Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
