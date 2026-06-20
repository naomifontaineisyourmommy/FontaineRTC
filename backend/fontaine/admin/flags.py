"""Country name -> flag HTML (ported 1:1 from OlcRTC-AdminVPS)."""

_CC = {
    "Afghanistan": "AF", "Albania": "AL", "Algeria": "DZ", "Argentina": "AR", "Armenia": "AM",
    "Australia": "AU", "Austria": "AT", "Azerbaijan": "AZ", "Bahrain": "BH", "Bangladesh": "BD",
    "Belarus": "BY", "Belgium": "BE", "Bolivia": "BO", "Bosnia": "BA", "Brazil": "BR",
    "Bulgaria": "BG", "Cambodia": "KH", "Canada": "CA", "Chile": "CL", "China": "CN",
    "Colombia": "CO", "Croatia": "HR", "Cuba": "CU", "Cyprus": "CY", "Czech Republic": "CZ",
    "Denmark": "DK", "Ecuador": "EC", "Egypt": "EG", "Estonia": "EE", "Ethiopia": "ET",
    "Finland": "FI", "France": "FR", "Georgia": "GE", "Germany": "DE", "Ghana": "GH",
    "Greece": "GR", "Guatemala": "GT", "Honduras": "HN", "Hong Kong": "HK", "Hungary": "HU",
    "Iceland": "IS", "India": "IN", "Indonesia": "ID", "Iran": "IR", "Iraq": "IQ", "Ireland": "IE",
    "Israel": "IL", "Italy": "IT", "Japan": "JP", "Jordan": "JO", "Kazakhstan": "KZ", "Kenya": "KE",
    "Kuwait": "KW", "Kyrgyzstan": "KG", "Latvia": "LV", "Lebanon": "LB", "Libya": "LY",
    "Lithuania": "LT", "Luxembourg": "LU", "Malaysia": "MY", "Mexico": "MX", "Moldova": "MD",
    "Mongolia": "MN", "Morocco": "MA", "Myanmar": "MM", "Nepal": "NP", "Netherlands": "NL",
    "New Zealand": "NZ", "Nigeria": "NG", "Norway": "NO", "Pakistan": "PK", "Panama": "PA",
    "Paraguay": "PY", "Peru": "PE", "Philippines": "PH", "Poland": "PL", "Portugal": "PT",
    "Qatar": "QA", "Romania": "RO", "Russia": "RU", "Saudi Arabia": "SA", "Serbia": "RS",
    "Singapore": "SG", "Slovakia": "SK", "Slovenia": "SI", "South Africa": "ZA",
    "South Korea": "KR", "Spain": "ES", "Sri Lanka": "LK", "Sweden": "SE", "Switzerland": "CH",
    "Taiwan": "TW", "Tajikistan": "TJ", "Thailand": "TH", "Turkey": "TR", "Turkmenistan": "TM",
    "UAE": "AE", "Ukraine": "UA", "United Kingdom": "GB", "United States": "US",
    "Uruguay": "UY", "Uzbekistan": "UZ", "Venezuela": "VE", "Vietnam": "VN", "Yemen": "YE",
}


def _code(country: str) -> str:
    return _CC.get(country) or next(
        (c for n, c in _CC.items() if country.lower() in n.lower()), "")


def flag_emoji(country: str) -> str:
    """Country name -> emoji flag (e.g. 'Spain' -> 🇪🇸); '' if unknown."""
    code = _code(country)
    if len(code) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(ch) - ord("A")) for ch in code.upper())


def flag(country: str) -> str:
    code = _CC.get(country) or next(
        (c for n, c in _CC.items() if country.lower() in n.lower()), "")
    if code:
        return (f'<img src="https://flagcdn.com/w40/{code.lower()}.png"'
                f' width="28" height="21" alt="{code}"'
                f' style="border-radius:3px;object-fit:cover;display:block">')
    return '<span style="font-size:1.4rem;line-height:1">&#x1F310;</span>'
