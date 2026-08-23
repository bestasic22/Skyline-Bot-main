from __future__ import annotations

import datetime
import traceback
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

import storage
from skylinebot.console.logging import logger
from skylinebot.engine.bot_runtime import AutoShardedBot
from skylinebot.src.checks import checks
from skylinebot.style import color
from skylinebot.workflows import shop as shop_flow


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Shop(commands.Cog):
    def __init__(self, bot: AutoShardedBot):
        self.bot = bot

        class CogInfo:
            name = "Shop"
            category = "Economy"
            description = "Guild Shop"
            hidden = False
            emoji = bot.emoji.ECONOMY

        self.cog_info = CogInfo

    async def _ensure_shop(self, guild_id: int) -> dict[str, Any]:
        return await shop_flow.ensure_shop_settings(guild_id)

    async def _guild_plan_tier(self, guild_id: int) -> str:
        return await shop_flow.guild_plan_tier(guild_id)

    def _format_amount(self, value: float, currency_symbol: str) -> str:
        return f"{currency_symbol} {round(max(0.0, value), 2):,.2f}"

    def _find_product(
        self,
        products: list[dict[str, Any]],
        token: str,
    ) -> dict[str, Any] | None:
        wanted = str(token or "").strip()
        if not wanted:
            return None
        if wanted.isdigit():
            wanted_id = int(wanted)
            for product in products:
                if int(product.get("id") or 0) == wanted_id:
                    return product
        wanted_upper = wanted.upper()
        for product in products:
            if str(product.get("sku") or "").strip().upper() == wanted_upper:
                return product
        for product in products:
            if str(product.get("name") or "").strip().lower() == wanted.lower():
                return product
        for product in products:
            if wanted.lower() in str(product.get("name") or "").strip().lower():
                return product
        return None

    async def _require_order(
        self,
        *,
        guild_id: int,
        order_code: str,
    ) -> dict[str, Any] | None:
        row = await storage.shop_orders.get(guild_id=guild_id, order_code=str(order_code or "").strip().upper())
        if not row:
            return None
        return shop_flow.normalize_order(row)

    async def _build_product_rows(
        self,
        *,
        guild_id: int,
        member: discord.Member,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        settings, products = await shop_flow.products_for_member(guild_id, member, include_disabled=False)
        products = [row for row in products if bool(row.get("enabled"))]
        return settings, products

    def _is_admin_like(self, member: discord.Member | None) -> bool:
        if member is None:
            return False
        perms = getattr(member, "guild_permissions", None)
        return bool(
            getattr(perms, "administrator", False)
            or getattr(perms, "manage_guild", False)
        )

    async def _deliver_if_enabled(
        self,
        *,
        settings: dict[str, Any],
        order_id: int,
        reviewer_user_id: int | None = None,
    ) -> tuple[bool, str]:
        if not bool(settings.get("auto_delivery")):
            return True, "Payment confirmed. Auto delivery is disabled by admin."
        ok, message, _row = await shop_flow.finalize_paid_order(
            bot=self.bot,
            order_id=order_id,
            reviewer_user_id=reviewer_user_id,
        )
        if ok:
            return True, message
        support_hint = shop_flow.support_contact_hint(settings)
        return False, f"{message}\n{support_hint}"

    def _support_view(self, guild_id: int, settings: dict[str, Any]) -> discord.ui.View | None:
        channel_id = _safe_int(settings.get("admin_contact_channel_id"), 0)
        if channel_id <= 0:
            return None
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Open Support Channel",
                style=discord.ButtonStyle.link,
                url=f"https://discord.com/channels/{int(guild_id)}/{channel_id}",
            )
        )
        return view

    @commands.hybrid_group(
        name="shop",
        help="คำสั่งร้านค้ากิลด์",
        with_app_command=True,
        invoke_without_command=True,
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=10, type=commands.BucketType.user)
    async def shop(self, ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        await self.shop_list(ctx)

    @shop.command(name="list", help="แสดงสินค้าที่มีอยู่ในกิลด์นี้")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def shop_list(self, ctx: commands.Context):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        try:
            settings, products = await self._build_product_rows(guild_id=ctx.guild.id, member=ctx.author)
            plan_tier = await self._guild_plan_tier(ctx.guild.id)
            if not bool(settings.get("enabled")):
                return await ctx.send("Guild shop is currently disabled.")
            if not products:
                return await ctx.send("No products are available for your roles right now.")

            symbol = str(settings.get("currency_symbol") or "THB")
            product_cap = shop_flow.product_limit_for_plan(plan_tier)
            lines: list[str] = []
            for product in products[:20]:
                sku = str(product.get("sku") or f"P{int(product.get('id') or 0)}")
                name = str(product.get("name") or "Product")
                price = _safe_float(product.get("price"), 0.0)
                stock = _safe_int(product.get("stock"), 0)
                stock_label = "Unlimited" if stock < 0 else f"{stock:,}"
                lines.append(
                    f"`{sku}` | **{name}** | {self._format_amount(price, symbol)} | Stock: `{stock_label}`"
                )

            embed = discord.Embed(
                title=f"Guild Shop - {ctx.guild.name} ({plan_tier.capitalize()})",
                description="\n".join(lines),
                color=color.blue,
            )
            embed.set_footer(text=f"Plan cap: {product_cap} products | Use /shop buy <sku> <quantity> <method>")
            await ctx.send(embed=embed)
        except Exception:
            logger.error(f"Shop list failed: {traceback.format_exc()}")
            await ctx.send("Unable to load shop products right now.")

    @shop.command(name="buy", help="สร้างคำสั่งซื้อใหม่")
    @app_commands.describe(
        product="SKU or product name",
        quantity="How many items you want to buy",
        method="Payment method",
    )
    @app_commands.choices(
        method=[
            app_commands.Choice(name="manual", value="manual"),
            app_commands.Choice(name="truemoney_gift", value="truemoney_gift"),
            app_commands.Choice(name="shipok", value="shipok"),
            app_commands.Choice(name="wallet", value="wallet"),
        ]
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=8, type=commands.BucketType.user)
    async def shop_buy(
        self,
        ctx: commands.Context,
        product: str,
        quantity: int = 1,
        method: str = "manual",
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        try:
            settings, products = await self._build_product_rows(guild_id=ctx.guild.id, member=ctx.author)
            plan_tier = await self._guild_plan_tier(ctx.guild.id)
            if not bool(settings.get("enabled")):
                return await ctx.send("Guild shop is currently disabled.")

            selected = self._find_product(products, product)
            if not selected:
                return await ctx.send("Product not found or not visible for your roles.")
            if not shop_flow.can_buy_product(
                role_ids={role.id for role in list(ctx.author.roles or [])},
                product=selected,
            ):
                return await ctx.send("You do not have permission to buy this product.")

            qty = max(1, min(100, int(quantity or 1)))
            stock = _safe_int(selected.get("stock"), 0)
            if stock >= 0 and stock < qty:
                return await ctx.send(f"Insufficient stock. Available: {stock}")

            payment_method = shop_flow.normalize_payment_mode(method)
            if payment_method == "truemoney_gift" and not shop_flow.is_shop_feature_allowed(plan_tier, "payment_truemoney_gift"):
                return await ctx.send("TrueMoney gift payment requires Silver+ plan.")
            if payment_method == "shipok" and not shop_flow.is_shop_feature_allowed(plan_tier, "payment_shipok"):
                return await ctx.send("SHIPOK/SlipOK payment requires Gole+ plan.")
            if payment_method == "wallet" and not bool(settings.get("allow_wallet_payment")):
                return await ctx.send("Wallet payment is disabled by guild admin.")
            if payment_method == "truemoney_gift" and not bool(settings.get("truemoney_gift_enabled")):
                return await ctx.send("TrueMoney gift payment is disabled by guild admin.")
            if payment_method == "shipok" and not bool(settings.get("shipok_enabled")):
                return await ctx.send("SlipOK/SHIPOK payment is disabled by guild admin.")

            order = await shop_flow.create_order(
                guild_id=ctx.guild.id,
                user_id=ctx.author.id,
                product=selected,
                quantity=qty,
                payment_method=payment_method,
                currency_symbol=str(settings.get("currency_symbol") or "THB"),
            )

            if payment_method == "wallet":
                ok_wallet, wallet_message, _wallet = await shop_flow.debit_economy_wallet(
                    guild_id=ctx.guild.id,
                    user_id=ctx.author.id,
                    amount=_safe_float(order.get("total_price"), 0.0),
                )
                if not ok_wallet:
                    await storage.shop_orders.update(
                        id=int(order.get("id") or 0),
                        verify_note=str(wallet_message)[:500],
                        updated_at=_utc_now(),
                    )
                    return await ctx.send(
                        f"Order `{order.get('order_code')}` created but wallet payment failed.\n{wallet_message}"
                    )
                await shop_flow.mark_order_wallet_paid(
                    order_id=int(order.get("id") or 0),
                    note=wallet_message,
                )
                ok_deliver, deliver_message = await self._deliver_if_enabled(
                    settings=settings,
                    order_id=int(order.get("id") or 0),
                    reviewer_user_id=ctx.author.id,
                )
                support_view = None if ok_deliver else self._support_view(ctx.guild.id, settings)
                return await ctx.send(
                    f"Wallet payment successful for order `{order.get('order_code')}`.\n{deliver_message}",
                    view=support_view,
                )

            amount_label = self._format_amount(
                _safe_float(order.get("total_price"), 0.0),
                str(order.get("currency_symbol") or settings.get("currency_symbol") or "THB"),
            )
            if payment_method == "truemoney_gift":
                instruction = f"Submit payment using `/shop pay {order.get('order_code')} <truemoney_gift_link>`"
            elif payment_method == "shipok":
                instruction = f"Submit payment using `/shop pay {order.get('order_code')} <slip_url>` or attach slip file"
            else:
                instruction = f"Submit payment proof using `/shop pay {order.get('order_code')} <reference>`"
            await ctx.send(
                f"Order created: `{order.get('order_code')}`\n"
                f"Product: **{selected.get('name')}** x{qty}\n"
                f"Total: **{amount_label}**\n"
                f"Method: **{payment_method}**\n"
                f"{instruction}"
            )
        except Exception:
            logger.error(f"Shop buy failed: {traceback.format_exc()}")
            await ctx.send("Unable to create order right now.")

    @shop.command(name="pay", help="ส่งหลักฐานการชำระเงินสำหรับการสั่งซื้อ")
    @app_commands.describe(
        order_code="Order code, for example S0001-000123",
        transfer_link="TrueMoney gift link or payment reference",
        slip_url="Slip image URL for SHIPOK/SlipOK",
        slip_qr_payload="Slip QR payload (optional)",
        slip="Slip image file (optional)",
    )
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    async def shop_pay(
        self,
        ctx: commands.Context,
        order_code: str,
        transfer_link: str = "",
        slip_url: str = "",
        slip_qr_payload: str = "",
        slip: discord.Attachment | None = None,
    ):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        try:
            order = await self._require_order(guild_id=ctx.guild.id, order_code=order_code)
            if not order:
                return await ctx.send("Order not found.")
            is_admin = self._is_admin_like(ctx.author)
            if int(order.get("user_id") or 0) != ctx.author.id and not is_admin:
                return await ctx.send("You can only submit payment for your own orders.")
            if str(order.get("status") or "") in {
                shop_flow.ORDER_STATUS_DELIVERED,
                shop_flow.ORDER_STATUS_CANCELLED,
            }:
                return await ctx.send("This order is already closed.")

            settings = await self._ensure_shop(ctx.guild.id)
            slip_attachment = slip
            if slip_attachment is None:
                attachments = list(getattr(getattr(ctx, "message", None), "attachments", []) or [])
                if attachments:
                    slip_attachment = attachments[0]
            slip_url_text = str(slip_url or "").strip()
            if slip_attachment is not None:
                try:
                    file_size = int(getattr(slip_attachment, "size", 0) or 0)
                except Exception:
                    file_size = 0
                if file_size > 10 * 1024 * 1024:
                    return await ctx.send("Slip file is too large (max 10MB).")
                attachment_url = str(getattr(slip_attachment, "url", "") or "").strip()
                if attachment_url:
                    slip_url_text = attachment_url

            verify_status, verify_note = await shop_flow.verify_order_evidence(
                order=order,
                settings=settings,
                transfer_link=transfer_link,
                slip_url=slip_url_text,
                slip_qr_payload=slip_qr_payload,
            )
            next_status = shop_flow.ORDER_STATUS_PENDING_REVIEW
            paid_at = None
            if verify_status == "approved":
                next_status = shop_flow.ORDER_STATUS_PAID
                paid_at = _utc_now()
            elif verify_status == "rejected":
                next_status = shop_flow.ORDER_STATUS_REJECTED
            updated = await storage.shop_orders.update(
                id=int(order.get("id") or 0),
                payment_evidence_link=(str(transfer_link or slip_url_text or "")[:500]),
                payment_reference=str(slip_qr_payload or "")[:900],
                verify_status=verify_status,
                verify_note=str(verify_note or "")[:500],
                status=next_status,
                paid_at=paid_at,
                updated_at=_utc_now(),
            )
            normalized = shop_flow.normalize_order(updated)

            if verify_status == "approved":
                ok_deliver, deliver_message = await self._deliver_if_enabled(
                    settings=settings,
                    order_id=int(normalized.get("id") or 0),
                    reviewer_user_id=ctx.author.id if is_admin else None,
                )
                if ok_deliver:
                    return await ctx.send(f"Payment approved for `{normalized.get('order_code')}`.\n{deliver_message}")
                return await ctx.send(
                    f"Payment approved but delivery failed.\n{deliver_message}",
                    view=self._support_view(ctx.guild.id, settings),
                )
            if verify_status == "rejected":
                return await ctx.send(f"Payment rejected for `{normalized.get('order_code')}`.\n{verify_note}")
            return await ctx.send(
                f"Payment evidence received for `{normalized.get('order_code')}`.\n"
                f"Status: `{verify_status}`\n{verify_note}"
            )
        except Exception:
            logger.error(f"Shop pay failed: {traceback.format_exc()}")
            await ctx.send("Unable to verify payment right now.")

    @shop.command(name="status", help="ตรวจสอบสถานะการสั่งซื้อของคุณ")
    @app_commands.describe(order_code="Optional order code")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    async def shop_status(self, ctx: commands.Context, order_code: str = ""):
        if not ctx.guild or not isinstance(ctx.author, discord.Member):
            return await ctx.send("This command can only be used in a server.")
        try:
            code = str(order_code or "").strip().upper()
            if code:
                order = await self._require_order(guild_id=ctx.guild.id, order_code=code)
                if not order:
                    return await ctx.send("Order not found.")
                if int(order.get("user_id") or 0) != ctx.author.id and not self._is_admin_like(ctx.author):
                    return await ctx.send("You can only view your own order.")
                await ctx.send(
                    f"Order `{order.get('order_code')}`\n"
                    f"Status: `{order.get('status')}`\n"
                    f"Verify: `{order.get('verify_status')}`\n"
                    f"Delivery: `{order.get('delivery_status')}`\n"
                    f"Note: {order.get('verify_note') or order.get('delivery_note') or '-'}"
                )
                return

            orders = await storage.shop_orders.gets(guild_id=ctx.guild.id, user_id=ctx.author.id) or []
            orders = sorted(orders, key=lambda row: int(row.get("id") or 0), reverse=True)[:8]
            if not orders:
                return await ctx.send("You do not have any orders yet.")
            lines: list[str] = []
            for row in orders:
                item = shop_flow.normalize_order(row)
                lines.append(
                    f"`{item.get('order_code')}` | `{item.get('status')}` | `{item.get('delivery_status')}`"
                )
            await ctx.send("Your recent orders:\n" + "\n".join(lines))
        except Exception:
            logger.error(f"Shop status failed: {traceback.format_exc()}")
            await ctx.send("Unable to load your order status.")

    @shop.command(name="approve", help="อนุมัติคำสั่งซื้อด้วยตนเอง (ผู้ดูแลระบบ)")
    @app_commands.describe(order_code="Order code", note="Optional approval note")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    async def shop_approve(
        self,
        ctx: commands.Context,
        order_code: str,
        *,
        note: str = "",
    ):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        try:
            order = await self._require_order(guild_id=ctx.guild.id, order_code=order_code)
            if not order:
                return await ctx.send("Order not found.")
            verified = await shop_flow.mark_order_verified(
                order_id=int(order.get("id") or 0),
                approved=True,
                note=note or "Approved by guild admin",
                reviewer_user_id=ctx.author.id,
            )
            if not verified:
                return await ctx.send("Unable to update order.")
            settings = await self._ensure_shop(ctx.guild.id)
            ok_deliver, deliver_message = await self._deliver_if_enabled(
                settings=settings,
                order_id=int(verified.get("id") or 0),
                reviewer_user_id=ctx.author.id,
            )
            if ok_deliver:
                return await ctx.send(f"Order `{verified.get('order_code')}` approved.\n{deliver_message}")
            return await ctx.send(
                f"Order approved but delivery failed.\n{deliver_message}",
                view=self._support_view(ctx.guild.id, settings),
            )
        except Exception:
            logger.error(f"Shop approve failed: {traceback.format_exc()}")
            await ctx.send("Unable to approve this order right now.")

    @shop.command(name="reject", help="ปฏิเสธคำสั่งซื้อด้วยตนเอง (ผู้ดูแลระบบ)")
    @app_commands.describe(order_code="Order code", note="Reason for rejection")
    @checks.ignore_check()
    @checks.blacklist_check()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(rate=2, per=6, type=commands.BucketType.user)
    async def shop_reject(
        self,
        ctx: commands.Context,
        order_code: str,
        *,
        note: str = "",
    ):
        if not ctx.guild:
            return await ctx.send("This command can only be used in a server.")
        try:
            order = await self._require_order(guild_id=ctx.guild.id, order_code=order_code)
            if not order:
                return await ctx.send("Order not found.")
            rejected = await shop_flow.mark_order_verified(
                order_id=int(order.get("id") or 0),
                approved=False,
                note=note or "Rejected by guild admin",
                reviewer_user_id=ctx.author.id,
            )
            if not rejected:
                return await ctx.send("Unable to update order.")
            await ctx.send(f"Order `{rejected.get('order_code')}` rejected.")
        except Exception:
            logger.error(f"Shop reject failed: {traceback.format_exc()}")
            await ctx.send("Unable to reject this order right now.")


async def setup(bot):
    await bot.add_cog(Shop(bot))


