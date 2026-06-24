from __future__ import annotations

import argparse
import csv
import random
import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


# Configurable constants
RAW_DIR = "Pics-BirdNests/RawPics"
OUTPUT_DIR = "Pics-BirdNests/Crops"
PATCH_SIZE = 256
STRIDE = 128
BLUE_HSV_LOWER = (90, 50, 50)
BLUE_HSV_UPPER = (140, 255, 255)
MASK_DILATION = 20
MIN_CONTENT_RATIO = 0.35
GENERATE_CLEAN_NEGATIVE = True
GENERATE_DIRTY_POSITIVE = True
POSITIVE_JITTER_CROPS = 3
POSITIVE_JITTER_RADIUS = 64
MIN_BLUE_COMPONENT_AREA = 20
RANDOM_SEED = 42
CLEAR_OUTPUT_DIRS = False
JPEG_QUALITY = 100
DIRTY_CROP_SOURCE = "registered_original"
BLUE_INPAINT_DILATION = 6
BLUE_INPAINT_RADIUS = 3
FEATURE_MASK_DILATION = 12
SIFT_MAX_FEATURES = 6000
SIFT_RATIO_TEST = 0.72
HOMOGRAPHY_RANSAC_REPROJ_THRESHOLD = 5.0
MIN_HOMOGRAPHY_INLIERS = 40
ORIGINAL_MATCH_SEARCH_RADIUS = 160
ORIGINAL_MATCH_BLUE_DILATION = 12
MIN_ORIGINAL_MATCH_VALID_RATIO = 0.30

# Adaptive clean-crop coverage. These preserve the original script's behavior,
# with a slightly denser pass to cover clean-region edges more thoroughly
# without creating as many near-duplicate crops as a 32 px step.
# find every valid top-left point first, then sample each connected clean region
# at a tighter interval and include useful region edges.
COVERAGE_STEP = 48
MIN_EDGE_SHIFT = 24

METADATA_COLUMNS = [
    "source_id",
    "source_image",
    "marked_image",
    "output_file",
    "label",
    "x",
    "y",
    "width",
    "height",
    "patch_size",
    "source_width",
    "source_height",
    "dirty_spot_id",
    "dirty_center_x",
    "dirty_center_y",
    "blue_component_area",
    "generation_method",
    "marked_x",
    "marked_y",
    "original_x",
    "original_y",
    "original_match_score",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate clean/dirty bird-nest crop patches and metadata."
    )
    parser.add_argument("--raw-dir", default=RAW_DIR, help="Directory containing raw image pairs.")
    parser.add_argument("--output-dir", default=OUTPUT_DIR, help="Directory to write crop outputs.")
    parser.add_argument("--patch-size", type=int, default=PATCH_SIZE)
    parser.add_argument("--stride", type=int, default=STRIDE)
    parser.add_argument("--coverage-step", type=int, default=COVERAGE_STEP)
    parser.add_argument("--min-edge-shift", type=int, default=MIN_EDGE_SHIFT)
    parser.add_argument("--mask-dilation", type=int, default=MASK_DILATION)
    parser.add_argument("--min-content-ratio", type=float, default=MIN_CONTENT_RATIO)
    parser.add_argument("--positive-jitter-crops", type=int, default=POSITIVE_JITTER_CROPS)
    parser.add_argument("--positive-jitter-radius", type=int, default=POSITIVE_JITTER_RADIUS)
    parser.add_argument("--min-blue-component-area", type=int, default=MIN_BLUE_COMPONENT_AREA)
    parser.add_argument("--random-seed", type=int, default=RANDOM_SEED)
    parser.add_argument(
        "--dirty-crop-source",
        choices=("registered_original", "matched_original", "inpainted_marked"),
        default=DIRTY_CROP_SOURCE,
    )
    parser.add_argument("--no-clean", action="store_true", help="Do not generate clean crops.")
    parser.add_argument("--no-dirty", action="store_true", help="Do not generate dirty crops.")
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep existing crop/debug files. This is the default safe behavior.",
    )
    parser.add_argument(
        "--clear-output",
        action="store_true",
        help="Delete previous generated crop/debug files before writing new outputs.",
    )
    return parser.parse_args()


def configure_from_args(args: argparse.Namespace) -> None:
    global RAW_DIR
    global OUTPUT_DIR
    global PATCH_SIZE
    global STRIDE
    global MASK_DILATION
    global MIN_CONTENT_RATIO
    global GENERATE_CLEAN_NEGATIVE
    global GENERATE_DIRTY_POSITIVE
    global POSITIVE_JITTER_CROPS
    global POSITIVE_JITTER_RADIUS
    global MIN_BLUE_COMPONENT_AREA
    global RANDOM_SEED
    global CLEAR_OUTPUT_DIRS
    global DIRTY_CROP_SOURCE
    global COVERAGE_STEP
    global MIN_EDGE_SHIFT

    RAW_DIR = args.raw_dir
    OUTPUT_DIR = args.output_dir
    PATCH_SIZE = args.patch_size
    STRIDE = args.stride
    COVERAGE_STEP = args.coverage_step
    MIN_EDGE_SHIFT = args.min_edge_shift
    MASK_DILATION = args.mask_dilation
    MIN_CONTENT_RATIO = args.min_content_ratio
    POSITIVE_JITTER_CROPS = args.positive_jitter_crops
    POSITIVE_JITTER_RADIUS = args.positive_jitter_radius
    MIN_BLUE_COMPONENT_AREA = args.min_blue_component_area
    RANDOM_SEED = args.random_seed
    DIRTY_CROP_SOURCE = args.dirty_crop_source
    GENERATE_CLEAN_NEGATIVE = not args.no_clean
    GENERATE_DIRTY_POSITIVE = not args.no_dirty
    CLEAR_OUTPUT_DIRS = bool(args.clear_output and not args.keep_existing)


