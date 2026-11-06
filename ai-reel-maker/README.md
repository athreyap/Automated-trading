# AI Reel Maker

A phone-friendly, manual-trigger reel creator with Google Photos Picker integration and device-upload fallback.

## First release
- Streamlit web interface.
- Google Photos Picker OAuth; the user explicitly selects media.
- Upload photos and videos from a phone or computer.
- OpenCV visual quality scoring to select a sharper, better-exposed moment from each video.
- Automatic vertical 9:16 conversion and clip assembly with FFmpeg.
- Optional user-supplied music.
- MP4 preview and download.

## Current limitations
The current release uses open-source computer-vision heuristics (OpenCV) for visual quality scoring. It is not a semantic AI editor: it does not understand scene meaning, identify a travel storyline, detect music beats, generate speech subtitles, or perform face-aware reframing. It preserves the user's selected media order and selects a visually stronger contiguous moment within each video.

## Run locally
1. Install Python 3.11 and FFmpeg.
2. Install dependencies with pip install -r requirements.txt.
3. Run streamlit run app.py from this directory.

## Deploy
Deploy this directory as a Streamlit Community Cloud app with main file path ai-reel-maker/app.py. Configure Google OAuth values in Streamlit Secrets using SETUP.md.

## Privacy
Google Photos access is selection-based through the Picker API, not unrestricted library access. Picker media URLs are temporary, so selected media is downloaded immediately. Cloud runtime storage is ephemeral; download the MP4 after rendering. Never commit OAuth secrets or private media.
