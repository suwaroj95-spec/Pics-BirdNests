# Blue Marker Policy Proposal

This report is evidence only. It does not finalize marker-size, radius, or merge-distance policy.

## Observed Distributions

- Marker area: min 320.0, median 848.0, p95 1804.8, max 4028.0 px.
- Equivalent radius: min 10.0925, median 16.4294, p95 23.968, max 35.8072 px.
- Enclosing radius: min 14.5389, median 35.7824, p95 70.6373, max 156.6047 px.
- Nearest-neighbor distance: min 40.2526, median 102.6981, p95 249.0313, max 479.6921 px.
- Spot count per image: min 13.0, median 24.0, p95 39.6, max 41.0.

## Minimum-size Threshold Options

- Conservative: keep current crop-pipeline minimum area 20 px.
- Balanced: consider p05 marker area around 474.55 px after reviewer spot-check.
- Strict: consider p25 marker area around 649.0 px if tiny components are often noise.

## Circle-radius Rule Options

- Use equivalent radius median around 16.4294 px for compact point circles.
- Use enclosing radius median around 35.7824 px for visible annotation circles.
- Use p75 enclosing radius around 49.0563 px when previews must fully cover larger marks.

## Merge-distance Evidence Options

- No automatic merge in this phase; treat each connected component as one preliminary spot.
- Review pairs below p05 nearest-neighbor distance around 50.7291 px as possible accidental splits.
- Use a candidate merge-distance near p25 nearest-neighbor distance around 78.4527 px only after human validation.

## Outlier Images To Review

- High spot count images: 2
- Large marker images: 10, 11, 12, 14, 15, 5, 7, 8, 9
- Close marker images: 12, 2, 3, 4, 5

## Business Risk Note

False Accept is the highest business risk, so any future automatic merge or minimum-size threshold should be validated against missed dirty spots before use.
