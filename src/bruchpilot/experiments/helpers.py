import numpy as np
from panda3d.core import Texture, PTAUchar, CPTAUchar


def create_color_texture(c):
    """Sets up a simple Panda3D texture from raw numpy values."""
    tex = Texture("image1")
    tex.setMagfilter(Texture.FTNearest)
    tex.setup2dTexture(1, 1, Texture.TUnsignedByte, Texture.FRgb8)

    Pic = np.array(c, np.uint8)
    p1 = PTAUchar()
    p1.setData(Pic.tostring())
    c1 = CPTAUchar(p1)
    tex.setRamImage(c1)

    return tex


def create_striped_texture(c1, c2, nearest=False):
    """Generates a stripe pattern with contrasts c1 and c2."""
    texture = Texture("stripes")

    Pic = np.r_[np.tile(c1, (64, 1)), np.tile(c2, (64, 1))]

    Pic1 = np.array([Pic], dtype=np.uint8)

    # print Pic1.shape
    texture.setup2dTexture(Pic1.shape[1], Pic1.shape[0], Texture.TUnsignedByte, Texture.FRgb8)
    if nearest:
        texture.setMagfilter(Texture.FTNearest)
    # texture.setMinfilter(Texture.FTLinearMipmapLinear)
    # texture.setAnisotropicDegree(16)

    p1 = PTAUchar()
    p1.setData(Pic1.tostring())
    c1 = CPTAUchar(p1)
    texture.setRamImage(c1)

    return texture


def create_checker_texture(c1, c2, size):
    """Creates checkerboard texture with contrasts c1 and c2."""
    tex = np.random.randint(2, size=size)
    zeros, ones = tex == 0, tex == 1
    tex[zeros] = c1
    tex[ones] = c2

    tex = np.tile(tex, (3, 1, 1)).swapaxes(0, 1).swapaxes(1, 2).astype(np.uint8)

    texture = Texture("image")
    texture.setup2dTexture(tex.shape[1], tex.shape[0], Texture.TUnsignedByte, Texture.FRgb8)

    p = PTAUchar.emptyArray(0)
    p.setData(tex.tostring())
    texture.setRamImage(CPTAUchar(p))

    texture.setMagfilter(Texture.FTNearest)
    texture.setMinfilter(Texture.FTNearest)

    return texture
