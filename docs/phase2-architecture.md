# Phase 2: 邮件营销核心链路 — 系统架构拆解

## 基础设施升级

### 新增依赖

```
# 消息队列 & Worker
celery[redis]>=5.4.0
redis>=5.0.0
flower>=2.0.0           # Celery 监控面板

# 邮件发送
aiosmtplib>=3.0.0       # 异步 SMTP
jinja2>=3.1.0           # 模板引擎（变量/条件/循环）
bleach>=6.1.0           # HTML 清洗防注入
premailer>=3.10.0       # CSS 内联
html5lib>=1.1           # HTML 校验

# 加密
cryptography>=42.0.0    # SMTP 凭据 Fernet 加密

# 追踪
python-dateutil>=2.9.0  # 时区处理

# 前端
# 新建 frontend/ 目录: React 18 + Vite + TypeScript
# antd 5.x, @ant-design/charts, react-query, zustand, react-router v6
# @monaco-editor/react (HTML 编辑器)
```

### docker-compose 新增服务

```yaml
redis:
  image: redis:7-alpine
  ports: ["6379:6379"]

celery-worker:
  build: .
  command: celery -A app.worker.celery_app worker -l info -Q send,track,default -c 4
  depends_on: [db, redis]

celery-beat:
  build: .
  command: celery -A app.worker.celery_app beat -l info
  depends_on: [redis]

flower:
  image: mher/flower
  ports: ["5555:5555"]
  depends_on: [redis]

frontend:
  build: ./frontend
  ports: ["3000:3000"]
```

---

## 一、数据模型（新增 12 张表）

### 1.1 email_templates — 邮件模板

```sql
CREATE TABLE email_templates (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            VARCHAR(255) NOT NULL,
    subject         VARCHAR(500) NOT NULL,       -- 支持 Jinja2 变量
    html_body       TEXT NOT NULL,               -- Jinja2 模板源码
    text_body       TEXT,                        -- 纯文本版本
    variables_schema JSONB DEFAULT '[]',         -- 可用变量定义 [{name, type, required, default}]
    category        VARCHAR(50) DEFAULT 'marketing',  -- marketing/transactional/notification
    thumbnail_url   VARCHAR(500),
    is_active       BOOLEAN DEFAULT TRUE,
    version         INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ,
    CONSTRAINT uq_template_tenant_name UNIQUE (tenant_id, name) WHERE deleted_at IS NULL
);
```

### 1.2 template_versions — 模板版本历史

```sql
CREATE TABLE template_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    template_id     UUID NOT NULL REFERENCES email_templates(id),
    version         INTEGER NOT NULL,
    subject         VARCHAR(500) NOT NULL,
    html_body       TEXT NOT NULL,
    text_body       TEXT,
    variables_schema JSONB,
    change_note     VARCHAR(500),
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### 1.3 campaigns — 营销活动

```sql
CREATE TABLE campaigns (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            VARCHAR(255) NOT NULL,
    status          VARCHAR(20) DEFAULT 'draft',
    -- status: draft -> scheduled -> sending -> paused -> completed / cancelled / failed
    template_id     UUID NOT NULL REFERENCES email_templates(id),
    template_version INTEGER,                    -- 锁定版本快照
    sender_name     VARCHAR(100),
    sender_email    VARCHAR(255),
    reply_to        VARCHAR(255),
    -- 发送目标
    list_ids        UUID[] NOT NULL DEFAULT '{}', -- 关联的发送列表
    segment_rules   JSONB DEFAULT '[]',          -- 分群过滤规则
    exclusion_list_ids UUID[] DEFAULT '{}',      -- 排除名单
    -- 排期
    scheduled_at    TIMESTAMPTZ,                 -- 排期发送时间
    timezone        VARCHAR(50) DEFAULT 'UTC',
    -- 批次配置
    batch_size      INTEGER DEFAULT 500,
    batch_interval_seconds INTEGER DEFAULT 10,   -- 批次间隔(限流)
    -- 统计快照
    total_recipients INTEGER DEFAULT 0,
    sent_count      INTEGER DEFAULT 0,
    failed_count    INTEGER DEFAULT 0,
    opened_count    INTEGER DEFAULT 0,
    clicked_count   INTEGER DEFAULT 0,
    bounced_count   INTEGER DEFAULT 0,
    unsubscribed_count INTEGER DEFAULT 0,
    -- 元数据
    tags            JSONB DEFAULT '[]',
    created_by      UUID REFERENCES users(id),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    paused_at       TIMESTAMPTZ,
    version         INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);
