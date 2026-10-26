# Open Media Test Corpus

> 面向解码器 / 播放器 / 智能电视验证的开放媒体测试语料库
> An open, systematically-organised media test corpus for decoder, player and smart-TV validation.

**1063 个样本 · 11.0 GB · 87 种容器格式 · 18 种视频编码 · 27 种音频编码**

每个文件名都自带完整规格标注，无需打开即可识别容器、解码标准、分辨率、帧率与音频参数。
全量元数据（含 sha256 与原始下载地址）见 [`MANIFEST.csv`](MANIFEST.csv)，
来源与授权见 [`CREDITS.md`](CREDITS.md)。

---

## 命名规范

```
视频： 容器__视频编码-Profile__宽x高p帧率__音频编码-声道-采样率__来源-原名.ext
音频： 容器__音频编码-声道-采样率__来源-原名.ext
```

| 示例 | 解读 |
| --- | --- |
| `MP4__H265-HEVC-Main__3840x2160p29.97__AAC-LC-2ch-44k1__chromium-bear.mp4` | MP4 容器 · H.265 HEVC Main Profile · 3840×2160 @29.97fps · AAC-LC 立体声 44.1kHz |
| `WEBM__VP9-Profile0__1920x1080p30__NOAUDIO__testvideos-Big_Buck_Bunny.webm` | WebM 容器 · VP9 Profile 0 · 1080p30 · 无音轨 |
| `MP4__DolbyVision-P8-1-HEVC__1920x1080p60__NOAUDIO__chromium-glass-blowing2.mp4` | Dolby Vision Profile 8.1（HEVC 基层）· 1080p60 |
| `FLAC__FLAC-8ch-176k4__chromium-negative_ts.flac` | FLAC · 8 声道 · 176.4 kHz |

约定：`NOAUDIO` = 无音轨 · `p` 后为帧率 · `44k1` = 44.1 kHz · `~2` 后缀 = 同名去重序号。

## 目录结构

| 目录 | 文件数 | 体积 | 说明 |
| --- | ---: | ---: | --- |
| `corpus/01-video/` | 526 | 4.3 GB | 含视频轨的文件，按容器格式分子目录 |
| `corpus/02-audio/` | 325 | 4.7 GB | 纯音频文件，按容器格式分子目录 |
| `corpus/03-elementary-streams/` | 102 | 846.1 MB | 裸码流 / 基本流（无容器封装），用于直喂解码器 |
| `corpus/08-unsupported-by-ffmpeg/` | 92 | 1.1 GB | **文件正常**但 ffmpeg 无对应解复用器的格式（多为 SoX 原生 / 无文件头格式），需 SoX 等工具处理 |
| `corpus/09-edge-cases-corrupt/` | 18 | 941.7 KB | 上游测试套件**故意损坏**的样本，用于验证容错与防崩溃 |

## 容器格式 ↔ 规范对应关系

