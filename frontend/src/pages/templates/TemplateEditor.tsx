import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Button, Card, Col, Form, Input, message, Row, Select, Space, Tabs } from 'antd';
import { templatesApi } from '../../api/templates';

export default function TemplateEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [htmlBody, setHtmlBody] = useState('');
  const [preview, setPreview] = useState('');
  const [testVars, setTestVars] = useState<Record<string, string>>({});
  const isNew = !id;

  const { data: template } = useQuery({
    queryKey: ['template', id],
    queryFn: () => templatesApi.get(id!).then((r) => r.data),
    enabled: !!id,
  });

  useEffect(() => {
    if (template) {
      form.setFieldsValue(template);
      setHtmlBody(template.html_body);
    }
  }, [template]);

  const saveMutation = useMutation({
    mutationFn: (values: any) => isNew
      ? templatesApi.create({ ...values, html_body: htmlBody })
      : templatesApi.update(id!, { ...values, html_body: htmlBody }),
    onSuccess: () => { message.success('Template saved'); navigate('/templates'); },
    onError: (e: any) => message.error(e.response?.data?.detail || 'Save failed'),
  });

  const handlePreview = async () => {
    if (id) {
      const res = await templatesApi.preview(id, testVars);
      setPreview(res.data.html);
    } else {
      const res = await templatesApi.renderTest({ html_body: htmlBody, variables: testVars });
      setPreview(res.data.rendered || '');
    }
  };

  return (
    <Card title={isNew ? 'New Template' : `Edit: ${template?.name || ''}`} extra={<Button onClick={() => navigate('/templates')}>Back</Button>}>
      <Row gutter={16}>
        <Col span={12}>
          <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)}>
            <Form.Item name="name" label="Name" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="subject" label="Subject" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="category" label="Category" initialValue="marketing">
              <Select options={[{ value: 'marketing', label: 'Marketing' }, { value: 'transactional', label: 'Transactional' }, { value: 'notification', label: 'Notification' }]} />
            </Form.Item>
            <Form.Item label="HTML Body">
              <Input.TextArea rows={16} value={htmlBody} onChange={(e) => setHtmlBody(e.target.value)} style={{ fontFamily: 'monospace' }} />
            </Form.Item>
            <Form.Item name="text_body" label="Text Body (optional)"><Input.TextArea rows={4} /></Form.Item>
            <Form.Item name="change_note" label="Change Note"><Input placeholder="What changed?" /></Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={saveMutation.isPending}>Save</Button>
              <Button onClick={handlePreview}>Preview</Button>
            </Space>
          </Form>
        </Col>
        <Col span={12}>
          <Tabs items={[
            { key: 'preview', label: 'Preview', children: <div dangerouslySetInnerHTML={{ __html: preview }} style={{ border: '1px solid #d9d9d9', minHeight: 400, padding: 16 }} /> },
            { key: 'vars', label: 'Test Variables', children: (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Input placeholder="name=John" onChange={(e) => {
                  const pairs = e.target.value.split(',').reduce((acc, p) => { const [k, v] = p.split('='); if (k && v) acc[k.trim()] = v.trim(); return acc; }, {} as Record<string, string>);
                  setTestVars(pairs);
                }} />
                <p style={{ color: '#888' }}>Comma-separated: name=John,vip=true</p>
              </Space>
            )},
          ]} />
        </Col>
      </Row>
    </Card>
  );
}
