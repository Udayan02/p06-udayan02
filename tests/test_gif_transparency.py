# -*- coding: utf-8 -*-

# thumbor imaging service
# https://github.com/thumbor/thumbor/wiki

# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license
# Copyright (c) 2011 globo.com thumbor@googlegroups.com

"""Regression test for a resized palette GIF losing its transparency.

A GIF whose source is in palette (``P``) mode marks one palette entry as
transparent through ``info["transparency"]``. With the default
``PILLOW_PRESERVE_INDEXED_MODE = True`` the Pillow engine resizes the
image and then quantizes it back to ``P`` mode, but the surviving palette
alpha is not written back to ``image.info["transparency"]``. The GIF
encoder therefore receives an indexed image with no transparent index and
writes every pixel as opaque, so the area that used to be transparent
becomes a solid black box.

The resized GIF must keep a transparency index, and the pixels that were
transparent in the source must be transparent in the output. A palette
GIF with no transparent entry stays opaque.
"""

from io import BytesIO
from unittest import TestCase

from PIL import Image

from thumbor.config import Config
from thumbor.context import Context
from thumbor.engines.pil import Engine


def _palette_gif_with_transparency():
    """Build a small palette GIF with a single transparent entry.

    Returns a ``(buffer, transparent_pixel_count)`` tuple. The source is a
    solid opaque disc on a fully transparent background, the shape the
    issue describes as the course sticker.
    """
    width, height = 40, 40
    rgba = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for y in range(height):
        for x in range(width):
            if (x - width // 2) ** 2 + (y - height // 2) ** 2 <= (width // 3) ** 2:
                rgba.putpixel((x, y), (0, 0, 255, 255))

    palette = rgba.convert("P", palette=Image.Palette.ADAPTIVE, colors=16)

    # Mark the entry that holds the transparent background as the
    # transparent index, the way the issue's palette source does.
    transparent_index = palette.getpixel((0, 0))
    palette.info["transparency"] = transparent_index

    buffer = BytesIO()
    palette.save(buffer, "GIF", transparency=transparent_index)

    transparent_pixels = sum(
        1 for pixel in palette.getdata() if pixel == transparent_index
    )
    return buffer.getvalue(), transparent_pixels


class GifTransparencyTestCase(TestCase):
    def get_context(self):
        cfg = Config(
            SECURITY_KEY="ACME-SEC",
            ENGINE="thumbor.engines.pil",
            PILLOW_PRESERVE_INDEXED_MODE=True,
        )
        cfg.LOADER = "thumbor.loaders.file_loader"
        cfg.STORAGE = "thumbor.storages.no_storage"

        return Context(config=cfg)

    def setUp(self):
        self.context = self.get_context()

    def test_resized_palette_gif_keeps_its_transparency_index(self):
        source, transparent_pixels = _palette_gif_with_transparency()
        assert transparent_pixels > 0, "the fixture has no transparent pixels"

        engine = Engine(self.context)
        engine.load(source, ".gif")
        engine.resize(120, 80)

        output = engine.read(extension=".gif")

        result = Image.open(BytesIO(output))

        assert result.format == "GIF"
        assert "transparency" in result.info, (
            "the resized GIF carries no transparency index, so the area "
            "that was transparent comes back as a solid black box"
        )

        transparency = result.info["transparency"]
        result_pixels = list(result.getdata())
        assert result_pixels.count(transparency) > 0, (
            "the resized GIF has a transparency index but no pixel uses it, "
            "so the transparent background was flattened"
        )