@dataclass(frozen=True)
class DirtySpot:
    spot_id: int
    center_x: int
    center_y: int
    bbox_x: int
    bbox_y: int
    bbox_width: int
    bbox_height: int
    area: int


@dataclass(frozen=True)
class PositiveWindow:
    x: int
    y: int
    dirty_spot: DirtySpot
    generation_method: str


@dataclass(frozen=True)
class MatchedPositiveWindow:
    marked_x: int
    marked_y: int
    original_x: int
    original_y: int
    dirty_spot: DirtySpot
    generation_method: str
    match_score: float


def natural_sort_key(path: Path) -> tuple[int, str]:
    """Sort 1m.jpg, 2m.jpg, ... before 10m.jpg."""
    match = re.fullmatch(r"(\d+)m", path.stem)
    if match:
        return (int(match.group(1)), path.name)
    return (10**9, path.name)


def resolve_project_path(configured_path: str) -> Path:
    """Resolve paths whether the script is run from the project root or its parent."""
    script_dir = Path(__file__).resolve().parent
    path = Path(configured_path)
    if path.is_absolute():
        resolved = path.resolve()
    elif path.exists():
        resolved = path.resolve()
    else:
        resolved = (script_dir / configured_path).resolve()

    try:
        resolved.relative_to(script_dir)
    except ValueError as exc:
        raise ValueError(f"Path must stay inside project root: {configured_path}") from exc

    if resolved.exists():
        return resolved

    parts = path.parts
    if parts and parts[0] == script_dir.name:
        return script_dir.joinpath(*parts[1:]).resolve()

    return resolved


def original_for_marked(marked_path: Path) -> Path:
    """Convert 15m.jpg to 15.jpg while leaving the directory unchanged."""
    stem = marked_path.stem
    if not stem.endswith("m"):
        raise ValueError(f"Marked image does not end with 'm': {marked_path.name}")
    return marked_path.with_name(f"{stem[:-1]}{marked_path.suffix}")


def read_image(path: Path) -> np.ndarray | None:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        print(f"  WARNING: could not read image: {path}")
    return image


def clear_generated_outputs(clean_dir: Path, dirty_dir: Path, debug_dir: Path) -> None:
    """Remove previous generated crop/debug files so reruns match metadata exactly."""
    if not CLEAR_OUTPUT_DIRS:
        return

    output_dir = resolve_project_path(OUTPUT_DIR)
    expected_dirs = {
        output_dir / "clean_negative",
        output_dir / "dirty_positive",
        output_dir / "debug_masks",
    }

    cleanup_patterns = {
        clean_dir: ("*.jpg",),
        dirty_dir: ("*.jpg",),
        debug_dir: ("*.png", "*.jpg"),
    }

    for directory, patterns in cleanup_patterns.items():
        resolved_directory = directory.resolve()
        if resolved_directory not in {path.resolve() for path in expected_dirs}:
            raise ValueError(f"Refusing to clear unexpected output directory: {directory}")
        if not directory.exists():
            continue
        for pattern in patterns:
            for path in directory.glob(pattern):
                if path.is_file():
                    path.unlink()


def detect_blue_mask(marked_image: np.ndarray) -> np.ndarray:
    """Detect blue annotation pixels from the marked image."""
    hsv = cv2.cvtColor(marked_image, cv2.COLOR_BGR2HSV)
    blue_mask = cv2.inRange(
        hsv,
        np.array(BLUE_HSV_LOWER, dtype=np.uint8),
        np.array(BLUE_HSV_UPPER, dtype=np.uint8),
    )

    return cv2.morphologyEx(
        blue_mask,
        cv2.MORPH_CLOSE,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
    )


def create_exclusion_mask(blue_mask: np.ndarray) -> np.ndarray:
    """Dilate detected blue marks into the clean-crop exclusion region."""
    if MASK_DILATION <= 0:
        return blue_mask.copy()

    kernel_size = (MASK_DILATION * 2) + 1
    dilation_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (kernel_size, kernel_size),
    )
    return cv2.dilate(blue_mask, dilation_kernel, iterations=1)


def dilate_blue_mask_for_inpainting(blue_mask: np.ndarray) -> np.ndarray:
    if BLUE_INPAINT_DILATION <= 0:
        return blue_mask.copy()

    kernel_size = (BLUE_INPAINT_DILATION * 2) + 1
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (kernel_size, kernel_size),
    )
    return cv2.dilate(blue_mask, kernel, iterations=1)


def remove_blue_marks(marked_image: np.ndarray, blue_mask: np.ndarray) -> np.ndarray:
    """Create an unmarked-looking image from the marked image."""
    inpaint_mask = dilate_blue_mask_for_inpainting(blue_mask)
    return cv2.inpaint(
        marked_image,
        inpaint_mask,
        BLUE_INPAINT_RADIUS,
        cv2.INPAINT_TELEA,
    )


