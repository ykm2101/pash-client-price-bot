"""Referral link generation and stats."""
from config import BOT_USERNAME
import logging

logger = logging.getLogger(__name__)


def generate_referral_link(telegram_id: int) -> str:
    """Generate personal referral link for a user."""
    return f"https://t.me/{BOT_USERNAME}?start=ref_{telegram_id}"


async def get_referral_stats(telegram_id: int, supabase) -> dict:
    """
    Get referral stats for a user.
    Returns: {"count": N, "converted": M}
    converted = users who made at least one price query
    """
    try:
        # Count users who were referred by this user
        referrer_key = str(telegram_id)
        response = (
            supabase.client.table("users")
            .select("telegram_id")
            .eq("referred_by", referrer_key)
            .execute()
        )
        referred_users = response.data or []
        count = len(referred_users)

        if count == 0:
            return {"count": 0, "converted": 0}

        # Count how many of them made at least one price query
        referred_ids = [u["telegram_id"] for u in referred_users]
        converted = 0
        for uid in referred_ids:
            q = (
                supabase.client.table("price_queries")
                .select("id", count="exact")
                .eq("telegram_id", uid)
                .limit(1)
                .execute()
            )
            if getattr(q, "count", 0) and q.count > 0:
                converted += 1

        return {"count": count, "converted": converted}

    except Exception as e:
        logger.error(f"Error getting referral stats for {telegram_id}: {e}")
        return {"count": 0, "converted": 0}
