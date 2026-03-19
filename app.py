import re
from urllib.parse import urlparse, parse_qs

import streamlit as st
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'skip_download': True,
}

LANGUAGE_PRIORITY = ['he', 'iw', 'en', 'en-US', 'en-GB']

st.set_page_config(
    page_title='YouTube Subtitles',
    page_icon='CC',
    layout='centered',
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;600;800&display=swap');

    .stApp {
        font-family: 'Heebo', sans-serif;
    }

    .hero-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FF4BA6, #7BFF4B);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.2rem;
        line-height: 1.3;
    }

    .hero-sub {
        text-align: center;
        color: #FF4BA6;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }

    .stDownloadButton button {
        width: 100%;
        background: linear-gradient(135deg, #FF4BA6, #D63F8E) !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        padding: 0.7rem 1.5rem !important;
        transition: all 0.3s ease !important;
    }
    .stDownloadButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(255, 75, 166, 0.4) !important;
    }

    .stFormSubmitButton button {
        background: linear-gradient(135deg, #7BFF4B, #4BDB6A) !important;
        color: #000000 !important;
        border: none !important;
        border-radius: 12px !important;
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        padding: 0.7rem 2rem !important;
        transition: all 0.3s ease !important;
    }
    .stFormSubmitButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(123, 255, 75, 0.4) !important;
    }

    div[data-testid="stForm"] {
        background: #111111;
        border: 4px solid #FF4BA6;
        border-radius: 16px;
        padding: 2rem;
    }

    div[data-testid="stExpander"] {
        background: #111111;
        border: 1px solid #2A2A2A;
        border-radius: 12px;
        margin-bottom: 0.5rem;
    }

    div[data-testid="stTextInput"] input {
        border-radius: 12px !important;
        border: 1px solid #2A2A2A !important;
        background: #000000 !important;
    }
    div[data-testid="stTextInput"] input:focus {
        border-color: #7BFF4B !important;
        box-shadow: 0 0 12px rgba(123, 255, 75, 0.25) !important;
    }

    div[data-testid="stMetric"] {
        background: #111111;
        border: 1px solid #2A2A2A;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }

    div[data-testid="stAlert"] {
        border-radius: 12px;
    }

    .stProgress > div > div {
        background: linear-gradient(90deg, #FF4BA6, #7BFF4B) !important;
        border-radius: 10px;
    }

    div[data-testid="stRadio"] label span {
        color: #FAFAFA !important;
    }
</style>
""", unsafe_allow_html=True)


def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', '', name)
    name = name.strip('. ')
    return name[:150] if name else 'transcript'


def extract_video_id(url):
    parsed = urlparse(url)
    if parsed.hostname in ('youtu.be',):
        return parsed.path.lstrip('/')
    qs = parse_qs(parsed.query)
    return qs.get('v', [None])[0]


def url_type(url):
    parsed = urlparse(url)
    if not parsed.hostname:
        return 'invalid'
    qs = parse_qs(parsed.query)
    has_list = 'list' in qs
    has_video = 'v' in qs or parsed.hostname == 'youtu.be'
    if has_list and has_video:
        return 'both'
    if has_list:
        return 'playlist'
    if has_video:
        return 'video'
    return 'invalid'


def get_transcript_text(video_id):
    ytt_api = YouTubeTranscriptApi()

    try:
        transcript = ytt_api.fetch(video_id, languages=LANGUAGE_PRIORITY)
        return ' '.join(snippet.text for snippet in transcript)
    except NoTranscriptFound:
        pass
    except (TranscriptsDisabled, VideoUnavailable):
        return None
    except Exception:
        return None

    try:
        transcript_list = ytt_api.list(video_id)
        for t in transcript_list:
            fetched = t.fetch()
            return ' '.join(snippet.text for snippet in fetched)
    except Exception:
        pass

    return None


def get_video_info(url):
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title'), info.get('id')
    except Exception:
        video_id = extract_video_id(url)
        if video_id:
            return None, video_id
        return None, None


def get_playlist_info(url):
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get('title', 'playlist')
        entries = info.get('entries', [])
        videos = []
        for entry in entries:
            if entry:
                videos.append({
                    'id': entry.get('id'),
                    'title': entry.get('title'),
                    'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                })
        return title, videos


def process_single_video(url):
    title, video_id = get_video_info(url)
    if not video_id:
        st.error('Could not identify the video from the provided link.')
        return

    display_title = title or video_id

    with st.spinner(f'Extracting subtitles: {display_title}...'):
        text = get_transcript_text(video_id)

    if text:
        st.success('Subtitles extracted successfully!')

        full_text = f'--- {display_title} ---\n\n{text}\n'
        filename = sanitize_filename(display_title) + '.txt'

        st.download_button(
            label=f'Download: {filename}',
            data=full_text.encode('utf-8'),
            file_name=filename,
            mime='text/plain; charset=utf-8',
        )

        with st.expander(display_title, expanded=True):
            st.markdown(text)
    else:
        st.error(f'No subtitles found for: {display_title}')


def process_playlist(url):
    with st.spinner('Loading playlist...'):
        try:
            playlist_title, videos = get_playlist_info(url)
        except Exception as e:
            st.error(f'Error loading playlist: {e}')
            return

    total = len(videos)
    if total == 0:
        st.warning('The playlist is empty — no videos found.')
        return
    st.info(f'**{playlist_title}** — {total} videos')

    progress_bar = st.progress(0, text='Starting...')
    status_container = st.container()

    results = []
    success_count = 0
    fail_count = 0

    for i, video in enumerate(videos):
        video_id = video['id']
        display_title = video['title'] or video_id or f'Video {i + 1}'
        progress_bar.progress((i + 1) / total, text=f'[{i + 1}/{total}] {display_title}')

        if not video_id:
            results.append((display_title, None))
            fail_count += 1
            continue

        text = get_transcript_text(video_id)
        results.append((display_title, text))
        if text:
            success_count += 1
        else:
            fail_count += 1

    progress_bar.progress(1.0, text='Done!')

    with status_container:
        col1, col2 = st.columns(2)
        col1.metric('Succeeded', f'{success_count}')
        col2.metric('No subtitles', f'{fail_count}')

    file_lines = []
    for display_title, text in results:
        file_lines.append(f'\n{"=" * 60}')
        file_lines.append(display_title)
        file_lines.append(f'{"=" * 60}\n')
        if text:
            file_lines.append(text)
        else:
            file_lines.append('No subtitles found for this video.')
        file_lines.append('')

    full_text = '\n'.join(file_lines)
    filename = sanitize_filename(playlist_title) + '.txt'

    st.download_button(
        label=f'Download all subtitles: {filename}',
        data=full_text.encode('utf-8'),
        file_name=filename,
        mime='text/plain; charset=utf-8',
    )

    for display_title, text in results:
        if text:
            with st.expander(display_title):
                st.markdown(text)
        else:
            with st.expander(f'{display_title} (no subtitles)'):
                st.markdown('No subtitles found for this video.')


st.markdown('<div class="hero-title">YouTube Subtitle Extractor</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-sub">Extract auto-generated subtitles from videos and playlists — Hebrew and English</div>', unsafe_allow_html=True)

with st.form('url_form'):
    url = st.text_input('Paste a video or playlist link:', placeholder='https://www.youtube.com/watch?v=...')
    mode = st.radio(
        'What to extract?',
        ['Auto-detect', 'Single video only', 'Full playlist'],
        horizontal=True,
    )
    submitted = st.form_submit_button('Extract Subtitles', type='primary')

if submitted:
    if not url.strip():
        st.warning('Please enter a link.')
    else:
        clean_url = url.strip()
        detected = url_type(clean_url)

        if detected == 'invalid':
            st.error('The provided link is not a valid YouTube URL.')
        elif mode == 'Single video only':
            process_single_video(clean_url)
        elif mode == 'Full playlist':
            if detected in ('playlist', 'both'):
                process_playlist(clean_url)
            else:
                st.error('The provided link does not contain a playlist.')
        else:
            if detected == 'both':
                st.info('The link contains both a video and a playlist — processing the full playlist. '
                        'Select "Single video only" if you only want that one video.')
                process_playlist(clean_url)
            elif detected == 'playlist':
                process_playlist(clean_url)
            else:
                process_single_video(clean_url)
