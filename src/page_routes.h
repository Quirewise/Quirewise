#ifndef QUIREWISE_APP_PAGE_ROUTES_H
#define QUIREWISE_APP_PAGE_ROUTES_H

#include <quirewise/convert.h>

#include <stddef.h>
#include <stdint.h>

#include "app_options.h"

/* Convert a page-family input (DjVu, PDG/PDZ, UVZ, CAJ, CEB) to PDF.
 * Returns QW_STATUS_ERR_UNSUPPORTED when the bytes are not one of those
 * formats. On success *out_pdf is malloc-owned (release with qw_buffer_free). */
int qw_app_page_convert(const uint8_t *data, size_t size,
                        const QwAppOptions *options,
                        uint8_t **out_pdf, size_t *out_size,
                        QwConvertReport *report);

/* Read a file and convert it through qw_app_page_convert. */
int qw_app_page_convert_file(const char *path,
                             const QwAppOptions *options,
                             uint8_t **out_pdf, size_t *out_size,
                             QwConvertReport *report);

#endif
