#include "audio_check.h"

#include <quirewise/audio.h>
#include <quirewise/status.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define QW_AUDIO_CHECK_MAX_INPUT (512u * 1024u * 1024u)
#define QW_AUDIO_CHECK_MAX_PACKETS 2000000u

static int audio_iequals(const char *left, const char *right)
{
    size_t index = 0u;
    while (left[index] && right[index]) {
        char a = left[index];
        char b = right[index];
        if (a >= 'A' && a <= 'Z') a = (char)(a - 'A' + 'a');
        if (b >= 'A' && b <= 'Z') b = (char)(b - 'A' + 'a');
        if (a != b) return 0;
        ++index;
    }
    return left[index] == '\0' && right[index] == '\0';
}

static int audio_extension_format(const char *path, QwAudioInputFormat *out)
{
    const char *dot = strrchr(path, '.');
    if (!dot) return 0;
    ++dot;
    if (audio_iequals(dot, "wav") || audio_iequals(dot, "wave")) {
        *out = QW_AUDIO_INPUT_WAV;
    } else if (audio_iequals(dot, "w64")) {
        *out = QW_AUDIO_INPUT_W64;
    } else if (audio_iequals(dot, "aif") || audio_iequals(dot, "aiff") ||
               audio_iequals(dot, "aifc")) {
        *out = QW_AUDIO_INPUT_AIFF;
    } else if (audio_iequals(dot, "caf")) {
        *out = QW_AUDIO_INPUT_CAF;
    } else if (audio_iequals(dot, "dsf")) {
        *out = QW_AUDIO_INPUT_DSF;
    } else if (audio_iequals(dot, "dff")) {
        *out = QW_AUDIO_INPUT_DFF;
    } else if (audio_iequals(dot, "dss")) {
        *out = QW_AUDIO_INPUT_DSS;
    } else if (audio_iequals(dot, "m4a") || audio_iequals(dot, "m4b") ||
               audio_iequals(dot, "mp4")) {
        *out = QW_AUDIO_INPUT_M4A;
    } else if (audio_iequals(dot, "mka") || audio_iequals(dot, "mkv")) {
        *out = QW_AUDIO_INPUT_MATROSKA;
    } else if (audio_iequals(dot, "webm")) {
        *out = QW_AUDIO_INPUT_WEBM;
    } else if (audio_iequals(dot, "mpc")) {
        *out = QW_AUDIO_INPUT_MPC;
    } else if (audio_iequals(dot, "wma") || audio_iequals(dot, "asf")) {
        *out = QW_AUDIO_INPUT_WMA;
    } else if (audio_iequals(dot, "au") || audio_iequals(dot, "snd")) {
        *out = QW_AUDIO_INPUT_AU;
    } else if (audio_iequals(dot, "aac") || audio_iequals(dot, "adts")) {
        *out = QW_AUDIO_INPUT_AAC;
    } else if (audio_iequals(dot, "flac")) {
        *out = QW_AUDIO_INPUT_FLAC;
    } else if (audio_iequals(dot, "mp2")) {
        *out = QW_AUDIO_INPUT_MP2;
    } else if (audio_iequals(dot, "mp3")) {
        *out = QW_AUDIO_INPUT_MP3;
    } else if (audio_iequals(dot, "amr")) {
        *out = QW_AUDIO_INPUT_AMR;
    } else if (audio_iequals(dot, "ac3")) {
        *out = QW_AUDIO_INPUT_AC3;
    } else if (audio_iequals(dot, "dts")) {
        *out = QW_AUDIO_INPUT_DTS;
    } else if (audio_iequals(dot, "tta")) {
        *out = QW_AUDIO_INPUT_TTA;
    } else if (audio_iequals(dot, "tak")) {
        *out = QW_AUDIO_INPUT_TAK;
    } else if (audio_iequals(dot, "wv")) {
        *out = QW_AUDIO_INPUT_WAVPACK;
    } else if (audio_iequals(dot, "voc")) {
        *out = QW_AUDIO_INPUT_VOC;
    } else if (audio_iequals(dot, "ape")) {
        *out = QW_AUDIO_INPUT_APE;
    } else if (audio_iequals(dot, "ogg") || audio_iequals(dot, "oga") ||
               audio_iequals(dot, "opus")) {
        *out = QW_AUDIO_INPUT_OGG;
    } else {
        return 0;
    }
    return 1;
}

