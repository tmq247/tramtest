import asyncio
import os
import re
import json
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch  # Giữ nguyên theo môi trường của bạn

from SANKIXD.utils.database import is_on_off
from SANKIXD.utils.formatters import time_to_seconds

import glob
import random
import logging

# ========== Cookies helper ==========
def cookie_txt_file():
    folder_path = f"{os.getcwd()}/cookies"
    filename = f"{os.getcwd()}/cookies/logs.csv"
    txt_files = glob.glob(os.path.join(folder_path, "*.txt"))
    if not txt_files:
        raise FileNotFoundError("No .txt files found in the specified folder.")
    cookie_txt = random.choice(txt_files)
    with open(filename, "a") as file:
        file.write(f"Choosen File : {cookie_txt}\n")
    return f"""cookies/{str(cookie_txt).split("/")[-1]}"""

# ========== Utils ==========
async def check_file_size(link):
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            print(f"Error:\n{stderr.decode()}")
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for fmt in formats:
            # Một số format không có 'filesize' → bỏ qua
            if "filesize" in fmt and isinstance(fmt["filesize"], (int, float)):
                total_size += fmt["filesize"]
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None

    formats = info.get("formats", [])
    if not formats:
        print("No formats found.")
        return None

    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        """
        Lấy direct stream URL ưu tiên 720p. Nếu format không có → fallback 'best'.
        Trả về: (status, url_or_error)
        """
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        # Ưu tiên bestvideo<=720 + bestaudio
        primary_fmt = "bestvideo[height<=?720]+bestaudio/best"
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-g",
            "-f", primary_fmt,
            "--geo-bypass",
            "--no-playlist",
            "--ignore-errors",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]

        # Fallback #1: dùng 'best' (yt-dlp tự chọn hợp lệ)
        proc2 = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-g",
            "-f", "best",
            "--geo-bypass",
            "--no-playlist",
            "--ignore-errors",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out2, err2 = await proc2.communicate()
        if out2:
            return 1, out2.decode().split("\n")[0]

        # Fallback #2: thử MP4-only nếu cần (một số môi trường chỉ chấp mp4)
        proc3 = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-g",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--geo-bypass",
            "--no-playlist",
            "--ignore-errors",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out3, err3 = await proc3.communicate()
        if out3:
            return 1, out3.decode().split("\n")[0]

        # Báo lỗi cuối cùng
        err_msg = (stderr.decode() or err2.decode() or err3.decode() or "").strip()
        return 0, err_msg or "Failed to resolve any playable format."

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} "
            f"--playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            result = [x for x in result if x.strip()]
        except Exception:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile": cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for fmt in r.get("formats", []):
                try:
                    str(fmt.get("format"))
                except Exception:
                    continue
                # Bỏ các dash-only nếu bạn không muốn
                if "dash" in str(fmt.get("format", "")).lower():
                    continue
                # Nhiều format không có filesize → an toàn hơn là dùng get()
                entry = {
                    "format": fmt.get("format"),
                    "filesize": fmt.get("filesize"),
                    "format_id": fmt.get("format_id"),
                    "ext": fmt.get("ext"),
                    "format_note": fmt.get("format_note"),
                    "yturl": link,
                }
                # Chỉ thêm khi có format_id/ext
                if entry["format_id"] and entry["ext"]:
                    formats_available.append(entry)
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        """
        Trả về: (path_or_url, direct: bool)
        direct=True nghĩa là đã tải về files; False nghĩa là trả về link trực tiếp để stream.
        """
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()

        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.mp3")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            # Sau PP, file sẽ là .mp3
            return xyz

        def video_dl():
            # Đồng bộ format với nhánh direct-stream để tránh mismatch
            ydl_optssx = {
                "format": "bestvideo[height<=?720]+bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile": cookie_txt_file(),
                "no_warnings": True,
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.mp4")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140" if format_id else "bestvideo+bestaudio/best"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id or "bestaudio/best",
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        # Nhánh tải theo lựa chọn UI
        if songvideo:
            await loop.run_in_executor(None, song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath, True

        elif songaudio:
            await loop.run_in_executor(None, song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath, True

        elif video:
            # Nếu cấu hình ON/OFF (ví dụ FORCE_DOWNLOAD) bật → tải về
            if await is_on_off(1):
                downloaded_file = await loop.run_in_executor(None, video_dl)
                return downloaded_file, True
            else:
                # Ưu tiên trả link direct để stream
                status, direct_or_err = await self.video(link)
                if status == 1:
                    return direct_or_err, False
                # fallback: kiểm tra size, nếu nhỏ thì tải về, nếu quá lớn thì bỏ qua
                file_size = await check_file_size(link)
                if not file_size:
                    print("None file Size")
                    return None, False
                total_size_mb = file_size / (1024 * 1024)
                if total_size_mb > 250:
                    print(f"File size {total_size_mb:.2f} MB exceeds the 250MB limit.")
                    return None, False
                downloaded_file = await loop.run_in_executor(None, video_dl)
                return downloaded_file, True

        else:
            # Audio mặc định → tải về mp3
            downloaded_file = await loop.run_in_executor(None, audio_dl)
            return downloaded_file, True
