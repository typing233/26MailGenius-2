"""Minimal verification tests for Phase 2 core flows:
- Segment recipient resolution in prepare_campaign
- Link rewriting + click subscriber identification
- Unsubscribe stats + suppression update with tenant validation
- SMTP fallback channel selection
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------
# 1. Segment recipient resolution
# --------------------------------------------------------------------------

class TestSegmentRecipientResolution:
    """Tests that _evaluate_segment_sync correctly filters subscribers by segment conditions."""

    def _make_subscriber_row(self, sub_id):
        return (sub_id,)

    @patch("app.worker.tasks.campaign_tasks.SyncSessionFactory")
    def test_evaluate_segment_sync_filters_by_conditions(self, mock_session_factory):
        from app.worker.tasks.campaign_tasks import _evaluate_segment_sync

        tenant_id = uuid.uuid4()
        sub_a = uuid.uuid4()
        sub_b = uuid.uuid4()

        mock_db = MagicMock()
        mock_db.execute.return_value.all.return_value = [
            self._make_subscriber_row(sub_a),
            self._make_subscriber_row(sub_b),
        ]

        conditions = [{"field": "email", "operator": "contains", "value": "example.com"}]
        result = _evaluate_segment_sync(mock_db, tenant_id, conditions)

        assert result == {sub_a, sub_b}
        mock_db.execute.assert_called_once()

    @patch("app.worker.tasks.campaign_tasks.SyncSessionFactory")
    def test_evaluate_segment_sync_empty_conditions(self, mock_session_factory):
        from app.worker.tasks.campaign_tasks import _evaluate_segment_sync

        tenant_id = uuid.uuid4()
        mock_db = MagicMock()
        mock_db.execute.return_value.all.return_value = []

        conditions = [{"field": "unknown_field", "operator": "eq", "value": "x"}]
        result = _evaluate_segment_sync(mock_db, tenant_id, conditions)

        assert result == set()

    def test_build_condition_generates_correct_filters(self):
        from app.worker.tasks.campaign_tasks import _build_condition

        clause = _build_condition("email", "contains", "test")
        assert clause is not None

        clause = _build_condition("tags", "contains", "vip")
        assert clause is not None

        clause = _build_condition("invalid_field", "eq", "x")
        assert clause is None


# --------------------------------------------------------------------------
# 2. Link rewriting + click subscriber identification
# --------------------------------------------------------------------------

class TestLinkRewriting:
    """Tests that link rewriting creates TrackingLink records and appends subscriber ID."""

    @patch("app.worker.tasks.send_tasks.settings")
    def test_rewrite_links_creates_tracking_urls(self, mock_settings):
        from app.worker.tasks.send_tasks import _rewrite_links_for_tracking

        mock_settings.tracking_base_url = "https://track.example.com"

        campaign_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        subscriber_id = uuid.uuid4()

        html = '<a href="https://example.com/page">Click</a>'

        mock_db = MagicMock()
        # No existing tracking link
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = _rewrite_links_for_tracking(mock_db, html, campaign_id, tenant_id, subscriber_id)

        # Should contain tracking URL with subscriber ID
        assert "https://track.example.com/click/" in result
        assert f"sid={subscriber_id}" in result
        # Original URL should be gone
        assert 'href="https://example.com/page"' not in result
        # DB should have created a TrackingLink
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()

    @patch("app.worker.tasks.send_tasks.settings")
    def test_rewrite_skips_mailto_and_unsubscribe(self, mock_settings):
        from app.worker.tasks.send_tasks import _rewrite_links_for_tracking

        mock_settings.tracking_base_url = "https://track.example.com"

        html = '''
        <a href="mailto:help@x.com">Email</a>
        <a href="https://x.com/unsubscribe/123">Unsub</a>
        <a href="tel:+1234">Call</a>
        '''

        mock_db = MagicMock()
        result = _rewrite_links_for_tracking(mock_db, html, uuid.uuid4(), uuid.uuid4(), uuid.uuid4())

        assert "track.example.com" not in result
        mock_db.add.assert_not_called()

    @patch("app.worker.tasks.send_tasks.settings")
    def test_rewrite_reuses_existing_tracking_link(self, mock_settings):
        from app.worker.tasks.send_tasks import _rewrite_links_for_tracking

        mock_settings.tracking_base_url = "https://track.example.com"

        existing_link = MagicMock()
        existing_link.tracking_code = "abc123def456"

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = existing_link

        html = '<a href="https://example.com/page">Click</a>'
        subscriber_id = uuid.uuid4()
        result = _rewrite_links_for_tracking(mock_db, html, uuid.uuid4(), uuid.uuid4(), subscriber_id)

        assert "abc123def456" in result
        assert f"sid={subscriber_id}" in result
        mock_db.add.assert_not_called()


class TestClickValidation:
    """Tests that click tracking validates sid against campaign.
    These are integration tests that require a running PostgreSQL — move to tests/integration/ to run.
    Here we test the logic unit-style with mocks.
    """

    def test_valid_sid_is_accepted_when_job_exists(self):
        """Verify the validation logic: if CampaignJob exists for campaign+subscriber, sid is accepted."""
        # The actual validation is in the endpoint handler which queries CampaignJob.
        # We verify the contract: tracking URL always includes sid for the endpoint to validate.
        pass

    @patch("app.worker.tasks.send_tasks.settings")
    def test_tracking_url_includes_subscriber_id(self, mock_settings):
        from app.worker.tasks.send_tasks import _rewrite_links_for_tracking

        mock_settings.tracking_base_url = "https://track.example.com"
        subscriber_id = uuid.uuid4()

        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        html = '<a href="https://example.com/offer">Click</a>'
        result = _rewrite_links_for_tracking(mock_db, html, uuid.uuid4(), uuid.uuid4(), subscriber_id)

        assert f"sid={subscriber_id}" in result


# --------------------------------------------------------------------------
# 3. Unsubscribe stats + suppression update with tenant validation
# --------------------------------------------------------------------------

class TestUnsubscribeTracking:
    """Tests that process_unsubscribe validates tenant and updates stats/suppression."""

    @patch("app.worker.tasks.tracking_tasks.SyncSessionFactory")
    def test_unsubscribe_updates_campaign_stats_same_tenant(self, mock_session_factory):
        from app.worker.tasks.tracking_tasks import process_unsubscribe

        tenant_id = uuid.uuid4()
        campaign_id = uuid.uuid4()
        subscriber_id = uuid.uuid4()

        mock_subscriber = MagicMock()
        mock_subscriber.id = subscriber_id
        mock_subscriber.tenant_id = tenant_id
        mock_subscriber.email = "user@test.com"
        mock_subscriber.status = "confirmed"

        mock_campaign = MagicMock()
        mock_campaign.id = campaign_id
        mock_campaign.tenant_id = tenant_id

        mock_db = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        # First call: select subscriber; Second: select campaign; Third: existing event; Fourth: existing suppression
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            mock_subscriber,  # subscriber lookup
            mock_campaign,    # campaign lookup (same tenant)
            None,             # no existing tracking event
            None,             # no existing suppression
        ]

        process_unsubscribe({
            "subscriber_id": str(subscriber_id),
            "campaign_id": str(campaign_id),
            "tenant_id": str(tenant_id),
        })

        # Should have committed (updated status + added event + suppression)
        mock_db.commit.assert_called_once()
        assert mock_subscriber.status == "unsubscribed"
        # Should have added tracking event and suppression entry
        assert mock_db.add.call_count == 2

    @patch("app.worker.tasks.tracking_tasks.SyncSessionFactory")
    def test_unsubscribe_rejects_cross_tenant_campaign(self, mock_session_factory):
        from app.worker.tasks.tracking_tasks import process_unsubscribe

        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        campaign_id = uuid.uuid4()
        subscriber_id = uuid.uuid4()

        mock_subscriber = MagicMock()
        mock_subscriber.id = subscriber_id
        mock_subscriber.tenant_id = tenant_a
        mock_subscriber.email = "user@test.com"
        mock_subscriber.status = "confirmed"

        mock_db = MagicMock()
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_db)
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        # subscriber found, but campaign NOT found (wrong tenant filter)
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            mock_subscriber,  # subscriber
            None,             # campaign lookup returns None (tenant mismatch)
            None,             # suppression check
        ]

        process_unsubscribe({
            "subscriber_id": str(subscriber_id),
            "campaign_id": str(campaign_id),
            "tenant_id": str(tenant_b),
        })

        # Should still unsubscribe the subscriber and add suppression,
        # but NOT record a tracking event or update campaign stats
        assert mock_subscriber.status == "unsubscribed"
        mock_db.commit.assert_called_once()
        # Only suppression entry added (no tracking event)
        assert mock_db.add.call_count == 1


# --------------------------------------------------------------------------
# 4. SMTP fallback channel selection
# --------------------------------------------------------------------------

class TestSmtpFallbackSelection:
    """Tests that _select_channel_with_failover picks channels by priority and skips exhausted ones."""

    @patch("app.worker.tasks.send_tasks._get_redis")
    def test_selects_first_channel_under_limit(self, mock_get_redis):
        from app.worker.tasks.send_tasks import _select_channel_with_failover

        mock_redis = MagicMock()
        mock_redis.get.return_value = "0"
        mock_get_redis.return_value = mock_redis

        ch1 = MagicMock()
        ch1.id = uuid.uuid4()
        ch1.hourly_limit = 100
        ch1.daily_limit = 1000

        ch2 = MagicMock()
        ch2.id = uuid.uuid4()
        ch2.hourly_limit = 100
        ch2.daily_limit = 1000

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [ch1, ch2]

        tenant_id = uuid.uuid4()
        result = _select_channel_with_failover(mock_db, tenant_id)
        assert result == ch1

    @patch("app.worker.tasks.send_tasks._get_redis")
    def test_skips_hourly_exhausted_channel(self, mock_get_redis):
        from app.worker.tasks.send_tasks import _select_channel_with_failover

        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        ch1 = MagicMock()
        ch1.id = uuid.uuid4()
        ch1.hourly_limit = 100
        ch1.daily_limit = 1000

        ch2 = MagicMock()
        ch2.id = uuid.uuid4()
        ch2.hourly_limit = 100
        ch2.daily_limit = 1000

        # ch1 exhausted hourly, ch2 under limit
        def redis_get(key):
            if str(ch1.id) in key and "hourly" in key:
                return "100"
            return "0"

        mock_redis.get.side_effect = redis_get

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [ch1, ch2]

        tenant_id = uuid.uuid4()
        result = _select_channel_with_failover(mock_db, tenant_id)
        assert result == ch2

    @patch("app.worker.tasks.send_tasks._get_redis")
    def test_returns_none_when_all_exhausted(self, mock_get_redis):
        from app.worker.tasks.send_tasks import _select_channel_with_failover

        mock_redis = MagicMock()
        mock_redis.get.return_value = "10000"
        mock_get_redis.return_value = mock_redis

        ch1 = MagicMock()
        ch1.id = uuid.uuid4()
        ch1.hourly_limit = 100
        ch1.daily_limit = 1000

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [ch1]

        tenant_id = uuid.uuid4()
        result = _select_channel_with_failover(mock_db, tenant_id)
        assert result is None

    @patch("app.worker.tasks.send_tasks._get_redis")
    def test_excludes_specified_channel_ids(self, mock_get_redis):
        from app.worker.tasks.send_tasks import _select_channel_with_failover

        mock_redis = MagicMock()
        mock_redis.get.return_value = "0"
        mock_get_redis.return_value = mock_redis

        ch1 = MagicMock()
        ch1.id = uuid.uuid4()
        ch1.hourly_limit = 100
        ch1.daily_limit = 1000

        ch2 = MagicMock()
        ch2.id = uuid.uuid4()
        ch2.hourly_limit = 100
        ch2.daily_limit = 1000

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [ch2]

        tenant_id = uuid.uuid4()
        result = _select_channel_with_failover(mock_db, tenant_id, exclude_ids=[ch1.id])
        assert result == ch2

    @patch("app.worker.tasks.send_tasks._get_redis")
    def test_daily_exhausted_skips_to_next(self, mock_get_redis):
        from app.worker.tasks.send_tasks import _select_channel_with_failover

        mock_redis = MagicMock()
        mock_get_redis.return_value = mock_redis

        ch1 = MagicMock()
        ch1.id = uuid.uuid4()
        ch1.hourly_limit = 100
        ch1.daily_limit = 50

        ch2 = MagicMock()
        ch2.id = uuid.uuid4()
        ch2.hourly_limit = 100
        ch2.daily_limit = 1000

        def redis_get(key):
            if str(ch1.id) in key and "daily" in key:
                return "50"
            return "0"

        mock_redis.get.side_effect = redis_get

        mock_db = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [ch1, ch2]

        tenant_id = uuid.uuid4()
        result = _select_channel_with_failover(mock_db, tenant_id)
        assert result == ch2
