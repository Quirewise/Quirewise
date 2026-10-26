# 音频与加密音乐

## 标准音频

音频输入容器结构和音频包边界由项目自研解析器读取；FFmpeg libav 用于通用编解码、重采样和输出封装。解析器未覆盖的输入变体返回不支持，不交给 libavformat 输入 demuxer。

AIFF `COMM` 的采样率以 80 位扩展浮点表示；自研数值解析器按最近整数舍入到项目采样率字段，并拒绝非正值或超出 `int` 表示范围的值。AIFC PCM 标签 `NONE`、`twos`、`sowt`、`raw `、`in24`、`in32`、`fl32` 和 `fl64` 由独立标签步骤映射并校验位深；`raw ` 为无符号 8-bit，`in24`/`in32` 为大端有符号 PCM，解码采样仍走项目的 PCM 转换路径。

CAF LPCM 路线将 `chan` 声道布局交给独立解析器。可映射为标准扬声器掩码的布局传递给解码器；自定义、未知或声道顺序无法由标准掩码表达的合法布局，以及缺少 `chan` 的多声道 LPCM，均保留声道数并标记为未指定顺序。

WAVE（含 RF64/BW64）、Wave64、AIFF 中自研解析器支持的整数 PCM 和 IEEE 浮点 PCM，以及 CAF 中未压缩 LPCM，由项目直接解析并构造采样帧；WAVE（含 RF64/BW64）、Wave64、AIFF PCM 支持 1–64 声道、正且可由 `int` 表示的整数采样率、8/16/24/32 位整数样本和 32/64 位 IEEE 浮点样本，并按容器字段校验块对齐与字节率；CAF LPCM 校验 `framesPerPacket` 与 packet 字节数的对应关系，支持 1–64 声道、1–32 位整数样本（包括高位对齐的非字节位宽、24 位 packed/unpacked 容器）和 32/64 位浮点样本，采样率必须是 1–`INT_MAX` 范围内的整数。WAVE MP3（format tag `0x0055`）由独立描述符解析器读取 `MPEGLAYER3WAVEFORMAT`，RIFF、RIFX、RF64、BW64 或 Wave64 容器解析器确定 `data`/`fact` 边界，自研 MPEG 帧 parser 验证帧序列并按 `nCodecDelay` 与 `fact` 限制输出时长；支持 RIFF、RIFX、RF64、BW64 与 Wave64，单/双声道及按 `nFramesPerBlock` 对齐的 Layer III 帧，压缩帧交给 libavcodec。AU/SND 的线性 PCM、IEEE 浮点 PCM 和 G.711 μ-law/A-law 由项目解析头部与数据范围，支持 1–64 声道及 1–`INT_MAX` 的整数采样率；RIFF WAVE、RF64、BW64、Wave64 G.711（format tag `0x0006`/`0x0007`，以及对应的 WAVE_FORMAT_EXTENSIBLE 子格式 GUID）和 AIFC `alaw`/`ulaw` 由共享容器块解析器读取数据范围，并构造有界数据包。RIFX 的 WAVE_FORMAT_EXTENSIBLE 按大端解析结构字段，并识别标准 SubFormat GUID 中的 PCM、IEEE 浮点与 G.711 子格式。WAVE extensible 的声道掩码会传递给解码器布局；掩码多余的高位会被忽略，掩码不足时按未指定布局保留声道数和顺序；整数 PCM 支持有效位数小于字节对齐容器位数的左对齐样本；IEEE 浮点 PCM 按 32/64-bit 容器读取，较低的 `wValidBitsPerSample` 只表示信号精度，不改变浮点容器位型。WAVE 压缩音频路线按 `fact` 样本数裁剪尾部。G.711 数据包交给 libavcodec 解码。AIFC `ima4` 由项目自研解析器扫描容器块、校验 34 字节/声道的固定包，并逐包交给 libavcodec 解码；当前支持单/双声道、16-bit 原始样本和 8–384 kHz。AIFC `MAC3`/`MAC6` 由独立解析器校验压缩包长度，并按每包 6 个采样帧分包交给 libavcodec；当前支持单/双声道、8-bit `COMM` 样本深度和 8–384 kHz。AIFC 的 `GSM `、`G722`、`G726`、`G728`、`Qclp`、`QDMC`、`QDM2`、`CBD2`、`SDX2`、`ADP4` 和 `VAPC` 由独立解析器读取共享 chunk parser 给出的数据范围、方法信息、`wave` 额外数据和编码块对齐，再将压缩包交给 libavcodec；ADP4 的 `APPL/stoc/VADPCMCODES` 额外数据由项目解析并传给解码器。AIFF `APCM` 块由独立块解析器提取 XA ADPCM 数据和块对齐，再由共享 AIFF codec 输入路径分包并交给 libavcodec；该路径要求单/双声道。未识别的 AIFC compression code 返回不支持。

