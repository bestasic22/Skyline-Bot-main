from __future__ import annotations

import io
from typing import Any

from PIL import Image, ImageDraw

from skylinebot.console.logging import logger
from skylinebot.style import urls as style_urls
from skylinebot.workflows.ui import load_image_from_url, load_ui_font

LAYOUT_CENTER_STACK = "center_stack"
LAYOUT_SIDE = "side"

AVATAR_LEFT = "left"
AVATAR_CENTER = "center"
AVATAR_RIGHT = "right"

TEXT_LEFT = "left"
TEXT_CENTER = "center"
TEXT_RIGHT = "right"


def normalize_layout_mode(raw_value: Any) -> str:
    value = str(raw_value or "").strip().lower()
    return LAYOUT_CENTER_STACK if value == LAYOUT_CENTER_STACK else LAYOUT_SIDE


def normalize_avatar_position(raw_value: Any) -> str:
    value = str(raw_value or "").strip().lower()
    if value in {AVATAR_LEFT, AVATAR_CENTER, AVATAR_RIGHT}:
        return value
    return AVATAR_CENTER


def normalize_text_align(raw_value: Any) -> str:
    value = str(raw_value or "").strip().lower()
    if value in {TEXT_LEFT, TEXT_CENTER, TEXT_RIGHT}:
        return value
    return TEXT_CENTER


def resolve_theme_url(
    theme_key: Any,
    custom_url: Any = None,
    *,
    user_url: Any = None,
    guild_url: Any = None,
) -> str:
    return style_urls.resolve_theme_image(
        str(theme_key or ""),
        str(custom_url or ""),
        user_url=str(user_url or ""),
        guild_url=str(guild_url or ""),
        fallback=style_urls.DEFAULT_MUSIC_BANNER,
        include_extended=True,
    )


def _fit_cover(image: Image.Image, width: int, height: int) -> Image.Image:
    source_ratio = image.width / max(1, image.height)
    target_ratio = width / max(1, height)
    if source_ratio > target_ratio:
        new_height = height
        new_width = int(height * source_ratio)
    else:
        new_width = width
        new_height = int(width / max(0.01, source_ratio))
    resized = image.resize((max(1, new_width), max(1, new_height)), Image.LANCZOS)
    left = max(0, (resized.width - width) // 2)
    top = max(0, (resized.height - height) // 2)
    return resized.crop((left, top, left + width, top + height))


def _ellipse_avatar(image: Image.Image, size: int) -> Image.Image:
    avatar = image.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    avatar.putalpha(mask)
    return avatar


def _text_xy(draw: ImageDraw.Draw, text: str, font, x: int, y: int, align: str) -> tuple[int, int]:
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=8)
    width = max(0, bbox[2] - bbox[0])
    height = max(0, bbox[3] - bbox[1])
    top_offset = bbox[1]
    left_offset = bbox[0]
    if align == TEXT_LEFT:
        return x - left_offset, y - top_offset
    if align == TEXT_RIGHT:
        return x - width - left_offset, y - top_offset
    return x - (width // 2) - left_offset, y - (height // 2) - top_offset


def _fit_font_size(
    draw: ImageDraw.Draw,
    text: str,
    *,
    initial_size: int,
    min_size: int,
    max_width: int,
    bold: bool,
    font_style: str = "classic",
    stroke_width: int = 2,
):
    size = max(min_size, initial_size)
    while size >= min_size:
        font = load_ui_font(size, text=text, bold=bold, font_style=font_style)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        width = max(0, bbox[2] - bbox[0])
        if width <= max_width:
            return font
        size -= 2
    return load_ui_font(min_size, text=text, bold=bold, font_style=font_style)


def _wrap_text_to_width(
    draw: ImageDraw.Draw,
    text: str,
    font,
    *,
    max_width: int,
    max_lines: int,
    stroke_width: int = 2,
) -> str:
    raw = " ".join(str(text or "").split())
    if not raw:
        return ""
    words = raw.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=stroke_width)
        width = max(0, bbox[2] - bbox[0])
        if width <= max_width or not current:
            current = candidate
            continue
        lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if len(lines) < max_lines and current:
        lines.append(current)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if len(lines) == max_lines and " ".join(lines) != raw:
        last = lines[-1]
        while last:
            candidate = f"{last}..."
            bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=stroke_width)
            width = max(0, bbox[2] - bbox[0])
            if width <= max_width:
                lines[-1] = candidate
                break
            last = last[:-1].rstrip()
        if not last:
            lines[-1] = "..."
    return "\n".join(lines)


def _clamp_text_position(
    draw: ImageDraw.Draw,
    text: str,
    font,
    x: int,
    y: int,
    *,
    max_width: int,
    max_height: int,
    stroke_width: int = 2,
) -> tuple[int, int]:
    bbox = draw.multiline_textbbox((x, y), text, font=font, stroke_width=stroke_width, spacing=8)
    dx = 0
    dy = 0
    if bbox[0] < 16:
        dx = 16 - bbox[0]
    elif bbox[2] > max_width - 16:
        dx = (max_width - 16) - bbox[2]
    if bbox[1] < 12:
        dy = 12 - bbox[1]
    elif bbox[3] > max_height - 12:
        dy = (max_height - 12) - bbox[3]
    return x + dx, y + dy


