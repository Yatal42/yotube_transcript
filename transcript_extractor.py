import re
import sys
from urllib.parse import urlparse, parse_qs

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


LANGUAGE_PRIORITY = ['he', 'iw', 'en', 'en-US', 'en-GB']


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


def is_playlist_url(url):
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    has_list = 'list' in qs
    has_video = 'v' in qs or parsed.hostname == 'youtu.be'
    if has_list and has_video:
        print('הקישור מכיל גם סרטון וגם פלייליסט — מעבד כפלייליסט.')
        print('(אם רצית רק את הסרטון, הסר את פרמטר ה-list מהקישור)')
        print()
    return has_list


def get_transcript_text(video_id):
    ytt_api = YouTubeTranscriptApi()

    try:
        transcript = ytt_api.fetch(video_id, languages=LANGUAGE_PRIORITY)
        return ' '.join(snippet.text for snippet in transcript)
    except NoTranscriptFound:
        pass
    except (TranscriptsDisabled, VideoUnavailable) as e:
        return None, str(e).split('!')[0]
    except Exception as e:
        return None, f'שגיאה: {type(e).__name__}'

    try:
        transcript_list = ytt_api.list(video_id)
        for t in transcript_list:
            fetched = t.fetch()
            return ' '.join(snippet.text for snippet in fetched)
    except Exception:
        pass

    return None


YDL_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'skip_download': True,
}


def get_video_info(url):
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            return info.get('title'), info.get('id')
    except Exception as e:
        video_id = extract_video_id(url)
        if video_id:
            return None, video_id
        raise ValueError(f'לא ניתן לעבד את הקישור: {url}') from e


def process_single_video(url):
    title, video_id = get_video_info(url)
    display_title = title or video_id
    print(f'מעבד: {display_title}')

    result = get_transcript_text(video_id)

    if isinstance(result, tuple):
        text, error = None, result[1]
    elif isinstance(result, str):
        text, error = result, None
    else:
        text, error = None, None

    filename = sanitize_filename(display_title) + '.txt'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f'--- {display_title} ---\n\n')
        if text:
            f.write(text + '\n')
        else:
            msg = error or 'לא נמצאו כתוביות לסרטון זה.'
            f.write(msg + '\n')
            print(f'  ⚠ {msg}')

    print(f'הקובץ נשמר: {filename}')


def process_playlist(url):
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)

    playlist_title = info.get('title', 'playlist')
    entries = [e for e in info.get('entries', []) if e]
    filename = sanitize_filename(playlist_title) + '.txt'
    total = len(entries)

    print(f'פלייליסט: {playlist_title}')
    print(f'מספר סרטונים: {total}')
    print()

    success_count = 0
    fail_count = 0

    with open(filename, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(entries, 1):
            video_id = entry.get('id')
            title = entry.get('title')

            display_title = title or video_id or f'סרטון {i}'
            print(f'[{i}/{total}] {display_title}...', end=' ', flush=True)

            f.write(f'\n{"=" * 60}\n')
            f.write(f'{display_title}\n')
            f.write(f'{"=" * 60}\n\n')

            if not video_id:
                f.write('לא ניתן לזהות את הסרטון.\n')
                fail_count += 1
                print('✗ (קישור לא תקין)')
                continue

            result = get_transcript_text(video_id)

            if isinstance(result, tuple):
                text, error = None, result[1]
            elif isinstance(result, str):
                text, error = result, None
            else:
                text, error = None, None

            if text:
                f.write(text + '\n')
                success_count += 1
                print('✓')
            else:
                msg = error or 'לא נמצאו כתוביות לסרטון זה.'
                f.write(msg + '\n')
                fail_count += 1
                print(f'✗ ({msg})')

    print()
    print(f'סיכום: {success_count} הצליחו, {fail_count} ללא כתוביות')
    print(f'הקובץ נשמר: {filename}')


def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input('הכנס קישור לסרטון או לפלייליסט ביוטיוב: ').strip()

    if not url:
        print('לא הוזן קישור.')
        return

    try:
        if is_playlist_url(url):
            process_playlist(url)
        else:
            process_single_video(url)
    except KeyboardInterrupt:
        print('\nהופסק על ידי המשתמש.')
    except Exception as e:
        print(f'שגיאה: {e}')


if __name__ == '__main__':
    main()
