# 音频与加密音乐

> **状态修正（2026-11-11）**：本文件此前的版本描述的是迁移前产品（FFmpeg libav 解码/重采样/封装 +
> 统一 CLI）的音频能力。当前发布包中的 `quirewise-audio` 是**音频容器与帧解析库（packet reader）**，
> 不是播放器、转码器或编码器：它把输入拆成音频包交给调用方；压缩编码的实际解码、重采样、声道映射、
> 输出封装与播放均不在包内。发布边界不包含 FFmpeg/libav 或其他第三方运行库，需要外部后端的路线
> 返回 `QW_AUDIO_UNSUPPORTED`。

## 1. 公共 API 与包语义

`quirewise/audio.h` 只提供 packet reader：

| 函数 | 作用 |
|---|---|
| `qw_audio_reader_open(data, size, input_format, requested_track, &reader)` | 打开内存中的音频容器；M4A/Matroska/WebM 的 `requested_track` 从 1 开始，0 表示默认音轨 |
| `qw_audio_reader_get_info(reader, &info)` | 容器格式、codec、采样率、声道数/掩码、样本数、是否有元数据 |
| `qw_audio_reader_next_packet(reader, &packet)` | 返回下一个音频包；`QW_AUDIO_OK`/`QW_AUDIO_END`/错误码 |
| `qw_audio_reader_close(reader)` | 关闭并释放 reader |
| `qw_audio_codec_name(codec)` | codec 枚举名称 |

包（`QwAudioPacket`）语义：

- **PCM / 未压缩容器**（WAV 族、AIFF/AIFC PCM、CAF LPCM、AU PCM 等）：`packet.data` 是按容器描述的
  采样字节（整数或 IEEE 浮点、位深/声道/采样率按容器字段）；库不做重采样、声道映射或采样格式转换。
- **压缩编码**：`packet.data` 是压缩帧/包；`decoder_header`（最多 8 字节）、`block_additions`、
  `discard_padding_ns`、`pts/duration` 供调用方转交外部解码器。
- 包数据由 reader 借用，下次 `next_packet` 或 `close` 前有效；调用方不做拷贝时不得跨调用持有。

## 2. 已实现的解析覆盖

容器/帧边界、包表、时长与裁切信息由项目自研解析器读取；未覆盖的变体返回 `QW_AUDIO_UNSUPPORTED`，
不回退到外部 demuxer。

| 容器族 | 已解析内容（子集） |
|---|---|
| WAV 族 | RIFF/RIFX/RF64/BW64/Wave64；整数 PCM（8/16/24/32）、IEEE 浮点（32/64）、G.711 A/µ-law、IMA ADPCM、Microsoft ADPCM（含自定义系数表）、GSM 6.10、WAVE MP3（0x0055）、`MPEG1WAVEFORMAT`（0x0050）、`WAVE_FORMAT_GSM610`（0x0031）、`WAVE_FORMAT_DTS`（0x0008） |
| AIFF/AIFC | PCM 整数/浮点、G.711、`ima4`、`MAC3`/`MAC6`、AIFC 压缩 code 子集（GSM/G.722/G.726/G.728、QDesign 系列、ADP4、APCM XA ADPCM 等） |
| CAF | LPCM、`ima4`、AAC（Main/LC/SSR/LTP、AAC-LD）、ALAC 子集、G.711、MACE3/MACE6、Apple GSM、iLBC、AMR-NB、AC-3、QDMC/QDM2、QCELP、MPEG 包序列 |
| AU/SND | 线性 PCM、IEEE 浮点、G.711；G.721/G.722/G.723/`7262` ADPCM 子集 |
| DSD 容器 | DSF、DFF、DSS 的容器/包解析（按实现子集） |
| MPEG 音频 | MP1/MP2/MP3 帧序列、ADTS AAC、WAVE/Matroska 内的 MP3 |
| 无损/其他 | FLAC（含 Ogg FLAC）、ALAC（CAF/M4A 子集）、TTA、TAK、WavPack（含 hybrid 容器）、APE、Musepack SV7/SV8 |
| ASF/WMA | Header/File Properties/Stream Properties/Data Object、按序号选流、跨包重组、压缩负载拆包 |
| M4A/MP4 | 渐进式与分片（`trex`/`tfhd`/`tfdt`/`trun`）音轨、sample 表、edit list 子集、priming/remainder 裁切 |
| Matroska/WebM | 音轨解析：Opus、Vorbis、FLAC、ALAC、AAC、A_MS/ACM（PCM/ADPCM/MP3）、TTA、WavPack hybrid；CodecDelay/DiscardPadding 元数据 |
| Ogg | Opus（mapping family 0/1/2/255 子集）、Vorbis、Speex、FLAC |
| VOC | Type 1/2/3/9 与 SBPro/ADPCM_CT 子集、有限循环控制块 |