| 容器 | 全称 | 规范 / 标准号 | 样本数 | 说明 |
| --- | --- | --- | ---: | --- |
| **MP4** | MPEG-4 Part 14 | ISO/IEC 14496-14 (on ISO BMFF, ISO/IEC 14496-12) | 231 | 最通用的分发容器 |
| **WEBM** | WebM | WebM Project（Matroska 子集） | 184 | Web 优化，限 VP8/VP9/AV1 + Vorbis/Opus |
| **MP3** | MPEG-1/2 Audio Layer III | ISO/IEC 11172-3 / 13818-3 | 52 | 含 ID3 标签的裸流 |
| **WAV** | Waveform Audio | Microsoft RIFF WAVE | 38 | 最常见的未压缩音频 |
| **HEVC** | HEVC Elementary Stream | ITU-T H.265 Annex B | 24 | 裸 HEVC 字节流 |
| **OGV** | Ogg Video | IETF RFC 3533 (Ogg) | 20 | Xiph 开放容器 |
| **H264** | H.264 Elementary Stream | ITU-T H.264 Annex B | 19 | 裸 H.264 字节流 |
| **MKV** | Matroska | IETF RFC 9559 | 18 | 开放容器，基于 EBML |
| **OGG** | Ogg | IETF RFC 3533 | 18 | Xiph 开放容器 |
| **VVC** | VVC Elementary Stream | ITU-T H.266 Annex B | 15 | 裸 VVC 字节流 |
| **IVF** | Indeo Video Format | IVF 简易封装 | 14 | VP8/VP9/AV1 测试常用裸封装 |
| **TS** | MPEG-2 Transport Stream | ISO/IEC 13818-1 | 12 | 广播/IPTV 传输层 |
| **AVI** | Audio Video Interleave | Microsoft RIFF AVI | 10 | 早期 Windows 容器 |
| **MJPEG** | Motion JPEG | ISO/IEC 10918-1 逐帧 | 10 | 每帧独立 JPEG |
| **MOV** | QuickTime File Format | Apple QTFF（ISO BMFF 的前身） | 10 | ISO BMFF 的原型 |
| **3GP** | 3GPP Media | 3GPP TS 26.244 | 9 | 移动端 ISO BMFF 剖面 |
| **ASF** | Advanced Systems Format | Microsoft ASF | 9 | WMV/WMA 的承载容器 |
| **FLAC** | Free Lossless Audio Codec | IETF RFC 9639 | 9 | 开放无损 |
| **FLV** | Flash Video | Adobe FLV | 9 | 旧 Flash 流媒体容器 |
| **M2TS** | BDAV MPEG-2 TS | ISO/IEC 13818-1 + BDAV | 9 | 蓝光光盘流 |
| **MPEG** | MPEG Program Stream | ISO/IEC 11172-1 / 13818-1 | 9 | MPEG-1/2 节目流 |
| **AAC** | AAC ADTS Stream | ISO/IEC 14496-3 + ADTS | 8 | 裸 AAC 流 |
| **F4V** | Flash MP4 | Adobe F4V（基于 ISO BMFF） | 8 | Adobe 的 ISO BMFF 变体 |
| **M2V** | MPEG-2 Elementary Video | ISO/IEC 13818-2 | 8 | 裸 MPEG-2 视频流 |
| **M4A** | MPEG-4 Audio | ISO/IEC 14496-14 变体 | 8 | 纯音频 MP4 |
| **M4V** | MPEG-4 Video | ISO/IEC 14496-14 变体 | 8 | Apple 使用的 MP4 变体 |
| **MTS** | AVCHD Stream | ISO/IEC 13818-1 + BDAV | 8 | 摄像机 AVCHD |
| **MXF** | Material Exchange Format | SMPTE ST 377-1 | 8 | 广播级专业交换格式 |
| **SWF** | Small Web Format | Adobe SWF | 8 | Flash 动画，可内嵌音视频 |
| **VOB** | DVD Video Object | DVD-Video 规范（基于 MPEG-2 PS） | 8 | DVD 光盘流 |
| **WTV** | Windows Recorded TV | Microsoft WTV | 7 | Windows Media Center 录制 |
| **OPUS** | Opus in Ogg | RFC 3533 + RFC 7845 | 6 | Opus 的 Ogg 封装 |
| **RM** | RealMedia | RealNetworks 私有 | 6 | 旧流媒体格式 |
| **8SVX** | 8-Bit Sampled Voice | EA IFF 85 / 8SVX | 5 | Amiga IFF 音频 |
| **AC3** | Dolby Digital | ATSC A/52 / ETSI TS 102 366 | 5 | 裸 AC-3 流 |
| **AMB** | Ambisonic B-Format | Ambisonic WAV | 5 | 空间音频 |
| **AVR** | Audio Visual Research | AVR | 5 | Mac 早期采样格式 |
| **CAF** | Core Audio Format | Apple CAF | 5 | Apple 无大小限制容器 |
| **CDDA** | CD Digital Audio | IEC 60908 (Red Book) | 5 | CD 音轨裸数据 |
| **CVS** | Continuously Variable Slope | CVSD | 5 | 无头语音编码 |
| **CVSD** | Continuously Variable Slope Delta | CVSD | 5 | 无头语音编码 |
| **CVU** | CVSD (unfiltered) | CVSD 变体 | 5 | 无头语音编码 |
| **DTS** | DTS Coherent Acoustics | ETSI TS 102 114 | 5 | 影院/蓝光音频 |
| **DVMS** | DVMS | Dialogic DVMS | 5 | 无头语音 |
| **FAP** | Ensoniq PARIS | Ensoniq PARIS | 5 | 同 PAF |
| **FSSD** | Sound Designer I | Digidesign SD I | 5 | 无头音频 |
| **GSRT** | Grandstream ringtone | Grandstream | 5 | 话机铃声 |
| **HCOM** | HCOM | Mac HCOM | 5 | Huffman 压缩 Mac 音频 |
| **HTK** | HTK Speech | HTK Toolkit | 5 | 语音识别特征/波形 |
| **IMA** | IMA ADPCM (raw) | IMA/DVI ADPCM | 5 | 无头 ADPCM |
| **IRCAM** | IRCAM/SDIF | IRCAM | 5 | 学术声音分析格式 |
| **M4R** | MPEG-4 Ringtone | ISO/IEC 14496-14 变体 | 5 | iPhone 铃声 |
| **MAUD** | MAUD | Amiga MAUD | 5 | Amiga 音频 |
| **MP2** | MPEG-1 Audio Layer II | ISO/IEC 11172-3 | 5 | 广播常用 |
| **NIST** | NIST SPHERE | NIST SPHERE | 5 | 语音研究语料格式 |
| **OGA** | Ogg Audio | IETF RFC 3533 | 5 | 纯音频 Ogg |
| **PAF** | Ensoniq PARIS | Ensoniq PARIS | 5 | 音频工作站格式 |
| **PRC** | Psion Record | Psion PRC | 5 | Psion PDA 音频 |
| **PVF** | Portable Voice Format | PVF | 5 | 便携语音 |
| **RA** | RealAudio | RealNetworks 私有 | 5 | 旧流媒体音频 |
| **SD2** | Sound Designer II | Digidesign SD2 | 5 | Pro Tools 传统格式 |
| **SLN** | Asterisk Signed Linear | Asterisk SLN | 5 | 无头 PCM 电话音频 |
| **SMP** | Turtle Beach SampleVision | SampleVision | 5 | 采样器格式 |
| **SND** | Sun/NeXT audio | Sun au 别名 | 5 | 同 AU |
| **SNDR** | Sounder | Sounder | 5 | 无头音频 |
| **SNDT** | SoundTool | SoundTool | 5 | 无头音频 |
| **SOU** | SoundTool | SoundTool | 5 | 无头音频 |
| **SPX** | Speex in Ogg | RFC 3533 + RFC 5574 | 5 | Speex 的 Ogg 封装 |
| **TTA** | True Audio | TTA 开放格式 | 5 | 开放无损 |
| **TXW** | Yamaha TX-16W | Yamaha TX-16W | 5 | 采样器格式 |
| **VMS** | VMS | Dialogic VMS | 5 | 无头语音 |
| **VOC** | Creative Voice File | Creative Labs VOC | 5 | Sound Blaster 时代格式 |
| **VOX** | Dialogic ADPCM | Dialogic VOX | 5 | 无头 ADPCM 电话音频 |
| **W64** | Sony Wave64 | Sony Wave64 | 5 | 突破 WAV 4GB 上限 |
| **WMA** | Windows Media Audio | Microsoft ASF | 5 | ASF 的音频扩展名 |
| **WV** | WavPack | WavPack 开放格式 | 5 | 开放无损/有损混合 |
| **WVE** | Psion Alaw | Psion WVE | 5 | Psion A-law 音频 |
| **AIFF** | Audio Interchange File Format | Apple AIFF | 4 | Apple 未压缩音频 |
| **AU** | Sun/NeXT audio | Sun au | 4 | Unix 传统音频格式 |
| **AC4** | Dolby AC-4 | ETSI TS 103 190 | 3 | 次世代广播音频 |
| **ADTS** | AAC ADTS Stream | ISO/IEC 13818-7 | 3 | AAC 传输帧格式 |
| **MKA** | Matroska Audio | IETF RFC 9559 | 3 | 纯音频 Matroska |
| **Y4M** | YUV4MPEG2 | YUV4MPEG2 | 2 | 未压缩 YUV 序列 |
| **EAC3** | Dolby Digital Plus | ATSC A/52 Annex E | 1 | 裸 E-AC-3 流 |
| **SPH** | NIST SPHERE | NIST SPHERE | 1 | 同 NIST |
| **VP8** | VP8 Elementary Stream | RFC 6386 | 1 | 裸 VP8 帧数据 |
| **VP9** | VP9 Elementary Stream | VP9 Bitstream Spec | 1 | 裸 VP9 帧数据 |