static int audio_magic_formats(const uint8_t *data, size_t size,
                               QwAudioInputFormat *formats, size_t capacity)
{
    size_t count = 0u;
#define ADD(fmt) do { if (count < capacity) formats[count++] = (fmt); } while (0)
    if (size >= 12u && memcmp(data, "RIFF", 4u) == 0 &&
        memcmp(data + 8u, "WAVE", 4u) == 0)
        ADD(QW_AUDIO_INPUT_WAV);
    if (size >= 4u && memcmp(data, "fLaC", 4u) == 0) ADD(QW_AUDIO_INPUT_FLAC);
    if (size >= 4u && memcmp(data, "OggS", 4u) == 0) ADD(QW_AUDIO_INPUT_OGG);
    if (size >= 3u && memcmp(data, "ID3", 3u) == 0) ADD(QW_AUDIO_INPUT_MP3);
    if (size >= 2u && data[0] == 0xFFu &&
        (data[1] == 0xFBu || data[1] == 0xFAu || data[1] == 0xF3u ||
         data[1] == 0xF2u))
        ADD(QW_AUDIO_INPUT_MP3);
    if (size >= 12u && memcmp(data, "FORM", 4u) == 0 &&
        (memcmp(data + 8u, "AIFF", 4u) == 0 ||
         memcmp(data + 8u, "AIFC", 4u) == 0))
        ADD(QW_AUDIO_INPUT_AIFF);
    if (size >= 4u && memcmp(data, "caff", 4u) == 0) ADD(QW_AUDIO_INPUT_CAF);
    if (size >= 8u && memcmp(data + 4u, "ftyp", 4u) == 0)
        ADD(QW_AUDIO_INPUT_M4A);
    if (size >= 4u && data[0] == 0x1Au && data[1] == 0x45u &&
        data[2] == 0xDFu && data[3] == 0xA3u)
        ADD(QW_AUDIO_INPUT_MATROSKA);
#undef ADD
    return (int)count;
}

static int audio_scan(const uint8_t *data, size_t size,
                      QwAudioInputFormat format, size_t audio_track,
                      QwConvertReport *report)
{
    QwAudioReader *reader = NULL;
    QwAudioStatus status;
    QwAudioInfo info;
    size_t packets = 0u;
    int packet_route_missing = 0;

    status = qw_audio_reader_open(data, size, format, audio_track, &reader);
    if (status != QW_AUDIO_OK || !reader) return 0;
    memset(&info, 0, sizeof(info));
    if (report && qw_audio_reader_get_info(reader, &info) == QW_AUDIO_OK) {
        const char *codec = qw_audio_codec_name(info.codec);
        snprintf(report->note, sizeof(report->note),
                 "%s, %u Hz, %u ch", codec ? codec : "unknown codec",
                 info.sample_rate, (unsigned)info.channels);
    }
    for (;;) {
        QwAudioPacket packet;
        memset(&packet, 0, sizeof(packet));
        status = qw_audio_reader_next_packet(reader, &packet);
        if (status == QW_AUDIO_END) break;
        if (status == QW_AUDIO_UNSUPPORTED) {
            /* PCM/raw containers parse but do not expose a packet stream. */
            packet_route_missing = 1;
            break;
        }
        if (status != QW_AUDIO_OK) {
            qw_audio_reader_close(reader);
            return 0;
        }
        if (++packets > QW_AUDIO_CHECK_MAX_PACKETS) {
            qw_audio_reader_close(reader);
            return 0;
        }
    }
    qw_audio_reader_close(reader);
    if (report) {
        if (packet_route_missing && packets == 0u) {
            snprintf(report->note, sizeof(report->note),
                     "audio container parsed; this route exposes no packets "
                     "(PCM samples are raw)");
        } else {
            snprintf(report->note, sizeof(report->note),
                     "audio stream scanned: %zu packet(s)", packets);
        }
    }
    return 1;
}

int qw_app_audio_check_file(const char *path, size_t audio_track,
                            QwConvertReport *report)
{
    FILE *file;
    long length;
    uint8_t *data;
    QwAudioInputFormat format = QW_AUDIO_INPUT_WAV;
    QwAudioInputFormat candidates[8];
    int candidate_count = 0;
    int recognized;
    int index;
    int ok = 0;

    if (!path) return QW_STATUS_ERR_INVALID_ARGUMENT;
    file = fopen(path, "rb");
    if (!file) return QW_STATUS_ERR_IO;
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return QW_STATUS_ERR_IO;
    }
    if ((unsigned long)length > (unsigned long)QW_AUDIO_CHECK_MAX_INPUT) {
        fclose(file);
        return QW_STATUS_ERR_RESOURCE_LIMIT;
    }
    data = (uint8_t *)malloc((size_t)length ? (size_t)length : 1u);
    if (!data) {
        fclose(file);
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    }
    if (length > 0 &&
        fread(data, 1u, (size_t)length, file) != (size_t)length) {
        free(data);
        fclose(file);
        return QW_STATUS_ERR_IO;
    }
    fclose(file);

    recognized = audio_extension_format(path, &format);
    if (recognized)
        ok = audio_scan(data, (size_t)length, format, audio_track, report);
    if (!ok) {
        candidate_count = audio_magic_formats(data, (size_t)length, candidates,
                                              8u);
        for (index = 0; index < candidate_count && !ok; ++index) {
            if (recognized && candidates[index] == format) continue;
            ok = audio_scan(data, (size_t)length, candidates[index],
                            audio_track, report);
        }
    }
    free(data);
    if (!ok) {
        if (report) snprintf(report->note, sizeof(report->note),
                             "input is not a supported audio container");
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    return QW_STATUS_OK;
}
