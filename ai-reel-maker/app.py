import tempfile
from pathlib import Path
import streamlit as st

from reelmaker.google_photos import GooglePhotosPicker
from reelmaker.render import render_reel

st.set_page_config(page_title="AI Reel Maker", page_icon="🎬", layout="wide")
st.title("🎬 AI Reel Maker")
st.caption("Manual reel creation · Google Photos Picker · Instagram-ready MP4")

with st.sidebar:
    st.header("Reel settings")
    duration = st.slider("Target duration (seconds)", 10, 60, 30, 5)
    clip_seconds = st.slider("Seconds per video clip", 2, 8, 4)
    image_seconds = st.slider("Seconds per photo", 1, 5, 2)
    music = st.file_uploader("Optional music (MP3/WAV/M4A)", type=["mp3", "wav", "m4a", "aac"])
    st.caption("Output: 1080 × 1920 · 30 fps · H.264/AAC")

st.subheader("1. Add your footage")
photos_tab, upload_tab = st.tabs(["Google Photos", "Upload from device"])
media_paths = []

with photos_tab:
    st.write("Google Photos access is selection-based. You choose which items to share through Google's Picker.")
    cfg = st.secrets.get("google", {}) if hasattr(st, "secrets") else {}
    configured = all(cfg.get(k) for k in ("client_id", "client_secret", "redirect_uri"))

    if not configured:
        st.info("Google Photos is not configured. Follow SETUP.md and add OAuth values in Streamlit app Secrets. You can use device upload meanwhile.")
    else:
        picker = GooglePhotosPicker(cfg)
        st.session_state.setdefault("google_credentials", None)
        st.session_state.setdefault("google_picker_session", None)
        st.session_state.setdefault("google_selected_items", [])
        st.session_state.setdefault("google_download_paths", [])

        if "code" in st.query_params and st.session_state.get("google_oauth_state"):
            try:
                creds = picker.exchange_code(st.query_params["code"], st.session_state.google_oauth_state)
                st.session_state.google_credentials = creds
                st.query_params.clear()
                st.success("Google Photos connected for this browser session.")
            except Exception as exc:
                st.error(f"Google sign-in failed: {exc}")

        if st.session_state.google_credentials is None:
            auth_url, state = picker.authorization_url()
            st.session_state.google_oauth_state = state
            st.link_button("Connect Google Photos", auth_url, use_container_width=True)
        else:
            if st.button("Create Google Photos selection"):
                try:
                    st.session_state.google_picker_session = picker.create_session(st.session_state.google_credentials)
                except Exception as exc:
                    st.error(f"Could not create picker session: {exc}")

            session = st.session_state.google_picker_session
            if session:
                st.link_button("Open Google Photos Picker", session["pickerUri"], use_container_width=True)
                if st.button("I've finished selecting — retrieve media"):
                    try:
                        st.session_state.google_selected_items = picker.get_selected_items(
                            st.session_state.google_credentials, session["id"]
                        )
                        st.success(f"Selected {len(st.session_state.google_selected_items)} items.")
                    except Exception as exc:
                        st.error(f"Could not retrieve selection: {exc}")

            selected = st.session_state.google_selected_items
            if selected and st.button("Download selected media"):
                try:
                    st.session_state.google_download_paths = picker.download_items(
                        st.session_state.google_credentials, selected
                    )
                    st.success(f"Downloaded {len(st.session_state.google_download_paths)} items.")
                except Exception as exc:
                    st.error(f"Download failed: {exc}")

            media_paths.extend(st.session_state.google_download_paths)

with upload_tab:
    uploads = st.file_uploader(
        "Choose photos and videos",
        type=["jpg", "jpeg", "png", "webp", "mp4", "mov", "m4v", "webm"],
        accept_multiple_files=True,
    )
    if uploads:
        upload_dir = Path(tempfile.gettempdir()) / "ai_reel_maker_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        for uploaded in uploads:
            safe_name = Path(uploaded.name).name
            target = upload_dir / safe_name
            target.write_bytes(uploaded.getbuffer())
            media_paths.append(str(target))
        st.success(f"{len(uploads)} files ready.")

media_paths = list(dict.fromkeys(media_paths))
if media_paths:
    st.subheader("2. Review and create")
    st.write(f"{len(media_paths)} media items ready.")
    with st.expander("Selected file order", expanded=False):
        for item in media_paths:
            st.caption(Path(item).name)

    st.warning(
        "This first cloud release performs automatic vertical framing and clip assembly in selection order. "
        "Semantic scene understanding, face-aware crops, beat detection and speech subtitles are not yet enabled."
    )
    if st.button("✨ Create my reel", type="primary", use_container_width=True):
        try:
            output_dir = Path(tempfile.gettempdir()) / "ai_reel_maker_output"
            output_dir.mkdir(parents=True, exist_ok=True)
            music_path = None
            if music:
                music_path = output_dir / f"music_{Path(music.name).name}"
                music_path.write_bytes(music.getbuffer())

            output_path = output_dir / "instagram_reel.mp4"
            with st.spinner("Rendering your reel..."):
                report = render_reel(
                    media_paths,
                    str(output_path),
                    target_seconds=duration,
                    video_clip_seconds=clip_seconds,
                    image_seconds=image_seconds,
                    music_path=str(music_path) if music_path else None,
                )
            st.session_state.last_output = str(output_path)
            st.session_state.last_report = report
            st.success("Reel rendered successfully.")
        except Exception as exc:
            st.error(f"Rendering failed: {exc}")

last_output = st.session_state.get("last_output")
if last_output and Path(last_output).exists():
    st.subheader("3. Preview and export")
    output = Path(last_output)
    st.video(str(output))
    st.download_button(
        "Download Instagram Reel (MP4)",
        output.read_bytes(),
        file_name="instagram_reel.mp4",
        mime="video/mp4",
        use_container_width=True,
    )
    st.json(st.session_state.get("last_report", {}))

st.divider()
st.caption(
    "Cloud files are temporary. Download each finished MP4 before the app sleeps or restarts. "
    "Do not store Google OAuth secrets in source code."
)
