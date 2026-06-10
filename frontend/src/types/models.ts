export interface Template {
  id: string;
  name: string;
  subject: string;
  html_body: string;
  text_body?: string;
  variables_schema: VariableSchema[];
  category: string;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface VariableSchema {
  name: string;
  type: string;
  required?: boolean;
  default?: any;
}

export interface Campaign {
  id: string;
  name: string;
  status: string;
  template_id: string;
  template_version?: number;
  sender_name?: string;
  sender_email?: string;
  reply_to?: string;
  list_ids: string[];
  segment_rule_ids: string[];
  exclusion_list_ids: string[];
  scheduled_at?: string;
  timezone: string;
  batch_size: number;
  batch_interval_seconds: number;
  total_recipients: number;
  sent_count: number;
  failed_count: number;
  opened_count: number;
  clicked_count: number;
  bounced_count: number;
  unsubscribed_count: number;
  tags: string[];
  started_at?: string;
  completed_at?: string;
  created_at: string;
}

export interface Segment {
  id: string;
  name: string;
  description?: string;
  conditions: SegmentCondition[];
  estimated_count?: number;
  last_evaluated?: string;
}

export interface SegmentCondition {
  field: string;
  operator: string;
  value: any;
  logic: string;
}

export interface SmtpChannel {
  id: string;
  name: string;
  host: string;
  port: number;
  username?: string;
  use_tls: boolean;
  is_active: boolean;
  priority: number;
  daily_limit: number;
  hourly_limit: number;
  consecutive_failures: number;
  last_success_at?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}
