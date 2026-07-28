from dataclasses import dataclass
from io import BytesIO
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_AVATAR_BYTES = 5 * 1024 * 1024
MAX_AVATAR_INPUT_PIXELS = 40_000_000
AVATAR_OUTPUT_SIZE = (512, 512)
ALLOWED_AVATAR_CONTENT_TYPES = frozenset(
    {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)
CONTENT_TYPE_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class AvatarValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ProcessedAvatar:
    content: bytes
    content_type: str = "image/webp"
    extension: str = "webp"


class AvatarImageProcessor:
    def process(self, content: bytes, declared_content_type: str | None) -> ProcessedAvatar:
        if not content:
            raise AvatarValidationError("avatar_empty", "Choose an image to upload.")
        if len(content) > MAX_AVATAR_BYTES:
            raise AvatarValidationError(
                "avatar_too_large",
                "Profile images must be 5 MB or smaller.",
            )
        if declared_content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
            raise AvatarValidationError(
                "avatar_type_unsupported",
                "Upload a JPEG, PNG, or WebP image.",
            )

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as source:
                    if source.format != CONTENT_TYPE_FORMATS[declared_content_type]:
                        raise AvatarValidationError(
                            "avatar_type_mismatch",
                            "The uploaded file does not match its image type.",
                        )
                    if source.width * source.height > MAX_AVATAR_INPUT_PIXELS:
                        raise AvatarValidationError(
                            "avatar_dimensions_too_large",
                            "The image dimensions are too large.",
                        )

                    source.load()
                    oriented = ImageOps.exif_transpose(source)
                    output_mode = "RGBA" if "A" in oriented.getbands() else "RGB"
                    normalized = oriented.convert(output_mode)
                    cropped = ImageOps.fit(
                        normalized,
                        AVATAR_OUTPUT_SIZE,
                        method=Image.Resampling.LANCZOS,
                    )
                    buffer = BytesIO()
                    cropped.save(
                        buffer,
                        format="WEBP",
                        quality=85,
                        method=6,
                    )
        except AvatarValidationError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as exc:
            raise AvatarValidationError(
                "avatar_invalid",
                "The selected file is not a valid image.",
            ) from exc

        return ProcessedAvatar(content=buffer.getvalue())