## 视频解码标准 ↔ 规范对应关系

| 解码标准 | 规范 / 标准号 | 组织 | 样本数 | 分辨率范围 | 承载容器 |
| --- | --- | --- | ---: | --- | --- |
| **H.264 / AVC** | ITU-T H.264 \| ISO/IEC 14496-10 | MPEG/ITU | 195 | 80×128 → 3840×2160 | 3GP, F4V, H264, M4V, MKV, MOV, MP4 |
| **VP9** | WebM Project VP9 Bitstream Spec | Google/WebM | 90 | 160×120 → 3840×2160 | IVF, MP4, VP9, WEBM |
| **VP8** | IETF RFC 6386 | Google/WebM | 80 | 320×176 → 1920×1080 | IVF, OGV, VP8, WEBM |
| **H.265 / HEVC** | ITU-T H.265 \| ISO/IEC 23008-2 | MPEG/ITU | 62 | 176×144 → 3840×2160 | HEVC, MKV, MP4 |
| **MPEG-2 Video** | ITU-T H.262 \| ISO/IEC 13818-2 | MPEG/ITU | 51 | 320×192 → 3840×2160 | M2TS, M2V, MTS, MXF, TS, VOB, WTV |
| **AV1** | AOMedia AV1 Bitstream & Decoding Process | AOMedia | 38 | 64×64 → 1920×1080 | IVF, MP4, WEBM |
| **Theora** | Xiph Theora Specification | Xiph | 17 | 240×240 → 3840×2160 | OGG, OGV |
| **Sorenson Spark (H.263)** | 基于 ITU-T H.263 | Adobe | 15 | 320×192 → 3840×2160 | FLV, SWF |
| **H.266 / VVC** | ITU-T H.266 \| ISO/IEC 23090-3 | MPEG/ITU | 15 | 208×120 → 1920×1080 | VVC |
| **Motion JPEG** | ISO/IEC 10918-1 逐帧 | JPEG | 11 | 320×192 → 3840×2160 | MJPEG, MP3 |
| **MPEG-4 Part 2** | ISO/IEC 14496-2 | MPEG/ITU | 10 | 320×192 → 3840×2160 | AVI |
| **MPEG-1 Video** | ISO/IEC 11172-2 | MPEG/ITU | 9 | 320×192 → 3840×2160 | MPEG |
| **MS MPEG-4 v3** | Microsoft 私有 | Microsoft | 8 | 640×360 → 3840×2160 | ASF |
| **Dolby Vision** | Dolby Vision Profile 5 / 8.1（HEVC 基层） | Dolby | 6 | 1920×1080 | MP4 |
| **RealVideo** | RealNetworks 私有 | RealNetworks | 5 | 960×400 → 3840×2160 | RM |
| **WMV 8** | Microsoft 私有 | Microsoft | 2 | 320×240 → 1280×720 | ASF, MKV |
| **未压缩 YUV** | 无（原始采样） | Raw | 2 | 320×240 → 962×540 | Y4M |
| **RealVideo G2** | RealNetworks 私有 | RealNetworks | 1 | 640×360 | RM |

