import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Card, Col, Row, Statistic, Table } from 'antd';
import { reportsApi } from '../../api/services';

export default function CampaignReport() {
  const { id } = useParams();

  const { data: summary } = useQuery({
    queryKey: ['report-summary', id],
    queryFn: () => reportsApi.getCampaignSummary(id!).then((r) => r.data),
    enabled: !!id,
  });

  const { data: funnel } = useQuery({
    queryKey: ['report-funnel', id],
    queryFn: () => reportsApi.getFunnel(id!).then((r) => r.data),
    enabled: !!id,
  });

  const { data: timeline } = useQuery({
    queryKey: ['report-timeline', id],
    queryFn: () => reportsApi.getTimeline(id!).then((r) => r.data),
    enabled: !!id,
  });

  const handleExport = async () => {
    const res = await reportsApi.exportReport({ campaign_id: id, format: 'csv' });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `report-${id}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  return (
    <div style={{ padding: 24 }}>
      <Card title="Campaign Report" extra={<Button onClick={handleExport}>Export CSV</Button>}>
        {summary?.metrics && (
          <Row gutter={16} style={{ marginBottom: 24 }}>
            <Col span={4}><Statistic title="Sent" value={summary.metrics.sent} /></Col>
            <Col span={4}><Statistic title="Opened" value={summary.metrics.opened} /></Col>
            <Col span={4}><Statistic title="Clicked" value={summary.metrics.clicked} /></Col>
            <Col span={4}><Statistic title="Bounced" value={summary.metrics.bounced} /></Col>
          </Row>
        )}

        {funnel?.funnel && (
          <Card title="Funnel" size="small" style={{ marginBottom: 16 }}>
            <Table
              dataSource={funnel.funnel}
              rowKey="stage"
              pagination={false}
              size="small"
              columns={[
                { title: 'Stage', dataIndex: 'stage' },
                { title: 'Count', dataIndex: 'count' },
                { title: '%', dataIndex: 'pct', render: (v: number) => `${v}%` },
              ]}
            />
          </Card>
        )}

        {timeline?.timeline && (
          <Card title="Timeline (by hour)" size="small">
            <Table
              dataSource={timeline.timeline}
              rowKey={(r: any) => `${r.hour}-${r.event_type}`}
              pagination={false}
              size="small"
              columns={[
                { title: 'Hour', dataIndex: 'hour' },
                { title: 'Event', dataIndex: 'event_type' },
                { title: 'Count', dataIndex: 'count' },
              ]}
            />
          </Card>
        )}
      </Card>
    </div>
  );
}
