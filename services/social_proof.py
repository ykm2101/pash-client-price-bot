import logging
from services.supabase import SupabaseService

logger = logging.getLogger(__name__)

async def get_stats(product_id: int, district: str, supabase_service: SupabaseService) -> int:
    """
    Count price_queries for this product in this district (last 7 days)
    Returns count (0 if less than 5)
    """
    count = await supabase_service.get_social_proof(product_id, district)
    return count if count >= 5 else 0

async def get_demand_count(product_name_raw: str, supabase_service: SupabaseService) -> int:
    """
    Count how many times this product (not in catalog) was requested
    Used for future logic of adding to assortment
    """
    try:
        response = supabase_service.client.table("price_queries") \
            .select("id", count="exact") \
            .ilike("product_name_raw", f"%{product_name_raw}%") \
            .eq("has_pash_offer", False) \
            .execute()

        return response.count if hasattr(response, 'count') else 0
    except Exception as e:
        logger.error(f"Error getting demand count for '{product_name_raw}': {e}")
        return 0
