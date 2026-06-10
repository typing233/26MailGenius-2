import { Routes, Route, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import { Spin } from 'antd';

const TemplateList = lazy(() => import('./pages/templates/TemplateList'));
const TemplateEditor = lazy(() => import('./pages/templates/TemplateEditor'));
const CampaignList = lazy(() => import('./pages/campaigns/CampaignList'));
const CampaignCreate = lazy(() => import('./pages/campaigns/CampaignCreate'));
const CampaignDetail = lazy(() => import('./pages/campaigns/CampaignDetail'));
const SegmentList = lazy(() => import('./pages/segments/SegmentList'));
const SegmentBuilder = lazy(() => import('./pages/segments/SegmentBuilder'));
const ChannelList = lazy(() => import('./pages/channels/ChannelList'));
const Dashboard = lazy(() => import('./pages/reports/Dashboard'));
const CampaignReport = lazy(() => import('./pages/reports/CampaignReport'));
const DeadLetterQueue = lazy(() => import('./pages/dead-letter/DeadLetterQueue'));
const SuppressionList = lazy(() => import('./pages/suppression/SuppressionList'));

function Loading() {
  return <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 200 }}><Spin size="large" /></div>;
}

export default function AppRouter() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/templates" element={<TemplateList />} />
        <Route path="/templates/new" element={<TemplateEditor />} />
        <Route path="/templates/:id" element={<TemplateEditor />} />
        <Route path="/campaigns" element={<CampaignList />} />
        <Route path="/campaigns/new" element={<CampaignCreate />} />
        <Route path="/campaigns/:id" element={<CampaignDetail />} />
        <Route path="/campaigns/:id/report" element={<CampaignReport />} />
        <Route path="/segments" element={<SegmentList />} />
        <Route path="/segments/new" element={<SegmentBuilder />} />
        <Route path="/segments/:id" element={<SegmentBuilder />} />
        <Route path="/channels" element={<ChannelList />} />
        <Route path="/dead-letter" element={<DeadLetterQueue />} />
        <Route path="/suppression" element={<SuppressionList />} />
      </Routes>
    </Suspense>
  );
}