def feature_detection_mask(blue_mask: np.ndarray) -> np.ndarray:
    if FEATURE_MASK_DILATION <= 0:
        return cv2.bitwise_not(blue_mask)

    kernel_size = (FEATURE_MASK_DILATION * 2) + 1
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (kernel_size, kernel_size),
    )
    expanded_blue = cv2.dilate(blue_mask, kernel, iterations=1)
    return cv2.bitwise_not(expanded_blue)


def estimate_marked_to_original_homography(
    marked_image: np.ndarray,
    original_image: np.ndarray,
    blue_mask: np.ndarray,
) -> tuple[np.ndarray | None, int, int]:
    """Estimate a projective transform from marked-image pixels to original pixels."""
    marked_gray = cv2.cvtColor(marked_image, cv2.COLOR_BGR2GRAY)
    original_gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
    marked_feature_mask = feature_detection_mask(blue_mask)

    sift = cv2.SIFT_create(nfeatures=SIFT_MAX_FEATURES)
    marked_keypoints, marked_descriptors = sift.detectAndCompute(
        marked_gray,
        marked_feature_mask,
    )
    original_keypoints, original_descriptors = sift.detectAndCompute(
        original_gray,
        None,
    )

    if (
        marked_descriptors is None
        or original_descriptors is None
        or len(marked_keypoints) < 4
        or len(original_keypoints) < 4
    ):
        return None, 0, 0

    matcher = cv2.FlannBasedMatcher(
        dict(algorithm=1, trees=5),
        dict(checks=80),
    )
    matches = matcher.knnMatch(marked_descriptors, original_descriptors, k=2)
    good_matches = [
        match
        for match, neighbor in matches
        if match.distance < SIFT_RATIO_TEST * neighbor.distance
    ]

    if len(good_matches) < 4:
        return None, 0, len(good_matches)

    marked_points = np.float32(
        [marked_keypoints[match.queryIdx].pt for match in good_matches]
    ).reshape(-1, 1, 2)
    original_points = np.float32(
        [original_keypoints[match.trainIdx].pt for match in good_matches]
    ).reshape(-1, 1, 2)

    homography, inlier_mask = cv2.findHomography(
        marked_points,
        original_points,
        cv2.RANSAC,
        HOMOGRAPHY_RANSAC_REPROJ_THRESHOLD,
    )
    if homography is None or inlier_mask is None:
        return None, 0, len(good_matches)

    inlier_count = int(inlier_mask.sum())
    if inlier_count < MIN_HOMOGRAPHY_INLIERS:
        return None, inlier_count, len(good_matches)

    return homography, inlier_count, len(good_matches)


def warp_original_to_marked_frame(
    original_image: np.ndarray,
    marked_image: np.ndarray,
    homography_marked_to_original: np.ndarray,
) -> np.ndarray:
    """Warp the unmarked original image into the marked image coordinate frame."""
    height, width = marked_image.shape[:2]
    return cv2.warpPerspective(
        original_image,
        homography_marked_to_original,
        (width, height),
        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REPLICATE,
    )


def registered_window_inside_original(
    homography_marked_to_original: np.ndarray,
    x: int,
    y: int,
    original_width: int,
    original_height: int,
) -> bool:
    corners = np.float32(
        [
            [
                [x, y],
                [x + PATCH_SIZE - 1, y],
                [x + PATCH_SIZE - 1, y + PATCH_SIZE - 1],
                [x, y + PATCH_SIZE - 1],
            ]
        ]
    )
    mapped = cv2.perspectiveTransform(corners, homography_marked_to_original)[0]
    return bool(
        mapped[:, 0].min() >= 0
        and mapped[:, 1].min() >= 0
        and mapped[:, 0].max() < original_width
        and mapped[:, 1].max() < original_height
    )


def shift_window_inside_registered_original(
    window: PositiveWindow,
    homography_marked_to_original: np.ndarray,
    image_width: int,
    image_height: int,
) -> tuple[PositiveWindow, bool]:
    """Shift a marked-frame crop so its registered original crop has real pixels."""
    if registered_window_inside_original(
        homography_marked_to_original,
        window.x,
        window.y,
        image_width,
        image_height,
    ):
        return window, False

    spot = window.dirty_spot
    min_x = max(0, spot.center_x - PATCH_SIZE + 1)
    max_x = min(spot.center_x, image_width - PATCH_SIZE)
    min_y = max(0, spot.center_y - PATCH_SIZE + 1)
    max_y = min(spot.center_y, image_height - PATCH_SIZE)

    best_position: tuple[int, int] | None = None
    best_distance = float("inf")

    for candidate_y in range(min_y, max_y + 1):
        for candidate_x in range(min_x, max_x + 1):
            distance = (
                ((candidate_x - window.x) * (candidate_x - window.x))
                + ((candidate_y - window.y) * (candidate_y - window.y))
            )
            if distance >= best_distance:
                continue

            if registered_window_inside_original(
                homography_marked_to_original,
                candidate_x,
                candidate_y,
                image_width,
                image_height,
            ):
                best_position = (candidate_x, candidate_y)
                best_distance = distance

    if best_position is None:
        return window, False

    shifted_x, shifted_y = best_position
    return (
        PositiveWindow(
            x=shifted_x,
            y=shifted_y,
            dirty_spot=window.dirty_spot,
            generation_method=window.generation_method,
        ),
        True,
    )