CREATE INDEX idx_campaigns_status ON campaigns(tenant_id, status);
CREATE INDEX idx_campaigns_scheduled ON campaigns(tenant_id, scheduled_at) WHERE status = 'scheduled';
```

### 1.4 campaign_jobs — 发送任务（重构原 send_queue_jobs）

```sql
CREATE TABLE campaign_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    campaign_id     UUID NOT NULL REFERENCES campaigns(id),
    subscriber_id   UUID NOT NULL REFERENCES subscribers(id),
    batch_number    INTEGER NOT NULL,
    -- 状态
    status          VARCHAR(20) DEFAULT 'pending',
    -- pending -> queued -> sending -> sent -> failed -> dead_letter
    idempotency_key VARCHAR(100) NOT NULL,       -- campaign_id:subscriber_id 防重复
    -- 发送结果
    message_id      VARCHAR(255),                -- SMTP 返回的 Message-ID
    sent_at         TIMESTAMPTZ,
    failed_at       TIMESTAMPTZ,
    error_code      VARCHAR(50),
    error_message   TEXT,
    error_chain     JSONB DEFAULT '[]',          -- 完整错误链路 [{attempt, error, timestamp}]
    -- 重试
    retry_count     INTEGER DEFAULT 0,
    max_retries     INTEGER DEFAULT 3,
    next_retry_at   TIMESTAMPTZ,
    -- 元数据
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX uq_campaign_job_idempotency ON campaign_jobs(idempotency_key);
CREATE INDEX idx_jobs_pending ON campaign_jobs(tenant_id, status, batch_number) WHERE status IN ('pending', 'queued');
CREATE INDEX idx_jobs_retry ON campaign_jobs(next_retry_at) WHERE status = 'failed' AND retry_count < max_retries;
```

### 1.5 dead_letter_jobs — 死信队列

```sql
CREATE TABLE dead_letter_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    campaign_job_id UUID NOT NULL REFERENCES campaign_jobs(id),
    campaign_id     UUID NOT NULL,
    subscriber_id   UUID NOT NULL,
    final_error     TEXT,
    error_chain     JSONB,
    moved_at        TIMESTAMPTZ DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    resolution      VARCHAR(50)                  -- manual_retry / skipped / bounced
);
CREATE INDEX idx_dlq_unresolved ON dead_letter_jobs(tenant_id) WHERE resolved_at IS NULL;
```

### 1.6 smtp_channels — SMTP 渠道配置

```sql
CREATE TABLE smtp_channels (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            VARCHAR(100) NOT NULL,
    host            VARCHAR(255) NOT NULL,
    port            INTEGER DEFAULT 587,
    username        VARCHAR(255),
    password_encrypted BYTEA,                    -- Fernet 加密存储
    use_tls         BOOLEAN DEFAULT TRUE,
    is_active       BOOLEAN DEFAULT TRUE,
    priority        INTEGER DEFAULT 0,           -- 故障切换优先级，0=最高
    daily_limit     INTEGER DEFAULT 10000,
    hourly_limit    INTEGER DEFAULT 1000,
    -- 健康状态
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,
    consecutive_failures INTEGER DEFAULT 0,
    -- 元数据
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);
```

### 1.7 tracking_pixels — 打开追踪

```sql
CREATE TABLE tracking_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    campaign_id     UUID NOT NULL,
    subscriber_id   UUID NOT NULL,
    job_id          UUID REFERENCES campaign_jobs(id),
    event_type      VARCHAR(20) NOT NULL,        -- open / click / bounce / unsubscribe / complaint
    -- 事件详情
    link_url        TEXT,                        -- click 事件的目标 URL
    user_agent      VARCHAR(500),
    ip_address      INET,
    -- 去重
    fingerprint     VARCHAR(100),                -- 事件指纹 (campaign:subscriber:type:url_hash:hour)
    is_first        BOOLEAN DEFAULT FALSE,       -- 标记首次事件（唯一打开/唯一点击）
    -- 时间
    occurred_at     TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_events_campaign ON tracking_events(tenant_id, campaign_id, event_type);
CREATE INDEX idx_events_subscriber ON tracking_events(tenant_id, subscriber_id);
CREATE INDEX idx_events_dedup ON tracking_events(fingerprint);
```

### 1.8 tracking_links — 链接重写映射

```sql
CREATE TABLE tracking_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    campaign_id     UUID NOT NULL,
    original_url    TEXT NOT NULL,
    tracking_code   VARCHAR(32) NOT NULL UNIQUE, -- 短码用于重写URL
    click_count     INTEGER DEFAULT 0,
    unique_clicks   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_links_code ON tracking_links(tracking_code);
