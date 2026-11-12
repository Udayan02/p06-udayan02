# -*- coding: utf-8 -*-

# thumbor imaging service
# https://github.com/thumbor/thumbor/wiki

# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license
# Copyright (c) 2011 globo.com thumbor@googlegroups.com

"""Regression test for an extreme aspect ratio returning an empty picture.

``auto_crop()`` picks a crop box from the target ratio. For a target far
from the source ratio the computed crop side rounds down to zero -- a 1x1
source asked for 800x20 gives ``round(1 * 20 / 800) = 0`` -- so the image
is cropped to a zero-height box. Resizing that empty image yields an
every-pixel-transparent result, which is the issue's blank picture.

A crop side of zero is never meaningful. Clamping both crop sides to at
least one pixel keeps a real one-pixel band to resize, so a target of at
least one pixel per side returns a real picture of that size.
"""

from io import BytesIO

from tornado.testing import gen_test

from PIL import Image

from tests.base import TestCase
from thumbor.config import Config
from thumbor.context import Context, RequestParameters
from thumbor.engines.pil import Engine
from thumbor.importer import Importer
from thumbor.transformer import Transformer


class ExtremeAspectCropTestCase(TestCase):
    def get_context(self):
        cfg = Config(
            SECURITY_KEY="ACME-SEC",
            ENGINE="thumbor.engines.pil",
            LOADER="thumbor.loaders.file_loader",
            STORAGE="thumbor.storages.no_storage",
        )
        importer = Importer(cfg)
        importer.import_modules()

        context = Context(config=cfg, importer=importer)
        context.request = RequestParameters()

        return context

    def _engine_with_rainbow(self):
        """A 16x16 transparent PNG with vertical rainbow bars.

        The bars keep the picture visible once resized, so an entirely
        transparent result can only come from an empty crop.
        """
        source = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        for x in range(16):
            for y in range(16):
                source.putpixel((x, y), (255, x * 16, y * 16, 255))

        buffer = BytesIO()
        source.save(buffer, "PNG")

        engine = Engine(self.context)
        engine.load(buffer.getvalue(), ".png")
        return engine

    @gen_test
    async def test_very_wide_target_returns_a_real_picture(self):
        engine = self._engine_with_rainbow()

        self.context.request.width = 800
        self.context.request.height = 20
        self.context.request.fit_in = False
        self.context.request.smart = True
        self.context.request.filters = []
        self.context.request.focal_points = []
        self.context.request.engine = engine
        engine.focal_points = []

        transformer = Transformer(self.context)
        await transformer.transform()

        result = engine.image.convert("RGBA")

        assert result.size == (800, 20)

        # Every pixel being fully transparent is the empty picture the
        # issue reports.
        alpha = result.getchannel("A")
        assert max(alpha.getextrema()) > 0, (
            "the 800x20 result is entirely transparent: the crop rounded "
            "to a zero-height box and there was nothing left to resize"
        )