def build_member_notice_card(
    *,
    avatar_url: str,
    top_text: str,
    bottom_text: str,
    theme_key: Any = "music",
    theme_url: Any = None,
    user_theme_url: Any = None,
    guild_theme_url: Any = None,
    layout_mode: Any = LAYOUT_CENTER_STACK,
    avatar_position: Any = AVATAR_CENTER,
    text_align: Any = TEXT_CENTER,
    font_style: Any = "classic",
    width: int = 1200,
    height: int = 420,
) -> io.BytesIO | None:
    try:
        normalized_layout = normalize_layout_mode(layout_mode)
        normalized_avatar_pos = normalize_avatar_position(avatar_position)
        normalized_text_align = normalize_text_align(text_align)
        normalized_font_style = str(font_style or "classic").strip().lower()

        bg_url = resolve_theme_url(
            theme_key,
            theme_url,
            user_url=user_theme_url,
            guild_url=guild_theme_url,
        )
        background = _fit_cover(load_image_from_url(bg_url), width, height).convert("RGBA")
        overlay = Image.new("RGBA", (width, height), (10, 17, 31, 150))
        card = Image.alpha_composite(background, overlay)

        draw = ImageDraw.Draw(card)
        avatar = _ellipse_avatar(load_image_from_url(avatar_url), 170)
        if normalized_avatar_pos == AVATAR_LEFT:
            avatar_x = 90
        elif normalized_avatar_pos == AVATAR_RIGHT:
            avatar_x = width - 90 - avatar.width
        else:
            avatar_x = (width - avatar.width) // 2
        avatar_y = (height - avatar.height) // 2
        card.paste(avatar, (avatar_x, avatar_y), avatar)

        top_value = str(top_text or "").strip()[:260] or "Welcome"
        bottom_value = str(bottom_text or "").strip()[:300] or "SkylineBOT"
        text_max_width = max(320, width - 100)
        top_font = _fit_font_size(
            draw,
            top_value,
            initial_size=58,
            min_size=32,
            max_width=text_max_width,
            bold=True,
            font_style=normalized_font_style,
        )
        bottom_font = _fit_font_size(
            draw,
            bottom_value,
            initial_size=36,
            min_size=24,
            max_width=text_max_width,
            bold=False,
            font_style=normalized_font_style,
        )
        top_wrapped = _wrap_text_to_width(
            draw,
            top_value,
            top_font,
            max_width=text_max_width,
            max_lines=2,
        )
        bottom_wrapped = _wrap_text_to_width(
            draw,
            bottom_value,
            bottom_font,
            max_width=text_max_width,
            max_lines=2,
        )
        stroke_fill = (0, 0, 0, 210)

        if normalized_layout == LAYOUT_CENTER_STACK:
            x_center = width // 2
            top_x, top_y = _text_xy(draw, top_wrapped, top_font, x_center, 64, TEXT_CENTER)
            bottom_x, bottom_y = _text_xy(draw, bottom_wrapped, bottom_font, x_center, height - 96, TEXT_CENTER)
        else:
            if normalized_text_align == TEXT_LEFT:
                x_anchor = 70
            elif normalized_text_align == TEXT_RIGHT:
                x_anchor = width - 70
            else:
                x_anchor = width // 2
            top_x, top_y = _text_xy(draw, top_wrapped, top_font, x_anchor, (height // 2) - 78, normalized_text_align)
            bottom_x, bottom_y = _text_xy(draw, bottom_wrapped, bottom_font, x_anchor, (height // 2) + 12, normalized_text_align)

        top_x, top_y = _clamp_text_position(draw, top_wrapped, top_font, top_x, top_y, max_width=width, max_height=height)
        bottom_x, bottom_y = _clamp_text_position(
            draw,
            bottom_wrapped,
            bottom_font,
            bottom_x,
            bottom_y,
            max_width=width,
            max_height=height,
        )

        draw.multiline_text(
            (top_x, top_y),
            top_wrapped,
            fill=(255, 255, 255, 255),
            font=top_font,
            stroke_width=2,
            stroke_fill=stroke_fill,
            spacing=8,
            align=normalized_text_align,
        )
        draw.multiline_text(
            (bottom_x, bottom_y),
            bottom_wrapped,
            fill=(215, 232, 255, 255),
            font=bottom_font,
            stroke_width=2,
            stroke_fill=stroke_fill,
            spacing=8,
            align=normalized_text_align,
        )

        byte = io.BytesIO()
        card.save(byte, format="PNG")
        byte.seek(0)
        return byte
    except Exception as error:
        logger.error(f"Error creating notice card: {error}")
        return None
