"""Construcao e manipulacao de mascaras (L, 255 = area ativa)."""

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def load_mask(path, size):
    m = Image.open(path).convert("L")
    if m.size != size:
        m = m.resize(size, Image.NEAREST)
    return m


def grow(mask, px):
    """Dilata (px > 0) ou erode (px < 0) a mascara em passos de 1 pixel."""
    for _ in range(abs(int(px))):
        f = ImageFilter.MaxFilter(3) if px > 0 else ImageFilter.MinFilter(3)
        mask = mask.filter(f)
    return mask


def mask_from_regions(size, regions, base=None):
    """Monta uma mascara a partir de formas descritas em JSON.

    Cada regiao: {"shape": "rect"|"ellipse"|"polygon"|"base_alpha",
                  "mode": "add"|"subtract" (padrao add),
                  "xy": [x0, y0, x1, y1] ou lista de pontos,
                  "grow": int (apenas base_alpha)}
    "base_alpha" usa a silhueta (canal alfa) da base do projeto.
    """
    m = Image.new("L", size, 0)
    for r in regions:
        mode = r.get("mode", "add")
        shape = r["shape"]
        if shape == "base_alpha":
            if base is None:
                raise ValueError("regiao base_alpha requer a imagem da base")
            part = base.getchannel("A").point(lambda v: 255 if v > 8 else 0)
            part = grow(part, r.get("grow", 0))
        elif shape == "file":
            im = Image.open(r["path"])
            if "A" in im.getbands():
                part = im.getchannel("A").point(lambda v: 255 if v > 8 else 0)
            else:
                part = im.convert("L").point(lambda v: 255 if v > 127 else 0)
            if part.size != size:
                part = part.resize(size, Image.NEAREST)
            part = grow(part, r.get("grow", 0))
        else:
            part = Image.new("L", size, 0)
            d = ImageDraw.Draw(part)
            xy = [tuple(p) if isinstance(p, (list, tuple)) else p for p in r["xy"]]
            if shape == "rect":
                d.rectangle(xy, fill=255)
            elif shape == "ellipse":
                d.ellipse(xy, fill=255)
            elif shape == "polygon":
                d.polygon(xy, fill=255)
            else:
                raise ValueError(f"shape desconhecido: {shape}")
        if mode == "add":
            m = ImageChops.lighter(m, part)
        else:
            m = ImageChops.subtract(m, part)
    return m
