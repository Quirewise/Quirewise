#ifndef QUIREWISE_APP_AUDIO_CHECK_H
#define QUIREWISE_APP_AUDIO_CHECK_H

#include <quirewise/convert.h>

/* Scan an audio container with the packet reader (no decode).
 * Returns QW_STATUS_OK when the stream was read to the end, or
 * QW_STATUS_ERR_UNSUPPORTED when the file is not a supported audio input. */
int qw_app_audio_check_file(const char *path, size_t audio_track,
                            QwConvertReport *report);

#endif
