# `crop_clean_patches.py`

Generated content. Do not edit by hand.

- Purpose: Generates clean and dirty crop patches plus metadata from raw image pairs.
- Source path: `crop_clean_patches.py`
- Source link: [crop_clean_patches.py](https://github.com/suwaroj95-spec/Pics-BirdNests/blob/main/crop_clean_patches.py)
- Risk notes: `--clear-output` deletes generated crop/debug image files under the selected output directory.

## Top-Level Classes And Functions

### `parse_args`

- Kind: `function`
- Signature: `def parse_args()`
- Lines: 77-110
- Docstring: No docstring.

### `configure_from_args`

- Kind: `function`
- Signature: `def configure_from_args(args)`
- Lines: 113-146
- Docstring: No docstring.

### `DirtySpot`

- Kind: `class`
- Signature: `class DirtySpot`
- Lines: 150-158
- Docstring: No docstring.

### `PositiveWindow`

- Kind: `class`
- Signature: `class PositiveWindow`
- Lines: 162-166
- Docstring: No docstring.

### `MatchedPositiveWindow`

- Kind: `class`
- Signature: `class MatchedPositiveWindow`
- Lines: 170-177
- Docstring: No docstring.

### `natural_sort_key`

- Kind: `function`
- Signature: `def natural_sort_key(path)`
- Lines: 180-185
- Docstring: Sort 1m.jpg, 2m.jpg, ... before 10m.jpg.

### `resolve_project_path`

- Kind: `function`
- Signature: `def resolve_project_path(configured_path)`
- Lines: 188-211
- Docstring: Resolve paths whether the script is run from the project root or its parent.

### `original_for_marked`

- Kind: `function`
- Signature: `def original_for_marked(marked_path)`
- Lines: 214-219
- Docstring: Convert 15m.jpg to 15.jpg while leaving the directory unchanged.

### `read_image`

- Kind: `function`
- Signature: `def read_image(path)`
- Lines: 222-226
- Docstring: No docstring.

### `clear_generated_outputs`

- Kind: `function`
- Signature: `def clear_generated_outputs(clean_dir, dirty_dir, debug_dir)`
- Lines: 229-256
- Docstring: Remove previous generated crop/debug files so reruns match metadata exactly.

### `detect_blue_mask`

- Kind: `function`
- Signature: `def detect_blue_mask(marked_image)`
- Lines: 259-272
- Docstring: Detect blue annotation pixels from the marked image.

### `create_exclusion_mask`

- Kind: `function`
- Signature: `def create_exclusion_mask(blue_mask)`
- Lines: 275-285
- Docstring: Dilate detected blue marks into the clean-crop exclusion region.

### `dilate_blue_mask_for_inpainting`

- Kind: `function`
- Signature: `def dilate_blue_mask_for_inpainting(blue_mask)`
- Lines: 288-297
- Docstring: No docstring.

### `remove_blue_marks`

- Kind: `function`
- Signature: `def remove_blue_marks(marked_image, blue_mask)`
- Lines: 300-308
- Docstring: Create an unmarked-looking image from the marked image.

### `feature_detection_mask`

- Kind: `function`
- Signature: `def feature_detection_mask(blue_mask)`
- Lines: 311-321
- Docstring: No docstring.

### `estimate_marked_to_original_homography`

- Kind: `function`
- Signature: `def estimate_marked_to_original_homography(marked_image, original_image, blue_mask)`
- Lines: 324-386
- Docstring: Estimate a projective transform from marked-image pixels to original pixels.

### `warp_original_to_marked_frame`

- Kind: `function`
- Signature: `def warp_original_to_marked_frame(original_image, marked_image, homography_marked_to_original)`
- Lines: 389-402
- Docstring: Warp the unmarked original image into the marked image coordinate frame.

### `registered_window_inside_original`

- Kind: `function`
- Signature: `def registered_window_inside_original(homography_marked_to_original, x, y, original_width, original_height)`
- Lines: 405-428
- Docstring: No docstring.

### `shift_window_inside_registered_original`

- Kind: `function`
- Signature: `def shift_window_inside_registered_original(window, homography_marked_to_original, image_width, image_height)`
- Lines: 431-487
- Docstring: Shift a marked-frame crop so its registered original crop has real pixels.

### `shift_positive_windows_inside_registered_original`

- Kind: `function`
- Signature: `def shift_positive_windows_inside_registered_original(positive_windows, homography_marked_to_original, image_width, image_height)`
- Lines: 490-510
- Docstring: No docstring.

### `has_enough_content`

- Kind: `function`
- Signature: `def has_enough_content(patch)`
- Lines: 513-525
- Docstring: Reject mostly white or very low-texture background patches.

### `window_sum_map`

- Kind: `function`
- Signature: `def window_sum_map(binary_map)`
- Lines: 528-536
- Docstring: Return the number of non-zero pixels in every PATCH_SIZE window.

### `content_ok_map`

- Kind: `function`
- Signature: `def content_ok_map(original_image)`
- Lines: 539-551
- Docstring: Calculate the content filter for every possible crop top-left position.

### `detect_dirty_spots`

- Kind: `function`
- Signature: `def detect_dirty_spots(blue_mask)`
- Lines: 554-586
- Docstring: Find connected blue-mark components and estimate dirty-spot centers.

### `clamp`

- Kind: `function`
- Signature: `def clamp(value, lower, upper)`
- Lines: 589-590
- Docstring: No docstring.

### `crop_top_left_centered_on_point`

- Kind: `function`
- Signature: `def crop_top_left_centered_on_point(center_x, center_y, image_width, image_height)`
- Lines: 593-604
- Docstring: No docstring.

### `crop_top_left_containing_point`

- Kind: `function`
- Signature: `def crop_top_left_containing_point(desired_x, desired_y, center_x, center_y, image_width, image_height)`
- Lines: 607-624
- Docstring: Clamp a crop position while guaranteeing the point stays inside it.

### `generate_positive_windows`

- Kind: `function`
- Signature: `def generate_positive_windows(dirty_spots, image_width, image_height, rng)`
- Lines: 627-675
- Docstring: No docstring.

### `template_valid_mask`

- Kind: `function`
- Signature: `def template_valid_mask(blue_mask, x, y)`
- Lines: 678-693
- Docstring: No docstring.

### `match_original_crop_to_marked_crop`

- Kind: `function`
- Signature: `def match_original_crop_to_marked_crop(original_image, marked_image, blue_mask, marked_x, marked_y)`
- Lines: 696-736
- Docstring: Find the original-image crop that best matches one marked-image crop.

### `match_positive_windows_to_original`

- Kind: `function`
- Signature: `def match_positive_windows_to_original(original_image, marked_image, blue_mask, positive_windows)`
- Lines: 739-766
- Docstring: No docstring.

### `axis_coverage_positions`

- Kind: `function`
- Signature: `def axis_coverage_positions(start, end)`
- Lines: 769-783
- Docstring: Choose positions that cover a valid interval, including its far edge.

### `add_nearest_valid_position`

- Kind: `function`
- Signature: `def add_nearest_valid_position(selected, seen, component_coords, desired_x, desired_y)`
- Lines: 786-805
- Docstring: Add the nearest valid top-left point inside one connected clean region.

### `find_valid_clean_windows`

- Kind: `function`
- Signature: `def find_valid_clean_windows(original_image, exclusion_mask)`
- Lines: 808-856
- Docstring: No docstring.

### `save_debug_outputs`

- Kind: `function`
- Signature: `def save_debug_outputs(source_stem, marked_image, original_image, blue_mask, exclusion_mask, dirty_spots, clean_windows, positive_windows, debug_dir)`
- Lines: 859-945
- Docstring: No docstring.

### `save_patch`

- Kind: `function`
- Signature: `def save_patch(original_image, x, y, output_path)`
- Lines: 948-955
- Docstring: No docstring.

### `metadata_row`

- Kind: `function`
- Signature: `def metadata_row(source_id, source_image, marked_image, output_file, label, x, y, source_width, source_height, generation_method, dirty_spot, marked_x, marked_y, original_x, original_y, original_match_score)`
- Lines: 958-999
- Docstring: No docstring.

### `main`

- Kind: `function`
- Signature: `def main()`
- Lines: 1002-1272
- Docstring: No docstring.
