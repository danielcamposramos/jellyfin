# Software stereo flattening: repair and regression evidence

This supports [Tim Eisele's Jellyfin PR #18060](https://github.com/jellyfin/jellyfin/pull/18060).
His commits and attribution are preserved.
The code-only repair branch is [stereo-18060-review](https://github.com/danielcamposramos/jellyfin/tree/stereo-18060-review).
This separate branch adds test evidence; it is not a replacement upstream pull request.
The local corrections and validation were prepared with Codex assistance under Daniel Ramos's direction.

## Changes

1. `3f1d25f6b`: merge `release-12.z` at `1c43227fc`, retaining the shared thumbnail flattening helper when resolving the conflict.
2. `b914da604`: retain the previous public `GetHwScaleFilter` and `GetSwScaleFilter` signatures through overloads, for existing compiled callers.
3. `6fa635b86`: preserve non-square sample aspect ratios when expanding half-packed views and remove `Stereo 3D` frame side data after software flattening to mono.

For example, a half-SBS or half-TB source with SAR 4:3 becomes SAR 1:1 with the original helper.
The corrected helper restores 4:3 after scaling.
All four original software filters also leave stereo frame signalling on the flattened H.264 output; the correction removes it.
Only the first spatial view is retained; this is not a generalized eye-order detection change.

## Results

| Check | Observed result |
| --- | --- |
| MediaEncoding tests, Release | 126 pass, one macOS-only skip |
| Controller tests, Release | 214 pass |
| MediaBrowser.Controller APICompat against current base | No breaking changes |
| Full solution `dotnet format --verify-no-changes` | Exit 0; zero of 2379 files needed formatting |
| Full/half SBS/TB, SAR 1:1 and 4:3 | Eight before/after cases pass |
| Independent decoded pixel check | Output contains the red first view, not the blue second view |
| Mono and packet-copy controls | Mono retains dimensions/SAR; copied stereo retains signalling |
| FFmpeg 7.1.5 and official Jellyfin FFmpeg 8.1.3-1 | Both reproduce the original defects and pass the correction |

[FFmpeg 7 results](results-ffmpeg7.json), [Jellyfin FFmpeg 8 results](results-ffmpeg8.json), [unit tests and APICompat](tests-and-abi.log).
The video checks execute real filters, encode the result, decode it and assert dimensions, SAR, pixels and side data.
The fixture consists only of generated red and blue fields.

## Reproduce the video check

Requirements: Python 3, Git and FFmpeg/ffprobe with libx264.
From the repository root:

```sh
git show 3f1d25f6b:MediaBrowser.Controller/MediaEncoding/EncodingHelper.cs \
  > validation/stereo-2026-10-19/before-EncodingHelper.cs
python3 validation/stereo-2026-10-19/validate.py
```

To select another FFmpeg installation:

```sh
python3 validation/stereo-2026-10-19/validate.py \
  --ffmpeg-dir /path/to/jellyfin-ffmpeg --label=-ffmpeg8
```

An extracted Jellyfin FFmpeg package needs its bundled `lib/` directory in `LD_LIBRARY_PATH`.
The actual package tested was `jellyfin-ffmpeg8_8.1.3-1-trixie_amd64.deb`, extracted into the test workspace, never installed on the host.
Logs, generated fixtures, probe JSON and exact commands go into `output/` or the chosen labelled output directory.

## Code checks

.NET SDK 10.0.402 on Linux x86-64:

```sh
dotnet test tests/Jellyfin.MediaEncoding.Tests/Jellyfin.MediaEncoding.Tests.csproj --configuration Release --verbosity minimal -m:4
dotnet test tests/Jellyfin.Controller.Tests/Jellyfin.Controller.Tests.csproj --configuration Release --verbosity minimal -m:4
dotnet format Jellyfin.sln --verify-no-changes
```

APICompat compared `MediaBrowser.Controller.dll` built from `1c43227fc` and `6fa635b86`, with no breaking changes.

## Scope still requiring review

The software helper and thumbnail path are covered here.
QSV, VAAPI/Vulkan, Apple, Windows, Rockchip, subtitle composition and rotation combinations were not validated by this matrix.
Hardware cropping still needs mono-output metadata checks.
Container/codec SAR conflicts, Matroska per-eye display dimensions, stream-only discovery, reverse eye-order representation and HDR rendering are separate work.
These results do not establish that every path in the original PR is ready for merge.

## Related stereo work

- [PeerTube #7816](https://github.com/Chocobozzz/PeerTube/pull/7816), merged: preserve declared packed stereo through transcodes. A deliberate mono conversion requires the opposite metadata transition.
- [mpv #18490](https://github.com/mpv-player/mpv/pull/18490), merged: stream signalling matters for detection alongside container metadata.
- [HandBrake #8100](https://github.com/HandBrake/HandBrake/pull/8100) and [UMS #6330](https://github.com/UniversalMediaServer/UniversalMediaServer/pull/6330), merged: preserve H.264 packing signalling through encode/transcode paths.
- [x265 #988](https://github.com/Multicorewareinc/x265/pull/988), merged: correct stale bytes in combined SEI messages.
- [x265 #986](https://github.com/Multicorewareinc/x265/pull/986) and [#999](https://github.com/Multicorewareinc/x265/pull/999), open: HEVC frame-packing signalling and the independently corrected field-coding restriction, tested together in a separate 48-encode matrix.
