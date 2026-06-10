import { useQuery } from '@tanstack/react-query';
import { Card, Col, Row, Statistic } from 'antd';
import { MailOutlined, EyeOutlined, LinkOutlined, WarningOutlined } from '@ant-design/icons';
import { reportsApi } from '../../api/services';

export default function Dashboard() {
  const { data } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => reportsApi.getDashboard().then((r) => r.data),
    refetchInterval: 30000,
  });

  if (!data) return null;

  return (
    <div style={{ padding: 24 }}>
      <h2>Dashboard</h2>
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card><Statistic title="Total Campaigns" value={data.total_campaigns} prefix={<MailOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Active Campaigns" value={data.active_campaigns} valueStyle={{ color: '#3f8600' }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Total Sent" value={data.total_sent} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Total Bounced" value={data.total_bounced} prefix={<WarningOutlined />} valueStyle={{ color: data.total_bounced > 0 ? '#cf1322' : undefined }} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Total Opened" value={data.total_opened} prefix={<EyeOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Total Clicked" value={data.total_clicked} prefix={<LinkOutlined />} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Open Rate" value={data.overall_open_rate} suffix="%" precision={2} /></Card>
        </Col>
        <Col span={6}>
          <Card><Statistic title="Click Rate" value={data.overall_click_rate} suffix="%" precision={2} /></Card>
        </Col>
      </Row>
    </div>
  );
}
