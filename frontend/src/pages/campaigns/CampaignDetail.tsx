import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Col, Descriptions, message, Progress, Row, Space, Statistic, Table, Tag } from 'antd';
import { campaignsApi } from '../../api/campaigns';

const STATUS_COLORS: Record<string, string> = {
  draft: 'default', scheduled: 'blue', sending: 'processing', paused: 'warning',
  completed: 'success', cancelled: 'error', failed: 'error',
};

export default function CampaignDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: campaign } = useQuery({
    queryKey: ['campaign', id],
    queryFn: () => campaignsApi.get(id!).then((r) => r.data),
    enabled: !!id,
  });

  const { data: progress } = useQuery({
    queryKey: ['campaign-progress', id],
    queryFn: () => campaignsApi.getProgress(id!).then((r) => r.data),
    enabled: !!id && campaign?.status === 'sending',
    refetchInterval: 5000,
  });

  const { data: errors } = useQuery({
    queryKey: ['campaign-errors', id],
    queryFn: () => campaignsApi.getErrors(id!).then((r) => r.data),
    enabled: !!id,
  });

  const actionMutation = useMutation({
    mutationFn: (action: string) => {
      switch (action) {
        case 'send-now': return campaignsApi.sendNow(id!);
        case 'pause': return campaignsApi.pause(id!);
        case 'resume': return campaignsApi.resume(id!);
        case 'cancel': return campaignsApi.cancel(id!);
        default: return Promise.reject();
      }
    },
    onSuccess: () => { message.success('Action performed'); queryClient.invalidateQueries({ queryKey: ['campaign', id] }); },
    onError: (e: any) => message.error(e.response?.data?.detail || 'Action failed'),
  });

  if (!campaign) return null;

  return (
    <Card title={campaign.name} extra={<Button onClick={() => navigate('/campaigns')}>Back</Button>}>
      <Space style={{ marginBottom: 16 }}>
        <Tag color={STATUS_COLORS[campaign.status]}>{campaign.status.toUpperCase()}</Tag>
        {campaign.status === 'draft' && <Button type="primary" onClick={() => actionMutation.mutate('send-now')}>Send Now</Button>}
        {campaign.status === 'sending' && <Button danger onClick={() => actionMutation.mutate('pause')}>Pause</Button>}
        {campaign.status === 'paused' && <Button type="primary" onClick={() => actionMutation.mutate('resume')}>Resume</Button>}
        {['draft', 'scheduled', 'sending', 'paused'].includes(campaign.status) && <Button danger onClick={() => actionMutation.mutate('cancel')}>Cancel</Button>}
        <Button onClick={() => navigate(`/campaigns/${id}/report`)}>View Report</Button>
      </Space>

      {campaign.status === 'sending' && progress && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Progress percent={progress.progress_pct} status="active" />
          <p>{progress.sent_count} / {progress.total_recipients} sent{progress.estimated_remaining_seconds ? ` — ~${Math.ceil(progress.estimated_remaining_seconds / 60)} min remaining` : ''}</p>
        </Card>
      )}

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}><Statistic title="Recipients" value={campaign.total_recipients} /></Col>
        <Col span={4}><Statistic title="Sent" value={campaign.sent_count} /></Col>
        <Col span={4}><Statistic title="Opened" value={campaign.opened_count} /></Col>
        <Col span={4}><Statistic title="Clicked" value={campaign.clicked_count} /></Col>
        <Col span={4}><Statistic title="Bounced" value={campaign.bounced_count} /></Col>
        <Col span={4}><Statistic title="Failed" value={campaign.failed_count} valueStyle={{ color: campaign.failed_count > 0 ? '#cf1322' : undefined }} /></Col>
      </Row>

      <Descriptions bordered column={2} size="small">
        <Descriptions.Item label="Sender">{campaign.sender_name} &lt;{campaign.sender_email}&gt;</Descriptions.Item>
        <Descriptions.Item label="Reply-To">{campaign.reply_to || '-'}</Descriptions.Item>
        <Descriptions.Item label="Timezone">{campaign.timezone}</Descriptions.Item>
        <Descriptions.Item label="Batch Size">{campaign.batch_size}</Descriptions.Item>
        <Descriptions.Item label="Scheduled">{campaign.scheduled_at ? new Date(campaign.scheduled_at).toLocaleString() : 'Immediate'}</Descriptions.Item>
        <Descriptions.Item label="Started">{campaign.started_at ? new Date(campaign.started_at).toLocaleString() : '-'}</Descriptions.Item>
      </Descriptions>

      {errors && errors.total > 0 && (
        <Card title={`Errors (${errors.total})`} size="small" style={{ marginTop: 16 }}>
          <Table
            dataSource={errors.items}
            rowKey="id"
            size="small"
            columns={[
              { title: 'Status', dataIndex: 'status', render: (v: string) => <Tag color="error">{v}</Tag> },
              { title: 'Error', dataIndex: 'error_message', ellipsis: true },
              { title: 'Retries', dataIndex: 'retry_count' },
              { title: 'Failed At', dataIndex: 'failed_at', render: (v: string) => v ? new Date(v).toLocaleString() : '-' },
              {
                title: 'Actions', render: (_: any, record: any) => (
                  <Button size="small" onClick={() => campaignsApi.retryError(id!, record.id).then(() => message.success('Retry queued'))}>Retry</Button>
                ),
              },
            ]}
          />
        </Card>
      )}
    </Card>
  );
}