> 备注：ffmpeg 会把部分 Dolby Vision 流的 codec 误报为 `dvvideo`（`dvh1` 标签与 DV 磁带格式冲突）。本库已依据 DOVI configuration record 更正，单独列为 Dolby Vision。

## 音频解码标准 ↔ 规范对应关系

| 解码标准 | 规范 / 标准号 | 组织 | 样本数 | 声道 | 采样率 (Hz) |
| --- | --- | --- | ---: | --- | --- |
| **AAC** | ISO/IEC 14496-3 (LC / HE-AAC v1 / v2) | MPEG | 102 | 1, 2 | 8000, 22050, 44100, 48000 |
| **线性 PCM 16-bit 小端** | 未压缩线性 PCM (LPCM) | Raw | 68 | 1, 2, 4, 9 | 3000, 8000, 16000, 44100, 48000, 96000, 192000 |
| **Opus** | IETF RFC 6716 | Xiph/IETF | 64 | 1, 2, 4, 6, 11 | 48000 |
| **Vorbis** | Xiph Vorbis I Specification | Xiph | 61 | 1, 2, 6, 9 | 22050, 44100, 48000 |
| **MP3** | ISO/IEC 11172-3 / 13818-3 Layer III | MPEG | 58 | 1, 2 | 22050, 44100, 48000 |
| **线性 PCM 16-bit 大端** | 未压缩线性 PCM (LPCM) | Raw | 39 | 2 | 44100 |
| **FLAC** | IETF RFC 9639 | Xiph/IETF | 24 | 1, 2, 4, 8 | 8000, 44100, 96000, 176400, 192000 |
| **Dolby Digital (AC-3)** | ATSC A/52 \| ETSI TS 102 366 | Dolby | 15 | 2 | 44100, 48000 |
| **MP2** | ISO/IEC 11172-3 Layer II | MPEG | 15 | 2 | 44100, 48000 |
| **DTS** | ETSI TS 102 114 | DTS | 8 | 2, 6 | 44100, 48000 |
| **WMA 8/9** | Microsoft 私有 | Microsoft | 7 | 2 | 44100, 48000 |
| **Speex** | IETF RFC 5574 | Xiph | 6 | 2 | 32000 |
| **Dolby AC-4** | ETSI TS 103 190 | Dolby | 6 | 2, 6 | 44100, 48000 |
| **G.711 A-law** | ITU-T G.711 | ITU-T | 6 | 1 | 8000 |
| **8-bit PCM (planar)** | 线性 PCM | Raw | 5 | 2 | 44100 |
| **HCOM** | Mac HCOM | 传统 | 5 | 1 | 22050 |
| **True Audio** | TTA 开放规范 | 开放 | 5 | 2 | 44100 |
| **WavPack** | WavPack 开放规范 | 开放 | 5 | 2 | 44100 |
| **Dolby Digital Plus (E-AC-3)** | ATSC A/52 Annex E | Dolby | 3 | 2, 6 | 44100, 48000 |
| **线性 PCM 24-bit 小端** | 未压缩线性 PCM (LPCM) | Raw | 3 | 1, 6 | 44100, 48000 |
| **ADPCM (SWF)** | Adobe SWF ADPCM | Adobe | 1 | 2 | 44100 |
| **truehd** | — | — | 1 | 6 | 48000 |
| **线性 PCM 24-bit 大端** | 未压缩线性 PCM (LPCM) | Raw | 1 | 2 | 44100 |
| **线性 PCM 32-bit 小端** | 未压缩线性 PCM (LPCM) | Raw | 1 | 1 | 44100 |
| **G.711 µ-law** | ITU-T G.711 | ITU-T | 1 | 1 | 8000 |
| **线性 PCM 32-bit 小端** | 未压缩线性 PCM (LPCM) | Raw | 1 | 1 | 44100 |
| **线性 PCM 8-bit** | 未压缩线性 PCM (LPCM) | Raw | 1 | 1 | 44100 |