```

### 1.9 campaign_reports — 报表快照（定期聚合）

```sql
CREATE TABLE campaign_reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    campaign_id     UUID NOT NULL REFERENCES campaigns(id),
    report_type     VARCHAR(20) NOT NULL,        -- hourly / daily / final
    period_start    TIMESTAMPTZ,
    period_end      TIMESTAMPTZ,
    metrics         JSONB NOT NULL,              -- {sent, delivered, opened, clicked, bounced, ...}
    funnel          JSONB,                       -- 漏斗数据
    generated_at    TIMESTAMPTZ DEFAULT now()
);
```

### 1.10 rate_limit_counters — 租户限流计数器（Redis辅助，DB备份）

```sql
CREATE TABLE rate_limit_counters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    channel_id      UUID REFERENCES smtp_channels(id),
    window_key      VARCHAR(50) NOT NULL,        -- hourly:2024-01-01T14 / daily:2024-01-01
    count           INTEGER DEFAULT 0,
    limit_value     INTEGER NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_rate_limit UNIQUE (tenant_id, channel_id, window_key)
);
```

### 1.11 segment_rules — 分群规则（可复用）

```sql
CREATE TABLE segment_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    conditions      JSONB NOT NULL,              -- [{field, operator, value, logic}]
    -- field: email/name/status/tags/custom_fields.*/list_membership/last_activity
    -- operator: eq/neq/contains/in/not_in/gt/lt/between/exists
    -- logic: AND/OR
    estimated_count INTEGER,
    last_evaluated  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    deleted_at      TIMESTAMPTZ
);
```

### 1.12 suppression_list — 全局抑制名单

```sql
CREATE TABLE suppression_list (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id),
    email           VARCHAR(255) NOT NULL,
    reason          VARCHAR(50) NOT NULL,        -- bounce / complaint / manual / unsubscribe
    source          VARCHAR(100),                -- campaign_id 或 manual
    suppressed_at   TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ,                 -- NULL = 永久
    CONSTRAINT uq_suppression UNIQUE (tenant_id, email) WHERE expires_at IS NULL OR expires_at > now()
);
```

---

## 二、后端接口设计

### 2.1 模板管理 `/api/v1/templates`

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| POST | `/` | 创建模板 | `template:write` |
| GET | `/` | 列表（分页/搜索/分类） | `template:read` |
| GET | `/{id}` | 模板详情 | `template:read` |
| PUT | `/{id}` | 更新模板（自动版本化） | `template:write` |
| DELETE | `/{id}` | 软删除 | `template:write` |
| GET | `/{id}/versions` | 版本历史列表 | `template:read` |
| GET | `/{id}/versions/{ver}` | 查看指定版本 | `template:read` |
| POST | `/{id}/versions/{ver}/restore` | 恢复到指定版本 | `template:write` |
| POST | `/{id}/preview` | 渲染预览（传入变量） | `template:read` |
| POST | `/{id}/validate` | 校验模板语法+变量 | `template:read` |
| POST | `/render-test` | 不保存直接渲染 HTML | `template:read` |

**模板引擎规则:**
- 使用 Jinja2 沙箱模式（`SandboxedEnvironment`）
- 支持: `{{ var }}`, `{% if %}`, `{% for %}`, `{% block %}`
- 禁止: `{% import %}`, `{% include %}`, `{{ config }}`, 任何 Python 表达式调用
- HTML 入库前经 bleach 清洗（白名单标签/属性），输出前 CSS 内联化

### 2.2 活动管理 `/api/v1/campaigns`

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| POST | `/` | 创建活动（草稿） | `campaign:write` |
| GET | `/` | 活动列表（状态/日期/标签过滤） | `campaign:read` |
| GET | `/{id}` | 活动详情+统计摘要 | `campaign:read` |
| PUT | `/{id}` | 编辑活动（仅 draft/scheduled） | `campaign:write` |
| DELETE | `/{id}` | 软删除（仅 draft） | `campaign:write` |
| POST | `/{id}/schedule` | 排期发送 | `campaign:write` |
| POST | `/{id}/send-now` | 立即发送 | `campaign:write` |
| POST | `/{id}/pause` | 暂停发送 | `campaign:write` |
| POST | `/{id}/resume` | 恢复发送 | `campaign:write` |
| POST | `/{id}/cancel` | 取消活动 | `campaign:write` |
| POST | `/{id}/test-send` | 发送测试邮件（指定邮箱） | `campaign:write` |
| GET | `/{id}/recipients` | 预览收件人列表（分页） | `campaign:read` |
| GET | `/{id}/progress` | 实时发送进度 | `campaign:read` |
| GET | `/{id}/stats` | 详细统计（漏斗+时间线） | `campaign:read` |
| GET | `/{id}/errors` | 错误列表（分页） | `campaign:read` |
| POST | `/{id}/errors/{job_id}/retry` | 手动重试单个失败任务 | `campaign:write` |

### 2.3 分群规则 `/api/v1/segments`

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| POST | `/` | 创建分群规则 | `segment:write` |
| GET | `/` | 规则列表 | `segment:read` |
| GET | `/{id}` | 规则详情 | `segment:read` |
| PUT | `/{id}` | 更新规则 | `segment:write` |
| DELETE | `/{id}` | 删除 | `segment:write` |
| POST | `/{id}/evaluate` | 估算匹配人数 | `segment:read` |
| GET | `/{id}/subscribers` | 查看匹配订阅者（分页） | `segment:read` |

### 2.4 SMTP 渠道 `/api/v1/channels`

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| POST | `/` | 创建渠道 | `channel:write` |
| GET | `/` | 渠道列表 | `channel:read` |
| GET | `/{id}` | 渠道详情（密码脱敏） | `channel:read` |
| PUT | `/{id}` | 更新渠道 | `channel:write` |
| DELETE | `/{id}` | 停用删除 | `channel:write` |
| POST | `/{id}/test` | 发送测试连接邮件 | `channel:write` |
| GET | `/{id}/health` | 健康状态+剩余额度 | `channel:read` |

### 2.5 追踪 `/api/v1/tracking`

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| GET | `/pixel/{job_id}.gif` | 打开追踪像素（公开） | 无需认证 |
| GET | `/click/{tracking_code}` | 链接点击重定向（公开） | 无需认证 |
| POST | `/webhook/bounce` | 退信 Webhook 接收 | Webhook 签名验证 |
| POST | `/webhook/complaint` | 投诉 Webhook 接收 | Webhook 签名验证 |
| GET | `/events` | 事件列表（内部查询） | `tracking:read` |

### 2.6 报表 `/api/v1/reports`

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| GET | `/dashboard` | 全局仪表板数据 | `report:read` |
| GET | `/campaigns/{id}/summary` | 单活动报表 | `report:read` |
| GET | `/campaigns/{id}/timeline` | 时间线数据（按小时） | `report:read` |
| GET | `/campaigns/{id}/funnel` | 漏斗转化数据 | `report:read` |
| POST | `/export` | 导出报表（CSV/PDF） | `report:read` |
| GET | `/export/{job_id}` | 下载导出文件 | `report:read` |

### 2.7 死信队列 `/api/v1/dead-letter`

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| GET | `/` | 死信列表（分页） | `send_queue:read` |
| GET | `/{id}` | 死信详情+错误链路 | `send_queue:read` |
| POST | `/{id}/retry` | 重新入队 | `send_queue:write` |
| POST | `/{id}/skip` | 标记跳过 | `send_queue:write` |
| POST | `/batch-retry` | 批量重试 | `send_queue:write` |

### 2.8 抑制名单 `/api/v1/suppression`

| Method | Path | 说明 | 权限 |
|--------|------|------|------|
| GET | `/` | 抑制名单列表 | `subscriber:read` |
| POST | `/` | 手动添加 | `subscriber:write` |
| DELETE | `/{id}` | 解除抑制 | `subscriber:write` |
| POST | `/import` | 批量导入 | `subscriber:write` |

---

## 三、队列消费逻辑（Celery Tasks）

### 3.1 架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                        Redis Broker                          │
├──────────┬──────────┬───────────┬───────────┬──────────────┤
│  send    │  track   │  report   │  default  │  dead_letter │
│  queue   │  queue   │  queue    │  queue    │  queue       │
└────┬─────┴────┬─────┴─────┬────┴─────┬────┴───────┬──────┘
     │          │            │          │            │
     ▼          ▼            ▼          ▼            ▼
┌─────────┐ ┌────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐
│ send    │ │ track  │ │ report  │ │ default│ │dead_letter│
│ worker  │ │ worker │ │ worker  │ │ worker │ │ worker   │
└─────────┘ └────────┘ └─────────┘ └────────┘ └──────────┘
```

