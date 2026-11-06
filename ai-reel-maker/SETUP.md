# Deployment and Google Photos setup

## 1. Deploy from the existing repository
1. Open https://share.streamlit.io/.
2. Create a Streamlit app from GitHub repository athreyap/Automated-trading.
3. Select branch main.
4. Set the main file path to ai-reel-maker/app.py.
5. Deploy and copy the resulting Streamlit app URL.

Do not create another GitHub repository. This app lives in its own folder in the existing Automated-trading repository.

## 2. Configure Google Photos Picker
1. Open https://console.cloud.google.com/ and create or select a Google Cloud project.
2. Enable Google Photos Picker API.
3. Configure the OAuth consent screen. For personal testing, add your Google account as a test user.
4. Create an OAuth Client ID with application type Web application.
5. Add the exact Streamlit app URL as an authorized redirect URI, without a trailing slash.
6. Copy the client ID and client secret.
7. In Streamlit Community Cloud, open app Settings → Secrets and add:

    [google]
    client_id = "YOUR_CLIENT_ID"
    client_secret = "YOUR_CLIENT_SECRET"
    redirect_uri = "https://YOUR-APP.streamlit.app"

8. Restart the app and connect Google Photos.

The application requests only the Google Photos Picker scope: photospicker.mediaitems.readonly. The user selects which photos/videos to share. It does not silently browse the entire library.

## 3. Create a reel
1. Open the deployed app on your phone.
2. Connect Google Photos.
3. Create a selection and open the Google Photos Picker.
4. Select the footage, return to the app, retrieve the selection, and download the selected media.
5. Or upload media directly from the device.
6. Set target duration, clip lengths, and optional music.
7. Press Create my reel, preview the result, and download the MP4.

## 4. Output profile
- 1080 × 1920 pixels (9:16)
- 30 frames per second
- H.264 video
- AAC audio when a music track is supplied
- MP4 container

## 5. Free-tier caveats
Streamlit Community Cloud is a limited free host and may sleep when inactive. Runtime files are temporary and large video renders can hit CPU, memory, or execution limits. This first release deliberately avoids loading large model weights on the cloud host.

## 6. Planned AI milestones
- Visual quality scoring and scene-change detection.
- Optional lightweight open-source scene classification.
- Whisper speech transcription and subtitle burn-in.
- Music beat detection and beat-aligned cut suggestions.
- Subject-aware reframing instead of center crop.

These are future milestones, not features of the first release.
