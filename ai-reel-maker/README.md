# AI Reel Maker

A phone-friendly, manual-trigger reel creator with Google Photos Picker integration and device-upload fallback.

## First release
- Streamlit web interface.
- Google Photos Picker OAuth; the user explicitly selects media.
- Optional Google Photos album-name target field to label the album the user intends to select from. The user must navigate to that album in the Picker and choose its media manually.
- Upload photos and videos from a phone or computer.
- OpenCV visual quality scoring to select a sharper, better-exposed moment from each video.
- Automatic vertical 9:16 conversion and clip assembly with FFmpeg.
- Optional user-supplied music.
- MP4 preview and download.

## Google Photos album limitation
The current Google Photos Picker API exposes a user-driven media selection flow and returns the media items selected in that session. It does not provide an API to search a user's full library by album title, list all of their existing albums, or report which album a picked item belongs to. Therefore, entering an album name is a selection aid/instruction, not an automatic album query or a verified album filter. The user must open the Picker and select the intended album's items. The app does not claim that selected items belong to the entered album.

Google's Library API is now limited to app-created content for listing/searching albums and media; it is not a workaround for reading arbitrary existing user albums.

## Current editing limitations
The current release uses open-source computer-vision heuristics (OpenCV) for visual quality scoring. It is not a semantic AI editor: it does not understand scene meaning, identify a travel storyline, detect music beats, generate speech subtitles, or perform face-aware reframing. It preserves the user's selected media order and selects a visually stronger contiguous moment within each video.

## Run locally
1. Install Python 3.11 and FFmpeg.
2. Install dependencies with pip install -r requirements.txt.
3. Run streamlit run app.py from this directory.

## Deploy
Deploy this directory as a Streamlit Community Cloud app with main file path ai-reel-maker/app.py. Configure Google OAuth values in Streamlit Secrets using SETUP.md.

## Privacy
Google Photos access is selection-based through the Picker API, not unrestricted library access. Picker media URLs are temporary, so selected media is downloaded immediately. Cloud runtime storage is ephemeral; download the MP4 after rendering. Never commit OAuth secrets or private media.
