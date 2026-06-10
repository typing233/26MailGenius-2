import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button, Card, DatePicker, Form, Input, InputNumber, message, Select, Steps } from 'antd';
import { campaignsApi } from '../../api/campaigns';
import { templatesApi } from '../../api/templates';
import { mailingListsApi, segmentsApi } from '../../api/services';

export default function CampaignCreate() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [form] = Form.useForm();

  const { data: templates } = useQuery({
    queryKey: ['templates-list'],
    queryFn: () => templatesApi.list({ limit: 100 }).then((r) => r.data),
  });

  const { data: segments } = useQuery({
    queryKey: ['segments-list'],
    queryFn: () => segmentsApi.list().then((r) => r.data),
  });

  const { data: mailingLists } = useQuery({
    queryKey: ['mailing-lists'],
    queryFn: () => mailingListsApi.list().then((r) => r.data),
  });

  const createMutation = useMutation({
    mutationFn: (values: any) => campaignsApi.create(values),
    onSuccess: (res) => { message.success('Campaign created'); navigate(`/campaigns/${res.data.id}`); },
    onError: (e: any) => message.error(e.response?.data?.detail || 'Creation failed'),
  });

  const steps = [
    { title: 'Basic Info' },
    { title: 'Template' },
    { title: 'Recipients' },
    { title: 'Schedule' },
    { title: 'Confirm' },
  ];

  const handleFinish = () => {
    const values = form.getFieldsValue(true);
    createMutation.mutate(values);
  };

  return (
    <Card title="Create Campaign" extra={<Button onClick={() => navigate('/campaigns')}>Cancel</Button>}>
      <Steps current={step} items={steps} style={{ marginBottom: 32 }} />
      <Form form={form} layout="vertical" style={{ maxWidth: 600 }}>
        {step === 0 && (
          <>
            <Form.Item name="name" label="Campaign Name" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="sender_name" label="Sender Name"><Input /></Form.Item>
            <Form.Item name="sender_email" label="Sender Email"><Input type="email" /></Form.Item>
            <Form.Item name="reply_to" label="Reply-To"><Input type="email" /></Form.Item>
          </>
        )}
        {step === 1 && (
          <Form.Item name="template_id" label="Select Template" rules={[{ required: true }]}>
            <Select placeholder="Choose a template" options={(templates?.items || []).map((t: any) => ({ value: t.id, label: `${t.name} (v${t.version})` }))} />
          </Form.Item>
        )}
        {step === 2 && (
          <>
            <Form.Item name="list_ids" label="Mailing Lists"><Select mode="multiple" placeholder="Select lists" options={(mailingLists || []).map((l: any) => ({ value: l.id, label: l.name }))} /></Form.Item>
            <Form.Item name="segment_rule_ids" label="Segments">
              <Select mode="multiple" placeholder="Select segments" options={(segments || []).map((s: any) => ({ value: s.id, label: s.name }))} />
            </Form.Item>
            <Form.Item name="exclusion_list_ids" label="Exclusion Lists"><Select mode="multiple" placeholder="Exclude lists" options={(mailingLists || []).map((l: any) => ({ value: l.id, label: l.name }))} /></Form.Item>
          </>
        )}
        {step === 3 && (
          <>
            <Form.Item name="scheduled_at" label="Schedule (leave empty for manual send)"><DatePicker showTime style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="timezone" label="Timezone" initialValue="UTC"><Input /></Form.Item>
            <Form.Item name="batch_size" label="Batch Size" initialValue={500}><InputNumber min={10} max={5000} /></Form.Item>
            <Form.Item name="batch_interval_seconds" label="Batch Interval (seconds)" initialValue={10}><InputNumber min={1} max={300} /></Form.Item>
          </>
        )}
        {step === 4 && (
          <div>
            <p><strong>Review your campaign settings and click Create.</strong></p>
            <pre style={{ background: '#f5f5f5', padding: 16, borderRadius: 4 }}>{JSON.stringify(form.getFieldsValue(true), null, 2)}</pre>
          </div>
        )}
        <div style={{ marginTop: 24, display: 'flex', gap: 8 }}>
          {step > 0 && <Button onClick={() => setStep(step - 1)}>Previous</Button>}
          {step < 4 && <Button type="primary" onClick={() => setStep(step + 1)}>Next</Button>}
          {step === 4 && <Button type="primary" onClick={handleFinish} loading={createMutation.isPending}>Create Campaign</Button>}
        </div>
      </Form>
    </Card>
  );
}
