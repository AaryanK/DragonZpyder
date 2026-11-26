# Android application resource navigation

Android resource directories are compiled by AAPT and must not contain Markdown. This guide covers each resource folder while the repository file inventory lists each resource path individually.

- [`drawable/ic_logo.xml`](drawable/ic_logo.xml): vector resource.
- [`values/dialog_themes.xml`](values/dialog_themes.xml): dialog theme resources.
- [`xml/camera_paths.xml`](xml/camera_paths.xml): FileProvider camera path declaration.
- `drawable-nodpi/brand_icon.xml`: generated native mark from `web/frontend/src/dz-mark.svg` by `android/prepare-brand.sh`; not tracked.