### 3.2 Task 清单

```python
# app/worker/tasks/campaign_tasks.py

@celery_app.task(queue='default')
def prepare_campaign(campaign_id: str):
    """
    活动准备阶段:
    1. 解析收件人: list_ids ∪ segment_rules - exclusion_list_ids - suppression_list
    2. 去重（同一人出现在多个列表只发一次）
    3. 写入 campaign_jobs 表，分配 batch_number
    4. 更新 campaign.total_recipients
    5. 触发 dispatch_batches
    """

@celery_app.task(queue='default')
def dispatch_batches(campaign_id: str):
    """
    批次调度:
    1. 检查 campaign 状态（paused/cancelled 则终止）
    2. 按 batch_number 顺序取出一批 pending jobs
    3. 发送到 send queue: send_email.apply_async()
    4. 设置 ETA 间隔（batch_interval_seconds）控制限流
    5. 当前批次完成后调度下一批次
    """

@celery_app.task(queue='send', rate_limit='100/m', bind=True, max_retries=3)
def send_email(self, job_id: str):
    """
    单封邮件发送:
    1. 幂等检查: idempotency_key 防重复
    2. 获取 SMTP 渠道（按优先级 + 健康状态 + 限流余量）
    3. 渲染模板: Jinja2 填充订阅者变量
    4. 注入追踪: 像素 + 链接重写
    5. 调用 aiosmtplib 发送
    6. 成功: 更新 job.status='sent', 记录 message_id
    7. 失败: 记录 error_chain, 判断是否重试或进死信
    """

@celery_app.task(queue='send', bind=True)
def retry_failed_job(self, job_id: str):
    """重试失败任务 — 指数退避"""

@celery_app.task(queue='dead_letter')
def move_to_dead_letter(job_id: str):
    """将超过重试次数的任务移入死信表"""

@celery_app.task(queue='track')
def record_tracking_event(event_data: dict):
    """
    追踪事件处理:
    1. 计算 fingerprint 去重
    2. 判断 is_first (唯一打开/唯一点击)
    3. 写入 tracking_events
    4. 增量更新 campaign 统计计数器
    5. 退信/投诉 → 写入 suppression_list
    """

@celery_app.task(queue='track')
def process_bounce(payload: dict):
    """处理退信 Webhook: 解析、记录事件、更新抑制名单、更新 subscriber 状态"""

@celery_app.task(queue='report')
def aggregate_campaign_report(campaign_id: str, report_type: str):
    """定期聚合活动报表快照"""

@celery_app.task(queue='default')
def check_scheduled_campaigns():
    """
    Beat 定时任务（每分钟）:
    扫描 status='scheduled' AND scheduled_at <= now() 的活动
    触发 prepare_campaign
    """

@celery_app.task(queue='default')
def health_check_channels():
    """
    Beat 定时任务（每5分钟）:
    检查 SMTP 渠道健康，重置 consecutive_failures
    """
```