def shift_positive_windows_inside_registered_original(
    positive_windows: list[PositiveWindow],
    homography_marked_to_original: np.ndarray,
    image_width: int,
    image_height: int,
) -> tuple[list[PositiveWindow], int]:
    shifted_windows: list[PositiveWindow] = []
    shifted_count = 0

    for window in positive_windows:
        shifted_window, was_shifted = shift_window_inside_registered_original(
            window,
            homography_marked_to_original,
            image_width,
            image_height,
        )
        shifted_windows.append(shifted_window)
        if was_shifted:
            shifted_count += 1

    return shifted_windows, shifted_count


def has_enough_content(patch: np.ndarray) -> bool:
    """Reject mostly white or very low-texture background patches."""
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)

    # Bird/nest regions tend to be darker or textured; blank background is bright.
    non_bright_ratio = float(np.mean(gray < 245))

    # A small edge contribution helps keep textured light regions from being discarded.
    edges = cv2.Canny(gray, threshold1=50, threshold2=150)
    edge_ratio = float(np.mean(edges > 0))
    content_ratio = max(non_bright_ratio, edge_ratio * 8.0)

    return content_ratio >= MIN_CONTENT_RATIO


def window_sum_map(binary_map: np.ndarray) -> np.ndarray:
    """Return the number of non-zero pixels in every PATCH_SIZE window."""
    integral = cv2.integral(binary_map.astype(np.uint8), sdepth=cv2.CV_32S)
    return (
        integral[PATCH_SIZE:, PATCH_SIZE:]
        - integral[:-PATCH_SIZE, PATCH_SIZE:]
        - integral[PATCH_SIZE:, :-PATCH_SIZE]
        + integral[:-PATCH_SIZE, :-PATCH_SIZE]
    )


def content_ok_map(original_image: np.ndarray) -> np.ndarray:
    """Calculate the content filter for every possible crop top-left position."""
    gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
    area = PATCH_SIZE * PATCH_SIZE

    non_bright = (gray < 245).astype(np.uint8)
    edges = (cv2.Canny(gray, threshold1=50, threshold2=150) > 0).astype(np.uint8)

    non_bright_ratio = window_sum_map(non_bright) / area
    edge_ratio = window_sum_map(edges) / area
    content_ratio = np.maximum(non_bright_ratio, edge_ratio * 8.0)

    return content_ratio >= MIN_CONTENT_RATIO


def detect_dirty_spots(blue_mask: np.ndarray) -> list[DirtySpot]:
    """Find connected blue-mark components and estimate dirty-spot centers."""
    component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        (blue_mask > 0).astype(np.uint8),
        connectivity=8,
    )

    spots: list[DirtySpot] = []
    for label in range(1, component_count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if area < MIN_BLUE_COMPONENT_AREA:
            continue

        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        width = int(stats[label, cv2.CC_STAT_WIDTH])
        height = int(stats[label, cv2.CC_STAT_HEIGHT])
        center_x = int(round(float(centroids[label][0])))
        center_y = int(round(float(centroids[label][1])))
        spots.append(
            DirtySpot(
                spot_id=len(spots) + 1,
                center_x=center_x,
                center_y=center_y,
                bbox_x=x,
                bbox_y=y,
                bbox_width=width,
                bbox_height=height,
                area=area,
            )
        )

    return spots


def clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))


def crop_top_left_centered_on_point(
    center_x: int,
    center_y: int,
    image_width: int,
    image_height: int,
) -> tuple[int, int]:
    x = int(round(center_x - (PATCH_SIZE / 2)))
    y = int(round(center_y - (PATCH_SIZE / 2)))
    return (
        clamp(x, 0, image_width - PATCH_SIZE),
        clamp(y, 0, image_height - PATCH_SIZE),
    )


def crop_top_left_containing_point(
    desired_x: int,
    desired_y: int,
    center_x: int,
    center_y: int,
    image_width: int,
    image_height: int,
) -> tuple[int, int]:
    """Clamp a crop position while guaranteeing the point stays inside it."""
    min_x = max(0, center_x - PATCH_SIZE + 1)
    max_x = min(center_x, image_width - PATCH_SIZE)
    min_y = max(0, center_y - PATCH_SIZE + 1)
    max_y = min(center_y, image_height - PATCH_SIZE)

    return (
        clamp(desired_x, min_x, max_x),
        clamp(desired_y, min_y, max_y),
    )


