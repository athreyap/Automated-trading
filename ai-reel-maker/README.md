# AI Reel Maker

A phone-friendly, manual-trigger reel creator with Google Photos Picker integration and device-upload fallback.

## First release
- Streamlit web interface.
- Google Photos Picker OAuth; the user explicitly selects media.
- Upload photos and videos from a phone or computer.
- Automatic vertical 9:16 conversion and clip assembly with FFmpeg.
- Optional user-supplied music.
- MP4 preview and download.

## Current limitations
This first release is an automatic renderer, not yet a semantic AI editor. It follows the selected media order, takes a centered segment from each video, holds photos for the configured duration, and center-crops to vertical format. It does not yet rank scenes semantically, detect beats, generate subtitles, or perform face-aware reframing. Those capabilities are planned for later milestones and are not represented as implemented.

## Run locally
1. Install Python 3.11 and FFmpeg.
2. Install dependencies with pip install -r requirements.txt.
3. Run streamlit run app.py from this directory.

## Deploy
Deploy this directory as a Streamlit Community Cloud app with main file path ai-reel-maker/app.py. Configure Google OAuth values in Streamlit Secrets using SETUP.md.

## Privacy
Google Photos access is selection-based through the Picker API, not unrestricted library access. Picker media URLs are temporary, so selected media is downloaded immediately. Cloud runtime storage is ephemeral; download the MP4 after rendering. Never commit OAuth secrets or private media.