### 3.3 限流策略

```
多层限流:
├── 租户级: tenant.settings.daily_limit (Redis sliding window)
├── 渠道级: smtp_channels.hourly_limit / daily_limit (Redis counter)
├── Celery级: rate_limit='100/m' per worker
└── 批次级: batch_interval_seconds 间隔调度

限流检查流程:
1. send_email 任务开始
2. Redis INCR tenant:{tid}:daily:{date} → 超限则 delay 到下一窗口
3. Redis INCR channel:{cid}:hourly:{hour} → 超限则尝试下一优先级渠道
4. 所有渠道超限 → 任务 retry with ETA
```

### 3.4 暂停/恢复机制

```
暂停 (POST /campaigns/{id}/pause):
1. campaign.status = 'paused', campaign.paused_at = now()
2. Redis SET campaign:{id}:paused = 1
3. 正在执行的 send_email 任务检查 Redis flag → 提前返回(不发送)
4. dispatch_batches 检查 flag → 停止调度后续批次

恢复 (POST /campaigns/{id}/resume):
1. campaign.status = 'sending', campaign.paused_at = NULL
2. Redis DEL campaign:{id}:paused
3. 触发 dispatch_batches 继续未完成批次
```

### 3.5 故障切换

```
SMTP 渠道选择算法:
1. 查询 is_active=True 的渠道，按 priority ASC 排序
2. 排除 consecutive_failures >= 5 的渠道（熔断）
3. 排除当前小时/天已达限额的渠道
4. 选择第一个可用渠道
5. 发送失败 → 递增 consecutive_failures, 尝试下一渠道
6. 所有渠道不可用 → 任务进入 retry（指数退避）

熔断恢复: health_check_channels 定时探测，成功后重置 failures
```

---

## 四、前端页面设计

### 4.1 页面结构