def generate_positive_windows(
    dirty_spots: list[DirtySpot],
    image_width: int,
    image_height: int,
    rng: random.Random,
) -> list[PositiveWindow]:
    if image_width < PATCH_SIZE or image_height < PATCH_SIZE:
        return []

    positive_windows: list[PositiveWindow] = []

    for spot in dirty_spots:
        base_x, base_y = crop_top_left_centered_on_point(
            spot.center_x,
            spot.center_y,
            image_width,
            image_height,
        )
        spot_windows = [
            PositiveWindow(base_x, base_y, spot, "centered_positive"),
        ]
        seen = {(base_x, base_y)}

        attempts = 0
        max_attempts = max(20, POSITIVE_JITTER_CROPS * 10)
        while len(spot_windows) < POSITIVE_JITTER_CROPS + 1 and attempts < max_attempts:
            attempts += 1
            desired_x = base_x + rng.randint(-POSITIVE_JITTER_RADIUS, POSITIVE_JITTER_RADIUS)
            desired_y = base_y + rng.randint(-POSITIVE_JITTER_RADIUS, POSITIVE_JITTER_RADIUS)
            jitter_x, jitter_y = crop_top_left_containing_point(
                desired_x,
                desired_y,
                spot.center_x,
                spot.center_y,
                image_width,
                image_height,
            )

            if (jitter_x, jitter_y) in seen:
                continue

            seen.add((jitter_x, jitter_y))
            spot_windows.append(
                PositiveWindow(jitter_x, jitter_y, spot, "jittered_positive")
            )

        positive_windows.extend(spot_windows)

    return positive_windows


def template_valid_mask(blue_mask: np.ndarray, x: int, y: int) -> np.ndarray:
    blue_patch = blue_mask[y : y + PATCH_SIZE, x : x + PATCH_SIZE]
    if ORIGINAL_MATCH_BLUE_DILATION > 0:
        kernel_size = (ORIGINAL_MATCH_BLUE_DILATION * 2) + 1
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (kernel_size, kernel_size),
        )
        blue_patch = cv2.dilate(blue_patch, kernel, iterations=1)

    valid_mask = np.where(blue_patch > 0, 0, 255).astype(np.uint8)
    valid_ratio = float(np.mean(valid_mask > 0))
    if valid_ratio < MIN_ORIGINAL_MATCH_VALID_RATIO:
        return np.full((PATCH_SIZE, PATCH_SIZE), 255, dtype=np.uint8)

    return valid_mask


def match_original_crop_to_marked_crop(
    original_image: np.ndarray,
    marked_image: np.ndarray,
    blue_mask: np.ndarray,
    marked_x: int,
    marked_y: int,
) -> tuple[int, int, float]:
    """Find the original-image crop that best matches one marked-image crop."""
    height, width = original_image.shape[:2]
    search_left = max(0, marked_x - ORIGINAL_MATCH_SEARCH_RADIUS)
    search_top = max(0, marked_y - ORIGINAL_MATCH_SEARCH_RADIUS)
    search_right = min(width, marked_x + PATCH_SIZE + ORIGINAL_MATCH_SEARCH_RADIUS)
    search_bottom = min(height, marked_y + PATCH_SIZE + ORIGINAL_MATCH_SEARCH_RADIUS)

    search_width = search_right - search_left
    search_height = search_bottom - search_top
    if search_width < PATCH_SIZE or search_height < PATCH_SIZE:
        return marked_x, marked_y, 0.0

    marked_gray = cv2.cvtColor(marked_image, cv2.COLOR_BGR2GRAY)
    original_gray = cv2.cvtColor(original_image, cv2.COLOR_BGR2GRAY)
    template = marked_gray[marked_y : marked_y + PATCH_SIZE, marked_x : marked_x + PATCH_SIZE]
    search_area = original_gray[search_top:search_bottom, search_left:search_right]
    valid_mask = template_valid_mask(blue_mask, marked_x, marked_y)

    try:
        result = cv2.matchTemplate(
            search_area,
            template,
            cv2.TM_CCORR_NORMED,
            mask=valid_mask,
        )
    except cv2.error:
        result = cv2.matchTemplate(search_area, template, cv2.TM_CCORR_NORMED)

    result = np.nan_to_num(result, nan=-1.0, posinf=-1.0, neginf=-1.0)
    _, max_score, _, max_location = cv2.minMaxLoc(result)
    original_x = search_left + int(max_location[0])
    original_y = search_top + int(max_location[1])

    return original_x, original_y, float(max_score)


def match_positive_windows_to_original(
    original_image: np.ndarray,
    marked_image: np.ndarray,
    blue_mask: np.ndarray,
    positive_windows: list[PositiveWindow],
) -> list[MatchedPositiveWindow]:
    matched_windows: list[MatchedPositiveWindow] = []
    for window in positive_windows:
        original_x, original_y, match_score = match_original_crop_to_marked_crop(
            original_image,
            marked_image,
            blue_mask,
            window.x,
            window.y,
        )
        matched_windows.append(
            MatchedPositiveWindow(
                marked_x=window.x,
                marked_y=window.y,
                original_x=original_x,
                original_y=original_y,
                dirty_spot=window.dirty_spot,
                generation_method=window.generation_method,
                match_score=match_score,
            )
        )

    return matched_windows


def axis_coverage_positions(start: int, end: int) -> list[int]:
    """Choose positions that cover a valid interval, including its far edge."""
    if end < start:
        return []

    positions = [start]
    cursor = start + COVERAGE_STEP
    while cursor < end:
        positions.append(cursor)
        cursor += COVERAGE_STEP

    if end - positions[-1] >= MIN_EDGE_SHIFT:
        positions.append(end)

    return positions