各格式的精确子集（声道/采样率/位深上限、包对齐、priming/remainder、edit/分片限制、错误分类）由
解析器校验并返回稳定的状态码；不支持的具体变体不会产生错误像素或静默回退。

## 3. 明确未实现（发布边界）

- **压缩音频解码到 PCM**：AAC、MP3、FLAC、Opus、Vorbis、Speex、WMA、AC-3/E-AC-3、DTS、TTA、TAK、
  WavPack、APE、Musepack、AMR、ALAC、GSM、iLBC、QDM2 等只输出压缩包，包内没有对应解码器。
- **重采样、声道映射、采样格式转换**：不在公共 API 中；调用方需自行或交给外部解码器处理。
- **编码、muxer、播放**：库不提供任何音频输出 writer 或播放接口。
- **统一 CLI**：只提供 `--check`（容器/包解析，可配 `--audio-track`），没有音频输出；
  加密音乐的密钥选项（`--key`/`--ekey`/`--kgm-*`）仍未接线。
- **视频**：不存在视频处理库；MP4/Matroska 解析只选择音频轨，不解析或解码视频编码。
- **外部后端**：FFmpeg/libav 等外部后端路线不在发布包内，按支持矩阵要求返回 `UNSUPPORTED`。
- 库内保留的 PCM 容器转码辅助实现（`audio_pcm.c`）当前没有公共入口或调用路径，不属于发布能力。

## 4. 加密音乐容器

`quirewise/encrypted_music.h` 提供探测与**容器解密**：输出是底层压缩音频负载（例如 MP3/FLAC），
不是 PCM，也不做转码。公共 API：`qw_encrypted_music_probe_memory`、
`qw_encrypted_music_format_from_path`、`qw_encrypted_music_decrypt_buffer`、
`qw_encrypted_music_buffer_free`、`qw_encrypted_music_status_string`。

| 容器 | 当前能力 | 限制 |
|---|---|---|
| NCM | 探测并解密为底层音频负载 | 公共 API 只返回负载；完整标签/封面导入不在 API 中 |
| QMC | QMC v1、QTag/PcV1Legacy（内嵌 EKey）、STag/MusicEx（需显式 EKey） | STag/MusicEx 需要与歌曲匹配的 EKey；独立解析器不查询播放器数据库 |
| KGM/KGMA/VPR | 按实现支持的版本子集解析；密钥文件通过 `kgm_key_path`（部分版本可用内置密钥），v5 使用显式 EKey | v5 在独立解析器且无显式 EKey 时返回 `UNSUPPORTED`（不查询 KGMusicV3.db） |
| KWM | 旧版 KWM 解密 | 新版 KWM 不支持；文件 API 依赖扩展名识别 |

解密输出仍是压缩负载，后续解码/转码由调用方负责；发布包不含解码器。

## 5. 验证与证据

- `quirewise-audio` CTest 3/3：AES known-answer、KGM 加密音乐解密、音频 fuzz smoke；
- 外部消费者用 `tone.wav` 走通 `open`/`get_info`/`next_packet`/`close` 与加密音乐探测；
- 四套 81 步验收矩阵（Windows/Linux × static/shared）均包含 audio 的 configure/build/install/ctest；
- 无 vendored 实现，依赖 `Quirewise::Compression`（PUBLIC）与 `Quirewise::Crypto`（PRIVATE）。

## 6. 与旧文档的差异

旧版本把“由 FFmpeg libav 解码/重采样/封装”和 `--audio-track`/`--ekey`/`--kgm-key` 等旧 CLI 参数
写成产品能力；这些属于迁移前应用层，未进入当前独立库发布包。当前能力以本文件的 parser-only 边界为准。