```
frontend/src/
├── pages/
│   ├── templates/
│   │   ├── TemplateList.tsx          — 模板列表（搜索/分类/创建）
│   │   ├── TemplateEditor.tsx        — 模板编辑器（Monaco + 实时预览）
│   │   └── TemplatePreview.tsx       — 全屏预览（桌面/移动端切换）
│   ├── campaigns/
│   │   ├── CampaignList.tsx          — 活动列表（状态筛选/批量操作）
│   │   ├── CampaignCreate.tsx        — 创建活动（步骤向导）
│   │   ├── CampaignDetail.tsx        — 活动详情+实时仪表板
│   │   ├── CampaignProgress.tsx      — 发送进度（实时刷新）
│   │   └── CampaignErrors.tsx        — 错误排查页
│   ├── segments/
│   │   ├── SegmentList.tsx           — 分群列表
│   │   └── SegmentBuilder.tsx        — 可视化规则构建器
│   ├── channels/
│   │   ├── ChannelList.tsx           — SMTP 渠道列表
│   │   └── ChannelForm.tsx           — 渠道配置表单
│   ├── reports/
│   │   ├── Dashboard.tsx             — 全局仪表板
│   │   ├── CampaignReport.tsx        — 单活动报表
│   │   └── ExportManager.tsx         — 报表导出管理
│   ├── dead-letter/
│   │   └── DeadLetterQueue.tsx       — 死信队列管理
│   └── suppression/
│       └── SuppressionList.tsx       — 抑制名单管理
├── components/
│   ├── template/
│   │   ├── HtmlEditor.tsx            — Monaco 编辑器封装
│   │   ├── VariableInserter.tsx      — 变量插入面板
│   │   ├── PreviewPane.tsx           — 实时渲染预览
│   │   └── ValidationPanel.tsx       — 校验结果面板
│   ├── campaign/
│   │   ├── RecipientSelector.tsx     — 列表+分群+排除选择
│   │   ├── SchedulePicker.tsx        — 排期+时区选择器
│   │   ├── ProgressBar.tsx           — 发送进度条
│   │   ├── StatCards.tsx             — 统计卡片组
│   │   └── FunnelChart.tsx           — 漏斗图
│   ├── segment/
│   │   ├── RuleRow.tsx               — 单条件行
│   │   └── RuleGroupBuilder.tsx      — AND/OR 组合
│   └── shared/
│       ├── StatusBadge.tsx           — 状态标签
│       ├── TimelineChart.tsx         — 时间线图表
│       └── ExportButton.tsx          — 导出按钮
```

### 4.2 核心页面交互

#### 模板编辑器 (`TemplateEditor.tsx`)
```
┌─────────────────────────────────────────────────────────────┐
│ [< 返回]  模板名称: ________  分类: [marketing ▼]  [保存] [预览] │
├────────────────────────────────┬────────────────────────────┤
│ Monaco HTML Editor             │ 实时预览面板               │
│                                │ ┌────────────────────────┐ │
│ <h1>Hi {{ name }}</h1>         │ │ Hi John               │ │
│ {% if vip %}                   │ │ [VIP Badge]            │ │
│   <span>VIP</span>            │ │                        │ │
│ {% endif %}                    │ │                        │ │
│                                │ └────────────────────────┘ │
├────────────────────────────────┤ [Desktop] [Mobile] [Text]  │
│ 变量面板 │ 校验结果            │                            │
│ + name   │ ✓ 语法正确          │ 变量测试数据:              │
│ + email  │ ✓ 无 XSS 风险       │ name: [John    ]           │
│ + vip    │ ⚠ 未使用变量: age   │ vip:  [✓]                  │
└────────────────────────────────┴────────────────────────────┘
```

#### 活动创建向导 (`CampaignCreate.tsx`)
```
Step 1: 基本信息     → 名称、发件人、回复地址
Step 2: 选择模板     → 模板列表 + 预览确认
Step 3: 选择收件人   → 列表选择 + 分群规则 + 排除名单 → 显示预估人数
Step 4: 排期设置     → 立即/排期 + 时区选择 + 批次配置
Step 5: 确认发送     → 摘要 + 发送测试邮件 + 最终确认
```

#### 活动仪表板 (`CampaignDetail.tsx`)
```
┌─────────────────────────────────────────────────────────────┐
│ Campaign: Black Friday Sale          [暂停] [取消]          │
│ Status: ● Sending (67%)              Started: 2024-01-01   │
├──────┬──────┬──────┬──────┬──────┬──────────────────────────┤
│ Sent │ Open │Click │Bounce│Unsub │ 进度条 ████████░░░ 67%  │
│ 6.7k │ 2.1k│ 890 │  23  │  12  │ ETA: 14 min remaining   │
├──────┴──────┴──────┴──────┴──────┴──────────────────────────┤
│ [漏斗图]              │ [时间线图 - 每小时发送/打开趋势]     │
│ Sent     → 10,000    │                                      │
│ Delivered→  9,950    │  ╭──────╮                            │
│ Opened   →  3,200    │  │      ╰──╮                        │
│ Clicked  →  1,200    │  ╯         ╰───                     │
│ Converted→    340    │                                      │
├───────────────────────┴──────────────────────────────────────┤
│ 错误排查: [23 failures] [5 dead letter] → 查看详情           │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 实时刷新策略

```
- 活动进度: 发送中 → 每 5s 轮询 GET /campaigns/{id}/progress
- 仪表板统计: 每 30s 轮询
- 死信队列: WebSocket 推送新增条目 (可降级为 30s 轮询)
- 使用 react-query 的 refetchInterval 配置
```

---

## 五、追踪系统设计

### 5.1 打开追踪（像素）

```
邮件 HTML 注入:
<img src="https://track.example.com/api/v1/tracking/pixel/{job_id}.gif" width="1" height="1" />

