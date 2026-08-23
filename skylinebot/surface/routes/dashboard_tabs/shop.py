from __future__ import annotations

from typing import Any
from skylinebot.workflows import shop as shop_flow

from .. import dashboard_core as core


def _render_shop(
    session: dict[str, Any],
    guilds: list[dict[str, Any]],
    current_guild: dict[str, Any],
    bot_guild: Any,
    state: dict[str, Any],
    notice: str | None = None,
    *,
    active_tab_slug: str = "shop",
) -> str:
    _core = core
    _escape = _core._escape
    _render_layout = _core._render_layout
    _render_dashboard_f_template = _core._render_dashboard_f_template
    _render_channel_select = _core._render_channel_select
    _render_role_select = _core._render_role_select

    settings = shop_flow.normalize_shop_settings(state.get("shop_settings") or {})
    products_raw = state.get("shop_products") if isinstance(state.get("shop_products"), list) else []
    products = [shop_flow.normalize_shop_product(row) for row in products_raw if isinstance(row, dict)]
    products.sort(key=lambda row: (int(row.get("sort_order") or 0), int(row.get("id") or 0)))
    guild_state = state.get("guild") if isinstance(state.get("guild"), dict) else {}
    plan_subscription = state.get("plan_subscription") if isinstance(state.get("plan_subscription"), dict) else {}
    row_plan_tier = shop_flow.normalize_plan_tier(plan_subscription.get("current_plan", "free"))
    plan_tier = row_plan_tier if row_plan_tier != "free" else shop_flow.normalize_plan_tier(guild_state.get("subscription", "free"))
    plan_label = {
        "free": "Free",
        "silver": "Silver",
        "golden": "Gole",
        "diamond": "Diamond",
        "permanent": "Permanent",
    }.get(str(plan_tier or "free").strip().lower(), "Free")
    product_limit = int(shop_flow.product_limit_for_plan(plan_tier))
    product_slots_left = max(0, product_limit - len(products))
    add_product_disabled = "disabled" if product_slots_left <= 0 else ""
    can_truemoney = shop_flow.is_shop_feature_allowed(plan_tier, "payment_truemoney_gift")
    can_shipok = shop_flow.is_shop_feature_allowed(plan_tier, "payment_shipok")
    can_auto_verify = shop_flow.is_shop_feature_allowed(plan_tier, "auto_verify")
    can_auto_delivery = shop_flow.is_shop_feature_allowed(plan_tier, "auto_delivery")
    can_delivery_dm_text = shop_flow.is_shop_feature_allowed(plan_tier, "delivery_dm_text")
    can_delivery_role = shop_flow.is_shop_feature_allowed(plan_tier, "delivery_role")
    can_auto_failed_ticket = shop_flow.is_shop_feature_allowed(plan_tier, "auto_open_failed_delivery_ticket")
    plan_product_caps_text = "Free:1 | Silver:3 | Gole:5 | Diamond:10 | Permanent:20"

    total_products = len(products)
    enabled_products = sum(1 for row in products if row.get("enabled"))
    out_of_stock_products = sum(1 for row in products if int(row.get("stock") or 0) == 0)

    support_roles_text = ",".join(str(role_id) for role_id in settings.get("support_role_ids") or [])

    payment_mode = settings.get("payment_mode") or "manual"
    pm_manual_selected = "selected" if payment_mode == "manual" else ""
    pm_truemoney_selected = "selected" if payment_mode == "truemoney_gift" else ""
    pm_shipok_selected = "selected" if payment_mode == "shipok" else ""
    pm_wallet_selected = "selected" if payment_mode == "wallet" else ""

    def _bool_checked(flag: Any) -> str:
        return "checked" if bool(flag) else ""

    product_cards: list[str] = []
    role_option_disabled = "disabled" if not can_delivery_role else ""
    dm_option_disabled = "disabled" if not can_delivery_dm_text else ""
    text_option_disabled = "disabled" if not can_delivery_dm_text else ""
    for item in products:
        item_id = int(item.get("id") or 0)
        sku = _escape(item.get("sku") or "")
        name = _escape(item.get("name") or "")
        description = _escape(item.get("description") or "")
        price = float(item.get("price") or 0.0)
        stock = int(item.get("stock") or 0)
        image_url = _escape(item.get("image_url") or "")
        visible_role_ids_text = ",".join(str(role_id) for role_id in (item.get("visible_role_ids") or []))
        buy_role_ids_text = ",".join(str(role_id) for role_id in (item.get("buy_role_ids") or []))
        delivery_type = str(item.get("delivery_type") or "none")
        delivery_role_id = item.get("delivery_role_id")
        delivery_payload = _escape(item.get("delivery_payload") or "")
        delivery_note = _escape(item.get("delivery_note") or "")

        dt_none_selected = "selected" if delivery_type == "none" else ""
        dt_role_selected = "selected" if delivery_type == "role" else ""
        dt_dm_selected = "selected" if delivery_type == "dm" else ""
        dt_text_selected = "selected" if delivery_type == "text" else ""

        stock_badge = "Unlimited" if stock < 0 else f"{stock:,}"
        stock_class = "is-danger" if stock == 0 else ""

        product_cards.append(
            f"""
            <section class=\"panel-sub detail-page-section\">
                <div class=\"panel-header\" style=\"margin-bottom: 10px;\">
                    <div class=\"panel-title\">
                        <h3 style=\"margin:0;\">{name} <span class=\"muted\">({sku})</span></h3>
                        <p style=\"margin:0;\">Price: <strong>{price:,.2f}</strong> | Stock: <span class=\"status-pill {stock_class}\">{stock_badge}</span></p>
                    </div>
                </div>
                <form method=\"post\" action=\"/dashboard/guild/{current_guild['id']}/shop\" class=\"field-group\" style=\"grid-template-columns:1fr;\">
                    <input type=\"hidden\" name=\"shop_action\" value=\"update_product\">
                    <input type=\"hidden\" name=\"product_id\" value=\"{item_id}\">
                    <div class=\"field-group detail-page-grid\">
                        <div class=\"field-item\"><label>Name</label><input type=\"text\" name=\"name\" value=\"{name}\" maxlength=\"120\"></div>
                        <div class=\"field-item\"><label>SKU</label><input type=\"text\" name=\"sku\" value=\"{sku}\" maxlength=\"32\"></div>
                    </div>
                    <div class=\"field-item\"><label>Description</label><textarea name=\"description\" style=\"min-height:80px;\">{description}</textarea></div>
                    <div class=\"field-group detail-page-grid\">
                        <div class=\"field-item\"><label>Price</label><input type=\"number\" step=\"0.01\" min=\"0\" name=\"price\" value=\"{price:.2f}\"></div>
                        <div class=\"field-item\"><label>Stock (-1 = unlimited)</label><input type=\"number\" min=\"-1\" name=\"stock\" value=\"{stock}\"></div>
                    </div>
                    <div class=\"field-group detail-page-grid\">
                        <div class=\"field-item\"><label>Visible role IDs (comma)</label><input type=\"text\" name=\"visible_role_ids\" value=\"{_escape(visible_role_ids_text)}\" placeholder=\"123,456\"></div>
                        <div class=\"field-item\"><label>Buy role IDs (comma)</label><input type=\"text\" name=\"buy_role_ids\" value=\"{_escape(buy_role_ids_text)}\" placeholder=\"123,456\"></div>
                    </div>
                    <div class=\"field-item\"><label>Image URL</label><input type=\"url\" name=\"image_url\" value=\"{image_url}\" placeholder=\"https://...\"></div>
                    <div class=\"field-group detail-page-grid\">
                        <div class=\"field-item\">
                            <label>Delivery Type</label>
                            <select name=\"delivery_type\">
                                <option value=\"none\" {dt_none_selected}>Manual</option>
                                <option value=\"role\" {dt_role_selected} {role_option_disabled}>Give Role (Diamond)</option>
                                <option value=\"dm\" {dt_dm_selected} {dm_option_disabled}>DM Code / Message (Silver+)</option>
                                <option value=\"text\" {dt_text_selected} {text_option_disabled}>DM Text (Silver+)</option>
                            </select>
                        </div>
                        <div class=\"field-item\">
                            <label>Delivery Role</label>
                            {_render_role_select("delivery_role_id", bot_guild, delivery_role_id, placeholder="No role")}
                        </div>
                    </div>
                    <div class=\"field-item\"><label>Delivery Payload (codes/messages, 1 line = 1 code)</label><textarea name=\"delivery_payload\" style=\"min-height:90px;\">{delivery_payload}</textarea></div>
                    <div class=\"field-item\"><label>Delivery Note</label><textarea name=\"delivery_note\" style=\"min-height:70px;\">{delivery_note}</textarea></div>
                    <div class=\"ux-toggle-group\">
                        <label class=\"ux-toggle\"><span class=\"ux-toggle-label\">Enable product</span><input type=\"checkbox\" name=\"enabled\" {_bool_checked(item.get('enabled'))}><span class=\"ux-switch\"></span></label>
                    </div>
                    <div class=\"field-group detail-page-grid\">
                        <button class=\"primary-btn\" type=\"submit\">Save Product</button>
                    </div>
                </form>
                <form method=\"post\" action=\"/dashboard/guild/{current_guild['id']}/shop\" style=\"margin-top: 8px;\" onsubmit=\"return confirm('Delete this product?');\">
                    <input type=\"hidden\" name=\"shop_action\" value=\"delete_product\">
                    <input type=\"hidden\" name=\"product_id\" value=\"{item_id}\">
                    <button class=\"ghost-btn danger\" type=\"submit\">Delete Product</button>
                </form>
            </section>
            """
        )

    product_cards_html = "".join(product_cards) if product_cards else '<section class="panel-sub detail-page-section"><p class="muted">No products yet.</p></section>'

    body = _render_dashboard_f_template("shop.html", locals())
    return _render_layout(
        title=f"SkylineBOT Shop - {current_guild['name']}",
        body=body,
        session=session,
        guilds=guilds,
        current_guild=current_guild,
        active_tab=active_tab_slug,
        notice=notice,
    )
