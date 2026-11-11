# -*- coding: utf-8 -*-

# thumbor imaging service
# https://github.com/thumbor/thumbor/wiki

# Licensed under the MIT license:
# http://www.opensource.org/licenses/mit-license
# Copyright (c) 2011 globo.com thumbor@googlegroups.com

"""Regression test for transparent round_corner carrying a dark ring.

When round_corner runs with the transparent flag set, the antialiased
edge of the arc used to keep its color channels and merely scale them
toward black by ``(1 - aa)``, while the alpha channel stayed fully
opaque. That produces a dark outline along every curved corner.

The edge should instead keep its original color and become partly
transparent, so the picture fades into whatever is behind it.
"""

import numpy as np
from PIL import Image
from tornado.testing import gen_test

from tests.base import FilterTestCase


class RoundCornerTransparentAlphaTestCase(FilterTestCase):
    @gen_test
    async def test_transparent_corner_fades_through_alpha(self):
        source = Image.open(self.get_fixture_path("source.jpg")).convert("RGBA")
        original = np.array(source)

        image = await self.get_filtered(
            "source.jpg",
            "thumbor.filters.round_corner",
            "round_corner(50,255,255,255,1)",
            mode="RGBA",
        )
        result = np.array(image)

        alpha = result[..., 3]
        partial = (alpha > 0) & (alpha < 255)

        # (1) The arc must be smoothed through the alpha channel: pixels on
        # the curve become partly transparent rather than fully opaque or
        # fully cut away.
        assert partial.any(), (
            "no pixel has alpha strictly between 0 and 255, so the corner "
            "is not smoothed through the alpha channel"
        )

        # (2) Those partly transparent edge pixels that come from the
        # picture (not from the fill color drawn outside the arc) must keep
        # their original color: the edge fades by alpha, it is not scaled
        # toward black. Before the fix every partial edge pixel that came
        # from the picture was darkened and fully opaque instead.
        same_color = (
            np.abs(
                result[partial, :3].astype(int) - original[partial, :3].astype(int)
            ).max(axis=1)
            <= 3
        )
        assert same_color.any(), (
            "no partly transparent edge pixel kept its original color, so "
            "the picture edge is not fading through alpha"
        )

        darkened_edge = (
            np.abs(
                result[partial, :3].astype(int) - original[partial, :3].astype(int)
            ).max(axis=1)
            > 3
        ) & (
            result[partial, :3].astype(int)
            < original[partial, :3].astype(int)
        ).all(axis=1)
        assert not darkened_edge.any(), (
            "partly transparent edge pixels were scaled toward black, which "
            "draws a dark ring along the arc"
        )