Sun AU（`.snd`）由项目解析头部、annotation 范围和数据边界。U-law/A-law、线性 8/16/24/32-bit PCM、32/64-bit IEEE float 走自研采样解析；G.721、G.722、G.723 24/40 kbit/s 与 `7262` 标签由独立 AU ADPCM 解析器计算码宽、样本数和包对齐，再交给 libavcodec；G.72x 当前限单声道。其他编码返回不支持。

WAVE IMA ADPCM（format tag `0x0011`）和 Microsoft ADPCM（format tag `0x0002`）由 RIFF、RF64、BW64 或 Wave64 容器解析器读取 `fmt`、`fact` 和 `data`，再由各自的格式解析器校验块边界并逐块交给 libavcodec。IMA ADPCM 支持 4-bit 单/双声道；Microsoft ADPCM 支持 4-bit、最多 6 声道，并按 `fact` 样本数裁掉最后一块的填充样本。Microsoft ADPCM 的 WAVEFORMATEX 系数表解析、编码块校验和 ADPCM 解码分别位于独立模块；标准七系数表继续交给 libavcodec，非标准自定义系数表由项目自研解码器转为 S16LE PCM 后送入通用音频转换路径。最多支持 256 组系数、4-bit 编码、1–6 声道，并校验每块的预测器索引和初始 delta；其他 WAVE 压缩编码返回不支持。

Wave64 的独立 GUID/chunk 扫描器校验 64-bit chunk size 和 8-byte 对齐，并生成共享的 `fmt`/`fact`/`data` 视图；IMA ADPCM、Microsoft ADPCM（包括自定义系数表）、G.711 和 MP3 复用对应的格式校验与 packet 路径。

