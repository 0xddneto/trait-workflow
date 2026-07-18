"""Export OpenRaster (.ora): zip com base travada na camada 1 e trait na 2."""

import io
import zipfile

STACK_XML = """<?xml version='1.0' encoding='UTF-8'?>
<image w="{w}" h="{h}" xres="72" yres="72" version="0.0.3">
  <stack>
    <layer name="layer 2 - trait" src="data/layer_trait.png" x="0" y="0" opacity="1.0" visibility="visible"/>
    <layer name="layer 1 - base (locked)" src="data/layer_base.png" x="0" y="0" opacity="1.0" visibility="visible" edit-locked="true"/>
  </stack>
</image>
"""


def _png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def write_ora(path, base, trait, merged):
    w, h = base.size
    with zipfile.ZipFile(path, "w") as z:
        # mimetype deve ser a primeira entrada e sem compressao (spec OpenRaster)
        z.writestr("mimetype", "image/openraster", compress_type=zipfile.ZIP_STORED)
        z.writestr("stack.xml", STACK_XML.format(w=w, h=h),
                   compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("data/layer_base.png", _png_bytes(base))
        z.writestr("data/layer_trait.png", _png_bytes(trait))
        z.writestr("mergedimage.png", _png_bytes(merged))
        thumb = merged.copy()
        thumb.thumbnail((256, 256))
        z.writestr("Thumbnails/thumbnail.png", _png_bytes(thumb))
    return path
