import cv2
import numpy as np


class ImageProcessor:
    @staticmethod
    def enhance_for_pencil(image):
        """
        Refined pencil processing with gentler contrast enhancement
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Gentle CLAHE enhancement
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Very mild contrast stretching
        min_val, max_val = np.percentile(enhanced, (5, 95))
        stretched = np.clip(
            (enhanced - min_val) * 255.0 / (max_val - min_val), 0, 255
        ).astype(np.uint8)

        # Lighter gamma correction to prevent darkening
        gamma = 0.85  # Higher gamma value keeps image brighter
        lookup_table = np.array(
            [((i / 255.0) ** gamma) * 255 for i in np.arange(256)]
        ).astype("uint8")
        gamma_corrected = cv2.LUT(stretched, lookup_table)

        return gamma_corrected

    @staticmethod
    def enhance_for_pen(image):
        """
        Enhanced pen processing optimized for better detail preservation
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 1. Gentle denoising
        denoised = cv2.fastNlMeansDenoising(gray, None, h=7)

        # 2. Enhance contrast using CLAHE with moderate parameters
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
        contrast_enhanced = clahe.apply(denoised)

        # 3. Gentle sharpening
        kernel = (
            np.array([[-0.5, -0.5, -0.5], [-0.5, 5.0, -0.5], [-0.5, -0.5, -0.5]]) / 2.0
        )
        sharpened = cv2.filter2D(contrast_enhanced, -1, kernel)

        # 4. Normalize contrast
        normalized = cv2.normalize(
            sharpened, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX
        )

        # 5. Adaptive thresholding with gentler parameters
        binary = cv2.adaptiveThreshold(
            normalized,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=35,
            C=25,
        )

        return binary