请求处理:
1. 返回 1x1 透明 GIF (预缓存在内存)
2. 设置 Cache-Control: no-cache, no-store (防邮件客户端缓存)
3. 异步投递 record_tracking_event task
4. 去重: fingerprint = sha256(campaign_id + subscriber_id + 'open' + hour_bucket)
5. 隐私: 不记录精确 IP (截断最后一段), UA 只记录客户端类型

处理邮件客户端预加载:
- Apple MPP 检测: User-Agent 包含 "Fetchmail" 或来自 Apple IP 段
- 标记 is_machine_open=True, 不计入唯一打开
```

### 5.2 链接点击追踪

```
模板渲染时:
1. 扫描 HTML 中所有 <a href="...">
2. 排除: mailto:, tel:, #anchor, unsubscribe links
3. 为每个 URL 生成 tracking_code (base62 encoded UUID[:8])
4. 重写为: https://track.example.com/api/v1/tracking/click/{tracking_code}
5. 记录映射到 tracking_links 表

点击处理:
1. 查找 tracking_code → original_url
2. 记录事件 (异步)
3. 302 重定向到 original_url
4. Cache-Control: private, max-age=0
```

### 5.3 退信处理

```
入站路径:
- SMTP bounce → 解析 DSN (Delivery Status Notification)
- ESP Webhook → POST /api/v1/tracking/webhook/bounce

处理流程:
1. 解析 bounce 类型 (hard/soft)
2. Hard bounce: 立即加入 suppression_list, 更新 subscriber.status='bounced'
3. Soft bounce: 记录事件，3次 soft bounce → 升级为 hard bounce
4. 更新 campaign.bounced_count
```

### 5.4 退订处理

```
邮件注入:
- List-Unsubscribe header (RFC 8058 one-click)
- 底部退订链接 → /api/v1/subscription/unsubscribe/{subscriber_id}?campaign={id}

处理:
1. 记录 tracking_event (type='unsubscribe')
2. 触发 Phase 1 退订状态机
3. 更新 campaign.unsubscribed_count
4. 加入 suppression_list (reason='unsubscribe')
```

---

## 六、权限扩展

在现有 RBAC 基础上新增权限:

```python
class Permission(str, Enum):
    # ... existing ...
    TEMPLATE_READ = "template:read"
    TEMPLATE_WRITE = "template:write"
    CAMPAIGN_READ = "campaign:read"
    CAMPAIGN_WRITE = "campaign:write"
    SEGMENT_READ = "segment:read"
    SEGMENT_WRITE = "segment:write"
    CHANNEL_READ = "channel:read"
    CHANNEL_WRITE = "channel:write"
    TRACKING_READ = "tracking:read"
    REPORT_READ = "report:read"

ROLE_PERMISSIONS = {
    "super_admin": [ALL],
    "tenant_admin": [ALL],
    "member": [
        # existing member permissions...
        Permission.TEMPLATE_READ,
        Permission.CAMPAIGN_READ,
        Permission.SEGMENT_READ,
        Permission.REPORT_READ,
    ],
}
```

---

## 七、关键流程时序

### 7.1 活动发送全链路

```
用户点击"发送" → API: POST /campaigns/{id}/send-now
    │
    ├─ 1. 校验: 模板/列表/渠道就绪
    ├─ 2. campaign.status = 'sending'
    ├─ 3. 触发 Celery: prepare_campaign.delay(campaign_id)
    │
    ▼ [Worker: prepare_campaign]
    ├─ 4. 解析收件人 (lists ∪ segments - exclusions - suppressions)
    ├─ 5. 去重，写入 campaign_jobs (batch_number 分配)
    ├─ 6. 更新 campaign.total_recipients
    ├─ 7. 触发 dispatch_batches.delay(campaign_id)
    │
    ▼ [Worker: dispatch_batches]
    ├─ 8. 检查 paused? → 终止
    ├─ 9. 取 batch N 的所有 pending jobs
    ├─ 10. 逐个 send_email.apply_async(job_id, eta=stagger)
    ├─ 11. sleep(batch_interval_seconds) 或 用 ETA 间隔
    ├─ 12. 递归: dispatch_batches(campaign_id) for next batch
    │
    ▼ [Worker: send_email]
    ├─ 13. 幂等检查 (idempotency_key)
    ├─ 14. 检查 campaign paused flag
    ├─ 15. 选择 SMTP 渠道 (优先级 + 限流)
    ├─ 16. 渲染模板 (Jinja2 + 订阅者数据)
    ├─ 17. 注入追踪 (pixel + link rewrite)
    ├─ 18. SMTP 发送
    ├─ 19. 成功 → job.status='sent', campaign.sent_count++
    └─ 20. 失败 → retry 或 move_to_dead_letter
