import re
import hmac
import hashlib
import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional
import requests
from PIL import Image, ImageDraw, ImageFont, ImageColor
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from ..config import settings
from .db import Database

# Font bundled alongside this file
_BUNDLED_FONT = Path(__file__).resolve().parent / "Inter-Bold.ttf"

IPO_SUFFIXES = (
    "inc", "incorporated", "corp", "corporation", "company", "co", "ltd", "limited", "llc", "plc",
    "holdco", "holding", "holdings", "mgmt", "management", "group", "trust",
    "partner", "partners", "capital", "capitals", "venture", "ventures",
    "acquisition", "acquisitions", "spac", "etf", "fund",
    "gmbh", "s.a.", "s.a", "n.v.", "n.v", "b.v.", "b.v", "a/s", "ab", "ag", "nv", "bv",
    "sarl", "spa", "pty", "oyj", "kk", "sas", "llp", "lp",
)

SUFFIX_RE = re.compile(rf"\b({'|'.join(map(re.escape, IPO_SUFFIXES))})\b", re.IGNORECASE)
ROMAN_RE = re.compile(r"\b(i|ii|iii|iv|v|vi|vii|viii|ix|x)\b$", re.IGNORECASE)

# Gradient color palette for placeholders
GRADIENTS = [
    ("#0F0F0F", "#1F2937", "#4B5563"), ("#1E1B4B", "#4F46E5", "#A5B4FC"),
    ("#1B4332", "#2D6A4F", "#94D3AC"), ("#1E3A8A", "#3B82F6", "#9AC7F5"),
    ("#4A044E", "#9333EA", "#D8B4FE"), ("#334155", "#64748B", "#9CA3AF"),
    ("#3F3CBB", "#6366F1", "#A5B4FC"), ("#065F46", "#10B981", "#91E2C3"),
    ("#0C4A6E", "#38BDF8", "#A0D4F9"), ("#831843", "#EC4899", "#F9A8D4"),
    ("#5B21B6", "#8B5CF6", "#C4B5FD"), ("#7F1D1D", "#DC2626", "#FCA5A5"),
    ("#14532D", "#22C55E", "#BBF7D0"), ("#DFBD12", "#D8C95A", "#DBD37A"),
    ("#9A3412", "#FDBA74", "#FFEDD5")
]

