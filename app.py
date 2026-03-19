import re
from urllib.parse import urlparse, parse_qs

import streamlit as st
from pytubefix import Playlist, YouTube
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

LANGUAGE_PRIORITY = ['he', 'iw', 'en', 'en-US', 'en-GB']

st.set_page_config(
    page_title='כתוביות יוטיוב',
    page_icon='📝',
    layout='centered',
)

st.markdown("""
<style>
    .stApp { direction: rtl; }
    .stTextInput label, .stRadio label, .stMarkdown { direction: rtl; text-align: right; }
    .stDownloadButton button { width: 100%; }
    div[data-testid="stExpander"] details summary p { direction: rtl; text-align: right; }
    div[data-testid="stExpander"] div[data-testid="stMarkdownContainer"] { direction: rtl; text-align: right; }
    .video-section { background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 12px 0; border-right: 4px solid #4CAF50; }
    .video-section-error { background: #fff3f3; border-radius: 8px; padding: 16px; margin: 12px 0; border-right: 4px solid #f44336; }
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
        yt = YouTube(url)
        return yt.title, yt.video_id
    except Exception:
        video_id = extract_video_id(url)
        if video_id:
            return None, video_id
        return None, None


def process_single_video(url):
    title, video_id = get_video_info(url)
    if not video_id:
        st.error('לא ניתן לזהות את הסרטון מהקישור שהוזן.')
        return

    display_title = title or video_id

    with st.spinner(f'מוריד כתוביות: {display_title}...'):
        text = get_transcript_text(video_id)

    if text:
        st.success(f'הכתוביות חולצו בהצלחה!')

        full_text = f'--- {display_title} ---\n\n{text}\n'
        filename = sanitize_filename(display_title) + '.txt'

        st.download_button(
            label=f'📥 הורד קובץ: {filename}',
            data=full_text.encode('utf-8'),
            file_name=filename,
            mime='text/plain; charset=utf-8',
        )

        with st.expander(f'📖 {display_title}', expanded=True):
            st.markdown(text)
    else:
        st.error(f'לא נמצאו כתוביות עבור: {display_title}')


def process_playlist(url):
    with st.spinner('טוען את הפלייליסט...'):
        try:
            playlist = Playlist(url)
            playlist_title = playlist.title or 'playlist'
            video_urls = list(playlist.video_urls)
        except Exception as e:
            st.error(f'שגיאה בטעינת הפלייליסט: {e}')
            return

    total = len(video_urls)
    if total == 0:
        st.warning('הפלייליסט ריק — לא נמצאו סרטונים.')
        return
    st.info(f'**{playlist_title}** — {total} סרטונים')

    progress_bar = st.progress(0, text='מתחיל...')
    status_container = st.container()

    results = []
    success_count = 0
    fail_count = 0

    for i, video_url in enumerate(video_urls):
        try:
            title, video_id = get_video_info(video_url)
        except Exception:
            video_id = extract_video_id(video_url)
            title = None

        display_title = title or video_id or f'סרטון {i + 1}'
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

    progress_bar.progress(1.0, text='הושלם!')

    with status_container:
        col1, col2 = st.columns(2)
        col1.metric('הצליחו', f'{success_count}')
        col2.metric('ללא כתוביות', f'{fail_count}')

    file_lines = []
    for display_title, text in results:
        file_lines.append(f'\n{"=" * 60}')
        file_lines.append(display_title)
        file_lines.append(f'{"=" * 60}\n')
        if text:
            file_lines.append(text)
        else:
            file_lines.append('לא נמצאו כתוביות לסרטון זה.')
        file_lines.append('')

    full_text = '\n'.join(file_lines)
    filename = sanitize_filename(playlist_title) + '.txt'

    st.download_button(
        label=f'📥 הורד את כל הכתוביות: {filename}',
        data=full_text.encode('utf-8'),
        file_name=filename,
        mime='text/plain; charset=utf-8',
    )

    for display_title, text in results:
        if text:
            with st.expander(f'✅ {display_title}'):
                st.markdown(text)
        else:
            with st.expander(f'❌ {display_title}'):
                st.markdown('לא נמצאו כתוביות לסרטון זה.')


st.title('📝 חילוץ כתוביות מיוטיוב')
st.markdown('הכלי מחלץ כתוביות (אוטומטיות או ידניות) מסרטונים ופלייליסטים ביוטיוב, בעברית ובאנגלית.')

with st.form('url_form'):
    url = st.text_input('הכנס קישור לסרטון או לפלייליסט:', placeholder='https://www.youtube.com/watch?v=...')
    mode = st.radio(
        'מה לחלץ?',
        ['זיהוי אוטומטי', 'סרטון בודד בלבד', 'פלייליסט שלם'],
        horizontal=True,
    )
    submitted = st.form_submit_button('חלץ כתוביות', type='primary')

if submitted:
    if not url.strip():
        st.warning('יש להזין קישור.')
    else:
        clean_url = url.strip()
        detected = url_type(clean_url)

        if detected == 'invalid':
            st.error('הקישור שהוזן אינו קישור תקין ליוטיוב.')
        elif mode == 'סרטון בודד בלבד':
            process_single_video(clean_url)
        elif mode == 'פלייליסט שלם':
            if detected in ('playlist', 'both'):
                process_playlist(clean_url)
            else:
                st.error('הקישור שהוזן אינו מכיל פלייליסט.')
        else:
            if detected == 'both':
                st.info('הקישור מכיל גם סרטון וגם פלייליסט — מעבד את הפלייליסט השלם. '
                        'אם רצית רק את הסרטון הבודד, בחר "סרטון בודד בלבד".')
                process_playlist(clean_url)
            elif detected == 'playlist':
                process_playlist(clean_url)
            else:
                process_single_video(clean_url)