```

### 7.2 凭据加密流程

```python
# 加密 (写入时)
from cryptography.fernet import Fernet
key = settings.encryption_key  # 从环境变量加载，Base64 编码
fernet = Fernet(key)
encrypted = fernet.encrypt(password.encode())  # 存入 password_encrypted

# 解密 (发送时)
password = fernet.decrypt(channel.password_encrypted).decode()
```

---

## 八、文件结构规划

### 后端新增

```
app/
├── worker/
│   ├── __init__.py
│   ├── celery_app.py             — Celery 实例配置
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── campaign_tasks.py     — 活动准备/调度
│   │   ├── send_tasks.py         — 邮件发送/重试
│   │   ├── tracking_tasks.py     — 事件记录/聚合
│   │   └── report_tasks.py       — 报表生成
│   └── beat_schedule.py          — 定时任务配置
├── models/
│   ├── template.py               — EmailTemplate + TemplateVersion
│   ├── campaign.py               — Campaign + CampaignJob
│   ├── dead_letter.py            — DeadLetterJob
│   ├── smtp_channel.py           — SmtpChannel
│   ├── tracking.py               — TrackingEvent + TrackingLink
│   ├── segment.py                — SegmentRule
│   ├── suppression.py            — SuppressionEntry
│   └── report.py                 — CampaignReport
├── schemas/
│   ├── template.py
│   ├── campaign.py
│   ├── channel.py
│   ├── segment.py
│   ├── tracking.py
│   └── report.py
├── services/
│   ├── template_service.py       — 模板 CRUD + 渲染 + 校验
│   ├── campaign_service.py       — 活动生命周期管理
│   ├── segment_service.py        — 分群规则解析+评估
│   ├── channel_service.py        — SMTP 渠道管理+加解密
│   ├── tracking_service.py       — 追踪事件处理
│   ├── sending_service.py        — 邮件渲染+发送+渠道选择
│   ├── report_service.py         — 报表聚合+导出
│   └── suppression_service.py    — 抑制名单管理
├── api/v1/
│   ├── templates.py
│   ├── campaigns.py
│   ├── segments.py
│   ├── channels.py
│   ├── tracking.py
│   ├── reports.py
│   ├── dead_letter.py
│   └── suppression.py
└── core/
    ├── encryption.py             — Fernet 加解密工具
    ├── template_engine.py        — Jinja2 沙箱 + 安全策略
    └── channel_selector.py       — 渠道选择+故障切换算法
```

### 前端新建

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── router.tsx
│   ├── api/                      — API 客户端 (axios + interceptors)
│   │   ├── client.ts
│   │   ├── templates.ts
│   │   ├── campaigns.ts
│   │   ├── segments.ts
│   │   ├── channels.ts
│   │   └── reports.ts
│   ├── stores/                   — Zustand stores
│   │   ├── authStore.ts
│   │   └── campaignStore.ts
│   ├── pages/                    — (如 4.1 所述)
│   ├── components/               — (如 4.1 所述)
│   ├── hooks/
│   │   ├── usePolling.ts         — 轮询 hook
│   │   └── useCampaignProgress.ts
│   └── types/                    — TypeScript 类型定义
│       ├── template.ts
│       ├── campaign.ts
│       └── common.ts
```

---

## 九、实施优先级

| 阶段 | 范围 | 预估工作量 |
|------|------|-----------|
| P0 | 基础设施: Redis + Celery + Worker docker 服务 | 1d |
| P1 | 数据模型: 全部新表迁移 + Model 定义 | 1d |
| P2 | 模板管理: CRUD + Jinja2 沙箱 + 预览 + 校验 | 2d |
| P3 | SMTP 渠道: CRUD + 加密 + 测试连接 + 故障切换 | 1d |
| P4 | 分群规则: CRUD + 评估引擎 | 1d |
| P5 | 活动管理: CRUD + 收件人解析 + 排期 | 2d |
| P6 | 发送引擎: Celery tasks + 批次调度 + 限流 + 重试 + 死信 | 3d |
| P7 | 追踪系统: 像素 + 链接重写 + 事件处理 + Webhook | 2d |
| P8 | 报表聚合: 统计 + 漏斗 + 导出 | 1d |
| P9 | 前端: 全部页面和组件 | 5d |
| **Total** | | **~19d** |