class LogoService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.session = requests.Session()
        self.font_path = str(_BUNDLED_FONT) if _BUNDLED_FONT.exists() else None
        self.backfill_mode = False  # set True in backfill to avoid Google API quota

    # ---------- name cleaning ----------
    @staticmethod
    def clean_company_name(name: str) -> str:
        s = name.lower().replace('&', ' and ')
        s = re.sub(r"[.,'()/]", " ", s)
        s = re.sub(r"[-_]", " ", s)
        s = SUFFIX_RE.sub(" ", s)
        s = ROMAN_RE.sub(" ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # ---------- filename (unguessable, deterministic) ----------
    @staticmethod
    def hashed_object_name(cik: str | int) -> str:
        digest = hmac.new(settings.LOGO_NAME_SALT.encode(), str(cik).encode(), hashlib.sha256).hexdigest()
        return f"{digest}.webp"

    # ---------- Google Search for homepage ----------
    def search_homepage_google(self, company_name: str) -> Optional[str]:
        """Get company homepage using Google Custom Search API (top 5 results only)"""
        if not hasattr(settings, 'GOOGLE_API_KEY') or not hasattr(settings, 'GOOGLE_SEARCH_ENGINE_ID'):
            return None
        
        if not settings.GOOGLE_API_KEY or not settings.GOOGLE_SEARCH_ENGINE_ID:
            return None
        
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': settings.GOOGLE_API_KEY,
            'cx': settings.GOOGLE_SEARCH_ENGINE_ID,
            'q': company_name,
            'num': 5
        }
        
        try:
            response = self.session.get(url, params=params, timeout=settings.HTTP_TIMEOUT)
            response.raise_for_status()
            results = response.json()
            
            for item in results.get('items', []):
                link = item['link']
                parsed = urlparse(link)
                
                # Only accept root paths (homepage)
                if parsed.path == '/' or parsed.path == '':
                    domain = parsed.netloc.replace('www.', '')
                    return f"https://{domain}"
            
            return None
            
        except Exception as e:
            # Log if it's a quota error
            if '429' in str(e) or 'quota' in str(e).lower():
                print(f"[WARN] Google API quota exceeded: {e}")
            return None

    # ---------- SEC filing URL extraction ----------
    _FILING_URL_RE = re.compile(
        r'(?:our\s+(?:website|web\s*site|internet\s+website)(?:\s+address)?\s+(?:is\s+(?:located\s+at|at)|address\s+is)\s*'
        r'|(?:located\s+at|available\s+at|found\s+at|visit\s+us\s+at)\s+)'
        r'((?:https?://)?(?:www\.)?[\w\-]+\.(?:com|io|co|net|org|ai|tech|app|us|info))',
        re.IGNORECASE,
    )

    def extract_url_from_filing(self, text: str) -> Optional[str]:
        """Extract the company's website URL directly from SEC filing text."""
        m = self._FILING_URL_RE.search(text)
        if not m:
            return None
        raw = m.group(1).strip().rstrip(".")
        if not raw.startswith("http"):
            raw = "https://" + raw
        parsed = urlparse(raw)
        return f"{parsed.scheme}://{parsed.netloc}"

    # ---------- DuckDuckGo instant answer ----------
    def search_homepage_duckduckgo(self, company_name: str) -> Optional[str]:
        """Find company homepage via DuckDuckGo instant answer API (no key, no quota)."""
        try:
            r = self.session.get(
                "https://api.duckduckgo.com/",
                params={"q": company_name, "format": "json", "no_redirect": "1", "no_html": "1"},
                timeout=settings.HTTP_TIMEOUT,
                headers={"User-Agent": settings.SEC_USER_AGENT},
            )
            data = r.json()
            url = data.get("AbstractURL") or data.get("OfficialWebsite")
            if url:
                parsed = urlparse(url)
                if parsed.netloc:
                    return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:
            pass
        return None

    # ---------- Favicon scraping ----------
    def get_favicon_url(self, homepage_url: str) -> Optional[str]:
        """Get favicon URL from homepage"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        parsed = urlparse(homepage_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        try:
            # Strategy 1: Try standard /favicon.ico
            favicon_url = f"{base_url}/favicon.ico"
            response = self.session.get(favicon_url, headers=headers, timeout=5)
            if response.status_code == 200 and len(response.content) > 0:
                return favicon_url
            
            # Strategy 2: Parse HTML for favicon links
            response = self.session.get(homepage_url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            favicon_links = []
            
            for rel in ['icon', 'shortcut icon', 'apple-touch-icon', 'apple-touch-icon-precomposed']:
                links = soup.find_all('link', rel=lambda x: x and rel in x.lower() if x else False)
                for link in links:
                    href = link.get('href')
                    if href and not href.startswith('data:'):
                        favicon_links.append({
                            'rel': link.get('rel'),
                            'href': href,
                            'sizes': link.get('sizes', 'unknown')
                        })
            
            if favicon_links:
                def get_size(fl):
                    sizes = fl.get('sizes', '')
                    if sizes and sizes != 'unknown' and 'x' in sizes:
                        try:
                            return int(sizes.split('x')[0])
                        except:
                            pass
                    return 0
                
                favicon_links.sort(key=get_size, reverse=True)
                
                for fl in favicon_links:
                    href = fl['href']
                    
                    if href.startswith('http'):
                        favicon_url = href
                    elif href.startswith('//'):
                        favicon_url = 'https:' + href
                    elif href.startswith('/'):
                        favicon_url = base_url + href
                    else:
                        favicon_url = f"{homepage_url.rstrip('/')}/{href}"
                    
                    try:
                        test_response = self.session.head(favicon_url, headers=headers, timeout=5)
                        if test_response.status_code == 200:
                            return favicon_url
                    except:
                        continue
            
            return None
            
        except Exception:
            return None

    def download_favicon_as_webp(self, favicon_url: str) -> Optional[bytes]:
        """Download favicon and convert to WebP"""
        try:
            response = self.session.get(favicon_url, timeout=10)
            response.raise_for_status()
            
            # Handle SVG separately
            if favicon_url.endswith('.svg') or response.headers.get('content-type', '').startswith('image/svg'):
                try:
                    import cairosvg
                    png_data = cairosvg.svg2png(bytestring=response.content)
                    img = Image.open(BytesIO(png_data))
                except:
                    return None
            else:
                img = Image.open(BytesIO(response.content))
            
            original_width, original_height = img.size
            
            # Convert to RGBA to preserve transparency
            if img.mode not in ['RGB', 'RGBA']:
                if img.mode == 'P':
                    if 'transparency' in img.info:
                        img = img.convert('RGBA')
                    else:
                        img = img.convert('RGB')
                elif img.mode in ['LA', 'La']:
                    img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')
            
            # Check if image actually has transparency
            has_transparency = img.mode == 'RGBA'
            if has_transparency:
                extrema = img.getextrema()
                if len(extrema) == 4 and extrema[3][0] == 255 and extrema[3][1] == 255:
                    has_transparency = False
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                    img = background
            
            # Calculate scaling to fit within LOGO_SIZE
            target_width, target_height = settings.LOGO_SIZE
            ratio = min(target_width / original_width, target_height / original_height)
            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)
            
            # Resize (upscale or downscale as needed)
            if new_width != original_width or new_height != original_height:
                resample_method = Image.LANCZOS if ratio < 1.0 else Image.BICUBIC
                img = img.resize((new_width, new_height), resample_method)
            
            # Create square canvas with padding
            if has_transparency:
                square_img = Image.new('RGBA', settings.LOGO_SIZE, (0, 0, 0, 0))
            else:
                square_img = Image.new('RGB', settings.LOGO_SIZE, (255, 255, 255))
            
            # Center the image
            offset_x = (target_width - new_width) // 2
            offset_y = (target_height - new_height) // 2
            
            if has_transparency and img.mode == 'RGBA':
                square_img.paste(img, (offset_x, offset_y), img)
            else:
                square_img.paste(img, (offset_x, offset_y))
            
            # Save as WebP
            buf = BytesIO()
            square_img.save(buf, format="WEBP", quality=80)
            return buf.getvalue()
            
        except Exception:
            return None

    # ---------- Placeholder generation ----------
    @staticmethod
    def get_gradient_colors(name: str) -> tuple[str, str, str]:
        """Get gradient colors based on company name hash"""
        if not name:
            return GRADIENTS[0]
        h = hashlib.md5(name.encode("utf-8")).hexdigest()
        index = int(h[:8], 16) % len(GRADIENTS)
        return GRADIENTS[index]

    @staticmethod
    def draw_smooth_gradient(draw, size, color1, color2, color3):
        """Draw a smooth 3-color gradient"""
        w, h = size
        r1, g1, b1 = ImageColor.getrgb(color1)
        r2, g2, b2 = ImageColor.getrgb(color2)
        r3, g3, b3 = ImageColor.getrgb(color3)
        
        for x in range(w):
            ratio = x / w
            if ratio < 0.5:
                sub = ratio * 2
                r = int(r1 + (r2 - r1) * sub)
                g = int(g1 + (g2 - g1) * sub)
                b = int(b1 + (b2 - b1) * sub)
            else:
                sub = (ratio - 0.5) * 2
                r = int(r2 + (r3 - r2) * sub)
                g = int(g2 + (g3 - g2) * sub)
                b = int(b2 + (b3 - b2) * sub)
            draw.line([(x, 0), (x, h)], fill=(r, g, b))

    @staticmethod
    def _get_monogram(name: str) -> str:
        """Return the first letter of the company name."""
        words = [w for w in name.strip().split() if w and w.lower() not in {
            "inc", "corp", "ltd", "llc", "co", "the", "a", "an", "of", "and", "group", "holdings"
        }]
        if words:
            return words[0][0].upper()
        return name.strip()[0].upper() if name.strip() else "?"

    @staticmethod
    def draw_diagonal_gradient(draw, size, color1, color2, color3):
        """Draw a diagonal (top-left → bottom-right) 3-color gradient."""
        w, h = size
        r1, g1, b1 = ImageColor.getrgb(color1)
        r2, g2, b2 = ImageColor.getrgb(color2)
        r3, g3, b3 = ImageColor.getrgb(color3)
        for i in range(w + h):
            ratio = i / (w + h)
            if ratio < 0.5:
                t = ratio * 2
                r = int(r1 + (r2 - r1) * t)
                g = int(g1 + (g2 - g1) * t)
                b = int(b1 + (b2 - b1) * t)
            else:
                t = (ratio - 0.5) * 2
                r = int(r2 + (r3 - r2) * t)
                g = int(g2 + (g3 - g2) * t)
                b = int(b2 + (b3 - b2) * t)
            draw.line([(max(0, i - h), min(i, h - 1)), (min(i, w - 1), max(0, i - w))], fill=(r, g, b))

    @staticmethod
    def _draw_dot_pattern(draw, size, dot_color):
        """Overlay a subtle grid of small semi-transparent dots."""
        w, h = size
        spacing = max(8, w // 8)
        r, g, b = ImageColor.getrgb(dot_color)
        for x in range(0, w, spacing):
            for y in range(0, h, spacing):
                draw.ellipse([x - 1, y - 1, x + 1, y + 1], fill=(r, g, b, 40))

    @staticmethod
    def _apply_rounded_corners(image: Image.Image, radius: int) -> Image.Image:
        """Clip image to rounded rectangle using an alpha mask."""
        image = image.convert("RGBA")
        w, h = image.size
        mask = Image.new("L", (w, h), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
        result = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        result.paste(image, mask=mask)
        return result

    def generate_placeholder_webp(self, name: str) -> Optional[bytes]:
        """Generate a polished placeholder logo: diagonal gradient, dot pattern, monogram, rounded corners."""
        try:
            monogram = self._get_monogram(name)
            color1, color2, color3 = self.get_gradient_colors(name)

            width, height = settings.LOGO_SIZE
            upscale = 8
            render_size = (width * upscale, height * upscale)

            image = Image.new("RGBA", render_size, (0, 0, 0, 0))
            draw = ImageDraw.Draw(image, "RGBA")

            # Diagonal gradient background
            self.draw_diagonal_gradient(draw, render_size, color1, color2, color3)

            # Subtle dot pattern overlay
            self._draw_dot_pattern(draw, render_size, "#FFFFFF")

            # Monogram text
            font_size = int(render_size[0] * 0.55)
            try:
                font = ImageFont.truetype(self.font_path, font_size) if self.font_path else ImageFont.load_default(size=font_size)
            except Exception:
                try:
                    font = ImageFont.load_default(size=font_size)
                except TypeError:
                    font = ImageFont.load_default()

            # Soft drop shadow
            shadow_draw = ImageDraw.Draw(image)
            bbox = shadow_draw.textbbox((0, 0), monogram, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = (render_size[0] - tw) / 2 - bbox[0]
            ty = (render_size[1] - th) / 2 - bbox[1]
            offset = max(2, render_size[0] // 32)
            shadow_draw.text((tx + offset, ty + offset), monogram, fill=(0, 0, 0, 60), font=font)

            # Main white text
            draw.text((tx, ty), monogram, fill=(255, 255, 255, 245), font=font)

            # Rounded corners (radius = 22% of render width → looks like an app icon)
            corner_radius = render_size[0] // 5
            image = self._apply_rounded_corners(image, corner_radius)

            # Downscale to final size with LANCZOS
            final_image = image.resize(settings.LOGO_SIZE, resample=Image.LANCZOS)

            buf = BytesIO()
            final_image.save(buf, format="WEBP", quality=85)
            return buf.getvalue()

        except Exception:
            return None

    # ---------- Upload ----------
    def upload_and_get_url(self, object_name: str, image_bytes: bytes) -> Optional[str]:
        if settings.DRY_RUN:
            try:
                host = settings.SUPABASE_URL.split("//")[1]
            except Exception:
                host = "example.local"
            return f"https://{host}/storage/v1/object/public/{settings.BUCKET_NAME}/{object_name}"
        
        bucket = self.db.client.storage.from_(settings.BUCKET_NAME)
        try:
            bucket.upload(object_name, image_bytes, file_options={"content-type": "image/webp", "upsert": True})
        except TypeError:
            try:
                bucket.upload(object_name, image_bytes, {"content-type": "image/webp"})
            except Exception as e:
                msg = str(e).lower()
                if any(k in msg for k in ("exists", "already", "conflict")):
                    try:
                        if hasattr(bucket, "update"):
                            bucket.update(object_name, image_bytes, {"content-type": "image/webp"})
                        else:
                            bucket.remove([object_name])
                            bucket.upload(object_name, image_bytes, {"content-type": "image/webp"})
                    except Exception:
                        return None
                else:
                    return None
        except Exception:
            return None

        try:
            public_url = bucket.get_public_url(object_name)
            if isinstance(public_url, dict):
                public_url = public_url.get("publicUrl") or public_url.get("public_url")
            return public_url
        except Exception:
            host = settings.SUPABASE_URL.split("//")[1]
            return f"https://{host}/storage/v1/object/public/{settings.BUCKET_NAME}/{object_name}"

    # ---------- public entrypoint ----------
    def add_logo_if_missing_or_stale(self, cik: str, company_name: str, filing_text: str = "") -> None:
        row = self.db.get_logo_fields(cik)
        needs_refresh = False
        if not row or not row.get("logo_url") or not row.get("updated_logo_date"):
            needs_refresh = True
        else:
            try:
                last = datetime.date.fromisoformat(str(row["updated_logo_date"])[:10])
                if (datetime.date.today() - last).days >= settings.REFRESH_AFTER_DAYS:
                    needs_refresh = True
            except Exception:
                needs_refresh = True

        if not needs_refresh:
            return

        logo_bytes = None
        logo_type = None
        homepage = None

        if self.backfill_mode:
            # Backfill strategy: SEC filing text → DuckDuckGo → placeholder
            # Strategy 1: Extract URL directly from filing text
            if filing_text:
                homepage = self.extract_url_from_filing(filing_text)
                if homepage:
                    print(f"[LOGO] Found homepage in filing: {homepage}")

            # Strategy 2: DuckDuckGo instant answer
            if not homepage:
                homepage = self.search_homepage_duckduckgo(company_name or "")
                if homepage:
                    print(f"[LOGO] Found homepage via DuckDuckGo: {homepage}")

            # Try to get favicon from whatever homepage we found
            if homepage:
                favicon_url = self.get_favicon_url(homepage)
                if favicon_url:
                    logo_bytes = self.download_favicon_as_webp(favicon_url)
                    if logo_bytes:
                        logo_type = "favicon"
        else:
            # Normal strategy: Google Custom Search → favicon
            homepage = self.search_homepage_google(company_name or "")
            if homepage:
                favicon_url = self.get_favicon_url(homepage)
                if favicon_url:
                    logo_bytes = self.download_favicon_as_webp(favicon_url)
                    if logo_bytes:
                        logo_type = "favicon"

        # Final fallback: generate placeholder
        if not logo_bytes:
            logo_bytes = self.generate_placeholder_webp(company_name or "")
            if logo_bytes:
                logo_type = "placeholder"

        if not logo_bytes:
            return

        object_name = self.hashed_object_name(cik)
        public_url = self.upload_and_get_url(object_name, logo_bytes)
        if not public_url:
            return

        today = datetime.date.today().isoformat()
        self.db.set_logo_fields(cik, public_url, logo_type, homepage, today)