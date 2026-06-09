"""
Automated content publisher for @pash_channel.
All posts: Kazakh first, then Russian. Never mention store names.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from config import TELEGRAM_CHANNEL_ID
from services.supabase import SupabaseService

logger = logging.getLogger(__name__)

ALMATY_TZ = timezone(timedelta(hours=5))


def _fmt(price) -> str:
    """Format price as integer with space thousands separator."""
    try:
        return f"{int(price):,}".replace(",", " ")
    except (TypeError, ValueError):
        return str(price)


# ─── 1. WEEKLY PRICE INDEX ──────────────────────────────────────────────────

async def post_weekly_index(bot) -> None:
    """
    Top-5 products where market price (magazin) is highest vs PÄSH price.
    Published every Tuesday 08:00.
    """
    supabase = SupabaseService()
    try:
        # Latest magazin snapshot per product joined to our_price
        response = supabase.client.rpc("get_weekly_index_data").execute()

        # Fallback: manual query via table API
        products_resp = supabase.client.table("products").select("id, name, our_price").not_.is_("our_price", "null").execute()
        products = {p["id"]: p for p in (products_resp.data or [])}

        snapshots_resp = (
            supabase.client.table("price_snapshots")
            .select("product_id, price, recorded_at")
            .eq("source", "magazin")
            .order("recorded_at", desc=True)
            .execute()
        )

        # Take latest snapshot per product
        latest: dict = {}
        for snap in (snapshots_resp.data or []):
            pid = snap["product_id"]
            if pid not in latest:
                latest[pid] = snap

        # Calculate diff % and sort
        items = []
        for pid, snap in latest.items():
            product = products.get(pid)
            if not product or not product.get("our_price"):
                continue
            our = float(product["our_price"])
            market = float(snap["price"])
            if our <= 0:
                continue
            diff_pct = (market - our) / our * 100
            items.append({
                "name": product["name"],
                "our_price": our,
                "market_price": market,
                "diff_pct": diff_pct,
            })

        if not items:
            logger.info("post_weekly_index: no data, skipping")
            return

        items.sort(key=lambda x: x["diff_pct"], reverse=True)
        top5 = items[:5]

        lines_kz = ["PASH индексі — аптаның бағасы 🥑", "Дүкендерде қымбаттады:"]
        lines_ru = ["Индекс PASH — цены недели 🥑", "В магазинах подорожало:"]

        for it in top5:
            sign = "↑" if it["diff_pct"] > 0 else "↓"
            lines_kz.append(f"{sign} {it['name'].capitalize()} {abs(int(it['diff_pct']))}%")
            lines_ru.append(f"{sign} {it['name'].capitalize()} {abs(int(it['diff_pct']))}%")

        lines_kz += ["Бізде өзгеріссіз.", "pash.kz"]
        lines_ru += ["У нас без изменений.", "pash.kz"]

        text = "\n".join(lines_kz) + "\n\n---\n\n" + "\n".join(lines_ru)
        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=text)
        logger.info("post_weekly_index: published")

    except Exception as e:
        logger.error(f"post_weekly_index error: {e}", exc_info=True)


# ─── 2. SEASONAL POST ────────────────────────────────────────────────────────

async def post_seasonal(bot) -> None:
    """
    Product with biggest price drop over last 14 days = seasonal signal.
    Published every Wednesday 08:00.
    """
    supabase = SupabaseService()
    try:
        cutoff = (datetime.now(ALMATY_TZ) - timedelta(days=14)).isoformat()

        snapshots_resp = (
            supabase.client.table("price_snapshots")
            .select("product_id, price, recorded_at")
            .gte("recorded_at", cutoff)
            .order("recorded_at", desc=False)
            .execute()
        )
        snaps = snapshots_resp.data or []

        if len(snaps) < 2:
            logger.info("post_seasonal: not enough data, skipping")
            return

        # First and last price per product
        first: dict = {}
        last: dict = {}
        for s in snaps:
            pid = s["product_id"]
            if pid not in first:
                first[pid] = s
            last[pid] = s

        best_drop = None
        best_pid = None
        for pid in first:
            if pid not in last:
                continue
            old_price = float(first[pid]["price"])
            new_price = float(last[pid]["price"])
            if old_price <= 0:
                continue
            drop = (old_price - new_price) / old_price * 100
            if best_drop is None or drop > best_drop:
                best_drop = drop
                best_pid = pid
                best_price = new_price

        if best_pid is None or best_drop < 5:
            logger.info("post_seasonal: no significant drop found, skipping")
            return

        prod_resp = supabase.client.table("products").select("name").eq("id", best_pid).execute()
        name = prod_resp.data[0]["name"].capitalize() if prod_resp.data else "Товар"

        text = (
            f"{name} маусымы келді 🍊\n"
            f"Қазір ең төменгі баға.\n"
            f"{_fmt(best_price)}₸/кг — тек осы аптада.\n"
            f"pash.kz\n\n"
            f"---\n\n"
            f"Сезон {name.lower()} 🍊\n"
            f"Сейчас самая низкая цена.\n"
            f"{_fmt(best_price)}₸/кг — только эта неделя.\n"
            f"pash.kz"
        )
        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=text)
        logger.info(f"post_seasonal: published for {name}")

    except Exception as e:
        logger.error(f"post_seasonal error: {e}", exc_info=True)


# ─── 3. HIT OF THE WEEK ──────────────────────────────────────────────────────

async def post_hit_of_week(bot) -> None:
    """
    Product with most kg sold in last 7 days (order_items → fallback price_queries).
    Published every Thursday 08:00.
    """
    supabase = SupabaseService()
    try:
        cutoff = (datetime.now(ALMATY_TZ) - timedelta(days=7)).isoformat()

        # Try order_items first
        orders_resp = (
            supabase.client.table("orders")
            .select("id")
            .gte("created_at", cutoff)
            .execute()
        )
        order_ids = [o["id"] for o in (orders_resp.data or [])]

        hit_name = None
        hit_qty = None

        if order_ids:
            items_resp = (
                supabase.client.table("order_items")
                .select("product_name, quantity")
                .in_("order_id", order_ids)
                .execute()
            )
            totals: dict = {}
            for item in (items_resp.data or []):
                n = item["product_name"]
                totals[n] = totals.get(n, 0) + float(item["quantity"] or 0)

            if totals:
                hit_name = max(totals, key=lambda k: totals[k])
                hit_qty = totals[hit_name]

        # Fallback: price_queries
        if not hit_name:
            pq_resp = (
                supabase.client.table("price_queries")
                .select("product_name_raw")
                .gte("created_at", cutoff)
                .not_.is_("product_name_raw", "null")
                .execute()
            )
            counts: dict = {}
            for row in (pq_resp.data or []):
                n = (row["product_name_raw"] or "").lower().strip()
                if n:
                    counts[n] = counts.get(n, 0) + 1

            if not counts:
                logger.info("post_hit_of_week: no data, skipping")
                return

            hit_name = max(counts, key=lambda k: counts[k])
            hit_qty = counts[hit_name]

        # Next delivery from trips
        trips_resp = (
            supabase.client.table("trips")
            .select("trip_date")
            .gte("trip_date", datetime.now(ALMATY_TZ).date().isoformat())
            .order("trip_date")
            .limit(1)
            .execute()
        )
        if trips_resp.data:
            trip_dt = datetime.fromisoformat(trips_resp.data[0]["trip_date"])
            DAYS_KZ = ["Дүйсенбі", "Сейсенбі", "Сәрсенбі", "Бейсенбі", "Жұма", "Сенбі", "Жексенбі"]
            DAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
            day_kz = DAYS_KZ[trip_dt.weekday()]
            day_ru = DAYS_RU[trip_dt.weekday()]
        else:
            day_kz = "@pash_club-да анықта"
            day_ru = "уточняй в @pash_club"

        name_cap = hit_name.capitalize()
        qty_str = f"{int(hit_qty)}" if hit_qty and hit_qty == int(hit_qty) else f"{hit_qty:.1f}"

        text = (
            f"Аптаның хиті — {name_cap} 🏆\n"
            f"{qty_str} кг бір рейспен кетті.\n"
            f"Келесі жеткізу — {day_kz}.\n"
            f"pash.kz\n\n"
            f"---\n\n"
            f"Хит недели — {name_cap} 🏆\n"
            f"{qty_str} кг разобрали за один рейс.\n"
            f"Следующая доставка — {day_ru}.\n"
            f"pash.kz"
        )
        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=text)
        logger.info(f"post_hit_of_week: published for {hit_name}")

    except Exception as e:
        logger.error(f"post_hit_of_week error: {e}", exc_info=True)


# ─── 4. PRICE ALERT ──────────────────────────────────────────────────────────

async def post_price_alert(bot) -> None:
    """
    Product with biggest price change (±) in last 7 days.
    Only publishes if change > 10%. Published every Friday 08:00.
    """
    supabase = SupabaseService()
    try:
        cutoff = (datetime.now(ALMATY_TZ) - timedelta(days=7)).isoformat()

        snaps_resp = (
            supabase.client.table("price_snapshots")
            .select("product_id, price, recorded_at")
            .gte("recorded_at", cutoff)
            .order("recorded_at")
            .execute()
        )
        snaps = snaps_resp.data or []

        if len(snaps) < 2:
            logger.info("post_price_alert: not enough data, skipping")
            return

        # First and last per product
        first: dict = {}
        last: dict = {}
        for s in snaps:
            pid = s["product_id"]
            if pid not in first:
                first[pid] = s
            last[pid] = s

        best_change = None  # biggest abs change
        best_pid = None
        for pid in first:
            if pid not in last or first[pid]["recorded_at"] == last[pid]["recorded_at"]:
                continue
            old_p = float(first[pid]["price"])
            new_p = float(last[pid]["price"])
            if old_p <= 0:
                continue
            change_pct = (new_p - old_p) / old_p * 100
            if best_change is None or abs(change_pct) > abs(best_change):
                best_change = change_pct
                best_pid = pid
                old_price = old_p
                new_price = new_p

        if best_pid is None or abs(best_change) < 10:
            logger.info(f"post_price_alert: max change {best_change:.1f}% < 10%, skipping")
            return

        prod_resp = supabase.client.table("products").select("name").eq("id", best_pid).execute()
        name = prod_resp.data[0]["name"].capitalize() if prod_resp.data else "Товар"
        change_int = int(abs(best_change))

        if best_change > 0:
            text = (
                f"📈 {name} дүкендерде қымбаттады\n"
                f"{_fmt(old_price)}₸ → {_fmt(new_price)}₸/кг (+{change_int}%)\n"
                f"Бізде өзгеріссіз.\n"
                f"pash.kz\n\n"
                f"---\n\n"
                f"📈 {name} подорожал в магазинах\n"
                f"{_fmt(old_price)}₸ → {_fmt(new_price)}₸/кг (+{change_int}%)\n"
                f"У нас без изменений.\n"
                f"pash.kz"
            )
        else:
            text = (
                f"🔥 {name} бағасы түсті\n"
                f"{_fmt(old_price)}₸ → {_fmt(new_price)}₸/кг\n"
                f"Қазір алу тиімді.\n"
                f"pash.kz\n\n"
                f"---\n\n"
                f"🔥 {name} подешевел\n"
                f"{_fmt(old_price)}₸ → {_fmt(new_price)}₸/кг\n"
                f"Хорошее время брать.\n"
                f"pash.kz"
            )

        await bot.send_message(chat_id=TELEGRAM_CHANNEL_ID, text=text)
        logger.info(f"post_price_alert: published for {name}, change={best_change:.1f}%")

    except Exception as e:
        logger.error(f"post_price_alert error: {e}", exc_info=True)
