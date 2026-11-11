#ifndef QUIREWISE_APP_COMIC_ROUTES_H
#define QUIREWISE_APP_COMIC_ROUTES_H

#include <quirewise/convert.h>

#include <stddef.h>
#include <stdint.h>

/* Convert a CBZ (ZIP) or CBT (USTAR) comic archive to a multi-page PDF.
 * Returns QW_STATUS_ERR_UNSUPPORTED for other extensions or archives that
 * do not open as comic containers. */
int qw_app_comic_convert_file(const char *path,
                              uint8_t **out_pdf, size_t *out_size,
                              QwConvertReport *report);

#endif