## 分辨率覆盖

| 档位 | 样本数 | 典型用途 |
| --- | ---: | --- |
| ≤288p | 178 | 低码率 / 缩略图 / 单元测试 |
| 360p | 74 | 移动网络 |
| 480p SD | 45 | 标清广播 |
| 576p SD | 36 | PAL 标清 |
| 720p HD | 123 | 高清广播 |
| 1080p FHD | 85 | 主流全高清 |
| 1440p QHD | 23 | 2K 显示 |
| 2160p 4K UHD | 35 | 4K 电视 / HDR |

## 专项测试集

| 专项 | 样本数 | 定位方式 |
| --- | ---: | --- |
| Dolby Vision (P5 / P8.1) | 6 | 文件名含 `DolbyVision-` |
| 10-bit / HDR 像素格式 | 53 | `MANIFEST.csv` 的 `pix_fmt` 含 `10le` |
| DRM 加密 (CENC / CBCS) | 32 | 文件名含 `cenc`/`cbcs`/`cbc1`/`cens` |
| 分片 MP4 (fMP4 / MSE) | 58 | 文件名含 `frag` |
| 多声道 (5.1 / 7.1+) | 16 | `channels` ≥ 6 |
| 故意损坏样本 | 18 | `corpus/09-edge-cases-corrupt/` |
| 多音轨 (>1) | 7 | `n_audio_tracks` > 1 |
| 含内封字幕 | 6 | `n_subtitle_tracks` > 0 |

