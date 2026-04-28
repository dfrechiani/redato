from enum import Enum
from typing import Dict, Optional

import cv2
from pydantic import BaseModel


class ImageFormat(str, Enum):
    """Enumeration of supported image formats."""

    JPEG = "jpeg"
    JPG = "jpg"
    PNG = "png"
    TIFF = "tiff"
    TIF = "tif"
    WEBP = "webp"
    BMP = "bmp"
    PPM = "ppm"
    PGM = "pgm"
    PBM = "pbm"
    PNM = "pnm"
    EXR = "exr"
    HDR = "hdr"
    GIF = "gif"
    JPEG2000 = "jpeg2000"
    JP2 = "jp2"

    @classmethod
    def from_string(cls, format_str: str) -> "ImageFormat":  # noqa: C901
        """Convert a string to an ImageFormat enum."""
        if not format_str:
            return cls.JPEG

        clean_format = format_str.lower().strip().lstrip(".")

        try:
            return cls(clean_format)
        except ValueError:
            if clean_format == "jpg":
                return cls.JPEG
            elif clean_format == "tif":
                return cls.TIFF
            elif clean_format in ("jp2", "j2k"):
                return cls.JPEG2000

            return cls.JPEG


class FormatSpec(BaseModel):
    """Specification for an image format."""

    extension: str
    mime_type: str
    quality_flag: Optional[int] = None
    default_quality: Optional[int] = None

    def get_encoding_params(self, quality: Optional[int] = None) -> list:
        """Get encoding parameters for cv2.imencode."""
        if self.quality_flag is None:
            return []

        # Use provided quality or default
        quality_value = quality if quality is not None else self.default_quality
        return [self.quality_flag, quality_value]


# Create format specifications
FORMAT_SPECS: Dict[ImageFormat, FormatSpec] = {
    ImageFormat.JPEG: FormatSpec(
        extension=".jpeg",
        mime_type="image/jpeg",
        quality_flag=cv2.IMWRITE_JPEG_QUALITY,
        default_quality=95,
    ),
    ImageFormat.JPG: FormatSpec(
        extension=".jpg",
        mime_type="image/jpeg",
        quality_flag=cv2.IMWRITE_JPEG_QUALITY,
        default_quality=95,
    ),
    ImageFormat.PNG: FormatSpec(
        extension=".png",
        mime_type="image/png",
        quality_flag=cv2.IMWRITE_PNG_COMPRESSION,
        default_quality=3,
    ),
    ImageFormat.TIFF: FormatSpec(
        extension=".tiff",
        mime_type="image/tiff",
        quality_flag=cv2.IMWRITE_TIFF_COMPRESSION,
        default_quality=1,
    ),
    ImageFormat.TIF: FormatSpec(
        extension=".tif",
        mime_type="image/tiff",
        quality_flag=cv2.IMWRITE_TIFF_COMPRESSION,
        default_quality=1,
    ),
    ImageFormat.WEBP: FormatSpec(
        extension=".webp",
        mime_type="image/webp",
        quality_flag=cv2.IMWRITE_WEBP_QUALITY,
        default_quality=95,
    ),
    ImageFormat.BMP: FormatSpec(extension=".bmp", mime_type="image/bmp"),
    ImageFormat.PPM: FormatSpec(extension=".ppm", mime_type="image/x-portable-pixmap"),
    ImageFormat.PGM: FormatSpec(extension=".pgm", mime_type="image/x-portable-graymap"),
    ImageFormat.PBM: FormatSpec(extension=".pbm", mime_type="image/x-portable-bitmap"),
    ImageFormat.PNM: FormatSpec(extension=".pnm", mime_type="image/x-portable-anymap"),
    ImageFormat.EXR: FormatSpec(extension=".exr", mime_type="image/x-exr"),
    ImageFormat.HDR: FormatSpec(extension=".hdr", mime_type="image/vnd.radiance"),
    ImageFormat.GIF: FormatSpec(extension=".gif", mime_type="image/gif"),
    ImageFormat.JPEG2000: FormatSpec(extension=".jp2", mime_type="image/jp2"),
    ImageFormat.JP2: FormatSpec(extension=".jp2", mime_type="image/jp2"),
}

IMGHDR_TO_FORMAT = {
    "jpeg": ImageFormat.JPEG,
    "png": ImageFormat.PNG,
    "gif": ImageFormat.GIF,
    "tiff": ImageFormat.TIFF,
    "bmp": ImageFormat.BMP,
    "webp": ImageFormat.WEBP,
}
