from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


_ASCII_UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_ASCII_LOWER = "abcdefghijklmnopqrstuvwxyz"
_ASCII_DIGITS = "0123456789"


def _build_char_map(
    *,
    upper: str = "",
    lower: str = "",
    digits: str = "",
    extra: dict[str, str] | None = None,
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if upper:
        for index, source in enumerate(_ASCII_UPPER):
            if index < len(upper):
                mapping[source] = upper[index]
    if lower:
        for index, source in enumerate(_ASCII_LOWER):
            if index < len(lower):
                mapping[source] = lower[index]
    if digits:
        for index, source in enumerate(_ASCII_DIGITS):
            if index < len(digits):
                mapping[source] = digits[index]
    if isinstance(extra, dict):
        mapping.update(extra)
    return mapping


def _apply_map(text: str, mapping: dict[str, str]) -> str:
    return "".join(mapping.get(char, char) for char in str(text or ""))


def _apply_combining_mark(text: str, combining_mark: str) -> str:
    if not combining_mark:
        return str(text or "")
    out: list[str] = []
    for char in str(text or ""):
        if char.isspace():
            out.append(char)
            continue
        out.append(f"{char}{combining_mark}")
    return "".join(out)


_UPSIDE_DOWN_MAP = _build_char_map(
    upper="∀qƆ◖ƎℲ⅁HIſʞ˥WNOԀΌᴚS┴∩ΛMX⅄Z",
    lower="ɐqɔpǝɟɓɥᴉɾʞlɯunodbɹsʇnʌʍxʎz",
    digits="0⇂ᄅƐㄣϛ9ㄥ86",
    extra={
        "?": "¿",
        "!": "¡",
        ".": "˙",
        ",": "'",
        "'": ",",
        '"': ",,",
        "(": ")",
        ")": "(",
        "[": "]",
        "]": "[",
        "{": "}",
        "}": "{",
        "<": ">",
        ">": "<",
        "_": "‾",
        "&": "⅋",
    },
)


def _upside_down(text: str) -> str:
    converted = _apply_map(text, _UPSIDE_DOWN_MAP)
    return converted[::-1]


_SUPERSCRIPT_MAP = {
    "a": "ᵃ",
    "b": "ᵇ",
    "c": "ᶜ",
    "d": "ᵈ",
    "e": "ᵉ",
    "f": "ᶠ",
    "g": "ᵍ",
    "h": "ʰ",
    "i": "ⁱ",
    "j": "ʲ",
    "k": "ᵏ",
    "l": "ˡ",
    "m": "ᵐ",
    "n": "ⁿ",
    "o": "ᵒ",
    "p": "ᵖ",
    "q": "ᑫ",
    "r": "ʳ",
    "s": "ˢ",
    "t": "ᵗ",
    "u": "ᵘ",
    "v": "ᵛ",
    "w": "ʷ",
    "x": "ˣ",
    "y": "ʸ",
    "z": "ᶻ",
    "A": "ᴬ",
    "B": "ᴮ",
    "D": "ᴰ",
    "E": "ᴱ",
    "G": "ᴳ",
    "H": "ᴴ",
    "I": "ᴵ",
    "J": "ᴶ",
    "K": "ᴷ",
    "L": "ᴸ",
    "M": "ᴹ",
    "N": "ᴺ",
    "O": "ᴼ",
    "P": "ᴾ",
    "R": "ᴿ",
    "T": "ᵀ",
    "U": "ᵁ",
    "V": "ⱽ",
    "W": "ᵂ",
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "+": "⁺",
    "-": "⁻",
    "=": "⁼",
    "(": "⁽",
    ")": "⁾",
}


_SUBSCRIPT_MAP = {
    "a": "\u2090",
    "e": "\u2091",
    "h": "\u2095",
    "i": "\u1d62",
    "j": "\u2c7c",
    "k": "\u2096",
    "l": "\u2097",
    "m": "\u2098",
    "n": "\u2099",
    "o": "\u2092",
    "p": "\u209a",
    "r": "\u1d63",
    "s": "\u209b",
    "t": "\u209c",
    "u": "\u1d64",
    "v": "\u1d65",
    "x": "\u2093",
    "0": "\u2080",
    "1": "\u2081",
    "2": "\u2082",
    "3": "\u2083",
    "4": "\u2084",
    "5": "\u2085",
    "6": "\u2086",
    "7": "\u2087",
    "8": "\u2088",
    "9": "\u2089",
    "+": "\u208a",
    "-": "\u208b",
    "=": "\u208c",
    "(": "\u208d",
    ")": "\u208e",
}


def _subscript(text: str) -> str:
    out: list[str] = []
    for char in str(text or ""):
        mapped = _SUBSCRIPT_MAP.get(char)
        if mapped is None:
            mapped = _SUBSCRIPT_MAP.get(char.lower())
        out.append(mapped or char)
    return "".join(out)


_TINY_CAPS_MAP = {
    "a": "\u1d43",
    "b": "\u1d47",
    "c": "\u1d9c",
    "d": "\u1d48",
    "e": "\u1d49",
    "f": "\u1da0",
    "g": "\u1d4d",
    "h": "\u02b0",
    "i": "\u2071",
    "j": "\u02b2",
    "k": "\u1d4f",
    "l": "\u02e1",
    "m": "\u1d50",
    "n": "\u207f",
    "o": "\u1d52",
    "p": "\u1d56",
    "q": "\ua7af",
    "r": "\u02b3",
    "s": "\u02e2",
    "t": "\u1d57",
    "u": "\u1d58",
    "v": "\u1d5b",
    "w": "\u02b7",
    "x": "\u02e3",
    "y": "\u02b8",
    "z": "\u1dbb",
}

_GLITCH_ABOVE = (
    "\u030d",
    "\u030e",
    "\u0304",
    "\u0305",
    "\u033f",
    "\u0311",
    "\u0306",
    "\u0310",
    "\u0352",
    "\u0357",
    "\u0351",
    "\u0307",
    "\u0308",
    "\u030a",
)

_GLITCH_MID = (
    "\u0334",
    "\u0335",
    "\u0336",
)

_GLITCH_BELOW = (
    "\u0316",
    "\u0317",
    "\u0318",
    "\u0319",
    "\u031c",
    "\u031d",
    "\u031e",
    "\u031f",
    "\u0320",
    "\u0324",
    "\u0325",
    "\u0326",
    "\u0329",
    "\u032a",
    "\u032b",
    "\u032c",
    "\u032d",
    "\u032e",
    "\u032f",
    "\u0330",
    "\u0331",
    "\u0332",
    "\u0333",
)


def _double_underline(text: str) -> str:
    return _apply_combining_mark(text, "\u0333")


def _tiny_caps(text: str) -> str:
    out: list[str] = []
    for char in str(text or ""):
        mapped = _TINY_CAPS_MAP.get(char.lower())
        out.append(mapped or char)
    return "".join(out)


def _glitch_text(text: str) -> str:
    out: list[str] = []
    visual_index = 0
    for char in str(text or ""):
        if char.isspace():
            out.append(char)
            continue
        above = _GLITCH_ABOVE[visual_index % len(_GLITCH_ABOVE)]
        middle = _GLITCH_MID[visual_index % len(_GLITCH_MID)]
        below = _GLITCH_BELOW[visual_index % len(_GLITCH_BELOW)]
        out.append(f"{char}{above}{middle}{below}")
        visual_index += 1
    return "".join(out)


_THAI_SYMBOL_MAP = {
    "ก": "∩",
    "ข": "श",
    "ฃ": "খ",
    "ค": "の",
    "ง": "ງ",
    "จ": "ຈ",
    "ช": "જ",
    "ญ": "₪",
    "ฒ": "ឍ",
    "ณ": "ભ",
    "ด": "ດ",
    "ต": "๓",
    "ท": "η",
    "ธ": "ຣ",
    "น": "Ա",
    "บ": "υ",
    "ป": "ປ",
    "ผ": "ຜ",
    "ฝ": "ධ",
    "พ": "ш",
    "ฟ": "ຟ",
    "ภ": "ग",
    "ม": "ນ",
    "ย": "ε",
    "ร": "ຮ",
    "ล": "ລ",
    "ว": "ວ",
    "ษ": "ម",
    "ส": "さ",
    "ห": "ㄨ",
    "ฬ": "ង",
    "อ": "Ә",
    "ฮ": "ර",
    "โ": "ໂ",
    "ไ": "ໄ",
    "ใ": "ໃ",
    "เ": "も",
    "ิ": "ິ",
    "ะ": "ະ",
    "า": "າ",
    "ๅ": "ๅ",
}


def _thai_symbol_style(text: str) -> str:
    mapped = _apply_map(text, _THAI_SYMBOL_MAP)
    # Add mild Latin styling too so mixed Thai/English looks consistent.
    return _apply_map(
        mapped,
        _build_char_map(
            upper="𝘼𝘽𝘾𝘿𝙀𝙁𝙂𝙃𝙄𝙅𝙆𝙇𝙈𝙉𝙊𝙋𝙌𝙍𝙎𝙏𝙐𝙑𝙒𝙓𝙔𝙕",
            lower="𝙖𝙗𝙘𝙙𝙚𝙛𝙜𝙝𝙞𝙟𝙠𝙡𝙢𝙣𝙤𝙥𝙦𝙧𝙨𝙩𝙪𝙫𝙬𝙭𝙮𝙯",
            digits="𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵",
        ),
    )


@dataclass(frozen=True)
class FancyStyle:
    key: str
    label: str
    description: str
    aliases: tuple[str, ...]
    transform: Callable[[str], str]


def _map_transform(mapping: dict[str, str]) -> Callable[[str], str]:
    def _inner(text: str) -> str:
        return _apply_map(text, mapping)

    return _inner


_STYLES: tuple[FancyStyle, ...] = (
    FancyStyle(
        key="normal",
        label="Normal",
        description="ข้อความปกติ",
        aliases=("plain", "default"),
        transform=lambda text: str(text or ""),
    ),
    FancyStyle(
        key="double_struck",
        label="Double Struck",
        description="ตัวหนาแนวคณิตศาสตร์",
        aliases=("ds", "blackboard", "mathbb"),
        transform=_map_transform(
            _build_char_map(
                upper="𝔸𝔹ℂ𝔻𝔼𝔽𝔾ℍ𝕀𝕁𝕂𝕃𝕄ℕ𝕆ℙℚℝ𝕊𝕋𝕌𝕍𝕎𝕏𝕐ℤ",
                lower="𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫",
                digits="𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡",
            )
        ),
    ),
    FancyStyle(
        key="small_caps",
        label="Small Caps",
        description="ตัวเล็กทรงแคป",
        aliases=("small", "caps"),
        transform=_map_transform(
            _build_char_map(
                upper="ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘꞯʀꜱᴛᴜᴠᴡxʏᴢ",
                lower="ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘꞯʀꜱᴛᴜᴠᴡxʏᴢ",
            )
        ),
    ),
    FancyStyle(
        key="tiny_caps",
        label="Tiny Caps",
        description="ตัวเล็กจิ๋วแบบยก",
        aliases=("tiny", "mini_caps", "micro_caps"),
        transform=_tiny_caps,
    ),
    FancyStyle(
        key="circled",
        label="Circled",
        description="ตัวอักษรวงกลม",
        aliases=("bubble", "circle"),
        transform=_map_transform(
            _build_char_map(
                upper="ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ",
                lower="ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ",
                digits="⓪①②③④⑤⑥⑦⑧⑨",
            )
        ),
    ),
    FancyStyle(
        key="squared",
        label="Squared",
        description="ตัวอักษรในกรอบเหลี่ยม",
        aliases=("box", "square"),
        transform=_map_transform(
            _build_char_map(
                upper="🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉",
                lower="🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉",
            )
        ),
    ),
    FancyStyle(
        key="negative_squared",
        label="Negative Squared",
        description="ตัวอักษรกรอบทึบ",
        aliases=("square_black", "neg_square"),
        transform=_map_transform(
            _build_char_map(
                upper="🅰🅱🅲🅳🅴🅵🅶🅷🅸🅹🅺🅻🅼🅽🅾🅿🆀🆁🆂🆃🆄🆅🆆🆇🆈🆉",
                lower="🅰🅱🅲🅳🅴🅵🅶🅷🅸🅹🅺🅻🅼🅽🅾🅿🆀🆁🆂🆃🆄🆅🆆🆇🆈🆉",
            )
        ),
    ),
    FancyStyle(
        key="bold",
        label="Bold",
        description="ตัวหนาคณิตศาสตร์",
        aliases=("math_bold",),
        transform=_map_transform(
            _build_char_map(
                upper="𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙",
                lower="𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳",
                digits="𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗",
            )
        ),
    ),
    FancyStyle(
        key="italic",
        label="Italic",
        description="ตัวเอียง",
        aliases=("math_italic",),
        transform=_map_transform(
            _build_char_map(
                upper="𝐴𝐵𝐶𝐷𝐸𝐹𝐺𝐻𝐼𝐽𝐾𝐿𝑀𝑁𝑂𝑃𝑄𝑅𝑆𝑇𝑈𝑉𝑊𝑋𝑌𝑍",
                lower="𝑎𝑏𝑐𝑑𝑒𝑓𝑔ℎ𝑖𝑗𝑘𝑙𝑚𝑛𝑜𝑝𝑞𝑟𝑠𝑡𝑢𝑣𝑤𝑥𝑦𝑧",
            )
        ),
    ),
    FancyStyle(
        key="bold_italic",
        label="Bold Italic",
        description="ตัวหนาเอียง",
        aliases=("bi",),
        transform=_map_transform(
            _build_char_map(
                upper="𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁",
                lower="𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛",
            )
        ),
    ),
    FancyStyle(
        key="sans_bold",
        label="Sans Bold",
        description="ตัวหนาแบบ Sans",
        aliases=("sans", "sansbold"),
        transform=_map_transform(
            _build_char_map(
                upper="𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭",
                lower="𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇",
                digits="𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵",
            )
        ),
    ),
    FancyStyle(
        key="monospace",
        label="Monospace",
        description="ตัวกว้างเท่ากัน",
        aliases=("mono", "code"),
        transform=_map_transform(
            _build_char_map(
                upper="𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉",
                lower="𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣",
                digits="𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿",
            )
        ),
    ),
    FancyStyle(
        key="fraktur",
        label="Fraktur",
        description="ฟอนต์ Gothic/Fraktur",
        aliases=("gothic",),
        transform=_map_transform(
            _build_char_map(
                upper="𝔄𝔅ℭ𝔇𝔈𝔉𝔊ℌℑ𝔍𝔎𝔏𝔐𝔑𝔒𝔓𝔔ℜ𝔖𝔗𝔘𝔙𝔚𝔛𝔜ℨ",
                lower="𝔞𝔟𝔠𝔡𝔢𝔣𝔤𝔥𝔦𝔧𝔨𝔩𝔪𝔫𝔬𝔭𝔮𝔯𝔰𝔱𝔲𝔳𝔴𝔵𝔶𝔷",
            )
        ),
    ),
    FancyStyle(
        key="bold_fraktur",
        label="Bold Fraktur",
        description="ฟอนต์ Gothic หนา",
        aliases=("gothic_bold",),
        transform=_map_transform(
            _build_char_map(
                upper="𝕬𝕭𝕮𝕯𝕰𝕱𝕲𝕳𝕴𝕵𝕶𝕷𝕸𝕹𝕺𝕻𝕼𝕽𝕾𝕿𝖀𝖁𝖂𝖃𝖄𝖅",
                lower="𝖆𝖇𝖈𝖉𝖊𝖋𝖌𝖍𝖎𝖏𝖐𝖑𝖒𝖓𝖔𝖕𝖖𝖗𝖘𝖙𝖚𝖛𝖜𝖝𝖞𝖟",
            )
        ),
    ),
    FancyStyle(
        key="script",
        label="Script",
        description="ตัวเขียนลายมือ",
        aliases=("cursive",),
        transform=_map_transform(
            _build_char_map(
                upper="𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬ℛ𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵",
                lower="𝒶𝒷𝒸𝒹ℯ𝒻𝓰𝒽𝒾𝒿𝓀𝓁𝓂𝓃𝓸𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏",
            )
        ),
    ),
    FancyStyle(
        key="bold_script",
        label="Bold Script",
        description="ตัวเขียนหนา",
        aliases=("cursive_bold",),
        transform=_map_transform(
            _build_char_map(
                upper="𝓐𝓑𝓒𝓓𝓔𝓕𝓖𝓗𝓘𝓙𝓚𝓛𝓜𝓝𝓞𝓟𝓠𝓡𝓢𝓣𝓤𝓥𝓦𝓧𝓨𝓩",
                lower="𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃",
            )
        ),
    ),
    FancyStyle(
        key="fullwidth",
        label="Full Width",
        description="ตัวกว้างแบบญี่ปุ่น",
        aliases=("fw", "zenkaku"),
        transform=_map_transform(
            _build_char_map(
                upper="ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ",
                lower="ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
                digits="０１２３４５６７８９",
            )
        ),
    ),
    FancyStyle(
        key="underline",
        label="Underline",
        description="ขีดเส้นใต้ทุกตัวอักษร",
        aliases=("u",),
        transform=lambda text: _apply_combining_mark(text, "\u0332"),
    ),
    FancyStyle(
        key="double_underline",
        label="Double Underline",
        description="ขีดเส้นใต้แบบสองชั้น",
        aliases=("u2", "underline2", "double_u"),
        transform=_double_underline,
    ),
    FancyStyle(
        key="strike",
        label="Strike",
        description="ขีดทับทุกตัวอักษร",
        aliases=("strikethrough",),
        transform=lambda text: _apply_combining_mark(text, "\u0336"),
    ),
    FancyStyle(
        key="overline",
        label="Overline",
        description="เส้นเหนือทุกตัวอักษร",
        aliases=("topline",),
        transform=lambda text: _apply_combining_mark(text, "\u0305"),
    ),
    FancyStyle(
        key="superscript",
        label="Superscript",
        description="ตัวยก",
        aliases=("super",),
        transform=lambda text: _apply_map(text, _SUPERSCRIPT_MAP),
    ),
    FancyStyle(
        key="subscript",
        label="Subscript",
        description="ตัวห้อย",
        aliases=("sub",),
        transform=_subscript,
    ),
    FancyStyle(
        key="upside_down",
        label="Upside Down",
        description="กลับหัวข้อความ",
        aliases=("flip", "reverse_flip"),
        transform=_upside_down,
    ),
    FancyStyle(
        key="glitch",
        label="Glitch",
        description="ตัวหนังสือเอฟเฟกต์แตกพร่า",
        aliases=("zalgo", "corrupt", "cursed"),
        transform=_glitch_text,
    ),
    FancyStyle(
        key="thai_symbols",
        label="Thai Symbols Mix",
        description="แทนตัวอักษรไทยด้วยสัญลักษณ์ใกล้เคียง",
        aliases=("thai", "thai_alt", "thai_style"),
        transform=_thai_symbol_style,
    ),
)


_STYLE_BY_KEY: dict[str, FancyStyle] = {}
for _style in _STYLES:
    _STYLE_BY_KEY[_style.key] = _style
    for _alias in _style.aliases:
        _STYLE_BY_KEY[str(_alias).strip().lower()] = _style


def normalize_style_key(raw_key: str) -> str:
    safe = str(raw_key or "double_struck").strip().lower().replace("-", "_").replace(" ", "_")
    resolved = _STYLE_BY_KEY.get(safe)
    return resolved.key if isinstance(resolved, FancyStyle) else "double_struck"


def is_known_style(raw_key: str) -> bool:
    safe = str(raw_key or "").strip().lower().replace("-", "_").replace(" ", "_")
    return bool(safe and safe in _STYLE_BY_KEY)


def resolve_style(raw_key: str) -> FancyStyle:
    return _STYLE_BY_KEY.get(normalize_style_key(raw_key), _STYLES[1])


def transform_text(text: str, style_key: str = "double_struck") -> str:
    style = resolve_style(style_key)
    return style.transform(str(text or ""))


# Category helpers (kept near end so they can safely override older helper behavior).
_STYLE_CATEGORY_MAP: dict[str, str] = {
    "normal": "basic",
    "double_struck": "math",
    "small_caps": "latin",
    "tiny_caps": "latin",
    "circled": "boxed",
    "squared": "boxed",
    "negative_squared": "boxed",
    "bold": "math",
    "italic": "math",
    "bold_italic": "math",
    "sans_bold": "math",
    "monospace": "math",
    "fraktur": "classic",
    "bold_fraktur": "classic",
    "script": "classic",
    "bold_script": "classic",
    "fullwidth": "latin",
    "underline": "decor",
    "double_underline": "decor",
    "strike": "decor",
    "overline": "decor",
    "superscript": "decor",
    "subscript": "decor",
    "glitch": "decor",
    "upside_down": "decor",
    "thai_symbols": "thai",
}

_CATEGORY_LABELS: dict[str, str] = {
    "all": "All",
    "basic": "Basic",
    "math": "Math",
    "latin": "Latin",
    "boxed": "Boxed",
    "classic": "Classic",
    "decor": "Decorative",
    "thai": "Thai Mix",
    "misc": "Misc",
}


def style_category(style_key: str) -> str:
    return _STYLE_CATEGORY_MAP.get(str(style_key or "").strip().lower(), "misc")


def style_category_label(category_key: str) -> str:
    key = str(category_key or "").strip().lower()
    return _CATEGORY_LABELS.get(key, key.title() if key else "Misc")


def list_categories() -> list[dict[str, str]]:
    ordered_keys = ["all", "basic", "math", "latin", "boxed", "classic", "decor", "thai"]
    return [{"id": key, "name": style_category_label(key)} for key in ordered_keys]


def list_styles(*, sample_text: str = "Fancy Fonts \u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35") -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for style in _STYLES:
        category_key = style_category(style.key)
        rows.append(
            {
                "id": style.key,
                "name": style.label,
                "category": category_key,
                "category_name": style_category_label(category_key),
                "description": style.description,
                "aliases": ", ".join(style.aliases),
                "preview": style.transform(sample_text),
            }
        )
    return rows


def convert_all(text: str) -> list[dict[str, str]]:
    safe_text = str(text or "")
    rows: list[dict[str, str]] = []
    for style in _STYLES:
        category_key = style_category(style.key)
        rows.append(
            {
                "id": style.key,
                "name": style.label,
                "category": category_key,
                "category_name": style_category_label(category_key),
                "text": style.transform(safe_text),
            }
        )
    return rows