## HDR 与色彩

| HDR 系统 | 传输特性 | 样本数 |
| --- | --- | --- |
| **SDR** | BT.709 / BT.601 等 | 59 |
| **HDR10** | SMPTE ST 2084 (PQ) | 7 |
| **DolbyVision-P5** | Dolby Vision Profile 5 | 5 |
| **DolbyVision-P8-1** | Dolby Vision Profile 8.1 | 1 |
| **HLG** | ARIB STD-B67 | 1 |

> 另有 **546** 个视频样本未携带色彩特性元数据，无法据此判定 HDR 类型。

## 编码 Level 分布

Level 直接决定硬件解码器能否处理该码流（如 H.264 L5.1、HEVC L5.1 对应 4K 能力），
是硬解能力验证的关键筛选维度。

| 编码 | Level 分布 | 有标注 |
| --- | --- | ---: |
| h264 | L1.2(9), L1.3(16), L2.0(1), L2.1(3), L3.0(42), L3.1(51), L4.0(29), L4.1(3), L4.2(10), L5.0(10), L5.1(10) | 184 |
| hevc | L2.0(11), L2.1(3), L3.0(3), L3.1(23), L4.0(5), L5.0(5), L5.1(7) | 57 |
| mpeg2video | L4(21), L6(23), L8(7) | 51 |
| av1 | L1(6), L4(2), L5(5), L8(4), L9(1) | 18 |
| vvc | L1.1(2), L1.2(3), L2.2(9), L3.5(1) | 15 |
| mpeg4 | L0.1(1), L1(9) | 10 |

> 335/617 个视频样本带 level 标注；部分容器/编码不暴露该字段。

## 数据来源