def add_nearest_valid_position(
    selected: list[tuple[int, int]],
    seen: set[tuple[int, int]],
    component_coords: np.ndarray,
    desired_x: int,
    desired_y: int,
) -> None:
    """Add the nearest valid top-left point inside one connected clean region."""
    if component_coords.size == 0:
        return

    dy = component_coords[:, 0] - desired_y
    dx = component_coords[:, 1] - desired_x
    nearest_index = int(np.argmin((dy * dy) + (dx * dx)))
    y = int(component_coords[nearest_index, 0])
    x = int(component_coords[nearest_index, 1])

    if (x, y) not in seen:
        selected.append((x, y))
        seen.add((x, y))


def find_valid_clean_windows(
    original_image: np.ndarray,
    exclusion_mask: np.ndarray,
) -> list[tuple[int, int]]:
    height, width = original_image.shape[:2]

    if height < PATCH_SIZE or width < PATCH_SIZE:
        return []

    forbidden_pixels = (exclusion_mask > 0).astype(np.uint8)
    mask_clear = window_sum_map(forbidden_pixels) == 0
    valid_top_left = mask_clear & content_ok_map(original_image)

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        valid_top_left.astype(np.uint8),
        connectivity=8,
    )

    selected_windows: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    for label in range(1, component_count):
        left = int(stats[label, cv2.CC_STAT_LEFT])
        top = int(stats[label, cv2.CC_STAT_TOP])
        component_width = int(stats[label, cv2.CC_STAT_WIDTH])
        component_height = int(stats[label, cv2.CC_STAT_HEIGHT])

        right = left + component_width - 1
        bottom = top + component_height - 1
        x_positions = axis_coverage_positions(left, right)
        y_positions = axis_coverage_positions(top, bottom)
        component_coords = np.argwhere(labels == label)

        for y in y_positions:
            for x in x_positions:
                if valid_top_left[y, x]:
                    if (x, y) not in seen:
                        selected_windows.append((x, y))
                        seen.add((x, y))
                else:
                    add_nearest_valid_position(
                        selected_windows,
                        seen,
                        component_coords,
                        x,
                        y,
                    )

    return sorted(selected_windows, key=lambda point: (point[1], point[0]))


def save_debug_outputs(
    source_stem: str,
    marked_image: np.ndarray,
    original_image: np.ndarray,
    blue_mask: np.ndarray,
    exclusion_mask: np.ndarray,
    dirty_spots: list[DirtySpot],
    clean_windows: list[tuple[int, int]],
    positive_windows: list[MatchedPositiveWindow],
    debug_dir: Path,
) -> None:
    cv2.imwrite(str(debug_dir / f"{source_stem}_blue_mask.png"), blue_mask)
    cv2.imwrite(str(debug_dir / f"{source_stem}_exclusion_mask.png"), exclusion_mask)

    dirty_preview = marked_image.copy()
    for spot in dirty_spots:
        top_left = (spot.bbox_x, spot.bbox_y)
        bottom_right = (
            spot.bbox_x + spot.bbox_width - 1,
            spot.bbox_y + spot.bbox_height - 1,
        )
        center = (spot.center_x, spot.center_y)
        cv2.rectangle(dirty_preview, top_left, bottom_right, (0, 255, 255), 2)
        cv2.drawMarker(
            dirty_preview,
            center,
            (0, 0, 255),
            markerType=cv2.MARKER_CROSS,
            markerSize=18,
            thickness=2,
        )
        cv2.putText(
            dirty_preview,
            str(spot.spot_id),
            (spot.center_x + 6, spot.center_y - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 255),
            2,
            cv2.LINE_AA,
        )
    cv2.imwrite(str(debug_dir / f"{source_stem}_dirty_spots_preview.jpg"), dirty_preview)

    positive_preview = original_image.copy()
    for window in positive_windows:
        color = (0, 255, 255)
        if window.generation_method == "centered_positive":
            color = (0, 0, 255)
        cv2.rectangle(
            positive_preview,
            (window.original_x, window.original_y),
            (window.original_x + PATCH_SIZE - 1, window.original_y + PATCH_SIZE - 1),
            color,
            2,
        )
        estimated_original_center_x = (
            window.dirty_spot.center_x + window.original_x - window.marked_x
        )
        estimated_original_center_y = (
            window.dirty_spot.center_y + window.original_y - window.marked_y
        )
        cv2.drawMarker(
            positive_preview,
            (estimated_original_center_x, estimated_original_center_y),
            (255, 0, 0),
            markerType=cv2.MARKER_CROSS,
            markerSize=16,
            thickness=2,
        )
    cv2.imwrite(
        str(debug_dir / f"{source_stem}_positive_crops_preview.jpg"),
        positive_preview,
    )

    allowed_preview = original_image.copy()
    excluded = exclusion_mask > 0
    allowed_preview[excluded] = (0, 0, 255)
    for x, y in clean_windows:
        cv2.rectangle(
            allowed_preview,
            (x, y),
            (x + PATCH_SIZE - 1, y + PATCH_SIZE - 1),
            (0, 255, 0),
            2,
        )
    blended = cv2.addWeighted(original_image, 0.65, allowed_preview, 0.35, 0)
    cv2.imwrite(str(debug_dir / f"{source_stem}_allowed_preview.jpg"), blended)


def save_patch(
    original_image: np.ndarray,
    x: int,
    y: int,
    output_path: Path,
) -> None:
    patch = original_image[y : y + PATCH_SIZE, x : x + PATCH_SIZE]
    cv2.imwrite(str(output_path), patch, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])


