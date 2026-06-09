"""
Scheduled posts to @pash_channel.
All jobs run at 08:00 Almaty time (UTC+5).
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.publisher import (
    post_weekly_index,
    post_seasonal,
    post_hit_of_week,
    post_price_alert,
)

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def create_scheduler(bot) -> AsyncIOScheduler:
    """Create and configure the scheduler. Call once at startup."""
    global _scheduler
    scheduler = AsyncIOScheduler(timezone="Asia/Almaty")

    # Tuesday 08:00 — weekly price index
    scheduler.add_job(
        post_weekly_index, "cron",
        day_of_week="tue", hour=8, minute=0,
        args=[bot],
        id="weekly_index",
        replace_existing=True,
    )

    # Wednesday 08:00 — seasonal signal
    scheduler.add_job(
        post_seasonal, "cron",
        day_of_week="wed", hour=8, minute=0,
        args=[bot],
        id="seasonal",
        replace_existing=True,
    )

    # Thursday 08:00 — hit of the week
    scheduler.add_job(
        post_hit_of_week, "cron",
        day_of_week="thu", hour=8, minute=0,
        args=[bot],
        id="hit_of_week",
        replace_existing=True,
    )

    # Friday 08:00 — price alert
    scheduler.add_job(
        post_price_alert, "cron",
        day_of_week="fri", hour=8, minute=0,
        args=[bot],
        id="price_alert",
        replace_existing=True,
    )

    _scheduler = scheduler
    logger.info("Scheduler configured: 4 jobs (tue/wed/thu/fri 08:00 Almaty)")
    return scheduler