| 来源 | 样本数 | 授权 | 状态 |
| --- | ---: | --- | --- |
| [filesamples.com](https://filesamples.com/) | 433 | 未声明 | ⚠️ 未声明 |
| [Chromium `media/test/data`](https://chromium.googlesource.com/chromium/src/media/+/refs/heads/main/test/data/) | 384 | BSD-3-Clause | ✅ 明确开源 |
| [samplelib.com](https://samplelib.com/) | 81 | 未声明 | ⚠️ 未声明 |
| [test-videos.co.uk](https://test-videos.co.uk/) | 42 | CC-BY 3.0 | ✅ 明确开源 |
| [web-platform-tests/wpt](https://github.com/web-platform-tests/wpt) | 31 | BSD-3-Clause | ✅ 明确开源 |
| [本项目自制（衍生自下列开源片源）](https://github.com/bandusix/open-media-test-corpus) | 30 | 沿用片源许可：CC-BY-3.0 / BSD-3-Clause / CC0 | ✅ 明确开源 |
| [webmproject/libwebm](https://github.com/webmproject/libwebm/tree/main/testing/testdata) | 28 | BSD-3-Clause | ✅ 明确开源 |
| [mdn/shared-assets](https://github.com/mdn/shared-assets) | 16 | CC0-1.0 / CC-BY | ✅ 明确开源 |
| [Wikimedia Commons](https://commons.wikimedia.org/) | 11 | CC BY-SA / 公有领域 | ✅ 明确开源 |
| [mdn/learning-area](https://github.com/mdn/learning-area) | 4 | CC0-1.0 / CC-BY | ✅ 明确开源 |
| [joshuatz/video-test-file-links 直链](https://github.com/joshuatz/video-test-file-links) | 2 | 依各自来源 | ✅ 明确开源 |
| [webmfiles.org](https://www.webmfiles.org/) | 1 | CC-BY 3.0 | ✅ 明确开源 |

其中 **549** 个来自授权明确的开源项目，**514** 个来自未声明再分发条款的样本聚合站点。完整逐项归属见 [`CREDITS.md`](CREDITS.md)。

> ⚠️ **使用须知**：本语料库仅供解码器 / 播放器功能测试与研究使用。
> 标记为「未声明」的样本，其来源站点未公布再分发许可，原始素材的著作权归各自权利人所有；
> 如需商用或再分发，请自行向权利人确认授权。若您是某素材的权利人并希望移除，请提 issue。

## 使用

> **媒体文件不在本仓库里。** GitHub 硬性拦截超过 100 MiB 的文件，且建议仓库控制在 1 GB 以内，
> 而本语料库约 11.0 GB。因此样本以分卷压缩包的形式发布在 [Releases](../../releases)，仓库只保留文档、清单与脚本。

```bash
# 1. 拉取全部样本（约 11.0 GB，解压到 corpus/）
python3 scripts/fetch.py

# 只取需要的部分
python3 scripts/fetch.py --list
python3 scripts/fetch.py --part 01-video

# 2. 校验完整性（比对 MANIFEST.csv 中的 sha256）
python3 scripts/verify.py
python3 scripts/verify.py --quick        # 只比体积，不做哈希

# 3. 按条件筛选样本
python3 scripts/query.py --codec hevc --min-height 2160
python3 scripts/query.py --dolby-vision
python3 scripts/query.py --audio-codec ac4
python3 scripts/query.py --container MKV --has-audio
python3 scripts/query.py --encrypted --format path
```

`MANIFEST.csv` 独立于媒体文件存在，因此**不下载任何样本也能查询覆盖情况**——
clone 仓库后直接跑 `query.py` 即可确认某个格式/编码组合是否存在。

---

本项目的**文档与脚本**以 MIT 许可发布（见 [`LICENSE`](LICENSE)）；
**媒体样本本身**沿用各自来源的许可，不受 MIT 覆盖。

灵感来自 [joshuatz/video-test-file-links](https://github.com/joshuatz/video-test-file-links)。