def metadata_row(
    source_id: str,
    source_image: str,
    marked_image: str,
    output_file: str,
    label: str,
    x: int,
    y: int,
    source_width: int,
    source_height: int,
    generation_method: str,
    dirty_spot: DirtySpot | None = None,
    marked_x: int | str = "",
    marked_y: int | str = "",
    original_x: int | str = "",
    original_y: int | str = "",
    original_match_score: float | str = "",
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "source_image": source_image,
        "marked_image": marked_image,
        "output_file": output_file,
        "label": label,
        "x": x,
        "y": y,
        "width": PATCH_SIZE,
        "height": PATCH_SIZE,
        "patch_size": PATCH_SIZE,
        "source_width": source_width,
        "source_height": source_height,
        "dirty_spot_id": "" if dirty_spot is None else dirty_spot.spot_id,
        "dirty_center_x": "" if dirty_spot is None else dirty_spot.center_x,
        "dirty_center_y": "" if dirty_spot is None else dirty_spot.center_y,
        "blue_component_area": "" if dirty_spot is None else dirty_spot.area,
        "generation_method": generation_method,
        "marked_x": marked_x,
        "marked_y": marked_y,
        "original_x": original_x,
        "original_y": original_y,
        "original_match_score": original_match_score,
    }


def main() -> None:
    raw_dir = resolve_project_path(RAW_DIR)
    output_dir = resolve_project_path(OUTPUT_DIR)
    clean_dir = output_dir / "clean_negative"
    dirty_dir = output_dir / "dirty_positive"
    debug_dir = output_dir / "debug_masks"
    metadata_path = output_dir / "metadata.csv"
    rng = random.Random(RANDOM_SEED)

    if not raw_dir.exists():
        raise FileNotFoundError(f"Raw image directory not found: {raw_dir}")

    clean_dir.mkdir(parents=True, exist_ok=True)
    dirty_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    if CLEAR_OUTPUT_DIRS:
        clear_generated_outputs(clean_dir, dirty_dir, debug_dir)

    marked_paths = sorted(raw_dir.glob("*m.jpg"), key=natural_sort_key)
    if not marked_paths:
        print(f"No marked images found in {raw_dir}")
        return

    rows: list[dict[str, object]] = []
    total_clean_saved = 0
    total_dirty_saved = 0
    total_dirty_mask_saved = 0
    total_dirty_spots = 0

    print(f"Raw directory: {raw_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Found {len(marked_paths)} marked images")

    for marked_path in marked_paths:
        print(f"\nProcessing {marked_path.name}")
        original_path = original_for_marked(marked_path)

        if not original_path.exists():
            print(f"  WARNING: original image pair is missing: {original_path.name}")
            continue

        marked_image = read_image(marked_path)
        original_image = read_image(original_path)
        if marked_image is None or original_image is None:
            continue

        if marked_image.shape[:2] != original_image.shape[:2]:
            print(
                "  WARNING: size mismatch between original and marked image; skipping pair: "
                f"{original_path.name}={original_image.shape[1]}x{original_image.shape[0]}, "
                f"{marked_path.name}={marked_image.shape[1]}x{marked_image.shape[0]}"
            )
            continue

        source_height, source_width = original_image.shape[:2]
        source_id = original_path.stem
        blue_mask = detect_blue_mask(marked_image)
        inpainted_marked_image = remove_blue_marks(marked_image, blue_mask)
        registered_original_image = original_image
        homography_marked_to_original: np.ndarray | None = None
        homography_inliers = 0
        homography_matches = 0
        shifted_registered_windows = 0
        effective_dirty_crop_source = DIRTY_CROP_SOURCE
        if DIRTY_CROP_SOURCE == "registered_original":
            homography_marked_to_original, homography_inliers, homography_matches = (
                estimate_marked_to_original_homography(
                    marked_image,
                    original_image,
                    blue_mask,
                )
            )
            if homography_marked_to_original is None:
                effective_dirty_crop_source = "inpainted_marked"
                print(
                    "  WARNING: homography registration failed; "
                    "falling back to inpainted marked crops"
                )
            else:
                registered_original_image = warp_original_to_marked_frame(
                    original_image,
                    marked_image,
                    homography_marked_to_original,
                )
                print(
                    "  Homography registration: "
                    f"inliers={homography_inliers}/{homography_matches}"
                )

        exclusion_mask = create_exclusion_mask(blue_mask)
        dirty_spots = detect_dirty_spots(blue_mask)
        total_dirty_spots += len(dirty_spots)
        print(f"  Detected dirty spots: {len(dirty_spots)}")

        clean_windows: list[tuple[int, int]] = []
        if GENERATE_CLEAN_NEGATIVE:
            clean_windows = find_valid_clean_windows(original_image, exclusion_mask)

        positive_windows: list[PositiveWindow] = []
        if GENERATE_DIRTY_POSITIVE:
            positive_windows = generate_positive_windows(
                dirty_spots,
                source_width,
                source_height,
                rng,
            )
            if (
                effective_dirty_crop_source == "registered_original"
                and homography_marked_to_original is not None
            ):
                positive_windows, shifted_registered_windows = (
                    shift_positive_windows_inside_registered_original(
                        positive_windows,
                        homography_marked_to_original,
                        source_width,
                        source_height,
                    )
                )
        if effective_dirty_crop_source == "matched_original":
            matched_positive_windows = match_positive_windows_to_original(
                original_image,
                marked_image,
                blue_mask,
                positive_windows,
            )
        else:
            matched_positive_windows = [
                MatchedPositiveWindow(
                    marked_x=window.x,
                    marked_y=window.y,
                    original_x=window.x,
                    original_y=window.y,
                    dirty_spot=window.dirty_spot,
                    generation_method=window.generation_method,
                    match_score=1.0,
                )
                for window in positive_windows
            ]

        save_debug_outputs(
            source_id,
            marked_image,
            original_image,
            blue_mask,
            exclusion_mask,
            dirty_spots,
            clean_windows,
            matched_positive_windows,
            debug_dir,
        )

        clean_saved_for_image = 0
        for crop_index, (x, y) in enumerate(clean_windows, start=1):
            filename = f"clean_{source_id}_{crop_index}.jpg"
            output_path = clean_dir / filename
            save_patch(original_image, x, y, output_path)
            rows.append(
                metadata_row(
                    source_id=source_id,
                    source_image=original_path.name,
                    marked_image=marked_path.name,
                    output_file=f"clean_negative/{filename}",
                    label="clean_negative",
                    x=x,
                    y=y,
                    source_width=source_width,
                    source_height=source_height,
                    generation_method="sliding_window_clean",
                )
            )
            clean_saved_for_image += 1

        dirty_saved_for_image = 0
        dirty_mask_saved_for_image = 0
        match_scores: list[float] = []
        for crop_index, window in enumerate(matched_positive_windows, start=1):
            spot = window.dirty_spot
            filename = f"dirty_{source_id}_{crop_index}.jpg"
            mask_filename = f"dirty_{source_id}_{crop_index}_mask.jpg"
            output_path = dirty_dir / filename
            mask_output_path = dirty_dir / mask_filename
            if effective_dirty_crop_source == "matched_original":
                save_patch(original_image, window.original_x, window.original_y, output_path)
                metadata_x = window.original_x
                metadata_y = window.original_y
                metadata_original_x: int | str = window.original_x
                metadata_original_y: int | str = window.original_y
                metadata_match_score: float | str = f"{window.match_score:.6f}"
            elif effective_dirty_crop_source == "registered_original":
                save_patch(
                    registered_original_image,
                    window.marked_x,
                    window.marked_y,
                    output_path,
                )
                metadata_x = window.marked_x
                metadata_y = window.marked_y
                metadata_original_x = "registered"
                metadata_original_y = "registered"
                metadata_match_score = (
                    f"homography_inliers={homography_inliers}/{homography_matches}"
                )
            else:
                save_patch(
                    inpainted_marked_image,
                    window.marked_x,
                    window.marked_y,
                    output_path,
                )
                metadata_x = window.marked_x
                metadata_y = window.marked_y
                metadata_original_x = ""
                metadata_original_y = ""
                metadata_match_score = DIRTY_CROP_SOURCE

            save_patch(marked_image, window.marked_x, window.marked_y, mask_output_path)
            rows.append(
                metadata_row(
                    source_id=source_id,
                    source_image=original_path.name,
                    marked_image=marked_path.name,
                    output_file=f"dirty_positive/{filename}",
                    label="dirty_positive",
                    x=metadata_x,
                    y=metadata_y,
                    source_width=source_width,
                    source_height=source_height,
                    dirty_spot=spot,
                    generation_method=window.generation_method,
                    marked_x=window.marked_x,
                    marked_y=window.marked_y,
                    original_x=metadata_original_x,
                    original_y=metadata_original_y,
                    original_match_score=metadata_match_score,
                )
            )
            dirty_saved_for_image += 1
            dirty_mask_saved_for_image += 1
            match_scores.append(window.match_score)

        total_clean_saved += clean_saved_for_image
        total_dirty_saved += dirty_saved_for_image
        total_dirty_mask_saved += dirty_mask_saved_for_image
        print(f"  Clean crops saved: {clean_saved_for_image}")
        print(f"  Dirty crops saved: {dirty_saved_for_image}")
        print(f"  Dirty mask crops saved: {dirty_mask_saved_for_image}")
        if effective_dirty_crop_source == "matched_original" and match_scores:
            print(
                "  Original match score: "
                f"min={min(match_scores):.3f}, avg={sum(match_scores) / len(match_scores):.3f}"
            )
        elif dirty_saved_for_image > 0:
            print(f"  Dirty crop source: {effective_dirty_crop_source}")
            if effective_dirty_crop_source == "registered_original":
                print(f"  Shifted edge dirty windows: {shifted_registered_windows}")

    with metadata_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=METADATA_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print("\nDone.")
    print(f"Detected dirty spots: {total_dirty_spots}")
    print(f"Clean crops saved: {total_clean_saved}")
    print(f"Dirty crops saved: {total_dirty_saved}")
    print(f"Dirty mask crops saved: {total_dirty_mask_saved}")
    if total_dirty_saved > 0:
        print(f"Clean/dirty ratio: {total_clean_saved / total_dirty_saved:.2f}:1")
    print(f"Metadata written to: {metadata_path}")


if __name__ == "__main__":
    configure_from_args(parse_args())
    main()
