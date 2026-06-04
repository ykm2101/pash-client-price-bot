import asyncio
import logging
from typing import Optional, List, Dict, Any
from supabase import create_client, Client
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SupabaseService:
    def __init__(self):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY")
        self.client: Client = create_client(url, key)

    async def upsert_user(self, telegram_id: int, username: Optional[str], full_name: Optional[str], language: str = 'ru') -> Dict[str, Any]:
        """Upsert user in users table"""
        data = {
            "telegram_id": telegram_id,
            "username": username,
            "full_name": full_name,
            "language": language,
            "last_seen_at": datetime.utcnow().isoformat()
        }

        try:
            response = self.client.table("users").upsert(data).execute()
            return response.data[0] if response.data else data
        except Exception as e:
            logger.error(f"Error upserting user {telegram_id}: {e}")
            raise

    async def update_user_district(self, telegram_id: int, district: Optional[str], location: Optional[tuple] = None) -> Dict[str, Any]:
        """Update user district and location"""
        data = {"district": district}

        if location:
            lat, lng = location
            data["location"] = f"POINT({lng} {lat})"

        try:
            response = self.client.table("users").update(data).eq("telegram_id", telegram_id).execute()
            return response.data[0] if response.data else data
        except Exception as e:
            logger.error(f"Error updating user district {telegram_id}: {e}")
            raise

    async def get_user(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user by telegram_id"""
        try:
            response = self.client.table("users").select("*").eq("telegram_id", telegram_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error getting user {telegram_id}: {e}")
            return None

    async def lookup_product(self, name: str) -> Optional[Dict[str, Any]]:
        """Lookup product by name or name_aliases"""
        try:
            name_lower = name.lower().strip()

            # First try exact match in name
            response = self.client.table("products").select("*").ilike("name", f"%{name_lower}%").limit(1).execute()
            if response.data:
                return response.data[0]

            # If not found, try through name_aliases (JSONB array)
            # Note: Supabase doesn't have direct JSONB array contains, so we fetch and filter
            all_products = self.client.table("products").select("*").execute()
            for product in all_products.data:
                if product.get("name_aliases"):
                    for alias in product["name_aliases"]:
                        if name_lower in alias.lower():
                            return product

            return None
        except Exception as e:
            logger.error(f"Error looking up product '{name}': {e}")
            return None

    async def get_pvz_list(self) -> List[Dict[str, Any]]:
        """Get list of active PVZ locations"""
        try:
            response = self.client.table("pvz_locations").select("*").eq("is_active", True).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error getting PVZ list: {e}")
            return []

    async def insert_query(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert price query"""
        try:
            response = self.client.table("price_queries").insert(data).execute()
            return response.data[0] if response.data else data
        except Exception as e:
            logger.error(f"Error inserting query: {e}")
            raise

    async def get_social_proof(self, product_id: int, district: Optional[str]) -> int:
        """Count price_queries for this product in this district (last 7 days)"""
        try:
            seven_days_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()

            query = self.client.table("price_queries").select("id", count="exact").gt("created_at", seven_days_ago).eq("product_id", product_id)

            if district:
                query = query.eq("district", district)

            response = query.execute()
            return response.count if hasattr(response, 'count') else 0
        except Exception as e:
            logger.error(f"Error getting social proof for product {product_id}, district {district}: {e}")
            return 0

    async def find_district_by_coords(self, lat: float, lng: float) -> Optional[str]:
        """Find nearest district by coordinates"""
        try:
            # Get all districts
            response = self.client.table("micro_districts").select("id, name, centroid_lat, centroid_lng").execute()

            if not response.data:
                return None

            # Calculate distance to each centroid and find nearest
            min_distance = float('inf')
            nearest_district = None

            for district in response.data:
                centroid_lat = district.get("centroid_lat")
                centroid_lng = district.get("centroid_lng")

                if centroid_lat is None or centroid_lng is None:
                    continue

                # Simple distance calculation (good enough for Almaty)
                distance = ((lat - centroid_lat) ** 2 + (lng - centroid_lng) ** 2) ** 0.5

                if distance < min_distance:
                    min_distance = distance
                    nearest_district = district["name"]

            return nearest_district
        except Exception as e:
            logger.error(f"Error finding district by coords ({lat}, {lng}): {e}")
            return None

    async def normalize_district(self, text: str) -> Optional[str]:
        """Normalize district name by matching name_aliases"""
        try:
            text_lower = text.lower().strip()

            response = self.client.table("micro_districts").select("name, name_aliases").execute()

            for district in response.data:
                if text_lower in district.get("name", "").lower():
                    return district["name"]

                if district.get("name_aliases"):
                    for alias in district["name_aliases"]:
                        if text_lower in alias.lower() or alias.lower() in text_lower:
                            return district["name"]

            return None
        except Exception as e:
            logger.error(f"Error normalizing district '{text}': {e}")
            return None

    async def update_user_last_seen(self, telegram_id: int):
        """Update user's last_seen_at"""
        try:
            self.client.table("users").update({"last_seen_at": datetime.utcnow().isoformat()}).eq("telegram_id", telegram_id).execute()
        except Exception as e:
            logger.error(f"Error updating last_seen for {telegram_id}: {e}")
