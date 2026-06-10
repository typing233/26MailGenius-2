import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Button, Card, Form, Input, message, Select, Space } from 'antd';
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons';
import { segmentsApi } from '../../api/services';

const FIELDS = ['email', 'name', 'status', 'source', 'tags', 'custom_fields.company'];
const OPERATORS = ['eq', 'neq', 'contains', 'starts_with', 'in', 'not_in'];

export default function SegmentBuilder() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const isNew = !id;

  const { data: segment } = useQuery({
    queryKey: ['segment', id],
    queryFn: () => segmentsApi.get(id!).then((r) => r.data),
    enabled: !!id,
  });

  useEffect(() => {
    if (segment) form.setFieldsValue(segment);
  }, [segment]);

  const saveMutation = useMutation({
    mutationFn: (values: any) => isNew ? segmentsApi.create(values) : segmentsApi.update(id!, values),
    onSuccess: () => { message.success('Segment saved'); navigate('/segments'); },
    onError: (e: any) => message.error(e.response?.data?.detail || 'Save failed'),
  });

  return (
    <Card title={isNew ? 'New Segment' : `Edit: ${segment?.name || ''}`} extra={<Button onClick={() => navigate('/segments')}>Back</Button>}>
      <Form form={form} layout="vertical" onFinish={(v) => saveMutation.mutate(v)} style={{ maxWidth: 700 }}>
        <Form.Item name="name" label="Segment Name" rules={[{ required: true }]}><Input /></Form.Item>
        <Form.Item name="description" label="Description"><Input.TextArea rows={2} /></Form.Item>

        <Form.List name="conditions" initialValue={[{ field: 'email', operator: 'contains', value: '', logic: 'AND' }]}>
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...rest }) => (
                <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                  <Form.Item {...rest} name={[name, 'field']} rules={[{ required: true }]}>
                    <Select style={{ width: 180 }} options={FIELDS.map((f) => ({ value: f, label: f }))} />
                  </Form.Item>
                  <Form.Item {...rest} name={[name, 'operator']} rules={[{ required: true }]}>
                    <Select style={{ width: 130 }} options={OPERATORS.map((o) => ({ value: o, label: o }))} />
                  </Form.Item>
                  <Form.Item {...rest} name={[name, 'value']} rules={[{ required: true }]}>
                    <Input style={{ width: 200 }} placeholder="Value" />
                  </Form.Item>
                  <Form.Item {...rest} name={[name, 'logic']} initialValue="AND">
                    <Select style={{ width: 80 }} options={[{ value: 'AND', label: 'AND' }, { value: 'OR', label: 'OR' }]} />
                  </Form.Item>
                  <MinusCircleOutlined onClick={() => remove(name)} />
                </Space>
              ))}
              <Button type="dashed" onClick={() => add({ field: 'email', operator: 'contains', value: '', logic: 'AND' })} icon={<PlusOutlined />}>Add Condition</Button>
            </>
          )}
        </Form.List>

        <Form.Item style={{ marginTop: 24 }}>
          <Button type="primary" htmlType="submit" loading={saveMutation.isPending}>Save Segment</Button>
        </Form.Item>
      </Form>
    </Card>
  );
}