RF64 与 BW64/WAVE 使用独立的 `ds64` 解析器；`ds64` 必须是首个 chunk，解析 64 位 RIFF/data 长度及可选 chunk size table，结果映射到共享 `fmt`/`fact`/`data` 视图，供自研 WAVE PCM、ADPCM、G.711、MPEG、GSM 与 DTS 子集复用。RF64 的 `sampleCount` 可替代 `fact` 中的 `0xFFFFFFFF`；BW64 的对应字段是兼容占位值并忽略，`fact` 中的 `0xFFFFFFFF` 样本数按未知处理。当前自研路线接受一个 `data` chunk，实际数据仍受项目输入大小上限约束。[EBU Tech 3306](https://tech.ebu.ch/files/live/sites/tech/files/shared/tech/tech3306v1_1.pdf)，[ITU-R BS.2088-2](https://www.itu.int/dms_pubrec/itu-r/rec/bs/R-REC-BS.2088-2-202511-I%21%21PDF-E.pdf)。

CAF 的 Apple IMA4、AAC Main/LC/SSR/LTP、AAC-LD、ALAC、G.711、MACE3/MACE6 路线由共享 CAF 块扫描器读取 `desc`、`data` 及编码所需的 `pakt`/`kuki`；共用包表头解析器读取有效帧数、priming 和 remainder，包长变长整数由共享 CAF varint 读取器处理。IMA4 解析器检查 34 字节/声道、64 样本的固定包，并将每包交给 libavcodec；有 `pakt` 时校验总包帧数与有效帧、priming、remainder 一致，解码后跳过 priming 并按有效帧数限长。AAC 解析器将 cookie 中的 ESDS 描述符交给共享 MPEG-4 ESDS 解析器，再由共享 AudioSpecificConfig 解析器读取 AAC 配置并验证变长包表，随后将原始 AAC 包交给 libavcodec；解码后跳过 priming 样本，再按有效帧数截掉 remainder。AAC-LD (`aacl`) 的独立子配置解析器读取 480/512 样本帧长、PCE 声道数、数据恢复标记和 `epConfig`，并要求 `epConfig=0`、CAF 描述字段 flags 为零；解码仍依赖 codec 库的 AAC-LD 能力。ALAC 解析器规范化新旧 `kuki` cookie，验证 ALAC 配置与 CAF 声道、位深、采样率及包表一致后，将原始包交给 libavcodec；解码后跳过 priming 样本并限制到有效帧数。G.711 解析器校验 `ulaw`/`alaw` 固定包描述和可选的常量包表，将完整编码帧交给 libavcodec，并按 `pakt` 跳过 priming、限制到有效帧数。MACE 解析器单独校验 `MAC3`/`MAC6` 描述、每包 6 帧和固定包长，接受可选的常量 `pakt` 包表，并在解码后跳过 priming、按有效帧数限长。Apple GSM (`agsm`) 解析器校验单声道 8 kHz、33 字节/160 帧的固定包及可选常量 `pakt`，再交给 GSM 解码器。iLBC (`ilbc`) 解析器支持固定包以及 `pakt` 包长表，校验 38 字节/160 帧或 50 字节/240 帧的包后交给 iLBC 解码器。AMR-NB (`samr`) 解析器按 `pakt` 变长包表逐包校验单声道 8 kHz AMR 帧，并保留 cookie、priming 和 remainder 信息后交给 AMR-NB 解码器。AC-3 (`ac-3`) 解析器按变长包表校验每包一个 1536 帧 AC-3 帧及声道/采样率描述，并保留 cookie 和裁切信息后交给 AC-3 解码器。QDMC/QDM2 解析器分别校验固定块长、2048×声道数的包帧数和 cookie，处理可选常量 `pakt` 后将包交给对应解码器。QCELP (`Qclp`) 解析器校验单声道 8 kHz、160 帧包，并支持 17/35 字节固定包或经 `pakt` 列出的变长包。CAF `.mp1`、`.mp2`、`.mp3` 及兼容的 `ms\0U`（Layer III）标签由独立解析器读取共享块结构和固定或变长包表，校验每包恰含一个与格式描述一致的 MPEG Layer I/II/III 帧，并按 `pakt` 的 priming/remainder 限制时长；压缩帧交给 libavcodec。其他 AAC 扩展和 CAF 编码返回不支持。

M4A 的渐进式 ISO BMFF 路线由项目自研解析容器结构、音轨和 sample tables，并把 AAC Main/LC/SSR/LTP、显式或同步扩展信令的 HE-AAC SBR/PS 配置或单/双声道 ALAC 包交给 libavcodec。共享 AAC AudioSpecificConfig 自研解析器支持 PCE 声道配置 0、显式或同步扩展的 SBR/PS 信令，并保留原始配置供解码器使用；PS 路线校验单声道 AAC 核心与双声道样本描述一致。当前支持按序号选择一条音轨、一个或多个解码配置等价的 sample description、最多 64 个 `mdat` 数据盒；渐进式路线支持一个或多个正向、1 倍速音频 edit entry，允许前置空 edit 并按其时长生成静音；多段非空 edit 仅在媒体区间连续时合并映射，并按采样点跳过起始媒体样本、限制呈现时长，`ctts` 在无 edit list 的渐进式路线按 sample 读取可变 composition offset；带 edit list 时仍要求恒定 offset。分片路线自研解析 `trex`、`tfhd`、`tfdt`、`trun` 和 `mdat` 数据范围，支持由容器默认值或 run 样本项提供时长、长度及 composition offset；当前拒绝 edit list、加密样本及无法确定基准偏移的多轨片段。媒体区间不连续的多段、空 edit 出现在媒体 edit 之后、变速 edit、不等价 sample description 和未覆盖的编码变体返回不支持。ALAC 的 24-byte `ALACSpecificConfig` 由项目直接解析。

对于仍由通用解码器处理的压缩音频，项目解析传输或帧结构并向 libavcodec 提供包。ADTS AAC 路线由项目解析帧头与帧边界、生成 AudioSpecificConfig 并去除传输头；支持声道配置 1–7，以及首个 raw data block 以有效 PCE 开始的声道配置 0，并要求文件内采样率和声道配置一致。当前支持单 raw data block 帧，以及 protection_absent=0 且 raw_data_block_position 表有效的多块帧；项目按位置表切出独立 AAC 包并跳过各块 CRC 字段（暂不校验 CRC 数值）。无位置表的多块帧返回不支持，不交由 libavformat。MP2/MP3 路线解析 MPEG 音频帧并计算时长，支持可变码率；要求文件内层级、MPEG 版本、采样率和声道数一致。ID3v2 开头标签与 ID3v1 尾标签只用于确定音频数据范围，标签内容暂不导入文档元数据。AMR-NB/WB 路线按存储格式解析文件头、帧长和 20 ms 帧边界；AMR-WB 的保留帧类型（10–13）按规范拒绝，存储帧头的填充位由解析器忽略，压缩语音帧交给 libavcodec 解码。原生 FLAC 路线解析 `fLaC` 元数据、STREAMINFO、帧头和帧边界，并校验帧头与帧 CRC；压缩子帧解码交给 libavcodec。原始 AC-3/E-AC-3 由家族级流扫描器校验连续帧，AC-3 与 E-AC-3 帧头分别由独立自研解析器处理，再交给 libavcodec 解码；E-AC-3 访问单元解析器只选取 substream_id=0 的独立子流并跳过其他独立子流；只将紧随其独立帧、ID 与帧时长匹配的依赖帧并入同一 packet。缺少 ID 0 或无法按此边界解析的依赖流返回不支持。原始 DTS 路线自研解析 16-bit 大端/小端和 14-bit 打包核心帧头与帧边界；识别 XCH/X96/XXCH 核心扩展类型并将完整 core 帧交给 libavcodec 解码；对 16-bit 大端 core 后的 DTS-HD ExSS，自研解析 4-byte 对齐的扩展帧边界并与 core 合并为一个 packet；无 core 配对或其他 DTS-HD ExSS 排布返回不支持。TTA v1 路线解析头部、校验头与帧索引表 CRC，并按索引读取压缩帧交给 libavcodec 解码；加密格式及不支持的采样宽度返回不支持。WavPack 路线解析块头、连续采样索引及每个采样区间内的连续 block 组，跳过音频前置的零采样 metadata block；对未知总样本数和非零起始 block_index 的截取文件按实际可用帧数累计样本数，并识别 APEv2/ID3v1 尾标签，再由 libavcodec 解码；当前支持最多 64 声道（超过 8 声道按未指定布局保留声道数和顺序）、标准采样率及含有效 3-byte SAMPLE_RATE 块元数据的自定义基础采样率（1–16,777,215 Hz）、PCM 与 DSD 数据（将 DSD_DATA 的 2^n 倍率计入有效采样率，且有效值不超过 int 范围；压缩位流由 libavcodec 解码）；缺失的自定义采样率及不受支持的版本返回不支持。VOC 路线由项目自研的块迭代器读取头部、校验和及块边界；当前支持 Type 1 U8 PCM（带 Type 8 时支持单/双声道参数）和单声道 Sound Blaster Pro 4/3/2-bit ADPCM、Type 2 的 U8/ADPCM 续块、Type 3 单声道 U8 静音段，以及 Type 9 的 U8/S16LE/G.711 A-law/μ-law、单声道 Sound Blaster Pro ADPCM 标签 1–3，以及单声道 16-bit ADPCM_CT 标签 `0x0200`。SBPro 首包包含一个初始样本，ADPCM_CT 每字节解码两个样本且不含初始样本；Type 9 的 SBPro ADPCM 使用 8-bit sample depth。Type 6/7 有限循环由自研控制块解析器扩展播放顺序，最多支持 16 层嵌套；循环体含 SBPro 初始化样本的重复循环和无限循环返回不支持；不含初始化样本的有限 ADPCM 循环按当前解码状态重放，空有限循环按零样本处理；立体声 SBPro ADPCM 和其他编码返回不支持。APE v3.80–3.99.0 路线由独立头解析器处理现代 descriptor 与旧版头；旧版兼容可选 peak-level/seek-element 字段及 v3.80–3.80.9 bit table，并解析 seek table 和帧边界，为 libavcodec 补齐每帧的 block/skip 头及 6-byte extradata；旧版路线按 APEv2/ID3v1 尾标签确定音频范围；当前要求压缩级别为 1000、2000、3000、4000 或 5000，位深为 8/16/24-bit，声道数为 1–8，且音频数据长度可验证；其他版本或异常帧布局返回不支持。

Ogg Opus 路线由项目解析 Ogg 页、CRC、lacing、OpusHead/OpusTags、音频包时长和 granule position，再将压缩包交给 libavcodec 解码；OpusHead 映射族解析与 Ogg 包序列解析由独立模块负责。mapping family 0 支持单/双声道，family 1 支持 1–8 声道，family 2 校验 RFC 8486 规定且不超过 64 声道的 Ambisonics 子集，family 255 校验并支持 1–64 声道的自定义映射；映射表均校验 stream count、coupled count 和 channel index。family 3 校验 RFC 8486 允许的输出声道数 C 和输入声道数 K=N+M（C、K 均不超过 64），读取小端 Q15 解混矩阵并交由后端应用，同时合成供 libavcodec 解码的 family 255 头；目标编码器可保留 C 个输出声道，也可使用 RFC 8486 推荐的单声道 W 声道或立体声 downmix。可按音轨序号从多个受支持逻辑流中选择，并按需动态组装跨页包。未识别映射族（含 240–254 实验号）和超出自研解析上限的映射返回不支持；未识别的音频逻辑流也返回不支持，不回退到 libavformat。解码器按 OpusHead 的 pre-skip 裁掉起始样本，项目再按最终 granule position 限制尾部样本数。

Ogg FLAC（映射 1.0）复用共享 Ogg 页校验与包迭代器，项目解析映射头、STREAMINFO、Vorbis Comment 元数据包边界、FLAC 帧边界和 CRC，跨页包按需动态组装，再将音频帧交给 libavcodec；1.1.1 之前的旧式映射由独立自研模块解析 `fLaC` 首包和后续 STREAMINFO 包，帧仍复用项目自研 FLAC 帧解析器；未识别的音频逻辑流返回不支持，不回退到 libavformat。

Ogg Vorbis 复用共享 Ogg 页校验与包迭代器，项目解析三个 Vorbis 头、注释包结构、音频包边界及 granule position，并构造解码器所需的 Xiph-laced extradata；Vorbis setup 码流解释、声道映射、起始 priming 样本裁剪和音频解码交给 libavcodec，项目按最终 granule position 限制总样本数。1–8 声道使用标准声道布局，更多声道保留未指定布局；未识别的音频逻辑流返回不支持，不回退到 libavformat；多个受支持音频逻辑流可按音轨序号选择。Vorbis 注释目前只做结构校验，尚未导入文档标签。

Ogg Speex 复用共享 Ogg 页校验与包迭代器，项目解析 Speex 头、注释包、扩展头数量、音频包边界和 granule position；Speex bitstream 解码交给 libavcodec。当前自研路线支持标准 80 字节头、窄带/宽带/超宽带模式、单/双声道及每包 1–64 帧；尾部样本数按最终 granule position 限制。非标准头和未识别的音频逻辑流返回不支持，不回退到 libavformat；多个受支持音频逻辑流可按音轨序号选择；Speex 注释目前只做结构校验，尚未导入文档标签。

DSF 1.0 DSD raw 路线由项目解析 DSD、fmt 和 data chunk，校验格式版本、声道类型、采样频率、位深、采样数和按声道分块的数据长度。适配器按通道组装 planar DSD 包，并剥除尾块填充；DSD 位流解码交给 libavcodec。支持 1-bit LSB-first 与 8-bit MSB-first、通道类型 1–7；ID3v2 标签目前只识别其尾部范围，不解析或导入标签内容。

DSDIFF/DFF 由项目解析 FRM8、FVER、PROP/SND 属性及 DSD/DST 数据块。未压缩 DSD 按文件中的多声道交错字节分包；DST 路线检查首个 FRTE、75 fps 帧率、DSTF 帧数，以及可选 DSTC 块的大小和数量，再逐帧交给 libavcodec 的 DSD/DST 解码器。当前自研路线限制为最多 6 声道；ID3、注释、标记等附加元数据不导入文档标签。

DSS v2/v3 路线由项目解析文件头、512 字节音频块边界及每块 6 字节块头。DSS-SP 的交替 42/40 字节帧由适配器重组为解码器包；G.723.1 路线扫描变长帧边界。语音解码交给 libavcodec，当前两种编码均限于单声道；作者、日期和注释字段暂不导入文档标签。

Matroska/WebM 输入由项目自研的 EBML 解析器读取 DocType、Segment、Info、Tracks、Cluster、Block 和无 lacing、Xiph、固定长度、EBML 四种音频分帧形式，并支持按序号选择音轨。Matroska 的 AAC、ALAC、FLAC、Opus、Vorbis、TTA v1、WavPack A_WAVPACK4、MPEG Layer I/II/III、AC-3（含 BSID9/10）、E-AC-3、ATRAC1、DTS（含 Express/Lossless）、MLP、TrueHD、QDMC、QDM2 及整数 8/16/24/32-bit 和 IEEE 浮点 32/64-bit PCM 包交给 libavcodec；WavPack 支持 1–8 声道、PCM 与 DSD、标准采样率或与轨道一致的自定义采样率；项目校验紧凑主包、PCM/DSD 模式一致性并重建 WavPack block header。hybrid 模式还会由独立解析器校验 BlockAdditional 中的单声道/立体声或多声道 correction block 布局，并将其作为 Matroska packet side data 交给 libavcodec。Matroska A_MS/ACM 的 PCM、IEEE 浮点、G.711 A-law/μ-law、IMA ADPCM、Microsoft ADPCM（包括最多 256 组的自定义系数表）和 MP3 Layer III（WAVE format tag 0x0055）由独立 ACM/WAVEFORMATEX 解析器读取；MP3 数据包再由独立 MPEG 帧校验器验证，压缩帧交给 libavcodec。标准 ADPCM 系数流交给 libavcodec，自定义系数流由项目解码为 S16LE PCM。旧版 A_AAC MPEG2/MPEG4 MAIN、LC、SSR、LTP 及 LC/SBR CodecID 在轨道采样率信息充分时，由项目根据轨道参数构造 AudioSpecificConfig。WebM 自研解复用支持 Opus 和 Vorbis。解析器提取 FLAC STREAMINFO，校验 ALAC cookie、A_MS/ACM ADPCM 块、MP3 帧序列和 TTA 私有头 CRC；显式 Matroska CodecDelay 优先裁掉起始延迟，否则 MP3 的 WAVEFORMATEX nCodecDelay 按采样率换算后用于起始样本裁剪；BlockGroup 的 DiscardPadding 会转为首帧或末帧的样本裁剪元数据。WavPack hybrid 包要求轨道存在 BlockAddIDType=1 的 BlockAdditionMapping，并在 BlockGroup 中恰有一个 BlockAddID=1 correction 项时使用自研容器和附加块解析；每个 BlockAdditions 最多解析 16 个 BlockMore，并保留各自 BlockAddID 与 payload。当前 libavcodec WavPack 解码器不消费 correction side data，输出仍基于有损主包，尚未无损应用 correction 数据。超过该上限或结构异常时返回不支持；其他尚未覆盖的 Matroska/WebM CodecID 返回不支持。

Musepack SV7 与 SV8 由独立解析器处理：SV7 按流头声明的帧数读取位打包边界；帧数为零时，在剔除 APEv2/ID3v1 尾标签后扫描音频区间并推导帧数。解析器同时补齐 libavcodec 所需的四字节帧前缀；SV8 读取 SH、AP、SE 包边界并提取采样率、声道、帧长及样本数；按块长跳过其他扩展块，缺失 SE 时在完整 chunk 边界以 EOF 结束。两种版本的解码均交给 libavcodec；SV7 固定为双声道，SV8 解析 SH 中的 1–16 声道字段。SV8 解析器检查 SH 的 CRC 字段非零但不重新计算 CRC；当前 libavcodec 解码器仅支持单/双声道，超过双声道会在解码阶段失败。

ASF/WMA 路线由项目解析 Header、File Properties、Stream Properties、Data Object 及数据包和负载边界，支持按序号选择音频流、跨包媒体对象重组、压缩负载拆包和 Spread 错误保护去交错。WMA Voice、WMA v1/v2、WMA Pro、WMA Lossless、XMA1/XMA2 压缩包交给 libavcodec 解码；加密流、未知 WMA 标签及未覆盖的错误保护布局返回不支持。

TAK 路线由项目自研解析元数据块、StreamInfo 和 CRC，并按 Last Frame 信息或 APEv2/ID3v1 尾标记确定音频范围；帧迭代器校验 TAK 帧头 CRC 和连续帧号，形成完整压缩帧后交给 libavcodec。当前支持 8/16/24-bit、1–6 声道的 StreamInfo；帧内 metadata 标记及与 StreamInfo 不一致的帧头信息返回不支持，不回退到 libavformat。

上述自研解析路线不经过 libavformat 输入 demuxer。VOC Type 1 支持旧式 U8 PCM（没有前置 Type 8 时为单声道，带前置 Type 8 时支持单/双声道）及单声道 Sound Blaster Pro 4/3/2-bit ADPCM；Type 2 支持紧跟在 Type 1/续块后的 U8 或 ADPCM 续块；Type 3 支持单声道 U8 静音段；Type 9 支持 U8、S16LE、G.711 A-law/μ-law、单声道 Sound Blaster Pro ADPCM 标签 1–3，以及单/双声道 16-bit ADPCM_CT 标签 `0x0200`。SBPro 首包包含一个初始样本，Type 2 续块按编码模式计算样本数；ADPCM_CT 不含初始样本，单声道每字节解码两个样本，双声道每字节解码一个样本/声道。Type 9 的 SBPro ADPCM 使用 8-bit sample depth。Type 6/7 有限循环由自研控制块解析器扩展播放顺序，最多支持 16 层嵌套；空的有限重复段按零样本处理；不含 SBPro 初始化样本的有限 ADPCM 循环由项目按块序列重放，解码器延续 ADPCM 状态；含初始化样本的重复段、无限循环、立体声 SBPro ADPCM 和其他 VOC 编码返回不支持。CAF Apple IMA4 固定包序列（按 `pakt` 有效帧数裁剪）、AAC Main/LC/SSR/LTP 声道配置 1–7 与 PCE、AAC-LD (`aacl`)、单/双声道 ALAC 子集、使用常量 `pakt` 的 G.711、MACE3/MACE6、Apple GSM (`agsm`)、iLBC (`ilbc`)、AMR-NB (`samr`)、AC-3 (`ac-3`)、QDMC/QDM2 与 QCELP (`Qclp`) 子集，以及 `.mp1`/`.mp2`/`.mp3` 和兼容 `ms\0U` 标签的 MPEG Layer I/II/III 包序列由项目解析并直接送入相应解码器；其他 AAC 变体及其他 CAF 编码返回不支持。M4A 的选定音轨、单个或多个等价 sample description、`stsz`/`stz2` sample size table、渐进式 AAC/ALAC 子集由项目解析；支持一个或多个非空、正向、1 倍速媒体 edit entry；媒体区间连续的多段 edit 可合并为采样点裁剪，恒定 composition offset 可与 edit entry 合并处理；无 edit list 的渐进式路线可使用逐 sample composition offset；分片路线已由项目解析 `trex`、`tfhd`、`tfdt`、`trun` 并验证 `mdat` 样本范围。当前不支持分片 edit list、加密样本、无法确定基准偏移的多轨片段、空 edit、媒体区间不连续的多段或变速 edit、带 edit list 的变动 composition offset、彼此不等价的 sample description 及未覆盖的编码变体返回不支持。其他输入包括未覆盖的 WAVE/AIFF 编码、加密或未覆盖的 WMA/ASF 变体、Matroska 未覆盖的编码、未覆盖的 DTS-HD ExSS 排布、加密 TTA、未覆盖的 WavPack 变体，以及未覆盖的 VOC 块类型、WEBA 等已登记变体；这些输入返回不支持；不满足上述 Ogg 自研子集的流返回不支持，不回退到 libavformat。

已登记的音频输出包括：

- MP2、MP3、FLAC、Ogg FLAC；
- AAC/ADTS、M4A/AAC、M4A/ALAC、M4B；
- WAV、AIFF、CAF 的 16/24/32-bit PCM；
- OGG、Opus、Speex、WebM/Opus、WebA；
- WMA/ASF、WavPack、TTA、Matroska/FLAC；
- AC-3、E-AC-3、AMR-NB、AU、VOC、Wave64。

编码格式可能限制声道数、采样率、位深和容器。例如 AMR-NB 只输出单声道 8 kHz；Speex 仅接受指定采样率及单/双声道配置；M4B 输出 AAC/MP4，不生成章节。具体支持取决于目标编码器和 muxer 是否编入程序。

默认选择后端判定的最佳音轨。可用 --audio-track N 选择从 1 开始计数的音轨。部分容器可保留标签、首个 JPEG/PNG 封面或章节；封面和章节映射并非所有目标格式都支持。

## 加密音乐

| 容器 | 当前能力 | 限制与所需信息 |
|---|---|---|
| NCM | 解密后读取常见标题、艺术家、专辑和封面，再进入音频路线。 | 解码及输出受音频后端能力限制。 |
| QMC | 支持 QMC v1、带内嵌 EKey 的 QTag/PcV1Legacy，以及通过 --ekey 提供密钥的 STag/MusicEx。 | STag/MusicEx 需要有权使用且与歌曲匹配的 EKey；部分场景可通过 --ekey-db 指定 player_process_db。 |
| KGM/KGMA/VPR | v3/v4 使用随程序提供的公钥，也可通过 --kgm-key 指定；v5 使用匹配歌曲 EKey，或查询 KGMusicV3.db。 | v5 仅适用于本地数据库中已有密钥的歌曲；可用 --kgm-db 指定数据库。 |
| KWM | 支持旧版 KWM 解密后转码。 | 新版 KWM 不支持；文件 API 依赖扩展名识别。 |

密钥参数见[命令行使用](../usage/command-line.md)。

## MPEG-1 WAVE 音频

WAVE format tag `0x0050`（`MPEG1WAVEFORMAT`）现在由独立的格式描述符解析器和帧序列解析器处理，RIFF、RIFX、RF64、BW64 与 Wave64 共用这条解析路径。支持单独声明的 MPEG Layer I、II 或 III、单/双声道、标准表中的可变码率、可选 `fact` 样本数，以及 `nBlockAlign=1` 的变长帧或固定长度帧；`nSamplesPerSec=0` 时由帧头提供采样率，但同一数据流中的帧必须保持一致。混合 Layer 流、变采样率流和 free-format/非标准码率不在当前解码子集中。MPEG 压缩帧交给 libavcodec。

WAVE format tag `0x0031`（`WAVE_FORMAT_GSM610`）由独立的 `WAVEFORMATEX` 描述符解析器和 GSM 数据块解析器处理，支持 RIFF、RF64、BW64 与 Wave64 的小端格式、单声道、65 字节编码块和每块 320 个采样；`fact` 样本数只可裁剪最后一个块。采样率、平均字节率、`nBlockAlign`、`wBitsPerSample`、扩展长度和 `wSamplesPerBlock` 均按描述符校验，编码块交给 libavcodec 的 Microsoft GSM 解码器。RIFX 和不符合此块布局的 GSM 数据暂不在自研子集中。

WAVE format tag `0x0008`（`WAVE_FORMAT_DTS`）由独立的 WAVE 描述符解析器读取 `WAVEFORMATEX`，再将 `data` 内容交给项目自研 DTS 帧解析器；RIFF、RIFX、RF64、BW64 和 Wave64 的容器字段按各自字节序读取。描述符采样率和声道数必须与 DTS 帧一致，可选 `fact` 样本数只可裁剪最后一个 DTS 帧；帧交给 libavcodec 解码。带 IEC 61937 填充的 burst 数据不属于此 raw-DTS 子集。

Matroska `A_MS/ACM` 的 tag `0x0050` 复用同一格式描述符，按声明层映射到 MP1/MP2/MP3，并由独立的数据包校验器确认实际帧的层、采样率、声道数和 MPEG-1 版本。WAVEFORMATEX 未固定采样率且 Matroska `SamplingFrequency` 未提供时，该轨道返回不支持。
