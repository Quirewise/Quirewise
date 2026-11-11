#ifndef QUIREWISE_APP_SUBTITLE_ROUTES_H
#define QUIREWISE_APP_SUBTITLE_ROUTES_H

#include <quirewise/convert.h>

#include <stddef.h>
#include <stdint.h>

/* Convert a subtitle file (SRT/VTT/LRC/ASS/SSA/SAMI/MicroDVD/SCC) to PDF
 * through the shared HTML layout writer. Returns QW_STATUS_ERR_UNSUPPORTED
 * when the extension is not a supported subtitle format. */
int qw_app_subtitle_convert_file(const char *path,
                                 uint8_t **out_pdf, size_t *out_size,
                                 QwConvertReport *report);

#endif
